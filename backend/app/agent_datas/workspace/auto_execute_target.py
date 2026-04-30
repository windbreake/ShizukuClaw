import os, sys, subprocess, shutil
target = 'snake_game.py'
start_mode = True
target = target.replace('\\', '/')
ext = os.path.splitext(target)[1].lower()
cwd = os.path.dirname(target) or '.'
base = os.path.basename(target)
def has(cmd):
    return shutil.which(cmd) is not None
cmd = []
if ext == '.py':
    cmd = [sys.executable, base]
elif ext in ('.js', '.mjs', '.cjs'):
    cmd = ['node', base]
elif ext in ('.ts', '.tsx'):
    cmd = ['tsx', base] if has('tsx') else (['npx', '-y', 'tsx', base] if has('npx') else [])
elif ext == '.java':
    cmd = ['java', base]
elif ext == '.go':
    cmd = ['go', 'run', base]
elif ext in ('.rb',):
    cmd = ['ruby', base]
elif ext in ('.php',):
    cmd = ['php', base]
elif ext in ('.ps1',):
    cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', base]
elif ext in ('.sh',):
    cmd = ['bash', base]
elif ext == '.csproj':
    cmd = ['dotnet', 'run', '--project', base]
elif ext == '.sln':
    cmd = ['dotnet', 'build', base]
elif ext in ('.c',):
    out = '_tmp_run.exe' if os.name == 'nt' else '_tmp_run'
    cmd = ['cmd', '/c', f'gcc "{base}" -o {out} && {out}'] if os.name == 'nt' else ['bash', '-lc', f'gcc "{base}" -o {out} && ./{out}']
elif ext in ('.cc', '.cpp', '.cxx'):
    out = '_tmp_run.exe' if os.name == 'nt' else '_tmp_run'
    cmd = ['cmd', '/c', f'g++ "{base}" -o {out} && {out}'] if os.name == 'nt' else ['bash', '-lc', f'g++ "{base}" -o {out} && ./{out}']
elif ext == '.rs':
    cmd = ['cargo', 'run'] if os.path.exists(os.path.join(cwd, 'Cargo.toml')) else []
print('target:', target)
print('cwd:', cwd)
if not cmd:
    print('unsupported target extension:', ext)
    sys.exit(3)
print('cmd:', ' '.join(cmd))
def _extract_missing(stderr_text):
    import re as _re
    m = _re.findall(r"No module named ['\"]([A-Za-z0-9_\-.]+)['\"]", str(stderr_text or ''))
    return list(dict.fromkeys([x.strip() for x in m if str(x).strip()]))
def _run_once(timeout_s):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
if ext == '.py' and start_mode:
    # Probe first to detect missing dependencies quickly.
    try:
        probe = _run_once(8)
        print('probe_returncode:', probe.returncode)
        if probe.stdout:
            print('probe_stdout:\n' + probe.stdout)
        if probe.stderr:
            print('probe_stderr:\n' + probe.stderr)
        if probe.returncode != 0:
            err_text = str(probe.stderr or '')
            missing = _extract_missing(probe.stderr)
            if missing:
                print('auto_install_missing:', ','.join(missing))
                pip_res = subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing, cwd=cwd, capture_output=True, text=True, timeout=180)
                print('pip_returncode:', pip_res.returncode)
                if pip_res.stdout:
                    print('pip_stdout:\n' + pip_res.stdout)
                if pip_res.stderr:
                    print('pip_stderr:\n' + pip_res.stderr)
                if pip_res.returncode == 0:
                    probe = _run_once(8)
                    print('probe_after_install_returncode:', probe.returncode)
                    if probe.stderr:
                        print('probe_after_install_stderr:\n' + probe.stderr)
            # One-shot syntax auto-fix for common formatting/indentation issues.
            if probe.returncode != 0 and ('IndentationError' in err_text or 'TabError' in err_text or 'SyntaxError' in err_text):
                print('auto_fix_syntax: trying autopep8 in-place')
                try:
                    chk = subprocess.run([sys.executable, '-m', 'autopep8', '--version'], cwd=cwd, capture_output=True, text=True, timeout=20)
                    if chk.returncode != 0:
                        inst = subprocess.run([sys.executable, '-m', 'pip', 'install', 'autopep8'], cwd=cwd, capture_output=True, text=True, timeout=120)
                        print('autopep8_install_returncode:', inst.returncode)
                    fix = subprocess.run([sys.executable, '-m', 'autopep8', '--in-place', base], cwd=cwd, capture_output=True, text=True, timeout=40)
                    print('autopep8_fix_returncode:', fix.returncode)
                    probe = _run_once(8)
                    print('probe_after_fix_returncode:', probe.returncode)
                    if probe.stderr:
                        print('probe_after_fix_stderr:\n' + probe.stderr)
                except Exception as _fix_err:
                    print('auto_fix_syntax_error:', str(_fix_err))
    except subprocess.TimeoutExpired:
        print('probe_timeout: target seems long-running, continue start')
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time as _time
    _time.sleep(1.0)
    alive = proc.poll() is None
    print('started_pid:', int(proc.pid))
    print('started_alive:', bool(alive))
    sys.exit(0 if alive else 1)
else:
    res = _run_once(120)
    if ext == '.py' and res.returncode != 0:
        missing = _extract_missing(res.stderr)
        if missing:
            print('auto_install_missing:', ','.join(missing))
            pip_res = subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing, cwd=cwd, capture_output=True, text=True, timeout=180)
            print('pip_returncode:', pip_res.returncode)
            if pip_res.stdout:
                print('pip_stdout:\n' + pip_res.stdout)
            if pip_res.stderr:
                print('pip_stderr:\n' + pip_res.stderr)
            if pip_res.returncode == 0:
                res = _run_once(120)
    print('returncode:', res.returncode)
    if res.stdout:
        print('stdout:\n' + res.stdout)
    if res.stderr:
        print('stderr:\n' + res.stderr)
