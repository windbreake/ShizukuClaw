#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试处理器功能
"""

import sys
from PIL import Image
import numpy as np
import io

# 尝试导入我们的处理器
try:
    import processors
    print("处理器导入成功")
except ImportError as e:
    print(f"处理器导入失败: {e}")
    sys.exit(1)

def test_pixelate_average():
    """测试像素化功能"""
    # 创建一个简单的测试图像
    test_image = Image.new('RGB', (100, 100), color='red')
    
    # 应用像素化
    result = processors.pixelate_average(test_image, 10)
    
    # 检查结果
    if result.size == test_image.size:
        print("像素化测试通过")
        return True
    else:
        print("像素化测试失败")
        return False

def test_median_cut_quantize():
    """测试中位切分量化"""
    # 创建一个有多颜色的测试图像
    test_image = Image.new('RGB', (100, 100), color='red')
    
    # 应用量化
    result = processors.median_cut_quantize(test_image, 16)
    
    # 检查结果
    if result.size == test_image.size:
        print("中位切分量化测试通过")
        return True
    else:
        print("中位切分量化测试失败")
        return False

def test_bayer_dither():
    """测试拜耳抖动"""
    # 创建一个测试图像
    test_image = Image.new('RGB', (100, 100), color='red')
    
    # 应用抖动
    result = processors.apply_bayer_dither(test_image, 0.1)
    
    # 检查结果
    if result.size == test_image.size:
        print("拜耳抖动测试通过")
        return True
    else:
        print("拜耳抖动测试失败")
        return False

def test_palette_quantize():
    """测试调色板量化"""
    # 创建一个测试图像
    test_image = Image.new('RGB', (100, 100), color='red')
    
    # 应用调色板量化
    result = processors.quantize_to_palette(test_image, 'gameboy')
    
    # 检查结果
    if result.size == test_image.size:
        print("调色板量化测试通过")
        return True
    else:
        print("调色板量化测试失败")
        return False

def test_cartoon_effect():
    """测试卡通效果"""
    # 创建一个测试图像
    test_image = Image.new('RGB', (100, 100), color='red')
    
    # 应用卡通效果
    result = processors.cartoon_effect(test_image, 0.3)
    
    # 检查结果
    if result.size == test_image.size:
        print("卡通效果测试通过")
        return True
    else:
        print("卡通效果测试失败")
        return False

def test_process_image_internal():
    """测试完整的图像处理管道"""
    # 创建一个测试图像
    test_image = Image.new('RGB', (100, 100), color='red')
    
    # 将图像转换为字节
    img_byte_arr = io.BytesIO()
    test_image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()
    
    # 设置处理选项
    options = {
        'block_size': 8,
        'max_colors': 32,
        'enable_dither': True,
        'dither_strength': 0.1,
        'enable_cartoon': False,
        'palette_name': 'gameboy'
    }
    
    # 处理图像
    try:
        result_bytes = processors.process_image_internal(image_bytes, options)
        result_image = Image.open(io.BytesIO(result_bytes))
        
        # 检查结果
        if result_image.size == test_image.size:
            print("完整图像处理管道测试通过")
            return True
        else:
            print("完整图像处理管道测试失败")
            return False
    except Exception as e:
        print(f"完整图像处理管道测试失败: {e}")
        return False

if __name__ == '__main__':
    print("开始测试处理器功能...")
    
    tests = [
        test_pixelate_average,
        test_median_cut_quantize,
        test_bayer_dither,
        test_palette_quantize,
        test_cartoon_effect,
        test_process_image_internal
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"测试 {test.__name__} 出错: {e}")
    
    print(f"测试完成: {passed}/{len(tests)} 通过")
    
    if passed == len(tests):
        print("所有测试通过!")
        sys.exit(0)
    else:
        print("部分测试失败!")
        sys.exit(1)