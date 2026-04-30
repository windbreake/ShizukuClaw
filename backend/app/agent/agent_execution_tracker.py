# -*- coding: utf-8 -*-
"""
Agent执行追踪器

功能描述:
    追踪Agent工具的执行过程，记录所有工具调用和结果，
    用于生成执行日志和前端可视化。
"""

import time
from typing import List, Dict, Optional, Any
from .response_types import ToolCallInfo, ToolResultInfo


class ExecutionTracker:
    """追踪Agent工具执行过程"""
    
    def __init__(self):
        """初始化执行追踪器"""
        self.call_stack: List[ToolCallInfo] = []
        self.results: Dict[str, ToolResultInfo] = {}
        self.events: List[Dict[str, Any]] = []
        self.start_time: float = time.time()
    
    def record_tool_call(
        self,
        tool_name: str,
        args: Dict,
        call_id: str = ""
    ) -> str:
        """
        记录工具调用
        
        参数:
            tool_name: 工具名称
            args: 工具参数
            call_id: 调用ID（可选，自动生成）
        
        返回:
            生成的call_id
        """
        call = ToolCallInfo(name=tool_name, args=args, call_id=call_id)
        self.call_stack.append(call)
        
        self.events.append({
            "type": "tool_call",
            "tool_name": tool_name,
            "call_id": call.call_id,
            "timestamp": time.time(),
            "args_keys": list(args.keys())
        })
        
        return call.call_id
    
    def record_tool_result(
        self,
        call_id: str,
        success: bool,
        output: str,
        duration: float = 0.0,
        error: Optional[str] = None
    ) -> None:
        """
        记录工具结果
        
        参数:
            call_id: 对应的调用ID
            success: 是否成功
            output: 输出内容
            duration: 执行时间
            error: 错误信息（可选）
        """
        tool_name = self._get_tool_name(call_id)
        
        result = ToolResultInfo(
            call_id=call_id,
            tool_name=tool_name,
            success=success,
            output=output,
            duration=duration,
            error=error
        )
        
        self.results[call_id] = result
        
        self.events.append({
            "type": "tool_result",
            "call_id": call_id,
            "tool_name": tool_name,
            "success": success,
            "duration": duration,
            "has_error": bool(error),
            "timestamp": time.time()
        })
    
    def format_execution_summary(self) -> str:
        """格式化执行总结（用于显示在Agent响应后）"""
        lines = ["## 📋 执行过程总结\n"]
        
        total_success = 0
        total_failed = 0
        total_duration = 0.0
        
        for i, event in enumerate(self.events, 1):
            if event["type"] == "tool_call":
                lines.append(f"\n**{i}. {event['tool_name']}**")
            
            elif event["type"] == "tool_result":
                result_info = self.results.get(event["call_id"])
                if result_info:
                    status = "✓" if event["success"] else "✗"
                    lines.append(f"   {status} {event['duration']:.2f}s")
                    
                    total_duration += event["duration"]
                    if event["success"]:
                        total_success += 1
                    else:
                        total_failed += 1
        
        lines.append(f"\n**统计**: ✓{total_success} ✗{total_failed} | 总耗时 {total_duration:.2f}s")
        
        return "\n".join(lines)
    
    def format_detailed_summary(self, max_output: int = 300) -> str:
        """
        格式化详细执行总结
        
        包括每个工具的输入参数和输出
        """
        lines = ["## 📊 详细执行报告\n"]
        
        for i, call_info in enumerate(self.call_stack, 1):
            lines.append(f"\n### {i}. {call_info.name}\n")
            
            # 参数
            if call_info.args:
                args_summary = ", ".join(call_info.args.keys())
                lines.append(f"**参数**: {args_summary}")
            
            # 结果
            result = self.results.get(call_info.call_id)
            if result:
                status = "✅ 成功" if result.success else "❌ 失败"
                lines.append(f"**状态**: {status}")
                lines.append(f"**耗时**: {result.duration:.2f}s")
                
                if result.output:
                    output_display = result.output[:max_output]
                    if len(result.output) > max_output:
                        output_display += "\n... (已截断)"
                    lines.append(f"**输出**:\n```\n{output_display}\n```")
                
                if result.error:
                    lines.append(f"**错误**: {result.error}")
            else:
                lines.append("**状态**: 未执行")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典用于JSON序列化"""
        return {
            "events": self.events,
            "total_duration": time.time() - self.start_time,
            "total_calls": len(self.call_stack),
            "successful": sum(1 for r in self.results.values() if r.success),
            "failed": sum(1 for r in self.results.values() if not r.success)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取通用统计信息"""
        return {
            'total_duration': time.time() - self.start_time,
            'total_calls': len(self.call_stack),
            'successful_calls': sum(1 for r in self.results.values() if r.success),
            'failed_calls': sum(1 for r in self.results.values() if not r.success),
            'call_stack_depth': len(self.call_stack),
            'event_count': len(self.events)
        }
    
    def _get_tool_name(self, call_id: str) -> str:
        """从call_id获取工具名称"""
        for call in self.call_stack:
            if call.call_id == call_id:
                return call.name
        return "unknown"
