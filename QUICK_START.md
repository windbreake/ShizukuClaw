# 新系统快速开始指南

## 📦 安装依赖

```bash
# 安装所有依赖
pip install -r requirements.txt

# 或单独安装APScheduler
pip install apscheduler~=3.10.4
```

## 🚀 快速开始

### 1. 初始化系统（首次运行）

```bash
python init_systems.py
```

这将：
- 初始化所有系统模块
- 创建默认配置
- 生成示例数据
- 启动定时任务调度器

### 2. 启动Web服务器

```bash
python main.py
# 或选择菜单选项启动web服务
```

服务器启动后，所有系统API会自动注册：
- 基础地址：`http://localhost:8888/api/systems/`

## 🎯 常见使用场景

### 场景1：创建日程提醒

```python
import requests
from datetime import datetime, timedelta

# 创建明天下午3点的提醒
tomorrow_3pm = (datetime.now() + timedelta(days=1)).replace(hour=15, minute=0)

response = requests.post(
    'http://localhost:8888/api/systems/tasks',
    json={
        'name': '项目截止日期提醒',
        'task_type': 'one_time',
        'scheduled_time': tomorrow_3pm.isoformat(),
        'command': 'remind',
        'args': {'project': 'MyProject'},
        'notify_on_complete': True
    }
)

print(f"任务ID: {response.json()['data']['id']}")
```

### 场景2：添加知识库条目

```python
import requests

response = requests.post(
    'http://localhost:8888/api/systems/knowledge/entries',
    json={
        'title': '项目配置说明',
        'content': '项目配置文件位于data/config.json...',
        'type': 'knowledge',
        'category': '文档',
        'tags': ['config', 'documentation'],
        'keywords': ['配置', '设置'],
        'priority': 5
    }
)

print(f"条目ID: {response.json()['data']['id']}")
```

### 场景3：配置Agent人格

```python
import requests

# 创建新人格
response = requests.post(
    'http://localhost:8888/api/systems/personalities',
    json={
        'name': '专业助手',
        'description': '专业、严谨的AI助手人格',
        'tone': 'formal',
        'traits': {
            'professionalism': 0.95,
            'cheerfulness': 0.4,
            'humor': 0.3
        },
        'response_length': 'medium',
        'emoji_usage': False
    }
)

personality_id = response.json()['data']['id']
print(f"人格ID: {personality_id}")
```

### 场景4：添加行为规则

```python
import requests

# 添加反馈收集规则
response = requests.post(
    'http://localhost:8888/api/systems/behavior-rules',
    json={
        'name': '用户满意度反馈',
        'trigger_pattern': '(满意|不满意|一般)',
        'trigger_type': 'regex',
        'action_type': 'response',
        'action_content': '感谢您的反馈！',
        'priority': 20,
        'weight': 1.0,
        'cooldown_seconds': 60
    }
)

print(f"规则ID: {response.json()['data']['id']}")
```

### 场景5：访问系统日志

```python
import requests

# 获取最近100条信息日志
response = requests.get(
    'http://localhost:8888/api/systems/logs?level=INFO&limit=100'
)

logs = response.json()['data']
for log in logs:
    print(f"[{log['timestamp']}] {log['level']}: {log['message']}")
```

## 📊 数据存储位置

所有数据都保存在本地：

```
data/
├── tasks/
│   └── tasks.json              # 定时任务配置
├── knowledge_base/
│   ├── entries.json            # 知识库条目
│   ├── glossaries.json         # 词库
│   └── index.json              # 搜索索引
├── instructions/
│   ├── instructions.json       # 系统指令
│   ├── personalities.json      # 人格配置
│   └── behavior_rules.json     # 行为规则
├── mcp/
│   ├── servers.json            # MCP服务器
│   ├── resources.json          # MCP资源  
│   └── tools.json              # MCP工具
└── logs/
    └── enhanced.log            # 详细日志
```

## 🔧 配置说明

### 日志系统配置

日志文件自动保存到 `data/logs/enhanced.log`，支持日志轮转：
- 最多保存5个日志文件
- 单个文件最大10MB

### 任务调度配置

定时任务支持Cron表达式：
```
# 每天9点执行
"0 9 * * *"

# 每周一10点执行
"0 10 * * 1"

# 每小时第5分钟执行
"5 * * * *"
```

## 🐛 故障排查

### 问题1：apscheduler模块未找到

**解决方案：**
```bash
pip install apscheduler==3.10.4
```

### 问题2：数据目录不存在

**解决方案：**
```bash
# 运行初始化脚本会自动创建所有目录
python init_systems.py
```

### 问题3：任务没有执行

**检查步骤：**
1. 确认任务已启用：`GET /api/systems/tasks/{id}`
2. 检查任务状态：查看response中的`status`字段
3. 查看系统日志：`GET /api/systems/logs`

## 📖 详细文档

- [系统详细文档](SYSTEMS_README.md) - 完整的API参考和使用示例
- 各模块源代码注释完整，可直接查看源码了解细节

## 💡 最佳实践

1. **日志记录**：在关键操作处使用get_enhanced_logger()记录日志
2. **任务管理**：为长时间任务设置合理的重试次数
3. **知识库**：使用合理的关键字和标签便于搜索
4. **人格配置**：创建多个人格以应对不同场景
5. **备份数据**：定期备份data目录中的JSON文件

## 🚨 注意事项

- 所有系统都会在启动时自动加载已保存的数据
- 删除操作是永久的，请谨慎操作
- API密钥和敏感信息不应存储在知识库中
- 大量任务可能会影响系统性能

## 联系支持

如有问题或建议，请查看源代码或提交反馈。

---

**现在您已经准备好使用这些强大的系统了！祝您使用愉快！** 🎉
