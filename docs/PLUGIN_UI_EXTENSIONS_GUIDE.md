# 插件UI扩展系统使用指南

## 📖 概述

ShizukuClaw 提供了强大的**插件UI扩展系统**，让插件可以安全地添加菜单、页面、设置项、小部件等UI元素，而不会影响核心系统的稳定性。

### ✨ 核心特性

- **沙箱化执行**：插件UI扩展在隔离环境中运行
- **命名空间隔离**：自动为插件资源添加前缀，防止冲突
- **钩子系统**：支持在关键生命周期点插入自定义逻辑
- **动态加载**：UI扩展在运行时动态注册和渲染
- **安全卸载**：插件卸载时自动清理所有UI元素
- **零侵入**：不修改任何核心代码

## 🎯 支持的UI扩展类型

| 类型 | 说明 | 用途 |
|------|------|------|
| 📋 **Menu Items** | 菜单项 | 在导航栏添加链接 |
| 📄 **Pages** | 页面 | 创建完整的独立页面 |
| ⚙️ **Setting Sections** | 设置区块 | 在系统设置中添加配置项 |
| 📊 **Widgets** | 小部件 | 在仪表板显示统计信息 |
| 💬 **Modals** | 模态框 | 弹出对话框 |
| 🔗 **Hooks** | 钩子 | 在特定事件执行回调 |

## 🚀 快速开始

### 步骤1：导入UI扩展类

```python
from app.plugin_framework.ui_extensions import (
    UIMenuItem, UIPage, UISettingSection, 
    UIWidget, UIModal, ui_registry
)
```

### 步骤2：在插件中注册UI扩展

```python
class MyPlugin:
    def on_load(self, manager):
        plugin_name = self.PLUGIN_META["name"]
        
        # 注册菜单项
        menu_item = UIMenuItem(
            id="my_page",
            label="我的页面",
            icon="fas fa-star",
            url="/plugins/my_plugin/page"
        )
        ui_registry.register_menu_item(menu_item, plugin_name)
        
        # 注册页面
        page = UIPage(
            id="my_page",
            title="我的页面",
            route="/page",
            content="<h1>Hello World</h1>"
        )
        ui_registry.register_page(page, plugin_name)
```

### 步骤3：完成！

前端会自动加载并渲染这些UI元素。

## 📝 详细用法

### 1. 注册菜单项

```python
from app.plugin_framework.ui_extensions import UIMenuItem, ui_registry

# 主菜单项
menu_item = UIMenuItem(
    id="dashboard",           # 唯一ID（会自动添加插件名前缀）
    label="仪表板",            # 显示文本
    icon="fas fa-chart-line", # FontAwesome图标
    order=10,                 # 排序（越小越靠前）
    url="/plugins/my_plugin/dashboard",  # 链接地址
    parent_id=None,           # 父菜单ID（用于子菜单）
    requires_permission=None  # 所需权限
)

ui_registry.register_menu_item(menu_item, "my_plugin")

# 子菜单项
submenu = UIMenuItem(
    id="settings",
    label="设置",
    icon="fas fa-cog",
    order=11,
    url="/plugins/my_plugin/settings",
    parent_id="dashboard"  # 指向父菜单
)

ui_registry.register_menu_item(submenu, "my_plugin")
```

### 2. 注册页面

```python
from app.plugin_framework.ui_extensions import UIPage, ui_registry

# HTML内容页面
page = UIPage(
    id="demo_page",
    title="演示页面",
    route="/demo",  # 最终路由: /plugins/my_plugin/demo
    content_type="html",
    content="""
        <div class="container">
            <h1>欢迎</h1>
            <p>这是插件页面</p>
        </div>
    """,
    requires_auth=True,  # 需要登录
    permissions=[]       # 所需权限列表
)

ui_registry.register_page(page, "my_plugin")

# 使用模板文件
template_page = UIPage(
    id="template_page",
    title="模板页面",
    route="/template",
    content_type="html",
    template_file="templates/my_page.html"  # 相对于插件目录
)

ui_registry.register_page(template_page, "my_plugin")
```

### 3. 注册设置区块

```python
from app.plugin_framework.ui_extensions import UISettingSection, ui_registry

section = UISettingSection(
    id="api_settings",
    title="API设置",
    description="配置API相关参数",
    order=100,  # 在设置页面中的显示顺序
    fields=[
        {
            "key": "api_key",
            "type": "password",
            "label": "API密钥",
            "required": True
        },
        {
            "key": "timeout",
            "type": "number",
            "label": "超时时间",
            "default": 30,
            "min": 1,
            "max": 300
        }
    ]
)

ui_registry.register_setting_section(section, "my_plugin")
```

设置区块会自动出现在系统设置页面中，并使用之前介绍的**配置UI生成系统**渲染表单。

### 4. 注册小部件

```python
from app.plugin_framework.ui_extensions import UIWidget, ui_registry

# 统计小部件
stats_widget = UIWidget(
    id="user_stats",
    title="用户统计",
    widget_type="stats",  # stats, chart, table, card
    position="dashboard", # dashboard, sidebar, header
    order=10,
    config={
        "items": [
            {"label": "总用户", "value": "1234", "icon": "fas fa-users"},
            {"label": "在线", "value": "56", "icon": "fas fa-circle text-success"}
        ]
    },
    data_source="/api/plugins/my_plugin/stats",  # 数据API
    refresh_interval=60  # 自动刷新间隔（秒）
)

ui_registry.register_widget(stats_widget, "my_plugin")
```

### 5. 注册模态框

```python
from app.plugin_framework.ui_extensions import UIModal, ui_registry

modal = UIModal(
    id="confirm_dialog",
    title="确认操作",
    size="md",  # sm, md, lg, xl
    content_type="html",
    content="""
        <div class="modal-body">
            <p>确定要执行此操作吗？</p>
        </div>
    """,
    buttons=[
        {"label": "取消", "class": "btn-secondary", "action": "close"},
        {"label": "确认", "class": "btn-danger", "action": "handleConfirm"}
    ]
)

ui_registry.register_modal(modal, "my_plugin")
```

### 6. 注册钩子

```python
from app.plugin_framework.ui_extensions import ui_registry

def my_hook_callback(page_id, context):
    """页面渲染前的回调"""
    print(f"Rendering page: {page_id}")
    # 可以修改context或执行其他操作
    return context

ui_registry.register_hook(
    "before_page_render",  # 钩子名称
    my_hook_callback,       # 回调函数
    "my_plugin"             # 插件名
)
```

#### 可用的钩子

| 钩子名称 | 触发时机 | 参数 |
|---------|---------|------|
| `before_page_render` | 页面渲染前 | page_id, context |
| `after_page_render` | 页面渲染后 | page_id, html |
| `before_menu_render` | 菜单渲染前 | menu_items |
| `on_user_login` | 用户登录时 | user_info |
| `on_plugin_load` | 插件加载时 | plugin_name |
| `on_plugin_unload` | 插件卸载时 | plugin_name |

## 🔌 API接口

### 获取所有UI扩展

```
GET /api/plugins/ui-extensions
```

响应：
```json
{
  "success": true,
  "extensions": {
    "menu_items": [...],
    "pages": [...],
    "setting_sections": [...],
    "widgets": [...],
    "modals": [...],
    "available_hooks": [...]
  }
}
```

### 获取菜单项

```
GET /api/plugins/ui-extensions/menu
```

### 获取页面列表

```
GET /api/plugins/ui-extensions/pages
```

### 获取设置区块

```
GET /api/plugins/ui-extensions/settings
```

### 获取小部件

```
GET /api/plugins/ui-extensions/widgets?position=dashboard
```

## 🛡️ 安全机制

### 1. 命名空间隔离

所有插件注册的UI元素ID都会自动添加插件名前缀：

```python
# 你注册的ID
UIMenuItem(id="my_page", ...)

# 实际存储的ID
"my_plugin.my_page"
```

这确保了不同插件之间不会产生命名冲突。

### 2. 沙箱化执行

插件代码在受限环境中运行：
- 无法访问核心系统对象
- 网络请求受策略限制
- 文件系统访问受控
- 执行时间有限制

### 3. 自动清理

插件卸载时，所有UI元素自动移除：

```python
def on_unload(self, manager):
    plugin_name = self.PLUGIN_META["name"]
    ui_registry.unregister_plugin(plugin_name)
    # 所有菜单、页面、设置等都会被清理
```

### 4. 权限控制

可以为UI元素设置权限要求：

```python
menu_item = UIMenuItem(
    id="admin_page",
    label="管理页面",
    requires_permission="admin"  # 只有管理员可见
)
```

## 📊 完整示例

参考 `backend/app/db/data/plungin/ui_extension_demo/plugin.py`

这个示例插件展示了：
- ✅ 注册主菜单和子菜单
- ✅ 创建HTML页面
- ✅ 添加设置区块
- ✅ 显示统计小部件
- ✅ 注册模态框
- ✅ 使用钩子

## 💡 最佳实践

### 1. 使用有意义的ID

```python
# ✅ 好
UIMenuItem(id="user_management", ...)

# ❌ 不好
UIMenuItem(id="page1", ...)
```

### 2. 提供合理的排序

```python
# 核心功能用较小的数字
UIMenuItem(id="dashboard", order=10, ...)
UIMenuItem(id="settings", order=20, ...)

# 辅助功能用较大的数字
UIMenuItem(id="help", order=100, ...)
```

### 3. 错误处理

```python
try:
    ui_registry.register_menu_item(item, plugin_name)
except Exception as e:
    logger.error(f"Failed to register menu: {e}")
```

### 4. 清理资源

```python
def on_unload(self, manager):
    # 清理定时器、事件监听器等
    ui_registry.unregister_plugin(self.PLUGIN_META["name"])
```

### 5. 渐进增强

```python
# 检查前端是否支持某个功能
if hasattr(ui_registry, 'register_widget'):
    # 注册小部件
else:
    # 降级方案
    pass
```

## 🎨 前端集成

前端会自动加载插件UI扩展，无需额外配置。

如果需要手动控制：

```javascript
// 初始化UI加载器
await window.pluginUILoader.initialize();

// 重新加载（插件安装/卸载后）
await window.pluginUILoader.loadExtensions();
await window.pluginUILoader.renderMenuItems();
```

## 🔧 自定义钩子

插件可以定义自己的钩子供其他插件使用：

```python
# 插件A：定义钩子
def process_data(self, data):
    results = ui_registry.execute_hook("custom_data_filter", data)
    # 处理结果
    return processed_data

# 插件B：注册到钩子
def my_filter(data):
    # 过滤数据
    return filtered_data

ui_registry.register_hook("custom_data_filter", my_filter, "plugin_b")
```

## 🐛 调试技巧

### 查看已注册的UI元素

```python
from app.plugin_framework.ui_extensions import ui_registry

# 查看所有菜单项
print(ui_registry.get_menu_items())

# 查看所有页面
print(ui_registry.get_pages())

# 导出完整状态
print(ui_registry.to_dict())
```

### 前端调试

打开浏览器控制台，查看日志：

```
[PluginUI] Loading UI extensions...
[PluginUI] Registered page route: /plugins/my_plugin/demo
[PluginUI] UI extensions loaded successfully
```

## 📚 相关文件

- **后端框架**: `backend/app/plugin_framework/ui_extensions.py`
- **前端加载器**: `backend/app/static/js/plugin_ui_loader.js`
- **示例插件**: `backend/app/db/data/plungin/ui_extension_demo/plugin.py`
- **配置Schema**: `docs/PLUGIN_CONFIG_SCHEMA_GUIDE.md`

## ⚠️ 注意事项

1. **不要直接修改核心UI**：始终使用提供的API
2. **避免频繁更新**：小部件刷新间隔不要太短
3. **处理异步操作**：确保异步操作有适当的错误处理
4. **测试兼容性**：在不同浏览器和屏幕尺寸下测试
5. **遵循命名规范**：使用清晰的ID和变量名

## 🎉 总结

插件UI扩展系统让你可以：
- ✅ 安全地添加菜单、页面、设置等UI元素
- ✅ 不影响核心系统稳定性
- ✅ 自动处理命名冲突
- ✅ 支持动态加载和卸载
- ✅ 提供丰富的扩展点

现在你可以创建功能丰富、界面美观的插件了！🚀
