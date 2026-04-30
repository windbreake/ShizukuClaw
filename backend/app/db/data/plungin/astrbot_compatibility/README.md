# AstrBot 插件兼容层

## 📖 概述

这是一个为 ShizukuClaw 设计的 AstrBot 插件兼容层，允许您在 ShizukuClaw 中加载和运行 AstrBot 生态的插件，无需修改核心代码。

## ✨ 功能特性

### 1. **完整的AstrBot API模拟**
- ✅ `Star` 基类支持
- ✅ `Context` 上下文对象
- ✅ `AstrMessageEvent` 事件系统
- ✅ `@command` 装饰器
- ✅ `AstrBotConfig` 配置管理
- ✅ `AstrBotLogger` 日志系统

### 2. **热插拔功能**
- 🔥 **热加载**: 添加插件后立即生效，无需重启
- 🔥 **热卸载**: 移除插件后完全清理
- 🔥 **热重载**: 更新插件代码后重新加载
- 🔥 **自动发现**: 自动扫描插件目录

### 3. **官方插件商店集成**
- 🛒 直接从 GitHub 获取 AstrBot 官方插件列表
- 🔍 支持搜索和分类筛选
- 📦 一键查看插件源码仓库
- 📋 显示插件详细信息（版本、作者、标签等）

### 4. **UI扩展系统**
- 📱 **自动侧边栏集成**: 插件菜单项自动出现在"插件页面"分组中
- 📊 **仪表板小部件**: 实时显示插件统计信息
- ⚙️ **设置页面**: 配置兼容层参数
- 📄 **管理页面**: 查看和管理已安装插件

### 5. **纯插件原则**
- 🔒 **零侵入**: 不修改任何项目核心文件（框架代码除外）
- 🔒 **用户控制**: 用户决定启用哪些插件
- 🔒 **沙箱隔离**: 所有代码在插件目录内

## 📁 目录结构

```
astrbot_compatibility/
├── plugin.py              # 主插件文件
├── plugin.json            # 插件元数据
├── astrbot/               # AstrBot API模拟模块
│   └── api/
│       ├── __init__.py
│       ├── star.py        # Star基类
│       ├── event.py       # 事件系统
│       └── ...
└── README.md              # 本文档
```

## 🚀 快速开始

### 1. 启用插件

在 ShizukuClaw 控制面板中：
1. 进入"插件管理"
2. 找到"astrbot_compatibility"
3. 点击"启用"

### 2. 访问插件商店

启用后，您会在首页菜单看到 **"AstrBot 插件商店"** 入口（图标：🏪）

点击进入商店页面，您将看到：
- 来自 [AstrBot_Plugins_Collection](https://github.com/AstrBotDevs/AstrBot_Plugins_Collection) 的所有官方插件
- 搜索框：按名称、描述、作者搜索
- 分类筛选：工具、娱乐、管理、游戏等
- 每个插件的详细信息卡片

### 3. 安装插件

由于安全限制，插件需要通过 Git 手动安装：

```bash
# 进入 ShizukuClaw backend 目录
cd backend

# 克隆插件到指定目录
git clone <插件仓库URL> app/db/data/plungin/astrbot_plugins/<插件名>

# 例如：
git clone https://github.com/Omnitopia/astrbot_plugin_history app/db/data/plungin/astrbot_plugins/astrbot-plugin-history
```

安装完成后：
1. 返回控制面板
2. 进入"AstrBot 插件商店" → "管理已安装插件"
3. 点击"刷新"即可看到新插件
4. 点击"重载"按钮加载插件

### 4. 管理插件

在"管理已安装插件"页面，您可以：
- 🔄 **重载插件**: 应用代码更改
- 🗑️ **卸载插件**: 从内存中移除（不删除文件）

## 📝 开发AstrBot插件

如果您想为 AstrBot 开发插件，请参考：
- [AstrBot 官方文档](https://docs.astrbot.app/)
- [插件开发指南](https://github.com/AstrBotDevs/AstrBot/wiki/zh-dev-star-plugin)

基本示例：

```python
from astrbot.api.star import Star, Context
from astrbot.api.event import AstrMessageEvent, command


class MyPlugin(Star):
    """我的第一个AstrBot插件"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
    
    async def initialize(self):
        """插件初始化时调用"""
        print("[MyPlugin] 插件已加载")
    
    @command("hello")
    async def hello_command(self, event: AstrMessageEvent):
        """响应 /hello 命令"""
        await event.plain_result("Hello from AstrBot plugin!")
```

## 🔧 配置选项

在"兼容层设置"页面，您可以配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `astrbot_plugins_dir` | `app/db/data/plungin/astrbot_plugins` | 插件存放目录（相对路径） |
| `auto_load_plugins` | `True` | 启动时自动加载插件 |
| `enable_sandbox` | `True` | 启用沙箱模式 |

## 🎯 技术实现

### 架构设计

```
ShizukuClaw Core
    ↓
Plugin Framework
    ↓
astrbot_compatibility Plugin
    ↓
AstrBotPluginLoader
    ↓
┌─────────────────────┐
│ AstrBot Plugins     │
│ - metadata.yaml     │
│ - main.py           │
│ - _conf_schema.json │
└─────────────────────┘
```

### 关键组件

1. **AstrBotPluginLoader**: 插件加载器
   - 扫描插件目录
   - 解析元数据
   - 动态导入模块
   - 管理生命周期

2. **API模拟层**: 
   - `astrbot.api.star.Star`: 插件基类
   - `astrbot.api.event.AstrMessageEvent`: 消息事件
   - `astrbot.api.platform.Context`: 上下文

3. **UI扩展系统**:
   - 通过 `ui_registry` 注册菜单、页面、小部件
   - 所有资源使用命名空间隔离（`astrbot_compatibility.*`）

### 热插拔机制

```python
# 加载流程
1. 检查插件目录是否存在 main.py
2. 读取 metadata.yaml 或 plugin.json
3. 将 astrbot_compatibility 目录加入 sys.path
4. 使用 importlib 动态导入模块
5. 实例化 Star 子类
6. 调用 initialize() 方法
7. 注册到 loaded_plugins 字典

# 卸载流程
1. 调用 terminate() 方法
2. 从 loaded_plugins 移除
3. 从 sys.modules 清除缓存
4. 清理相关资源
```

## 📊 插件商店数据来源

插件列表来自：
```
https://raw.githubusercontent.com/AstrBotDevs/AstrBot_Plugins_Collection/master/plugins.json
```

该JSON文件包含所有官方收录的插件信息：
- `display_name`: 显示名称
- `desc`: 描述
- `author`: 作者
- `repo`: GitHub仓库地址
- `tags`: 标签分类
- `version`: 版本号（可选）

## 🛡️ 安全性

- ✅ **沙箱隔离**: 插件在独立环境中运行
- ✅ **命名空间隔离**: 防止插件间冲突
- ✅ **权限控制**: 仅管理员可安装/卸载插件
- ✅ **网络限制**: 插件网络访问受策略限制

## ❓ 常见问题

### Q: 为什么不能直接在商店中点击安装？

A: 出于安全考虑，ShizukuClaw 不允许插件直接执行 Git 命令或下载外部代码。需要手动克隆到指定目录。

### Q: 插件加载失败怎么办？

A: 检查以下几点：
1. 插件目录是否有 `main.py`
2. 是否有 `metadata.yaml` 或 `plugin.json`
3. 查看后端日志中的错误信息
4. 确认插件依赖已安装

### Q: 如何更新插件？

A: 进入插件目录执行 `git pull`，然后在控制面板点击"重载"按钮。

### Q: 支持哪些AstrBot插件？

A: 理论上支持所有基于 Star 架构的 AstrBot 插件。但某些依赖特定平台适配器（如 QQ、Telegram）的插件可能无法正常工作。

## 📚 相关资源

- [AstrBot 官方项目](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件集合](https://github.com/AstrBotDevs/AstrBot_Plugins_Collection)
- [AstrBot 文档](https://docs.astrbot.app/)
- [ShizukuClaw 插件框架文档](../../../docs/PLUGIN_UI_EXTENSIONS_GUIDE.md)

## 📄 许可证

本兼容层遵循与 ShizukuClaw 相同的许可证。

---

**开发者**: ShizukuClaw Team  
**版本**: 1.0.0  
**最后更新**: 2026-04-27
