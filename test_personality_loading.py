#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script to verify personality loading"""

import sys
import os

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

from app.frameworks.instruction_manager import get_instruction_manager

def test_load_personalities():
    print("Loading instruction manager...")
    manager = get_instruction_manager()
    
    print("Fetching personalities...")
    personalities = manager.list_personalities()
    
    print(f'\nLoaded {len(personalities)} personalities:')
    for p in personalities:
        print(f"  - ID: {p['id']}, Name: {p['name']}, Description: {p['description']}")
    
    return len(personalities) > 0

if __name__ == '__main__':
    try:
        success = test_load_personalities()
        if success:
            print('\n✓ SUCCESS: Personalities loaded correctly!')
            sys.exit(0)
        else:
            print('\n✗ FAILED: No personalities loaded!')
            sys.exit(1)
    except Exception as e:
        print(f'\n✗ ERROR: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
