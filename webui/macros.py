"""Seven small utility routines.

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

containercenter.g paints a tick on the canvas at the X of every container
the config names, so the positions typed into the form can be held against
the holder they claim to describe. It is the one macro here that paints:
black loads the brush, a tick at a time, and the brush is washed and parked
at the end the way a job leaves it. A machine with no black cup -- a classic
one, whose four dishes hold water and three colours -- gets a file that says
so and paints nothing. Its file name keeps the spelling it was asked for;
renaming it now would strand the copy already sitting in a machine's flash.

backlash.g is the one that draws: a sheet of paired strokes for
reading the play in each axis off, one pair arriving from each side, against a
gauge of known gaps. It is drawn with a pen fitted where the brush goes, so it
visits no cup and dips for nothing -- the machine needs no paint in it. Five
stations, each answering both axes where it stands: the four corners of
everything the machine can paint, which is wider than the canvas a job uses,
and the middle. It wants a pen in the holder and paper under all of it.

None of the seven carries an M-code or a G28, so none needs the controller
dialect handling `gcode_pipeline.sanitize_for_controller` does for a real job:
G90/G0/G1/G10 are understood the same way by Marlin, GRBL and FluidNC.
"""
from __future__ import annotations

from configspec import (CMYK_TO_TRAY, MODELS, RECTANGULAR_SHAPES,
                        fit_cups_to_shape, holder_of, in_cup_order, model_of,
                        tray_entries, with_defaults, workable_x)
from gcode_pipeline import to_ascii
from version import gcode_note

MACRO_NAMES = ["zero.g", "home.g", "paper.g", "clean.g", "calibrate.g",
               "containercenter.g", "backlash.g"]

# The gauges of backlash.g, in millimetres. A half-millimetre gap between
# two drawn lines is not something a ruler settles, whether they were drawn
# with a pen or painted a millimetre wide with a brush: each gauge prints
# known gaps, drawn so the play cannot affect them,
# and the test pairs are matched against it by eye. There is one per axis,
# each in its own axis's orientation -- a gap between two horizontal lines is
# not judged against a gap between two vertical ones, and which of the two
# axes carries the larger play is the machine's own business.
_GAUGE_GAPS = (0.5, 1.0, 1.5, 2.0, 2.5)

# How long a leg of a test station is, in millimetres: at most _TEST_LEG, and
# never less than _LEG_MIN. A pen is not working out of a dip, so the figure
# is about reading and not about paint. The cap is where more length stops
# telling you anything; the floor is where a pair of lines stops being a pair
# you can look along, and it is the one figure here allowed to push the
# gauges into showing fewer pairs. Between them the legs take what is left
# once both gauges have their room -- 30 mm on a Mini, and the floor itself on
# a Mikro, whose 65 mm of X has to hold two gauges and a station besides.
_TEST_LEG = 30.0
_LEG_MIN = 10.0

# How much clear paper is left between a station and a gauge, and between the
# gauges. Enough that nothing reads as belonging to its neighbour.
_CLEAR = 3.0

# The room a gauge is given before anything else gets any: its own gaps plus
# 2 mm of clear paper between each pair. The stations are sized around it, so
# a station is as long as the paper allows once both gauges are legible --
# rather than as long as it likes, with the gauges taking what is left.
_GAUGE_MIN = sum(_GAUGE_GAPS) + 2.0 * (len(_GAUGE_GAPS) - 1)

# How far a stroke backs off before it comes in, so the axis is certainly
# travelling the way the test means it to when it arrives. It only has to
# exceed the play itself; it is clamped to the bed for a machine with no room
# to give it, and the test still holds as long as something is left.
_RUN_UP = 12.0

# How long a containercenter.g tick is, in millimetres, and the shortest one
# worth painting. 20 is long enough to sight along and to lay a rule against,
# and short enough to come out of one pickup with room to spare -- the kept
# configs carry 150 to 180 mm of painting between dips, and the shortest
# canvas of the two machines is 70 mm deep, so the tick fits on the paper as
# well as in the brush.
_TICK = 20.0
_TICK_MIN = 2.0

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


def _gap_list(gaps: list[float]) -> str:
    """"0.5, 1, 1.5, 2 and 2.5" -- a gauge's gaps, for its own header."""
    shown = [_fmt(g) for g in gaps]
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


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


def _run_up(pos: float, approach: int, lo: float, hi: float) -> float:
    """How far a stroke at `pos` may back off before it comes in.

    _RUN_UP, or whatever of it there is room for: the point is only that the
    axis is certainly travelling the way the stroke means it to when it
    arrives, so a short one still holds, and a move that backed off past the
    end of an axis would finish against a stop instead.
    """
    room = (pos - lo) if approach > 0 else (hi - pos)
    return max(0.0, min(_RUN_UP, room))


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
    """The macros, as {filename: text}, in MACRO_NAMES order."""
    # fit_cups_to_shape as well as with_defaults, the way new_config and
    # apply_form both normalise a config: with_defaults offers a black cup to
    # every config, because the form is built once and the container shape can
    # change under it, and on a classic machine there is no fifth petri dish
    # for it to be. Left in, it is a cup nothing can dip in, guessed one step
    # past yellow -- off the end of the dish holder, and marked on the paper by
    # containercenter.g as though it were somewhere.
    conf = fit_cups_to_shape(with_defaults(conf))
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

    # What the two macros that draw have in common. Both touch down at
    # canvas_height, the figure the brush already paints the paper at, so a pen
    # fitted in its place draws at the height the config names and neither
    # macro has to invent a pen height nobody has a setting for.
    cz = _num(bg, "canvas_height", 0)
    wx_lim = workable_x(conf)
    # How far either of them may command, run-ups included: a few millimetres
    # short of the ends, so that nothing finishes against a stop. What a move
    # loses against a stop it loses for the rest of the file, and every line
    # after it lands short of where it says -- which in a file whose whole
    # content is where lines land would not look like a fault at all.
    reach_x, reach_y = wx_lim - _CLEAR, max_h - _CLEAR

    # containercenter.g -- the X of every container, painted on the canvas in
    # black, so the container positions in the form can be held against the
    # holder they claim to describe. A container position is the one setting
    # with nothing to check it against: where a cup is, is a measurement
    # somebody took with a rule and typed in, and the only way to read it back
    # was to watch a dip and judge by eye whether the brush went into the
    # middle of the cup or into a wall.
    #
    # Only X, and only on the canvas. The containers and the canvas share the
    # X axis and nothing else -- the cups sit in the strip of Y below the
    # paper -- so X is the whole of what a mark up on the paper can say about
    # them, and it is the interesting half: it is the spacing along the row
    # that auto-spacing guesses and a rule measures badly. The marks are
    # painted where a job paints, on paper that is already there, with no
    # container lifted out and nothing dismantled.
    #
    # Black paints them because black is the colour that shows on every paper
    # the six themes are drawn on, and because a machine with a black cup has
    # a CMYK holder: fit_cups_to_shape takes the black cup away from a classic
    # machine, whose four petri dishes hold water and three colours. That
    # machine gets a file that says so and paints nothing, rather than one
    # that dips into a cup which is not there.
    trays = conf.get("trays", {})
    black = trays.get(CMYK_TO_TRAY["K"]) if isinstance(trays, dict) else None
    cups = [(e, _num(e, "x")) for e in in_cup_order(tray_entries(conf))]
    # The canvas: where the paper is, and the near edge of it is where the
    # ticks stand. That edge is the closest the paper comes to the containers,
    # so a tick can be sighted down to the cup it belongs to without anything
    # in between.
    can_w, can_h = _num(bg, "width", max_w), _num(bg, "height", max_h)
    tick = min(_TICK, max(0.0, can_h))

    lines = [
        "; containercenter.g -- paint the X of every container on the canvas,",
        "; to check the container positions in the form against the holder.",
        ";",
        "; Black paints the ticks, so put paint in the black cup and paper on",
        "; the canvas. Nothing is lifted out and nothing is dismantled: the",
        "; marks go where a job paints. Each tick stands at one container's X,",
        "; on the near edge of the canvas, which is the closest the paper comes",
        "; to the containers.",
        ";",
        "; Only X is marked, because X is all the canvas can say about a",
        "; container: the cups sit in the strip of Y below the paper. It is the",
        "; interesting half -- the spacing along the row is what auto-spacing",
        "; guesses, and what a rule measures worst.",
        ";",
        "; Sight each tick down to the cup it belongs to, or lay the holder",
        "; along the row of them. A tick that does not line up with the middle",
        "; of its cup is a position that wants correcting, and how far it",
        "; misses by is the correction, in millimetres, into that container's",
        "; X. Water is ticked too, and it is the one to correct first: every",
        "; other cup is spaced from it.",
        ";",
        "; The brush is dipped once per tick and washed and parked at the end,",
        "; the way a job leaves it.",
    ]

    # Two ways there is nothing to paint, each said in the file rather than
    # left to be guessed at from a sheet that came out blank.
    if black is None:
        lines += [
            ";",
            "; This machine has no black container -- the Classic petri dish",
            "; holder has four places, water and three colours -- so there is",
            "; nothing to paint the ticks with and this file does nothing.",
            "; Select the CMYK holder under Containers and generate again.",
            *_preamble(bg, "normal"),
        ]
    elif tick < _TICK_MIN:
        lines += [
            ";",
            f"; The canvas is {_fmt(can_h)} mm deep, which is not enough to",
            "; paint a tick in, so this file does nothing.",
            *_preamble(bg, "normal"),
        ]
    else:
        bx, by = _num(black, "x"), _num(black, "y")
        off_canvas = [e["label"] for e, ex in cups
                      if not ox <= ex <= ox + can_w]
        if off_canvas:
            # Painted all the same, because the machine can reach them, and a
            # row of ticks missing its end says least about the end -- which is
            # where the spacing has had furthest to drift. Pinkograph's black
            # cup stands at X 156 against a canvas that ends at 132: that tick
            # wants paper of its own, or it is painted on the bed.
            lines += [
                ";",
                "; One tick or more stands past the end of the canvas and",
                "; lands off the paper unless a wider sheet is laid for it.",
                "; They are painted anyway: a row of ticks missing its last one",
                "; says least about the end of the row, which is where the",
                "; spacing has had furthest to drift. Past the end here: "
                + ", ".join(off_canvas) + ".",
            ]
        lines += [
            ";",
            f"; {len(cups)} containers, in the order they stand on the bed.",
            f"; Painted from the black cup at X{_fmt(bx)} Y{_fmt(by)},"
            f" {_fmt(tick)} mm a tick.",
            *_preamble(bg, "normal"),
            f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- clear before crossing the bed",
        ]
        for entry, ex in cups:
            head = f"; {entry['label']} [{entry['tray']}] -- X{_fmt(ex)}"
            if not 0 <= ex <= wx_lim:
                # A container the config puts somewhere the machine cannot go.
                # Painting the nearest reachable X instead would put a tick
                # that is not where it says it is, which is the one thing this
                # file must not do.
                lines.append(head + " -- out of reach, not painted")
                continue
            lines.append(head)
            # A pickup per tick. A job works a brushful across 150 mm and more
            # of painting, so 20 mm of tick is nowhere near a dry brush -- but
            # the cup is passed anyway between one tick and the next, and a
            # tick painted with a full brush is the same width as the one
            # before it, which is what makes the row worth looking along.
            # _container_motion makes its own approach to the cup, and makes
            # it to the clamped near edge of the bay rather than to the centre
            # the config names. Moving to the centre first, the way clean.g
            # does, is a move to Y -3 on Brushparang, which is the Y endstop:
            # the clamp inside that helper exists precisely because a cup can
            # be configured south of the ground there is.
            lines += [f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- the black cup",
                      *_container_motion(conf, bx, by, reps=1)]
            lines += _comb_stroke(True, ex, oy, oy + tick, 1,
                                  _run_up(ex, 1, 0.0, wx_lim), cz, go_lift)
        # Washed and parked in the water, the way a job leaves the brush:
        # there is black paint in it, and the shared park at Dip Depth + 1 is
        # inside the water cup on a holder whose water crucible covers the
        # origin.
        lines += [
            "; wash and park",
            f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- the water cup",
            *_container_motion(conf, wx, wy, reps=_WASH_REPS),
            f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift",
            *_park_at_origin(park_z),
        ]
    out["containercenter.g"] = "\n".join(lines) + "\n"

    # backlash.g -- the calibration sheet for Backlash X and Backlash Y,
    # drawn dry with a pen fitted in the holder in place of the brush.
    #
    # It was painted until v2.10.3. Measuring the play does not need paint:
    # the sheet is lines on paper and the reading is the gap between two of
    # them, which a pen makes as well as a brush does, and without a cup of
    # colour, a dip, or a wash afterwards. What the paint cost was the sheet itself -- every pair had
    # to come out of one pickup, 150 mm of painting on Pinkograph, so no
    # stroke could be longer than 55 mm and no station could be anywhere the
    # brush could not be fed from a cup.
    #
    # Backlash does not accumulate. Alternating moves lose the play once and
    # get it back on the next reversal, and a staircase with a net direction
    # loses it on the way out and regains it on the way back, so there is no
    # arrangement of moves that turns a half millimetre into a visible ten.
    # That rules out a drift test and leaves reading a gap, which is why this
    # prints a gauge alongside: the eye is poor at half a millimetre in the
    # open and good at telling two lines from one against a known example.
    #
    # Five stations -- the four corners of the sheet and its middle -- because
    # neither axis has one play. X changes along X, which is the belt; Y
    # changes along X too, which is the beam twisting. Both of those a row
    # across the bed could see. What a row cannot see is either of them
    # changing along Y, and a corner at each end of both axes can: two
    # stations at the same X that disagree say the play depends on where the
    # gantry is standing, which no pair of figures in the form can describe.
    # The middle is the check -- with the play a straight line across the bed
    # it falls halfway between the corners.
    # The sheet is laid out on everything the machine can paint, not on the
    # canvas the config happens to be set to. The figures it produces are
    # applied to every job on the machine, whatever size that job is, so they
    # are read across the whole of the ground those jobs can cover: a Mini
    # asked to paint 132 by 89 in the middle of a 151 by 156 bed would
    # otherwise be measured over two thirds of its X and well under half its
    # Y, and the play at the ends -- which is the whole point of the far-end
    # boxes -- read where the belt is not at its longest.
    #
    # The far edge is the paintable width or workable_x, whichever is nearer:
    # workable_x is how far a job already asks the machine to go and so how
    # far it is known to reach, and it is never the axis travel, because that
    # is where zero.g drives into the stops on purpose. The near edge is the
    # canvas offset, which is what keeps the pen out of the containers: on a
    # Mini they sit in the 32 mm of Y below the paper.
    paint_w = max(0.0, min(max_w, wx_lim) - ox)
    paint_h = max(0.0, max_h - oy)

    def pair(vertical, pos, start, end, lo, hi):
        """The two strokes of one test pair: one commanded line, drawn once
        arriving from each side, so the gap between the marks is the play."""
        lines = []
        for approach in (1, -1):
            lines += _comb_stroke(vertical, pos, start, end, approach,
                                  _run_up(pos, approach, lo, hi), cz, go_lift)
        return lines

    def gauge(vertical, at, gap, start, end, lo, hi):
        """One gauge pair: the same stroke twice, `gap` apart, same side both
        times, so what is printed is the number and not the number plus the
        play."""
        lines = []
        for edge in (at, at + gap):
            lines += _comb_stroke(vertical, edge, start, end, 1,
                                  _run_up(edge, 1, lo, hi), cz, go_lift)
        return lines

    def gauge_gaps(span: float) -> list[float]:
        """Which gaps a gauge with `span` millimetres to draw in can show.

        All five where there is room, and otherwise the widest are dropped
        one at a time until the clear space between pairs is at least as wide
        as the widest gap drawn. A reader who cannot tell the space after a
        pair from the pair itself has no ruler, and the gaps that go are the
        ones least needed: a gap of 2.5 mm is wide enough to lay a rule
        across, which is what a gauge is for saving you from at half a
        millimetre. The remaining pairs always run 0.5, 1, 1.5 ... from the
        narrowest, so they are counted from that end and none is ambiguous.
        """
        for n in range(len(_GAUGE_GAPS), 1, -1):
            gaps = _GAUGE_GAPS[:n]
            clear = (span - sum(gaps)) / (n - 1)
            if clear >= gaps[-1]:
                return list(gaps)
        return list(_GAUGE_GAPS[:2])

    def gauge_slots(lo: float, hi: float, gaps: list[float]) -> list[float]:
        """Where each gauge pair starts, with the same clear space between
        every pair whatever gap it is drawing.

        Spread evenly instead, the 0.5 mm pair sits in a slot as wide as the
        2.5 mm pair does and the clear space after the widest one shrinks
        towards its own gap, which is the one place a reader must not have to
        guess which line belongs to which pair.
        """
        clear = max(0.0, hi - lo - sum(gaps)) / max(1, len(gaps) - 1)
        at, out = lo, []
        for gap in gaps:
            out.append(at)
            at += gap + clear
        return out

    # The corners. Every stroke backs off _RUN_UP before it comes in, so a
    # station can stand at the very edge of the paintable area only where the
    # machine can reach that far past it: the outermost ones go to the corners
    # and are pulled in exactly as far as the run-up needs, and no further.
    # Pinkograph's stations come out at X12 and X141 of a bed that paints 0 to
    # 151, and at Y32 -- the bottom of the paper, with the containers in the
    # Y below it -- and Y141 of 156.
    x0 = max(ox, _RUN_UP)
    x1 = max(x0, min(ox + paint_w, reach_x - _RUN_UP))
    y0 = max(oy, _RUN_UP)
    y1 = max(y0, min(oy + paint_h, reach_y - _RUN_UP))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def station(px: float, py: float, sx: int, sy: int, note: str) -> list[str]:
        """One station: an upright pair and a flat pair meeting at (px, py).

        The upright pair is that station's X figure and the flat pair its Y
        figure, so one station answers both axes at one place on the bed.

        Both legs are drawn in the positive direction whichever corner they
        belong to, the corner ones running inward and the middle's centred on
        it. `_comb_stroke` settles by backing off before the start of a line,
        and at the far end of an axis backing off is backing into the stop.
        """
        span = leg / 2 if (sx == 0 or sy == 0) else leg
        vy = (py, py + span) if sy >= 0 else (py - span, py)
        hx = (px, px + span) if sx >= 0 else (px - span, px)
        if sx == 0 and sy == 0:
            vy, hx = (py - span, py + span), (px - span, px + span)
        return [
            f"; station at X{_fmt(px)} Y{_fmt(py)} -- {note}",
            *pair(True, px, vy[0], vy[1], 0.0, reach_x),
            *pair(False, py, hx[0], hx[1], 0.0, reach_y),
        ]

    # Where the two gauges go, and how long a station's leg is, which is one
    # question and not two. The stations hold the corners and the middle; what
    # is left for the gauges is the band between the top and bottom pairs of
    # them, either side of the middle station. Both rulers get their room
    # first and the legs take what remains, so the answer on a small machine
    # is short legs and a legible gauge rather than the reverse. The Mini's
    # legs come out at the 30 mm cap and the Mikro's at the 10 mm floor, and
    # on the Mikro it is the gauges that then give way: its X gauge shows four
    # pairs where the Mini's shows five.
    usable_w, usable_h = x1 - x0, y1 - y0
    leg = max(_LEG_MIN, min(_TEST_LEG,
                            0.25 * min(paint_w, paint_h),
                            usable_w - 2 * _GAUGE_MIN - 2 * _CLEAR,
                            (usable_h - 2 * _CLEAR - _GAUGE_MIN) / 2))
    # The Y gauge's rows to the left of the middle station, the X gauge's
    # columns to its right, both drawn the height of the band. A gauge is a
    # ruler and can sit anywhere it is legible; these two places are simply
    # the paper the stations do not want.
    band = (y0 + leg + _CLEAR, y1 - leg - _CLEAR)
    left = (x0, cx - leg / 2 - _CLEAR)
    right = (cx + leg / 2 + _CLEAR, x1)
    yg_slots, yg_run = band, (left[0], min(left[1], left[0] + leg * 2))
    xg_slots, xg_run = right, (band[0], min(band[1], band[0] + leg * 2))
    xg_gaps = gauge_gaps(xg_slots[1] - xg_slots[0])
    yg_gaps = gauge_gaps(yg_slots[1] - yg_slots[0])

    lines = [
        "; backlash.g -- measure the play in X and Y with a pen, to fill in",
        "; Backlash X, Backlash X far end, Backlash Y and Backlash Y far end.",
        "; Needs a pen fitted where the brush goes, and paper under all of it:",
        "; it is drawn over everything the machine can paint and not over the",
        "; canvas a job happens to be set to, so lay a full sheet on the bed or",
        "; the outer marks will land on the bed itself. It visits no cup and",
        "; dips for nothing, so the machine needs no paint in it and there is",
        "; nothing to wash afterwards.",
        ";",
        "; Every pair is one commanded position drawn twice, arrived at from",
        "; each side in turn, and the gap between the two marks is the play.",
        ";",
        "; Five stations: the corners of the paintable area and its middle --",
        f"; here X{_fmt(x0)} to X{_fmt(x1)} and Y{_fmt(y0)} to Y{_fmt(y1)}."
        " Each is an",
        "; upright pair and a flat pair meeting at a corner: the upright one",
        "; is that station's X figure, read across the line, and the flat one",
        "; its Y figure, read up and down it.",
        ";",
        "; Backlash X is the two upright pairs at the X0 end and Backlash X far",
        "; end the two at the other; Backlash Y is the two flat pairs at the X0",
        "; end and Backlash Y far end the two at the other. Two stations at the",
        "; same end should agree: where they do not, the play depends on where",
        "; the gantry is standing along Y as well, which no pair of figures can",
        "; describe -- take the middle station's reading for both boxes and",
        "; expect the compensation to be right in the middle and light at the",
        "; edges. The middle station is the check either way: with the play a",
        "; straight line across the bed it falls halfway between the corners.",
        ";",
        "; Then the two gauges, each in its own direction: the Y gauge's rows",
        "; to the left of the middle station and the X gauge's columns to its",
        "; right. Both strokes of a gauge pair arrive from the same side, so",
        "; the play cannot open or close them: they are the ruler. Find the",
        "; gauge pair a test pair looks like and that is the figure, to a",
        "; tenth or so. Do not read one gauge against the other's pairs -- a",
        "; gap between two horizontal lines does not look like the same gap",
        "; between two vertical ones.",
        (f"; Both gauges are drawn {_gap_list(xg_gaps)} mm apart, narrowest"
         if xg_gaps == yg_gaps else
         f"; The X gauge is drawn {_gap_list(xg_gaps)} mm apart and the Y one"),
        ("; first, so count from that end. A" if xg_gaps == yg_gaps else
         f"; {_gap_list(yg_gaps)}, narrowest first, so count from that end. A"),
        "; gap wider than the widest pair drawn is wide enough to lay a rule",
        "; across, which is what a gauge is for saving you from at half a",
        "; millimetre and not at three -- so where the paper is too narrow to",
        "; keep the widest pairs apart from their neighbours, they are the",
        "; ones dropped.",
        ";",
        "; The corners stand as far out as the machine can measure, which is",
        "; not always the edge of the paint: every stroke backs off 12 mm and",
        "; comes in along the axis under test, so a station can only stand",
        "; where there is 12 mm of ground beyond it, and nothing here is",
        "; commanded within 3 mm of either far end. A move that finishes",
        "; against a stop loses what it loses for the rest of the file.",
        *_preamble(bg, "normal"),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- clear before crossing the bed",
    ]

    # Round the sheet and then the middle, which is also the shortest way
    # between them.
    for px, py, sx, sy, note in (
        (x0, y0, 1, 1, "near X, near Y"),
        (x1, y0, -1, 1, "far X, near Y"),
        (x1, y1, -1, -1, "far X, far Y"),
        (x0, y1, 1, -1, "near X, far Y"),
        (cx, cy, 0, 0, "the middle"),
    ):
        lines += station(px, py, sx, sy, note)

    for at, gap in zip(gauge_slots(*xg_slots, xg_gaps), xg_gaps):
        lines.append(f"; X gauge pair {_fmt(gap)} mm")
        lines += gauge(True, at, gap, xg_run[0], xg_run[1], 0.0, reach_x)
    for at, gap in zip(gauge_slots(*yg_slots, yg_gaps), yg_gaps):
        lines.append(f"; Y gauge pair {_fmt(gap)} mm")
        lines += gauge(False, at, gap, yg_run[0], yg_run[1], 0.0, reach_y)

    lines.append(f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift")
    # Not the shared park: that one ends at Dip Depth + 1, which is below the
    # paper, and on a holder whose water crucible covers the origin it is
    # under the rim. A brush left there is a brush kept wet; a pen left there
    # is a pen pressed into whatever is under it.
    lines.append("G00 X0 Y0 ; park lifted -- a pen has no cup to hang in")
    out["backlash.g"] = "\n".join(lines) + "\n"

    # Every macro, zero.g's fixed routine included, says what made it — and
    # goes out in ASCII, like everything else the machine is sent.
    return {name: to_ascii(gcode_note() + "\n" + text)
            for name, text in out.items()}
