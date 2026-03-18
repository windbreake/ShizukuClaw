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

def start_monitor_thread():
    """启动后台监控线程"""
    global _MONITOR_THREAD_STARTED
    if _MONITOR_THREAD_STARTED:
        return
    _MONITOR_THREAD_STARTED = True
    
    def monitor_loop():
        global _LATEST_SYSTEM_STATS, _CPU_NAME_CACHE
        # Initial Collection
        try:
             # 获取CPU名称 (缓存)
            if _CPU_NAME_CACHE is None:
                try:
                    cpu_name = platform.processor() # Default
                    sys_name = platform.system()
                    if sys_name == "Windows":
                        # Windows wmic call might be slow, so we cache it
                        result = subprocess.run(["wmic", "cpu", "get", "name"], 
                                              capture_output=True, text=True, timeout=2)
                        lines = result.stdout.strip().split('\n')
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

        while True:
            try:
                # 1. CPU
                current_percent = psutil.cpu_percent(interval=1)
                current_per_core = psutil.cpu_percent(interval=None, percpu=True)
                
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
                        disk = D(0, 0, 0, 0)
                
                # 4. Net
                try:
                    net_io = psutil.net_io_counters()
                except Exception:
                    from collections import namedtuple
                    N = namedtuple('io', ['bytes_sent', 'bytes_recv'])
                    net_io = N(0, 0)
                
                # 5. Boot / Load
                boot_time = psutil.boot_time()
                try:
                    if hasattr(psutil, "getloadavg"):
                        load_avg = psutil.getloadavg()
                    else:
                        load_avg = (0, 0, 0)
                except Exception:
                    load_avg = (0, 0, 0)

                 # 构造完整数据
                system_info = {
                    'cpu': _CPU_NAME_CACHE,
                    'cpu_count': psutil.cpu_count(),
                    'total_memory': memory.total,
                    'used_memory': memory.used,
                    'available_memory': memory.available,
                    'memory_unit': memory_percent,
                    'total_disk': disk.total,
                    'used_disk': disk.used,
                    'free_disk': disk.free,
                    'disk_percent': (disk.used / disk.total * 100) if disk.total > 0 else 0,
                    'net_bytes_sent': net_io.bytes_sent,
                    'net_bytes_recv': net_io.bytes_recv,
                    'boot_time': boot_time,
                    'load_avg_1min': load_avg[0],
                    'load_avg_5min': load_avg[1],
                    'load_avg_15min': load_avg[2],
                    'python_version': platform.python_version(),
                    'platform': platform.platform()
                }

                # 计算运行时间
                uptime = time.time() - START_TIME
                
                # Token统计信息
                token_stats = {
                    'input_tokens': INPUT_TOKENS,
                    'output_tokens': OUTPUT_TOKENS,
                    'total_tokens': INPUT_TOKENS + OUTPUT_TOKENS
                }

                _LATEST_SYSTEM_STATS = {
                    'cpu_percent': current_percent,
                    'cpu_per_core': current_per_core,
                    'memory_percent': memory_percent,
                    'memory_details': memory_details,
                    'system_info': system_info,
                    'uptime': uptime,
                    'token_stats': token_stats
                }

            except Exception as e:
                # print(f"Monitor Thread Error: {e}")
                time.sleep(1)

    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()




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
def run_web_server():
    """沙箱聊天模式 (Flask服务 + 控制面板)"""
    port = 8888
    # 使用绝对路径指向 src/static 目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(base_dir, 'static')
    app = Flask(
        __name__,
        static_folder=static_dir,
        static_url_path='/static',
        template_folder=base_dir  # 将模板文件夹指向 src 目录
    )
    
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
        # 根据环境变量决定默认页面
        default_page = os.environ.get('DEFAULT_PAGE', '/control_panel')
        return app.send_static_file(default_page.lstrip('/'))
        
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

            # Web请求被视为管理员操作，允许使用Agent工具
            response = chat_system.chat(
                data.get('message'), 
                data.get('image'), 
                is_admin=True, 
                attachments=data.get('attachments')
            )
            return jsonify({'success': True, 'reply': response})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/koishi_console')
    def koishi_console():
        return app.send_static_file('koishi_console.html')

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

    @app.route('/koishi_logs')
    def koishi_logs():
        return app.send_static_file('koishi_logs.html')

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

            memory_percent = memory.percent
            
            # 获取磁盘使用情况 (兼容性处理)
            try:
                disk = psutil.disk_usage('/')
            except Exception:
                try:
                    disk = psutil.disk_usage('C:\\')
                except Exception:
                    # 如果都失败，构造一个虚拟对象
                    from collections import namedtuple
                    D = namedtuple('usage', ['total', 'used', 'free', 'percent'])
                    disk = D(0, 0, 0, 0)
            
            # 获取网络IO统计信息
            try:
                net_io = psutil.net_io_counters()
            except Exception:
                from collections import namedtuple
                N = namedtuple('io', ['bytes_sent', 'bytes_recv'])
                net_io = N(0, 0)
            
            # 获取系统启动时间
            boot_time = psutil.boot_time()
            
            # 获取系统负载
            try:
                if hasattr(psutil, "getloadavg"):
                    load_avg = psutil.getloadavg()
                else:
                    load_avg = (0, 0, 0)
            except Exception:
                load_avg = (0, 0, 0)
            
            # 获取CPU名称 (缓存)
            if _CPU_NAME_CACHE is None:
                try:
                    cpu_name = platform.processor() # Default
                    sys_name = platform.system()
                    if sys_name == "Windows":
                        # Windows wmic call might be slow, so we cache it
                        result = subprocess.run(["wmic", "cpu", "get", "name"], 
                                              capture_output=True, text=True, timeout=2)
                        lines = result.stdout.strip().split('\n')
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
                     app.logger.warning(f"Failed to get exact CPU name: {e}")
                     _CPU_NAME_CACHE = platform.processor() or "Unknown CPU"

            # 获取系统信息
            system_info = {
                'cpu': _CPU_NAME_CACHE,
                'cpu_count': psutil.cpu_count(),
                'total_memory': memory.total,
                'used_memory': memory.used,
                'available_memory': memory.available,
                'memory_unit': memory_percent,
                'total_disk': disk.total,
                'used_disk': disk.used,
                'free_disk': disk.free,
                'disk_percent': (disk.used / disk.total * 100) if disk.total > 0 else 0,
                'net_bytes_sent': net_io.bytes_sent,
                'net_bytes_recv': net_io.bytes_recv,
                'boot_time': boot_time,
                'load_avg_1min': load_avg[0],
                'load_avg_5min': load_avg[1],
                'load_avg_15min': load_avg[2],
                'python_version': platform.python_version(),
                'platform': platform.platform()
            }
            
            # 计算运行时间
            uptime = time.time() - START_TIME
            
            # Token统计信息
            token_stats = {
                'input_tokens': INPUT_TOKENS,
                'output_tokens': OUTPUT_TOKENS,
                'total_tokens': INPUT_TOKENS + OUTPUT_TOKENS
            }
            
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
            
            return jsonify({
                'cpu_percent': cpu_percent,
                'cpu_per_core': cpu_per_core,
                'memory_percent': memory_percent,
                'memory_details': memory_details,
                'system_info': system_info,
                'uptime': uptime,
                'token_stats': token_stats
            })
        except Exception as e:
            app.logger.error(f"获取监控数据时出错: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/agent/status')
    def api_agent_status():
        try:
            # Read Plan
            plan_path = os.path.join("agent_datas", "plan.md")
            plan_content = ""
            if os.path.exists(plan_path):
                with open(plan_path, 'r', encoding='utf-8') as f:
                    plan_content = f.read()

            # Read Short Term Memory Stats
            memory_path = os.path.join("agent_datas", "memory", "short_term.json")
            memory_count = 0
            if os.path.exists(memory_path):
                with open(memory_path, 'r', encoding='utf-8') as f:
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

    # 日志尾部（演示用）
    @app.route('/api/logs')
    def api_logs():
        try:
            # 添加超时和文件大小限制
            import os
            if os.path.exists('app.log') and os.path.getsize('app.log') > 10*1024*1024:  # 10MB限制
                with open('app.log', 'r', encoding='utf-8') as f:
                    return f.read()[-2000:]  # 只读最后2000个字符
            else:
                with open('app.log', 'r', encoding='utf-8') as f:
                    return f.read()[-2000:]
        except Exception as e:
            app.logger.error(f"读取日志时出错: {str(e)}")
            return ''

    # Koishi 日志API
    @app.route('/api/koishi_logs')
    def api_koishi_logs():
        try:
            import os
            if os.path.exists('koishi.log') and os.path.getsize('koishi.log') > 10*1024*1024:  # 10MB限制
                with open('koishi.log', 'r', encoding='utf-8') as f:
                    return f.read()[-2000:]  # 只读最后2000个字符
            else:
                with open('koishi.log', 'r', encoding='utf-8') as f:
                    return f.read()[-2000:]
        except Exception as e:
            app.logger.error(f"读取Koishi日志时出错: {str(e)}")
            return ''

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
            
            # 更新数据库配置（在内存中）
            if 'database' in new_config:
                CONFIG['database'].update(new_config['database'])
            
            # 写入配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            # 重新生成系统提示
            CONFIG['system_prompt'] = generate_system_prompt(
                new_config.get('character', config_data['character']), 
                config_data['system_prompt_template']
            )
            
            return jsonify({'message': '配置更新成功'})
        except Exception as e:
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
    # 使用 werkzeug.make_server 启动 Flask 服务，彻底绕过 WERKZEUG_SERVER_FD 读取
    try:
        http_server = make_server('0.0.0.0', port, app)  # 绑定到所有接口
        print(Fore.CYAN + f"\n🌐 沙箱聊天模式已启动: http://localhost:{port}")

        app.logger.info(f"服务器启动于 http://localhost:{port}")
        http_server.serve_forever()
    except Exception as e:
        print(Fore.RED + f"\n❌ 服务器启动失败: {str(e)}")
        app.logger.error(f"服务器启动失败: {str(e)}")
        return 1

    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n正在关闭服务器...")
        http_server.shutdown()
        print(Fore.GREEN + "服务器已关闭。")
        return 0
    except Exception as e:
        print(Fore.RED + f"\n❌ 服务器运行出错: {str(e)}")
        app.logger.error(f"服务器运行出错: {str(e)}")
        return 1
