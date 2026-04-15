# ShizukuNyaBot 快速开始

本指南聚焦当前稳定可用链路：

- 数据目录统一在 `data/`
- 上下文构建走 DB 优先缓存（未命中再检索）
- 记忆系统（短/中/长期）与 DB 缓存可共存
- 数据库运行时支持 MySQL / PostgreSQL / SQLite

## 1. 安装与启动

```bash
cd Shizuku_Nya_Bot-master
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

可选：双击 `start.bat`。

控制面板默认地址：

- `http://localhost:8888/control_panel`

## 2. 最小配置

编辑 `data/config.json`。

### 2.1 数据库引擎

```json
{
    "database": {
        "engine": "mysql",
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": "***",
        "database": "shizuku_nya_bot",
        "sqlite_path": "data/chat_history.db"
    }
}
```

说明：

- `engine=mysql`：默认路径
- `engine=postgresql`：需安装可用 psycopg2
- `engine=sqlite`：使用 `sqlite_path`

### 2.2 仓库上下文检索（省 Token）

```json
{
    "repo_context_retrieval": {
        "enabled": true,
        "mode": "coarse2fine",
        "gamma": 0.25,
        "max_chars": 1800,
        "min_remaining_tokens": 280,
        "history_recall_limit": 3,
        "history_recall_max_chars": 900
    }
}
```

## 3. 当前存储与注入逻辑

上下文构建顺序：

1. 读取最近聊天记录
2. 构建动态系统提示词
3. 优先从 `repo_context_cache` 取仓库上下文缓存
4. 未命中则执行代码图检索并回写缓存
5. 对重复片段做增量注入（同会话去重）
6. 合并历史回忆并按预算截断

记忆系统共存：

- Agent 记忆：`agent_datas/workspace/memory/`
    - `short_term.json` / `short_term.md`
    - `mid_term.md`
    - `long_term.md`
    - `context_compression.md`
- DB 缓存：`repo_context_cache`（或 Provider 接管）

## 4. 插件扩展数据库能力

代码扩展点（无需改业务调用层）：

- 连接工厂注册：
    - `DatabaseManager.register_connection_factory(engine, factory)`
- 缓存 Provider 注册（适合 Redis）：
    - `DatabaseManager.register_cache_provider(engine, provider)`
- 生命周期钩子：
    - `on_connect`
    - `before_execute`
    - `after_execute`
    - `on_error`

### Provider 需要实现的最小方法

- `get_repo_context_cache(query_text, persona_filename=None)`
- `save_repo_context_cache(query_text, payload, persona_filename=None)`

可选：

- `touch_repo_context_cache_hit(cache_id)`
- `prune_repo_context_cache(max_rows=2000)`

## 5. 常用检查

### 5.1 运行测试

```bash
python -m pytest -q
```

### 5.2 快速验证仓库上下文缓存链路

```bash
python -c "from src.agent.ai_chat_system import AIChatSystem; s=AIChatSystem(); _=s.build_chat_context('cache check', max_tokens=6000, persona_filename='shizuku.json'); print(s.get_repo_retrieval_stats())"
```

## 6. 故障排查

- 启动失败：先检查 `data/config.json` 中数据库配置是否可连接。
- PostgreSQL 失败：确认 `psycopg2` 已安装且账号权限正确。
- 缓存不生效：检查 `repo_context_retrieval.enabled` 是否为 `true`。
- token 偏高：降低 `max_chars`、`history_recall_max_chars`，或提高 `min_remaining_tokens`。

## 7. 注意事项

- 敏感配置不要提交到公开仓库。
- 所有运行时数据应保持在 `data/`，不要写回 `src/`。
- 生产环境建议启用数据库备份与日志轮转。
