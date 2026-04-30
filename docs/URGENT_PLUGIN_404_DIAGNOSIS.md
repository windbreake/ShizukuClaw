# 🔧 插件404问题 - 紧急诊断指南

## ⚠️ 当前状态

✅ **已确认**：
- 页面确实在注册表中（3个页面，路由正确）
- API `/api/plugins/ui-extensions/pages` 返回200和正确的页面列表
- 服务已经重启过（进程ID 23032，启动时间 14:54:40）

❌ **问题**：
- 直接访问 `/plugins/astrbot_compatibility/settings` 返回404
- 路由处理器没有被触发（或者触发了但匹配失败）

## 🔍 刚刚添加的调试

已在 `web_server.py` 第3943-3967行的 `plugin_page_route` 函数中添加了详细的调试日志：

```python
print(f"[DEBUG] Plugin page route called: plugin_name={plugin_name}, page_route={page_route}")
print(f"[DEBUG] Found {len(pages)} pages in registry")
print(f"[DEBUG] Looking for route: {full_route}")
print(f"[DEBUG] Checking page: {page.id} -> {page.route}")
print(f"[DEBUG] MATCH FOUND! Returning page content")
print(f"[DEBUG] No match found, returning 404")
```

## 📋 现在必须做什么

### 步骤1：重启后端服务（再次！）

**非常重要**：由于添加了新的调试代码，必须再次重启服务！

```powershell
# 1. 找到并停止当前服务
Get-Process -Id 23032 | Stop-Process -Force

# 2. 重新启动
cd C:\Users\win11\Desktop\ShizukuClaw-alpha1.0debugging\backend
python app/main.py
# 选择模式 5 (Web控制面板)
```

### 步骤2：访问页面并查看后端日志

访问任意插件页面，例如：
```
http://127.0.0.1:8888/plugins/astrbot_compatibility/settings
```

**立即查看后端控制台输出**，应该看到以下日志之一：

#### 情况A：路由被触发但匹配失败
```
[DEBUG] Plugin page route called: plugin_name=astrbot_compatibility, page_route=settings
[DEBUG] Found 3 pages in registry
[DEBUG] Looking for route: /plugins/astrbot_compatibility/settings
[DEBUG] Checking page: astrbot_compatibility.store_page -> /plugins/astrbot_compatibility/store
[DEBUG] Checking page: astrbot_compatibility.manage_page -> /plugins/astrbot_compatibility/manage
[DEBUG] Checking page: astrbot_compatibility.settings_page -> /plugins/astrbot_compatibility/settings
[DEBUG] MATCH FOUND! Returning page content
```

#### 情况B：路由根本没有被触发
后端控制台**没有任何** `[DEBUG]` 日志输出。

这说明路由根本没有注册到Flask应用中！

### 步骤3：根据日志判断问题

#### 如果是情况A（路由被触发）

说明路由逻辑有问题，请提供完整的控制台日志。

#### 如果是情况B（路由未被触发）

这说明路由定义在函数内部，但没有被正确调用。需要检查`run_web_server()`函数是否完整执行。

## 🔧 可能的根本原因

### 原因1：Flask路由注册顺序问题

所有插件路由都在`run_web_server()`函数内部定义。如果函数在某个地方提前返回或抛出异常，路由就不会被注册。

**检查方法**：查看后端启动日志，确认没有错误。

### 原因2：路由被其他规则覆盖

Flask可能有一个更具体的路由规则优先匹配了`/plugins/`开头的URL。

**检查方法**：访问 `http://127.0.0.1:8888/api/systems/_health` 查看注册的所有路由。

### 原因3：静态文件服务拦截

Flask的静态文件服务可能拦截了`/plugins/`路径。

**解决方法**：确保插件路由在静态文件路由之前定义。

## 📊 验证路由是否注册

重启服务后，访问：
```
http://127.0.0.1:8888/api/systems/_health
```

查看 `sample_routes` 字段，应该包含：
```
/plugins/<plugin_name>/<path:page_route>
```

如果没有这个路由，说明路由定义没有被执行。

---

**请立即重启服务并提供后端控制台的完整日志！**
