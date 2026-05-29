"""数据库操作封装模块"""

import hashlib
import json
import os
import re
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

from app.core.config import CONFIG

# 获取项目根目录
# database.py在backend/app/database/，需要向上2层到backend
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 导入规范的数据目录常量
from app.core.config import DATA_DIR

# 数据库文件路径
DB_PATH = os.path.join(DATA_DIR, 'chat_history.db')


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

        # 尝试连接到具体的数据库
        try:
            connection = mysql.connector.connect(
                host=db_cfg.get('host', '127.0.0.1'),
                user=db_cfg.get('user', 'root'),
                password=db_cfg.get('password', ''),
                database=db_cfg.get('database', 'shizuku_nya_bot'),
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            return connection
        except mysql.connector.Error as e:
            # 如果是"Unknown database"错误，则尝试连接到MySQL服务器而不指定数据库
            if e.errno == 1049:  # Error 1049: Unknown database
                print(Fore.YELLOW + f"数据库不存在，正在尝试创建: {db_cfg.get('database', 'shizuku_nya_bot')}")
                return create_database_if_not_exists(db_cfg)
            else:
                raise e
    except Exception as e:
        print(Fore.RED + f"数据库连接错误: {e}")
        return None


def create_database_if_not_exists(db_cfg):
    """创建数据库（如果不存在）
    
    Args:
        db_cfg (dict): 数据库配置
        
    Returns:
        mysql.connector.connection.MySQLConnection: 数据库连接对象
    """
    try:
        # 首先连接到MySQL服务器，但不指定数据库
        temp_connection = mysql.connector.connect(
            host=db_cfg.get('host', '127.0.0.1'),
            user=db_cfg.get('user', 'root'),
            password=db_cfg.get('password', ''),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        
        cursor = temp_connection.cursor()
        
        # 创建数据库（如果不存在）
        database_name = db_cfg.get('database', 'shizuku_nya_bot')
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        
        print(Fore.GREEN + f"数据库 `{database_name}` 创建成功或已存在")
        
        # 关闭临时连接
        cursor.close()
        temp_connection.close()
        
        # 现在连接到刚刚创建的数据库
        connection = mysql.connector.connect(
            host=db_cfg.get('host', '127.0.0.1'),
            user=db_cfg.get('user', 'root'),
            password=db_cfg.get('password', ''),
            database=database_name,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        
        return connection
    except mysql.connector.Error as e:
        print(Fore.RED + f"创建数据库时出错: {e}")
        return None
    except Exception as e:
        print(Fore.RED + f"创建数据库时发生未知错误: {e}")
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
        self._chat_history_bootstrapped_tables = set()

        # 确保所有必要的表都存在
        self._ensure_all_tables_exist()
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

    def _ensure_all_tables_exist(self):
        """确保所有必要的表都存在，如果不存在则创建它们"""
        cursor = None
        try:
            cursor = self._new_cursor()
            
            # 确保 chat_history 表存在
            self._ensure_chat_history_table(cursor, 'chat_history')
            
            # 确保 repo_context_cache 表存在
            if self.cache_provider is None:
                self._ensure_repo_context_cache_table_with_cursor(cursor)
            
            # 确保 character_info 表存在
            self._ensure_character_info_table(cursor)
            
            self.connection.commit()
        except Exception as e:
            print(f"确保所有表存在时出错: {e}")
            traceback.print_exc()
        finally:
            if cursor:
                cursor.close()

    def _ensure_character_info_table(self, cursor):
        """确保 character_info 表存在"""
        if self._table_exists(cursor, 'character_info'):
            # 如果表已存在，检查并添加缺失的列
            self._ensure_character_info_table_columns(cursor)
            return

        if self.engine in ('postgres', 'postgresql'):
            create_sql = """
            CREATE TABLE IF NOT EXISTS character_info (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                personality TEXT,
                avatar_url VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        elif self.engine in ('sqlite', 'sqlite3'):
            create_sql = """
            CREATE TABLE IF NOT EXISTS character_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                personality TEXT,
                avatar_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        else:  # MySQL
            create_sql = """
            CREATE TABLE IF NOT EXISTS character_info (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                personality TEXT,
                avatar_url VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """

        self._execute(cursor, create_sql)

    def _ensure_character_info_table_columns(self, cursor):
        """确保 character_info 表包含所有必要的列"""
        columns_to_check = [
            ('name', 'VARCHAR(255) NOT NULL'),
            ('description', 'TEXT'),
            ('personality', 'TEXT'),
            ('avatar_url', 'VARCHAR(500)'),
            ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
            ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ]
        
        for col_name, col_def in columns_to_check:
            if not self._column_exists_in_cursor(cursor, 'character_info', col_name):
                try:
                    # 根据数据库类型调整列定义
                    if self.engine in ('sqlite', 'sqlite3'):
                        # SQLite 不支持直接添加带默认值的列
                        alter_sql = f"ALTER TABLE character_info ADD COLUMN {col_name} {col_def.split(' ', 1)[1] if ' ' in col_def else col_def}"
                    elif self.engine in ('postgres', 'postgresql'):
                        alter_sql = f"ALTER TABLE character_info ADD COLUMN {col_name} {col_def}"
                        if 'DEFAULT' in col_def:
                            alter_sql += ", ALTER COLUMN {} SET DEFAULT {}".format(col_name, col_def.split('DEFAULT')[1].strip().split()[0])
                    else:  # MySQL
                        alter_sql = f"ALTER TABLE character_info ADD COLUMN {col_name} {col_def}"
                    
                    self._execute(cursor, alter_sql)
                    print(f"已添加列 {col_name} 到 character_info 表")
                except Exception as e:
                    print(f"添加列 {col_name} 到 character_info 表时出错: {e}")

    def _ensure_repo_context_cache_table_with_cursor(self, cursor):
        """使用传入的游标确保 repo_context_cache 表存在"""
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
        if not self._column_exists_in_cursor(cursor, 'repo_context_cache', 'hit_count'):
            self._add_column_to_table(cursor, 'repo_context_cache', 'hit_count', 'INT NOT NULL DEFAULT 0')

        if not self._column_exists_in_cursor(cursor, 'repo_context_cache', 'updated_at'):
            if self.engine in ('mysql', 'mariadb'):
                self._add_column_to_table(cursor, 'repo_context_cache', 'updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
            else:
                self._add_column_to_table(cursor, 'repo_context_cache', 'updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')

        if not self._column_exists_in_cursor(cursor, 'repo_context_cache', 'last_hit_at'):
            self._add_column_to_table(cursor, 'repo_context_cache', 'last_hit_at', 'TIMESTAMP NULL')

    def _add_column_to_table(self, cursor, table_name, column_name, column_definition):
        """向表中添加列"""
        try:
            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            self._execute(cursor, alter_sql)
            print(f"已添加列 {column_name} 到 {table_name} 表")
        except Exception as e:
            print(f"添加列 {column_name} 到 {table_name} 表时出错: {e}")

    def _column_exists_in_cursor(self, cursor, table_name, column_name):
        """检查列是否存在（使用传入的游标）"""
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

        if self.engine in ('sqlite', 'sqlite3'):
            self._execute(cursor, f"PRAGMA table_info({table_name})")
            rows = cursor.fetchall() or []
            for row in rows:
                if len(row) > 1 and str(row[1]) == column_name:
                    return True
            return False

        self._execute(cursor, f"SHOW COLUMNS FROM {table_name} LIKE %s", (column_name,))
        return cursor.fetchone() is not None

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

        if self.engine in ('sqlite', 'sqlite3'):
            self._execute(cursor, f"PRAGMA table_info({table_name})")
            rows = cursor.fetchall() or []
            for row in rows:
                if len(row) > 1 and str(row[1]) == column_name:
                    return True
            return False

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
            thinking_exists = self._column_exists(cursor, 'chat_history', 'thinking')
            if not thinking_exists:
                self._execute(cursor, "ALTER TABLE chat_history ADD COLUMN thinking LONGTEXT NULL DEFAULT NULL")
                self.connection.commit()
        except Exception as e:
            print(f"确保 persona_filename 列时出错: {e}")
        finally:
            if cursor:
                cursor.close()

    def _ensure_chat_history_thinking_column(self, table_name):
        """确保指定聊天表存在 thinking 列。"""
        cursor = None
        try:
            cursor = self._new_cursor()
            if not self._table_exists(cursor, table_name):
                return
            exists = self._column_exists(cursor, table_name, 'thinking')
            if not exists:
                self._execute(cursor, f"ALTER TABLE {table_name} ADD COLUMN thinking LONGTEXT NULL DEFAULT NULL")
                self.connection.commit()
        except Exception as e:
            print(f"确保 thinking 列时出错({table_name}): {e}")
        finally:
            if cursor:
                cursor.close()

    @staticmethod
    def _normalize_persona_table_key(persona_filename):
        filename = str(persona_filename or '').strip()
        if not filename:
            return ''
        filename = os.path.basename(filename)
        if filename.lower().endswith('.json'):
            filename = filename[:-5]
        filename = re.sub(r'[^A-Za-z0-9_.-]+', '_', filename).strip('._-')
        return filename.lower()[:48]

    def _chat_history_table_name(self, persona_filename=None):
        key = self._normalize_persona_table_key(persona_filename)
        if not key:
            return 'chat_history'
        return f'chat_history_{key}'

    def _ensure_chat_history_table(self, cursor, table_name):
        if self._table_exists(cursor, table_name):
            return

        if self.engine in ('postgres', 'postgresql'):
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id BIGSERIAL PRIMARY KEY,
                user_input TEXT,
                ai_response TEXT,
                image_description TEXT,
                persona_filename VARCHAR(120) NULL,
                thinking TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        elif self.engine in ('sqlite', 'sqlite3'):
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_input TEXT,
                ai_response TEXT,
                image_description TEXT,
                persona_filename TEXT NULL,
                thinking TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        else:
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_input TEXT,
                ai_response LONGTEXT,
                image_description TEXT,
                persona_filename VARCHAR(120) NULL,
                thinking LONGTEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """

        self._execute(cursor, create_sql)

    def _bootstrap_persona_chat_history(self, cursor, persona_filename, table_name):
        if table_name in self._chat_history_bootstrapped_tables:
            return

        self._ensure_chat_history_table(cursor, table_name)
        self._ensure_chat_history_thinking_column(table_name)

        if not persona_filename or not self._table_exists(cursor, 'chat_history'):
            self._chat_history_bootstrapped_tables.add(table_name)
            return

        try:
            self._execute(
                cursor,
                "SELECT user_input, ai_response, image_description, persona_filename, thinking FROM chat_history WHERE persona_filename = %s ORDER BY id ASC",
                (persona_filename,)
            )
            legacy_rows = cursor.fetchall() or []
            if legacy_rows:
                self._execute(cursor, f"SELECT COUNT(*) FROM {table_name}")
                current_count_row = cursor.fetchone()
                current_count = int(current_count_row[0]) if current_count_row else 0
                if current_count == 0:
                    for row in legacy_rows:
                        self._execute(
                            cursor,
                            f"INSERT INTO {table_name} (user_input, ai_response, image_description, persona_filename, thinking) VALUES (%s, %s, %s, %s, %s)",
                            (row[0], row[1], row[2], row[3], row[4] if len(row) > 4 else None)
                        )
                    self.connection.commit()
        except Exception:
            pass

        self._chat_history_bootstrapped_tables.add(table_name)

    def _list_chat_history_tables(self, cursor):
        if self.engine in ('postgres', 'postgresql'):
            self._execute(
                cursor,
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND (tablename = %s OR tablename LIKE %s)",
                ('chat_history', 'chat_history\\_%')
            )
            return [row[0] for row in cursor.fetchall() or []]

        if self.engine in ('sqlite', 'sqlite3'):
            self._execute(
                cursor,
                "SELECT name FROM sqlite_master WHERE type='table' AND (name = ? OR name LIKE ?)",
                ('chat_history', 'chat_history_%')
            )
            return [row[0] for row in cursor.fetchall() or []]

        self._execute(cursor, "SHOW TABLES LIKE %s", ('chat_history%',))
        return [row[0] for row in cursor.fetchall() or []]

    def migrate_legacy_chat_history_to_persona_tables(self, delete_legacy=False):
        """将 legacy chat_history 中的人格数据迁移到独立表。

        Returns:
            dict: 迁移统计信息
        """
        cursor = None
        stats = {
            'success': False,
            'legacy_exists': False,
            'personas_scanned': 0,
            'personas_migrated': 0,
            'tables_created': [],
            'legacy_rows_deleted': 0,
            'errors': [],
        }
        try:
            cursor = self._new_cursor()
            if not self._table_exists(cursor, 'chat_history'):
                stats['success'] = True
                return stats

            stats['legacy_exists'] = True
            self._execute(
                cursor,
                "SELECT DISTINCT persona_filename FROM chat_history WHERE persona_filename IS NOT NULL AND TRIM(persona_filename) <> ''"
            )
            persona_rows = cursor.fetchall() or []
            persona_list = [str(row[0]).strip() for row in persona_rows if row and str(row[0]).strip()]
            stats['personas_scanned'] = len(persona_list)

            for persona_filename in persona_list:
                table_name = self._chat_history_table_name(persona_filename)
                before_count = 0
                if self._table_exists(cursor, table_name):
                    self._execute(cursor, f"SELECT COUNT(*) FROM {table_name}")
                    row = cursor.fetchone()
                    before_count = int(row[0]) if row else 0

                self._bootstrap_persona_chat_history(cursor, persona_filename, table_name)

                self._execute(cursor, f"SELECT COUNT(*) FROM {table_name}")
                row = cursor.fetchone()
                after_count = int(row[0]) if row else 0

                if table_name not in stats['tables_created']:
                    stats['tables_created'].append(table_name)
                if after_count > before_count:
                    stats['personas_migrated'] += 1

            if delete_legacy and persona_list:
                placeholders = ','.join(['%s'] * len(persona_list))
                self._execute(
                    cursor,
                    f"DELETE FROM chat_history WHERE persona_filename IN ({placeholders})",
                    tuple(persona_list)
                )
                if hasattr(cursor, 'rowcount') and cursor.rowcount is not None:
                    stats['legacy_rows_deleted'] = int(cursor.rowcount)

            self.connection.commit()
            stats['success'] = True
            return stats
        except Exception as e:
            stats['errors'].append(str(e))
            return stats
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
            self._ensure_repo_context_cache_table_with_cursor(cursor)
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
                if result:
                    # 将结果转换为字典
                    if isinstance(result, dict):
                        return result
                    else:
                        # 处理 sqlite3.Row 等类型
                        keys = [description[0] for description in cursor.description]
                        return dict(zip(keys, result))
            return None
        except Exception as e:
            print(f"读取 character_info 表时出错: {e}")
            return None
        finally:
            if cursor:
                cursor.close()

    def get_chat_history(self, limit=50, persona_filename=None):
        """获取聊天记录
        
        Args:
            limit (int): 限制记录数，默认为50
            persona_filename (str): 人格文件名，可选
            
        Returns:
            list: 聊天记录列表
        """
        try:
            cursor = self._new_cursor(dictionary=True)
            table_name = self._chat_history_table_name(persona_filename)
            
            if not self._table_exists(cursor, table_name):
                return []

            try:
                self._ensure_chat_history_thinking_column(table_name)
            except Exception:
                pass
                
            try:
                if persona_filename:
                    self._execute(
                        cursor,
                        f"SELECT * FROM {table_name} WHERE persona_filename = %s ORDER BY id DESC LIMIT %s",
                        (persona_filename, limit)
                    )
                else:
                    self._execute(
                        cursor,
                        f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT %s",
                        (limit,)
                    )
            except Exception:
                if persona_filename:
                    self._execute(
                        cursor,
                        f"SELECT user_input, ai_response, image_description, persona_filename, created_at FROM {table_name} WHERE persona_filename = %s ORDER BY id DESC LIMIT %s",
                        (persona_filename, limit)
                    )
                else:
                    self._execute(
                        cursor,
                        f"SELECT user_input, ai_response, image_description, persona_filename, created_at FROM {table_name} ORDER BY id DESC LIMIT %s",
                        (limit,)
                    )
                
            result = cursor.fetchall()
            return result
        except Exception as e:
            print(f"获取聊天记录时出错: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

    def get_recent_chat_history(self, limit=50, persona_filename=None):
        """获取最近的聊天记录，并转换为对话消息格式
        
        Args:
            limit (int): 限制记录数，默认为50
            persona_filename (str): 人格文件名，可选
            
        Returns:
            list: 对话消息列表，格式为 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
                  按时间顺序排列（从旧到新）
        """
        cursor = None
        try:
            cursor = self._new_cursor(dictionary=True)
            table_name = self._chat_history_table_name(persona_filename)
            
            if not self._table_exists(cursor, table_name):
                return []

            try:
                self._ensure_chat_history_thinking_column(table_name)
            except Exception:
                pass
                
            # 获取最近的记录（按ID降序），然后反转以得到时间顺序
            try:
                if persona_filename:
                    self._execute(
                        cursor,
                        f"SELECT user_input, ai_response, image_description, thinking FROM {table_name} WHERE persona_filename = %s ORDER BY id DESC LIMIT %s",
                        (persona_filename, limit)
                    )
                else:
                    self._execute(
                        cursor,
                        f"SELECT user_input, ai_response, image_description, thinking FROM {table_name} ORDER BY id DESC LIMIT %s",
                        (limit,)
                    )
            except Exception:
                # 兼容旧表：没有 thinking 列时回退到老查询
                if persona_filename:
                    self._execute(
                        cursor,
                        f"SELECT user_input, ai_response, image_description FROM {table_name} WHERE persona_filename = %s ORDER BY id DESC LIMIT %s",
                        (persona_filename, limit)
                    )
                else:
                    self._execute(
                        cursor,
                        f"SELECT user_input, ai_response, image_description FROM {table_name} ORDER BY id DESC LIMIT %s",
                        (limit,)
                    )
                
            rows = cursor.fetchall()
            if not rows:
                return []
            
            # 反转为时间顺序（从旧到新）
            rows = list(reversed(rows))
            
            # 转换为对话消息格式
            messages = []
            for row in rows:
                # 处理字典或元组两种情况
                if isinstance(row, dict):
                    user_input = row.get('user_input', '')
                    ai_response = row.get('ai_response', '')
                    image_desc = row.get('image_description', '')
                    thinking = row.get('thinking', '')
                else:
                    # 元组情况：(user_input, ai_response, image_description, [thinking])
                    user_input = row[0] if len(row) > 0 else ''
                    ai_response = row[1] if len(row) > 1 else ''
                    image_desc = row[2] if len(row) > 2 else ''
                    thinking = row[3] if len(row) > 3 else ''
                
                # 添加用户消息
                if user_input:
                    if image_desc:
                        messages.append({"role": "user", "content": f"{user_input}\n[图片描述: {image_desc}]"})
                    else:
                        messages.append({"role": "user", "content": str(user_input)})
                
                # 添加AI回复
                if ai_response:
                    messages.append({"role": "assistant", "content": str(ai_response)})

                if thinking:
                    messages.append({"role": "assistant", "content": str(thinking), "metadata": {"type": "thinking"}})
            
            return messages
        except Exception as e:
            print(f"获取最近聊天记录时出错: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            if cursor:
                cursor.close()

    def save_chat(self, user_input, ai_response, image_description=None, persona_filename=None, thinking=None):
        """保存聊天记录到数据库
        
        Args:
            user_input (str): 用户输入
            ai_response (str): AI回复
            image_description (str): 图片描述（可选）
            persona_filename (str): 人格文件名（可选）
        """
        cursor = None
        try:
            cursor = self._new_cursor()
            table_name = self._chat_history_table_name(persona_filename)
            
            # 确保表存在
            self._bootstrap_persona_chat_history(cursor, persona_filename, table_name)
            
            # 插入聊天记录
            if persona_filename:
                self._execute(
                    cursor,
                    f"INSERT INTO {table_name} (user_input, ai_response, image_description, persona_filename, thinking) VALUES (%s, %s, %s, %s, %s)",
                    (user_input, ai_response, image_description, persona_filename, thinking)
                )
            else:
                self._execute(
                    cursor,
                    f"INSERT INTO {table_name} (user_input, ai_response, image_description, thinking) VALUES (%s, %s, %s, %s)",
                    (user_input, ai_response, image_description, thinking)
                )
            
            self.connection.commit()
            print(f"[DEBUG] Chat saved to {table_name}: user_input={user_input[:30]}..., ai_response_length={len(ai_response)}")
        except Exception as e:
            print(f"保存聊天记录时出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if cursor:
                cursor.close()

    def close(self):
        """关闭数据库连接"""
        try:
            if self.connection and not self.connection.is_closed():
                self.connection.close()
        except Exception as e:
            print(f"关闭数据库连接时出错: {e}")
