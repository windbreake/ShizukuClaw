# adapter_service.py
# -*- coding: utf-8 -*-
# pyright: reportMissingImports=false, reportPrivateUsage=false
# ruff: noqa: G004, BLE001, ARG001, F811, F841, SLF001
"""
Adapter 通用适配模块
"""
# pylint: disable=import-error,protected-access,broad-exception-caught
# pylint: disable=logging-fstring-interpolation,redefined-outer-name,unused-argument,unused-variable
import asyncio
import json
import socket
import threading
import time
import traceback

import uvicorn
import websockets
from colorama import Fore, Style, init
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import StreamingResponse

from app.agent.ai_chat_system import AIChatSystem
from app.core.config import CONFIG
from app.utils.logging_config import setup_logging
from app.services.onebot_reverse_ws_server import run_server as run_onebot_reverse_ws
from app.utils.shared_utils import (
    create_chat_completion_response,
    create_streaming_response_chunk,
    extract_user_input,
)

try:
    from app.agent.reply_policy import (
        can_reply_now, default_reply_policy, mark_replied,
        should_reply_to_onebot_message
    )
except ImportError:
    from app.agent.reply_policy import (
        can_reply_now, default_reply_policy, mark_replied,
        should_reply_to_onebot_message
    )

init(autoreset=True)


class _LazyChatSystemProxy:
    """Delay AIChatSystem initialization until the first real use."""

    def __init__(self):
        self._instance = None
        self._lock = threading.Lock()

    def _ensure(self):
        if self._instance is not None:
            return self._instance
        with self._lock:
            if self._instance is None:
                self._instance = AIChatSystem()
        return self._instance

    def __getattr__(self, item):
        return getattr(self._ensure(), item)

# 配置日志
logger = setup_logging('adapter_core', 'adapter_core.log')

app = FastAPI()

chat_system = _LazyChatSystemProxy()


def _chat_completion_with_retry(api_kwargs: dict, preferred_model: str = None):
    """统一走 AIChatSystem 的重试与模型回退策略。"""
    return chat_system._create_chat_completion_with_retry(
        api_kwargs,
        preferred_model=preferred_model,
    )


def _current_reply_policy() -> dict:
    return default_reply_policy(CONFIG.get('work_mode', {}).get('reply_policy', {}))


def _handle_neko_model(data: dict, request_id: str):
    """处理 Neko 模型的特殊逻辑"""
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
                    elif (isinstance(item, dict) and
                          item.get("type") == "image_url"):
                        image_data = item.get("image_url", {}).get("url")
                        logger.info(f"[{request_id}] 提取到图片 URL: {image_data}")
            else:
                user_input = content
            break

    log_msg = (f"[{request_id}] 用户输入内容: {user_input[:50]}..."
               if len(user_input) > 50
               else f"[{request_id}] 用户输入内容: {user_input}")
    logger.info(log_msg)

    response_text = chat_system.chat(user_input, image=image_data,
                                      is_admin=False)
    logger.info(f"[{request_id}] Neko 模型生成响应完成")
    return create_chat_completion_response(response_text, "neko")


def _extract_user_input_openai(messages: list) -> str:
    """从消息列表中提取最后一个用户消息"""
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            return msg.get('content', "")
    return ""


def _build_chat_api_kwargs(user_input: str, temperature: float = 0.7,
                            max_tokens: int = 200, timeout: int = 30,
                            stream: bool = False) -> dict:
    """构建聊天 API 请求参数"""
    context_messages = chat_system.build_chat_context(user_input)
    full_messages = context_messages + [{"role": "user",
                                          "content": user_input}]
    return {
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "stream": stream,
    }


def _stream_response_events(stream_resp, user_input: str, request_id: str):
    """生成流式响应事件"""
    content_accum = ""
    chunk_count = 0
    for chunk in stream_resp:
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


def _process_normal_response(response, used_model: str) -> dict:
    """处理普通模式的响应"""
    ai_response = AIChatSystem.clean_dsml_markup(
        response.choices[0].message.content)
    usage_info = getattr(response, "usage", None)
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": used_model,
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
            "completion_tokens": (usage_info.completion_tokens
                                   if usage_info else 0),
            "total_tokens": usage_info.total_tokens if usage_info else 0
        }
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容聊天完成接口"""
    request_id = f"req-{int(time.time()*1000)}"
    try:
        data = await request.json()
        logger.info(f"[{request_id}] 收到 API 请求 via /v1/chat/completions")
        logger.debug(f"[{request_id}] 请求载荷: {json.dumps(data, ensure_ascii=False)}")
        print(Fore.CYAN + f"[{request_id}] 收到请求: {data}")

        # 动态选择模型
        selected_model = data.get("model", "deepseek-chat")
        logger.info(f"[{request_id}] 选定模型: {selected_model}")

        # neko 模型专属处理
        if selected_model == "neko":
            return _handle_neko_model(data, request_id)

        # 提取用户消息 (OpenAI 兼容模式)
        messages = data.get('messages', [])
        user_input = _extract_user_input_openai(messages)
        print(Fore.GREEN + f"用户输入: {user_input}")
        logger.info(f"[{request_id}] 用户输入: {user_input}")

        stream_mode = data.get("stream", False)
        if stream_mode:
            logger.info(f"[{request_id}] 启用流式传输模式")
            api_kwargs = _build_chat_api_kwargs(user_input, stream=True)
            api_kwargs.pop("stream")  # Remove stream from context building

            stream_resp, used_model = _chat_completion_with_retry(
                {**api_kwargs, "stream": True},
                preferred_model=selected_model,
            )
            if used_model != selected_model:
                logger.info(f"[{request_id}] 模型回退触发: "
                           f"{selected_model} -> {used_model}")

            return StreamingResponse(
                _stream_response_events(stream_resp, user_input,
                                        request_id),
                media_type="text/event-stream"
            )

        # 普通模式 (非流式)
        api_kwargs = _build_chat_api_kwargs(user_input)
        logger.info(f"[{request_id}] 上下文构建完成，正在请求上游 API...")

        start_t = time.time()
        response, used_model = _chat_completion_with_retry(
            api_kwargs,
            preferred_model=selected_model,
        )
        duration = time.time() - start_t
        logger.info(f"[{request_id}] 上游 API 响应耗时: {duration:.2f}s")
        if used_model != selected_model:
            logger.info(f"[{request_id}] 模型回退触发: "
                       f"{selected_model} -> {used_model}")

        result = _process_normal_response(response, used_model)
        chat_system.db.save_chat(
            user_input,
            result['choices'][0]['message']['content']
        )
        logger.info(f"[{request_id}] 对话已保存到数据库")

        print(Fore.CYAN + f"发送响应: {result}")
        logger.info(f"[{request_id}] 请求处理完成，发送响应")
        return result

    except Exception as e:
        logger.error(f"[{request_id}] 处理请求时发生异常: {str(e)}",
                    exc_info=True)
        model_name = "deepseek-chat"
        if 'data' in locals() and data is not None:
            model_name = data.get("model", "deepseek-chat")
        return create_error_response(e, model_name,
                                      data if 'data' in locals() else None)



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
            {
                "id": "deepseek-chat", "object": "model",
                "created": int(time.time()), "owned_by": "local"
            },
            {
                "id": "deepseek-v1", "object": "model",
                "created": int(time.time()), "owned_by": "local"
            },
            {
                "id": "neko", "object": "model",
                "created": int(time.time()), "owned_by": "neko"
            }
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


def find_available_port_near(preferred_port: int, end_port: int = 5100):
    """优先使用首选端口，冲突时向后查找可用端口。"""
    try:
        preferred_port = int(preferred_port)
    except Exception:
        preferred_port = 5000
    if not is_port_in_use(preferred_port):
        return preferred_port
    return find_available_port(preferred_port + 1, end_port)


def normalize_onebot_config(cfg: dict) -> dict:
    """兼容旧版 onebot(host/port) 与新版 onebot(http/ws/ws_reverse) 配置结构。"""
    cfg = cfg if isinstance(cfg, dict) else {}
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


def extract_onebot_message_text(message):
    """兼容 OneBot 字符串与 NapCat array 消息格式，提取可读纯文本。"""
    if isinstance(message, str):
        return message.strip()

    if isinstance(message, list):
        parts = []
        for seg in message:
            if isinstance(seg, str):
                if seg.strip():
                    parts.append(seg.strip())
                continue
            if not isinstance(seg, dict):
                continue

            seg_type = str(seg.get('type', '')).strip().lower()
            data = seg.get('data', {}) if isinstance(seg.get('data', {}), dict) else {}

            if seg_type == 'text':
                txt = str(data.get('text', '')).strip()
                if txt:
                    parts.append(txt)
            elif seg_type == 'at':
                qq = str(data.get('qq', '')).strip()
                if qq:
                    parts.append(f"@{qq}")
            elif seg_type:
                # 其他类型保留占位，避免整条消息被判空。
                parts.append(f"[{seg_type}]")

        return " ".join(parts).strip()

    return ""


def normalize_reverse_ws_url(url: str) -> str:
    """Normalize a reverse WS URL to the AstrBot/NapCat OneBot v11 convention."""
    raw = str(url or '').strip()
    if not raw:
        return 'ws://127.0.0.1:6199/ws'

    if raw.startswith('http://'):
        raw = 'ws://' + raw[len('http://'):]
    elif raw.startswith('https://'):
        raw = 'wss://' + raw[len('https://'):]

    if '://' not in raw:
        raw = f'ws://{raw}'

    base, _, query = raw.partition('?')
    if base.endswith('/'):
        base = base.rstrip('/')

    if not base.endswith('/ws'):
        base = f'{base}/ws'

    if query:
        return f'{base}?{query}'
    return base


def build_ws_auth_headers(token: str) -> dict:
    """Build websocket auth headers compatible with AstrBot reverse WS."""
    token = str(token or '').strip()
    if not token:
        return {}
    return {
        'Authorization': f'Bearer {token}',
    }


def is_ws_token_valid(websocket: WebSocket, expected_token: str) -> bool:
    """兼容 NapCat 常见鉴权方式: Authorization Bearer / token / access_token(Query)。"""
    token = str(expected_token or '').strip()
    if not token:
        return True

    try:
        auth_header = str(websocket.headers.get('authorization', '') or '').strip()
        token_header = str(websocket.headers.get('token', '') or '').strip()
        query_token = str(websocket.query_params.get('access_token', '') or '').strip()

        if auth_header.lower().startswith('bearer '):
            bearer = auth_header[7:].strip()
            if bearer == token:
                return True

        return token in (token_header, query_token)
    except Exception:
        return False


def create_error_response(e, model_name, data=None):
    """创建统一的错误响应"""
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

    chat_system = _LazyChatSystemProxy()

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
                    stream_resp, _used_model = _chat_completion_with_retry(
                        {
                            "messages": full_messages,
                            "temperature": 0.7,
                            "max_tokens": 200,
                            "timeout": 30,
                            "stream": True,
                        },
                        preferred_model=selected_model,
                    )
                    for chunk in stream_resp:
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
            response, used_model = _chat_completion_with_retry(
                {
                    "messages": full_messages,
                    "temperature": 0.7,
                    "max_tokens": 200,
                    "timeout": 30,
                },
                preferred_model=selected_model,
            )
            ai_response = AIChatSystem.clean_dsml_markup(response.choices[0].message.content)
            # chat_system.messages.append({"role": "assistant", "content": ai_response})
            chat_system.db.save_chat(user_input, ai_response)

            usage_info = getattr(response, "usage", None)
            result = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": used_model,
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
                {
                    "id": "deepseek-chat", "object": "model",
                    "created": int(time.time()), "owned_by": "deepseek"
                },
                {
                    "id": "neko", "object": "model",
                    "created": int(time.time()), "owned_by": "neko"
                },
                {
                    "id": "gpt-3.5-turbo", "object": "model",
                    "created": int(time.time()), "owned_by": "neko"
                }
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
                    for char in full_response:
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
            error_trace = traceback.format_exc()
            print(Fore.RED + f"统一API错误:\n{error_trace}")

            # 返回错误信息但仍保持OpenAI格式
            return create_error_response(e, "neko")

    # 查找可用端口（优先 5000，冲突时自动顺延）
    port = find_available_port_near(5000, 5100)
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
    onebot_cfg = normalize_onebot_config(CONFIG.get('onebot', {}))

    # 当两个 WS 模式都未启用时，默认启用正向 WS 以兼容 NapCat WebSocket Client。
    ws_enabled = bool(onebot_cfg.get('ws', {}).get('enable', False))
    ws_reverse_enabled = bool(onebot_cfg.get('ws_reverse', {}).get('enable', False))
    if not ws_enabled and not ws_reverse_enabled:
        onebot_cfg.setdefault('ws', {})['enable'] = True
        logger.info("OneBot WS 与 Reverse WS 均未启用，已自动启用 OneBot WS 以兼容 NapCat WebSocket Client")

    # 1. HTTP Server
    if onebot_cfg.get('http', {}).get('enable'):
        h_host = onebot_cfg['http'].get('host', '0.0.0.0')
        h_port = int(onebot_cfg['http'].get('port', 3000) or 3000)
        if is_port_in_use(h_port):
            alt_port = find_available_port_near(h_port, h_port + 100)
            if alt_port is not None and alt_port != h_port:
                logger.warning("OneBot HTTP 端口 %s 占用，自动切换到 %s", h_port, alt_port)
                h_port = alt_port
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
                    should_reply, meta = should_reply_to_onebot_message(data, _current_reply_policy())
                    raw_msg = meta.get('message_text', '')
                    user_id = data.get('user_id')
                    persona_filename = CONFIG.get('active_persona', 'shizuku.json')

                    if not should_reply:
                        logger.debug(f"OneBot HTTP skipped: {meta.get('reason', 'not matched')}")
                        return {"status": "ok", "retcode": 0, "data": None}

                    cooldown_ok, wait_seconds = can_reply_now(meta.get('conversation_key', 'http'), _current_reply_policy().get('cooldown_seconds', 0))
                    if not cooldown_ok:
                        logger.debug(f"OneBot HTTP cooldown active: wait={wait_seconds:.1f}s")
                        return {"status": "ok", "retcode": 0, "data": None}

                    if raw_msg:
                        logger.info(f"OneBot Message from {user_id}: {raw_msg}")
                        reply = chat_system.chat(raw_msg, frontend_source='onebot', persona_filename=persona_filename, onebot_meta=meta)
                        mark_replied(meta.get('conversation_key', 'http'))
                        logger.info(f"OneBot Reply to {user_id}: {reply}")
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
        w_port = int(onebot_cfg['ws'].get('port', 3001) or 3001)
        ws_token = str(onebot_cfg.get('access_token', '') or '').strip()
        if is_port_in_use(w_port):
            alt_port = find_available_port_near(w_port, w_port + 100)
            if alt_port is not None and alt_port != w_port:
                logger.warning("OneBot WS 端口 %s 占用，自动切换到 %s", w_port, alt_port)
                w_port = alt_port
        print(Fore.YELLOW + f"► OneBot WebSocket:     ws://{w_host}:{w_port}/ws (Starting...)")

        ob_ws_app = FastAPI()

        @ob_ws_app.websocket("/")
        @ob_ws_app.websocket("/ws")
        @ob_ws_app.websocket("/ws/")
        @ob_ws_app.websocket("/onebot/v11/ws")
        @ob_ws_app.websocket("/onebot/v11/ws/")
        async def onebot_ws_endpoint(websocket: WebSocket):
            if not is_ws_token_valid(websocket, ws_token):
                await websocket.close(code=1008)
                logger.warning("OneBot WS 鉴权失败，连接已拒绝")
                return

            await websocket.accept()
            logger.info("OneBot WS Client Connected")
            try:
                while True:
                    data = await websocket.receive_text()
                    try:
                        payload = json.loads(data)
                        if payload.get('post_type') == 'message':
                            should_reply, meta = should_reply_to_onebot_message(payload, _current_reply_policy())
                            raw_msg = meta.get('message_text', '')
                            persona_filename = CONFIG.get('active_persona', 'shizuku.json')
                            if not should_reply:
                                logger.debug(f"OneBot WS skipped: {meta.get('reason', 'not matched')}")
                                continue

                            cooldown_ok, wait_seconds = can_reply_now(meta.get('conversation_key', 'ws'), _current_reply_policy().get('cooldown_seconds', 0))
                            if not cooldown_ok:
                                logger.debug(f"OneBot WS cooldown active: wait={wait_seconds:.1f}s")
                                continue

                            if raw_msg:
                                # Simple reply echoing for now or use chat_system
                                # Note: synchronous call might block loop slightly
                                reply = chat_system.chat(raw_msg, frontend_source='onebot', persona_filename=persona_filename, onebot_meta=meta)

                                message_type = payload.get('message_type', 'private')
                                params = {
                                    "message": reply,
                                    "message_type": message_type
                                }

                                if message_type == 'group':
                                    params["group_id"] = payload.get('group_id')
                                else:
                                    params["user_id"] = payload.get('user_id')

                                await websocket.send_json({
                                    "action": "send_msg",
                                    "params": params,
                                    "echo": f"reply_{int(time.time() * 1000)}"
                                })
                                mark_replied(meta.get('conversation_key', 'ws'))
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

    # 2.5 Reverse WebSocket Server (接收 NapCat 的反向连接)
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
        logger.info("OneBot Reverse WS Server 线程已启动")

    # 3. Reverse WebSocket Client
    if onebot_cfg.get('ws_reverse', {}).get('enable'):
        r_url = str(onebot_cfg['ws_reverse'].get('url', '') or '').strip()
        if not r_url:
            r_url = 'ws://127.0.0.1:6199/ws'
            logger.info("OneBot Reverse WS 未提供 URL，已默认使用 AstrBot 兼容地址 %s", r_url)
        else:
            print(Fore.YELLOW + f"► OneBot Reverse WS:    {r_url} (Starting...)")

        r_url = normalize_reverse_ws_url(r_url)
        r_token = str(onebot_cfg.get('access_token', '') or '').strip()
        r_headers = build_ws_auth_headers(r_token)
        logger.info("OneBot Reverse WS 连接目标已规范化为: %s", r_url)

        def run_reverse_ws():
            def _build_reverse_candidates(base_url: str, token: str, headers: dict):
                base_url = str(base_url or '').strip()
                token = str(token or '').strip()
                headers = headers or {}

                if not token:
                    return [
                        {'url': base_url, 'headers': {}, 'mode': 'no_token'},
                    ]

                joiner = '&' if '?' in base_url else '?'
                query_url = f"{base_url}{joiner}access_token={token}" if 'access_token=' not in base_url else base_url

                return [
                    {'url': query_url, 'headers': headers, 'mode': 'query+header'},
                    {'url': query_url, 'headers': {}, 'mode': 'query_only'},
                    {'url': base_url, 'headers': headers, 'mode': 'header_only'},
                    {'url': base_url, 'headers': {}, 'mode': 'no_auth'},
                ]

            async def _open_reverse_ws(url: str, headers: dict):
                headers = headers or {}
                if not headers:
                    return await websockets.connect(url)

                try:
                    return await websockets.connect(url, additional_headers=headers)
                except TypeError as te:
                    if 'additional_headers' in str(te) or 'unexpected keyword' in str(te):
                        return await websockets.connect(url, extra_headers=headers)
                    raise

            async def _recv_and_reply_loop(websocket):
                while True:
                    msg = await websocket.recv()
                    try:
                        payload = json.loads(msg)
                        if payload.get('post_type') == 'message':
                            should_reply, meta = should_reply_to_onebot_message(payload, _current_reply_policy())
                            raw = meta.get('message_text', '')
                            persona_filename = CONFIG.get('active_persona', 'shizuku.json')
                            if not should_reply or not raw:
                                continue

                            cooldown_ok, wait_seconds = can_reply_now(meta.get('conversation_key', 'reverse_ws'), _current_reply_policy().get('cooldown_seconds', 0))
                            if not cooldown_ok:
                                logger.debug(f"Reverse WS cooldown active: wait={wait_seconds:.1f}s")
                                continue

                            reply = chat_system.chat(raw, frontend_source='onebot', persona_filename=persona_filename, onebot_meta=meta)
                            message_type = str(payload.get('message_type', 'private') or 'private')
                            params = {
                                "message": reply,
                                "message_type": message_type,
                            }
                            if message_type == 'group':
                                params['group_id'] = payload.get('group_id') or payload.get('sender', {}).get('group_id')
                            else:
                                params['user_id'] = payload.get('user_id') or payload.get('sender', {}).get('user_id')

                            await websocket.send(json.dumps({
                                "action": "send_msg",
                                "params": params,
                                "echo": f"reply_{int(time.time() * 1000)}"
                            }, ensure_ascii=False))
                            mark_replied(meta.get('conversation_key', 'reverse_ws'))
                    except Exception as e:
                        logger.error(f"Reverse WS Msg Error: {e}")

            async def connect():
                while True:
                    candidates = _build_reverse_candidates(r_url, r_token, r_headers)
                    connected = False

                    for candidate in candidates:
                        c_url = candidate['url']
                        c_headers = candidate['headers']
                        c_mode = candidate['mode']
                        websocket = None
                        try:
                            websocket = await _open_reverse_ws(c_url, c_headers)
                            logger.info(f"Connected to Reverse WS: {c_url} (mode={c_mode})")
                            connected = True
                            await _recv_and_reply_loop(websocket)
                        except Exception as e:
                            logger.error(f"Reverse WS Connection Failed ({c_mode}): {e}")
                        finally:
                            if websocket is not None:
                                try:
                                    await websocket.close()
                                except Exception:
                                    pass

                        if connected:
                            break

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
