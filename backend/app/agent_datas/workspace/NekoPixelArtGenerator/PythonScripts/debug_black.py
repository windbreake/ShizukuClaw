from PIL import Image
import numpy as np
from core import PixelArtGenerator, PixelArtConfig

rgb = np.array(Image.open(r"C:\Users\win11\Pictures\baka.png").convert("RGB"))
print("原图范围:", rgb.min(), rgb.max())

cfg = PixelArtConfig(pixel_size=16, color_count=32)
gen = PixelArtGenerator(cfg)

# ① 先跑分割（已修复）
labels = gen.slic.slic_superpixel(rgb)   # 现在会赋值 self.labels
print("labels 范围:", labels.min(), labels.max(), "unique=", np.unique(labels).size)

# ② 生成像素画（已修复）
out_rgb = gen.generate(rgb, style="basic")
print("结果范围:", out_rgb.min(), out_rgb.max())

Image.fromarray(out_rgb).save("debug_result.png")
print("已保存：debug_result.png")