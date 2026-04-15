#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
像素画生成器主脚本
支持多种像素化算法和效果处理
"""

import sys
import argparse
import json
import time
import numpy as np
from PIL import Image, ImageEnhance
from pathlib import Path
from typing import List, Tuple, Optional
import io

# 导入新的高性能处理器
try:
    import processors
    USE_NEW_PROCESSOR = True
except ImportError:
    USE_NEW_PROCESSOR = False

def main():
    """主函数 - 处理命令行参数并执行像素化处理"""
    parser = argparse.ArgumentParser(description='像素画生成工具')
    parser.add_argument('--input', required=True, help='输入图片路径')
    parser.add_argument('--output', required=True, help='输出图片路径')
    parser.add_argument('--pixel-size', type=int, default=16, help='像素块大小 (4-64)')
    parser.add_argument('--color-count', type=int, default=32, help='颜色数量 (2-256)')
    parser.add_argument('--palette', default='default', help='调色板名称')
    parser.add_argument('--algorithm', default='basic', help='像素化算法')
    parser.add_argument('--dithering', action='store_true', help='启用抖动效果')
    parser.add_argument('--edge-smoothing', type=float, default=0.5, help='边缘平滑程度 (0-1)')
    parser.add_argument('--contrast', type=float, default=1.0, help='对比度调整 (0.1-3.0)')
    parser.add_argument('--brightness', type=float, default=1.0, help='亮度调整 (0.1-2.0)')
    parser.add_argument('--saturation', type=float, default=1.0, help='饱和度调整 (0-2.0)')
    parser.add_argument('--progress-file', help='进度报告文件路径')
    # 新增参数
    parser.add_argument('--dither-strength', type=float, default=0.1, help='抖动强度 (0-1)')
    parser.add_argument('--cartoon-effect', action='store_true', help='启用卡通效果')
    
    args = parser.parse_args()
    
    try:
        # 验证参数
        validate_parameters(args)
        
        # 开始处理
        start_time = time.time()
        report_progress(args.progress_file, 5, "开始处理图片...")
        
        # 加载图片
        image = load_image(args.input)
        report_progress(args.progress_file, 15, "图片加载完成")
        
        # 基础调整
        image = apply_basic_adjustments(image, args)
        report_progress(args.progress_file, 25, "基础调整完成")
        
        if USE_NEW_PROCESSOR:
            # 使用新的高性能处理器
            result = process_with_new_processor(image, args)
        else:
            # 使用原有处理方法
            # 像素化处理
            pixelated = apply_pixelation(image, args.pixel_size, args.algorithm)
            report_progress(args.progress_file, 50, "像素化完成")
            
            # 颜色处理
            if args.palette != 'original':
                pixelated = apply_palette(pixelated, args.palette, args.color_count)
            report_progress(args.progress_file, 70, "调色板应用完成")
            
            # 抖动处理
            if args.dithering:
                pixelated = apply_dithering(pixelated, args.color_count)
            report_progress(args.progress_file, 85, "抖动处理完成")
            
            # 边缘平滑
            if args.edge_smoothing > 0:
                pixelated = apply_edge_smoothing(pixelated, args.edge_smoothing)
            report_progress(args.progress_file, 95, "边缘平滑完成")
            
            result = pixelated
        
        # 保存结果
        save_image(result, args.output)
        
        processing_time = time.time() - start_time
        report_progress(args.progress_file, 100, f"处理完成 (耗时: {processing_time:.2f}秒)")
        
        # 输出成功信息
        print(f"SUCCESS:{args.output}")
        print(f"TIME:{processing_time:.2f}")
        
    except Exception as e:
        print(f"ERROR:{str(e)}", file=sys.stderr)
        sys.exit(1)

def process_with_new_processor(image, args):
    """使用新的高性能处理器进行处理"""
    # 将图像转换为字节
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()
    
    # 构造选项字典
    options = {
        'block_size': args.pixel_size,
        'max_colors': args.color_count,
        'enable_dither': args.dithering,
        'dither_strength': args.dither_strength,
        'enable_cartoon': args.cartoon_effect,
        'palette_name': args.palette
    }
    
    # 处理图像
    result_bytes = processors.process_image_internal(image_bytes, options)
    
    # 将结果转换为PIL图像
    return Image.open(io.BytesIO(result_bytes))

def validate_parameters(args):
    """验证输入参数的有效性"""
    if not Path(args.input).exists():
        raise ValueError(f"输入文件不存在: {args.input}")
    
    if not (4 <= args.pixel_size <= 64):
        raise ValueError("像素大小必须在4-64之间")
    
    if not (2 <= args.color_count <= 256):
        raise ValueError("颜色数量必须在2-256之间")
    
    if not (0.1 <= args.contrast <= 3.0):
        raise ValueError("对比度必须在0.1-3.0之间")
    
    if not (0.1 <= args.brightness <= 2.0):
        raise ValueError("亮度必须在0.1-2.0之间")
    
    if not (0 <= args.saturation <= 2.0):
        raise ValueError("饱和度必须在0-2.0之间")
    
    if not (0 <= args.edge_smoothing <= 1.0):
        raise ValueError("边缘平滑必须在0-1.0之间")
    
    if not (0 <= args.dither_strength <= 1.0):
        raise ValueError("抖动强度必须在0-1.0之间")

def load_image(image_path):
    """加载图片文件"""
    try:
        image = Image.open(image_path)
        
        # 转换为RGB模式（如果需要）
        if image.mode != 'RGB':
            if image.mode == 'RGBA':
                # 处理透明背景
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background
            else:
                image = image.convert('RGB')
        
        return image
    except Exception as e:
        raise ValueError(f"无法加载图片: {str(e)}")

def apply_basic_adjustments(image, args):
    """应用基础调整（亮度、对比度、饱和度）"""
    # 亮度调整
    if args.brightness != 1.0:
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(args.brightness)
    
    # 对比度调整
    if args.contrast != 1.0:
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(args.contrast)
    
    # 饱和度调整
    if args.saturation != 1.0:
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(args.saturation)
    
    return image

def apply_pixelation(image, pixel_size, algorithm='basic'):
    """应用像素化效果"""
    width, height = image.size
    
    # 计算缩小后的尺寸
    small_width = max(1, width // pixel_size)
    small_height = max(1, height // pixel_size)
    
    # 根据算法选择不同的处理方式
    if algorithm == 'basic':
        # 基础像素化 - 最近邻缩放
        small = image.resize((small_width, small_height), Image.Resampling.NEAREST)
        result = small.resize((width, height), Image.Resampling.NEAREST)
        
    elif algorithm == 'average':
        # 平均值像素化 - 使用LANCZOS采样
        small = image.resize((small_width, small_height), Image.Resampling.LANCZOS)
        result = small.resize((width, height), Image.Resampling.NEAREST)
        
    elif algorithm == 'median':
        # 中值像素化 - 先缩小再放大
        small = image.resize((small_width, small_height), Image.Resampling.LANCZOS)
        
        # 应用中值滤波
        small_array = np.array(small)
        small_array = apply_median_filter(small_array, 2)
        small = Image.fromarray(small_array.astype(np.uint8))
        
        result = small.resize((width, height), Image.Resampling.NEAREST)
        
    else:
        raise ValueError(f"不支持的算法: {algorithm}")
    
    return result

def apply_median_filter(array, size):
    """应用中值滤波"""
    height, width = array.shape[:2]
    result = np.zeros_like(array)
    
    for y in range(height):
        for x in range(width):
            # 获取邻域
            y_min = max(0, y - size)
            y_max = min(height, y + size + 1)
            x_min = max(0, x - size)
            x_max = min(width, x + size + 1)
            
            neighborhood = array[y_min:y_max, x_min:x_max]
            result[y, x] = np.median(neighborhood, axis=(0, 1))
    
    return result

def apply_palette(image, palette_name, color_count):
    """应用调色板"""
    if palette_name == 'original':
        return image
    
    # 获取调色板颜色
    palette_colors = get_palette_colors(palette_name, color_count)
    
    if not palette_colors:
        # 如果没有找到调色板，从图片中提取颜色
        palette_colors = extract_colors_from_image(image, color_count)
    
    # 应用调色板
    return quantize_to_palette(image, palette_colors)

def get_palette_colors(palette_name, color_count):
    """获取预设调色板颜色"""
    palettes = {
        'gameboy': [
            (15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)
        ],
        'nes': [
            (84, 84, 84), (0, 30, 116), (8, 16, 144), (48, 0, 136),
            (68, 0, 100), (92, 0, 48), (136, 0, 0), (120, 16, 0),
            (104, 40, 0), (88, 48, 0), (64, 64, 0), (0, 120, 0),
            (8, 104, 0), (0, 88, 0), (0, 64, 88), (0, 0, 0)
        ],
        'c64': [
            (0, 0, 0), (255, 255, 255), (136, 0, 0), (170, 255, 238),
            (204, 68, 204), (0, 204, 85), (170, 68, 0), (102, 102, 0),
            (238, 119, 119), (221, 102, 0), (238, 170, 51), (0, 136, 0),
            (170, 170, 170), (85, 85, 85), (119, 119, 255), (85, 85, 85)
        ],
        'monochrome': [(0, 0, 0), (255, 255, 255)],
        'sepia': [
            (62, 39, 35), (147, 104, 67), (211, 161, 116), 
            (241, 217, 169), (255, 245, 208), (255, 255, 255)
        ],
        'vaporwave': [
            (255, 105, 180), (255, 20, 147), (138, 43, 226), (75, 0, 130),
            (0, 191, 255), (135, 206, 250), (255, 255, 255), (192, 192, 192)
        ]
    }
    
    if palette_name in palettes:
        colors = palettes[palette_name]
        # 如果调色板颜色数量多于需要的，进行采样
        if len(colors) > color_count:
            step = len(colors) / color_count
            colors = [colors[int(i * step)] for i in range(color_count)]
        return colors
    
    return []

def extract_colors_from_image(image, color_count):
    """从图片中提取主要颜色"""
    # 缩小图片以加快处理速度
    small_image = image.resize((100, 100), Image.Resampling.LANCZOS)
    pixels = np.array(small_image).reshape(-1, 3)
    
    # 使用K-means聚类提取主要颜色
    try:
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=color_count, random_state=42, n_init=10)
        kmeans.fit(pixels)
        colors = kmeans.cluster_centers_.astype(int)
        return [tuple(color) for color in colors]
    except ImportError:
        # 如果scikit-learn不可用，使用简单的颜色量化
        return simple_color_quantization(pixels, color_count)

def simple_color_quantization(pixels, color_count):
    """简单的颜色量化算法"""
    # 将颜色空间分成color_count个区域
    colors = []
    step = 256 // int(color_count ** (1/3))
    
    for r in range(0, 256, step):
        for g in range(0, 256, step):
            for b in range(0, 256, step):
                if len(colors) < color_count:
                    colors.append((r, g, b))
    
    return colors[:color_count]

def quantize_to_palette(image, palette_colors):
    """将图片量化到指定调色板"""
    img_array = np.array(image)
    height, width = img_array.shape[:2]
    
    # 创建调色板数组
    palette_array = np.array(palette_colors)
    
    # 对每个像素找到最接近的颜色
    for y in range(height):
        for x in range(width):
            pixel = img_array[y, x]
            
            # 计算与调色板中所有颜色的距离
            distances = np.sum((palette_array - pixel) ** 2, axis=1)
            closest_index = np.argmin(distances)
            
            img_array[y, x] = palette_array[closest_index]
    
    return Image.fromarray(img_array.astype(np.uint8))

def apply_dithering(image, color_count):
    """应用Floyd-Steinberg抖动算法"""
    img_array = np.array(image, dtype=float)
    height, width = img_array.shape[:2]
    
    # 获取调色板（如果需要）
    if color_count < 256:
        # 从图片中提取调色板
        pixels = img_array.reshape(-1, 3)
        try:
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=color_count, random_state=42, n_init=10)
            kmeans.fit(pixels)
            palette = kmeans.cluster_centers_
        except ImportError:
            # 简单的颜色量化
            palette = simple_color_quantization(pixels, color_count)
    else:
        palette = None
    
    for y in range(height):
        for x in range(width):
            old_pixel = img_array[y, x].copy()
            
            # 找到最接近的颜色
            if palette is not None:
                distances = np.sum((palette - old_pixel) ** 2, axis=1)
                new_pixel = palette[np.argmin(distances)]
            else:
                # 简单的量化
                new_pixel = np.round(old_pixel / 255) * 255
            
            img_array[y, x] = new_pixel
            
            # 计算误差
            error = old_pixel - new_pixel
            
            # 扩散误差到邻近像素
            if x + 1 < width:
                img_array[y, x + 1] += error * 7/16
            if y + 1 < height:
                if x > 0:
                    img_array[y + 1, x - 1] += error * 3/16
                img_array[y + 1, x] += error * 5/16
                if x + 1 < width:
                    img_array[y + 1, x + 1] += error * 1/16
    
    return Image.fromarray(img_array.astype(np.uint8))

def apply_edge_smoothing(image, smooth_factor):
    """应用边缘平滑"""
    if smooth_factor <= 0:
        return image
    
    img_array = np.array(image)
    
    # 使用高斯滤波进行平滑
    from scipy.ndimage import gaussian_filter
    
    # 根据平滑因子调整sigma值
    sigma = smooth_factor * 0.5
    
    smoothed = gaussian_filter(img_array, sigma=sigma, mode='nearest')
    
    # 混合原始图像和平滑图像
    alpha = smooth_factor
    result = (1 - alpha) * img_array + alpha * smoothed
    
    return Image.fromarray(result.astype(np.uint8))

def save_image(image, output_path):
    """保存处理后的图片"""
    try:
        # 确保输出目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 保存图片
        image.save(output_path, 'PNG', optimize=True)
    except Exception as e:
        raise ValueError(f"无法保存图片: {str(e)}")

def report_progress(progress_file, progress, message):
    """报告处理进度"""
    if progress_file:
        try:
            progress_data = {
                'progress': progress,
                'message': message,
                'timestamp': time.time()
            }
            with open(progress_file, 'w') as f:
                json.dump(progress_data, f)
        except:
            pass  # 进度报告失败不影响主流程

if __name__ == '__main__':
    main()