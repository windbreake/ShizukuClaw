import re
with open('src/static/css/style.css', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure all col-md-X wrappers are safely full width
# Adjust standard row width if needed
if '#v-pills-tabContent' not in content:
    content += "\n\n#v-pills-tabContent {\n    max-width: 1400px;\n    margin: 0 auto;\n}\n"
else:
    content = content.replace('max-width: 1100px;', 'max-width: 1400px;')

with open('src/static/css/style.css', 'w', encoding='utf-8') as f:
    f.write(content)

