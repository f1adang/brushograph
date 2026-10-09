#!/usr/bin/python3
"""A coarse cartoon of a photograph of someone, before it is separated into plates.

The separation thresholds each ink, so a photograph's soft gradients come out as
ragged fields: a cheek that drifts across the cutoff is painted as a coastline of
islands, and each island is a brush-down. A cartoon is the opposite kind of
picture: a few flat colours, each one a field with a clean edge, and dark lines
where the features are. That is what a brush that paints solid ink or nothing
can lay down well, so this turns the photograph into one before the plates are
cut from it.

Everything is measured against the largest face, not the frame. A cartoon of a
person is a drawing of that face, and a selfie whose face fills a seventh of
the frame flattened at the frame's scale came out as two blobs with no eyes.

And like the portraitists on the Place du Tertre, it is a caricature: before
anything else, each face has the trait it has most of (or least) exaggerated,
grotesquely. That is `caricature.py`.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

import caricature
import facefilter
from images import flatten

# How many pixels across the largest face is when it is flattened, which is how
# much of it the cartoon can draw. At 80 the features were about eight pixels
# each: a cartoon, but a coarse one, the curls of a hairdo a single blob. At 140
# the folds round a mouth and the shape of a brow come through. At 200 the
# lines began to break into dashes along the hair.
FACE_PX = 140

# Never work on a picture smaller or larger than this along its long side. A face
# filling the whole frame would otherwise be cartooned at 80 px and the painting
# made of blocks; a face that is a speck in a crowd would ask for a picture
# larger than the photograph.
WORK_MIN, WORK_MAX = 256, 1024

# How many flat colours. Each one is a field after the cutoff, and every field
# is one more set of edges to paint round. Six keep hair, skin, its shadow,
# clothes and background apart and no more; eight give the face a second shadow
# and, with FACE_WEIGHT and the hairlines, the shapes of its light.
COLOURS = 8

# The edges between the cartoon's flat colours are drawn as hairlines when they
# run at least this far, as a fraction of the face (see `_cel_lines`). At 0.3
# every hairdo was a contour map; at 0.6 what is left is the edge of a shadow,
# the wing of a nose, the outline of an eye. Nought draws none.
CEL_MIN = 0.6

# How many times over a face's pixels count when the colours are chosen.
FACE_WEIGHT = 4

# How far apart two colours may be (in 8-bit Lab) and still be flattened into
# one by the mean shift. Wider, and lips go into the cheek.
COLOUR_RADIUS = 24

# A line is drawn where the picture is this much darker than its surroundings,
# as a ratio rather than a difference: a dim selfie and a studio portrait have
# the same eyes in them, and a fixed difference found them only in the bright
# one. Three hundredths finds the lines round a mouth and the curls of a hairdo;
# the coarse cartoon drew only the eyes, the nostrils and the mouth, at five.
LINE_DARKER = 0.03

# The line finder's scale, as a fraction of the face. Finer than it was (0.018
# of the 80 px face) now that the face is worked larger, so a line is a line
# and not a patch: the creases at the eyes, the parting of the lips.
LINE_SIGMA = 0.008

# A line shorter than this, as a fraction of the face's work size, is a speck of
# texture rather than a feature. Fifteen hundredths keeps a nostril and a dimple.
LINE_MIN = 0.15


def _work_scale(h: int, w: int, faces) -> tuple[float, float]:
    """The scale to work at, and how wide the largest face is in the source."""
    face = max((float(f[2]) for f in faces or []), default=0.0)
    if face <= 0:
        # No face to measure by: take a face to be what a head-and-shoulders
        # portrait gives it, a sixth of the diagonal.
        face = float(np.hypot(w, h)) / 6.0
    scale = FACE_PX / face
    long_side = max(h, w)
    scale = max(scale, WORK_MIN / long_side)
    scale = min(scale, WORK_MAX / long_side, 1.0)
    return scale, face


def _lines(small: np.ndarray, face_work: float) -> np.ndarray:
    """Dark lines in a picture, as a 0/1 map at its own size.

    A difference of Gaussians taken as a ratio: where the fine blur is darker
    than the wide blur by LINE_DARKER of it, there is a line. The eyes, the
    brows, the line of the lips and the nostrils are all narrow and darker than
    what surrounds them, which is what this finds; a broad shadow is not narrow,
    and is left to the colours.
    """
    grey = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32)
    # The floor stops a black that is black because the picture is black from
    # being read as infinitely darker than the near-black beside it.
    grey += 8.0
    sigma = max(1.0, face_work * LINE_SIGMA)
    near = cv2.GaussianBlur(grey, (0, 0), sigma)
    wide = cv2.GaussianBlur(grey, (0, 0), sigma * 2.5)
    line = (near < (1.0 - LINE_DARKER) * wide).astype(np.uint8)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(line, connectivity=8)
    keep = stats[:, cv2.CC_STAT_AREA] >= face_work * LINE_MIN
    keep[0] = False
    return keep[labels].astype(np.uint8)


def _cel_lines(label: np.ndarray, mask: np.ndarray | None, face: float) -> np.ndarray:
    """The edges between the cartoon's own flat colours, as hairlines.

    The colours a cartoon gives a face (its light, its shadow, the shadow
    under the nose) are often too close to separate into different inks: they
    are all magenta, or all paper, and the face paints as one flat field with
    dots for eyes. Drawn as a line, the edge of a shadow survives the cutoff,
    which is how a drawn cartoon shows where the light falls. Only inside the
    subject, and a run shorter than CEL_MIN of the face is dropped as a scrap.
    """
    edge = np.zeros(label.shape, bool)
    edge[:, 1:] |= label[:, 1:] != label[:, :-1]
    edge[1:, :] |= label[1:, :] != label[:-1, :]
    if mask is not None:
        edge &= cv2.erode(mask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    _, labels, stats, _ = cv2.connectedComponentsWithStats(edge.astype(np.uint8), connectivity=8)
    keep = stats[:, cv2.CC_STAT_AREA] >= face * CEL_MIN
    keep[0] = False
    return keep[labels]


def cartoonify(image: Image.Image, faces=None, mask: np.ndarray | None = None,
               brush_px: float = 0.0, log=None) -> tuple[Image.Image, list]:
    """The photograph as a coarse cartoon: flat colours and dark feature lines,
    and each face a caricature of itself.

    `faces` are face boxes in this picture's pixels, with the detector's eye
    points where it has them (`subject._faces(..., points=True)`); the largest
    sets the scale. `mask`, when the subject is isolated, takes the palette from
    the subject alone, leaves the rest bare paper and outlines the subject.
    `brush_px` is the stroke's width in this picture's pixels: no line is drawn
    thinner than half of it, which is the width a contour is drawn at, and for
    the same reason.

    Returns the cartoon and the trait exaggerated in each face, as
    `caricature.caricature` reports them.
    """
    # The caricature first, on the photograph: the warp moves shading and
    # edges together, and the flat colours and the lines are then found on the
    # face as it is to be drawn rather than bent after the fact.
    image, mask, traits = caricature.caricature(image, faces or [], mask, log)
    rgb = np.asarray(flatten(image))
    h, w = rgb.shape[:2]
    faces = [tuple(int(v) for v in f[:4]) for f in (faces or [])]
    scale, face = _work_scale(h, w, faces)
    face_work = face * scale

    # Even the light on the face first. A face lit from one side is two colours
    # to the k-means, a lit one and a shadowed one, and the cartoon draws a
    # line down the middle of it.
    if faces:
        rgb = np.asarray(flatten(facefilter.enhance(Image.fromarray(rgb), faces=faces)))

    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    small = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA) if scale < 1.0 else rgb.copy()
    inside = None
    if mask is not None:
        inside = cv2.resize(mask.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST) > 0

    # Flatten: the mean shift pulls each pixel to the colour of the region it
    # belongs to, so a cheek is one colour before anything is counted.
    spatial = max(4, round(face_work * 0.08))
    flat = cv2.pyrMeanShiftFiltering(cv2.cvtColor(small, cv2.COLOR_RGB2BGR),
                                     spatial, COLOUR_RADIUS, maxLevel=1)
    lab = cv2.cvtColor(flat, cv2.COLOR_BGR2LAB).astype(np.float32)

    # Choose the colours. With the subject isolated they are chosen from the
    # subject alone: the background is about to become paper, and every colour
    # it was given would be one the face did not get.
    sample = lab[inside] if inside is not None and inside.sum() > 256 else lab.reshape(-1, 3)
    # And the faces count several times over. A face is a small part of most
    # photographs, and counted once its skin got one colour while a jacket and
    # a hat took the rest: a flat mask with dots for eyes. Counted FACE_WEIGHT
    # times, the light and the shadow on it are colours of their own.
    for fx, fy, fw, fh in faces:
        x0, y0 = int(fx * scale), int(fy * scale)
        x1, y1 = int((fx + fw) * scale), int((fy + fh) * scale)
        skin = lab[max(0, y0):max(0, y1), max(0, x0):max(0, x1)].reshape(-1, 3)
        if len(skin):
            sample = np.concatenate([sample.reshape(-1, 3)] + [skin] * (FACE_WEIGHT - 1))
    k =int(min(COLOURS, max(1, len(np.unique(sample.astype(np.uint8), axis=0)))))
    # Seeded, so the same photograph makes the same cartoon and the same G-code.
    cv2.setRNGSeed(1)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, _, centres = cv2.kmeans(sample.reshape(-1, 3), k, None, criteria, 3,
                               cv2.KMEANS_PP_CENTERS)
    distance = ((lab[:, :, None, :] - centres[None, None]) ** 2).sum(-1)
    label = distance.argmin(-1).astype(np.uint8)
    # A median over the labels tidies the ragged edge between two fields; on a
    # boundary between two of them it is a majority vote.
    label = cv2.medianBlur(label, 5)
    palette = cv2.cvtColor(centres.astype(np.uint8)[None], cv2.COLOR_LAB2RGB)[0]

    lines = _lines(small, face_work)
    if inside is not None:
        lines[~inside] = 0
        # The subject's own outline. Cut out onto paper, a pale shoulder or a
        # white cap has no edge at all against the sheet it stands on.
        ring = max(1, round(face_work * 0.02))
        ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ring + 1, 2 * ring + 1))
        edge = inside.astype(np.uint8) - cv2.erode(inside.astype(np.uint8), ker)
        lines |= edge

    # Back up to the photograph's own size: the plates are cut there, and the
    # stroke is measured there. Labels go up by nearest neighbour and are then
    # smoothed, so a field's edge is a curve and not a staircase.
    if scale < 1.0:
        label = cv2.resize(label, (w, h), interpolation=cv2.INTER_NEAREST)
        label = cv2.medianBlur(label, _odd(min(1.0 / scale, 5)))
        lines = cv2.resize(lines.astype(np.float32), (w, h),
                           interpolation=cv2.INTER_LINEAR) > 0.5
    else:
        lines = lines > 0
    if CEL_MIN > 0:
        lines = lines | _cel_lines(label, mask, face)
    across = round(0.5 * brush_px)
    if across >= 2:
        lines = cv2.dilate(lines.astype(np.uint8),
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (across, across))) > 0

    out = palette[label]
    out[lines] = 0
    if mask is not None:
        out[(mask == 0) & ~lines] = 255
    if log:
        log(f"cartoon: {k} colours, face {face:.0f} px, worked at {size[0]}×{size[1]}")
    return Image.fromarray(out.astype(np.uint8), "RGB"), traits


def _odd(n: float) -> int:
    n = max(1, round(n))
    return n if n % 2 else n + 1
