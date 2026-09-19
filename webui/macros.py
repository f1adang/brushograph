"""Five small utility routines.

home.g parks the brush, paper.g moves it out of the way for replacing the
paper, and clean.g washes the brush the way a real job does before parking
too. The wash in clean.g follows whichever container shape
`brushograph.cup_shape` names, classic, modern or custom. All three, plus zero.g's
own last line, end the same way — parked at X0 Y0, Z = Dip Depth + 1 — via
the shared `_park_at_origin()`.

zero.g is the machine's own self-zero dance — a fixed sequence tuned on the
actual hardware, reproduced here verbatim, with the config read for nothing
but the model's far corner and that final park.

calibrate.g is the odd one out on purpose: no wash, no lift first, just the
dot and a park over it, at two literal heights that are neither
`canvas_height` nor `go_in_tray_lift`.

None of the five carries an M-code or a G28, so none needs the controller
dialect handling `gcode_pipeline.sanitize_for_controller` does for a real job:
G90/G0/G1/G10 are understood the same way by Marlin, GRBL and FluidNC.
"""
from __future__ import annotations

from configspec import (MODELS, RECTANGULAR_SHAPES, holder_of, model_of,
                        with_defaults, workable_x)
from version import gcode_note

MACRO_NAMES = ["zero.g", "home.g", "paper.g", "clean.g", "calibrate.g"]

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


def _preamble(bg: dict, feed_group: str = "normal") -> list[str]:
    return ["G90 ; absolute positioning", "G21 ; millimetres", _feed(bg, feed_group)]


def _park_at_origin(park_z: float) -> list[str]:
    """Park at X0 Y0, Z = Dip Depth + 1.

    How home.g, clean.g and zero.g all finish once whatever they were doing is
    done and the brush is already lifted clear — a shared ending rather than
    three copies of the same two lines.
    """
    return [
        "G00 X0 Y0",
        f"G00 Z{_fmt(park_z)} ; Dip Depth + 1",
    ]


def _container_motion(conf: dict, tray_x: float, tray_y: float, reps: int) -> list[str]:
    """`reps` dips or swipes at (tray_x, tray_y), classic or modern.

    No rim wipe: the only caller is clean.g's wash, which — like copicograf's
    own wash_the_brush() — passes remove_drop=False, because a brush being
    rinsed has nothing to shed on the way out. A modern bay's swipe wipes
    itself regardless, on the way up the stairs.
    """
    bg = conf.get("brushograph", {})
    shape = str(bg.get("cup_shape", "classic")).strip().lower()
    dip = _num(bg, "dip_depth", -4)
    lift = _num(bg, "go_in_tray_lift", 8)
    lines: list[str] = []

    if shape in RECTANGULAR_SHAPES:
        holder = holder_of(conf)
        depth = holder["swipe_length"]
        exit_z = _num(bg, "cup_swipe_exit_z", 1.0)
        margin = depth * 0.15
        near, far = tray_y - depth / 2 + margin, tray_y + depth / 2 - margin
        # The near edge gets the clamp the stir across X already has. A bay
        # deeper than the strip it stands in reaches south of the origin — on
        # Pinkograph the water crucible puts this edge at Y -4.5 — and there
        # is no ground down there to reach: zero.g backs three millimetres off
        # the Y endstop and calls that spot Y0, so Y -3 is the stop itself.
        # Every wash drove into it, and what a move loses against a stop it
        # loses for the whole of the rest of the file.
        near = max(near, 0.0)
        # The same stir copicograf makes before climbing out, kept on the bed
        # the same way — the water crucible is the wide one, and wide enough
        # on some holders to hang over the endstop.
        reach = holder["water_bay_width"] / 2 * 0.7
        sweeps = int(_num(bg, "cup_mix_sweeps", 2))
        # Centred on the cup, however near the end of the axis it sits: the
        # shorter side sets both, as it does in copicograf, and neither side
        # goes past the ground a job already covers — the far end of that is
        # the endstop, and a move that reaches it loses steps against it.
        reach = min(reach, tray_x, workable_x(conf) - tray_x)
        left, right = tray_x - reach, tray_x + reach
        if reach < 0.5:
            sweeps = 0
        for _ in range(max(1, reps)):
            lines += [
                f"G00 X{_fmt(tray_x)} Y{_fmt(near)}",
                f"G00 Z{_fmt(dip)}",
            ]
            for i in range(max(0, sweeps)):
                lines += [
                    f"G00 X{_fmt(left)} Y{_fmt(near)}"
                    + (" ; stir, then load" if i == 0 else ""),
                    f"G00 X{_fmt(right)} Y{_fmt(near)}",
                ]
            if sweeps > 0:
                lines.append(f"G00 X{_fmt(tray_x)} Y{_fmt(near)}")
            lines += [
                f"G01 X{_fmt(tray_x)} Y{_fmt(far)} Z{_fmt(exit_z)} ; up the stairs — wipes itself",
                f"G00 Z{_fmt(lift)}",
            ]
        return lines

    # Classic: down the middle, a diagonal sweep, back up. The real dance
    # picks a random quadrant each pickup; this cycles through the four so the
    # same config always produces the same macro.
    radius = _num(bg, "tray_enter_radius", 10)
    d = radius * 0.70711
    # The chord is swept from both corners, so whichever side runs out of
    # ground first sets it for all four quadrants — the same bound the
    # rectangular stir gets, and for the same reason. A dish sits in the strip
    # along the front, and a sweep wider than the strip is deep reaches south
    # of the origin, where there is nothing but the Y endstop: on the Mini's
    # dish, 15 mm of enter radius around a tray at Y 6 asks for Y -4.6.
    d = min(d, tray_x, tray_y, workable_x(conf) - tray_x)
    for i in range(max(1, reps)):
        qx, qy = _QUADRANTS[i % 4]
        lines += [
            f"G00 X{_fmt(tray_x)} Y{_fmt(tray_y)}",
            f"G00 Z{_fmt(dip)}",
        ]
        if d >= 0.5:
            lines += [
                f"G00 X{_fmt(tray_x + qx * d)} Y{_fmt(tray_y + qy * d)}",
                f"G00 X{_fmt(tray_x - qx * d)} Y{_fmt(tray_y - qy * d)}",
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
    shape = str(bg.get("cup_shape", "classic")).strip().lower()
    # Every move to somewhere new — a tray, the canvas, the origin — is preceded
    # by a lift to this, and only this: not the larger of it and some other
    # height, so a macro's travel Z is always the one the config names for it.
    go_lift = _num(bg, "go_in_tray_lift", 8)
    dip = _num(bg, "dip_depth", -4)
    park_z = dip + 1  # Dip Depth + 1 — where home.g, clean.g and zero.g all end
    # A config need not carry a travel limit distinct from the painted size —
    # sketch.py falls back the same way for the same reason.
    max_w = _num(bg, "max_width", _num(bg, "width", 200))
    max_h = _num(bg, "max_height", _num(bg, "height", 200))
    ox, oy = _num(bg, "offset_x", 0), _num(bg, "offset_y", 0)

    out: dict[str, str] = {}

    # zero.g — the machine's own self-zero dance: touch the near corner off at
    # 0,0,0, sweep to the far corner and back to confirm nothing is fouled,
    # re-zero at a travel height, then a short jog sequence that ends by
    # declaring the offset X10 Y0 Z10 point. The jog's last step is 1 mm more
    # on Y, so later moves to Y0 stop short of the endstop instead of hitting it. A fixed routine tuned on the
    # actual hardware, not derived from the config, except for two things: the
    # far corner is the model's — a Micro's racks end well short of the Mini's
    # 160 — and its very last line finishes the same way home.g and clean.g
    # do, parked at X0 Y0, Z = Dip Depth + 1.
    sweep_x, sweep_y, sweep_z = MODELS[model_of(conf)]["zero_sweep"]
    out["zero.g"] = "\n".join([
        "G10 P0 L20 X0 Y0 Z0;",
        "G0 Z10 F1000;",
        "G90;",
        f"G0 X{sweep_x} Y{sweep_y} Z{sweep_z} F2100;",
        f"G0 X0 Y0 Z{sweep_z} F2100;",
        "G10 P0 L20 X0 Y0 Z10;",
        "G1 Z15 F1000;",
        "G1 Z10 F1000;",
        "G0 X-10 Y-10 F1200;",
        "G0 X+2 Y-8 F2100;",
        "G0 Y-7 F2100;",
        "G10 P0 L20 X10 Y0 Z10;",
        f"G0 X0 Y0 Z{_fmt(park_z)} F2100;",
    ]) + "\n"

    # home.g — park at X0 Y0, Z = Dip Depth + 1.
    lines = [
        "; home.g — park over the origin, just above dipping depth",
        *_preamble(bg, "normal"),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift — clear before crossing the bed",
        *_park_at_origin(park_z),
    ]
    out["home.g"] = "\n".join(lines) + "\n"

    # paper.g — half of Max Width on X, all of Max Height on Y.
    px, py = max_w / 2, max_h
    lines = [
        "; paper.g — move the brush out of the way for replacing paper",
        *_preamble(bg, "normal"),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift — clear before crossing the bed",
        f"G00 X{_fmt(px)} Y{_fmt(py)} ; half of Max Width, all of Max Height",
    ]
    out["paper.g"] = "\n".join(lines) + "\n"

    # clean.g — wash the brush at the water container, then park. Three dips,
    # no rim wipe, matching copicograf's own wash_the_brush(); the park at the
    # end matches home.g's, so a clean brush is also a homed one.
    lines = [
        "; clean.g — wash the brush in the water container, then park",
        f"; containers: {shape}",
        *_preamble(bg, "fast"),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift",
        f"G00 X{_fmt(wx)} Y{_fmt(wy)}",
        *_container_motion(conf, wx, wy, reps=_WASH_REPS),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift",
        *_park_at_origin(park_z),
    ]
    out["clean.g"] = "\n".join(lines) + "\n"

    # calibrate.g — place the dot and park over it. No wash and nothing else:
    # this one is meant to do only the dot. It lifts first all the same, the
    # way every other macro here does, because it is run from wherever the
    # brush was left and where these macros leave it is X0 Y0 at Dip Depth + 1
    # — inside the water container, under its rim. Crossing to the canvas
    # origin from there at that height drags the brush through the container
    # wall, so the trip starts at Go In Tray Lift, the height that clears the
    # rims. Z0 and Z10 stay literal for this macro specifically, not
    # canvas_height or go_in_tray_lift: the dot is the canvas itself, and the
    # park is only high enough to see it.
    lines = [
        "; calibrate.g — place the dot, then park over it",
        *_preamble(bg, "normal"),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift — clear before crossing the bed",
        f"G00 X{_fmt(ox)} Y{_fmt(oy)} ; the canvas origin",
        "G00 Z0 ; touch down — the single dot",
        "G00 Z10 ; park over the dot",
    ]
    out["calibrate.g"] = "\n".join(lines) + "\n"

    # Every macro, zero.g's fixed routine included, says what made it.
    return {name: gcode_note() + "\n" + text for name, text in out.items()}
