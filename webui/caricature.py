#!/usr/bin/python3
"""Pick the trait a face has most of, and make far too much of it.

What a caricaturist on the Place du Tertre does is measure, by eye, how a face
differs from the faces they have drawn before, choose where it differs most and
push that further. This does the same with numbers. Each face is given 68
landmarks, and nine traits are measured off them: nose length and width, mouth
width, the fullness of the lips, the size of the eyes and how far apart they
sit, the length of the chin, the width of the jaw and the height of the brows.
Each is compared with what is typical for faces measured the same way, in units
of how much that trait varies between them, and the one furthest from typical
wins.

It is exaggerated with a warp of the picture, not by moving landmarks: a bloat
or a push centred on the feature that fades to nothing at the edge of its
reach, the way a liquify tool works. A face pulled about by its 68 points folds
over wherever two points close together are sent different ways; a warp with
one centre and a smooth falloff cannot.
"""
from __future__ import annotations

import threading

import cv2
import numpy as np
from PIL import Image

from images import flatten
from subject import _fetch

# The 68-point landmark model OpenCV's face module reads, trained on the 300-W
# faces.
LANDMARK_MODEL = {"file": "lbfmodel.yaml", "mb": 54,
                  "url": "https://raw.githubusercontent.com/kurnianggoro/GSOC2017/"
                         "master/data/lbfmodel.yaml"}

# What each trait typically measures, in eye-to-eye distances, and how much it
# varies (the spread of its logarithm, a robust standard deviation). Measured
# with this module on 260 faces in a collection of everyday photographs, mostly
# selfies and snapshots. One spread from typical is as unusual for a nose as for
# a jaw.
#
# Measured, because the landmark model's own mean face would not do. Against
# it, 84 of those faces had the longest nose and 83 the longest chin: the
# model's mean is a normalised training shape, and a selfie from arm's length
# draws the middle of the face long. A caricaturist judges a face against the
# faces they have seen, with the eye they see them with, and so does this. With
# these figures no trait is chosen for more than 35 of the 260.
REFERENCE = {
    "nose_length": (0.925, 0.152),
    "nose_width": (0.484, 0.109),
    "mouth_width": (0.934, 0.164),
    "lips": (0.244, 0.202),
    "eye_size": (0.192, 0.146),
    "eye_spacing": (0.438, 0.064),
    "chin": (0.679, 0.232),
    "jaw": (1.842, 0.076),
    "brows": (0.343, 0.243),
}

# How grotesque. A feature that is larger than the mean is drawn this much
# larger at its centre, one that is smaller this much smaller. A caricature at
# 1.3 reads as a slightly odd photograph; at 1.75 it reads as a drawing that
# knows what it is doing.
GROW = 2.3
SHRINK = 0.5

# A trait the face has less of counts for this much of its distance from
# typical. Shrinking a feature is the weaker joke: a mouth made smaller reads as
# a smaller mouth, one made larger as a caricature. At 0.6, 72% of the 260 faces
# have something made larger; counted in full, the four most common choices
# were all something made smaller.
LESS_COUNTS = 0.6

_FM = None
_TRIED = False
_LOCK = threading.Lock()


def _model(log=None):
    """The landmark model, or None without it."""
    global _FM, _TRIED
    with _LOCK:
        if _FM is not None or _TRIED:
            return _FM
        _TRIED = True
        path = _fetch(LANDMARK_MODEL, log)
        if path is None:
            if log:
                log("landmark model unavailable; the cartoon will not be a caricature")
            return None
        try:
            fm = cv2.face.createFacemarkLBF()
            fm.loadModel(str(path))
        except (cv2.error, AttributeError) as exc:
            if log:
                log(f"landmark model would not load ({exc})")
            return None
        _FM = fm
        if log:
            log(f"caricature using {LANDMARK_MODEL['file']}")
        return _FM


def warm(log=None) -> bool:
    return _model(log) is not None


def _landmarks(gray: np.ndarray, face) -> np.ndarray | None:
    """The 68 points of one face, in the picture's own coordinates.

    The model was trained on faces that are upright and finds a tilted one
    poorly: a head leaning a third of the way to the shoulder had its mouth
    found on its cheek. So when the detector has said where the eyes are, the
    picture is turned about the face until they are level, the points are found
    there, and turned back.
    """
    fm = _model()
    if fm is None:
        return None
    x, y, w, h = (float(v) for v in face[:4])
    turn = np.eye(2, 3)
    if len(face) >= 8:
        rx, ry, lx, ly = (float(v) for v in face[4:8])
        angle = float(np.degrees(np.arctan2(ly - ry, lx - rx)))
        turn = cv2.getRotationMatrix2D((x + w / 2, y + h / 2), angle, 1.0)
        gray = cv2.warpAffine(gray, turn, gray.shape[::-1], flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)
    with _LOCK:
        ok, found = fm.fit(gray, np.array([[x, y, w, h]], np.int32))
    if not ok or not len(found):
        return None
    pts = found[0].reshape(-1, 2).astype(np.float64)
    back = cv2.invertAffineTransform(turn)
    return pts @ back[:, :2].T + back[:, 2]


def _eye_centres(p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return p[36:42].mean(0), p[42:48].mean(0)


def _measures(p: np.ndarray) -> dict[str, float]:
    """The nine traits, as lengths in eye-to-eye distances.

    All of them are distances, so how the head is tilted in the picture does
    not enter into it; dividing by the distance between the eyes takes out how
    large the face is in the frame and, roughly, how far it is turned.
    """
    def d(a, b):
        return float(np.hypot(*(p[a] - p[b])))

    right, left = _eye_centres(p)
    iod = float(np.hypot(*(left - right))) or 1.0

    def area(idx):
        return abs(float(cv2.contourArea(p[idx].astype(np.float32))))

    eye = np.sqrt((area(list(range(36, 42))) + area(list(range(42, 48)))) / 2)
    brow = (d(19, 37) + d(20, 38) + d(23, 43) + d(24, 44)) / 4
    return {
        "nose_length": d(27, 33) / iod,
        "nose_width": d(31, 35) / iod,
        "mouth_width": d(48, 54) / iod,
        "lips": (d(51, 62) + d(66, 57)) / iod,
        "eye_size": eye / iod,
        "eye_spacing": iod / (d(0, 16) or 1.0),
        "chin": d(57, 8) / iod,
        "jaw": d(4, 12) / iod,
        "brows": brow / iod,
    }


def choose(points: np.ndarray) -> tuple[str, int, float]:
    """The trait furthest from typical: (name, +1 more or -1 less, spreads)."""
    face = _measures(points)
    best, sign, score, weighed = "nose_length", 1, 0.0, 0.0
    for name, (typical, spread) in REFERENCE.items():
        if face[name] <= 0:
            continue
        z = float(np.log(face[name] / typical)) / spread
        counts = abs(z) * (1.0 if z > 0 else LESS_COUNTS)
        if counts > weighed:
            best, sign, score, weighed = name, (1 if z > 0 else -1), z, counts
    return best, sign, score


# --- the warps -------------------------------------------------------------
# Each is written as where an output pixel takes its colour from, which is what
# cv2.remap wants, in the face's own frame: `across` runs from the right eye to
# the left and `down` at right angles to it, so a tilted head is warped along
# its own axes.

def _falloff(rho: np.ndarray) -> np.ndarray:
    """1 at the centre, 0 from the edge of the reach out, smooth throughout."""
    inside = np.clip(1.0 - rho * rho, 0.0, 1.0)
    return inside * inside


def _bloat(mx, my, centre, across, down, reach, scale):
    """Swell (or shrink) what is round `centre` by `scale` (across, down) at the
    middle, fading to nothing at `reach` (across, down).

    Does not fold for any scale above about 0.55: along each axis, where a pixel
    lands moves steadily outward as the pixel does.
    """
    qx = (mx - centre[0]) * across[0] + (my - centre[1]) * across[1]
    qy = (mx - centre[0]) * down[0] + (my - centre[1]) * down[1]
    w = _falloff(np.hypot(qx / reach[0], qy / reach[1]))
    sx = 1.0 + (scale[0] - 1.0) * w
    sy = 1.0 + (scale[1] - 1.0) * w
    qx, qy = qx / sx, qy / sy
    return (centre[0] + qx * across[0] + qy * down[0],
            centre[1] + qx * across[1] + qy * down[1])


def _push(mx, my, centre, across, down, reach, shift):
    """Move what is round `centre` by `shift` (across, down), dragging the
    surroundings less the further out they are. Kept under 0.6 of the reach,
    past which the falloff is too steep to follow and the picture folds.
    """
    qx = (mx - centre[0]) * across[0] + (my - centre[1]) * across[1]
    qy = (mx - centre[0]) * down[0] + (my - centre[1]) * down[1]
    w = _falloff(np.hypot(qx / reach[0], qy / reach[1]))
    dx = shift[0] * across[0] + shift[1] * down[0]
    dy = shift[0] * across[1] + shift[1] * down[1]
    return mx - dx * w, my - dy * w


def _stretch(mx, my, top, across, down, length, extra, width):
    """Lengthen what lies below the line through `top`: the band `length` deep
    under it is drawn `extra` longer, and below that the extra is given back
    over twice its own depth, so a chin grows away from a mouth that stays
    where it was and the neck takes up the difference. Fades to nothing
    `width` to either side.

    A push centred on the chin cannot do this. It drags everything near the
    chin with it, the mouth included, and a lower lip pulled down to meet a
    chin that has moved reads as a face melting rather than a long jaw.
    """
    give = 2.0 * extra
    # Where each source row lands, as a table; turned round for where each
    # output row comes from. The landing is steadily increasing, so the table
    # inverts exactly.
    src = np.linspace(-length, length + give + 4.0 * extra, 2048)
    grown = np.clip(src / length, 0.0, 1.0) * extra
    back = np.clip((src - length) / give, 0.0, 1.0)
    landed = src + grown - extra * back * back * (3.0 - 2.0 * back)
    qx = (mx - top[0]) * across[0] + (my - top[1]) * across[1]
    qy = (mx - top[0]) * down[0] + (my - top[1]) * down[1]
    origin = np.interp(qy, landed, src, left=None, right=None)
    origin = np.where(qy < landed[0], qy, origin)
    origin = np.where(qy > landed[-1], qy - (landed[-1] - src[-1]), origin)
    w = _falloff(np.abs(qx) / width)
    qy = qy + (origin - qy) * w
    return (top[0] + qx * across[0] + qy * down[0],
            top[1] + qx * across[1] + qy * down[1])


def _operations(p: np.ndarray, trait: str, sign: int) -> list:
    """The warps that exaggerate one trait of one face, in its own frame."""
    right, left = _eye_centres(p)
    iod = float(np.hypot(*(left - right))) or 1.0
    across = (left - right) / iod
    down = np.array([-across[1], across[0]])
    s = GROW if sign > 0 else SHRINK

    def part(k):
        """A share of the full scale, for the axis a feature is not known by."""
        return 1.0 + (s - 1.0) * k

    def bloat(centre, reach, scale):
        return (_bloat, centre, across, down, (reach[0] * iod, reach[1] * iod), scale)

    def push(centre, reach, shift):
        return (_push, centre, across, down, (reach[0] * iod, reach[1] * iod),
                (shift[0] * iod, shift[1] * iod))

    mouth = p[48:60].mean(0)
    if trait == "nose_width":
        return [bloat(p[30:36].mean(0), (0.95, 1.05), (s, part(0.45)))]
    if trait == "nose_length":
        return [bloat(p[[28, 29, 30, 33]].mean(0), (0.75, 1.25), (part(0.35), s))]
    if trait == "mouth_width":
        return [bloat(mouth, (1.2, 0.75), (s, part(0.2)))]
    if trait == "lips":
        return [bloat(mouth, (1.0, 0.7), (part(0.2), s))]
    if trait == "eye_size":
        # Eyes are close to each other and to the brows, so they are not swollen
        # quite as far as a nose: at the full figure the two met over the bridge.
        e = 1.0 + (s - 1.0) * 0.8
        return [bloat(c, (0.55, 0.5), (e, e)) for c in (right, left)]
    if trait == "eye_spacing":
        # Wide-set eyes go further apart, close-set ones closer, brows with them.
        out = 0.3 * sign
        return [push((right + p[17:22].mean(0)) / 2, (0.6, 0.65), (-out, 0.0)),
                push((left + p[22:27].mean(0)) / 2, (0.6, 0.65), (out, 0.0))]
    if trait == "chin":
        # From the corners of the mouth to the tip of the chin.
        top = (p[48] + p[54]) / 2
        depth = float(np.dot(p[8] - top, down)) or 0.5 * iod
        if sign > 0:
            return [(_stretch, top, across, down, depth, 0.75 * depth, 1.3 * iod)]
        return [push(p[8], (1.4, 1.3), (0.0, -0.35))]
    if trait == "jaw":
        return [bloat((p[4] + p[12] + p[8]) / 3, (1.6, 1.2), (part(0.7), 1.0))]
    # Brows: high ones are raised further, low ones brought down into a glower.
    lift = -0.4 if sign > 0 else 0.22
    return [push(p[17:22].mean(0), (0.7, 0.7), (0.0, lift)),
            push(p[22:27].mean(0), (0.7, 0.7), (0.0, lift))]


def caricature(image: Image.Image, faces, mask: np.ndarray | None = None,
               log=None) -> tuple[Image.Image, np.ndarray | None, list[tuple[str, int]]]:
    """The picture with each face's most unusual trait exaggerated.

    `faces` are boxes from `subject._faces(..., points=True)`; a box with its
    eye points is turned level before its landmarks are found. `mask`, the
    isolated subject, is warped the same way, so a nose grown past the edge of
    the face is still part of the subject. Returns the picture, the mask, and
    the trait chosen for each face that could be measured, as (name, +1 for
    more of it or -1 for less).
    """
    if _model(log) is None or not faces:
        return image, mask, []
    rgb = np.asarray(flatten(image))
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    mx, my = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    traits = []
    for face in faces:
        points = _landmarks(gray, face)
        if points is None:
            continue
        trait, sign, score = choose(points)
        traits.append((trait, sign))
        if log:
            log(f"caricature: {trait} {'more' if sign > 0 else 'less'}, "
                f"{abs(score):.1f} spreads from typical")
        # Composed in turn on where each output pixel comes from: the warps of
        # different faces, and of the two eyes of one, do not overlap.
        for op, *args in _operations(points, trait, sign):
            mx, my = op(mx, my, *args)
    if not traits:
        return image, mask, []
    mx, my = mx.astype(np.float32), my.astype(np.float32)
    out = cv2.remap(rgb, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if mask is not None:
        mask = cv2.remap(mask.astype(np.uint8), mx, my, cv2.INTER_NEAREST,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return Image.fromarray(out, "RGB"), mask, traits
