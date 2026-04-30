# 插件配置UI生成系统使用指南

## 📖 概述

ShizukuClaw 提供了强大的插件配置UI生成系统，让插件开发者可以通过简单的JSON配置快速创建美观、功能完整的设置页面，无需编写前端代码。

## ✨ 核心优势

- **零前端开发**：只需编写JSON配置，自动生成完整UI
- **丰富的组件**：支持开关、文本框、下拉选择、滑块等12种字段类型
- **智能验证**：内置表单验证和错误提示
- **条件显示**：支持字段间的依赖关系
- **响应式设计**：自动适配各种屏幕尺寸

## 🚀 快速开始

### 步骤1：创建plugin.json文件

在插件根目录创建 `plugin.json` 文件：

```json
{
  "name": "我的插件",
  "version": "1.0.0",
  "description": "插件描述",
  "author": "作者名",
  
  "config_schema": {
    "title": "插件配置",
    "description": "配置插件参数",
    "version": "1.0.0",
    "sections": [
      // 配置区块定义
    ]
  }
}
```

### 步骤2：定义配置区块

每个插件可以包含多个配置区块（section），每个区块包含多个字段（field）：

```json
"sections": [
  {
    "title": "基础设置",
    "description": "基本功能开关",
    "collapsed": false,
    "fields": [
      // 字段定义
    ]
  }
]
```

### 步骤3：添加配置字段

支持的字段类型：

#### 1. 开关 (switch)
```json
{
  "key": "enabled",
  "type": "switch",
  "label": "启用插件",
  "default": true,
  "description": "开启或关闭插件功能"
}
```

#### 2. 单行文本 (text)
```json
{
  "key": "api_url",
  "type": "text",
  "label": "API地址",
  "default": "https://api.example.com",
  "placeholder": "请输入URL",
  "required": true
}
```

#### 3. 密码框 (password)
```json
{
  "key": "api_key",
  "type": "password",
  "label": "API密钥",
  "placeholder": "请输入API Key",
  "required": true,
  "description": "从服务商获取的密钥"
}
```

#### 4. 数字输入 (number)
```json
{
  "key": "timeout",
  "type": "number",
  "label": "超时时间",
  "default": 30,
  "min": 1,
  "max": 300,
  "step": 1,
  "description": "请求超时时间（秒）"
}
```

#### 5. 多行文本 (textarea)
```json
{
  "key": "custom_prompt",
  "type": "textarea",
  "label": "自定义提示词",
  "default": "你是一个有用的助手",
  "placeholder": "输入提示词...",
  "rows": 5
}
```

#### 6. 下拉选择 (select)
```json
{
  "key": "model",
  "type": "select",
  "label": "模型选择",
  "default": "gpt-4",
  "options": [
    {"value": "gpt-4", "label": "GPT-4"},
    {"value": "gpt-3.5", "label": "GPT-3.5"},
    {"value": "claude", "label": "Claude"}
  ]
}
```

#### 7. 滑块 (slider)
```json
{
  "key": "temperature",
  "type": "slider",
  "label": "温度参数",
  "default": 0.7,
  "min": 0,
  "max": 2,
  "step": 0.1,
  "description": "控制输出的随机性"
}
```

#### 8. 颜色选择器 (color)
```json
{
  "key": "theme_color",
  "type": "color",
  "label": "主题颜色",
  "default": "#4CAF50"
}
```

#### 9. 邮箱 (email)
```json
{
  "key": "admin_email",
  "type": "email",
  "label": "管理员邮箱",
  "placeholder": "admin@example.com"
}
```

#### 10. URL (url)
```json
{
  "key": "webhook_url",
  "type": "url",
  "label": "Webhook地址",
  "placeholder": "https://example.com/webhook"
}
```

#### 11. 日期 (date)
```json
{
  "key": "start_date",
  "type": "date",
  "label": "开始日期"
}
```

#### 12. 时间 (time)
```json
{
  "key": "schedule_time",
  "type": "time",
  "label": "执行时间"
}
```

## 🔧 高级功能

### 字段验证

```json
{
  "key": "username",
  "type": "text",
  "label": "用户名",
  "required": true,
  "pattern": "^[a-zA-Z0-9_]{3,20}$",
  "validation_message": "用户名只能包含字母、数字和下划线，长度3-20"
}
```

### 条件显示

根据其他字段的值动态显示/隐藏字段：

```json
{
  "key": "cache_ttl",
  "type": "number",
  "label": "缓存有效期",
  "default": 300,
  "depends_on": {
    "cache_enabled": true
  }
}
```

只有当 `cache_enabled` 为 `true` 时，此字段才会显示。

### 字段属性说明

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| key | string | ✅ | 配置键名（唯一标识） |
| type | string | ✅ | 字段类型 |
| label | string | ✅ | 显示标签 |
| default | any | ❌ | 默认值 |
| description | string | ❌ | 描述文本 |
| placeholder | string | ❌ | 占位符 |
| required | boolean | ❌ | 是否必填 |
| min | number | ❌ | 最小值（数字/滑块） |
| max | number | ❌ | 最大值（数字/滑块） |
| step | number | ❌ | 步长（数字/滑块） |
| options | array | ❌ | 选项列表（下拉选择） |
| pattern | string | ❌ | 正则表达式验证 |
| validation_message | string | ❌ | 验证失败提示 |
| disabled | boolean | ❌ | 是否禁用 |
| hidden | boolean | ❌ | 是否隐藏 |
| depends_on | object | ❌ | 依赖条件 |

## 📝 完整示例

参考 `backend/app/db/data/plungin/example_plugin_with_config/plugin.json`

## 💻 在插件中读取配置

```python
class MyPlugin:
    def on_load(self, manager):
        plugin_name = self.PLUGIN_META["name"]
        
        # 加载配置
        self.config = manager.get_plugin_runtime_config(plugin_name)
        
        # 如果配置为空，使用默认值
        if not self.config:
            self.config = self._get_default_config()
            manager.update_plugin_runtime_config(plugin_name, self.config)
    
    def _get_default_config(self):
        return {
            "enabled": True,
            "api_key": "",
            "timeout": 30
        }
```

## 🎨 前端集成

控制面板会自动检测并渲染配置schema：

```javascript
// 获取插件配置和schema
fetch(`/api/plugins/config?plugin_name=my_plugin`)
  .then(res => res.json())
  .then(data => {
    if (data.schema) {
      // 渲染配置表单
      const form = renderPluginConfigForm(
        data.schema,
        data.config,
        async (formData) => {
          // 保存配置
          await fetch('/api/plugins/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              plugin_name: 'my_plugin',
              config: formData
            })
          });
        }
      );
      
      document.getElementById('config-container').appendChild(form);
    }
  });
```

## 🔌 API接口

### 获取配置和Schema

```
GET /api/plugins/config?plugin_name=your_plugin
```

响应：
```json
{
  "success": true,
  "plugin_name": "your_plugin",
  "config": {
    "enabled": true,
    "api_key": "sk-xxx"
  },
  "schema": {
    "title": "插件配置",
    "sections": [...]
  }
}
```

### 保存配置

```
POST /api/plugins/config
Content-Type: application/json

{
  "plugin_name": "your_plugin",
  "config": {
    "enabled": true,
    "api_key": "sk-xxx"
  }
}
```

## 💡 最佳实践

1. **提供合理的默认值**：让用户可以直接使用，无需配置
2. **清晰的标签和描述**：帮助用户理解每个配置项的作用
3. **适当的验证**：防止用户输入无效数据
4. **分组合理**：将相关配置放在同一个区块
5. **渐进式披露**：高级配置默认折叠，避免 overwhelm 用户
6. **使用条件显示**：只在需要时显示相关配置

## 🐛 常见问题

### Q: 配置没有生效？
A: 确保配置文件名为 `plugin.json`，且位于插件根目录。

### Q: 如何调试配置schema？
A: 访问 `/api/plugins/config?plugin_name=your_plugin` 查看返回的schema是否正确。

### Q: 支持自定义组件吗？
A: 当前版本支持12种内置组件，未来会扩展更多类型。

## 📚 参考资料

- Python Schema定义：`backend/app/plugin_framework/config_schema.py`
- 前端渲染器：`backend/app/static/js/plugin_config_renderer.js`
- 示例插件：`backend/app/db/data/plungin/example_plugin_with_config/`

---

**Happy Coding!** 🎉
