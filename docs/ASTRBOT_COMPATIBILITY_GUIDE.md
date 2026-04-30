# AstrBot 插件兼容层使用指南

## 📖 概述

ShizukuClaw 现在支持通过**完全隔离的插件**来加载和运行 AstrBot 插件，无需修改任何核心代码。这个兼容层让你可以利用 AstrBot 生态系统中丰富的插件资源。

### ✨ 核心特性

- **完全隔离**：所有代码都在插件目录内，不修改核心系统
- **API 兼容**：模拟 AstrBot 的核心 API（Star、Context、Event等）
- **独立商店页面**：专门的 AstrBot 插件商店管理界面
- **自动加载**：启动时自动发现并加载可用的 AstrBot 插件
- **热重载**：支持运行时重载和卸载插件
- **沙箱安全**：可选的沙箱模式提高安全性

## 🎯 架构设计

```
ShizukuClaw Core (不可修改)
    ↓
Plugin Framework (标准插件系统)
    ↓
astrbot_compatibility (兼容层插件)
    ├── UI Extensions (菜单、页面、设置)
    ├── AstrBot API Simulation
    │   ├── astrbot.api.star (Star基类)
    │   ├── astrbot.api.event (事件系统)
    │   └── astrbot.api.logger (日志系统)
    └── Plugin Loader (插件加载器)
        ↓
    astrbot_plugins/ (AstrBot插件目录)
        ├── astrbot_plugin_helloworld/
        │   ├── main.py
        │   └── metadata.yaml
        └── ...其他AstrBot插件
```

## 🚀 快速开始

### 步骤1：安装依赖

```bash
cd backend
pip install pyyaml
```

### 步骤2：启用插件

在控制面板中：
1. 进入"插件管理"
2. 找到 "astrbot_compatibility"
3. 点击"启用"

### 步骤3：访问商店

启用后，左侧菜单会出现 **"AstrBot 插件商店"**，点击进入即可浏览和管理插件。

## 📁 目录结构

```
backend/app/db/data/plungin/
├── astrbot_compatibility/          # 兼容层插件（核心）
│   ├── plugin.py                   # 主插件文件
│   ├── plugin.json                 # 插件元数据
│   ├── requirements.txt            # Python依赖
│   └── astrbot/                    # AstrBot API模拟
│       ├── __init__.py
│       └── api/
│           ├── __init__.py
│           ├── star.py             # Star基类
│           ├── event.py            # 事件系统
│           ├── filter.py           # 过滤器
│           └── logger.py           # 日志系统
│
└── astrbot_plugins/                # AstrBot插件存放目录
    ├── astrbot_plugin_helloworld/  # 示例插件
    │   ├── main.py
    │   └── metadata.yaml
    └── ...其他插件
```

## 🔧 安装 AstrBot 插件

### 方法1：从商店安装（推荐）

1. 进入"AstrBot 插件商店"页面
2. 浏览或搜索插件
3. 点击"安装"按钮

### 方法2：手动安装

```bash
# 1. 克隆或下载AstrBot插件到指定目录
cd backend/app/db/data/plungin/astrbot_plugins
git clone <plugin-repo-url>

# 2. 确保插件结构正确
# 插件目录必须包含：
# - main.py (必需)
# - metadata.yaml (推荐)

# 3. 在管理页面重载插件
```

### 方法3：从 AstrBot 插件市场

访问 [AstrBot Plugins Collection](https://github.com/AstrBotDevs/AstrBot_Plugins_Collection)

```bash
# 示例：安装天气插件
cd backend/app/db/data/plungin/astrbot_plugins
git clone https://github.com/example/astrbot_plugin_weather.git

# 然后在管理页面点击"重载"
```

## 📝 插件结构要求

### 必需的 files

#### 1. main.py

```python
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    @filter.command("mycommand")
    async def mycommand(self, event: AstrMessageEvent):
        """Command handler"""
        yield event.plain_result("Hello!")
    
    async def terminate(self):
        """Cleanup on unload"""
        pass
```

#### 2. metadata.yaml

```yaml
plugin_name: "astrbot_plugin_myplugin"
display_name: "我的插件"
author: "Your Name"
version: "1.0.0"
description: "插件描述"
repo: "https://github.com/your/repo"
```

### 可选的 files

#### _conf_schema.json (配置Schema)

```json
{
  "api_key": {
    "description": "API密钥",
    "type": "string",
    "hint": "请输入你的API密钥"
  },
  "timeout": {
    "description": "超时时间",
    "type": "int",
    "default": 30
  }
}
```

#### requirements.txt

```
requests>=2.28.0
aiohttp>=3.8.0
```

## 🎮 使用示例

### 示例1：Hello World 插件

已包含在 `astrbot_plugins/astrbot_plugin_helloworld/`

**功能**：
- `/helloworld` - 返回问候消息
- `/astrbot_info` - 显示兼容层信息

**测试**：
```python
# 在聊天中输入
/helloworld

# 输出
Hello, User! This is an AstrBot plugin running in ShizukuClaw!
```

### 示例2：创建自己的插件

```python
# astrbot_plugins/astrbot_plugin_weather/main.py
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
import aiohttp

class WeatherPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        self.api_key = self.config.get('api_key', '')
    
    @filter.command("weather")
    async def weather(self, event: AstrMessageEvent):
        """查询天气
        
        Usage: /weather <city>
        """
        # 获取城市参数
        parts = event.message_str.split()
        if len(parts) < 2:
            yield event.plain_result("用法: /weather <城市>")
            return
        
        city = parts[1]
        
        # 调用天气API
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.weather.com/v1/{city}?key={self.api_key}"
                async with session.get(url) as resp:
                    data = await resp.json()
                    temp = data.get('temperature', 'N/A')
                    yield event.plain_result(f"{city} 当前温度: {temp}°C")
        except Exception as e:
            logger.error(f"Weather query failed: {e}")
            yield event.plain_result("查询失败，请稍后重试")
```

**metadata.yaml**:
```yaml
plugin_name: "astrbot_plugin_weather"
display_name: "天气查询"
author: "Your Name"
version: "1.0.0"
description: "查询各地天气信息"
```

**_conf_schema.json**:
```json
{
  "api_key": {
    "description": "天气API密钥",
    "type": "string",
    "hint": "从 weather.com 获取API密钥"
  }
}
```

## 🔌 API 兼容性

### 支持的 AstrBot API

| API | 状态 | 说明 |
|-----|------|------|
| `astrbot.api.star.Star` | ✅ | 插件基类 |
| `astrbot.api.star.Context` | ✅ | 上下文对象 |
| `astrbot.api.event.filter.command` | ✅ | 命令装饰器 |
| `astrbot.api.event.AstrMessageEvent` | ✅ | 消息事件 |
| `astrbot.api.logger` | ✅ | 日志系统 |
| `event.plain_result()` | ✅ | 文本回复 |
| `event.image_result()` | ✅ | 图片回复 |
| `event.get_sender_name()` | ✅ | 获取发送者 |
| `event.message_str` | ✅ | 消息文本 |

### 暂不支持的 API

- ❌ 平台适配器（QQ、Telegram等）
- ❌ 消息链复杂操作
- ❌ 主动消息推送
- ❌ 多媒体消息（语音、视频）

> 💡 **提示**：大部分功能性插件可以正常运行，仅依赖消息平台的插件需要适配。

## 🛠️ 管理界面

### 1. AstrBot 插件商店

**路径**: 左侧菜单 → AstrBot 插件商店

**功能**：
- 浏览可用插件
- 搜索插件
- 一键安装
- 查看插件详情

### 2. 管理已安装插件

**路径**: AstrBot 插件商店 → 管理已安装插件

**功能**：
- 查看已加载插件列表
- 重载插件（应用代码更改）
- 卸载插件

### 3. 兼容层设置

**路径**: AstrBot 插件商店 → 兼容层设置

**配置项**：
- **AstrBot插件目录**: 存放插件的路径
- **自动加载插件**: 启动时自动加载
- **启用沙箱模式**: 隔离执行环境

## 📊 API 接口

### 获取可用插件

```
GET /api/plugins/astrbot_compatibility/available
```

响应：
```json
{
  "success": true,
  "plugins": [
    {
      "name": "astrbot_plugin_helloworld",
      "path": "...",
      "metadata": {
        "display_name": "Hello World 示例插件",
        "version": "1.0.0"
      }
    }
  ]
}
```

### 获取已加载插件

```
GET /api/plugins/astrbot_compatibility/loaded
```

### 安装插件

```
POST /api/plugins/astrbot_compatibility/install
Content-Type: application/json

{
  "plugin_name": "astrbot_plugin_weather"
}
```

### 卸载插件

```
POST /api/plugins/astrbot_compatibility/unload
Content-Type: application/json

{
  "plugin_name": "astrbot_plugin_weather"
}
```

### 重载插件

```
POST /api/plugins/astrbot_compatibility/reload
Content-Type: application/json

{
  "plugin_name": "astrbot_plugin_weather"
}
```

### 获取统计信息

```
GET /api/plugins/astrbot_compatibility/stats
```

响应：
```json
{
  "success": true,
  "stats": {
    "loaded": 3,
    "available": 5,
    "errors": 0
  }
}
```

## 🔒 安全机制

### 1. 完全隔离

- ✅ 所有代码在插件目录内
- ✅ 不修改核心系统文件
- ✅ 独立的命名空间
- ✅ 可单独卸载

### 2. 沙箱模式（可选）

启用沙箱后：
- 限制文件系统访问
- 限制网络请求
- 限制执行时间
- 捕获异常防止崩溃

### 3. 权限控制

可以为插件设置权限要求：
```python
# 在插件元数据中声明
requires_permission = "admin"
```

## 🐛 故障排查

### 问题1：插件未加载

**症状**：管理页面显示"暂无插件"

**解决**：
```bash
# 1. 检查插件目录是否存在
ls backend/app/db/data/plungin/astrbot_plugins

# 2. 检查插件结构
ls astrbot_plugin_xxx/
# 应该看到 main.py

# 3. 查看日志
# 在控制台查找 "[AstrBotLoader]" 相关错误
```

### 问题2：导入错误

**症状**：`ModuleNotFoundError: No module named 'astrbot'`

**解决**：
```bash
# 确保 astrbot_compatibility 插件已启用
# 检查 astrbot/ 目录是否存在于插件目录下
```

### 问题3：依赖缺失

**症状**：`ModuleNotFoundError: No module named 'xxx'`

**解决**：
```bash
# 在插件目录创建 requirements.txt
echo "package_name>=1.0.0" > requirements.txt

# 安装依赖
pip install -r requirements.txt
```

### 问题4：插件崩溃

**症状**：插件加载后立即卸载

**解决**：
```python
# 在插件中添加错误处理
try:
    # 你的代码
except Exception as e:
    logger.error(f"Error: {e}")
    import traceback
    traceback.print_exc()
```

## 📚 从 AstrBot 迁移插件

### 步骤1：复制插件

```bash
# 从 AstrBot 复制插件
cp -r /path/to/astrbot/data/plugins/astrbot_plugin_xxx \
      backend/app/db/data/plungin/astrbot_plugins/
```

### 步骤2：检查依赖

```bash
# 查看是否有 requirements.txt
cat astrbot_plugin_xxx/requirements.txt

# 安装缺失的依赖
pip install -r requirements.txt
```

### 步骤3：测试运行

1. 在管理页面点击"重载"
2. 查看日志确认加载成功
3. 测试插件功能

### 常见问题

**Q: 所有AstrBot插件都能用吗？**

A: 大部分**功能性插件**可以直接使用，但依赖特定消息平台（如QQ、Telegram）的插件需要适配。

**Q: 需要修改插件代码吗？**

A: 通常不需要。兼容层已经模拟了核心API。只有使用高级特性的插件可能需要微调。

**Q: 性能如何？**

A: 几乎无性能损失。兼容层只是简单的API映射，开销极小。

## 💡 最佳实践

### 1. 插件命名

```
✅ astrbot_plugin_weather
✅ astrbot_plugin_music
❌ my-plugin
❌ WeatherPlugin
```

### 2. 错误处理

```python
@filter.command("mycmd")
async def mycmd(self, event: AstrMessageEvent):
    try:
        # 你的逻辑
        result = do_something()
        yield event.plain_result(result)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        yield event.plain_result(f"执行失败: {str(e)}")
```

### 3. 配置管理

```python
def __init__(self, context: Context, config=None):
    super().__init__(context)
    self.config = config or {}
    self.api_key = self.config.get('api_key', '')

# 使用配置
if not self.api_key:
    yield event.plain_result("请先配置API密钥")
```

### 4. 资源清理

```python
async def terminate(self):
    """插件卸载时清理资源"""
    # 关闭连接
    # 保存状态
    # 清理临时文件
    logger.info("Plugin cleanup complete")
```

## 🎉 总结

通过这个完全隔离的插件，你可以：

- ✅ **零侵入**：不修改任何核心代码
- ✅ **丰富生态**：利用 AstrBot 的海量插件
- ✅ **简单管理**：专用的商店和管理界面
- ✅ **安全可靠**：沙箱隔离和错误处理
- ✅ **易于开发**：熟悉的 AstrBot API

现在你可以在 ShizukuClaw 中享受 AstrBot 生态的强大功能了！🚀

## 📖 相关资源

- **AstrBot 官方**: https://github.com/AstrBotDevs/AstrBot
- **插件集合**: https://github.com/AstrBotDevs/AstrBot_Plugins_Collection
- **插件开发指南**: https://github.com/AstrBotDevs/AstrBot/wiki
- **兼容层插件**: `backend/app/db/data/plungin/astrbot_compatibility/`
- **示例插件**: `backend/app/db/data/plungin/astrbot_plugins/astrbot_plugin_helloworld/`
