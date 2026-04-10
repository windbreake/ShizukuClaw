#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速功能测试脚本 - 验证所有新模块
"""

from src.agent.response_types import ResponseType, ResponseMessage
from src.agent.execution_intent_detector import ExecutionIntentDetector
from src.agent.tool_message_formatter import ToolMessageFormatter
from src.agent.sandbox_execution_result import ExecutionResult
from src.agent.agent_execution_tracker import ExecutionTracker

print('✅ response_types 导入成功')
print('✅ execution_intent_detector 导入成功')
print('✅ tool_message_formatter 导入成功')
print('✅ sandbox_execution_result 导入成功')
print('✅ agent_execution_tracker 导入成功')

# 测试1: 执行意图检测
result = ExecutionIntentDetector.detect('运行test.py检查输出', True, 'sandbox')
print(f"\n[测试1] 执行意图检测:")
print(f"  - is_execution: {result['is_execution_request']}")
print(f"  - confidence: {result['confidence']:.1%}")
print(f"  - suggested_target: {result['suggested_target']}")

# 测试2: 工具消息格式化
from src.agent.response_types import ToolCallInfo
call_info = ToolCallInfo(name="exec_python", args={"code": "print('hello')"})
formatted_call = ToolMessageFormatter.format_tool_call(call_info)
print(f"\n[测试2] 工具消息格式化:")
print(f"  {formatted_call}")

# 测试3: 执行结果
exec_result = ExecutionResult(
    success=True,
    return_code=0,
    stdout="hello world",
    stderr="",
    duration=0.1,
    execution_type="python"
)
print(f"\n[测试3] 执行结果:")
print(f"  {exec_result.get_short_summary()}")

# 测试4: 执行追踪
tracker = ExecutionTracker()
call_id = tracker.record_tool_call("exec_python", {"code": "print('test')"})
tracker.record_tool_result(call_id, True, "test output", 0.5)
print(f"\n[测试4] 执行追踪:")
print(f"  {tracker.format_execution_summary()}")

print('\n🎉 所有模块导入和功能测试通过！')
