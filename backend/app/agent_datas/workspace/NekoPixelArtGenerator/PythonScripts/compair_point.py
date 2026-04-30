from PIL import Image
import numpy as np
from core import PixelArtConfig, PixelArtGenerator

def compare(param: dict, name: str):
    rgb = np.array(Image.open(r"C:\Users\win11\Pictures\win11.jpg").convert("RGB"))
    cfg = PixelArtConfig(**param)
    gen = PixelArtGenerator(cfg)
    out = gen.generate(rgb, style="basic")
    print(f"[DEBUG] 保存前：min={out.min()} max={out.shape} shape={out.shape}")
    Image.fromarray(out).save(f"perfect_{name}.png")
    print(f"[DEBUG] 已保存：perfect_{name}.png")

# ① 超高密度 + 高精度（1×1 栅格 + 256 色）
compare({
    "pixel_size": 1,              # 1×1 栅格（超高密度）
    "color_count": 256,           # 256 级灰度（精度 ×8）
    "compactness": 40.0,          # 色块方正
    "edge_harden": 1.0,           # 硬边
    "align_grid": True,           # 完美 1×1 对齐
    "quantize_space": "LAB"       # 感知量化
}, "extreme_density")

# ① 默认（可能歪斜）
compare({"pixel_size": 16, "color_count": 32}, "default")

# ② 紧凑度修复（方正）
compare({"pixel_size": 16, "color_count": 32, "compactness": 20.0}, "compact")

# ③ 边缘硬化 + 栅格对齐
compare({"pixel_size": 16, "color_count": 32, "compactness": 20.0, "edge_harden": 1.0, "align_grid": True}, "harden")

# ④ 感知量化
compare({"pixel_size": 16, "color_count": 32, "compactness": 20.0, "edge_harden": 1.0, "align_grid": True,
         "quantize_space": "LAB"}, "percept")
