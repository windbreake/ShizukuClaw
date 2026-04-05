# -*- coding: utf-8 -*-
"""
OneBot 反向 WebSocket 服务器
独立的 WebSocket 服务器，接收 NapCat 的反向连接
"""
import asyncio
import json
import logging
import websockets
from urllib.parse import parse_qs, urlparse

try:
    from .reply_policy import can_reply_now, default_reply_policy, mark_replied, should_reply_to_onebot_message
except ImportError:
    from reply_policy import can_reply_now, default_reply_policy, mark_replied, should_reply_to_onebot_message
try:
    from .config import CONFIG
except ImportError:
    from config import CONFIG

logger = logging.getLogger('OneBot-ReverseWS')


class OneBotReverseWSServer:
    """OneBot 反向 WebSocket 服务器"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 8000, token: str = '', chat_system=None):
        """
        初始化服务器
        
        Args:
            host: 绑定 IP 地址
            port: 绑定端口
            token: 访问令牌（可选）
            chat_system: 聊天系统实例
        """
        self.host = host
        self.port = port
        self.token = token
        self.chat_system = chat_system

    def _current_reply_policy(self):
        try:
            return default_reply_policy(CONFIG.get('work_mode', {}).get('reply_policy', {}))
        except Exception:
            return default_reply_policy({})

    def _current_persona_filename(self):
        try:
            return str(CONFIG.get('active_persona', 'shizuku.json') or 'shizuku.json').strip() or 'shizuku.json'
        except Exception:
            return 'shizuku.json'
        
    async def handle_client(self, websocket, path=None):
        """处理客户端连接"""
        client_addr = websocket.remote_address
        logger.info(f"[{client_addr}] OneBot Reverse WS 客户端已连接")
        
        try:
            # 兼容不同 websockets 版本的 path / headers 访问方式
            ws_path = path
            if ws_path is None:
                ws_path = getattr(websocket, 'path', None)
            if ws_path is None and hasattr(websocket, 'request'):
                ws_path = getattr(websocket.request, 'path', None)
            if not ws_path:
                ws_path = '/'

            request_headers = {}
            if hasattr(websocket, 'request_headers'):
                request_headers = websocket.request_headers
            elif hasattr(websocket, 'request') and hasattr(websocket.request, 'headers'):
                request_headers = websocket.request.headers

            # 鉴权检查
            if self.token:
                # 支持 Authorization header 与 query(access_token/token)
                auth_header = ''
                if request_headers:
                    auth_header = request_headers.get('Authorization', '') or request_headers.get('authorization', '')

                parsed = urlparse(str(ws_path))
                query = parse_qs(parsed.query)
                query_token = (query.get('access_token', [''])[0] or query.get('token', [''])[0] or '').strip()

                expected_auth = f"Bearer {self.token}"

                auth_ok = (auth_header == expected_auth) or (query_token == self.token)
                if not auth_ok:
                    logger.warning(f"[{client_addr}] 鉴权失败: path={ws_path}, auth_header={auth_header}, query_token={'***' if query_token else ''}")
                    await websocket.close(code=1008, reason="Unauthorized")
                    return

            logger.info(f"[{client_addr}] OneBot Reverse WS 鉴权通过: path={ws_path}")
            
            # 处理消息
            async for message in websocket:
                try:
                    # 解析 JSON
                    if isinstance(message, bytes):
                        payload = json.loads(message.decode('utf-8'))
                    else:
                        payload = json.loads(message)
                    
                    logger.debug(f"[{client_addr}] 收到消息: {payload.get('post_type', 'unknown')}")
                    
                    # 处理连接事件
                    if payload.get('post_type') == 'meta' and payload.get('detail_type') == 'connect':
                        logger.info(f"[{client_addr}] 收到 meta.connect 事件")
                    
                    # 处理消息事件
                    elif payload.get('post_type') == 'message':
                        await self._handle_message(websocket, payload, client_addr)
                    
                except json.JSONDecodeError:
                    logger.error(f"[{client_addr}] JSON 解析失败: {message}")
                except Exception as e:
                    logger.error(f"[{client_addr}] 消息处理错误: {e}", exc_info=True)
        
        except asyncio.CancelledError:
            logger.debug(f"[{client_addr}] 连接被取消")
        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"[{client_addr}] 连接已关闭")
        except Exception as e:
            logger.error(f"[{client_addr}] 处理异常: {e}", exc_info=True)
    
    async def _handle_message(self, websocket, payload: dict, client_addr):
        """处理消息事件"""
        try:
            # 提取消息文本
            policy = self._current_reply_policy()
            should_reply, meta = should_reply_to_onebot_message(payload, policy)
            raw_msg = meta.get('message_text', '')
            
            if not raw_msg:
                logger.debug(f"[{client_addr}] 消息为空，跳过处理")
                return

            if not should_reply:
                logger.debug(f"[{client_addr}] 不满足回复条件: {meta.get('reason', 'not matched')}")
                return

            cooldown_ok, wait_seconds = can_reply_now(meta.get('conversation_key', f'ws:{client_addr}'), policy.get('cooldown_seconds', 0))
            if not cooldown_ok:
                logger.debug(f"[{client_addr}] 冷却中，跳过回复: wait={wait_seconds:.1f}s")
                return
            
            logger.info(f"[{client_addr}] 消息: {raw_msg}")
            
            # 调用聊天系统
            if self.chat_system:
                reply = self.chat_system.chat(raw_msg, frontend_source='onebot', persona_filename=self._current_persona_filename(), onebot_meta=meta)
                logger.info(f"[{client_addr}] 回复: {reply}")
                
                # 构造回复
                message_type = payload.get('message_type', 'private')
                user_id = payload.get('user_id')
                group_id = payload.get('group_id')
                
                response = {
                    "action": "send_msg",
                    "params": {
                        "message": reply,
                        "message_type": message_type,
                    },
                    "echo": f"reply_{id(websocket)}"
                }
                
                if message_type == 'group' and group_id:
                    response["params"]["group_id"] = group_id
                elif user_id:
                    response["params"]["user_id"] = user_id
                
                # 发送回复
                await websocket.send(json.dumps(response, ensure_ascii=False))
                mark_replied(meta.get('conversation_key', f'ws:{client_addr}'))
                logger.debug(f"[{client_addr}] 已发送回复")
            else:
                logger.warning(f"[{client_addr}] 聊天系统未初始化")
        
        except Exception as e:
            logger.error(f"[{client_addr}] 消息处理异常: {e}", exc_info=True)
    
    async def start(self):
        """启动服务器"""
        try:
            async with websockets.serve(self.handle_client, self.host, self.port, ping_interval=20):
                logger.info(f"OneBot Reverse WS Server 已启动在 ws://{self.host}:{self.port}")
                print(f"✓ OneBot Reverse WS Server 已启动在 ws://{self.host}:{self.port}")
                await asyncio.Future()  # run forever
        except OSError as e:
            if 'Address already in use' in str(e) or 'Only one usage of each socket address' in str(e):
                logger.warning(f"端口 {self.port} 已被占用")
                print(f"⚠ 端口 {self.port} 已被占用，跳过启动反向 WS 服务器")
            else:
                logger.error(f"启动失败: {e}")
                raise
        except Exception as e:
            logger.error(f"异常: {e}", exc_info=True)
            raise


def run_server(host: str = '127.0.0.1', port: int = 8000, token: str = '', chat_system=None):
    """在事件循环中运行服务器"""
    try:
        server = OneBotReverseWSServer(host, port, token, chat_system)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.start())
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器异常: {e}", exc_info=True)


if __name__ == '__main__':
    # 测试运行
    import logging.config
    
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
    )
    
    run_server()
