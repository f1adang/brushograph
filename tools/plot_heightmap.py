#!/usr/bin/env python3
"""plot_heightmap.py <csv> [out.png]
Works with probemap.csv (z_mm) and the older ToF heightmap.csv (dist_mm)."""
import sys
import numpy as np
import matplotlib.pyplot as plt

d = np.genfromtxt(sys.argv[1], delimiter=",", names=True)
if "z_mm" in d.dtype.names:
    v = d["z_mm"]                                    # probe: higher Z = higher surface
else:
    v = -d["dist_mm"]                                # ToF: bigger distance = lower
v = v - np.nanmedian(v)

xs, ys = np.unique(d["x"]), np.unique(d["y"])
Z = np.full((len(ys), len(xs)), np.nan)
Z[np.searchsorted(ys, d["y"]), np.searchsorted(xs, d["x"])] = v

dx = xs[1] - xs[0] if len(xs) > 1 else 1
dy = ys[1] - ys[0] if len(ys) > 1 else 1
lo, hi = np.nanpercentile(Z, [2, 98])
plt.imshow(Z, origin="lower", cmap="viridis", aspect="equal", vmin=lo, vmax=hi,
           extent=[xs[0] - dx/2, xs[-1] + dx/2, ys[0] - dy/2, ys[-1] + dy/2])
plt.colorbar(label="height relative to median [mm]")
plt.xlabel("X [mm]"); plt.ylabel("Y [mm]")
plt.title(f"Z heightmap  (full range {np.nanmax(Z) - np.nanmin(Z):.2f} mm)")
plt.tight_layout()
if len(sys.argv) > 2:
    plt.savefig(sys.argv[2], dpi=150)
else:
    plt.show()
