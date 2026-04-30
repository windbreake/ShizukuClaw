#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SLIC 超像素分割 - 纯 Python 实现
保留原类接口，供 .NET GUI 直接实例化
"""
import numpy as np
from core import rgb_to_lab_numba as rgb_to_lab   # 使用纯 Python LAB


def slic_superpixel_rgb(image_bgr: np.ndarray, step: int = 10, iters: int = 5, weight: float = 10.0) -> np.ndarray:
    """纯 Python SLIC，输入 BGR，输出 BGR"""
    h, w = image_bgr.shape[:2]
    lab = rgb_to_lab(image_bgr)
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
            centers.append({"x": ci, "y": cj,
                            "l": lab[ci, cj, 0], "a": lab[ci, cj, 1], "b": lab[ci, cj, 2],
                            "count": 0})

    labels = np.full((h, w), -1, dtype=np.int32)
    dists = np.full((h, w), np.inf, dtype=np.float32)

    for itr in range(iters):
        for k, c in enumerate(centers):
            cx, cy = int(c["x"]), int(c["y"])
            x0, x1 = max(0, cx - step), min(h, cx + step)
            y0, y1 = max(0, cy - step), min(w, cy + step)
            for x in range(x0, x1):
                for y in range(y0, y1):
                    dc = np.sqrt(np.sum((lab[x, y] - np.array([c["l"], c["a"], c["b"]])) ** 2))
                    ds = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    d = (dc / weight) ** 2 + (ds / step) ** 2
                    if d < dists[x, y]:
                        dists[x, y], labels[x, y] = d, k

        for c in centers:
            c["count"] = c["l"] = c["a"] = c["b"] = c["x"] = c["y"] = 0
        for x in range(h):
            for y in range(w):
                k = labels[x, y]
                if k != -1:
                    centers[k]["l"] += lab[x, y, 0]
                    centers[k]["a"] += lab[x, y, 1]
                    centers[k]["b"] += lab[x, y, 2]
                    centers[k]["x"] += x
                    centers[k]["y"] += y
                    centers[k]["count"] += 1
        for c in centers:
            if c["count"] > 0:
                c["l"] /= c["count"]
                c["a"] /= c["count"]
                c["b"] /= c["count"]
                c["x"] = int(c["x"] / c["count"])
                c["y"] = int(c["y"] / c["count"])

    out = image_bgr.copy()
    for x in range(h):
        for y in range(w):
            k = labels[x, y]
            if k != -1:
                cx, cy = centers[k]["x"], centers[k]["y"]
                out[x, y] = image_bgr[cx, cy]
    return out


def create_slic_instance(image_array: np.ndarray, width: int, height: int):
    return SLIC(image_array, width, height)


# ---------- 保留原类接口（供 .NET GUI ） ----------
class SLIC:
    def __init__(self, image_array: np.ndarray, width: int, height: int):
        self.image_bgr = image_array[:, :, :3]

    def pixel_deal(self, step: int, iters: int, stride: int, weight: float) -> np.ndarray:
        return slic_superpixel_rgb(self.image_bgr, step=step, iters=iters, weight=weight)