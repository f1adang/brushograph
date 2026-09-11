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

# The modern holder, measured off CMYK_holder_big.stl. Five bays: the water one
# is 39.1 mm across and every colour bay 29.1, with the walls between them
# putting the colour bays on 34 mm centres and the first colour 39 mm from the
# water. The numbers here are centre-to-centre offsets from the water bay, so a
# layout only needs to know where the holder's water end sits.
MODERN_BAY_OFFSETS = OrderedDict(
    [("water", 0.0), ("cyan", 39.0), ("magenta", 73.0), ("yellow", 107.0), ("kroma", 141.0)]
)

# Settings the form always offers, whatever the config happens to carry. The
# form is otherwise built from the config's own keys, so a machine file written
# before one of these existed — or by hand, or by an older version — simply has
# no control for it and no way to gain one.
#
# Defaults are chosen to be safe on a machine that never named them: a dip no
# deeper than the old fixed one, and a backlash figure small enough to be worth
# tuning rather than large enough to matter if ignored.
ALWAYS_OFFERED = {
    ("brushograph", "dip_depth"): -4.0,
    # The cups. "classic" is the round petri dish the machine was built around;
    # "modern" is the rectangular CMYK holder, whose floor steps up towards the
    # back so the brush can be drawn out of the paint rather than lifted from
    # it. Measured off CMYK_holder_big.stl by bisecting to the bay walls: the
    # four colour bays are 29.2 mm across and the water bay 39.2, all of them
    # opening 35.1 mm deep. The stepped floor is not in that file — it is a
    # frame over the paint — so the two Z figures below have to be measured on
    # the machine rather than derived, and the depth stays inside the opening.
    ("brushograph", "cup_shape"): "classic",
    ("brushograph", "cup_width"): 29.2,
    ("brushograph", "cup_width_water"): 39.2,
    ("brushograph", "cup_depth"): 30.0,
    ("brushograph", "cup_swipe_exit_z"): 1.0,
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


def _offer_black(conf: dict) -> None:
    """Give a config a black cup if it has not got one.

    The holder has a bay for black, so the machine paints CMYK. A config
    written before that bay existed names three colours, and the form is built
    from the config: with no `kroma` tray and no `K` in `color_order` there is
    no black card to upload to and no way to gain one, which is the same reason
    ALWAYS_OFFERED exists for settings.

    Where the cup is, is a measurement. The guess is one more step along the row
    the other cups are already in — the gap between the last two of them, or the
    holder's own 34 mm if there are not two to learn from — which lands it about
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
    ("Painted size", ["width", "height"], True),
    ("Where it sits on the bed",
     ["offset_x", "offset_y", "max_width", "max_height", "canvas_height"], False),
    ("Brush heights",
     ["go_in_tray_lift", "dip_depth", "remove_drops_lift", "move_to_other_shape_lift"], False),
    ("Containers",
     ["cup_shape", "cup_width", "cup_width_water", "cup_depth", "cup_swipe_exit_z"], False),
    ("Loading the brush",
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
    "classic": "Classic",
    "modern": "Modern",
}

ENUMS = {
    # Ordered by how well
    # they suit a brush: long flowing strokes first, raster last.
    "slicer-infill_pattern": [
        "concentric", "archimedeanchords", "alignedrectilinear", "rectilinear", "hilbertcurve",
    ],
    "controller-controller_type": ["GRBL", "Marlin", "FluidNC"],
    "brushograph-cup_shape": ["classic", "modern"],
}

# Keys that describe the machine rather than a run, kept out of the generated
# form because the Trays section renders them itself.
TRAY_SKIP = {"additionals"}

HELP = {
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
    "brushograph-cup_shape": "Classic is the round cup the machine was built around: the brush goes down the middle, sweeps a chord and comes back up. Modern is the rectangular CMYK holder, whose floor climbs towards the back — there the brush makes one swipe from the deep end to the shallow one, rising as it goes.",
    "brushograph-cup_width": "How wide a colour cup is across X (mm). Modern cups only; a colour bay of the printed holder measures 29.2.",
    "brushograph-cup_width_water": "How wide the water cup is across X (mm). Modern cups only. The holder gives the water its own, wider bay — 39.2 against the colours' 29.2 — so the brush has room to be rinsed.",
    "brushograph-cup_depth": "How deep a cup is along Y (mm) — the length of the swipe. Modern cups only. The holder's bays open 35.1 mm deep; the default keeps the swipe inside that.",
    "brushograph-cup_swipe_exit_z": "Z at the shallow end of the stairs, where the swipe finishes (mm). The swipe starts at Dip Depth, in the paint, and rises to this. Keep it above Canvas Height, or the brush leaves the cup at paper level. Measure it on the machine: nothing in the holder's STL gives the step heights.",
    "brushograph-dip_depth": "How far the brush descends into a cup, as a Z coordinate. Negative goes down. Deep enough to reach the paint, no deeper — a shallow petri dish wants far less than a tall pot.",
    "brushograph-remove_drops_lift": "Lift when exiting the container, so it hits the edge and removes excess color",
    "brushograph-move_to_other_shape_lift": "Lift on Z-axis when painting/drawing",
    "brushograph-tray_enter_radius": "Must be smaller than the radius of the container",
    "brushograph-remove_drops_radius": "Radius for exiting the container, typically the same or slightly larger than radius of petridish",
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

_ACRONYMS = {"x": "X", "y": "Y", "z": "Z", "mm": "(mm)", "px": "(px)"}


def label_for(key: str) -> str:
    """cosmetic only: z_paint_max_raw -> 'Z Paint Max', max_width_mm -> 'Max Width (mm)'."""
    parts = key.split("_")
    if parts and parts[-1] == "raw":
        parts = parts[:-1]
    return " ".join(_ACRONYMS.get(p, p.capitalize()) for p in parts)


def _field(path: list[str], value) -> dict:
    name = "-".join(path)
    f = {"name": name, "label": label_for(path[-1]), "help": HELP.get(name), "value": value}
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
                    "config_only", "sketch_only"}:
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
    return out, problems
