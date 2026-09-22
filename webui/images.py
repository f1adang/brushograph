#!/usr/bin/python3
"""Getting an uploaded picture into the form the rest of the code expects."""
from __future__ import annotations

from PIL import Image, ImageOps

# Transparent means bare paper, so it composites onto white. Dropping the alpha
# channel instead leaves whatever happens to be stored under it, which in a PNG
# is very often black: one logo arrived with a transparent background whose
# hidden pixels were (0.8, 0.8, 0.8), so the whole picture came through nearly
# black, the lettering stopped being darker than what surrounded it, and the
# counters in its O and R vanished into the letters they belong to.
_PAPER = (255, 255, 255)

# How large an upload is worked on. Nothing downstream uses more: the woodcut
# never works finer than 2400 px on the long side (woodcut.MAX_WORK_SIDE), and
# the stroke geometry stops enlarging at 4000 (gcode_pipeline.MAX_WORK_PX). A
# phone photograph is 8000 px or more, and every step before the woodcut
# resizes it — subject detection, the face filter, the CMYK separation, and the
# distance transform over each of the four plates — ran at that size.
PHOTO_MAX_SIDE = 2400
DRAWING_MAX_SIDE = 4000


def prepare(image: Image.Image, max_side: int, log=None, name: str = "") -> Image.Image:
    """An upload upright, flattened, and no larger than max_side on its long side.

    Upright first, from the camera's orientation tag, and only then shrunk: the
    browser measures the picture the right way up to work out the painted
    height, so the picture painted has to be that way up too, and a tag read
    after a resize could be applied to the wrong axes. The shrink keeps the
    original's proportions to the pixel, so where the picture lands and which
    way it lies are the original's; only the detail it is worked from changes.
    """
    image = flatten(ImageOps.exif_transpose(image))
    w, h = image.size
    scale = max_side / max(w, h)
    if scale >= 1.0:
        return image
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    if log:
        log(f"{name or 'picture'}: {w}×{h} px, working at {size[0]}×{size[1]}")
    return image.resize(size, Image.Resampling.LANCZOS, reducing_gap=3.0)


def lay_along(image: Image.Image, canvas_w: float, canvas_h: float) -> Image.Image:
    """A photograph turned a quarter turn when its long side would then lie along the canvas's.

    The pixel grid is mapped onto the painted width by height whatever their
    proportions, so a portrait photograph painted into a landscape canvas is
    not merely small, it is stretched. Turning it is the difference between a
    picture that fills the paper and one squeezed into a column of it: on a
    151 x 124 mm bed a 3:4 photograph paints 93 x 124 upright and 151 x 113 on
    its side, which is half as much paper again.

    The canvas, not the bed, because the canvas is what the picture is mapped
    onto and both ends of this can see it: the browser sizes the canvas from
    the picture it has measured, and the server reads the same two figures off
    the form. A rule either of them worked out alone would be a rule they could
    disagree about, and a disagreement here is a painting stretched by exactly
    the amount of the turn.

    Only photographs. An already thresholded picture is somebody's own artwork,
    laid out the way they meant it; it is passed through upright.
    """
    if canvas_w <= 0 or canvas_h <= 0:
        return image
    if (image.width >= image.height) != (canvas_w >= canvas_h):
        return image.transpose(Image.Transpose.ROTATE_90)
    return image


def flatten(image: Image.Image) -> Image.Image:
    """An RGB copy, with any transparency laid over white."""
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        paper = Image.new("RGBA", rgba.size, (*_PAPER, 255))
        return Image.alpha_composite(paper, rgba).convert("RGB")
    return image.convert("RGB")
