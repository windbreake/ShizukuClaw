import re

with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('<h3 class="mb-4">⚙️ 系统全量配置</h3>', '<div class="d-flex justify-content-between align-items-center mb-4">\n                <h3><i class="fas fa-sliders-h text-info me-2"></i> 系统全量配置</h3>\n              </div>')

html = html.replace('<h3 class="mb-4">🚀 启动器 & 工具箱</h3>', '<div class="d-flex justify-content-between align-items-center mb-4">\n                <h3><i class="fas fa-rocket text-danger me-2"></i> 启动器 & 工具箱</h3>\n              </div>')

html = html.replace('<div class="col-md-4">\n                      <div class="card h-100 shadow-sm border-0 fade-in">', '<div class="col-md-4 fade-in">\n                      <div class="card h-100 shadow-sm border-0">')

with open('src/static/control_panel.html', 'w', encoding='utf-8') as f:
    f.write(html)
