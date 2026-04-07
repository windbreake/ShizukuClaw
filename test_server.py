#!/usr/bin/env python
# -*- coding: utf-8 -*-
import traceback
import sys

sys.path.insert(0, '.')

try:
    print("= 导入 web_server...")
    from src.web_server import main, app
    print("✓ 导入成功")
    
    print("\n= 检查 Flask app...")
    print(f"  Flask app: {app}")
    print(f"  App name: {app.name}")
    
    print("\n= 启动服务器...")
    sys.exit(main())
except Exception as e:
    print(f"\n✗ 错误: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)
