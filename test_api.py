#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

from app.frameworks.instruction_manager import get_instruction_manager

manager = get_instruction_manager()
personalities = manager.list_personalities()
print(f'Loaded {len(personalities)} personalities:')
for p in personalities:
    print(f'  - {p["name"]} (ID: {p["id"]})')
