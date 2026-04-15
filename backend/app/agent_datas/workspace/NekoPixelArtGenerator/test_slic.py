#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试SLIC算法功能
"""

import sys
import os
import numpy as np
from PIL import Image

# 添加PythonScripts到路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PythonScripts'))

def test_slic():
    """测试SLIC算法"""
    try:
        # 创建测试图像
        test_image = Image.new('RGB', (100, 100), color='red')
        from PIL import ImageDraw
        draw = ImageDraw.Draw(test_image)
        draw.rectangle([25, 25, 75, 75], fill='blue')
        draw.ellipse([40, 40, 60, 60], fill='green')
        
        # 转换为numpy数组
        image_array = np.array(test_image)
        height, width = image_array.shape[:2]
        
        print(f"测试图像尺寸: {width}x{height}")
        
        # 测试SLIC
        from slic import SLIC
        slic_instance = SLIC(image_array, width, height)
        
        # 执行像素化处理
        result = slic_instance.pixel_deal(step=10, iters=5, stride=10, weight=10.0)
        
        # 转换结果为PIL图像
        result_image = Image.fromarray(result.astype('uint8'), 'RGB')
        
        # 保存结果
        result_image.save('test_slic_output.png')
        print("✓ SLIC算法测试通过，结果已保存为 test_slic_output.png")
        return True
        
    except Exception as e:
        print(f"✗ SLIC算法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("开始测试SLIC算法...")
    success = test_slic()
    sys.exit(0 if success else 1)