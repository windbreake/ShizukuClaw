import re

with open('good_content.html', 'r', encoding='utf-8') as f:
    good_content = f.read()

# Apply the col-12 wrapper and layout fixes to good_content
good_content = good_content.replace('<div class="col-md-8 mx-auto">', '<div class="col-12 px-4">')
# Actually let's just make sure all mx-auto or similar are updated to col-12

with open('src/static/control_panel.html', 'w', encoding='utf-8') as f:
    f.write(good_content)

print('Restored HTML to good version and saved.')
