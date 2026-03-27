import re
with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure all col-md-X wrappers in the form of class="col-8" are safely full width
content = re.sub(r'class="col-\d+"', 'class="col-12 px-4"', content)

with open('src/static/control_panel.html', 'w', encoding='utf-8') as f:
    f.write(content)

