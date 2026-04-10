# -*- coding: utf-8 -*-
"""
工具消息格式化器

功能描述:
    标准化工具调用和执行结果的消息格式，
    提供清晰的用户界面和AI友好的格式。
"""

import json
from typing import Dict, Any, Optional
from .response_types import ToolCallInfo, ToolResultInfo


class ToolMessageFormatter:
    """格式化工具相关的消息"""
    
    # 工具图标映射
    TOOL_ICONS = {
        'read_file': '📖',
        'write_file': '✍️',
        'delete_file': '🗑️',
        'exec_python': '🐍',
        'execute_shell': '💻',
        'run_project_debug': '🧪',
        'list_dir': '📁',
        'create_document': '📄',
        'convert_document': '🔄',
        'start_web_preview': '🌐',
    }
    
    @staticmethod
    def format_tool_call(tool_call: ToolCallInfo, show_args: bool = True) -> str:
        """
        格式化工具调用消息
        
        参数:
            tool_call: 工具调用信息
            show_args: 是否显示参数
        
        返回:
            格式化的字符串
        """
        icon = ToolMessageFormatter.TOOL_ICONS.get(tool_call.name, '🔧')
        
        msg = f"{icon} **调用工具**: `{tool_call.name}`"
        
        if show_args and tool_call.args:
            # 移除敏感参数
            safe_args = ToolMessageFormatter._sanitize_args(tool_call.args, tool_call.name)
            
            # 格式化参数
            if len(str(safe_args)) > 200:
                # 参数过长，简化显示
                key_list = ", ".join(safe_args.keys())
                msg += f"\n*Params*: {key_list}"
            else:
                args_str = json.dumps(safe_args, ensure_ascii=False, indent=2)
                msg += f"\n```json\n{args_str}\n```"
        
        return msg
    
    @staticmethod
    def format_tool_result(
        tool_result: ToolResultInfo,
        show_output: bool = True,
        max_output_len: int = 500
    ) -> str:
        """
        格式化工具结果消息
        
        参数:
            tool_result: 工具执行结果
            show_output: 是否显示结果输出
            max_output_len: 最大输出长度
        
        返回:
            格式化的字符串
        """
        status_icon = "✅" if tool_result.success else "❌"
        duration_str = f"({tool_result.duration:.2f}s)" if tool_result.duration > 0 else ""
        
        msg = f"{status_icon} **{tool_result.tool_name} 完成** {duration_str}\n"
        
        if show_output:
            output_display = tool_result.output
            if len(output_display) > max_output_len:
                output_display = output_display[:max_output_len] + "\n... (输出已截断)"
            
            if output_display:
                msg += f"\n```\n{output_display}\n```"
            
            if tool_result.error:
                msg += f"\n**错误**: {tool_result.error[:300]}"
        
        return msg
    
    @staticmethod
    def format_execution_summary(
        tool_calls: list,
        tool_results: Dict[str, ToolResultInfo]
    ) -> str:
        """
        格式化执行总结（显示在Agent响应后面）
        
        参数:
            tool_calls: 工具调用列表
            tool_results: 工具结果字典（key为call_id）
        
        返回:
            格式化的执行总结字符串
        """
        if not tool_calls:
            return ""
        
        summary = "\n\n---\n## 📋 执行过程总结\n\n"
        
        successful_count = 0
        failed_count = 0
        total_duration = 0.0
        
        for i, call_info in enumerate(tool_calls, 1):
            summary += f"**{i}. {call_info.name}**\n"
            
            result = tool_results.get(call_info.call_id)
            if result:
                status = "✓ 成功" if result.success else "✗ 失败"
                summary += f"   - 状态: {status}\n"
                summary += f"   - 耗时: {result.duration:.2f}s\n"
                total_duration += result.duration
                
                if result.success:
                    successful_count += 1
                else:
                    failed_count += 1
                
                if result.error:
                    summary += f"   - 错误: {result.error[:100]}\n"
            else:
                summary += f"   - 状态: 未执行\n"
        
        # 添加统计信息
        summary += f"\n**统计**: 成功 {successful_count}, 失败 {failed_count}, 总耗时 {total_duration:.2f}s"
        
        return summary
    
    @staticmethod
    def format_quick_status(
        tool_name: str,
        success: bool,
        duration: float = 0.0
    ) -> str:
        """快速格式化状态消息（用于流式输出中的快速反馈）"""
        status_icon = "✅" if success else "❌"
        time_str = f" ({duration:.2f}s)" if duration > 0 else ""
        return f"{status_icon} {tool_name}{time_str}"
    
    @staticmethod
    def _sanitize_args(args: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """清理敏感参数"""
        safe_args = {}
        
        # 定义敏感参数
        sensitive_keys = {'code', 'content', 'password', 'token', 'key', 'secret'}
        
        for key, value in args.items():
            if key.lower() in sensitive_keys:
                # 长代码显示摘要
                if isinstance(value, str) and len(value) > 100:
                    safe_args[key] = f"<{len(value)} chars of code>"
                else:
                    safe_args[key] = "<sensitive_data>"
            else:
                safe_args[key] = value
        
        return safe_args or args
