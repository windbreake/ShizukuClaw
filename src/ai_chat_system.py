# -*- coding: utf-8 -*-
"""AI聊天系统模块"""

import json
import logging
import os
import time
import threading
import base64
import re
from datetime import datetime
from typing import Optional, Tuple
from io import BytesIO

import requests
from mysql.connector import Error
from PIL import Image
from openai import OpenAI, APITimeoutError

from src.config import CONFIG
from src.database import get_connection, DatabaseManager
from src.shared_utils import count_tokens, estimate_tokens

# 全局变量用于跟踪Token使用（需要在web_server.py中更新这些值）
try:
    from src.web_server import INPUT_TOKENS, OUTPUT_TOKENS
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
        # 在单例模式下，不要在__init__中初始化属性
        # 这些属性应该在initialize()方法中初始化

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
        db = DatabaseManager()
        # 直接从配置中获取系统提示语，不再在代码中生成
        system_prompt = CONFIG['system_prompt']

        # 初始化 Agent Manager
        from src.agent_manager import AgentManager
        self.agent_manager = AgentManager(self)

        # 使用配置中的基础URL
        client = OpenAI(
            api_key=CONFIG['api']['key'],
            base_url=CONFIG['api']['base_url'],
            timeout=30.0  # 添加超时设置
        )
        messages = [{"role": "system", "content": system_prompt}]

        # 确保赋值成功
        self.db = db
        self.system_prompt = system_prompt
        self.client = client
        self.messages = messages

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
    def _make_api_request(url, headers, payload):
        """发送API请求的通用方法"""
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return response

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
                kimi_payload
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
                                kimi_payload
                            )

                            if final_response.status_code == 200:
                                final_result = final_response.json()
                                if final_result.get("choices") and len(final_result["choices"]) > 0:
                                    final_choice = final_result["choices"][0]
                                    if final_choice.get("message") and final_choice["message"].get("content"):
                                        return final_choice["message"]["content"]

            return "未找到相关搜索结果"

        except Exception as e:
            error_msg = f"搜索失败: {str(e)}"
            print(f"Search Error: {error_msg}")
            return error_msg

    @staticmethod
    def should_search(user_input):
        """判断是否需要进行搜索"""
        from src.shared_utils import should_search as util_should_search
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
            from src.web_server import INPUT_TOKENS, OUTPUT_TOKENS
            INPUT_TOKENS += prompt_tokens
            OUTPUT_TOKENS += completion_tokens
        except ImportError:
            INPUT_TOKENS += prompt_tokens
            OUTPUT_TOKENS += completion_tokens

        return content, prompt_tokens, completion_tokens

    def build_chat_context(self, user_input, max_tokens=2500):
        """
        构建智能上下文：
        1. 系统提示词
        2. 相关历史记忆（通过搜索提取的深层记忆）
        3. 最近对话窗口（短期记忆）
        4. 当前用户输入
        """
        # 1. 基础系统提示词
        context_messages = [{"role": "system", "content": self.system_prompt}]
        
        # 2. 回忆技能：如果用户输入较长，尝试搜索相关的深层历史
        if user_input and len(user_input) > 4:
            # 简单的关键词提取（取前10个字符作为搜索索引，可优化）
            search_keyword = user_input[:10]
            relevant_history = self.db.search_chat_history(search_keyword, limit=3)
            
            if relevant_history:
                memory_text = "【相关历史记忆】\n"
                for row in relevant_history:
                    # row[0] is user_input, row[1] is ai_response
                    if row[0] and row[1]:
                        memory_text += f"User: {row[0]}\nAI: {row[1]}\n---\n"
                # 将相关记忆作为System Prompt的一部分插入，不占用对话轮次
                if memory_text != "【相关历史记忆】\n":
                    context_messages.append({"role": "system", "content": f"你可以参考以下历史对话记录回答：\n{memory_text}"})

        # 3. 读取最近的短期记忆 (从数据库读取，保证重启后记忆不丢失)
        # 获取最近10轮对话，保证连贯性
        recent_messages = self.db.get_recent_chat_history(limit=10)
        
        # 4. Token 预算控制 (滑动窗口)
        # 如果历史记录太多，动态移除最早的记录，直到满足max_tokens限制
        current_tokens = estimate_tokens(context_messages) + estimate_tokens(recent_messages)
        
        while current_tokens > max_tokens and len(recent_messages) > 0:
            recent_messages.pop(0) # 移除最旧的一条
            current_tokens = estimate_tokens(context_messages) + estimate_tokens(recent_messages)
            
        return context_messages + recent_messages

    def chat(self, user_input, image=None, is_admin=False, attachments=None):
        """处理聊天请求，支持文本、图片及其他附件（无状态优化版）
        
        Args:
            user_input (str): 用户输入文本
            image (str): 图片路径或base64 (Legacy)
            is_admin (bool): 是否为管理员
            attachments (list): 附件列表 [{'name':..., 'type':..., 'content':...}]
        """
        
        # === 核心变更1：动态构建Agent上下文（如果启用Agent） ===
        # 即使不是管理员，也可以读取Agent上下文，但不能执行写操作
        try:
            agent_context = self.agent_manager.get_agent_context()
        except:
            agent_context = ""

        # 将Agent上下文注入到系统提示词中（临时）
        original_system_prompt = self.system_prompt
        self.system_prompt = f"{original_system_prompt}\n\n{agent_context}"
        
        # === 核心变更2：每次动态构建上下文 ===
        messages = self.build_chat_context(user_input)
        
        # 恢复系统提示词（避免污染全局状态，虽然这是单例...）
        # 更好的做法是 build_chat_context 接受额外的 system_suffix
        self.system_prompt = original_system_prompt
        
        # 手动将 agent_context 添加到 messages 的第一个系统消息中
        if messages and messages[0]['role'] == 'system':
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

        # 处理文本输入
        if user_input:
            # 判断是否需要搜索
            if AIChatSystem.should_search(user_input):
                print(f"检测到搜索请求: {user_input}")
                search_result = AIChatSystem.search_with_ai_search(user_input)

                # 检查搜索是否成功
                if "搜索API错误" in search_result or "搜索失败" in search_result:
                    # 如果搜索失败，使用普通聊天模式
                    messages.append({"role": "user", "content": user_input})
                else:
                    # 将搜索结果拼接到当前输入中
                    search_context = f"用户问题: {user_input}\n{search_result}"
                    messages.append({
                        "role": "user",
                        "content": search_context
                    })
                    print(f"搜索结果: {search_result[:100]}...")
            else:
                messages.append({"role": "user", "content": user_input})
        # 如果没有文本输入但有图片
        elif not user_input and image:
            messages.append({"role": "user", "content": "[用户发送了一张图片]"})
        # 如果没有文本输入
        elif not user_input:
            return "请发送文本内容喵~"

        try:
            # 使用DeepSeek-Chat模型生成回复（添加超时）
            
            # --- AGENT EXTENSION ---
            # 获取工具定义
            tools = None
            try:
                if is_admin:
                    tools = self.agent_manager.get_tools_definitions(is_admin)
            except AttributeError:
                # 如果没有初始化 agent_manager
                pass

            api_kwargs = {
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.7,
                # "max_tokens": 200, # 移除硬限制，由 Agent 自行决定
                "timeout": 60      # 增加超时
            }
            
            if tools:
                api_kwargs["tools"] = tools
                # api_kwargs["tool_choice"] = "auto" 

            response = self.client.chat.completions.create(**api_kwargs)
            
            choice = response.choices[0]
            message = choice.message
            
            ai_response = message.content # 默认回复

            # 处理工具调用
            if hasattr(message, 'tool_calls') and message.tool_calls:
                # 将助手的工具调用消息添加到历史
                # 注意：openai python sdk 对象不能直接作为 dict 添加
                # 需要转换格式
                messages.append(message)
                
                tool_calls = message.tool_calls
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except:
                        function_args = {}
                    
                    print(f"Executing tool: {function_name} with {function_args}")
                    
                    # 执行工具
                    tool_result = self.agent_manager.execute_tool(function_name, function_args, is_admin=is_admin)
                    
                    # 记录操作到 AgentMemory (Short Term)
                    self.agent_manager.record_action("assistant", f"Called {function_name}")
                    self.agent_manager.record_action("system", f"Result: {tool_result}")

                    # 将结果返回给 LLM
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(tool_result)
                    })
                
                # 再次调用 LLM 获取最终回复
                # 注意：这里可能会产生递归，目前只支持一轮工具调用
                try:
                    second_response = self.client.chat.completions.create(
                        model="deepseek-chat",
                        messages=messages,
                        temperature=0.7,
                        timeout=60
                    )
                    ai_response = second_response.choices[0].message.content
                    
                    # 更新 response 对象以便后续统计
                    response = second_response
                except Exception as e:
                    ai_response = f"工具执行完毕，但生成最终回复时出错: {str(e)}"

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

            # 保存对话记录（包括图片描述）
            self.db.save_chat(user_input or "[图片]", ai_response, image_description)

            return ai_response

        except APITimeoutError:
            return "呜...思考太久超时啦Nanaoda! (>_<)"
        except Exception as e:
            return f"呜...出错啦Nanaoda! ({str(e)})"
