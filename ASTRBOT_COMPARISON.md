# AstrBot vs ShizukuClaw(改进) - 架构对比分析

## 概述

本文档详细对比AstrBot的Agent架构设计与改进后ShizukuClaw系统的设计，展示两者的相似之处、差异以及设计考量。

---

## 一、整体架构对比

### AstrBot架构

```
LLM Provider
    ↓
ProviderRequest (请求对象)
    ↓
AgentRunner (核心Agent运行器)
    ├─ ToolLoopAgentRunner (工具循环执行)
    ├─ DashscopeAgentRunner (第三方平台)
    └─ CozeAgentRunner (其他平台)
    ↓
FunctionToolExecutor (工具执行器)
    ↓
Tool Registry (Shipyard Sandbox)
    ├─ Python Tool
    ├─ Shell Tool
    └─ Browser Tool
    ↓
AgentResponse (统一响应格式)
    ├─ streaming_delta
    ├─ tool_call
    ├─ tool_result
    └─ llm_result
    ↓
run_agent() (异步流式生成器)
    └─ 向前端逐步推送响应
```

### ShizukuClaw (改进) 架构

```
OpenAI API
    ↓
AIChatSystem.chat() (聊天主方法)
    ↓
AgentManager (管理层)
    ├─ ExecutionTracker (执行追踪)
    ├─ ExecutionIntentDetector (意图检测)
    ├─ ToolMessageFormatter (消息格式化)
    └─ AgentSandbox (工具执行)
    ↓
Sandbox (本地进程沙箱)
    ├─ exec_python
    ├─ execute_shell
    └─ run_project_debug
    ↓
ExecutionResult (结构化结果)
    └─ to_dict() / format_for_user() / format_for_ai()
    ↓
ResponseMessage (统一响应格式)
    └─ 返回给前端作为聊天回复的一部分
```

---

## 二、核心设计对比

### 2.1 响应流管理（Response Stream Pipeline）

#### AstrBot 做法

**使用异步生成器流式推送**:
```python
async for resp in agent_runner.step():
    if resp.type == "streaming_delta":
        yield AgentResponse(type="streaming_delta", data=...)
    elif resp.type == "tool_call":
        yield AgentResponse(type="tool_call", data=...)
    elif resp.type == "tool_result":
        yield AgentResponse(type="tool_result", data=...)
```

**优点**:
- 支持多种响应类型的实时推送
- 前端可逐步显示LLM思考过程、工具调用状态
- 适合长时间运行的任务（如浏览器自动化）
- 支持流式TTS输出

**缺点**:
- 复杂度较高，需要异步编程
- 对前端框架要求较高
- 网络连接不稳定时容易中断

#### ShizukuClaw (改进) 做法

**使用同步结果对象记录**:
```python
tracker = ExecutionTracker()
for tool_call in tool_calls:
    call_id = tracker.record_tool_call(tool_name, args)
    result = execute_tool(tool_name, args)
    tracker.record_tool_result(call_id, success, output, duration)

# 在最终响应中附带追踪数据
return {
    "reply": ai_response,
    "execution_tracker": tracker.to_dict()
}
```

**优点**:
- 实现简单，易于维护
- 不需要异步/流式基础设施
- 适合本地快速执行的任务
- 前端易于集成

**缺点**:
- 无法实时流式显示执行过程
- 长时间任务用户体验较差
- 执行信息在任务完成后才返回

#### 设计选择理由

ShizukuClaw选择**同步记录**而非AstrBot的**异步流式**是因为：
1. **本地执行** - 大多数任务在1-10秒内完成
2. **简洁性** - ShizukuClaw强调代码可维护性
3. **渐进式升级** - 可以后续添加异步支持但不强制

---

### 2.2 工具输出格式化

#### AstrBot 做法

```python
def _build_tool_call_status_message(tool_info: dict | None) -> str:
    """格式化工具调用消息"""
    # 生成 "🔨 调用工具: xxx" 格式的消息

def _build_tool_result_status_message(msg_chain: MessageChain, ...) -> str:
    """格式化工具结果消息"""
    # 生成带图标的结果消息
    # 消息类型: "tool_call" (分段)
    # 这触发平台的消息分段逻辑
```

**特点**:
- 消息类型驱动的格式化
- 与流式推送紧密结合
- 平台可根据消息类型自适应显示

#### ShizukuClaw (改进) 做法

```python
class ToolMessageFormatter:
    @staticmethod
    def format_tool_call(tool_call: ToolCallInfo) -> str:
        # 返回 "🔧 **调用工具**: `tool_name`" 格式
    
    @staticmethod
    def format_tool_result(tool_result: ToolResultInfo) -> str:
        # 返回 "✅ **tool_name 完成**" 格式
    
    @staticmethod
    def format_execution_summary(tracker) -> str:
        # 返回完整的执行总结（用于追加到AI响应）
```

**特点**:
- 简单的字符串格式化方法
- 包括执行总结的汇总功能
- 支持多种输出格式（用户友好/AI友好）

#### 对比总结

| 方面 | AstrBot | ShizukuClaw |
|------|---------|-----------|
| 集成方式 | 流式推送与消息类型 | 字符串拼接 |
| 适用场景 | 实时、长时间任务 | 快速、本地任务 |
| 实现复杂度 | 中等 | 低 |
| 用户体验 | 渐进式反馈 | 汇总反馈 |

---

### 2.3 执行意图检测

#### AstrBot 做法

- **Skills系统** - 通过YAML元数据声明执行需求
- **任务优先级** - 内置任务管理系统自动优化
- **平台检测** - 自动匹配合适的沙箱profile
- **微粒度控制** - 可配置browser capability等

#### ShizukuClaw (改进) 做法

```python
class ExecutionIntentDetector:
    # 关键词集合（动词、否定词、排除短语）
    EXECUTION_VERBS = {'运行', '执行', '调试', ...}
    NEGATION_WORDS = {'不', '无法', ...}
    EXCLUSION_PHRASES = {'代码运行良好', ...}
    
    @staticmethod
    def detect(user_input, is_admin, frontend_source):
        # 返回: {is_execution_request, confidence, reason, suggested_target, risk_level}
```

**特点**:
- 关键词集合 + 否定语境检查
- 置信度评分（0-1）
- 目标提取（自动识别要执行的文件）
- 风险等级评估（high/medium/low）

#### 对比总结

| 方面 | AstrBot | ShizukuClaw |
|------|---------|-----------|
| 检测方式 | 元数据声明 | 关键词+语境分析 |
| 准确度 | 高（显式声明） | 中（启发式） |
| 易用性 | 需学习YAML语法 | 自动开箱即用 |
| 覆盖范围 | 注册的skills | 任何用户输入 |

---

### 2.4 结果数据结构

#### AstrBot 做法

```python
# 执行结果由工具直接返回（无统一格式）
# 由 ToolExecResult 包装：
@dataclass
class ToolExecResult:
    error: str | None
    data: Any  # 工具返回的任意数据
    extra: dict  # 额外元数据
```

#### ShizukuClaw (改进) 做法

```python
@dataclass
class ExecutionResult:
    success: bool
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    execution_type: str = "python"
    
    # 多种导出格式
    def to_dict(self) -> Dict  # JSON
    def format_for_user(self) -> str  # UI显示
    def format_for_ai(self) -> str  # 传给LLM
```

**优点**:
- 结构化的执行结果（返回码+输出+错误分离）
- 自动的格式转换方法
- 便于前端解析和显示
- 支持执行时间追踪

---

### 2.5 Agent系统提示词

#### AstrBot 做法

- **系统提示是动态构建的** - 包括可用的工具列表
- **工具优先级指导** - 在提示中强调何时使用哪个工具
- **Profile感知** - 根据当前沙箱profile调整提示

#### ShizukuClaw (改进) 做法

```python
AGENT_EXECUTION_COMMITMENT = """
[执行承诺 - 关键要求]

当用户明确要求执行/运行/调试时：
1. 识别执行意图
2. 选择合适工具（exec_python / run_project_debug）
3. 执行必定执行（不能只提供代码）
4. 报告完整的执行结果
"""

# 在Agent上下文中明确指导：
- 何时使用 delete_file vs delete_file_content
- 何时使用 write_file vs append_file_content
- 何时使用 exec_python vs run_project_debug
```

**优点**:
- 显式清晰的执行保证
- 工具选择策略明确
- 易于维护和调试

---

## 三、沙箱设计对比

### AstrBot (Shipyard Neo)

```
Bay (控制面)
├─ 创建/销毁沙箱
├─ 管理生命周期和TTL
└─ 资源隔离和配额

Ship (Python/Shell/文件系统)
├─ Python 3.11+ 执行
├─ Shell 命令执行
└─ 文件系统隔离 (/workspace)

Gull (浏览器自动化)
├─ Playwright 支持
├─ 截图和交互
└─ Cookie/Session 管理

Warm Pool (预热池)
├─ 保持N个待命实例
├─ 减少冷启动延迟
└─ 基于profile配置
```

**特点**:
- ✅ 完全隔离，安全性最高
- ✅ 多容器架构，功能模块化
- ✅ 生产就绪，支持HA部署
- ✅ 浏览器自动化能力
- ❌ 复杂度高，部署成本大
- ❌ 额外的网络开销

### ShizukuClaw（本地进程沙箱）

```
AgentSandbox
├─ exec_python
│  └─ subprocess.run([sys.executable, ...])
├─ execute_shell
│  └─ subprocess.run([shell_cmd], shell=True)
├─ run_project_debug
│  └─ pytest / python main.py
└─ 工作区隔离
   └─ self.root_dir (agent_datas/workspace)
```

**特点**:
- ✅ 简洁轻量，零额外部署
- ✅ 直接本地执行，性能好
- ✅ 易于调试和监控
- ❌ 安全性依赖于操作系统
- ❌ 无浏览器支持
- ❌ 跨平台兼容性问题

### 设计权衡

ShizukuClaw选择本地沙箱是因为：
1. **快速迭代** - 开发阶段无需Shipyard部署
2. **可访问性** - 个人用户和小团队易于使用
3. **调试友好** - 直接查看进程和文件
4. **资源消耗** - Windows客户端运行更轻便

---

## 四、代码执行流程对比

### AstrBot 执行流程

```
用户输入
    ↓
ProviderRequest 构建
    ↓
AgentRunner.reset() 将请求和工具注入
    ↓
async for step() in agent_runner.step():
    ├─ LLM 调用 (流式)
    ├─ 工具调用识别
    ├─ 工具执行
    └─ 结果反馈给LLM
    ↓
最多迭代 max_step 次 (默认30)
    ↓
最终 LLM 响应通过异步生成器推送
```

### ShizukuClaw 执行流程

```
用户输入
    ↓
执行意图检测 (ExecutionIntentDetector)
    ↓
AIChatSystem.chat()
    ├─ 构建messages + system_prompt
    ├─ LLM 调用 (非流式)
    ├─ 解析tool_calls（如果有）
    ├─ 逐个执行工具
    │  └─ 记录到ExecutionTracker
    ├─ 收集工具结果
    ├─ 重新调用LLM作最终总结
    │  或直接返回结果
    └─ 自动执行检测（如果LLM没调用工具）
    ↓
返回结构化响应 {reply, execution_tracker, debug}
```

#### 关键差异

| 方面 | AstrBot | ShizukuClaw |
|------|---------|-----------|
| LLM调用 | 流式多次 | 非流式1-2次 |
| 推送方式 | 异步生成器 | 同步返回 |
| 工具循环 | 内部自动 | 外部手动 |
| 中间件 | 最少（直接LLM） | 多步（detect→chat→track→execute） |
| 复杂度 | 高（内部逻辑复杂） | 中（流程清晰） |

---

## 五、学习和改进建议

### ShizukuClaw 可参考的 AstrBot 特性

1. **流式输出支持** - 可选实现 `_run_agent_feeder()` 的分句逻辑
2. **浏览器自动化** - 后续可扩展支持Playwright
3. **多Provider支持** - 参考ToolLoopAgentRunner的抽象设计
4. **会话管理** - 参考Bay的沙箱生命周期管理
5. **技能市场** - 参考AstrBot的Skills发布和版本管理

### AstrBot 可学习的 ShizukuClaw 方案

1. **执行意图检测器** - 更智能的中文语境分析
2. **结构化结果对象** - ExecutionResult的多格式导出
3. **执行追踪** - 简化的追踪方案（vs AstrBot的复杂日志系统）
4. **本地沙箱** - 小规模部署的轻量选项

---

## 六、后续升级路线

### ShizukuClaw 如果要向 AstrBot 靠拢

**Phase 1** (现在):
- 执行意图检测器
- 执行追踪器
- 结构化结果

**Phase 2** (可选):
- 异步工具执行支持
- 流式结果推送
- 多工具并行执行

**Phase 3** (未来):
- 迁移到外部沙箱（如Shipyard）
- 浏览器自动化支持
- Skills市场集成

### AstrBot 如果要简化某些复杂性

- 参考ExecutionIntentDetector的简化版本
- 支持本地沙箱选项用于开发环境
- 简化系统提示词的构建逻辑

---

## 总结

两个系统代表了不同的设计哲学：

- **AstrBot** = 追求功能完整、生产就绪、可扩展性
- **ShizukuClaw** = 追求简洁易用、快速迭代、易于理解

改进后的ShizukuClaw吸取了AstrBot的最佳实践（执行保证、工具追踪、消息格式化），但保持了自己的轻量化特色（本地沙箱、同步执行、明确的逻辑流）。

两者都值得学习，取决于具体的项目需求和约束。
