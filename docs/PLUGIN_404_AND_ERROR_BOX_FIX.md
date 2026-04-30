# 修复404错误和错误框显示问题

## 问题描述

1. 访问 `/plugins/astrbot_compatibility/settings` 等URL时返回 404 错误
2. 在非插件页面也显示了红色的"加载失败"错误框

## 修复内容

### 1. 添加后端路由（web_server.py）

**文件**: `backend/app/services/web_server.py`

**位置**: 第4316行后

**添加的路由**:
- `/plugins/astrbot_compatibility/store` - AstrBot插件商店页面
- `/plugins/astrbot_compatibility/manage` - 插件管理页面  
- `/plugins/astrbot_compatibility/settings` - 兼容层设置页面

这些路由会从已加载的 `astrbot_compatibility` 插件实例中获取对应的HTML内容并返回。

### 2. 修改前端错误处理（plugin_ui_loader.js）

**文件**: `backend/app/static/js/plugin_ui_loader.js`

**位置**: 第314-327行

**修改内容**:
- 添加了页面类型检测：`const isPluginPage = url.startsWith('/plugins/')`
- 插件页面（URL以 `/plugins/` 开头）：显示完整的红色错误框，包含详细错误信息
- 非插件页面：只显示简单的黄色警告提示，不显示详细的"请检查后端服务是否重启"等信息

## 修改后的效果

### 插件页面（/plugins/astrbot_compatibility/*）
- ✅ 路由正常，返回200状态码
- ✅ 显示插件内容
- 如果出错，显示红色详细错误框

### 非插件页面
- ✅ 不再显示红色的"加载失败"大错误框
- ✅ 如果加载失败，只显示简单的黄色警告提示
- ✅ 界面更简洁友好

## 测试方法

1. **重启后端服务**（必须！）
   ```powershell
   cd backend
   python app/main.py
   # 选择模式5
   ```

2. **访问插件页面**
   ```
   http://127.0.0.1:8888/plugins/astrbot_compatibility/settings
   ```
   应该正常显示设置页面，不再404

3. **访问其他页面**
   即使其他页面加载失败，也不会显示红色的大错误框

## 技术细节

### 后端路由实现
```python
@app.route('/plugins/astrbot_compatibility/settings')
def astrbot_plugin_settings():
    """AstrBot plugin settings page."""
    try:
        # 从已加载的插件实例获取HTML内容
        if 'astrbot_compatibility' in chat_system.plugin_manager._loaded_plugins:
            plugin_instance = ... # 获取插件实例
            if plugin_instance and hasattr(plugin_instance, '_get_settings_page_html'):
                return plugin_instance._get_settings_page_html()
        return '<div class="alert alert-danger">设置页面加载失败</div>', 500
    except Exception as e:
        return f'<div class="alert alert-danger">错误: {str(e)}</div>', 500
```

### 前端错误处理逻辑
```javascript
if (!response.ok) {
    const isPluginPage = url.startsWith('/plugins/');
    if (isPluginPage) {
        // 插件页面：显示详细错误信息
        container.innerHTML = `...红色错误框...`;
    } else {
        // 非插件页面：显示简单提示
        container.innerHTML = `...黄色警告...`;
    }
}
```

## 文件清单

修改的文件：
1. `backend/app/services/web_server.py` - 添加3个路由
2. `backend/app/static/js/plugin_ui_loader.js` - 优化错误显示逻辑

## 注意事项

⚠️ **重要**: 修改Python代码后必须重启后端服务才能生效！
