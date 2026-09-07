#!/usr/bin/python3
"""Find the person or prominent object in a photo, and cut it from its background.

Everything here uses what OpenCV already ships: Haar cascades bundled with the
package and its saliency operators. Nothing is downloaded, so detection works
offline and adds no dependency.
"""
from __future__ import annotations

import hashlib
import threading
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from images import flatten

# A small salient-object segmentation network, run through OpenCV's own ONNX
# support so it costs no new Python dependency. Colour-based segmentation cannot
# separate dark hair from dark foliage however it is seeded; this can.
MODEL_DIR = Path(__file__).resolve().parent / "models"
_RELEASE = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/"

# Tried in order, best first. The large one is markedly better on cluttered
# scenes and machinery — it follows a gantry rail and wiring that the small one
# blobs over — and no worse on people. The small one is kept as a light second
# choice for when the big download will not happen.
MODELS = [
    {"file": "isnet-general-use.onnx", "side": 1024, "mean": 0.5, "std": 1.0,
     "mb": 170, "url": _RELEASE + "isnet-general-use.onnx"},
    {"file": "u2netp.onnx", "side": 320, "mean": (0.485, 0.456, 0.406),
     "std": (0.229, 0.224, 0.225), "mb": 4, "url": _RELEASE + "u2netp.onnx"},
]

# A small ImageNet classifier, used only to tell an animal from a thing. The
# first 398 ImageNet classes are organisms and the rest are artifacts, so the
# probability mass below that boundary answers the question directly. There is
# no "person" class in ImageNet, which is why people are still recognised by
# their faces.
# A face detector that copes with a head turned or tilted. The Haar cascades
# OpenCV bundles only find a face looking at the camera or squarely side-on: a
# person glancing down was reported as an "object", and rotating the picture to
# chase the tilt found a face on a machine instead. This one finds the downturned
# head at 0.91 confidence and still finds nothing on the machine.
FACE_MODEL = {"file": "face_detection_yunet_2023mar.onnx", "mb": 0.3, "min_bytes": 100_000,
              "url": "https://github.com/opencv/opencv_zoo/raw/main/models/"
                     "face_detection_yunet/face_detection_yunet_2023mar.onnx"}
FACE_CONF = 0.6     # below this the detector is guessing

CLASSIFIER = {"file": "squeezenet1.1-7.onnx", "mb": 5, "side": 224,
              "url": "https://github.com/onnx/models/raw/main/validated/vision/"
                     "classification/squeezenet/model/squeezenet1.1-7.onnx"}
ANIMAL_CLASSES = 398
ANIMAL_AT = 0.5

_NET = None
_SPEC = None
_CLS = None
_CLS_TRIED = False
_FACE = None
_FACE_TRIED = False
_NET_TRIED = False
_LOCK = threading.Lock()
_CACHE: dict[str, np.ndarray] = {}


WORK = 640          # detection resolution; boxes are returned in source pixels
MIN_COVER = 0.015   # below this a "subject" is a speck, not the subject
MAX_COVER = 0.92    # above this it is the whole frame, so isolating gains nothing


def _fetch(spec, log=None) -> Path | None:
    """Ensure one model is on disk, downloading it once into webui/models/."""
    floor = int(spec.get("min_bytes", 1_000_000))
    path = MODEL_DIR / spec["file"]
    if path.exists() and path.stat().st_size > floor:
        return path
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    try:
        if log:
            log(f"fetching segmentation model {spec['file']} ({spec['mb']} MB)")
        with urllib.request.urlopen(spec["url"], timeout=300) as r, tmp.open("wb") as f:
            shutil.copyfileobj(r, f)
        if tmp.stat().st_size < floor:
            raise OSError(f"download was only {tmp.stat().st_size} bytes")
        tmp.replace(path)
        return path
    except (urllib.error.URLError, OSError, ValueError) as exc:
        if log:
            log(f"{spec['file']} unavailable ({exc})")
        tmp.unlink(missing_ok=True)
        return None


def _net(log=None):
    """The best network that could be had, or None."""
    global _NET, _NET_TRIED, _SPEC
    with _LOCK:
        if _NET is not None or _NET_TRIED:
            return _NET
        _NET_TRIED = True
        for spec in MODELS:
            path = _fetch(spec, log)
            if path is None:
                continue
            try:
                _NET = cv2.dnn.readNetFromONNX(str(path))
                _SPEC = spec
                if log:
                    log(f"segmentation using {spec['file']}")
                return _NET
            except cv2.error as exc:
                if log:
                    log(f"{spec['file']} would not load ({exc})")
        if log:
            log("no segmentation model available; falling back to GrabCut")
        return None


def warm(log=None) -> bool:
    """Load the networks up front so the first upload is not the one that waits."""
    ok = _net(log) is not None
    _face_net(log)
    return ok


def _face_net(log=None):
    """The DNN face detector, or None if it could not be had."""
    global _FACE, _FACE_TRIED
    with _LOCK:
        if _FACE is not None or _FACE_TRIED:
            return _FACE
        _FACE_TRIED = True
        path = _fetch(FACE_MODEL, log)
        if path is None:
            if log:
                log("face detector unavailable; falling back to Haar cascades")
            return None
        try:
            _FACE = cv2.FaceDetectorYN.create(str(path), "", (320, 320),
                                              score_threshold=FACE_CONF,
                                              nms_threshold=0.3, top_k=20)
            if log:
                log(f"faces using {FACE_MODEL['file']}")
        except (cv2.error, AttributeError) as exc:
            if log:
                log(f"face detector would not load ({exc}); falling back to Haar cascades")
            _FACE = None
        return _FACE


def _classifier(log=None):
    global _CLS, _CLS_TRIED
    with _LOCK:
        if _CLS is not None or _CLS_TRIED:
            return _CLS
        _CLS_TRIED = True
        path = _fetch(CLASSIFIER, log)
        if path is None:
            return None
        try:
            _CLS = cv2.dnn.readNetFromONNX(str(path))
        except cv2.error as exc:
            if log:
                log(f"classifier would not load ({exc}); animals will read as objects")
            _CLS = None
        return _CLS


def animal_score(image: Image.Image, mask: np.ndarray | None = None,
                 box=None, log=None) -> float:
    """How much of the classifier's confidence falls on animal classes.

    The subject is cut out and cropped before classifying: a cat fills little of
    a photograph, and asking about the whole frame asks the wrong question.
    """
    net = _classifier(log)
    if net is None:
        return 0.0
    rgb = np.asarray(flatten(image))
    if mask is not None and box is not None and mask.any():
        x, y, w, h = box
        rgb = np.where(mask[..., None] > 0, rgb, 255).astype(np.uint8)[y:y + h, x:x + w]
    if rgb.size == 0:
        return 0.0
    side = CLASSIFIER["side"]
    small = cv2.resize(rgb, (side, side), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], np.float32)
    std = np.array([0.229, 0.224, 0.225], np.float32)
    with _LOCK:
        net.setInput(((small - mean) / std).transpose(2, 0, 1)[None])
        out = net.forward().reshape(-1)
    exp = np.exp(out - out.max())
    prob = exp / exp.sum()
    return float(prob[:ANIMAL_CLASSES].sum())


def segment(image: Image.Image, log=None) -> np.ndarray | None:
    """Probability that each pixel belongs to the subject, or None without a model.

    Results are cached by image content: detection and isolation both want this
    and there is no sense running the network twice for one upload.
    """
    rgb = np.asarray(flatten(image))
    key = hashlib.blake2b(rgb.tobytes(), digest_size=16).hexdigest()
    if key in _CACHE:
        return _CACHE[key]
    net = _net(log)
    if net is None:
        return None
    side = _SPEC["side"]
    mean = np.array(_SPEC["mean"], np.float32)
    std = np.array(_SPEC["std"], np.float32)
    small = cv2.resize(rgb, (side, side), interpolation=cv2.INTER_AREA)
    blob = ((small.astype(np.float32) / 255.0 - mean) / std).transpose(2, 0, 1)[None]
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


def _mask_from_prob(prob: np.ndarray, strong: float = 0.60, weak: float = 0.22) -> np.ndarray:
    """Threshold with hysteresis: confident regions, grown into their doubtful parts.

    A single cut-off cannot win here. The network scores a dark circuit board
    bolted to a machine well below its confident regions, so a level high enough
    to exclude the table also excludes the board; a level low enough to keep the
    board also keeps the clutter behind it. Growing outward from the confident
    core keeps whatever is attached to the subject and nothing that merely
    happens to score similarly somewhere else in the frame.
    """
    strong_mask = (prob > strong).astype(np.uint8)
    weak_mask = (prob > weak).astype(np.uint8)
    if not strong_mask.any():
        strong_mask = (prob > float(prob.max()) * 0.7).astype(np.uint8)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(weak_mask, connectivity=8)
    if n > 1:
        touched = {int(v) for v in np.unique(labels[strong_mask > 0]) if v}
        # Ignore weak blobs that only brush the strong core: a genuine part is
        # joined to it, not merely adjacent to a few of its pixels.
        keep = []
        for i in touched:
            overlap = int(((labels == i) & (strong_mask > 0)).sum())
            if overlap >= max(64, stats[i, cv2.CC_STAT_AREA] * 0.02):
                keep.append(i)
        mask = np.isin(labels, keep).astype(np.uint8) if keep else strong_mask
    else:
        mask = strong_mask

    k = max(3, _odd(int(min(mask.shape) * 0.006)))
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, ker)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, ker)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n < 2:
        return mask
    biggest = int(stats[1:, cv2.CC_STAT_AREA].max())
    keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= max(biggest * 0.06, 64)]
    return np.isin(labels, keep).astype(np.uint8) if keep else mask


def snap_to_edges(image: Image.Image, mask: np.ndarray, band: float = 0.04,
                  iterations: int = 5, work: int = 900) -> np.ndarray:
    """Pull the mask boundary onto the picture's own edges.

    The network answers "what is the subject" well and "exactly where does it
    end" only roughly, and on a busy background the boundary can sweep out into
    scaffolding and foliage beside a head. GrabCut is given the inside of the
    mask as certain subject, the outside as certain background, and only a band
    either side of the boundary to decide — so it cannot re-open the question of
    what the subject is, only where its edge runs.
    """
    rgb = np.asarray(flatten(image))
    h, w = mask.shape
    scale = min(1.0, work / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) \
        if scale < 1.0 else rgb
    mm = cv2.resize(mask, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
    r = max(3, int(min(mm.shape) * band)) | 1
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r, r))

    guide = np.where(mm > 0, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype(np.uint8)
    guide[cv2.erode(mm, ker) > 0] = cv2.GC_FGD
    guide[cv2.dilate(mm, ker) == 0] = cv2.GC_BGD
    if not (guide == cv2.GC_FGD).any() or not (guide == cv2.GC_BGD).any():
        return mask

    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), guide, None,
                    bgd, fgd, iterations, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return mask
    out = np.where((guide == cv2.GC_FGD) | (guide == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    # A refinement that eats half the subject has gone wrong, not right.
    if out.sum() < 0.45 * max(int(mm.sum()), 1):
        return mask
    full = cv2.resize(out, (w, h), interpolation=cv2.INTER_NEAREST)
    # Retract only. This step exists to pull the boundary in off the background;
    # letting it push out as well let it claim sunlit boardwalk beside an arm,
    # because that matches skin closely enough for a colour model to be fooled.
    # What the subject reaches is the network's call, not GrabCut's.
    return np.minimum(full, mask)


def _faces(image: Image.Image) -> list:
    """Face boxes in source coordinates.

    The DNN detector is tried first and the bundled Haar cascades are the
    fallback, so this still works with nothing downloaded — less well, but it
    works.
    """
    rgb = np.asarray(flatten(image))
    h, w = rgb.shape[:2]
    scale = min(1.0, WORK / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) \
        if scale < 1.0 else rgb
    sh, sw = small.shape[:2]
    back = 1.0 / scale if scale < 1.0 else 1.0

    net = _face_net()
    if net is not None:
        try:
            # The detector is built once and re-pointed at each picture's size;
            # it is not thread-safe, so the call is held under the same lock the
            # models are loaded behind.
            with _LOCK:
                net.setInputSize((sw, sh))
                _, faces = net.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
            if faces is not None and len(faces):
                return [[int(v * back) for v in f[:4]] for f in faces]
            return []
        except cv2.error:
            pass    # fall through to the cascades

    gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY))
    found = []
    # The profile cascade is held to a stricter vote. At the same threshold as
    # the frontal one it invented a face on a stepper motor, which is enough to
    # have a photograph of a machine announced as a person.
    for name, neighbours in (("haarcascade_frontalface_default.xml", 6),
                             ("haarcascade_profileface.xml", 9)):
        c = _cascade(name)
        if c is None:
            continue
        for f in c.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=neighbours,
                                    minSize=(max(18, sw // 22), max(18, sh // 22))):
            found.append(tuple(int(v) for v in f))
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
        if faces:
            kind, how = "person", f"segmentation and {len(faces)} face(s)"
        else:
            score = animal_score(image, mask, box, log)
            if score >= ANIMAL_AT:
                kind, how = "animal", f"segmentation, {score * 100:.0f}% animal"
            else:
                kind, how = "object", "segmentation"
        return {
            "found": True,
            "kind": kind,
            "how": how,
            "count": len(faces) or 1,
            "coverage": round(cover, 3),
            "box": box,
            "parts": [box],
            "faces": faces,
        }

    rgb = np.asarray(flatten(image))
    h, w = rgb.shape[:2]
    scale = min(1.0, WORK / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) \
        if scale < 1.0 else rgb
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)
    sh, sw = gray.shape
    back = 1.0 / scale if scale < 1.0 else 1.0

    # Same detector as the model path uses, so a machine is not announced as a
    # person just because the segmentation network was unavailable.
    faces = [tuple(int(v * scale) for v in f) for f in _faces(image)]
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
        # Also held to a stricter vote: at the looser setting these fired on a
        # stepper motor and nothing else across the test images.
        found = c.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=8,
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
        return _fill_holes(snap_to_edges(image, _mask_from_prob(prob)))

    rgb = np.asarray(flatten(image))
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


def _fill_holes(mask: np.ndarray, max_share: float = 0.01) -> np.ndarray:
    """Close pinholes enclosed by the subject — and only pinholes.

    A hole is background that touches no edge of the picture, but that
    description also fits the gap between an arm and a torso, which is real
    background and must stay out. Only holes small against the subject are
    filled; anything larger is a gap the subject genuinely has.
    """
    h, w = mask.shape
    subject_area = float(mask.sum()) or 1.0
    n, labels, stats, _ = cv2.connectedComponentsWithStats((1 - mask).astype(np.uint8), 8)
    out = mask.copy()
    for i in range(1, n):
        left, top = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
        right = left + stats[i, cv2.CC_STAT_WIDTH]
        bottom = top + stats[i, cv2.CC_STAT_HEIGHT]
        enclosed = left > 0 and top > 0 and right < w and bottom < h
        if enclosed and stats[i, cv2.CC_STAT_AREA] <= subject_area * max_share:
            out[labels == i] = 1
    return out
