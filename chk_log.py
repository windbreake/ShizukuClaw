import subprocess
out = subprocess.check_output(['git', 'log', '-1', 'src/static/control_panel.html']).decode()
with open('tmp_out.txt', 'w', encoding='utf-8') as f:
    f.write(out)
