#!/usr/bin/python3
"""Colour photograph -> four thresholded CMYK plates.

A brush paints solid ink or nothing, so each process colour has to become a
two-tone plate before the rest of the pipeline sees it. The split is a real
CMYK conversion (the same paper profile `i2gc` uses), then a cutoff: a tint
below the cutoff is paper, anything at or above is that tray's ink. The colour
plates are then knocked out where the black plate paints, so no tray lays down
a coat that the key plate covers. The plates are what you would have uploaded
as already-thresholded pictures.

Dithering is not used. A Floyd–Steinberg plate is thousands of specks, and the
brush cannot lay those down; a hard cutoff is the same kind of image the
pipeline already traces.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageDraw, ImageOps

from configspec import CMYK_TO_TRAY
from images import flatten
from sketch import font_for

CHANNELS = ("C", "M", "Y", "K")

# What the sheet calls its pictures. The Kongress theme speaks German, and this
# sheet is printed by the server, so the words on it are chosen here rather than
# translated in the browser like the rest of the page.
CAPTIONS = {
    "default": {"overprint": "Overprint", "C": "Cyan", "M": "Magenta",
                "Y": "Yellow", "K": "Black"},
    "kongress": {"overprint": "Übereinanderdruck", "C": "Cyan", "M": "Magenta",
                 "Y": "Gelb", "K": "Schwarz"},
}

# Screen stand-ins for the four inks, matching the CSS pigment tokens, so a
# plate preview is the colour of the paint that will draw it.
PIGMENT = {
    "C": (0, 174, 239),
    "M": (236, 0, 140),
    "Y": (255, 212, 0),
    "K": (35, 35, 40),
}

_PROFILES = Path(__file__).resolve().parent.parent / "color_profiles"
_SRGB = _PROFILES / "sRGB_v4_ICC_preference.icc"
_CMYK = _PROFILES / "SC_paper_eci.icc"


def _cutoff_level(cutoff: float) -> int:
    """Channel value that just counts as ink.

    0% keeps any non-zero tint (the `i2gc` levels=1 behaviour). 100% keeps only
    a channel that is already solid.
    """
    return int(np.clip(round(float(cutoff) / 100.0 * 255.0), 1, 255))


def landscape(image: Image.Image) -> Image.Image:
    """The photograph upright as taken, then turned on its side if it is taller than wide.

    The painted width is fixed and the height follows the picture's ratio, so a
    portrait photograph would be painted narrow — or run past the machine's
    height limit. Lying it down fills the width instead. The camera's
    orientation tag is applied first, because the browser measuring the picture
    for the painted size applies it too, and the two must agree on which way is
    tall.
    """
    image = ImageOps.exif_transpose(image)
    if image.height > image.width:
        image = image.transpose(Image.Transpose.ROTATE_90)
    return image


def to_cmyk(image: Image.Image) -> Image.Image:
    """An 8-bit CMYK image: 0 is no ink, 255 is a solid plate."""
    if image.mode == "CMYK":
        return image
    rgb = flatten(image)
    if _SRGB.is_file() and _CMYK.is_file():
        intent = getattr(ImageCms, "Intent", None)
        rendering = intent.PERCEPTUAL if intent is not None else 0
        return ImageCms.profileToProfile(
            rgb, str(_SRGB), str(_CMYK), outputMode="CMYK",
            renderingIntent=rendering,
        )
    # Pillow's built-in conversion is a last resort: no paper profile, so the
    # black plate is a naive undercolour removal rather than a press GCR.
    return rgb.convert("CMYK")


def threshold_plates(image: Image.Image, cutoff: float = 40.0,
                     knockout: bool = True) -> dict[str, Image.Image]:
    """1-bit images keyed C/M/Y/K, black where that ink should paint, lying landscape.

    `knockout` drops the colour inks wherever the black plate already paints.
    The profile writes a press black: pure black comes out C 60% M 50% Y 54%
    K 95%, because on paper those tints sit under the key plate as a colour bed
    that keeps the black from looking brown. A press lays them as screens; here
    the cutoff turns every one of them into a solid brush pass, hidden under a
    solid black pass that follows. Knocking them out costs nothing visible —
    the black covers that ground either way — and on a photograph it more than
    halves the painting: yellow in particular is almost entirely the black
    plate's underlay. Switch it off to paint the colour bed anyway, which is
    the better black where the trays are out of register, since a black pass
    that lands a little off then shows colour at its edge rather than bare
    paper.
    """
    cmyk = to_cmyk(landscape(image))
    level = _cutoff_level(cutoff)
    ink = {name: np.asarray(channel) >= level
           for name, channel in zip(CHANNELS, cmyk.split())}
    if knockout:
        for name in ("C", "M", "Y"):
            ink[name] = ink[name] & ~ink["K"]
    return {name: Image.fromarray(
        np.where(mask, 0, 255).astype(np.uint8), "L").convert("1")
        for name, mask in ink.items()}


def ink_fraction(img: Image.Image) -> float:
    return float((np.asarray(img.convert("L")) < 128).mean())


def plates_for_trays(image: Image.Image, cutoff: float = 40.0,
                     knockout: bool = True) -> dict[str, Image.Image]:
    """Plates keyed by tray name (cyan, magenta, yellow, kroma)."""
    return {CMYK_TO_TRAY[ch]: plate
            for ch, plate in threshold_plates(image, cutoff, knockout).items()}


def _ink_mask(plate: Image.Image) -> np.ndarray:
    return np.asarray(plate.convert("L")) < 128


def composite(plates: dict[str, Image.Image], paper=(255, 255, 255)) -> Image.Image:
    """What the four binary plates look like printed on top of each other.

    Multiply-blend of the pigment colours: where two inks overlap they darken
    the way dyes do, which is close enough to judge registration and coverage.
    """
    first = next(iter(plates.values()))
    h, w = np.asarray(first.convert("L")).shape
    rgb = np.full((h, w, 3), np.array(paper, np.float32), np.float32)
    for ch in CHANNELS:
        plate = plates.get(ch) or plates.get(CMYK_TO_TRAY[ch])
        if plate is None:
            continue
        mask = _ink_mask(plate)
        if not mask.any():
            continue
        rgb[mask] *= np.array(PIGMENT[ch], np.float32) / 255.0
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


def _tint_plate(plate: Image.Image, pigment: tuple[int, int, int],
                paper: tuple[int, int, int]) -> Image.Image:
    grey = np.asarray(plate.convert("L"))
    ink = grey < 128
    out = np.empty(grey.shape + (3,), np.uint8)
    out[ink] = pigment
    out[~ink] = paper
    return Image.fromarray(out, "RGB")


def _caption(draw: ImageDraw.ImageDraw, xy, text: str, fill, font) -> None:
    draw.text(xy, text, fill=fill, font=font)


def contact_sheet(plates: dict[str, Image.Image], paper=(255, 255, 255),
                  ink=(34, 38, 37), width: int = 880,
                  theme: str = "default") -> Image.Image:
    """Composite on top, the four plates in a row underneath, labelled."""
    words = CAPTIONS.get(theme, CAPTIONS["default"])
    font = font_for(14, theme=theme)
    by_ch = {ch: plates[ch] if ch in plates else plates[CMYK_TO_TRAY[ch]]
             for ch in CHANNELS if ch in plates or CMYK_TO_TRAY[ch] in plates}
    proof = composite(by_ch, paper=paper)
    pw, ph = proof.size
    scale = min(1.0, width / max(pw, 1))
    if scale < 1.0:
        proof = proof.resize((max(1, int(pw * scale)), max(1, int(ph * scale))),
                             Image.Resampling.NEAREST)
        by_ch = {ch: p.resize(proof.size, Image.Resampling.NEAREST)
                 for ch, p in by_ch.items()}

    gap, label_h, pad = 10, 22, 14
    thumb_w = (proof.size[0] - 3 * gap) // 4
    thumb_h = max(1, int(proof.size[1] * thumb_w / max(proof.size[0], 1)))
    sheet_w = proof.size[0] + 2 * pad
    sheet_h = pad + proof.size[1] + label_h + gap + thumb_h + label_h + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), paper)
    draw = ImageDraw.Draw(sheet)
    x0, y0 = pad, pad
    sheet.paste(proof, (x0, y0))
    _caption(draw, (x0, y0 + proof.size[1] + 4), words["overprint"], ink, font)

    y_thumbs = y0 + proof.size[1] + label_h + gap
    for i, ch in enumerate(CHANNELS):
        if ch not in by_ch:
            continue
        thumb = _tint_plate(by_ch[ch], PIGMENT[ch], paper).resize(
            (thumb_w, thumb_h), Image.Resampling.NEAREST)
        x = x0 + i * (thumb_w + gap)
        sheet.paste(thumb, (x, y_thumbs))
        share = ink_fraction(by_ch[ch]) * 100
        _caption(draw, (x, y_thumbs + thumb_h + 4),
                 f"{words[ch]}  {share:.0f}%", PIGMENT[ch] if ch != "Y" else ink, font)
    return sheet
