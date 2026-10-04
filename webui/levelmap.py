"""A probed height map of the bed, read as the height of the paper anywhere on it.

The five bed-levelling readings say how a sheet lies at five spots and assume
it is flat in between. A touch probe says it at hundreds: `probescan.py` walks
a grid with G38.2 and writes `x,y,z_mm,z_fast_mm`, one row per point, in the
order it probed them. That order is kept, because it is evidence -- see
`surface` on why.

Z in that file is the machine's own Z at contact, wherever it happened to be
when the scan started; probescan neither homes nor zeroes. Only differences
mean anything, so the map is read relative to its own height at one spot, the
middle of the bed, which is where Canvas Height is taken to have been set.
"""
from __future__ import annotations

import csv
import io
import math

import numpy as np

# More than this between the lowest and highest point is not a sheet on a bed:
# it is a probe that came down on a clamp, a file from another machine, or a
# column in the wrong units. A brush is lifted 2 mm between shapes; a map that
# moves it by several times that is refused rather than painted with.
MAX_SPREAD = 5.0

# A 2 mm grid over the Mini's whole bed is under 5,000 points. The map is
# carried in the config, and the config is kept at a few kilobytes.
MAX_POINTS = 6000

# A probe move shorter than this is not a change of direction, for the same
# reason a G-code move that short is not a reversal to the backlash pass.
REVERSAL = 0.05


def read_csv(text: str) -> tuple[list[list[float]], int]:
    """probescan.py's CSV as [[x, y, z], ...] in probing order, and how many
    points it had no contact for.

    The slow probe's `z_mm`, not `z_fast_mm`: the fast one overshoots by
    however far the axis coasts after the switch closes, and the slow one is
    what the script takes the reading from. A point with no contact is written
    `nan` and is left out; its neighbours cover for it.
    """
    rows = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower(): f for f in rows.fieldnames or []}
    z_key = fields.get("z_mm") or fields.get("z")
    if "x" not in fields or "y" not in fields or not z_key:
        raise ValueError("A probe map needs x, y and z_mm columns, the way probescan.py "
                         "writes them.")
    points, missed = [], 0
    for row in rows:
        try:
            x = float(row[fields["x"]])
            y = float(row[fields["y"]])
            z = float(row[z_key])
        except (TypeError, ValueError):
            raise ValueError(f"Line {rows.line_num} of the probe map is not three numbers.")
        if not all(math.isfinite(v) for v in (x, y)):
            raise ValueError(f"Line {rows.line_num} of the probe map has no position.")
        if not math.isfinite(z):
            missed += 1
            continue
        points.append([round(x, 3), round(y, 3), round(z, 3)])
    return clean(points), missed


def clean(value) -> list[list[float]]:
    """The map as the config should hold it, or ValueError saying why not.

    An empty list is no map, and is what a config without one carries.
    """
    if value in (None, "", []):
        return []
    if not isinstance(value, list):
        raise ValueError("A probe map is a list of points.")
    points = []
    for p in value:
        if not (isinstance(p, (list, tuple)) and len(p) == 3):
            raise ValueError("Each point in a probe map is x, y and z.")
        try:
            x, y, z = (float(v) for v in p)
        except (TypeError, ValueError):
            raise ValueError("Each point in a probe map is three numbers.")
        if not all(math.isfinite(v) for v in (x, y, z)):
            raise ValueError("A probe map cannot hold a point that is not a number.")
        points.append([x, y, z])
    if len(points) > MAX_POINTS:
        raise ValueError(f"That probe map has {len(points)} points; {MAX_POINTS} is the most "
                         "a config will carry. Probe on a coarser grid.")
    if len({p[0] for p in points}) < 2 or len({p[1] for p in points}) < 2:
        raise ValueError("A probe map needs at least two rows of at least two points; "
                         "with fewer there is no surface to read between them.")
    zs = [p[2] for p in points]
    if max(zs) - min(zs) > MAX_SPREAD:
        raise ValueError(f"That probe map runs {max(zs) - min(zs):.1f} mm from its lowest "
                         f"point to its highest, more than the {MAX_SPREAD:g} mm a sheet on a "
                         "bed could. Look for a point that came down on a clamp or off the "
                         "edge of the bed.")
    return points


def where_probed(points: list[list[float]], play_x, play_y) -> list[tuple[float, float, float]]:
    """Where the probe actually was at each point, given the machine's play.

    The scan was driven by the same axes the brush is, slack and all, and it is
    driven serpentine: one row left to right, the next right to left. Coming
    from the right and asked for X60, the probe stops at X60 plus the play,
    exactly as the brush does. So every other row of the file is written a
    play's width away from where it was measured, and a step in the bed --
    Parang's has several, a millimetre high -- comes out in a zigzag, nearer
    the origin on the rows probed leftwards.

    The direction is read off the order of the file, which is why that order is
    kept. The convention is `apply_backlash`'s: travelling towards the origin
    the axis stands the play beyond the commanded point, travelling away from
    it the axis is where it was told, and an axis that has not moved yet is
    taken to be where it was told. Both axes, though probescan only ever steps
    Y one way and its Y needs no correction.
    """
    out = []
    last_x = last_y = None
    dir_x = dir_y = 0
    for x, y, z in points:
        if last_x is not None and abs(x - last_x) > REVERSAL:
            dir_x = 1 if x > last_x else -1
        if last_y is not None and abs(y - last_y) > REVERSAL:
            dir_y = 1 if y > last_y else -1
        last_x, last_y = x, y
        out.append((x + (play_x(x) if dir_x < 0 else 0.0),
                    y + (play_y(x) if dir_y < 0 else 0.0), z))
    return out


def surface(points: list[list[float]], play_x=lambda _x: 0.0, play_y=lambda _x: 0.0):
    """A function (x, y) -> the paper's Z there, in the probe's own Z.

    Bilinear between the probed points, and nothing smoother. The bed this was
    built against does not bend, it steps -- a millimetre in a few millimetres,
    in several places -- and a spline through a step rings either side of it,
    lifting the brush off the paper just before the edge and driving it in
    just after. Bilinear never reads higher or lower than the points around it.

    Each row is laid along X at where the probe really was (`where_probed`) and
    resampled onto the grid's own columns; the rows are then taken as they
    stand in Y. A point outside the map reads as its nearest edge, the way the
    five readings are clamped: past the last point there is nothing measured.
    """
    true = where_probed(points, play_x, play_y)
    rows: dict[float, list[tuple[float, float, float]]] = {}
    for (_, y, _), p in zip(points, true):
        rows.setdefault(y, []).append(p)
    cols = np.array(sorted({p[0] for p in points}))
    ys, grid = [], []
    for y in sorted(rows):
        row = sorted(rows[y])
        ys.append(float(np.mean([p[1] for p in row])))
        grid.append(np.interp(cols, [p[0] for p in row], [p[2] for p in row]))
    ys, grid = np.array(ys), np.array(grid)

    def at(x: float, y: float) -> float:
        x = min(max(x, cols[0]), cols[-1])
        y = min(max(y, ys[0]), ys[-1])
        i = min(max(int(np.searchsorted(cols, x)) - 1, 0), len(cols) - 2)
        j = min(max(int(np.searchsorted(ys, y)) - 1, 0), len(ys) - 2)
        fx = (x - cols[i]) / (cols[i + 1] - cols[i])
        fy = (y - ys[j]) / (ys[j + 1] - ys[j])
        lo = grid[j, i] * (1 - fx) + grid[j, i + 1] * fx
        hi = grid[j + 1, i] * (1 - fx) + grid[j + 1, i + 1] * fx
        return float(lo * (1 - fy) + hi * fy)

    # Where the surface stops being one smooth patch: a stroke that crosses one
    # of these lines has to be broken there for its Z to follow (see
    # `crossings`).
    at.knots = (cols, ys)
    return at


def crossings(x0: float, y0: float, x1: float, y1: float, knots) -> list[float]:
    """Where a straight move from (x0, y0) to (x1, y1) crosses the map's grid
    lines, as fractions of the way along it, in order.

    A G1 moves Z in a straight line between its ends, and the paper does not:
    a 100 mm scanline stroke levelled only at its ends sails over every step in
    between. Inside one cell of the map the surface is a single bilinear patch,
    so a stroke broken where it enters and leaves each cell follows it.
    """
    cols, ys = knots
    ts = []
    for lines, a, b in ((cols, x0, x1), (ys, y0, y1)):
        if abs(b - a) < 1e-9:
            continue
        lo, hi = min(a, b), max(a, b)
        ts.extend((v - a) / (b - a) for v in lines if lo < v < hi)
    out = []
    for t in sorted(ts):
        if 1e-6 < t < 1 - 1e-6 and (not out or t - out[-1] > 1e-6):
            out.append(t)
    return out
