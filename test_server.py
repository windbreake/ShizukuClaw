#!/usr/bin/env python
# -*- coding: utf-8 -*-
import traceback
import sys

sys.path.insert(0, '.')


def run_server_debug() -> int:
    """Debug entry for local manual validation of src.web_server."""
    try:
        print("= 导入 web_server...")
        from src.web_server import run_web_server, app

        print("✓ 导入成功")
        print("\n= 检查 Flask app...")
        print(f"  Flask app: {app}")
        print(f"  App name: {app.name}")

        print("\n= 启动服务器...")
        return int(run_web_server() or 0)
    except (ImportError, OSError, RuntimeError, ValueError) as e:
        print(f"\n✗ 错误: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(run_server_debug())
