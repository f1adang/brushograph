#!/usr/bin/python3
"""Turns a machine .conf into a form schema, and a submitted form back into a .conf.

The form is generated from the config itself: whatever keys a config carries get
rendered, so a config for a different generator brings its own fields along.
Field names are flat, dash-joined paths ("brushograph-moves-normal-acc") so a
posted form can be folded straight back into the nested JSON it came from.
"""
from __future__ import annotations

import json
import re
from collections import OrderedDict

CMYK_TO_TRAY = {"C": "cyan", "M": "magenta", "Y": "yellow", "K": "kroma"}

# What each channel is called in the form. "kroma" is what the tray is keyed as
# throughout this project, and it is not a word anyone reading the machine
# expects: the holder has W C M Y K stamped on it, so the form says Black (K)
# and leaves "kroma" showing as the config key it is.
CMYK_LABEL = {"C": "Cyan", "M": "Magenta", "Y": "Yellow", "K": "Black"}

# The order a multi-colour painting is laid down in, lightest first: yellow,
# magenta, cyan, black. A light colour painted over a dark one barely shows, and
# the key plate goes on last to sharpen everything under it. Colours that are
# not process colours keep the order the config gives them, between cyan and
# black.
PAINT_ORDER = {"Y": 0, "M": 1, "C": 2, "K": 4}
_OTHER_COLOURS = 3


def paint_order(colors: list) -> list:
    """color_order put into painting order, Y M C, anything else, then K."""
    return sorted(colors, key=lambda c: PAINT_ORDER.get(c, _OTHER_COLOURS))

# The Mini's CMYK holder: the `CMYK_standard` preset of openBrushograph_hardware's
# Extras/colourContainers.scad (once mini_petri.scad), which is the design,
# checked against the parts in Extras/CMYK_ColourContainers,
# CMYK_standard_holder.stl and CMYK_standard_containers_steps.stl. Five
# crucibles in a row: a 38 mm water one and four of 28, with 4 mm between them,
# so the colours sit on 32 mm centres and the first 37 mm from the water —
# slicing the holder finds its slots centred at 2.0, 39, 71, 103 and 135, which
# is those figures exactly. The numbers here are centre-to-centre offsets from
# the water crucible, so a layout only needs to know where the water sits.
#
# These are the second set of figures this holder has had. Until September 2026
# the preset was `Standard_CMYK`: a 30 mm water crucible and four of 18.6 on
# 23.6 mm centres, 29.3 mm from the water to the first colour and 100.1 to
# black, in a 144.4 x 39.2 mm plate. It was redrawn wholesale — bigger pans, a
# bowl-like 4 mm fillet inside them instead of 1.4, and 4 mm between them
# rather than 5 — and the files renamed with it, so nothing of the old holder
# is left upstream to check against. (An earlier, bigger one still,
# CMYK_holder_big.stl, had 39.2 and 29.2 mm bays on 34 mm centres. It was never
# the design, and it is gone too.) A machine carrying a holder printed before
# the change wants `custom` cups, which is what both kept configs already use.
MODERN_BAY_OFFSETS = OrderedDict(
    [("water", 0.0), ("cyan", 37.0), ("magenta", 69.0), ("yellow", 101.0), ("kroma", 133.0)]
)

# The crucibles themselves, inside their 1.2 mm walls: 35.6 mm for water and
# 25.6 for a colour, 32.6 long. These are fixed by the print, not tuned per
# machine, so they are constants rather than settings: the water crucible is
# the wide one so the brush has room to be rinsed. The swipe keeps the same
# share of the crucible it has always kept, 85% of the inside length, which is
# what the Mikro's 17.5 mm is of its 20.6.
MODERN_BAY_WIDTH = 25.6
MODERN_WATER_BAY_WIDTH = 35.6
MODERN_SWIPE_LENGTH = 27.7

# The classic cups: the low petri dishes in openBrushograph_hardware's
# Extras_openBrushograph.scad, sitting in the 4xPetri_rounded_new.stl holder.
# Slicing that STL at mid-plate finds four round holes of 20.14 mm radius
# (20.2 in the SCAD, less the facets) at 45, 44 and 44 mm centres, WASH first,
# then C 1, C 2, C 3 — four cups, so a classic machine paints CMY and has no
# black. Offsets from the water dish, like MODERN_BAY_OFFSETS.
CLASSIC_DISH_OFFSETS = OrderedDict(
    [("water", 0.0), ("cyan", 45.0), ("magenta", 89.0), ("yellow", 133.0)]
)

# What the dish itself fixes. From the SCAD: the wall is a cylinder of r 17
# grown by a 2 mm sphere inside and r 18 grown by 2.1 outside, cut off 11.2 mm
# above its base — so 19 mm inside radius, 20.1 outside, a 1.1 mm floor and
# 10.1 mm of depth. The Z figures take Z 0 as the surface the dishes stand on,
# the same one the paper lies on at canvas_height 0. copicograf reads all but
# dip_depth as whole millimetres.
CLASSIC_DISH_RADIUS = 19.0
CLASSIC_DISH_RIM_RADIUS = 20.1
CLASSIC_DISH_SETTINGS = OrderedDict([
    ("dip_depth", 1.0),             # onto the 1.1 mm floor, bristles flexing
    ("tray_enter_radius", 15),      # the sweep stays 4 mm off the 19 mm wall
    ("remove_drops_radius", 21),    # dragged clear past the 20.1 mm rim
    ("remove_drops_lift", 9),       # tip 2 mm below the rim, so it catches
    ("go_in_tray_lift", 14),        # clears the 11.2 mm rim
])

# The two machines openBrushograph_hardware V6.0 builds, from the `params`
# spreadsheet in brushograf_V6.FCStd and the parts its release zips put beside
# each gantry. Mini is the one every config so far was written for, so a config
# that names no model is a Mini.
#
# Mini: 14 mm pinion with 11 teeth (module 1.27) on 183 mm racks — 46 teeth,
# 183.9 mm — with the 18 mm Z-mechanism and the big CMYK holder above. Its
# travel figures are the ones the kept configs were tuned to on the machine.
#
# Micro: 11 mm pinion with 8 teeth (module 1.375). The racks are counted off
# the STLs in the release's Mikro_STLs.zip rather than read from the
# spreadsheet, whose Micro column still says 120 mm for X: the X rack printed
# has 23 teeth, 99.3 mm, and the Y rack 34, 146.9 mm — against 46 and 46,
# 183.9 mm, on the Mini. The carriages take the same share of a rack on both,
# so the Micro loses 84.6 mm of X and 37.0 of Y: about 66 mm across. On the
# machine the area that can be painted is 65 × 100, with the colours along the
# bottom, so that is what the limits say. The Z-mechanism's "mikro" preset has
# 12 mm of travel against 18.
#
# Its holder is the `mikro_container` preset of Extras/colourContainers.scad,
# sliced off Extras/CMYK_ColourContainers/mikro_CMYK_holder.stl and
# mikro_containers_steps.stl to check: a 22 mm water crucible and four 13 mm
# colour ones on 16 mm centres, the first colour 20.5 mm from the water, walls
# and floor 1.2 so 19.6 and 10.6 mm inside, and 23 mm long, 20.6 inside. The
# crucibles carry the same stairs as the Mini's, so a Micro swipes rather than
# dips; the swipe keeps the Mini's proportion of its crucible (23.5 of 27.6).
# Its water and black crucibles are 68.5 mm apart, all but the whole of the X
# travel, so the water starts at X 2 rather than the Mini's 12: from 12,
# auto-spacing put black at 80.5, out of reach. There is no petri dish holder
# for it — the classic dishes span 173 mm, more than twice its X travel.
#
# What a CMYK holder fixes besides where its crucibles are, from the same SCAD
# presets — Z 0 being the surface the crucibles stand on, as for the dishes.
# The tray lift clears the rim by 2 mm. The dip goes just under the floor, the
# bristles flexing, as the classic dish's does. The swipe ends over the stairs
# (the back 40% of the crucible, five steps rising to the rim): its far end,
# 35% of the swipe past the centre, is over the third step on both holders, so
# that step's top is where the swipe finishes.
def _crucible_settings(rim, floor, length, swipe):
    stairs = length * 0.4
    start = length / 2 - stairs           # where they begin, from the centre
    far = swipe * 0.35
    step = int((far - start) // (stairs / 5)) + 1 if far > start else 0
    return OrderedDict([
        ("go_in_tray_lift", int(rim + 2)),
        ("dip_depth", round(floor - 0.2, 1)),
        ("cup_swipe_exit_z", round(floor + step * (rim - floor) / 5, 1)),
    ])


MODELS = OrderedDict([
    ("mini", {
        "label": "Mini",
        "holder": {
            "offsets": MODERN_BAY_OFFSETS,
            "bay_width": MODERN_BAY_WIDTH,
            "water_bay_width": MODERN_WATER_BAY_WIDTH,
            "swipe_length": MODERN_SWIPE_LENGTH,
            # The crucibles as seen from above, outside their walls: water,
            # colour, length. The plan draws these.
            "outside": (38.0, 28.0, 35.0),
            # The plate the crucibles stand in: width and depth, then where the
            # water crucible's centre is from its left and front edges. Its
            # slots open 11 mm back from the front, 35.0 mm deep.
            "plate": (182.0, 46.2, 27.0, 28.7),
            # 10 mm crucibles with a 1.2 mm floor, 35 mm long.
            "settings": _crucible_settings(10, 1.2, 35, MODERN_SWIPE_LENGTH),
        },
        "classic": True,
        # What choosing the model puts in the form.
        "settings": OrderedDict([
            ("max_width", 151), ("max_height", 156), ("offset_x", 0),
            ("canvas_start_y", 25),
        ]),
        # Where choosing the model puts the water container; the others are
        # auto-spaced from it.
        "water": (12, 6),
        # zero.g's sweep to the far corner and back: X, Y, Z. It drives into
        # the endstops on purpose, which is what makes it a zeroing routine and
        # what makes it useless as a limit: the machine cannot work out there.
        # Nothing but zero.g may use these figures as somewhere to move to.
        "zero_sweep": (160, 160, 32),
    }),
    ("micro", {
        "label": "𝔐𝔦𝔨𝔯𝔬",
        "holder": {
            "offsets": OrderedDict([("water", 0.0), ("cyan", 20.5), ("magenta", 36.5),
                                    ("yellow", 52.5), ("kroma", 68.5)]),
            "bay_width": 10.6,
            "water_bay_width": 19.6,
            "swipe_length": 17.5,
            "outside": (22.0, 13.0, 23.0),
            # Slots open 7 mm back from the front.
            "plate": (96.0, 30.2, 16.0, 18.7),
            # 8 mm crucibles with a 1.2 mm floor, 23 mm long.
            "settings": _crucible_settings(8, 1.2, 23, 17.5),
        },
        "classic": False,
        # 65 × 100 as found on the machine, above a canvas that starts 19 mm
        # out — the 23 mm crucibles on the same Y 6 leave that much.
        "settings": OrderedDict([
            ("max_width", 65), ("max_height", 100), ("offset_x", 0),
            ("canvas_start_y", 19),
        ]),
        "water": (2, 6),
        # The Mini's sweep, shortened by the racks and scaled to the Z travel,
        # and driven into the endstops the same way.
        "zero_sweep": (75, 123, 21),
    }),
])


# What a machine that has never been configured starts with, beyond the model's
# own figures and the settings the form always offers. Most of it is simply
# what both machines in webui_configs already agree on; the rest is the gentler
# of the two, because a bed nobody has measured yet is better off slow.
NEW_MACHINE_BASE = OrderedDict([
    ("canvas_height", 0),
    ("paint_per_run_min", 130),
    ("paint_per_run_max", 150),
    ("move_to_other_shape_lift", 2),
    ("prepare_paint_count", 2),
    ("moves", OrderedDict([
        ("normal", OrderedDict([("acc", "M204 P20 T10"), ("feedrate_1", "G0 F1000"),
                                ("feedrate_2", "M203 X1000 Y1000 Z1000")])),
        ("fast", OrderedDict([("acc", "M204 P20 T20"), ("feedrate_1", "G0 F1500"),
                              ("feedrate_2", "M203 X1300 Y1300 Z1000")])),
        ("remove_drops", OrderedDict([("acc", "M204 P20 T20"), ("feedrate_1", "G0 F600"),
                                      ("feedrate_2", "M203 X600 Y600 Z500")])),
    ])),
])


def new_config(model: str) -> dict:
    """A fresh config for `model`, carrying that model's defaults and nothing else.

    What choosing the model in the form already does — travel limits, canvas
    offset, the containers spaced along from where the holder has room for them
    — written out as a whole config rather than applied to somebody else's. The
    container heights come from the shape the model can actually hold: the
    petri dish's if it takes one, the printed crucibles' if it does not.

    Every section the form builds controls from is present, because the form is
    built from the config's own keys: a config that omits a section simply has
    no control for it, and a new machine would have no way to gain one.
    """
    name = model if model in MODELS else "mini"
    m = MODELS[name]
    classic = m["classic"]
    offsets = CLASSIC_DISH_OFFSETS if classic else m["holder"]["offsets"]
    water_x, water_y = m["water"]

    bg = OrderedDict([("model", name)])
    bg.update(m["settings"])
    # The whole paintable bed: the limits less the strip the containers stand
    # in. Fitted the way the form fits it, so a new machine cannot open asking
    # to paint off the end of its own bed.
    bg["width"] = max(1, int(m["settings"]["max_width"] - m["settings"]["offset_x"]))
    bg["height"] = max(1, int(m["settings"]["max_height"] - m["settings"]["canvas_start_y"]))
    bg.update(NEW_MACHINE_BASE)
    bg["cup_shape"] = "classic" if classic else "modern"
    bg.update(CLASSIC_DISH_SETTINGS if classic else m["holder"]["settings"])

    conf = OrderedDict([
        ("trays", OrderedDict(
            [(tray, {"x": round(water_x + off, 1), "y": water_y}) for tray, off in offsets.items()]
            + [("additionals", OrderedDict())])),
        ("additionals", []),
        ("separation", OrderedDict([
            ("selection", OrderedDict([("C", 0), ("M", 0), ("Y", 0), ("K", 0),
                                       ("additionals", OrderedDict())])),
            ("levels", 12),
        ])),
        ("color_order", ["C", "M", "Y", "K"]),
        ("brushograph", bg),
        ("slicer", OrderedDict([("infill_pattern", "concentric"), ("infill_line_distance", "0"),
                                ("infill_angles", "[0]"), ("wall_line_count", "1")])),
        ("controller", OrderedDict([("controller_type", "FluidNC")])),
        ("connection", OrderedDict([("hostname", "fluidnc.local")])),
    ])
    return fit_cups_to_shape(with_defaults(conf))


def model_of(conf: dict) -> str:
    bg = conf.get("brushograph", {})
    name = str(bg.get("model", "mini")).strip().lower() if isinstance(bg, dict) else "mini"
    return name if name in MODELS else "mini"


# The custom container setup: rectangular cups swiped like the CMYK holder's,
# sized and spaced by the config rather than by a printed part, for a holder
# nobody has a preset for. The defaults are Pinkograph's big holder,
# CMYK_holder_big.stl: 39.2 mm water and 29.2 mm colour bays on 34 mm centres,
# swiped 30 mm of their 35.1 mm depth.
CUSTOM_CUP_DEFAULTS = OrderedDict([
    ("cup_width_water", 39.2),
    ("cup_width", 29.2),
    ("cup_depth", 30.0),
    ("cup_spacing", 34.0),
])

RECTANGULAR_SHAPES = ("modern", "custom")


def cup_shape_of(conf: dict) -> str:
    bg = conf.get("brushograph", {})
    return str(bg.get("cup_shape", "classic")).strip().lower() if isinstance(bg, dict) \
        else "classic"


def custom_offsets(water_width: float, width: float, spacing: float) -> OrderedDict:
    """Centre offsets from the water cup for custom cups.

    Spacing is centre to centre between colour cups, so the wall between two
    of them is spacing less a cup's width; the water cup is parted from cyan by
    the same wall. On Pinkograph's figures that is 39 mm to cyan, then 34 —
    its holder exactly.
    """
    first = water_width / 2 + width / 2 + (spacing - width)
    return OrderedDict([("water", 0.0)] + [
        (name, round(first + i * spacing, 2))
        for i, name in enumerate(("cyan", "magenta", "yellow", "kroma"))])


def holder_of(conf: dict) -> dict:
    """The rectangular holder this config paints from.

    The model's CMYK holder, or with custom containers one made of the config's
    own cup sizes and spacing — which has no plate to draw and no heights
    anyone designed, so it sets none.
    """
    if cup_shape_of(conf) != "custom":
        return MODELS[model_of(conf)]["holder"]
    bg = conf.get("brushograph", {})

    def size(key):
        try:
            return float(bg.get(key, CUSTOM_CUP_DEFAULTS[key]))
        except (TypeError, ValueError):
            return CUSTOM_CUP_DEFAULTS[key]
    water, width, depth = size("cup_width_water"), size("cup_width"), size("cup_depth")
    return {
        "offsets": custom_offsets(water, width, size("cup_spacing")),
        "bay_width": width,
        "water_bay_width": water,
        "swipe_length": depth,
        "outside": (water, width, depth),
        "plate": None,
        "settings": OrderedDict(),
    }


# Settings the form always offers, whatever the config happens to carry. The
# form is otherwise built from the config's own keys, so a machine file written
# before one of these existed — or by hand, or by an older version — simply has
# no control for it and no way to gain one.
#
# Defaults are chosen to be safe on a machine that never named them: a dip no
# deeper than the old fixed one, and a backlash figure small enough to be worth
# tuning rather than large enough to matter if ignored.
ALWAYS_OFFERED = {
    ("brushograph", "model"): "mini",
    ("brushograph", "dip_depth"): -4.0,
    # The cups. "classic" is the round petri dish the machine was built around;
    # "modern" is the rectangular CMYK holder, whose floor steps up towards the
    # back so the brush can be drawn out of the paint rather than lifted from
    # it, sized by the model's print; "custom" is rectangular cups of the sizes
    # and spacing below, for any other holder.
    ("brushograph", "cup_shape"): "classic",
    ("brushograph", "cup_swipe_exit_z"): 1.0,
    # Five places across a rectangular bay for the dips to work their way
    # over, a different one each pickup, so the paint is mixed by where the
    # brush goes down rather than by stirring it once it is there. 1 puts
    # every dip down the middle, which is what a bay did before any of this.
    ("brushograph", "cup_dip_lanes"): 5,
    **{("brushograph", key): value for key, value in CUSTOM_CUP_DEFAULTS.items()},
    ("brushograph", "backlash_compensation"): True,
    ("brushograph", "backlash_x"): 0.5,
    ("brushograph", "backlash_y"): 0.5,
    # The same two read at the far end of X. Offered as a constant here and
    # then mirrored onto the near figures by with_defaults, because a config
    # that never named them is a config whose play was measured once: filling
    # in 0.5 beside a stated 2.3 would invent a slope nobody read off a sheet.
    # Bed levelling. Off until somebody measures: with all five readings at
    # zero it is a no-op anyway, but a machine that has not been measured
    # should say so rather than quietly compensating by nothing.
    ("brushograph", "level_compensation"): False,
    ("brushograph", "level_tl"): 0.0,
    ("brushograph", "level_tr"): 0.0,
    ("brushograph", "level_c"): 0.0,
    ("brushograph", "level_bl"): 0.0,
    ("brushograph", "level_br"): 0.0,
    ("connection", "hostname"): "fluidnc.local",
}


# Settings that used to drive something and no longer do. The form is built
# from the config's own keys, so a key a machine file was written with outlives
# the behaviour it named: a box in the Containers group, read by nobody, sitting
# beside the one that replaced it and quietly implying it still does something.
# These are taken out when the config is read, which takes the control with
# them — and, because the config that is saved is the config that was read,
# takes the key out of the file the next time it is kept.
RETIRED = {
    # Stirs across the bay at dip depth before the swipe up the stairs.
    # cup_dip_lanes replaced it: the paint is mixed by moving the whole pickup
    # across the cup now, not by dragging the brush sideways through it.
    ("brushograph", "cup_mix_sweeps"),
}


def _forget(conf: dict, path: tuple) -> None:
    """Drop conf[a][b][...] if every step of the way is there."""
    node = conf
    for key in path[:-1]:
        node = node.get(key)
        if not isinstance(node, dict):
            return
    node.pop(path[-1], None)


def _dig(conf: dict, path: tuple) -> dict:
    node = conf
    for key in path[:-1]:
        if not isinstance(node.get(key), dict):
            node[key] = {}
        node = node[key]
    return node


def with_defaults(conf: dict) -> dict:
    """A copy of the config with the always-offered settings filled in.

    Filled in, not overridden: a config that states a value keeps it, including
    a `false`. These defaults exist so a setting the config never mentions still
    has a control, not to overrule one it does.

    The RETIRED keys go the other way, and go first: a setting nothing reads
    any more loses its control here, whatever the config says about it.
    """
    out = json.loads(json.dumps(conf))
    for path in RETIRED:
        _forget(out, path)
    for path, value in ALWAYS_OFFERED.items():
        _dig(out, path).setdefault(path[-1], value)
    _offer_far_backlash(out)
    _offer_canvas_start(out)
    _offer_plain_feeds(out)
    _offer_black(out)
    # Written back in painting order too, so a saved config says what happens.
    if isinstance(out.get("color_order"), list):
        out["color_order"] = paint_order(out["color_order"])
    return out


def _offer_far_backlash(conf: dict) -> None:
    """Give a config the far-end play figures, equal to the ones it has.

    The play is a straight line across X between two readings, and a config
    written when it was one number has only the near one. It gets the control
    the way it gets every other always-offered setting — and it gets it set to
    what it already says, so the line is flat and the machine does exactly what
    it did before. A machine whose sheet says otherwise is two boxes away from
    saying so.
    """
    bg = conf.get("brushograph")
    if not isinstance(bg, dict):
        return
    for axis in ("x", "y"):
        bg.setdefault(f"backlash_{axis}_far", bg.get(f"backlash_{axis}", 0.5))


# A feedrate setting that is nothing but a rapid and an F word, and an
# acceleration setting that is nothing but an M204 and its two figures.
# Anything else a config puts in those boxes -- a compound line, a G1, a
# comment -- is somebody meaning it, and is left exactly as it is.
_PLAIN_FEED = re.compile(r"^G0?0\s+F(\d+(?:\.\d+)?)$", re.IGNORECASE)
_PLAIN_ACCEL = re.compile(
    r"^M204\s+P(\d+(?:\.\d+)?)\s+T(\d+(?:\.\d+)?)$", re.IGNORECASE)

# The speed group settings that hold a figure rather than a line of G-code.
# feedrate_2 is the third, and it is an M203 with a word per axis: three
# figures, no single number to reduce it to, and Marlin-only besides.
FEED_KEYS = ("feedrate_1",)
ACCEL_KEYS = ("acc",)
PLAIN_KEYS = FEED_KEYS + ACCEL_KEYS


def feed_rate(value) -> float | None:
    """The millimetres a minute in a feedrate setting, however it is written."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    found = _PLAIN_FEED.match(str(value).strip())
    return float(found.group(1)) if found else None


def accel_rate(value) -> float | None:
    """The millimetres a second squared in an acceleration setting.

    An M204 carries two: P for a move that extrudes and T for one that does
    not. These machines have no extruder, so only one of the two can ever
    apply, and where a config's pair differ it is because somebody set one of
    them and left the other. The larger is taken, which is the figure a real
    run matches: a job estimated at 1.5 hours on Pinkograph, whose groups read
    P20 T10 and P20 T20, took about five, and 20 is what predicts that.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    found = _PLAIN_ACCEL.match(str(value).strip())
    return max(float(found.group(1)), float(found.group(2))) if found else None


def accel_line(value, fallback: str = "M204 P500 T500") -> str:
    """An acceleration setting as the line that goes in the file."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"M204 P{value:g} T{value:g}"
    text = str(value or "").strip()
    return text or fallback


def feed_line(value, fallback: str = "G0 F1000") -> str:
    """A feedrate setting as the line that goes in the file.

    The box holds millimetres a minute now, so the G-code is written around it
    here. A config that carries the old `G0 F1200`, or anything else the
    generator should emit verbatim, is passed through untouched.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"G0 F{value:g}"
    text = str(value or "").strip()
    return text or fallback


def _offer_plain_feeds(conf: dict) -> None:
    """Read `G0 F1200` in a speed group as the 1200 it is.

    The three speed groups came out of the generator's own G-code, so what the
    form offered was a text box with `G0 F1200` in it: the figure that matters
    wrapped in the syntax that carries it. On a FluidNC or GRBL machine the
    other two settings in the group are Marlin commands and are hidden, so the
    whole of a speed group was one text box asking for a line of G-code when
    what it wanted was a number.

    A value that is a rapid and an F word and nothing else is stored as that
    number, and the generator writes the `G0 F` back around it. Anything else
    is left alone: a config with a compound line in that box means it, and is
    emitted verbatim the way it always was.
    """
    moves = conf.get("brushograph", {}).get("moves")
    if not isinstance(moves, dict):
        return
    for group in moves.values():
        if not isinstance(group, dict):
            continue
        for key, read in ((k, feed_rate) for k in FEED_KEYS):
            _plainly(group, key, read)
        for key, read in ((k, accel_rate) for k in ACCEL_KEYS):
            _plainly(group, key, read)


def _plainly(group: dict, key: str, read) -> None:
    """Store what `read` makes of a setting, if it can make anything of it."""
    value = group.get(key, "")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return
    pattern = _PLAIN_FEED if read is feed_rate else _PLAIN_ACCEL
    if not pattern.match(str(value).strip()):
        return
    rate = read(value)
    if rate is not None:
        group[key] = int(rate) if float(rate).is_integer() else rate


def _offer_canvas_start(conf: dict) -> None:
    """Split a config's one canvas offset into where the bed starts and where the painting does.

    `offset_y` used to be both: the strip the containers stand in, which is a
    fact about the machine, and however far up the bed this painting was
    wanted, which is a decision about this painting. One figure for two things
    means neither can be changed without minding the other — moving a painting
    5 mm up the paper reads as claiming the containers take 5 mm more room.

    `canvas_start_y` is the machine's share and `offset_y` what is left, and
    the brush is sent to the two added together. A config written before the
    split has all of it in `offset_y`: it is moved across here and the offset
    zeroed, so the machine paints exactly where it painted before and the two
    boxes now say which part of that figure was which.
    """
    bg = conf.get("brushograph")
    if not isinstance(bg, dict):
        return
    if "canvas_start_y" not in bg:
        bg["canvas_start_y"] = bg.get("offset_y", 0)
        bg["offset_y"] = 0
    # A config that names the start but not the offset -- a fresh one, since
    # the model's settings carry the start alone -- paints at the start.
    bg.setdefault("offset_y", 0)


# How much of the travel a painting keeps clear of, at the far end of each
# axis, in millimetres.
#
# Max Width and Max Height are where the machine stops, and where a machine
# stops is a stop: an endstop triggers a little before the mechanical end of
# the travel, and a figure somebody measured with a rule is right to about a
# millimetre. Painting to the limit is therefore painting into the switch.
#
# It was not theoretical. A photograph painted at full size on Brushparang put
# 142 strokes at exactly Y 140 against a Max Height of exactly 140, and the
# machine hit the upper Y endstop -- the same lesson X learned from zero_sweep,
# which drives into the stops on purpose and is no use as a working limit. Two
# millimetres is a little more than the millimetre a rule leaves in doubt, and
# on a 140 mm axis it is 1.4% of the picture.
EDGE_HEADROOM = 2.0


# How far inside the corners of the bed the levelling points sit, in
# millimetres, and at most this fraction of a side -- a small bed still wants
# five points that are properly apart.
LEVEL_INSET = 5.0
LEVEL_INSET_MAX = 0.4


def level_area(conf: dict) -> tuple[float, float, float, float]:
    """The bed the levelling covers, as (lo_x, lo_y, hi_x, hi_y) in mm.

    Everything the machine can reach that is paper: from the origin out to the
    travel limits in X, and from Canvas Start Y -- where the strip the
    containers stand in ends -- to the limit in Y. Not the painting. Levelling
    is a fact about how the sheet lies on the bed, and the sheet does not move
    when the picture is made smaller or offset into a corner.

    It used to be the canvas, which made every reading mean something
    different from one job to the next: five figures measured for a full-bed
    painting, reused for a 50 mm one in the middle, were being read as that
    small square's own corners -- a tilt of a tenth over 150 mm applied as a
    tenth over 50. The readings are typed once, after taping the paper down,
    and they have to keep meaning the same spots.
    """
    bg = conf.get("brushograph", {}) if isinstance(conf.get("brushograph"), dict) else {}

    def num(key):
        try:
            return float(bg.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    return 0.0, num("canvas_start_y"), num("max_width"), num("max_height")


def level_points(conf: dict) -> dict[str, tuple[float, float]]:
    """Where the five bed-levelling readings are taken, in machine coordinates.

    The four corners of the bed's paper area and its middle, held LEVEL_INSET
    inside the corners so the brush is on the bed rather than over its edge --
    and clear of the endstops, which is why the inset is larger than
    EDGE_HEADROOM. Studio takes its five off the machine's own travel, and this
    is the same frame less the containers' strip.
    """
    lo_x, lo_y, hi_x, hi_y = level_area(conf)
    in_x = min(LEVEL_INSET, max(0.0, hi_x - lo_x) * LEVEL_INSET_MAX)
    in_y = min(LEVEL_INSET, max(0.0, hi_y - lo_y) * LEVEL_INSET_MAX)
    lo_x, hi_x = lo_x + in_x, hi_x - in_x
    lo_y, hi_y = lo_y + in_y, hi_y - in_y
    return {
        "level_bl": (lo_x, lo_y), "level_br": (hi_x, lo_y),
        "level_tl": (lo_x, hi_y), "level_tr": (hi_x, hi_y),
        "level_c": ((lo_x + hi_x) / 2, (lo_y + hi_y) / 2),
    }


def level_offset(conf: dict, x: float, y: float) -> float:
    """How much higher the paper is at (x, y) than where Z0 was set.

    Studio's scheme, and the shape of it is the point: five readings, and the
    rectangle between them split into four triangles about the middle one. A
    point is found in whichever triangle holds it and its height read off that
    triangle's plane, by barycentric weights.
    
    Four triangles rather than one plane because paper is not flat and a bed is
    not either. Three points fit a plane and can say nothing about a twist; a
    corner that sits high, which is what a sheet taped at its edges does, is
    exactly what three points average away and what the fifth reading in the
    middle catches.

    A point outside the rectangle is clamped into it, so the inset at the
    bed's edges and the strip the containers stand in read as the nearest edge
    rather than as an extrapolation off the end of the paper. The painting is
    always inside it, wherever it is offset to.
    """
    bg = conf.get("brushograph", {}) if isinstance(conf.get("brushograph"), dict) else {}
    points = level_points(conf)

    def z(key):
        try:
            return float(bg.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    corners = {k: (points[k][0], points[k][1], z(k)) for k in points}
    lo_x, hi_x = corners["level_bl"][0], corners["level_br"][0]
    lo_y, hi_y = corners["level_bl"][1], corners["level_tl"][1]
    px = min(max(x, lo_x), hi_x)
    py = min(max(y, lo_y), hi_y)

    def on_triangle(a, b, c):
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-9:
            return None
        w1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / det
        w2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / det
        w3 = 1.0 - w1 - w2
        if min(w1, w2, w3) < -0.01:
            return None
        return w1 * a[2] + w2 * b[2] + w3 * c[2]

    mid = corners["level_c"]
    for a, b in (("level_tl", "level_tr"), ("level_tr", "level_br"),
                 ("level_br", "level_bl"), ("level_bl", "level_tl")):
        found = on_triangle(corners[a], corners[b], mid)
        if found is not None:
            return found
    return mid[2]


def paintable_size(conf: dict) -> tuple[float, float]:
    """The widest and tallest a painting can be on this machine.

    The travel limits, less where the canvas starts, less the headroom that
    keeps the last stroke off the endstop. Both ends read this: the form caps
    the two size boxes with it, and the pipeline holds a config that asks for
    more down to it and says so, the way a clipped dip is said.
    """
    bg = conf.get("brushograph", {}) if isinstance(conf.get("brushograph"), dict) else {}

    def num(key, default=0.0):
        try:
            return float(bg.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    origin_x, origin_y = canvas_origin(conf)
    return (max(1.0, num("max_width") - origin_x - EDGE_HEADROOM),
            max(1.0, num("max_height") - origin_y - EDGE_HEADROOM))


def canvas_origin(conf: dict) -> tuple[float, float]:
    """Where the picture's own (0,0) corner lands on the bed.

    X is the offset alone; Y is the machine's canvas start plus this
    painting's offset from it. Everything that draws or paints the canvas
    reads it here, so the two figures are added in one place.
    """
    bg = conf.get("brushograph", {}) if isinstance(conf.get("brushograph"), dict) else {}

    def num(key):
        try:
            return float(bg.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    return num("offset_x"), num("canvas_start_y") + num("offset_y")


def is_classic(conf: dict) -> bool:
    return isinstance(conf.get("brushograph", {}), dict) and \
        cup_shape_of(conf) not in RECTANGULAR_SHAPES


def fit_cups_to_shape(conf: dict) -> dict:
    """Take the black cup away again if the cups are classic.

    The petri dish holder has four holes — water and three colours — so a
    classic machine paints CMY. with_defaults offers black whatever the shape,
    because the form is built once and the shape can change under it; this is
    the step after the form is read, so the config that is drawn, painted and
    saved has no black cup unless the modern holder is the one selected.

    A model with no petri dish holder is given its CMYK one instead, whatever
    the config says: the form does not offer Classic for it.
    """
    bg = conf.get("brushograph")
    if isinstance(bg, dict) and not MODELS[model_of(conf)]["classic"] and is_classic(conf):
        bg["cup_shape"] = "modern"
    if not is_classic(conf):
        return conf
    black = CMYK_TO_TRAY["K"]
    trays = conf.get("trays")
    if isinstance(trays, dict):
        trays.pop(black, None)
    order = conf.get("color_order")
    if isinstance(order, list):
        conf["color_order"] = [c for c in order if c != "K"]
    return conf


def _offer_black(conf: dict) -> None:
    """Give a config a black cup if it has not got one.

    The holder has a bay for black, so the machine paints CMYK. A config
    written before that bay existed names three colours, and the form is built
    from the config: with no `kroma` tray and no `K` in `color_order` there is
    no black card to upload to and no way to gain one, which is the same reason
    ALWAYS_OFFERED exists for settings.

    Where the cup is, is a measurement. The guess is one more step along the row
    the other cups are already in — the gap between the last two of them, or the
    Mini holder's own 32 mm if there are not two to learn from — which lands it about
    where a fifth cup goes and leaves a wrong number visible in the form and
    flagged in the plan view rather than a missing one that is not.

    Nothing is painted from it until a picture is uploaded for it: a tray in
    `color_order` with no image is skipped, so an unused black cup costs a row
    in the setup and nothing else.
    """
    trays = conf.setdefault("trays", {})
    order = conf.setdefault("color_order", [])
    if not isinstance(trays, dict) or not isinstance(order, list):
        return
    black = CMYK_TO_TRAY["K"]
    if black not in trays:
        cups = [(k, v) for k, v in trays.items()
                if k not in TRAY_SKIP and isinstance(v, dict) and "x" in v]
        if not cups:
            return                      # nothing to place it relative to
        xs = [float(v["x"]) for _, v in cups]
        step = xs[-1] - xs[-2] if len(xs) > 1 else MODERN_BAY_OFFSETS["magenta"] - \
            MODERN_BAY_OFFSETS["cyan"]
        last = cups[-1][1]
        trays[black] = {"x": xs[-1] + step, "y": last.get("y", 0)}
    if "K" not in order:
        order.append("K")               # the key plate goes on last


# The machine section is a flat list of nineteen settings in whatever order the
# config file happens to list them, which put Width beside Offset Y beside Paint
# Per Run Min. They are grouped here by what they are actually for. The first
# group is marked `job` because it is the only one that changes from one run to
# the next, and the form shows it with the artwork rather than the machine.
BRUSHOGRAPH_GROUPS = [
    ("Model", ["model"], False),
    # Where the painting goes and how big it is: the one group that changes
    # from one run to the next, so it sits with the picture rather than in the
    # machine setup. The offsets moved in with it — they say where on the bed
    # this painting lands, which is a decision about this painting.
    ("Painting dimensions",
     ["width", "height", "offset_x", "offset_y", "canvas_height"], True),
    ("Canvas", ["canvas_start_y", "max_width", "max_height"], False),
    ("Brush control",
     ["go_in_tray_lift", "dip_depth", "remove_drops_lift", "move_to_other_shape_lift"], False),
    ("Containers",
     ["cup_shape", "cup_swipe_exit_z", "cup_dip_lanes", "cup_width_water",
      "cup_width", "cup_depth", "cup_spacing"], False),
    ("Paint management",
     ["paint_per_run_min", "paint_per_run_max", "prepare_paint_count",
      "tray_enter_radius", "remove_drops_radius"], False),
    ("Bed levelling",
     ["level_compensation", "level_tl", "level_tr", "level_c",
      "level_bl", "level_br"], False),
    ("Backlash",
     ["backlash_compensation", "backlash_x", "backlash_x_far", "backlash_y",
      "backlash_y_far"], False),
]

SECTIONS = [
    ("trays", "Trays and Images"),
    ("connection", "Connection"),
    ("brushograph", "Brushograph Options"),
    ("slicer", "Fill Options"),
    ("controller", "Controller Options"),
]

# How an enum's values are spelled in the picker. Anything missing shows as it is
# stored, which suits the slicer patterns and controller names: those are spelled
# the way the slicer and the firmware spell them.
ENUM_LABELS = {
    **{name: m["label"] for name, m in MODELS.items()},
    "classic": "Classic",
    "modern": "CMYK",
    "custom": "Custom",
}

ENUMS = {
    # Ordered by how well
    # they suit a brush: long flowing strokes first, raster last.
    "slicer-infill_pattern": [
        "concentric", "archimedeanchords", "alignedrectilinear", "rectilinear", "hilbertcurve", "scanline",
    ],
    "controller-controller_type": ["GRBL", "Marlin", "FluidNC"],
    "brushograph-cup_shape": ["classic", "modern", "custom"],
    "brushograph-model": list(MODELS),
}

# Keys that describe the machine rather than a run, kept out of the generated
# form because the Trays section renders them itself.
TRAY_SKIP = {"additionals"}

HELP = {
    "brushograph-model": "Which openBrushograph this is. Mini is the standard machine; 𝔐𝔦𝔨𝔯𝔬 is the small "
                         "one, with shorter racks, 12 mm of Z and its own five-crucible CMYK holder. "
                         "Choosing one sets the travel limits, the canvas offset, the tray lift and the "
                         "container spacing to suit it.",
    "connection-hostname": "Where the machine answers on the network — the name or address of its "
                           "FluidNC controller, without http://. Used by Send to machine and "
                           "Upload & start.",
    "brushograph-width": "Width of a file (mm); you may upload larger files, but they need to be in the same aspect ratio",
    "brushograph-height": "Height of a file (mm); you may upload larger files, but they need to be in the same aspect ratio",
    "brushograph-offset_x": "How far right of X0 this painting starts (mm). The picture's own (0,0) corner lands here.",
    "brushograph-offset_y": "How far past Canvas Start Y this painting starts (mm). 0 puts it at the start of the paintable area, right where the containers end; raise it to paint further up the bed. What the machine is asked for is the two added together.",
    "brushograph-canvas_start_y": "Where the paintable area begins in Y (mm): the far edge of the strip the containers stand in, and a fact about the machine rather than about this painting. Nothing is painted below it, and the painted height is measured from it — with Offset Y at 0 the canvas starts exactly here. Choosing a model sets it: 25 mm on the Mini, 19 on the 𝔐𝔦𝔨𝔯𝔬.",
    "brushograph-max_width": "Total width limit of machine (mm), measured from the origin. A painting starts at Offset X, so the widest one is this less that offset.",
    "brushograph-max_height": "Total height limit of machine (mm), measured from the origin. A painting starts at Canvas Start Y, past the strip the containers stand in, plus whatever Offset Y adds to it, so the tallest one is this less both: 124 mm of Pinkograph's 156.",
    "brushograph-level_compensation": "Write every move made on the paper at the height the paper is at there, from the five readings below, which are taken at the corners and middle of the bed itself, not of the painting. Canvas Height is one figure and a sheet taped to a bed is not one height: a brush set to touch in the middle rides over the paper at one corner and digs in at another, which a watercolour brush shows at a tenth of a millimetre. Off until the five are measured \u2014 with all five the same it does nothing anyway.",
    "brushograph-level_tl": "How much higher the paper is at the top-left of the bed than where Canvas Height was set, in millimetres. Take the brush there, lower it until it just touches, and type the difference from Canvas Height. The plan view marks the spot.",
    "brushograph-level_tr": "The same reading at the top-right corner of the bed. The plan view marks the spot.",
    "brushograph-level_c": "The same reading at the middle of the bed. This is the one that catches a twist: three corners fit a plane and can say nothing about a sheet that bellies or a bed that is not flat.",
    "brushograph-level_bl": "The same reading at the bottom-left corner of the bed, the corner nearest the containers. The plan view marks the spot.",
    "brushograph-level_br": "The same reading at the bottom-right corner of the bed. The plan view marks the spot.",
    "brushograph-moves-normal-acc": "How hard this machine accelerates while painting, in millimetres a second squared. Almost no stroke in a picture is long enough to reach the feedrate, so this figure decides how long a job takes far more than the feedrate does \u2014 the page's estimate is built on it. Marlin is sent it as an M204; GRBL and FluidNC hold their own figure and have that line stripped, so set this to match what the controller is configured with.",
    "brushograph-moves-fast-acc": "How hard this machine accelerates while travelling, in millimetres a second squared. The same figure as the painting one on every machine here, and used the same way \u2014 see the note on that one.",
    "brushograph-moves-remove_drops-acc": "How hard this machine accelerates while wiping a round cup's rim, in millimetres a second squared. Nothing reads it for a rectangular bay.",
    "brushograph-moves-normal-feedrate_1": "How fast the brush paints, in millimetres a minute. This is the rate a stroke is laid at, and the macros drop to it for the marks they put on the paper.",
    "brushograph-moves-fast-feedrate_1": "How fast the machine crosses the bed, in millimetres a minute \u2014 the trips to the containers and back, and the whole of every macro. Nothing the generator writes goes faster than this.",
    "brushograph-moves-remove_drops-feedrate_1": "How fast the brush is drawn over the rim of a round cup to shed its drop, in millimetres a minute. Nothing reads it for a rectangular bay, which wipes itself on the way up its stairs.",
    "brushograph-paint_per_run_min": "Minimum path length (mm) for painting. For plotting set this number really high (e.g. 1000000) to avoid the paint fetching sequence",
    "brushograph-paint_per_run_max": "Maximum path length (mm) for painting. For plotting set this number really high (e.g. 1000000) to avoid the paint fetching sequence",
    "brushograph-canvas_height": "Set canvas height (mm), for thicker surfaces (e.g. ceramic tile)",
    "brushograph-go_in_tray_lift": "Lift on Z-axis when going into a container for color",
    "brushograph-cup_shape": "Classic is the round cup the machine was built around: the brush goes down the middle, sweeps a chord and comes back up. CMYK is the rectangular five-bay holder, whose floor climbs towards the back — there the brush makes one swipe from the deep end to the shallow one, rising as it goes. Custom is rectangular cups swiped the same way, at the sizes and spacing you give below.",
    "brushograph-cup_dip_lanes": "Rectangular containers: how many places across the cup the pickups are spread over. The brush goes straight down at one of them, at Dip Depth, and swipes up the stairs from there, and the next pickup uses another — so the paint is mixed by where the brush lands rather than by stirring it. The lanes are evenly spaced over the middle 70% of the cup, 15% off each wall, and are visited out of order so one pickup and the next land at opposite ends of it. 1 puts every pickup down the middle.",
    "brushograph-cup_width_water": "Custom containers: how wide the water cup is across X, inside (mm). Wider than the colours, so the brush has room to be rinsed.",
    "brushograph-cup_width": "Custom containers: how wide each colour cup is across X, inside (mm).",
    "brushograph-cup_depth": "Custom containers: how far the swipe runs along Y, which should stay inside the cup (mm).",
    "brushograph-cup_spacing": "Custom containers: centre to centre between colour cups along X (mm). The water cup is parted from cyan by the same wall, so Auto-space puts cyan at half of each width plus that wall from the water.",
    "brushograph-cup_swipe_exit_z": "Z at the shallow end of the stairs, where the swipe finishes (mm). The swipe starts at Dip Depth, in the paint, and rises to this. Keep it above Canvas Height, or the brush leaves the cup at paper level. Auto-space containers sets it from the holder's design; adjust it on the machine if the brush does not drag up the stairs.",
    "brushograph-dip_depth": "How far the brush descends into a cup, as a Z coordinate. Negative goes down. Deep enough to reach the paint, no deeper — a shallow petri dish wants far less than a tall pot.",
    "brushograph-remove_drops_lift": "Lift when exiting the container, so it hits the edge and removes excess color",
    "brushograph-move_to_other_shape_lift": "Lift on Z-axis when painting/drawing",
    "brushograph-tray_enter_radius": "Must be smaller than the radius of the container",
    "brushograph-remove_drops_radius": "How far the brush is dragged over the rim to knock the drop off, once on each side (mm). Typically the same or slightly larger than the radius of the petri dish. Classic containers only: a modern bay wipes the brush on its own stairs, so nothing reads this.",
    "brushograph-prepare_paint_count": "Number of initial color mixing cycles. 0 for plotter",
    "brushograph-moves": "Speed settings for painting/drawing, fetching color (faster), and removing color drops",
    "brushograph-backlash_compensation": "Post-processes the generated G-code to apply backlash compensation by injecting specific corrective moves whenever the X or Y axis changes direction",
    "brushograph-backlash_x": "Play in the X axis (mm), measured at the X0 end of the bed. Draw backlash.g with a pen and read the upright pairs of its two stations at that end against the X gauge. On Pinkograph this is the axis that changes across the bed: 1.9 mm here and 1.3 at the far end.",
    "brushograph-backlash_x_far": "Play in the X axis (mm) at the far end of X. Read the upright pairs of backlash.g's two stations at that end. Equal to Backlash X means one figure everywhere, which is what an even axis wants; where the two differ the compensation follows a straight line between them across the bed. X play that changes with X is the belt: what is lost at a reversal is the slack and the stretch of the length between the drive and the carriage, and that length is what changes.",
    "brushograph-backlash_y": "Play in the Y axis (mm), measured at the X0 end of the bed. Read the flat pairs of backlash.g's two stations at that end against the Y gauge. Pinkograph reads 1.3 mm here and 1.2 at the far end, which is near enough one figure.",
    "brushograph-backlash_y_far": "Play in the Y axis (mm) at the far end of X. Read the flat pairs of backlash.g's two stations at that end. Two stations at one end that disagree mean the play depends on where the gantry stands along Y as well, which no pair of figures can describe: take the middle station's reading for both boxes. Y play that changes with X is the gantry beam twisting: it is driven from one side, so the far side arrives carrying whatever the beam has wound up. Equal figures mean one play everywhere.",
    "brushograph-max_width_mm": "Max brush width (mm) for Z-mapping",
    "brushograph-min_path_length_px": "Minimum skeleton path length in pixels",
    "brushograph-smooth_window_size": "Smoothing window size for path filtering",
    "brushograph-dip_distance_threshold_mm": "Travel distance in millimetres of painting before performing an automatic dip",
    "brushograph-feed_rate": "Feed rate mm/min for painting moves",
    "brushograph-dip_wipe_radius": "Wipe radius in millimetres after dipping",
    "brushograph-z_wipe_travel_raw": "Z height in millimetres used during wiping motion (before offset)",
    "brushograph-dip_entry_radius": "Dip entry radius in millimetres",
    "brushograph-remove_drops_enabled": "Enable removal of drops via wiping",
    "brushograph-z_global_offset_val": "Global Z offset added to all Z coordinates",
    "brushograph-z_safe_raw": "Safe Z for rapid moves (mm, before offset)",
    "brushograph-z_safe_dip_raw": "Safe Z for dip moves (mm, before offset)",
}

# Where a key's own name is not what the form should call it.
LABELS = {
    "cup_shape": "Container setup",
    # Named for the plan view, which draws Y upwards the way the bed is
    # looked at, and marks these five where they are.
    "level_compensation": "Bed levelling",
    "level_tl": "Z top-left",
    "level_tr": "Z top-right",
    "level_c": "Z middle",
    "level_bl": "Z bottom-left",
    "level_br": "Z bottom-right",
    # Only right while the box holds a figure. A config that keeps a whole line
    # of G-code in there gets the old label back, in _field.
    "feedrate_1": "Feedrate (mm/minute)",
    "acc": "Acceleration (mm/s\u00b2)",
    # Backlash X and Backlash Y are the near end, and keep the names they were
    # given when they were the only figures there were.
    "backlash_x_far": "Backlash X far end",
    "backlash_y_far": "Backlash Y far end",
}

_ACRONYMS = {"x": "X", "y": "Y", "z": "Z", "mm": "(mm)", "px": "(px)"}


def label_for(key: str) -> str:
    """cosmetic only: z_paint_max_raw -> 'Z Paint Max', max_width_mm -> 'Max Width (mm)'."""
    parts = key.split("_")
    if parts and parts[-1] == "raw":
        parts = parts[:-1]
    return " ".join(_ACRONYMS.get(p, p.capitalize()) for p in parts)


def _field(path: list[str], value) -> dict:
    name = "-".join(path)
    label = LABELS.get(path[-1]) or label_for(path[-1])
    # "Feedrate (mm/minute)" is a promise about the box, so it is only made
    # where the box holds a figure. A config whose speed group still carries a
    # line of G-code -- because it carries something this cannot read as a
    # plain rate -- is asking for that line, and says so.
    if path[-1] in PLAIN_KEYS and not isinstance(value, (int, float)):
        label = label_for(path[-1])
    f = {"name": name, "label": label, "help": HELP.get(name), "value": value}
    if name in ENUMS:
        f["type"] = "select"
        # Keep the config's own value even if it is not one of the known ones.
        options = list(ENUMS[name])
        if value not in options:
            options.insert(0, value)
        f["options"] = [{"value": o, "label": ENUM_LABELS.get(o, o)} for o in options]
    elif isinstance(value, bool):
        f["type"] = "checkbox"
    elif isinstance(value, (int, float)):
        f["type"] = "number"
    else:
        f["type"] = "text"
    return f


def _walk(path: list[str], value) -> list[dict]:
    """Flatten a config subtree into fields, keeping nested dicts as groups."""
    if isinstance(value, dict):
        groups, fields = [], []
        for k, v in value.items():
            if isinstance(v, dict):
                groups.append({"label": label_for(k), "fields": _walk(path + [k], v)})
            elif isinstance(v, list):
                continue  # lists (color_order, additionals) are structure, not settings
            else:
                fields.append(_field(path + [k], v))
        out = fields
        for g in groups:
            out.append({"group": g["label"], "fields": g["fields"], "help": HELP.get("-".join(path))})
        return out
    return [_field(path, value)]


def workable_x(conf: dict) -> float:
    """The furthest right a job already asks the machine to go.

    The containers and the far edge of the canvas: a job has always visited
    both, so both are known to be reachable. Deliberately not the axis travel.
    zero.g sweeps to the model's far corner and drives into the endstops on
    purpose, which is what zeroes the machine and what makes that corner
    useless as a working limit: the machine cannot reach out there. A move that
    ends against a stop loses what it loses for the whole of the rest of the
    file, and everything after it lands short of where it was asked for.
    The stir in the paint is the only thing that would otherwise go looking for
    room past the last container, and the last container is black.

    Only the containers the job actually dips in, which is what tray_entries
    lists — the water cup and the colours in color_order. A cup the job never
    visits says nothing about where the machine can go, and one it does not
    paint from tends to be parked well off the bed, as the additionals always
    are.
    """
    bg = conf.get("brushograph", {})
    wanted = {e["tray"] for e in tray_entries(conf)}
    xs = [float(t["x"]) for name, t in conf.get("trays", {}).items()
          if name in wanted and isinstance(t, dict) and "x" in t]
    try:
        xs.append(float(bg.get("offset_x", 0)) + float(bg.get("width", 0)))
    except (TypeError, ValueError):
        pass
    return max(xs) if xs else 0.0


def tray_entries(conf: dict) -> list[dict]:
    """Water tray plus one entry per colour in color_order, in painting order.

    Painting order is Y M C K (PAINT_ORDER), whatever order the config lists
    its colours in: the entries are what the job paints in sequence, and what
    the tray cards and the plan's painting order are listed from.

    Tray numbering follows the position in the trays dict, which is why a config
    with a water tray starts its colours at 1 and one without starts at 0. A
    CMYK channel is labelled by its colour instead; the positional name is the
    fallback for the additionals, which have no channel to be named after.
    """
    trays = conf.get("trays", {})
    # Number by position among actual trays. "additionals" sits in the same dict
    # but is a group of colours, not a cup, so counting it would skip a number
    # for every tray declared after it — which is where a fifth cup lands.
    order = [k for k in trays if k not in TRAY_SKIP]
    wanted = []
    for color in paint_order(conf.get("color_order", [])):
        tray_name = CMYK_TO_TRAY.get(color, color)
        if tray_name in trays and tray_name not in TRAY_SKIP:
            wanted.append((tray_name, color))

    entries = []
    if "water" in trays:
        entries.append(
            {
                "tray": "water",
                "color": None,
                "index": 0,
                "label": "Water",
                "image": False,
                "x": trays["water"].get("x", 0),
                "y": trays["water"].get("y", 0),
            }
        )
    for tray_name, color in wanted:
        entries.append(
            {
                "tray": tray_name,
                "color": color,
                "index": order.index(tray_name),
                "label": CMYK_LABEL.get(color, f"Tray {order.index(tray_name)}")
                + (f" ({color})" if color in CMYK_LABEL else ""),
                "image": True,
                "x": trays[tray_name].get("x", 0),
                "y": trays[tray_name].get("y", 0),
            }
        )
    return entries


# Every holder is one straight row in the same order, whatever its centres:
# water first, then cyan, magenta, yellow, and — where there is a fifth place —
# black. MODERN_BAY_OFFSETS, the Mikro's and CLASSIC_DISH_OFFSETS all read that
# way, because the cups cannot be moved relative to each other.
CUP_ORDER = ("water", "cyan", "magenta", "yellow", "kroma")


def in_cup_order(entries: list[dict]) -> list[dict]:
    """tray_entries sorted the way the cups actually stand on the bed.

    The entries come in painting order, Y M C K, because that is the sequence
    the job runs in and the order the picture cards and the plan's legend want.
    Container positions are not a sequence, though: they are a row of cups, and
    listing them Water, Yellow, Magenta, Cyan put the form's rows in the
    opposite order to the holder in front of you — on Classic, four dishes
    plainly running W C M Y at 0, 45, 89 and 133 from the water. Reading a
    position off the machine and typing it into the third box down meant
    counting backwards every time.

    Sorted rather than rebuilt, so every entry keeps its label, index and
    picture flag. An additional colour is in no holder's row, so it sorts last
    and keeps its painting order among its own kind — the sort is stable.
    """
    return sorted(entries, key=lambda e: CUP_ORDER.index(e["tray"])
                  if e["tray"] in CUP_ORDER else len(CUP_ORDER))


# The separation's own order, which is the one the letters are said in and the
# one every plate is labelled with: C, M, Y, K.
CARD_ORDER = ("C", "M", "Y", "K")


def in_channel_order(entries: list[dict]) -> list[dict]:
    """tray_entries sorted the way the plates are named, C M Y K.

    The cards are where a picture is chosen for each plate, and a picture is
    chosen against the plate's letter — the file from the separation is called
    `-c1`, the card says "Cyan (C)". Painting order is a fact about the job,
    not about the pictures: listing the cards Yellow, Magenta, Cyan, Black put
    them in the reverse of the order they are spoken and of the order the
    separation hands the four files over, so picking the right file for the
    right card meant reading every heading.

    Painting order is still what the job runs in and what the plan's legend
    shows; only the cards are sorted. Sorted rather than rebuilt, so each entry
    keeps its label, index and picture flag, and an additional colour, which is
    no CMYK channel, sorts last in its painting order — the sort is stable.
    """
    return sorted(entries, key=lambda e: CARD_ORDER.index(e["color"])
                  if e["color"] in CARD_ORDER else len(CARD_ORDER))


def _regroup(fields: list[dict], groups) -> list[dict]:
    """Sort flat fields into named groups, keeping anything unlisted."""
    loose, nested = {}, []
    for f in fields:
        if f.get("group"):
            nested.append(f)          # a dict in the config, already a group
        else:
            loose[f["name"].rsplit("-", 1)[-1]] = f
    out = []
    for title, keys, is_job in groups:
        picked = [loose.pop(k) for k in keys if k in loose]
        if picked:
            out.append({"group": title, "fields": picked, "job": is_job})
    # A config with settings this map has never heard of still shows them.
    if loose:
        out.append({"group": "Other settings", "fields": list(loose.values()), "job": False})
    out.extend(nested)
    return out


def build_schema(conf: dict) -> list[dict]:
    """Sections in the order the UI renders them, skipping ones the config lacks."""
    conf = with_defaults(conf)
    schema = []
    for key, title in SECTIONS:
        if key not in conf:
            continue
        if key == "trays":
            # Three orders of the same trays: painting order, which is the
            # job's; the holder's own row for the positions; and C M Y K for
            # the picture cards, which is how the plates are named.
            entries = tray_entries(conf)
            schema.append({"key": key, "title": title, "trays": entries,
                           "cups": in_cup_order(entries),
                           "cards": in_channel_order(entries)})
        else:
            fields = _walk([key], conf[key])
            if key == "brushograph":
                fields = _regroup(fields, BRUSHOGRAPH_GROUPS)
            schema.append({"key": key, "title": title, "fields": fields})
    return schema


# ------------------------------------------------------------------ form -> conf

def _coerce(original, raw: str):
    """Match the type the config had, so a round trip does not rewrite it."""
    if isinstance(original, bool):
        return raw.lower() in {"true", "1", "on", "yes"}
    if isinstance(original, int) and not isinstance(original, bool):
        try:
            f = float(raw)
        except ValueError:
            return original
        return int(f) if f.is_integer() else f
    if isinstance(original, float):
        try:
            return float(raw)
        except ValueError:
            return original
    return raw


def apply_form(conf: dict, form) -> tuple[dict, list[str]]:
    """Fold posted `a-b-c` fields back into a copy of the config."""
    out = with_defaults(conf)
    problems = []
    for name in form.keys():
        if name in {"session_id", "machine_config_name", "machine_config_mode",
                    "machine_config_version", "config_only", "sketch_only", "cmyk_photo",
                    "cmyk_threshold", "cmyk_knockout", "cmyk_contours"}:
            continue
        parts = name.split("-")
        node = out
        for p in parts[:-1]:
            if not isinstance(node, dict) or p not in node:
                node = None
                break
            node = node[p]
        if node is None or not isinstance(node, dict) or parts[-1] not in node:
            continue  # unknown field: never invent config keys from form input
        leaf = parts[-1]
        values = form.getlist(name)
        # A checkbox posts a hidden "false" plus "true" when ticked.
        raw = values[-1] if values else ""
        new = _coerce(node[leaf], raw)
        if isinstance(node[leaf], (int, float)) and not isinstance(node[leaf], bool):
            try:
                float(raw)
            except ValueError:
                problems.append(f"{name}: '{raw}' is not a number")
                continue
        node[leaf] = new
    return fit_cups_to_shape(out), problems
