# adapter_service.py
# -*- coding: utf-8 -*-
"""
Adapter 通用适配模块
"""
import socket
import uvicorn
import threading
import asyncio
import websockets
from fastapi import FastAPI, Request, WebSocket
from .ai_chat_system import AIChatSystem
import time
import json
import logging
from fastapi.responses import StreamingResponse
from colorama import Fore, init
from .database import DatabaseManager
from .shared_utils import create_chat_completion_response, create_error_response, create_streaming_response_chunk, extract_user_input
from .logging_config import setup_logging
from .config import CONFIG

init(autoreset=True)

# 配置日志
logger = setup_logging('adapter_core', 'adapter_core.log')

app = FastAPI()

chat_system = AIChatSystem()
chat_system.db = DatabaseManager()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    request_id = f"req-{int(time.time()*1000)}"
    try:
        data = await request.json()
        logger.info(f"[{request_id}] 收到 API 请求 via /v1/chat/completions")
        logger.debug(f"[{request_id}] 请求载荷: {json.dumps(data, ensure_ascii=False)}")
        print(Fore.CYAN + f"[{request_id}] 收到请求: {data}")

        # 动态选择模型
        selected_model = data.get("model", "deepseek-chat")
        logger.info(f"[{request_id}] 选定模型: {selected_model}")

        # 新增：neko 模型专属处理
        if selected_model == "neko":
            logger.info(f"[{request_id}] 进入 Neko 模型独立处理流程")
            user_input = ""
            image_data = None
            for msg in reversed(data.get("messages", [])):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                user_input += item.get("text", "")
                            elif isinstance(item, dict) and item.get("type") == "image_url":
                                image_data = item.get("image_url", {}).get("url")
                                logger.info(f"[{request_id}] 提取到图片 URL: {image_data}")
                    else:
                        user_input = content
                    break
            
            logger.info(f"[{request_id}] 用户输入内容: {user_input[:50]}..." if len(user_input) > 50 else f"[{request_id}] 用户输入内容: {user_input}")

            response_text = chat_system.chat(user_input, image=image_data, is_admin=False)
            logger.info(f"[{request_id}] Neko 模型生成响应完成")
            
            return create_chat_completion_response(response_text, "neko")

        # 提取用户消息 (OpenAI 兼容模式)
        user_input = ""
        messages = data.get('messages', [])
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_input = msg.get('content', "")
                break

        print(Fore.GREEN + f"用户输入: {user_input}")
        logger.info(f"[{request_id}] 用户输入: {user_input}")

        stream_mode = data.get("stream", False)
        if stream_mode:
            logger.info(f"[{request_id}] 启用流式传输模式")
            async def event_generator():
                content_accum = ""
                
                # 动态构建上下文
                context_messages = chat_system.build_chat_context(user_input)
                full_messages = context_messages + [{"role": "user", "content": user_input}]
                logger.info(f"[{request_id}] 上下文构建完成，包含 {len(full_messages)} 条消息")
                
                # 逐块请求 API 并推送
                chunk_count = 0
                for chunk in chat_system.client.chat.completions.create(
                        model=selected_model,
                        messages=full_messages,
                        temperature=0.7, max_tokens=200, timeout=30, stream=True
                ):
                    # 修改这里，从属性读取 content
                    delta = getattr(chunk.choices[0].delta, "content", "")
                    if delta:
                        chunk_count += 1
                        content_accum += delta
                        payload = {
                            "choices": [{
                                "delta": {"content": delta},
                                "index": 0,
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                logger.info(f"[{request_id}] 流式传输完成，共发送 {chunk_count} 个数据块")
                chat_system.db.save_chat(user_input, content_accum)
                yield "data: [DONE]\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        # 普通模式 (非流式)
        # 动态构建上下文
        context_messages = chat_system.build_chat_context(user_input)
        full_messages = context_messages + [{"role": "user", "content": user_input}]
        logger.info(f"[{request_id}] 上下文构建完成，正在请求上游 API...")

        # 调用 DeepSeek 接口，使用动态模型
        start_t = time.time()
        response = chat_system.client.chat.completions.create(
            model=selected_model,
            messages=full_messages,
            temperature=0.7,
            max_tokens=200,
            timeout=30
        )
        duration = time.time() - start_t
        logger.info(f"[{request_id}] 上游 API 响应耗时: {duration:.2f}s")
        
        ai_response = AIChatSystem.clean_dsml_markup(response.choices[0].message.content)
        # chat_system.messages.append({"role": "assistant", "content": ai_response})
        chat_system.db.save_chat(user_input, ai_response)
        logger.info(f"[{request_id}] 对话已保存到数据库")

        # 提取 usage 信息
        usage_info = getattr(response, "usage", None)
        result = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": selected_model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": ai_response
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": usage_info.prompt_tokens if usage_info else 0,
                "completion_tokens": usage_info.completion_tokens if usage_info else 0,
                "total_tokens": usage_info.total_tokens if usage_info else 0
            }
        }

        print(Fore.CYAN + f"发送响应: {result}")
        logger.info(f"[{request_id}] 请求处理完成，发送响应")
        return result

    except Exception as e:
        logger.error(f"[{request_id}] 处理请求时发生异常: {str(e)}", exc_info=True)
        # 确保data变量在异常处理中可用
        model_name = "deepseek-chat"
        if 'data' in locals() and data is not None:
            model_name = data.get("model", "deepseek-chat")
        return create_error_response(e, model_name, data if 'data' in locals() else None)


@app.get("/")
async def root():
    """根路径返回服务信息"""
    return {
        "service": "Adapter API Service",
        "endpoints": [
            "/v1/chat/completions (POST)",
            "/v1/models (GET)",
            "/health (GET)"
        ]
    }


@app.get("/v1/models")
async def model_list():
    """返回支持的模型列表"""
    return {
        "object": "list",
        "data": [
            {"id": "deepseek-chat", "object": "model", "created": int(time.time()), "owned_by": "local"},
            {"id": "deepseek-v1", "object": "model", "created": int(time.time()), "owned_by": "local"},
            {"id": "neko", "object": "model", "created": int(time.time()), "owned_by": "neko"}  # 添加neko模型
        ]
    }


@app.get("/health")
async def health_check():
    """服务健康检查"""
    return {"status": "ok", "service": "Adapter API"}


def is_port_in_use(port: int) -> bool:
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)  # 设置超时时间
        try:
            s.connect(("localhost", port))
            return True
        except (socket.timeout, ConnectionRefusedError):
            return False
        except OSError:
            # 其他OSError也认为端口不可用
            return True


def find_available_port(start_port=5000, end_port=5100):
    """在指定范围内查找可用端口"""
    for port in range(start_port, end_port + 1):
        if not is_port_in_use(port):
            return port
    return None


def create_error_response(e, model_name, data=None):
    """创建统一的错误响应"""
    import traceback
    error_trace = traceback.format_exc()
    print(Fore.RED + f"完整错误信息:\n{error_trace}")
    
    # 即使出现错误，也返回有效的JSON格式
    return {
        "id": f"error-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"出错了喵({str(e)})"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }


def run_adapter_service():
    """Adapter 映射模式 (FastAPI服务)"""
    # 创建FastAPI应用
    fastapi_app = FastAPI()

    # 添加CORS中间件
    from fastapi.middleware.cors import CORSMiddleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    chat_system = AIChatSystem()
    chat_system.db = DatabaseManager()

    @fastapi_app.post("/v1/chat/completions")
    async def openai_api(request: Request):
        try:
            data = await request.json()
            print(Fore.CYAN + f"收到请求: {data}")

            # 动态选择模型，后端支持 deepseek-chat / deepseek-vl / o4-mini-preview
            selected_model = data.get("model", "deepseek-chat")

            # 新增：neko 模型专属处理
            if selected_model == "neko":
                user_input = ""
                image_data = None
                for msg in reversed(data.get("messages", [])):
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    user_input += item.get("text", "")
                                elif isinstance(item, dict) and item.get("type") == "image_url":
                                    image_data = item.get("image_url", {}).get("url")
                        else:
                            user_input = content
                        break

                # 网关请求被视为非管理员操作，禁止使用Agent工具 (is_admin=False)
                response_text = chat_system.chat(user_input, image=image_data, is_admin=False)
                return {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": "neko",
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop"
                    }],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                }

            # 提取用户消息
            user_input = ""
            messages = data.get('messages', [])
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    user_input = msg.get('content', "")
                    break
            print(Fore.GREEN + f"用户输入: {user_input}")

            stream_mode = data.get("stream", False)
            if stream_mode:
                async def event_generator():
                    content_accum = ""
                    
                    # 动态构建上下文
                    context_messages = chat_system.build_chat_context(user_input)
                    full_messages = context_messages + [{"role": "user", "content": user_input}]
                    
                    # 逐块请求 API 并推送
                    for chunk in chat_system.client.chat.completions.create(
                            model=selected_model,
                            messages=full_messages,
                            temperature=0.7, max_tokens=200, timeout=30, stream=True
                    ):
                        # 修改这里，从属性读取 content
                        delta = getattr(chunk.choices[0].delta, "content", "")
                        if delta:
                            content_accum += delta
                            payload = {
                                "choices": [{
                                    "delta": {"content": delta},
                                    "index": 0,
                                    "finish_reason": None
                                }]
                            }
                            yield f"data: {json.dumps(payload)}\n\n"
                    chat_system.db.save_chat(user_input, content_accum)
                    yield "data: [DONE]\n\n"

                return StreamingResponse(event_generator(), media_type="text/event-stream")

            # 动态构建上下文
            context_messages = chat_system.build_chat_context(user_input)
            full_messages = context_messages + [{"role": "user", "content": user_input}]

            # 调用 DeepSeek 接口，使用动态模型
            response = chat_system.client.chat.completions.create(
                model=selected_model,
                messages=full_messages,
                temperature=0.7,
                max_tokens=200,
                timeout=30
            )
            ai_response = AIChatSystem.clean_dsml_markup(response.choices[0].message.content)
            # chat_system.messages.append({"role": "assistant", "content": ai_response})
            chat_system.db.save_chat(user_input, ai_response)

            usage_info = getattr(response, "usage", None)
            result = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": selected_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": ai_response
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": usage_info.prompt_tokens if usage_info else 0,
                    "completion_tokens": usage_info.completion_tokens if usage_info else 0,
                    "total_tokens": usage_info.total_tokens if usage_info else 0
                }
            }
            print(Fore.CYAN + f"发送响应: {result}")
            return result

        except Exception as e:
            # 确保data变量在异常处理中可用
            model_name = "deepseek-chat"
            if 'data' in locals() and data is not None:
                model_name = data.get("model", "deepseek-chat")
            return create_error_response(e, model_name, data if 'data' in locals() else None)

    @fastapi_app.get("/")
    async def root():
        """根路径返回服务信息"""
        return {
            "service": "Adapter API Service",
            "endpoints": [
                "/v1/chat/completions (POST)",
                "/v1/models (GET)",
                "/health (GET)"
            ]
        }

    @fastapi_app.get("/v1/models")
    async def model_list():
        """返回支持的模型列表"""
        return {
            "object": "list",
            "data": [
                {"id": "deepseek-chat", "object": "model", "created": int(time.time()), "owned_by": "deepseek"},
                {"id": "neko", "object": "model", "created": int(time.time()), "owned_by": "neko"},  # 添加neko模型
                {"id": "gpt-3.5-turbo", "object": "model", "created": int(time.time()), "owned_by": "neko"}
            ]
        }

    @fastapi_app.get("/health")
    async def inner_health_check():
        """服务健康检查"""
        return {"status": "ok", "service": "Adapter API"}

    # 统一API接口，隐藏后端多个API的复杂性
    @fastapi_app.post("/v1/unified/chat/completions")
    async def unified_chat_completions(request: Request):
        """
        统一聊天完成接口
        前端可以像调用单一模型一样调用此接口，
        后端会根据内容自动决定调用哪些API（文本、图像识别、网络搜索等）
        """
        try:
            data = await request.json()
            print(Fore.CYAN + f"收到统一API请求: {data}")

            # 提取用户消息
            messages = data.get('messages', [])
            user_input, image_urls = extract_user_input(messages)

            print(Fore.GREEN + f"处理后用户输入: {user_input}")
            print(Fore.GREEN + f"提取到图片URL: {image_urls}")

            stream_mode = data.get("stream", False)
            if stream_mode:
                async def event_generator():
                    # 调用AI聊天系统处理（会自动处理图片和搜索等）
                    # 对于流式响应，我们先生成一个完整的回复，然后逐字发送
                    if image_urls:
                        # 如果有图片URL，传递第一张图片
                        full_response = chat_system.chat(user_input, image=image_urls[0])
                    else:
                        # 否则只处理文本
                        full_response = chat_system.chat(user_input)
                    
                    # 逐字发送响应
                    for i, char in enumerate(full_response):
                        payload = create_streaming_response_chunk(char)
                        yield f"data: {json.dumps(payload)}\n\n"
                    
                    # 发送结束标记
                    yield "data: [DONE]\n\n"

                return StreamingResponse(event_generator(), media_type="text/event-stream")

            # 调用AI聊天系统处理（会自动处理图片和搜索等）
            if image_urls:
                # 如果有图片URL，传递第一张图片
                response_text = chat_system.chat(user_input, image=image_urls[0])
            else:
                # 否则只处理文本
                response_text = chat_system.chat(user_input)

            # 构造符合OpenAI格式的响应
            result = create_chat_completion_response(response_text, "neko")
            
            print(Fore.CYAN + f"发送统一API响应: {result}")
            return result

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(Fore.RED + f"统一API错误:\n{error_trace}")
            
            # 返回错误信息但仍保持OpenAI格式
            return create_error_response(e, "neko")

    # 查找可用端口
    port = find_available_port()
    if port is None:
        print(Fore.RED + "错误: 没有找到可用端口 (5000-5100)")
        return

    logger.info(f"Adapter 服务正在启动，端口: {port}")
    
    # 打印网络环境提示
    print(Fore.YELLOW + "提示: 如果连接失败，请检查是否设置了 HTTP_PROXY/HTTPS_PROXY 环境变量")
    print(Fore.YELLOW + "      本地连接建议设置 NO_PROXY=localhost,127.0.0.1")
    
    # 获取融合后的API Key (显示部分掩码)
    api_key = CONFIG['api'].get('key', 'sk-unknown')
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else api_key
    
    # 打印详细banner
    from colorama import Style
    banner = f"""
{Fore.CYAN}================================================================
   Universal Adapter Service Started Successfully!
================================================================{Style.RESET_ALL}
{Fore.GREEN}► Status:{Style.RESET_ALL}       Online
{Fore.GREEN}► Base URL:{Style.RESET_ALL}     http://127.0.0.1:{port}/v1
{Fore.GREEN}► API Key:{Style.RESET_ALL}      {masked_key} (Fused)
{Fore.GREEN}► Models:{Style.RESET_ALL}       deepseek-chat, neko, gpt-3.5-turbo (Compatible)
{Fore.GREEN}► Docs:{Style.RESET_ALL}         http://127.0.0.1:{port}/docs
{Fore.GREEN}► Integration:{Style.RESET_ALL}  Set 'openai.base_url' in your bot to above URL
{Fore.CYAN}================================================================{Style.RESET_ALL}
"""
    # 同时输出到日志和控制台
    logger.info("Service banner displayed")
    print(banner)

    # OneBot Connection Configuration Check
    onebot_cfg = CONFIG.get('onebot', {})
    
    # 1. HTTP Server
    if onebot_cfg.get('http', {}).get('enable'):
        h_host = onebot_cfg['http'].get('host', '0.0.0.0')
        h_port = onebot_cfg['http'].get('port', 3000)
        print(Fore.YELLOW + f"► OneBot HTTP Server:   http://{h_host}:{h_port} (Starting...)")
        
        # Define a simple FastAPI app for OneBot HTTP
        ob_http_app = FastAPI()
        
        @ob_http_app.post("/")
        @ob_http_app.post("/post")
        async def onebot_http_handler(request: Request):
            try:
                data = await request.json()
                msg_type = data.get('post_type')
                
                if msg_type == 'message':
                    # Extract message
                    raw_msg = data.get('message') or data.get('raw_message', '')
                    user_id = data.get('user_id')
                    
                    if raw_msg:
                        logger.info(f"OneBot Message from {user_id}: {raw_msg}")
                        # Process with AI
                        reply = chat_system.chat(raw_msg)
                        logger.info(f"OneBot Reply to {user_id}: {reply}")
                        
                        # Return quick response (if supported by implementation)
                        return {"reply": reply, "block": True, "at_sender": False}
                
                return {"status": "ok", "retcode": 0, "data": None}
            except Exception as e:
                logger.error(f"OneBot HTTP Handler Error: {e}")
                return {"status": "failed", "retcode": -1, "msg": str(e)}

        def run_ob_http():
            try:
                # Use a new loop if needed, but uvicorn handles it
                uvicorn.run(ob_http_app, host=h_host, port=h_port, log_level="warning")
            except Exception as e:
                logger.error(f"OneBot HTTP Server Error: {e}")

        t_http = threading.Thread(target=run_ob_http, daemon=True)
        t_http.start()

    # 2. WebSocket Server
    if onebot_cfg.get('ws', {}).get('enable'):
        w_host = onebot_cfg['ws'].get('host', '0.0.0.0')
        w_port = onebot_cfg['ws'].get('port', 3001)
        print(Fore.YELLOW + f"► OneBot WebSocket:     ws://{w_host}:{w_port} (Starting...)")
        
        ob_ws_app = FastAPI()

        @ob_ws_app.websocket("/")
        @ob_ws_app.websocket("/onebot/v11/ws")
        async def onebot_ws_endpoint(websocket: WebSocket):
            await websocket.accept()
            logger.info("OneBot WS Client Connected")
            try:
                while True:
                    data = await websocket.receive_text()
                    try:
                        payload = json.loads(data)
                        if payload.get('post_type') == 'message':
                            raw_msg = payload.get('message')
                            if raw_msg:
                                # Simple reply echoing for now or use chat_system
                                # Note: synchronous call might block loop slightly
                                reply = chat_system.chat(raw_msg)
                                await websocket.send_json({
                                    "action": "send_msg",
                                    "params": {
                                        "user_id": payload.get('user_id'),
                                        "message": reply,
                                        "message_type": payload.get('message_type', 'private')
                                    }
                                })
                    except Exception as e:
                        logger.error(f"OneBot WS Processing Error: {e}")
            except Exception as e:
                logger.debug(f"OneBot WS Disconnect: {e}")

        def run_ob_ws():
            try:
                uvicorn.run(ob_ws_app, host=w_host, port=w_port, log_level="warning")
            except Exception as e:
                logger.error(f"OneBot WS Server Error: {e}")

        t_ws = threading.Thread(target=run_ob_ws, daemon=True)
        t_ws.start()

    # 3. Reverse WebSocket Client
    if onebot_cfg.get('ws_reverse', {}).get('enable'):
        r_url = onebot_cfg['ws_reverse'].get('url', '')
        print(Fore.YELLOW + f"► OneBot Reverse WS:    {r_url} (Starting...)")
        
        def run_reverse_ws():
            async def connect():
                while True:
                    try:
                        async with websockets.connect(r_url) as websocket:
                            logger.info(f"Connected to Reverse WS: {r_url}")
                            while True:
                                msg = await websocket.recv()
                                try:
                                    payload = json.loads(msg)
                                    if payload.get('post_type') == 'message':
                                        raw = payload.get('message')
                                        if raw:
                                            reply = chat_system.chat(raw)
                                            await websocket.send(json.dumps({
                                                "action": "send_msg",
                                                "params": {
                                                    "user_id": payload.get('user_id'),
                                                    "message": reply,
                                                    "message_type": payload.get('message_type', 'private')
                                                }
                                            }))
                                except Exception as e:
                                    logger.error(f"Reverse WS Msg Error: {e}")

                    except Exception as e:
                        logger.error(f"Reverse WS Connection Failed: {e}")
                        await asyncio.sleep(5) # Retry delay

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(connect())
            except Exception as e:
                logger.error(f"Reverse WS Loop Error: {e}")

        t_rev = threading.Thread(target=run_reverse_ws, daemon=True)
        t_rev.start()

    # Use 0.0.0.0 to listen on all interfaces (IPv4)
    # This often resolves issues where localhost resolves to ::1 (IPv6)
    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        timeout_keep_alive=120
    )
