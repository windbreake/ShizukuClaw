"""
纯 Python 像素画处理核心
对外唯一入口：process_image_internal
"""
import io
from PIL import Image
import numpy as np
from core import PixelArtGenerator, PixelArtConfig

def _pil_to_rgb(pil_img: Image.Image) -> np.ndarray:
    return np.array(pil_img.convert("RGB"))

def _rgb_to_pil(rgb: np.ndarray) -> Image.Image:
    return Image.fromarray(rgb, "RGB")

def process_image_internal(image_bytes: bytes, options: dict) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    rgb = _pil_to_rgb(img)

    cfg = PixelArtConfig(
        pixel_size=options["block_size"],
        color_count=options["max_colors"],
        dithering_method="floyd_steinberg" if options.get("enable_dither") else None,
        dithering_strength=options.get("dither_strength", 0.1),
    )
    gen = PixelArtGenerator(cfg)
    style_map = {"basic": "basic", "average": "quantized", "median": "quantized", "slic": "basic"}
    out_rgb = gen.generate(rgb, style=style_map.get(options.get("algorithm", "basic"), "basic"))

    out_pil = _rgb_to_pil(out_rgb)
    buf = io.BytesIO()
    out_pil.save(buf, format="PNG", optimize=True)
    return buf.getvalue()