import glob
import os

hist_dir = r'C:\Users\win11\AppData\Roaming\Code\User\History\*\*.css'
files = glob.glob(hist_dir)
css_files = [f for f in files if open(f, 'r', encoding='utf-8', errors='ignore').read().find('--primary-color: #6f42c1') != -1]
css_files.sort(key=os.path.getmtime)
print(f"Found {len(css_files)} backups for style.css")
if css_files:
    print(f"Latest: {css_files[-1]}")
    import shutil
    shutil.copy(css_files[-1], 'src/static/css/style.css')
    print("reverted style.css")
