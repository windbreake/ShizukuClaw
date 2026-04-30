# AstrBot Plugins Directory

This directory contains **AstrBot plugins** that are loaded by the `astrbot_compatibility` plugin.

## 📁 Structure

```
astrbot_plugins/
├── astrbot_plugin_helloworld/    # Example plugin
│   ├── main.py                   # Plugin entry point (required)
│   └── metadata.yaml             # Plugin metadata (recommended)
└── ...other plugins
```

## 🔧 How to Add Plugins

### Method 1: Clone from Git
```bash
cd astrbot_plugins
git clone https://github.com/example/astrbot_plugin_xxx.git
```

### Method 2: Manual Copy
Copy your AstrBot plugin folder here, ensuring it has:
- `main.py` (required)
- `metadata.yaml` (recommended)

## 📝 Plugin Requirements

Each AstrBot plugin must have:

1. **main.py** - Plugin code
```python
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    @filter.command("mycmd")
    async def mycmd(self, event: AstrMessageEvent):
        yield event.plain_result("Hello!")
```

2. **metadata.yaml** - Plugin info
```yaml
plugin_name: "astrbot_plugin_myplugin"
display_name: "My Plugin"
author: "Your Name"
version: "1.0.0"
description: "Plugin description"
```

## 🚀 Management

After adding plugins:
1. Go to Control Panel → Plugins → AstrBot Plugin Store
2. Click "Manage Installed Plugins"
3. Click "Reload" to load new plugins

## ⚠️ Important

- This directory is for **AstrBot plugins only**
- Do NOT place ShizukuClaw plugins here
- ShizukuClaw plugins go in the parent `plungin/` directory
- All AstrBot plugins run in isolated environment

## 📚 Documentation

See `docs/ASTRBOT_COMPATIBILITY_GUIDE.md` for complete usage guide.
