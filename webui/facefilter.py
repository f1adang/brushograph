#!/usr/bin/python3
"""Flatter light and smoother skin on a face, before the woodcut is cut.

A woodcut has two tones. Everything the photograph does with grey — the soft
falloff down one cheek, the shadow under a brow, the texture of skin — has to
land on one side of a threshold or the other, and a face lit from one side
lands mostly on the black side: half the face fills in as one solid shape and
the likeness goes with it.

So this evens the light out and smooths the skin before any of that happens,
the way a phone's portrait filter does, while keeping the features that carry
the likeness — eyes, brows, nostrils, the line of the lips — exactly as dark
and as sharp as they were.

Only the face is touched. Everything else in the frame is left alone, and the
edge of the treated area is feathered wide enough that there is no seam.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from images import flatten

# The ellipse drawn over a face box, as multiples of that box. The detector's
# box runs roughly forehead to chin, so this only has to reach out to the sides
# of the jaw and a little down the neck, which catches the same light.
_FACE_WIDEN = 1.45
_FACE_HEIGHTEN = 1.35
_FACE_DROP = 0.10       # centre moved down the box, towards the jaw

# How far a tone may be pushed. Beyond this the face reads as a cut-out.
_MAX_LIFT = 0.55

# How far the light-evening may push any one pixel. Dividing out the lighting
# is a ratio, so an area that is dark because it *is* dark — hair, a collar,
# the background behind the head — would be hauled up towards mid grey and
# leave a bright halo round the face. Clamping the ratio stops that.
_GAIN_LIMIT = (0.75, 1.45)

# The scale the lighting is estimated at, as a fraction of the face. This is the
# setting that decides how much shadow comes off. Too wide and the estimate
# flattens out the very gradient it is meant to find — at 0.35 only a third of
# the imbalance came off a strongly side-lit portrait; at 0.12, seven eighths of
# it does. Too narrow and it starts following the eye sockets rather than the
# light, and the face goes plastic.
_SIGMA_FRAC = 0.12


def _face_mask(shape: tuple[int, int], faces, feather: float) -> np.ndarray:
    """A soft ellipse over every face, 0.0 outside and 1.0 well inside."""
    mask = np.zeros(shape, np.float32)
    for x, y, fw, fh in faces:
        centre = (int(x + fw / 2), int(y + fh * (0.5 + _FACE_DROP)))
        axes = (int(fw * _FACE_WIDEN / 2), int(fh * _FACE_HEIGHTEN / 2))
        cv2.ellipse(mask, centre, axes, 0, 0, 360, 1.0, -1)
    if feather > 0:
        k = int(feather) | 1
        mask = cv2.GaussianBlur(mask, (k, k), 0)
    return np.clip(mask, 0.0, 1.0)


def _skin_weight(lab: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """How much each pixel looks like the skin in the faces found.

    The colour of skin is the one thing that separates a cheek from the hair
    above it and the collar below, and it is read off this face rather than
    assumed: a face is whatever colour it is under whatever light it is in.
    """
    core = mask > 0.6
    if core.sum() < 32:
        core = mask > 0.2
    if core.sum() < 32:
        return mask
    a = lab[:, :, 1].astype(np.float32)
    b = lab[:, :, 2].astype(np.float32)
    a0, b0 = float(np.median(a[core])), float(np.median(b[core]))
    # A robust spread, floored so a very even face does not produce a weight so
    # tight that the jaw falls outside its own skin tone.
    spread = max(6.0, 1.4826 * float(np.median(np.abs(a[core] - a0) + np.abs(b[core] - b0))))
    d2 = (a - a0) ** 2 + (b - b0) ** 2
    return np.exp(-d2 / (2.0 * spread * spread)).astype(np.float32)


def enhance(image: Image.Image, faces=None, strength: float = 1.0, log=None) -> Image.Image:
    """Even the light and smooth the skin on every face found in the picture.

    Returns the picture unchanged when there is no face to work on, so it is
    safe to call on anything.
    """
    strength = float(np.clip(strength, 0.0, 1.0))
    if strength <= 0:
        return image

    if faces is None:
        import subject
        faces = subject._faces(image)
    faces = [tuple(int(v) for v in f) for f in (faces or [])]
    if not faces:
        if log:
            log("face filter: no face found, picture left alone")
        return image

    rgb = np.asarray(flatten(image))
    h, w = rgb.shape[:2]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    L = lab[:, :, 0].astype(np.float32)

    span = max(max(fw, fh) for _, _, fw, fh in faces)
    mask = _face_mask((h, w), faces, feather=max(3, span * 0.25))
    if mask.max() <= 0:
        return image

    # Only the skin, so hair, glasses, a collar and the background behind the
    # head keep the tone they had — and, just as important, none of them get a
    # vote on how the face is lit.
    skin = _skin_weight(lab, mask) * mask
    skin = cv2.GaussianBlur(skin, (0, 0), max(2.0, span * 0.03))
    if skin.max() <= 1e-3:
        return image

    # --- 1. even the light out -------------------------------------------
    # The shadow across a face is low-frequency: it varies over the width of
    # the face, not over the width of an eyelid. Blurring at that scale
    # estimates the lighting alone, and dividing it out leaves the face's own
    # tones lit flat. Working on a ratio rather than a difference keeps the
    # dark features dark: an eye that was a third of the brightness of the
    # cheek beside it is still a third of it afterwards.
    # Estimated over the skin alone, by blurring the skin and its weight
    # together and dividing. Blurring the picture flat instead let the dark hair
    # above and the collar below drag the estimate down, and the face was then
    # lifted past level — the shadowed side came out brighter than the lit one.
    sigma = max(4.0, span * _SIGMA_FRAC)
    lit = cv2.GaussianBlur(L * skin, (0, 0), sigma)
    cover = cv2.GaussianBlur(skin, (0, 0), sigma)
    illum = lit / np.maximum(cover, 1e-4)
    level = float(np.average(illum, weights=skin))
    gain = np.clip(level / np.maximum(illum, 1.0), *_GAIN_LIMIT)
    L_even = np.clip(L * gain, 0, 255)

    # --- 2. smooth the skin, keep the features ---------------------------
    # A bilateral filter already respects strong edges, which is what the
    # features are; what it removes is pore-scale texture and the mottling
    # that would otherwise become speckle in the cut.
    smooth = cv2.bilateralFilter(L_even.astype(np.uint8), d=0,
                                 sigmaColor=28.0, sigmaSpace=max(3.0, span * 0.045))
    smooth = smooth.astype(np.float32)
    # Whatever the smoothing removed that was *strong* was a feature, not skin,
    # so it goes back. The weight rises with the size of the detail, so an
    # eyelash returns in full and a pore does not return at all.
    detail = L_even - smooth
    keep = np.clip((np.abs(detail) - 4.0) / 14.0, 0.0, 1.0)
    L_skin = smooth + detail * keep

    # --- 3. lift the midtones --------------------------------------------
    # Skin sitting just under the threshold is what fills a cheek in solid.
    # A gamma below 1 lifts the midtones without touching either end, so the
    # cheek moves to the paper side while the pupils and nostrils stay put.
    lifted = 255.0 * np.power(np.clip(L_skin / 255.0, 0.0, 1.0), 0.78)
    L_out = L_skin + (lifted - L_skin) * _MAX_LIFT

    # --- 4. blend back ----------------------------------------------------
    weight = skin * strength
    L_final = L * (1.0 - weight) + L_out * weight
    lab[:, :, 0] = np.clip(L_final, 0, 255).astype(np.uint8)
    out = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    if log:
        moved = float(np.average(np.abs(L_final - L), weights=skin))
        log(f"face filter: {len(faces)} face(s), tone moved {moved:.1f} levels on average")
    return Image.fromarray(out)
