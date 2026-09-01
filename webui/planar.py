#!/usr/bin/python3
"""Turn a bitmap into brush paths directly, without a trip through 3D.

The external chain traces the bitmap to vectors, extrudes those to a solid, and
slices the solid back to 2D paths. Everything it produces — an outline inset by
half a stroke, and a fill inside that — is a planar operation on a polygon, so
it is done here as one: contours from the bitmap, then polygon offsetting.

Roughly thirty times quicker, and it removes three external programs from the
machine this has to run on.
"""
from __future__ import annotations

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Polygon

# Mitre joins, as a slicer uses: a corner stays a corner instead of being
# rounded off, so the outline follows the drawing.
_JOIN_MITRE = 2

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


def polygons_from_mask(ink: np.ndarray, width_mm: float, height_mm: float,
                       simplify_mm: float = 0.0) -> list[Polygon]:
    """Contours of the painted areas, as polygons with their holes, in mm.

    Image row 0 is the top and machine Y grows upward, hence the flip. The
    artwork is mapped onto exactly (0,0)-(width_mm, height_mm), which is the
    same frame OpenSCAD produced, so everything downstream is unchanged.
    """
    import cv2

    h, w = ink.shape
    sx, sy = width_mm / w, height_mm / h
    contours, hierarchy = cv2.findContours(ink.astype(np.uint8), cv2.RETR_CCOMP,
                                           cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []

    def to_mm(contour):
        return [(float(p[0][0]) * sx, height_mm - float(p[0][1]) * sy) for p in contour]

    polys = []
    for i, contour in enumerate(contours):
        # RETR_CCOMP puts outer boundaries at the top level and their holes one
        # level down, so a hole is reached from its own parent and never twice.
        if hierarchy[0][i][3] != -1 or len(contour) < 4:
            continue
        holes = []
        child = hierarchy[0][i][2]
        while child != -1:
            if len(contours[child]) >= 4:
                holes.append(to_mm(contours[child]))
            child = hierarchy[0][child][0]
        poly = Polygon(to_mm(contour), holes)
        if not poly.is_valid:
            # A traced contour can touch itself; buffer(0) is the standard
            # repair and returns a valid equivalent.
            poly = poly.buffer(0)
        for piece in _as_polygons(poly):
            if piece.area > 0:
                polys.append(piece.simplify(simplify_mm) if simplify_mm > 0 else piece)
    return polys


def _as_polygons(geom) -> list[Polygon]:
    if geom.is_empty:
        return []
    parts = geom.geoms if hasattr(geom, "geoms") else [geom]
    return [g for g in parts if isinstance(g, Polygon) and not g.is_empty]


def _rings(geom) -> list[list[tuple[float, float]]]:
    out = []
    for poly in _as_polygons(geom):
        out.append(list(poly.exterior.coords))
        out.extend(list(ring.coords) for ring in poly.interiors)
    return out


def _concentric(region, line_w: float, max_loops: int = 2000):
    """Loops stepping inward until nothing is left."""
    out, current = [], region
    for _ in range(max_loops):
        current = current.buffer(-line_w, join_style=_JOIN_MITRE)
        if current.is_empty:
            break
        out.extend(_rings(current))
    return out


def _lines(region, line_w: float, angle_deg: float = 45.0):
    """Parallel lines clipped to the region.

    Rotating the region rather than the lines keeps the spacing exact: the
    lines stay axis-aligned, so consecutive ones really are one line width
    apart however the fill is angled.
    """
    if region.is_empty:
        return []
    centre = region.centroid
    turned = affinity.rotate(region, -angle_deg, origin=centre)
    minx, miny, maxx, maxy = turned.bounds
    rows = np.arange(miny, maxy + line_w, line_w)
    if len(rows) == 0:
        return []
    grid = MultiLineString([[(minx - line_w, float(y)), (maxx + line_w, float(y))]
                            for y in rows])
    clipped = turned.intersection(grid)
    pieces = clipped.geoms if hasattr(clipped, "geoms") else [clipped]
    return [list(affinity.rotate(p, angle_deg, origin=centre).coords)
            for p in pieces if isinstance(p, LineString) and not p.is_empty]


def _centreline(poly, ink_shape, width_mm: float, height_mm: float, min_len_mm: float):
    """The line down the middle of a shape too narrow to outline.

    A rib a millimetre across cannot take an inset outline — there is no inside
    left — but the brush can still draw it, once, down its spine. Rasterising
    the single shape and thinning it keeps the result local, so a rib comes out
    as one path instead of being cut up by whatever else shares the picture.
    """
    import cv2
    from gcode_pipeline import _trace_skeleton, simplify, _length

    h, w = ink_shape
    sx, sy = w / width_mm, h / height_mm
    canvas = np.zeros((h, w), np.uint8)

    def to_px(coords):
        return np.array([[int(round(x * sx)), int(round((height_mm - y) * sy))]
                         for x, y in coords], np.int32)

    cv2.fillPoly(canvas, [to_px(poly.exterior.coords)], 1)
    for ring in poly.interiors:
        cv2.fillPoly(canvas, [to_px(ring.coords)], 0)
    if not canvas.any():
        return []

    thin = cv2.ximgproc.thinning(canvas * 255, thinningType=cv2.ximgproc.THINNING_ZHANGSUEN)
    out = []
    for run in _trace_skeleton(thin > 0):
        line = [(c / sx, height_mm - r / sy) for r, c in run]
        line = simplify(line, tol=0.15)
        if len(line) > 1 and _length(line) >= min_len_mm:
            out.append(line)
    return out


def build(ink: np.ndarray, width_mm: float, height_mm: float, line_w: float,
          pattern: str = "concentric", infill: bool = True,
          perimeters: int = 1, log=None) -> list[list[tuple[float, float]]]:
    """Outline every painted shape, and fill it if asked.

    Shapes narrower than the brush produce nothing here — there is no room to
    inset an outline into them — and are left to the centreline pass, which
    picks up whatever these paths do not cover.
    """
    style = PATTERNS.get(str(pattern).strip().lower(), FALLBACK_PATTERN)
    polys = polygons_from_mask(ink, width_mm, height_mm)

    paths: list[list[tuple[float, float]]] = []
    thin_shapes = 0
    for poly in polys:
        region = poly.buffer(-line_w / 2, join_style=_JOIN_MITRE)
        if region.is_empty:
            # Narrower than the brush, so there is no inside to outline. Left to
            # the centreline pass in write_brush_paths, which sees the whole
            # picture at once. Rasterising each shape separately here was tried
            # and cost five times the runtime without drawing a better line.
            thin_shapes += 1
            continue
        paths.extend(_rings(region))

        for _ in range(max(0, perimeters - 1)):
            region = region.buffer(-line_w, join_style=_JOIN_MITRE)
            if region.is_empty:
                break
            paths.extend(_rings(region))
        if region.is_empty:
            continue

        if infill:
            inner = region.buffer(-line_w, join_style=_JOIN_MITRE)
            if not inner.is_empty:
                paths.extend(_concentric(inner, line_w) if style == "concentric"
                             else _lines(inner, line_w))

    if log:
        log(f"  {len(polys)} shapes as {style}: {len(paths)} paths"
            f"{f', {thin_shapes} too thin to outline and drawn down the middle' if thin_shapes else ''}")
    return [p for p in paths if len(p) > 1]
