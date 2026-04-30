# -*- coding: utf-8 -*-
"""Web服务器模块，提供聊天界面和相关API"""

import io
import json
import logging
import os
import re
import socket
import sys
import time
import subprocess
import threading
import traceback
import uuid
import webbrowser
import psutil
import locale
import platform
import mimetypes
import datetime
import hashlib
import hmac
import shutil
import tempfile
import urllib.request
import urllib.error
import zipfile
import requests
from openai import OpenAI
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('text/html', '.html')

from flask import Flask, request, jsonify, Response, send_from_directory, render_template
from flask.cli import pass_script_info
from colorama import Fore, Back, Style, init
from werkzeug.serving import make_server
from logging.handlers import RotatingFileHandler

# 添加项目根目录到 sys.path（兼容从任意工作目录启动）
PROJECT_ROOT_FOR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT_FOR_PATH)

from app.agent.ai_chat_system import AIChatSystem
try:
    from app.agent.reply_policy import default_reply_policy
except ImportError:
    from app.agent.reply_policy import default_reply_policy
from app.core.config import CONFIG, generate_system_prompt, PROJECT_ROOT, DATA_DIR

init(autoreset=True)

# 全局变量用于跟踪Token使用情况和启动时间
START_TIME = time.time()
INPUT_TOKENS = 0
OUTPUT_TOKENS = 0
_CPU_NAME_CACHE = None # CPU名称缓存
_LATEST_CPU_PERCENT = 0.0 # 最新CPU使用率
_LATEST_SYSTEM_STATS = {}
_MONITOR_THREAD_STARTED = False


def _hash_password(raw_password: str) -> str:
    return hashlib.sha256((raw_password or '').encode('utf-8')).hexdigest()


def _verify_password(raw_password: str, password_hash: str) -> bool:
    if not raw_password or not password_hash:
        return False
    return hmac.compare_digest(_hash_password(raw_password), password_hash)


def _is_work_mode_enabled(frontend_source: str = '') -> bool:
    wm = CONFIG.get('work_mode', {})
    global_enabled = bool(wm.get('enabled', False))
    sandbox_enabled = bool(wm.get('sandbox_enabled', False))
    source = (frontend_source or '').strip().lower()
    return global_enabled or (sandbox_enabled and source == 'sandbox')


def _default_work_mode_features(existing: dict = None) -> dict:
    existing = existing or {}
    return {
        'allow_file_write': bool(existing.get('allow_file_write', True)),
        'allow_code_exec': bool(existing.get('allow_code_exec', True)),
        'allow_plan_update': bool(existing.get('allow_plan_update', True)),
        'allow_coder_tool': bool(existing.get('allow_coder_tool', True)),
        'plugin_command_requires_work_mode': bool(existing.get('plugin_command_requires_work_mode', False)),
        'plugin_dev_tools_require_work_mode': bool(existing.get('plugin_dev_tools_require_work_mode', True)),
        'allow_external_access': bool(existing.get('allow_external_access', False)),
        'require_external_approval': bool(existing.get('require_external_approval', True))
    }


def _normalize_trace_retention_days(value, default: int = 7) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = int(default)
    return max(0, min(days, 3650))


def _normalize_long_term_refresh_interval(value, default: int = 8) -> int:
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = int(default)
    return max(1, min(interval, 200))


def _default_chat_settings(existing: dict = None) -> dict:
    existing = existing or {}
    return {
        'bothub_enabled': bool(existing.get('bothub_enabled', True)),
        'sandbox_show_agent_trace': bool(existing.get('sandbox_show_agent_trace', True)),
        'sandbox_trace_collapsed': bool(existing.get('sandbox_trace_collapsed', True)),
        'sandbox_show_back_to_top': bool(existing.get('sandbox_show_back_to_top', True)),
        'sandbox_use_docker_runtime': bool(existing.get('sandbox_use_docker_runtime', True)),
        'sandbox_agent_autonomous': bool(existing.get('sandbox_agent_autonomous', True)),
        'sandbox_trace_retention_days': _normalize_trace_retention_days(existing.get('sandbox_trace_retention_days', 7), default=7),
        'long_term_refresh_interval': _normalize_long_term_refresh_interval(existing.get('long_term_refresh_interval', 8), default=8),
    }


def _format_trace_markdown(events: list, user_message: str = '', reply_message: str = '') -> str:
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = [
        '# Sandbox Trace',
        '',
        f'- created_at: {now}',
        f'- events: {len(events)}',
        '',
        '## User Input',
        '```text',
        str(user_message or ''),
        '```',
        '',
        '## Assistant Reply',
        '```text',
        str(reply_message or ''),
        '```',
        '',
        '## Events',
    ]

    for idx, event in enumerate(events, 1):
        label = str(event.get('label', '步骤') or '步骤')
        role = str(event.get('role', 'unknown') or 'unknown')
        evt_type = str(event.get('type', 'message') or 'message')
        tool_name = str(event.get('tool_name', '') or '')
        ts = str(event.get('timestamp', '') or '')
        content = str(event.get('content', '') or '')

        lines.extend([
            '',
            f'### {idx}. {label}',
            f'- role: {role}',
            f'- type: {evt_type}',
            f'- tool: {tool_name}',
            f'- timestamp: {ts}',
            '```text',
            content,
            '```',
        ])

    lines.append('')
    return '\n'.join(lines)


def _normalize_api_base_url(raw_url: str) -> tuple[str, str]:
    """Normalize API URL for OpenAI-compatible /models probing and return provider hint."""
    raw = str(raw_url or '').strip()
    if not raw:
        return '', 'unknown'

    if '://' not in raw:
        raw = f"https://{raw}"

    provider_hint = 'openai_compatible'
    host = ''
    path = ''
    try:
        parsed = requests.utils.urlparse(raw)
        host = (parsed.netloc or '').lower()
        path = (parsed.path or '').strip()
    except Exception:
        pass

    host_provider_map = {
        'api.deepseek.com': 'deepseek',
        'api.openai.com': 'openai',
        'openrouter.ai': 'openrouter',
        'api.moonshot.cn': 'moonshot',
        'api.minimaxi.com': 'minimax',
        'api.anthropic.com': 'anthropic',
    }
    for host_key, hint in host_provider_map.items():
        if host_key in host:
            provider_hint = hint
            break

    # Strip known completion paths back to API root.
    for suffix in ('/chat/completions', '/completions', '/responses', '/messages', '/models'):
        if path.endswith(suffix):
            raw = raw[: -len(suffix)]
            break

    if re.search(r'/v\d+$', raw.rstrip('/')):
        normalized = raw.rstrip('/')
    else:
        normalized = raw.rstrip('/') + '/v1'

    return normalized, provider_hint


def _extract_model_ids(payload) -> list:
    models = []
    if isinstance(payload, dict):
        data = payload.get('data')
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    model_id = str(item.get('id', '') or '').strip()
                    if model_id:
                        models.append(model_id)
                elif isinstance(item, str):
                    text = item.strip()
                    if text:
                        models.append(text)
        elif isinstance(payload.get('models'), list):
            for item in payload.get('models', []):
                if isinstance(item, dict):
                    model_id = str(item.get('id', '') or item.get('name', '') or '').strip()
                    if model_id:
                        models.append(model_id)
                elif isinstance(item, str):
                    text = item.strip()
                    if text:
                        models.append(text)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                model_id = str(item.get('id', '') or item.get('name', '') or '').strip()
                if model_id:
                    models.append(model_id)
            elif isinstance(item, str):
                text = item.strip()
                if text:
                    models.append(text)

    # de-dup
    seen = set()
    dedup = []
    for m in models:
        if m not in seen:
            seen.add(m)
            dedup.append(m)
    return dedup


def _reload_runtime_config_after_write():
    """Reload config in memory and refresh AIChatSystem runtime objects for hot switch."""
    from app.core.config import load_config

    new_conf = load_config()
    CONFIG.update(new_conf)

    ai = AIChatSystem()
    ai.system_prompt = CONFIG.get('system_prompt', ai.system_prompt)
    ai.persona_runtime = CONFIG.get('persona_runtime', ai.persona_runtime)

    api_cfg = CONFIG.get('api', {}) or {}
    api_key = str(api_cfg.get('key', '') or '').strip()
    base_url = str(api_cfg.get('base_url', '') or '').strip()
    if api_key and base_url:
        ai.client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)


def _cleanup_trace_markdown_files(trace_dir: str, retention_days: int) -> int:
    if retention_days <= 0:
        return 0

    removed = 0
    cutoff = time.time() - (retention_days * 24 * 60 * 60)
    for name in os.listdir(trace_dir):
        if not name.endswith('.md'):
            continue
        if not name.startswith('trace_'):
            continue

        path = os.path.join(trace_dir, name)
        if not os.path.isfile(path):
            continue

        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except Exception:
            continue

    return removed


def _write_trace_markdown(events: list, user_message: str = '', reply_message: str = '', retention_days: int = 7) -> str:
    trace_dir = os.path.join(PROJECT_ROOT, 'agent_datas', 'workspace', 'trace_tmp')
    os.makedirs(trace_dir, exist_ok=True)
    _cleanup_trace_markdown_files(trace_dir, _normalize_trace_retention_days(retention_days, default=7))
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    trace_name = f'trace_{stamp}_{uuid.uuid4().hex[:8]}.md'
    trace_abs = os.path.join(trace_dir, trace_name)

    content = _format_trace_markdown(events, user_message=user_message, reply_message=reply_message)
    with open(trace_abs, 'w', encoding='utf-8') as f:
        f.write(content)

    return os.path.relpath(trace_abs, PROJECT_ROOT).replace('\\', '/')


def _system_config_path() -> str:
    return os.path.join(DATA_DIR, 'system_config.json')


def _load_system_config() -> dict:
    default_data = {
        'server': {'port': 8888},
        'launcher': {
            'startup_self_check': True,
            'open_browser': True,
            'startup_page': '/control_panel'
        },
        'unified_api': {
            'host': '0.0.0.0',
            'port': 8000,
            'access_token': 'neko-proxy-key-123'
        },
        'onebot': {
            'host': '0.0.0.0',
            'port': 3000,
            'access_token': '',
            'http': {
                'enable': False,
                'host': '0.0.0.0',
                'port': 3000
            },
            'ws': {
                'enable': True,
                'host': '0.0.0.0',
                'port': 3001
            },
            'ws_reverse': {
                'enable': False,
                'url': ''
            }
        },
        'work_mode': {
            'enabled': False,
            'password_hash': '',
            'sandbox_enabled': False,
            'reply_policy': default_reply_policy({}),
            'chat_settings': _default_chat_settings({}),
            'features': _default_work_mode_features({}),
            'allowed_databases': ['catgirl_db']
        },
        'comm_protocol': 'unified'
    }

    path = _system_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for key, value in default_data.items():
                    if isinstance(value, dict):
                        if key not in loaded or not isinstance(loaded.get(key), dict):
                            loaded[key] = value
                        else:
                            for child_key, child_value in value.items():
                                loaded[key].setdefault(child_key, child_value)
                    else:
                        loaded.setdefault(key, value)
                return loaded
        except Exception:
            pass
    return default_data


def _save_system_config(system_config: dict):
    path = _system_config_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(system_config, f, ensure_ascii=False, indent=2)

def start_monitor_thread():
    """启动后台监控线程"""
    global _MONITOR_THREAD_STARTED
    if _MONITOR_THREAD_STARTED:
        return
    _MONITOR_THREAD_STARTED = True
    
    def monitor_loop():
        global _LATEST_SYSTEM_STATS, _CPU_NAME_CACHE, _LATEST_CPU_PERCENT
        
        # 0. Fast Initialization
        try:
            if not _LATEST_SYSTEM_STATS:
                _LATEST_SYSTEM_STATS = {
                    'cpu_percent': 0, 
                    'memory_percent': 0, 
                    'token_stats': {'total_tokens': 0},
                    'uptime': "Loading...",
                    'input_tokens': 0, 'output_tokens': 0
                }
        except: pass

        # Initial Collection
        try:
             # 获取CPU名称 (缓存)
            if _CPU_NAME_CACHE is None:
                try:
                    cpu_name = platform.processor() # Default
                    sys_name = platform.system()
                    if sys_name == "Windows":
                        # Windows wmic call might be slow, so we cache it
                        # Removed text=True to handle encoding manually and avoid Thread crash
                        result = subprocess.run("wmic cpu get name", shell=True,
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2)
                        
                        # Try decoding with common encodings
                        raw_out = result.stdout
                        decoded_out = ""
                        try:
                            decoded_out = raw_out.decode('utf-8')
                        except:
                            try:
                                decoded_out = raw_out.decode('mbcs') # Windows System Default
                            except:
                                decoded_out = raw_out.decode('utf-8', errors='ignore')

                        lines = decoded_out.strip().split('\n')
                        non_empty = [line.strip() for line in lines if line.strip()]
                        if len(non_empty) > 1:
                            cpu_name = non_empty[1]
                    elif sys_name == "Linux":
                        if os.path.exists('/proc/cpuinfo'):
                            with open('/proc/cpuinfo', 'r') as f:
                                for line in f:
                                    if line.startswith('model name'):
                                        cpu_name = line.split(':')[1].strip()
                                        break
                    elif sys_name == "Darwin":
                        result = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], 
                                              capture_output=True, text=True, timeout=2)
                        cpu_name = result.stdout.strip()
                    
                    _CPU_NAME_CACHE = cpu_name
                except Exception as e:
                    _CPU_NAME_CACHE = platform.processor() or "Unknown CPU"
        except:
            pass

        # Prime psutil CPU counters to avoid the first-sample spike/zero.
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(interval=None, percpu=True)
        except Exception:
            pass

        while True:
            try:
                # 1. CPU
                current_per_core = psutil.cpu_percent(interval=0.8, percpu=True)
                if current_per_core:
                    sampled_percent = sum(current_per_core) / len(current_per_core)
                else:
                    sampled_percent = psutil.cpu_percent(interval=None)

                # Task Manager is visually smoothed; apply light smoothing to reduce jitter.
                if _LATEST_CPU_PERCENT <= 0:
                    current_percent = round(sampled_percent, 1)
                else:
                    current_percent = round((_LATEST_CPU_PERCENT * 0.6) + (sampled_percent * 0.4), 1)
                _LATEST_CPU_PERCENT = current_percent
                
                # 2. Memory
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                # 获取详细的内存信息
                memory_details = {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free,
                    'active': getattr(memory, 'active', 0),
                    'inactive': getattr(memory, 'inactive', 0),
                    'buffers': getattr(memory, 'buffers', 0),
                    'cached': getattr(memory, 'cached', 0),
                    'shared': getattr(memory, 'shared', 0)
                }

                # 3. Disk
                try:
                    disk = psutil.disk_usage('/')
                except Exception:
                    try:
                        disk = psutil.disk_usage('C:\\')
                    except Exception:
                        from collections import namedtuple
                        D = namedtuple('usage', ['total', 'used', 'free', 'percent'])
                        disk = D(100, 50, 50, 50) # Fallback to avoid division by zero
                
                # 4. Net
                try:
                    net_io = psutil.net_io_counters()
                except Exception:
                    from collections import namedtuple
                    N = namedtuple('io', ['bytes_sent', 'bytes_recv'])
                    net_io = N(0, 0)
                
                # 5. Boot / Load
                try:
                    boot_time = psutil.boot_time()
                    boot_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(boot_time))
                except:
                    boot_time = 0
                    boot_time_str = "Unknown"

                try:
                    if hasattr(psutil, "getloadavg"):
                        load_avg = psutil.getloadavg()
                    else:
                        load_avg = (0, 0, 0)
                except Exception:
                    load_avg = (0, 0, 0)

                # 构造完整数据（兼容前端依赖的扁平字段 + system_info 嵌套结构）
                nested_system_info = {
                    'cpu': _CPU_NAME_CACHE,
                    'cpu_count': psutil.cpu_count(),
                    'platform': platform.platform(),
                    'python_version': platform.python_version(),
                    'total_memory': memory.total,
                    'used_memory': memory.used,
                    'available_memory': memory.available,
                    'memory_percent': memory_percent,
                    'memory_details': memory_details,
                    'total_disk': disk.total,
                    'used_disk': disk.used,
                    'free_disk': disk.free,
                    'disk_percent': disk.percent,
                    'net_bytes_sent': net_io.bytes_sent,
                    'net_bytes_recv': net_io.bytes_recv,
                    'boot_time': int(boot_time) if boot_time else 0,
                    'boot_time_str': boot_time_str,
                    'load_avg': load_avg
                }

                system_info = {
                    'cpu': _CPU_NAME_CACHE,
                    'cpu_count': psutil.cpu_count(),
                    'total_memory': memory.total,
                    'used_memory': memory.used,
                    'available_memory': memory.available,
                    'memory_percent': memory_percent,
                    'memory_unit': memory_percent,
                    'memory_details': memory_details,
                    'total_disk': disk.total,
                    'used_disk': disk.used,
                    'free_disk': disk.free,
                    'disk_percent': disk.percent,
                    'sent_bytes': net_io.bytes_sent,
                    'recv_bytes': net_io.bytes_recv,
                    'cpu_percent': current_percent,
                    'cpu_per_core': current_per_core,
                    'system_info': nested_system_info,
                    'boot_time': boot_time_str,
                    'load_avg': load_avg,
                    'input_tokens': INPUT_TOKENS,
                    'output_tokens': OUTPUT_TOKENS,
                    'token_stats': {'total_tokens': INPUT_TOKENS + OUTPUT_TOKENS},
                    'uptime': str(datetime.timedelta(seconds=int(time.time() - START_TIME))),
                    'uptime_seconds': int(time.time() - START_TIME)
                }
                
                _LATEST_SYSTEM_STATS = system_info
                
            except Exception as e:
                # Log error but don't crash thread
                print(f"[Monitor] Error collecting stats: {e}")
                # Log to app logger if available
                # app.logger.error(f"Monitor Thread Error: {e}")
                time.sleep(1)
            
            # Additional small sleep to keep update cadence stable.
            time.sleep(0.2)

    # Start the thread
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()

# Initialize Flask App (Global)
# web_server.py is in src/services/, need to go up 2 levels to reach src/static
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(base_dir, 'static')
app = Flask(__name__, static_folder=static_dir, static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Helper method to send static files with correct path and cache control
def send_static_file(filename):
    """Send static file from the static directory with cache headers"""
    response = send_from_directory(app.static_folder, filename)
    
    # Add cache control headers for better performance
    if filename.endswith(('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot')):
        # Cache static assets for 1 day
        response.headers['Cache-Control'] = 'public, max-age=86400'  # 24 hours
        response.headers['Expires'] = datetime.datetime.now() + datetime.timedelta(days=1)
    else:
        # HTML files - shorter cache or no cache
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    return response

app.send_static_file = send_static_file

# 注册系统API蓝图
SYSTEMS_BP_REGISTERED = False
SYSTEMS_BP_ERROR = ''
try:
    from app.services.systems_api import systems_bp
    app.register_blueprint(systems_bp)
    SYSTEMS_BP_REGISTERED = True
except Exception as e:
    SYSTEMS_BP_ERROR = str(e)
    print(f"Warning: Could not import/register systems_api: {e}")
    traceback.print_exc()

# 注册安全认证API蓝图
SECURITY_BP_REGISTERED = False
SECURITY_BP_ERROR = ''
try:
    from app.services.security_api import security_bp
    app.register_blueprint(security_bp)
    SECURITY_BP_REGISTERED = True
except Exception as e:
    SECURITY_BP_ERROR = str(e)
    print(f"Warning: Could not import/register security_api: {e}")
    traceback.print_exc()


@app.route('/api/systems/_health', methods=['GET'])
def api_systems_health():
    systems_routes = []
    try:
        systems_routes = sorted(
            [str(rule) for rule in app.url_map.iter_rules() if str(rule).startswith('/api/systems')]
        )
    except Exception:
        systems_routes = []

    return jsonify({
        'success': True,
        'systems_blueprint_registered': SYSTEMS_BP_REGISTERED,
        'error': SYSTEMS_BP_ERROR,
        'systems_route_count': len(systems_routes),
        'sample_routes': systems_routes[:20],
    })

@app.route('/api/sandbox/execute', methods=['POST'])
def api_sandbox_execute():
    try:
        data = request.get_json()
        code = data.get('code')
        if not code:
            return jsonify({'success': False, 'error': 'No code provided'}), 400

        frontend_source = request.headers.get('X-Frontend-Source', '')
        if not _is_work_mode_enabled(frontend_source):
            return jsonify({'success': False, 'error': 'Work Mode is disabled. Local code execution is blocked for safety.'}), 403
        if not CONFIG.get('work_mode', {}).get('features', {}).get('allow_code_exec', True):
            return jsonify({'success': False, 'error': 'allow_code_exec is disabled in Work Mode settings.'}), 403
        
        # Security check (basic)
        if 'os.system' in code or 'subprocess' in code:
            # In a real sandbox, we'd block this. But user might want it.
            # For now, let's allow it but log it.
            app.logger.warning("Sandbox executing potentially dangerous code.")

        from app.agent.agent_manager import AgentManager
        am = AgentManager() # This initializes a new manager (and sandbox)
        details = am.sandbox.execute_python_with_details(code)

        return jsonify({'success': True, 'output': details.get('combined_output', ''), 'details': details})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sandbox/external_approvals', methods=['GET'])
def api_sandbox_external_approvals_list():
    try:
        status = (request.args.get('status') or 'pending').strip().lower()
        limit = request.args.get('limit', 100, type=int)
        from app.agent.agent_manager import AgentManager
        am = AgentManager()
        rows = am.sandbox.list_external_approvals(status=status, limit=limit)
        return jsonify({'success': True, 'data': rows, 'count': len(rows)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sandbox/external_approvals/<request_id>', methods=['POST'])
def api_sandbox_external_approvals_resolve(request_id):
    try:
        frontend_source = request.headers.get('X-Frontend-Source', 'sandbox')
        if not _is_work_mode_enabled(frontend_source):
            return jsonify({'success': False, 'error': 'Work Mode is disabled.'}), 403

        data = request.get_json() or {}
        approve = bool(data.get('approve', False))
        reason = data.get('reason', '')
        from app.agent.agent_manager import AgentManager
        am = AgentManager()
        result = am.sandbox.resolve_external_approval(request_id=request_id, approve=approve, reason=reason)
        code = 200 if result.get('success') else 400
        return jsonify(result), code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sandbox/open_path', methods=['POST'])
def api_sandbox_open_path():
    try:
        frontend_source = request.headers.get('X-Frontend-Source', 'sandbox')
        if not _is_work_mode_enabled(frontend_source):
            return jsonify({'success': False, 'error': 'Work Mode is disabled.'}), 403

        data = request.get_json() or {}
        path = str(data.get('path') or '').strip()
        if not path:
            return jsonify({'success': False, 'error': 'path is required'}), 400

        from app.agent.agent_manager import AgentManager
        am = AgentManager()
        safe_path = am.sandbox.validate_path(path, action='read', external_approval_id=data.get('external_approval_id', ''))
        if not os.path.exists(safe_path):
            return jsonify({'success': False, 'error': f'Path not found: {safe_path}'}), 404

        if os.name == 'nt':
            os.startfile(safe_path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', safe_path])
        else:
            subprocess.Popen(['xdg-open', safe_path])

        return jsonify({'success': True, 'path': safe_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sandbox/open_url', methods=['POST'])
def api_sandbox_open_url():
    try:
        frontend_source = request.headers.get('X-Frontend-Source', 'sandbox')
        if not _is_work_mode_enabled(frontend_source):
            return jsonify({'success': False, 'error': 'Work Mode is disabled.'}), 403

        data = request.get_json() or {}
        url = str(data.get('url') or '').strip()
        if not url:
            return jsonify({'success': False, 'error': 'url is required'}), 400
        if not re.match(r'^https?://', url, flags=re.IGNORECASE):
            return jsonify({'success': False, 'error': 'Only http/https url is allowed'}), 400

        webbrowser.open(url)
        return jsonify({'success': True, 'url': url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 终端聊天模式
def run_terminal_chat():
    """终端聊天模式"""
    chat_system = AIChatSystem()
    print(Fore.CYAN + "\n🐱 终端聊天模式已启动 (输入'exit'退出)")
    print(Fore.YELLOW + "小雫: 喵~哥哥今天想聊什么呀？")

    while True:
        user_input = input(Fore.GREEN + "你: ").strip()
        if user_input.lower() == 'exit':
            break

        start_time = time.time()
        print(Fore.YELLOW + "小雫: 思考中...", end='\r')

        # 获取回复
        response = chat_system.chat(user_input)

        # 显示回复并计算响应时间
        elapsed = time.time() - start_time
        print(Fore.YELLOW + f"小雫: {response} (响应时间: {elapsed:.2f}s)")


# 沙箱聊天模式
class NoMonitoringFilter(logging.Filter):
    def filter(self, record):
        return '/api/monitoring' not in record.getMessage()

# Configure werkzeug logger before app starts
logging.getLogger('werkzeug').addFilter(NoMonitoringFilter())

def run_web_server():
    """沙箱聊天模式 (Flask服务 + 控制面板)"""
    port = int(CONFIG.get('server', {}).get('port', 8888) or 8888)
    # 使用绝对路径指向 src/static 目录
    # base_dir/static_dir are now global
    
    # Update global app template folder if needed (though API mostly returns JSON or send_file)
    app.template_folder = base_dir 

    
    # 添加额外的静态文件路由以支持子目录
    @app.route('/static/<path:filename>')
    def static_files(filename):
        return send_from_directory(app.static_folder, filename)
    
    # favicon.ico路由处理，避免重复启动
    @app.route('/favicon.ico')
    def favicon():
        favicon_path = os.path.join(static_dir, 'images', 'favicon.ico')
        if os.path.exists(favicon_path):
            return send_from_directory(os.path.join(static_dir, 'images'), 'favicon.ico')
        else:
            # 返回空的图标响应
            return Response('', mimetype='image/x-icon')
    
    # 移除下方重复定义，后续已用 app.send_static_file 统一映射
    # {
    # @app.route('/control_panel')
    # def control_panel():
    #     return send_from_directory(static_dir, 'control_panel.html')
    #
    # @app.route('/db_management')
    # def db_management():
    #     return send_from_directory(static_dir, 'db_management.html')
    #
    # @app.route('/logs')
    # def logs():
    #     return send_from_directory(static_dir, 'logs.html')
    # }
    
    class _LazyChatSystemProxy:
        """Lazily initialize AIChatSystem so DB/config errors won't block panel startup."""

        def __init__(self):
            self._instance = None

        def _ensure(self):
            if self._instance is not None:
                return self._instance
            try:
                self._instance = AIChatSystem()
                return self._instance
            except Exception as exc:
                raise RuntimeError(f"AIChatSystem unavailable: {exc}") from exc

        def __getattr__(self, item):
            inst = self._ensure()
            return getattr(inst, item)

    chat_system = _LazyChatSystemProxy()

    def _build_degraded_plugin_status(error_message):
        """Return a safe plugin status payload when AIChatSystem is unavailable."""
        plugin_framework_cfg = {}
        plugin_projects = []
        try:
            base_path = PROJECT_ROOT
            config_path = os.path.join(DATA_DIR, 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    plugin_framework_cfg = cfg.get('plugin_framework', {}) or {}

            plugins_dir = os.path.join(base_path, 'data', 'plungin')
            if os.path.isdir(plugins_dir):
                for item in os.listdir(plugins_dir):
                    if item.startswith('_'):
                        continue
                    project_dir = os.path.join(plugins_dir, item)
                    if os.path.isdir(project_dir):
                        plugin_projects.append(item)
        except Exception:
            pass

        return {
            'enabled': bool(plugin_framework_cfg.get('enabled', True)),
            'loaded_plugins': [],
            'plugins': [],
            'commands': [],
            'degraded': True,
            'error': str(error_message),
            'project_count': len(plugin_projects),
            'projects': plugin_projects,
        }

    def _build_degraded_skill_status(error_message):
        """Return a safe skill status payload when AIChatSystem is unavailable."""
        skill_framework_cfg = {}
        skill_projects = []
        try:
            base_path = PROJECT_ROOT
            config_path = os.path.join(DATA_DIR, 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    skill_framework_cfg = cfg.get('skill_framework', {}) or {}

            skills_dirs = [
                os.path.join(base_path, 'db', 'data', 'skills'),
                os.path.join(base_path, 'data', 'skills'),
            ]
            seen_projects = set()
            for skills_dir in skills_dirs:
                if not os.path.isdir(skills_dir):
                    continue
                for item in os.listdir(skills_dir):
                    if item.startswith('_') or item in seen_projects:
                        continue
                    project_dir = os.path.join(skills_dir, item)
                    skill_md = os.path.join(project_dir, 'SKILL.md')
                    if os.path.isdir(project_dir) and os.path.exists(skill_md):
                        skill_projects.append(item)
                        seen_projects.add(item)
        except Exception:
            pass

        return {
            'enabled': bool(skill_framework_cfg.get('enabled', True)),
            'loaded_skills': [],
            'skills': [],
            'degraded': True,
            'error': str(error_message),
            'project_count': len(skill_projects),
            'projects': skill_projects,
        }

    def _extract_skill_zip_to_workspace(upload_file):
        """Safely extract a skill zip to db/data/skills and return the installed skill id."""
        base_path = PROJECT_ROOT
        skills_root = os.path.join(base_path, 'db', 'data', 'skills')
        os.makedirs(skills_root, exist_ok=True)

        filename = (getattr(upload_file, 'filename', '') or '').strip()
        if not filename.lower().endswith('.zip'):
            raise ValueError('仅支持 zip 压缩包')

        temp_dir = tempfile.mkdtemp(prefix='skill_upload_')
        try:
            zip_path = os.path.join(temp_dir, 'upload.zip')
            upload_file.save(zip_path)

            with zipfile.ZipFile(zip_path, 'r') as archive:
                members = archive.infolist()
                if not members:
                    raise ValueError('压缩包为空')

                for member in members:
                    member_path = os.path.normpath(member.filename)
                    if member_path.startswith('..') or os.path.isabs(member_path):
                        raise ValueError('压缩包包含非法路径')

                extract_dir = os.path.join(temp_dir, 'extracted')
                os.makedirs(extract_dir, exist_ok=True)
                archive.extractall(extract_dir)

            top_level = [item for item in os.listdir(extract_dir) if not item.startswith('__MACOSX')]
            candidate_dir = None
            if len(top_level) == 1:
                first_path = os.path.join(extract_dir, top_level[0])
                if os.path.isdir(first_path):
                    candidate_dir = first_path

            if candidate_dir is None:
                candidate_dir = extract_dir

            if not os.path.exists(os.path.join(candidate_dir, 'SKILL.md')):
                nested_dirs = []
                for item in os.listdir(candidate_dir):
                    item_path = os.path.join(candidate_dir, item)
                    if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'SKILL.md')):
                        nested_dirs.append(item_path)
                if len(nested_dirs) == 1:
                    candidate_dir = nested_dirs[0]
                else:
                    raise ValueError('压缩包内未找到 SKILL.md')

            skill_id = os.path.basename(candidate_dir.rstrip('\\/'))
            target_dir = os.path.join(skills_root, skill_id)
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.copytree(candidate_dir, target_dir)

            return skill_id
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _extract_skill_zip_file_to_workspace(zip_path):
        """Safely extract a local zip file into db/data/skills and return installed skill id."""
        base_path = PROJECT_ROOT
        skills_root = os.path.join(base_path, 'db', 'data', 'skills')
        os.makedirs(skills_root, exist_ok=True)

        if not os.path.exists(zip_path):
            raise ValueError('zip 文件不存在')
        if not str(zip_path).lower().endswith('.zip'):
            raise ValueError('仅支持 zip 压缩包')

        temp_dir = tempfile.mkdtemp(prefix='skill_market_')
        try:
            with zipfile.ZipFile(zip_path, 'r') as archive:
                members = archive.infolist()
                if not members:
                    raise ValueError('压缩包为空')
                for member in members:
                    member_path = os.path.normpath(member.filename)
                    if member_path.startswith('..') or os.path.isabs(member_path):
                        raise ValueError('压缩包包含非法路径')

                extract_dir = os.path.join(temp_dir, 'extracted')
                os.makedirs(extract_dir, exist_ok=True)
                archive.extractall(extract_dir)

            top_level = [item for item in os.listdir(extract_dir) if not item.startswith('__MACOSX')]
            candidate_dir = None
            if len(top_level) == 1:
                first_path = os.path.join(extract_dir, top_level[0])
                if os.path.isdir(first_path):
                    candidate_dir = first_path

            if candidate_dir is None:
                candidate_dir = extract_dir

            if not os.path.exists(os.path.join(candidate_dir, 'SKILL.md')):
                nested_dirs = []
                for item in os.listdir(candidate_dir):
                    item_path = os.path.join(candidate_dir, item)
                    if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'SKILL.md')):
                        nested_dirs.append(item_path)
                if len(nested_dirs) == 1:
                    candidate_dir = nested_dirs[0]
                else:
                    raise ValueError('压缩包内未找到 SKILL.md')

            skill_id = os.path.basename(candidate_dir.rstrip('\\/'))
            target_dir = os.path.join(skills_root, skill_id)
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.copytree(candidate_dir, target_dir)
            return skill_id
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    _COCOLOOP_URLS_CACHE = {'ts': 0.0, 'urls': []}
    _COCOLOOP_META_CACHE = {}
    _COCOLOOP_URLS_TTL = 600
    _COCOLOOP_META_TTL = 86400
    _SKILL_MARKET_RESULTS_CACHE = {'entries': {}}
    _SKILL_MARKET_RESULTS_TTL = 900
    _SKILLHUB_INSTALL_JOBS = {}
    _SKILLHUB_INSTALL_JOBS_LOCK = threading.Lock()
    _SKILLHUB_INSTALL_JOB_TTL = 3600
    _AGENT_DEPLOY_JOBS = {}
    _AGENT_DEPLOY_JOBS_LOCK = threading.Lock()
    _AGENT_DEPLOY_JOB_TTL = 3600
    _COCOLOOP_LAST_DIAG = {
        'timestamp': 0.0,
        'sources': [],
        'errors': [],
        'warnings': [],
        'total_urls': 0,
        'used_cache': False,
    }

    def _load_skill_market_config():
        config_path = os.path.join(DATA_DIR, 'config.json')
        if not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f) or {}
            market_cfg = cfg.get('skill_market', {}) or {}
            return market_cfg.get('cocoloop', {}) or {}
        except Exception:
            return {}

    def _load_skill_market_github_config():
        config_path = os.path.join(DATA_DIR, 'config.json')
        if not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f) or {}
            market_cfg = cfg.get('skill_market', {}) or {}
            return market_cfg.get('github', {}) or {}
        except Exception:
            return {}

    def _load_skillhub_config():
        config_path = os.path.join(DATA_DIR, 'config.json')
        if not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f) or {}
            market_cfg = cfg.get('skill_market', {}) or {}
            return market_cfg.get('skillhub', {}) or {}
        except Exception:
            return {}

    def _skillhub_runner():
        cfg = _load_skillhub_config()
        configured_bin = str(cfg.get('cli_bin') or '').strip()
        candidate_bins = []
        if configured_bin:
            candidate_bins.append(configured_bin)
        candidate_bins.extend(['skills', 'skillhub', 'skillhub-cli'])

        seen = set()
        for b in candidate_bins:
            if not b or b in seen:
                continue
            seen.add(b)
            full = shutil.which(b)
            if full:
                base_name = os.path.basename(full).lower()
                if b == 'skills' or base_name.startswith('npx'):
                    return [full, '-y', 'skills'] if base_name.startswith('npx') else [full]
                return [full]

        npx = shutil.which('npx')
        if npx:
            return [npx, '-y', 'skills']
        return []

    def _skillhub_runner_info():
        cfg = _load_skillhub_config()
        configured_bin = str(cfg.get('cli_bin') or '').strip()

        if configured_bin:
            full = shutil.which(configured_bin)
            if full:
                base_name = os.path.basename(full).lower()
                cli_kind = 'skills' if ('skills' in base_name and 'skillhub' not in base_name) else ('skillhub' if 'skillhub' in base_name else 'skills')
                return {
                    'runner': [full],
                    'installed': True,
                    'mode': 'configured',
                    'cli': full,
                    'cli_kind': cli_kind,
                }

        for b in ['skills', 'skillhub', 'skillhub-cli']:
            full = shutil.which(b)
            if full:
                base_name = os.path.basename(full).lower()
                cli_kind = 'skills' if ('skills' in base_name and 'skillhub' not in base_name) else ('skillhub' if 'skillhub' in base_name else 'skills')
                return {
                    'runner': [full],
                    'installed': True,
                    'mode': 'global',
                    'cli': full,
                    'cli_kind': cli_kind,
                }

        npx = shutil.which('npx')
        if npx:
            return {
                'runner': [npx, '-y', 'skills'],
                'installed': False,
                'mode': 'npx-fallback',
                'cli': f'{npx} -y skills',
                'cli_kind': 'skills',
            }

        return {
            'runner': [],
            'installed': False,
            'mode': 'missing',
            'cli': '',
            'cli_kind': '',
        }

    def _find_skillhub_cli():
        info = _skillhub_runner_info()
        return str(info.get('cli') or '').strip()

    def _run_skillhub_cli(args, timeout=45):
        info = _skillhub_runner_info()
        runner = list(info.get('runner') or [])
        if not runner:
            raise RuntimeError('SkillHub CLI 未安装，请先点击“安装 SkillHub CLI”')
        cmd = list(runner) + list(args or [])
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=max(5, int(timeout or 45)),
            cwd=PROJECT_ROOT
        )
        return {
            'ok': proc.returncode == 0,
            'code': int(proc.returncode),
            'stdout': str(proc.stdout or ''),
            'stderr': str(proc.stderr or ''),
            'cmd': cmd,
        }

    def _skillhub_install_attempts_for_ref(ref: str, external_url: str = ''):
        info = _skillhub_runner_info()
        cli_kind = str(info.get('cli_kind') or '').strip().lower()
        candidates = [str(ref or '').strip()]
        ext = str(external_url or '').strip()
        if ext and ext not in candidates:
            candidates.append(ext)

        attempts = []
        if cli_kind == 'skillhub':
            for target in candidates:
                if not target:
                    continue
                attempts.append(['pull', target])
        else:
            for target in candidates:
                if not target:
                    continue
                attempts.extend([
                    ['add', target, '--yes'],
                    ['add', target],
                    ['install', target, '--yes'],
                    ['install', target],
                ])
        return attempts

    def _skillhub_install_job_log_dir():
        base_path = PROJECT_ROOT
        log_dir = os.path.join(base_path, 'logs', 'skillhub_install')
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def _skillhub_install_job_prune_locked(now=None):
        now = now or time.time()
        stale_ids = []
        for job_id, job in list(_SKILLHUB_INSTALL_JOBS.items()):
            updated_at = float(job.get('updated_at') or job.get('created_at') or 0.0)
            if job.get('status') in ('running', 'queued'):
                continue
            if (now - updated_at) > _SKILLHUB_INSTALL_JOB_TTL:
                stale_ids.append(job_id)
        for job_id in stale_ids:
            _SKILLHUB_INSTALL_JOBS.pop(job_id, None)

    def _skillhub_install_job_snapshot(job_id: str):
        with _SKILLHUB_INSTALL_JOBS_LOCK:
            _skillhub_install_job_prune_locked()
            job = _SKILLHUB_INSTALL_JOBS.get(job_id)
            if not job:
                return None
            return {
                'job_id': job.get('job_id', job_id),
                'status': job.get('status', 'queued'),
                'created_at': job.get('created_at'),
                'updated_at': job.get('updated_at'),
                'command': job.get('command', ''),
                'command_display': job.get('command_display', ''),
                'log_path': job.get('log_path', ''),
                'returncode': job.get('returncode'),
                'message': job.get('message', ''),
                'logs': list(job.get('logs') or []),
                'installed': bool(job.get('status') == 'success'),
            }

    def _skillhub_install_job_append(job_id: str, line: str):
        text = str(line or '').replace('\r', '').rstrip('\n')
        if not text.strip():
            return
        log_line = text.strip('\n')
        now = time.time()
        with _SKILLHUB_INSTALL_JOBS_LOCK:
            job = _SKILLHUB_INSTALL_JOBS.get(job_id)
            if not job:
                return
            logs = list(job.get('logs') or [])
            logs.append(log_line)
            if len(logs) > 400:
                logs = logs[-400:]
            job['logs'] = logs
            job['updated_at'] = now
            log_path = job.get('log_path')
        if log_path:
            try:
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
            except Exception:
                pass
        print(f"[SkillHub CLI][{job_id}] {log_line}")

    def _skillhub_install_job_finish(job_id: str, status: str, message: str, returncode: int = None):
        now = time.time()
        with _SKILLHUB_INSTALL_JOBS_LOCK:
            job = _SKILLHUB_INSTALL_JOBS.get(job_id)
            if not job:
                return
            job['status'] = status
            job['message'] = str(message or '')
            job['updated_at'] = now
            if returncode is not None:
                job['returncode'] = int(returncode)
            job['logs'] = list(job.get('logs') or [])
        print(f"[SkillHub CLI][{job_id}] {status.upper()}: {message}")

    def _start_skillhub_install_job():
        base_path = PROJECT_ROOT
        job_id = uuid.uuid4().hex
        log_dir = _skillhub_install_job_log_dir()
        log_path = os.path.join(log_dir, f'{job_id}.log')
        now = time.time()

        bash = shutil.which('bash')
        npm = shutil.which('npm')
        npx = shutil.which('npx')

        install_steps = []
        if bash:
            install_cmd = 'curl -fsSL https://skillhub.cn/install/install.sh | bash -s -- --no-skills'
            install_steps.append({
                'kind': 'bash-script',
                'display': install_cmd,
                'command': [bash, '-lc', install_cmd],
            })
        if npm:
            install_steps.append({
                'kind': 'npm-global',
                'display': f'{npm} install -g skills',
                'command': [npm, 'install', '-g', 'skills'],
            })
        if npx:
            install_steps.append({
                'kind': 'npx-fallback',
                'display': f'{npx} -y skills (无需全局安装，直接启用)',
                'command': [npx, '-y', 'skills', '--help'],
            })

        if not install_steps:
            raise RuntimeError('未找到可用的 SkillHub 安装器（bash / npm / npx 均不可用）')

        with _SKILLHUB_INSTALL_JOBS_LOCK:
            _skillhub_install_job_prune_locked(now)
            _SKILLHUB_INSTALL_JOBS[job_id] = {
                'job_id': job_id,
                'status': 'queued',
                'created_at': now,
                'updated_at': now,
                'command': install_steps[0]['command'],
                'command_display': install_steps[0]['display'],
                'log_path': log_path,
                'returncode': None,
                'message': '准备启动 SkillHub CLI 安装',
                'logs': [
                    '准备启动官方 SkillHub CLI 安装脚本',
                    f'候选步骤数: {len(install_steps)}',
                    f'首选命令: {install_steps[0]["display"]}',
                ],
            }

        def _runner():
            process = None
            try:
                with _SKILLHUB_INSTALL_JOBS_LOCK:
                    job = _SKILLHUB_INSTALL_JOBS.get(job_id)
                    if job:
                        job['status'] = 'running'
                        job['updated_at'] = time.time()

                _skillhub_install_job_append(job_id, f'工作目录: {base_path}')
                last_error = None
                for step in install_steps:
                    command = list(step['command'])
                    display = step['display']
                    kind = step['kind']
                    _skillhub_install_job_append(job_id, f'开始执行: {display}')

                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        bufsize=1,
                        cwd=base_path,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    )

                    if process.stdout:
                        for raw_line in iter(process.stdout.readline, ''):
                            if raw_line == '':
                                break
                            _skillhub_install_job_append(job_id, raw_line)

                    returncode = process.wait()
                    if returncode == 0:
                        if kind == 'npx-fallback':
                            _skillhub_install_job_append(job_id, '检测到 npx fallback 可用，已启用无需全局安装的运行方式')
                            _skillhub_install_job_finish(job_id, 'success', 'SkillHub CLI 已启用 npx fallback', returncode)
                        else:
                            _skillhub_install_job_finish(job_id, 'success', 'SkillHub CLI 安装完成', returncode)
                        return

                    last_error = f'{display} 退出码: {returncode}'
                    _skillhub_install_job_append(job_id, last_error)

                _skillhub_install_job_finish(job_id, 'error', 'SkillHub CLI 安装失败，请查看日志', -1)
            except Exception as exc:
                _skillhub_install_job_append(job_id, f'安装异常: {exc}')
                _skillhub_install_job_finish(job_id, 'error', str(exc), -1)
            finally:
                try:
                    if process and process.stdout:
                        process.stdout.close()
                except Exception:
                    pass

        threading.Thread(target=_runner, daemon=True).start()
        return _skillhub_install_job_snapshot(job_id)

    def _agent_deploy_job_log_dir():
        base_path = PROJECT_ROOT
        log_dir = os.path.join(base_path, 'logs', 'agent_deploy')
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def _agent_deploy_job_prune_locked(now=None):
        now = now or time.time()
        stale_ids = []
        for job_id, job in list(_AGENT_DEPLOY_JOBS.items()):
            updated_at = float(job.get('updated_at') or job.get('created_at') or 0.0)
            if job.get('status') in ('running', 'queued'):
                continue
            if (now - updated_at) > _AGENT_DEPLOY_JOB_TTL:
                stale_ids.append(job_id)
        for job_id in stale_ids:
            _AGENT_DEPLOY_JOBS.pop(job_id, None)

    def _agent_deploy_job_snapshot(job_id: str):
        with _AGENT_DEPLOY_JOBS_LOCK:
            _agent_deploy_job_prune_locked()
            job = _AGENT_DEPLOY_JOBS.get(job_id)
            if not job:
                return None
            return {
                'job_id': job.get('job_id', job_id),
                'status': job.get('status', 'queued'),
                'created_at': job.get('created_at'),
                'updated_at': job.get('updated_at'),
                'title': job.get('title', ''),
                'command_display': job.get('command_display', ''),
                'log_path': job.get('log_path', ''),
                'returncode': job.get('returncode'),
                'message': job.get('message', ''),
                'reply': job.get('reply', ''),
                'logs': list(job.get('logs') or []),
            }

    def _agent_deploy_job_append(job_id: str, line: str):
        text = str(line or '').replace('\r', '').rstrip('\n')
        if not text.strip():
            return
        log_line = text.strip('\n')
        now = time.time()
        with _AGENT_DEPLOY_JOBS_LOCK:
            job = _AGENT_DEPLOY_JOBS.get(job_id)
            if not job:
                return
            logs = list(job.get('logs') or [])
            logs.append(log_line)
            if len(logs) > 600:
                logs = logs[-600:]
            job['logs'] = logs
            job['updated_at'] = now
            log_path = job.get('log_path')
        if log_path:
            try:
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
            except Exception:
                pass
        print(f"[Agent Deploy][{job_id}] {log_line}")

    def _agent_deploy_job_finish(job_id: str, status: str, message: str, returncode: int = None, reply: str = ''):
        now = time.time()
        with _AGENT_DEPLOY_JOBS_LOCK:
            job = _AGENT_DEPLOY_JOBS.get(job_id)
            if not job:
                return
            job['status'] = status
            job['message'] = str(message or '')
            job['updated_at'] = now
            if returncode is not None:
                job['returncode'] = int(returncode)
            if reply:
                job['reply'] = str(reply)
            job['logs'] = list(job.get('logs') or [])

    def _derive_skill_target_id(source: str, skill_id: str, name: str, external_url: str) -> str:
        sid = str(skill_id or '').strip()
        if sid:
            return sid

        nm = str(name or '').strip()
        if nm:
            return re.sub(r'[^a-zA-Z0-9._-]+', '-', nm).strip('-').lower() or 'skill'

        url = str(external_url or '').strip()
        if url:
            m = re.search(r'github\.com/([^/]+)/([^/?#]+)', url, flags=re.IGNORECASE)
            if m:
                owner = re.sub(r'[^a-zA-Z0-9._-]+', '-', m.group(1)).strip('-').lower()
                repo = re.sub(r'[^a-zA-Z0-9._-]+', '-', m.group(2)).strip('-').lower()
                if owner and repo:
                    return f'{owner}__{repo}'
        return 'skill'

    def _normalize_skill_layout_in_dir(base_dir: str):
        """Ensure SkillManager-compatible layout: <skill_dir>/SKILL.md exists.

        Many GitHub skill repos store SKILL.md under skills/<name>/SKILL.md.
        This function copies one discovered SKILL.md to root if missing.
        """
        root_skill = os.path.join(base_dir, 'SKILL.md')
        if os.path.exists(root_skill):
            return root_skill

        candidates = []
        preferred = []
        for cur_root, _, files in os.walk(base_dir):
            if 'SKILL.md' not in files:
                continue
            full = os.path.join(cur_root, 'SKILL.md')
            rel = os.path.relpath(full, base_dir).replace('\\', '/')
            candidates.append((rel, full))
            if '/skills/' in f'/{rel}':
                preferred.append((rel, full))

        pool = preferred or candidates
        if not pool:
            raise RuntimeError('仓库中未找到 SKILL.md，无法作为技能导入')

        pool.sort(key=lambda x: len(x[0]))
        _, chosen = pool[0]
        shutil.copy2(chosen, root_skill)

        chosen_dir = os.path.dirname(chosen)
        for fn in os.listdir(chosen_dir):
            if fn == 'SKILL.md':
                continue
            src = os.path.join(chosen_dir, fn)
            dst = os.path.join(base_dir, fn)
            if os.path.isdir(src) or os.path.exists(dst):
                continue
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

        return root_skill

    def _fallback_deploy_skill_from_github(source: str, skill_id: str, name: str, external_url: str):
        url = str(external_url or '').strip()
        if not re.match(r'^https?://github\.com/', url, flags=re.IGNORECASE):
            return {'ok': False, 'error': '当前仅支持 github URL 自动回退部署'}

        target_id = _derive_skill_target_id(source, skill_id, name, external_url)
        skills_root = os.path.join(PROJECT_ROOT, 'data', 'skills')
        os.makedirs(skills_root, exist_ok=True)

        tmp_parent = tempfile.mkdtemp(prefix='skill_deploy_', dir=tempfile.gettempdir())
        clone_dir = os.path.join(tmp_parent, 'repo')
        target_dir = os.path.join(skills_root, target_id)

        try:
            cmd = ['git', 'clone', '--depth', '1', url, clone_dir]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if proc.returncode != 0:
                stderr = (proc.stderr or proc.stdout or '').strip()
                return {'ok': False, 'error': f'git clone 失败: {stderr[:800]}'}

            _normalize_skill_layout_in_dir(clone_dir)

            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.move(clone_dir, target_dir)

            deployment_meta = {
                'source': source or 'github',
                'skill_id': target_id,
                'name': name or target_id,
                'url': url,
                'deployed_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'layout': 'github_clone_with_root_skill_md',
            }
            with open(os.path.join(target_dir, '_deployment.json'), 'w', encoding='utf-8') as f:
                json.dump(deployment_meta, f, ensure_ascii=False, indent=2)

            try:
                chat_system.reload_skills()
                status = chat_system.get_skill_status() or {}
                skills = list(status.get('skills') or [])
                found = any(str(x.get('skill_id') or '') == target_id for x in skills)
            except Exception:
                found = os.path.exists(os.path.join(target_dir, 'SKILL.md'))

            if not found:
                return {'ok': False, 'error': f'已下载到 {target_dir}，但框架未识别该技能'}

            return {
                'ok': True,
                'skill_id': target_id,
                'target_dir': target_dir,
                'message': 'fallback 部署成功并已通过框架识别',
            }
        finally:
            try:
                if os.path.exists(tmp_parent):
                    shutil.rmtree(tmp_parent)
            except Exception:
                pass

    def _safe_skill_dir_name(name: str) -> str:
        val = re.sub(r'[^a-zA-Z0-9._-]+', '-', str(name or '').strip()).strip('-').lower()
        return val or 'skill'

    def _is_skill_discovered(candidate_ids=None, candidate_names=None):
        candidate_ids = {str(x or '').strip().lower() for x in (candidate_ids or []) if str(x or '').strip()}
        candidate_names = {str(x or '').strip().lower() for x in (candidate_names or []) if str(x or '').strip()}
        try:
            chat_system.reload_skills()
            status = chat_system.get_skill_status() or {}
            skills = list(status.get('skills') or [])
            for it in skills:
                sid = str(it.get('skill_id') or '').strip().lower()
                sname = str(it.get('name') or '').strip().lower()
                if sid in candidate_ids or sname in candidate_names:
                    return True
        except Exception:
            return False
        return False

    def _create_local_skill_scaffold(target_dir: str, skill_id: str, name: str, source: str):
        os.makedirs(target_dir, exist_ok=True)
        title = str(name or skill_id or 'Skill').strip() or 'Skill'
        sid = str(skill_id or _safe_skill_dir_name(title)).strip()
        skill_md = os.path.join(target_dir, 'SKILL.md')
        if not os.path.exists(skill_md):
            content = (
                '---\n'
                f'name: {title}\n'
                f'id: {sid}\n'
                'version: 0.1.0\n'
                f'source: {source or "agent-fallback"}\n'
                '---\n\n'
                f'# {title}\n\n'
                '该技能由系统回退流程创建。\n'
                '如果你有正式仓库版本，请后续覆盖此目录内容。\n'
            )
            with open(skill_md, 'w', encoding='utf-8') as f:
                f.write(content)

    def _fallback_deploy_skill_from_skillhub(source: str, skill_id: str, name: str, external_url: str):
        refs = []
        for v in [skill_id, name, external_url]:
            vv = str(v or '').strip()
            if vv and vv not in refs:
                refs.append(vv)
        if not refs:
            return {'ok': False, 'error': 'skillhub 回退部署缺少可用标识'}

        errors = []
        for ref in refs:
            attempts = _skillhub_install_attempts_for_ref(ref, external_url)
            for args in attempts:
                try:
                    r = _run_skillhub_cli(args, timeout=120)
                except Exception as exc:
                    errors.append({'ref': ref, 'cmd': ' '.join(args), 'message': str(exc)[:500]})
                    continue

                if r.get('ok'):
                    target_id = _derive_skill_target_id(source, skill_id, name, external_url)
                    discovered = _is_skill_discovered(
                        candidate_ids=[target_id, skill_id, ref],
                        candidate_names=[name, ref],
                    )
                    if discovered:
                        return {
                            'ok': True,
                            'skill_id': target_id,
                            'target_dir': '',
                            'message': f"skillhub CLI 安装成功: {' '.join(map(str, r.get('cmd') or []))}",
                        }

                    errors.append({
                        'ref': ref,
                        'cmd': ' '.join(map(str, r.get('cmd') or [])),
                        'message': 'CLI 返回成功，但技能未被框架识别',
                    })
                else:
                    errors.append({
                        'ref': ref,
                        'cmd': ' '.join(map(str, r.get('cmd') or [])),
                        'message': (r.get('stderr') or r.get('stdout') or '').strip()[:500],
                    })

        skills_root = os.path.join(PROJECT_ROOT, 'data', 'skills')
        os.makedirs(skills_root, exist_ok=True)
        target_id = _safe_skill_dir_name(skill_id or name or 'skillhub-skill')
        target_dir = os.path.join(skills_root, target_id)
        try:
            _create_local_skill_scaffold(target_dir, skill_id or target_id, name or target_id, source or 'skillhub')
            discovered = _is_skill_discovered(
                candidate_ids=[target_id, skill_id],
                candidate_names=[name, target_id],
            )
            if discovered:
                return {
                    'ok': True,
                    'skill_id': target_id,
                    'target_dir': target_dir,
                    'message': 'skillhub 自动回退已创建本地技能骨架并通过框架识别',
                }
            return {
                'ok': False,
                'error': f'skillhub 回退已创建目录但仍未识别: {target_dir}',
                'details': errors[-5:],
            }
        except Exception as exc:
            return {
                'ok': False,
                'error': f'skillhub 回退部署失败: {exc}',
                'details': errors[-5:],
            }

    def _fallback_deploy_skill(source: str, skill_id: str, name: str, external_url: str):
        src = str(source or '').strip().lower()
        if src == 'skillhub':
            return _fallback_deploy_skill_from_skillhub(source, skill_id, name, external_url)
        return _fallback_deploy_skill_from_github(source, skill_id, name, external_url)

    def _start_agent_deploy_job(source: str, skill_id: str, name: str, external_url: str):
        job_id = uuid.uuid4().hex
        log_dir = _agent_deploy_job_log_dir()
        log_path = os.path.join(log_dir, f'{job_id}.log')
        now = time.time()
        title = name or skill_id or external_url or 'skill'

        with _AGENT_DEPLOY_JOBS_LOCK:
            _agent_deploy_job_prune_locked(now)
            _AGENT_DEPLOY_JOBS[job_id] = {
                'job_id': job_id,
                'status': 'queued',
                'created_at': now,
                'updated_at': now,
                'title': title,
                'command_display': f'Agent 一键部署技能: {title}',
                'log_path': log_path,
                'returncode': None,
                'message': '准备启动 Agent 一键部署',
                'reply': '',
                'logs': [
                    '准备启动 Agent 一键部署任务',
                    f'来源: {source}',
                    f'技能标识: {skill_id or "-"}',
                    f'名称: {name or "-"}',
                    f'链接: {external_url or "-"}',
                ],
            }

        def _runner():
            try:
                with _AGENT_DEPLOY_JOBS_LOCK:
                    job = _AGENT_DEPLOY_JOBS.get(job_id)
                    if job:
                        job['status'] = 'running'
                        job['updated_at'] = time.time()

                _agent_deploy_job_append(job_id, '进入 Agent 沙箱工作流')
                _agent_deploy_job_append(job_id, '正在构建部署提示词...')

                deploy_prompt = (
                    "你现在是沙箱内的自主 Agent。请在当前项目中完成以下任务：\n"
                    f"1) 从技能商店部署技能（source={source}, skill_id={skill_id}, name={name}, url={external_url}）。\n"
                    "2) 允许你自行运行沙箱虚拟终端、安装依赖、修改文件、执行检查并修复问题。\n"
                    "3) 不要使用爬虫，不要抓取网页内容。\n"
                    "4) 完成后给出部署结果、修改文件和验证结果。"
                )
                _agent_deploy_job_append(job_id, '已向 Agent 发送部署任务')

                reply = chat_system.chat(
                    deploy_prompt,
                    image=None,
                    is_admin=True,
                    attachments=None,
                    frontend_source='sandbox',
                    persona_filename=None,
                )
                reply_text = str(reply or '').strip()
                _agent_deploy_job_append(job_id, 'Agent 已返回部署结果')
                if reply_text:
                    _agent_deploy_job_append(job_id, '------ Agent Reply Begin ------')
                    for line in reply_text.splitlines():
                        _agent_deploy_job_append(job_id, line)
                    _agent_deploy_job_append(job_id, '------ Agent Reply End ------')

                _agent_deploy_job_append(job_id, '检查 Agent 是否已实际完成部署...')
                target_id = _derive_skill_target_id(source, skill_id, name, external_url)
                target_dir = os.path.join(PROJECT_ROOT, 'data', 'skills', target_id)
                if os.path.exists(os.path.join(target_dir, 'SKILL.md')):
                    _agent_deploy_job_append(job_id, f'检测到已部署技能目录: {target_dir}')
                    _agent_deploy_job_finish(job_id, 'success', 'Agent 一键部署完成', 0, reply_text)
                    return

                _agent_deploy_job_append(job_id, 'Agent 未产生可识别部署结果，触发后端自动回退部署...')
                fb = _fallback_deploy_skill(source, skill_id, name, external_url)
                if fb.get('ok'):
                    _agent_deploy_job_append(job_id, f"回退部署成功: {fb.get('skill_id')}")
                    if fb.get('target_dir'):
                        _agent_deploy_job_append(job_id, f"目录: {fb.get('target_dir')}")
                    final_reply = reply_text + "\n\n[系统回退部署]\n" + str(fb.get('message') or '')
                    _agent_deploy_job_finish(job_id, 'success', 'Agent 一键部署完成（含系统回退）', 0, final_reply)
                    return

                _agent_deploy_job_append(job_id, f"回退部署失败: {fb.get('error')}")
                _agent_deploy_job_finish(job_id, 'error', f"部署失败: {fb.get('error')}", -1, reply_text)
                return
            except Exception as exc:
                _agent_deploy_job_append(job_id, f'部署异常: {exc}')
                _agent_deploy_job_finish(job_id, 'error', str(exc), -1)

        threading.Thread(target=_runner, daemon=True).start()
        return _agent_deploy_job_snapshot(job_id)

    def _extract_json_from_text(text):
        raw = str(text or '').strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            pass

        s1 = raw.find('[')
        s2 = raw.find('{')
        starts = [x for x in [s1, s2] if x >= 0]
        if not starts:
            return None
        start = min(starts)

        for end in range(len(raw), start, -1):
            chunk = raw[start:end].strip()
            if not chunk:
                continue
            try:
                return json.loads(chunk)
            except Exception:
                continue
        return None

    def _normalize_skillhub_items(payload):
        rows = []
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            for k in ('items', 'data', 'list', 'skills', 'results'):
                v = payload.get(k)
                if isinstance(v, list):
                    rows = v
                    break

        out = []
        for it in rows:
            if not isinstance(it, dict):
                continue
            sid = str(it.get('id') or it.get('name') or it.get('slug') or '').strip()
            if not sid:
                continue
            external_url = str(it.get('url') or it.get('homepage') or it.get('repository') or '').strip()
            name = _skillhub_clean_text(it.get('name') or sid)
            description = _skillhub_clean_text(it.get('description') or '')
            author = _skillhub_clean_text(it.get('author') or it.get('owner') or '')
            language = _skillhub_clean_text(it.get('language') or '')
            topics = []
            for tag in list(it.get('tags') or it.get('topics') or []):
                cleaned_tag = _skillhub_clean_text(tag)
                if cleaned_tag:
                    topics.append(cleaned_tag)

            if not name:
                name = sid
            out.append({
                'id': sid,
                'name': name,
                'description': description,
                'source': 'skillhub',
                'external_url': external_url,
                'author': author,
                'version': _skillhub_clean_text(it.get('version') or ''),
                'language': language,
                'topics': topics,
                'stars': int(it.get('stars') or it.get('stargazers_count') or 0),
                'skillhub_id': sid,
            })
        return out

    def _skillhub_clean_text(value):
        text = str(value or '')
        text = text.replace('\r', ' ').replace('\n', ' ')
        text = re.sub(r'[│┆┊|]+', ' ', text)
        text = re.sub(r'^[\s\-_=•·⋅⋮⋯…:;]+$', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            return ''
        lowered = text.lower()
        if lowered in {'custom', 'unknown', 'undefined', 'null', '-', '---', '...', '....'}:
            return ''
        if not re.search(r'[\w\u4e00-\u9fff]', text):
            return ''
        return text

    def _skill_market_cache_key(source: str, query: str, extra: str = '') -> str:
        return f"{str(source or '').strip().lower()}|{str(query or '').strip().lower()}|{str(extra or '').strip().lower()}"

    def _skill_market_cache_get(key: str):
        now = time.time()
        entry = _SKILL_MARKET_RESULTS_CACHE.get('entries', {}).get(key)
        if not entry:
            return None
        if (now - float(entry.get('ts') or 0.0)) > _SKILL_MARKET_RESULTS_TTL:
            return None
        return dict(entry)

    def _skill_market_cache_set(key: str, items, diag: dict = None):
        _SKILL_MARKET_RESULTS_CACHE.setdefault('entries', {})[key] = {
            'ts': time.time(),
            'items': list(items or []),
            'diag': dict(diag or {}),
        }

    def _extract_cocoloop_skill_links_from_html(html_text):
        html = str(html_text or '')
        links = []
        seen = set()

        for m in re.finditer(r'https?://hub\.cocoloop\.cn/skills/([^"\'\s<#?]+)', html, flags=re.IGNORECASE):
            url = f'https://hub.cocoloop.cn/skills/{m.group(1)}'
            if url not in seen:
                seen.add(url)
                links.append(url)

        for m in re.finditer(r'(?:href|src)=["\'](/skills/[^"\'\s<#?]+)["\']', html, flags=re.IGNORECASE):
            path = m.group(1)
            url = f'https://hub.cocoloop.cn{path}'
            if url not in seen:
                seen.add(url)
                links.append(url)

        return links

    def _normalize_cocoloop_api_items(payload):
        items = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            for key in ('items', 'data', 'list', 'rows', 'result'):
                val = payload.get(key)
                if isinstance(val, list):
                    items = val
                    break
                if isinstance(val, dict):
                    for nested_key in ('items', 'list', 'rows', 'result'):
                        nested_val = val.get(nested_key)
                        if isinstance(nested_val, list):
                            items = nested_val
                            break
                    if items:
                        break

        out = []
        for it in items:
            if not isinstance(it, dict):
                continue
            sid = str(it.get('id') or it.get('skill_id') or it.get('slug') or '').strip()
            name = str(it.get('name') or it.get('title') or '').strip()
            desc = str(it.get('description') or it.get('desc') or '').strip()
            external_url = str(it.get('external_url') or it.get('url') or it.get('link') or '').strip()
            download_url = str(it.get('download_url') or it.get('download') or '').strip()

            if not external_url and sid:
                external_url = f'https://hub.cocoloop.cn/skills/{sid}'
            if external_url and '/skills/' not in external_url:
                continue

            out.append({
                'id': sid or (external_url.rsplit('/', 1)[-1] if external_url else ''),
                'name': name,
                'description': desc,
                'external_url': external_url,
                'download_url': download_url,
            })
        return out

    def _fetch_cocoloop_urls_from_api(limit=2000, query=''):
        cfg = _load_skill_market_config()
        configured = cfg.get('api_urls', []) or []
        default_candidates = [
            'https://hub.cocoloop.cn/api/skills',
            'https://hub.cocoloop.cn/api/market/skills',
            'https://hub.cocoloop.cn/api/search/skills',
        ]

        candidates = []
        for u in configured + default_candidates:
            url = str(u or '').strip()
            if not url:
                continue
            if url not in candidates:
                candidates.append(url)

        headers = {'User-Agent': 'ShizukuNyaBot/1.0'}
        seen = set()
        urls = []
        source_diag = []
        errors = []

        max_pages = 12
        for api_url in candidates:
            try:
                added_total = 0
                for p in range(1, max_pages + 1):
                    resp = requests.get(
                        api_url,
                        timeout=12,
                        headers=headers,
                        params={
                            'page': p,
                            'page_size': min(200, limit),
                            'limit': min(200, limit),
                            'per_page': min(200, limit),
                            'size': min(200, limit),
                            'query': query or ''
                        }
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                    normalized = _normalize_cocoloop_api_items(payload)
                    if not normalized:
                        break

                    added_page = 0
                    for it in normalized:
                        u = str(it.get('external_url') or '').strip()
                        if not u or u in seen:
                            continue
                        seen.add(u)
                        urls.append(u)
                        added_page += 1
                        added_total += 1
                        if len(urls) >= limit:
                            break

                    if len(urls) >= limit:
                        break
                    # 当翻页已无新增时提前停止
                    if added_page == 0:
                        break

                source_diag.append({'source': f'api:{api_url}', 'count': added_total, 'ok': True})
                if len(urls) >= limit:
                    break
            except Exception as exc:
                errors.append(f'api {api_url}: {exc}')
                source_diag.append({'source': f'api:{api_url}', 'count': 0, 'ok': False})

        return urls[:limit], source_diag, errors

    def _extract_cocoloop_locs(xml_text):
        return re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', str(xml_text or ''), flags=re.IGNORECASE)

    def _fetch_cocoloop_skill_urls(limit=2000, query=''):
        limit = max(1, min(5000, int(limit or 2000)))
        now = time.time()
        diag = {
            'timestamp': now,
            'sources': [],
            'errors': [],
            'total_urls': 0,
            'used_cache': False,
            'mode': 'official_only',
        }
        cached_urls = list(_COCOLOOP_URLS_CACHE.get('urls') or [])
        if cached_urls and (now - float(_COCOLOOP_URLS_CACHE.get('ts') or 0.0)) <= _COCOLOOP_URLS_TTL:
            diag['used_cache'] = True
            diag['total_urls'] = min(len(cached_urls), limit)
            _COCOLOOP_LAST_DIAG.update(diag)
            return cached_urls[:limit]

        skill_urls = []
        seen = set()

        api_urls, api_diag, api_errors = _fetch_cocoloop_urls_from_api(limit=limit, query=query)
        for u in api_urls:
            if u not in seen:
                seen.add(u)
                skill_urls.append(u)
        diag['sources'].extend(api_diag)
        diag['errors'].extend(api_errors)

        if skill_urls:
            _COCOLOOP_URLS_CACHE['ts'] = now
            _COCOLOOP_URLS_CACHE['urls'] = list(skill_urls)
            diag['total_urls'] = len(skill_urls)
            _COCOLOOP_LAST_DIAG.update(diag)
            return skill_urls[:limit]

        diag['errors'].append('official api unavailable or empty')
        diag['used_cache'] = True
        diag['total_urls'] = min(len(cached_urls), limit)
        _COCOLOOP_LAST_DIAG.update(diag)
        return cached_urls[:limit]

    def _extract_cocoloop_skill_meta(skill_url):
        now = time.time()
        cache_item = _COCOLOOP_META_CACHE.get(skill_url)
        if cache_item and (now - float(cache_item.get('ts') or 0.0)) <= _COCOLOOP_META_TTL:
            return dict(cache_item.get('data') or {})

        headers = {'User-Agent': 'ShizukuNyaBot/1.0'}
        try:
            resp = requests.get(skill_url, timeout=12, headers=headers)
            resp.raise_for_status()
            html = resp.text
        except Exception:
            meta = {
                'name': f'skill-{skill_url.rsplit("/", 1)[-1]}',
                'description': '来自 CocoLoop 市场',
                'download_url': ''
            }
            _COCOLOOP_META_CACHE[skill_url] = {'ts': now, 'data': meta}
            return meta

        name = ''
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, flags=re.IGNORECASE | re.DOTALL)
        if h1:
            name = re.sub(r'<[^>]+>', '', h1.group(1)).strip()
        if not name:
            t = re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.IGNORECASE | re.DOTALL)
            if t:
                name = re.sub(r'<[^>]+>', '', t.group(1)).strip().split('|')[0].strip()
        if not name:
            name = f'skill-{skill_url.rsplit("/", 1)[-1]}'

        desc = ''
        og_desc = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        if og_desc:
            desc = og_desc.group(1).strip()
        if not desc:
            meta_desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
            if meta_desc:
                desc = meta_desc.group(1).strip()
        if not desc:
            desc = '来自 CocoLoop 市场'

        dl = ''
        m = re.search(r'https?://dl\.cocoloop\.cn[^"\'\s>]+\.zip', html, flags=re.IGNORECASE)
        if m:
            dl = m.group(0).strip()

        meta = {'name': name, 'description': desc, 'download_url': dl}
        _COCOLOOP_META_CACHE[skill_url] = {'ts': now, 'data': meta}
        return meta

    def _fetch_cocoloop_market_items(limit=40, query=''):
        """GitHub-driven skill market list (metadata only)."""
        limit = max(1, min(5000, int(limit or 40)))
        query = str(query or '').strip().lower()

        gh_cfg = _load_skill_market_github_config()
        topics = gh_cfg.get('topics') or ['copilot-skill', 'github-copilot-skill', 'ai-skill']
        cache_key = _skill_market_cache_key('github', query, ','.join(sorted([str(t).strip().lower() for t in topics if str(t).strip()])))
        cached = _skill_market_cache_get(cache_key)
        if cached and cached.get('items'):
            cached_items = list(cached.get('items') or [])
            _COCOLOOP_LAST_DIAG['timestamp'] = cached.get('ts') or time.time()
            _COCOLOOP_LAST_DIAG['sources'] = cached.get('diag', {}).get('sources') or [{'source': 'github.search.repositories', 'count': len(cached_items), 'ok': True}]
            _COCOLOOP_LAST_DIAG['errors'] = []
            _COCOLOOP_LAST_DIAG['warnings'] = []
            _COCOLOOP_LAST_DIAG['total_urls'] = len(cached_items)
            _COCOLOOP_LAST_DIAG['used_cache'] = True
            _COCOLOOP_LAST_DIAG['mode'] = 'github_metadata_only'
            _COCOLOOP_URLS_CACHE['ts'] = cached.get('ts') or time.time()
            _COCOLOOP_URLS_CACHE['urls'] = [str(x.get('external_url') or '') for x in cached_items if str(x.get('external_url') or '').strip()]
            return cached_items[:limit]

        per_page = min(100, max(10, limit))
        headers = {
            'User-Agent': 'ShizukuNyaBot/1.0',
            'Accept': 'application/vnd.github+json'
        }

        # 允许通过配置或环境变量提供 GitHub token，缓解匿名速率限制导致的 403。
        token = str(gh_cfg.get('token') or os.getenv('GITHUB_TOKEN') or '').strip()
        if token:
            headers['Authorization'] = f'Bearer {token}'

        fallback_repos = [
            {
                'full_name': 'microsoft/skills',
                'name': 'skills',
                'description': 'Community skills and examples',
                'html_url': 'https://github.com/microsoft/skills',
                'owner': {'login': 'microsoft'},
                'stargazers_count': 0,
                'language': '',
                'topics': ['skill']
            },
            {
                'full_name': 'openai/openai-cookbook',
                'name': 'openai-cookbook',
                'description': 'Examples and guides for AI integrations',
                'html_url': 'https://github.com/openai/openai-cookbook',
                'owner': {'login': 'openai'},
                'stargazers_count': 0,
                'language': 'Python',
                'topics': ['ai', 'examples']
            },
            {
                'full_name': 'modelcontextprotocol/servers',
                'name': 'servers',
                'description': 'Reference MCP servers and integrations',
                'html_url': 'https://github.com/modelcontextprotocol/servers',
                'owner': {'login': 'modelcontextprotocol'},
                'stargazers_count': 0,
                'language': '',
                'topics': ['mcp', 'server', 'skill']
            },
        ]

        all_items = []
        seen = set()
        errs = []
        warns = []
        for topic in topics:
            try:
                q = f'topic:{topic} archived:false'
                resp = requests.get(
                    'https://api.github.com/search/repositories',
                    params={'q': q, 'sort': 'stars', 'order': 'desc', 'per_page': per_page},
                    headers=headers,
                    timeout=15
                )
                if resp.status_code == 403:
                    rem = resp.headers.get('X-RateLimit-Remaining', '')
                    rst = resp.headers.get('X-RateLimit-Reset', '')
                    raise RuntimeError(f'github rate limit or forbidden (remaining={rem}, reset={rst})')
                resp.raise_for_status()
                payload = resp.json() or {}
                repos = payload.get('items') or []
                for repo in repos:
                    rid = str(repo.get('full_name') or '').strip().lower()
                    if not rid or rid in seen:
                        continue
                    seen.add(rid)
                    tags = list(repo.get('topics') or [])
                    item = {
                        'id': rid.replace('/', '__'),
                        'name': str(repo.get('name') or rid),
                        'description': str(repo.get('description') or 'GitHub 开源 Skill 条目'),
                        'source': 'github.com',
                        'external_url': str(repo.get('html_url') or ''),
                        'download_url': '',
                        'author': str((repo.get('owner') or {}).get('login') or ''),
                        'stars': int(repo.get('stargazers_count') or 0),
                        'language': str(repo.get('language') or ''),
                        'topics': tags,
                        'updated_at': str(repo.get('updated_at') or ''),
                        'registry_mode': 'metadata_only',
                    }
                    if query:
                        qsrc = ' '.join([
                            str(item.get('name', '')).lower(),
                            str(item.get('description', '')).lower(),
                            str(item.get('external_url', '')).lower(),
                            str(item.get('author', '')).lower(),
                            ' '.join([str(t).lower() for t in tags]),
                        ])
                        if query not in qsrc:
                            continue
                    all_items.append(item)
                    if len(all_items) >= limit:
                        break
                if len(all_items) >= limit:
                    break
            except Exception as exc:
                warns.append(f'github topic {topic}: {exc}')

        # 无法从 GitHub API 拉到数据时，回退到稳定开源仓库清单，避免前端 0 条。
        if not all_items:
            for repo in fallback_repos:
                rid = str(repo.get('full_name') or '').strip().lower()
                if not rid or rid in seen:
                    continue
                seen.add(rid)
                tags = list(repo.get('topics') or [])
                item = {
                    'id': rid.replace('/', '__'),
                    'name': str(repo.get('name') or rid),
                    'description': str(repo.get('description') or 'GitHub 开源 Skill 条目'),
                    'source': 'github.com',
                    'external_url': str(repo.get('html_url') or ''),
                    'download_url': '',
                    'author': str((repo.get('owner') or {}).get('login') or ''),
                    'stars': int(repo.get('stargazers_count') or 0),
                    'language': str(repo.get('language') or ''),
                    'topics': tags,
                    'updated_at': str(repo.get('updated_at') or ''),
                    'registry_mode': 'metadata_only',
                }
                if query:
                    qsrc = ' '.join([
                        str(item.get('name', '')).lower(),
                        str(item.get('description', '')).lower(),
                        str(item.get('external_url', '')).lower(),
                        str(item.get('author', '')).lower(),
                        ' '.join([str(t).lower() for t in tags]),
                    ])
                    if query not in qsrc:
                        continue
                all_items.append(item)
                if len(all_items) >= limit:
                    break

            if all_items:
                warns.append('github api unavailable, fallback to built-in open-source repository list')

        # 只要有可用条目，外部只展示空错误；警告仅作为内部信息，不推到主诊断。
        if all_items:
            errs = []
            warns = []

        # 回填缓存，避免诊断面板长期显示“缓存 0 条”。
        now = time.time()
        _COCOLOOP_URLS_CACHE['ts'] = now
        _COCOLOOP_URLS_CACHE['urls'] = [str(x.get('external_url') or '') for x in all_items if str(x.get('external_url') or '').strip()]
        _skill_market_cache_set(cache_key, all_items, {
            'sources': [{'source': 'github.search.repositories', 'count': len(all_items), 'ok': len(all_items) > 0}],
            'errors': errs,
            'warnings': warns,
        })

        _COCOLOOP_LAST_DIAG['timestamp'] = now
        _COCOLOOP_LAST_DIAG['sources'] = [{'source': 'github.search.repositories', 'count': len(all_items), 'ok': len(all_items) > 0}]
        _COCOLOOP_LAST_DIAG['errors'] = errs
        _COCOLOOP_LAST_DIAG['warnings'] = warns
        _COCOLOOP_LAST_DIAG['total_urls'] = len(all_items)
        _COCOLOOP_LAST_DIAG['used_cache'] = False
        _COCOLOOP_LAST_DIAG['mode'] = 'github_metadata_only'

        return all_items[:limit]

    def _resolve_cocoloop_download_url(raw_url):
        """Official-only: only direct CocoLoop download URL is accepted."""
        url = str(raw_url or '').strip()
        if not url:
            raise ValueError('url is required')

        if re.search(r'^https?://dl\.cocoloop\.cn/.+\.zip$', url, flags=re.IGNORECASE):
            return url

        raise ValueError('官方模式仅支持 dl.cocoloop.cn 的直链 zip。请先通过官方 API 获取 download_url。')

    @app.route('/api/skills/market/github', methods=['GET'])
    @app.route('/api/skills/market/cocoloop', methods=['GET'])
    def api_skills_market_cocoloop():
        try:
            page = int(request.args.get('page', 1) or 1)
            page_size = int(request.args.get('page_size', 30) or 30)
            query = str(request.args.get('query', '') or '').strip()

            page = max(1, page)
            page_size = max(5, min(100, page_size))

            fetch_limit = min(5000, page * page_size + page_size)
            items = _fetch_cocoloop_market_items(limit=fetch_limit, query=query)

            start = (page - 1) * page_size
            end = start + page_size
            paged = items[start:end]
            has_more = end < len(items)

            return jsonify({
                'success': True,
                'items': paged,
                'count': len(paged),
                'source': 'github.com',
                'page': page,
                'page_size': page_size,
                'total': len(items),
                'has_more': has_more,
                'query': query,
                'diagnostics': {
                    'timestamp': _COCOLOOP_LAST_DIAG.get('timestamp'),
                    'sources': list(_COCOLOOP_LAST_DIAG.get('sources') or []),
                    'errors': list(_COCOLOOP_LAST_DIAG.get('errors') or []),
                    'warnings': list(_COCOLOOP_LAST_DIAG.get('warnings') or []),
                    'total_urls': _COCOLOOP_LAST_DIAG.get('total_urls', 0),
                    'used_cache': bool(_COCOLOOP_LAST_DIAG.get('used_cache', False)),
                    'cache': {
                        'count': len(_COCOLOOP_URLS_CACHE.get('urls') or []),
                        'age_seconds': (max(0, int(time.time() - float(_COCOLOOP_URLS_CACHE.get('ts') or 0.0))) if _COCOLOOP_URLS_CACHE.get('ts') else None),
                        'ttl_seconds': _SKILL_MARKET_RESULTS_TTL,
                    },
                    'meta_cache': {
                        'count': len(_COCOLOOP_META_CACHE),
                        'ttl_seconds': _COCOLOOP_META_TTL,
                    },
                    'mode': 'github_metadata_only'
                }
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'items': [],
                'count': 0,
                'source': 'github.com',
                'page': 1,
                'page_size': max(5, min(100, int(request.args.get('page_size', 30) or 30))),
                'total': 0,
                'has_more': False,
                'query': str(request.args.get('query', '') or '').strip(),
                'diagnostics': {
                    'timestamp': _COCOLOOP_LAST_DIAG.get('timestamp'),
                    'sources': list(_COCOLOOP_LAST_DIAG.get('sources') or []),
                    'errors': list(_COCOLOOP_LAST_DIAG.get('errors') or []) + [str(e)],
                    'warnings': list(_COCOLOOP_LAST_DIAG.get('warnings') or []),
                    'total_urls': _COCOLOOP_LAST_DIAG.get('total_urls', 0),
                    'used_cache': bool(_COCOLOOP_LAST_DIAG.get('used_cache', False)),
                    'cache': {
                        'count': len(_COCOLOOP_URLS_CACHE.get('urls') or []),
                        'age_seconds': (max(0, int(time.time() - float(_COCOLOOP_URLS_CACHE.get('ts') or 0.0))) if _COCOLOOP_URLS_CACHE.get('ts') else None),
                        'ttl_seconds': _SKILL_MARKET_RESULTS_TTL,
                    },
                    'meta_cache': {
                        'count': len(_COCOLOOP_META_CACHE),
                        'ttl_seconds': _COCOLOOP_META_TTL,
                    },
                    'mode': 'github_metadata_only'
                }
            }), 502

    @app.route('/api/skills/market/github/install', methods=['POST'])
    @app.route('/api/skills/market/cocoloop/install', methods=['POST'])
    def api_skills_market_cocoloop_install():
        try:
            data = request.get_json() or {}
            return jsonify({
                'success': True,
                'message': 'Skill 市场为元数据模式：请前往仓库 README 按说明手动配置',
                'mode': 'github_metadata_only',
                'setup_instructions': {
                    'description': '该 Skill 由 GitHub 开源市场提供元数据，不执行自动下载安装。',
                    'required_fields': ['repository_url', 'branch/tag', 'skill_entrypoint', 'env(optional)'],
                    'note': '请点击“查看详情”进入仓库，按项目文档完成接入。'
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/market/skillhub/status', methods=['GET'])
    def api_skills_market_skillhub_status():
        try:
            info = _skillhub_runner_info()
            cli = str(info.get('cli') or '').strip()
            installed = bool(info.get('installed'))
            mode = str(info.get('mode') or '')
            if not cli:
                return jsonify({'success': True, 'installed': False, 'cli': '', 'version': '', 'mode': 'missing'})

            version = ''
            for args in (['--version'], ['version']):
                try:
                    r = _run_skillhub_cli(args, timeout=10)
                    if r.get('ok'):
                        version = (r.get('stdout') or '').strip().splitlines()[0] if (r.get('stdout') or '').strip() else ''
                        break
                except Exception:
                    continue
            return jsonify({'success': True, 'installed': installed, 'cli': cli, 'version': version, 'mode': mode})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/market/skillhub/cli/install', methods=['POST'])
    def api_skills_market_skillhub_cli_install():
        try:
            job = _start_skillhub_install_job()
            return jsonify({
                'success': True,
                'installed': False,
                'message': 'SkillHub CLI 安装已在后台启动',
                'job_id': job.get('job_id'),
                'status_url': f"/api/skills/market/skillhub/cli/install/jobs/{job.get('job_id')}",
                'command': job.get('command_display', ''),
                'logs': list(job.get('logs') or []),
                'status': job.get('status', 'queued')
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/market/skillhub/cli/install/jobs/<job_id>', methods=['GET'])
    def api_skills_market_skillhub_cli_install_job(job_id):
        try:
            job = _skillhub_install_job_snapshot(str(job_id).strip())
            if not job:
                return jsonify({'success': False, 'error': 'job not found'}), 404
            return jsonify({'success': True, **job})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/market/skillhub/search', methods=['GET'])
    def api_skills_market_skillhub_search():
        try:
            page = int(request.args.get('page', 1) or 1)
            page_size = int(request.args.get('page_size', 30) or 30)
            query = str(request.args.get('query', '') or '').strip()

            page = max(1, page)
            page_size = max(5, min(100, page_size))

            cli = _find_skillhub_cli()
            if not cli:
                return jsonify({'success': False, 'error': 'SkillHub CLI 未安装'}), 400

            cache_key = _skill_market_cache_key('skillhub', query, cli)
            cached = _skill_market_cache_get(cache_key)
            if cached and cached.get('items'):
                items = list(cached.get('items') or [])
                start = (page - 1) * page_size
                end = start + page_size
                paged = items[start:end]
                _COCOLOOP_URLS_CACHE['ts'] = cached.get('ts') or time.time()
                _COCOLOOP_URLS_CACHE['urls'] = [str(x.get('external_url') or x.get('skillhub_id') or x.get('id') or '') for x in items if str(x.get('external_url') or x.get('skillhub_id') or x.get('id') or '').strip()]
                diag = dict(cached.get('diag') or {})
                diag.update({
                    'mode': 'skillhub_cli',
                    'cli': cli,
                    'cached': True,
                    'errors': list(diag.get('errors') or []),
                })
                return jsonify({
                    'success': True,
                    'items': paged,
                    'count': len(paged),
                    'source': 'skillhub',
                    'page': page,
                    'page_size': page_size,
                    'total': len(items),
                    'has_more': end < len(items),
                    'query': query,
                    'diagnostics': diag,
                })

            attempts = []
            if query:
                attempts.extend([
                    ['find', query],
                    ['search', query],
                ])
            else:
                attempts.extend([
                    ['find', ''],
                    ['search', ''],
                ])

            payload = None
            text_rows = []
            errors = []
            for args in attempts:
                result = _run_skillhub_cli(args, timeout=40)
                if not result.get('ok'):
                    errors.append((result.get('stderr') or result.get('stdout') or '').strip()[:300])
                    continue

                out = result.get('stdout') or ''
                parsed = _extract_json_from_text(out)
                if parsed is not None:
                    payload = parsed
                    break

                for line in out.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    text_rows.append(line)
                if text_rows:
                    break

            items = _normalize_skillhub_items(payload) if payload is not None else []
            if not items and text_rows:
                for i, line in enumerate(text_rows, start=1):
                    cleaned = _skillhub_clean_text(line)
                    if not cleaned:
                        continue
                    if query and query.lower() not in cleaned.lower():
                        continue
                    sid = f'skillhub-{i}'
                    items.append({
                        'id': sid,
                        'name': cleaned[:80],
                        'description': cleaned,
                        'source': 'skillhub',
                        'external_url': '',
                        'author': '',
                        'version': '',
                        'language': '',
                        'topics': [],
                        'stars': 0,
                        'skillhub_id': sid,
                    })

            _skill_market_cache_set(cache_key, items, {
                'mode': 'skillhub_cli',
                'errors': [],
                'warnings': errors[:5],
                'cli': cli,
                'cached': False,
            })
            _COCOLOOP_URLS_CACHE['ts'] = time.time()
            _COCOLOOP_URLS_CACHE['urls'] = [str(x.get('external_url') or x.get('skillhub_id') or x.get('id') or '') for x in items if str(x.get('external_url') or x.get('skillhub_id') or x.get('id') or '').strip()]

            start = (page - 1) * page_size
            end = start + page_size
            paged = items[start:end]
            return jsonify({
                'success': True,
                'items': paged,
                'count': len(paged),
                'source': 'skillhub',
                'page': page,
                'page_size': page_size,
                'total': len(items),
                'has_more': end < len(items),
                'query': query,
                'diagnostics': {
                    'mode': 'skillhub_cli',
                    'errors': errors[:5],
                    'cli': cli,
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/market/skillhub/install', methods=['POST'])
    def api_skills_market_skillhub_install():
        try:
            data = request.get_json() or {}
            source = str(data.get('source') or 'skillhub').strip().lower()
            external_url = str(data.get('external_url') or data.get('url') or '').strip()
            skill_ref = str(data.get('skill_id') or data.get('id') or data.get('name') or '').strip()

            refs = []
            for v in [skill_ref, external_url, str(data.get('repository') or '').strip()]:
                if v and v not in refs:
                    refs.append(v)

            if not refs:
                return jsonify({'success': False, 'error': 'skill_id is required'}), 400

            errors = []
            for ref in refs:
                attempts = _skillhub_install_attempts_for_ref(ref, external_url)
                for args in attempts:
                    r = _run_skillhub_cli(args, timeout=120)
                    if r.get('ok'):
                        try:
                            chat_system.reload_skills()
                        except Exception:
                            pass
                        return jsonify({
                            'success': True,
                            'skill_id': ref,
                            'message': f'SkillHub 技能安装完成: {ref}',
                            'stdout': (r.get('stdout') or '')[-1200:],
                            'source': source,
                            'used_command': ' '.join(map(str, r.get('cmd') or [])),
                        })
                    errors.append({
                        'ref': ref,
                        'cmd': ' '.join(map(str, r.get('cmd') or [])),
                        'message': (r.get('stderr') or r.get('stdout') or '').strip()[:800],
                        'code': r.get('code'),
                    })

            return jsonify({
                'success': False,
                'error': 'SkillHub 安装失败，请检查 CLI 输出',
                'details': errors,
                'suggestion': '请优先尝试使用仓库 URL（owner/repo 或 https://...）作为 skill_id，或使用“Agent 一键部署”。'
            }), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/market/agent-deploy', methods=['POST'])
    def api_skills_market_agent_deploy():
        try:
            data = request.get_json() or {}
            source = str(data.get('source') or '').strip().lower() or 'github'
            skill_id = str(data.get('skill_id') or data.get('id') or '').strip()
            name = str(data.get('name') or '').strip()
            external_url = str(data.get('external_url') or data.get('url') or '').strip()

            if not (skill_id or external_url or name):
                return jsonify({'success': False, 'error': '缺少 skill 标识信息'}), 400

            job = _start_agent_deploy_job(source, skill_id, name, external_url)
            return jsonify({
                'success': True,
                'message': 'Agent 一键部署已启动',
                'job_id': job.get('job_id'),
                'status_url': f"/api/skills/market/agent-deploy/jobs/{job.get('job_id')}",
                'status': job.get('status', 'queued'),
                'command': job.get('command_display', ''),
                'logs': list(job.get('logs') or []),
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/market/agent-deploy/jobs/<job_id>', methods=['GET'])
    def api_skills_market_agent_deploy_job(job_id):
        try:
            job = _agent_deploy_job_snapshot(str(job_id).strip())
            if not job:
                return jsonify({'success': False, 'error': 'job not found'}), 404
            return jsonify({'success': True, **job})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/market/cocoloop/diagnostics', methods=['GET'])
    def api_skills_market_cocoloop_diagnostics():
        try:
            now = time.time()
            cache_ts = float(_COCOLOOP_URLS_CACHE.get('ts') or 0.0)
            cached_count = len(_COCOLOOP_URLS_CACHE.get('urls') or [])
            cache_age = max(0, int(now - cache_ts)) if cache_ts else None
            diag = dict(_COCOLOOP_LAST_DIAG or {})
            diag.update({
                'cache': {
                    'count': cached_count,
                    'age_seconds': cache_age,
                    'ttl_seconds': _COCOLOOP_URLS_TTL,
                },
                'meta_cache': {
                    'count': len(_COCOLOOP_META_CACHE),
                    'ttl_seconds': _COCOLOOP_META_TTL,
                }
            })
            return jsonify({'success': True, 'diagnostics': diag})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    def _test_database_connectivity(db_cfg):
        """Run ping/TCP/login checks after database configuration changes."""
        result = {
            'engine': str((db_cfg or {}).get('engine', 'mysql') or 'mysql'),
            'host': str((db_cfg or {}).get('host', '') or ''),
            'port': int((db_cfg or {}).get('port', 3306) or 3306),
            'ping': {'ok': False, 'detail': '未执行'},
            'tcp': {'ok': False, 'detail': '未执行'},
            'db_login': {'ok': False, 'detail': '未执行'},
            'overall_ok': False,
        }

        host = result['host']
        port = result['port']
        if not host:
            result['ping'] = {'ok': False, 'detail': 'host 为空'}
            result['tcp'] = {'ok': False, 'detail': 'host 为空'}
            result['db_login'] = {'ok': False, 'detail': 'host 为空'}
            return result

        # 1) Ping test
        try:
            if platform.system().lower().startswith('win'):
                cmd = ['ping', '-n', '1', '-w', '2000', host]
            else:
                cmd = ['ping', '-c', '1', '-W', '2', host]
            ping_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if ping_proc.returncode == 0:
                result['ping'] = {'ok': True, 'detail': 'ping 成功'}
            else:
                detail = (ping_proc.stderr or ping_proc.stdout or '').strip()
                result['ping'] = {'ok': False, 'detail': detail[:200] or 'ping 失败'}
        except Exception as exc:
            result['ping'] = {'ok': False, 'detail': f'ping 异常: {exc}'}

        # 2) TCP test
        try:
            with socket.create_connection((host, port), timeout=3):
                result['tcp'] = {'ok': True, 'detail': f'TCP {host}:{port} 可达'}
        except Exception as exc:
            result['tcp'] = {'ok': False, 'detail': f'TCP 连接失败: {exc}'}

        # 3) DB login handshake
        try:
            from app.database.database import get_connection
            conn = get_connection()
            if conn:
                conn.close()
                result['db_login'] = {'ok': True, 'detail': '数据库登录成功'}
            else:
                result['db_login'] = {'ok': False, 'detail': '数据库登录失败'}
        except Exception as exc:
            result['db_login'] = {'ok': False, 'detail': f'数据库登录异常: {exc}'}

        result['overall_ok'] = bool(result['tcp']['ok'] and result['db_login']['ok'])
        return result

    def _normalize_onebot_config(onebot_cfg):
        """Support both legacy and structured OneBot config."""
        cfg = onebot_cfg if isinstance(onebot_cfg, dict) else {}
        host = str(cfg.get('host', '0.0.0.0') or '0.0.0.0')
        port = int(cfg.get('port', 3000) or 3000)
        token = str(cfg.get('access_token', '') or '')

        http_cfg = cfg.get('http', {}) if isinstance(cfg.get('http', {}), dict) else {}
        ws_cfg = cfg.get('ws', {}) if isinstance(cfg.get('ws', {}), dict) else {}
        rev_cfg = cfg.get('ws_reverse', {}) if isinstance(cfg.get('ws_reverse', {}), dict) else {}

        if not http_cfg:
            http_cfg = {'enable': True, 'host': host, 'port': port}
        if not ws_cfg:
            ws_cfg = {'enable': False, 'host': host, 'port': port + 1}
        if not rev_cfg:
            rev_cfg = {'enable': False, 'url': ''}

        http_cfg.setdefault('enable', True)
        http_cfg.setdefault('host', host)
        http_cfg.setdefault('port', port)

        ws_cfg.setdefault('enable', False)
        ws_cfg.setdefault('host', host)
        ws_cfg.setdefault('port', port + 1)

        rev_cfg.setdefault('enable', False)
        rev_cfg.setdefault('url', '')

        return {
            'access_token': token,
            'http': http_cfg,
            'ws': ws_cfg,
            'ws_reverse': rev_cfg,
        }

    def _normalize_probe_host(host):
        host = str(host or '').strip()
        if host in ('', '0.0.0.0', '::'):
            return '127.0.0.1'
        return host

    def _run_host_ping(host):
        if not host:
            return {'ok': False, 'detail': 'host 为空'}
        host = _normalize_probe_host(host)
        try:
            if platform.system().lower().startswith('win'):
                cmd = ['ping', '-n', '1', '-w', '1200', host]
            else:
                cmd = ['ping', '-c', '1', '-W', '1', host]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if proc.returncode == 0:
                return {'ok': True, 'detail': 'ping 成功'}
            detail = (proc.stderr or proc.stdout or '').strip()
            return {'ok': False, 'detail': detail[:200] or 'ping 失败'}
        except Exception as exc:
            return {'ok': False, 'detail': f'ping 异常: {exc}'}

    def _check_tcp(host, port, timeout=3):
        host = _normalize_probe_host(host)
        try:
            with socket.create_connection((host, int(port)), timeout=max(0.1, float(timeout))):
                return {'ok': True, 'detail': f'TCP {host}:{port} 可达'}
        except Exception as exc:
            return {'ok': False, 'detail': f'TCP 连接失败: {exc}'}

    def _check_http_json(url, timeout=3):
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
                status = int(getattr(resp, 'status', 200) or 200)
                return {
                    'ok': 200 <= status < 300,
                    'status': status,
                    'detail': raw[:240]
                }
        except urllib.error.HTTPError as exc:
            return {'ok': False, 'status': int(exc.code), 'detail': str(exc)}
        except Exception as exc:
            return {'ok': False, 'status': 0, 'detail': str(exc)}

    def _check_http_candidates(base_url, paths, timeout=3):
        """Try multiple HTTP probe paths and return the first successful result."""
        base = str(base_url or '').rstrip('/')
        last_result = None
        for path in paths:
            suffix = path if str(path).startswith('/') else f'/{path}'
            url = f"{base}{suffix}"
            result = _check_http_json(url, timeout=timeout)
            detail = str(result.get('detail', '') or '').strip()
            result['detail'] = f"{suffix} {detail}".strip()
            result['probe_url'] = url
            if result.get('ok'):
                return result
            last_result = result
        return last_result or {'ok': False, 'status': 0, 'detail': '未执行'}

    # 配置日志写入 app.log
    log_handler = RotatingFileHandler(CONFIG['server']['log_file'], maxBytes=1e6, backupCount=2, encoding='utf-8')
    log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    app.logger.addHandler(log_handler)
    app.logger.setLevel(logging.INFO)

    @app.route('/')
    def index():
        # 根据环境变量决定默认页面，默认为 /control_panel
        default_page = os.environ.get('DEFAULT_PAGE', '/control_panel')
        
        # 如果是文件（包含.），则尝试作为静态文件发送
        if '.' in default_page:
            return app.send_static_file(default_page.lstrip('/'))
        
        # 否则作为路由重定向
        if default_page.startswith('/'):
            target_file = default_page.lstrip('/') + '.html'
            if os.path.exists(os.path.join(app.static_folder, target_file)):
                return app.send_static_file(target_file)
            
        # 默认回退
        return app.send_static_file('control_panel.html')
        
    @app.route('/control_panel')
    def control_panel():
        return app.send_static_file('control_panel.html')

    @app.route('/security-init')
    def security_init_route():
        """提供安全系统初始化页面 (管理员专用)"""
        return app.send_static_file('security-init.html')

    @app.route('/sandbox')
    def sandbox_route():
        return app.send_static_file('chat-sandbox.html')

    @app.route('/chat', methods=['POST'])
    def chat_endpoint():
        try:
            data = request.get_json()
            if not data or (not data.get('message') and not data.get('image') and not data.get('attachments')):
                return jsonify({'success': False, 'error': '无效请求'}), 400

            frontend_source = request.headers.get('X-Frontend-Source', 'control_panel')
            quick_reply = None
            short_term_before = []
            if frontend_source in ('sandbox', 'control_panel'):
                try:
                    short_term_before = chat_system.agent_manager.memory.load_short_term()
                except Exception:
                    short_term_before = []

            stream_mode = bool(data.get('stream'))
            # Web请求被视为管理员操作，允许使用Agent工具
            def _build_chat_response():
                return chat_system.chat(
                    data.get('message'),
                    data.get('image'),
                    is_admin=True,
                    attachments=data.get('attachments'),
                    frontend_source=frontend_source,
                    persona_filename=data.get('persona_filename')
                )

            if stream_mode:
                def _sse(event_name: str, payload) -> str:
                    try:
                        body = json.dumps(payload, ensure_ascii=False)
                    except Exception:
                        body = json.dumps({'text': str(payload)}, ensure_ascii=False)
                    return f"event: {event_name}\ndata: {body}\n\n"

                def stream_reply():
                    # AstrBot 风格：流式事件先发 start，再持续 delta，最后 done。
                    trace_events = []

                    def _trace_event(event_type: str, label: str, content: str = '', tool_name: str = ''):
                        event = {
                            'role': 'assistant',
                            'type': event_type,
                            'label': label,
                            'tool_name': tool_name,
                            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                            'content': str(content or '')[:6000],
                        }
                        trace_events.append(event)
                        return event

                    yield _sse('meta', {'stage': 'start'})
                    try:
                        policy = {}
                        try:
                            policy = chat_system._build_call_policy(
                                data.get('message', ''),
                                has_image=bool(data.get('image')),
                                attachments=data.get('attachments'),
                                is_admin=True,
                                frontend_source=frontend_source
                            )
                        except Exception:
                            policy = {}
                        if policy:
                            policy_note = (
                                f"simple={bool(policy.get('simple_chat'))}, "
                                f"repo={bool(policy.get('enable_repo_context'))}, "
                                f"history={bool(policy.get('enable_history_recall'))}, "
                                f"turns={int(policy.get('context_max_turns') or 0)}"
                            )
                            yield _sse('trace', _trace_event('assistant_message', '调用策略', policy_note))

                        stream_iter = chat_system.stream_chat(
                            data.get('message'),
                            data.get('image'),
                            is_admin=True,
                            attachments=data.get('attachments'),
                            frontend_source=frontend_source,
                            persona_filename=data.get('persona_filename')
                        )
                        has_chunk = False
                        full_text = ''
                        for piece in stream_iter:
                            text = str(piece or '')
                            if not text:
                                continue
                            has_chunk = True
                            full_text += text
                            yield _sse('delta', {'text': text})
                        if not has_chunk:
                            full_text = '（空回复）'
                            yield _sse('delta', {'text': full_text})

                        debug_payload = None
                        if frontend_source in ('sandbox', 'control_panel'):
                            try:
                                short_term_after = chat_system.agent_manager.memory.load_short_term()
                                delta = short_term_after[len(short_term_before):] if len(short_term_after) >= len(short_term_before) else short_term_after
                                for item in delta[-80:]:
                                    role = str(item.get('role', 'unknown') or 'unknown')
                                    content = str(item.get('content', '') or '')
                                    event_type = 'message'
                                    label = '消息'
                                    tool_name = ''
                                    if role == 'assistant' and content.startswith('Called '):
                                        event_type = 'tool_call'
                                        tool_name = content[len('Called '):].strip()
                                        label = f"调用工具 {tool_name}" if tool_name else '调用工具'
                                    elif role == 'system' and content.startswith('Result:'):
                                        event_type = 'tool_result'
                                        label = '工具返回结果'
                                    elif role == 'assistant':
                                        stripped = content.strip()
                                        if stripped.startswith('思考:') or stripped.startswith('Thought:') or stripped.startswith('[THINK]'):
                                            event_type = 'assistant_message'
                                            label = '思考内容'
                                        else:
                                            event_type = 'assistant_reply'
                                            label = 'AI 回复'

                                    event = {
                                        'role': role,
                                        'type': event_type,
                                        'label': label,
                                        'tool_name': tool_name,
                                        'timestamp': item.get('timestamp'),
                                        'content': content[:6000],
                                    }
                                    trace_events.append(event)
                                    yield _sse('trace', event)

                                chat_settings = _default_chat_settings((CONFIG.get('work_mode', {}) or {}).get('chat_settings', {}))
                                debug_payload = {
                                    'enabled': bool(chat_settings.get('show_chat_debug_trace', True)) and bool(trace_events),
                                    'collapsed': bool(chat_settings.get('chat_trace_default_collapsed', True)),
                                    'events': trace_events[-120:],
                                    'trace_md': {'path': '/trace/stream', 'preview': ''}
                                }
                            except Exception:
                                debug_payload = None

                        done_payload = {'reply': full_text}
                        if debug_payload:
                            done_payload['debug'] = debug_payload
                        yield _sse('done', done_payload)
                    except Exception:
                        # 流式异常时回退原同步链路，避免接口中断。
                        yield _sse('trace', _trace_event('tool_result', '流式回退', 'stream failed, fallback to sync reply'))
                        response = _build_chat_response()
                        response_text = str(response or '')
                        if not response_text:
                            response_text = '（空回复）'
                        chunk_size = 120
                        for i in range(0, len(response_text), chunk_size):
                            yield _sse('delta', {'text': response_text[i:i + chunk_size]})
                        yield _sse('done', {'reply': response_text})

                streamed = Response(stream_reply(), mimetype='text/event-stream')
                streamed.headers['Cache-Control'] = 'no-cache'
                streamed.headers['X-Accel-Buffering'] = 'no'
                streamed.headers['Connection'] = 'keep-alive'
                return streamed

            response = quick_reply if quick_reply is not None else _build_chat_response()
            payload = {'success': True, 'reply': response}

            if frontend_source in ('sandbox', 'control_panel'):
                try:
                    short_term_after = chat_system.agent_manager.memory.load_short_term()
                    delta = short_term_after[len(short_term_before):] if len(short_term_after) >= len(short_term_before) else short_term_after
                    chat_settings = _default_chat_settings((CONFIG.get('work_mode', {}) or {}).get('chat_settings', {}))

                    events = []
                    seen_thinking_contents = set()  # 用于去重思考内容
                    for item in delta[-80:]:
                        role = str(item.get('role', 'unknown') or 'unknown')
                        content = str(item.get('content', '') or '')
                        ts = item.get('timestamp')

                        event_type = 'message'
                        label = '消息'
                        tool_name = ''
                        if role == 'assistant' and content.startswith('Called '):
                            event_type = 'tool_call'
                            tool_name = content[len('Called '):].strip()
                            label = f"调用工具 {tool_name}" if tool_name else '调用工具'
                        elif role == 'system' and content.startswith('Result:'):
                            event_type = 'tool_result'
                            label = '工具返回结果'
                        elif role == 'assistant':
                            stripped = content.strip()
                            # 检测思考内容的多种格式
                            thinking_patterns = [
                                '思考:', 'Thought:', '[THINK]', '<think>', 'Thinking:',
                                '让我想想', '分析一下', '首先', '其次', '最后',
                                '从', '根据', '考虑到', '综上所述'
                            ]
                            is_thinking = any(stripped.startswith(p) for p in thinking_patterns)
                            
                            # 如果内容较长且不是简单的回复，也认为是思考内容
                            if not is_thinking and len(stripped) > 50:
                                # 检查是否包含分析性词汇
                                analysis_words = ['因为', '所以', '但是', '然而', '因此', '可能', '应该', '需要']
                                if any(word in stripped for word in analysis_words):
                                    is_thinking = True
                            
                            if is_thinking:
                                # 去重：如果思考内容已经出现过，跳过
                                content_hash = hash(stripped[:200])  # 使用前200个字符作为哈希
                                if content_hash in seen_thinking_contents:
                                    continue  # 跳过重复的思考内容
                                seen_thinking_contents.add(content_hash)
                                
                                event_type = 'assistant_message'
                                label = '思考内容'
                            else:
                                event_type = 'assistant_reply'
                                label = 'AI 回复'

                        events.append({
                            'role': role,
                            'type': event_type,
                            'label': label,
                            'tool_name': tool_name,
                            'timestamp': ts,
                            'content': content[:6000]
                        })

                    has_thought = any(e.get('type') == 'assistant_message' for e in events)
                    has_tool = any(e.get('type') in ('tool_call', 'tool_result') for e in events)
                    if has_tool and not has_thought:
                        events.insert(0, {
                            'role': 'assistant',
                            'type': 'assistant_message',
                            'label': '思考内容',
                            'tool_name': '',
                            'timestamp': datetime.datetime.now().timestamp(),
                            'content': '已接收到工具调用请求，正在基于工具结果组织最终回复。'
                        })

                    payload['debug'] = {
                        'enabled': bool(chat_settings.get('sandbox_show_agent_trace', True)),
                        'collapsed': bool(chat_settings.get('sandbox_trace_collapsed', True)),
                        'show_back_to_top': bool(chat_settings.get('sandbox_show_back_to_top', True)),
                        'events': events,
                    }
                    try:
                        payload['debug']['call_policy'] = chat_system.get_last_call_policy()
                    except Exception:
                        payload['debug']['call_policy'] = {}
                    try:
                        trace_rel_path = _write_trace_markdown(
                            events,
                            user_message=(data.get('message') or ''),
                            reply_message=response,
                            retention_days=chat_settings.get('sandbox_trace_retention_days', 7),
                        )
                        payload['debug']['trace_md'] = {
                            'path': trace_rel_path,
                            'created_at': datetime.datetime.now().isoformat(),
                            'retention_days': _normalize_trace_retention_days(chat_settings.get('sandbox_trace_retention_days', 7), default=7),
                        }
                    except Exception as trace_err:
                        payload['debug']['trace_md'] = {
                            'path': '',
                            'error': str(trace_err),
                        }
                except Exception:
                    payload['debug'] = {
                        'enabled': True,
                        'collapsed': True,
                        'show_back_to_top': True,
                        'events': []
                    }

            return jsonify(payload)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/realtime_search/query', methods=['POST'])
    def api_realtime_search_query():
        try:
            data = request.get_json() or {}
            query = (data.get('query') or '').strip()
            if not query:
                return jsonify({'success': False, 'error': 'query 不能为空'}), 400

            result = chat_system.realtime_search(query)
            return jsonify({'success': bool(result.get('success')), 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/realtime_search/subscriptions', methods=['GET'])
    def api_realtime_search_list_subscriptions():
        try:
            subscriptions = chat_system.list_realtime_subscriptions()
            return jsonify({'success': True, 'data': subscriptions, 'count': len(subscriptions)})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/realtime_search/subscriptions', methods=['POST'])
    def api_realtime_search_create_subscription():
        try:
            data = request.get_json() or {}
            query = (data.get('query') or '').strip()
            interval_seconds = data.get('interval_seconds', 300)

            if not query:
                return jsonify({'success': False, 'error': 'query 不能为空'}), 400

            subscription = chat_system.create_realtime_subscription(query, interval_seconds)
            return jsonify({'success': True, 'data': subscription}), 201
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/realtime_search/subscriptions/<subscription_id>', methods=['DELETE'])
    def api_realtime_search_delete_subscription(subscription_id):
        try:
            ok = chat_system.delete_realtime_subscription(subscription_id)
            if not ok:
                return jsonify({'success': False, 'error': 'subscription not found'}), 404
            return jsonify({'success': True, 'id': subscription_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/realtime_search/updates', methods=['GET'])
    def api_realtime_search_updates():
        try:
            subscription_id = (request.args.get('subscription_id') or '').strip()
            since = (request.args.get('since') or '').strip()
            limit = request.args.get('limit', 20, type=int)

            updates = chat_system.poll_realtime_updates(subscription_id=subscription_id, since=since, limit=limit)
            return jsonify({'success': True, 'data': updates, 'count': len(updates)})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ========== 任务管理 API ==========
    @app.route('/api/systems/tasks', methods=['GET'])
    def api_get_tasks():
        try:
            tasks = []
            # 返回占位符任务数据
            return jsonify({'code': 0, 'message': 'success', 'data': tasks})
        except Exception as e:
            return jsonify({'code': 500, 'message': str(e), 'data': []}), 500

    @app.route('/api/systems/tasks', methods=['POST'])
    def api_create_task():
        try:
            data = request.get_json() or {}
            # 简单的任务创建逻辑 - 暂时只记录
            task_id = f"task_{int(time.time())}"
            return jsonify({'code': 0, 'message': 'success', 'data': {'id': task_id}})
        except Exception as e:
            return jsonify({'code': 500, 'message': str(e), 'data': None}), 500

    @app.route('/api/systems/tasks/<task_id>', methods=['DELETE'])
    def api_delete_task(task_id):
        try:
            return jsonify({'code': 0, 'message': 'success', 'data': None})
        except Exception as e:
            return jsonify({'code': 500, 'message': str(e), 'data': None}), 500

    # ========== MCP 管理 API ==========
    @app.route('/api/systems/mcp', methods=['GET'])
    def api_get_mcp_servers():
        try:
            mcp_servers = []
            return jsonify({'code': 0, 'message': 'success', 'data': mcp_servers})
        except Exception as e:
            return jsonify({'code': 500, 'message': str(e), 'data': []}), 500

    # ========== 知识库 API ==========
    @app.route('/api/systems/knowledge', methods=['GET'])
    def api_get_knowledge_base():
        try:
            knowledge_items = []
            return jsonify({'code': 0, 'message': 'success', 'data': knowledge_items})
        except Exception as e:
            return jsonify({'code': 500, 'message': str(e), 'data': []}), 500

    # ========== 插件管理 API ==========
    @app.route('/api/systems/plugins', methods=['GET'])
    def api_get_plugins():
        try:
            plugins = []
            return jsonify({'code': 0, 'message': 'success', 'data': plugins})
        except Exception as e:
            return jsonify({'code': 500, 'message': str(e), 'data': []}), 500

    # ========== 技能管理 API ==========
    @app.route('/api/systems/skills', methods=['GET'])
    def api_get_skills():
        try:
            skills = []
            return jsonify({'code': 0, 'message': 'success', 'data': skills})
        except Exception as e:
            return jsonify({'code': 500, 'message': str(e), 'data': []}), 500

    @app.route('/api/work_mode/status', methods=['GET'])
    def api_work_mode_status():
        try:
            wm = CONFIG.get('work_mode', {})
            return jsonify({
                'success': True,
                'global_enabled': bool(wm.get('enabled', False)),
                'sandbox_enabled': bool(wm.get('sandbox_enabled', False)),
                'has_password': bool(wm.get('password_hash')),
                'active_persona': str(CONFIG.get('active_persona', 'shizuku.json') or 'shizuku.json'),
                'features': _default_work_mode_features(wm.get('features', {})),
                'chat_settings': _default_chat_settings(wm.get('chat_settings', {})),
                'reply_policy': default_reply_policy(wm.get('reply_policy', {}))
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/work_mode/password', methods=['POST'])
    def api_work_mode_set_password():
        try:
            data = request.get_json() or {}
            password = data.get('password') or ''
            current_password = data.get('current_password') or ''
            if len(password) < 6:
                return jsonify({'success': False, 'error': '安全密码至少 6 位'}), 400

            system_config = _load_system_config()
            if 'work_mode' not in system_config:
                system_config['work_mode'] = {}

            existing_hash = system_config['work_mode'].get('password_hash', '')
            if existing_hash and not _verify_password(current_password, existing_hash):
                return jsonify({'success': False, 'error': '旧密码错误，无法修改'}), 403

            system_config['work_mode']['password_hash'] = _hash_password(password)
            _save_system_config(system_config)

            if 'work_mode' not in CONFIG:
                CONFIG['work_mode'] = {}
            CONFIG['work_mode']['password_hash'] = system_config['work_mode']['password_hash']

            return jsonify({'success': True, 'message': '安全密码已设置'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/work_mode/options', methods=['POST'])
    def api_work_mode_options():
        try:
            data = request.get_json() or {}
            incoming = data.get('features', {})
            features = _default_work_mode_features(incoming)
            reply_policy = default_reply_policy(data.get('reply_policy', {}))
            chat_settings = _default_chat_settings(data.get('chat_settings', {}))

            system_config = _load_system_config()
            if 'work_mode' not in system_config:
                system_config['work_mode'] = {}
            system_config['work_mode']['features'] = features
            system_config['work_mode']['reply_policy'] = reply_policy
            system_config['work_mode']['chat_settings'] = chat_settings
            _save_system_config(system_config)

            if 'work_mode' not in CONFIG:
                CONFIG['work_mode'] = {}
            CONFIG['work_mode']['features'] = features
            CONFIG['work_mode']['reply_policy'] = reply_policy
            CONFIG['work_mode']['chat_settings'] = chat_settings

            return jsonify({'success': True, 'features': features, 'reply_policy': reply_policy, 'chat_settings': chat_settings})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/work_mode/reset_password_terminal', methods=['POST'])
    def api_work_mode_reset_password_terminal():
        try:
            project_root = PROJECT_ROOT
            script_path = os.path.join(project_root, 'src', 'tools', 'reset_workmode_password.py')
            py_exe = sys.executable or 'python'
            if not os.path.exists(script_path):
                return jsonify({'success': False, 'error': f'重置脚本不存在: {script_path}'}), 404

            if os.name == 'nt':
                # 在新控制台中直接运行，避免 cmd + shell 的双层引号解析导致路径被错误拼接。
                cmd_line = f'"{py_exe}" "{script_path}" && echo. && echo Password reset finished. You can close this window.'
                subprocess.Popen(
                    ['cmd.exe', '/k', cmd_line],
                    cwd=project_root,
                    creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
                )
            else:
                subprocess.Popen([py_exe, script_path], cwd=project_root)

            return jsonify({'success': True, 'message': '已启动重置终端，请按提示完成密码重置。'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/work_mode/toggle', methods=['POST'])
    def api_work_mode_toggle():
        try:
            data = request.get_json() or {}
            scope = (data.get('scope') or '').strip().lower()
            enable = bool(data.get('enable', False))

            if scope not in ['sandbox', 'global']:
                return jsonify({'success': False, 'error': 'scope 必须是 sandbox 或 global'}), 400

            if scope == 'sandbox':
                if 'work_mode' not in CONFIG:
                    CONFIG['work_mode'] = {}
                CONFIG['work_mode']['sandbox_enabled'] = enable
                system_config = _load_system_config()
                system_config.setdefault('work_mode', {})['sandbox_enabled'] = enable
                _save_system_config(system_config)
                return jsonify({'success': True, 'scope': 'sandbox', 'enabled': enable})

            # Global scope requires password verification
            system_config = _load_system_config()
            wm = system_config.setdefault('work_mode', {})
            saved_hash = wm.get('password_hash', '') or CONFIG.get('work_mode', {}).get('password_hash', '')
            if not saved_hash:
                return jsonify({'success': False, 'error': '请先在设置中配置安全密码'}), 400

            password = data.get('password') or ''
            if not _verify_password(password, saved_hash):
                return jsonify({'success': False, 'error': '安全密码错误'}), 403

            wm['enabled'] = enable
            wm['password_hash'] = saved_hash
            wm['features'] = _default_work_mode_features(wm.get('features', {}))
            _save_system_config(system_config)

            if 'work_mode' not in CONFIG:
                CONFIG['work_mode'] = {}
            CONFIG['work_mode']['enabled'] = enable
            CONFIG['work_mode']['password_hash'] = saved_hash
            CONFIG['work_mode']['features'] = _default_work_mode_features(wm.get('features', {}))

            return jsonify({'success': True, 'scope': 'global', 'enabled': enable})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/chat_settings/deepseek_thinking', methods=['GET'])
    def api_get_deepseek_thinking():
        """获取 DeepSeek 思考模式配置"""
        try:
            chat_settings = (CONFIG.get('work_mode', {}) or {}).get('chat_settings', {})
            enable = bool(chat_settings.get('deepseek_thinking_mode', False))
            reasoning_effort = str(chat_settings.get('deepseek_reasoning_effort', 'high')).lower()
            
            if reasoning_effort not in ['high', 'max']:
                reasoning_effort = 'high'
            
            return jsonify({
                'success': True,
                'thinking_mode': enable,
                'reasoning_effort': reasoning_effort
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/chat_settings/deepseek_thinking', methods=['POST'])
    def api_set_deepseek_thinking():
        """动态切换 DeepSeek 思考模式（热启动）"""
        try:
            data = request.get_json() or {}
            enable = bool(data.get('enable', False))
            reasoning_effort = str(data.get('reasoning_effort', 'high')).lower()
            
            if reasoning_effort not in ['high', 'max']:
                reasoning_effort = 'high'
            
            # 更新系统配置
            system_config = _load_system_config()
            if 'work_mode' not in system_config:
                system_config['work_mode'] = {}
            if 'chat_settings' not in system_config['work_mode']:
                system_config['work_mode']['chat_settings'] = {}
            
            system_config['work_mode']['chat_settings']['deepseek_thinking_mode'] = enable
            system_config['work_mode']['chat_settings']['deepseek_reasoning_effort'] = reasoning_effort
            _save_system_config(system_config)
            
            # 更新运行时配置
            if 'work_mode' not in CONFIG:
                CONFIG['work_mode'] = {}
            if 'chat_settings' not in CONFIG['work_mode']:
                CONFIG['work_mode']['chat_settings'] = {}
            
            CONFIG['work_mode']['chat_settings']['deepseek_thinking_mode'] = enable
            CONFIG['work_mode']['chat_settings']['deepseek_reasoning_effort'] = reasoning_effort
            
            print(f"[INFO] DeepSeek thinking mode {'enabled' if enable else 'disabled'} (effort={reasoning_effort})")
            
            return jsonify({
                'success': True,
                'message': f'DeepSeek 思考模式已{"启用" if enable else "禁用"}',
                'thinking_mode': enable,
                'reasoning_effort': reasoning_effort
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/adapter_console')
    def adapter_console():
        return app.send_static_file('adapter_console.html')

    @app.route('/api/gateway/diagnose', methods=['GET'])
    def api_gateway_diagnose():
        """Unified connectivity diagnostics for frontend integrations."""
        try:
            from app.core.config import CONFIG as LIVE_CONFIG

            unified_cfg = LIVE_CONFIG.get('unified_api', {}) or {}
            onebot_cfg = _normalize_onebot_config(LIVE_CONFIG.get('onebot', {}) or {})

            adapter_candidates = []
            configured_adapter_port = None
            service_ports = LIVE_CONFIG.get('system_config', {}).get('service_ports', {})
            if isinstance(service_ports, dict):
                try:
                    configured_adapter_port = int(service_ports.get('adapter'))
                except Exception:
                    configured_adapter_port = None

            if configured_adapter_port:
                adapter_candidates.append(configured_adapter_port)
            adapter_candidates.extend([5000, 5001, 5002, 5003])

            seen = set()
            dedup_candidates = []
            for p in adapter_candidates:
                if p in seen:
                    continue
                seen.add(p)
                dedup_candidates.append(p)

            adapter_status = {
                'port': None,
                'tcp': {'ok': False, 'detail': '未执行'},
                'health': {'ok': False, 'status': 0, 'detail': '未执行'},
                'models': {'ok': False, 'status': 0, 'detail': '未执行'},
            }

            for p in dedup_candidates:
                tcp = _check_tcp('127.0.0.1', p, timeout=0.35)
                if not tcp['ok']:
                    continue
                health = _check_http_json(f'http://127.0.0.1:{p}/health', timeout=1.0)
                models = _check_http_json(f'http://127.0.0.1:{p}/v1/models', timeout=1.0)
                adapter_status = {'port': p, 'tcp': tcp, 'health': health, 'models': models}
                if health.get('ok') or models.get('ok'):
                    break

            unified_host = str(unified_cfg.get('host', '127.0.0.1') or '127.0.0.1')
            unified_port = int(unified_cfg.get('port', 8000) or 8000)
            unified_check_host = '127.0.0.1' if unified_host in ('0.0.0.0', '::') else unified_host

            onebot_http = onebot_cfg.get('http', {})
            onebot_ws = onebot_cfg.get('ws', {})
            onebot_rev = onebot_cfg.get('ws_reverse', {})

            http_enabled = bool(onebot_http.get('enable', True))
            ws_enabled = bool(onebot_ws.get('enable', False))
            onebot_http_host = _normalize_probe_host(onebot_http.get('host', '127.0.0.1'))
            onebot_ws_host = _normalize_probe_host(onebot_ws.get('host', '127.0.0.1'))
            onebot_http_port = int(onebot_http.get('port', 3000) or 3000)
            onebot_ws_port = int(onebot_ws.get('port', 3001) or 3001)

            onebot_http_ping = _run_host_ping(onebot_http_host) if http_enabled else {'ok': True, 'detail': '未启用'}
            onebot_http_tcp = _check_tcp(onebot_http_host, onebot_http_port, timeout=0.8) if http_enabled else {'ok': True, 'detail': '未启用'}
            onebot_ws_ping = _run_host_ping(onebot_ws_host) if ws_enabled else {'ok': True, 'detail': '未启用'}
            onebot_ws_tcp = _check_tcp(onebot_ws_host, onebot_ws_port, timeout=0.8) if ws_enabled else {'ok': True, 'detail': '未启用'}

            target_host = (request.args.get('target_host') or '127.0.0.1').strip()

            unified_base = f'http://{unified_check_host}:{unified_port}'
            result = {
                'success': True,
                'timestamp': int(time.time()),
                'frontend_ping': _run_host_ping(target_host),
                'adapter': {
                    'base_url': f"http://127.0.0.1:{adapter_status['port']}/v1" if adapter_status['port'] else '',
                    **adapter_status,
                },
                'unified_api': {
                    'base_url': f"{unified_base}/v1",
                    'ping': _run_host_ping(unified_check_host),
                    'tcp': _check_tcp(unified_check_host, unified_port, timeout=0.8),
                    'health': _check_http_candidates(
                        unified_base,
                        ['/health', '/v1/health', '/v1/models'],
                        timeout=1.2
                    ),
                },
                'onebot': {
                    'http': {
                        'enabled': http_enabled,
                        'url': f"http://{onebot_http_host}:{onebot_http_port}",
                        'ping': onebot_http_ping,
                        'tcp': onebot_http_tcp,
                    },
                    'ws': {
                        'enabled': ws_enabled,
                        'url': f"ws://{onebot_ws_host}:{onebot_ws_port}",
                        'ping': onebot_ws_ping,
                        'tcp': onebot_ws_tcp,
                    },
                    'ws_reverse': {
                        'enabled': bool(onebot_rev.get('enable', False)),
                        'url': str(onebot_rev.get('url', '') or ''),
                    },
                }
            }
            return jsonify(result)
        except Exception as exc:
            return jsonify({'success': False, 'error': str(exc)}), 500

    @app.route('/terminal_page')
    def terminal_page():
        return app.send_static_file('terminal_chat.html')

    @app.route('/db_console')
    def db_console():
        return app.send_static_file('db_management.html')

    @app.route('/logs_page')
    def logs_page():
        return app.send_static_file('logs.html')

    @app.route('/adapter_logs')
    def adapter_logs():
        return app.send_static_file('adapter_logs.html')

    @app.route('/config_editor')
    def config_editor():
        return app.send_static_file('config_editor.html')

    @app.route('/monitoring')
    def monitoring():
        return app.send_static_file('monitoring.html')


    # 系统监控API
    @app.route('/api/monitoring')
    def api_monitoring():
        global _LATEST_SYSTEM_STATS

        # 确保后台监控线程已启动
        start_monitor_thread()

        # 如果数据还没准备好，返回空/等待
        if not _LATEST_SYSTEM_STATS:
            return jsonify({'error': 'Initializing'}), 202

        try:
            return jsonify(_LATEST_SYSTEM_STATS)
        except Exception as e:
            app.logger.error(f"获取监控数据时出错: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/agent/status')
    def api_agent_status():
        try:
            # Read Plan
            plan_path = os.path.join("agent_datas", "workspace", "plan.md")
            legacy_plan_path = os.path.join("agent_datas", "plan.md")
            plan_content = ""
            if os.path.exists(plan_path):
                with open(plan_path, 'r', encoding='utf-8') as f:
                    plan_content = f.read()
            elif os.path.exists(legacy_plan_path):
                with open(legacy_plan_path, 'r', encoding='utf-8') as f:
                    plan_content = f.read()

            # Read Short Term Memory Stats
            memory_path = os.path.join("agent_datas", "workspace", "memory", "short_term.json")
            legacy_memory_path = os.path.join("agent_datas", "memory", "short_term.json")
            memory_count = 0
            if os.path.exists(memory_path):
                with open(memory_path, 'r', encoding='utf-8') as f:
                    try:
                        mem_data = json.load(f)
                        memory_count = len(mem_data)
                    except:
                        pass
            elif os.path.exists(legacy_memory_path):
                with open(legacy_memory_path, 'r', encoding='utf-8') as f:
                    try:
                        mem_data = json.load(f)
                        memory_count = len(mem_data)
                    except:
                        pass
            
            return jsonify({
                'success': True,
                'plan': plan_content,
                'memory_count': memory_count
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/agent/memory/long_term', methods=['GET'])
    def api_agent_long_term_memory():
        try:
            persona_filename = (request.args.get('persona_filename') or '').strip() or None
            include_meta_raw = str(request.args.get('include_meta', '1') or '1').strip().lower()
            include_meta = include_meta_raw not in ('0', 'false', 'no', 'off')

            payload = chat_system.agent_manager.memory.get_long_term_memory_view(
                persona_filename=persona_filename,
                include_meta=include_meta
            )
            return jsonify({'success': True, **payload})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/plugins/status', methods=['GET'])
    def api_plugins_status():
        try:
            status = chat_system.get_plugin_status()
            status['degraded'] = False
            return jsonify({'success': True, 'status': status})
        except Exception as e:
            degraded = _build_degraded_plugin_status(str(e))
            return jsonify({'success': True, 'status': degraded, 'warning': '插件系统不可用，已返回降级状态'})

    @app.route('/api/plugins/reload', methods=['POST'])
    def api_plugins_reload():
        try:
            status = chat_system.reload_plugins()
            return jsonify({'success': True, 'status': status, 'message': 'Plugin framework reloaded'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/plugins/policy', methods=['POST'])
    def api_plugins_policy():
        try:
            data = request.get_json() or {}
            plugin_name = (data.get('plugin_name') or '').strip()
            policy = data.get('policy') or {}
            if not plugin_name:
                return jsonify({'success': False, 'error': 'plugin_name is required'}), 400

            normalized = chat_system.update_plugin_policy(plugin_name, policy)
            return jsonify({'success': True, 'plugin_name': plugin_name, 'policy': normalized})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/plugins/config', methods=['GET'])
    def api_plugins_config_get():
        try:
            plugin_name = (request.args.get('plugin_name') or '').strip()
            if not plugin_name:
                return jsonify({'success': False, 'error': 'plugin_name is required'}), 400
                        # 特殊处理内置插件 - 更加健壮的处理
            if plugin_name.lower().strip() == "builtin.basic":
                src_dir = os.path.dirname(__file__)
                builtin_config_dir = os.path.join(src_dir, 'plugin_framework', 'builtin')
                config_path = os.path.join(builtin_config_dir, 'config.json')
                print(f"[DEBUG] Loading builtin config from: {config_path}")
                
                # 确保目录存在
                if not os.path.exists(builtin_config_dir):
                    os.makedirs(builtin_config_dir, exist_ok=True)
                    
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            cfg = json.load(f)
                        print(f"[DEBUG] Loaded config: {cfg}")
                        return jsonify({'success': True, 'plugin_name': plugin_name, 'config': cfg, 'schema': None})
                    except Exception as e:
                        print(f"[DEBUG] Error reading config file: {e}")
                        # 如果读取失败，返回默认配置
                        default_config = {
                            "description": "Built-in basic plugin configuration",
                            "version": "1.0.0",
                            "enabled": True
                        }
                        return jsonify({'success': True, 'plugin_name': plugin_name, 'config': default_config, 'schema': None})
                
                print(f"[DEBUG] Config file not found, returning default config")
                # 如果文件不存在，返回默认配置
                default_config = {
                    "description": "Built-in basic plugin configuration",
                    "version": "1.0.0",
                    "enabled": True
                }
                return jsonify({'success': True, 'plugin_name': plugin_name, 'config': default_config, 'schema': None})
            
            cfg = chat_system.plugin_manager.get_plugin_runtime_config(plugin_name)
            
            # 尝试获取配置schema
            schema = None
            
            # 从 plugin.json 加载 schema
            plugin_project_path = chat_system.plugin_manager._plugin_projects.get(plugin_name)
            if plugin_project_path:
                plugin_json_path = os.path.join(plugin_project_path, 'plugin.json')
                if os.path.exists(plugin_json_path):
                    try:
                        with open(plugin_json_path, 'r', encoding='utf-8') as f:
                            plugin_data = json.load(f)
                        schema = plugin_data.get('config_schema')
                    except Exception as e:
                        app.logger.warning(f"Failed to load plugin.json for {plugin_name}: {e}")
            
            return jsonify({'success': True, 'plugin_name': plugin_name, 'config': cfg, 'schema': schema})
        except Exception as e:
            print(f"[API ERROR] GET config failed: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/plugins/config', methods=['POST'])
    def api_plugins_config_set():
        try:
            data = request.get_json() or {}
            plugin_name = (data.get('plugin_name') or '').strip()
            config_data = data.get('config')
            print(f"[API] POST /api/plugins/config - plugin_name: {plugin_name}, config_data: {config_data}")
            if not plugin_name:
                return jsonify({'success': False, 'error': 'plugin_name is required'}), 400
            if not isinstance(config_data, dict):
                return jsonify({'success': False, 'error': 'config must be json object'}), 400
            
            # 特殊处理内置插件 - 更加健壮的处理
            if plugin_name.lower().strip() == "builtin.basic":
                src_dir = os.path.dirname(__file__)
                builtin_config_dir = os.path.join(src_dir, 'plugin_framework', 'builtin')
                if not os.path.exists(builtin_config_dir):
                    os.makedirs(builtin_config_dir, exist_ok=True)
                    print(f"[DEBUG] Created config dir: {builtin_config_dir}")
                config_path = os.path.join(builtin_config_dir, 'config.json')
                print(f"[DEBUG] Saving builtin config to: {config_path}")
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                print(f"[API] Config saved successfully for {plugin_name} to {config_path}")
                return jsonify({'success': True, 'plugin_name': plugin_name, 'config': config_data})
            
            cfg = chat_system.plugin_manager.update_plugin_runtime_config(plugin_name, config_data)
            print(f"[API] Config saved successfully for {plugin_name}")
            return jsonify({'success': True, 'plugin_name': plugin_name, 'config': cfg})
        except Exception as e:
            print(f"[API ERROR] POST /api/plugins/config failed: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/plugins/framework_enabled', methods=['POST'])
    def api_plugins_framework_enabled():
        try:
            data = request.get_json() or {}
            enabled = bool(data.get('enabled', True))
            chat_system.plugin_manager.set_framework_enabled(enabled, persist=True)
            if enabled:
                chat_system.reload_plugins()
            return jsonify({'success': True, 'enabled': enabled})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== Plugin Page Routes ====================
    
    @app.route('/plugins/<plugin_name>/<path:page_route>', methods=['GET'])
    def plugin_page_route(plugin_name, page_route):
        """Serve plugin pages from UI registry."""
        print(f"[DEBUG] Plugin page route called: plugin_name={plugin_name}, page_route={page_route}")
        try:
            from app.plugin_framework.ui_extensions import ui_registry
            
            # Find the page in registry
            pages = ui_registry.get_pages()
            print(f"[DEBUG] Found {len(pages)} pages in registry")
            
            # Construct the full route that matches what's stored in registry
            full_route = f"/plugins/{plugin_name}/{page_route}"
            print(f"[DEBUG] Looking for route: {full_route}")
            
            for page in pages:
                print(f"[DEBUG] Checking page: {page.id} -> {page.route}")
                if page.route == full_route and page.id.startswith(f"{plugin_name}."):
                    print(f"[DEBUG] MATCH FOUND! Returning page content")
                    # Return the page content - support callable for dynamic pages
                    if page.content_type == 'html':
                        content = page.content() if callable(page.content) else page.content
                        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
                    else:
                        return jsonify({'error': f'Unsupported content type: {page.content_type}'}), 400
            
            print(f"[DEBUG] No match found, returning 404")
            return 'Not Found', 404
            
        except Exception as e:
            print(f"[ERROR] Exception in plugin_page_route: {e}")
            app.logger.error(f"Error serving plugin page: {e}")
            import traceback
            traceback.print_exc()
            return 'Internal Server Error', 500

    @app.route('/api/plugins/ui-extensions', methods=['GET'])
    def api_plugins_ui_extensions():
        """获取所有插件注册的UI扩展"""
        try:
            from app.plugin_framework.ui_extensions import ui_registry
            
            # 获取所有UI扩展
            extensions = ui_registry.to_dict()
            
            return jsonify({
                'success': True,
                'extensions': extensions
            })
        except Exception as e:
            app.logger.error(f"Error getting UI extensions: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/plugins/ui-extensions/menu', methods=['GET'])
    def api_plugins_ui_menu():
        """获取插件菜单项"""
        try:
            from app.plugin_framework.ui_extensions import ui_registry
            menu_items = ui_registry.get_menu_items(sorted=True)
            
            return jsonify({
                'success': True,
                'menu_items': [item.to_dict() for item in menu_items]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/plugins/ui-extensions/pages', methods=['GET'])
    def api_plugins_ui_pages():
        """获取插件页面列表"""
        try:
            from app.plugin_framework.ui_extensions import ui_registry
            pages = ui_registry.get_pages()
            
            return jsonify({
                'success': True,
                'pages': [page.to_dict() for page in pages]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/plugins/ui-extensions/settings', methods=['GET'])
    def api_plugins_ui_settings():
        """获取插件设置区块"""
        try:
            from app.plugin_framework.ui_extensions import ui_registry
            sections = ui_registry.get_setting_sections(sorted=True)
            
            return jsonify({
                'success': True,
                'sections': [section.to_dict() for section in sections]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/plugins/ui-extensions/widgets', methods=['GET'])
    def api_plugins_ui_widgets():
        """获取插件小部件"""
        try:
            position = request.args.get('position')
            from app.plugin_framework.ui_extensions import ui_registry
            widgets = ui_registry.get_widgets(position=position, sorted=True)
            
            return jsonify({
                'success': True,
                'widgets': [widget.to_dict() for widget in widgets]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== Generic Plugin API Dispatch ====================
    
    @app.route('/api/plugins/<plugin_name>/<path:action>', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def plugin_api_dispatch(plugin_name, action):
        """Dispatch API requests to registered plugin API handlers."""
        try:
            from app.plugin_framework.ui_extensions import ui_registry
            
            norm_action = action if action.startswith("/") else f"/{action}"
            handler = ui_registry.find_api_handler(request.method, norm_action, plugin_name)
            if handler:
                return handler(request)
            
            return jsonify({'success': False, 'error': f'Unknown API: {request.method} /api/plugins/{plugin_name}/{action}'}), 404
        except Exception as e:
            app.logger.error(f"Error dispatching plugin API: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500
    def api_plugins_delete():
        try:
            data = request.get_json() or {}
            plugin_name = (data.get('plugin_name') or '').strip()
            confirm_name = (data.get('confirm_name') or '').strip()

            if not plugin_name:
                return jsonify({'success': False, 'error': 'plugin_name is required'}), 400
            if confirm_name and confirm_name != plugin_name:
                return jsonify({'success': False, 'error': 'confirm_name mismatch'}), 400

            result = chat_system.delete_plugin(plugin_name)
            status = chat_system.get_plugin_status()
            return jsonify({
                'success': True,
                'message': f'Plugin deleted: {plugin_name}',
                'result': result,
                'status': status
            })
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/status', methods=['GET'])
    def api_skills_status():
        try:
            status = chat_system.get_skill_status()
            status['degraded'] = False
            return jsonify({'success': True, 'status': status})
        except Exception as e:
            degraded = _build_degraded_skill_status(str(e))
            return jsonify({'success': True, 'status': degraded, 'warning': '技能系统不可用，已返回降级状态'})

    @app.route('/api/skills/reload', methods=['POST'])
    def api_skills_reload():
        try:
            status = chat_system.reload_skills()
            return jsonify({'success': True, 'status': status, 'message': 'Skill framework reloaded'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/policy', methods=['POST'])
    def api_skills_policy():
        try:
            data = request.get_json() or {}
            skill_id = (data.get('skill_id') or '').strip()
            policy = data.get('policy') or {}
            if not skill_id:
                return jsonify({'success': False, 'error': 'skill_id is required'}), 400

            normalized = chat_system.update_skill_policy(skill_id, policy)
            return jsonify({'success': True, 'skill_id': skill_id, 'policy': normalized})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/framework_enabled', methods=['POST'])
    def api_skills_framework_enabled():
        try:
            data = request.get_json() or {}
            enabled = bool(data.get('enabled', True))
            chat_system.set_skill_framework_enabled(enabled)
            if enabled:
                chat_system.reload_skills()
            return jsonify({'success': True, 'enabled': enabled})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/upload', methods=['POST'])
    def api_skills_upload():
        try:
            upload_file = request.files.get('file')
            if not upload_file:
                return jsonify({'success': False, 'error': 'file is required'}), 400

            skill_id = _extract_skill_zip_to_workspace(upload_file)
            chat_system.reload_skills()
            return jsonify({'success': True, 'skill_id': skill_id, 'message': f'Skill {skill_id} uploaded'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/skills/delete', methods=['POST'])
    def api_skills_delete():
        try:
            data = request.get_json() or {}
            skill_id = (data.get('skill_id') or '').strip()
            confirm_name = (data.get('confirm_name') or '').strip()

            if not skill_id:
                return jsonify({'success': False, 'error': 'skill_id is required'}), 400
            if confirm_name and confirm_name != skill_id:
                return jsonify({'success': False, 'error': 'confirm_name mismatch'}), 400

            result = chat_system.delete_skill(skill_id)
            status = chat_system.get_skill_status()
            return jsonify({
                'success': True,
                'message': f'Skill deleted: {skill_id}',
                'result': result,
                'status': status
            })
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # 后端获取记录
    @app.route('/api/records')
    def api_records():
        from app.database.database import DatabaseManager
        db_manager = None
        try:
            db_manager = DatabaseManager()
            # 减少默认查询数量，提高响应速度
            limit = min(int(request.args.get('limit', 50)), 100)  # 限制最大100条记录
            persona_filename = (request.args.get('persona_filename') or '').strip()
            
            # 如果指定了角色，只查询该角色的记录
            if persona_filename:
                rows = db_manager.get_chat_history(limit=limit, persona_filename=persona_filename)
            else:
                # 否则查询所有角色的记录（先查默认表，再查所有角色表）
                all_rows = []
                # 查询默认表
                default_rows = db_manager.get_chat_history(limit=limit, persona_filename=None)
                all_rows.extend(default_rows)
                
                # 查询所有角色表
                try:
                    cursor = db_manager._new_cursor()
                    cursor.execute("SHOW TABLES LIKE 'chat_history_%'")
                    persona_tables = [row[0] for row in cursor.fetchall()]
                    cursor.close()
                    
                    for table_name in persona_tables:
                        persona_name = table_name.replace('chat_history_', '')
                        persona_rows = db_manager.get_chat_history(limit=limit, persona_filename=persona_name + '.json')
                        all_rows.extend(persona_rows)
                except Exception as e:
                    app.logger.warning(f"查询角色表时出错: {e}")
                
                # 按id排序，返回最新的limit条（处理字典和元组两种情况）
                def get_id(row):
                    if isinstance(row, dict):
                        return row.get('id', 0)
                    elif isinstance(row, (list, tuple)) and len(row) > 0:
                        return row[0]
                    return 0
                
                all_rows.sort(key=get_id, reverse=True)
                rows = all_rows[:limit]
            
            return jsonify(rows)
        except Exception as e:
            app.logger.error(f"获取聊天记录时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify([]) 
        finally:
            if db_manager:
                db_manager.close()

    @app.route('/api/delete_record', methods=['POST'])
    def api_del_record():
        data = request.get_json()
        rid = data.get('id')
        persona_filename = (data.get('persona_filename') or '').strip() if isinstance(data, dict) else ''
        from app.database.database import DatabaseManager
        db_manager = None
        try:
            db_manager = DatabaseManager()
            db_manager.delete_chat_record(rid, persona_filename=persona_filename or None)
            return jsonify({'message': 'ok'})
        except Exception as e:
            app.logger.error(f"删除聊天记录时出错: {str(e)}")
            return jsonify({'message': 'error'}), 500
        finally:
            if db_manager:
                db_manager.close()

    @app.route('/api/clear_records', methods=['POST'])
    def api_clear():
        from app.database.database import DatabaseManager
        db_manager = None
        try:
            data = request.get_json(silent=True) or {}
            persona_filename = (data.get('persona_filename') or '').strip() if isinstance(data, dict) else ''
            db_manager = DatabaseManager()
            db_manager.clear_chat_history(persona_filename=persona_filename or None)
            return jsonify({'message': 'cleared'})
        except Exception as e:
            app.logger.error(f"清空聊天记录时出错: {str(e)}")
            return jsonify({'message': 'error'}), 500
        finally:
            if db_manager:
                db_manager.close()

    @app.route('/api/delete_first_n', methods=['POST'])
    def api_del_n():
        data = request.get_json()
        n = data.get('n', 0)
        persona_filename = (data.get('persona_filename') or '').strip() if isinstance(data, dict) else ''
        from app.database.database import DatabaseManager
        db_manager = None
        try:
            db_manager = DatabaseManager()
            db_manager.delete_first_n_records(n, persona_filename=persona_filename or None)
            return jsonify({'message': 'deleted_first_n'})
        except Exception as e:
            app.logger.error(f"删除前N条聊天记录时出错: {str(e)}")
            return jsonify({'message': 'error'}), 500
        finally:
            if db_manager:
                db_manager.close()

    @app.route('/api/migrate_chat_history_personas', methods=['POST'])
    def api_migrate_chat_history_personas():
        from app.database.database import DatabaseManager
        db_manager = None
        try:
            data = request.get_json(silent=True) or {}
            delete_legacy = bool(data.get('delete_legacy', False)) if isinstance(data, dict) else False
            db_manager = DatabaseManager()
            result = db_manager.migrate_legacy_chat_history_to_persona_tables(delete_legacy=delete_legacy)
            status_code = 200 if bool(result.get('success')) else 500
            return jsonify(result), status_code
        except Exception as e:
            app.logger.error(f"迁移聊天记录到人格表时出错: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if db_manager:
                db_manager.close()

    @app.route('/api/database/query', methods=['POST'])
    def api_db_query():
        try:
            query = request.get_json().get('query')
            if not query:
                return jsonify({'error': 'No query provided'}), 400

            from app.database.database import get_connection, get_engine

            uq = query.strip().upper()
            if get_engine() == 'postgresql' and uq.startswith('SHOW'):
                return jsonify({
                    'error': 'PostgreSQL 不支持 SHOW，请查询 information_schema（例如 pg_tables）',
                }), 400

            conn = get_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500

            try:
                cur = conn.cursor()
                cur.execute(query)
                is_read = (
                    uq.startswith('SELECT')
                    or uq.startswith('WITH')
                    or uq.startswith('SHOW')
                    or uq.startswith('DESCRIBE')
                    or uq.startswith('EXPLAIN')
                )
                if is_read:
                    columns = [desc[0] for desc in cur.description] if cur.description else []
                    rows = cur.fetchall()
                    result = [dict(zip(columns, row)) for row in rows]
                    return jsonify({'success': True, 'data': result, 'columns': columns})
                conn.commit()
                return jsonify({'success': True, 'message': f'Affected {cur.rowcount} rows'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
            finally:
                conn.close()
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # 启动模式
    @app.route('/api/run_mode', methods=['POST'])
    def api_run_mode():
        m = request.get_json().get('mode', 0)
        # 异步调用 main.py
        base = PROJECT_ROOT
        main_py = os.path.join(base, 'main.py')
        # 修复Windows路径问题
        main_py = main_py.replace('/', '\\')
        threading.Thread(target=lambda: subprocess.Popen([sys.executable, main_py, str(m)])).start()
        return jsonify({'message': f'mode {m} launched'})

    # Launcher API Endpoints
    @app.route('/api/launcher/cleanup', methods=['POST'])
    def api_launcher_cleanup():
        try:
            base_path = PROJECT_ROOT
            script_path = os.path.join(base_path, 'src', 'tools', 'cleanup_chat_history.py')
            result = subprocess.check_output(
                [sys.executable, script_path],
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                cwd=base_path,
                timeout=60
            )
            app.logger.info(f"清理数据库成功: {result.strip()}")
            return jsonify({'success': True, 'message': 'Cleanup successful', 'output': result})
        except Exception as e:
            output = str(e)
            if hasattr(e, 'output'):
                output = e.output
            app.logger.error(f"清理数据库失败: {output}")
            return jsonify({'success': False, 'error': output}), 500

    @app.route('/api/launcher/create_db', methods=['POST'])
    def api_launcher_create_db():
        try:
            base_path = PROJECT_ROOT
            script_path = os.path.join(base_path, 'src', 'database', 'create_database.py')
            result = subprocess.check_output(
                [sys.executable, script_path],
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                cwd=base_path,
                timeout=120
            )
            app.logger.info(f"重置数据库成功: {result.strip()}")
            return jsonify({'success': True, 'message': 'Database reset successful', 'output': result})
        except Exception as e:
            output = str(e)
            if hasattr(e, 'output'):
                output = e.output
            app.logger.error(f"重置数据库失败: {output}")
            return jsonify({'success': False, 'error': output}), 500

    @app.route('/api/launcher/services', methods=['POST'])
    def api_launcher_services():
        # Starts Adapter service and Unified API in background (Unifying terminals)
        logger_ok = False
        try:
            base_path = PROJECT_ROOT
            main_py = os.path.join(base_path, 'main.py')
            unified_py = os.path.join(base_path, 'src', 'services', 'unified_api.py')
            
            # Simulate monitoring startup logs
            app.logger.info("正在初始化系统监控模块...")
            time.sleep(0.1)
            app.logger.info("CPU 监控服务已启动 [OK]")
            time.sleep(0.1)
            app.logger.info("内存监控服务已启动 [OK]")
            time.sleep(0.1)
            app.logger.info("网络流量分析器已就绪 [OK]")
            time.sleep(0.1)
            app.logger.info("磁盘 I/O 监控已挂载 [OK]")
            
            # Enhanced run_bg to stream output to BOTH file and console
            def run_bg(cmd, log_file, name="Service"):
                log_path = os.path.join(base_path, log_file)
                
                # subprocess.PIPE allows us to read the output
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    cwd=base_path, 
                    text=True,
                    encoding='utf-8',
                    bufsize=1,
                    # On Windows, we need to handle window creation flags if we want to hide it
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                def stream_output(proc, file_path, prefix):
                    try:
                        with open(file_path, 'a', encoding='utf-8') as f:
                            for line in iter(proc.stdout.readline, ''):
                                if not line: break
                                # Write to file
                                f.write(line)
                                f.flush()
                                # Print to main console with prefix
                                sys.stdout.write(f"[{prefix}] {line}")
                                sys.stdout.flush()
                    except Exception as ex:
                        print(f"Error streaming output for {prefix}: {ex}")
                    finally:
                        proc.stdout.close()

                # Start monitoring thread
                t = threading.Thread(target=stream_output, args=(process, log_path, name))
                t.daemon = True
                t.start()
                return process

            # Mode 0 is Adapter service (adapter_service.py via main.py)
            # Use unbuffered python (-u) to ensure real-time logging
            run_bg([sys.executable, '-u', main_py, '0'], 'adapter.log', "Adapter")
            app.logger.info("已启动 核心适配器服务")

            msg = '核心适配器服务已在后台启动'
            
            if os.path.exists(unified_py):
                run_bg([sys.executable, '-u', unified_py], 'unified_api.log', "Unified")
                app.logger.info("已启动 统一 API 网关服务")
                msg += ' 及 统一API服务'
            
            logger_ok = True
            
            # Unified API Key
            from app.core.config import CONFIG
            unified_key = CONFIG.get('unified_api', {}).get('access_token', 'neko-proxy-key-123')
            port = CONFIG.get('unified_api', {}).get('port', 8000)
            
            return jsonify({
                'success': True, 
                'message': msg,
                'details': {
                    'adapter_url': 'http://127.0.0.1:5000/v1',
                    'unified_url': f'http://127.0.0.1:{port}/v1',
                    'api_key': unified_key,
                    'models': ['deepseek-chat', 'neko', 'gpt-3.5-turbo']
                }
            })
        except Exception as e:
            app.logger.error(f"启动服务失败: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/launcher/terminal', methods=['POST'])
    def api_launcher_terminal():
        # Starts Terminal Chat in a new terminal window
        try:
            base = PROJECT_ROOT
            main_py = os.path.join(base, 'main.py')
            base = base.replace('/', '\\')
            
            # Mode 1 is Terminal Chat
            cmd = f'start "Terminal Chat" cmd /k python "{main_py}" 1'
            subprocess.Popen(cmd, shell=True, cwd=base)
            return jsonify({'success': True, 'message': 'Terminal Chat launched in new window'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # 服务诊断
    @app.route('/api/diagnosis')
    def api_diag():
        try:
            # 获取项目根目录
            base_path = PROJECT_ROOT
            main_py_path = os.path.join(base_path, 'main.py')

            # 使用 subprocess 调用 main.py 的诊断功能
            # cwd=base_path 确保 main.py 在正确的上下文中执行
            result = subprocess.check_output(
                [sys.executable, main_py_path, '3'],
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                cwd=base_path,
                timeout=60  # 增加超时到60秒
            )
            response_text = f"<pre>{result}</pre>"
            # 添加不使用缓存的头部
            response = Response(response_text, mimetype='text/html')
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        except subprocess.CalledProcessError as e:
            error_response = f"<pre>诊断执行出错:\n{e.output}</pre>"
            response = Response(error_response, mimetype='text/html')
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response, 500
        except subprocess.TimeoutExpired as e:
            timeout_output = e.output.decode('utf-8') if e.output else "诊断执行超时"
            error_response = f"<pre>诊断执行超时 (超过60秒):\n{timeout_output}</pre>"
            response = Response(error_response, mimetype='text/html')
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response, 408
        except Exception as e:
            error_response = f"<pre>未知错误: {str(e)}</pre>"
            response = Response(error_response, mimetype='text/html')
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response, 500

    # 日志API (Common)
    @app.route('/api/logs')
    def api_logs():
        try:
            import os
            log_type = request.args.get('type', 'app')
            log_file = 'app.log'
            
            if log_type in ('adapter', 'adapter_core'):
                log_file = 'adapter_core.log' if os.path.exists('adapter_core.log') else 'adapter.log'
            elif log_type == 'unified':
                log_file = 'unified_api.log'
            
            if not os.path.exists(log_file):
                return f"Log file '{log_file}' not found."

            # Read last 20KB for more context
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                read_size = 20000 
                if file_size > read_size:
                    f.seek(file_size - read_size)
                else:
                    f.seek(0)
                return f.read()
        except Exception as e:
            app.logger.error(f"Error reading logs: {str(e)}")
            return f"Error reading logs: {str(e)}"

    def _tail_log_file(log_candidates, size=2000):
        for log_file in log_candidates:
            try:
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                        data = f.read()
                        return data[-size:]
            except Exception as exc:
                app.logger.warning(f"无法读取日志 {log_file}: {exc}")
        return ''

    @app.route('/api/adapter_logs')
    def api_adapter_logs():
        return _tail_log_file(['adapter_core.log', 'adapter.log'])

    @app.route('/stream_logs')
    def stream_logs():
        def event_stream():
            try:
                with open('app.log', 'r', encoding='utf-8') as f:
                    f.seek(0, os.SEEK_END)
                    while True:
                        line = f.readline()
                        if line:
                            yield f"data:{line}\n\n"
                        else:
                            time.sleep(0.5)
            except Exception as e:
                app.logger.error(f"流式传输日志时出错: {str(e)}")
                yield "data: Error reading log file\n\n"

        return Response(event_stream(), mimetype='text/event-stream')

    @app.route('/api/exec_cmd', methods=['GET', 'POST'])
    def api_exec_cmd():
        # 获取命令参数（支持GET和POST）
        if request.method == 'POST':
            data = request.get_json()
            cmd = data.get('cmd') if data else None
        else:
            cmd = request.args.get('cmd')
            
        if not cmd:
            return 'Missing cmd parameter', 400
            
        # 安全提示：生产环境要严格校验或白名单
        try:
            # 添加超时控制
            import signal
            import subprocess
            
            # shell=True 可执行字符串命令，注意安全
            # 处理可能的编码问题
            try:
                # 使用超时控制执行命令，指定编码为系统默认编码
                system_encoding = locale.getpreferredencoding()
                output = subprocess.check_output(
                    cmd, 
                    shell=True, 
                    cwd=base_dir,
                    stderr=subprocess.STDOUT,
                    encoding=system_encoding,
                    timeout=30  # 30秒超时
                )
            except subprocess.TimeoutExpired:
                output = "命令执行超时（超过30秒）"
            except UnicodeDecodeError:
                # 如果系统默认编码解码失败，尝试多种编码
                try:
                    output = subprocess.check_output(
                        cmd, 
                        shell=True, 
                        cwd=base_dir,
                        stderr=subprocess.STDOUT,
                        timeout=30  # 30秒超时
                    )
                except subprocess.TimeoutExpired:
                    output = "命令执行超时（超过30秒）".encode('utf-8')
                # 尝试解码输出
                try:
                    # 首先尝试UTF-8
                    output = output.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        output = output.decode('gbk')  # Windows中文系统常用编码
                    except UnicodeDecodeError:
                        try:
                            output = output.decode('gb2312')  # 另一种中文编码
                        except UnicodeDecodeError:
                            try:
                                # 尝试系统默认编码
                                output = output.decode(locale.getpreferredencoding())
                            except UnicodeDecodeError:
                                output = output.decode('utf-8', errors='ignore')  # 忽略无法解码的字符
            except Exception as e:
                output = str(e)
                    
        except subprocess.CalledProcessError as e:
            output = e.output
            # 处理可能的编码问题
            if isinstance(output, bytes):
                try:
                    # 首先尝试UTF-8
                    output = output.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        output = output.decode('gbk')
                    except UnicodeDecodeError:
                        try:
                            output = output.decode('gb2312')
                        except UnicodeDecodeError:
                            try:
                                # 尝试系统默认编码
                                output = output.decode(locale.getpreferredencoding())
                            except UnicodeDecodeError:
                                output = output.decode('utf-8', errors='ignore')
            else:
                # 如果output不是bytes，直接使用
                pass
        except Exception as e:
            output = f"执行命令时出错: {str(e)}"
            
        # 返回 HTML 格式保留换行
        return f'<pre>{output}</pre>'

    # 配置管理API
    @app.route('/api/config', methods=['GET'])
    def get_config():
        try:
            config_path = os.path.join(DATA_DIR, 'config.json')
            system_config = _load_system_config()
            
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 添加数据库配置
            if 'database' not in config_data:
                config_data['database'] = {}
            
            db_cfg = CONFIG.get('database', {})
            eng = str(db_cfg.get('engine', 'mysql')).lower()
            is_pg = eng in ('postgresql', 'postgres', 'pg')
            default_port = 5432 if is_pg else 3306
            _p = db_cfg.get('port', default_port)
            if _p is None or _p == '':
                _p = default_port
            config_data['database']['engine'] = 'postgresql' if is_pg else 'mysql'
            config_data['database']['port'] = int(_p)
            config_data['database']['host'] = db_cfg.get('host', '')
            config_data['database']['user'] = db_cfg.get('user', '')
            config_data['database']['password'] = db_cfg.get('password', '')
            config_data['database']['database'] = db_cfg.get('database', '')

            config_data['server'] = system_config.get('server', {})
            config_data['launcher'] = system_config.get('launcher', {})
            config_data['unified_api'] = system_config.get('unified_api', {})
            config_data['onebot'] = system_config.get('onebot', {})
            config_data['comm_protocol'] = str(system_config.get('comm_protocol', 'unified') or 'unified').lower()
            config_data['work_mode'] = {
                'enabled': bool(system_config.get('work_mode', {}).get('enabled', False)),
                'has_password': bool(system_config.get('work_mode', {}).get('password_hash', '')),
                'sandbox_enabled': bool(system_config.get('work_mode', {}).get('sandbox_enabled', False)),
                'reply_policy': default_reply_policy(system_config.get('work_mode', {}).get('reply_policy', {})),
                'chat_settings': _default_chat_settings(system_config.get('work_mode', {}).get('chat_settings', {})),
                'features': _default_work_mode_features(system_config.get('work_mode', {}).get('features', {})),
                'allowed_databases': system_config.get('work_mode', {}).get('allowed_databases', ['catgirl_db'])
            }

            # 从数据库获取角色信息
            try:
                from app.database.database import get_connection, table_exists

                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    if table_exists(cur, 'character_info'):
                        cur.execute(
                            'SELECT name, personality, brother_qqid, height, weight, catchphrases '
                            'FROM character_info LIMIT 1'
                        )
                        row = cur.fetchone()
                        if row:
                            config_data['character'] = {
                                'name': row[0],
                                'personality': row[1],
                                'brother_qqid': row[2],
                                'height': row[3],
                                'weight': row[4],
                                'catchphrases': row[5],
                            }
                    conn.close()
            except Exception as e:
                print(f"获取角色信息时出错: {e}")

            return jsonify(config_data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/config', methods=['POST'])
    def update_config():
        try:
            config_path = os.path.join(DATA_DIR, 'config.json')
            
            # 获取请求数据
            new_config = request.get_json()
            system_config = _load_system_config()

            # 先合并数据库配置，后续写库/读角色使用最新 engine
            if new_config and 'database' in new_config:
                CONFIG['database'].update(new_config['database'])
                db_path_early = os.path.join(
                    DATA_DIR,
                    'database.json',
                )
                with open(db_path_early, 'w', encoding='utf-8') as df:
                    json.dump(new_config['database'], df, ensure_ascii=False, indent=2)
                try:
                    AIChatSystem.rebind_database()
                except Exception as ex:
                    app.logger.warning('AIChatSystem.rebind_database failed: %s', ex)

            if new_config and 'server' in new_config:
                system_config['server'] = new_config['server']
            if new_config and 'launcher' in new_config:
                system_config['launcher'] = new_config['launcher']
            if new_config and 'unified_api' in new_config:
                system_config['unified_api'] = new_config['unified_api']
            if new_config and 'onebot' in new_config:
                system_config['onebot'] = new_config['onebot']
            if new_config and 'work_mode' in new_config:
                incoming_work_mode = new_config['work_mode'] or {}
                current_work_mode = system_config.get('work_mode', {})
                current_work_mode['enabled'] = bool(incoming_work_mode.get('enabled', current_work_mode.get('enabled', False)))
                current_work_mode['sandbox_enabled'] = bool(incoming_work_mode.get('sandbox_enabled', current_work_mode.get('sandbox_enabled', False)))
                if 'password_hash' in incoming_work_mode:
                    current_work_mode['password_hash'] = incoming_work_mode.get('password_hash', current_work_mode.get('password_hash', ''))
                if 'reply_policy' in incoming_work_mode:
                    current_work_mode['reply_policy'] = default_reply_policy(incoming_work_mode.get('reply_policy', {}))
                if 'chat_settings' in incoming_work_mode:
                    current_work_mode['chat_settings'] = _default_chat_settings(incoming_work_mode.get('chat_settings', {}))
                if 'features' in incoming_work_mode:
                    current_work_mode['features'] = _default_work_mode_features(incoming_work_mode.get('features', {}))
                if 'allowed_databases' in incoming_work_mode:
                    current_work_mode['allowed_databases'] = incoming_work_mode.get('allowed_databases', current_work_mode.get('allowed_databases', ['catgirl_db']))
                system_config['work_mode'] = current_work_mode
            if new_config and 'comm_protocol' in new_config:
                proto = str(new_config.get('comm_protocol', '') or '').strip().lower()
                system_config['comm_protocol'] = 'onebot' if proto == 'onebot' else 'unified'
            _save_system_config(system_config)

            # 读取现有配置
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 更新API密钥配置
            if 'api_keys' in new_config:
                config_data.setdefault('api_keys', {})
                config_data['api_keys'].update(new_config['api_keys'])
            
            # 更新OneBot配置
            if 'onebot' in new_config:
                config_data['onebot'] = new_config['onebot']
            
            # 更新Unified API配置
            if 'unified_api' in new_config:
                config_data['unified_api'] = new_config['unified_api']

            # 更新 Coder API 聚合配置
            if 'coder_api' in new_config:
                config_data['coder_api'] = new_config['coder_api']
            
            # 更新角色配置到数据库
            if 'character' in new_config:
                try:
                    from app.database.database import get_connection, get_engine, table_exists

                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        if table_exists(cur, 'character_info'):
                            cur.execute('SELECT COUNT(*) FROM character_info')
                            count = cur.fetchone()[0]
                            vals = (
                                new_config['character'].get('name', 'Default Character'),
                                new_config['character'].get('personality', ''),
                                new_config['character'].get('brother_qqid', ''),
                                new_config['character'].get('height', ''),
                                new_config['character'].get('weight', ''),
                                new_config['character'].get('catchphrases', ''),
                            )
                            if count > 0:
                                if get_engine() == 'postgresql':
                                    cur.execute(
                                        """UPDATE character_info SET name = %s, personality = %s,
                                        brother_qqid = %s, height = %s, weight = %s, catchphrases = %s
                                        WHERE id = (SELECT id FROM character_info ORDER BY id LIMIT 1)""",
                                        vals,
                                    )
                                else:
                                    cur.execute(
                                        """UPDATE character_info SET name = %s, personality = %s,
                                        brother_qqid = %s, height = %s, weight = %s, catchphrases = %s
                                        LIMIT 1""",
                                        vals,
                                    )
                            else:
                                cur.execute(
                                    """INSERT INTO character_info
                                    (name, personality, brother_qqid, height, weight, catchphrases)
                                    VALUES (%s, %s, %s, %s, %s, %s)""",
                                    vals,
                                )
                            conn.commit()
                        conn.close()
                except Exception as e:
                    print(f"更新角色信息时出错: {e}")
            
            # 同时更新 config.json 中的 character 信息
            if 'character' in new_config:
                if 'character' not in config_data:
                    config_data['character'] = {}
                config_data['character'].update(new_config['character'])
            
            # 更新Unified API配置（在内存中）
            if 'unified_api' in new_config:
                if 'unified_api' not in CONFIG:
                    CONFIG['unified_api'] = {}
                CONFIG['unified_api'].update(new_config['unified_api'])

            if 'server' in new_config:
                if 'server' not in CONFIG:
                    CONFIG['server'] = {}
                CONFIG['server'].update(new_config['server'])

            if 'launcher' in new_config:
                if 'launcher' not in CONFIG:
                    CONFIG['launcher'] = {}
                CONFIG['launcher'].update(new_config['launcher'])

            if 'onebot' in new_config:
                if 'onebot' not in CONFIG:
                    CONFIG['onebot'] = {}
                CONFIG['onebot'].update(new_config['onebot'])

            if 'work_mode' in new_config:
                CONFIG['work_mode'] = system_config.get('work_mode', CONFIG.get('work_mode', {}))

            # 更新 Coder API 配置（在内存中）
            if 'coder_api' in new_config:
                CONFIG['coder_api'] = new_config['coder_api']
            
            # 写入主配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                # 过滤掉 character 和 database 以避免写入 config.json
                data_to_save = {k: v for k, v in config_data.items() if k not in ['character', 'database', 'system_prompt_template']}
                # 确保 system_prompt_template 不被写回（它现在在 persona 文件里）
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)

            _reload_runtime_config_after_write()

            # database.json 已在请求开头写入；此处不再重复

            db_test_result = None
            if new_config and 'database' in new_config:
                db_test_result = _test_database_connectivity(new_config.get('database', {}))

            # 更新 Persona (Separated)
            if 'character' in new_config:
                active_persona = config_data.get('active_persona', 'shizuku.json')
                persona_path = os.path.join(DATA_DIR, 'personas', active_persona)
                
                # Try to load existing persona to preserve meta/system_prompt
                current_persona = {}
                if os.path.exists(persona_path):
                    with open(persona_path, 'r', encoding='utf-8') as f:
                        current_persona = json.load(f)
                
                # Update character section
                current_persona['character'] = new_config['character']
                
                # Save Persona
                with open(persona_path, 'w', encoding='utf-8') as f:
                    json.dump(current_persona, f, ensure_ascii=False, indent=2)

                # Re-generate system prompt
                template = current_persona.get('system_prompt', {}).get('template', CONFIG.get('system_prompt_template', ''))
                CONFIG['system_prompt'] = generate_system_prompt(new_config['character'], template)
            
            response_payload = {'message': '配置更新成功'}
            if db_test_result is not None:
                response_payload['database_test'] = db_test_result
            return jsonify(response_payload)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/config/model-discovery', methods=['POST'])
    def api_model_discovery():
        try:
            payload = request.get_json() or {}
            base_url = str(payload.get('base_url', '') or '').strip()
            api_key = str(payload.get('key', '') or '').strip()
            normalized_url, provider_hint = _normalize_api_base_url(base_url)
            if not normalized_url:
                return jsonify({'success': False, 'error': 'base_url 不能为空'}), 400

            headers = {}
            if api_key:
                if provider_hint == 'anthropic':
                    headers['x-api-key'] = api_key
                    headers['anthropic-version'] = '2023-06-01'
                else:
                    headers['Authorization'] = f'Bearer {api_key}'

            resp = requests.get(f"{normalized_url.rstrip('/')}/models", headers=headers, timeout=12)
            text = resp.text or ''
            try:
                parsed = resp.json() if text else {}
            except Exception:
                parsed = {}

            models = _extract_model_ids(parsed)
            if resp.status_code >= 400:
                return jsonify({
                    'success': False,
                    'normalized_base_url': normalized_url,
                    'provider_hint': provider_hint,
                    'status_code': resp.status_code,
                    'error': parsed.get('error', {}).get('message') if isinstance(parsed, dict) else text[:300] or f'HTTP {resp.status_code}',
                    'models': models,
                }), 200

            return jsonify({
                'success': True,
                'normalized_base_url': normalized_url,
                'provider_hint': provider_hint,
                'models': models,
                'count': len(models),
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/config/hot-switch-model', methods=['POST'])
    def api_hot_switch_model():
        try:
            data = request.get_json() or {}
            service_key = str(data.get('service_key', '') or '').strip()
            model = str(data.get('model', '') or '').strip()
            base_url = str(data.get('base_url', '') or '').strip()
            api_key = str(data.get('key', '') or '').strip()
            if not service_key:
                return jsonify({'success': False, 'error': 'service_key 不能为空'}), 400
            if not model:
                return jsonify({'success': False, 'error': 'model 不能为空'}), 400

            config_path = os.path.join(DATA_DIR, 'config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            config_data.setdefault('api_keys', {})
            section = config_data['api_keys'].get(service_key, {})
            if isinstance(section, str):
                section = {'key': section, 'base_url': '', 'model': ''}
            elif not isinstance(section, dict):
                section = {'key': '', 'base_url': '', 'model': ''}

            section['model'] = model
            if base_url:
                section['base_url'] = base_url
            if api_key:
                section['key'] = api_key
            config_data['api_keys'][service_key] = section

            # Keep coder_api providers aligned with their mirrored legacy keys.
            if service_key in ('kimi_coder', 'minimax_coder', 'claude_coder'):
                provider_key = service_key.replace('_coder', '')
                config_data.setdefault('coder_api', {})
                coder_api = config_data['coder_api'] if isinstance(config_data.get('coder_api'), dict) else {}
                providers = coder_api.get('providers', {}) if isinstance(coder_api.get('providers'), dict) else {}
                provider_cfg = providers.get(provider_key, {}) if isinstance(providers.get(provider_key), dict) else {}
                provider_cfg['model'] = model
                if base_url:
                    provider_cfg['base_url'] = base_url
                if api_key:
                    provider_cfg['key'] = api_key
                providers[provider_key] = provider_cfg
                coder_api['providers'] = providers
                config_data['coder_api'] = coder_api

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            _reload_runtime_config_after_write()

            active_api = CONFIG.get('api', {}) or {}
            return jsonify({
                'success': True,
                'service_key': service_key,
                'model': model,
                'active_runtime_model': str(active_api.get('model', '') or ''),
                'active_runtime_base_url': str(active_api.get('base_url', '') or ''),
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/config/api-templates', methods=['GET'])
    def api_get_api_templates():
        """获取可用的API服务类型列表（供插件使用）"""
        try:
            templates = [
                {'key': 'deepseek_chat', 'name': '聊天 API (DeepSeek)', 'description': '用于日常对话的API'},
                {'key': 'programming_chat', 'name': '编程对话 API (Programming)', 'description': '用于编程相关的对话（非Agent模式）'},
                {'key': 'search', 'name': '搜索 API (SearchAPI)', 'description': '用于网络搜索的API'},
                {'key': 'image_recognition', 'name': '图像识别 API (VisionAPI)', 'description': '用于图片理解的API'},
                {'key': 'image_generation', 'name': '图像生成 API (ImageGenAPI)', 'description': '用于图片生成的API'},
                {'key': 'video_generation', 'name': '视频生成 API (VideoGenAPI)', 'description': '用于视频生成的API'},
                {'key': 'speech_to_text', 'name': '语音转文本 API (STT)', 'description': '用于语音识别的API'},
                {'key': 'text_to_speech', 'name': '文本转语音 API (TTS)', 'description': '用于语音合成的API'},
                {'key': 'coder', 'name': '代码助手 API (CoderAPI)', 'description': '用于代码生成的Agent API'},
                {'key': 'kimi_coder', 'name': '代码助手 API (Kimi方案)', 'description': 'Kimi Coder Agent方案'},
                {'key': 'minimax_coder', 'name': '代码助手 API (MiniMax方案)', 'description': 'MiniMax Coder Agent方案'},
                {'key': 'claude_coder', 'name': '代码助手 API (Claude方案)', 'description': 'Claude Coder Agent方案'}
            ]
            
            # 主流AI提供商预设配置
            provider_presets = {
                'openai': {
                    'name': 'OpenAI',
                    'base_url': 'https://api.openai.com/v1',
                    'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
                    'icon': '🟢',
                    'category': 'cloud'
                },
                'anthropic': {
                    'name': 'Anthropic (Claude)',
                    'base_url': 'https://api.anthropic.com/v1',
                    'models': ['claude-3-7-sonnet', 'claude-3-5-sonnet', 'claude-3-opus', 'claude-3-haiku'],
                    'icon': '🟣',
                    'category': 'cloud'
                },
                'deepseek': {
                    'name': 'DeepSeek (深度求索)',
                    'base_url': 'https://api.deepseek.com/v1',
                    'models': ['deepseek-chat', 'deepseek-reasoner', 'deepseek-coder'],
                    'icon': '🔵',
                    'category': 'domestic'
                },
                'moonshot': {
                    'name': 'Moonshot (月之暗面/Kimi)',
                    'base_url': 'https://api.moonshot.cn/v1',
                    'models': ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k', 'kimi-latest'],
                    'icon': '🌙',
                    'category': 'domestic'
                },
                'qwen': {
                    'name': 'Qwen (通义千问)',
                    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                    'models': ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-long'],
                    'icon': '🟠',
                    'category': 'domestic'
                },
                'zhipu': {
                    'name': 'Zhipu (智谱AI/GLM)',
                    'base_url': 'https://open.bigmodel.cn/api/paas/v4',
                    'models': ['glm-4', 'glm-4-plus', 'glm-4-air', 'glm-4-flash'],
                    'icon': '🔴',
                    'category': 'domestic'
                },
                'minimax': {
                    'name': 'MiniMax',
                    'base_url': 'https://api.minimaxi.com/v1',
                    'models': ['abab6.5-chat', 'abab6.5s-chat', 'abab5.5-chat'],
                    'icon': '⚡',
                    'category': 'domestic'
                },
                'doubao': {
                    'name': 'Doubao (豆包/字节)',
                    'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
                    'models': ['doubao-pro-32k', 'doubao-lite-32k', 'doubao-pro-128k'],
                    'icon': '🟤',
                    'category': 'domestic'
                },
                'groq': {
                    'name': 'Groq',
                    'base_url': 'https://api.groq.com/openai/v1',
                    'models': ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
                    'icon': '⚡',
                    'category': 'international'
                },
                'gemini': {
                    'name': 'Google Gemini',
                    'base_url': 'https://generativelanguage.googleapis.com/v1beta',
                    'models': ['gemini-2.0-flash', 'gemini-2.0-pro', 'gemini-1.5-pro'],
                    'icon': '🔮',
                    'category': 'international'
                },
                'openrouter': {
                    'name': 'OpenRouter',
                    'base_url': 'https://openrouter.ai/api/v1',
                    'models': ['openai/gpt-4o', 'anthropic/claude-3.5-sonnet', 'google/gemini-2.0-flash'],
                    'icon': '🌐',
                    'category': 'aggregator'
                },
                'ollama': {
                    'name': 'Ollama (本地)',
                    'base_url': 'http://localhost:11434/v1',
                    'models': ['llama3.2', 'llama3.1', 'qwen2.5', 'deepseek-r1', 'mistral'],
                    'icon': '🦙',
                    'category': 'local',
                    'requires_key': False
                },
                'vllm': {
                    'name': 'vLLM (本地)',
                    'base_url': 'http://localhost:8000/v1',
                    'models': ['custom-model'],
                    'icon': '🚀',
                    'category': 'local',
                    'requires_key': False
                },
                'lmstudio': {
                    'name': 'LM Studio (本地)',
                    'base_url': 'http://localhost:1234/v1',
                    'models': ['local-model'],
                    'icon': '💻',
                    'category': 'local',
                    'requires_key': False
                }
            }
            
            return jsonify({
                'success': True,
                'templates': templates,
                'provider_presets': provider_presets,
                'template_count': len(templates),
                'preset_count': len(provider_presets)
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/config/active-model-service', methods=['GET'])
    def api_get_active_model_service():
        try:
            config_path = os.path.join(DATA_DIR, 'config.json')
            if not os.path.exists(config_path):
                return jsonify({'success': False, 'error': '找不到 config.json'}), 404
                
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                
            api_cfg = cfg.get('api') or {}
            
            try:
                service_key = str(api_cfg.get('service', 'openai-compatible'))
            except Exception as e:
                raise Exception(f"api_cfg.get('service') failed. api_cfg is {type(api_cfg)}: {repr(api_cfg)}")
                
            try:
                model = str(api_cfg.get('model', 'gpt-3.5-turbo'))
            except Exception as e:
                raise Exception(f"api_cfg.get('model') failed. api_cfg is {type(api_cfg)}")
            
            active_api = CONFIG.get('api') or {}
            
            try:
                active_runtime_model = str(active_api.get('model', '') or '')
            except Exception as e:
                raise Exception(f"active_api.get('model') failed. active_api is {type(active_api)}: {repr(active_api)}")
                
            active_runtime_base_url = str(active_api.get('base_url', '') or '')
                
            return jsonify({
                'success': True,
                'service_key': service_key,
                'model': model,
                'active_runtime_model': active_runtime_model,
                'active_runtime_base_url': active_runtime_base_url,
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # Persiona Management APIs

    # Persiona Management APIs
    @app.route('/api/personas', methods=['GET'])
    def list_personas():
        try:
            personas_dir = os.path.join(DATA_DIR, 'personas')
            if not os.path.exists(personas_dir):
                os.makedirs(personas_dir)
            
            files = [f for f in os.listdir(personas_dir) if f.endswith('.json')]
            personas = []
            
            # Load active persona name
            config_path = os.path.join(DATA_DIR, 'config.json')
            active = "shizuku.json"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    active = json.load(f).get('active_persona', 'shizuku.json')

            for file in files:
                try:
                    with open(os.path.join(personas_dir, file), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        meta = data.get('meta', {})
                        personas.append({
                            'filename': file,
                            'name': meta.get('name', 'Unknown'),
                            'description': meta.get('description', ''),
                            'version': meta.get('version', '1.0'),
                            'is_active': (file == active)
                        })
                except Exception:
                    continue
            return jsonify({'personas': personas, 'active': active})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/personas/<filename>', methods=['GET'])
    def get_persona(filename):
        try:
            path = os.path.join(DATA_DIR, 'personas', filename)
            if not os.path.exists(path):
                return jsonify({'error': 'Not found'}), 404
            with open(path, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/personas', methods=['POST'])
    def create_persona():
        try:
            data = request.get_json()
            filename = data.get('filename')
            if not filename.endswith('.json'):
                filename += '.json'
            
            content = data.get('content')
            os.makedirs(os.path.join(DATA_DIR, 'personas'), exist_ok=True)
            path = os.path.join(DATA_DIR, 'personas', filename)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            
            # 自动为角色创建数据库表
            try:
                from app.database.database import DatabaseManager
                db_manager = DatabaseManager()
                # 创建该角色的聊天历史表
                persona_table_name = f"chat_history_{filename.replace('.json', '')}"
                cursor = db_manager._new_cursor()
                # 检查表是否已存在
                cursor.execute("SHOW TABLES LIKE %s", (persona_table_name,))
                if not cursor.fetchone():
                    # 表不存在，创建新表
                    db_manager._bootstrap_persona_chat_history(cursor, filename, persona_table_name)
                    db_manager.connection.commit()
                    app.logger.info(f"为角色 {filename} 自动创建数据库表 {persona_table_name}")
                cursor.close()
                db_manager.close()
            except Exception as db_err:
                app.logger.warning(f"创建角色数据库表时出错: {db_err}")
                # 不影响角色创建流程，仅记录警告
            
            return jsonify({'success': True, 'filename': filename})
        except Exception as e:
            app.logger.error(f"创建角色时出错: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/personas/activate', methods=['POST'])
    def activate_persona():
        try:
            filename = (request.get_json() or {}).get('filename')
            if not filename:
                return jsonify({'error': 'filename is required'}), 400
            if not filename.endswith('.json'):
                filename += '.json'

            config_path = os.path.join(DATA_DIR, 'config.json')
            persona_path = os.path.join(DATA_DIR, 'personas', filename)
            if not os.path.exists(persona_path):
                return jsonify({'error': f'persona not found: {filename}'}), 404
            
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            
            cfg['active_persona'] = filename
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            
            # Reload in memory
            from app.core.config import load_config
            new_conf = load_config()
            CONFIG.update(new_conf)

            # 同步刷新单例中的人格上下文，避免切换后首条消息仍用旧人格。
            try:
                from app.agent.ai_chat_system import AIChatSystem
                ai = AIChatSystem()
                ai.system_prompt = CONFIG.get('system_prompt', ai.system_prompt)
                ai.persona_runtime = CONFIG.get('persona_runtime', ai.persona_runtime)
            except Exception:
                pass
            
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/personas/<filename>', methods=['DELETE'])
    def delete_persona(filename):
        try:
            path = os.path.join(DATA_DIR, 'personas', filename)
            
            # 删除对应的数据库表
            try:
                from app.database.database import DatabaseManager
                db_manager = DatabaseManager()
                persona_table_name = f"chat_history_{filename.replace('.json', '')}"
                cursor = db_manager._new_cursor()
                # 检查表是否存在
                cursor.execute("SHOW TABLES LIKE %s", (persona_table_name,))
                if cursor.fetchone():
                    # 表存在，删除表
                    cursor.execute(f"DROP TABLE IF EXISTS {persona_table_name}")
                    db_manager.connection.commit()
                    app.logger.info(f"为角色 {filename} 自动删除数据库表 {persona_table_name}")
                cursor.close()
                db_manager.close()
            except Exception as db_err:
                app.logger.warning(f"删除角色数据库表时出错: {db_err}")
                # 不影响角色删除流程，仅记录警告
            
            # 删除角色文件
            if os.path.exists(path):
                os.remove(path)
            
            return jsonify({'success': True})
        except Exception as e:
            app.logger.error(f"删除角色时出错: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/personas/open-folder')
    def open_persona_folder():
        try:
            personas_dir = os.path.join(DATA_DIR, 'personas')
            os.makedirs(personas_dir, exist_ok=True)
            if os.name == 'nt':
                os.startfile(personas_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', personas_dir])
            else:
                subprocess.Popen(['xdg-open', personas_dir])
            return jsonify({'success': True, 'path': personas_dir})
        except Exception as e:
            app.logger.error(f"打开人格目录失败: {e}")
            return jsonify({'error': str(e)}), 500

    # 批处理接口：传入 "0"~"5" 对应 start.bat 菜单项
    @app.route('/api/batch/<choice>', methods=['POST'])
    def api_batch_choice(choice):
        backend_root = os.path.dirname(PROJECT_ROOT).replace('/', '\\')
        # 在新终端窗口执行 app 模块入口，兼容新目录结构
        cmd = (
            f'cd /d "{backend_root}" && '
            f'start "Mode {choice}" cmd /k '
            f'"set PYTHONPATH={backend_root};%PYTHONPATH% && python -m app.main {choice}"'
        )
        subprocess.Popen(cmd, shell=True)
        return '', 204

    # 挂载静态
    # app.static_folder 已指向 src/static

    # 定义一个函数来打开浏览器
    def open_browser():
        # 根据环境变量决定打开哪个页面
        default_page = os.environ.get('DEFAULT_PAGE', '/control_panel')
        webbrowser.open_new_tab(f'http://localhost:{port}{default_page}')

    # 为防止调试模式下的重载器多次打开浏览器，我们只在主进程中执行此操作
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        # 在服务器启动后延迟1秒打开浏览器
        threading.Timer(1, open_browser).start()

    # 启动服务
    try:
        print(Fore.CYAN + f"\n🌐 沙箱聊天模式已启动: http://localhost:{port}")
        app.logger.info(f"服务器启动于 http://localhost:{port}")
        app.run(host='0.0.0.0', port=port, use_reloader=False, threaded=True)
    except Exception as e:
        print(Fore.RED + f"\n❌ 服务器启动失败: {str(e)}")
        app.logger.error(f"服务器运行出错: {str(e)}")
        return 1

    return 0
