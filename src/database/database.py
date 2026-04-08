"""数据库操作封装模块"""

import hashlib
import json
import os
import sqlite3
import traceback
import mysql.connector
from mysql.connector import Error
from colorama import Fore, init

try:
    import psycopg2
    from psycopg2 import Error as PsycopgError
    from psycopg2.extras import RealDictCursor
except Exception:
    psycopg2 = None
    PsycopgError = None
    RealDictCursor = None

from src.core.config import CONFIG

# 获取项目根目录
# database.py在src/database/，需要向上3层到项目根
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 数据库文件路径
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'chat_history.db')


def get_engine() -> str:
    """Return configured database engine type, defaulting to mysql."""
    db_cfg = CONFIG.get('database', {}) if isinstance(CONFIG, dict) else {}
    return str(db_cfg.get('engine') or 'mysql').strip().lower()


def get_connection():
    """获取数据库连接
    
    Returns:
        mysql.connector.connection.MySQLConnection: 数据库连接对象
    """
    db_cfg = CONFIG.get('database', {}) if isinstance(CONFIG, dict) else {}
    engine = get_engine()
    try:
        if engine in ('sqlite', 'sqlite3'):
            sqlite_path = str(db_cfg.get('sqlite_path') or DB_PATH)
            sqlite_abs = sqlite_path if os.path.isabs(sqlite_path) else os.path.join(PROJECT_ROOT, sqlite_path)
            os.makedirs(os.path.dirname(sqlite_abs), exist_ok=True)
            connection = sqlite3.connect(sqlite_abs)
            connection.row_factory = sqlite3.Row
            return connection

        if engine in ('postgres', 'postgresql'):
            if psycopg2 is None:
                raise RuntimeError('PostgreSQL driver psycopg2 is not installed.')
            connection = psycopg2.connect(
                host=db_cfg.get('host', '127.0.0.1'),
                user=db_cfg.get('user', 'postgres'),
                password=db_cfg.get('password', ''),
                dbname=db_cfg.get('database', 'shizuku_nya_bot'),
                port=int(db_cfg.get('port', 5432))
            )
            return connection

        connection = mysql.connector.connect(
            host=db_cfg.get('host', '127.0.0.1'),
            user=db_cfg.get('user', 'root'),
            password=db_cfg.get('password', ''),
            database=db_cfg.get('database', 'shizuku_nya_bot'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return connection
    except Exception as e:
        print(Fore.RED + f"数据库连接错误: {e}")
        return None


def table_exists(cursor, table_name, engine='mysql'):
    """检查表是否存在
    
    Args:
        cursor: 数据库游标
        table_name (str): 表名
        
    Returns:
        bool: 表存在返回True，否则返回False
    """
    if engine in ('postgres', 'postgresql'):
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            (table_name,)
        )
        row = cursor.fetchone()
        return bool(row[0]) if row else False

    if engine in ('sqlite', 'sqlite3'):
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None

    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


class DatabaseManager:
    """数据库管理器类，用于处理与MySQL数据库的连接和操作"""

    CONNECTION_FACTORIES = {}
    CACHE_PROVIDERS = {}

    @classmethod
    def register_connection_factory(cls, engine, factory):
        """注册自定义连接工厂，供插件/未来扩展接管连接逻辑。"""
        if not engine or not callable(factory):
            return
        cls.CONNECTION_FACTORIES[str(engine).strip().lower()] = factory

    @classmethod
    def register_cache_provider(cls, engine, provider):
        """注册缓存Provider（如Redis），用于替代repo_context_cache表。"""
        if not engine or provider is None:
            return
        cls.CACHE_PROVIDERS[str(engine).strip().lower()] = provider

    def __init__(self):
        """初始化数据库连接"""
        # 初始化 colorama
        init(autoreset=True)

        self.engine = get_engine()
        self._hooks = {
            'on_connect': [],
            'before_execute': [],
            'after_execute': [],
            'on_error': [],
        }

        try:
            factory = self.CONNECTION_FACTORIES.get(self.engine)
            if callable(factory):
                self.connection = factory(CONFIG)
            else:
                self.connection = get_connection()

            if self.connection is None:
                raise RuntimeError('数据库连接为空。')
            self._emit_hook('on_connect', engine=self.engine)
        except Exception as e:
            print(Fore.RED + f"数据库连接错误: {e}")
            raise

        self.cache_provider = self.CACHE_PROVIDERS.get(self.engine)

        self._ensure_chat_history_persona_column()
        self._ensure_repo_context_cache_table()
        self._repo_cache_write_count = 0

    def register_hook(self, event_name, callback):
        """注册数据库生命周期钩子，供插件扩展（审计、路由、熔断等）。"""
        if event_name not in self._hooks or not callable(callback):
            return False
        self._hooks[event_name].append(callback)
        return True

    def get_engine_name(self):
        return self.engine

    def has_cache_provider(self):
        return self.cache_provider is not None

    def _emit_hook(self, event_name, **kwargs):
        for cb in self._hooks.get(event_name, []):
            try:
                cb(self, **kwargs)
            except Exception:
                pass

    def _new_cursor(self, dictionary=False):
        if self.engine in ('postgres', 'postgresql'):
            if dictionary and RealDictCursor is not None:
                return self.connection.cursor(cursor_factory=RealDictCursor)
            return self.connection.cursor()
        if self.engine in ('sqlite', 'sqlite3'):
            return self.connection.cursor()
        if dictionary:
            return self.connection.cursor(dictionary=True)
        return self.connection.cursor()

    def _adapt_query_for_engine(self, query):
        if self.engine in ('sqlite', 'sqlite3'):
            return query.replace('%s', '?')
        return query

    def _execute(self, cursor, query, params=None):
        query = self._adapt_query_for_engine(query)
        self._emit_hook('before_execute', engine=self.engine, query=query, params=params)
        try:
            if params is None:
                cursor.execute(query)
            else:
                cursor.execute(query, params)
            self._emit_hook('after_execute', engine=self.engine, query=query, params=params)
        except Exception as e:
            self._emit_hook('on_error', engine=self.engine, query=query, params=params, error=e)
            raise

    def _table_exists(self, cursor, table_name):
        return table_exists(cursor, table_name, engine=self.engine)

    def _column_exists(self, cursor, table_name, column_name):
        if self.engine in ('postgres', 'postgresql'):
            self._execute(
                cursor,
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
                )
                """,
                (table_name, column_name)
            )
            row = cursor.fetchone()
            return bool(row[0]) if row else False

        self._execute(cursor, f"SHOW COLUMNS FROM {table_name} LIKE %s", (column_name,))
        return cursor.fetchone() is not None

    def _ensure_chat_history_persona_column(self):
        """确保 chat_history 存在 persona_filename 列，用于多角色卡隔离历史。"""
        cursor = None
        try:
            cursor = self._new_cursor()
            if not self._table_exists(cursor, 'chat_history'):
                return
            exists = self._column_exists(cursor, 'chat_history', 'persona_filename')
            if not exists:
                self._execute(cursor, "ALTER TABLE chat_history ADD COLUMN persona_filename VARCHAR(120) NULL DEFAULT NULL")
                self.connection.commit()
        except Exception as e:
            print(f"确保 persona_filename 列时出错: {e}")
        finally:
            if cursor:
                cursor.close()

    def _ensure_repo_context_cache_table(self):
        """确保 repo_context_cache 表存在，用于复用仓库检索结果，减少上下文与token消耗。"""
        if self.cache_provider is not None:
            return
        cursor = None
        try:
            cursor = self._new_cursor()
            if self.engine in ('postgres', 'postgresql'):
                self._execute(
                    cursor,
                    """
                    CREATE TABLE IF NOT EXISTS repo_context_cache (
                        id BIGSERIAL PRIMARY KEY,
                        query_hash VARCHAR(64) NOT NULL,
                        query_text TEXT,
                        persona_filename VARCHAR(120) NULL,
                        payload_json TEXT,
                        hit_count INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_hit_at TIMESTAMP NULL
                    )
                    """
                )
                self._execute(cursor, "CREATE INDEX IF NOT EXISTS idx_repo_ctx_query_hash ON repo_context_cache (query_hash)")
                self._execute(cursor, "CREATE INDEX IF NOT EXISTS idx_repo_ctx_persona ON repo_context_cache (persona_filename)")
            else:
                create_sql = (
                    """
                    CREATE TABLE IF NOT EXISTS repo_context_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query_hash TEXT NOT NULL,
                        query_text TEXT,
                        persona_filename TEXT NULL,
                        payload_json TEXT,
                        hit_count INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_hit_at TIMESTAMP NULL
                    )
                    """
                    if self.engine in ('sqlite', 'sqlite3') else
                    """
                    CREATE TABLE IF NOT EXISTS repo_context_cache (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        query_hash VARCHAR(64) NOT NULL,
                        query_text TEXT,
                        persona_filename VARCHAR(120) NULL,
                        payload_json LONGTEXT,
                        hit_count INT NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        last_hit_at TIMESTAMP NULL,
                        INDEX idx_query_hash (query_hash),
                        INDEX idx_persona (persona_filename)
                    )
                    """
                )
                self._execute(
                    cursor,
                    create_sql
                )
                if self.engine in ('sqlite', 'sqlite3'):
                    self._execute(cursor, "CREATE INDEX IF NOT EXISTS idx_query_hash ON repo_context_cache (query_hash)")
                    self._execute(cursor, "CREATE INDEX IF NOT EXISTS idx_persona ON repo_context_cache (persona_filename)")

            # 兼容已有表：缺列时补齐。
            if not self._column_exists(cursor, 'repo_context_cache', 'hit_count'):
                self._execute(cursor, "ALTER TABLE repo_context_cache ADD COLUMN hit_count INT NOT NULL DEFAULT 0")

            if not self._column_exists(cursor, 'repo_context_cache', 'updated_at'):
                self._execute(cursor, "ALTER TABLE repo_context_cache ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

            if not self._column_exists(cursor, 'repo_context_cache', 'last_hit_at'):
                self._execute(cursor, "ALTER TABLE repo_context_cache ADD COLUMN last_hit_at TIMESTAMP NULL")

            self.connection.commit()
        except Exception as e:
            print(f"确保 repo_context_cache 表时出错: {e}")
        finally:
            if cursor:
                cursor.close()

    def _touch_repo_context_cache_hit(self, cache_id):
        if self.cache_provider is not None:
            method = getattr(self.cache_provider, 'touch_repo_context_cache_hit', None)
            if callable(method):
                try:
                    method(cache_id)
                except Exception:
                    pass
            return
        cursor = None
        try:
            cursor = self._new_cursor()
            self._execute(
                cursor,
                """
                UPDATE repo_context_cache
                SET hit_count = hit_count + 1, last_hit_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (cache_id,)
            )
            self.connection.commit()
        except Exception:
            pass
        finally:
            if cursor:
                cursor.close()

    def _prune_repo_context_cache(self, max_rows=2000):
        """裁剪缓存表，保留最近且更常用的记录。"""
        if self.cache_provider is not None:
            method = getattr(self.cache_provider, 'prune_repo_context_cache', None)
            if callable(method):
                try:
                    method(max_rows=max_rows)
                except Exception:
                    pass
            return
        cursor = None
        try:
            cursor = self._new_cursor()
            if not self._table_exists(cursor, 'repo_context_cache'):
                return

            self._execute(cursor, "SELECT COUNT(1) FROM repo_context_cache")
            row = cursor.fetchone()
            total = int(row[0]) if row else 0
            if total <= max_rows:
                return

            to_delete = total - max_rows
            if self.engine in ('postgres', 'postgresql'):
                self._execute(
                    cursor,
                    """
                    DELETE FROM repo_context_cache
                    WHERE id IN (
                        SELECT id
                        FROM repo_context_cache
                        ORDER BY hit_count ASC, COALESCE(last_hit_at, created_at) ASC
                        LIMIT %s
                    )
                    """,
                    (to_delete,)
                )
            else:
                self._execute(
                    cursor,
                    """
                    DELETE FROM repo_context_cache
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id
                            FROM repo_context_cache
                            ORDER BY hit_count ASC, COALESCE(last_hit_at, created_at) ASC
                            LIMIT %s
                        ) AS t
                    )
                    """,
                    (to_delete,)
                )
            self.connection.commit()
        except Exception:
            pass
        finally:
            if cursor:
                cursor.close()

    @staticmethod
    def _safe_json_loads(text, default_value):
        try:
            if text:
                return json.loads(text)
        except Exception:
            pass
        return default_value

    def get_repo_context_cache(self, query_text, persona_filename=None):
        """按 query 精确命中仓库上下文缓存，未命中时返回 None。"""
        if self.cache_provider is not None:
            method = getattr(self.cache_provider, 'get_repo_context_cache', None)
            if callable(method):
                try:
                    return method(query_text=query_text, persona_filename=persona_filename)
                except Exception as e:
                    print(f"读取插件缓存错误: {e}")
            return None
        cursor = None
        try:
            q = str(query_text or '').strip()
            if not q:
                return None

            cursor = self._new_cursor()
            if not self._table_exists(cursor, 'repo_context_cache'):
                return None

            q_hash = hashlib.sha1(q.lower().encode('utf-8', errors='ignore')).hexdigest()
            if persona_filename:
                self._execute(
                    cursor,
                    """
                    SELECT id, payload_json FROM repo_context_cache
                    WHERE query_hash = %s AND (persona_filename = %s OR persona_filename IS NULL)
                    ORDER BY hit_count DESC, id DESC LIMIT 1
                    """,
                    (q_hash, persona_filename)
                )
            else:
                self._execute(
                    cursor,
                    """
                    SELECT id, payload_json FROM repo_context_cache
                    WHERE query_hash = %s
                    ORDER BY hit_count DESC, id DESC LIMIT 1
                    """,
                    (q_hash,)
                )

            row = cursor.fetchone()
            if not row:
                # 轻量模糊回退：同 persona 下按 query 前缀匹配最新热点缓存。
                prefix = q[:24]
                if prefix:
                    like_prefix = f"{prefix}%"
                    if persona_filename:
                        self._execute(
                            cursor,
                            """
                            SELECT id, payload_json FROM repo_context_cache
                            WHERE (persona_filename = %s OR persona_filename IS NULL) AND query_text LIKE %s
                            ORDER BY hit_count DESC, id DESC LIMIT 1
                            """,
                            (persona_filename, like_prefix)
                        )
                    else:
                        self._execute(
                            cursor,
                            """
                            SELECT id, payload_json FROM repo_context_cache
                            WHERE query_text LIKE %s
                            ORDER BY hit_count DESC, id DESC LIMIT 1
                            """,
                            (like_prefix,)
                        )
                    row = cursor.fetchone()

            if not row:
                return None

            cache_id, payload_text = row[0], row[1]
            self._touch_repo_context_cache_hit(cache_id)
            return self._safe_json_loads(payload_text, None)
        except Exception as e:
            print(f"读取 repo_context_cache 错误: {e}")
            return None
        finally:
            if cursor:
                cursor.close()

    def save_repo_context_cache(self, query_text, payload, persona_filename=None):
        """保存仓库检索结果，供后续同类请求复用。"""
        if self.cache_provider is not None:
            method = getattr(self.cache_provider, 'save_repo_context_cache', None)
            if callable(method):
                try:
                    method(query_text=query_text, payload=payload, persona_filename=persona_filename)
                except Exception as e:
                    print(f"保存插件缓存错误: {e}")
            return
        cursor = None
        try:
            q = str(query_text or '').strip()
            if not q or not isinstance(payload, dict):
                return

            cursor = self._new_cursor()
            if not self._table_exists(cursor, 'repo_context_cache'):
                return

            q_hash = hashlib.sha1(q.lower().encode('utf-8', errors='ignore')).hexdigest()
            payload_text = json.dumps(payload, ensure_ascii=False)

            # 去重更新：同 query_hash + persona 优先更新，避免无上限重复插入。
            if persona_filename:
                self._execute(
                    cursor,
                    """
                    SELECT id FROM repo_context_cache
                    WHERE query_hash = %s AND persona_filename = %s
                    ORDER BY id DESC LIMIT 1
                    """,
                    (q_hash, persona_filename)
                )
            else:
                self._execute(
                    cursor,
                    """
                    SELECT id FROM repo_context_cache
                    WHERE query_hash = %s AND persona_filename IS NULL
                    ORDER BY id DESC LIMIT 1
                    """,
                    (q_hash,)
                )

            row = cursor.fetchone()
            if row:
                self._execute(
                    cursor,
                    """
                    UPDATE repo_context_cache
                    SET query_text = %s, payload_json = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (q[:1024], payload_text, row[0])
                )
            else:
                self._execute(
                    cursor,
                    """
                    INSERT INTO repo_context_cache (query_hash, query_text, persona_filename, payload_json)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (q_hash, q[:1024], persona_filename, payload_text)
                )

            self.connection.commit()

            self._repo_cache_write_count += 1
            if self._repo_cache_write_count % 20 == 0:
                self._prune_repo_context_cache(max_rows=2000)
        except Exception as e:
            print(f"保存 repo_context_cache 错误: {e}")
        finally:
            if cursor:
                cursor.close()

    def get_character_info(self):
        """获取角色信息
        
        Returns:
            dict: 包含角色信息的字典
        """
        try:
            cursor = self._new_cursor(dictionary=True)
            if self._table_exists(cursor, 'character_info'):
                # 获取第一条记录，而不是特定名称的记录
                self._execute(cursor, "SELECT * FROM character_info LIMIT 1")
                result = cursor.fetchone()
                # 如果数据库中没有角色信息，则使用配置文件中的默认值
                return result if result else CONFIG['character']
            else:
                # 表不存在时使用配置文件中的默认值
                return CONFIG['character']
        except Exception as e:
            print(Fore.RED + f"获取角色信息错误: {e}")
            # 出现异常时使用配置文件中的默认值
            return CONFIG['character']
        finally:
            if 'cursor' in locals():
                cursor.close()

    def save_chat(self, user_input, ai_response, image_description=None, persona_filename=None):
        """保存对话记录，包括图片描述

        Args:
            user_input (str): 用户输入
            ai_response (str): AI回复
            image_description (str, optional): 图片描述
        """
        cursor = None
        try:
            print(f"开始保存聊天记录: {user_input[:20]}... -> {ai_response[:20]}...")
            cursor = self._new_cursor()
            if self._table_exists(cursor, 'chat_history'):
                query = """
                INSERT INTO chat_history 
                (user_input, ai_response, image_description, persona_filename) 
                VALUES (%s, %s, %s, %s)
                """
                self._execute(cursor, query, (user_input, ai_response, image_description, persona_filename))
                self.connection.commit()
                print(f"聊天记录已成功保存！ID: {getattr(cursor, 'lastrowid', None)}")
        except Exception as e:
            print(f"保存对话记录错误 [详细]: {e}")
            # 打印堆栈跟踪以获取更多信息
            traceback.print_exc()
        finally:
            if cursor:
                cursor.close()

    def get_chat_history(self, limit=50, persona_filename=None):
        """获取聊天历史记录
        
        Args:
            limit (int): 限制返回的记录数
            
        Returns:
            list: 聊天记录列表
        """
        cursor = None
        try:
            cursor = self._new_cursor()
            if self._table_exists(cursor, 'chat_history'):
                if persona_filename:
                    self._execute(
                        cursor,
                        "SELECT * FROM chat_history WHERE persona_filename = %s ORDER BY id DESC LIMIT %s",
                        (persona_filename, limit)
                    )
                else:
                    # 改为降序，优先显示最新记录
                    self._execute(cursor, "SELECT * FROM chat_history ORDER BY id DESC LIMIT %s", (limit,))
                return cursor.fetchall()
            return []
        except Exception as e:
            print(f"获取聊天记录错误: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

    def search_chat_history(self, keyword, limit=5, persona_filename=None):
        """搜索包含关键词的聊天记录
        
        Args:
            keyword (str): 搜索关键词
            limit (int): 限制返回数量
            
        Returns:
            list: 匹配的聊天记录列表
        """
        cursor = None
        try:
            cursor = self._new_cursor()
            if self._table_exists(cursor, 'chat_history'):
                # 使用LIKE进行简单的模糊查询
                search_query = f"%{keyword}%"
                if persona_filename:
                    query = """
                    SELECT user_input, ai_response FROM chat_history 
                    WHERE persona_filename = %s AND (user_input LIKE %s OR ai_response LIKE %s)
                    ORDER BY id DESC LIMIT %s
                    """
                    self._execute(cursor, query, (persona_filename, search_query, search_query, limit))
                else:
                    query = """
                    SELECT user_input, ai_response FROM chat_history 
                    WHERE user_input LIKE %s OR ai_response LIKE %s 
                    ORDER BY id DESC LIMIT %s
                    """
                    self._execute(cursor, query, (search_query, search_query, limit))
                return cursor.fetchall()
            return []
        except Exception as e:
            print(f"搜索聊天记录错误: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

    def get_recent_chat_history(self, limit=10, persona_filename=None):
        """获取最近的聊天记录，并格式化为消息列表
        
        Args:
            limit (int): 限制数量
            
        Returns:
            list: 格式化后的消息列表 [{"role": "user", ...}, ...]
        """
        # 复用 get_chat_history 获取原始数据
        # get_chat_history 返回的是 (id, user_input, ai_response, image_description, created_at)
        raw_history = self.get_chat_history(limit, persona_filename=persona_filename)
        messages = []
        
        # 数据库返回是倒序（最新的在前），我们需要将其反转为正序（按时间发展顺序）
        for record in reversed(raw_history):
            # 记录结构: id(0), user_input(1), ai_response(2), image_description(3), created_at(4)
            user_msg = record[1]
            ai_msg = record[2]
            
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            if ai_msg:
                messages.append({"role": "assistant", "content": ai_msg})
                
        return messages

    def delete_chat_record(self, record_id):
        """删除指定聊天记录
        
        Args:
            record_id (int): 要删除的记录ID
        """
        cursor = None
        try:
            cursor = self._new_cursor()
            if self._table_exists(cursor, 'chat_history'):
                self._execute(cursor, "DELETE FROM chat_history WHERE id = %s", (record_id,))
                self.connection.commit()
        except Exception as e:
            print(f"删除聊天记录错误: {e}")
        finally:
            if cursor:
                cursor.close()

    def clear_chat_history(self):
        """清空所有聊天记录"""
        cursor = None
        try:
            cursor = self._new_cursor()
            if self._table_exists(cursor, 'chat_history'):
                self._execute(cursor, "DELETE FROM chat_history")
                self.connection.commit()
        except Exception as e:
            print(f"清空聊天记录错误: {e}")
        finally:
            if cursor:
                cursor.close()

    def purge_command_history(self, persona_filename=None):
        """清理命令/菜单类历史，避免 bot hub 菜单污染后续上下文。"""
        cursor = None
        try:
            cursor = self._new_cursor()
            if not self._table_exists(cursor, 'chat_history'):
                return

            patterns = [
                '%/bothub%',
                '%/hub%',
                '%bot hub界面%',
                '%请选择你要使用的设置%',
                '%请使用 @机器人 /bothub%',
                '%bothub 指令已关闭%',
                '%bothub 指令格式错误%',
                '%为避免误触发，请使用 /bothub%',
            ]

            if persona_filename:
                persona_clause = ' AND persona_filename = %s'
                params = [persona_filename]
            else:
                persona_clause = ''
                params = []

            conditions = ' OR '.join(['user_input LIKE %s OR ai_response LIKE %s'] * len(patterns))
            query = f"DELETE FROM chat_history WHERE ({conditions}){persona_clause}"

            query_params = []
            for pattern in patterns:
                query_params.extend([pattern, pattern])
            query_params.extend(params)

            self._execute(cursor, query, tuple(query_params))
            self.connection.commit()
        except Exception as e:
            print(f"清理命令聊天记录错误: {e}")
        finally:
            if cursor:
                cursor.close()

    def delete_first_n_records(self, n):
        """删除前N条记录
        
        Args:
            n (int): 要删除的记录数
        """
        cursor = None
        try:
            cursor = self._new_cursor()
            if self._table_exists(cursor, 'chat_history'):
                self._execute(cursor, "SELECT id FROM chat_history ORDER BY id ASC LIMIT %s", (n,))
                ids = [r[0] for r in cursor.fetchall()]
                if ids:
                    # 使用参数化查询避免SQL注入
                    format_strings = ','.join(['%s'] * len(ids))
                    query = f"DELETE FROM chat_history WHERE id IN ({format_strings})"
                    self._execute(cursor, query, tuple(ids))
                    self.connection.commit()
        except Exception as e:
            print(f"删除前N条记录错误: {e}")
        finally:
            if cursor:
                cursor.close()

    def close(self):
        """关闭数据库连接"""
        if not self.connection:
            return
        try:
            if hasattr(self.connection, 'is_connected'):
                if self.connection.is_connected():
                    self.connection.close()
            else:
                self.connection.close()
        except Exception:
            pass
            # print(Fore.YELLOW + "数据库连接已关闭")
