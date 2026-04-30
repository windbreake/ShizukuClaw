# AstrBot 兼容层 - 功能测试清单

## 📋 测试步骤

### 1. 启动服务
```bash
cd backend
python main.py
```

### 2. 访问控制面板
打开浏览器访问: http://127.0.0.1:8080/static/control_panel.html

### 3. 检查菜单入口

**预期结果**:
- ✅ 在左侧侧边栏看到 **"AstrBot 插件商店"** 菜单项（🏪图标）
- ✅ 菜单位置应该在"扩展与人格"分组附近
- ✅ 点击后应该展开子菜单：
  - 管理已安装插件
  - 兼容层设置

**如果看不到菜单**:
1. 打开浏览器控制台 (F12)
2. 查看是否有 `[PluginUI]` 相关的日志
3. 检查是否有错误信息

### 4. 进入插件商店页面

点击 **"AstrBot 插件商店"** 菜单项

**预期结果**:
- ✅ 右侧内容区显示商店页面
- ✅ 标题: "AstrBot 插件商店"
- ✅ 副标题: "浏览和安装来自 AstrBot 官方生态的插件（数据来自 GitHub）"
- ✅ 搜索框、分类筛选器、刷新按钮
- ✅ 插件列表从 GitHub 加载

**检查网络请求**:
1. 打开浏览器开发者工具 → Network 标签
2. 应该看到对以下URL的请求:
   ```
   https://raw.githubusercontent.com/AstrBotDevs/AstrBot_Plugins_Collection/master/plugins.json
   ```
3. 响应应该是JSON格式的插件列表

### 5. 测试搜索和筛选

**搜索功能**:
- 在搜索框输入 "历史记录" 或 "history"
- 应该过滤出匹配的插件

**分类筛选**:
- 选择"工具"分类
- 应该只显示带有"工具"标签的插件

### 6. 检查插件卡片

每个插件卡片应该显示:
- ✅ 插件名称（display_name）
- ✅ 描述信息
- ✅ 版本号
- ✅ 作者
- ✅ 标签（最多3个）
- ✅ "源码"按钮（链接到GitHub仓库）
- ✅ "安装"按钮

### 7. 测试安装流程

点击任意插件的"安装"按钮:

**预期结果**:
- ✅ 弹出确认对话框
- ✅ 显示克隆命令
- ✅ 点击确认后打开GitHub仓库页面

**手动安装示例**:
```bash
cd backend
git clone https://github.com/Omnitopia/astrbot_plugin_history app/db/data/plungin/astrbot_plugins/astrbot-plugin-history
```

### 8. 管理已安装插件

点击侧边栏 **"管理已安装插件"**:

**预期结果**:
- ✅ 显示所有已加载的AstrBot插件列表
- ✅ 每个插件有"重载"和"卸载"按钮
- ✅ 如果没有插件，显示提示信息

### 9. 兼容层设置

点击侧边栏 **"兼容层设置"**:

**预期结果**:
- ✅ 显示配置表单
- ✅ 包含以下配置项:
  - AstrBot插件目录
  - 自动加载插件（开关）
  - 启用沙箱模式（开关）

### 10. 仪表板小部件

返回首页仪表盘:

**预期结果**:
- ✅ 看到"AstrBot 插件统计"小部件
- ✅ 显示三个统计项:
  - 已加载: X
  - 可用: X
  - 错误: 0

## 🔍 调试技巧

### 检查插件是否加载成功

在浏览器控制台执行:
```javascript
// 获取UI扩展
fetch('/api/plugins/ui-extensions')
  .then(r => r.json())
  .then(data => {
    console.log('Menu items:', data.extensions.menu_items);
    console.log('Pages:', data.extensions.pages);
    console.log('Widgets:', data.extensions.widgets);
  });
```

**预期输出**:
```javascript
Menu items: [
  {id: "astrbot_compatibility.astrbot_store", label: "AstrBot 插件商店", ...},
  {id: "astrbot_compatibility.astrbot_manage", label: "管理已安装插件", ...},
  ...
]
```

### 检查后端日志

在终端中查看后端输出，应该有类似:
```
[AstrBotCompatibility] Plugin loaded successfully
[AstrBotCompatibility] Registered UI extensions
[PluginUI] Loading UI extensions...
[PluginUI] Found 3 menu items to render
[PluginUI] Added menu item: AstrBot 插件商店
```

### 常见问题排查

**问题1: 菜单不显示**
- 检查 `plugin_ui_loader.js` 是否正确加载
- 检查控制台是否有 `[PluginUI]` 日志
- 确认插件已启用

**问题2: 商店页面空白**
- 检查网络连接（需要访问GitHub）
- 检查浏览器控制台的Network标签
- 查看是否有CORS错误

**问题3: 插件加载失败**
- 检查插件目录是否存在: `backend/app/db/data/plungin/astrbot_plugins/`
- 确认插件有 `main.py` 文件
- 查看后端日志中的错误信息

## ✅ 完成标志

全部测试通过后，您应该能够:
1. ✅ 在侧边栏看到"AstrBot 插件商店"入口
2. ✅ 点击进入商店页面
3. ✅ 浏览来自GitHub的官方插件列表
4. ✅ 搜索和筛选插件
5. ✅ 查看插件详情和源码
6. ✅ 获得安装指引
7. ✅ 管理已安装的插件
8. ✅ 配置兼容层参数

---

**测试日期**: ___________  
**测试人员**: ___________  
**测试结果**: ☐ 通过  ☐ 失败  
**备注**: ___________
