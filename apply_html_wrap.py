import re
with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure all col-md-X wrappers are safely full width
content = re.sub(r'col-md-\d+\s+mx-auto', 'col-12 px-4', content)
content = re.sub(r'class="col-md-\d+"', 'class="col-12 px-4"', content)

with open('src/static/control_panel.html', 'w', encoding='utf-8') as f:
    f.write(content)

