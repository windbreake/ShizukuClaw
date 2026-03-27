import os
import sys

# 修复 Windows 后台运行时的 OSError: [Errno 22] Invalid argument 错误
import sys
import os
try:
    sys.stdout.fileno()
except OSError:
    sys.stdout = open(os.devnull, "w")
try:
    sys.stderr.fileno()
except OSError:
    sys.stderr = open(os.devnull, "w")


# 修复 Windows 后台运行时的 OSError: [Errno 22] Invalid argument 错误
import sys

# 修复 Windows 后台运行时的 OSError: [Errno 22] Invalid argument 错误
import sys
import os
try:
    sys.stdout.fileno()
except OSError:
    sys.stdout = open(os.devnull, "w")
try:
    sys.stderr.fileno()
except OSError:
    sys.stderr = open(os.devnull, "w")

import os
try:
    sys.stdout.fileno()
except OSError:
    sys.stdout = open(os.devnull, "w")
try:
    sys.stderr.fileno()
except OSError:
    sys.stderr = open(os.devnull, "w")


# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv
import requests
import base64
from io import BytesIO
from PIL import Image
import time
import json

# 加载环境变量
load_dotenv()

app = Flask(__name__)

import logging
from logging.handlers import RotatingFileHandler

# 配置日志
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler('unified_api.log', maxBytes=1000000, backupCount=1, encoding='utf-8')
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# 从配置获取API密钥和基础URL
from src.config import CONFIG
from src.shared_utils import create_chat_completion_response, create_error_response, extract_user_input, should_search


# 中间件函数：验证自定义API key
def authenticate():
    proxy_key = request.headers.get('Authorization')
    if proxy_key:
        # 提取Bearer token
        if proxy_key.startswith('Bearer '):
            proxy_key = proxy_key[7:]  # 移除'Bearer '前缀
    
    # 动态获取有效Keys
    valid_key = CONFIG['unified_api'].get('access_token', 'neko-proxy-key-123')
    
    if not proxy_key or (proxy_key != valid_key and proxy_key != '114514'): # 114514 保留为调试后门
        app.logger.warning(f"认证失败: 无效的 API Key - {proxy_key}")
        return jsonify({'error': 'Invalid API key'}), 401
    return None  # 通过验证


@app.before_request
def before_request():
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
        data = request.json
        app.logger.info(f"收到统一API聊天请求")
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

        # 处理图片（如果有的话）
        image_description = None
        if image_urls:
            app.logger.info("开始处理图片...")
            # 获取第一张图片
            image_url = image_urls[0]
            try:
                # 从URL获取图片
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()

                # 将图片转换为Base64
                image_data = base64.b64encode(response.content).decode('utf-8')

                # 使用阿里云通义VL MAX分析图片
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
                                    {
                                        "image": f"data:image/jpeg;base64,{image_data}"
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
                app.logger.info("调用阿里云通义VL MAX进行图片分析")
                api_response = requests.post(
                    f"{CONFIG['aliyun_api']['base_url']}/services/aigc/multimodal-generation/generation",
                    headers=headers,
                    json=payload
                )

                if api_response.status_code == 200:
                    result = api_response.json()
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
                            image_description = " ".join(text_parts)
                        else:
                            image_description = str(content)

                        user_input = f"[图片内容: {image_description}] {user_input}"
                        app.logger.info(f"图片分析成功: {image_description[:50]}...")
                else:
                    user_input = f"[图片分析失败] {user_input}"
                    app.logger.error(f"图片分析API失败: {api_response.text}")

            except Exception as e:
                print(f"图片处理错误: {e}")
                app.logger.error(f"图片处理异常: {str(e)}")
                user_input = f"[图片处理出错] {user_input}"

        # 检查是否需要网络搜索
        search_result = None
        if should_search(user_input):
            app.logger.info("检测到搜索意图，开始联网搜索...")
            try:
                # 使用Kimi API进行联网搜索
                headers = {
                    "Authorization": f"Bearer {CONFIG['search_api']['key']}",
                    "Content-Type": "application/json"
                }

                # 构造Kimi API请求消息
                kimi_messages = [
                    {"role": "system", "content": "你是 Kimi，由 Moonshot AI 提供支持的人工智能助手。"},
                    {"role": "user", "content": user_input}
                ]

                # 发送请求到Kimi API
                kimi_payload = {
                     # ... (省略部分不变)
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

                app.logger.info("调用 Kimi API 搜索...")
                kimi_response = requests.post(
                    f"{CONFIG['search_api']['base_url']}/chat/completions",
                    headers=headers,
                    json=kimi_payload
                )

                if kimi_response.status_code == 200:
                    result = kimi_response.json()
                    # 检查是否需要工具调用
                    if result.get("choices") and len(result["choices"]) > 0:
                        choice = result["choices"][0]
                        if choice.get("finish_reason") == "tool_calls" and choice.get("message") and choice[
                            "message"].get("tool_calls"):
                            # 处理工具调用
                            tool_calls = choice["message"]["tool_calls"]
                            for tool_call in tool_calls:
                                if tool_call["function"]["name"] == "$web_search":
                                    # 执行搜索工具调用
                                    tool_call_id = tool_call["id"]
                                    tool_call_arguments = json.loads(tool_call["function"]["arguments"])
                                    app.logger.info(f"执行搜索工具: {tool_call_arguments}")

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
                                    final_response = requests.post(
                                        f"{CONFIG['search_api']['base_url']}/chat/completions",
                                        headers=headers,
                                        json=kimi_payload
                                    )

                                    if final_response.status_code == 200:
                                        final_result = final_response.json()
                                        if final_result.get("choices") and len(final_result["choices"]) > 0:
                                            final_choice = final_result["choices"][0]
                                            if final_choice.get("message") and final_choice["message"].get("content"):
                                                search_result = final_choice["message"]["content"]
                                                user_input = f"用户问题: {user_input}\n搜索结果: {search_result}"
                                                app.logger.info("搜索完成，已整合结果")
                                    break
                else:
                    print(f"Kimi API错误: {kimi_response.status_code} - {kimi_response.text}")
                    app.logger.error(f"Kimi API错误: {kimi_response.text}")

            except Exception as e:
                print(f"搜索错误: {e}")
                app.logger.error(f"搜索过程异常: {str(e)}")

        # 检查是否是图片生成请求
        is_image_gen_request = False
        if "画" in user_input or "生成图片" in user_input or "画一张" in user_input or "绘图" in user_input:
            is_image_gen_request = True

        # 检查是否是视频生成请求
        is_video_gen_request = False
        if "视频" in user_input or "生成视频" in user_input or "制作视频" in user_input:
            is_video_gen_request = True

        # 图片生成请求处理
        if is_image_gen_request and CONFIG['image_generation_api']['key']:
            app.logger.info("检测到图片生成请求")
            try:
                # 构造图片生成请求
                image_headers = {
                    "Authorization": f"Bearer {CONFIG['image_generation_api']['key']}",
                    "Content-Type": "application/json"
                }

                image_payload = {
                    "prompt": user_input,
                    "n": 1,
                    "size": "1024x1024"
                }

                # 发送请求到图片生成API
                image_response = requests.post(
                    f"{CONFIG['image_generation_api']['base_url']}/images/generations",
                    headers=image_headers,
                    json=image_payload
                )

                if image_response.status_code == 200:
                    result = image_response.json()
                    # 构造图片响应格式
                    response_content = "我为您生成了图片:\n"
                    if "data" in result and len(result["data"]) > 0:
                        response_content += f"![生成的图片]({result['data'][0]['url']})\n"
                        if "revised_prompt" in result["data"][0]:
                            response_content += f"优化后的提示词: {result['data'][0]['revised_prompt']}\n"
                    
                    app.logger.info("图片生成成功")
                    return jsonify(create_chat_completion_response(response_content, "neko-image-generator"))
                else:
                    # 如果图片生成失败，则继续使用聊天API
                    print(f"图片生成失败: {image_response.status_code} - {image_response.text}")
                    app.logger.error(f"图片生成API失败: {image_response.text}")
            except Exception as e:
                print(f"图片生成错误: {e}")
                app.logger.error(f"图片生成异常: {str(e)}")

        # 视频生成请求处理
        if is_video_gen_request and CONFIG['video_generation_api']['key'] and CONFIG['video_generation_api'][
            'base_url']:
            app.logger.info("检测到视频生成请求")
            try:
                # 构造视频生成请求
                video_headers = {
                    "Authorization": f"Bearer {CONFIG['video_generation_api']['key']}",
                    "Content-Type": "application/json"
                }

                video_payload = {
                    "prompt": user_input,
                    "duration": 5  # 默认5秒视频
                }

                # 发送请求到视频生成API
                video_response = requests.post(
                    f"{CONFIG['video_generation_api']['base_url']}/videos/generations",
                    headers=video_headers,
                    json=video_payload
                )

                if video_response.status_code == 200:
                    result = video_response.json()
                    # 构造视频响应格式
                    response_content = "我为您生成了视频:\n"
                    if "data" in result and len(result["data"]) > 0:
                        response_content += f"视频链接: {result['data'][0]['url']}\n"
                        if "revised_prompt" in result["data"][0]:
                            response_content += f"优化后的提示词: {result['data'][0]['revised_prompt']}\n"

                    return jsonify(create_chat_completion_response(response_content, "neko-video-generator"))
                else:
                    # 如果视频生成失败，则继续使用聊天API
                    print(f"视频生成失败: {video_response.status_code} - {video_response.text}")
            except Exception as e:
                print(f"视频生成错误: {e}")

        # 使用DeepSeek API生成回复
        headers = {
            "Authorization": f"Bearer {CONFIG['api']['key']}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": user_input}],
            "temperature": 0.7,
            "max_tokens": 500
        }

        # 检查是否需要流式响应
        stream_mode = data.get("stream", False)
        
        # 注入 Persona System Prompt (如果 active_persona 存在)
        if 'system_prompt' in CONFIG and CONFIG['system_prompt']:
            #Check if system message already exists
            has_system = any(m.get('role') == 'system' for m in payload['messages'])
            if not has_system:
                payload['messages'].insert(0, {"role": "system", "content": CONFIG['system_prompt']})

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
        api_response = requests.post(
            f"{CONFIG['api']['base_url']}/chat/completions",
            headers=headers,
            json=payload
        )


        if api_response.status_code == 200:
            result = api_response.json()
            # 修改模型名称为neko
            result["model"] = "neko"
            return jsonify(result)
        else:
            return jsonify(create_error_response(Exception(f"{api_response.status_code} - {api_response.text}")))

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"统一API错误:\n{error_trace}")

        # 返回错误信息但仍保持OpenAI格式
        return jsonify(create_error_response(e))


if __name__ == '__main__':
    from logging_config import setup_logging
    # Configure logger
    logger = setup_logging('unified_api', 'unified_api.log')
    
    # Print Banner
    from config import CONFIG
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
