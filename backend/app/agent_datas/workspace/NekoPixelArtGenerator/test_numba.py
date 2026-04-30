#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Numba是否正常工作
"""

import numpy as np
try:
    import numba
    print('numba available')
except ImportError:
    print('numba not available')
from numba import jit

@jit(nopython=True)
def test_function(x):
    return x ** 2

def main():
    # 创建测试数组
    test_array = np.array([1, 2, 3, 4, 5], dtype=np.float64)
    
    # 测试Numba函数
    result = test_function(test_array)
    print("Numba测试结果:", result)
    print("Numba正常工作!")

if __name__ == '__main__':
    main()