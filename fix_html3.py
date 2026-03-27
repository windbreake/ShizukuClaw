import glob
import os
hist_files = glob.glob(r'C:\Users\win11\AppData\Roaming\Code\User\History\-65ea3cc\*.html')
hist_files.sort(key=os.path.getmtime)

for file in hist_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    if '在此处配置 OneBot 11' in content:
        print(f"Found good version in {file}")
        with open('good_content.html', 'w', encoding='utf-8') as out_f:
            out_f.write(content)
        break
