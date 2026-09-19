"""Six small utility routines.

home.g parks the brush, paper.g moves it out of the way for replacing the
paper, and clean.g washes the brush the way a real job does before parking
too. The wash in clean.g follows whichever container shape
`brushograph.cup_shape` names, classic, modern or custom. All three, plus zero.g's
own last line, end the same way — parked at X0 Y0, Z = Dip Depth + 1 — via
the shared `_park_at_origin()`.

zero.g is the machine's own self-zero dance — a fixed sequence tuned on the
actual hardware, reproduced here verbatim, with the config read for nothing
but the model's far corner and that final park.

calibrate.g is the odd one out on purpose: no wash, just the dot and a park
over it, at two literal heights that are neither `canvas_height` nor
`go_in_tray_lift`.

backlash.g is the only one that paints: a sheet of paired strokes for reading
the play in each axis off, one pair drawn arriving from each side, against a
gauge of known gaps. It wants paper on the bed and paint in the cups.

None of the six carries an M-code or a G28, so none needs the controller
dialect handling `gcode_pipeline.sanitize_for_controller` does for a real job:
G90/G0/G1/G10 are understood the same way by Marlin, GRBL and FluidNC.
"""
from __future__ import annotations

from configspec import (MODELS, RECTANGULAR_SHAPES, holder_of, model_of,
                        tray_entries, with_defaults, workable_x)
from version import gcode_note

MACRO_NAMES = ["zero.g", "home.g", "paper.g", "clean.g", "calibrate.g",
               "backlash.g"]

# backlash.g's gauges, in millimetres. A brush stroke is about a millimetre
# wide, so a half-millimetre gap between two of them is not something a ruler
# settles: each gauge prints known gaps, drawn so the play cannot affect them,
# and the test pairs are matched against it by eye. There is one per axis,
# each in its own axis's orientation -- a gap between two horizontal lines is
# not judged against a gap between two vertical ones, and the Y play is the
# larger of the two on the machine this was written for.
_GAUGE_GAPS = (0.5, 1.0, 1.5, 2.0, 2.5)

# Where the eight pairs of a section sit across it: three test pairs, a clear
# break, then the five of the gauge. The break is wider than any spacing
# inside either group, so neither can be counted into the other.
_SLOTS = (0.0, 0.11, 0.22, 0.42, 0.56, 0.70, 0.84, 0.98)

# A stroke long enough to read a gap along and no longer: two of them plus the
# travel between has to come out of one dip, and Pinkograph's paint_per_run_max
# is 150 mm. At the full height of the canvas a pair came to 163.
_STROKE_MAX = 55.0

# How far a stroke backs off before it comes in, so the axis is certainly
# travelling the way the test means it to when it arrives. It only has to
# exceed the play itself; it is clamped to the bed for a machine with no room
# to give it, and the test still holds as long as something is left.
_RUN_UP = 12.0

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


def _comb_stroke(vertical: bool, pos: float, start: float, end: float,
                 approach: int, run_up: float, canvas_z: float,
                 lift: float) -> list[str]:
    """One stroke of the comb, arrived at from the side `approach` names.

    The last move before the brush goes down is along the axis under test, so
    that axis is definitely travelling the way this stroke wants it to. The
    move before that is along the other one, in the same direction the stroke
    itself runs, which keeps the play out of the end of the line: a stroke that
    began with a reversal would start a millimetre and a half short of where it
    says, and the ends of these lines are what is being read.
    """
    pre = pos - approach * run_up
    # The settle backs off along the axis the stroke runs, and by the same
    # distance as the run-up rather than a token millimetre or two: this
    # macro exists because the play is not known, so a settle that assumed it
    # was small would displace the start of every stroke on a machine loose
    # enough to be worth measuring. Clamped, because on a canvas starting at
    # the origin it backs straight into the endstop -- the first pair of a
    # Mikro's Y test asked for X -0.6, and what a move loses against a stop it
    # loses for the rest of the file.
    settle = max(0.0, start - run_up)
    if vertical:
        travel = [
            f"G00 X{_fmt(pre)} Y{_fmt(settle)}",
            f"G00 X{_fmt(pre)} Y{_fmt(start)} ; settle Y before the stroke",
            f"G00 X{_fmt(pos)} Y{_fmt(start)} ; arrive from the "
            + ("left" if approach > 0 else "right"),
        ]
        draw = f"G01 X{_fmt(pos)} Y{_fmt(end)}"
    else:
        travel = [
            f"G00 X{_fmt(settle)} Y{_fmt(pre)}",
            f"G00 X{_fmt(start)} Y{_fmt(pre)} ; settle X before the stroke",
            f"G00 X{_fmt(start)} Y{_fmt(pos)} ; arrive from "
            + ("below" if approach > 0 else "above"),
        ]
        draw = f"G01 X{_fmt(end)} Y{_fmt(pos)}"
    return [*travel, f"G01 Z{_fmt(canvas_z)}", draw, f"G00 Z{_fmt(lift)}"]


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
    # The painted area, not the travel limits: backlash.g draws on the paper.
    w, h = _num(bg, "width", 100), _num(bg, "height", 100)

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

    # backlash.g -- the calibration sheet for Backlash X and Backlash Y.
    #
    # Backlash does not accumulate. Alternating moves lose the play once and
    # get it back on the next reversal, and a staircase with a net direction
    # loses it on the way out and regains it on the way back, so there is no
    # arrangement of moves that turns a half millimetre into a visible ten.
    # That rules out a drift test and leaves reading a gap, which is why this
    # prints a gauge alongside: the eye is poor at half a millimetre in the
    # open and good at telling two lines from one against a known example.
    #
    # Three pairs per axis rather than one, spread across the bed, because a
    # belt that has gone slack in one place and a nut with play in it
    # everywhere do not read the same, and the answer to put in the box is
    # only a single figure if the three pairs agree.
    cz = _num(bg, "canvas_height", 0)
    wx_lim = workable_x(conf)
    # The sheet is laid out on the painted area, but a config is free to name a
    # canvas that runs past what the machine can reach -- sketch.py draws that
    # overhang rather than flattering it, and here it would drive into a stop.
    sheet_w = max(0.0, min(w, wx_lim - ox))
    sheet_h = max(0.0, min(h, max_h - oy))
    entries = tray_entries(conf)
    # The last tray in painting order is the darkest the config has -- black
    # where there is a black cup, cyan on a classic holder that has no room
    # for one. Water only if there are no colours at all, which will draw
    # nothing much, but the geometry is still right and the file still runs.
    load = entries[-1] if entries else {"x": wx, "y": wy, "label": "water"}
    lx, ly = _num(load, "x", wx), _num(load, "y", wy)

    def run_up(pos: float, approach: int, lo: float, hi: float) -> float:
        room = (pos - lo) if approach > 0 else (hi - pos)
        return max(0.0, min(_RUN_UP, room))

    def dip() -> list[str]:
        return [f"G00 Z{_fmt(go_lift)}", f"G00 X{_fmt(lx)} Y{_fmt(ly)}",
                *_container_motion(conf, lx, ly, reps=1)]

    def pair(vertical, pos, start, end, lo, hi):
        """The two strokes of one test pair, and the dip that feeds them."""
        lines = dip()
        for approach in (1, -1):
            lines += _comb_stroke(vertical, pos, start, end, approach,
                                  run_up(pos, approach, lo, hi), cz, go_lift)
        return lines

    def gauge(vertical, at, gap, start, end, lo, hi):
        """One gauge pair: the same stroke twice, `gap` apart, same side both
        times, so what is printed is the number and not the number plus the
        play."""
        lines = dip()
        for edge in (at, at + gap):
            lines += _comb_stroke(vertical, edge, start, end, 1,
                                  run_up(edge, 1, lo, hi), cz, go_lift)
        return lines

    lines = [
        "; backlash.g -- measure the play in X and Y, to fill in Backlash X",
        "; and Backlash Y with. Needs paper on the bed and paint in the cups.",
        ";",
        "; Two sections, set apart, each read on its own and each with its own",
        "; gauge in its own direction. Every pair is one commanded position",
        "; drawn twice, arrived at from each side in turn, and the gap between",
        "; the two marks is the play.",
        ";",
        "; X section: vertical strokes, the pairs spread along X, arriving",
        "; from the left and from the right.",
        "; Y section: horizontal strokes, the pairs spread along Y, arriving",
        "; from below and from above.",
        ";",
        "; In each section the first three pairs are the test, then a clear",
        "; break, then five gauge pairs drawn "
        + ", ".join(_fmt(g) for g in _GAUGE_GAPS[:-1])
        + " and " + _fmt(_GAUGE_GAPS[-1]) + " mm apart, in that order.",
        "; Both strokes of a gauge pair arrive from the same side, so the play",
        "; cannot open or close them: they are the ruler. Find the gauge pair",
        "; a test pair looks like and that is the figure, to a tenth or so.",
        "; Do not read one section's gauge against the other's pairs -- a gap",
        "; between two horizontal lines does not look like the same gap",
        "; between two vertical ones.",
        ";",
        "; Three test pairs an axis rather than one because a belt slack in",
        "; one place and a nut with play in it everywhere do not read the",
        "; same. If the three disagree, one figure will not compensate all of",
        "; it; take the middle and expect the ends to stay soft.",
        f"; Loading from the {load.get('label', 'last')} cup, one dip a pair.",
        *_preamble(bg, "normal"),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- clear before crossing the bed",
    ]

    # The two sections, each with its own gauge, set well apart. The X section
    # is vertical strokes spread along X and the Y section horizontal strokes
    # spread along Y, so one of them wants width and the other height: side by
    # side on a canvas wider than it is tall, stacked on one taller than it is
    # wide. That is the difference between the Mini at 132 by 89 and the Mikro
    # at 65 by 100, and doing it the one way for both puts eight of the
    # Mikro's columns into 65 mm, where a 2.5 mm pair has nothing between it
    # and the next.
    #
    # Both sections keep off the near edges by the run-up, where the canvas
    # can spare it: every stroke backs off that way before it comes in, and
    # below X0 and Y0 there is nothing to back off into but the endstop.
    pad_x = min(_RUN_UP, sheet_w * 0.12)
    pad_y = min(_RUN_UP, sheet_h * 0.12)
    if sheet_w >= sheet_h:
        y_box = (ox + pad_x, oy + pad_y, ox + sheet_w * 0.38, oy + sheet_h * 0.99)
        x_box = (ox + sheet_w * 0.46, oy + pad_y, ox + sheet_w * 0.99, oy + sheet_h * 0.99)
    else:
        x_box = (ox + pad_x, oy + sheet_h * 0.62, ox + sheet_w * 0.99, oy + sheet_h * 0.99)
        y_box = (ox + pad_x, oy + pad_y, ox + sheet_w * 0.62, oy + sheet_h * 0.54)

    def slots(lo: float, hi: float) -> list[float]:
        """The eight pair positions across a section, the widest gauge gap
        left over at the far end so the last pair still lands on the paper."""
        span = max(0.0, hi - max(_GAUGE_GAPS) - lo)
        return [lo + f * span for f in _SLOTS]

    # The X section: vertical strokes, the pairs spread along X.
    vy0 = x_box[1]
    vy1 = min(x_box[3], vy0 + _STROKE_MAX)
    cols = slots(x_box[0], x_box[2])
    for at in cols[:3]:
        lines.append(f"; X pair at {_fmt(at)}")
        lines += pair(True, at, vy0, vy1, 0.0, wx_lim)
    for at, gap in zip(cols[3:], _GAUGE_GAPS):
        lines.append(f"; X gauge pair {_fmt(gap)} mm")
        lines += gauge(True, at, gap, vy0, vy1, 0.0, wx_lim)

    # The Y section: horizontal strokes, the pairs spread along Y.
    hx0 = y_box[0]
    hx1 = min(y_box[2], hx0 + _STROKE_MAX)
    rows = slots(y_box[1], y_box[3])
    for at in rows[:3]:
        lines.append(f"; Y pair at {_fmt(at)}")
        lines += pair(False, at, hx0, hx1, 0.0, max_h)
    for at, gap in zip(rows[3:], _GAUGE_GAPS):
        lines.append(f"; Y gauge pair {_fmt(gap)} mm")
        lines += gauge(False, at, gap, hx0, hx1, 0.0, max_h)

    lines += [f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift", *_park_at_origin(park_z)]
    out["backlash.g"] = "\n".join(lines) + "\n"

    # Every macro, zero.g's fixed routine included, says what made it.
    return {name: gcode_note() + "\n" + text for name, text in out.items()}
