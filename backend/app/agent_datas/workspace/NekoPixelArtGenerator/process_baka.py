#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理Baka.png图像，使用优化参数
"""

import sys
import os
from PIL import Image
import numpy as np
import time

# 添加PythonScripts到路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PythonScripts'))

def main():
    # 加载图像
    print("加载图像...")
    image_path = r"C:\Users\win11\Pictures\baka.png"
    img = Image.open(image_path)
    print(f"原始图像尺寸: {img.size}")
    
    # 适度缩小图像
    print("调整图像大小...")
    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
    print(f"调整后尺寸: {img.size}")
    
    # 转换为numpy数组
    image_array = np.array(img)
    height, width = image_array.shape[:2]
    
    print("开始SLIC处理...")
    start_time = time.time()
    
    # 测试SLIC
    from slic import SLIC
    slic_instance = SLIC(image_array, width, height)
    
    # 执行像素化处理 (使用优化参数)
    print("执行像素化处理...")
    result = slic_instance.pixel_deal(step=20, iters=3, stride=20, weight=10.0)
    
    # 转换结果为PIL图像
    result_image = Image.fromarray(result.astype('uint8'), 'RGB')
    
    # 保存结果
    output_path = 'baka_pixelated_output.png'
    result_image.save(output_path)
    
    end_time = time.time()
    print(f"处理完成，耗时: {end_time - start_time:.2f} 秒")
    print(f"结果已保存为 {output_path}")

if __name__ == '__main__':
    main()