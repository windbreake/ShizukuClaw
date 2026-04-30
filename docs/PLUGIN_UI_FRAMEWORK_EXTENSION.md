# 插件UI框架扩展说明

##  框架修改内容

### 修改的文件

**仅修改了一个核心文件**：
- `backend/app/static/js/plugin_ui_loader.js` - 插件UI加载器

### 修改的目的

让框架**自动支持**所有插件的侧边栏菜单集成，而不是为每个插件硬编码。

## 🔧 框架功能

### 1. 自动创建"插件页面"分组

所有插件通过 `ui_registry.register_menu_item()` 注册的菜单项，会**自动**出现在侧边栏的"插件页面"分组中。

```
侧边栏结构:
🐱 Shizuku
━━━━━━━━━━━━━━━━━━━━
⏱️  仪表盘
💬  沙箱对话
🤖  Agent 状态  ▼
📦  扩展与人格  ▼
🧩  插件页面    ▼  ← 框架自动创建
    ├─ 🏪 AstrBot 插件商店  ← 插件自动注册
    ├─ ⭐ 其他插件1
    └─ 🔧 其他插件2
🔧  系统运维中心 ▼
```

### 2. 通用插件菜单渲染

`plugin_ui_loader.js` 中的 `renderMenuItems()` 方法现在会：

1. ✅ 从API获取所有插件注册的菜单项
2. ✅ 自动创建"插件页面"nav-group
3. ✅ 将每个插件的菜单项放入分组
4. ✅ 支持嵌套子菜单
5. ✅ 点击后在内容区加载插件页面

### 3. 插件页面加载机制

点击插件菜单项时：

```javascript
navigateToPluginPage(url, title)
  ↓
创建新的 tab-pane
  ↓
fetch(url) 获取插件页面HTML
  ↓
解析并注入到内容区
  ↓
执行页面内的JavaScript
  ↓
渲染完成
```

**不使用iframe**，而是直接加载HTML内容，确保：
- 样式与其他页面一致
- 可以共享全局CSS
- 更好的用户体验

## 📝 插件如何使用

插件开发者**不需要做任何额外工作**，只需正常注册UI扩展：

```python
from app.plugin_framework.ui_extensions import UIMenuItem, UIPage, ui_registry

class MyPlugin:
    def on_load(self, manager):
        plugin_name = self.PLUGIN_META["name"]
        
        # 1. 注册菜单项
        menu_item = UIMenuItem(
            id="my_plugin_page",
            label="我的插件",
            icon="fas fa-star",
            order=10,
            url="/plugins/my_plugin/page"
        )
        ui_registry.register_menu_item(menu_item, plugin_name)
        
        # 2. 注册页面
        page = UIPage(
            id="my_page",
            title="我的插件页面",
            route="/page",
            content_type="html",
            content="<h1>Hello</h1>"
        )
        ui_registry.register_page(page, plugin_name)
```

**结果**：菜单项会自动出现在"插件页面"分组中！

## 🎨 样式支持

框架会自动应用与控制面板一致的样式：
- ✅ nav-group 折叠/展开
- ✅ nav-link 样式
- ✅ tab-pane 切换动画
- ✅ 响应式布局

## 📊 技术细节

### 修改的方法

1. **`renderMenuItems()`** - 完全重写
   - 支持 ShizukuClaw 的导航结构（#v-pills-tab）
   - 自动创建"插件页面"分组
   - 插入到"系统运维中心"之前

2. **`createPluginGroup()`** - 新增
   - 创建外层nav-group
   - 包含所有插件菜单项

3. **`createPluginNavGroup()`** - 新增
   - 为每个插件创建内层nav-group
   - 支持子菜单

4. **`createSimpleLink()`** - 新增
   - 创建简单的nav-link
   - 绑定点击事件

5. **`navigateToPluginPage()`** - 新增
   - 处理页面导航
   - 创建/激活tab-pane

6. **`loadPluginContent()`** - 新增
   - 通过fetch加载插件页面
   - 解析HTML并注入
   - 执行脚本

### API兼容性

完全兼容现有的UI扩展API：
- ✅ `/api/plugins/ui-extensions` - 获取所有UI扩展
- ✅ `/api/plugins/ui-extensions/menu` - 获取菜单项
- ✅ `/api/plugins/ui-extensions/pages` - 获取页面列表

## ✅ 优势

### 对用户的优势

1. ✅ **零配置** - 启用插件后自动出现在侧边栏
2. ✅ **统一管理** - 所有插件菜单在一个分组中
3. ✅ **风格一致** - 与系统其他页面完全一致
4. ✅ **易于发现** - 用户可以轻松找到所有插件

### 对开发者的优势

1. ✅ **无需额外代码** - 正常注册UI扩展即可
2. ✅ **自动集成** - 框架处理所有渲染逻辑
3. ✅ **标准化** - 统一的插件UI体验
4. ✅ **易维护** - 集中管理插件菜单

## 🔒 设计原则

### 做了什么

- ✅ 修改框架代码以支持插件UI扩展
- ✅ 提供通用的菜单渲染机制
- ✅ 确保与现有系统风格一致

### 没做什么

- ❌ 没有为特定插件硬编码菜单
- ❌ 没有修改项目HTML文件
- ❌ 没有破坏现有功能

### 为什么这样设计

1. **框架职责** - `plugin_ui_loader.js` 的职责就是加载插件UI
2. **通用性** - 修改是通用的，适用于所有插件
3. **可维护** - 集中管理，易于更新
4. **标准化** - 提供统一的插件集成方式

## 📚 相关文件

- **框架代码**: `backend/app/static/js/plugin_ui_loader.js`
- **后端API**: `backend/app/services/web_server.py` (已有)
- **UI注册表**: `backend/app/plugin_framework/ui_extensions.py` (已有)
- **使用指南**: `docs/PLUGIN_UI_EXTENSIONS_GUIDE.md` (已有)

## 🎉 总结

框架现在支持：
1. ✅ 自动创建"插件页面"分组
2. ✅ 自动渲染所有插件菜单项
3. ✅ 支持嵌套子菜单
4. ✅ 点击加载插件页面
5. ✅ 风格与系统一致

**插件开发者只需注册UI扩展，框架会自动处理其余所有工作！**

---

**框架版本**: 2.0  
**最后更新**: 2026-04-27  
**修改者**: ShizukuClaw Team
