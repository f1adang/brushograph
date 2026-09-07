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
# paint in the cups and are the same colour whatever the page is wearing.
PALETTES = {
    "default": dict(bg=(255, 255, 255), grid=(232, 234, 238), bed=(120, 128, 140),
                    canvas=(40, 44, 52), text=(60, 66, 76), muted=(150, 156, 166),
                    accent=(200, 90, 90)),
    "dark": dict(bg=(29, 33, 32), grid=(45, 51, 50), bed=(123, 133, 131),
                 canvas=(230, 233, 232), text=(211, 216, 214), muted=(134, 143, 141),
                 accent=(224, 138, 122)),
    "coconut": dict(bg=(253, 246, 232), grid=(234, 217, 189), bed=(185, 138, 82),
                    canvas=(55, 34, 15), text=(74, 44, 24), muted=(125, 92, 57),
                    accent=(156, 43, 22)),
    "pinkograph": dict(bg=(14, 20, 32), grid=(30, 42, 62), bed=(0, 229, 255),
                       canvas=(232, 244, 255), text=(200, 220, 240), muted=(125, 147, 176),
                       accent=(255, 30, 111)),
    "uwu": dict(bg=(43, 8, 36), grid=(69, 18, 58), bed=(255, 138, 212),
                       canvas=(255, 232, 246), text=(255, 212, 238), muted=(229, 140, 192),
                       accent=(255, 107, 107)),
}

TRAY_FILL = {
    "water": (150, 200, 235),
    "cyan": (0, 174, 239),
    "magenta": (236, 0, 140),
    "yellow": (255, 212, 0),
    "kroma": (35, 35, 40),
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
    pad_r = max(drops_r, enter_r)
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
    for name, x, y in all_trays:
        if not (min_x - pad_r <= x <= max_x + pad_r and min_y - pad_r <= y <= max_y + pad_r):
            offscreen.append(name)
            continue
        cx, cy = px(x, y)
        in_use = name in active
        fill = TRAY_FILL.get(name, (120, 120, 130))
        if name.startswith("#"):
            try:
                fill = tuple(int(name[i:i + 2], 16) for i in (1, 3, 5))
            except ValueError:
                pass
        alpha = 255 if in_use else 70
        if drops_r:
            r = drops_r * scale
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*MUTED, alpha))
        r = max(enter_r * scale, 3)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*fill, alpha), outline=(*CANVAS, alpha))
        off_bed = not (0 <= x <= max_w and 0 <= y <= max_h)
        tag = name + (" (off bed)" if off_bed else "")
        d.text((cx + r + 4, cy - 6), tag, font=fs, fill=ACCENT if off_bed else (TEXT if in_use else MUTED))

    d.line([px(min_x, 0), px(max_x, 0)], fill=ACCENT, width=1)
    d.line([px(0, min_y), px(0, max_y)], fill=ACCENT, width=1)
    zx, zy = px(0, 0)
    d.ellipse([zx - 3, zy - 3, zx + 3, zy + 3], fill=ACCENT)
    d.text((zx + 6, zy + 4), "0,0", font=fs, fill=ACCENT)

    order = ", ".join(e["tray"] for e in entries if e["color"]) or "none in color_order"
    d.text((PAD, 12), f"Painting order: {order}", font=f, fill=TEXT)
    if offscreen:
        d.text((PAD, H - 24), f"not shown, parked far outside the bed: {', '.join(offscreen)}",
               font=fs, fill=ACCENT)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
