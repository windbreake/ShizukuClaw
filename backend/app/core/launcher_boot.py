# -*- coding: utf-8 -*-
"""Launcher bootstrap for startup checks and web app entry."""

import json
import os
import socket
import subprocess
import sys
import time
from urllib import error, request

# launcher_boot.py 位于 backend/app/core，向上一层是 app 根目录
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
SYSTEM_CONFIG_PATH = os.path.join(BASE_DIR, 'db', 'data', 'system_config.json')

# Ensure imports from backend root work when launching via module entry.
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def load_launcher_settings():
    default_settings = {
        'startup_self_check': True,
        'open_browser': True,
        'startup_page': '/control_panel',
        'auto_start_adapter': True,
        'auto_install_office_deps': True,
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


def ensure_office_dependencies(auto_install=True):
    """Deprecated: use app.core.dependency_checker.check_main_dependencies() instead."""
    from app.core.dependency_checker import check_main_dependencies
    return check_main_dependencies()


def run_startup_self_check(timeout_seconds=20):
    """Run startup self-check in a subprocess and never block startup flow."""
    print('[INFO] Running startup self-check...')
    started_at = time.time()
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'app.main', '3'],
            cwd=BACKEND_DIR,
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
    finally:
        print(f'[INFO] Startup self-check finished in {time.time() - started_at:.1f}s.')


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
    scan_started_at = time.time()
    scan_start_port = 5000
    scan_end_port = 5005
    print(f'[INFO] Quick-checking adapter ports {scan_start_port}-{scan_end_port}...')
    if is_adapter_running(scan_start_port, scan_end_port):
        print(f'[INFO] Adapter already running ({scan_start_port}-{scan_end_port}); scan took {time.time() - scan_started_at:.1f}s.')
        return

    kwargs = {
        'cwd': BACKEND_DIR,
        'stdin': subprocess.DEVNULL,
        'stdout': subprocess.DEVNULL,
        'stderr': subprocess.DEVNULL,
    }
    if os.name == 'nt':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)

    subprocess.Popen([sys.executable, '-m', 'app.main', '0'], **kwargs)

    # Give adapter a short warm-up window without blocking startup too long.
    for _ in range(4):
        if is_adapter_running():
            print(f'[INFO] Adapter started successfully after {time.time() - scan_started_at:.1f}s.')
            return
        time.sleep(0.25)
    print(f'[WARN] Adapter start requested, but no listening port detected yet after {time.time() - scan_started_at:.1f}s.')


def main():
    launcher = load_launcher_settings()
    startup_page = str(launcher.get('startup_page', '/control_panel') or '/control_panel').strip()
    if not startup_page.startswith('/'):
        startup_page = f'/{startup_page}'

    # Allow one-off override from caller scripts; otherwise follow launcher config.
    os.environ.setdefault('DEFAULT_PAGE', startup_page)

    ensure_office_dependencies(bool(launcher.get('auto_install_office_deps', True)))

    if launcher.get('startup_self_check', True):
        timeout_seconds = launcher.get('startup_self_check_timeout_sec', 20)
        run_startup_self_check(timeout_seconds)
    else:
        print('[INFO] Startup self-check is disabled.')

    if launcher.get('auto_start_adapter', True):
        start_adapter_background()
    else:
        print('[INFO] Auto-start adapter is disabled.')

    print(f"[INFO] Launching web control panel on DEFAULT_PAGE={os.environ.get('DEFAULT_PAGE', '/control_panel')}")
    return subprocess.call([sys.executable, '-m', 'app.main', '5'], cwd=BACKEND_DIR)


if __name__ == '__main__':
    raise SystemExit(main())
