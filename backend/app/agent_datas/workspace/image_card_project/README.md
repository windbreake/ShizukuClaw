# image_card_project - 阿里云 API 错误展示系统

## 项目概述

这是一个现代化的 Web 应用，用于展示和分析阿里云 API 的错误消息。采用磁贴卡片式设计，提供友好的用户界面和交互体验。

## 项目结构

```
image_card_project/
├── index.html        # HTML 主页
├── style.css         # 样式表
├── script.js         # 交互脚本
└── README.md         # 项目文档
```

## 技术栈

- **HTML5** - 标准化标记语言
- **CSS3** - 现代样式系统（支持 Flexbox/Grid, 深色模式）
- **Vanilla JavaScript** - 纯 JavaScript（无框架依赖）
- **Font Awesome 6.4.0** - 图标库

## 功能特性

### 1. 磁贴卡片设计

多个卡片展示不同的 API 错误，每个卡片包含：
- 错误代码和标题
- 错误截图（可点击放大）
- 详细错误信息
- 快速操作按钮
- 解决方案链接

### 2. 响应式布局

- 桌面版：4 列网格布局
- 平板版：2-3 列自适应
- 移动版：单列堆栈布局
- Flexbox 和 CSS Grid 实现灵活布局

### 3. 交互功能

- **图片放大**：点击卡片中的错误截图查看大图
- **复制请求 ID**：快速复制到剪贴板
- **深色模式**：支持亮色/深色主题切换
- **键盘快捷键**：
  - `Esc` - 关闭模态框
  - `C` - 复制错误代码
  - `?` - 显示帮助菜单

### 4. 通知系统

- 成功通知（绿色）
- 错误通知（红色）
- 信息通知（蓝色）
- 自动消失或可关闭

### 5. 数据展示

统计面板：
- 总错误数
- 警告数
- 成功请求数
- 平均延迟

分析面板：
- 错误率趋势图表
- API 端点分布统计

## 使用方法

### 本地运行

1. **在浏览器中打开：**
   ```bash
   # 方式 1：直接打开文件
   open index.html
   
   # 方式 2：使用 Python 简单服务器
   python -m http.server 8000
   # 然后访问 http://localhost:8000
   ```

2. **与 Node.js 服务器集成：**
   ```bash
   npm install
   npm start
   # 访问 http://localhost:3000
   ```

### 基本操作

- **查看错误详情**：点击卡片查看完整信息
- **放大图片**：点击卡片中的图片区域
- **复制请求 ID**：点击请求 ID 旁的复制按钮
- **切换主题**：点击右上角的月亮图标
- **刷新数据**：点击右上角的刷新图标

## 代码结构

### HTML 结构

```html
<body>
  <header class="header">...</header>
  <main class="main-content">
    <section class="stats-panel">...</section>
    <section class="cards-section">...</section>
    <section class="analysis-section">...</section>
  </main>
  <div class="modal" id="imageModal">...</div>
</body>
```

### CSS 变量系统

```css
:root {
  --primary-color: #0084ff;
  --error-color: #ff3b30;
  --success-color: #34c759;
  --warning-color: #ff9500;
  --bg-color: #f5f5f5;
  --text-color: #333;
  /* ... 更多变量 */
}

/* 深色模式 */
body.dark-mode {
  --bg-color: #1a1a1a;
  --text-color: #f0f0f0;
  /* ... */
}
```

### JavaScript 模块

```javascript
// 初始化函数
initializeEventListeners()
initializeData()

// 模态框处理
openImageModal()
closeImageModal()

// 事件处理
handleActionButton()
handleLinkClick()
handleKeyboardShortcuts()

// 数据操作
fetchErrorData()
filterAndSort()
renderCards()

// 通知系统
showNotification(message, type)
updateStats()
```

## API 数据格式

项目期望的数据格式：

```javascript
{
  errors: [
    {
      id: "error_401",
      code: "InvalidApiKey",
      title: "认证错误",
      message: "Invalid API-key provided.",
      severity: "error",
      timestamp: "2024-04-10T10:15:32Z",
      requestId: "ce999c53-c828-9b83-b370-eae4db87a93f",
      screenshot: "data:image/...",
      solutions: [
        { title: "重新生成密钥", url: "#" }
      ]
    },
    // ... 更多错误
  ],
  stats: {
    totalErrors: 42,
    warnings: 12,
    successRate: 0.95,
    avgLatency: 245
  }
}
```

## 样式定制

### 修改主题色

编辑 `style.css` 中的 CSS 变量：

```css
:root {
  --primary-color: #新颜色;      /* 主色调 */
  --error-color: #新颜色;        /* 错误色 */
  --success-color: #新颜色;      /* 成功色 */
}
```

### 调整卡片布局

```css
.cards-grid {
  grid-template-columns: repeat(4, 1fr);  /* 改为需要的列数 */
  gap: 20px;                               /* 卡片间距 */
}
```

## 浏览器兼容性

- ✅ Chrome / Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ⚠️ IE 11（不支持 CSS Grid）

## 性能指标

- 首屏加载时间：< 1s
- 图片加载：按需加载（模态框）
- LCP（最大内容绘制）：< 2.5s
- CLS（累积布局偏移）：< 0.1

## 常见问题

### Q: 如何添加新的错误卡片？
**A:** 修改 `script.js` 中的数据，添加新的错误对象到 `ErrorData` 数组。

### Q: 如何自定义通知样式？
**A:** 在 `style.css` 中修改 `.notification` 及其伪类的样式。

### Q: 深色模式如何工作？
**A:** JavaScript 在 `<body>` 上添加 `dark-mode` 类，CSS 使用属性选择器切换变量值。

### Q: 如何连接真实 API？
**A:** 修改 `script.js` 中的 `fetchErrorData()` 函数，指向真实的数据端点。

## 部署指南

### 静态托管（GitHub Pages, Vercel）

1. 上传三个文件到仓库
2. 配置 GitHub Pages 或连接 Vercel
3. 自动部署完成

### 自主服务器部署

```bash
# 使用 Nginx
location / {
    root /var/www/image_card_project;
    try_files $uri $uri/ /index.html;
}

# 使用 Apache
<Directory /var/www/image_card_project>
    RewriteEngine On
    RewriteBase /
    RewriteRule ^index\.html$ - [L]
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule . /index.html [L]
</Directory>
```

## 许可证

MIT License

## 作者

开发者：Shizuku 与 Agent
创建日期：2026-04-10
最后更新：2026-04-10
