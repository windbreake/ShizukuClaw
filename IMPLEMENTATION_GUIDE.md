# ShizukuClaw Agent系统改进 - 实施集成指南

## 快速参考

### 新增文件
1. `src/agent/response_types.py` - 统一响应格式
2. `src/agent/execution_intent_detector.py` - 执行意图检测
3. `src/agent/tool_message_formatter.py` - 工具消息格式化
4. `src/agent/sandbox_execution_result.py` - 执行结果封装
5. `src/agent/agent_execution_tracker.py` - 执行追踪

## 集成步骤

### 步骤1：更新Agent管理器 (agent_manager.py)

**修改位置**: `get_agent_context()` 方法

替换现有的 Agent 系统提示词为:

```python
def get_agent_context(self):
    """Builds context string for the LLM with execution guarantees"""
    try:
        plan = self.planner.load_plan()
        memory_packet = self.memory.build_context_packet()
        
        # 增强的执行承诺部分
        execution_commitment = """
[执行承诺 - 关键要求]

当用户明确要求您执行、运行、调试或测试某个项目/脚本时，您必须：

1. **识别执行意图**:
   - 文本中是否出现"运行"、"执行"、"调试"、"检查"、"测试"等关键词？
   - 是否关联到具体的项目文件或命令？

2. **工具选择**:
   - 单个Python脚本 → 使用 exec_python
   - 完整项目 → 使用 run_project_debug
   - 系统命令 → 使用 execute_shell（如可用）

3. **执行保证**:
   - ❌ 不能只提供代码建议，必须实际执行
   - ✅ 捕获并报告完整的执行结果
   - ✅ 最终答复必须包含[执行结果]段落
   
4. **结果格式**:
   - 返回码 (success / failure)
   - 标准输出
   - 任何错误消息
   - 执行时间

示例正确做法:
用户: "运行 test.py 并检查输出"
✅ 你应该:
  1. 调用 exec_python("python test.py")
  2. 获取输出结果
  3. 回复: "我执行了test.py。[执行结果] 返回码: 0, 输出: ..."
"""

        context = f"""
[Agent能力]
- 文件系统: 代理数据目录内的读写删除
- Python执行: 沙箱中的脚本执行
- 项目调试: 运行项目测试
- 网页预览: 启动本地服务器预览

{execution_commitment}

[当前计划]
{plan}

[记忆包]
{memory_packet}
"""
        return context
    except Exception as e:
        return f"[Agent Context Error: {str(e)}]"
```

### 步骤2：更新工具执行方法 (agent_manager.py)

**目标**: 导入新模块并在 `execute_tool()` 中使用

```python
# 在文件开头添加导入
from src.agent.response_types import ResponseType, ResponseMessage, ToolCallInfo, ToolResultInfo
from src.agent.execution_intent_detector import ExecutionIntentDetector
from src.agent.tool_message_formatter import ToolMessageFormatter
from src.agent.sandbox_execution_result import ExecutionResult
from src.agent.agent_execution_tracker import ExecutionTracker

# 在 AgentManager.__init__() 中添加
self.execution_tracker = ExecutionTracker()
```

**修改 `execute_tool()` 中的工具调用**:

```python
def execute_tool(self, tool_name, args, is_admin=False, frontend_source='control_panel', user_input=''):
    """Execute a tool call from the LLM"""
    
    # ... 原有的权限检查代码 ...
    
    try:
        # 记录工具调用
        call_id = self.execution_tracker.record_tool_call(tool_name, args)
        start_time = time.time()
        
        # 原有的工具分支逻辑
        if tool_name == 'exec_python':
            result = self.sandbox.execute_python(args.get('code'), args.get('filename', 'script.py'))
            # 如果返回的是字典（新格式），转换为ExecutionResult
            if isinstance(result, dict):
                result = ExecutionResult(**result)
                output = f"返回码: {result.return_code}\n{result.stdout}"
            else:
                output = result
            
            duration = time.time() - start_time
            success = isinstance(result, ExecutionResult) and result.success
            self.execution_tracker.record_tool_result(call_id, success, output, duration)
            return output
        
        elif tool_name == 'run_project_debug':
            result = self.sandbox.run_project_debug(
                target=args.get('target', '.'),
                run_tests=bool(args.get('run_tests', True)),
                external_approval_id=args.get('external_approval_id', '')
            )
            # 同上处理结果
            duration = time.time() - start_time
            self.execution_tracker.record_tool_result(call_id, True, str(result), duration)
            return result
        
        # ... 其他工具 ...
    
    except Exception as e:
        duration = time.time() - start_time
        self.execution_tracker.record_tool_result(call_id, False, "", duration, error=str(e))
        return f"Error executing tool {tool_name}: {str(e)}"
```

### 步骤3：改进自动执行检测 (ai_chat_system.py)

**替换旧的正则检测**:

```python
# 在 chat() 方法中，当返回LLM结果前

from src.agent.execution_intent_detector import ExecutionIntentDetector

# 检查是否需要自动执行
if is_admin and frontend_source == 'sandbox':
    detection = ExecutionIntentDetector.detect(
        user_input=user_input,
        is_admin=is_admin,
        frontend_source=frontend_source
    )
    
    if detection['is_execution_request'] and detection['confidence'] > 0.7:
        # 需要执行
        target = detection['suggested_target']
        if target and not did_tool_execution:
            # 自动执行逻辑
            try:
                if target.endswith('.py'):
                    result = self.agent_manager.execute_tool(
                        'exec_python',
                        {'code': f"exec(open('{target}').read())", 'filename': target},
                        is_admin=is_admin
                    )
                else:
                    result = self.agent_manager.execute_tool(
                        'run_project_debug',
                        {'target': target},
                        is_admin=is_admin
                    )
                
                # 将执行结果添加到AI响应
                ai_response += f"\n\n[自动执行结果]\n{result}"
            except Exception as e:
                ai_response += f"\n\n[自动执行失败]\n{str(e)}"
```

### 步骤4：改进沙箱执行方法 (agent_sandbox.py)

**修改 `execute_python()` 返回结构化结果**:

```python
def execute_python(self, code: str, filename: str = 'script.py') -> dict:
    """执行Python代码 - 返回结构化结果"""
    import time
    start_time = time.time()
    
    safe_path = self.validate_path(filename, action='write')
    safe_dir = os.path.dirname(safe_path)
    if safe_dir:
        os.makedirs(safe_dir, exist_ok=True)
    
    try:
        # 写入代码
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 执行
        result = subprocess.run(
            [sys.executable, safe_path],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=self.workspace_dir
        )
        
        duration = time.time() - start_time
        
        # 返回结构化结果
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "duration": duration,
            "type": "python"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": "执行超时（90秒）",
            "duration": 90.0,
            "type": "python"
        }
    except Exception as e:
        return {
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": str(e),
            "duration": time.time() - start_time,
            "type": "python"
        }
```

### 步骤5：前端适配 (control_panel.html)

在 `/chat` 响应处理中添加对新的执行追踪数据的支持：

```javascript
// 在 postChat() 中，处理响应时
const data = await res.json();

// 新增：获取执行追踪信息
if (data.execution_tracker) {
    const tracker_info = data.execution_tracker;
    // 可以用于显示执行统计
    console.log("Execution Stats:", tracker_info);
}

// 原有的消息更新逻辑保持不变
updateBotMessage(pendingBotMessageId, data.reply, {debug: data.debug || null});
```

## 验证检查清单

### 编译检查
- [ ] `python -m py_compile src/agent/response_types.py`
- [ ] `python -m py_compile src/agent/execution_intent_detector.py`
- [ ] `python -m py_compile src/agent/tool_message_formatter.py`
- [ ] `python -m py_compile src/agent/sandbox_execution_result.py`
- [ ] `python -m py_compile src/agent/agent_execution_tracker.py`
- [ ] `python -m py_compile src/agent/agent_manager.py` (修改后)
- [ ] `python -m py_compile src/agent/ai_chat_system.py` (修改后)

### 功能测试
- [ ] **执行意图检测**: 用户输入"运行snake_game.py" → 识别为执行请求且confidence > 0.7
- [ ] **执行意图排除**: 用户输入"代码运行良好" → 识别为非执行请求
- [ ] **自动执行**: 输入"运行xxx.py"且LLM没有调用工具 → 自动调用exec_python
- [ ] **结果格式化**: 工具执行后的输出包含返回码和标准输出
- [ ] **执行追踪**: 查看日志显示工具调用堆栈和执行时间
- [ ] **错误处理**: 执行失败时正确捕获错误信息

### 回归测试
- [ ] 正常聊天功能不受影响
- [ ] 文件读写操作正常
- [ ] 插件命令可用
- [ ] 权限控制仍有效

## 常见问题

### Q1: 如何查看执行追踪信息？
A: 在Agent执行后，检查 `agent_manager.execution_tracker` 或调用 `format_execution_summary()`:
```python
print(agent_manager.execution_tracker.format_execution_summary())
```

### Q2: 执行结果数据类型改变了怎么办？
A: 使用 `ExecutionResult.from_dict()` 进行兼容转换：
```python
result_dict = {"success": True, "return_code": 0, ...}
exc_result = ExecutionResult.from_dict(result_dict)
```

### Q3: 如何禁用自动执行？
A: 在 `ExecutionIntentDetector.detect()` 调用处设置 `is_admin=False` 或 `frontend_source 不为'sandbox'`

## 性能考量

- 执行追踪内存占用：每个事件约100字节，一般不超过10KB
- 执行意图检测耗时：<5ms
- 消息格式化耗时：<10ms
- 总体系统开销：可忽略

## 后续改进方向

1. **流式执行**: 支持边执行边输出（参考AstrBot的分句逻辑）
2. **执行历史**: 持久化存储执行记录用于审计
3. **高级信息面板**: 前端实时显示执行进度和堆栈
4. **超时管理**: 可配置的执行超时和中断机制
5. **资源监控**: 收集内存、CPU等执行时的资源使用
