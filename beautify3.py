with open('src/static/css/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

if '#v-pills-tabContent' not in css:
    css += "\n#v-pills-tabContent {\n    max-width: 1400px;\n    margin: 0 auto;\n}\n"

with open('src/static/css/style.css', 'w', encoding='utf-8') as f:
    f.write(css)
