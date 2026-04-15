# ShizukuClaw

ShizukuClaw 是一个面向 AI Agent 的本地化运行与管理项目，当前已完成前后端分离结构重构。

后端负责 Agent 运行、插件与技能管理、系统接口与控制面板服务；前端目录已预留，便于后续独立构建 UI 应用。

## 项目状态

- 后端可运行，支持模块方式启动。
- 控制面板可通过 Web 访问。
- 前端工程目录已创建，但当前仅为结构骨架。

## 目录结构

```text
ShizukuClaw/
├── backend/                  # Python 后端
│   ├── app/                  # 后端主代码（核心入口：app.main）
│   ├── tests/                # 后端测试
│   ├── requirements.txt      # 后端依赖
│   └── Dockerfile
├── frontend/                 # 前端工程（结构预留）
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── shared/                   # 前后端共享资源（类型/常量/契约）
├── docs/                     # 文档目录
│   ├── api/
│   ├── architecture/
│   └── deployment/
├── scripts/                  # 启动与辅助脚本
├── docker-compose.yml
└── README.md
```

## 环境要求

- Python 3.11+
- Windows / Linux / macOS
- 可选：Docker 与 Docker Compose
- 可选：Node.js 16+（用于 JS 沙箱相关能力）

## 快速开始

### 1) 创建并激活 Python 虚拟环境

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) 安装后端依赖

```bash
pip install -r backend/requirements.txt
```

### 3) 启动后端

在仓库根目录执行：

```bash
cd backend
python -m app.main 5
```

说明：

- 参数 5 表示启动 Web 控制面板模式。
- 默认访问地址通常为 http://127.0.0.1:8888。

### 4) Windows 一键启动（可选）

```powershell
scripts\start.bat
```

## 运行模式

后端入口位于 backend/app/main.py，支持以下模式：

- 0: 启动核心适配器服务（OpenAI API 兼容）
- 1: 终端聊天模式
- 2: 沙箱聊天模式（Web）
- 3: 诊断模式
- 5: Web 控制面板

示例：

```bash
cd backend
python -m app.main 3
```

## 常用脚本

- scripts/start.bat: Windows 快速启动
- scripts/setup-sandbox.bat: Windows 沙箱初始化
- scripts/setup-sandbox.sh: Linux/macOS 沙箱初始化
- scripts/test_modules.py: 模块导入与基础功能自检
- scripts/verify_fixes.py: 关键修复点验证

## Docker（可选）

项目提供 docker-compose.yml，但部分路径仍沿用历史布局，使用前建议先根据当前结构做一次路径校准。

基础命令：

```bash
docker compose up -d
docker compose logs -f
docker compose down
```

## 文档索引

- 架构文档目录：docs/architecture
- 部署文档目录：docs/deployment
- API 文档目录：docs/api

## 开发建议

- 后端开发统一在 backend/app 下进行。
- 新增模块优先使用 app.* 导入路径。
- 需要脚本启动时，优先使用模块方式：python -m app.xxx。

## 许可证

本项目采用 LICENSE 中声明的许可证。
