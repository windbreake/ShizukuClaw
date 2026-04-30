# -*- coding: utf-8 -*-
"""
Agent响应类型定义

功能描述:
    定义Agent系统的统一响应格式，支持工具调用、结果返回、
    LLM输出等多种响应类型的标准化。
"""

from enum import Enum
from typing import Any, Optional, Dict
from dataclasses import dataclass, field
import time


class ResponseType(Enum):
    """Agent响应类型枚举"""
    TOOL_CALL = "tool_call"           # 工具调用
    TOOL_RESULT = "tool_result"       # 工具执行结果
    LLM_THINKING = "llm_thinking"     # LLM思考过程
    LLM_RESULT = "llm_result"          # LLM最终结果
    ERROR = "error"                    # 错误
    STATUS = "status"                  # 状态消息


@dataclass
class ToolCallInfo:
    """工具调用信息"""
    name: str
    args: Dict[str, Any]
    call_id: str = ""
    timestamp: float = 0.0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.call_id:
            self.call_id = f"call_{int(self.timestamp * 1000) % 1000000}"


@dataclass
class ToolResultInfo:
    """工具执行结果信息"""
    call_id: str
    tool_name: str
    success: bool
    output: str
    duration: float = 0.0
    error: Optional[str] = None
    timestamp: float = 0.0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class ResponseMessage:
    """统一的Agent响应消息"""
    type: ResponseType
    content: str = ""
    tool_call: Optional[ToolCallInfo] = None
    tool_result: Optional[ToolResultInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典用于序列化"""
        return {
            "type": self.type.value,
            "content": self.content,
            "tool_call": self.tool_call.__dict__ if self.tool_call else None,
            "tool_result": self.tool_result.__dict__ if self.tool_result else None,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }
