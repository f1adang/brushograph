#!/usr/bin/python3
"""Renders the machine sketch: bed limits, canvas, and tray positions to scale."""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from configspec import tray_entries

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
}

# How many steps to draw across a modern cup. The holder's own floor is not in
# its STL, so this is a drawing convention rather than a measurement.
MODERN_STEPS = 4

# The K tray is keyed "kroma" throughout this project. The holder has W C M Y K
# stamped on it and nothing says kroma, so the drawing calls it black.
TRAY_LABEL = {"kroma": "black"}

TRAY_FILL = {
    "water": (150, 200, 235),
    "cyan": (0, 174, 239),
    "magenta": (236, 0, 140),
    "yellow": (255, 212, 0),
    # kroma is not here: black is whatever the palette's `key` says, because on
    # the dark grounds a black cup drawn black is an empty patch of background.
}


def _font(size=12):
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

    max_w = _num(bg, "max_width", _num(bg, "width", 200))
    max_h = _num(bg, "max_height", _num(bg, "height", 200))
    cw, ch = _num(bg, "width", 0), _num(bg, "height", 0)
    ox, oy = _num(bg, "offset_x", 0), _num(bg, "offset_y", 0)
    enter_r = _num(bg, "tray_enter_radius", _num(bg, "dip_entry_radius", 5))
    modern = str(bg.get("cup_shape", "classic")).strip().lower() == "modern"
    cup_w = _num(bg, "cup_width", 29.2)
    cup_w_water = _num(bg, "cup_width_water", 39.2)
    cup_h = _num(bg, "cup_depth", 30.0)

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
    pad_r = max(cup_w_water / 2, cup_w / 2, cup_h / 2, drops_r) if modern else max(drops_r, enter_r)
    xs = [0.0, max_w, ox, ox + cw] + [x + pad_r for _, x, _ in framed] + [x - pad_r for _, x, _ in framed]
    ys = [0.0, max_h, oy, oy + ch] + [y + pad_r for _, _, y in framed] + [y - pad_r for _, _, y in framed]
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
    f, fs = _font(12), _font(10)

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

    # Bed limits
    d.rectangle([px(0, max_h), px(max_w, 0)], outline=BED, width=2)
    # Right-aligned: the bed and the image often share a top-left corner.
    bx, by = px(max_w, max_h)
    txt = f"bed {max_w:g} × {max_h:g} mm"
    d.text((bx - d.textlength(txt, font=fs) - 5, by + 4), txt, font=fs, fill=MUTED)

    # Canvas / image area
    if cw and ch:
        d.rectangle([px(ox, oy + ch), px(ox + cw, oy)], fill=(*CANVAS, 18), outline=CANVAS, width=2)
        tx, ty = px(ox, oy + ch)
        d.text((tx + 5, ty + 4), f"image {cw:g} × {ch:g} mm @ ({ox:g}, {oy:g})", font=fs, fill=TEXT)

    offscreen = []
    wipe_marks = []
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
            # A rectangular bay, with the steps its floor climbs drawn across
            # it: the brush swipes from the near end to the far one, rising as
            # it goes, so the steps are the thing worth seeing. The water bay is
            # the wide one — the holder gives it 39.2 mm against the colours'
            # 29.2 — and drawing them all alike hid which cup that was.
            hw, hh = max(bay_w(name) * scale / 2, 3), max(cup_h * scale / 2, 3)
            d.rectangle([cx - hw, cy - hh, cx + hw, cy + hh],
                        fill=(*fill, alpha), outline=(*CANVAS, alpha), width=1)
            for i in range(1, MODERN_STEPS):
                sy = cy - hh + 2 * hh * i / MODERN_STEPS
                d.line([(cx - hw, sy), (cx + hw, sy)], fill=(*CANVAS, alpha))
            # The swipe runs from the deep end to the shallow one.
            d.line([(cx, cy + hh - 2), (cx, cy - hh + 2)], fill=(*CANVAS, alpha))
            d.polygon([(cx, cy - hh + 1), (cx - 3, cy - hh + 7), (cx + 3, cy - hh + 7)],
                      fill=(*CANVAS, alpha))
            # How far the wipe carries. The round cups get this as a circle;
            # here it matters more, because the holder puts the bays on 34 mm
            # centres and a reach over half of that flicks the drop into the
            # bay next door. Kept for a second pass: drawn here, the next bay
            # along would paint over the very overlap worth seeing.
            if drops_r:
                wipe_marks.append((cx, cy - hh - 5, drops_r * scale, alpha))
            r = hw
        else:
            if drops_r:
                r = drops_r * scale
                d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*MUTED, alpha))
            r = max(enter_r * scale, 3)
            d.ellipse([cx - r, cy - r, cx + r, cy + r],
                      fill=(*fill, alpha), outline=(*CANVAS, alpha))
        off_bed = not (0 <= x <= max_w and 0 <= y <= max_h)
        tag = TRAY_LABEL.get(name, name) + (" (off bed)" if off_bed else "")
        colour = ACCENT if off_bed else (TEXT if in_use else MUTED)
        if modern:
            # Under the bay: beside it would be on top of the next one along.
            tw = d.textlength(tag, font=fs)
            d.text((cx - tw / 2, cy + hh + 5), tag, font=fs, fill=colour)
        else:
            d.text((cx + r + 4, cy - 6), tag, font=fs, fill=colour)

    for cx, wy, wr, alpha in wipe_marks:
        d.line([(cx - wr, wy), (cx + wr, wy)], fill=(*MUTED, alpha))
        for end in (cx - wr, cx + wr):
            d.line([(end, wy - 3), (end, wy + 3)], fill=(*MUTED, alpha))

    d.line([px(min_x, 0), px(max_x, 0)], fill=ACCENT, width=1)
    d.line([px(0, min_y), px(0, max_y)], fill=ACCENT, width=1)
    zx, zy = px(0, 0)
    d.ellipse([zx - 3, zy - 3, zx + 3, zy + 3], fill=ACCENT)
    d.text((zx + 6, zy + 4), "0,0", font=fs, fill=ACCENT)

    order = ", ".join(TRAY_LABEL.get(e["tray"], e["tray"]) for e in entries if e["color"]) \
        or "none in color_order"
    d.text((PAD, 12), f"Painting order: {order}", font=f, fill=TEXT)
    if offscreen:
        d.text((PAD, H - 24), f"not shown, parked far outside the bed: {', '.join(offscreen)}",
               font=fs, fill=ACCENT)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
