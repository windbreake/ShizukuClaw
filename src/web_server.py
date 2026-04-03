# -*- coding: utf-8 -*-
"""Web服务器模块，提供聊天界面和相关API"""

import io
import json
import logging
import os
import sys
import time
import subprocess
import threading
import webbrowser
import psutil
import locale
import platform
import mimetypes
import datetime
import hashlib
import hmac
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('text/html', '.html')

from flask import Flask, request, jsonify, Response, send_from_directory, render_template
from flask.cli import pass_script_info
from colorama import Fore, Back, Style, init
from werkzeug.serving import make_server
from logging.handlers import RotatingFileHandler

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ai_chat_system import AIChatSystem
from src.config import CONFIG, generate_system_prompt

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
        'allow_coder_tool': bool(existing.get('allow_coder_tool', True))
    }

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
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, 'static')
app = Flask(__name__, static_folder=static_dir, static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# 注册系统API蓝图
try:
    from src.systems_api import systems_bp
    app.register_blueprint(systems_bp)
except ImportError as e:
    print(f"Warning: Could not import systems_api: {e}")

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

        from src.agent_manager import AgentManager
        am = AgentManager() # This initializes a new manager (and sandbox)
        result = am.sandbox.execute_python(code)
        
        return jsonify({'success': True, 'output': result})
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
    port = 8888
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
    
    chat_system = AIChatSystem()

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

            # Web请求被视为管理员操作，允许使用Agent工具
            response = chat_system.chat(
                data.get('message'), 
                data.get('image'), 
                is_admin=True, 
                attachments=data.get('attachments'),
                frontend_source=frontend_source
            )
            return jsonify({'success': True, 'reply': response})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/work_mode/status', methods=['GET'])
    def api_work_mode_status():
        try:
            wm = CONFIG.get('work_mode', {})
            return jsonify({
                'success': True,
                'global_enabled': bool(wm.get('enabled', False)),
                'sandbox_enabled': bool(wm.get('sandbox_enabled', False)),
                'has_password': bool(wm.get('password_hash')),
                'features': _default_work_mode_features(wm.get('features', {}))
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

            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            config_path = os.path.join(base_path, 'data', 'config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            if 'work_mode' not in config_data:
                config_data['work_mode'] = {}

            existing_hash = config_data['work_mode'].get('password_hash', '')
            if existing_hash and not _verify_password(current_password, existing_hash):
                return jsonify({'success': False, 'error': '旧密码错误，无法修改'}), 403

            config_data['work_mode']['password_hash'] = _hash_password(password)

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            if 'work_mode' not in CONFIG:
                CONFIG['work_mode'] = {}
            CONFIG['work_mode']['password_hash'] = config_data['work_mode']['password_hash']

            return jsonify({'success': True, 'message': '安全密码已设置'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/work_mode/options', methods=['POST'])
    def api_work_mode_options():
        try:
            data = request.get_json() or {}
            incoming = data.get('features', {})
            features = _default_work_mode_features(incoming)

            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            config_path = os.path.join(base_path, 'data', 'config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            if 'work_mode' not in config_data:
                config_data['work_mode'] = {}
            config_data['work_mode']['features'] = features

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            if 'work_mode' not in CONFIG:
                CONFIG['work_mode'] = {}
            CONFIG['work_mode']['features'] = features

            return jsonify({'success': True, 'features': features})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/work_mode/reset_password_terminal', methods=['POST'])
    def api_work_mode_reset_password_terminal():
        try:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            script_path = os.path.join(project_root, 'src', 'reset_workmode_password.py')
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
                return jsonify({'success': True, 'scope': 'sandbox', 'enabled': enable})

            # Global scope requires password verification
            wm = CONFIG.get('work_mode', {})
            saved_hash = wm.get('password_hash', '')
            if not saved_hash:
                return jsonify({'success': False, 'error': '请先在设置中配置安全密码'}), 400

            password = data.get('password') or ''
            if not _verify_password(password, saved_hash):
                return jsonify({'success': False, 'error': '安全密码错误'}), 403

            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            config_path = os.path.join(base_path, 'data', 'config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            if 'work_mode' not in config_data:
                config_data['work_mode'] = {}
            config_data['work_mode']['enabled'] = enable
            if 'features' not in config_data['work_mode']:
                config_data['work_mode']['features'] = _default_work_mode_features({})

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            if 'work_mode' not in CONFIG:
                CONFIG['work_mode'] = {}
            CONFIG['work_mode']['enabled'] = enable
            CONFIG['work_mode']['features'] = _default_work_mode_features(CONFIG['work_mode'].get('features', {}))

            return jsonify({'success': True, 'scope': 'global', 'enabled': enable})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/adapter_console')
    def adapter_console():
        return app.send_static_file('adapter_console.html')

    @app.route('/terminal_page')
    def terminal_page():
        return app.send_static_file('terminal_chat.html')

    @app.route('/diagnosis_page')
    def diagnosis_page():
        return app.send_static_file('diagnosis.html')

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

    @app.route('/api/diagnosis')
    def api_diagnosis():
        import re
        try:
            # Run diagnose.py from src
            # base_dir is src/
            project_root = os.path.dirname(base_dir)
            script_path = os.path.join('src', 'diagnose.py')
            
            result = subprocess.run([sys.executable, script_path], capture_output=True, text=True, cwd=project_root)
            output = result.stdout + result.stderr
            
            # Strip ANSI codes
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            try:
                raw_output = (result.stdout or "") + (result.stderr or "")
                clean_output = ansi_escape.sub('', raw_output)
            except Exception as e:
                clean_output = f"Error processing output: {str(e)}"
            
            # Simple formatting for HTML
            html_output = f"<pre>{clean_output}</pre>"
            return html_output
        except Exception as e:
            return f"<span class='text-danger'>Error running diagnosis: {str(e)}</span>"

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

    @app.route('/api/plugins/status', methods=['GET'])
    def api_plugins_status():
        try:
            status = chat_system.get_plugin_status()
            return jsonify({'success': True, 'status': status})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

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
                import os
                import json
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
                        return jsonify({'success': True, 'plugin_name': plugin_name, 'config': cfg})
                    except Exception as e:
                        print(f"[DEBUG] Error reading config file: {e}")
                        # 如果读取失败，返回默认配置
                        default_config = {
                            "description": "Built-in basic plugin configuration",
                            "version": "1.0.0",
                            "enabled": True
                        }
                        return jsonify({'success': True, 'plugin_name': plugin_name, 'config': default_config})
                
                print(f"[DEBUG] Config file not found, returning default config")
                # 如果文件不存在，返回默认配置
                default_config = {
                    "description": "Built-in basic plugin configuration",
                    "version": "1.0.0",
                    "enabled": True
                }
                return jsonify({'success': True, 'plugin_name': plugin_name, 'config': default_config})
            
            cfg = chat_system.plugin_manager.get_plugin_runtime_config(plugin_name)
            return jsonify({'success': True, 'plugin_name': plugin_name, 'config': cfg})
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
                import os
                import json
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

    # 后端获取记录
    @app.route('/api/records')
    def api_records():
        from src.database import DatabaseManager
        db_manager = DatabaseManager()
        try:
            # 减少默认查询数量，提高响应速度
            limit = min(int(request.args.get('limit', 50)), 100)  # 限制最大100条记录
            rows = db_manager.get_chat_history(limit=limit)
            return jsonify(rows)
        except Exception as e:
            app.logger.error(f"获取聊天记录时出错: {str(e)}")
            return jsonify([]) 
        finally:
            db_manager.close()

    @app.route('/api/delete_record', methods=['POST'])
    def api_del_record():
        data = request.get_json()
        rid = data.get('id')
        from src.database import DatabaseManager
        db_manager = DatabaseManager()
        try:
            db_manager.delete_chat_record(rid)
            return jsonify({'message': 'ok'})
        except Exception as e:
            app.logger.error(f"删除聊天记录时出错: {str(e)}")
            return jsonify({'message': 'error'}), 500
        finally:
            db_manager.close()

    @app.route('/api/clear_records', methods=['POST'])
    def api_clear():
        from src.database import DatabaseManager
        db_manager = DatabaseManager()
        try:
            db_manager.clear_chat_history()
            return jsonify({'message': 'cleared'})
        except Exception as e:
            app.logger.error(f"清空聊天记录时出错: {str(e)}")
            return jsonify({'message': 'error'}), 500
        finally:
            db_manager.close()

    @app.route('/api/delete_first_n', methods=['POST'])
    def api_del_n():
        data = request.get_json()
        n = data.get('n', 0)
        from src.database import DatabaseManager
        db_manager = DatabaseManager()
        try:
            db_manager.delete_first_n_records(n)
            return jsonify({'message': 'deleted_first_n'})
        except Exception as e:
            app.logger.error(f"删除前N条聊天记录时出错: {str(e)}")
            return jsonify({'message': 'error'}), 500
        finally:
            db_manager.close()

    @app.route('/api/database/query', methods=['POST'])
    def api_db_query():
        try:
            query = request.get_json().get('query')
            if not query:
                return jsonify({'error': 'No query provided'}), 400
            
            from src.reset_database import get_connection
            conn = get_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            try:
                cur = conn.cursor()
                cur.execute(query)
                
                if query.strip().upper().startswith('SELECT') or query.strip().upper().startswith('SHOW'):
                    columns = [desc[0] for desc in cur.description] if cur.description else []
                    rows = cur.fetchall()
                    result = [dict(zip(columns, row)) for row in rows]
                    return jsonify({'success': True, 'data': result, 'columns': columns})
                else:
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
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        main_py = os.path.join(base, 'main.py')
        # 修复Windows路径问题
        main_py = main_py.replace('/', '\\')
        threading.Thread(target=lambda: subprocess.Popen([sys.executable, main_py, str(m)])).start()
        return jsonify({'message': f'mode {m} launched'})

    # Launcher API Endpoints
    @app.route('/api/launcher/cleanup', methods=['POST'])
    def api_launcher_cleanup():
        try:
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            script_path = os.path.join(base_path, 'src', 'cleanup_chat_history.py')
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
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            script_path = os.path.join(base_path, 'src', 'create_database.py')
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
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            main_py = os.path.join(base_path, 'main.py')
            unified_py = os.path.join(base_path, 'src', 'unified_api.py')
            
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
            from src.config import CONFIG
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
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
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
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
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
            # 获取项目根目录
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            config_path = os.path.join(base_path, 'data', 'config.json')
            
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 添加数据库配置
            if 'database' not in config_data:
                config_data['database'] = {}
            
            config_data['database']['host'] = CONFIG.get('database', {}).get('host', '')
            config_data['database']['user'] = CONFIG.get('database', {}).get('user', '')
            config_data['database']['password'] = CONFIG.get('database', {}).get('password', '')
            config_data['database']['database'] = CONFIG.get('database', {}).get('database', '')
            
            # 从数据库获取角色信息
            try:
                from src.reset_database import get_connection
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    # 检查表是否存在
                    cur.execute("SHOW TABLES LIKE 'character_info'")
                    if cur.fetchone():
                        cur.execute("SELECT name, personality, brother_qqid, height, weight, catchphrases FROM character_info WHERE name = '小雫'")
                        row = cur.fetchone()
                        if row:
                            config_data['character'] = {
                                'name': row[0],
                                'personality': row[1],
                                'brother_qqid': row[2],
                                'height': row[3],
                                'weight': row[4],
                                'catchphrases': row[5]
                            }
                    conn.close()
            except Exception as e:
                print(f"获取角色信息时出错: {e}")

            # Work mode: never expose password hash to frontend
            wm = config_data.get('work_mode', {})
            config_data['work_mode'] = {
                'enabled': bool(wm.get('enabled', False)),
                'has_password': bool(wm.get('password_hash', ''))
            }
            
            return jsonify(config_data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/config', methods=['POST'])
    def update_config():
        try:
            # 获取项目根目录
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            config_path = os.path.join(base_path, 'data', 'config.json')
            
            # 获取请求数据
            new_config = request.get_json()
            
            # 读取现有配置
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 更新API密钥配置
            if 'api_keys' in new_config:
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
                    from src.reset_database import get_connection
                    conn = get_connection()
                    if conn:
                        cur = conn.cursor()
                        # 检查表是否存在
                        cur.execute("SHOW TABLES LIKE 'character_info'")
                        if cur.fetchone():
                            # 先检查是否有记录
                            cur.execute("SELECT COUNT(*) FROM character_info")
                            count = cur.fetchone()[0]
                            if count > 0:
                                # 如果存在记录，则更新第一条记录
                                cur.execute("""UPDATE character_info 
                                             SET name = %s, personality = %s, brother_qqid = %s, 
                                                 height = %s, weight = %s, catchphrases = %s 
                                             LIMIT 1""", (
                                    new_config['character'].get('name', 'Default Character'),
                                    new_config['character'].get('personality', ''),
                                    new_config['character'].get('brother_qqid', ''),
                                    new_config['character'].get('height', ''),
                                    new_config['character'].get('weight', ''),
                                    new_config['character'].get('catchphrases', '')
                                ))
                            else:
                                # 如果没有记录，则插入新记录
                                cur.execute("""INSERT INTO character_info 
                                             (name, personality, brother_qqid, height, weight, catchphrases) 
                                             VALUES (%s, %s, %s, %s, %s, %s)""", (
                                    new_config['character'].get('name', 'Default Character'),
                                    new_config['character'].get('personality', ''),
                                    new_config['character'].get('brother_qqid', ''),
                                    new_config['character'].get('height', ''),
                                    new_config['character'].get('weight', ''),
                                    new_config['character'].get('catchphrases', '')
                                ))
                            conn.commit()
                        conn.close()
                except Exception as e:
                    print(f"更新角色信息时出错: {e}")
            
            # 同时更新 config.json 中的 character 信息
            if 'character' in new_config:
                if 'character' not in config_data:
                    config_data['character'] = {}
                config_data['character'].update(new_config['character'])
            
            # 更新数据库配置（在内存中）
            if 'database' in new_config:
                CONFIG['database'].update(new_config['database'])
            
            # 更新Unified API配置（在内存中）
            if 'unified_api' in new_config:
                if 'unified_api' not in CONFIG:
                    CONFIG['unified_api'] = {}
                CONFIG['unified_api'].update(new_config['unified_api'])

            # 更新 Coder API 配置（在内存中）
            if 'coder_api' in new_config:
                CONFIG['coder_api'] = new_config['coder_api']
            
            # 写入主配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                # 过滤掉 character 和 database 以避免写入 config.json
                data_to_save = {k: v for k, v in config_data.items() if k not in ['character', 'database', 'system_prompt_template']}
                # 确保 system_prompt_template 不被写回（它现在在 persona 文件里）
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)

            # 更新 Database (Separated)
            if 'database' in new_config:
                db_path = os.path.join(base_path, 'data', 'database.json')
                with open(db_path, 'w', encoding='utf-8') as f:
                    json.dump(new_config['database'], f, ensure_ascii=False, indent=2)
                CONFIG['database'].update(new_config['database']) # Update Memory

            # 更新 Persona (Separated)
            if 'character' in new_config:
                active_persona = config_data.get('active_persona', 'shizuku.json')
                persona_path = os.path.join(base_path, 'data', 'personas', active_persona)
                
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
            
            return jsonify({'message': '配置更新成功'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Persiona Management APIs
    @app.route('/api/personas', methods=['GET'])
    def list_personas():
        try:
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            personas_dir = os.path.join(base_path, 'data', 'personas')
            if not os.path.exists(personas_dir):
                os.makedirs(personas_dir)
            
            files = [f for f in os.listdir(personas_dir) if f.endswith('.json')]
            personas = []
            
            # Load active persona name
            config_path = os.path.join(base_path, 'data', 'config.json')
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
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            path = os.path.join(base_path, 'data', 'personas', filename)
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
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            path = os.path.join(base_path, 'data', 'personas', filename)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/personas/activate', methods=['POST'])
    def activate_persona():
        try:
            filename = request.get_json().get('filename')
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            config_path = os.path.join(base_path, 'data', 'config.json')
            
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            
            cfg['active_persona'] = filename
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            
            # Reload in memory
            from src.config import load_config
            new_conf = load_config()
            CONFIG.update(new_conf)
            
            return jsonify({'success': True})
        except Exception as e:
             return jsonify({'error': str(e)}), 500

    @app.route('/api/personas/<filename>', methods=['DELETE'])
    def delete_persona(filename):
        try:
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            path = os.path.join(base_path, 'data', 'personas', filename)
            os.remove(path)
            return jsonify({'success': True})
        except Exception as e:
             return jsonify({'error': str(e)}), 500

    @app.route('/api/personas/open-folder')
    def open_persona_folder():
        try:
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            personas_dir = os.path.join(base_path, 'data', 'personas')
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
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        main_py = os.path.join(base, 'main.py')
        # 在新终端窗口执行：start "标题" cmd /k "python main.py <choice>"
        # 修复Windows路径问题
        main_py = main_py.replace('/', '\\')
        base = base.replace('/', '\\')
        # 使用完整的命令确保在新窗口中运行
        cmd = f'cd /d "{base}" && start "Mode {choice}" cmd /k python "{main_py}" {choice}'
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
