#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
像素画生成器主脚本
纯 Python 实现，无 OpenCV，保留 GUI 接口
"""
import sys
import argparse
import json
import time
import numpy as np
from pathlib import Path
from PIL import Image, ImageEnhance, ImageDraw
from typing import Optional, Tuple
from io import BytesIO
from core import PixelArtGenerator, PixelArtConfig
from slic import create_slic_instance  # 保留 GUI 接口


# ---------- 进度 ----------
def report_progress(progress_file: Optional[str], percent: int, msg: str):
    if not progress_file:
        return
    try:
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump({"progress": percent, "message": msg, "timestamp": time.time()}, f)
    except Exception:
        pass


# ---------- 参数验证 ----------
def validate_args(args: argparse.Namespace):
    if not args.pipe_mode:  # 只有在非管道模式下才需要检查输入文件
        if not Path(args.input).exists():
            raise ValueError(f"输入文件不存在: {args.input}")
    for v, low, high, name in [
        (args.pixel_size, 1, 64, "像素大小"),
        (args.color_count, 2, 256, "颜色数量"),
        (args.contrast, 0.1, 3.0, "对比度"),
        (args.brightness, 0.1, 2.0, "亮度"),
        (args.saturation, 0, 2.0, "饱和度"),
        (args.edge_smoothing, 0, 1.0, "边缘平滑"),
        (args.dither_strength, 0, 1.0, "抖动强度"),
    ]:
        if not (low <= v <= high):
            raise ValueError(f"{name}必须在{low}-{high}之间")


# ---------- 图像 IO ----------
def load_image(path: str) -> Image.Image:
    try:
        img = Image.open(path)
        if img.mode != "RGB":
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            else:
                img = img.convert("RGB")
        return img
    except Exception as e:
        raise ValueError(f"加载图像失败: {e}")


def save_image(img: Image.Image, path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


# ---------- 管道模式图像 IO ----------
def load_image_from_stdin() -> Image.Image:
    """从stdin读取图像数据"""
    try:
        # 从stdin读取所有数据
        image_data = sys.stdin.buffer.read()
        # 创建BytesIO对象
        image_stream = BytesIO(image_data)
        # 打开图像
        img = Image.open(image_stream)
        if img.mode != "RGB":
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            else:
                img = img.convert("RGB")
        return img
    except Exception as e:
        raise ValueError(f"从stdin加载图像失败: {e}")


def save_image_to_stdout(img: Image.Image):
    """将图像数据写入stdout"""
    try:
        # 创建BytesIO对象
        output_stream = BytesIO()
        # 保存图像到流
        img.save(output_stream, format="PNG", optimize=True)
        # 获取字节数据
        image_data = output_stream.getvalue()
        # 写入stdout
        sys.stdout.buffer.write(image_data)
        sys.stdout.buffer.flush()
    except Exception as e:
        raise ValueError(f"保存图像到stdout失败: {e}")


# ---------- 基础调整 ----------
def apply_basic_adjustments(img: Image.Image, args: argparse.Namespace) -> Image.Image:
    for enh_name, factor in [
        ("Brightness", args.brightness),
        ("Contrast", args.contrast),
        ("Color", args.saturation),
    ]:
        if factor == 1.0:
            continue
        img = getattr(ImageEnhance, enh_name)(img).enhance(factor)
    return img


# ---------- 新核心处理（无 OpenCV） ----------
def process_with_new_core(img: Image.Image, args: argparse.Namespace) -> Image.Image:
    cfg = PixelArtConfig(
        pixel_size=args.pixel_size,
        color_count=args.color_count,
        dithering_method="floyd_steinberg" if args.dithering else None,
        dithering_strength=args.dither_strength,
        align_grid=True  # 强制栅格对齐以确保像素严格对齐
    )
    gen = PixelArtGenerator(cfg)
    rgb = np.array(img)
    style_map = {"basic": "basic", "average": "quantized", "median": "quantized", "slic": "basic"}
    out_rgb = gen.generate(rgb, style=style_map.get(args.algorithm, "basic"))
    result_img = Image.fromarray(out_rgb)
    
    # 如果启用边缘黑色像素处理，则添加边缘描边
    if getattr(args, 'edge_outline', False):
        # 获取边缘描边参数
        thickness = getattr(args, 'edge_outline_thickness', 3)
        color_str = getattr(args, 'edge_outline_color', "30,30,30")
        color = tuple(map(int, color_str.split(',')))
        out_rgb = add_edge_outline(out_rgb, thickness=thickness, color=color)
        result_img = Image.fromarray(out_rgb)
    
    # 如果启用网格线，则在图像上绘制网格
    if getattr(args, 'show_grid', False):
        result_img = draw_grid_on_image(result_img, args.pixel_size)
    
    return result_img


def draw_grid_on_image(img: Image.Image, pixel_size: int) -> Image.Image:
    """在图像上绘制网格线"""
    # 创建一个可以在上面绘制的图像副本
    grid_img = img.copy()
    draw = ImageDraw.Draw(grid_img)
    
    # 获取图像尺寸
    width, height = img.size
    
    # 在每个像素格子内绘制网格线
    for y in range(0, height, pixel_size):
        for x in range(0, width, pixel_size):
            # 绘制格子的右边线
            draw.line([(x + pixel_size - 1, y), (x + pixel_size - 1, min(y + pixel_size, height))], 
                      fill=(255, 255, 255, 128), width=1)
            # 绘制格子的下边线
            draw.line([(x, y + pixel_size - 1), (min(x + pixel_size, width), y + pixel_size - 1)], 
                      fill=(255, 255, 255, 128), width=1)
    
    return grid_img


def add_edge_outline(img: np.ndarray, thickness: int = 3, color: Tuple[int, int, int] = (30, 30, 30)) -> np.ndarray:
    """
    一键描黑 + 硬边
    thickness: 描黑厚度（像素）
    color: 描黑颜色（默认深灰）
    """
    h, w = img.shape[:2]

    # ① 改进的硬边掩膜（使用更细的网格以减少整块感）
    step = 8  # 减小步长以获得更细致的掩膜
    h_grid, w_grid = h // step, w // step
    mask = np.zeros((h, w), dtype=np.uint8)
    
    # 添加亚像素偏移以减少过于整齐的网格感
    for gy in range(h_grid):
        for gx in range(w_grid):
            y0, x0 = gy * step, gx * step
            # 添加随机偏移（±1像素）以减少网格的机械感
            y_offset = np.random.randint(-1, 2) if gy > 0 and gy < h_grid - 1 else 0
            x_offset = np.random.randint(-1, 2) if gx > 0 and gx < w_grid - 1 else 0
            
            y1 = min(h, max(0, y0 + y_offset))
            x1 = min(w, max(0, x0 + x_offset))
            y2 = min(h, max(0, y0 + step + y_offset))
            x2 = min(w, max(0, x0 + step + x_offset))
            
            mask[y1:y2, x1:x2] = 1  # 硬边掩膜

    # ② 描黑（厚度 = thickness）
    # 使用numpy操作替代cv2.dilate
    outline = np.zeros_like(mask)
    for i in range(thickness):
        # 上下左右扩展
        if i < h-1:
            outline[i+1:, :] = np.maximum(outline[i+1:, :], mask[:-i-1, :])
        if i < h-1:
            outline[:-i-1, :] = np.maximum(outline[:-i-1, :], mask[i+1:, :])
        if i < w-1:
            outline[:, i+1:] = np.maximum(outline[:, i+1:], mask[:, :-i-1])
        if i < w-1:
            outline[:, :-i-1] = np.maximum(outline[:, :-i-1], mask[:, i+1:])
    
    # 只描边，不包括原始区域
    outline = outline - mask
    outline_rgb = np.zeros_like(img)
    outline_rgb[outline > 0] = color

    # ③ 硬边描黑（硬边 + 原图）
    out = img.copy()
    out[outline > 0] = outline_rgb[outline > 0]
    return out.astype(np.uint8)


# ---------- 保留 GUI 接口 ----------
def create_slic_instance(image_array: np.ndarray, width: int, height: int):
    from slic import SLIC
    return SLIC(image_array, width, height)


# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="像素画生成工具")
    parser.add_argument("--input", help="输入图片路径")
    parser.add_argument("--output", help="输出图片路径")
    parser.add_argument("--pipe-mode", action="store_true", help="启用管道模式")
    parser.add_argument("--pixel-size", type=int, default=16, help="像素块大小 (4-64)")
    parser.add_argument("--color-count", type=int, default=32, help="颜色数量 (2-256)")
    parser.add_argument("--palette", default="default", help="调色板名称")
    parser.add_argument("--algorithm", default="basic", help="像素化算法")
    parser.add_argument("--dithering", action="store_true", help="启用抖动")
    parser.add_argument("--edge-smoothing", type=float, default=0.5, help="边缘平滑 (0-1)")
    parser.add_argument("--contrast", type=float, default=1.0, help="对比度 (0.1-3.0)")
    parser.add_argument("--brightness", type=float, default=1.0, help="亮度 (0.1-2.0)")
    parser.add_argument("--saturation", type=float, default=1.0, help="饱和度 (0-2.0)")
    parser.add_argument("--progress-file", help="进度报告文件")
    parser.add_argument("--dither-strength", type=float, default=0.1, help="抖动强度 (0-1)")
    parser.add_argument("--cartoon-effect", action="store_true", help="卡通效果")
    parser.add_argument("--slic-iters", type=int, default=10, help="SLIC迭代次数")
    parser.add_argument("--slic-weight", type=float, default=10.0, help="SLIC颜色权重")
    parser.add_argument("--show-grid", action="store_true", help="在图像上显示网格线")
    parser.add_argument("--edge-outline", action="store_true", help="在图像上添加边缘黑色像素描边")
    parser.add_argument("--edge-outline-thickness", type=int, default=3, help="边缘描边厚度 (像素)")
    parser.add_argument("--edge-outline-color", default="30,30,30", help="边缘描边颜色 (R,G,B)")

    args = parser.parse_args()
    validate_args(args)

    start = time.time()
    report_progress(args.progress_file, 5, "开始处理...")

    # 根据模式加载图像
    if args.pipe_mode:
        img = load_image_from_stdin()
        report_progress(args.progress_file, 15, "图像加载完成")
    else:
        img = load_image(args.input)
        report_progress(args.progress_file, 15, "图像加载完成")
    
    img = apply_basic_adjustments(img, args)
    report_progress(args.progress_file, 25, "基础调整完成")

    result = process_with_new_core(img, args)
    report_progress(args.progress_file, 90, "像素画生成完成")

    # 根据模式保存图像
    if args.pipe_mode:
        save_image_to_stdout(result)
    else:
        save_image(result, args.output)
        
    elapsed = time.time() - start
    report_progress(args.progress_file, 100, f"处理完成 (耗时: {elapsed:.2f}秒)")

    print(f"SUCCESS:{'PIPE_MODE' if args.pipe_mode else args.output}")
    print(f"TIME:{elapsed:.2f}")


if __name__ == "__main__":
    main()