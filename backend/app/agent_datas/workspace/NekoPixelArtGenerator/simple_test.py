#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试脚本，用于测试SLIC算法性能
"""

import sys
import os
from PIL import Image
import numpy as np

# 添加PythonScripts到路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PythonScripts'))

def main():
    # 加载图像
    print("加载图像...")
    image_path = r"C:\Users\win11\Pictures\baka.png"
    img = Image.open(image_path)
    print(f"原始图像尺寸: {img.size}")
    
    # 缩小图像以加快处理速度
    print("调整图像大小以加快处理...")
    img.thumbnail((100, 100), Image.Resampling.LANCZOS)
    print(f"调整后尺寸: {img.size}")
    
    # 转换为numpy数组
    image_array = np.array(img)
    height, width = image_array.shape[:2]
    
    print("开始SLIC处理...")
    
    # 测试SLIC
    from slic import SLIC
    slic_instance = SLIC(image_array, width, height)
    
    # 执行像素化处理 (使用较小的参数以加快速度)
    print("执行像素化处理...")
    result = slic_instance.pixel_deal(step=10, iters=3, stride=10, weight=10.0)
    
    # 转换结果为PIL图像
    result_image = Image.fromarray(result.astype('uint8'), 'RGB')
    
    # 保存结果
    result_image.save('baka_slic_test_output.png')
    print("处理完成，结果已保存为 baka_slic_test_output.png")

if __name__ == '__main__':
    main()