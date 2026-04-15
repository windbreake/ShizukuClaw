# -*- coding: utf-8 -*-
"""
沙箱执行结果封装

功能描述:
    标准化代码执行后的结果对象，支持多种格式导出
    (字典、用户友好字符串、AI友好字符串)
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ExecutionResult:
    """沙箱执行结果"""
    success: bool
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    execution_type: str = "python"  # python, shell, project_debug
    
    def to_dict(self) -> Dict:
        """转换为字典（用于JSON序列化）"""
        return {
            "success": self.success,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration": self.duration,
            "type": self.execution_type
        }
    
    def is_successful(self) -> bool:
        """检查执行是否成功"""
        return self.success and self.return_code == 0
    
    def format_for_user(self, max_output: int = 1000) -> str:
        """
        格式化为用户友好的字符串
        
        参数:
            max_output: 最大输出长度
        
        返回:
            格式化的字符串，适合直接显示在UI中
        """
        status_icon = "✅" if self.success else "❌"
        status_text = "成功" if self.success else "失败"
        
        result_text = f"{status_icon} **执行{status_text}**\n\n"
        result_text += f"• **类型**: {self.execution_type}\n"
        result_text += f"• **返回码**: {self.return_code}\n"
        result_text += f"• **耗时**: {self.duration:.2f}s\n\n"
        
        if self.stdout:
            stdout_display = self.stdout
            if len(stdout_display) > max_output:
                stdout_display = stdout_display[:max_output] + "\n... (输出已截断)"
            result_text += "**输出**:\n```\n" + stdout_display + "\n```\n\n"
        
        if self.stderr:
            stderr_display = self.stderr
            if len(stderr_display) > max_output:
                stderr_display = stderr_display[:max_output] + "\n... (错误已截断)"
            result_text += "**错误/警告**:\n```\n" + stderr_display + "\n```\n"
        
        return result_text
    
    def format_for_ai(self, max_output: int = 2000) -> str:
        """
        格式化为AI友好的字符串（用于传递给下一轮LLM）
        
        参数:
            max_output: 最大输出长度
        
        返回:
            格式化的字符串，包含结构化的执行结果信息
        """
        lines = [
            "[执行结果]",
            f"状态: {'成功' if self.success else '失败'}",
            f"返回码: {self.return_code}",
            f"执行类型: {self.execution_type}",
            f"耗时: {self.duration:.2f}s"
        ]
        
        if self.stdout:
            stdout_display = self.stdout
            if len(stdout_display) > max_output:
                stdout_display = stdout_display[:max_output] + "\n... (已截断)"
            lines.append(f"标准输出:\n{stdout_display}")
        
        if self.stderr:
            stderr_display = self.stderr
            if len(stderr_display) > max_output:
                stderr_display = stderr_display[:max_output] + "\n... (已截断)"
            lines.append(f"标准错误:\n{stderr_display}")
        
        return "\n".join(lines)
    
    def get_short_summary(self) -> str:
        """获取执行结果的简短总结（一行）"""
        status = "✅成功" if self.success else "❌失败"
        if self.stdout:
            first_line = self.stdout.split('\n')[0][:50]
            return f"{status} | {first_line}"
        return f"{status} (返回码: {self.return_code})"
    
    def has_errors(self) -> bool:
        """是否有错误输出"""
        return bool(self.stderr)
    
    def has_output(self) -> bool:
        """是否有标准输出"""
        return bool(self.stdout)


@staticmethod
def from_dict(data: Dict) -> 'ExecutionResult':
    """从字典创建ExecutionResult对象"""
    return ExecutionResult(
        success=data.get('success', False),
        return_code=data.get('return_code', 0),
        stdout=data.get('stdout', ''),
        stderr=data.get('stderr', ''),
        duration=data.get('duration', 0.0),
        execution_type=data.get('type', 'python')
    )
