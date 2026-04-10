# ShizukuClaw Agent系统架构优化方案

## 总体目标
参考AstrBot的Agent设计模式，改进ShizukuClaw的代码执行逻辑、输出格式和响应流程，但保留ShizukuClaw本地沙箱的简洁性，不采用Shipyard等外部沙箱依赖。

---

## 一、AstrBot设计核心特性分析

### 1. 响应流管理（Response Stream Pipeline）
**AstrBot特点：**
- 使用 `AgentResponse` 类统一响应格式
- 响应类型：`streaming_delta`、`tool_call`、`tool_result`、`llm_result` 等
- 支持异步生成器流式推送：`async for resp in agent_runner.step()`

**启发：**
- 应当实现响应类型标准化
- 支持工具调用和结果的分步推送
- 前端可以实时显示执行进度

### 2. 工具状态消息格式化（Tool Status Messaging）
**AstrBot特点：**
- `_build_tool_call_status_message()` 格式化工具调用信息
- `_build_tool_result_status_message()` 格式化工具结果
- 向用户显示："🔨 调用工具: {tool_name}"、"✅ {tool_name} 完成"等

**启发：**
- 改进现有工具输出的可读性
- 添加执行状态图标和消息
- 记录工具调用堆栈和执行时间

### 3. 执行意图检测（Execution Intent Detection）
**AstrBot特点：**
- 用户任务管理中内置优先级排序
- Skills系统可检测执行环境需求
- Agent自动选择合适的沙箱profile

**启发：**
- 将现有的"run_request"检测逻辑标准化
- 为不同执行类型（Python、Shell、Project Debug）提供专门处理
- 保证"显式执行请求"总是执行到完成

### 4. 分句和流式输出（Sentence-Level Streaming）
**AstrBot特点：**
- `_run_agent_feeder()` 使用正则 `r"([.。!！?？\n]+)"` 分句
- 分句后逐句推送，支持TTS实时播放
- 缓冲区管理避免分句错误

**启发：**
- 可用于支持实时输出和逐句播放
- ShizukuClaw暂可不实现，但架构应兼容

---

## 二、ShizukuClaw改进方案

### 2.1 新增：统一响应对象（ResponseMessage）

```python
# src/agent/response_types.py [新建文件]

from enum import Enum
from typing import Any, Optional, Dict
from dataclasses import dataclass, field

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

@dataclass
class ToolResultInfo:
    """工具执行结果信息"""
    call_id: str
    tool_name: str
    success: bool
    output: str
    duration: float = 0.0
    error: Optional[str] = None

@dataclass
class ResponseMessage:
    """统一的Agent响应消息"""
    type: ResponseType
    content: str = ""
    tool_call: Optional[ToolCallInfo] = None
    tool_result: Optional[ToolResultInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
```

### 2.2 改进：Agent执行跟踪（Execution Tracking）

**当前问题：**
- 工具调用和结果没有统一的追踪机制
- 前端无法显示执行进度
- Agent上下文中的自动执行缺乏足够的日志

**改进方案：**

```python
# src/agent/agent_execution_tracker.py [新建文件]

class ExecutionTracker:
    """追踪Agent工具执行过程"""
    
    def __init__(self):
        self.call_stack: List[ToolCallInfo] = []
        self.results: Dict[str, ToolResultInfo] = {}
        self.events: List[Dict] = []
    
    def record_tool_call(self, tool_name: str, args: Dict, call_id: str = ""):
        """记录工具调用"""
        call = ToolCallInfo(name=tool_name, args=args, call_id=call_id or self._gen_id())
        self.call_stack.append(call)
        self.events.append({
            "type": "tool_call",
            "tool_name": tool_name,
            "timestamp": time.time(),
            "call_id": call.call_id
        })
        return call.call_id
    
    def record_tool_result(self, call_id: str, success: bool, output: str, duration: float = 0.0):
        """记录工具结果"""
        result = ToolResultInfo(
            call_id=call_id,
            tool_name=self._get_tool_name(call_id),
            success=success,
            output=output,
            duration=duration
        )
        self.results[call_id] = result
        self.events.append({
            "type": "tool_result",
            "call_id": call_id,
            "success": success,
            "duration": duration,
            "timestamp": time.time()
        })
    
    def format_execution_summary(self) -> str:
        """格式化执行总结"""
        lines = ["## 执行过程\n"]
        for event in self.events:
            if event["type"] == "tool_call":
                lines.append(f"→ 调用工具：{event['tool_name']}")
            elif event["type"] == "tool_result":
                status = "✓" if event["success"] else "✗"
                lines.append(f"  {status} 完成 ({event['duration']:.2f}s)")
        return "\n".join(lines)
```

### 2.3 改进：工具输出格式化（Tool Output Formatting）

**当前问题：**
- 工具结果直接返回原始字符串
- 用户看不到工具调用状态和执行流程
- 错误信息格式不统一

**改进方案：**

```python
# src/agent/tool_message_formatter.py [新建文件]

class ToolMessageFormatter:
    """格式化工具相关的消息"""
    
    @staticmethod
    def format_tool_call(tool_name: str, args: Dict, call_id: str = "") -> str:
        """格式化工具调用消息"""
        icon = "🔧"
        args_str = json.dumps(args, ensure_ascii=False, indent=2)[:200]
        return f"{icon} **调用工具**: `{tool_name}`\n```json\n{args_str}\n```"
    
    @staticmethod
    def format_tool_result(tool_name: str, success: bool, output: str, duration: float = 0.0) -> str:
        """格式化工具结果消息"""
        status_icon = "✅" if success else "❌"
        time_str = f"({duration:.2f}s)" if duration > 0 else ""
        
        # 截断超长输出
        output_display = output[:500] + "..." if len(output) > 500 else output
        
        result = f"{status_icon} **{tool_name} 完成** {time_str}\n"
        if output_display:
            result += f"```\n{output_display}\n```"
        return result
    
    @staticmethod
    def format_execution_summary(tracker: ExecutionTracker) -> str:
        """格式化执行总结（在Agent响应后面）"""
        summary = "\n\n---\n### 执行过程总结\n"
        
        for i, event in enumerate(tracker.events, 1):
            if event["type"] == "tool_call":
                summary += f"\n**{i}. 工具调用**: `{event['tool_name']}`\n"
            elif event["type"] == "tool_result":
                result_info = tracker.results.get(event["call_id"])
                if result_info:
                    status = "成功" if event["success"] else "失败"
                    summary += f"   - 结果: {status} ({event['duration']:.2f}s)\n"
        
        return summary
```

### 2.4 改进：Agent系统提示词（System Prompt Enhancement）

**当前问题：**
- "执行必定执行"的保证只通过正则匹配
- 没有在系统提示中明确指导Agent的方法论
- 缺乏对"执行阶段"vs"思考阶段"的区分

**改进方案：**

```python
# 在 src/agent/agent_manager.py 的 get_agent_context() 中增强提示

AGENT_EXECUTION_COMMITMENT = """
[执行承诺 - Critical Requirement]

当用户明确要求您执行、运行、调试或测试某个项目/脚本时，您必须：

1. **识别执行意图**：
   - 文本包含"运行"、"执行"、"调试"、"检查"、"测试"？ 
   - 是否关联到一个具体的项目、文件或命令？

2. **执行优先级**：
   - 使用 exec_python 执行Python脚本
   - 使用 run_project_debug 运行完整项目
   - 使用 execute_shell 运行系统命令

3. **执行保证**：
   - 不能仅提供代码建议，必须实际执行
   - 捕获完整的输出（stdout、stderr、return code）
   - 在最终答复中包含实际执行结果

4. **格式要求**：
   - 执行结果必须包含 [执行结果] 段落
   - 显示返回码和重要输出
   - 如果失败，分析原因并建议修复

示例：
❌ 不允许这样做: "以下是运行该脚本的代码 `python main.py`..."
✅ 应该这样做: 
   1. 实际调用 exec_python 工具: `code = "..."`
   2. 捕获输出
   3. 回复: "我已执行了脚本。[执行结果] 返回码: 0, 输出: ..."
"""
```

### 2.5 改进：自动执行检测逻辑（Auto-Execution Detection）

**当前问题：**
- 正则表达式可能误触发（"代码运行良好"）
- 缺乏上下文感知
- 没有记录为什么自动执行

**改进方案：**

```python
# src/agent/execution_intent_detector.py [新建文件]

class ExecutionIntentDetector:
    """检测用户的执行意图"""
    
    # 执行关键词（动词）
    EXECUTION_VERBS = {
        '运行', '执行', '跑起来', '调试', '检查', '测试',
        '启动', '运行一遍', '试试看', '验证',
        'run', 'execute', 'debug', 'test', 'check'
    }
    
    # 否定词（排除误触发）
    NEGATION_WORDS = {'不', '无法', '错误', '问题', '可能', '试过', '已'}
    
    @staticmethod
    def detect(user_input: str, is_admin: bool = False, frontend_source: str = '') -> dict:
        """
        检测执行意图
        返回: {
            "is_execution_request": bool,
            "confidence": float (0-1),
            "reason": str,
            "suggested_target": str or None
        }
        """
        
        # 基础检查
        if not user_input or not is_admin or frontend_source != 'sandbox':
            return {"is_execution_request": False, "confidence": 0.0, "reason": "context_mismatch"}
        
        text_lower = user_input.lower()
        
        # 检查是否包含执行关键词
        has_verb = any(verb in text_lower for verb in ExecutionIntentDetector.EXECUTION_VERBS)
        if not has_verb:
            return {"is_execution_request": False, "confidence": 0.0, "reason": "no_execution_verb"}
        
        # 检查是否在否定语境
        has_negation = any(neg in user_input for neg in ExecutionIntentDetector.NEGATION_WORDS)
        if has_negation:
            # 计算前后距离，确定是否真的是否定
            confidence = 0.3  # 低置信度，但不完全排除
        else:
            confidence = 0.9
        
        # 尝试识别执行目标
        target = ExecutionIntentDetector._extract_target(user_input)
        
        return {
            "is_execution_request": confidence > 0.5,
            "confidence": confidence,
            "reason": "explicit_request",
            "suggested_target": target
        }
    
    @staticmethod
    def _extract_target(text: str) -> Optional[str]:
        """从用户输入中提取运行目标"""
        # 匹配 "运行 xxx.py" 或 "执行 xxx"
        match = re.search(r'(?:运行|执行|调试|运行一遍)\s+(.+?)(?:\s+|，|。|$)', text)
        if match:
            target = match.group(1).strip()
            # 移除尾部的中文标点
            target = re.sub(r'[，。！？，、；：]+$', '', target)
            return target
        return None
```

### 2.6 改进：执行结果封装（Execution Result Wrapper）

**当前问题：**
- run_project_debug 和 exec_python 的输出格式不统一
- 缺乏结构化的ret urn code、stdout、stderr 分离
- 难以前端解析和展示

**改进方案：**

```python
# src/agent/sandbox_execution_result.py [新建文件]

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
        """转换为字典"""
        return {
            "success": self.success,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration": self.duration,
            "type": self.execution_type
        }
    
    def format_for_user(self) -> str:
        """格式化为用户友好的字符串"""
        status_icon = "✅" if self.success else "❌"
        result_text = f"{status_icon} **执行{('成功' if self.success else '失败')}**\n\n"
        result_text += f"**执行时间**: {self.duration:.2f}s\n"
        result_text += f"**返回码**: {self.return_code}\n\n"
        
        if self.stdout:
            result_text += "**输出**:\n```\n" + self.stdout[:1000] + "\n```\n\n"
        
        if self.stderr:
            result_text += "**错误**:\n```\n" + self.stderr[:1000] + "\n```\n"
        
        return result_text
    
    def format_for_ai(self) -> str:
        """格式化为AI友好的字符串（用于传递给下一轮LLM）"""
        lines = [f"[执行结果]"]
        lines.append(f"状态: {'成功' if self.success else '失败'}")
        lines.append(f"返回码: {self.return_code}")
        if self.stdout:
            lines.append(f"标准输出:\n{self.stdout[:2000]}")
        if self.stderr:
            lines.append(f"标准错误:\n{self.stderr[:1000]}")
        lines.append(f"耗时: {self.duration:.2f}s")
        return "\n".join(lines)
```

---

## 三、实施路线图

### 第1阶段（响应格式标准化）
- [ ] 创建 `response_types.py` 定义AgentResponse
- [ ] 创建 `tool_message_formatter.py` 格式化工具消息
- [ ] 改进工具调用后的输出格式

### 第2阶段（执行追踪和检测）
- [ ] 创建 `agent_execution_tracker.py` 追踪工具执行
- [ ] 创建 `execution_intent_detector.py` 检测执行意图
- [ ] 集成到 `ai_chat_system.py` 的执行逻辑

### 第3阶段（结构化执行结果）
- [ ] 创建 `sandbox_execution_result.py` 封装执行结果
- [ ] 修改 `agent_sandbox.py` 的 `exec_python()` 和 `run_project_debug()` 返回结构化结果
- [ ] 前端适配新的结果格式

### 第4阶段（Agent上下文增强）
- [ ] 增强 `agent_manager.py` 的系统提示词
- [ ] 集成执行承诺说明
- [ ] 添加执行保证逻辑

### 第5阶段（前端支持）
- [ ] control_panel.html 新增执行进度显示
- [ ] 支持渲染结构化的工具调用和结果
- [ ] 实时显示执行堆栈

---

## 四、与AstrBot的对比总结

| 方面 | AstrBot | ShizukuClaw (改进后) | 差异 |
|------|---------|-------------------|------|
| **沙箱类型** | Shipyard Neo (Docker) | 本地进程 | ShizukuClaw保持简洁 |
| **响应格式** | AgentResponse枚举 | ResponseMessage数据类 | 功能相似，适配本地 |
| **工具输出** | 流式AgentResponse | 格式化字符串+metadata | 兼容前端显示 |
| **执行追踪** | run_agent异步生成器 | ExecutionTracker记录 | 异步简化为记录型 |
| **执行保证** | 系统提示+自动检测 | 相同，更强化 | 相同理念 |
| **分句流式** | _run_agent_feeder分句 | 可选择实现 | ShizukuClaw暂不需要 |

---

## 五、具体代码改进示例

### 示例1：改进的Agent上下文（agent_manager.py）

```python
def get_agent_context(self):
    """构建Agent执行上下文"""
    try:
        plan = self.planner.load_plan()
        memory_packet = self.memory.build_context_packet()
        
        context = f"""
[Agent能力]
- 文件系统: 读写删除文件，创建目录
- Python执行: 在沙箱中运行Python脚本
- 项目调试: 运行项目测试和调试
- 系统命令: 执行shell命令

[执行承诺 - 必读]
当用户明确要求"运行"、"执行"、"调试"或"测试"时：
1. 识别要执行的目标（文件名或项目）
2. 选择合适的工具执行（exec_python / run_project_debug）
3. 捕获并报告执行结果（返回码+输出）
4. 在回复中包含[执行结果]段落

示例:
→ 用户: "运行 snake_game/snake.py 并检查错误"
✓ 你应该:
  1. 调用exec_python工具，目标是snake_game/snake.py
  2. 获取执行输出和错误
  3. 回复: "我已执行了脚本。[执行结果] 返回码: ..., 输出: ..."

[当前计划]
{plan}

[记忆包]
{memory_packet}
"""
        return context
    except Exception as e:
        return f"[Agent上下文错误: {str(e)}]"
```

### 示例2：改进的工具执行结果处理（agent_sandbox.py）

```python
def execute_python(self, code: str, filename: str = 'script.py') -> dict:
    """执行Python代码 - 返回结构化结果"""
    import time
    start_time = time.time()
    
    safe_path = os.path.join(self.workspace_dir, filename)
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
            timeout=90
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

---

## 六、迁移检查清单

- [ ] 所有新文件创建完毕
- [ ] response_types.py 导入到 ai_chat_system.py
- [ ] agent_execution_tracker.py 集成到 execute_tool()
- [ ] tool_message_formatter.py 用于格式化输出
- [ ] execution_intent_detector.py 替代旧的正则检测
- [ ] sandbox_execution_result.py 结构化返回值
- [ ] 系统提示词更新
- [ ] 前端 control_panel.html 适配新响应格式
- [ ] 测试：执行项目请求并验证完整性
- [ ] 测试：检查执行进度是否可视化

---

## 七、参考资源

- AstrBot Agent 执行: `astrbot/core/astr_agent_run_util.py`
- AstrBot 工具消息格式: `astrbot/core/astr_agent_run_util.py` 中的 `_build_tool_*` 函数
- AstrBot 沙箱配置: 文档 `docs/zh/use/astrbot-agent-sandbox.md`
- ShizukuClaw 当前实现: `src/agent/agent_manager.py`, `src/agent/agent_sandbox.py`
