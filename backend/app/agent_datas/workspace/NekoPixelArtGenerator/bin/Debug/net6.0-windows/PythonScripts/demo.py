#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
像素画生成器演示脚本
展示高性能处理器的各种功能
"""

import sys
import os
from PIL import Image, ImageDraw
import numpy as np
import io

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import processors
    print("✓ 成功导入处理器模块")
except ImportError as e:
    print(f"✗ 导入处理器模块失败: {e}")
    sys.exit(1)

def create_sample_image():
    """创建一个示例图像用于测试"""
    # 创建一个彩色图像
    image = Image.new('RGB', (300, 300), color='white')
    draw = ImageDraw.Draw(image)
    
    # 绘制一些图形
    draw.rectangle([50, 50, 250, 250], fill='red', outline='black')
    draw.ellipse([100, 100, 200, 200], fill='blue', outline='black')
    draw.polygon([(150, 50), (100, 150), (200, 150)], fill='green')
    
    return image

def demo_pixelation():
    """演示像素化功能"""
    print("演示像素化功能...")
    image = create_sample_image()
    
    # 应用不同的像素大小
    for block_size in [4, 8, 16]:
        result = processors.pixelate_average(image, block_size)
        output_path = f'pixelation_{block_size}px.png'
        result.save(output_path)
        print(f"  ✓ 像素化 (块大小: {block_size}) 已保存为 {output_path}")

def demo_color_quantization():
    """演示颜色量化功能"""
    print("演示颜色量化功能...")
    image = create_sample_image()
    
    # 应用不同的颜色数量
    for color_count in [4, 8, 16]:
        result = processors.median_cut_quantize(image, color_count)
        output_path = f'quantization_{color_count}colors.png'
        result.save(output_path)
        print(f"  ✓ 颜色量化 ({color_count} 色) 已保存为 {output_path}")

def demo_dithering():
    """演示抖动功能"""
    print("演示抖动功能...")
    image = create_sample_image()
    
    # 应用不同的抖动强度
    for strength in [0.0, 0.1, 0.3]:
        result = processors.apply_bayer_dither(image, strength)
        output_path = f'dithering_{strength}.png'
        result.save(output_path)
        print(f"  ✓ 抖动 (强度: {strength}) 已保存为 {output_path}")

def demo_palette_mapping():
    """演示调色板映射功能"""
    print("演示调色板映射功能...")
    image = create_sample_image()
    
    # 应用不同的调色板
    for palette_name in ['gameboy', 'nes', 'c64']:
        result = processors.quantize_to_palette(image, palette_name)
        output_path = f'palette_{palette_name}.png'
        result.save(output_path)
        print(f"  ✓ 调色板映射 ({palette_name}) 已保存为 {output_path}")

def demo_cartoon_effect():
    """演示卡通效果功能"""
    print("演示卡通效果功能...")
    image = create_sample_image()
    
    # 应用不同的边缘权重
    for edge_weight in [0.0, 0.3, 0.6]:
        result = processors.cartoon_effect(image, edge_weight)
        output_path = f'cartoon_{edge_weight}.png'
        result.save(output_path)
        print(f"  ✓ 卡通效果 (边缘权重: {edge_weight}) 已保存为 {output_path}")

def demo_full_pipeline():
    """演示完整处理管道"""
    print("演示完整处理管道...")
    image = create_sample_image()
    
    # 将图像转换为字节
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()
    
    # 设置处理选项
    options = {
        'block_size': 8,
        'max_colors': 16,
        'enable_dither': True,
        'dither_strength': 0.2,
        'enable_cartoon': True,
        'palette_name': 'gameboy'
    }
    
    # 处理图像
    result_bytes = processors.process_image_internal(image_bytes, options)
    result_image = Image.open(io.BytesIO(result_bytes))
    
    # 保存结果
    output_path = 'full_pipeline_result.png'
    result_image.save(output_path)
    print(f"  ✓ 完整处理管道结果已保存为 {output_path}")

def main():
    """主函数"""
    print("像素画生成器演示")
    print("=" * 30)
    
    try:
        demo_pixelation()
        print()
        
        demo_color_quantization()
        print()
        
        demo_dithering()
        print()
        
        demo_palette_mapping()
        print()
        
        demo_cartoon_effect()
        print()
        
        demo_full_pipeline()
        print()
        
        print("所有演示完成！")
        print("请查看生成的图像文件以查看处理效果。")
        
    except Exception as e:
        print(f"演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()