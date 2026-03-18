# ShizukuNyaBot

 一个基于大语言APIKeys的AI聊天系统，支持以下多种运行模式：
- Koishi/AstrBot/NoneBot 映射模式（FastAPI，OpenAI Chat Completion 兼容）
- 终端聊天模式（命令行交互）
- 沙箱聊天模式（Flask + Web 前端）
- 统一API服务模式（提供统一接口支持多种AI功能）
- web前端控制面板（最近新增）

![项目吉祥物雪风酱](./pictures/yukikaze.jpg)

---

##目录结构

- `main.py`：入口脚本，根据参数选择模式  
- `koishi_service.py`：FastAPI 实现的 OpenAI-completion 兼容接口  
- `web_server.py`：终端模式 & Web 沙箱模式（Flask）  
- `ai_chat_system.py`：AIChatSystem 核心逻辑，封装 DeepSeek 调用及消息管理  
- `database.py`：MySQL 数据库操作（角色和聊天记录）  
- `config.py`：配置文件（API Key、Base URL、数据库连接）  
- `chat-sandbox.html`：沙箱模式的前端页面  
- `unified_api.py`：统一API服务，提供整合的AI功能接口  
- `start.bat`：Windows 启动脚本，安装依赖并选择运行模式  
- `control_panel.html`：Web控制面板前端页面  
- `db_management.html`：数据库管理前端页面  
- `logs.html`：日志查看前端页面  
- `control_panel.js`：控制面板JavaScript逻辑  
- `create_database.py`：数据库和表初始化脚本  
- `init_database.sql`：数据库初始化SQL脚本  

---

## 环境准备

1. Python ≥3.8  
2. MySQL 数据库（schema 包含 `character_info`、`chat_history` 表）  
3. 克隆或下载本项目到本地

---

## 快速开始

1. 激活虚拟环境：  
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: .\venv\Scripts\activate
   ```
2. 安装依赖：  
   ```bash
   pip install fastapi uvicorn flask openai mysql-connector-python pillow colorama requests python-dotenv
   ```
3. 修改 `data/config.json` 中的API密钥、基础URL及数据库连接信息。  
4. 创建数据库和表：
   ```bash
   python src/create_database.py
   ```
5. 直接运行 Windows 启动器：  
   ```
   start.bat
   ```
   或者手动调用：
   ```bash
   # Koishi 模式 (OpenAI API 兼容)
   python main.py 0

   # 终端聊天模式
   python main.py 1

   # 沙箱聊天模式（打开 http://localhost:8888）
   python main.py 2

   # 统一API服务模式
   python src/unified_api.py
   ```
注：目前对于Linux端的bash启动正在开发中，暂时请自行修改启动脚本。
---

## 已修复和改进的功能（2025年10月29号更新内容）

### 控制面板功能完善
- 控制面板现已完全可用，提供完整的系统监控和管理功能
- 新增系统资源监控（CPU、内存、磁盘使用情况）
- 添加了Token使用统计功能
- 实现了数据库记录的增删查改管理
- 集成了日志查看和实时终端功能
- 支持通过Web界面执行系统命令

### 启动脚本优化
- 提供了专门的控制面板启动脚本 [start_control_panel.bat](start_control_panel.bat)
- 优化了各模式的启动流程和用户体验

---

## 各模式说明

### 1. Koishi 映射模式  
- 启动 FastAPI 服务，监听 `/v1/chat/completions`、`/v1/models`、`/health`  
- 支持 OpenAI Chat Completion 标准参数（model、messages、stream 等）  
- 流式返回（SSE）兼容 ChatLuna，当 `stream=true` 时会以 `text/event-stream` 分块推送
- 支持多种模型：deepseek-chat、neko等

### 2. 终端聊天模式  
- 纯命令行交互，输入内容后显示bot回复并展示响应耗时  
- 运行：`python main.py 1`

### 3. 沙箱聊天模式  
- 在Web上进行聊天测试并在后台终端输出日志，以方便调试
- Flask+HTML 前端，提供简单的 Web 页面用于测试（支持文本与图片上传）  
- 访问 `http://localhost:8888` 并在页面中聊天  
- 支持图片识别功能，可上传图片进行分析  
- 运行：`python main.py 2`

### 4. 统一API服务模式
- 提供统一的API接口，整合多种AI功能
- 支持图片识别和网络搜索功能
- 可作为代理服务使用，支持API密钥验证
- 运行：`python src/unified_api.py`

---

## 数据库说明

- character_info：存储角色名称、性格、口癖等信息  
- chat_history：保存用户输入与 AI 回复，包括图片描述信息  

> 如果数据库不存在表，系统会使用默认角色配置，并在保存失败时输出警告。

数据库初始化脚本位于 `data/init_database.sql`，可通过运行 `src/create_database.py` 自动创建数据库和表。

---

## 高级功能

### 图片识别
- 系统支持图片识别功能，可分析用户上传的图片内容
- 作者测试及日常使用的模型为阿里云通义VL MAX API进行图片分析

### 网络搜索
- 系统可根据用户问题自动触发网络搜索
- 使用AI Search API获取搜索结果并整合到回复中
- 作者现使用Kimi API来实现Bot搜索功能

### Web控制面板(2025年10月30日正式修复完成)
- 提供Web界面的控制面板，可管理服务和查看日志
- 访问 `http://localhost:8888/control_panel`
- 支持系统监控、数据库记录管理、日志查看等功能
- 实时显示CPU、内存使用率和Token统计信息
- 可直接在面板中执行系统命令和查看执行结果
- 可以直接在控制面板中编辑API信息和BOT设定等

## 配置说明

所有配置信息存储在 `data/config.json` 文件中：
- `api_keys`：包含DeepSeek API、搜索API和图片识别API的密钥及基础URL
- `character`：角色设定，包括姓名、性格、主人QQ号和口癖

## License

此项目仅供学习，禁止任何商用行为
如有问题，请联系项目维护人NekoSunami。

联系邮箱：<EMAIL>windbreaak339@gmail.com
