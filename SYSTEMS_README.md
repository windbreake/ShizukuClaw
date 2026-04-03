# 新系统文档

本项目已增加以下5大系统模块，保留现有web界面布局和风格不变，通过后端API接口暴露功能。

## 系统概览

### 1. 增强型日志系统 (`enhanced_logging.py`)

提供类似AstR BOT的直观日志格式，支持颜色输出和结构化日志存储。

**主要功能：**
- 彩色日志输出（控制台）
- 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL, SUCCESS
- 内存日志条目存储（可通过API查询）
- 日志过滤和限制

**API端点：**

```bash
# 获取日志
GET /api/systems/logs?level=INFO&limit=100

# 清除日志
POST /api/systems/logs/clear
```

**Python使用示例：**

```python
from src.enhanced_logging import get_enhanced_logger

logger = get_enhanced_logger()
logger.info("这是一条信息")
logger.success("操作成功！")
logger.error("发生错误", details={'code': 500})

# 获取日志条目
entries = logger.get_entries(level='INFO', limit=50)
```

---

### 2. Agent定时任务系统 (`agent_task_scheduler.py`)

灵活的任务调度系统，支持一次性任务、循环任务和Cron任务。

**任务类型：**
- `ONE_TIME`: 一次性任务（在指定时间执行）
- `RECURRING`: 循环任务（按间隔时间重复执行）
- `CRON`: Cron任务（基于Cron表达式）

**示例：**

```python
from src.agent_task_scheduler import get_task_scheduler, AgentTask, TaskType
from datetime import datetime, timedelta

scheduler = get_task_scheduler()

# 创建明天下午14:00的提醒任务
tomorrow_2pm = (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0)
task = AgentTask(
    name="下午喝水提醒",
    description="提醒用户喝水",
    task_type=TaskType.ONE_TIME.value,
    scheduled_time=tomorrow_2pm.isoformat(),
    command="remind_water",
    args={"message": "该喝水了！"}
)

# 定义任务回调
def remind_water(message):
    print(f"💧 {message}")
    return {"status": "success"}

# 添加任务
task_id = scheduler.add_task(task, callback=remind_water)
```

**API端点：**

```bash
# 列表任务
GET /api/systems/tasks?status=pending

# 创建任务
POST /api/systems/tasks
{
    "name": "下午喝水提醒",
    "task_type": "one_time",
    "scheduled_time": "2026-04-05T14:00:00",
    "command": "remind",
    "args": {"msg": "喝水"}
}

# 获取任务详情
GET /api/systems/tasks/{task_id}

# 更新任务
PUT /api/systems/tasks/{task_id}

# 取消/删除任务
POST /api/systems/tasks/{task_id}/cancel
DELETE /api/systems/tasks/{task_id}

# 获取任务执行结果
GET /api/systems/tasks/{task_id}/results
```

---

### 3. MCP系统 (`mcp_manager.py`)

Model Context Protocol集成管理系统，用于管理外部MCP服务器、资源和工具。

**核心概念：**
- **Server**: MCP服务器配置（stdio、SSE、HTTP）
- **Resource**: MCP资源（从服务器获取的资源）
- **Tool**: MCP工具定义（可执行的工具）

**示例：**

```python
from src.mcp_manager import get_mcp_manager, MCPServer

manager = get_mcp_manager()

# 添加MCP服务器
server = MCPServer(
    name="文件系统服务器",
    type="stdio",
    command="python",
    args=["-m", "mcp_file_server"],
    capabilities={
        "resources": True,
        "tools": True,
        "sampling": False
    }
)
server_id = manager.add_server(server)

# 列表服务器
servers = manager.list_servers(enabled_only=True)

# 获取服务器工具
tools = manager.list_tools(server_id=server_id, enabled_only=True)
```

**API端点：**

```bash
# MCP服务器管理
GET /api/systems/mcp/servers
POST /api/systems/mcp/servers
GET /api/systems/mcp/servers/{server_id}
PUT /api/systems/mcp/servers/{server_id}
DELETE /api/systems/mcp/servers/{server_id}

# 资源管理
GET /api/systems/knowledge/entries  # 也用于资源
```

---

### 4. 知识库/词库系统 (`knowledge_base_manager.py`)

强大的知识库管理系统，支持多种条目类型、搜索、标签和分类。

**条目类型：**
- `KNOWLEDGE`: 知识条目
- `TERM`: 术语条目
- `PHRASE`: 短语条目
- `FACT`: 事实条目
- `RULE`: 规则条目

**示例：**

```python
from src.knowledge_base_manager import get_knowledge_base_manager, KnowledgeEntry, EntryType, Glossary

kb = get_knowledge_base_manager()

# 添加知识条目
entry = KnowledgeEntry(
    title="Python装饰器",
    content="装饰器是一个高级函数，接收一个函数作为参数...",
    entry_type=EntryType.KNOWLEDGE.value,
    category="编程",
    tags=["python", "进阶"],
    keywords=["decorator", "高阶函数"],
    priority=5,
    author="管理员"
)
entry_id = kb.add_entry(entry)

# 搜索条目
results = kb.search_entries("装饰器", limit=10)

# 创建词库
glossary = Glossary(
    name="AI术语",
    language="zh_CN"
)
glossary_id = kb.add_glossary(glossary)

# 添加术语
kb.add_term_to_glossary(glossary_id, "LLM", "大型语言模型")
kb.add_term_to_glossary(glossary_id, "RAG", "检索增强生成")
```

**API端点：**

```bash
# 知识库条目
GET /api/systems/knowledge/entries?category=编程&type=knowledge
POST /api/systems/knowledge/entries
GET /api/systems/knowledge/entries/{entry_id}
PUT /api/systems/knowledge/entries/{entry_id}
DELETE /api/systems/knowledge/entries/{entry_id}

# 搜索
GET /api/systems/knowledge/entries/search?q=装饰器&limit=20

# 分类
GET /api/systems/knowledge/categories
```

---

### 5. 自定义指令系统 (`instruction_manager.py`)

参考AstR BOT，提供完整的Agent行为设定系统。

**指令类型：**
- `SYSTEM_PROMPT`: 系统指令
- `PERSONALITY`: 人格设定
- `BEHAVIOR`: 行为规则
- `TRIGGER`: 触发规则
- `RESPONSE_TEMPLATE`: 回复模板

**示例：**

```python
from src.instruction_manager import (
    get_instruction_manager, AgentInstruction, Personality, BehaviorRule,
    InstructionType
)

manager = get_instruction_manager()

# 创建系统提示
instruction = AgentInstruction(
    name="基础人格",
    instruction_type=InstructionType.SYSTEM_PROMPT.value,
    content="你是一个友善的AI助手，名字叫小雫。",
    priority=10,
    enabled=True
)
manager.add_instruction(instruction)

# 创建人格配置
personality = Personality(
    name="可爱少女",
    traits={
        "cheerfulness": 0.9,
        "professionalism": 0.6,
        "humor": 0.8
    },
    tone="casual",
    speaking_style="cute",
    emoji_usage=True,
    response_length="medium"
)
manager.add_personality(personality)

# 创建行为规则
rule = BehaviorRule(
    name="问候规则",
    trigger_pattern="你好|Hi|Hello",
    trigger_type="regex",
    action_type="response",
    action_content="喵~你好呀！很开心见到你~",
    priority=10,
    weight=1.0
)
manager.add_behavior_rule(rule)

# 检查匹配的规则
matched = manager.check_behavior_rules("你好啊", agent_id="default")
```

**API端点：**

```bash
# 指令管理
GET /api/systems/instructions?type=system_prompt&agent_id=default
POST /api/systems/instructions
PUT /api/systems/instructions/{instruction_id}
DELETE /api/systems/instructions/{instruction_id}

# 人格管理
GET /api/systems/personalities
POST /api/systems/personalities
PUT /api/systems/personalities/{personality_id}
DELETE /api/systems/personalities/{personality_id}

# 行为规则管理
GET /api/systems/behavior-rules
POST /api/systems/behavior-rules
PUT /api/systems/behavior-rules/{rule_id}
DELETE /api/systems/behavior-rules/{rule_id}

# 系统状态
GET /api/systems/system-status
```

---

## 数据存储

所有系统都将数据持久化到本地JSON文件：

```
data/
├── logs/
│   └── enhanced.log
├── tasks/
│   └── tasks.json
├── mcp/
│   ├── servers.json
│   ├── resources.json
│   └── tools.json
├── knowledge_base/
│   ├── entries.json
│   ├── glossaries.json
│   └── index.json
└── instructions/
    ├── instructions.json
    ├── personalities.json
    └── behavior_rules.json
```

---

## 集成到web_server

所有系统已经自动集成到Flask web服务器中：

```python
# 自动注册蓝图
from src.systems_api import systems_bp
app.register_blueprint(systems_bp)
```

所有API只需访问 `http://localhost:8888/api/systems/...` 即可使用。

---

## 安装依赖

确保安装了APScheduler：

```bash
pip install apscheduler
```

---

## 使用建议

1. **日志系统**：在关键操作处添加日志记录，便于调试和监控
2. **任务系统**：用于定时提醒、定期清理、定时同步等
3. **MCP系统**：集成外部工具和资源，扩展Agent能力
4. **知识库系统**：存储项目相关的知识、文档、术语等
5. **指令系统**：定制Agent行为和人格，提供一致的交互体验

---

## 示例：综合应用

```python
# 创建一个完整的Agent设置示例
from datetime import datetime, timedelta
from src.enhanced_logging import get_enhanced_logger
from src.agent_task_scheduler import get_task_scheduler, AgentTask, TaskType
from src.instruction_manager import get_instruction_manager, AgentInstruction, Personality, InstructionType
from src.knowledge_base_manager import get_knowledge_base_manager, KnowledgeEntry, EntryType

# 1. 初始化各个系统
logger = get_enhanced_logger()
scheduler = get_task_scheduler()
instr_mgr = get_instruction_manager()
kb_mgr = get_knowledge_base_manager()

# 2. 设置Agent人格
personality = Personality(
    name="Shizuku",
    traits={
        "cheerfulness": 0.85,
        "helpfulness": 0.9,
        "humor": 0.7
    },
    tone="casual",
    emoji_usage=True
)
instr_mgr.add_personality(personality)

# 3. 添加系统提示
sys_prompt = AgentInstruction(
    name="系统指令",
    instruction_type=InstructionType.SYSTEM_PROMPT.value,
    content="你是一个友善、聪慧的AI助手小雫。",
    priority=100
)
instr_mgr.add_instruction(sys_prompt)

# 4. 添加知识库条目
kb_entry = KnowledgeEntry(
    title="项目信息",
    content="这是Shizuku机器人项目",
    category="基础信息",
    tags=["project", "info"]
)
kb_mgr.add_entry(kb_entry)

# 5. 创建定时任务
task = AgentTask(
    name="每日问候",
    task_type=TaskType.CRON.value,
    cron_expression="0 9 * * *",  # 每天9点
    command="greeting"
)
scheduler.add_task(task, callback=lambda: logger.info("早上好~"))

logger.success("所有系统初始化完成")
```

---

## API响应格式

所有API响应遵循统一格式：

**成功响应：**
```json
{
    "code": 0,
    "message": "success",
    "data": {...},
    "count": 10
}
```

**错误响应：**
```json
{
    "code": 400,
    "message": "错误描述"
}
```

---

更多信息请参考各模块的源代码。
