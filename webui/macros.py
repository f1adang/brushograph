"""Five small utility routines, built from the same config the pipeline reads.

zero.g sets the controller's origin, home.g parks the brush, paper.g positions
it over the paper for a placement check, and clean.g/prime.g wash and charge
the brush the way a real job does — following whichever container shape
`brushograph.cup_shape` names, classic or modern.

None of the five carries an M-code or a G28, so none needs the controller
dialect handling `gcode_pipeline.sanitize_for_controller` does for a real job:
G90/G21/G0/G1/G10/G92 are understood the same way by Marlin, GRBL and FluidNC.
"""
from __future__ import annotations

import math

from configspec import CMYK_TO_TRAY, with_defaults

MACRO_NAMES = ["zero.g", "home.g", "paper.g", "clean.g", "prime.g"]

# The classic dip sweep in copicograf picks a random quadrant each time, which
# suits a real job's hundreds of pickups — spreading the wear across the cup —
# but not a canned macro someone downloads and reads. Cycling through the four
# quadrants by repetition index keeps the same config always producing the
# same macro, while still covering the cup the way the random version does.
_QUADRANTS = [(1, 1), (-1, 1), (-1, -1), (1, -1)]

# How many times wash_the_brush() dips in copicograf's own choreography — see
# copicograf.py's wash_the_brush(), which is not itself reusable here because
# its motion lives in closures nested inside Copicograf.prepare_path().
_WASH_REPS = 3


def _num(d: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(d.get(key, default))
    except (TypeError, ValueError):
        return default


def _fmt(v: float) -> str:
    """3 decimal places, trailing zeros trimmed — "47", not "47.000"."""
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _feed(bg: dict, group: str, fallback: str = "G0 F1000") -> str:
    moves = bg.get("moves", {})
    g = moves.get(group, {}) if isinstance(moves, dict) else {}
    val = str(g.get("feedrate_1", "")).strip() if isinstance(g, dict) else ""
    return val or fallback


def _safe_z(bg: dict) -> float:
    """The height copicograf already treats as clear of every cup and the paper."""
    return max(_num(bg, "go_in_tray_lift", 10),
               _num(bg, "move_to_other_shape_lift") + _num(bg, "canvas_height"))


def _preamble(bg: dict, feed_group: str = "normal") -> list[str]:
    return ["G90 ; absolute positioning", "G21 ; millimetres", _feed(bg, feed_group)]


def _color_trays(conf: dict) -> list[tuple[str, float, float]]:
    """[(tray name, x, y), ...] for every colour in color_order, config order."""
    trays = conf.get("trays", {})
    out = []
    for color in conf.get("color_order", []):
        name = CMYK_TO_TRAY.get(color, color)
        t = trays.get(name)
        if isinstance(t, dict) and "x" in t:
            out.append((name, float(t["x"]), float(t["y"])))
    return out


def _wipe_axis(conf: dict, tray_x: float, tray_y: float) -> tuple[float, float]:
    """Unit vector along the row of cups, from the nearest other cup.

    Mirrors copicograf's own wipe_axis(): direction from the nearest other cup
    rather than assumed to be X, so a machine that arranges its cups along Y
    still wipes along its own row instead of off the front edge of the bed.
    """
    trays = conf.get("trays", {})
    best, best_d2 = None, None
    for name, t in trays.items():
        if name == "additionals" or not isinstance(t, dict) or "x" not in t:
            continue
        tx, ty = float(t["x"]), float(t["y"])
        if tx == tray_x and ty == tray_y:
            continue
        d2 = (tx - tray_x) ** 2 + (ty - tray_y) ** 2
        if best_d2 is None or d2 < best_d2:
            best, best_d2 = (tx, ty), d2
    if best is None:
        return 1.0, 0.0
    dx, dy = best[0] - tray_x, best[1] - tray_y
    dist = math.hypot(dx, dy) or 1.0
    return dx / dist, dy / dist


def _container_motion(bg: dict, conf: dict, tray_x: float, tray_y: float,
                       reps: int, wipe: bool) -> list[str]:
    """`reps` dips or swipes at (tray_x, tray_y), classic or modern.

    A modern bay wipes itself on the way up the stairs — see copicograf's
    append_go_in_tray(), which skips the rim wipe there for the same reason —
    so `wipe` only has an effect for a classic, round container.
    """
    shape = str(bg.get("cup_shape", "classic")).strip().lower()
    dip = _num(bg, "dip_depth", -4)
    lift = _num(bg, "go_in_tray_lift", 8)
    lines: list[str] = []

    if shape == "modern":
        depth = _num(bg, "cup_depth", 30.0)
        exit_z = _num(bg, "cup_swipe_exit_z", 1.0)
        margin = depth * 0.15
        near, far = tray_y - depth / 2 + margin, tray_y + depth / 2 - margin
        for _ in range(max(1, reps)):
            lines += [
                f"G00 X{_fmt(tray_x)} Y{_fmt(near)}",
                f"G00 Z{_fmt(dip)}",
                f"G01 X{_fmt(tray_x)} Y{_fmt(far)} Z{_fmt(exit_z)} ; up the stairs — wipes itself",
                f"G00 Z{_fmt(lift)}",
            ]
        return lines

    # Classic: down the middle, a diagonal sweep, back up. The real dance
    # picks a random quadrant each pickup; this cycles through the four so the
    # same config always produces the same macro.
    radius = _num(bg, "tray_enter_radius", 10)
    d = radius * 0.70711
    for i in range(max(1, reps)):
        qx, qy = _QUADRANTS[i % 4]
        lines += [
            f"G00 X{_fmt(tray_x)} Y{_fmt(tray_y)}",
            f"G00 Z{_fmt(dip)}",
            f"G00 X{_fmt(tray_x + qx * d)} Y{_fmt(tray_y + qy * d)}",
            f"G00 X{_fmt(tray_x - qx * d)} Y{_fmt(tray_y - qy * d)}",
            f"G00 X{_fmt(tray_x)} Y{_fmt(tray_y)}",
            f"G00 Z{_fmt(lift)}",
        ]
    if wipe:
        ax, ay = _wipe_axis(conf, tray_x, tray_y)
        rr = _num(bg, "remove_drops_radius", 20)
        wlift = _num(bg, "remove_drops_lift", lift)
        lines.append(f"G00 Z{_fmt(wlift)}")
        for side in (1, -1):
            lines += [
                f"G01 X{_fmt(tray_x + ax * rr * side)} Y{_fmt(tray_y + ay * rr * side)}",
                f"G00 X{_fmt(tray_x)} Y{_fmt(tray_y)}",
            ]
        lines.append(f"G00 Z{_fmt(lift)}")
    return lines


def generate_macros(conf: dict) -> dict[str, str]:
    """The five macros, as {filename: text}, in MACRO_NAMES order."""
    conf = with_defaults(conf)
    bg = conf.get("brushograph", {})
    trays = conf.get("trays", {})
    water = trays.get("water", {}) if isinstance(trays, dict) else {}
    wx, wy = _num(water, "x", 0), _num(water, "y", 0)
    controller = str(conf.get("controller", {}).get("controller_type") or "GRBL").strip().lower()
    shape = str(bg.get("cup_shape", "classic")).strip().lower()
    safe_z = _safe_z(bg)
    dip = _num(bg, "dip_depth", -4)
    # A config need not carry a travel limit distinct from the painted size —
    # sketch.py falls back the same way for the same reason.
    max_w = _num(bg, "max_width", _num(bg, "width", 200))
    max_h = _num(bg, "max_height", _num(bg, "height", 200))
    prepare_count = max(1, int(_num(bg, "prepare_paint_count", 3)))

    out: dict[str, str] = {}

    # zero.g — the current physical position becomes the origin. Run with the
    # brush parked exactly where 0,0,0 should be.
    lines = [
        "; zero.g — set the current physical position as X0 Y0 Z0",
        "; park the brush by hand first: this does not move anything",
        "G90", "G21",
    ]
    if controller == "marlin":
        lines.append("G92 X0 Y0 Z0")
    else:
        lines.append("G10 L20 P0 X0 Y0 Z0 ; FluidNC/GRBL: here becomes the origin")
    out["zero.g"] = "\n".join(lines) + "\n"

    # home.g — park at X0 Y0, Z = Dip Depth + 1.
    park_z = dip + 1
    lines = [
        "; home.g — park over the origin, just above dipping depth",
        *_preamble(bg, "normal"),
        f"G00 Z{_fmt(safe_z)} ; lift clear before crossing the bed",
        "G00 X0 Y0",
        f"G00 Z{_fmt(park_z)} ; Dip Depth + 1",
    ]
    out["home.g"] = "\n".join(lines) + "\n"

    # paper.g — half of Max Width on X, all of Max Height on Y.
    px, py = max_w / 2, max_h
    lines = [
        "; paper.g — position over the paper for a placement check",
        *_preamble(bg, "normal"),
        f"G00 Z{_fmt(safe_z)} ; lift clear before crossing the bed",
        f"G00 X{_fmt(px)} Y{_fmt(py)} ; half of Max Width, all of Max Height",
    ]
    out["paper.g"] = "\n".join(lines) + "\n"

    # clean.g — wash the brush at the water container. Three dips, no
    # rim wipe, matching copicograf's own wash_the_brush().
    lines = [
        "; clean.g — wash the brush in the water container",
        f"; containers: {shape}",
        *_preamble(bg, "fast"),
        f"G00 Z{_fmt(safe_z)}",
        f"G00 X{_fmt(wx)} Y{_fmt(wy)}",
        *_container_motion(bg, conf, wx, wy, reps=_WASH_REPS, wipe=False),
        f"G00 Z{_fmt(safe_z)}",
    ]
    out["clean.g"] = "\n".join(lines) + "\n"

    # prime.g — charge every colour tray in color_order, Prepare Paint Count
    # dips or swipes each, matching copicograf's own prepare_paint().
    lines = [
        "; prime.g — charge every colour container before a job",
        f"; containers: {shape}",
        *_preamble(bg, "fast"),
        f"G00 Z{_fmt(safe_z)}",
    ]
    colors = _color_trays(conf)
    if not colors:
        lines.append("; no colour containers configured in color_order")
    for name, tx, ty in colors:
        lines.append(f"; {name}")
        lines.append(f"G00 X{_fmt(tx)} Y{_fmt(ty)}")
        lines += _container_motion(bg, conf, tx, ty, reps=prepare_count, wipe=True)
        lines.append(f"G00 Z{_fmt(safe_z)}")
    out["prime.g"] = "\n".join(lines) + "\n"

    return out
