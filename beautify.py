import re

with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Launcher formatting
# Add shadows and nice headers to Launcher cards
html = html.replace('<div class="card h-100">', '<div class="card h-100 shadow-sm border-0 fade-in">')
# The ones that already have bg-primary etc. we can keep or adjust

# 2. Config Formatting
# Find DB config header
html = html.replace('<div class="card mb-4">', '<div class="card h-100 shadow-sm border-0 fade-in mb-4">')
# Replace old card-headers with dashboard-friendly ones
html = html.replace('<div class="card-header bg-light fw-bold">', '<div class="card-header bg-white border-bottom-0 pt-3 fw-bold fs-5">')
html = html.replace('<div class="card-header bg-success text-white fw-bold">', '<div class="card-header bg-white border-bottom-0 pt-3 fw-bold fs-5 text-success">')
html = html.replace('<div class="card-header bg-info text-white fw-bold">', '<div class="card-header bg-white border-bottom-0 pt-3 fw-bold fs-5 text-info">')
html = html.replace('<div class="card-header bg-warning text-dark fw-bold d-flex', '<div class="card-header bg-white border-bottom-0 pt-3 fw-bold fs-5 text-warning d-flex')

# Adjust config grid: if DB is col-md-6 and there's no right column anymore, it looks unbalanced. Let's make DB col-lg-8 mx-auto or just leave it.
# Actually, since we extracted Persona out of config, DB Config is alone as a col-md-6 in a row. It should probably be col-12 or col-lg-8 mx-auto.
html = html.replace('<!-- DB Config -->\n                      <div class="col-md-6">', '<!-- DB Config -->\n                      <div class="col-xl-8 mx-auto">')

# 3. Persona layout
# Find persona block
html = html.replace('<!-- Persona Tab -->\n        <div class="tab-pane fade" id="v-persona" role="tabpanel">\n            <h3 class="mb-4"><i class="fas fa-masks me-2"></i> 预设词与人格管理 (Persona)</h3>\n            <div class="row">\n                <div class="col-lg-10 mx-auto">', 
'<!-- Persona Tab -->\n        <div class="tab-pane fade" id="v-persona" role="tabpanel">\n            <div class="d-flex justify-content-between align-items-center mb-4">\n                <h3><i class="fas fa-masks text-warning me-2"></i> 预设词与人格管理</h3>\n            </div>\n            <div class="row">\n                <div class="col-xl-10 mx-auto">')
html = html.replace('<div class="col-lg-10 mx-auto">', '<div class="col-xl-8 mx-auto">') # General adjustment for wide layout
html = html.replace('<div class="col-md-8 mx-auto">', '<div class="col-xl-8 mx-auto">') 

# Sandbox formatting
html = html.replace('<h3 class="mb-4">💬 沙箱对话测试</h3>', '<div class="d-flex justify-content-between align-items-center mb-4">\n                <h3><i class="fas fa-comments text-primary me-2"></i> 沙箱对话测试</h3>\n              </div>')


with open('src/static/control_panel.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Beautiful styles applied")
