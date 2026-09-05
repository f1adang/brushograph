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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import planar

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from configspec import CMYK_TO_TRAY, tray_entries  # noqa: E402

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
        rgb = im.convert("RGB")
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
            kept.append("; homing removed for " + controller + " — home or zero the machine first")
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
            feed = str(normal["feedrate_1"]).strip()
    return [
        "G90 ; Absolute positioning",
        "G21 ; Millimeters",
        "G90",
        "G21",
        feed,
        f"G00 Z{safe_z:g}",
    ]


# --------------------------------------------------------------------- backlash

def apply_backlash(lines: list[str], bx: float, by: float) -> list[str]:
    """Insert a corrective move whenever an axis reverses direction.

    On a reversal the axis first has to take up its own slack, so the commanded
    distance is short by the backlash figure. Overshooting by that amount and
    coming back puts the head where the path asked for.
    """
    out: list[str] = []
    x = y = None
    dir_x = dir_y = 0
    for line in lines:
        body = line.split(";", 1)[0].strip()
        if not (_G1.match(body) or _G0.match(body)):
            out.append(line)
            continue
        words = dict(_WORD.findall(body))
        nx = float(words["X"]) if "X" in words else x
        ny = float(words["Y"]) if "Y" in words else y
        cx = cy = None
        if x is not None and nx is not None and abs(nx - x) > 1e-9:
            d = 1 if nx > x else -1
            if dir_x and d != dir_x and bx:
                cx = x - d * bx
            dir_x = d
        if y is not None and ny is not None and abs(ny - y) > 1e-9:
            d = 1 if ny > y else -1
            if dir_y and d != dir_y and by:
                cy = y - d * by
            dir_y = d
        if cx is not None or cy is not None:
            parts = ["G1"]
            if cx is not None:
                parts.append(f"X{cx:.3f}")
            if cy is not None:
                parts.append(f"Y{cy:.3f}")
            out.append(" ".join(parts) + " ; backlash take-up")
        out.append(line)
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

    from copicograf import Copicograf  # imported late: needs the repo on sys.path

    bg = conf.get("brushograph", {})
    width_mm = float(bg.get("width", 100))
    height_mm = float(bg.get("height", 100))
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
        n = write_brush_paths(paths, adapted, log, line_w=line_w, mask=canvas)
        return adapted, n, lines

    # Preparation runs in parallel; the choreography does not. copicograf
    # appends into one list, and the order it is appended in is the order the
    # machine paints, so that stays sequential and in color_order.
    if len(todo) > 1:
        with ThreadPoolExecutor(max_workers=min(len(todo), os.cpu_count() or 1)) as pool:
            prepared = list(pool.map(prepare, todo))
    else:
        prepared = [prepare(todo[0])]

    for entry, (adapted, n, lines) in zip(todo, prepared):
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
        copicograf.prepare_path(str(adapted), float(entry["x"]), float(entry["y"]),
                                calibrate=False, pickup_at=pickup_at)
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
        lines = apply_backlash(lines, float(bg.get("backlash_x", 0)), float(bg.get("backlash_y", 0)))
        log(f"backlash compensation: +{len(lines) - before} corrective moves")

    header = [
        "; Brushograph WebUI",
        f"; controller: {controller}",
        f"; trays: {', '.join(t['tray'] for t in stats['trays'])}",
        f"; image area: {width_mm:g} x {height_mm:g} mm",
    ]
    out_path.write_text("\n".join(header + start_sequence(conf) + lines) + "\n")
    stats["infill"] = infill
    stats["lines"] = len(lines) + len(header)
    stats["bytes"] = out_path.stat().st_size
    log(f"wrote {out_path.name}: {stats['lines']} lines, {stats['bytes'] / 1024:.0f} KB")
    return stats
