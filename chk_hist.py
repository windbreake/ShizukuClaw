import os, glob
history_dir = r'C:\Users\win11\AppData\Roaming\Code\User\History\-65ea3cc'
files = glob.glob(os.path.join(history_dir, '*.html'))
files.sort(key=os.path.getmtime, reverse=True)
for f in files[:10]:
    try:
        text = open(f, 'r', encoding='utf-8').read()
        print(f"{os.path.basename(f)} size: {len(text)}, garbled: {'' in text or 'ڴ˴' in text}, onebot: {'OneBot' in text}, time: {os.path.getmtime(f)}")
    except Exception as e:
        print(f, e)
