# -*- coding: utf-8 -*-
"""AI聊天系统模块"""

import json
import logging
import os
import time
import threading
import base64
import re
import random
import uuid
import hashlib
from collections import Counter
from datetime import datetime
from typing import Optional, Tuple, List
from io import BytesIO

import requests
from mysql.connector import Error
from PIL import Image
from openai import OpenAI, APITimeoutError

from src.config import CONFIG, generate_system_prompt
from src.database import get_connection, DatabaseManager
from src.shared_utils import count_tokens, estimate_tokens
from src.plugin_framework import PluginContext, PluginManager
from src.agent_task_scheduler import get_task_scheduler, AgentTask, TaskType

# 全局变量用于跟踪Token使用（需要在web_server.py中更新这些值）
try:
    from src.web_server import INPUT_TOKENS, OUTPUT_TOKENS
except ImportError:
    # 如果无法导入，则使用局部变量
    INPUT_TOKENS = 0
    OUTPUT_TOKENS = 0


class AIChatSystem:
    """AI聊天系统类，使用单例模式实现"""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        """初始化AI聊天系统"""
        # 在单例模式下，不要在__init__中初始化属性
        # 这些属性应该在initialize()方法中初始化

    def __new__(cls):
        """创建单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.initialize()
        return cls._instance

    def initialize(self):
        """初始化聊天系统属性"""
        db = DatabaseManager()
        # 直接从配置中获取系统提示语，不再在代码中生成
        system_prompt = CONFIG['system_prompt']

        # 初始化 Agent Manager
        from src.agent_manager import AgentManager
        self.agent_manager = AgentManager(self)

        # 初始化插件框架
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_all()

        # 使用配置中的基础URL
        client = OpenAI(
            api_key=CONFIG['api']['key'],
            base_url=CONFIG['api']['base_url'],
            timeout=30.0  # 添加超时设置
        )
        messages = [{"role": "system", "content": system_prompt}]

        persona_runtime = CONFIG.get('persona_runtime', {})

        # 确保赋值成功
        self.db = db
        self.system_prompt = system_prompt
        self.client = client
        self.messages = messages
        self.persona_runtime = persona_runtime
        self.current_persona_state = None

        # 实时搜索订阅存储
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(project_root, 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.realtime_subscriptions_path = os.path.join(data_dir, 'realtime_subscriptions.json')
        self.realtime_updates_path = os.path.join(data_dir, 'realtime_updates.json')
        self._realtime_lock = threading.Lock()
        self._ensure_realtime_storage_files()

    @classmethod
    def rebind_database(cls):
        """CONFIG['database'] 在控制面板保存后重建连接，避免单例仍持有旧引擎（如 PostgreSQL）。"""
        if cls._instance is None:
            return
        inst = cls._instance
        old = getattr(inst, 'db', None)
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
        inst.db = DatabaseManager()

    def reload_plugins(self):
        """Reload plugin framework and return latest status."""
        self.plugin_manager.reload_all()
        return self.plugin_manager.get_framework_status()

    def get_plugin_status(self):
        """Return plugin framework status for admin API/UI."""
        return self.plugin_manager.get_framework_status()

    def set_plugin_framework_enabled(self, enabled):
        """Enable or disable the plugin framework."""
        self.plugin_manager.set_framework_enabled(bool(enabled), persist=True)
        return self.plugin_manager.get_framework_status()

    def update_plugin_policy(self, plugin_name, policy):
        """Update plugin isolation policy and return normalized policy."""
        return self.plugin_manager.update_plugin_policy(plugin_name, policy, persist=True)

    def get_plugin_runtime_config(self, plugin_name):
        """Read a plugin runtime config from its project directory."""
        return self.plugin_manager.get_plugin_runtime_config(plugin_name)

    def update_plugin_runtime_config(self, plugin_name, config_data):
        """Write a plugin runtime config to its project directory."""
        return self.plugin_manager.update_plugin_runtime_config(plugin_name, config_data)

    def run_plugin_command(self, command_text, is_admin=True, frontend_source='control_panel'):
        """Execute a plugin command directly (e.g. /plugins reload, /kemono_crawl ...)."""
        context = PluginContext(
            user_input=command_text,
            is_admin=is_admin,
            frontend_source=frontend_source,
            attachments=None,
            metadata={"invoked_from": "api"},
            chat_system=self
        )
        result = self.plugin_manager.process_input(context)
        if not result:
            return {"handled": False, "response": ""}

        response_text = result.response or ""
        response_text = self.plugin_manager.process_response(context, response_text)
        return {
            "handled": bool(result.handled),
            "response": response_text,
            "metadata": result.metadata,
        }

    def _ensure_realtime_storage_files(self):
        if not os.path.exists(self.realtime_subscriptions_path):
            with open(self.realtime_subscriptions_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        if not os.path.exists(self.realtime_updates_path):
            with open(self.realtime_updates_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    @staticmethod
    def _load_json_file(path, default_value):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default_value

    @staticmethod
    def _save_json_file(path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def realtime_search(self, query: str) -> dict:
        q = (query or '').strip()
        if not q:
            return {
                'success': False,
                'query': q,
                'source': 'moonshot_web_search',
                'fetched_at': datetime.now().isoformat(timespec='seconds'),
                'result': '搜索失败: query 不能为空'
            }

        result_text = AIChatSystem.search_with_ai_search(q)
        is_ok = not ("搜索API错误" in result_text or "搜索失败" in result_text)
        return {
            'success': is_ok,
            'query': q,
            'source': 'moonshot_web_search',
            'fetched_at': datetime.now().isoformat(timespec='seconds'),
            'result': result_text
        }

    def _execute_realtime_subscription(self, subscription_id: str):
        with self._realtime_lock:
            subscriptions = self._load_json_file(self.realtime_subscriptions_path, [])
            updates = self._load_json_file(self.realtime_updates_path, [])

            target = None
            for sub in subscriptions:
                if sub.get('id') == subscription_id:
                    target = sub
                    break

            if not target or not target.get('enabled', True):
                return {'skipped': True, 'reason': 'subscription_not_found_or_disabled'}

            payload = self.realtime_search(target.get('query', ''))
            result_text = payload.get('result', '')
            result_hash = hashlib.sha1(result_text.encode('utf-8')).hexdigest() if result_text else ''
            now_iso = datetime.now().isoformat(timespec='seconds')

            target['last_run_at'] = now_iso
            target['updated_at'] = now_iso

            if payload.get('success'):
                if result_hash and result_hash != target.get('last_result_hash'):
                    target['last_result_hash'] = result_hash
                    target['last_result_preview'] = result_text[:280]
                    updates.append({
                        'id': str(uuid.uuid4())[:8],
                        'subscription_id': subscription_id,
                        'query': target.get('query', ''),
                        'created_at': now_iso,
                        'source': payload.get('source', 'moonshot_web_search'),
                        'result': result_text
                    })
                    updates = updates[-200:]
            else:
                target['last_error'] = result_text

            self._save_json_file(self.realtime_subscriptions_path, subscriptions)
            self._save_json_file(self.realtime_updates_path, updates)

        return payload

    def create_realtime_subscription(self, query: str, interval_seconds: int = 300) -> dict:
        q = (query or '').strip()
        if not q:
            raise ValueError('query 不能为空')

        try:
            interval = int(interval_seconds)
        except Exception:
            interval = 300
        interval = max(30, interval)

        sub_id = str(uuid.uuid4())[:8]
        now_iso = datetime.now().isoformat(timespec='seconds')

        task = AgentTask(
            name=f'realtime_search:{sub_id}',
            description=f'订阅实时搜索: {q[:40]}',
            task_type=TaskType.RECURRING.value,
            command='realtime_search_subscription',
            args={},
            interval_seconds=interval,
            max_retries=2,
            enabled=True,
            notify_on_complete=False
        )

        scheduler = get_task_scheduler()
        task_id = scheduler.add_task(task, callback=lambda: self._execute_realtime_subscription(sub_id))

        subscription = {
            'id': sub_id,
            'query': q,
            'interval_seconds': interval,
            'enabled': True,
            'task_id': task_id,
            'created_at': now_iso,
            'updated_at': now_iso,
            'last_run_at': None,
            'last_result_hash': '',
            'last_result_preview': '',
            'last_error': ''
        }

        with self._realtime_lock:
            subscriptions = self._load_json_file(self.realtime_subscriptions_path, [])
            subscriptions.append(subscription)
            self._save_json_file(self.realtime_subscriptions_path, subscriptions)

        return subscription

    def list_realtime_subscriptions(self) -> List[dict]:
        with self._realtime_lock:
            subscriptions = self._load_json_file(self.realtime_subscriptions_path, [])
        return sorted(subscriptions, key=lambda x: x.get('created_at', ''), reverse=True)

    def delete_realtime_subscription(self, subscription_id: str) -> bool:
        sid = (subscription_id or '').strip()
        if not sid:
            return False

        deleted = False
        task_id_to_remove = None

        with self._realtime_lock:
            subscriptions = self._load_json_file(self.realtime_subscriptions_path, [])
            kept = []
            for sub in subscriptions:
                if sub.get('id') == sid:
                    deleted = True
                    task_id_to_remove = sub.get('task_id')
                    continue
                kept.append(sub)

            if deleted:
                self._save_json_file(self.realtime_subscriptions_path, kept)

        if deleted and task_id_to_remove:
            try:
                get_task_scheduler().delete_task(task_id_to_remove)
            except Exception:
                pass

        return deleted

    def poll_realtime_updates(self, subscription_id: str = '', since: str = '', limit: int = 20) -> List[dict]:
        sid = (subscription_id or '').strip()
        since_ts = (since or '').strip()
        try:
            max_count = int(limit)
        except Exception:
            max_count = 20
        max_count = max(1, min(max_count, 200))

        with self._realtime_lock:
            updates = self._load_json_file(self.realtime_updates_path, [])

        filtered = []
        for item in updates:
            if sid and item.get('subscription_id') != sid:
                continue
            if since_ts and item.get('created_at', '') <= since_ts:
                continue
            filtered.append(item)

        filtered.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return filtered[:max_count]

    @staticmethod
    def _normalize_persona_runtime(persona_data: dict) -> dict:
        persona_data = persona_data or {}
        return {
            'reply_style': persona_data.get('reply_style', ''),
            'states': persona_data.get('states', []),
            'state_probability': persona_data.get('state_probability', 0.3),
            'plan_style': persona_data.get('plan_style', ''),
            'plan_style_private': persona_data.get('plan_style_private', ''),
            'plan_style_group': persona_data.get('plan_style_group', ''),
            'state_weights': persona_data.get('state_weights', []),
            'enable_expression_learning': persona_data.get('enable_expression_learning', True),
            'behavior_rules': persona_data.get('behavior_rules', [])
        }

    @staticmethod
    def _resolve_persona_override(persona_filename: str):
        filename = (persona_filename or '').strip()
        if not filename:
            return None
        if not filename.endswith('.json'):
            filename += '.json'
        if '/' in filename or '\\' in filename or '..' in filename:
            raise ValueError('invalid persona filename')

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        persona_path = os.path.join(project_root, 'data', 'personas', filename)
        if not os.path.exists(persona_path):
            raise FileNotFoundError(f'persona not found: {filename}')

        with open(persona_path, 'r', encoding='utf-8') as f:
            persona_data = json.load(f)

        character = persona_data.get('character', {})
        template = persona_data.get('system_prompt', {}).get('template', '')
        system_prompt = generate_system_prompt(character, template)
        runtime = AIChatSystem._normalize_persona_runtime(persona_data)
        meta = persona_data.get('meta', {})

        return {
            'filename': filename,
            'meta': meta,
            'system_prompt': system_prompt,
            'persona_runtime': runtime,
            'raw': persona_data
        }

    def _pick_persona_state(self, persona_runtime=None):
        """按概率切换 persona 状态，模拟更自然的人格波动。"""
        runtime = persona_runtime if persona_runtime is not None else self.persona_runtime
        states = runtime.get('states') or []
        if not states:
            return None

        def choose_state_with_weight():
            raw_weights = runtime.get('state_weights')
            weights = None

            if isinstance(raw_weights, dict):
                weights = []
                for state in states:
                    try:
                        w = float(raw_weights.get(state, 1.0))
                    except Exception:
                        w = 1.0
                    weights.append(max(0.0, w))
            elif isinstance(raw_weights, list) and len(raw_weights) == len(states):
                weights = []
                for x in raw_weights:
                    try:
                        w = float(x)
                    except Exception:
                        w = 1.0
                    weights.append(max(0.0, w))

            if not weights or sum(weights) <= 0:
                return random.choice(states)

            return random.choices(states, weights=weights, k=1)[0]

        try:
            probability = float(runtime.get('state_probability', 0.3))
        except Exception:
            probability = 0.3
        probability = max(0.0, min(1.0, probability))

        if self.current_persona_state is None:
            self.current_persona_state = choose_state_with_weight()
            return self.current_persona_state

        if random.random() < probability:
            self.current_persona_state = choose_state_with_weight()

        return self.current_persona_state

    def _extract_recent_style_hint(self, recent_messages):
        """从最近用户消息中抽取风格提示，提升群聊表达贴合度。"""
        if not recent_messages:
            return ""

        user_texts = [
            m.get('content', '') for m in recent_messages
            if isinstance(m, dict) and m.get('role') == 'user' and m.get('content')
        ][-8:]

        if not user_texts:
            return ""

        internet_words = [
            '哈哈', '笑死', '离谱', '逆天', '绷不住', '蚌埠住了',
            '确实', '草', '绝了', '有一说一', '要不', '我超'
        ]
        found = []
        for t in user_texts:
            for w in internet_words:
                if w in t:
                    found.append(w)

        punct = Counter()
        for t in user_texts:
            for p in ['！', '!', '？', '?', '...', '～', '~']:
                if p in t:
                    punct[p] += t.count(p)

        style_bits = []
        if found:
            top_words = [w for w, _ in Counter(found).most_common(4)]
            style_bits.append(f"可适度借鉴群聊常用表达：{', '.join(top_words)}")
        if punct:
            top_punct = [p for p, _ in punct.most_common(2)]
            style_bits.append(f"标点节奏可参考：{', '.join(top_punct)}")

        return '；'.join(style_bits)

    def _build_dynamic_persona_prompt(self, user_input, recent_messages, frontend_source='control_panel', system_prompt=None, persona_runtime=None):
        """构建动态人格提示：基础人格 + 状态 + 行为规划 + 表达学习。"""
        runtime = persona_runtime if persona_runtime is not None else self.persona_runtime
        base_prompt = system_prompt if system_prompt is not None else self.system_prompt
        parts = [base_prompt]

        active_state = self._pick_persona_state(runtime)
        if active_state:
            parts.append(f"[当前状态]\n{active_state}")

        reply_style = (runtime.get('reply_style') or '').strip()
        if reply_style:
            parts.append(f"[回复风格]\n{reply_style}")

        default_plan_style = (runtime.get('plan_style') or '').strip()
        plan_style_private = (runtime.get('plan_style_private') or '').strip()
        plan_style_group = (runtime.get('plan_style_group') or '').strip()

        if frontend_source == 'sandbox':
            plan_style = plan_style_group or default_plan_style
        else:
            plan_style = plan_style_private or default_plan_style

        if plan_style:
            parts.append(f"[行为规划]\n{plan_style}")

        behavior_rules = runtime.get('behavior_rules') or []
        if behavior_rules:
            rules_text = '\n'.join([f"- {r}" for r in behavior_rules if str(r).strip()])
            if rules_text:
                parts.append(f"[行为规则]\n{rules_text}")

        expression_learning_enabled = runtime.get('enable_expression_learning', True)
        if isinstance(expression_learning_enabled, str):
            expression_learning_enabled = expression_learning_enabled.lower() not in ['0', 'false', 'off', 'no']

        if expression_learning_enabled:
            style_hint = self._extract_recent_style_hint(recent_messages)
            if style_hint:
                parts.append(f"[表达学习]\n{style_hint}")

        if user_input:
            parts.append("[当前轮建议]\n优先自然、像真人聊天，不要机械枚举；允许保留轻微情绪与主见，但避免无意义攻击。")

        # 添加严格的格式要求
        parts.append("[格式要求]严禁输出任何DSML、XML或特殊标记格式。不要使用 <| |> 符号。只回复纯文本对话。")

        return '\n\n'.join(parts)

    @staticmethod
    def _build_headers(api_key):
        """构建通用的请求头"""
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def _build_chat_messages(system_content, user_content):
        """构建聊天消息结构"""
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

    @staticmethod
    def _match_patterns(patterns, text, flags=0):
        """匹配多个正则表达式模式"""
        for pattern in patterns:
            if re.search(pattern, text, flags):
                return True
        return False

    @staticmethod
    def _make_api_request(url, headers, payload, timeout=30, retries=0, retry_delay=1.0):
        """发送API请求的通用方法，支持简单重试。"""
        last_exc = None
        for attempt in range(retries + 1):
            try:
                return requests.post(url, headers=headers, json=payload, timeout=timeout)
            except requests.exceptions.Timeout as exc:
                last_exc = exc
                if attempt < retries:
                    time.sleep(retry_delay)
                    continue
                raise

        if last_exc:
            raise last_exc

        return requests.post(url, headers=headers, json=payload, timeout=timeout)

    @staticmethod
    def _handle_tool_call(tool_call):
        """处理工具调用"""
        tool_call_id = tool_call["id"]
        tool_call_arguments = json.loads(tool_call["function"]["arguments"])
        return tool_call_id, tool_call_arguments

    @staticmethod
    def compress_image(base64_data):
        """压缩图片以减少大小"""
        try:
            # 提取纯base64数据
            if ',' in base64_data:
                base64_data = base64_data.split(',', 1)[1]

            # 解码base64
            img_data = base64.b64decode(base64_data)
            img = Image.open(BytesIO(img_data))

            # 压缩图片：调整大小和质量
            max_size = 1024
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size))

            # 转换为JPEG格式减少大小
            output_buffer = BytesIO()
            img = img.convert("RGB")  # 确保是RGB格式
            img.save(output_buffer, format="JPEG", quality=85)
            compressed_data = output_buffer.getvalue()

            # 重新编码为base64
            return base64.b64encode(compressed_data).decode('utf-8')

        except Exception as e:
            print(f"图片压缩错误: {e}")
            return base64_data.split(',')[-1] if ',' in base64_data else base64_data

    @staticmethod
    def clean_dsml_markup(text):
        """清理DSML及类似标记格式，确保输出为纯文本"""
        if not text:
            return text
        
        # 直接和彻底的方法：移除所有 < ... > 形式的标记，如果它们包含｜或|
        max_iterations = 15
        iteration = 0
        while iteration < max_iterations:
            original_text = text
            
            # 移除所有包含｜或|的 <...> 标记
            text = re.sub(r'<[^>]*[\|｜][^>]*>', '', text)
            # 也移除 </...> 格式的
            text = re.sub(r'</[^>]*[\|｜][^>]*>', '', text)
            
            if text == original_text:
                break
            iteration += 1
        
        # 移除残留的孤立竖线
        text = text.replace('｜', '').replace('|', '')
        
        # 清理多余空白
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    @staticmethod
    def analyze_image_with_aliyun(image_data):
        """使用阿里云通义VL MAX分析图片"""
        try:
            # 提取纯base64数据
            if ',' in image_data:
                base64_data = image_data.split(',', 1)[1]
            else:
                base64_data = image_data

            # 构建请求头
            headers = AIChatSystem._build_headers(CONFIG['aliyun_api']['key'])

            # 构建请求体
            payload = {
                "model": "qwen-vl-max",
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "image": f"data:image/jpeg;base64,{base64_data}"
                                },
                                {
                                    "text": "请详细描述这张图片的内容"
                                }
                            ]
                        }
                    ]
                },
                "parameters": {
                    "max_tokens": 300
                }
            }

            # 发送请求到阿里云通义VL MAX API
            response = AIChatSystem._make_api_request(
                f"{CONFIG['aliyun_api']['base_url']}/services/aigc/multimodal-generation/generation",
                headers,
                payload
            )

            if response.status_code != 200:
                error_msg = f"阿里云API错误: {response.status_code} - {response.text}"
                print(f"Aliyun API Error: {error_msg}")
                return error_msg

            result = response.json()
            if "output" in result and "choices" in result["output"]:
                content = result["output"]["choices"][0]["message"]["content"]
                # 确保返回的是字符串而不是列表
                if isinstance(content, list):
                    # 如果是列表，提取其中的文本内容
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            text_parts.append(item["text"])
                        elif isinstance(item, str):
                            text_parts.append(item)
                    return " ".join(text_parts)
                return str(content)
            else:
                return "无法解析图片内容"

        except Exception as e:
            error_msg = f"图片分析失败: {str(e)}"
            print(f"Image Analysis Error: {error_msg}")
            return error_msg

    @staticmethod
    def analyze_image_from_url(image_url):
        """通过URL获取图片并使用阿里云通义VL MAX分析图片"""
        try:
            # 从URL获取图片
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            # 将图片转换为Base64
            image_data = base64.b64encode(response.content).decode('utf-8')

            # 使用现有的方法分析图片
            return AIChatSystem.analyze_image_with_aliyun(image_data)

        except Exception as e:
            error_msg = f"从URL获取图片失败: {str(e)}"
            print(f"Image URL Error: {error_msg}")
            return error_msg

    @staticmethod
    def search_with_ai_search(query):
        """使用Kimi API进行搜索"""
        try:
            headers = AIChatSystem._build_headers(CONFIG['search_api']['key'])

            # 构造Kimi API请求消息
            kimi_messages = AIChatSystem._build_chat_messages(
                "你是 Kimi，由 Moonshot AI 提供支持的人工智能助手。",
                query
            )

            # 发送请求到Kimi API
            kimi_payload = {
                "model": "kimi-k2-0905-preview",
                "messages": kimi_messages,
                "temperature": 0.6,
                "max_tokens": 32768,
                "tools": [
                    {
                        "type": "builtin_function",
                        "function": {
                            "name": "$web_search",
                        },
                    }
                ]
            }

            response = AIChatSystem._make_api_request(
                f"{CONFIG['search_api']['base_url']}/chat/completions",
                headers,
                kimi_payload,
                timeout=45,
                retries=1,
                retry_delay=1.0
            )

            if response.status_code != 200:
                error_msg = f"搜索API错误: {response.status_code} - {response.text}"
                print(f"Search API Error: {error_msg}")
                return error_msg

            result = response.json()
            # 检查是否需要工具调用
            if result.get("choices") and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if choice.get("finish_reason") == "tool_calls" and \
                        choice.get("message") and choice["message"].get("tool_calls"):
                    # 处理工具调用
                    tool_calls = choice["message"]["tool_calls"]
                    for tool_call in tool_calls:
                        if tool_call["function"]["name"] == "$web_search":
                            # 执行搜索工具调用
                            tool_call_id, tool_call_arguments = AIChatSystem._handle_tool_call(tool_call)

                            # 将工具调用结果返回给Kimi API
                            kimi_messages.append(choice["message"])
                            kimi_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "name": "$web_search",
                                "content": json.dumps(tool_call_arguments)
                            })

                            # 再次调用Kimi API获取最终结果
                            kimi_payload["messages"] = kimi_messages
                            final_response = AIChatSystem._make_api_request(
                                f"{CONFIG['search_api']['base_url']}/chat/completions",
                                headers,
                                kimi_payload,
                                timeout=45,
                                retries=1,
                                retry_delay=1.0
                            )

                            if final_response.status_code == 200:
                                final_result = final_response.json()
                                if final_result.get("choices") and len(final_result["choices"]) > 0:
                                    final_choice = final_result["choices"][0]
                                    if final_choice.get("message") and final_choice["message"].get("content"):
                                        return final_choice["message"]["content"]

            return "未找到相关搜索结果"

        except requests.exceptions.Timeout:
            error_msg = "搜索失败: 搜索服务响应超时，请稍后重试"
            print(f"Search Error: {error_msg}")
            return error_msg
        except Exception as e:
            error_msg = f"搜索失败: {str(e)}"
            print(f"Search Error: {error_msg}")
            return error_msg

    @staticmethod
    def should_search(user_input):
        """判断是否需要进行搜索"""
        from src.shared_utils import should_search as util_should_search
        return util_should_search(user_input)

    def _send_deepseek_request(self, messages: list) -> Tuple[str, int, int]:
        """发送请求到DeepSeek API
        
        Args:
            messages (list): 消息历史列表
            
        Returns:
            tuple: (回复内容, 输入token数, 输出token数)
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CONFIG['api']['key']}"
        }

        # 构造请求数据
        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "stream": False
        }

        # 发送请求
        response = requests.post(
            f"{CONFIG['api']['base_url']}/chat/completions",
            headers=headers,
            json=data,
            timeout=300
        )
        response.raise_for_status()

        # 解析响应
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # 获取token统计
        prompt_tokens = result.get('usage', {}).get('prompt_tokens', 0)
        completion_tokens = result.get('usage', {}).get('completion_tokens', 0)
        
        # 更新全局token计数
        global INPUT_TOKENS, OUTPUT_TOKENS
        try:
            from src.web_server import INPUT_TOKENS, OUTPUT_TOKENS
            INPUT_TOKENS += prompt_tokens
            OUTPUT_TOKENS += completion_tokens
        except ImportError:
            INPUT_TOKENS += prompt_tokens
            OUTPUT_TOKENS += completion_tokens

        return content, prompt_tokens, completion_tokens

    def build_chat_context(self, user_input, max_tokens=2500, frontend_source='control_panel', system_prompt=None, persona_runtime=None, persona_filename=None):
        """
        构建智能上下文：
        1. 系统提示词
        2. 相关历史记忆（通过搜索提取的深层记忆）
        3. 最近对话窗口（短期记忆）
        4. 当前用户输入
        """
        # 1. 读取最近短期记忆（后续用于动态人格构建）
        recent_messages = self.db.get_recent_chat_history(limit=10, persona_filename=persona_filename)

        # 2. 动态系统提示词（人格状态 + 行为规划 + 表达学习）
        dynamic_system_prompt = self._build_dynamic_persona_prompt(
            user_input,
            recent_messages,
            frontend_source=frontend_source,
            system_prompt=system_prompt,
            persona_runtime=persona_runtime
        )
        context_messages = [{"role": "system", "content": dynamic_system_prompt}]
        
        # 3. 回忆技能：如果用户输入较长，尝试搜索相关的深层历史
        if user_input and len(user_input) > 4:
            # 简单的关键词提取（取前10个字符作为搜索索引，可优化）
            search_keyword = user_input[:10]
            relevant_history = self.db.search_chat_history(search_keyword, limit=3, persona_filename=persona_filename)
            
            if relevant_history:
                memory_text = "【相关历史记忆】\n"
                for row in relevant_history:
                    # row[0] is user_input, row[1] is ai_response
                    if row[0] and row[1]:
                        memory_text += f"User: {row[0]}\nAI: {row[1]}\n---\n"
                # 将相关记忆作为System Prompt的一部分插入，不占用对话轮次
                if memory_text != "【相关历史记忆】\n":
                    context_messages.append({"role": "system", "content": f"你可以参考以下历史对话记录回答：\n{memory_text}"})

        # 4. Token 预算控制 (滑动窗口)
        # 如果历史记录太多，动态移除最早的记录，直到满足max_tokens限制
        current_tokens = estimate_tokens(context_messages) + estimate_tokens(recent_messages)
        
        while current_tokens > max_tokens and len(recent_messages) > 0:
            recent_messages.pop(0) # 移除最旧的一条
            current_tokens = estimate_tokens(context_messages) + estimate_tokens(recent_messages)
            
        return context_messages + recent_messages

    def coder_agent(self, task_description: str, code_context: str = "") -> str:
        """
        调用专用的代码生成模型 (Coder Agent)
        
        Args:
            task_description: 任务描述
            code_context: 相关代码上下文或文件内容
            
        Returns:
            生成的代码或建议
        """
        try:
            coder_config = CONFIG.get('coder_api', {})
            provider = str(coder_config.get('provider', 'kimi')).lower().strip()
            provider_aliases = {
                'moonshot': 'kimi',
                'kimi_coder': 'kimi',
                'minimax_coder': 'minimax',
                'cloude': 'claude',
                'claude_coder': 'claude'
            }
            provider = provider_aliases.get(provider, provider)

            providers = coder_config.get('providers', {})
            selected = providers.get(provider, {})

            api_key = selected.get('key')
            base_url = str(selected.get('base_url', '')).rstrip('/')
            model = selected.get('model')
            
            if not api_key:
                return f"Error: Coder API key not configured for provider '{provider}'."
            if not base_url:
                return f"Error: Coder base_url not configured for provider '{provider}'."
            if not model:
                return f"Error: Coder model not configured for provider '{provider}'."
            
            system_prompt = """You are an expert AI coding assistant (Coder Agent). 
Your task is to write high-quality, efficient, and bug-free code based on the user's request.
You should provide the complete code implementation, not just snippets.
If the request involves modifying existing code, output the full modified file content or clear diffs."""

            user_content = f"Task: {task_description}\n\nContext:\n{code_context}"
            
            # Claude uses Anthropic Messages API. Kimi/MiniMax use OpenAI-compatible chat completions.
            if provider == 'claude':
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "max_tokens": 4096,
                    "temperature": 0.3,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_content}
                    ]
                }
                response = self._make_api_request(
                    f"{base_url}/messages",
                    headers,
                    payload
                )

                if response.status_code == 200:
                    result = response.json()
                    content_list = result.get('content', [])
                    for part in content_list:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            return part.get('text', '')
                    return str(result)
                return f"Coder API Error({provider}): {response.status_code} - {response.text}"

            headers = self._build_headers(api_key)
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.3
            }
            response = self._make_api_request(
                f"{base_url}/chat/completions",
                headers,
                payload
            )

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            return f"Coder API Error({provider}): {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"Coder Agent Exception: {str(e)}"

    def chat(self, user_input, image=None, is_admin=False, attachments=None, frontend_source='control_panel', persona_filename=None):
        """处理聊天请求，支持文本、图片及其他附件（无状态优化版）
        
        Args:
            user_input (str): 用户输入文本
            image (str): 图片路径或base64 (Legacy)
            is_admin (bool): 是否为管理员
            attachments (list): 附件列表 [{'name':..., 'type':..., 'content':...}]
        """
        
        # === 核心变更1：动态构建Agent上下文（如果启用Agent） ===
        # 即使不是管理员，也可以读取Agent上下文，但不能执行写操作
        try:
            agent_context = self.agent_manager.get_agent_context()
        except:
            agent_context = ""

        persona_override = None
        if persona_filename:
            try:
                persona_override = self._resolve_persona_override(persona_filename)
            except Exception as e:
                return f"角色卡加载失败: {str(e)}"
        
        # === 核心变更2：每次动态构建上下文 ===
        effective_persona_filename = (persona_override or {}).get('filename')

        messages = self.build_chat_context(
            user_input,
            frontend_source=frontend_source,
            system_prompt=(persona_override or {}).get('system_prompt'),
            persona_runtime=(persona_override or {}).get('persona_runtime'),
            persona_filename=effective_persona_filename
        )
        
        # 手动将 agent_context 添加到 messages 的第一个系统消息中
        if messages and messages[0]['role'] == 'system':
            messages[0]['content'] += f"\n\n{agent_context}"

        image_description = None

        # 处理图片 (Legacy)
        if image:
            # 使用阿里云通义VL MAX分析图片
            image_description = self.analyze_image_with_aliyun(image)
            # 将图片描述添加到消息历史中
            messages.append({
                "role": "user",
                "content": f"[图片内容]: {image_description}"
            })

        # 处理新版附件列表
        if attachments:
            for att in attachments:
                att_type = att.get('type')
                content = att.get('content')
                name = att.get('name', 'unknown')
                
                if not content: continue
                
                if att_type == 'image':
                    # Treat as image
                    desc = self.analyze_image_with_aliyun(content)
                    messages.append({"role": "user", "content": f"[附件图片 {name} 内容]: {desc}"})
                elif att_type == 'text':
                    # Treat as text file
                    try:
                        # Extract base64 payload if needed (usually data:text/plain;base64,...)
                        if ',' in content:
                            b64_str = content.split(',', 1)[1]
                        else:
                            b64_str = content
                        
                        file_text = base64.b64decode(b64_str).decode('utf-8')
                        # Limit text size to avoid token overflow
                        if len(file_text) > 10000:
                            file_text = file_text[:10000] + "\n...(truncated)..."
                        
                        messages.append({"role": "user", "content": f"[附件文件 {name}]:\n{file_text}"})
                    except Exception as e:
                        messages.append({"role": "user", "content": f"[附件 {name} 读取失败]: {str(e)}"})

        # 处理文本输入
        if user_input:
            plugin_context = PluginContext(
                user_input=user_input,
                is_admin=is_admin,
                frontend_source=frontend_source,
                attachments=attachments,
                metadata={
                    "image_present": bool(image),
                    "persona_filename": (persona_override or {}).get('filename')
                },
                chat_system=self
            )

            plugin_result = self.plugin_manager.process_input(plugin_context)
            if plugin_result.handled and plugin_result.response is not None:
                plugin_response = self.clean_dsml_markup(plugin_result.response)
                plugin_response = self.plugin_manager.process_response(plugin_context, plugin_response)
                self.db.save_chat(user_input, plugin_response, image_description, persona_filename=effective_persona_filename)
                return plugin_response

            if plugin_result.rewritten_input:
                user_input = plugin_result.rewritten_input
                plugin_context.user_input = user_input

            # 判断是否需要搜索
            if AIChatSystem.should_search(user_input):
                print(f"检测到搜索请求: {user_input}")
                search_result = AIChatSystem.search_with_ai_search(user_input)

                # 检查搜索是否成功
                if "搜索API错误" in search_result or "搜索失败" in search_result:
                    # 如果搜索失败，使用普通聊天模式
                    messages.append({"role": "user", "content": user_input})
                else:
                    # 将搜索结果拼接到当前输入中
                    search_context = f"用户问题: {user_input}\n{search_result}"
                    messages.append({
                        "role": "user",
                        "content": search_context
                    })
                    print(f"搜索结果: {search_result[:100]}...")
            else:
                messages.append({"role": "user", "content": user_input})
        # 如果没有文本输入但有图片
        elif not user_input and image:
            messages.append({"role": "user", "content": "[用户发送了一张图片]"})
        # 如果没有文本输入
        elif not user_input:
            return "请发送文本内容喵~"

        try:
            # 使用DeepSeek-Chat模型生成回复（添加超时）
            
            # --- AGENT EXTENSION ---
            # 获取工具定义
            tools = None
            try:
                if is_admin:
                    tools = self.agent_manager.get_tools_definitions(is_admin)
            except AttributeError:
                # 如果没有初始化 agent_manager
                pass

            api_kwargs = {
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.7,
                # "max_tokens": 200, # 移除硬限制，由 Agent 自行决定
                "timeout": 60      # 增加超时
            }
            
            if tools:
                api_kwargs["tools"] = tools
                # api_kwargs["tool_choice"] = "auto" 

            response = self.client.chat.completions.create(**api_kwargs)
            
            choice = response.choices[0]
            message = choice.message
            
            ai_response = self.clean_dsml_markup(message.content) # 默认回复，清理DSML标记

            # 处理工具调用
            if hasattr(message, 'tool_calls') and message.tool_calls:
                # 将助手的工具调用消息添加到历史
                # 注意：openai python sdk 对象不能直接作为 dict 添加
                # 需要转换格式
                messages.append(message)
                
                tool_calls = message.tool_calls
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    try:
                        # 清理工具参数中的DSML标记
                        raw_arguments = tool_call.function.arguments
                        raw_arguments = AIChatSystem.clean_dsml_markup(raw_arguments)
                        function_args = json.loads(raw_arguments)
                    except:
                        function_args = {}
                    
                    print(f"Executing tool: {function_name} with {function_args}")
                    
                    # 执行工具
                    tool_result = self.agent_manager.execute_tool(
                        function_name,
                        function_args,
                        is_admin=is_admin,
                        frontend_source=frontend_source,
                        user_input=user_input
                    )
                    
                    # 记录操作到 AgentMemory (Short Term)
                    self.agent_manager.record_action("assistant", f"Called {function_name}")
                    self.agent_manager.record_action("system", f"Result: {tool_result}")

                    # 将结果返回给 LLM
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(tool_result)
                    })
                
                # 再次调用 LLM 获取最终回复
                # 注意：这里可能会产生递归，目前只支持一轮工具调用
                try:
                    second_response = self.client.chat.completions.create(
                        model="deepseek-chat",
                        messages=messages,
                        temperature=0.7,
                        timeout=60
                    )
                    ai_response = self.clean_dsml_markup(second_response.choices[0].message.content)
                    
                    # 更新 response 对象以便后续统计
                    response = second_response
                except Exception as e:
                    ai_response = f"工具执行完毕，但生成最终回复时出错: {str(e)}"

            # --- TOKEN COUNTING FIX BEGIN ---
            # 获取token使用情况并更新全局计数
            if hasattr(response, 'usage'):
                prompt_tokens = getattr(response.usage, 'prompt_tokens', 0)
                completion_tokens = getattr(response.usage, 'completion_tokens', 0)
                
                # 尝试更新 web_server 中的全局变量
                try:
                    from src import web_server
                    web_server.INPUT_TOKENS += prompt_tokens
                    web_server.OUTPUT_TOKENS += completion_tokens
                except ImportError:
                    pass
                except Exception as e:
                    print(f"Update token stats failed: {e}")
            # --- TOKEN COUNTING FIX END ---
            
            # 更新 self.messages 以兼容旧代码（虽然主要逻辑已不再依赖它）
            # 注意：这可能会导致 self.messages 增长，但在本设计中它不再是核心
            # 为了防止内存泄漏，可以选择不更新 self.messages 或者定期清理
            # 这里简单追加，但建议在后续代码中尽量使用数据库作为单一事实来源
            # self.messages.append({"role": "assistant", "content": ai_response})

            # 清理DSML标记（二次清理，以防万一）
            ai_response = self.clean_dsml_markup(ai_response)
            response_context = PluginContext(
                user_input=user_input or "",
                is_admin=is_admin,
                frontend_source=frontend_source,
                attachments=attachments,
                metadata={"image_present": bool(image)},
                chat_system=self
            )
            ai_response = self.plugin_manager.process_response(response_context, ai_response)
            
            # 保存对话记录（包括图片描述）
            self.db.save_chat(user_input or "[图片]", ai_response, image_description, persona_filename=effective_persona_filename)

            return ai_response

        except APITimeoutError:
            return "呜...思考太久超时啦Nanaoda! (>_<)"
        except Exception as e:
            return f"呜...出错啦Nanaoda! ({str(e)})"
