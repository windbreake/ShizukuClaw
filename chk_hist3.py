import os, glob
history_dir = r'C:\Users\win11\AppData\Roaming\Code\User\History\-65ea3cc'
files = glob.glob(os.path.join(history_dir, '*.html'))
files.sort(key=os.path.getmtime, reverse=True)
for f in files[:20]:
    try:
        text = open(f, 'r', encoding='utf-8').read()
        target = text.find('HTTP/WebSocket')
        snippet = text[max(0, target-30) : target+150].replace('\n', ' ')
        print(f"{os.path.basename(f)}: {snippet}")
    except Exception as e:
        print(f, e)
