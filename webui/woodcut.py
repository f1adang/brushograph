#!/usr/bin/python3
"""Photo -> woodcut / linocut black and white.

The pipeline downstream traces black regions with potrace and fills them with a
brush, so the output must be pure two-tone with nothing finer than the brush can
lay down. Detail therefore cannot come from grey: it comes the way it does in a
real cut, from carved hatching whose density carries the tone. That also suits
the machine, since hatching is long parallel strokes.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

MAX_SIDE = 1600


def _odd(n, lo: int = 1) -> int:
    n = max(lo, int(n))
    return n if n % 2 else n + 1


def convert(
    image: Image.Image,
    detail: float = 78.0,       # 0-100: how much fine structure survives
    threshold: float = 8.0,     # -50..50: bias toward more white / more black
    roughness: float = 40.0,    # 0-100: how irregular the carved edges look
    outlines: bool = True,      # keep dark contours as knife lines
    hatching: float = 70.0,     # 0-100: how much midtone is carried by hatching
    min_feature_px: float = 3.0,  # thinnest mark the brush can actually paint
    mask: np.ndarray | None = None,  # optional subject mask; outside becomes paper
) -> Image.Image:
    """Return a 1-bit image: black where the brush should paint."""
    detail = float(np.clip(detail, 0, 100))
    threshold = float(np.clip(threshold, -50, 50))
    roughness = float(np.clip(roughness, 0, 100))
    hatching = float(np.clip(hatching, 0, 100))

    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, MAX_SIDE / max(h, w))
    if scale < 1.0:
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        if mask is not None:
            mask = cv2.resize(mask, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    short_side = min(gray.shape)
    min_feature = max(1.0, float(min_feature_px))

    gray = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8)).apply(gray)

    # Smoothing is now light: it exists to stop sensor noise becoming marks, not
    # to flatten the picture. More detail means less of it.
    d = _odd(short_side * (0.014 - 0.0125 * detail / 100), 3)
    tone = cv2.bilateralFilter(gray, d=min(d, 15), sigmaColor=95 - 0.65 * detail, sigmaSpace=d)

    if roughness > 0:
        tone = _roughen(tone, roughness, short_side)

    # Three bands, cut at percentiles of this image's own tones rather than at
    # a fixed level. Otsu splits ink from paper, which is the wrong question
    # here: what matters is how much of the picture becomes solid black, how
    # much becomes hatching and how much is left as paper, and that should hold
    # steady whether the photograph is bright or dim.
    sample = tone[mask > 0] if mask is not None and (mask > 0).any() else tone
    solid_pct = float(np.clip(17.0 - threshold * 0.55, 1.5, 60.0))
    paper_pct = float(np.clip(58.0 - threshold * 0.85, 12.0, 96.0))
    solid_at = float(np.percentile(sample, solid_pct))
    paper_at = float(np.percentile(sample, max(paper_pct, solid_pct + 4)))

    ink = tone < solid_at

    if hatching > 0:
        ink |= _hatch(tone, solid_at, paper_at, hatching, min_feature)

    if outlines:
        ink |= _contours(tone, gray, detail, min_feature)

    solid = ink.astype(np.uint8)
    # Only a light close, and never an open: an open with a kernel wider than a
    # hatch line would erase the hatching that carries the tone.
    k = _odd(max(2.0, min_feature * 0.9), 3)
    solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    solid = _drop_specks(solid, min_area=(min_feature * 1.25) ** 2)

    if mask is not None:
        solid = np.where(mask > 0, solid, 0).astype(np.uint8)

    return Image.fromarray(np.where(solid > 0, 0, 255).astype(np.uint8), "L").convert("1")


def _contours(tone: np.ndarray, gray: np.ndarray, detail: float, min_feature: float) -> np.ndarray:
    """Knife lines along real boundaries, not along texture.

    Canny fires on grass and cloud as readily as on a jawline. Short fragments
    are therefore discarded before the lines are thickened: what is left is the
    contours a carver would actually cut, and the speckle that would otherwise
    become hundreds of unpaintable dabs is gone.
    """
    lo = int(64 - 34 * detail / 100)
    edges = cv2.Canny(cv2.GaussianBlur(tone, (0, 0), 1.1), lo, int(lo * 2.6)) > 0
    if detail > 55:
        edges |= cv2.Canny(cv2.GaussianBlur(gray, (0, 0), 0.7), lo + 30, int((lo + 30) * 2.8)) > 0

    min_run = max(4.0, min_feature * (4.6 - 2.6 * detail / 100))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(edges.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    for i in range(1, n):
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if max(w_, h_) >= min_run and stats[i, cv2.CC_STAT_AREA] >= min_feature:
            keep[i] = True
    edges = keep[labels]

    thickness = _odd(max(min_feature, 1.0), 1)
    if thickness > 1:
        edges = cv2.dilate(edges.astype(np.uint8),
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (thickness, thickness))) > 0
    return edges


def _roughen(tone: np.ndarray, roughness: float, short_side: int) -> np.ndarray:
    """Wobble the tone so cut boundaries are irregular rather than mathematical."""
    rng = np.random.default_rng(7)   # fixed: a photo always prints the same
    small = rng.normal(0, 1, (max(2, tone.shape[0] // 28), max(2, tone.shape[1] // 28)))
    noise = cv2.resize(small.astype(np.float32), tone.shape[::-1], interpolation=cv2.INTER_CUBIC)
    noise = cv2.GaussianBlur(noise, (0, 0), sigmaX=max(1.0, short_side / 500))
    peak = float(np.abs(noise).max()) or 1.0
    return np.clip(tone.astype(np.float32) + noise / peak * (22.0 * roughness / 100),
                   0, 255).astype(np.uint8)


def _hatch(tone: np.ndarray, solid_at: float, paper_at: float,
           hatching: float, min_feature: float) -> np.ndarray:
    """Carve the midtones as parallel lines that thicken as the tone darkens.

    Line spacing and the thinnest line are both held at or above what the brush
    can paint, so the tone is carried by marks the machine can actually make
    rather than by a pattern that collapses when it is traced.
    """
    h, w = tone.shape
    # Spacing is set so the thinnest line is a fixed fraction of the gap. That
    # keeps the lightest hatch light even for a wide brush, where a fixed
    # spacing would force every line to be thick and flood the midtones.
    spacing = min_feature * (5.6 - 2.5 * hatching / 100)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    t = tone.astype(np.float32)
    # 0 at the edge of the solid blacks, 1 where the paper starts.
    ramp = np.clip((t - solid_at) / max(paper_at - solid_at, 1e-6), 0, 1)
    in_band = (t >= solid_at) & (t < paper_at)

    duty_min = min_feature / spacing
    duty = duty_min + (1.0 - ramp) * (0.5 - duty_min)

    def lines(angle, offset=0.0):
        proj = (xx * np.cos(angle) + yy * np.sin(angle)) / spacing + offset
        return (proj - np.floor(proj)) < duty

    out = lines(np.pi / 4) & in_band
    # The darkest third of the band gets a second pass, the way a cut is
    # cross-hatched to hold a deeper tone.
    if hatching > 35:
        out |= lines(-np.pi / 4, 0.5) & in_band & (ramp < 0.34)
    return out


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


def feature_px(image_px: int, image_mm: float, brush_mm: float) -> float:
    """Brush width expressed in pixels of the working image."""
    if image_mm <= 0 or image_px <= 0:
        return 3.0
    working = min(image_px, MAX_SIDE)
    return max(1.5, brush_mm * working / image_mm)


def ink_fraction(img: Image.Image) -> float:
    return float((np.asarray(img.convert("L")) < 128).mean())
