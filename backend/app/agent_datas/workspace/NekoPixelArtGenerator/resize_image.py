#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调整图像大小
"""

from PIL import Image

def main():
    # 加载图像
    print("加载图像...")
    image_path = r"C:\Users\win11\Pictures\baka.png"
    img = Image.open(image_path)
    print(f"原始图像尺寸: {img.size}")
    
    # 缩小图像
    print("调整图像大小...")
    img_resized = img.resize((256, int(256 * img.height / img.width)), Image.Resampling.LANCZOS)
    print(f"调整后尺寸: {img_resized.size}")
    
    # 保存结果
    output_path = 'baka_small.png'
    img_resized.save(output_path)
    print(f"结果已保存为 {output_path}")

if __name__ == '__main__':
    main()