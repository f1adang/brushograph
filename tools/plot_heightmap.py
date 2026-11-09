#!/usr/bin/env python3
"""plot_heightmap.py <csv> [out.png] [--conf machine.conf | --model mini|micro]

Works with probemap.csv (z_mm) and the older ToF heightmap.csv (dist_mm).

Heights are drawn relative to the paper at the calibration dot, where
calibrate.g touches down: 5 mm in from X 0 and from Canvas Start Y. That is
the levelling's own nought -- the one place Canvas Height is true -- so the
figures here are the corrections the brush will be given, and they agree with
the heat map in the WebUI's plan. Canvas Start Y is the machine's: read from
--conf, or the model's default (a Mini unless --model says otherwise).

It used to be the median, which nothing on the machine touches: on the three
kept maps the dot sits 0.48 to 0.79 mm away from it.
"""
import argparse
import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

# The zero is taken from the WebUI's own functions, so the tool and the plan
# cannot drift apart on where the dot is or how the bed between points is read.
# Only levelmap and configspec: both need nothing past NumPy, unlike
# gcode_pipeline (OpenCV), which is why the scan's backlash is not undone here.
# On Parang, Pinkograph and Testikel that moves the zero at the dot by at most
# 0.001 mm.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webui"))
import configspec
import levelmap

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("csv")
ap.add_argument("out", nargs="?", help="write a PNG instead of opening a window")
where = ap.add_mutually_exclusive_group()
where.add_argument("--conf", help="the machine's .conf, for its Canvas Start Y")
where.add_argument("--model", choices=list(configspec.MODELS), default="mini",
                   help="the machine's model, for its default Canvas Start Y (default: mini)")
args = ap.parse_args()

if args.conf:
    with open(args.conf) as f:
        conf = configspec.with_defaults(json.load(f))
else:
    conf = configspec.with_defaults(configspec.new_config(args.model))
dot = configspec.calibration_point(conf)

d = np.genfromtxt(args.csv, delimiter=",", names=True)
laser = "z_mm" not in d.dtype.names
if not laser:
    v = d["z_mm"]                                    # probe: higher Z = higher surface
else:
    v = -d["dist_mm"]                                # ToF: bigger distance = lower
    v[v >= 0] = np.nan                               # nought distance: saw nothing

# The surface at the dot, as the levelling reads it: outliers left out, a
# laser's readings smoothed, bilinear between points, and the nearest edge
# for a dot outside the scan.
seen = np.isfinite(v)
points = [[float(x), float(y), float(z)] for x, y, z in zip(d["x"][seen], d["y"][seen], v[seen])]
bed, _ = levelmap.drop_outliers(points)
if laser:
    bed = levelmap.smooth(bed, levelmap.LASER_SMOOTH_MM)
surf = levelmap.surface(bed)
v = v - surf(*dot)
cols, rows = surf.knots
outside = not (cols[0] <= dot[0] <= cols[-1] and rows[0] <= dot[1] <= rows[-1])

xs, ys = np.unique(d["x"]), np.unique(d["y"])
Z = np.full((len(ys), len(xs)), np.nan)
Z[np.searchsorted(ys, d["y"]), np.searchsorted(xs, d["x"])] = v

dx = xs[1] - xs[0] if len(xs) > 1 else 1
dy = ys[1] - ys[0] if len(ys) > 1 else 1
lo, hi = np.nanpercentile(Z, [2, 98])
plt.imshow(Z, origin="lower", cmap="viridis", aspect="equal", vmin=lo, vmax=hi,
           extent=[xs[0] - dx/2, xs[-1] + dx/2, ys[0] - dy/2, ys[-1] + dy/2])
plt.colorbar(label="height relative to calibration dot [mm]")
plt.plot(*dot, marker="x", color="red", markersize=10, mew=2, clip_on=False)
plt.annotate("0", dot, xytext=(6, 6), textcoords="offset points", color="red",
             annotation_clip=False)
plt.xlabel("X [mm]"); plt.ylabel("Y [mm]")
title = f"Z heightmap  (full range {np.nanmax(Z) - np.nanmin(Z):.2f} mm)"
title += f"\n0 at the calibration dot, X{dot[0]:g} Y{dot[1]:g}"
if outside:
    title += ": outside the scan, read off its edge"
plt.title(title)
plt.tight_layout()
if args.out:
    plt.savefig(args.out, dpi=150)
else:
    plt.show()
