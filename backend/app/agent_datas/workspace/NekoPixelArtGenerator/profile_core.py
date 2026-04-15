#!/usr/bin/env python3
"""core.py 性能热点定位器（无外部依赖）"""
import time
import tracemalloc
from PIL import Image
import numpy as np
from PythonScripts.core import PixelArtGenerator, PixelArtConfig   # 你的最新 core.py

def profile_once(pixel_size: int):
    # 创建测试图像
    test_image = Image.new('RGB', (200, 200), color='red')
    from PIL import ImageDraw
    draw = ImageDraw.Draw(test_image)
    draw.rectangle([50, 50, 150, 150], fill='blue')
    draw.ellipse([75, 75, 125, 125], fill='green')
    
    rgb = np.array(test_image)
    cfg = PixelArtConfig(pixel_size=pixel_size, color_count=16, dithering_method="floyd_steinberg")
    gen = PixelArtGenerator(cfg)

    tracemalloc.start()
    t0 = time.perf_counter()
    out = gen.generate(rgb, style="basic")           # 只测 SLIC 部分
    t1 = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"pixel_size={pixel_size:2d} | 耗时={t1-t0:.3f}s | 峰值内存={peak/1024/1024:.1f}MB")

if __name__ == "__main__":
    print("开始性能分析...")
    for sz in [8, 16, 32, 64]:
        profile_once(sz)