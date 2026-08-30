#!/usr/bin/python3
"""Find the person or prominent object in a photo, and cut it from its background.

Everything here uses what OpenCV already ships: Haar cascades bundled with the
package and its saliency operators. Nothing is downloaded, so detection works
offline and adds no dependency.
"""
from __future__ import annotations

import hashlib
import threading
import urllib.error
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# A small salient-object segmentation network, run through OpenCV's own ONNX
# support so it costs no new Python dependency. Colour-based segmentation cannot
# separate dark hair from dark foliage however it is seeded; this can.
MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "u2netp.onnx"
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
MODEL_BYTES = 4_574_861
MODEL_SIDE = 320

_NET = None
_NET_TRIED = False
_LOCK = threading.Lock()
_CACHE: dict[str, np.ndarray] = {}
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)

WORK = 640          # detection resolution; boxes are returned in source pixels
MIN_COVER = 0.015   # below this a "subject" is a speck, not the subject
MAX_COVER = 0.92    # above this it is the whole frame, so isolating gains nothing


def _fetch_model(log=None) -> bool:
    """Download the segmentation network once, into webui/models/."""
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_000_000:
        return True
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MODEL_PATH.with_suffix(".part")
    try:
        if log:
            log(f"fetching segmentation model ({MODEL_BYTES // 1024 // 1024} MB) from {MODEL_URL}")
        with urllib.request.urlopen(MODEL_URL, timeout=60) as r, tmp.open("wb") as f:
            f.write(r.read())
        if tmp.stat().st_size < 1_000_000:
            raise OSError(f"download was only {tmp.stat().st_size} bytes")
        tmp.replace(MODEL_PATH)
        return True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        if log:
            log(f"segmentation model unavailable ({exc}); falling back to GrabCut")
        tmp.unlink(missing_ok=True)
        return False


def _net(log=None):
    """The loaded network, or None if it could not be had."""
    global _NET, _NET_TRIED
    with _LOCK:
        if _NET is not None or _NET_TRIED:
            return _NET
        _NET_TRIED = True
        if not _fetch_model(log):
            return None
        try:
            _NET = cv2.dnn.readNetFromONNX(str(MODEL_PATH))
        except cv2.error as exc:
            if log:
                log(f"segmentation model would not load ({exc}); falling back to GrabCut")
            _NET = None
        return _NET


def warm(log=None) -> bool:
    """Load the network up front so the first upload is not the one that waits."""
    return _net(log) is not None


def segment(image: Image.Image, log=None) -> np.ndarray | None:
    """Probability that each pixel belongs to the subject, or None without a model.

    Results are cached by image content: detection and isolation both want this
    and there is no sense running the network twice for one upload.
    """
    rgb = np.asarray(image.convert("RGB"))
    key = hashlib.blake2b(rgb.tobytes(), digest_size=16).hexdigest()
    if key in _CACHE:
        return _CACHE[key]
    net = _net(log)
    if net is None:
        return None
    small = cv2.resize(rgb, (MODEL_SIDE, MODEL_SIDE), interpolation=cv2.INTER_AREA)
    blob = ((small.astype(np.float32) / 255.0 - _MEAN) / _STD).transpose(2, 0, 1)[None]
    with _LOCK:
        net.setInput(blob)
        out = net.forward(net.getUnconnectedOutLayersNames())[0][0, 0]
    span = float(out.max() - out.min())
    out = (out - out.min()) / (span if span > 1e-8 else 1.0)
    prob = cv2.resize(out, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
    if len(_CACHE) > 4:
        _CACHE.clear()
    _CACHE[key] = prob
    return prob


def _mask_from_prob(prob: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    mask = (prob > threshold).astype(np.uint8)
    k = max(3, _odd(int(min(mask.shape) * 0.006)))
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, ker)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, ker)
    # Keep every piece worth painting, so a second person is not discarded, but
    # drop the scraps the threshold leaves behind.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n < 2:
        return mask
    biggest = int(stats[1:, cv2.CC_STAT_AREA].max())
    keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= max(biggest * 0.06, 64)]
    return np.isin(labels, keep).astype(np.uint8) if keep else mask


def _faces(image: Image.Image) -> list:
    """Face boxes in source coordinates; used only to name what was found."""
    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, WORK / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) \
        if scale < 1.0 else rgb
    gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY))
    sh, sw = gray.shape
    found = []
    for name in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
        c = _cascade(name)
        if c is None:
            continue
        for f in c.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6,
                                    minSize=(max(18, sw // 22), max(18, sh // 22))):
            found.append(tuple(int(v) for v in f))
    back = 1.0 / scale if scale < 1.0 else 1.0
    return [[int(v * back) for v in f] for f in _dedupe(found)]


def _odd(n: int) -> int:
    n = max(1, int(n))
    return n if n % 2 else n + 1


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
    """A face tells you where a person is; the body hangs below and around it.

    If the estimate runs close to the bottom of the frame the subject is almost
    certainly cropped by it — people are photographed standing far more often
    than they are photographed floating — so the box is taken all the way down
    rather than slicing their feet off.
    """
    x, y, fw, fh = face
    box = _clip((x - fw * 1.2, y - fh * 0.9, fw * 3.4, fh * 8.0), w, h)
    bx, by, bw, bh = box
    if by + bh > h * 0.82:
        bh = h - by
    return _clip((bx, by, bw, bh), w, h)


def detect(image: Image.Image, log=None) -> dict:
    """Report what is worth isolating, in source-image coordinates."""
    prob = segment(image, log)
    if prob is not None:
        mask = _mask_from_prob(prob)
        cover = float(mask.mean())
        if not (MIN_COVER < cover < MAX_COVER):
            return {"found": False,
                    "reason": f"the subject found covers {cover * 100:.0f}% of the frame"}
        ys, xs = np.nonzero(mask)
        box = [int(xs.min()), int(ys.min()),
               int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]
        faces = _faces(image)
        return {
            "found": True,
            "kind": "person" if faces else "object",
            "how": "segmentation" + (f" and {len(faces)} face(s)" if faces else ""),
            "count": len(faces) or 1,
            "coverage": round(cover, 3),
            "box": box,
            "parts": [box],
            "faces": faces,
        }

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
                       count=len(faces), how=f"{len(faces)} face(s)", seeds=faces)

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


def _result(kind, box, parts, sw, sh, back, count, how, seeds=None) -> dict:
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
        "faces": [[int(v * back) for v in f] for f in (seeds or [])],
    }


def isolate(image: Image.Image, box, faces=None, iterations: int = 6, log=None) -> np.ndarray:
    """Cut the subject from its background; returns a full-size 0/1 mask.

    The segmentation network does this when it is available. What follows is the
    fallback for when it is not: GrabCut seeded with a trimap rather than a bare
    rectangle. Handed only a
    rectangle it has to guess which parts of the box are subject, and it
    reliably loses dark hair against dark foliage. Marking the head and a core
    down the body as definite foreground, and a frame of definite background,
    tells it the two things it cannot work out on its own.
    """
    prob = segment(image, log)
    if prob is not None:
        return _fill_holes(_mask_from_prob(prob))

    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, WORK / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) \
        if scale < 1.0 else rgb
    sh, sw = small.shape[:2]
    x, y, bw, bh = _clip([int(v * scale) for v in box], sw, sh)

    # Outside the detected box is *certain* background, exactly as seeding with
    # a plain rectangle would have it. Leaving it merely probable lets GrabCut
    # annex whatever outside the box happens to share the subject's colours —
    # a wall, a diving board, the sky.
    mask = np.full((sh, sw), cv2.GC_BGD, np.uint8)
    mask[y:y + bh, x:x + bw] = cv2.GC_PR_FGD

    seeds = [[int(v * scale) for v in f] for f in (faces or [])]
    single = len(seeds) == 1
    for fx, fy, fw_, fh_ in seeds:
        # The face plus the hair just above it: the part that kept being lost to
        # a dark background. Kept narrow — a seed wide enough to overlap the
        # foliage beside someone's head marks that foliage as certain subject,
        # and no amount of later cleaning gets it back out.
        hx, hy, hw, hh = _clip((fx + fw_ * 0.22, fy + fh_ * 0.2,
                                fw_ * 0.56, fh_ * 0.6), sw, sh)
        mask[hy:hy + hh, hx:hx + hw] = cv2.GC_FGD
        # A narrow core down the trunk. Deliberately small: it only has to be
        # certainly-subject. Seeded generously it drags the sky between two
        # people into the foreground.
        # Only for a lone subject. With a group the box spans the whole huddle
        # and a strip under each face drags the gaps between them in too.
        if not single:
            continue
        cx = fx + fw_ // 2
        run = ((y + bh) - (fy + fh_ * 1.2)) * 0.55
        tx, ty, tw, th = _clip((cx - fw_ * 0.22, fy + fh_ * 1.2, fw_ * 0.44, run), sw, sh)
        if th > 0:
            mask[ty:ty + th, tx:tx + tw] = cv2.GC_FGD

    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), mask, None,
                    bgd, fgd, iterations, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        mask = np.zeros((sh, sw), np.uint8)
        mask[y:y + bh, x:x + bw] = cv2.GC_FGD

    out = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    if out.sum() < 0.01 * sh * sw:      # GrabCut gave up: fall back to the box
        out[:] = 0
        out[y:y + bh, x:x + bw] = 1

    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE,
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    # Open before choosing the piece to keep, so a few pixels of foliage
    # touching the hair cannot smuggle a tree in as part of the subject, then
    # dilate back so the subject does not end up whittled down.
    bridge = _odd(max(3, int(min(sw, sh) * 0.012)))
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bridge, bridge))
    opened = cv2.morphologyEx(out, cv2.MORPH_OPEN, ker)
    if opened.sum() > 0.2 * out.sum():
        out = cv2.dilate(_keep_subject(opened, seeds, (x, y, bw, bh)), ker)
        out = np.minimum(out, cv2.dilate(opened, ker))
    else:
        out = _keep_subject(out, seeds, (x, y, bw, bh))
    out = _fill_holes(out)
    return cv2.resize(out, (w, h), interpolation=cv2.INTER_NEAREST)


def _keep_subject(mask: np.ndarray, seeds, box) -> np.ndarray:
    """Discard blobs that are not the subject.

    GrabCut happily returns islands of background that resemble the subject's
    colours. The piece to keep is the one under a detected face, or failing
    that the largest one overlapping the detected box.
    """
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n < 2:
        return mask
    wanted = set()
    for fx, fy, fw_, fh_ in seeds:
        cy, cx = min(mask.shape[0] - 1, fy + fh_ // 2), min(mask.shape[1] - 1, fx + fw_ // 2)
        lab = int(labels[cy, cx])
        if lab:
            wanted.add(lab)
    if not wanted:
        x, y, bw, bh = box
        best, best_area = 0, 0
        for i in range(1, n):
            sub = labels[y:y + bh, x:x + bw] == i
            area = int(sub.sum())
            if area > best_area:
                best, best_area = i, area
        if best:
            wanted.add(best)
    if not wanted:
        return mask
    return np.isin(labels, list(wanted)).astype(np.uint8)


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    """Close gaps enclosed by the subject.

    A hole is a background region that touches no edge of the picture. Flooding
    from one corner would not do: once the subject reaches an edge it splits the
    background in two, and half of it would be filled in as subject.
    """
    h, w = mask.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats((1 - mask).astype(np.uint8), 8)
    out = mask.copy()
    for i in range(1, n):
        left, top = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
        right = left + stats[i, cv2.CC_STAT_WIDTH]
        bottom = top + stats[i, cv2.CC_STAT_HEIGHT]
        if left > 0 and top > 0 and right < w and bottom < h:
            out[labels == i] = 1
    return out
