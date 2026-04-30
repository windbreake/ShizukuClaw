# 插件页面路由修复

## 🔧 问题

1. **重复导入** - `plugin_ui_loader.js` 被初始化了两次
2. **页面 Not Found** - 插件页面路由没有在后端注册

## ✅ 修复内容

### 1. 添加插件页面路由（web_server.py）

**文件**: `backend/app/services/web_server.py`

**新增路由**:
```python
@app.route('/plugins/<plugin_name>/<path:page_route>', methods=['GET'])
def plugin_page_route(plugin_name, page_route):
    """Serve plugin pages from UI registry."""
    # 从 ui_registry 查找页面并返回 HTML 内容
```

**功能**:
- ✅ 通用插件页面路由
- ✅ 支持所有插件的页面
- ✅ 从 UI 注册表动态查找页面
- ✅ 返回 HTML 内容

**URL 格式**:
```
/plugins/{plugin_name}/{page_route}

示例:
/plugins/astrbot_compatibility/store
/plugins/ui_extension_demo/demo
/plugins/ui_extension_demo/settings
```

### 2. 修复重复导入（control_panel.html）

**问题**:
```html
<!-- 错误：plugin_ui_loader.js 内部已经有自动初始化 -->
<script src="static/js/plugin_ui_loader.js"></script>
<script>
    // 这会导致重复初始化
    document.addEventListener('DOMContentLoaded', async function() {
        await window.pluginUILoader.initialize();
    });
</script>
```

**修复**:
```html
<!-- 正确：只加载脚本，让它自己初始化 -->
<script src="static/js/plugin_ui_loader.js"></script>
```

**原因**:
- `plugin_ui_loader.js` 末尾已经有自动初始化代码
- 不需要在 HTML 中再次初始化

## 📊 工作流程

### 完整的页面加载流程

```
1. 用户访问 /control_panel
   ↓
2. control_panel.html 加载
   ↓
3. 加载 plugin_ui_loader.js
   ↓
4. 脚本自动初始化（DOMContentLoaded）
   ↓
5. 调用 /api/plugins/ui-extensions
   ↓
6. 获取所有插件的菜单项和页面
   ↓
7. 渲染侧边栏菜单
   ↓
8. 用户点击 "AstrBot 插件商店"
   ↓
9. navigateToPluginPage() 创建 tab-pane
   ↓
10. fetch('/plugins/astrbot_compatibility/store')
    ↓
11. 后端 plugin_page_route() 处理
    ↓
12. 从 ui_registry 查找页面
    ↓
13. 返回 HTML 内容
    ↓
14. 前端解析并注入内容
    ↓
15. 执行页面内的 JavaScript
    ↓
16. 插件商店页面加载完成
```

## 🔍 验证方法

### 1. 检查路由注册

重启服务后，访问：
```
http://127.0.0.1:8888/plugins/astrbot_compatibility/store
```

应该看到 AstrBot 插件商店的 HTML 内容。

### 2. 检查控制台

打开浏览器控制台（F12），应该看到：

```
[PluginUI] Loading UI extensions...
[PluginUI] Rendering 3 menu items
[PluginUI] Plugin menu group added successfully
```

**不应该看到**：
```
[PluginUI] Loading UI extensions...
[PluginUI] Loading UI extensions...  ← 重复！
```

### 3. 检查侧边栏

侧边栏应该显示：

```
🧩 插件页面  ▼
    ├─ ⭐ 演示页面
    ├─ 🏪 AstrBot 插件商店
    │   ├─ 管理已安装插件
    │   └─ 兼容层设置
```

## 📝 技术细节

### 路由匹配逻辑

```python
for page in pages:
    # 匹配路由
    if page.route == full_route:
        # 验证插件名（安全保护）
        if page.id.startswith(f"{plugin_name}."):
            return page.content
```

**安全保护**:
- ✅ 只返回属于该插件的页面
- ✅ 防止跨插件访问
- ✅ 命名空间隔离

### 内容类型支持

当前支持：
- ✅ `html` - 直接返回 HTML 内容

未来可扩展：
- `iframe` - 返回 iframe 包装
- `component` - 返回组件名
- `json` - 返回 JSON 数据

## 🎯 总结

### 修复了什么

1. ✅ 添加了通用插件页面路由
2. ✅ 修复了重复初始化问题
3. ✅ 支持所有插件的页面访问

### 设计原则

- ✅ 通用性 - 一个路由处理所有插件
- ✅ 安全性 - 验证插件命名空间
- ✅ 动态性 - 从注册表动态查找
- ✅ 简洁性 - 不需要为每个插件添加路由

### 下一步

现在插件系统应该完全正常工作了：
1. ✅ 插件菜单自动显示在侧边栏
2. ✅ 点击菜单加载插件页面
3. ✅ 页面内容正确显示
4. ✅ 没有重复加载问题

---

**修复版本**: 1.0  
**最后更新**: 2026-04-27  
**修复者**: ShizukuClaw Team
