#!/usr/bin/python3
"""Photo -> woodcut / linocut black and white.

The pipeline downstream outlines black regions and fills them with a
brush, so the output must be pure two-tone with nothing finer than the brush can
lay down. Detail therefore cannot come from grey: it comes the way it does in a
real cut, from carved hatching whose density carries the tone. That also suits
the machine, since hatching is long parallel strokes.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

# Working resolution, and how hard the cleanup stages press, both follow the
# Detail control. At the top of the range only the brush itself is allowed to
# limit what survives; at the bottom the picture is deliberately coarsened.
MIN_WORK_SIDE = 1400
MAX_WORK_SIDE = 2400
# Resolution the hatching streaks are grown at before being scaled up.
LIC_SIDE = 900


def working_side(detail: float) -> int:
    return int(MIN_WORK_SIDE + (MAX_WORK_SIDE - MIN_WORK_SIDE) * float(detail) / 100.0)


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
    min_feature_px: float | None = None,  # thinnest mark the brush can paint
    width_mm: float | None = None,   # how wide the picture will be painted
    brush_mm: float | None = None,   # how wide a stroke the brush lays down
    mask: np.ndarray | None = None,  # optional subject mask; outside becomes paper
) -> Image.Image:
    """Return a 1-bit image: black where the brush should paint."""
    detail = float(np.clip(detail, 0, 100))
    threshold = float(np.clip(threshold, -50, 50))
    roughness = float(np.clip(roughness, 0, 100))
    hatching = float(np.clip(hatching, 0, 100))

    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, working_side(detail) / max(h, w))
    if scale < 1.0:
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        if mask is not None:
            mask = cv2.resize(mask, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    short_side = min(gray.shape)
    # Derived after the resize, so the brush width is expressed in the pixels
    # actually being worked on. Passing it in precomputed went stale the moment
    # the working resolution started following Detail.
    if width_mm and brush_mm:
        min_feature = max(1.2, float(brush_mm) * rgb.shape[1] / float(width_mm))
    else:
        min_feature = max(1.0, float(min_feature_px or 3.0))
    ease = detail / 100.0

    gray = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8)).apply(gray)

    # Smoothing is now light: it exists to stop sensor noise becoming marks, not
    # to flatten the picture. More detail means less of it.
    # Smoothing is set by sigma rather than by a pixel window. A window has to
    # be a whole odd number, so sliding Detail made it jump — 5 to 3 between 80
    # and 81 — and every stage downstream reads the tone this produces. Letting
    # OpenCV derive the window from a continuous sigma removes the step.
    sigma_space = float(np.clip(short_side * (0.014 - 0.0132 * detail / 100), 1.2, 12.0))
    tone = cv2.bilateralFilter(gray, d=0, sigmaColor=95 - 0.65 * detail,
                               sigmaSpace=sigma_space)

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
        ink |= _hatch(tone, solid_at, paper_at, hatching, min_feature, ease, gray)

    if outlines:
        ink |= _contours(tone, gray, detail, min_feature)

    solid = ink.astype(np.uint8)
    # Only a light close, and never an open: an open with a kernel wider than a
    # hatch line would erase the hatching that carries the tone.
    k = _odd(max(2.0, min_feature * (0.95 - 0.6 * ease)), 3)
    solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    solid = _drop_specks(solid, min_area=(min_feature * (1.3 - 0.75 * ease)) ** 2)

    if mask is not None:
        solid = np.where(mask > 0, solid, 0).astype(np.uint8)

    return Image.fromarray(np.where(solid > 0, 0, 255).astype(np.uint8), "L").convert("1")


def _contours(tone: np.ndarray, gray: np.ndarray, detail: float, min_feature: float) -> np.ndarray:
    """Knife lines along real boundaries, not along texture.

    Two layers. The broad contours come from Canny, whose threshold slides with
    Detail. The finer interior lines — eyelids, folds, strands — come from
    gradient strength above a moving percentile, rather than from extra Canny
    passes switched on at fixed points on the slider. A pass that appears all at
    once takes a face from line drawing to near-solid black in one step of the
    control; a percentile lets the same lines arrive a few at a time.

    Canny fires on grass and cloud as readily as on a jawline, so short
    fragments are discarded before the lines are thickened.
    """
    ease = float(np.clip(detail, 0, 100)) / 100.0

    # Float thresholds, not rounded ones: Canny's hysteresis is sensitive
    # enough that a single integer step in the level moved the ink by 2.5%.
    lo = 70.0 - 34.0 * ease
    edges = cv2.Canny(cv2.GaussianBlur(tone, (0, 0), 1.1), lo, lo * 2.6) > 0

    # Interior detail, faded in by how much of the gradient range is admitted.
    # 99.7% of pixels rejected at the bottom of the slider, 88% at the top.
    fine = cv2.GaussianBlur(gray, (0, 0), 0.8)
    gx = cv2.Sobel(fine, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(fine, cv2.CV_32F, 0, 1, ksize=3)
    strength = cv2.magnitude(gx, gy)
    keep_pct = 99.7 - 11.7 * ease
    level = float(np.percentile(strength, keep_pct))
    if level > 0:
        edges |= strength > level

    min_run = max(3.0, min_feature * (4.6 - 3.4 * ease))
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


def _flow_field(gray: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The direction the form runs in at each pixel, and how sure we are of it.

    From the structure tensor: its dominant eigenvector points across an edge,
    so the perpendicular runs along it. Blurring the tensor rather than the
    angles is what makes the field continuous — angles wrap at pi and cannot be
    averaged directly.
    """
    g = gray.astype(np.float32) / 255.0
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=5)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), sigma)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), sigma)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), sigma)

    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)   # across the edge
    tangent = theta + np.pi / 2.0                    # along it
    vx, vy = np.cos(tangent), np.sin(tangent)

    # How directional the neighbourhood is. Where nothing runs anywhere —
    # an open sky, a flat wall — this falls to zero and the field is meaningless.
    diff = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy ** 2)
    total = jxx + jyy
    coherence = np.where(total > 1e-8, diff / (total + 1e-8), 0.0).astype(np.float32)
    return vx.astype(np.float32), vy.astype(np.float32), coherence


def _hatch(tone: np.ndarray, solid_at: float, paper_at: float,
           hatching: float, min_feature: float, detail_ease: float = 0.0,
           gray: np.ndarray | None = None) -> np.ndarray:
    """Carve the midtones as lines that follow the form.

    A cut is made with a knife travelling along the shape, so its lines curve
    around a cheek and run the length of a limb. Straight stripes at a fixed
    angle, and the lattice you get from crossing two of them, read as a screen
    laid over the picture rather than as something carved.

    The lines here are grown by smearing a coarse noise field along the image's
    own tangent flow — the streaks that come out are continuous, follow the
    contours, and fan around features. Their spacing is set by how coarse the
    noise is, so it still answers to the brush; how much of each becomes ink is
    set by the tone, so darkness still reads as darkness.
    """
    h, w = tone.shape
    spacing = min_feature * (5.6 - 2.5 * hatching / 100 - 0.6 * detail_ease)
    spacing = max(spacing, min_feature * 2.0)

    t = tone.astype(np.float32)
    ramp = np.clip((t - solid_at) / max(paper_at - solid_at, 1e-6), 0, 1)
    in_band = (t >= solid_at) & (t < paper_at)
    if not in_band.any():
        return np.zeros_like(in_band)

    vx, vy, coherence = _flow_field(gray if gray is not None else tone,
                                    sigma=max(2.0, spacing * 0.9))
    # Where the picture has no direction of its own, fall back to a steady
    # diagonal so flat areas still read as cut rather than as blank.
    steady = np.pi / 4.0
    weight = np.clip(coherence * 3.0, 0, 1)[..., None] if False else np.clip(coherence * 3.0, 0, 1)
    vx = vx * weight + np.cos(steady) * (1 - weight)
    vy = vy * weight + np.sin(steady) * (1 - weight)
    norm = np.sqrt(vx * vx + vy * vy) + 1e-8
    vx, vy = (vx / norm).astype(np.float32), (vy / norm).astype(np.float32)

    # The streaks are grown at a working size and scaled up. Following a flow
    # field a step at a time is the expensive part of this, and it costs with
    # the square of the resolution; the pattern itself is smooth enough that
    # nothing of it is lost on the way back up.
    lic_scale = min(1.0, LIC_SIDE / max(h, w))
    lh, lw = max(8, int(h * lic_scale)), max(8, int(w * lic_scale))
    lic_spacing = max(2.0, spacing * lic_scale)

    # Fine noise smeared a long way. The ratio of the two is what makes a mark
    # read as a cut line rather than a blot: short smears over coarse noise give
    # dabs, and it is length against width that says "carved".
    rng = np.random.default_rng(11)
    cell = max(1, int(round(lic_spacing * 0.22)))
    noise = rng.random((max(2, lh // cell), max(2, lw // cell))).astype(np.float32)
    noise = cv2.resize(noise, (lw, lh), interpolation=cv2.INTER_LINEAR)

    small_vx = cv2.resize(vx, (lw, lh), interpolation=cv2.INTER_LINEAR)
    small_vy = cv2.resize(vy, (lw, lh), interpolation=cv2.INTER_LINEAR)
    # Renormalise after the resize: averaging neighbouring directions shortens
    # the vectors, and the smear steps one length at a time.
    scale_norm = np.sqrt(small_vx ** 2 + small_vy ** 2) + 1e-8
    small_vx = (small_vx / scale_norm).astype(np.float32)
    small_vy = (small_vy / scale_norm).astype(np.float32)

    lic = _smear_along(noise, small_vx, small_vy, steps=max(8, int(lic_spacing * 9)))
    if lic_scale < 1.0:
        lic = cv2.resize(lic, (w, h), interpolation=cv2.INTER_LINEAR)
    # Normalise locally, so the streak pattern is comparable everywhere and the
    # threshold below means the same thing in a bright region as in a dark one.
    blur = max(3, _odd(int(spacing * 6)))
    local_mean = cv2.GaussianBlur(lic, (blur, blur), 0)
    local_dev = np.sqrt(cv2.GaussianBlur((lic - local_mean) ** 2, (blur, blur), 0)) + 1e-6
    z = (lic - local_mean) / local_dev
    level = np.clip(z, -3, 3) / 6.0 + 0.5      # roughly 0..1

    duty_min = min(0.45, min_feature / spacing)
    duty = duty_min + (1.0 - ramp) * (0.62 - duty_min)
    return (level < duty) & in_band


def _smear_along(field: np.ndarray, vx: np.ndarray, vy: np.ndarray, steps: int) -> np.ndarray:
    """Average a field along the flow through every pixel, both ways.

    Line integral convolution: following the field a step at a time and
    resampling it as we go is what lets a streak bend with the form instead of
    running off straight.
    """
    h, w = field.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    total = field.copy()
    count = np.ones_like(field)
    for direction in (1.0, -1.0):
        px, py = xs.copy(), ys.copy()
        for _ in range(steps):
            dx = cv2.remap(vx, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            dy = cv2.remap(vy, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            px = px + direction * dx
            py = py + direction * dy
            np.clip(px, 0, w - 1, out=px)
            np.clip(py, 0, h - 1, out=py)
            total += cv2.remap(field, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            count += 1.0
    return total / count


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
    return float((np.asarray(img.convert("L")) < 128).mean())
