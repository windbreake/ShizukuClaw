import re
with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Fix config DB config class
html = re.sub(r'(<!-- DB Config -->\s*)<div class="col-md-6">', r'\g<1><div class="col-lg-8 mx-auto">', html)

# Change plain rows to row g-4 where they don't have it
html = html.replace('<div class="row">', '<div class="row g-4">')

# Config other sections: OneBot 11 is now col-12, Unified API is col-12. Let's make them col-lg-8 mx-auto
html = re.sub(r'(<!-- OneBot 11 Connection Settings -->\s*)<div class="col-12">', r'\g<1><div class="col-lg-8 mx-auto">', html)
html = re.sub(r'(<!-- Unified API Settings -->\s*)<div class="col-12">', r'\g<1><div class="col-lg-8 mx-auto">', html)
html = re.sub(r'(<!-- Admin UI Access Control -->\s*)<div class="col-12">', r'\g<1><div class="col-lg-8 mx-auto">', html)

with open('src/static/control_panel.html', 'w', encoding='utf-8') as f:
    f.write(html)
