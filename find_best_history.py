import glob
import os
import re

hist_dir = r'C:\Users\win11\AppData\Roaming\Code\User\History\-65ea3cc\*.html'
files = glob.glob(hist_dir)
files.sort(key=os.path.getmtime)

for i, f in enumerate(files):
    content = open(f, 'r', encoding='utf-8', errors='ignore').read()
    has_launcher = 'v-launcher-tab' in content
    has_persona = 'v-persona-tab' in content
    has_good_encoding = '在此处配置 OneBot 11' in content
    has_bad_encoding = '在此处配?OneBot 11' in content
    print(f"[{i}] {os.path.basename(f)}: Launcher={has_launcher} Persona={has_persona} GoodEnc={has_good_encoding} BadEnc={has_bad_encoding}")
