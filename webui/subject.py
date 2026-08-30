#!/usr/bin/python3
"""Find the person or prominent object in a photo, and cut it from its background.

Everything here uses what OpenCV already ships: Haar cascades bundled with the
package and its saliency operators. Nothing is downloaded, so detection works
offline and adds no dependency.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

WORK = 640          # detection resolution; boxes are returned in source pixels
MIN_COVER = 0.015   # below this a "subject" is a speck, not the subject
MAX_COVER = 0.92    # above this it is the whole frame, so isolating gains nothing


def _cascade(name: str):
    path = cv2.data.haarcascades + name
    c = cv2.CascadeClassifier(path)
    return None if c.empty() else c


def _union(boxes) -> tuple[int, int, int, int]:
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return x0, y0, x1 - x0, y1 - y0


def _clip(box, w, h):
    x, y, bw, bh = box
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(w, int(x + bw)), min(h, int(y + bh))
    return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


def _body_from_face(face, w, h):
    """A face tells you where a person is; the body hangs below and around it."""
    x, y, fw, fh = face
    return _clip((x - fw * 1.0, y - fh * 0.7, fw * 3.0, fh * 7.5), w, h)


def detect(image: Image.Image) -> dict:
    """Report what is worth isolating, in source-image coordinates."""
    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, WORK / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) \
        if scale < 1.0 else rgb
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)
    sh, sw = gray.shape
    back = 1.0 / scale if scale < 1.0 else 1.0

    faces = []
    for name in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
        c = _cascade(name)
        if c is None:
            continue
        found = c.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6,
                                   minSize=(max(18, sw // 22), max(18, sh // 22)))
        faces.extend([tuple(int(v) for v in f) for f in found])
    faces = _dedupe(faces)

    if faces:
        bodies = [_body_from_face(f, sw, sh) for f in faces]
        box = _clip(_union(bodies), sw, sh)
        return _result("person", box, faces, sw, sh, back,
                       count=len(faces), how=f"{len(faces)} face(s)")

    for name, kind in (("haarcascade_upperbody.xml", "person"),
                       ("haarcascade_fullbody.xml", "person")):
        c = _cascade(name)
        if c is None:
            continue
        found = c.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4,
                                   minSize=(max(28, sw // 12), max(28, sh // 12)))
        if len(found):
            boxes = [tuple(int(v) for v in b) for b in found]
            return _result(kind, _clip(_union(boxes), sw, sh), boxes, sw, sh, back,
                           count=len(boxes), how=name.split("_")[1].replace(".xml", ""))

    box = _salient_box(small)
    if box is not None:
        return _result("object", box, [box], sw, sh, back, count=1, how="saliency")

    return {"found": False, "reason": "no person or prominent object stood out"}


def _dedupe(boxes, overlap: float = 0.35):
    """Drop boxes that mostly repeat one already kept (the cascades overlap)."""
    kept: list[tuple] = []
    for b in sorted(boxes, key=lambda b: -b[2] * b[3]):
        bx, by, bw, bh = b
        if any(_iou(b, k) > overlap for k in kept):
            continue
        kept.append((bx, by, bw, bh))
    return kept


def _iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = a[0], a[1], a[0] + a[2], a[1] + a[3]
    bx0, by0, bx1, by1 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    ix = max(0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union else 0.0


def _salient_box(small_rgb):
    """Largest region the saliency operator considers to stand out."""
    try:
        sal = cv2.saliency.StaticSaliencyFineGrained_create()
        ok, smap = sal.computeSaliency(small_rgb)
    except (cv2.error, AttributeError):
        return None
    if not ok:
        return None
    smap = (smap * 255).astype(np.uint8)
    smap = cv2.GaussianBlur(smap, (0, 0), 5)
    _, mask = cv2.threshold(smap, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n < 2:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    total = mask.shape[0] * mask.shape[1]
    if not (MIN_COVER < stats[i, cv2.CC_STAT_AREA] / total < MAX_COVER):
        return None
    return (int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP]),
            int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT]))


def _result(kind, box, parts, sw, sh, back, count, how) -> dict:
    cover = (box[2] * box[3]) / float(sw * sh)
    if not (MIN_COVER < cover < MAX_COVER):
        return {"found": False, "reason": f"the {kind} found covers {cover * 100:.0f}% of the frame"}
    return {
        "found": True,
        "kind": kind,
        "how": how,
        "count": count,
        "coverage": round(cover, 3),
        "box": [int(v * back) for v in box],
        "parts": [[int(v * back) for v in p] for p in parts],
    }


def isolate(image: Image.Image, box, iterations: int = 4) -> np.ndarray:
    """GrabCut the subject out of its background; returns a full-size 0/1 mask.

    The detected box seeds it as probable foreground. GrabCut then decides the
    actual outline from colour statistics, which matters here because a
    rectangle of background would otherwise be hatched along with the subject.
    """
    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, WORK / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) \
        if scale < 1.0 else rgb
    sh, sw = small.shape[:2]
    x, y, bw, bh = _clip([int(v * scale) for v in box], sw, sh)
    # GrabCut needs room around the seed to learn what the background looks like.
    if bw >= sw - 2 or bh >= sh - 2:
        pad = max(2, int(min(sw, sh) * 0.02))
        x, y, bw, bh = _clip((x + pad, y + pad, bw - 2 * pad, bh - 2 * pad), sw, sh)

    mask = np.zeros((sh, sw), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), mask, (x, y, bw, bh),
                    bgd, fgd, iterations, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        mask = np.zeros((sh, sw), np.uint8)
        mask[y:y + bh, x:x + bw] = cv2.GC_FGD

    out = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    if out.sum() < 0.01 * sh * sw:      # GrabCut gave up: fall back to the box
        out[:] = 0
        out[y:y + bh, x:x + bw] = 1
    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE,
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    return cv2.resize(out, (w, h), interpolation=cv2.INTER_NEAREST)
