#!/usr/bin/python3
"""Thresholded image per tray -> brush paths -> copicograf G-code.

This is the chain `image_to_gcode_adaptive.py` describes, driven from uploads
instead of files named by a CMYK separation, and using the tools that are
actually on PATH instead of hardcoded macOS app bundles.
"""
from __future__ import annotations

import math
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from images import flatten

import planar
from version import gcode_note

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from configspec import (CLASSIC_DISH_RIM_RADIUS, CMYK_TO_TRAY,  # noqa: E402
                        RECTANGULAR_SHAPES, canvas_origin, cup_shape_of,
                        EDGE_HEADROOM, feed_line, holder_of,
                        paintable_size, tray_entries, workable_x)

FALLBACK_PATTERN = "concentric"

# How far apart two stroke ends may be and still be joined into one stroke,
# as a multiple of the fill line spacing. Raise it for longer strokes at the
# cost of painting over slightly more bare paper.
BRIDGE_MULTIPLE = 1.5

# How many pixels wide the brush must be in the raster the geometry is worked
# on. Everything downstream — the distance transform, the contours, the rescue
# pass — resolves to whole pixels, so when a stroke is barely one pixel across
# there is nothing left to place it with. Measured over a test corpus: at the
# file's own resolution a 400 px picture painted 151 mm wide left 12% of its ink
# unpainted and put 18% of it onto bare paper. Working at six pixels to the
# brush brings both into line with what a large picture gets, for about a third
# more time on the small pictures and none at all on the large ones.
MIN_PX_PER_BRUSH = 6.0

# Beyond this the enlargement costs more than it returns.
MAX_WORK_PX = 4000

# Stroke width assumed when the config asks for no infill and so states no
# spacing to take one from.
NOMINAL_BRUSH_MM = 1.0

# Bridging further than this does not pay. A bridge replaces a lift and a travel
# with painted distance, and painted distance is what forces trips to the paint
# tray: copicograf re-inks every paint_per_run. Past a few line widths the trips
# cost more than the lifts saved.

# The Z values copicograf.prepare_path() watches for to raise and lower the brush.
PEN_UP = "G1 F600 Z6"
PEN_DOWN = "G1 F600 Z1"


class PipelineError(RuntimeError):
    pass


# ------------------------------------------------------------------ raster prep

def to_pbm(src: Path, dst: Path, log) -> tuple[int, int, np.ndarray]:
    """Split the picture into ink and paper, and write it as a bitmap.

    The dividing tone is found per image with Otsu's method rather than fixed
    near white. A stylised or scanned print is very often on cream paper — one
    such file measured (237, 229, 216) — and treating anything not almost-white
    as ink turned 99.9% of it into a single solid shape that painted the whole
    canvas.

    The darkest channel is what gets thresholded, not the brightness. A
    saturated ink reads as dark in at least one channel however bright it looks,
    so pure yellow on tinted paper still separates correctly.
    """
    with Image.open(src) as im:
        rgb = flatten(im)
        w, h = rgb.size
        a = np.asarray(rgb)

    darkest = a.min(axis=2).astype(np.uint8)
    # OpenCV returns 0 for a perfectly bimodal image, where every threshold
    # separates the two tones equally well; `<=` keeps that case working and
    # also keeps ink whose tone lands exactly on the level.
    level, _ = cv2.threshold(darkest, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = darkest <= level

    if not ink.any():
        raise PipelineError(f"{src.name} has no ink in it — nothing to paint")
    share = float(ink.mean())
    if share > 0.97:
        log(f"  warning: {share * 100:.1f}% of {src.name} reads as ink — "
            "the whole canvas will be painted")
    out = np.where(ink, 0, 255).astype(np.uint8)
    Image.fromarray(out, "L").convert("1").save(dst)
    log(f"  {src.name}: {w}×{h} px, ink/paper split at {level:.0f}, {share * 100:.1f}% ink")
    return w, h, ink


# ------------------------------------------------------------------- G-code I/O

_G1 = re.compile(r"^G0*1(?![0-9])")
_G0 = re.compile(r"^G0*0(?![0-9])")
_WORD = re.compile(r"([XYZEF])\s*(-?\d*\.?\d+)")


def _mm_size(value: float) -> str:
    """A painted dimension for a message: whole millimetres where it is one."""
    return f"{value:g}"


def _enlarge_for_brush(ink: np.ndarray, width_mm: float, line_w: float, log) -> np.ndarray:
    """Resample the ink so a stroke is a few pixels wide, if it is not already.

    A small picture painted large leaves the brush thinner than one pixel of
    the raster the geometry is worked on, and an outline cannot be placed
    inside a shape that is one pixel across. Enlarging first costs a little
    time and returns most of the ink: a 400 px picture went from a third of its
    ink unpainted to a fortieth.

    The resample is smooth rather than blocky on purpose. The pixel edges are
    an artefact of the file's size, not of the drawing, and carrying them into
    the strokes would have the brush trace a staircase that was never there.
    """
    h, w = ink.shape
    per_brush = w / width_mm * line_w
    if per_brush >= MIN_PX_PER_BRUSH:
        return ink
    factor = min(MIN_PX_PER_BRUSH / per_brush, MAX_WORK_PX / max(w, h))
    if factor <= 1.01:
        return ink
    size = (int(round(w * factor)), int(round(h * factor)))
    smooth = cv2.resize(ink.astype(np.uint8) * 255, size, interpolation=cv2.INTER_CUBIC)
    grown = smooth >= 128
    log(f"  brush is {per_brush:.1f} px here; working at {size[0]}×{size[1]} "
        f"({factor:.1f}x) so it is {per_brush * factor:.1f}")
    return grown


class InkMask:
    """Answers whether a straight move stays inside the painted shape.

    The artwork is scaled so the source image spans exactly
    (0,0)-(width_mm, height_mm) in slicer coordinates, and image row 0 is the
    top while machine Y grows upward — hence the flip.
    """

    def __init__(self, ink, width_mm: float, height_mm: float):
        self.ink = ink
        self.h, self.w = ink.shape
        self.width_mm = width_mm
        self.height_mm = height_mm

    def at(self, x_mm: float, y_mm: float) -> bool:
        col = int(x_mm / self.width_mm * self.w)
        row = int((1.0 - y_mm / self.height_mm) * self.h)
        if 0 <= row < self.h and 0 <= col < self.w:
            return bool(self.ink[row, col])
        return False

    def segment_inside(self, a, b, step: float = 0.5) -> bool:
        dx, dy = b[0] - a[0], b[1] - a[1]
        dist = (dx * dx + dy * dy) ** 0.5
        n = max(2, int(dist / step) + 1)
        for i in range(n + 1):
            t = i / n
            if not self.at(a[0] + dx * t, a[1] + dy * t):
                return False
        return True


def order_polylines(polys, tol_grid: float = 8.0):
    """Emit strokes nearest-first so the brush spends less time travelling."""
    if len(polys) < 3:
        return polys
    cell = max(tol_grid, 1e-6)
    buckets: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def key(pt):
        return (int(pt[0] // cell), int(pt[1] // cell))

    for i, poly in enumerate(polys):
        buckets.setdefault(key(poly[0]), []).append((i, 0))
        buckets.setdefault(key(poly[-1]), []).append((i, 1))

    used = [False] * len(polys)
    out = [polys[0]]
    used[0] = True
    cur = polys[0][-1]
    for _ in range(len(polys) - 1):
        best = None
        ring = 1
        while best is None and ring < 64:
            cx, cy = key(cur)
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    if max(abs(dx), abs(dy)) != ring - 1 and ring > 1:
                        continue
                    for j, end in buckets.get((cx + dx, cy + dy), ()):
                        if used[j]:
                            continue
                        pt = polys[j][0] if end == 0 else polys[j][-1]
                        d = (pt[0] - cur[0]) ** 2 + (pt[1] - cur[1]) ** 2
                        if best is None or d < best[0]:
                            best = (d, j, end)
            ring += 1
        if best is None:
            for j in range(len(polys)):
                if not used[j]:
                    best = (0.0, j, 0)
                    break
        if best is None:
            break
        _, j, end = best
        used[j] = True
        nxt = polys[j] if end == 0 else polys[j][::-1]
        out.append(nxt)
        cur = nxt[-1]
    return out


def chain_polylines(polys: list[list[tuple[float, float]]], tol: float,
                    permit=None) -> list[list[tuple[float, float]]]:
    """Rejoin runs whose ends meet, so one brush stroke stays one brush stroke.

    A slicer emits a fill as many separate extrusion runs even where they are
    physically continuous — perimeter into infill, or one infill line into the
    next. Honouring those splits would lift the brush and re-ink mid-stroke,
    which is exactly what a watercolour brush must not do. Endpoints are matched
    on a grid, and a run is reversed when that is the end which meets.
    """
    cell = max(tol, 1e-9)
    buckets: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def key(pt):
        return (int(pt[0] // cell), int(pt[1] // cell))

    for i, poly in enumerate(polys):
        buckets.setdefault(key(poly[0]), []).append((i, 0))
        buckets.setdefault(key(poly[-1]), []).append((i, 1))

    used = [False] * len(polys)
    out = []
    for i in range(len(polys)):
        if used[i]:
            continue
        used[i] = True
        chain = list(polys[i])
        while True:
            tail = chain[-1]
            cx, cy = key(tail)
            best = None
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j, end in buckets.get((cx + dx, cy + dy), ()):
                        if used[j]:
                            continue
                        pt = polys[j][0] if end == 0 else polys[j][-1]
                        d = (pt[0] - tail[0]) ** 2 + (pt[1] - tail[1]) ** 2
                        if d <= tol * tol and (best is None or d < best[0]):
                            if permit is not None and d > 1e-6 and not permit(tail, pt):
                                continue
                            best = (d, j, end)
            if best is None:
                break
            _, j, end = best
            used[j] = True
            nxt = polys[j] if end == 0 else polys[j][::-1]
            chain.extend(nxt[1:])   # drop the duplicated joint point
        out.append(chain)
    return out


def simplify(poly: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Douglas-Peucker, iteratively — these paths run to thousands of points."""
    if len(poly) < 3 or tol <= 0:
        return poly
    keep = [False] * len(poly)
    keep[0] = keep[-1] = True
    stack = [(0, len(poly) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        ax, ay = poly[a]
        bx, by = poly[b]
        dx, dy = bx - ax, by - ay
        norm = (dx * dx + dy * dy) ** 0.5
        worst, worst_i = -1.0, -1
        for i in range(a + 1, b):
            px, py = poly[i]
            if norm < 1e-12:
                d = ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
            else:
                d = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if d > worst:
                worst, worst_i = d, i
        if worst > tol:
            keep[worst_i] = True
            stack.append((a, worst_i))
            stack.append((worst_i, b))
    return [pt for pt, k in zip(poly, keep) if k]


def _length(poly) -> float:
    return sum(((poly[i + 1][0] - poly[i][0]) ** 2 + (poly[i + 1][1] - poly[i][1]) ** 2) ** 0.5
               for i in range(len(poly) - 1))


def _trace_skeleton(skeleton: np.ndarray) -> list[list[tuple[int, int]]]:
    """Walk a one-pixel-wide skeleton into runs of pixels.

    Greedy: start from the loose ends, follow unvisited neighbours, and take
    whatever is left over as loops. A fork becomes two runs, which is what a
    brush has to do with one anyway.
    """
    points = set(zip(*np.nonzero(skeleton)))
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    def neighbours(p):
        r, c = p
        return [(r + dr, c + dc) for dr, dc in offsets if (r + dr, c + dc) in points]

    used: set = set()

    def walk(start):
        """Follow the skeleton, carrying straight on through a junction.

        Taking whichever neighbour came first would stop at every fork and turn
        one rib into a handful of stubs. Choosing the neighbour that best
        continues the current direction keeps a stroke whole, which is what the
        brush wants and what the outline it stands in for would have been.
        """
        run = [start]
        used.add(start)
        current = start
        heading = None
        while True:
            nxt = [q for q in neighbours(current) if q not in used]
            if not nxt:
                break
            if heading is None:
                pick = nxt[0]
            else:
                def straightness(q):
                    dr, dc = q[0] - current[0], q[1] - current[1]
                    norm = (dr * dr + dc * dc) ** 0.5 or 1.0
                    return -(dr * heading[0] + dc * heading[1]) / norm
                pick = min(nxt, key=straightness)
            dr, dc = pick[0] - current[0], pick[1] - current[1]
            norm = (dr * dr + dc * dc) ** 0.5 or 1.0
            heading = (dr / norm, dc / norm)
            used.add(pick)
            run.append(pick)
            current = pick
        return run

    runs = []
    for start in [p for p in points if len(neighbours(p)) == 1]:
        if start not in used:
            runs.append(walk(start))
    for p in points:                      # closed loops have no loose end
        if p not in used:
            runs.append(walk(p))
    return [r for r in runs if len(r) >= 2]


def centrelines_for_missed(mask, polys, line_w: float, log=None) -> list:
    """A stroke down the middle of whatever the paths left unpainted.

    A shape narrower than the brush gets no perimeter — there is nowhere to put
    one — so a rib, a hairline or a stroke of lettering simply disappears. Its
    centreline is the one line a brush can lay there, and laying it is closer to
    the drawing than leaving the shape blank.

    What is rescued is the *residual*: the ink minus what the strokes already
    cover. Judging whole connected shapes instead, as this once did, is
    all-or-nothing — a line whose broad part got an outline counts as covered,
    and its thin part stays blank however long it is. Working from the residual
    also means one thinning pass over one image rather than one per shape.
    """
    ink = mask.ink
    h, w = ink.shape
    px_per_mm = w / mask.width_mm

    covered = np.zeros((h, w), np.uint8)
    brush_px = max(1, int(round(line_w * px_per_mm)))
    for run in polys:
        pts = np.array([[int(x / mask.width_mm * w), int((1 - y / mask.height_mm) * h)]
                        for x, y in run], np.int32)
        if len(pts) > 1:
            cv2.polylines(covered, [pts], False, 1, thickness=brush_px)
    # Rounding puts a stroke's edge a pixel either side of the shape's, which
    # would leave a hairline of "missed" ink along every outline. Within a pixel
    # of paint counts as painted.
    covered = cv2.dilate(covered, np.ones((3, 3), np.uint8))

    # One pass does not finish the job. A shape two brushes wide loses its
    # middle to a centreline and keeps a strip either side; those strips are
    # ink too. So the residual is re-measured after each set of strokes and
    # worked again, until what is left is not worth a stroke.
    min_area = max(12.0, (line_w * px_per_mm * 0.6) ** 2)
    rescued: list = []
    for _ in range(4):
        residual = ink.astype(np.uint8) & (covered == 0).astype(np.uint8)
        if not residual.any():
            break
        n, labels, stats, _ = cv2.connectedComponentsWithStats(residual, 8)
        keep = np.zeros(n, bool)
        for i in range(1, n):
            keep[i] = stats[i, cv2.CC_STAT_AREA] >= min_area
        if not keep.any():
            break
        skeleton = cv2.ximgproc.thinning(
            (keep[labels] * 255).astype(np.uint8),
            thinningType=cv2.ximgproc.THINNING_ZHANGSUEN)
        fresh = []
        for run in _trace_skeleton(skeleton > 0):
            line = [(c / w * mask.width_mm, (1 - r / h) * mask.height_mm) for r, c in run]
            line = simplify(line, tol=min(line_w * 0.25, 0.4))
            if len(line) > 1 and _length(line) >= line_w:
                fresh.append(line)
        if not fresh:
            break
        rescued.extend(fresh)
        for run in fresh:
            pts = np.array([[int(x / mask.width_mm * w), int((1 - y / mask.height_mm) * h)]
                            for x, y in run], np.int32)
            cv2.polylines(covered, [pts], False, 1, thickness=brush_px)
        covered = cv2.dilate(covered, np.ones((3, 3), np.uint8))

    if rescued and log:
        log(f"  {len(rescued)} centreline strokes for ink the outlines missed")
    return rescued


def first_stroke_point(path: Path) -> tuple[float, float] | None:
    """Where the first stroke of an adapted file begins, in canvas mm."""
    down = False
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if line == PEN_DOWN:
            down = True
            continue
        if down and _G1.match(line):
            words = dict(_WORD.findall(line))
            if "X" in words and "Y" in words:
                return float(words["X"]), float(words["Y"])
    return None


def last_stroke_point(path: Path) -> tuple[float, float] | None:
    """Where the last stroke of an adapted file ends, in canvas mm.

    The mirror of first_stroke_point, and wanted for the same kind of reason:
    a trip that ramps its Z across the bed has to be written from where the
    brush is actually standing, and at the end of a tray that is wherever the
    painting happened to finish — not the canvas origin the wash was being
    told about.
    """
    down = False
    last = None
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if line == PEN_DOWN:
            down = True
            continue
        if line == PEN_UP:
            down = False
            continue
        if down and _G1.match(line):
            words = dict(_WORD.findall(line))
            if "X" in words and "Y" in words:
                last = (float(words["X"]), float(words["Y"]))
    return last


def write_brush_paths(polys, dst: Path, log, line_w: float = 1.0,
                      mask: "InkMask | None" = None) -> int:
    """Chain, tidy and write paths in the pen-up/pen-down form copicograf reads.

    Takes paths from either source — the external slicer or the planar
    backend — so both get the same chaining, the same centreline rescue for
    shapes too thin to outline, and the same output format.
    """
    if mask is not None:
        polys = polys + centrelines_for_missed(mask, polys, line_w, log)
    if not polys:
        raise PipelineError("nothing to paint")

    raw_n = len(polys)
    raw_pts = sum(len(p) for p in polys)
    raw_len = sum(_length(p) for p in polys)
    # Two passes. The first rejoins runs the slicer split at a shared point.
    # The second bridges ends up to 1.5 line widths apart, turning adjacent fill
    # lines into one serpentine. Adjacent lines sit exactly one line width
    # apart, so 1.5x reaches the neighbour but not the one beyond it, and the
    # bridge stays inside the filled region rather than crossing bare paper.
    #
    # There is no gain in reaching further: copicograf re-inks every
    # paint_per_run (120-140 mm), so a longer stroke than that is split for a
    # dip regardless of how it was chained.
    polys = chain_polylines(polys, tol=max(line_w * 0.05, 0.02))
    # The bridge is only taken where the move between the two ends stays inside
    # the ink, so joining never draws across bare paper and the shape is
    # preserved exactly.
    polys = chain_polylines(polys, tol=line_w * BRIDGE_MULTIPLE,
                            permit=mask.segment_inside if mask else None)
    polys = [simplify(p, tol=min(line_w * 0.1, 0.15)) for p in polys]
    # A dab far shorter than the brush is wide is not a stroke; it is a blot,
    # and it costs a lift and a re-ink to place.
    polys = [p for p in polys if len(p) > 1 and _length(p) >= line_w * 0.5]
    if not polys:
        raise PipelineError("nothing left to paint after removing sub-brush-width fragments")

    polys = order_polylines(polys)
    lengths = sorted(_length(p) for p in polys)
    median = lengths[len(lengths) // 2]
    grew = (sum(lengths) - raw_len) / raw_len * 100 if raw_len else 0.0
    log(f"  strokes {raw_n} -> {len(polys)}, median {median:.1f} mm, "
        f"longest {lengths[-1]:.0f} mm, points {raw_pts} -> {sum(len(p) for p in polys)}, "
        f"paint {grew:+.1f}%")

    lines = ["; adapted for copicograf by the Brushograph WebUI"]
    for poly in polys:
        sx, sy = poly[0]
        lines.append(PEN_UP)
        lines.append(f"G1 X{sx:.3f} Y{sy:.3f}")
        lines.append(PEN_DOWN)
        # The start point again, on purpose. copicograf treats the first
        # coordinate after a pen-down marker as "go there, then lower", so
        # without repeating it the brush comes down at the *second* point and
        # the opening segment of every stroke is travelled dry. A stroke short
        # enough to be two points — which is what a thin shape's centreline
        # simplifies to — is then lost entirely.
        lines.append(f"G1 X{sx:.3f} Y{sy:.3f}")
        for px, py in poly[1:]:
            lines.append(f"G1 X{px:.3f} Y{py:.3f}")
    lines.append(PEN_UP)
    dst.write_text("\n".join(lines) + "\n")
    return len(polys)


# ------------------------------------------------------------------ controller

# M204 (set acceleration), M203 (set max feedrate) and M400 (wait for moves to
# finish) are Marlin commands. GRBL and FluidNC answer an unknown M-code with an
# error and stop executing, so leaving them in bricks the run on its first line.
MARLIN_ONLY = re.compile(r"^\s*M(204|203|400)\b", re.I)

# copicograf emits `G28 X Y` to home. Marlin reads bare axis words as "home
# these axes"; GRBL and FluidNC require a value after each word and reject the
# line outright ("Bad GCode number format"), which alarms the controller. Even
# written as `G28 X0 Y0` it would not home there — it rapids to the stored G28
# position, and homing is `$H`.
HOMING = re.compile(r"^\s*G0*28\b", re.I)


# What the prose in this repo is written with, and what a controller can be
# given instead. Anything not listed decomposes or becomes a question mark,
# which is visible in the file rather than silently dropped.
_FOR_MACHINE = str.maketrans({
    "\u2014": "--", "\u2013": "-", "\u2026": "...", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u00d7": "x", "\u00b0": " deg", "\u00b1": "+/-",
    "\u00a0": " ", "\u2212": "-",
})


def to_ascii(text: str) -> str:
    """Every byte the machine reads, inside ASCII.

    GRBL and FluidNC read any byte above 127 as a realtime command, and a
    sender streams a comment like any other line — so an em dash in a comment
    is not a typographical detail, it is a character the board acts on. The
    site URL in the header has been punycode for that reason since it was
    written; this is the same rule applied to everything else, at the one
    place where the text becomes a file.

    Applied at the end rather than by writing the comments differently in the
    first place, because the comments are prose and the repo writes prose with
    em dashes: the fault was not that someone typed one, it was that nothing
    stood between what was typed and what the machine was sent. A figure taken
    from a config can carry anything at all, which is the other half of it.

    Punctuation this repo uses is translated, the rest is decomposed the way
    NFKD does it — which turns the 𝔐𝔦𝔨𝔯𝔬's own name into Mikro — and whatever
    survives that becomes a question mark. A question mark in a comment is
    wrong and looks wrong, which is the right way round for something nobody
    has thought about yet.
    """
    decomposed = unicodedata.normalize("NFKD", text.translate(_FOR_MACHINE))
    # NFKD splits an accented letter into a letter and a combining mark, and
    # the mark has no ASCII to become. Dropping it leaves the letter, where
    # keeping it would put a question mark in the middle of a word: naive, not
    # nai?ve.
    return ("".join(c for c in decomposed if unicodedata.category(c) != "Mn")
            .encode("ascii", "replace").decode("ascii"))


def sanitize_for_controller(lines: list[str], controller: str) -> tuple[list[str], int]:
    """Drop commands the target controller cannot parse.

    copicograf takes the acceleration and feedrate lines straight from the
    config's `moves` blocks, which are written for Marlin. Only Marlin gets to
    keep them; the G0 F… feedrate in each block is understood everywhere and
    survives either way.
    """
    if controller.strip().lower() == "marlin":
        return lines, 0
    kept = []
    dropped = 0
    for ln in lines:
        if MARLIN_ONLY.match(ln):
            dropped += 1
            continue
        if HOMING.match(ln):
            # Not rewritten to `$H`: that needs limit switches, and a machine
            # without them is zeroed where it stands (FluidNC's startup_line0
            # `G10 P0 L20 …` idiom). Homing is left to the operator.
            kept.append("; homing removed for " + controller + " - home or zero the machine first")
            dropped += 1
            continue
        kept.append(ln)
    return kept, dropped


def start_sequence(conf: dict) -> list[str]:
    """Put the machine in a known state before anything moves.

    copicograf emits its G90/G21 only after the first acceleration line, so a
    controller that rejects that line never reaches them. Stating the units and
    positioning mode first, then lifting Z, means the first real move is safe.
    """
    bg = conf.get("brushograph", {})

    def num(key, default=0.0):
        try:
            return float(bg.get(key, default))
        except (TypeError, ValueError):
            return default

    # The height the machine already treats as safe for crossing the bed.
    safe_z = max(num("go_in_tray_lift", 10),
                 num("move_to_other_shape_lift") + num("canvas_height"))
    feed = "G0 F1000"
    moves = bg.get("moves", {})
    if isinstance(moves, dict):
        normal = moves.get("normal", {})
        if isinstance(normal, dict) and str(normal.get("feedrate_1", "")).strip():
            # The box holds millimetres a minute; the G-code goes round it here.
            feed = feed_line(normal["feedrate_1"])
    return [
        "G90 ; Absolute positioning",
        "G21 ; Millimeters",
        "G90",
        "G21",
        feed,
        f"G00 Z{safe_z:g}",
    ]


# --------------------------------------------------------------------- backlash

# What counts as a change of direction, from openBrushograph Studio. A wobble of
# a fraction of a step is not a reversal, and spending the whole take-up on one
# moves the brush further than the move that asked for it. On a job out of this
# pipeline it is nearly free — 148 take-ups against 149 at 1e-9, because
# planar's SIMPLIFY_PX has already dropped the moves that small — so it is
# insurance rather than a saving, and it costs nothing to carry. Anything the
# machine does is repeatable to worse than this.
BACKLASH_THRESHOLD = 0.05

# How far the shift is allowed to drift from the last figure stated in the file
# before it is stated again. Only the preview reads those notes, and only to
# subtract them: a twentieth of a millimetre is a twentieth of a brush stroke
# and well under a pixel at preview scale. A play that changes across the bed
# changes the shift on nearly every move, and stating every change costs 251
# notes on a two-tray job where this costs 123 — 42 KB against 38. Measured at
# 0.2 mm it is 37 notes, which is 2 KB saved for an error a fifth of a stroke
# wide, so this is the end of the curve worth being on.
BACKLASH_SHIFT_STEP = 0.05


def _figure(bg: dict, key: str, fallback: float = 0.0) -> float:
    """One backlash figure out of the config, however it got written there.

    A config is a file people edit, and a figure that is missing, blank or not
    a number is the same thing here: nothing was read off the sheet for it.
    """
    value = bg.get(key)
    if value is None or value == "":
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _coord(value: float) -> str:
    """A coordinate written the way the rest of the file writes them."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _rewrite(line: str, values: dict[str, float]) -> str:
    """Replace named axis words in one move, leaving everything else alone."""
    body, sep, comment = line.partition(";")

    def sub(match: re.Match) -> str:
        axis = match.group(1)
        return axis + _coord(values[axis]) if axis in values else match.group(0)

    return _WORD.sub(sub, body) + sep + comment


def _play_across_x(near: float, far: float | None,
                   span: tuple[float, float] | None):
    """The play at a given X, as a straight line across the axis.

    Two figures and a straight line between them, because two figures are what
    a sheet can be read for and a straight line is what the fault is: the play
    that changes across the bed is the gantry skewing, and a skew held at one
    end and free at the other grows with the distance from the driven side.
    Outside the span it is held at the end figure rather than extrapolated —
    the containers sit past the canvas on some machines, and a line drawn
    through two readings has nothing to say about ground neither was taken on.

    One figure, or two the same, gives a constant: the function is then exactly
    what the single figure always was, and the file comes out byte for byte
    what it did before any of this.
    """
    lo, hi = span if span else (0.0, 0.0)
    if far is None or hi - lo < 1e-9 or abs(far - near) < 1e-9:
        return lambda _x: near

    def at(x: float) -> float:
        return near + (far - near) * min(max((x - lo) / (hi - lo), 0.0), 1.0)

    return at


def apply_backlash(lines: list[str], bx: float, by: float,
                   x_range: tuple[float, float] | None = None,
                   y_range: tuple[float, float] | None = None,
                   bx_far: float | None = None,
                   by_far: float | None = None,
                   play_range: tuple[float, float] | None = None) -> list[str]:
    """Command the machine where the brush has to be, not where the path is.

    An axis with slack in it carries the brush ahead of the commanded position
    by the backlash figure, on the side it was last travelling from: drive left
    to X40 having come from the right and the brush stops at X40.5, because the
    first half millimetre of the move only moved the nut across its own play.
    So the file is written in the axis's terms rather than the path's. While
    the axis travels left every coordinate is written half a millimetre low,
    while it travels right they are written as they are, and at each reversal a
    move between the two is inserted — half a millimetre of commanded motion
    that the slack swallows whole and the brush does not follow.

    This is openBrushograph Studio's scheme, and the sign of it is the point.
    What was here before moved the brush half a millimetre *past* every corner,
    the way it had been going, and left every coordinate after it alone: the
    corner was overshot and then missed by exactly as much as it would have
    been missed with no compensation at all. Simulated against a lost-motion
    axis over 10 -> 50 -> 40 -> 60 -> 20 at 0.5 mm of play, it carried the brush
    out to 50.5 and 60.5 as tails past the corners and then landed those corners
    at 40.5 and 20.5, which is where no compensation at all puts them, to the
    micron. A small job makes about 140 reversals. This lands all five on the
    number — but only if the figure is right: it is the coordinates that move
    now, so an over-estimate costs what an under-estimate of the same size does.

    Because the shift is only ever downwards, the compensated file never
    reaches past the far end of an axis. That end is where it hurt: leaving the
    black crucible, which on Pinkograph sits at X 156 with the axis ending
    there, the old take-up asked for X 156.5 and the carriage found the stop
    instead, and what it lost there it did not get back — every move after it
    landed short by as much, which on a file that paints black last was the
    whole black plate. `x_range` remains as the floor under the other end,
    where a coordinate written low could ask for less than zero.

    `y_range` is that floor for the other axis, and it was missing until the
    play in Y was being compensated on a machine that parks at Y 0: the park
    at the end of a job was written to Y -0.5 and finished against the stop.
    Only the floor of either can bite, since the shift is downwards only --
    which is why the ceiling passed for Y is infinite rather than the travel.
    A ceiling there would be a figure that silently squashes the top of a
    painting on any config whose canvas is taller than its travel limit says,
    and a painting quietly shortened is worse than one that does not fit.

    `bx_far` and `by_far` are the same two figures read at the far end of X,
    and they make the play a function of where the brush is rather than a
    number. Pinkograph's sheet reads 1.9 mm of X play at the X0 end of the
    paper and 1.3 at the other, and 1.3 falling to 1.2 in Y: it is the X axis
    that changes across this bed, and Y that is near enough one figure. No
    single figure fits the first — the best one is the mean, and it is 0.3 mm
    out at each end, a third of a brush stroke and enough to stop the plates
    registering with each other.

    Both axes are written for the play at the X each coordinate is going to,
    rather than for the play crossed at the last reversal, and this is the one
    place this differs from a fix that only inserts moves. Neither axis's play
    is something the machine carries away from the reversal and keeps. Y is the
    gantry beam, driven from one side: a Y play that changes along X is the beam
    racking, and how much of the twist reaches the brush is a matter of where
    the carriage is standing, changing continuously as X moves with no reversal
    anywhere. X is the carriage running along that beam, where the lost motion
    is the slack and the stretch of the belt between the drive and the carriage
    — which is also a matter of position, since it is the free length that
    changes. Either way the offset follows the carriage rather than staying at
    whatever the reversal left, and a coordinate written for its own X is what
    lands the brush on the path.

    Simulated both ways to be sure, on a play larger at the X0 end and against
    a lost-motion axis modelled as a local clearance and then as an offset the
    drive keeps: identical to the micron, because both let the offset grow to
    the play where the carriage is while it travels towards the wider end and
    both hold it at zero coming back. Freezing the figure at the reversal
    instead was measurably worse on the same job — 0.076 mm of mean X error
    against 0.019, and a fifth of the painted points out by more than 0.1 mm
    against a fifteenth.

    Writing each coordinate for its own X is also exact along a stroke and not
    only at its ends: the model is a straight line in X, a G1 is a straight
    line in X, so compensating the two endpoints compensates every point
    between them. An axis given equal figures is a constant again, and none of
    this shows.

    The take-up moves are untouched by any of it. They cross the slack, and
    slack is crossed only at a reversal; the drift between reversals is the
    belt and the beam following the carriage, which the coordinates carry.
    """
    out: list[str] = []
    x = y = None            # where the path last asked the brush to be
    cmd_x = cmd_y = None    # what was last written to get it there
    dir_x = dir_y = 0
    said_x = said_y = 0.0   # the shift the file last stated
    # The two figures are the two ends of the *painting*, not of the axis:
    # they are read off a sheet, the sheet is painted on the paper, and a line
    # drawn through two readings says nothing about the ground past them. So
    # the containers, which on Pinkograph stand at X 156 to the canvas's 132,
    # are compensated with the figure for the end of the paper rather than one
    # extrapolated a fifth of the way further out. Nothing is painted there.
    span = play_range if play_range is not None else x_range
    play_x = _play_across_x(bx, bx_far, span)
    play_y = _play_across_x(by, by_far, span)

    def clamp_x(value: float) -> float:
        if x_range is None:
            return value
        return min(max(value, x_range[0]), x_range[1])

    def clamp_y(value: float) -> float:
        if y_range is None:
            return value
        return min(max(value, y_range[0]), y_range[1])

    for line in lines:
        body = line.split(";", 1)[0].strip()
        if not (_G1.match(body) or _G0.match(body)):
            out.append(line)
            continue
        words = dict(_WORD.findall(body))
        nx = float(words["X"]) if "X" in words else x
        ny = float(words["Y"]) if "Y" in words else y

        # The move that seats the nut on its other face. Both axes reversing at
        # once share one, as they share the move that follows. The play crossed
        # by a take-up is the play where the brush is standing, not where it is
        # going: the slack is taken up before the move proper begins.
        seat: dict[str, float] = {}
        if x is not None and nx is not None and abs(nx - x) > BACKLASH_THRESHOLD:
            d = 1 if nx > x else -1
            if d != dir_x:
                reversal = dir_x != 0
                dir_x = d
                here = play_x(x)
                # Nothing to seat on the first move of the file: the side the
                # nut is resting on is not knowable, and the brush is up.
                if reversal and here:
                    at = clamp_x(x if d > 0 else x - here)
                    if cmd_x is None or abs(at - cmd_x) > 1e-9:
                        seat["X"] = at
        if y is not None and ny is not None and abs(ny - y) > BACKLASH_THRESHOLD:
            d = 1 if ny > y else -1
            if d != dir_y:
                reversal = dir_y != 0
                dir_y = d
                here = play_y(x if x is not None else 0.0)
                if reversal and here:
                    at = clamp_y(y if d > 0 else y - here)
                    if cmd_y is None or abs(at - cmd_y) > 1e-9:
                        seat["Y"] = at

        # What these coordinates are written low by, each for the play at the X
        # they are going to. An axis that has not settled on a direction yet is
        # not shifted at all.
        going = nx if nx is not None else 0.0
        off_x = -play_x(going) if dir_x < 0 else 0.0
        off_y = -play_y(going) if dir_y < 0 else 0.0

        # The shift now in force, written into the file where it changes. The
        # preview has to undo it to draw the path that was asked for, and
        # working it out from the take-up moves alone does not survive the
        # clamp: a take-up cut short at the end of an axis reports a smaller
        # step than the shift really took, and a reader adding those steps up
        # carries that error to the end of the file. Stated outright it is
        # exact, it costs a few characters a reversal, and a controller reads
        # none of it.
        shift = f", shift X{_coord(off_x)} Y{_coord(off_y)}"
        if seat:
            # No feedrate of its own: Studio sends these at a slow one, but F
            # is modal and it never puts the old one back, so every move after
            # a reversal crawls until something sets F again. At the prevailing
            # feed the move is over in the time it takes to cross the slack.
            out.append("G1 " + " ".join(f"{a}{_coord(v)}" for a, v in sorted(seat.items()))
                       + " ; backlash take-up" + shift)
            cmd_x = seat.get("X", cmd_x)
            cmd_y = seat.get("Y", cmd_y)
            said_x, said_y = off_x, off_y
        elif (abs(off_x - said_x) > BACKLASH_SHIFT_STEP
              or abs(off_y - said_y) > BACKLASH_SHIFT_STEP):
            # The shift changed with no move to carry the note. That is the
            # first time an axis settles on a direction, where there is nothing
            # to seat because which face the nut is resting on is not knowable;
            # and it is every BACKLASH_SHIFT_STEP of drift while a play that
            # changes across the bed is followed across it. The coordinates are
            # shifted either way, so the note goes on a line of its own rather
            # than leaving the preview a step behind.
            out.append("; backlash" + shift)
            said_x, said_y = off_x, off_y

        shifted: dict[str, float] = {}
        if "X" in words and nx is not None:
            cmd_x = clamp_x(nx + off_x)
            if abs(cmd_x - nx) > 1e-9:
                shifted["X"] = cmd_x
        if "Y" in words and ny is not None:
            cmd_y = clamp_y(ny + off_y)
            if abs(cmd_y - ny) > 1e-9:
                shifted["Y"] = cmd_y
        out.append(_rewrite(line, shifted) if shifted else line)
        x, y = nx, ny
    return out


# ------------------------------------------------------------------- the driver

def generate(conf: dict, images: dict[str, Path], workdir: Path, out_path: Path, log) -> dict:
    """Run every tray that has an image, then stitch one G-code file."""
    generator = conf.get("brushograph", {}).get("generator")
    if generator and generator != "copicograf":
        raise PipelineError(
            f"this config asks for the '{generator}' generator, which is not part of this "
            "repository — only the default copicograf generator can be built here."
        )

    from copicograf import Copicograf, dip_lanes  # imported late: needs the repo on sys.path

    bg = conf.get("brushograph", {})
    width_mm = float(bg.get("width", 100))
    height_mm = float(bg.get("height", 100))
    # Checked here rather than left to fail somewhere further in. Every scale in
    # the pipeline is pixels over millimetres, so a painted side of zero is a
    # division by zero several calls deep -- which reaches the page as a 500 and
    # a traceback rather than as the one sentence that would fix it. A negative
    # side does not even fail: it flips the picture and paints it off the bed,
    # which is worse, because it looks like it worked.
    if width_mm <= 0 or height_mm <= 0:
        raise PipelineError(
            f"the painted size is {_mm_size(width_mm)} x {_mm_size(height_mm)} mm: "
            f"both sides have to be more than nothing before anything can be "
            f"painted at them")

    # And held off the far end of each axis. Max Width and Max Height are where
    # the machine stops, and a painting that runs to one of them is a painting
    # that ends on the endstop -- a photograph at full size on Brushparang put
    # 142 strokes at exactly Y 140 against a Max Height of exactly 140, and the
    # machine hit the upper Y stop. Scaled rather than cropped, and both sides
    # by the same amount, so what comes out is the picture and not a squashed
    # one; said out loud, because a painting that is not the size that was
    # asked for is a thing to know about before the paper goes on.
    room_w, room_h = paintable_size(conf)
    fit = min(1.0, room_w / width_mm, room_h / height_mm)
    if fit < 1.0:
        was = (width_mm, height_mm)
        width_mm, height_mm = width_mm * fit, height_mm * fit
        log(f"painted size brought in to {width_mm:.1f} x {height_mm:.1f} mm from "
            f"{was[0]:g} x {was[1]:g}: the canvas starts at "
            f"({canvas_origin(conf)[0]:g}, {canvas_origin(conf)[1]:g}) and the travel "
            f"ends at {_figure(bg, 'max_width'):g} x {_figure(bg, 'max_height'):g}, "
            f"and a painting keeps {EDGE_HEADROOM:g} mm off that -- the far end of an "
            f"axis is where the endstop is")
    slicer_conf = conf.get("slicer", {})

    # infill_line_distance is the gap between brush strokes, which is to say
    # the width of the stroke the brush lays down.
    try:
        requested = float(slicer_conf.get("infill_line_distance", 1))
    except (TypeError, ValueError):
        requested = 1.0
    # Zero means draw the outlines and leave the shapes unfilled. The brush
    # still has a width, and the perimeter and the woodcut's finest mark are
    # both measured in it, so a nominal one stands in — the config offers no
    # other figure to take it from.
    infill = requested > 0
    line_w = min(max(requested, 0.05), 20.0) if infill else NOMINAL_BRUSH_MM

    if not infill:
        log(f"infill off (line distance 0): outlines only, "
            f"{NOMINAL_BRUSH_MM:g} mm nominal stroke width")

    want = str(slicer_conf.get("infill_pattern", FALLBACK_PATTERN)).strip().lower()
    pattern = planar.PATTERNS.get(want, planar.FALLBACK_PATTERN)
    if want not in planar.PATTERNS:
        log(f"unknown infill pattern {want!r} — using {pattern}")

    entries = [e for e in tray_entries(conf) if e["image"]]
    todo = [e for e in entries if e["tray"] in images]
    if not todo:
        raise PipelineError("no thresholded images were uploaded for any tray in color_order")

    # gcodes=[] on purpose: Copicograf's default argument is a shared mutable
    # list, so leaving it out would append this run onto the previous one.
    copicograf = Copicograf(conf=conf, gcodes=[])
    # copicograf knows the Mini's holder only; the swipe and the lanes the
    # dips are spread over fit the model's.
    holder = holder_of(conf)
    copicograf.cup_depth = holder["swipe_length"]
    copicograf.cup_width = holder["bay_width"]
    copicograf.water_cup_width = holder["water_bay_width"]
    # The lanes are held inside the ground a job already covers — the
    # containers and the canvas — not the axis travel. Backlash compensation
    # writes every coordinate low by up to the take-up while the axis travels
    # left, so the near end keeps off the endstop by that much. The far end
    # needs nothing: the compensated file never asks for more X than the path
    # did.
    # The largest of the X figures, not the near one: the play is read at both
    # ends of the axis now, and the floor has to hold against whichever end the
    # cup happens to be at.
    take_up = max(_figure(bg, "backlash_x"),
                  _figure(bg, "backlash_x_far")) if bg.get("backlash_compensation", True) else 0.0
    copicograf.x_limits = (take_up, workable_x(conf))
    # And the same floor under Y, for the same reason and a worse symptom. A
    # bay is deeper than the strip of Y it stands in on more than one machine:
    # Brushparang's cups sit at Y -3 and their 30 mm bays put the deep end at
    # Y -13.5, which is not ground, it is the stop. Every dip drove into it,
    # the axis stalled while the counter carried on, and the file's coordinates
    # were from then on that much below where the carriage actually was -- so
    # what a crashed dip at the bottom of the bed shows up as is the far end of
    # the canvas hitting the *top* stop. On that config it is 11 mm of shift
    # into a canvas whose top edge, at Y 140, is the travel limit exactly.
    copicograf.y_floor = (max(_figure(bg, "backlash_y"), _figure(bg, "backlash_y_far"))
                          if bg.get("backlash_compensation", True) else 0.0)
    # A crucible near either end of the axis has less room across it than the
    # bay is wide, so the dips cannot spread over the whole of it: the lanes
    # stay centred on the cup and give up the same distance on each side,
    # going short rather than lopsided. Worth saying, because the G-code just
    # has its dips closer together and the paint mixes less.
    if cup_shape_of(conf) in RECTANGULAR_SHAPES and copicograf.cup_dip_lanes > 1:
        for name, tray in sorted(conf.get("trays", {}).items()):
            if not isinstance(tray, dict) or "x" not in tray:
                continue
            x = float(tray["x"])
            width = (holder["water_bay_width"] if name == "water"
                     else holder["bay_width"])
            # 70% of the width, which is what the lanes get when nothing is
            # in the way: 15% of the bay off each wall, as the swipe leaves
            # off its own ends.
            full = width * 0.7
            lanes = dip_lanes(x, width, copicograf.cup_dip_lanes, copicograf.x_limits)
            spread = max(lanes) - min(lanes)
            if len(lanes) == 1:
                log(f"[{name}] no room to spread the dips at X {x:g} — every one "
                    f"of them down the middle: the crucible is the outermost "
                    f"thing the machine goes to")
            elif spread < full - 0.05:
                log(f"[{name}] dips spread over {spread:.1f} mm of {full:.1f} — "
                    f"X {x:g} leaves the bay short of the ground a job covers")
    # The round-cup figures are optional in copicograf, because a machine with
    # no petri dish holder should not have to carry figures describing one --
    # the Mikro has none, and demanding them made a freshly created Mikro
    # config fail every run before anything was painted. On a machine that
    # does use round cups, though, a missing one is not a machine without
    # dishes, it is a figure nobody filled in: the sweep or the rim wipe
    # silently becomes a move to the middle of the cup, which is where the
    # brush already is. Cheap to say, and impossible to see in the G-code,
    # where it shows up as a move that is simply not there.
    if cup_shape_of(conf) not in RECTANGULAR_SHAPES:
        blank = [key for key in ("tray_enter_radius", "remove_drops_radius",
                                 "remove_drops_lift")
                 if bg.get(key) in (None, "")]
        if blank:
            log(f"round cups, but {', '.join(blank)} not set — taken as 0: "
                f"the brush dips without sweeping the paint or wiping the rim")

    # And the same again down the length of a bay. The brush enters at the deep
    # end and walks up the stairs to the back; where the deep end is south of
    # the bed, it enters further back and the swipe is shorter by what was
    # clipped. Said out loud because the G-code shows only a shorter move: the
    # brush is working less of the bay, so it loads with less paint, and the
    # reason is a container position, which is a thing in the form that can be
    # corrected.
    #
    # Reported once per distinct Y and not once per cup. Every holder is one
    # straight row, so all five share a figure and five copies of one sentence
    # is a log nobody reads to the end.
    if cup_shape_of(conf) in RECTANGULAR_SHAPES:
        depth = holder["swipe_length"]
        margin = depth * 0.15
        rows: dict[float, list[str]] = {}
        for name, tray in sorted(conf.get("trays", {}).items()):
            if isinstance(tray, dict) and "x" in tray:
                rows.setdefault(float(tray.get("y", 0)), []).append(name)
        for y, names in sorted(rows.items()):
            who = ", ".join(names)
            entry_y = y - depth / 2 + margin
            bay0, bay1 = y - depth / 2, y + depth / 2
            if entry_y < copicograf.y_floor - 1e-9:
                full = depth - 2 * margin
                left = max(0.0, bay1 - margin - copicograf.y_floor)
                log(f"[{who}] bay entered {copicograf.y_floor - entry_y:.1f} mm short at "
                    f"Y {y:g}: the deep end is off the bed, so the swipe is "
                    f"{left:.1f} mm of {full:.1f} and the brush loads with less")

    # Where the containers end and the painting begins. Canvas Start Y says
    # where the paintable area starts; the cups say where they actually reach,
    # which is the back of a bay or the rim of a dish. A canvas that starts
    # inside that is a painting laid over the holder: the brush comes down on
    # a crucible wall rather than on paper, and the G-code cannot show it,
    # because both figures are perfectly ordinary numbers on their own.
    origin_y = canvas_origin(conf)[1]
    # How far back the holder really stands, which is not how far the brush
    # goes into it: a design holder is a plate the crucibles sit in, and the
    # plate is the thing the paper would be laid over. Its depth is known from
    # where the water crucible sits in it. A custom holder is nobody's design
    # and has no plate, so its bays are all there is to go on, and a dish is
    # its rim.
    if cup_shape_of(conf) in RECTANGULAR_SHAPES:
        plate = holder["plate"]
        water = conf.get("trays", {}).get("water")
        if plate and isinstance(water, dict) and "y" in water:
            _pw, depth, _wx, wy_in = plate
            backs = [float(water["y"]) - wy_in + depth]
        else:
            backs = [float(tray["y"]) + holder["swipe_length"] / 2
                     for tray in conf.get("trays", {}).values()
                     if isinstance(tray, dict) and "y" in tray]
    else:
        backs = [float(tray["y"]) + CLASSIC_DISH_RIM_RADIUS
                 for name, tray in conf.get("trays", {}).items()
                 if isinstance(tray, dict) and "y" in tray
                 and name in {e["tray"] for e in tray_entries(conf)}]
    if backs and origin_y < max(backs) - 1e-9:
        log(f"the canvas starts at Y {origin_y:g}, {max(backs) - origin_y:.1f} mm inside "
            f"the containers, which reach Y {max(backs):.1f} — raise Canvas Start Y or "
            f"move the holder forward")

    stats = {"trays": [], "strokes": 0}

    def prepare(entry):
        """Everything for one tray up to, but not including, the choreography.

        Trays are independent here: each writes its own files, and the work is
        OpenCV, which drops the GIL. Log lines are collected rather than
        emitted, so a parallel run still reads in tray order once the results
        are stitched back together.
        """
        lines: list[str] = []
        log = lines.append

        tray = entry["tray"]
        log(f"[{tray}] tracing")
        src = images[tray]
        pbm = workdir / f"threshold_{tray}.pbm"
        adapted = workdir / f"threshold_{tray}_adapted.gcode"

        _w_px, _h_px, ink = to_pbm(src, pbm, log)
        ink = _enlarge_for_brush(ink, width_mm, line_w, log)
        canvas = InkMask(ink, width_mm, height_mm)

        paths = planar.build(ink, width_mm, height_mm, line_w,
                             pattern=pattern,
                             infill=infill,
                             perimeters=int(float(slicer_conf.get("wall_line_count", 1) or 1)),
                             log=log)
        try:
            n = write_brush_paths(paths, adapted, log, line_w=line_w, mask=canvas)
        except PipelineError:
            # Nothing on this plate survives at this size with this stroke.
            # Not the run's problem to die of: it is one tray of several, and
            # the others may be covered in ink. Reported and skipped here, and
            # only if *every* tray comes back like this does the run stop --
            # with a message that says which lever to pull.
            log(f"[{tray}] nothing to paint at {_mm_size(width_mm)} x "
                f"{_mm_size(height_mm)} mm with a {line_w:g} mm stroke: every shape "
                f"on this plate is finer than one stroke. Skipped")
            return None, 0, lines
        return adapted, n, lines

    # Preparation runs in parallel; the choreography does not. copicograf
    # appends into one list, and the order it is appended in is the order the
    # machine paints, so that stays sequential and in color_order.
    if len(todo) > 1:
        with ThreadPoolExecutor(max_workers=min(len(todo), os.cpu_count() or 1)) as pool:
            prepared = list(pool.map(prepare, todo))
    else:
        prepared = [prepare(todo[0])]

    # The trays that came back with something on them. A tray whose shapes are
    # all finer than a stroke has already said so in its own log lines; what is
    # left here is the painting order minus those.
    for entry, (adapted, _n, lines) in zip(todo, prepared):
        if adapted is None:
            for line in lines:
                log(line)
    kept = [(e, r) for e, r in zip(todo, prepared) if r[0] is not None]
    if not kept:
        raise PipelineError(
            f"nothing to paint: at {_mm_size(width_mm)} x {_mm_size(height_mm)} mm "
            f"every shape in every picture is finer than the {line_w:g} mm stroke the "
            f"brush lays down. Paint it larger, or set a narrower stroke width under "
            f"Infill line distance")
    todo, prepared = [e for e, _ in kept], [r for _, r in kept]

    for i, (entry, (adapted, n, lines)) in enumerate(zip(todo, prepared)):
        for line in lines:
            log(line)
        tray = entry["tray"]
        # Every tray starts by loading the brush. copicograf ends each tray by
        # washing the brush and parking it in the water, so a colour change
        # leaves it clean and wet — and it only re-inks once paint_per_run has
        # been laid down, so without this the opening strokes of each colour
        # would be painted with water. The trip ends at the point that colour's
        # painting starts from, so it leaves no mark of its own.
        pickup_at = first_stroke_point(adapted)
        if pickup_at:
            log(f"[{tray}] loading the brush before the first stroke at "
                f"({pickup_at[0]:.1f}, {pickup_at[1]:.1f})")
        # A marker before each tray's block, so a reader — the preview, or a
        # person — can tell which colour is being laid down where.
        copicograf.gcodes.append(f"; tray {tray}")
        # The brush is left standing in the water when the job is over, so it
        # does not dry with paint in it. Between colours there is no point: it
        # is already over the water from the wash, and the next thing it does is
        # go for the next colour.
        # Where this tray's painting ends, so the wash that follows it can
        # climb to the water on the way there instead of standing still to
        # lift and then flying the bed level.
        copicograf.prepare_path(str(adapted), float(entry["x"]), float(entry["y"]),
                                calibrate=False, pickup_at=pickup_at,
                                park=(i == len(todo) - 1),
                                wash_from=last_stroke_point(adapted))
        stats["trays"].append({"tray": tray, "color": entry["color"], "strokes": n})
        stats["strokes"] += n

    copicograf.save_gcode(str(out_path))

    lines = out_path.read_text().splitlines()

    # Absent controller_type, assume the stricter dialect: emitting Marlin-only
    # codes to a GRBL board halts it, while dropping them costs a Marlin board
    # only its acceleration tuning.
    controller = str(conf.get("controller", {}).get("controller_type") or "GRBL")
    lines, dropped = sanitize_for_controller(lines, controller)
    if dropped:
        log(f"{controller}: dropped {dropped} Marlin-only lines (M204/M203/M400/G28)")
    stats["dropped_marlin_lines"] = dropped
    stats["controller"] = controller

    # On unless the config turns it off. A config carrying no backlash figures
    # at all still passes through here, but compensating by zero is a no-op.
    if bg.get("backlash_compensation", True):
        before = len(lines)
        span = (0.0, workable_x(conf))
        # A config that names no far figure has one play, the way every config
        # did before the play was found to change across the bed.
        near_x, near_y = _figure(bg, "backlash_x"), _figure(bg, "backlash_y")
        far_x = _figure(bg, "backlash_x_far", near_x)
        far_y = _figure(bg, "backlash_y_far", near_y)
        # Where the two figures were read: the ends of the painting, which is
        # where backlash.g draws the sheet they come off.
        paper = (float(bg.get("offset_x", 0) or 0),
                 float(bg.get("offset_x", 0) or 0) + width_mm)
        lines = apply_backlash(lines, near_x, near_y, x_range=span,
                               y_range=(0.0, float("inf")),
                               bx_far=far_x, by_far=far_y, play_range=paper)
        moves = sum(1 for line in lines if "; backlash take-up" in line)
        log(f"backlash compensation: {moves} corrective moves, "
            f"+{len(lines) - before} lines")
        for axis, near, far in (("X", near_x, far_x), ("Y", near_y, far_y)):
            if abs(far - near) > 1e-9:
                log(f"backlash {axis}: {near:g} mm at X{paper[0]:g} to {far:g} at "
                    f"X{paper[1]:g}, straight between, held either side")

    header = [
        gcode_note(),
        f"; Trays: {', '.join(t['tray'] for t in stats['trays'])}",
        f"; Image area: {width_mm:g} x {height_mm:g} mm",
    ]
    out_path.write_text(to_ascii("\n".join(header + start_sequence(conf) + lines)) + "\n")
    stats["infill"] = infill
    stats["lines"] = len(lines) + len(header)
    stats["bytes"] = out_path.stat().st_size
    log(f"wrote {out_path.name}: {stats['lines']} lines, {stats['bytes'] / 1024:.0f} KB")
    return stats
