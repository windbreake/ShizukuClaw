import glob
import re
import time

for f in glob.glob('src/static/*.html'):
    with open(f, 'r', encoding='utf-8') as file:
        text = file.read()
    
    text = re.sub(r'\.(css|js)(\?v=\w+)?\"', r'.\1?v=n1"', text)
    
    with open(f, 'w', encoding='utf-8') as file:
        file.write(text)
print('Done!')
