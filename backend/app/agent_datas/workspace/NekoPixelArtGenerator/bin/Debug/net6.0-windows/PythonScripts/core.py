"""
Numba 加速版 SLIC + 颜色量化 + 抖动
无 OpenCV，纯 NumPy + PIL + Numba
"""
from PIL import Image
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from sklearn.cluster import MiniBatchKMeans

@dataclass
class PixelArtConfig:
    pixel_size: int = 16
    color_count: int = 32
    dithering_method: Optional[str] = None
    dithering_strength: float = 0.5
    # ↓ 一键扩展（已开放）
    compactness: float = 10.0          # SLIC 紧凑度
    edge_harden: float = 0.0           # 边缘硬化强度
    align_grid: bool = False           # 栅格对齐
    quantize_space: str = "RGB"        # 颜色空间


# ---------- 颜色空间 ----------
# Apply njit decorator only if numba is available
njit_decorator = njit if 'numba' in globals() else lambda x: x

@njit_decorator
def rgb_to_lab_numba(img: np.ndarray) -> np.ndarray:
    def gamma(c):
        return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

    r, g, b = gamma(img[..., 0] / 255.0), gamma(img[..., 1] / 255.0), gamma(img[..., 2] / 255.0)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    x, y, z = x / 0.95047, y / 1.0, z / 1.08883

    def f(t):
        return np.where(t > 0.008856, t ** (1 / 3), (7.787 * t) + 16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    l = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)

    lab = np.empty((l.shape[0], l.shape[1], 3), dtype=np.float64)
    lab[:, :, 0] = l
    lab[:, :, 1] = a
    lab[:, :, 2] = b
    return lab

def _rgb_to_lab_numpy(img: np.ndarray) -> np.ndarray:
    def gamma(c):
        return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

    r, g, b = gamma(img[..., 0] / 255.0), gamma(img[..., 1] / 255.0), gamma(img[..., 2] / 255.0)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    x, y, z = x / 0.95047, y / 1.0, z / 1.08883

    def f(t):
        return np.where(t > 0.008856, t ** (1 / 3), (7.787 * t) + 16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    l = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)

    lab = np.empty((l.shape[0], l.shape[1], 3), dtype=np.float64)
    lab[:, :, 0] = l
    lab[:, :, 1] = a
    lab[:, :, 2] = b
    return lab


# 定义njit和prange的替代实现
try:
    from numba import njit, prange
except ImportError:
    # njit的简单替代实现
    def njit(func=None, *args, **kwargs):
        if func is None:
            # 如果作为装饰器使用带参数
            def wrapper(f):
                return f
            return wrapper
        else:
            # 如果作为装饰器直接使用
            return func
    
    # prange的简单替代实现
    def prange(*args):
        return range(*args)

# ---------- Numba 加速 SLIC ----------
class SLICPixelArtCore:
    def __init__(self, cfg: PixelArtConfig):
        self.cfg = cfg
        self.labels = None
        self.centers = []

    def initialize_centers(self, lab: np.ndarray) -> np.ndarray:
        h, w = lab.shape[:2]
        step = self.cfg.pixel_size
        centers = []
        for i in range(step // 2, h, step):
            for j in range(step // 2, w, step):
                min_grad, best = np.inf, (i, j)
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        ni, nj = i + di, j + dj
                        if 0 <= ni < h and 0 <= nj < w and ni + 1 < h and nj + 1 < w:
                            grad = (np.sum(np.abs(lab[ni + 1, nj] - lab[ni - 1, nj])) +
                                    np.sum(np.abs(lab[ni, nj + 1] - lab[ni, nj - 1])))
                            if grad < min_grad:
                                min_grad, best = grad, (ni, nj)
                ci, cj = best
                centers.append([float(ci), float(cj), lab[ci, cj, 0], lab[ci, cj, 1], lab[ci, cj, 2]])
        return np.array(centers)

    def slic_superpixel(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        # Use the numpy version when numba is not available
        lab = rgb_to_lab_numba(img) if hasattr(rgb_to_lab_numba, '__compiled__') else _rgb_to_lab_numpy(img)
        step = self.cfg.pixel_size
        centers = self.initialize_centers(lab)
        n_cent = len(centers)
        labels = np.full((h, w), 0, dtype=np.int32)  # ← 非 -1，防止全黑
        dists = np.full((h, w), np.inf, dtype=np.float32)

        yy, xx = np.mgrid[0:h, 0:w]
        lab_flat = lab.reshape(-1, 3)
        yy_flat = yy.ravel()
        xx_flat = xx.ravel()
        labels_flat = labels.ravel()
        dists_flat = dists.ravel()

        for itr in range(10):
            for k in range(n_cent):
                cx, cy = int(centers[k, 0]), int(centers[k, 1])
                x0, x1 = max(0, cx - step), min(h, cx + step)
                y0, y1 = max(0, cy - step), min(w, cy + step)
                h_sub, w_sub = x1 - x0, y1 - y0

                sub_idx = np.arange(x0, x1)[:, None] * w + np.arange(y0, y1)[None, :]
                sub_idx = sub_idx.ravel()

                sub_lab = lab[x0:x1, y0:y1]
                sub_xx = xx[x0:x1, y0:y1]
                sub_yy = yy[x0:x1, y0:y1]

                dc = np.sum((sub_lab - centers[k, 2:5]) ** 2, axis=2)
                ds = (sub_xx - cx) ** 2 + (sub_yy - cy) ** 2
                d_flat = (dc / (step ** 2) + ds / (step ** 2)).ravel()

                sub_d_flat = dists_flat[sub_idx]
                mask_flat = d_flat < sub_d_flat
                sub_d_flat[mask_flat] = d_flat[mask_flat]
                dists_flat[sub_idx] = sub_d_flat
                labels_flat[sub_idx[mask_flat]] = k

            # 一次性向量化中心更新
            new_cent = np.zeros((n_cent, 5))
            counts = np.bincount(labels_flat, minlength=n_cent)
            new_cent[:, 0] = np.bincount(labels_flat, weights=xx_flat, minlength=n_cent)
            new_cent[:, 1] = np.bincount(labels_flat, weights=yy_flat, minlength=n_cent)
            new_cent[:, 2] = np.bincount(labels_flat, weights=lab_flat[:, 0], minlength=n_cent)
            new_cent[:, 3] = np.bincount(labels_flat, weights=lab_flat[:, 1], minlength=n_cent)
            new_cent[:, 4] = np.bincount(labels_flat, weights=lab_flat[:, 2], minlength=n_cent)
            counts = np.maximum(counts, 1)
            new_cent /= counts.reshape(-1, 1)
            centers = new_cent

            # Early-Stop（可选）
            if np.max(np.abs(new_cent - centers)) < 0.5:
                break

        self.labels, self.centers = labels, centers
        # 向量化像素画（无逐 mask 循环）
        out = np.zeros_like(img)
        counts = np.bincount(labels.ravel(), minlength=n_cent)
        for c in range(3):
            channel_mean = np.bincount(labels.ravel(), weights=img[..., c].ravel(), minlength=n_cent)
            channel_mean /= np.maximum(counts, 1)
            out[..., c] = channel_mean[labels].astype(np.uint8)
        return out

    def generate_pixel_art(self, img: np.ndarray) -> np.ndarray:
        # ① 先跑分割（若未跑）
        if self.labels is None:
            self.slic_superpixel(img)

        h, w = img.shape[:2]
        labels = self.labels
        n_cent = len(self.centers)

        # ② 强制 16×16 栅格对齐（零填充到可被 step 整除）
        if self.cfg.align_grid:
            step = self.cfg.pixel_size
            # 零填充到可被 step 整除
            h_pad = (step - h % step) % step
            w_pad = (step - w % step) % step
            img_pad = np.pad(img, ((0, h_pad), (0, w_pad), (0, 0)), mode='constant', constant_values=0)
            h_pad, w_pad = img_pad.shape[0], img_pad.shape[1]

            h_grid, w_grid = h_pad // step, w_pad // step
            grid_rgb = img_pad.reshape(h_grid, step, w_grid, step, 3).mean(axis=(1, 3))  # H_grid×W_grid×3
            grid_rgb = grid_rgb.reshape(-1, 3)  # H_grid*W_grid×3

            # 回填到原图（零填充部分也保存）
            out = np.zeros_like(img)  # 原图大小
            for g in range(h_grid * w_grid):
                y0, x0 = (g // w_grid) * step, (g % w_grid) * step
                out[y0:y0 + step, x0:x0 + step] = grid_rgb[g]
            return out.astype(np.uint8)

        # ③ 非对齐模式（原向量化）
        counts = np.bincount(labels.ravel(), minlength=n_cent)
        lab_flat = img.reshape(-1, 3)
        mean_rgb = np.zeros((n_cent, 3), dtype=np.float32)
        for c in range(3):
            mean_rgb[:, c] = np.bincount(labels.ravel(), weights=lab_flat[:, c], minlength=n_cent)
        mean_rgb /= np.maximum(counts, 1)[:, None]
        out = mean_rgb[labels].astype(np.uint8)
        return out


# ---------- 颜色量化 ----------
class ColorQuantization:
    def quantize_kmeans(self, img: np.ndarray, n: int) -> np.ndarray:
        pts = img.reshape(-1, 3)
        model = MiniBatchKMeans(n_clusters=n, batch_size=4096, random_state=42)
        labels = model.fit_predict(pts)
        return model.cluster_centers_[labels].reshape(img.shape).astype(np.uint8)


# ---------- 抖动 ----------
class Dithering:
    _patterns = {
        "floyd_steinberg": np.array([[0, 0, 7], [3, 5, 1]], dtype=np.float32) / 16.0,
        "atkinson": np.array([[0, 1, 1], [1, 1, 1], [0, 1, 0]], dtype=np.float32) / 8.0,
    }

    def apply_dithering(self, img: np.ndarray, method: str = "floyd_steinberg", bit_depth: int = 1) -> np.ndarray:
        if method not in self._patterns:
            method = "floyd_steinberg"
        pattern = self._patterns[method]
        if img.ndim == 3:
            return np.stack(
                [self._dither_channel(ch.astype(np.float32), pattern, bit_depth) for ch in np.moveaxis(img, -1, 0)],
                axis=-1)
        else:
            return self._dither_channel(img.astype(np.float32), pattern, bit_depth)

    @njit_decorator
    def _dither_channel(self, ch: np.ndarray, pattern: np.ndarray, bit_depth: int) -> np.ndarray:
        h, w = ch.shape
        levels = 2 ** bit_depth
        scale = 255 / (levels - 1)
        for y in range(h - 2):
            for x in range(1, w - 1):
                old = ch[y, x]
                new = np.round(old / scale) * scale
                ch[y, x] = new
                err = old - new
                for dy in range(pattern.shape[0]):
                    for dx in range(pattern.shape[1]):
                        if pattern[dy, dx] > 0:
                            ny, nx = y + dy, x + (dx - 1)
                            if 0 <= ny < h and 0 <= nx < w:
                                ch[ny, nx] += err * pattern[dy, dx]
        return np.clip(ch, 0, 255).astype(np.uint8)


# ---------- 调色板 ----------
class ColorMapping:
    _palettes = {
        "gameboy": np.array([[155, 188, 15], [139, 172, 15], [48, 98, 48], [15, 56, 15]], dtype=np.uint8),
        "c64": np.array([[0, 0, 0], [255, 255, 255], [136, 0, 0], [170, 255, 238],
                         [204, 68, 204], [0, 204, 85], [0, 0, 170], [238, 238, 119],
                         [221, 136, 85], [102, 68, 0], [255, 119, 119], [51, 51, 51],
                         [119, 119, 119], [170, 255, 102], [0, 136, 255], [187, 187, 187]], dtype=np.uint8),
        "mono": np.array([[i, i, i] for i in range(0, 256, 16)], dtype=np.uint8),
    }

    def create_retro_palette(self, name: str = "gameboy") -> np.ndarray:
        return self._palettes.get(name, self._palettes["gameboy"])

    def apply_palette(self, img: np.ndarray, palette: np.ndarray) -> np.ndarray:
        pts = img.reshape(-1, 3)
        diff = ((pts[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
        idx = diff.argmin(axis=1)
        return palette[idx].reshape(img.shape)


# ---------- 生成器 ----------
class PixelArtGenerator:
    def __init__(self, cfg: PixelArtConfig):
        self.cfg = cfg
        self.slic = SLICPixelArtCore(cfg)
        self.quant = ColorQuantization()
        self.dith = Dithering()
        self.mapper = ColorMapping()

    def generate(self, img: np.ndarray, style: str = "basic") -> np.ndarray:
        handlers = {
            "basic": self._basic,
            "quantized": self._quantized,
            "dithered": self._dithered,
            "retro": self._retro,
            "monochrome": self._mono,
        }
        return handlers.get(style, handlers["basic"])(img)

    def _basic(self, img: np.ndarray) -> np.ndarray:
        return self.slic.generate_pixel_art(img)

    def _quantized(self, img: np.ndarray) -> np.ndarray:
        base = self._basic(img)
        return self.quant.quantize_kmeans(base, self.cfg.color_count)

    def _dithered(self, img: np.ndarray) -> np.ndarray:
        base = self._basic(img)
        quant = self.quant.quantize_kmeans(base, self.cfg.color_count)
        if not self.cfg.dithering_method:
            return quant
        dith = self.dith.apply_dithering(quant, self.cfg.dithering_method, 1)
        return np.clip(quant * (1 - self.cfg.dithering_strength) + dith * self.cfg.dithering_strength, 0, 255).astype(
            np.uint8)

    def _retro(self, img: np.ndarray) -> np.ndarray:
        base = self._basic(img)
        pal = self.mapper.create_retro_palette("gameboy")
        return self.mapper.apply_palette(base, pal)

    def _mono(self, img: np.ndarray) -> np.ndarray:
        base = self._basic(img)
        pal = self.mapper.create_retro_palette("mono")[::256 // self.cfg.color_count]
        return self.mapper.apply_palette(base, pal)

    def create_comparison(self, img: np.ndarray) -> np.ndarray:
        styles = ["basic", "quantized", "dithered", "retro", "monochrome"]
        imgs = [self.generate(img, s) for s in styles]
        return self._grid(imgs, styles)

    def _grid(self, imgs: list, titles: list, cols: int = 3) -> np.ndarray:
        rows = (len(imgs) + cols - 1) // cols
        h, w = imgs[0].shape[:2]
        grid = np.zeros((rows * (h + 30), cols * w, 3), dtype=np.uint8)
        for i, (img, title) in enumerate(zip(imgs, titles)):
            r, c = i // cols, i % cols
            y0, x0 = r * (h + 30), c * w
            grid[y0 + 30: y0 + 30 + h, x0: x0 + w] = img
            # 文字占位（无 cv2，可后期叠加）
        return grid
