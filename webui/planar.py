#!/usr/bin/python3
"""Turn a bitmap into brush paths directly, without a trip through 3D.

The old chain traced the bitmap to vectors, extruded those to a solid, and
sliced the solid back to 2D paths, using potrace, OpenSCAD and PrusaSlicer to
do it. Everything it produced — an outline inset by half a stroke, and a fill
inside that — is a planar operation, so it is done here as one.

The trick is the distance transform. Every pixel is labelled with its distance
to the nearest bare paper, and then an outline inset by d is simply the contour
of "at least d from the edge". A concentric fill is the same thing at
d = w/2, 3w/2, 5w/2 …, so the whole fill falls out of one distance transform
plus a threshold per ring — and because the rings do not depend on each other,
they are drawn in parallel.

Offsetting the polygons one at a time instead, as this first did, is both
slower and stubbornly serial: in a real picture a single connected shape is
95% of the work, so no amount of splitting by shape helps.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

PATTERNS = {
    "concentric": "concentric",
    "archimedeanchords": "concentric",
    "hilbertcurve": "concentric",
    "gyroid": "concentric",
    "lines": "lines",
    "rectilinear": "lines",
    "alignedrectilinear": "lines",
    "zigzag": "lines",
    "cross": "lines",
    "cross_3d": "lines",
}
FALLBACK_PATTERN = "concentric"

# How far in from the edge the outline sits, as a fraction of half a stroke.
# Exactly half would put the brush's edge on the shape's edge in theory; in
# practice the stroke is quantised and the shape's edge is a traced pixel
# boundary, which leaves a hairline of bare paper all the way round. Sitting a
# little further out covers it, the way the slicer's extrusion width did.
EDGE_BIAS = 0.8

# How far the step from one ring to the one inside it may reach, in line
# widths. Rings sit exactly one apart, so a step much longer than that is not
# the ring below -- it is another shape, and it starts a spiral of its own.
SPIRAL_REACH = 2.2

# A shape flatter than this in pixels cannot hold a ring worth painting.
_MIN_RING_PTS = 3

# How far a simplified ring may stray from the traced one, in pixels. A contour
# read off a raster climbs every diagonal as a staircase, and each step is a
# point in the G-code; straightening within a pixel removes the steps without
# moving the stroke anywhere the brush could tell.
SIMPLIFY_PX = 0.75


def _distance(ink: np.ndarray) -> np.ndarray:
    """Every pixel's distance, in pixels, to the nearest bare paper."""
    return cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 5)


def _spiral(by_depth: list[list[list[tuple[float, float]]]],
            reach: float) -> list[list[tuple[float, float]]]:
    """Rings, outermost first, joined into one stroke a shape.

    A concentric fill is nested rings, and it used to be handed over as nested
    rings: one brush stroke each, lifted between, and painted in whatever order
    the ordering pass made of them. That is what a slicer does, and a slicer is
    not holding a wet brush. Two things came of it. Each ring cost a lift and a
    place, so a shape three rings deep was three brush-downs where one would
    do. And the ordering pass, which goes to whatever is nearest, would finish
    the outline of a big shape and then wander off into the rings of a sliver
    beside it, because the sliver's rings were nearer than the next ring in --
    the fill *looked* like it was picking at a corner instead of working
    inwards, and it was.

    So a nest is walked as one path: round the outer ring, in to the nearest
    point of the ring below it, round that, and on to the middle. It is the
    line a person fills a shape with, and it is one stroke with no lift in it.

    `reach` is how far the step inward may be. Rings sit one line width apart,
    so anything much over that is a different shape and starts a spiral of its
    own -- which is what keeps the two sides of a shape that erodes into two
    from being sewn together across the gap between them.
    """
    spirals: list[list[tuple[float, float]]] = []
    open_ends: list[int] = []                 # indices of spirals still growing
    for rings in by_depth:
        next_open: list[int] = []
        taken: set[int] = set()
        for contour in rings:
            if len(contour) < 2:
                continue
            best = None
            for idx in open_ends:
                if idx in taken:
                    continue        # one ring a depth a spiral, or two
                                    # sub-regions get sewn to the same tail
                tail = spirals[idx][-1]
                at, d2 = _nearest(contour, tail)
                if d2 <= reach * reach and (best is None or d2 < best[1]):
                    best = (idx, d2, at)
            if best is None:
                spirals.append(list(contour))
                next_open.append(len(spirals) - 1)
                continue
            idx, _, at = best
            taken.add(idx)
            # Round the ring from the point nearest where the last one ended,
            # and all the way round to it again: a ring is a closed loop, so
            # where it is entered is the only choice to make about it.
            turned = contour[at:] + contour[1:at + 1] if at else list(contour)
            spirals[idx].extend(turned)
            next_open.append(idx)
        open_ends = next_open
    return spirals


def _nearest(contour: list[tuple[float, float]], to: tuple[float, float]):
    """Which vertex of `contour` is closest to `to`, and how far it is, squared."""
    at, best = 0, None
    for i, (x, y) in enumerate(contour):
        d2 = (x - to[0]) ** 2 + (y - to[1]) ** 2
        if best is None or d2 < best:
            at, best = i, d2
    return at, (best if best is not None else 0.0)


def _contours_at(dt: np.ndarray, depth_px: float, sx: float, sy: float,
                 height_mm: float) -> list[list[tuple[float, float]]]:
    """Closed rings around everything at least `depth_px` in from the edge.

    Image row 0 is the top and machine Y grows upward, hence the flip. The
    artwork lands on exactly (0,0)-(width_mm, height_mm), the frame the rest of
    the pipeline already expects.
    """
    region = (dt >= depth_px).astype(np.uint8)
    contours, _ = cv2.findContours(region, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    rings = []
    for contour in contours:
        if len(contour) < _MIN_RING_PTS:
            continue
        if SIMPLIFY_PX > 0 and len(contour) > 2:
            contour = cv2.approxPolyDP(contour, SIMPLIFY_PX, True)
            if len(contour) < _MIN_RING_PTS:
                continue
        ring = [(float(p[0][0]) * sx, height_mm - float(p[0][1]) * sy) for p in contour]
        # findContours leaves the loop open; a brush stroke round a shape should
        # come back to where it started.
        ring.append(ring[0])
        rings.append(ring)
    return rings


def _scanlines(dt: np.ndarray, depth_px: float, line_w: float, sx: float, sy: float,
               height_mm: float, angle_deg: float) -> list[list[tuple[float, float]]]:
    """Parallel strokes across everything at least `depth_px` in from the edge.

    The region is rotated rather than the strokes, so consecutive strokes really
    are one width apart whatever the angle, and each row is a straight run.
    """
    region = ((dt >= depth_px) * 255).astype(np.uint8)
    h, w = region.shape
    centre = (w / 2.0, h / 2.0)
    rot = cv2.getRotationMatrix2D(centre, angle_deg, 1.0)
    # Rotating about the centre can push content outside the frame; a canvas
    # sized to the diagonal always holds it.
    diag = int(np.ceil(np.hypot(w, h)))
    rot[0, 2] += (diag - w) / 2.0
    rot[1, 2] += (diag - h) / 2.0
    turned = cv2.warpAffine(region, rot, (diag, diag), flags=cv2.INTER_NEAREST)
    back = cv2.invertAffineTransform(rot)

    step = max(1, int(round(line_w / sx)))
    out = []
    for row in range(0, diag, step):
        line = turned[row] > 0
        if not line.any():
            continue
        # Run starts and ends, from where the row switches on and off.
        edges = np.flatnonzero(np.diff(np.concatenate(([0], line.view(np.int8), [0]))))
        for start, end in zip(edges[::2], edges[1::2]):
            if end - start < 1:
                continue
            pts = np.array([[start, row, 1.0], [end - 1, row, 1.0]]).T
            (x0, x1), (y0, y1) = back @ pts
            out.append([(float(x0) * sx, height_mm - float(y0) * sy),
                        (float(x1) * sx, height_mm - float(y1) * sy)])
    return out


def build(ink: np.ndarray, width_mm: float, height_mm: float, line_w: float,
          pattern: str = "concentric", infill: bool = True,
          perimeters: int = 1, log=None) -> list[list[tuple[float, float]]]:
    """Outline every painted shape, and fill it if asked.

    Shapes narrower than a stroke hold no ring at all — there is nothing to
    inset into — and are left to the centreline pass, which sees the whole
    picture at once and draws whatever these paths do not cover.
    """
    style = PATTERNS.get(str(pattern).strip().lower(), FALLBACK_PATTERN)
    h, w = ink.shape
    sx, sy = width_mm / w, height_mm / h
    px_per_mm = w / width_mm

    dt = _distance(ink)
    deepest_mm = float(dt.max()) / px_per_mm
    first_mm = line_w * EDGE_BIAS / 2.0

    walls = max(1, int(perimeters))
    depths = [first_mm + k * line_w for k in range(walls)]
    if infill and style == "concentric":
        k = walls
        while first_mm + k * line_w <= deepest_mm:
            depths.append(first_mm + k * line_w)
            k += 1
    depths = [d for d in depths if d <= deepest_mm]

    # Every ring is read off the same distance transform, so none of them waits
    # on any other. OpenCV drops the GIL for the threshold and the contour
    # trace, which is all this is.
    def ring(depth_mm):
        return _contours_at(dt, depth_mm * px_per_mm, sx, sy, height_mm)

    paths: list[list[tuple[float, float]]] = []
    if depths:
        if len(depths) > 1:
            workers = min(len(depths), os.cpu_count() or 1)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                by_depth = list(pool.map(ring, depths))
        else:
            by_depth = [ring(depths[0])]
        paths.extend(_spiral(by_depth, line_w * SPIRAL_REACH))

    if infill and style == "lines":
        inner = first_mm + walls * line_w
        if inner <= deepest_mm:
            paths.extend(_scanlines(dt, inner * px_per_mm, line_w, sx, sy,
                                    height_mm, 45.0))

    paths = [p for p in paths if len(p) > 1]
    if log:
        log(f"  {style} from {len(depths)} depth{'' if len(depths) == 1 else 's'}: "
            f"{len(paths)} paths")
    return paths
