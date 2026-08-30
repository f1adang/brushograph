#!/usr/bin/python3
"""Photo -> rough woodcut / linocut black and white.

The pipeline downstream traces black regions with potrace and fills them with a
brush, so the output has to be bold and solid: no grey, no dither, and no
feature finer than the brush can lay down. Everything here works toward that
rather than toward photographic fidelity.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

# Working resolution. Big enough to keep carved edges crisp, small enough that
# the filtering stays quick; the result is traced to vectors afterwards anyway.
MAX_SIDE = 1400


def _odd(n: int, lo: int = 1) -> int:
    n = max(lo, int(n))
    return n if n % 2 else n + 1


def convert(
    image: Image.Image,
    simplify: float = 60.0,    # 0-100: how much detail is flattened away
    threshold: float = 12.0,   # -50..50: bias toward more white / more black
    roughness: float = 45.0,   # 0-100: how irregular the carved edges look
    outlines: bool = True,     # keep dark edges as linocut-style contour lines
) -> Image.Image:
    """Return a 1-bit image: black where the brush should paint."""
    simplify = float(np.clip(simplify, 0, 100))
    threshold = float(np.clip(threshold, -50, 50))
    roughness = float(np.clip(roughness, 0, 100))

    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, MAX_SIDE / max(h, w))
    if scale < 1.0:
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    short_side = min(gray.shape)

    # Local contrast first: a woodcut reads as shapes, and CLAHE pulls shapes
    # out of flat lighting before anything is thrown away.
    gray = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)

    # Edge-preserving smoothing collapses texture into flat regions while
    # keeping the boundaries a carver would follow. Strength tracks image size
    # so the look does not change with resolution.
    d = _odd(short_side * (0.004 + 0.020 * simplify / 100), 3)
    flat = cv2.bilateralFilter(gray, d=min(d, 25), sigmaColor=45 + simplify, sigmaSpace=d)
    for _ in range(1 + int(simplify // 40)):
        flat = cv2.bilateralFilter(flat, d=min(d, 25), sigmaColor=45 + simplify, sigmaSpace=d)

    # Carved edges wobble. Perturbing the tone with smooth low-frequency noise
    # before the cut makes the boundary irregular, which is what separates a
    # woodcut from a plain threshold.
    if roughness > 0:
        rng = np.random.default_rng(7)   # fixed: same photo gives the same print
        small = rng.normal(0, 1, (max(2, gray.shape[0] // 24), max(2, gray.shape[1] // 24)))
        noise = cv2.resize(small.astype(np.float32), flat.shape[::-1], interpolation=cv2.INTER_CUBIC)
        noise = cv2.GaussianBlur(noise, (0, 0), sigmaX=max(1.0, short_side / 400))
        rng_amp = 26.0 * roughness / 100
        peak = float(np.abs(noise).max()) or 1.0
        flat = np.clip(flat.astype(np.float32) + noise / peak * rng_amp, 0, 255).astype(np.uint8)

    # Otsu finds the natural split between ink and paper; the bias shifts it.
    level, _ = cv2.threshold(flat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    level = float(np.clip(level - threshold * 2.2, 5, 250))
    ink = flat < level

    if outlines:
        # Dark contours, thickened, read as the knife lines around a shape.
        edges = cv2.Canny(cv2.GaussianBlur(flat, (0, 0), 1.2), 40, 110) > 0
        thickness = _odd(short_side * 0.004 * (0.5 + simplify / 100), 3)
        edges = cv2.dilate(edges.astype(np.uint8), np.ones((thickness, thickness), np.uint8)) > 0
        ink |= edges

    # Clean up so every remaining shape is something a brush can actually paint:
    # close pinholes, then drop specks. Kernel grows with `simplify`.
    k = _odd(short_side * (0.004 + 0.012 * simplify / 100), 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    solid = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    solid = cv2.morphologyEx(solid, cv2.MORPH_OPEN, kernel)

    solid = _drop_specks(solid, min_area=(short_side * (0.006 + 0.014 * simplify / 100)) ** 2)

    out = np.where(solid > 0, 0, 255).astype(np.uint8)   # black = paint
    return Image.fromarray(out, "L").convert("1")


def _drop_specks(mask: np.ndarray, min_area: float) -> np.ndarray:
    """Remove islands and pinholes smaller than the brush can render."""
    min_area = max(4.0, min_area)
    for value in (1, 0):
        target = (mask == value).astype(np.uint8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(target, connectivity=8)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < min_area:
                mask[labels == i] = 1 - value
    return mask


def ink_fraction(img: Image.Image) -> float:
    a = np.asarray(img.convert("L"))
    return float((a < 128).mean())
