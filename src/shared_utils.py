"""共享工具模块，包含各种通用函数"""

import re
import time
from typing import Dict, Any, List, Optional


def count_tokens(text: str) -> int:
    """
    简单的token计数函数（按字符数估算）
    
    Args:
        text: 要计数的文本
        
    Returns:
        估算的token数量
    """
    # 这是一个简化的token计数方法，实际应用中可能需要更精确的方法
    # 这里我们假设每个中文字符大约为1个token，英文单词大约为1个token
    return len(text)


def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
    """
    估算消息列表的token数量
    
    Args:
        messages: 消息列表
        
    Returns:
        估算的token数量
    """
    total_tokens = 0
    for message in messages:
        content = message.get('content', '')
        if isinstance(content, str):
            total_tokens += count_tokens(content)
        elif isinstance(content, list):
            # 处理多模态内容
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    total_tokens += count_tokens(item.get('text', ''))
    return total_tokens


def create_chat_completion_response(
    content: str, 
    model: str = "neko",
    finish_reason: str = "stop"
) -> Dict[str, Any]:
    """
    创建标准的聊天完成响应
    
    Args:
        content: 响应内容
        model: 模型名称
        finish_reason: 完成原因
        
    Returns:
        标准化的响应字典
    """
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": finish_reason
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }


def create_error_response(
    error: Exception,
    model: str = "neko"
) -> Dict[str, Any]:
    """
    创建标准的错误响应
    
    Args:
        error: 异常对象
        model: 模型名称
        
    Returns:
        标准化的错误响应字典
    """
    return {
        "id": f"error-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"出错了喵({str(error)})"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }


def create_streaming_response_chunk(
    content: str = "",
    finish_reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建流式响应的数据块
    
    Args:
        content: 要发送的内容片段
        finish_reason: 完成原因（如果已完成）
        
    Returns:
        流式响应的数据块
    """
    return {
        "choices": [{
            "delta": {"content": content} if content else {},
            "index": 0,
            "finish_reason": finish_reason
        }]
    }


def extract_user_input(messages: List[Dict[str, Any]]) -> tuple[str, List[str]]:
    """
    从消息列表中提取用户输入和图片URL
    
    Args:
        messages: 消息列表
        
    Returns:
        (用户输入文本, 图片URL列表)的元组
    """
    user_input = ""
    image_urls = []
    
    # 遍历所有消息，提取文本和图像URL
    for msg in reversed(messages):  # 从最新的消息开始
        if msg.get('role') == 'user':
            content = msg.get('content', "")
            # 处理包含image_url的消息
            if isinstance(content, list):
                # 如果是列表类型，说明包含多种类型的内容（如text和image_url）
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
                        elif item.get('type') == 'image_url':
                            # 对于图片URL，提取实际URL并保存
                            image_url = item.get('image_url', {}).get('url', '')
                            if image_url:
                                image_urls.append(image_url)
                                text_parts.append(f'[图片: {image_url}]')
                user_input = ''.join(text_parts)
            else:
                # 如果是字符串类型，直接使用
                user_input = content
            break  # 只处理最新的用户消息
            
    return user_input, image_urls


def should_search(user_input: str) -> bool:
    """
    判断是否需要进行网络搜索
    
    Args:
        user_input: 用户输入
        
    Returns:
        是否需要搜索
    """
    if not user_input:
        return False
        
    # 定义触发搜索的关键词模式
    search_keywords = [
        r'(?:(?:搜索|查|找|了解|知道|什么是|是什么|怎么样|如何|怎么|哪里|哪儿|哪个|哪些|谁是|谁的|几点|时间|日期|天气|新闻|最新|最近|现在).*)',
        r'(.*(?:天气|新闻|股价|比分|时间|日期|定义|解释|介绍|攻略|评测|比较|区别|方法|步骤|教程|怎么做).*)',
        r'(.*(?:最新|最近|现在|今天|明天|昨天|今年|去年|这个月|下个月|上个月).*)'
    ]
    
    # 检查用户输入是否包含触发搜索的关键词
    for pattern in search_keywords:
        if re.search(pattern, user_input, re.IGNORECASE):
            return True
            
    # 添加更多智能判断逻辑
    # 如果输入以"查询"、"请问"等词开头，也触发搜索
    if re.match(r'^(查询|请问|我想了解|我想知道)', user_input.strip(), re.IGNORECASE):
        return True
        
    # 如果输入包含问号且长度较短，可能是一个问题查询
    if '?' in user_input or '？' in user_input:
        return True
        
    return False