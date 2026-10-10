#!/usr/bin/python3
"""The order strokes are painted in: a shape finished before the next is begun,
and the shapes visited in the order that takes the machine least time.

Nearest-first, which is what ordered the strokes before this, is the obvious
way to put a few thousand strokes in order and it has one well-known fault: it
strands things. It goes to whatever is closest, and what is closest after the
outline of a wing is as often a sliver of the head beside it as the next ring
in. The sliver is painted, then the next, and the ring that was passed over is
left for the very end, when nothing nearer is left and the brush has to cross
the picture to fetch it. On the dragonfly at a 1 mm stroke the cyan plate went
back to a shape it had already left 9 times in 35 strokes, and the last thing
it painted was the inside of the upper wing it had outlined first.

So the order is built in two levels:

- **A section is finished before the brush leaves it.** A section is one
  connected patch of ink. Every stroke lies inside one -- the bridges and the
  moves through the ink are only ever taken inside it -- so the strokes of a
  plate fall into sections without ambiguity, and once a section is begun the
  brush is only offered strokes in it until there are none left.
- **The sections are toured.** Each is painted either way round, from its
  first stroke or from its last, and 2-opt and or-opt rearrange them, then the
  strokes inside each, until no swap is any quicker.

What is minimised is time, not distance. A move between strokes on a machine
that accelerates at 100 mm/s² and travels at 35 mm/s does not reach that speed
in under 12 mm, and below that its time goes as the square root of its length:
two 5 mm moves take longer than one of 10. Shortest-distance tours buy many
small moves with a few long ones, which is the wrong trade here.

The tour is anchored at the cups: a tray's painting starts after its pickup at
the colour's cup and ends with a wash at the water, so a tour that begins and
ends near the containers saves the crossing either side.
"""
from __future__ import annotations

import cv2
import numpy as np

# Rounds of improvement before settling. Each round is a 2-opt sweep and an
# or-opt sweep. Three came to the same order as eight on both the dragonfly
# and The Starry Night, and the five after it cost a photograph 3 s.
ROUNDS = 3

# A swap has to save at least this many seconds to be taken, so float noise
# cannot keep a sweep going for ever.
EPSILON = 1e-6

# Up to this many items every swap is tried. Past it only the swaps that make
# a move to one of an item's NEIGHBOURS nearest are: a full sweep is quadratic,
# a photograph's biggest section holds thousands of strokes, and a swap that
# saves time is one that puts something next to what is near it on the paper.
FULL = 300
NEIGHBOURS = 10

# Or-opt moves runs of up to this many items.
OR_RUN = 3


def travel_seconds(dist, accel: float, speed: float):
    """How long a move of `dist` mm takes from a standstill to a standstill.

    Short of `speed`² / `accel` it never gets up to speed and is two halves of
    a triangle; past it, the ramps plus the cruise.
    """
    d = np.asarray(dist, dtype=float)
    reach = speed * speed / accel
    return np.where(d < reach, 2.0 * np.sqrt(np.maximum(d, 0.0) / accel),
                    d / speed + speed / accel)


def sections_of(polys, ink: np.ndarray, width_mm: float, height_mm: float) -> list[int]:
    """Which connected patch of ink each stroke lies in.

    Read at a few points along the stroke and settled by vote, because a
    stroke's ends sit near the edge of the ink and rounding can put one of
    them a pixel outside. A stroke found in no ink at all is a section of its
    own.
    """
    _n, labels = cv2.connectedComponents(ink.astype(np.uint8), connectivity=8)
    h, w = labels.shape
    out = []
    for i, poly in enumerate(polys):
        pts = np.asarray(poly[::max(1, len(poly) // 8)] + [poly[-1]], dtype=float)
        cols = np.clip((pts[:, 0] / width_mm * w).astype(int), 0, w - 1)
        rows = np.clip(((1.0 - pts[:, 1] / height_mm) * h).astype(int), 0, h - 1)
        found = labels[rows, cols]
        found = found[found > 0]
        if found.size == 0:
            # Look a few pixels round the first point before giving up.
            r, c = rows[0], cols[0]
            win = labels[max(0, r - 3):r + 4, max(0, c - 3):c + 4]
            found = win[win > 0]
        out.append(int(np.bincount(found).argmax()) if found.size else -(i + 1))
    return out


def _cost(a, b, seconds):
    """Seconds from each of `a` to each of `b`; a missing anchor (NaN) is free."""
    d = np.hypot(a[..., 0] - b[..., 0], a[..., 1] - b[..., 1])
    return np.where(np.isnan(d), 0.0, seconds(np.nan_to_num(d)))


def _neighbours(P, Q, k):
    """Per item, the items with an end among the `k` nearest either of its ends.

    Worked out once, from where the ends are, and good for the whole of
    `improve`: turning an item round swaps its ends but does not move them.
    FLANN's k-d trees, which found 99.9% of the true nearest dozen in 20,000
    points in a fifth of a second; a fresh sort per question was most of the
    minute this pass first took on a photograph.
    """
    n = len(P)
    ends = np.vstack([P, Q]).astype(np.float32)
    k = min(k + 1, len(ends))
    index = cv2.flann_Index(ends, {"algorithm": 1, "trees": 4})
    found, _ = index.knnSearch(ends, k, params={"checks": 64})
    found = found % n
    return [np.unique(np.concatenate([found[i], found[i + n]])) for i in range(n)]


def improve(P: np.ndarray, Q: np.ndarray, start, end, seconds):
    """Reorder and turn round items that are entered at P and left at Q.

    `start` and `end` are where the brush comes from and goes to, either of
    them None when it does not matter. Returns the new order and, per item in
    it, whether it is now painted the other way round.
    """
    n = len(P)
    order = np.arange(n)
    flip = np.zeros(n, bool)
    if n < 2 and start is None and end is None:
        return order, flip
    P, Q = P.astype(float).copy(), Q.astype(float).copy()
    S = np.array(start if start is not None else (np.nan, np.nan), float)
    E = np.array(end if end is not None else (np.nan, np.nan), float)

    # Which positions to try against a given one. Every one while there are
    # few; past that, where the items near it on the paper now stand.
    small = n <= FULL
    every = np.arange(n)
    if not small:
        near = _neighbours(P, Q, NEIGHBOURS)
        anchors = np.array([-1, n - 1])
    pos = np.arange(n)            # where each original item now stands

    def around(*at):
        """Positions of the items near the ones standing at `at`, and one before."""
        if small:
            return every
        got = np.concatenate([pos[near[order[a]]] for a in at if 0 <= a < n])
        return np.unique(np.concatenate([got, got - 1, anchors]))

    def after(js):
        """Where the brush goes after item j: the next one's entry, or the end."""
        last = js == n - 1
        return np.where(last[:, None], E[None, :], P[np.minimum(js + 1, n - 1)])

    def before(ks):
        """Where the brush comes from into gap k+1: item k's exit, or the start."""
        return np.where((ks >= 0)[:, None], Q[np.maximum(ks, 0)], S[None, :])

    for _ in range(ROUNDS):
        changed = False

        # 2-opt: reverse items i..j, so the path runs prev -> Q[j] ... P[i] -> next.
        # j == i is turning one item round on its own. Worth it only when one
        # of the two new moves is short: Q[j] near prev, or P[j+1] near P[i].
        for i in range(n):
            prev = Q[i - 1] if i else S
            js = around(i - 1, i)
            js = js[(js >= i) & (js < n)]
            if js.size == 0:
                continue
            nxt = after(js)
            pi = P[i][None, :]
            gain = (_cost(prev[None, :], pi, seconds) + _cost(Q[js], nxt, seconds)
                    - _cost(prev[None, :], Q[js], seconds) - _cost(pi, nxt, seconds))
            k = int(np.argmax(gain))
            if gain[k] > EPSILON:
                j = int(js[k])
                P[i:j + 1], Q[i:j + 1] = Q[i:j + 1][::-1].copy(), P[i:j + 1][::-1].copy()
                order[i:j + 1] = order[i:j + 1][::-1]
                flip[i:j + 1] = ~flip[i:j + 1][::-1]
                pos[order[i:j + 1]] = np.arange(i, j + 1)
                changed = True

        # Or-opt: lift a run of up to OR_RUN items out and put it, either way
        # round, into whichever gap it costs least in. This is what fetches a
        # stranded item back to where it belongs, which 2-opt can only do by
        # reversing everything in between.
        for run in range(1, min(OR_RUN, n - 1) + 1):
            i = 0
            while i + run <= n:
                s, e = i, i + run - 1
                i += 1
                prev = Q[s - 1] if s else S
                nxt = P[e + 1] if e + 1 < n else E
                saved = float(_cost(prev, P[s], seconds) + _cost(Q[e], nxt, seconds)
                              - _cost(prev, nxt, seconds))
                if saved <= EPSILON:
                    continue
                # Gaps k sit between item k and k+1; -1 is the start, n-1 the end.
                ks = np.union1d(around(s, e), [-1]) if small else around(s, e)
                ks = ks[((ks < s - 1) | (ks > e)) & (ks >= -1) & (ks < n)]
                if ks.size == 0:
                    continue
                a, b = before(ks), after(ks)
                base = _cost(a, b, seconds)
                fwd = (_cost(a, P[s][None, :], seconds) + _cost(Q[e][None, :], b, seconds)
                       - base)
                rev = (_cost(a, Q[e][None, :], seconds) + _cost(P[s][None, :], b, seconds)
                       - base)
                both = np.minimum(fwd, rev)
                k = int(np.argmin(both))
                if saved - both[k] <= EPSILON:
                    continue
                gap, turned = int(ks[k]), bool(rev[k] < fwd[k])
                idx = np.arange(n)
                seg = idx[s:e + 1][::-1] if turned else idx[s:e + 1]
                rest = np.concatenate([idx[:s], idx[e + 1:]])
                at = int(np.searchsorted(rest, gap)) + 1 if gap >= 0 else 0
                new = np.concatenate([rest[:at], seg, rest[at:]])
                P, Q, flip, order = P[new], Q[new], flip[new], order[new]
                if turned:
                    span = slice(at, at + run)
                    P[span], Q[span] = Q[span].copy(), P[span].copy()
                    flip[span] = ~flip[span]
                pos[order] = every
                changed = True
        if not changed:
            break
    return order, flip


def _ends(strokes):
    return (np.array([s[0] for s in strokes], float),
            np.array([s[-1] for s in strokes], float))


def _apply(items, order, flip, turn):
    return [turn(items[k]) if f else items[k] for k, f in zip(order, flip)]


def _reverse_stroke(stroke):
    return stroke[::-1]


def _reverse_block(block):
    return [s[::-1] for s in block[::-1]]


def arrange(polys, sections, seconds, start=None, end=None):
    """Strokes grouped by section, each section finished, the whole toured.

    `polys` arrive with each section's strokes together (order_polylines sees
    to that) and leave in the order and direction they should be painted.
    """
    if len(polys) < 2:
        return polys
    blocks: list[list] = []
    for poly, sec in zip(polys, sections):
        if blocks and sec == blocks[-1][0]:
            blocks[-1][1].append(poly)
        else:
            blocks.append((sec, [poly]))
    blocks = [b for _s, b in blocks]

    def within(blocks):
        """Tidy each section's own strokes between the ones either side of it."""
        out = []
        for i, block in enumerate(blocks):
            if len(block) > 1:
                before = out[-1][-1][-1] if out else start
                after = blocks[i + 1][0][0] if i + 1 < len(blocks) else end
                P, Q = _ends(block)
                order, flip = improve(P, Q, before, after, seconds)
                block = _apply(block, order, flip, _reverse_stroke)
            out.append(block)
        return out

    blocks = within(blocks)
    P = np.array([b[0][0] for b in blocks], float)
    Q = np.array([b[-1][-1] for b in blocks], float)
    order, flip = improve(P, Q, start, end, seconds)
    blocks = _apply(blocks, order, flip, _reverse_block)
    blocks = within(blocks)
    return [s for b in blocks for s in b]
