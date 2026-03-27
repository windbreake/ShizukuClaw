import re

with open('src/unified_api.py', 'r', encoding='utf-8') as f:
    text = f.read()

fix_code = '''
# 修复 Windows 后台运行时的 OSError: [Errno 22] Invalid argument 错误
import sys
import os
try:
    sys.stdout.fileno()
except OSError:
    sys.stdout = open(os.devnull, "w")
try:
    sys.stderr.fileno()
except OSError:
    sys.stderr = open(os.devnull, "w")
'''

text = text.replace('import sys', 'import sys\n' + fix_code)

with open('src/unified_api.py', 'w', encoding='utf-8') as f:
    f.write(text)
