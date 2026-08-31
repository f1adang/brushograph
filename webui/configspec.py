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
    ("brushograph", "backlash_compensation"): True,
    ("brushograph", "backlash_x"): 0.5,
    ("brushograph", "backlash_y"): 0.5,
}


# Settings whose *opening* state in the form is fixed, whatever a config stores.
# Backlash compensation is wanted on: a config carrying a stale `false` — the
# ones published for these machines do — should not quietly start it off. The
# box is still a box, and unticking it is honoured for the run and written out
# by Download Config; only the state it opens in is decided here.
FORM_DEFAULTS = {
    ("brushograph", "backlash_compensation"): True,
}


def _dig(conf: dict, path: tuple) -> dict:
    node = conf
    for key in path[:-1]:
        if not isinstance(node.get(key), dict):
            node[key] = {}
        node = node[key]
    return node


def with_defaults(conf: dict, for_form: bool = False) -> dict:
    """A copy of the config with the always-offered settings filled in.

    `for_form` additionally forces the settings whose opening state is fixed.
    Folding a posted form back does not use it, so what the operator chose on
    screen is what takes effect.
    """
    out = json.loads(json.dumps(conf))
    for path, value in ALWAYS_OFFERED.items():
        _dig(out, path).setdefault(path[-1], value)
    if for_form:
        for path, value in FORM_DEFAULTS.items():
            _dig(out, path)[path[-1]] = value
    return out


SECTIONS = [
    ("trays", "Trays and Images"),
    ("brushograph", "Brushograph Options"),
    ("slicer", "Slicer Options"),
    ("controller", "Controller Options"),
]

ENUMS = {
    # Only patterns the slicer accepts at 100% density. Ordered by how well
    # they suit a brush: long flowing strokes first, raster last.
    "slicer-infill_pattern": [
        "concentric", "archimedeanchords", "alignedrectilinear", "rectilinear", "hilbertcurve",
    ],
    "controller-controller_type": ["GRBL", "Marlin", "FluidNC"],
}

# Keys that describe the machine rather than a run, kept out of the generated
# form because the Trays section renders them itself.
TRAY_SKIP = {"additionals"}

HELP = {
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
        f["options"] = options
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
    with a water tray starts its colours at 1 and one without starts at 0.
    """
    trays = conf.get("trays", {})
    order = list(trays.keys())
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
                "label": f"Tray {order.index(tray_name)}",
                "image": True,
                "x": trays[tray_name].get("x", 0),
                "y": trays[tray_name].get("y", 0),
            }
        )
    return entries


def build_schema(conf: dict) -> list[dict]:
    """Sections in the order the UI renders them, skipping ones the config lacks."""
    conf = with_defaults(conf, for_form=True)
    schema = []
    for key, title in SECTIONS:
        if key not in conf:
            continue
        if key == "trays":
            schema.append({"key": key, "title": title, "trays": tray_entries(conf)})
        else:
            schema.append({"key": key, "title": title, "fields": _walk([key], conf[key])})
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
