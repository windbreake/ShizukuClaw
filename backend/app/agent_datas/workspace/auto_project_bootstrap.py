import os, subprocess, sys, time, json, shutil
project_dir = 'weather-app'
start_mode = True
workspace = os.getcwd()
target = os.path.join(workspace, project_dir)
print('workspace:', workspace)
print('project_dir:', project_dir)
os.makedirs(target, exist_ok=True)
print('cd', project_dir)
print('ls')
try:
    print(sorted(os.listdir(target)))
except Exception as e:
    print('list_error:', str(e))
def run(cmd, cwd=target, timeout=300):
    print('cmd:', cmd)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
pkg_json = os.path.join(target, 'package.json')
if not os.path.exists(pkg_json):
    init_cmd = f'npm create vite@latest {project_dir} -- --template vanilla-ts'
    print('init_cmd:', init_cmd)
    init_res = run(init_cmd, cwd=workspace, timeout=600)
    print('init_returncode:', init_res.returncode)
    if init_res.stdout:
        print('init_stdout:\n' + init_res.stdout)
    if init_res.stderr:
        print('init_stderr:\n' + init_res.stderr)
if os.path.exists(pkg_json):
    install_res = run('npm install', timeout=600)
    print('install_returncode:', install_res.returncode)
    if install_res.stdout:
        print('install_stdout:\n' + install_res.stdout)
    if install_res.stderr:
        print('install_stderr:\n' + install_res.stderr)
else:
    print('package_json_not_found_after_init')
    sys.exit(1)
if start_mode:
    start_cmd = 'npm run dev -- --host 127.0.0.1 --port 5173'
    print('start_cmd:', start_cmd)
    proc = subprocess.Popen(start_cmd, cwd=target, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    print('pid:', proc.pid)
    print('alive:', proc.poll() is None)
    print('url:', 'http://127.0.0.1:5173/')
    sys.exit(0 if proc.poll() is None else 1)
else:
    print('start_mode_disabled')
    sys.exit(0)
