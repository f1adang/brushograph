#!/usr/bin/python3
"""Photo -> woodcut / linocut black and white.

The pipeline downstream outlines black regions and fills them with a
brush, so the output must be pure two-tone with nothing finer than the brush can
lay down. Detail therefore cannot come from grey: it comes the way it does in a
real cut, from hatching whose density carries the tone.

What comes out is meant to be **strokes** — long ones, following the form,
about a brush wide, laid further apart where the picture is lighter. That is
how an engraver works and it is the only thing a brush does well: a brush
cannot lay a dash, leave a millimetre and lay another, it has to come off the
paper and go back down, and every one of those is a lift, a trip for paint and
a blot where it lands. So there are no solid blacks here and no dashes. The
darkest shadow is strokes packed tight, and the lightest tone the picture holds
is the same stroke with more paper either side of it.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image

from images import flatten

# Working resolution, and how hard the cleanup stages press, both follow the
# Detail control. At the top of the range only the brush itself is allowed to
# limit what survives; at the bottom the picture is deliberately coarsened.
# How much broader than the brush the cut's marks are drawn. Every mark and
# every gap between marks is measured in `min_feature`, so this scales the whole
# cut together: broader strokes, laid proportionally further apart, rather than
# just fattening the lines over an unchanged layout. It does darken the picture
# a little — 50% ink to 57% on a test portrait — because the marks grow at the
# ends as well as across, and speckle that used to be separate dots merges.
# Past about 1.5 the merging starts eating fine structure such as hair.
STROKE_BOLDNESS = 1.35

MIN_WORK_SIDE = 1400
MAX_WORK_SIDE = 2400
# How many pixels wide the brush is at the resolution the strokes are traced
# at. Tracing costs with the picture's area over the stroke spacing, and
# neither is interesting in fine pixels, so it is done coarse and the lines are
# drawn at the working resolution from the coordinates that come back.
TRACE_BRUSH_PX = 6.0


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

    rgb = np.asarray(flatten(image))
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
    min_feature *= STROKE_BOLDNESS
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

    # Two levels, at percentiles of this image's own tones rather than at a
    # fixed level. Otsu splits ink from paper, which is the wrong question
    # here: what matters is where the strokes run as tight as they go and where
    # they give out altogether, and that should hold steady whether the
    # photograph is bright or dim.
    sample = tone[mask > 0] if mask is not None and (mask > 0).any() else tone
    solid_pct = float(np.clip(17.0 - threshold * 0.55, 1.5, 60.0))
    paper_pct = float(np.clip(58.0 - threshold * 0.85, 12.0, 96.0))
    solid_at = float(np.percentile(sample, solid_pct))
    paper_at = float(np.percentile(sample, max(paper_pct, solid_pct + 4)))

    # The darkest band used to be filled in solid and the hatching ran only
    # between it and the paper. A solid is not a thing a brush does: the tracer
    # covers one by walking round and round inside it, so a shadow came out as
    # a contour map of nested rings — on a test portrait the middle stroke was
    # 11.5 mm long. It is strokes all the way down now, tightest in the darks,
    # and the middle stroke of that same portrait is 40.2 mm.
    #
    # Hatching at 0 is the exception, and has to be: with no strokes to draw
    # the shadows with, the only thing left that says "shadow" is filling them
    # in, which is what that end of the slider has always meant.
    ink = (_hatch(tone, solid_at, paper_at, hatching, min_feature, ease, gray)
           if hatching > 0 else tone < solid_at)

    if outlines:
        ink |= _contours(tone, gray, detail, min_feature)

    solid = ink.astype(np.uint8)
    # Only a light close, and never an open: an open with a kernel wider than a
    # stroke would erase the hatching that carries the tone.
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
    """Draw the tone as long strokes that follow the form.

    A cut is made with a knife travelling along the shape, so its lines curve
    around a cheek and run the length of a limb. Straight stripes at a fixed
    angle — and the lattice you get from crossing two of them — read as a
    screen laid over the picture rather than as something carved. So the
    strokes are traced along the picture's own tangent flow, from the structure
    tensor, and where an image has no direction of its own — an open sky, a
    flat wall — the field falls back to a steady diagonal.

    **Tone is carried by how far apart the strokes run, not by breaking them
    up.** That is the whole of it: a stroke is drawn about one brush wide from
    end to end, and the darks get more of them. It is how an engraver works and
    it is the only thing a brush can do well — a brush cannot lay a dash and
    then another dash a millimetre later, it has to come off the paper and go
    back down, and a dab is a blot with a wet brush.
    """
    h, w = tone.shape
    t = tone.astype(np.float32)

    # How far apart the strokes run: nearly touching where the picture is at
    # its darkest, far apart at the edge of the highlights, and nowhere at all
    # on paper. Hatching slides both ends, so it reads as "how much of the
    # picture is worked".
    tight = min_feature * (2.4 - 0.6 * hatching / 100)
    loose = min_feature * (10.0 - 5.0 * hatching / 100)
    ramp = np.clip((t - solid_at) / max(paper_at - solid_at, 1e-6), 0, 1)
    apart = tight + (loose - tight) * ramp
    paintable = t < paper_at
    if not paintable.any():
        return np.zeros_like(paintable)

    vx, vy, coherence = _flow_field(gray if gray is not None else tone,
                                    sigma=max(2.0, tight * 0.9))
    steady = np.pi / 4.0
    weight = np.clip(coherence * 3.0, 0, 1)
    vx = vx * weight + np.cos(steady) * (1 - weight)
    vy = vy * weight + np.sin(steady) * (1 - weight)
    norm = np.sqrt(vx * vx + vy * vy) + 1e-8
    vx, vy = (vx / norm).astype(np.float32), (vy / norm).astype(np.float32)

    strokes = _trace_strokes(t, apart, paintable, vx, vy, min_feature, detail_ease)

    # The strokes are traced coarse and drawn fine: the coordinates come back
    # in working-image pixels, so a line is as smooth as the picture it is
    # drawn into however cheaply it was followed.
    marks = np.zeros((h, w), np.uint8)
    for pts, widths in strokes:
        for (x0, y0), (x1, y1), width in zip(pts, pts[1:], widths):
            cv2.line(marks, (int(round(x0)), int(round(y0))),
                     (int(round(x1)), int(round(y1))), 1, max(1, int(round(width))))
    return marks > 0


def _trace_strokes(tone: np.ndarray, apart: np.ndarray, paintable: np.ndarray,
                   vx: np.ndarray, vy: np.ndarray, min_feature: float,
                   detail_ease: float) -> list[tuple[list, list]]:
    """Follow the flow from seed to seed, keeping the strokes off each other.

    Evenly spaced streamlines, in the manner of Jobard and Lefebvre: a stroke
    is traced until it runs into paper or into the ground another stroke has
    already claimed, and the ground it claims for itself is a band as wide as
    the spacing the tone asks for there. Seeds are taken darkest first, so the
    shadows are laid out before the half-tones and it is the lights that go
    without when the two compete.

    Tracing costs with the area over the spacing, and neither figure is
    interesting in the fine pixels of the working image, so it is done at
    whatever resolution makes the brush TRACE_BRUSH_PX across — coarse enough
    to be quick, fine enough that a stroke bends smoothly. The coordinates come
    back scaled to the working image, where the line is actually drawn.

    The flow is a direction without a sign: the tangent at one pixel may come
    back as the opposite of its neighbour's, and following it blindly walks a
    stroke back over itself. Every step is therefore turned to agree with the
    step before it.
    """
    h, w = tone.shape
    scale = float(np.clip(TRACE_BRUSH_PX / max(min_feature, 1e-6), 0.08, 1.0))
    th, tw = max(8, int(h * scale)), max(8, int(w * scale))

    def small(field, interp=cv2.INTER_LINEAR):
        return cv2.resize(field, (tw, th), interpolation=interp)

    fvx, fvy = small(vx), small(vy)
    n = np.sqrt(fvx * fvx + fvy * fvy) + 1e-8      # the resize averages directions
    fvx, fvy = (fvx / n).astype(np.float32), (fvy / n).astype(np.float32)
    fapart = small(apart) * scale
    ftone = small(tone)
    fok = small(paintable.astype(np.uint8), cv2.INTER_NEAREST) > 0

    # A stroke shorter than this is a dab, and a dab is a trip to the paint,
    # a brush put down and lifted, and a blot. More detail keeps shorter ones.
    min_run = max(3.0, min_feature * (7.0 - 3.0 * detail_ease)) * scale
    max_steps = int(3.0 * max(th, tw))
    claimed = np.zeros((th, tw), np.uint8)

    def walk(x0: float, y0: float, back: bool) -> list:
        pts, x, y = [], float(x0), float(y0)
        dx, dy = float(fvx[int(y0), int(x0)]), float(fvy[int(y0), int(x0)])
        if back:
            dx, dy = -dx, -dy
        for _ in range(max_steps):
            ix, iy = int(x), int(y)
            if not (0 <= ix < tw and 0 <= iy < th) or not fok[iy, ix] or claimed[iy, ix]:
                break
            pts.append((x, y))
            nx, ny = float(fvx[iy, ix]), float(fvy[iy, ix])
            if nx * dx + ny * dy < 0:
                nx, ny = -nx, -ny
            dx, dy = nx, ny
            x, y = x + dx, y + dy
        return pts

    # Candidates on a grid half the tightest spacing, darkest first: a seed in
    # the shadows is worth more than one in a half-tone, and one that has been
    # claimed by an earlier stroke is skipped rather than pushed aside.
    grid = max(1, int(round(float(fapart.min()) * 0.5)))
    ys, xs = np.mgrid[0:th:grid, 0:tw:grid]
    ys, xs = ys.ravel(), xs.ravel()
    keep = fok[ys, xs]
    ys, xs = ys[keep], xs[keep]
    order = np.argsort(ftone[ys, xs], kind="stable")

    strokes = []
    for i in order:
        sx, sy = int(xs[i]), int(ys[i])
        if claimed[sy, sx]:
            continue
        pts = walk(sx, sy, back=True)[::-1] + walk(sx, sy, back=False)[1:]
        if len(pts) < 2:
            continue
        run = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
        if run < min_run:
            continue
        # The ground this stroke takes for itself, and the stroke as it will be
        # drawn. Both follow the tone under them, so a stroke that runs out of
        # the shadow into a half-tone thins and gives its neighbours more room
        # without ever coming off the paper.
        widths = []
        for a, b in zip(pts, pts[1:]):
            mx, my = int((a[0] + b[0]) / 2), int((a[1] + b[1]) / 2)
            mx, my = min(max(mx, 0), tw - 1), min(max(my, 0), th - 1)
            cv2.line(claimed, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 1,
                     max(1, int(round(float(fapart[my, mx])))))
            widths.append(_stroke_width(float(ftone[my, mx]), min_feature))
        strokes.append(([(x / scale, y / scale) for x, y in pts], widths))
    return strokes


def _stroke_width(tone_here: float, min_feature: float) -> float:
    """One brush wide, a little broader in the dark.

    Not broader than that: a mark much wider than the brush stops being a
    stroke and becomes a shape, and a shape is painted by going round and round
    inside it — which is where the short strokes came from in the first place.
    """
    return min_feature * (0.95 - 0.25 * min(tone_here / 255.0, 1.0))


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
