#!/usr/bin/python3
"""Renders the machine sketch: bed limits, canvas, and tray positions to scale."""
from __future__ import annotations

import io
import os

from PIL import Image, ImageDraw, ImageFont

from configspec import (CLASSIC_DISH_RIM_RADIUS, RECTANGULAR_SHAPES, cup_shape_of, holder_of,
                        tray_entries)

W, H = 760, 480
PAD = 46

# One palette per interface theme, so the plan sits on the same paper the page
# does. Only the surfaces and the annotation change: the tray fills are the
# paint in the cups and are the same colour whatever the page is wearing —
# except black, which on a dark ground is the ground. Each palette carries a
# `key` for that, the same value the stylesheet gives `--k`.
PALETTES = {
    "default": dict(bg=(255, 255, 255), grid=(232, 234, 238), bed=(120, 128, 140),
                    canvas=(40, 44, 52), text=(60, 66, 76), muted=(150, 156, 166),
                    accent=(200, 90, 90), key=(35, 35, 40)),
    "dark": dict(bg=(29, 33, 32), grid=(45, 51, 50), bed=(123, 133, 131),
                 canvas=(230, 233, 232), text=(211, 216, 214), muted=(134, 143, 141),
                 accent=(224, 138, 122), key=(223, 228, 226)),
    "coconut": dict(bg=(253, 246, 232), grid=(234, 217, 189), bed=(185, 138, 82),
                    canvas=(55, 34, 15), text=(74, 44, 24), muted=(125, 92, 57),
                    accent=(156, 43, 22), key=(35, 35, 40)),
    "pinkograph": dict(bg=(22, 3, 42), grid=(60, 10, 102), bed=(255, 107, 181),
                       canvas=(255, 234, 244), text=(227, 160, 192), muted=(160, 110, 150),
                       accent=(0, 245, 255), key=(232, 214, 245)),
    "uwu": dict(bg=(43, 8, 36), grid=(69, 18, 58), bed=(255, 138, 212),
                       canvas=(255, 232, 246), text=(255, 212, 238), muted=(229, 140, 192),
                       accent=(255, 107, 107), key=(255, 220, 240)),
    "kongress": dict(bg=(246, 245, 240), grid=(216, 214, 206), bed=(20, 20, 20),
                     canvas=(10, 10, 10), text=(0, 0, 0), muted=(90, 90, 90),
                     accent=(139, 0, 0), key=(0, 0, 0)),
}

# How many stairs a CMYK crucible has — five, in both of mini_petri.scad's
# presets.
MODERN_STEPS = 5

# The K tray is keyed "kroma" throughout this project. The holder has W C M Y K
# stamped on it and nothing says kroma, so the drawing calls it black.
TRAY_LABEL = {"kroma": "black"}
TRAY_LABEL_DE = {
    "kroma": "Schwarz",
    "water": "Wasser",
    "cyan": "Cyan",
    "magenta": "Magenta",
    "yellow": "Gelb",
}

# Every word the plan writes on itself. 𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘 is a
# German-language theme, and this drawing is lettered on the server rather than
# in the browser, so it is translated here rather than in static/de.js with the
# rest of the interface. The vocabulary is the same one: bed → Arbeitsfläche,
# the image area → Druckbereich, a tray → Behälter.
WORDS = {
    "default": {
        "trays": TRAY_LABEL,
        "bed": "bed {w:g} × {h:g} mm",
        "image": "image {w:g} × {h:g} mm @ ({x:g}, {y:g})",
        "off_bed": " (off bed)",
        "order": "Painting order: {order}",
        "order_none": "none in color_order",
        "offscreen": "not shown, parked far outside the bed: {trays}",
    },
    "kongress": {
        "trays": TRAY_LABEL_DE,
        "bed": "Arbeitsfläche {w:g} × {h:g} mm",
        "image": "Druckbereich {w:g} × {h:g} mm bei ({x:g}, {y:g})",
        "off_bed": " (außerhalb)",
        "order": "Auftragsreihenfolge: {order}",
        "order_none": "keine in der Auftragsreihenfolge",
        "offscreen": "nicht dargestellt, weit außerhalb der Arbeitsfläche: {trays}",
    },
}

TRAY_FILL = {
    "water": (150, 200, 235),
    "cyan": (0, 174, 239),
    "magenta": (236, 0, 140),
    "yellow": (255, 212, 0),
    # kroma is not here: black is whatever the palette's `key` says, because on
    # the dark grounds a black cup drawn black is an empty patch of background.
}


def font_for(size=12, theme="default"):
    """The face this theme writes in. Shared with the CMYK contact sheet, so
    both server-drawn pictures are lettered the way the page around them is."""
    if theme == "kongress":
        local_font = os.path.join(os.path.dirname(__file__), "static", "UnifrakturMaguntia.ttf")
        if os.path.exists(local_font):
            try:
                return ImageFont.truetype(local_font, size)
            except OSError:
                pass
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _num(d, key, default=0.0):
    try:
        return float(d.get(key, default))
    except (TypeError, ValueError):
        return default


def render(conf: dict, theme: str = "default") -> bytes:
    pal = PALETTES.get(theme, PALETTES["default"])
    BG, GRID, BED = pal["bg"], pal["grid"], pal["bed"]
    CANVAS, TEXT, MUTED, ACCENT = pal["canvas"], pal["text"], pal["muted"], pal["accent"]

    bg = conf.get("brushograph", {})
    trays = conf.get("trays", {})

    cw, ch = _num(bg, "width", 0), _num(bg, "height", 0)
    ox, oy = _num(bg, "offset_x", 0), _num(bg, "offset_y", 0)
    # Max Width and Max Height are the machine's limits, measured from the
    # origin where the trays are, so the bed is drawn at them alone. A painting
    # starts at the canvas offset, which leaves it the limit less that offset —
    # 131 mm of Pinkograph's 156, the other 25 being the strip its containers
    # stand in. This was drawn as offset plus limit, a bed 25 mm longer than the
    # machine, because a full-size Mini picture otherwise hung over the edge of
    # it. That picture really did hang over the edge: the form was matching the
    # painted height against the limit without taking the offset off first, and
    # a 149 mm painting on Pinkograph ran 18 mm past the end of the bed. The
    # form subtracts it now, and a canvas that still overshoots is drawn
    # overshooting rather than given a bed that flatters it.
    max_w = _num(bg, "max_width", _num(bg, "width", 200))
    max_h = _num(bg, "max_height", _num(bg, "height", 200))
    enter_r = _num(bg, "tray_enter_radius", _num(bg, "dip_entry_radius", 5))
    modern = cup_shape_of(conf) in RECTANGULAR_SHAPES
    # The holder the model was printed with: a Micro's crucibles are a fraction
    # of the Mini's bays.
    holder = holder_of(conf)
    # Drawn at their outside size, which is what you see on the bed: the inside
    # was a good deal smaller — 16.2 against 18.6 across, and only the swipe's
    # 23.5 of the 30 mm length — and the holder looked like a row of gaps.
    cup_w_water, cup_w, cup_h = holder["outside"]
    swipe = holder["swipe_length"]

    def bay_w(name):
        return cup_w_water if name == "water" else cup_w
    drops_r = _num(bg, "remove_drops_radius", _num(bg, "dip_wipe_radius", 0))

    entries = tray_entries(conf)
    # Include every tray the config defines, even ones outside color_order, so
    # a tray parked off the bed is visible rather than silently cropped.
    all_trays = [
        (name, _num(t, "x"), _num(t, "y"))
        for name, t in trays.items()
        if isinstance(t, dict) and "x" in t
    ]
    for name, sub in trays.get("additionals", {}).items():
        if isinstance(sub, dict) and "x" in sub:
            all_trays.append((name, _num(sub, "x"), _num(sub, "y")))

    # Frame on the bed, the image area and the trays actually in color_order.
    # Configs routinely park unused trays hundreds of mm away; letting those set
    # the scale would squash the part you care about into a corner.
    active = {e["tray"] for e in entries}
    framed = [(n, x, y) for n, x, y in all_trays if n in active]
    pad_r = max(cup_w_water / 2, cup_w / 2, cup_h / 2) if modern \
        else max(drops_r, enter_r, CLASSIC_DISH_RIM_RADIUS)
    xs = [0.0, max_w, ox, ox + cw] + [x + pad_r for _, x, _ in framed] + [x - pad_r for _, x, _ in framed]
    ys = [0.0, max_h, oy, oy + ch] + [y + pad_r for _, _, y in framed] + [y - pad_r for _, _, y in framed]
    # The CMYK holder is a plate the crucibles stand in, a good deal bigger than
    # the row of them: placed off the water crucible, since that is the one
    # position the form takes as where the holder sits.
    water = trays.get("water") if isinstance(trays, dict) else None
    plate = None
    if modern and holder["plate"] and isinstance(water, dict) and "x" in water:
        pw, pd, wx_in, wy_in = holder["plate"]
        left, front = _num(water, "x") - wx_in, _num(water, "y") - wy_in
        plate = (left, front, left + pw, front + pd)
        xs += [plate[0], plate[2]]
        ys += [plate[1], plate[3]]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    scale = min((W - 2 * PAD) / span_x, (H - 2 * PAD) / span_y)

    # Machine Y grows away from the origin; screen Y grows downward.
    def px(x, y):
        return (PAD + (x - min_x) * scale, H - PAD - (y - min_y) * scale)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")
    f, fs = font_for(13 if theme == "kongress" else 12, theme=theme), font_for(11 if theme == "kongress" else 10, theme=theme)

    step = 10 if span_x <= 220 else 50
    g = min_x - (min_x % step)
    while g <= max_x:
        x0, _ = px(g, 0)
        d.line([(x0, PAD - 8), (x0, H - PAD + 8)], fill=GRID)
        g += step
    g = min_y - (min_y % step)
    while g <= max_y:
        _, y0 = px(0, g)
        d.line([(PAD - 8, y0), (W - PAD + 8, y0)], fill=GRID)
        g += step

    words = WORDS.get(theme, WORDS["default"])
    tray_labels = words["trays"]

    # Bed limits
    d.rectangle([px(0, max_h), px(max_w, 0)], outline=BED, width=2)
    # Right-aligned: the bed and the image often share a top-left corner. And
    # above the line rather than under it, where a picture a few millimetres
    # short of the top of the bed would run its edge through the words — or
    # above the picture, when one taller than the machine's limit passes it.
    bx, by = px(max_w, max(max_h, oy + ch))
    txt = words["bed"].format(w=max_w, h=max_h)
    d.text((bx - d.textlength(txt, font=fs) - 5, by - 16), txt, font=fs, fill=MUTED)

    # Canvas / image area
    if cw and ch:
        d.rectangle([px(ox, oy + ch), px(ox + cw, oy)], fill=(*CANVAS, 18), outline=CANVAS, width=2)
        tx, ty = px(ox, oy + ch)
        d.text((tx + 5, ty + 4), words["image"].format(w=cw, h=ch, x=ox, y=oy),
               font=fs, fill=TEXT)

    if plate:
        d.rectangle([px(plate[0], plate[3]), px(plate[2], plate[1])],
                    fill=(*MUTED, 40), outline=(*MUTED, 200), width=1)

    offscreen = []
    for name, x, y in all_trays:
        if not (min_x - pad_r <= x <= max_x + pad_r and min_y - pad_r <= y <= max_y + pad_r):
            offscreen.append(name)
            continue
        cx, cy = px(x, y)
        in_use = name in active
        fill = pal["key"] if name == "kroma" else TRAY_FILL.get(name, (120, 120, 130))
        if name.startswith("#"):
            try:
                fill = tuple(int(name[i:i + 2], 16) for i in (1, 3, 5))
            except ValueError:
                pass
        alpha = 255 if in_use else 70
        if modern:
            # A rectangular crucible, with the stairs its floor climbs drawn
            # across the back of it: the brush swipes from the deep end up
            # them, rising as it goes, so the stairs are the thing worth
            # seeing. The water crucible is the wide one — 30 mm against the
            # colours' 18.6 on the Mini — and drawing them all alike hid which
            # cup that was.
            hw, hh = max(bay_w(name) * scale / 2, 3), max(cup_h * scale / 2, 3)
            d.rectangle([cx - hw, cy - hh, cx + hw, cy + hh],
                        fill=(*fill, alpha), outline=(*CANVAS, alpha), width=1)
            # The stairs take the back 40%, away from the origin — up here.
            stairs = 2 * hh * 0.4
            for i in range(MODERN_STEPS):
                sy = cy - hh + stairs * i / MODERN_STEPS
                d.line([(cx - hw, sy), (cx + hw, sy)], fill=(*CANVAS, alpha))
            # The swipe, at its own length, from the deep end up the stairs.
            sh = max(swipe * scale / 2, 3)
            d.line([(cx, cy + sh), (cx, cy - sh + 2)], fill=(*CANVAS, alpha))
            d.polygon([(cx, cy - sh), (cx - 3, cy - sh + 6), (cx + 3, cy - sh + 6)],
                      fill=(*CANVAS, alpha))
            # No wipe reach to draw: a rectangular bay does its own wiping on
            # the way up the stairs, so remove_drops_radius is a round-cup
            # setting and nothing here answers to it.
            r = hw
        else:
            # The dish, then how far the wipe reaches past its rim, then the
            # sweep filled in with the paint's colour.
            r = CLASSIC_DISH_RIM_RADIUS * scale
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*CANVAS, alpha), width=2)
            if drops_r:
                r = drops_r * scale
                d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*MUTED, alpha))
            r = max(enter_r * scale, 3)
            d.ellipse([cx - r, cy - r, cx + r, cy + r],
                      fill=(*fill, alpha), outline=(*CANVAS, alpha))
        off_bed = not (0 <= x <= max_w and 0 <= y <= max_h)
        tag = tray_labels.get(name, name) + (words["off_bed"] if off_bed else "")
        colour = ACCENT if off_bed else (TEXT if in_use else MUTED)
        # Under the cup: beside it would be on top of the next one along.
        below = hh if modern else max(CLASSIC_DISH_RIM_RADIUS, drops_r) * scale
        tw = d.textlength(tag, font=fs)
        d.text((cx - tw / 2, cy + below + 5), tag, font=fs, fill=colour)

    d.line([px(min_x, 0), px(max_x, 0)], fill=ACCENT, width=1)
    d.line([px(0, min_y), px(0, max_y)], fill=ACCENT, width=1)
    zx, zy = px(0, 0)
    d.ellipse([zx - 3, zy - 3, zx + 3, zy + 3], fill=ACCENT)
    d.text((zx + 6, zy + 4), "0,0", font=fs, fill=ACCENT)

    order = ", ".join(tray_labels.get(e["tray"], e["tray"]) for e in entries if e["color"]) \
        or words["order_none"]
    d.text((PAD, 12), words["order"].format(order=order), font=f, fill=TEXT)
    if offscreen:
        d.text((PAD, H - 24), words["offscreen"].format(trays=", ".join(offscreen)),
               font=fs, fill=ACCENT)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
