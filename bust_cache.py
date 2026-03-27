import glob
import re

for filename in glob.glob('src/static/*.html'):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # match .css" or .css?v=..." and replace it
    content = re.sub(r'\.(css|js)(\?v=[\w\d]+)?\"', r'.\1?v=n9"', content)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

print("Cache busters injected perfectly!")