# -*- coding: utf-8 -*-
"""Launcher bootstrap for startup checks and web app entry."""

import json
import os
import socket
import subprocess
import sys
import time
from urllib import error, request

# launcher_boot.py 在 src/core/ 目录，需要向上两层到项目根目录
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SYSTEM_CONFIG_PATH = os.path.join(BASE_DIR, 'data', 'system_config.json')

# Ensure imports from project root work when launching via `python src/launcher_boot.py`.
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def load_launcher_settings():
    default_settings = {
        'startup_self_check': True,
        'open_browser': True,
        'startup_page': '/control_panel',
        'auto_start_adapter': True,
    }
    try:
        with open(SYSTEM_CONFIG_PATH, 'r', encoding='utf-8') as file_handle:
            data = json.load(file_handle)
        launcher = data.get('launcher', {}) if isinstance(data, dict) else {}
        if isinstance(launcher, dict):
            default_settings.update(launcher)
    except Exception:
        pass
    return default_settings


def run_startup_self_check(timeout_seconds=20):
    """Run startup self-check in a subprocess and never block startup flow."""
    print('[INFO] Running startup self-check...')
    main_py = os.path.join(BASE_DIR, 'main.py')
    try:
        result = subprocess.run(
            [sys.executable, main_py, '3'],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )

        output = (result.stdout or '').strip()
        if output:
            print(output)

        if result.returncode != 0:
            err = (result.stderr or '').strip()
            if err:
                print(f'[WARN] Startup self-check stderr: {err}')
            print(f'[WARN] Startup self-check exited with code {result.returncode}; continuing startup.')
    except subprocess.TimeoutExpired:
        print(f'[WARN] Startup self-check timeout ({timeout_seconds}s); continuing startup.')
    except BaseException as exc:
        print(f'[WARN] Startup self-check failed: {exc}; continuing startup.')


def _is_adapter_health_ok(port: int) -> bool:
    """Only treat a port as adapter when /health returns adapter signature."""
    health_url = f'http://127.0.0.1:{int(port)}/health'
    try:
        req = request.Request(health_url, method='GET')
        with request.urlopen(req, timeout=0.4) as resp:
            body = (resp.read() or b'').decode('utf-8', errors='ignore').lower()
            return resp.status == 200 and ('ok' in body or 'healthy' in body)
    except (error.URLError, TimeoutError, OSError, ValueError):
        return False


def is_adapter_running(start_port=5000, end_port=5100):
    for port in range(int(start_port), int(end_port) + 1):
        # Fast TCP check first to skip closed ports quickly.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.15)
            if sock.connect_ex(('127.0.0.1', port)) != 0:
                continue

        if _is_adapter_health_ok(port):
            return True
    return False


def start_adapter_background():
    """Start main.py mode 0 in background if adapter is not running."""
    if is_adapter_running():
        print('[INFO] Adapter already running (5000-5100).')
        return

    main_py = os.path.join(BASE_DIR, 'main.py')
    kwargs = {
        'cwd': BASE_DIR,
        'stdin': subprocess.DEVNULL,
        'stdout': subprocess.DEVNULL,
        'stderr': subprocess.DEVNULL,
    }
    if os.name == 'nt':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)

    subprocess.Popen([sys.executable, main_py, '0'], **kwargs)

    # Give adapter a short warm-up window.
    for _ in range(12):
        if is_adapter_running():
            print('[INFO] Adapter started successfully.')
            return
        time.sleep(0.25)
    print('[WARN] Adapter start requested, but no listening port detected yet.')


def main():
    launcher = load_launcher_settings()
    startup_page = str(launcher.get('startup_page', '/control_panel') or '/control_panel').strip()
    if not startup_page.startswith('/'):
        startup_page = f'/{startup_page}'

    # Allow one-off override from caller scripts; otherwise follow launcher config.
    os.environ.setdefault('DEFAULT_PAGE', startup_page)

    if launcher.get('startup_self_check', True):
        timeout_seconds = launcher.get('startup_self_check_timeout_sec', 20)
        run_startup_self_check(timeout_seconds)
    else:
        print('[INFO] Startup self-check is disabled.')

    if launcher.get('auto_start_adapter', True):
        start_adapter_background()
    else:
        print('[INFO] Auto-start adapter is disabled.')

    main_py = os.path.join(BASE_DIR, 'main.py')
    return subprocess.call([sys.executable, main_py, '5'], cwd=BASE_DIR)


if __name__ == '__main__':
    raise SystemExit(main())
