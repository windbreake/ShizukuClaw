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

from app.core.config import CONFIG, PROJECT_ROOT, DATA_DIR, generate_system_prompt
from app.database.database import get_connection, DatabaseManager
from app.utils.shared_utils import count_tokens, estimate_tokens
from app.plugin_framework import PluginContext, PluginManager
from app.skill_framework import SkillManager
from app.agent.agent_task_scheduler import get_task_scheduler, AgentTask, TaskType
from app.agent.repo_context_graph import CodeContextGraph
from app.agent.execution_intent_detector import ExecutionIntentDetector

# 全局变量用于跟踪Token使用（需要在web_server.py中更新这些值）
try:
    from app.services.web_server import INPUT_TOKENS, OUTPUT_TOKENS
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
        # Singleton guard: avoid resetting initialized managers on repeated AIChatSystem() calls.
        if getattr(self, '_core_initialized', False):
            return
        # 在单例模式下，核心属性先声明为 None，避免热重载/半初始化阶段出现属性缺失。
        self.db = None
        self.agent_manager = None
        self.plugin_manager = None
        self.skill_manager = None

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
        # 直接从配置中获取系统提示语，不再在代码中生成
        system_prompt = CONFIG['system_prompt']

        # 初始化 Agent Manager
        from app.agent.agent_manager import AgentManager
        self.agent_manager = AgentManager(self, persona_filename=CONFIG.get('active_persona', 'shizuku.json'))

        # 初始化插件框架
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_all()

        # 初始化 Skill 框架（OpenClaw/AstrBot 风格目录）
        project_root = PROJECT_ROOT
        self.skill_manager = SkillManager(project_root)
        self.skill_manager.load_all()

        db = None
        try:
            db = DatabaseManager()
        except Exception:
            db = None

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
        self._last_search_result = ''
        self._last_call_policy = {}
        self._last_call_policy_local = threading.local()
        self.current_persona_state = None
        self.repo_context_graph = CodeContextGraph(PROJECT_ROOT)
        self.repo_context_recent_hashes = []
        self.repo_context_recent_hashes_limit = 80
        retrieval_cfg = CONFIG.get('repo_context_retrieval', {}) or {}
        self.repo_retrieval_enabled = bool(retrieval_cfg.get('enabled', True))
        self.repo_retrieval_mode = str(retrieval_cfg.get('mode', 'coarse2fine') or 'coarse2fine')
        self.repo_retrieval_gamma = float(retrieval_cfg.get('gamma', 0.25) or 0.25)
        self.repo_retrieval_max_chars = int(retrieval_cfg.get('max_chars', 1800) or 1800)
        self.repo_retrieval_min_remaining_tokens = int(retrieval_cfg.get('min_remaining_tokens', 280) or 280)
        self.history_recall_limit = int(retrieval_cfg.get('history_recall_limit', 3) or 3)
        self.history_recall_max_chars = int(retrieval_cfg.get('history_recall_max_chars', 900) or 900)
        self.repo_retrieval_stats = {
            "total_calls": 0,
            "cache_hits": 0,
            "avg_runtime_ms": 0.0,
            "last_runtime_ms": 0,
            "last_selected_files": [],
        }
        self.current_persona_filename = str(CONFIG.get('active_persona', 'shizuku.json') or 'shizuku.json').strip() or 'shizuku.json'

        # 实时搜索订阅存储
        project_root = PROJECT_ROOT
        from app.core.config import DATA_DIR
        os.makedirs(DATA_DIR, exist_ok=True)
        self.realtime_subscriptions_path = os.path.join(DATA_DIR, 'realtime_subscriptions.json')
        self.realtime_updates_path = os.path.join(DATA_DIR, 'realtime_updates.json')
        self._realtime_lock = threading.Lock()
        self._ensure_realtime_storage_files()
        self._bothub_pending = {}
        self._bothub_pending_lock = threading.Lock()
        self._bothub_pending_ttl_seconds = 45.0
        self._core_initialized = True

    def _ensure_initialized(self) -> bool:
        """Ensure core managers exist before using feature methods."""
        skill_manager = getattr(self, 'skill_manager', None)
        plugin_manager = getattr(self, 'plugin_manager', None)
        db = getattr(self, 'db', None)
        if skill_manager is not None and plugin_manager is not None and db is not None:
            return True

        try:
            self.initialize()
            return True
        except Exception:
            return False

    def _set_last_call_policy(self, policy: dict, route: str = '') -> None:
        payload = dict(policy or {})
        if route:
            payload['route'] = str(route)
        payload['timestamp'] = datetime.now().isoformat()
        try:
            self._last_call_policy_local.payload = payload
        except Exception:
            pass
        self._last_call_policy = payload

    def get_last_call_policy(self) -> dict:
        try:
            local_payload = getattr(self._last_call_policy_local, 'payload', None)
            if isinstance(local_payload, dict):
                return dict(local_payload)
        except Exception:
            pass
        return dict(getattr(self, '_last_call_policy', {}) or {})

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

    def delete_plugin(self, plugin_name):
        """Delete an external plugin project and unregister it."""
        return self.plugin_manager.delete_plugin_project(plugin_name)

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

    def reload_skills(self):
        """Reload skill framework and return latest status."""
        if not self._ensure_initialized():
            return {'enabled': False, 'degraded': True, 'error': 'Skill system is not initialized'}
        if self.skill_manager is None:
            self.skill_manager = SkillManager(PROJECT_ROOT)
            self.skill_manager.load_all()
        self.skill_manager.reload_all()
        return self.skill_manager.get_framework_status()

    def get_skill_status(self):
        """Return skill framework status for admin API/UI."""
        if not self._ensure_initialized():
            return {'enabled': False, 'degraded': True, 'error': 'Skill system is not initialized'}
        if self.skill_manager is None:
            self.skill_manager = SkillManager(PROJECT_ROOT)
            self.skill_manager.load_all()
        return self.skill_manager.get_framework_status()

    def set_skill_framework_enabled(self, enabled):
        """Enable or disable the skill framework."""
        if not self._ensure_initialized():
            return {'enabled': False, 'degraded': True, 'error': 'Skill system is not initialized'}
        self.skill_manager.set_framework_enabled(bool(enabled), persist=True)
        return self.skill_manager.get_framework_status()

    def update_skill_policy(self, skill_id, policy):
        """Update skill policy and return normalized policy."""
        if not self._ensure_initialized():
            return {'enabled': False, 'degraded': True, 'error': 'Skill system is not initialized'}
        return self.skill_manager.update_skill_policy(skill_id, policy, persist=True)

    def delete_skill(self, skill_id):
        """Delete a skill project directory and unregister it."""
        if not self._ensure_initialized():
            return {'enabled': False, 'degraded': True, 'error': 'Skill system is not initialized'}
        return self.skill_manager.delete_skill_project(skill_id)

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
        quick_ack_replies = persona_data.get('quick_ack_replies', {})
        if not isinstance(quick_ack_replies, dict):
            quick_ack_replies = {}
        try:
            no_repeat_window = int(persona_data.get('quick_ack_no_repeat_window', 3) or 3)
        except Exception:
            no_repeat_window = 3
        no_repeat_window = max(0, min(no_repeat_window, 8))

        detemplate_openers = persona_data.get('detemplate_openers', [])
        if isinstance(detemplate_openers, str):
            detemplate_openers = [detemplate_openers]
        if not isinstance(detemplate_openers, list):
            detemplate_openers = []
        detemplate_openers = [str(x).strip() for x in detemplate_openers if str(x).strip()]

        try:
            detemplate_no_repeat_window = int(persona_data.get('detemplate_no_repeat_window', 4) or 4)
        except Exception:
            detemplate_no_repeat_window = 4
        detemplate_no_repeat_window = max(0, min(detemplate_no_repeat_window, 10))

        return {
            'reply_style': persona_data.get('reply_style', ''),
            'states': persona_data.get('states', []),
            'state_probability': persona_data.get('state_probability', 0.3),
            'plan_style': persona_data.get('plan_style', ''),
            'plan_style_private': persona_data.get('plan_style_private', ''),
            'plan_style_group': persona_data.get('plan_style_group', ''),
            'state_weights': persona_data.get('state_weights', []),
            'enable_expression_learning': persona_data.get('enable_expression_learning', True),
            'behavior_rules': persona_data.get('behavior_rules', []),
            'command_responses': persona_data.get('command_responses', {}),
            'quick_ack_replies': quick_ack_replies,
            'quick_ack_no_repeat_window': no_repeat_window,
            'detemplate_openers': detemplate_openers,
            'detemplate_no_repeat_window': detemplate_no_repeat_window,
        }

    @staticmethod
    def _should_enable_agent_tools(is_admin: bool, is_simple_chat: bool, run_request: bool) -> bool:
        """仅在明确执行请求时启用工具，普通聊天保持纯 chat 模式。"""
        return bool(is_admin) and bool(run_request) and (not bool(is_simple_chat))

    @staticmethod
    def _build_call_policy(
        *,
        is_admin: bool,
        frontend_source: str,
        normalized_input: str,
        image,
        attachments,
        execution_intent: dict,
    ) -> dict:
        """统一决策入口：按语境确定模型/工具/检索调用策略。"""
        text = str(normalized_input or '').strip()
        has_extra_inputs = bool(image) or bool(attachments)
        run_request = bool((execution_intent or {}).get('is_execution_request')) and bool((execution_intent or {}).get('allow_auto_execute', True))
        is_search_intent = AIChatSystem.should_search(text) if text else False

        is_simple_chat = (
            (not bool(is_admin))
            and (not has_extra_inputs)
            and (not any(kw in text.lower() for kw in ['运行', '执行', '跑起来', '调试', '自检', '检查', '启动', 'run', 'test', 'pytest', 'debug']))
            and (not is_search_intent)
        )

        lightweight_chat_mode = AIChatSystem._should_use_lightweight_chat_mode(is_simple_chat, execution_intent or {}, text)
        text_lower = text.lower()
        coding_intent = bool(re.search(
            r'(代码|报错|异常|调试|修复|重构|测试|堆栈|函数|类|仓库|脚本|工程|编译|部署|性能|优化|traceback|error|exception|debug|fix|refactor|test|pytest|stack|function|class|repo|script|build|deploy|performance)',
            text_lower,
            re.IGNORECASE,
        ))
        history_ref_intent = bool(re.search(
            r'(上次|刚才|之前|历史|回顾|继续|接着|延续|remember|previous|last\s*time|continue)',
            text_lower,
            re.IGNORECASE,
        ))

        # AstrBot风格：重上下文能力按需打开，默认优先轻载主链路。
        enable_repo_context = (not lightweight_chat_mode) and (run_request or coding_intent)
        enable_history_recall = (not lightweight_chat_mode) and history_ref_intent
        context_max_turns = 3 if lightweight_chat_mode else (8 if run_request else 6)

        return {
            'run_request': run_request,
            'is_search_intent': is_search_intent,
            'is_simple_chat': is_simple_chat,
            'lightweight_chat_mode': lightweight_chat_mode,
            'has_onebot_command_check': (str(frontend_source or '') == 'onebot' and bool(text)),
            'use_low_signal_shortcut': False,
            'load_agent_context': (not is_simple_chat),
            'enable_plugin_pipeline': (not is_simple_chat),
            'enable_search_pipeline': ((not is_simple_chat) and (not run_request)),
            'enable_tools': AIChatSystem._should_enable_agent_tools(is_admin, is_simple_chat, run_request),
            'allow_model_fallback': (bool(run_request) and (not lightweight_chat_mode)),
            'enable_repo_context': enable_repo_context,
            'enable_history_recall': enable_history_recall,
            'context_max_turns': context_max_turns,
        }

    @staticmethod
    def _trim_recent_messages_to_token_budget(recent_messages: list, context_messages: list, max_tokens: int) -> list:
        """AstrBot风格上下文裁剪：优先保留最近对话，避免循环重算整段token。"""
        recent = list(recent_messages or [])
        context = list(context_messages or [])

        if not recent:
            return []

        base_tokens = estimate_tokens(context)
        budget = int(max_tokens or 0) - int(base_tokens or 0)
        if budget <= 0:
            return [recent[-1]]

        kept_reversed = []
        used_tokens = 0

        for item in reversed(recent):
            item_tokens = estimate_tokens([item])
            if kept_reversed and (used_tokens + item_tokens > budget):
                break
            if item_tokens > budget and not kept_reversed:
                kept_reversed.append(item)
                break
            if used_tokens + item_tokens <= budget:
                kept_reversed.append(item)
                used_tokens += item_tokens

        if not kept_reversed:
            kept_reversed.append(recent[-1])

        return list(reversed(kept_reversed))

    @staticmethod
    def _extract_bothub_selector(command_text: str) -> Optional[str]:
        command = str(command_text or '').strip().lower()
        if not command:
            return None

        match = re.search(r'(^|\s)/bothub(?:\s+([^\s]+))?(?=\s|$)', command)
        if not match:
            return None

        raw_selector = str(match.group(2) or '').strip()
        if not raw_selector:
            return ''

        return raw_selector

    @staticmethod
    def _contains_invalid_bothub_variant(command_text: str) -> bool:
        command = str(command_text or '').strip().lower()
        if not command:
            return False
        return re.search(r'(^|\s)/bothub\S+', command) is not None

    def _list_persona_records(self):
        personas_dir = os.path.join(DATA_DIR, 'personas')
        active = str(CONFIG.get('active_persona', 'shizuku.json') or 'shizuku.json').strip()

        records = []
        if not os.path.exists(personas_dir):
            return records

        for filename in sorted([item for item in os.listdir(personas_dir) if item.endswith('.json')]):
            persona_path = os.path.join(personas_dir, filename)
            try:
                with open(persona_path, 'r', encoding='utf-8') as f:
                    persona_data = json.load(f)
                meta = persona_data.get('meta', {}) if isinstance(persona_data, dict) else {}
                character = persona_data.get('character', {}) if isinstance(persona_data, dict) else {}
                display_name = str(meta.get('name') or character.get('name') or filename).strip()
                records.append({
                    'filename': filename,
                    'name': display_name,
                    'active': filename == active
                })
            except Exception:
                continue

        return records

    def _format_bothub_menu(self) -> str:
        records = self._list_persona_records()
        lines = ['bot hub界面', '请选择你要使用的设置：']
        if not records:
            lines.append('当前没有可用的人格')
            return '\n'.join(lines)

        lines.append('角色卡列表')
        for idx, record in enumerate(records, start=1):
            suffix = '（当前）' if record.get('active') else ''
            lines.append(f'{idx}.{record.get("name", "未命名")}{suffix}')
        return '\n'.join(lines)

    def _activate_persona_by_selector(self, selector: str) -> str:
        chat_settings = (CONFIG.get('work_mode', {}) or {}).get('chat_settings', {}) or {}
        bothub_enabled = bool(chat_settings.get('bothub_enabled', True))
        if not bothub_enabled:
            return 'bothub 指令已关闭，请在控制面板的聊天设置中开启后使用。'

        records = self._list_persona_records()
        if not records:
            return '当前没有可用的人格'

        normalized = str(selector or '').strip()
        if not normalized:
            return '请输入要切换的人格编号或类型'

        if re.fullmatch(r'\d+', normalized):
            selection_index = int(normalized)
            if selection_index < 1 or selection_index > len(records):
                return f'人格编号无效，请输入 1-{len(records)} 之间的数字'
            selected = records[selection_index - 1]
            selected_label = f'人格{selection_index}'
        else:
            key = normalized.lower()
            selected = None
            for idx, item in enumerate(records, start=1):
                filename = str(item.get('filename', '')).strip().lower()
                stem = filename[:-5] if filename.endswith('.json') else filename
                name = str(item.get('name', '')).strip().lower()
                if key in {filename, stem, name}:
                    selected = item
                    selected_label = f'人格{idx}'
                    break
            if selected is None:
                for idx, item in enumerate(records, start=1):
                    filename = str(item.get('filename', '')).strip().lower()
                    stem = filename[:-5] if filename.endswith('.json') else filename
                    name = str(item.get('name', '')).strip().lower()
                    if key in name or key in stem:
                        selected = item
                        selected_label = f'人格{idx}'
                        break
            if selected is None:
                return f'未找到类型“{normalized}”，请使用 /bothub 查看可选项'
        project_root = PROJECT_ROOT
        from app.core.config import DATA_DIR
        config_path = os.path.join(DATA_DIR, 'config.json')

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

        cfg['active_persona'] = selected['filename']
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        from app.core.config import load_config
        new_conf = load_config()
        CONFIG.update(new_conf)
        self.system_prompt = CONFIG.get('system_prompt', self.system_prompt)
        self.persona_runtime = CONFIG.get('persona_runtime', self.persona_runtime)
        self.current_persona_state = None
        self.current_persona_filename = selected['filename']
        try:
            if hasattr(self, 'agent_manager') and self.agent_manager:
                self.agent_manager.set_persona_context(selected['filename'])
        except Exception:
            pass

        return f'{selected_label}.“{selected["name"]}”成功加载'

    def _resolve_command_response(self, command_text: str, onebot_meta: Optional[dict] = None) -> Optional[str]:
        meta = onebot_meta or {}
        conversation_key = str(meta.get('conversation_key', '') or '').strip()
        sender_id = str(meta.get('sender_id', '') or meta.get('user_id', '') or '').strip()

        chat_settings = (CONFIG.get('work_mode', {}) or {}).get('chat_settings', {}) or {}
        bothub_enabled = bool(chat_settings.get('bothub_enabled', True))
        if not bothub_enabled:
            if self._extract_bothub_selector(command_text) is not None:
                return 'bothub 指令已关闭，请在控制面板的聊天设置中开启后使用。'

        if self._contains_invalid_bothub_variant(command_text):
            return 'bothub 指令格式错误，请使用 @机器人 /bothub <类型/序号>'

        selector = self._extract_bothub_selector(command_text)
        if selector is not None:
            if selector == '':
                menu = self._format_bothub_menu()
                return f'{menu}\n请使用 @机器人 /bothub <类型/序号> 进行选择（例如 @机器人 /bothub 1）'

            result = self._activate_persona_by_selector(selector)
            return result

        return None

    @staticmethod
    def _resolve_persona_override(persona_filename: str):
        filename = (persona_filename or '').strip()
        if not filename:
            return None
        if not filename.endswith('.json'):
            filename += '.json'
        if '/' in filename or '\\' in filename or '..' in filename:
            raise ValueError('invalid persona filename')

        persona_path = os.path.join(DATA_DIR, 'personas', filename)
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

    @staticmethod
    def _should_skip_chat_history(user_input: str, assistant_reply: str) -> bool:
        text = str(assistant_reply or '').strip()
        if not text:
            return True
        menu_markers = ['bot hub界面', '请选择你要使用的设置', '请使用 @机器人 /bothub', 'bothub 指令已关闭']
        if any(marker in text for marker in menu_markers):
            return True
        user_text = str(user_input or '').strip().lower()
        if user_text in {'/bothub', '/bothub ', '/hub', '/hub '}:
            return True
        return False

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

    def _extract_thinking_content(self, raw_content):
        """从原始响应中提取思考内容
        
        支持多种思考内容格式：
        1. <thinking>...</thinking>
        2. <think>...</think>
        3. <Thought>...</Thought>
        4. 以“思考:”、“Thought:”等开头的内容
        
        Args:
            raw_content: 模型的原始响应内容
            
        Returns:
            str: 提取的思考内容，如果没有则返回空字符串
        """
        if not raw_content:
            return ''
        
        # 尝试匹配 XML 风格的思考标签
        thinking_patterns = [
            r'<thinking>(.*?)</thinking>',
            r'<Thought>(.*?)</Thought>',
            r'<thought>(.*?)</thought>',
            r'<think>(.*?)</think>',
            r'<Thinking>(.*?)</Thinking>',
        ]
        
        for pattern in thinking_patterns:
            match = re.search(pattern, raw_content, re.DOTALL | re.IGNORECASE)
            if match:
                thinking = match.group(1).strip()
                if thinking:
                    return f"思考:\n{thinking}"
        
        # 尝试匹配以特定前缀开头的思考内容
        lines = raw_content.split('\n')
        thinking_lines = []
        in_thinking = False
        
        thinking_prefixes = ['思考:', 'Thought:', 'Thinking:', '让我想想', '分析一下']
        
        for line in lines:
            stripped = line.strip()
            
            # 检查是否开始思考
            if not in_thinking and any(stripped.startswith(p) for p in thinking_prefixes):
                in_thinking = True
                thinking_lines.append(stripped)
                continue
            
            # 如果在思考中，继续收集
            if in_thinking:
                # 检查是否结束思考（遇到明显的回复开始）
                if stripped and not stripped.startswith(('思考:', 'Thought:', '因为', '所以', '但是', '然而', '首先', '其次', '最后')):
                    # 如果这一行看起来像是正式回复，停止收集
                    if len(thinking_lines) > 0 and not any(word in stripped for word in ['因为', '所以', '可能', '应该']):
                        break
                thinking_lines.append(line)
        
        if thinking_lines:
            result = '\n'.join(thinking_lines).strip()
            # 如果提取的内容太短，不认为是思考
            if len(result) > 20:
                return result
        
        return ''

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
        from app.utils.shared_utils import should_search as util_should_search
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
            from app.services.web_server import INPUT_TOKENS, OUTPUT_TOKENS
            INPUT_TOKENS += prompt_tokens
            OUTPUT_TOKENS += completion_tokens
        except ImportError:
            INPUT_TOKENS += prompt_tokens
            OUTPUT_TOKENS += completion_tokens

        return content, prompt_tokens, completion_tokens

    @staticmethod
    def _is_retryable_chat_error(exc: Exception) -> bool:
        """判断是否属于可重试的上游临时错误。"""
        text = f"{type(exc).__name__}: {str(exc)}".lower()
        retryable_keywords = (
            '502',
            '503',
            '504',
            'internalservererror',
            'badgateway',
            'serviceunavailable',
            'gateway',
            'temporarily unavailable',
            'timeout',
            'connection reset',
            'connection aborted',
        )
        return any(k in text for k in retryable_keywords)

    def _get_chat_model_candidates(self, preferred_model: Optional[str] = None, allow_fallback: bool = True) -> List[str]:
        """返回聊天模型候选列表（主模型 + 可选回退模型）。"""
        api_cfg = CONFIG.get('api', {}) or {}

        candidates = []
        if preferred_model:
            candidates.append(str(preferred_model).strip())

        primary_model = str(api_cfg.get('model') or 'deepseek-chat').strip()
        if primary_model:
            candidates.append(primary_model)

        if allow_fallback:
            fallback_models = api_cfg.get('fallback_models', [])
            if isinstance(fallback_models, str):
                fallback_models = [m.strip() for m in fallback_models.split(',') if m.strip()]
            elif not isinstance(fallback_models, list):
                fallback_models = []

            for model in fallback_models:
                m = str(model).strip()
                if m:
                    candidates.append(m)

        # 去重并保序
        dedup = []
        seen = set()
        for item in candidates:
            if item and item not in seen:
                dedup.append(item)
                seen.add(item)

        if not dedup:
            dedup = ['deepseek-chat']
        return dedup

    def _create_chat_completion_with_retry(self, api_kwargs: dict, preferred_model: Optional[str] = None, allow_fallback: bool = True):
        """带重试与模型回退的聊天调用，缓解上游 502 等瞬时故障。"""
        model_candidates = self._get_chat_model_candidates(preferred_model, allow_fallback=allow_fallback)
        max_retries = 3
        last_error = None
        errors = []

        for model in model_candidates:
            kwargs = dict(api_kwargs)
            kwargs['model'] = model

            for attempt in range(1, max_retries + 1):
                try:
                    response = self.client.chat.completions.create(**kwargs)
                    return response, model
                except Exception as exc:
                    last_error = exc
                    errors.append(f"{model}#{attempt}: {type(exc).__name__}: {str(exc)[:180]}")

                    if attempt < max_retries and self._is_retryable_chat_error(exc):
                        time.sleep(min(1.0 * (2 ** (attempt - 1)), 4.0))
                        continue
                    break

        summary = ' | '.join(errors[-6:]) if errors else 'unknown error'
        raise RuntimeError(f"All chat models failed: {summary}") from last_error

    def _create_chat_completion_stream_with_retry(self, api_kwargs: dict, preferred_model: Optional[str] = None, allow_fallback: bool = True):
        """带重试与模型回退的流式聊天调用。"""
        model_candidates = self._get_chat_model_candidates(preferred_model, allow_fallback=allow_fallback)
        max_retries = 3
        last_error = None
        errors = []

        for model in model_candidates:
            kwargs = dict(api_kwargs)
            kwargs['model'] = model
            kwargs['stream'] = True

            for attempt in range(1, max_retries + 1):
                try:
                    response = self.client.chat.completions.create(**kwargs)
                    return response, model
                except Exception as exc:
                    last_error = exc
                    errors.append(f"{model}#{attempt}: {type(exc).__name__}: {str(exc)[:180]}")

                    if attempt < max_retries and self._is_retryable_chat_error(exc):
                        time.sleep(min(1.0 * (2 ** (attempt - 1)), 4.0))
                        continue
                    break

        summary = ' | '.join(errors[-6:]) if errors else 'unknown error'
        raise RuntimeError(f"All chat models failed: {summary}") from last_error

    @staticmethod
    def _is_long_term_memory_request(user_input: str) -> bool:
        text = str(user_input or '').strip().lower()
        if not text:
            return False
        compact = re.sub(r'\s+', '', text)
        keywords = [
            '查看长期记忆',
            '显示长期记忆',
            '读取长期记忆',
            '看看长期记忆',
            'longtermmemory',
            'showlongtermmemory',
            'viewlongtermmemory',
        ]
        if any(k in compact for k in keywords):
            return True
        return bool(re.search(r'(查看|显示|读取|看看).*(长期记忆)', text))

    @staticmethod
    def _format_long_term_memory_reply(payload: dict) -> str:
        persona = str((payload or {}).get('persona_filename') or 'default')
        long_term = str((payload or {}).get('long_term') or '暂无长期记忆。').strip() or '暂无长期记忆。'
        meta = (payload or {}).get('meta') if isinstance(payload, dict) else None

        lines = [f"【长期记忆】角色: {persona}", "", long_term]
        if isinstance(meta, dict):
            lines.extend([
                "",
                "【长期记忆状态】",
                f"- 距离上次自动更新的对话轮次: {int(meta.get('dialog_turns_since_long_term_update') or 0)}",
                f"- 总计已记录对话轮次: {int(meta.get('total_dialog_turns') or 0)}",
                f"- 自动更新阈值: {int(meta.get('long_term_update_interval') or 0)}",
                f"- 上次自动更新时间: {str(meta.get('last_long_term_update_at') or '暂无')}",
            ])
        return "\n".join(lines)

    def stream_chat(self, user_input, image=None, is_admin=False, attachments=None, frontend_source='control_panel', persona_filename=None, onebot_meta=None):
        """真实流式聊天：优先增量输出；复杂场景回退到同步链路。"""
        normalized_input = str(user_input or '').strip()

        active_persona_filename = str(CONFIG.get('active_persona', 'shizuku.json') or 'shizuku.json').strip() or 'shizuku.json'
        if not persona_filename:
            persona_filename = active_persona_filename

        persona_override = None
        if persona_filename:
            try:
                persona_override = self._resolve_persona_override(persona_filename)
            except Exception as e:
                yield f"角色卡加载失败: {str(e)}"
                return

        effective_persona_filename = (persona_override or {}).get('filename') or active_persona_filename

        if self._is_long_term_memory_request(normalized_input):
            try:
                if hasattr(self, 'agent_manager') and self.agent_manager:
                    self.agent_manager.set_persona_context(effective_persona_filename)
                    memory_payload = self.agent_manager.memory.get_long_term_memory_view(
                        persona_filename=effective_persona_filename,
                        include_meta=True
                    )
                    yield self._format_long_term_memory_reply(memory_payload)
                    return
            except Exception:
                pass

        execution_intent = ExecutionIntentDetector.detect(
            normalized_input,
            is_admin=is_admin,
            frontend_source=frontend_source
        )
        call_policy = AIChatSystem._build_call_policy(
            is_admin=is_admin,
            frontend_source=frontend_source,
            normalized_input=normalized_input,
            image=image,
            attachments=attachments,
            execution_intent=execution_intent,
        )
        self._set_last_call_policy(call_policy, route='precheck_stream')

        # 复杂路径（执行/工具/附件）保持原同步实现，确保行为一致。
        if image or attachments or call_policy.get('run_request') or call_policy.get('enable_tools'):
            yield str(self.chat(
                user_input,
                image=image,
                is_admin=is_admin,
                attachments=attachments,
                frontend_source=frontend_source,
                persona_filename=persona_filename,
                onebot_meta=onebot_meta,
            ) or '')
            return

        if call_policy.get('has_onebot_command_check'):
            command_response = self._resolve_command_response(normalized_input, onebot_meta=onebot_meta)
            if command_response:
                self._set_last_call_policy(call_policy, route='onebot_command_stream')
                yield str(command_response)
                return

        if getattr(self, 'current_persona_filename', None) != effective_persona_filename:
            self.current_persona_state = None
        self.current_persona_filename = effective_persona_filename

        try:
            if hasattr(self, 'agent_manager') and self.agent_manager:
                self.agent_manager.set_persona_context(effective_persona_filename)
        except Exception:
            pass

        lightweight_chat_mode = bool(call_policy.get('lightweight_chat_mode'))
        is_simple_chat = bool(call_policy.get('is_simple_chat'))

        agent_context = ""
        if call_policy.get('load_agent_context'):
            try:
                agent_context = self.agent_manager.get_agent_context(persona_filename=effective_persona_filename)
            except Exception:
                agent_context = ""

        messages = self.build_chat_context(
            user_input,
            frontend_source=frontend_source,
            system_prompt=(persona_override or {}).get('system_prompt'),
            persona_runtime=(persona_override or {}).get('persona_runtime'),
            persona_filename=effective_persona_filename,
            lightweight_mode=lightweight_chat_mode,
            enable_repo_context=bool(call_policy.get('enable_repo_context')),
            enable_history_recall=bool(call_policy.get('enable_history_recall')),
            context_max_turns=int(call_policy.get('context_max_turns') or 0) or None,
        )

        if not is_simple_chat and messages and messages[0].get('role') == 'system' and agent_context:
            messages[0]['content'] += f"\n\n{agent_context}"

        # 流式模式下若命中插件拦截，直接返回插件结果。
        if user_input and call_policy.get('enable_plugin_pipeline'):
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
                self._set_last_call_policy(call_policy, route='plugin_handled_stream')
                try:
                    self.db.save_chat(user_input, plugin_response, None, persona_filename=effective_persona_filename)
                except Exception:
                    pass
                yield str(plugin_response)
                return
            if plugin_result.rewritten_input:
                user_input = plugin_result.rewritten_input

        # 搜索路径暂时回退同步，避免拆分搜索注入逻辑导致语义漂移。
        if call_policy.get('enable_search_pipeline') and AIChatSystem.should_search(user_input):
            yield str(self.chat(
                user_input,
                image=image,
                is_admin=is_admin,
                attachments=attachments,
                frontend_source=frontend_source,
                persona_filename=persona_filename,
                onebot_meta=onebot_meta,
            ) or '')
            return

        if user_input:
            messages.append({"role": "user", "content": user_input})
            try:
                self.agent_manager.record_action("user", user_input, persona_filename=effective_persona_filename)
            except Exception:
                pass

        api_kwargs = {
            "messages": messages,
            "temperature": 0.7,
            "timeout": 35 if lightweight_chat_mode else 60,
        }
        
        # 【DeepSeek V4 兼容】根据配置启用思考模式（流式）
        chat_settings = (CONFIG.get('work_mode', {}) or {}).get('chat_settings', {})
        enable_thinking = bool(chat_settings.get('deepseek_thinking_mode', False))
        preferred_model = 'deepseek-reasoner' if enable_thinking else None
        
        if enable_thinking:
            # 【官方文档】DeepSeek 思考模式的正确格式
            api_kwargs["extra_body"] = {
                "enable_thinking": True
            }
            print(f"[INFO] Stream chat - DeepSeek thinking mode enabled")

        stream, selected_model = self._create_chat_completion_stream_with_retry(
            api_kwargs,
            preferred_model=preferred_model,
            allow_fallback=bool(call_policy.get('allow_model_fallback')),
        )
        self._set_last_call_policy(
            {
                **call_policy,
                'selected_model': selected_model,
                'tools_attached': False,
            },
            route='chat_completion_stream',
        )

        full_text = ''
        reasoning_content = ''
        prompt_tokens = 0
        completion_tokens = 0
        thinking_start_time = None

        for chunk in stream:
            try:
                usage = getattr(chunk, 'usage', None)
                if usage:
                    prompt_tokens = int(getattr(usage, 'prompt_tokens', 0) or prompt_tokens)
                    completion_tokens = int(getattr(usage, 'completion_tokens', 0) or completion_tokens)
            except Exception:
                pass

            piece = ''
            try:
                choice = (chunk.choices or [None])[0]
                delta = getattr(choice, 'delta', None) if choice is not None else None
                
                # 【DeepSeek 兼容】提取思考内容
                if delta is not None:
                    # 检查 reasoning_content 字段
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        chunk_thinking = str(delta.reasoning_content)
                        reasoning_content += chunk_thinking

                        # 记录开始时间
                        if thinking_start_time is None:
                            import time
                            thinking_start_time = time.time()

                        # 实时记录思考内容到短期记忆（用于前端实时更新）
                        try:
                            self.agent_manager.record_action(
                                "assistant",
                                f"思考:\n{reasoning_content.strip()}",
                                persona_filename=effective_persona_filename,
                            )
                        except Exception:
                            pass

                        # 向上层暴露实时思考增量，供前端做流式预览
                        yield {
                            'type': 'thinking_delta',
                            'text': chunk_thinking,
                        }

                    # 提取普通内容
                    content = getattr(delta, 'content', '')
                    piece = str(content or '')
            except Exception:
                piece = ''

            if piece:
                full_text += piece
                yield piece

        # 【DeepSeek 兼容】记录最终思考内容（包含时间信息）
        if reasoning_content:
            thinking_duration = 0
            if thinking_start_time:
                import time
                thinking_duration = time.time() - thinking_start_time
            
            print(f"[INFO] Stream chat - Thinking completed: {len(reasoning_content)} chars, {thinking_duration:.1f}s")
            
            thinking_formatted = f"思考:\n{reasoning_content.strip()}"
            try:
                self.agent_manager.record_action("assistant", thinking_formatted, persona_filename=effective_persona_filename)
            except Exception:
                pass

        final_reply = self.clean_dsml_markup(full_text).strip() if full_text else ''
        if not final_reply:
            final_reply = '（空回复）'

        try:
            if self.db and not self._should_skip_chat_history(user_input, final_reply):
                print(f"[INFO] Saving chat to database: user_input={user_input[:50]}..., reply_length={len(final_reply)}")
                thinking_text = f"思考:\n{reasoning_content.strip()}" if reasoning_content else None
                self.db.save_chat(user_input or "[图片]", final_reply, None, persona_filename=effective_persona_filename, thinking=thinking_text)
                print(f"[INFO] Chat saved successfully")
            elif not self.db:
                print(f"[WARNING] self.db is None, cannot save chat")
            else:
                print(f"[INFO] Skipping chat history (should_skip=True)")
        except Exception as e:
            print(f"[ERROR] Failed to save chat: {e}")
            import traceback
            traceback.print_exc()

        try:
            self.agent_manager.record_action("assistant", final_reply, persona_filename=effective_persona_filename)
        except Exception:
            pass

        if prompt_tokens or completion_tokens:
            try:
                from app.services import web_server as ws
                ws.INPUT_TOKENS += int(prompt_tokens or 0)
                ws.OUTPUT_TOKENS += int(completion_tokens or 0)
            except Exception:
                pass

    def build_chat_context(
        self,
        user_input,
        max_tokens=2500,
        frontend_source='control_panel',
        system_prompt=None,
        persona_runtime=None,
        persona_filename=None,
        lightweight_mode=False,
        enable_repo_context=True,
        enable_history_recall=True,
        context_max_turns=None,
    ):
        """
        构建智能上下文：
        1. 系统提示词
        2. 相关历史记忆（通过搜索提取的深层记忆）
        3. 最近对话窗口（短期记忆）
        4. 当前用户输入
        """
        # 1. 读取最近短期记忆（后续用于动态人格构建）
        if context_max_turns is None:
            context_max_turns = 3 if lightweight_mode else 6
        recent_limit = max(2, int(context_max_turns) * 2)
        recent_messages = self.db.get_recent_chat_history(limit=recent_limit, persona_filename=persona_filename)

        # 2. 动态系统提示词（人格状态 + 行为规划 + 表达学习）
        dynamic_system_prompt = self._build_dynamic_persona_prompt(
            user_input,
            recent_messages,
            frontend_source=frontend_source,
            system_prompt=system_prompt,
            persona_runtime=persona_runtime
        )
        context_messages = [{"role": "system", "content": dynamic_system_prompt}]

        # 轻量聊天：跳过重检索与深层历史回忆，只保留基础系统提示 + 最近对话窗口。
        if lightweight_mode:
            recent_messages = AIChatSystem._trim_recent_messages_to_token_budget(
                recent_messages,
                context_messages,
                max_tokens,
            )
            return context_messages + recent_messages

        # 预估基础token占用，为检索上下文动态分配预算
        base_tokens = estimate_tokens(context_messages) + estimate_tokens(recent_messages)
        remaining_tokens = max(200, max_tokens - base_tokens)
        retrieval_chars_budget = max(450, min(self.repo_retrieval_max_chars, int(remaining_tokens * 2.2)))
        retrieval_top_k = 1 if remaining_tokens < 500 else (2 if remaining_tokens < 900 else 3)

        # 2.1 Repository-level context retrieval (GraphCoder-Lite)
        repo_context = ""
        if enable_repo_context and self.repo_retrieval_enabled and remaining_tokens >= self.repo_retrieval_min_remaining_tokens and user_input and len(user_input) > 3:
            try:
                retrieval_payload = self.db.get_repo_context_cache(
                    user_input,
                    persona_filename=persona_filename
                )

                if retrieval_payload:
                    stats = retrieval_payload.get('stats', {}) if isinstance(retrieval_payload, dict) else {}
                    stats['cache_hit'] = True
                    stats['runtime_ms'] = int(stats.get('runtime_ms', 0) or 0)
                    retrieval_payload['stats'] = stats
                else:
                    retrieval_payload = self.repo_context_graph.retrieve_with_meta(
                        user_input,
                        max_chars=retrieval_chars_budget,
                        top_k=retrieval_top_k,
                        mode=self.repo_retrieval_mode,
                        gamma=self.repo_retrieval_gamma,
                    )
                    self.db.save_repo_context_cache(
                        user_input,
                        retrieval_payload,
                        persona_filename=persona_filename
                    )

                repo_context = self._build_delta_repo_context(retrieval_payload, retrieval_chars_budget)
                self._update_repo_retrieval_stats(retrieval_payload)
            except Exception:
                repo_context = ""

        if repo_context:
            context_messages.append({
                "role": "system",
                "content": f"你可以参考以下与当前问题最相关的仓库代码上下文（已压缩）:\n{repo_context}"
            })
        
        # 3. 回忆技能：如果用户输入较长，尝试搜索相关的深层历史
        if enable_history_recall and user_input and len(user_input) > 4:
            # 简单的关键词提取（取前10个字符作为搜索索引，可优化）
            search_keyword = user_input[:10]
            relevant_history = self.db.search_chat_history(
                search_keyword,
                limit=self.history_recall_limit,
                persona_filename=persona_filename
            )
            
            if relevant_history:
                memory_text = "【相关历史记忆】\n"
                for row in relevant_history:
                    # row[0] is user_input, row[1] is ai_response
                    if row[0] and row[1]:
                        memory_text += f"User: {row[0]}\nAI: {row[1]}\n---\n"

                # 自适应限制历史记忆注入，避免与仓库检索叠加导致token浪费
                history_budget_chars = min(
                    self.history_recall_max_chars,
                    max(280, int(max_tokens * 1.2) - retrieval_chars_budget)
                )
                if len(memory_text) > history_budget_chars:
                    memory_text = memory_text[:history_budget_chars] + "\n...(历史记忆已截断)..."

                # 将相关记忆作为System Prompt的一部分插入，不占用对话轮次
                if memory_text != "【相关历史记忆】\n":
                    context_messages.append({"role": "system", "content": f"你可以参考以下历史对话记录回答：\n{memory_text}"})

        # 4. Token 预算控制 (滑动窗口)
        # 如果历史记录太多，动态移除最早的记录，直到满足max_tokens限制
        recent_messages = AIChatSystem._trim_recent_messages_to_token_budget(
            recent_messages,
            context_messages,
            max_tokens,
        )
            
        return context_messages + recent_messages

    @staticmethod
    def _should_use_lightweight_chat_mode(is_simple_chat: bool, execution_intent: dict, user_input: str) -> bool:
        is_exec = bool((execution_intent or {}).get('is_execution_request'))
        if not is_simple_chat or is_exec:
            return False
        return not AIChatSystem.should_search(str(user_input or ''))

    def _build_delta_repo_context(self, retrieval_payload, max_chars):
        if not isinstance(retrieval_payload, dict):
            return ""

        snippet_blocks = retrieval_payload.get("snippet_blocks", []) or []
        snippet_hashes = retrieval_payload.get("snippet_hashes", []) or []
        terms = retrieval_payload.get("terms", []) or []

        fresh_blocks = []
        fresh_hashes = []
        recent_hash_set = set(self.repo_context_recent_hashes)

        for idx, h in enumerate(snippet_hashes):
            if h in recent_hash_set:
                continue
            if idx < len(snippet_blocks):
                fresh_blocks.append(snippet_blocks[idx])
                fresh_hashes.append(h)

        if not fresh_blocks:
            return ""

        for h in fresh_hashes:
            self.repo_context_recent_hashes.append(h)
        if len(self.repo_context_recent_hashes) > self.repo_context_recent_hashes_limit:
            overflow = len(self.repo_context_recent_hashes) - self.repo_context_recent_hashes_limit
            self.repo_context_recent_hashes = self.repo_context_recent_hashes[overflow:]

        sections = [
            "## Repository Context Graph Retrieval (Delta)",
            f"Query terms: {', '.join(terms)}",
            "",
        ]
        sections.extend(fresh_blocks)
        text = "\n".join(sections)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n(Delta repository context truncated for token budget.)"
        return text

    def _update_repo_retrieval_stats(self, retrieval_payload):
        if not isinstance(retrieval_payload, dict):
            return
        stats = retrieval_payload.get("stats", {}) or {}
        runtime_ms = int(stats.get("runtime_ms", 0) or 0)
        cache_hit = bool(stats.get("cache_hit", False))

        old_calls = int(self.repo_retrieval_stats.get("total_calls", 0))
        new_calls = old_calls + 1
        old_avg = float(self.repo_retrieval_stats.get("avg_runtime_ms", 0.0))
        new_avg = ((old_avg * old_calls) + runtime_ms) / max(new_calls, 1)

        self.repo_retrieval_stats["total_calls"] = new_calls
        self.repo_retrieval_stats["avg_runtime_ms"] = new_avg
        self.repo_retrieval_stats["last_runtime_ms"] = runtime_ms
        self.repo_retrieval_stats["last_selected_files"] = retrieval_payload.get("selected_files", [])[:6]
        if cache_hit:
            self.repo_retrieval_stats["cache_hits"] = int(self.repo_retrieval_stats.get("cache_hits", 0)) + 1

    def get_repo_retrieval_stats(self):
        return dict(self.repo_retrieval_stats)

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

    def chat(self, user_input, image=None, is_admin=False, attachments=None, frontend_source='control_panel', persona_filename=None, onebot_meta=None):
        """处理聊天请求，支持文本、图片及其他附件（无状态优化版）
        
        Args:
            user_input (str): 用户输入文本
            image (str): 图片路径或base64 (Legacy)
            is_admin (bool): 是否为管理员
            attachments (list): 附件列表 [{'name':..., 'type':..., 'content':...}]
        """
        
        # ========== 优化：快速路径（简单聊天） ==========
        # 对于非管理员、无特殊请求的简单聊天，跳过复杂处理以加快响应
        normalized_input = str(user_input or '').strip()

        active_persona_filename = str(CONFIG.get('active_persona', 'shizuku.json') or 'shizuku.json').strip() or 'shizuku.json'
        if not persona_filename:
            persona_filename = active_persona_filename

        persona_override = None
        if persona_filename:
            try:
                persona_override = self._resolve_persona_override(persona_filename)
            except Exception as e:
                return f"角色卡加载失败: {str(e)}"

        effective_persona_filename = (persona_override or {}).get('filename') or active_persona_filename

        if self._is_long_term_memory_request(normalized_input):
            try:
                if hasattr(self, 'agent_manager') and self.agent_manager:
                    self.agent_manager.set_persona_context(effective_persona_filename)
                    memory_payload = self.agent_manager.memory.get_long_term_memory_view(
                        persona_filename=effective_persona_filename,
                        include_meta=True
                    )
                    return self._format_long_term_memory_reply(memory_payload)
            except Exception as e:
                return f"读取长期记忆失败: {str(e)}"

        # 统一走正常聊天链路：短输入也不再本地模板秒回。
        execution_intent = ExecutionIntentDetector.detect(
            normalized_input,
            is_admin=is_admin,
            frontend_source=frontend_source
        )
        call_policy = AIChatSystem._build_call_policy(
            is_admin=is_admin,
            frontend_source=frontend_source,
            normalized_input=normalized_input,
            image=image,
            attachments=attachments,
            execution_intent=execution_intent,
        )
        self._set_last_call_policy(call_policy, route='precheck')
        run_request = bool(call_policy.get('run_request'))
        is_simple_chat = bool(call_policy.get('is_simple_chat'))
        lightweight_chat_mode = bool(call_policy.get('lightweight_chat_mode'))

        if call_policy.get('has_onebot_command_check'):
            command_response = self._resolve_command_response(normalized_input, onebot_meta=onebot_meta)
            if command_response:
                self._set_last_call_policy(call_policy, route='onebot_command')
                if '/bothub' in normalized_input.lower() or '/hub' in normalized_input.lower():
                    try:
                        self.db.purge_command_history(persona_filename=effective_persona_filename)
                    except Exception:
                        pass
                return command_response

        agent_context = ""

        if getattr(self, 'current_persona_filename', None) != effective_persona_filename:
            self.current_persona_state = None
        self.current_persona_filename = effective_persona_filename
        try:
            if hasattr(self, 'agent_manager') and self.agent_manager:
                self.agent_manager.set_persona_context(effective_persona_filename)
        except Exception:
            pass

        agent_context = ""
        # 只在非简单聊天时加载 Agent 上下文
        if call_policy.get('load_agent_context'):
            try:
                agent_context = self.agent_manager.get_agent_context(persona_filename=effective_persona_filename)
            except:
                agent_context = ""
        
        # === 核心变更2：每次动态构建上下文 ===
        messages = self.build_chat_context(
            user_input,
            frontend_source=frontend_source,
            system_prompt=(persona_override or {}).get('system_prompt'),
            persona_runtime=(persona_override or {}).get('persona_runtime'),
            persona_filename=effective_persona_filename,
            lightweight_mode=lightweight_chat_mode,
            enable_repo_context=bool(call_policy.get('enable_repo_context')),
            enable_history_recall=bool(call_policy.get('enable_history_recall')),
            context_max_turns=int(call_policy.get('context_max_turns') or 0) or None,
        )
        
        # 手动将 agent_context 添加到 messages 的第一个系统消息中（只在非简单聊天时）
        if not is_simple_chat and messages and messages[0]['role'] == 'system':
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

        def _build_search_query(text, history_messages):
            raw = str(text or '').strip()
            if not raw:
                return ''

            generic_search = re.compile(
                r'^(网上搜索|上网搜索|搜索一下|搜一下|帮我搜(一下)?|查一下|去网上搜(一下)?|搜索)$',
                re.IGNORECASE
            )
            if not generic_search.search(raw):
                return raw

            for msg in reversed(history_messages or []):
                if str(msg.get('role')) != 'user':
                    continue
                content = str(msg.get('content') or '').strip()
                if not content or content == raw:
                    continue
                if content.startswith('用户问题:'):
                    continue
                if generic_search.search(content):
                    continue
                return f"{content}（优先官网来源，给出可核验数据）"

            return raw

        # 处理文本输入
        if user_input:
            # 对于简单聊天，跳过插件处理和搜索逻辑
            if call_policy.get('enable_plugin_pipeline'):
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
                    self._set_last_call_policy(call_policy, route='plugin_handled')
                    self.db.save_chat(user_input, plugin_response, image_description, persona_filename=effective_persona_filename)
                    try:
                        if user_input:
                            self.agent_manager.record_action("user", user_input, persona_filename=effective_persona_filename)
                        self.agent_manager.record_action("assistant", plugin_response, persona_filename=effective_persona_filename)
                    except Exception:
                        pass
                    return plugin_response

                if plugin_result.rewritten_input:
                    user_input = plugin_result.rewritten_input
                    plugin_context.user_input = user_input

                # 判断是否需要搜索
                if call_policy.get('enable_search_pipeline') and AIChatSystem.should_search(user_input):
                    print(f"检测到搜索请求: {user_input}")
                    search_query = _build_search_query(user_input, messages)
                    try:
                        self.agent_manager.record_action(
                            "assistant",
                            f"Called web_search(query={search_query})",
                            persona_filename=effective_persona_filename
                        )
                    except Exception:
                        pass

                    search_result = AIChatSystem.search_with_ai_search(search_query)

                    try:
                        self.agent_manager.record_action(
                            "system",
                            f"Result: {search_result}",
                            persona_filename=effective_persona_filename
                        )
                    except Exception:
                        pass

                    # 检查搜索是否成功
                    if "搜索API错误" in search_result or "搜索失败" in search_result:
                        # 如果搜索失败，使用普通聊天模式
                        messages.append({"role": "user", "content": user_input})
                    else:
                        # 将搜索结果拼接到当前输入中
                        self._last_search_result = str(search_result or '')[:20000]
                        search_context = f"用户问题: {user_input}\n搜索查询: {search_query}\n{search_result}"
                        messages.append({
                            "role": "user",
                            "content": search_context
                        })
                        print(f"搜索结果: {search_result[:100]}...")
                else:
                    messages.append({"role": "user", "content": user_input})

                try:
                    self.agent_manager.record_action("user", user_input, persona_filename=effective_persona_filename)
                except Exception:
                    pass
            else:
                # 简单聊天快速路径：直接添加用户输入
                messages.append({"role": "user", "content": user_input})
        # 如果没有文本输入但有图片
        elif not user_input and image:
            messages.append({"role": "user", "content": "[用户发送了一张图片]"})
        # 如果没有文本输入
        elif not user_input:
            return "请发送文本内容喵~"

        try:
            # 使用DeepSeek-Chat模型生成回复（添加超时）
            def _extract_code_target(text):
                raw = str(text or '')
                # Capture explicit code/script/project files from user input.
                m = re.findall(
                    r'([A-Za-z0-9_./\\-]+\.(?:py|js|mjs|cjs|ts|tsx|java|go|c|cc|cpp|cxx|cs|csproj|sln|rs|rb|php|ps1|sh))\b',
                    raw,
                    flags=re.IGNORECASE,
                )
                if not m:
                    return ''
                return str(m[-1]).strip("`'\" ").replace('\\', '/')

            def _resolve_code_target(text):
                target = _extract_code_target(text)
                if target:
                    return target
                lower_text = str(text or '').lower()
                if ('贪吃蛇' in str(text or '')) or ('snake' in lower_text):
                    workspace_root = os.path.join(PROJECT_ROOT, 'agent_datas', 'workspace')
                    for cand in ('snake_game.py', 'snake.py'):
                        if os.path.exists(os.path.join(workspace_root, cand)):
                            return cand
                return ''

            def _resolve_project_target(text):
                raw = str(text or '')
                lower_text = raw.lower()
                workspace_root = os.path.join(PROJECT_ROOT, 'agent_datas', 'workspace')

                # Prefer explicit app-like directory names requested by user (e.g. weather-app, climate-app).
                name_candidates = re.findall(r'\b([A-Za-z0-9._-]{2,80}(?:-app|_app|app))\b', raw)
                for cand in reversed(name_candidates):
                    normalized = cand.strip().replace('\\', '/').lstrip('./')
                    if not normalized:
                        continue
                    abs_path = os.path.join(workspace_root, normalized)
                    if os.path.isdir(abs_path):
                        return normalized

                fallback_candidates = []
                for cand in name_candidates:
                    normalized = cand.strip().replace('\\', '/').lstrip('./')
                    if not normalized:
                        continue
                    if normalized.lower() in {'app', 'webapp'}:
                        continue
                    fallback_candidates.append(normalized)
                if fallback_candidates:
                    # Even if directory does not exist yet, prefer explicit user hint
                    # so auto execution won't run on unrelated workspace root projects.
                    return fallback_candidates[-1]

                # If user is clearly asking to create/build an app, keep the explicit directory hint
                # so fallback execution won't accidentally run on unrelated root projects.
                create_like = bool(re.search(r'(create|build|make|scaffold|制作|创建|搭建|开发)', lower_text, re.IGNORECASE))
                if create_like and name_candidates:
                    return str(name_candidates[-1]).strip().replace('\\', '/').lstrip('./')

                return ''

            def _build_project_bootstrap_code(project_dir, start_mode=False):
                """Bootstrap a new web app project deterministically inside an explicit directory.

                The agent should first cd into the requested project directory and ls it,
                then initialize a TypeScript web app when needed, install deps, and start
                the dev server in the foreground/background depending on the requested mode.
                """
                project_dir = str(project_dir or '').replace('\\', '/').lstrip('./')
                if not project_dir:
                    project_dir = 'weather-app'

                return (
                    "import os, subprocess, sys, time, json, shutil\n"
                    f"project_dir = {repr(project_dir)}\n"
                    f"start_mode = {bool(start_mode)}\n"
                    "workspace = os.getcwd()\n"
                    "target = os.path.join(workspace, project_dir)\n"
                    "print('workspace:', workspace)\n"
                    "print('project_dir:', project_dir)\n"
                    "os.makedirs(target, exist_ok=True)\n"
                    "print('cd', project_dir)\n"
                    "print('ls')\n"
                    "try:\n"
                    "    print(sorted(os.listdir(target)))\n"
                    "except Exception as e:\n"
                    "    print('list_error:', str(e))\n"
                    "def run(cmd, cwd=target, timeout=300):\n"
                    "    print('cmd:', cmd)\n"
                    "    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))\n"
                    "pkg_json = os.path.join(target, 'package.json')\n"
                    "if not os.path.exists(pkg_json):\n"
                    "    init_cmd = f'npm create vite@latest {project_dir} -- --template vanilla-ts'\n"
                    "    print('init_cmd:', init_cmd)\n"
                    "    init_res = run(init_cmd, cwd=workspace, timeout=600)\n"
                    "    print('init_returncode:', init_res.returncode)\n"
                    "    if init_res.stdout:\n"
                    "        print('init_stdout:\\n' + init_res.stdout)\n"
                    "    if init_res.stderr:\n"
                    "        print('init_stderr:\\n' + init_res.stderr)\n"
                    "if os.path.exists(pkg_json):\n"
                    "    install_res = run('npm install', timeout=600)\n"
                    "    print('install_returncode:', install_res.returncode)\n"
                    "    if install_res.stdout:\n"
                    "        print('install_stdout:\\n' + install_res.stdout)\n"
                    "    if install_res.stderr:\n"
                    "        print('install_stderr:\\n' + install_res.stderr)\n"
                    "else:\n"
                    "    print('package_json_not_found_after_init')\n"
                    "    sys.exit(1)\n"
                    "if start_mode:\n"
                    "    start_cmd = 'npm run dev -- --host 127.0.0.1 --port 5173'\n"
                    "    print('start_cmd:', start_cmd)\n"
                    "    proc = subprocess.Popen(start_cmd, cwd=target, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                    "    time.sleep(2)\n"
                    "    print('pid:', proc.pid)\n"
                    "    print('alive:', proc.poll() is None)\n"
                    "    print('url:', 'http://127.0.0.1:5173/')\n"
                    "    sys.exit(0 if proc.poll() is None else 1)\n"
                    "else:\n"
                    "    print('start_mode_disabled')\n"
                    "    sys.exit(0)\n"
                )

            def _build_targeted_exec_code(target, start_mode=False):
                # Execute explicit user target with best-effort runtime mapping.
                return (
                    "import os, sys, subprocess, shutil\n"
                    f"target = {repr(str(target or ''))}\n"
                    f"start_mode = {bool(start_mode)}\n"
                    "target = target.replace('\\\\', '/')\n"
                    "ext = os.path.splitext(target)[1].lower()\n"
                    "cwd = os.path.dirname(target) or '.'\n"
                    "base = os.path.basename(target)\n"
                    "def has(cmd):\n"
                    "    return shutil.which(cmd) is not None\n"
                    "cmd = []\n"
                    "if ext == '.py':\n"
                    "    cmd = [sys.executable, base]\n"
                    "elif ext in ('.js', '.mjs', '.cjs'):\n"
                    "    cmd = ['node', base]\n"
                    "elif ext in ('.ts', '.tsx'):\n"
                    "    cmd = ['tsx', base] if has('tsx') else (['npx', '-y', 'tsx', base] if has('npx') else [])\n"
                    "elif ext == '.java':\n"
                    "    cmd = ['java', base]\n"
                    "elif ext == '.go':\n"
                    "    cmd = ['go', 'run', base]\n"
                    "elif ext in ('.rb',):\n"
                    "    cmd = ['ruby', base]\n"
                    "elif ext in ('.php',):\n"
                    "    cmd = ['php', base]\n"
                    "elif ext in ('.ps1',):\n"
                    "    cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', base]\n"
                    "elif ext in ('.sh',):\n"
                    "    cmd = ['bash', base]\n"
                    "elif ext == '.csproj':\n"
                    "    cmd = ['dotnet', 'run', '--project', base]\n"
                    "elif ext == '.sln':\n"
                    "    cmd = ['dotnet', 'build', base]\n"
                    "elif ext in ('.c',):\n"
                    "    out = '_tmp_run.exe' if os.name == 'nt' else '_tmp_run'\n"
                    "    cmd = ['cmd', '/c', f'gcc \"{base}\" -o {out} && {out}'] if os.name == 'nt' else ['bash', '-lc', f'gcc \"{base}\" -o {out} && ./{out}']\n"
                    "elif ext in ('.cc', '.cpp', '.cxx'):\n"
                    "    out = '_tmp_run.exe' if os.name == 'nt' else '_tmp_run'\n"
                    "    cmd = ['cmd', '/c', f'g++ \"{base}\" -o {out} && {out}'] if os.name == 'nt' else ['bash', '-lc', f'g++ \"{base}\" -o {out} && ./{out}']\n"
                    "elif ext == '.rs':\n"
                    "    cmd = ['cargo', 'run'] if os.path.exists(os.path.join(cwd, 'Cargo.toml')) else []\n"
                    "print('target:', target)\n"
                    "print('cwd:', cwd)\n"
                    "if not cmd:\n"
                    "    print('unsupported target extension:', ext)\n"
                    "    sys.exit(3)\n"
                    "print('cmd:', ' '.join(cmd))\n"
                    "def _extract_missing(stderr_text):\n"
                    "    import re as _re\n"
                    "    m = _re.findall(r\"No module named ['\\\"]([A-Za-z0-9_\\-.]+)['\\\"]\", str(stderr_text or ''))\n"
                    "    return list(dict.fromkeys([x.strip() for x in m if str(x).strip()]))\n"
                    "def _run_once(timeout_s):\n"
                    "    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)\n"
                    "if ext == '.py' and start_mode:\n"
                    "    # Probe first to detect missing dependencies quickly.\n"
                    "    try:\n"
                    "        probe = _run_once(8)\n"
                    "        print('probe_returncode:', probe.returncode)\n"
                    "        if probe.stdout:\n"
                    "            print('probe_stdout:\\n' + probe.stdout)\n"
                    "        if probe.stderr:\n"
                    "            print('probe_stderr:\\n' + probe.stderr)\n"
                    "        if probe.returncode != 0:\n"
                    "            err_text = str(probe.stderr or '')\n"
                    "            missing = _extract_missing(probe.stderr)\n"
                    "            if missing:\n"
                    "                print('auto_install_missing:', ','.join(missing))\n"
                    "                pip_res = subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing, cwd=cwd, capture_output=True, text=True, timeout=180)\n"
                    "                print('pip_returncode:', pip_res.returncode)\n"
                    "                if pip_res.stdout:\n"
                    "                    print('pip_stdout:\\n' + pip_res.stdout)\n"
                    "                if pip_res.stderr:\n"
                    "                    print('pip_stderr:\\n' + pip_res.stderr)\n"
                    "                if pip_res.returncode == 0:\n"
                    "                    probe = _run_once(8)\n"
                    "                    print('probe_after_install_returncode:', probe.returncode)\n"
                    "                    if probe.stderr:\n"
                    "                        print('probe_after_install_stderr:\\n' + probe.stderr)\n"
                    "            # One-shot syntax auto-fix for common formatting/indentation issues.\n"
                    "            if probe.returncode != 0 and ('IndentationError' in err_text or 'TabError' in err_text or 'SyntaxError' in err_text):\n"
                    "                print('auto_fix_syntax: trying autopep8 in-place')\n"
                    "                try:\n"
                    "                    chk = subprocess.run([sys.executable, '-m', 'autopep8', '--version'], cwd=cwd, capture_output=True, text=True, timeout=20)\n"
                    "                    if chk.returncode != 0:\n"
                    "                        inst = subprocess.run([sys.executable, '-m', 'pip', 'install', 'autopep8'], cwd=cwd, capture_output=True, text=True, timeout=120)\n"
                    "                        print('autopep8_install_returncode:', inst.returncode)\n"
                    "                    fix = subprocess.run([sys.executable, '-m', 'autopep8', '--in-place', base], cwd=cwd, capture_output=True, text=True, timeout=40)\n"
                    "                    print('autopep8_fix_returncode:', fix.returncode)\n"
                    "                    probe = _run_once(8)\n"
                    "                    print('probe_after_fix_returncode:', probe.returncode)\n"
                    "                    if probe.stderr:\n"
                    "                        print('probe_after_fix_stderr:\\n' + probe.stderr)\n"
                    "                except Exception as _fix_err:\n"
                    "                    print('auto_fix_syntax_error:', str(_fix_err))\n"
                    "    except subprocess.TimeoutExpired:\n"
                    "        print('probe_timeout: target seems long-running, continue start')\n"
                    "    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                    "    import time as _time\n"
                    "    _time.sleep(1.0)\n"
                    "    alive = proc.poll() is None\n"
                    "    print('started_pid:', int(proc.pid))\n"
                    "    print('started_alive:', bool(alive))\n"
                    "    sys.exit(0 if alive else 1)\n"
                    "else:\n"
                    "    res = _run_once(120)\n"
                    "    if ext == '.py' and res.returncode != 0:\n"
                    "        missing = _extract_missing(res.stderr)\n"
                    "        if missing:\n"
                    "            print('auto_install_missing:', ','.join(missing))\n"
                    "            pip_res = subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing, cwd=cwd, capture_output=True, text=True, timeout=180)\n"
                    "            print('pip_returncode:', pip_res.returncode)\n"
                    "            if pip_res.stdout:\n"
                    "                print('pip_stdout:\\n' + pip_res.stdout)\n"
                    "            if pip_res.stderr:\n"
                    "                print('pip_stderr:\\n' + pip_res.stderr)\n"
                    "            if pip_res.returncode == 0:\n"
                    "                res = _run_once(120)\n"
                    "    print('returncode:', res.returncode)\n"
                    "    if res.stdout:\n"
                    "        print('stdout:\\n' + res.stdout)\n"
                    "    if res.stderr:\n"
                    "        print('stderr:\\n' + res.stderr)\n"
                )

            def _is_start_request(text):
                return bool(re.search(r'(启动|运行它|跑起来|launch|start|open)', str(text or ''), re.IGNORECASE))

            def _contains_chart_block(text):
                lower = str(text or '').lower()
                return '```chart' in lower or '```chartjs' in lower

            def _wants_bar_chart(text):
                return bool(re.search(r'(柱状图|条形图|bar\s*chart)', str(text or ''), re.IGNORECASE))

            def _extract_year_value_pairs(text):
                pairs = {}
                for line in str(text or '').splitlines():
                    year_match = re.search(r'\b(20\d{2})\b', line)
                    if not year_match:
                        continue
                    year = int(year_match.group(1))
                    if year < 2000 or year > 2100:
                        continue
                    remain = line.replace(year_match.group(1), ' ', 1)
                    nums = re.findall(r'(?<!\d)(\d{3,6})(?!\d)', remain)
                    if not nums:
                        continue
                    value = int(nums[0])
                    if value <= 0:
                        continue
                    pairs[year] = value
                return sorted(pairs.items(), key=lambda x: x[0])

            def _find_chart_pairs_from_context(current_reply, history_messages):
                candidates = [str(current_reply or '')]
                if getattr(self, '_last_search_result', ''):
                    candidates.append(str(getattr(self, '_last_search_result') or ''))
                for msg in reversed(history_messages or []):
                    c = str(msg.get('content') or '').strip()
                    if c:
                        candidates.append(c)
                    if len(candidates) >= 10:
                        break

                best = []
                for text in candidates:
                    parsed = _extract_year_value_pairs(text)
                    if len(parsed) > len(best):
                        best = parsed
                return best

            def _build_bar_chart_block(pairs, title='数据柱状图'):
                labels = [str(year) for year, _ in pairs]
                values = [int(v) for _, v in pairs]
                config = {
                    'type': 'bar',
                    'data': {
                        'labels': labels,
                        'datasets': [{
                            'label': '人数',
                            'data': values,
                            'backgroundColor': 'rgba(37, 99, 235, 0.70)',
                            'borderColor': 'rgba(29, 78, 216, 1)',
                            'borderWidth': 1
                        }]
                    },
                    'options': {
                        'responsive': True,
                        'plugins': {
                            'title': {'display': True, 'text': title}
                        },
                        'scales': {
                            'y': {'beginAtZero': False}
                        }
                    }
                }
                return "```chart\n" + json.dumps(config, ensure_ascii=False, indent=2) + "\n```"

            def _format_auto_result(raw_result):
                text = str(raw_result or '').strip()
                if not text:
                    return "自动执行：无返回内容。"
                try:
                    obj = json.loads(text)
                except Exception:
                    if len(text) > 1800:
                        text = text[:1800] + "\n...truncated..."
                    return f"自动执行结果:\n{text}"

                ok = bool(obj.get('ok')) if isinstance(obj, dict) else False
                project_type = str(obj.get('project_type', 'unknown')) if isinstance(obj, dict) else 'unknown'
                summary = str(obj.get('summary', '')).strip() if isinstance(obj, dict) else ''
                parts = []
                parts.append(f"自动执行状态: {'成功' if ok else '失败'}")
                parts.append(f"项目类型: {project_type}")
                if summary:
                    parts.append(f"摘要: {summary}")
                if isinstance(obj, dict) and obj.get('exe'):
                    parts.append(f"可执行文件: {obj.get('exe')}")
                if isinstance(obj, dict) and obj.get('pid'):
                    parts.append(f"进程 PID: {obj.get('pid')}")

                steps = obj.get('steps') if isinstance(obj, dict) else None
                if isinstance(steps, list) and steps:
                    step_lines = []
                    for s in steps[:6]:
                        step_name = str(s.get('step', 'step'))
                        code = s.get('return_code', '')
                        step_lines.append(f"- {step_name}: rc={code}")
                    parts.append("步骤:\n" + "\n".join(step_lines))

                return "\n".join(parts)

            def _extract_model_python_action(text):
                """Extract likely Python action code from assistant reply.

                This is used as a generic fallback when the model forgot to call tools
                but clearly produced executable Python operations.
                """
                raw = str(text or '').strip()
                if not raw:
                    return ''

                fenced = re.search(r"```python\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
                if fenced:
                    snippet = str(fenced.group(1) or '').strip()
                    return snippet if snippet else ''

                # Heuristic for plain-text Python action scripts.
                lines = [ln.rstrip() for ln in raw.splitlines() if ln.strip()]
                if not lines:
                    return ''

                joined = "\n".join(lines)
                python_markers = (
                    'import os', 'import sys', 'import subprocess', 'from pathlib import',
                    'os.makedirs(', 'open(', 'with open(', 'subprocess.run(', 'print(',
                )
                if any(marker in joined for marker in python_markers):
                    normalized_code = joined
                    # Heuristic normalization for one-line pseudo-Python like:
                    # "import os os.makedirs(...) print(...)"
                    normalized_code = re.sub(r"\b(import\s+[A-Za-z0-9_\.]+)\s+(?=(?:import|from|os\.|subprocess\.|with\s+open|open\(|print\(|[A-Za-z_][A-Za-z0-9_]*\s*=))", r"\1\n", normalized_code)
                    normalized_code = re.sub(r"\)\s+(?=(?:print\(|os\.|subprocess\.|with\s+open|open\(|[A-Za-z_][A-Za-z0-9_]*\s*=))", r")\n", normalized_code)
                    normalized_code = re.sub(
                        r"#.*?(?=(?:\n|\bimport\b|\bfrom\b|\bos\.|\bsubprocess\.|\bwith\s+open\b|\bopen\(|\bprint\(|\b[A-Za-z_][A-Za-z0-9_]*\s*=|$))",
                        "\n",
                        normalized_code,
                        flags=re.DOTALL,
                    )
                    normalized_code = re.sub(r"\s+if\s+", "\nif ", normalized_code)
                    normalized_code = re.sub(
                        r"((?:\"[^\"\\]*(?:\\.[^\"\\]*)*\"|'[^'\\]*(?:\\.[^'\\]*)*'))\s+(?=(?:print\(|[A-Za-z_][A-Za-z0-9_]*\s*=|if\s|for\s|while\s|try:|except\b|os\.|subprocess\.|sys\.))",
                        r"\1\n",
                        normalized_code,
                    )
                    normalized_code = re.sub(
                        r"(^|\n)(if\s+[^\n:]+):\s+([^\n]+)",
                        r"\1\2:\n    \3",
                        normalized_code,
                    )
                    normalized_code = re.sub(r"\s*;\s*", "\n", normalized_code)
                    # Keep fallback bounded for safety and predictability.
                    return normalized_code[:7000]

                return ''
            
            # --- AGENT EXTENSION ---
            # 获取工具定义（只在需要时获取）
            tools = None
            try:
                if call_policy.get('enable_tools'):
                    tools = self.agent_manager.get_tools_definitions(is_admin)
            except AttributeError:
                # 如果没有初始化 agent_manager
                pass

            api_kwargs = {
                "messages": messages,
                "temperature": 0.7,
                # "max_tokens": 200, # 移除硬限制，由 Agent 自行决定
                "timeout": 35 if lightweight_chat_mode else 60
            }
            
            # 【DeepSeek V4 兼容】根据配置启用思考模式
            chat_settings = (CONFIG.get('work_mode', {}) or {}).get('chat_settings', {})
            enable_thinking = bool(chat_settings.get('deepseek_thinking_mode', False))
            preferred_model = 'deepseek-reasoner' if enable_thinking else None
            
            if enable_thinking:
                # 【官方文档】DeepSeek 思考模式的正确格式
                api_kwargs["extra_body"] = {
                    "enable_thinking": True
                }
                print(f"[INFO] DeepSeek thinking mode enabled")
            
            if tools:
                api_kwargs["tools"] = tools
                # api_kwargs["tool_choice"] = "auto" 

            response, selected_model = self._create_chat_completion_with_retry(
                api_kwargs,
                preferred_model=preferred_model,
                allow_fallback=bool(call_policy.get('allow_model_fallback'))
            )
            self._set_last_call_policy(
                {
                    **call_policy,
                    'selected_model': selected_model,
                    'tools_attached': bool(tools),
                },
                route='chat_completion',
            )
            
            choice = response.choices[0]
            message = choice.message
            
            # 保存原始响应内容，用于提取思考过程
            raw_content = message.content or ''
            
            # 【DeepSeek 兼容】尝试从多种来源提取思考内容
            thinking_content = None
            
            # 方法 1: 检查 reasoning_content 字段（DeepSeek 官方字段）
            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                thinking_content = str(message.reasoning_content).strip()
                print(f"[INFO] Found reasoning_content in message: {len(thinking_content)} chars")
            
            # 方法 2: 从 content 中提取思考标记
            if not thinking_content:
                thinking_content = self._extract_thinking_content(raw_content)
                if thinking_content:
                    print(f"[INFO] Extracted thinking from content: {len(thinking_content)} chars")
            
            # 格式化思考内容
            if thinking_content:
                thinking_content = f"思考:\n{thinking_content}"
                # 记录思考内容到短期记忆
                try:
                    self.agent_manager.record_action("assistant", thinking_content, persona_filename=effective_persona_filename)
                except Exception:
                    pass
            
            ai_response = self.clean_dsml_markup(raw_content) # 默认回复，清理DSML标记
            did_run_execution_tool = False
            executed_tool_summaries = []
            run_execution_tools = {'run_project_debug', 'exec_python', 'git_clone_repo', 'start_web_preview'}
            executed_tool_names = set()

            # 处理工具调用（多轮循环）
            if not is_simple_chat and hasattr(message, 'tool_calls') and message.tool_calls:
                tool_round_message = message
                max_tool_rounds = 4
                tool_round = 0

                while tool_round_message is not None and hasattr(tool_round_message, 'tool_calls') and tool_round_message.tool_calls and tool_round < max_tool_rounds:
                    tool_round += 1
                    # 将助手的工具调用消息添加到历史
                    messages.append(tool_round_message)

                    tool_calls = tool_round_message.tool_calls
                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        try:
                            # 清理工具参数中的DSML标记
                            raw_arguments = tool_call.function.arguments
                            raw_arguments = AIChatSystem.clean_dsml_markup(raw_arguments)
                            function_args = json.loads(raw_arguments)
                        except Exception:
                            function_args = {}

                        print(f"Executing tool(round={tool_round}): {function_name} with {function_args}")

                        # 执行工具
                        tool_result = self.agent_manager.execute_tool(
                            function_name,
                            function_args,
                            is_admin=is_admin,
                            frontend_source=frontend_source,
                            user_input=user_input
                        )
                        executed_tool_names.add(function_name)

                        if function_name in run_execution_tools:
                            did_run_execution_tool = True

                        if function_name in {'run_project_debug', 'exec_python', 'git_clone_repo', 'start_web_preview'}:
                            try:
                                executed_tool_summaries.append(f"{function_name}:\n{_format_auto_result(tool_result)}")
                            except Exception:
                                executed_tool_summaries.append(f"{function_name}:\n{str(tool_result)[:800]}")

                        # 记录操作到 AgentMemory (Short Term)
                        self.agent_manager.record_action("assistant", f"Called {function_name}", persona_filename=effective_persona_filename)
                        self.agent_manager.record_action("system", f"Result: {tool_result}", persona_filename=effective_persona_filename)

                        # 将结果返回给 LLM
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": str(tool_result)
                        })

                    try:
                        # 【DeepSeek V4 兼容】为 follow_response 也启用思考模式
                        chat_settings = (CONFIG.get('work_mode', {}) or {}).get('chat_settings', {})
                        enable_thinking = bool(chat_settings.get('deepseek_thinking_mode', False))
                        
                        follow_api_kwargs = {
                            "messages": messages,
                            "temperature": 0.7,
                            "timeout": 25 if run_request else 60,
                        }
                        
                        if enable_thinking:
                            # 【官方文档】DeepSeek 思考模式的正确格式
                            follow_api_kwargs["extra_body"] = {
                                "enable_thinking": True
                            }
                            print(f"[INFO] DeepSeek follow thinking mode enabled (enable_thinking=True)")
                        
                        follow_response, _ = self._create_chat_completion_with_retry(
                            follow_api_kwargs,
                            preferred_model=selected_model,
                            allow_fallback=False,
                        )
                        response = follow_response
                        follow_message = follow_response.choices[0].message
                        
                        # 【DeepSeek 兼容】尝试从多种来源提取思考内容
                        follow_thinking = None
                        
                        # 方法 1: 检查 reasoning_content 字段
                        if hasattr(follow_message, 'reasoning_content') and follow_message.reasoning_content:
                            follow_thinking = str(follow_message.reasoning_content).strip()
                            print(f"[INFO] Found reasoning_content in follow message: {len(follow_thinking)} chars")
                        
                        # 方法 2: 从 content 中提取思考标记
                        if not follow_thinking:
                            follow_raw_content = follow_message.content or ''
                            follow_thinking = self._extract_thinking_content(follow_raw_content)
                            if follow_thinking:
                                print(f"[INFO] Extracted thinking from follow content: {len(follow_thinking)} chars")
                        
                        # 格式化思考内容
                        if follow_thinking:
                            follow_thinking = f"思考:\n{follow_thinking}"
                            try:
                                self.agent_manager.record_action("assistant", follow_thinking, persona_filename=effective_persona_filename)
                            except Exception:
                                pass
                        
                        ai_response = self.clean_dsml_markup(follow_message.content or '')
                        tool_round_message = follow_message
                    except Exception as e:
                        ai_response = f"工具执行完毕，但生成最终回复时出错: {str(e)}"
                        tool_round_message = None

                if tool_round >= max_tool_rounds and tool_round_message is not None and getattr(tool_round_message, 'tool_calls', None):
                    ai_response = f"{ai_response}\n\n[提示] 工具调用达到最大轮次({max_tool_rounds})，已停止继续调用。"

                if run_request and executed_tool_summaries:
                    confirm = "\n\n[执行确认]\n" + "\n\n".join(executed_tool_summaries[:2])
                    ai_response = f"{ai_response}{confirm}"

            want_start = _is_start_request(user_input)
            code_target = _resolve_code_target(user_input) if run_request else ''
            if is_admin and run_request and code_target and (not did_run_execution_tool) and ('exec_python' not in executed_tool_names):
                targeted_result = self.agent_manager.execute_tool(
                    'exec_python',
                    {'code': _build_targeted_exec_code(code_target, start_mode=want_start), 'filename': 'auto_execute_target.py'},
                    is_admin=is_admin,
                    frontend_source=frontend_source,
                    user_input=user_input
                )
                did_run_execution_tool = True
                self.agent_manager.record_action(
                    "assistant",
                    f"Called exec_python(auto_execute_target={code_target})",
                    persona_filename=effective_persona_filename
                )
                self.agent_manager.record_action(
                    "system",
                    f"Result: {targeted_result}",
                    persona_filename=effective_persona_filename
                )
                ai_response = f"{ai_response}\n\n[补充执行]\n{_format_auto_result(targeted_result)}"

            if is_admin and run_request and not did_run_execution_tool:
                auto_result = ''
                code_target = _resolve_code_target(user_input)
                if code_target:
                    code = _build_targeted_exec_code(code_target, start_mode=want_start)
                    auto_result = self.agent_manager.execute_tool(
                        'exec_python',
                        {'code': code, 'filename': 'auto_execute_request.py'},
                        is_admin=is_admin,
                        frontend_source=frontend_source,
                        user_input=user_input
                    )
                    self.agent_manager.record_action("assistant", "Called exec_python(auto_execute_request)", persona_filename=effective_persona_filename)
                    self.agent_manager.record_action("system", f"Result: {auto_result}", persona_filename=effective_persona_filename)
                else:
                    model_action_code = _extract_model_python_action(ai_response)
                    if model_action_code:
                        auto_result = self.agent_manager.execute_tool(
                            'exec_python',
                            {'code': model_action_code, 'filename': 'auto_model_action.py'},
                            is_admin=is_admin,
                            frontend_source=frontend_source,
                            user_input=user_input
                        )
                        self.agent_manager.record_action("assistant", "Called exec_python(auto_model_action)", persona_filename=effective_persona_filename)
                        self.agent_manager.record_action("system", f"Result: {auto_result}", persona_filename=effective_persona_filename)
                    else:
                        project_target = _resolve_project_target(user_input)
                        app_like_request = bool(re.search(r'(app|webapp|网站|网页|小网页|页面)', str(user_input or ''), re.IGNORECASE))
                        if project_target and app_like_request:
                            auto_result = self.agent_manager.execute_tool(
                                'exec_python',
                                {'code': _build_project_bootstrap_code(project_target, start_mode=want_start), 'filename': 'auto_project_bootstrap.py'},
                                is_admin=is_admin,
                                frontend_source=frontend_source,
                                user_input=user_input
                            )
                            self.agent_manager.record_action("assistant", f"Called exec_python(auto_project_bootstrap={project_target})", persona_filename=effective_persona_filename)
                            self.agent_manager.record_action("system", f"Result: {auto_result}", persona_filename=effective_persona_filename)
                        else:
                            auto_result = self.agent_manager.execute_tool(
                                'run_project_debug',
                                {
                                    'target': project_target or '.',
                                    'run_tests': (not want_start),
                                    'start_app': bool(want_start)
                                },
                                is_admin=is_admin,
                                frontend_source=frontend_source,
                                user_input=user_input
                            )
                            self.agent_manager.record_action("assistant", "Called run_project_debug(auto_execute_request)", persona_filename=effective_persona_filename)
                            self.agent_manager.record_action("system", f"Result: {auto_result}", persona_filename=effective_persona_filename)

                auto_text = _format_auto_result(auto_result)
                ai_response = f"{ai_response}\n\n[自动执行结果]\n{auto_text}"

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

            if user_input and _wants_bar_chart(user_input) and not _contains_chart_block(ai_response):
                pairs = _find_chart_pairs_from_context(ai_response, messages)
                if len(pairs) >= 3:
                    chart_title = str(user_input).strip()[:40] or '数据柱状图'
                    ai_response = (
                        f"{ai_response}\n\n"
                        "已根据对话中的结构化数据自动生成柱状图：\n\n"
                        f"{_build_bar_chart_block(pairs, chart_title)}"
                    )
                    try:
                        self.agent_manager.record_action(
                            "assistant",
                            f"Called chart_synthesizer(pairs={len(pairs)})",
                            persona_filename=effective_persona_filename
                        )
                        self.agent_manager.record_action(
                            "system",
                            f"Result: generated chart block with {len(pairs)} points",
                            persona_filename=effective_persona_filename
                        )
                    except Exception:
                        pass

            # 保存对话记录（包括图片描述）
            self.db.save_chat(user_input or "[图片]", ai_response, image_description, persona_filename=effective_persona_filename)

            try:
                self.agent_manager.record_action("assistant", ai_response, persona_filename=effective_persona_filename)
            except Exception:
                pass

            return ai_response

        except APITimeoutError:
            return "呜...思考太久超时啦Nanaoda! (>_<)"
        except Exception as e:
            return f"呜...出错啦Nanaoda! ({str(e)})"
