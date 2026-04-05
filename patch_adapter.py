# -*- coding: utf-8 -*-
"""
自动修复 adapter_service.py 以支持独立的反向 WS 服务器
"""
import re

def patch_adapter_service():
    filepath = 'src/adapter_service.py'
    
    # 读取文件
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 添加导入（如果还没有的话）
    if 'from .onebot_reverse_ws_server import' not in content:
        # 在现有导入后添加
        import_line = "from .logging_config import setup_logging"
        if import_line in content:
            content = content.replace(
                import_line,
                import_line + "\nfrom .onebot_reverse_ws_server import run_server as run_onebot_reverse_ws"
            )
    
    # 2. 替换 2.5 反向 WS 服务器部分
    # 找到并替换长的脚本部分
    old_pattern = r'# 2\.5 Reverse WebSocket Server.*?logger\.debug\("OneBot Reverse WS Server 后台线程已启动"\)'
    
    new_code = '''# 2.5 Reverse WebSocket Server (接收 NapCat 的反向连接)
    rws_recv_host = onebot_cfg.get('host', '0.0.0.0')
    rws_recv_port = 8000  # NapCat 期望反向 WS 服务端在 8000 端口
    rws_recv_token = str(onebot_cfg.get('access_token', '') or '').strip()
    
    if rws_recv_port:
        print(Fore.YELLOW + f"► OneBot Reverse WS Server: ws://{rws_recv_host}:{rws_recv_port}/ws (Starting...)")
        
        # 使用独立的反向 WS 服务器
        bind_host = '127.0.0.1' if rws_recv_host == '0.0.0.0' else rws_recv_host
        
        def start_reverse_ws():
            try:
                run_onebot_reverse_ws(
                    host=bind_host,
                    port=rws_recv_port,
                    token=rws_recv_token,
                    chat_system=chat_system
                )
            except Exception as e:
                logger.error(f"OneBot Reverse WS Server 启动失败: {e}")
        
        t_rws = threading.Thread(target=start_reverse_ws, daemon=True, name="OneBot-ReverseWS")
        t_rws.start()
        logger.info("OneBot Reverse WS Server 线程已启动")'''
    
    content = re.sub(old_pattern, new_code, content, flags=re.DOTALL)
    
    # 写回文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ adapter_service.py 已自动修复")

if __name__ == '__main__':
    patch_adapter_service()
