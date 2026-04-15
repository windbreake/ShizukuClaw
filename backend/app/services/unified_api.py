"""Unified API service bridging chat, search, image and video workflows."""

# pylint: disable=wrong-import-position,logging-fstring-interpolation,
# pylint: disable=broad-exception-caught,too-many-return-statements,
# pylint: disable=too-many-statements,inconsistent-return-statements,
# pylint: disable=line-too-long,trailing-whitespace,reimported

import base64
import json
import logging
import os
import sys
import traceback
import time
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response


def _ensure_stdio_streams() -> None:
    """Fix Invalid argument issue for detached Windows console handles."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        try:
            stream.fileno()
        except OSError:
            # Keep a writable fallback stream for detached Windows console mode.
            # pylint: disable=consider-using-with
            setattr(sys, stream_name, open(os.devnull, "w", encoding="utf-8"))


_ensure_stdio_streams()


# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 配置日志
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler('unified_api.log', maxBytes=1000000, backupCount=1, encoding='utf-8')
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# 从配置获取API密钥和基础URL
from app.core.config import CONFIG
from app.utils.shared_utils import create_chat_completion_response, create_error_response, extract_user_input, should_search

DEFAULT_HTTP_TIMEOUT = 60


def _post_json(url: str, headers: dict, payload: dict, timeout: int = DEFAULT_HTTP_TIMEOUT):
    """统一 POST JSON 请求，避免各分支重复参数拼装。"""
    return requests.post(url, headers=headers, json=payload, timeout=timeout)


def _analyze_image_and_merge_prompt(user_input: str, image_urls: list) -> str:
    """分析首张图片并将描述拼接回用户输入。"""
    if not image_urls:
        return user_input

    app.logger.info("开始处理图片...")
    image_url = image_urls[0]
    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image_data = base64.b64encode(response.content).decode('utf-8')

        headers = {
            "Authorization": f"Bearer {CONFIG['aliyun_api']['key']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "qwen-vl-max",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": f"data:image/jpeg;base64,{image_data}"},
                            {"text": "请详细描述这张图片的内容"},
                        ],
                    }
                ]
            },
            "parameters": {"max_tokens": 300},
        }

        app.logger.info("调用阿里云通义VL MAX进行图片分析")
        api_response = _post_json(
            f"{CONFIG['aliyun_api']['base_url']}/services/aigc/multimodal-generation/generation",
            headers=headers,
            payload=payload,
        )

        if api_response.status_code != 200:
            app.logger.error(f"图片分析API失败: {api_response.text}")
            return f"[图片分析失败] {user_input}"

        result = api_response.json()
        if "output" not in result or "choices" not in result["output"]:
            return user_input

        content = result["output"]["choices"][0]["message"]["content"]
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)
            image_description = " ".join(text_parts)
        else:
            image_description = str(content)

        app.logger.info(f"图片分析成功: {image_description[:50]}...")
        return f"[图片内容: {image_description}] {user_input}"
    except Exception as exc:
        app.logger.error(f"图片处理异常: {exc}")
        return f"[图片处理出错] {user_input}"


def _search_and_merge_prompt(user_input: str) -> str:
    """根据搜索意图调用联网搜索，并拼接结果。"""
    if not should_search(user_input):
        return user_input

    app.logger.info("检测到搜索意图，开始联网搜索...")
    try:
        headers = {
            "Authorization": f"Bearer {CONFIG['search_api']['key']}",
            "Content-Type": "application/json",
        }
        kimi_messages = [
            {"role": "system", "content": "你是 Kimi，由 Moonshot AI 提供支持的人工智能助手。"},
            {"role": "user", "content": user_input},
        ]
        kimi_payload = {
            "model": "kimi-k2-0905-preview",
            "messages": kimi_messages,
            "temperature": 0.6,
            "max_tokens": 32768,
            "tools": [
                {
                    "type": "builtin_function",
                    "function": {"name": "$web_search"},
                }
            ],
        }

        app.logger.info("调用 Kimi API 搜索...")
        kimi_response = _post_json(
            f"{CONFIG['search_api']['base_url']}/chat/completions",
            headers=headers,
            payload=kimi_payload,
        )
        if kimi_response.status_code != 200:
            app.logger.error(f"Kimi API错误: {kimi_response.text}")
            return user_input

        result = kimi_response.json()
        if not (result.get("choices") and len(result["choices"]) > 0):
            return user_input

        choice = result["choices"][0]
        if choice.get("finish_reason") != "tool_calls":
            return user_input
        if not (choice.get("message") and choice["message"].get("tool_calls")):
            return user_input

        for tool_call in choice["message"]["tool_calls"]:
            if tool_call["function"]["name"] != "$web_search":
                continue

            tool_call_id = tool_call["id"]
            tool_call_arguments = json.loads(tool_call["function"]["arguments"])
            app.logger.info(f"执行搜索工具: {tool_call_arguments}")

            kimi_messages.append(choice["message"])
            kimi_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": "$web_search",
                    "content": json.dumps(tool_call_arguments),
                }
            )

            kimi_payload["messages"] = kimi_messages
            final_response = _post_json(
                f"{CONFIG['search_api']['base_url']}/chat/completions",
                headers=headers,
                payload=kimi_payload,
            )
            if final_response.status_code != 200:
                return user_input

            final_result = final_response.json()
            if not (final_result.get("choices") and len(final_result["choices"]) > 0):
                return user_input

            final_choice = final_result["choices"][0]
            if final_choice.get("message") and final_choice["message"].get("content"):
                search_result = final_choice["message"]["content"]
                app.logger.info("搜索完成，已整合结果")
                return f"用户问题: {user_input}\n搜索结果: {search_result}"
            return user_input
        return user_input
    except Exception as exc:
        app.logger.error(f"搜索过程异常: {exc}")
        return user_input


def _is_image_generation_request(user_input: str) -> bool:
    return any(k in user_input for k in ("画", "生成图片", "画一张", "绘图"))


def _is_video_generation_request(user_input: str) -> bool:
    return any(k in user_input for k in ("视频", "生成视频", "制作视频"))


def _try_generate_image_response(user_input: str):
    if not (_is_image_generation_request(user_input) and CONFIG['image_generation_api']['key']):
        return None

    app.logger.info("检测到图片生成请求")
    try:
        image_headers = {
            "Authorization": f"Bearer {CONFIG['image_generation_api']['key']}",
            "Content-Type": "application/json",
        }
        image_payload = {"prompt": user_input, "n": 1, "size": "1024x1024"}
        image_response = _post_json(
            f"{CONFIG['image_generation_api']['base_url']}/images/generations",
            headers=image_headers,
            payload=image_payload,
        )
        if image_response.status_code != 200:
            app.logger.error(f"图片生成API失败: {image_response.text}")
            return None

        result = image_response.json()
        response_content = "我为您生成了图片:\n"
        if "data" in result and len(result["data"]) > 0:
            response_content += f"![生成的图片]({result['data'][0]['url']})\n"
            if "revised_prompt" in result["data"][0]:
                response_content += f"优化后的提示词: {result['data'][0]['revised_prompt']}\n"
        return jsonify(create_chat_completion_response(response_content, "neko-image-generator"))
    except Exception as exc:
        app.logger.error(f"图片生成异常: {exc}")
        return None


def _try_generate_video_response(user_input: str):
    if not (
        _is_video_generation_request(user_input)
        and CONFIG['video_generation_api']['key']
        and CONFIG['video_generation_api']['base_url']
    ):
        return None

    app.logger.info("检测到视频生成请求")
    try:
        video_headers = {
            "Authorization": f"Bearer {CONFIG['video_generation_api']['key']}",
            "Content-Type": "application/json",
        }
        video_payload = {"prompt": user_input, "duration": 5}
        video_response = _post_json(
            f"{CONFIG['video_generation_api']['base_url']}/videos/generations",
            headers=video_headers,
            payload=video_payload,
        )
        if video_response.status_code != 200:
            return None

        result = video_response.json()
        response_content = "我为您生成了视频:\n"
        if "data" in result and len(result["data"]) > 0:
            response_content += f"视频链接: {result['data'][0]['url']}\n"
            if "revised_prompt" in result["data"][0]:
                response_content += f"优化后的提示词: {result['data'][0]['revised_prompt']}\n"
        return jsonify(create_chat_completion_response(response_content, "neko-video-generator"))
    except Exception as exc:
        app.logger.error(f"视频生成异常: {exc}")
        return None


def _build_chat_payload(user_input: str) -> dict:
    """Build base chat payload and inject optional system prompt."""
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": user_input}],
        "temperature": 0.7,
        "max_tokens": 500,
    }
    if 'system_prompt' in CONFIG and CONFIG['system_prompt']:
        has_system = any(m.get('role') == 'system' for m in payload['messages'])
        if not has_system:
            payload['messages'].insert(0, {"role": "system", "content": CONFIG['system_prompt']})
    return payload


# 中间件函数：验证自定义API key
def authenticate():
    """Validate proxy API key from Authorization header."""
    proxy_key = request.headers.get('Authorization')
    if proxy_key:
        # 提取Bearer token
        if proxy_key.startswith('Bearer '):
            proxy_key = proxy_key[7:]  # 移除'Bearer '前缀
    
    # 动态获取有效Keys
    valid_key = CONFIG['unified_api'].get('access_token', 'neko-proxy-key-123')
    
    if not proxy_key or proxy_key not in (valid_key, '114514'):  # 114514 保留为调试后门
        app.logger.warning(f"认证失败: 无效的 API Key - {proxy_key}")
        return jsonify({'error': 'Invalid API key'}), 401
    return None  # 通过验证


@app.before_request
def before_request():
    """Authenticate incoming requests except health/model endpoints."""
    # 对于非健康检查和模型列表的请求进行身份验证
    if request.endpoint not in ['health_check', 'model_list']:
        auth_error = authenticate()
        if auth_error:
            return auth_error
    
    app.logger.info(f"收到请求: {request.method} {request.path} from {request.remote_addr}")


@app.route('/v1/models', methods=['GET'])
def model_list():
    """返回支持的模型列表"""
    app.logger.info("请求模型列表")
    return jsonify({
        "object": "list",
        "data": [
            {"id": "neko", "object": "model", "created": int(time.time()), "owned_by": "neko"},
            {"id": "gpt-3.5-turbo", "object": "model", "created": int(time.time()), "owned_by": "neko"}
        ]
    })


@app.route('/health', methods=['GET'])
def health_check():
    """服务健康检查"""
    return jsonify({"status": "ok", "service": "Unified API"})


@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """统一聊天完成接口"""
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify(create_error_response(ValueError("JSON body must be an object"))), 400
        app.logger.info("收到统一API聊天请求")
        app.logger.debug(f"请求数据: {json.dumps(data, ensure_ascii=False)}")
        print(f"收到统一API请求: {data}")

        # 提取用户消息
        messages = data.get('messages', [])
        user_input, image_urls = extract_user_input(messages)

        app.logger.info(f"用户输入: {user_input}")
        if image_urls:
            app.logger.info(f"包含图片URL: {image_urls}")

        print(f"处理后用户输入: {user_input}")
        print(f"提取到图片URL: {image_urls}")
        user_input = _analyze_image_and_merge_prompt(user_input, image_urls)
        user_input = _search_and_merge_prompt(user_input)

        image_resp = _try_generate_image_response(user_input)
        if image_resp is not None:
            return image_resp

        video_resp = _try_generate_video_response(user_input)
        if video_resp is not None:
            return video_resp

        headers = {
            "Authorization": f"Bearer {CONFIG['api']['key']}",
            "Content-Type": "application/json"
        }
        payload = _build_chat_payload(user_input)

        # 检查是否需要流式响应
        stream_mode = data.get("stream", False)

        if stream_mode:
            def generate():
                try:
                    with requests.post(
                        f"{CONFIG['api']['base_url']}/chat/completions",
                        headers=headers,
                        json=payload,
                        stream=True,
                        timeout=60
                    ) as resp:
                        if resp.status_code != 200:
                            err_msg = f"Upstream API Error: {resp.status_code} {resp.text}"
                            app.logger.error(err_msg)
                            yield f"data: {json.dumps({'choices': [{'delta': {'content': err_msg}, 'finish_reason': 'stop'}]})}\n\n"
                            yield "data: [DONE]\n\n"
                            return

                        for line in resp.iter_lines():
                            if line:
                                line = line.decode('utf-8')
                                if line.startswith('data: '):
                                    yield line + "\n\n"
                except Exception as ex:
                    app.logger.error(f"Stream Error: {ex}")
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': f'Stream Error: {ex}'}, 'finish_reason': 'stop'}]})}\n\n"
                    yield "data: [DONE]\n\n"

            return Response(generate(), mimetype='text/event-stream')

        # 发送请求到DeepSeek API
        api_response = _post_json(
            f"{CONFIG['api']['base_url']}/chat/completions",
            headers=headers,
            payload=payload,
        )


        if api_response.status_code == 200:
            result = api_response.json()
            # 修改模型名称为neko
            result["model"] = "neko"
            return jsonify(result)
        return jsonify(create_error_response(Exception(f"{api_response.status_code} - {api_response.text}")))

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"统一API错误:\n{error_trace}")

        # 返回错误信息但仍保持OpenAI格式
        return jsonify(create_error_response(e))


if __name__ == '__main__':
    from app.utils.logging_config import setup_logging
    # Configure logger
    logger = setup_logging('unified_api', 'unified_api.log')
    
    # Print Banner
    from colorama import Fore, Style, init
    init(autoreset=True)
    
    port = CONFIG.get('unified_api', {}).get('port', 8000)
    key = CONFIG.get('unified_api', {}).get('access_token', 'neko-proxy-key-123')
    key_show = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else key
    
    banner = f"""
{Fore.MAGENTA}================================================================
   Unified API Service Started Successfully!
================================================================{Style.RESET_ALL}
{Fore.GREEN}► Status:{Style.RESET_ALL}       Online
{Fore.GREEN}► Address:{Style.RESET_ALL}      http://127.0.0.1:{port}/v1/chat/completions
{Fore.GREEN}► API Key:{Style.RESET_ALL}      {key_show} (Fused)
{Fore.GREEN}► Capabilities:{Style.RESET_ALL} Chat, Image Gen, Search, Video Gen
{Fore.GREEN}► Logs:{Style.RESET_ALL}         unified_api.log
{Fore.MAGENTA}================================================================{Style.RESET_ALL}
"""
    logger.info("Service banner displayed")
    print(banner)

    app.run(debug=False, port=port, host='0.0.0.0')
