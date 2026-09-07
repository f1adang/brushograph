#!/usr/bin/python3
"""Getting an uploaded picture into the form the rest of the code expects."""
from __future__ import annotations

from PIL import Image

# Transparent means bare paper, so it composites onto white. Dropping the alpha
# channel instead leaves whatever happens to be stored under it, which in a PNG
# is very often black: one logo arrived with a transparent background whose
# hidden pixels were (0.8, 0.8, 0.8), so the whole picture came through nearly
# black, the lettering stopped being darker than what surrounded it, and the
# counters in its O and R vanished into the letters they belong to.
_PAPER = (255, 255, 255)


def flatten(image: Image.Image) -> Image.Image:
    """An RGB copy, with any transparency laid over white."""
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        paper = Image.new("RGBA", rgba.size, (*_PAPER, 255))
        return Image.alpha_composite(paper, rgba).convert("RGB")
    return image.convert("RGB")
