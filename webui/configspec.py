#!/usr/bin/python3
"""Turns a machine .conf into a form schema, and a submitted form back into a .conf.

The form is generated from the config itself: whatever keys a config carries get
rendered, so a config for a different generator brings its own fields along.
Field names are flat, dash-joined paths ("brushograph-moves-normal-acc") so a
posted form can be folded straight back into the nested JSON it came from.
"""
from __future__ import annotations

import json
from collections import OrderedDict

CMYK_TO_TRAY = {"C": "cyan", "M": "magenta", "Y": "yellow", "K": "kroma"}

# What each channel is called in the form. "kroma" is what the tray is keyed as
# throughout this project, and it is not a word anyone reading the machine
# expects: the holder has W C M Y K stamped on it, so the form says Black (K)
# and leaves "kroma" showing as the config key it is.
CMYK_LABEL = {"C": "Cyan", "M": "Magenta", "Y": "Yellow", "K": "Black"}

# The Mini's CMYK holder: the `Standard_CMYK` preset of openBrushograph_hardware's
# Extras/colourContainers.scad (once mini_petri.scad), which is the design,
# checked against the parts in Extras/CMYK_ColourContainers,
# standard_CMYK_holder.stl and standard_colourContainters_steps.stl. Five
# crucibles in a row: a 30 mm water one and four of 18.6, with 5 mm between
# them, so the colours sit on 23.6 mm centres and the first 29.3 mm from the
# water — slicing the holder finds its slots centred at 25.0, 54.3, 77.9, 101.5
# and 125.1. (An earlier, bigger holder, CMYK_holder_big.stl, had 34 mm
# centres; it is not the design.) The numbers here are centre-to-centre offsets
# from the water crucible, so a layout only needs to know where the water sits.
MODERN_BAY_OFFSETS = OrderedDict(
    [("water", 0.0), ("cyan", 29.3), ("magenta", 52.9), ("yellow", 76.5), ("kroma", 100.1)]
)

# The crucibles themselves, inside their 1.2 mm walls: 27.6 mm for water and
# 16.2 for a colour, 27.6 long. These are fixed by the print, not tuned per
# machine, so they are constants rather than settings: the water crucible is
# the wide one so the brush has room to be rinsed. The swipe keeps inside the
# length the way the 30 mm swipe kept inside the old holder's 35.1 mm bays.
MODERN_BAY_WIDTH = 16.2
MODERN_WATER_BAY_WIDTH = 27.6
MODERN_SWIPE_LENGTH = 23.5

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
            "outside": (30.0, 18.6, 30.0),
            # The plate the crucibles stand in: width and depth, then where the
            # water crucible's centre is from its left and front edges. Its
            # slots open 9 mm back from the front, 30.4 mm deep.
            "plate": (144.4, 39.2, 25.0, 24.2),
            # 9 mm crucibles with a 1.2 mm floor, 30 mm long.
            "settings": _crucible_settings(9, 1.2, 30, MODERN_SWIPE_LENGTH),
        },
        "classic": True,
        # What choosing the model puts in the form.
        "settings": OrderedDict([
            ("max_width", 151), ("max_height", 156), ("offset_x", 0), ("offset_y", 25),
        ]),
        # Where choosing the model puts the water container; the others are
        # auto-spaced from it.
        "water": (12, 6),
        # zero.g's sweep to the far corner and back: X, Y, Z.
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
            ("max_width", 65), ("max_height", 100), ("offset_x", 0), ("offset_y", 19),
        ]),
        "water": (2, 6),
        # The Mini's sweep, shortened by the racks and scaled to the Z travel.
        "zero_sweep": (75, 123, 21),
    }),
])


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
    **{("brushograph", key): value for key, value in CUSTOM_CUP_DEFAULTS.items()},
    ("brushograph", "backlash_compensation"): True,
    ("brushograph", "backlash_x"): 0.5,
    ("brushograph", "backlash_y"): 0.5,
    ("connection", "hostname"): "fluidnc.local",
}


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
    """
    out = json.loads(json.dumps(conf))
    for path, value in ALWAYS_OFFERED.items():
        _dig(out, path).setdefault(path[-1], value)
    _offer_black(out)
    return out


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
    Mini holder's own 23.6 mm if there are not two to learn from — which lands it about
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
    ("Painted size", ["width", "height"], True),
    ("Canvas",
     ["offset_x", "offset_y", "max_width", "max_height", "canvas_height"], False),
    ("Brush control",
     ["go_in_tray_lift", "dip_depth", "remove_drops_lift", "move_to_other_shape_lift"], False),
    ("Containers",
     ["cup_shape", "cup_swipe_exit_z", "cup_width_water", "cup_width", "cup_depth",
      "cup_spacing"], False),
    ("Paint management",
     ["paint_per_run_min", "paint_per_run_max", "prepare_paint_count",
      "tray_enter_radius", "remove_drops_radius"], False),
    ("Backlash", ["backlash_compensation", "backlash_x", "backlash_y"], False),
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
        "concentric", "archimedeanchords", "alignedrectilinear", "rectilinear", "hilbertcurve",
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
    "brushograph-offset_x": "X offset for image (0,0) position",
    "brushograph-offset_y": "Y offset for image (0,0) position",
    "brushograph-max_width": "Total width limit of machine (mm)",
    "brushograph-max_height": "Total height limit of machine (mm)",
    "brushograph-paint_per_run_min": "Minimum path length (mm) for painting. For plotting set this number really high (e.g. 1000000) to avoid the paint fetching sequence",
    "brushograph-paint_per_run_max": "Maximum path length (mm) for painting. For plotting set this number really high (e.g. 1000000) to avoid the paint fetching sequence",
    "brushograph-canvas_height": "Set canvas height (mm), for thicker surfaces (e.g. ceramic tile)",
    "brushograph-go_in_tray_lift": "Lift on Z-axis when going into a container for color",
    "brushograph-cup_shape": "Classic is the round cup the machine was built around: the brush goes down the middle, sweeps a chord and comes back up. CMYK is the rectangular five-bay holder, whose floor climbs towards the back — there the brush makes one swipe from the deep end to the shallow one, rising as it goes. Custom is rectangular cups swiped the same way, at the sizes and spacing you give below.",
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
    "brushograph-backlash_x": "Backlash distance (mm) to apply when the X-axis reverses direction.",
    "brushograph-backlash_y": "Backlash distance (mm) to apply when the Y-axis reverses direction.",
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
    f = {"name": name, "label": LABELS.get(path[-1]) or label_for(path[-1]), "help": HELP.get(name), "value": value}
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


def tray_entries(conf: dict) -> list[dict]:
    """Water tray plus one entry per colour in color_order, in config order.

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
    for color in conf.get("color_order", []):
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
            schema.append({"key": key, "title": title, "trays": tray_entries(conf)})
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
                    "cmyk_threshold"}:
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
