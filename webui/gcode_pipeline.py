#!/usr/bin/python3
"""Thresholded image per tray -> potrace -> OpenSCAD -> slicer -> copicograf G-code.

This is the chain `image_to_gcode_adaptive.py` describes, driven from uploads
instead of files named by a CMYK separation, and using the tools that are
actually on PATH instead of hardcoded macOS app bundles.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from configspec import CMYK_TO_TRAY, tray_entries  # noqa: E402

SLICER_CANDIDATES = [
    "prusa-slicer",
    "PrusaSlicer",
    "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer",
]
OPENSCAD_CANDIDATES = [
    "openscad",
    "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
    "/Applications/OpenSCAD-2021.01.app/Contents/MacOS/OpenSCAD",
]

# The Z values copicograf.prepare_path() watches for to raise and lower the brush.
PEN_UP = "G1 F600 Z6"
PEN_DOWN = "G1 F600 Z1"


def _which(candidates: list[str]) -> str | None:
    for c in candidates:
        found = shutil.which(c) if not c.startswith("/") else (c if os.access(c, os.X_OK) else None)
        if found:
            return found
    return None


def preflight() -> dict:
    potrace = _which(["potrace"])
    openscad = _which(OPENSCAD_CANDIDATES)
    slicer = _which(SLICER_CANDIDATES)
    tools = {
        "potrace": potrace,
        "openscad": openscad,
        "slicer": slicer,
    }
    return {
        "tools": tools,
        "ok": all(tools.values()),
        "missing": [k for k, v in tools.items() if not v],
    }


class PipelineError(RuntimeError):
    pass


def _run(cmd: list[str], log, cwd: Path | None = None):
    log(f"$ {' '.join(str(c) for c in cmd)}")
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    tail = (p.stdout or "")[-800:] + (p.stderr or "")[-800:]
    for line in tail.splitlines()[-12:]:
        if line.strip():
            log("  " + line.rstrip())
    if p.returncode != 0:
        raise PipelineError(f"{Path(cmd[0]).name} exited {p.returncode}")
    return p


# ------------------------------------------------------------------ raster prep

def to_pbm(src: Path, dst: Path, log) -> tuple[int, int]:
    """Anything that is not close to white counts as ink.

    The previews this pipeline is fed carry coloured ink on white, and a plain
    black-on-white threshold works out the same way. Keying on 'dark' instead
    would drop light inks like yellow entirely.
    """
    with Image.open(src) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        a = np.asarray(rgb)
    ink = (a < 250).any(axis=2)
    if not ink.any():
        raise PipelineError(f"{src.name} has no ink in it — nothing to paint")
    out = np.where(ink, 0, 255).astype(np.uint8)
    Image.fromarray(out, "L").convert("1").save(dst)
    log(f"  {src.name}: {w}×{h} px, {ink.mean() * 100:.1f}% ink")
    return w, h


_SVG_LEN = re.compile(r'^\s*([-\d.]+)\s*([a-z%]*)\s*$')
_UNIT_MM = {"": 25.4 / 96, "px": 25.4 / 96, "pt": 25.4 / 72, "mm": 1.0, "cm": 10.0, "in": 25.4}


def _svg_size_mm(svg_path: Path) -> tuple[float, float]:
    """How large OpenSCAD will import this SVG, in mm.

    potrace writes one point per source pixel, and OpenSCAD honours the declared
    unit, so the source image's DPI metadata does not enter into it. Reading the
    SVG's own width/height is what keeps the output at the requested size.
    """
    head = svg_path.read_text(errors="replace")[:2000]
    dims = []
    for axis in ("width", "height"):
        m = re.search(rf'{axis}="([^"]+)"', head)
        if not m:
            raise PipelineError(f"{svg_path.name} does not declare a {axis}")
        n = _SVG_LEN.match(m.group(1))
        if not n or n.group(2) not in _UNIT_MM:
            raise PipelineError(f"{svg_path.name} has an unusable {axis}: {m.group(1)!r}")
        dims.append(float(n.group(1)) * _UNIT_MM[n.group(2)])
    return dims[0], dims[1]


def _scad(scad_path: Path, svg_path: Path, width_mm: float, height_mm: float,
          extrude_mm: float, log):
    raw_w, raw_h = _svg_size_mm(svg_path)
    if raw_w <= 0 or raw_h <= 0:
        raise PipelineError(f"{svg_path.name} traced to nothing")
    log(f"  traced {raw_w:.1f}×{raw_h:.1f} mm, scaling to {width_mm:g}×{height_mm:g} mm")
    # Each axis gets its own factor. image_to_gcode_adaptive transposes these
    # two, which squashes any non-square image; kept correct here.
    scad_path.write_text(
        f"scale([{width_mm} / {raw_w}, {height_mm} / {raw_h}])\n"
        f"linear_extrude({extrude_mm})\n"
        f'  import("{svg_path.name}");\n'
    )


# --------------------------------------------------------------- slicer adapter

_G1 = re.compile(r"^G0*1(?![0-9])")
_G0 = re.compile(r"^G0*0(?![0-9])")
_WORD = re.compile(r"([XYZEF])\s*(-?\d*\.?\d+)")


def _polylines(gcode: Path) -> list[list[tuple[float, float]]]:
    """Pull extruding runs out of slicer output as plain XY polylines."""
    x = y = 0.0
    e = 0.0
    relative_e = False
    current: list[tuple[float, float]] = []
    out: list[list[tuple[float, float]]] = []
    for raw in gcode.read_text(errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("M83"):
            relative_e = True
            continue
        if line.startswith("M82"):
            relative_e = False
            continue
        if line.startswith("G92"):
            m = dict(_WORD.findall(line))
            if "E" in m:
                e = float(m["E"])
            continue
        if not (_G1.match(line) or _G0.match(line)):
            continue
        words = dict(_WORD.findall(line))
        nx = float(words.get("X", x))
        ny = float(words.get("Y", y))
        extruding = False
        if "E" in words:
            ev = float(words["E"])
            extruding = ev > 1e-9 if relative_e else ev > e + 1e-9
            e = e + ev if relative_e else ev
        moved = abs(nx - x) > 1e-9 or abs(ny - y) > 1e-9
        if extruding and moved:
            if not current:
                current = [(x, y)]
            current.append((nx, ny))
        elif current:
            out.append(current)
            current = []
        x, y = nx, ny
    if current:
        out.append(current)
    return out


def adapt_for_copicograf(slicer_gcode: Path, dst: Path, log) -> int:
    """Rewrite slicer output into the pen-up/pen-down form copicograf reads.

    copicograf.prepare_path() decides the brush is on the canvas by matching two
    exact Z lines that only `cura-slicer` emits. Rather than patch that matching,
    the extruding runs are re-emitted around those markers, which keeps
    copicograf.py untouched and works with whichever slicer is installed.
    """
    polys = _polylines(slicer_gcode)
    if not polys:
        raise PipelineError("slicer produced no extrusion moves — nothing to paint")
    lines = ["; adapted for copicograf by the Brushograph WebUI"]
    for poly in polys:
        sx, sy = poly[0]
        lines.append(PEN_UP)
        lines.append(f"G1 X{sx:.3f} Y{sy:.3f}")
        lines.append(PEN_DOWN)
        for px, py in poly[1:]:
            lines.append(f"G1 X{px:.3f} Y{py:.3f}")
    lines.append(PEN_UP)
    dst.write_text("\n".join(lines) + "\n")
    log(f"  {len(polys)} stroke paths, {sum(len(p) for p in polys)} points")
    return len(polys)


# --------------------------------------------------------------------- backlash

def apply_backlash(lines: list[str], bx: float, by: float) -> list[str]:
    """Insert a corrective move whenever an axis reverses direction.

    On a reversal the axis first has to take up its own slack, so the commanded
    distance is short by the backlash figure. Overshooting by that amount and
    coming back puts the head where the path asked for.
    """
    out: list[str] = []
    x = y = None
    dir_x = dir_y = 0
    for line in lines:
        body = line.split(";", 1)[0].strip()
        if not (_G1.match(body) or _G0.match(body)):
            out.append(line)
            continue
        words = dict(_WORD.findall(body))
        nx = float(words["X"]) if "X" in words else x
        ny = float(words["Y"]) if "Y" in words else y
        cx = cy = None
        if x is not None and nx is not None and abs(nx - x) > 1e-9:
            d = 1 if nx > x else -1
            if dir_x and d != dir_x and bx:
                cx = x - d * bx
            dir_x = d
        if y is not None and ny is not None and abs(ny - y) > 1e-9:
            d = 1 if ny > y else -1
            if dir_y and d != dir_y and by:
                cy = y - d * by
            dir_y = d
        if cx is not None or cy is not None:
            parts = ["G1"]
            if cx is not None:
                parts.append(f"X{cx:.3f}")
            if cy is not None:
                parts.append(f"Y{cy:.3f}")
            out.append(" ".join(parts) + " ; backlash take-up")
        out.append(line)
        x, y = nx, ny
    return out


# ------------------------------------------------------------------- the driver

def generate(conf: dict, images: dict[str, Path], workdir: Path, out_path: Path, log) -> dict:
    """Run every tray that has an image, then stitch one G-code file."""
    pre = preflight()
    if not pre["ok"]:
        raise PipelineError(
            "missing external tools: " + ", ".join(pre["missing"])
            + ". Install them (brew install potrace openscad, plus PrusaSlicer) and retry."
        )

    generator = conf.get("brushograph", {}).get("generator")
    if generator and generator != "copicograf":
        raise PipelineError(
            f"this config asks for the '{generator}' generator, which is not part of this "
            "repository — only the default copicograf generator can be built here."
        )

    from copicograf import Copicograf  # imported late: needs the repo on sys.path

    bg = conf.get("brushograph", {})
    width_mm = float(bg.get("width", 100))
    height_mm = float(bg.get("height", 100))
    slicer_conf = conf.get("slicer", {})

    # infill_line_distance is the gap between brush strokes. In slicer terms
    # that is the extrusion width, not the nozzle bore; feeding it in as a
    # nozzle diameter made PrusaSlicer reject any value below the layer height.
    try:
        line_w = float(slicer_conf.get("infill_line_distance", 1) or 1)
    except (TypeError, ValueError):
        line_w = 1.0
    line_w = min(max(line_w, 0.05), 20.0)
    # One layer only: the extrusion is the painting, height carries no meaning.
    layer_h = min(line_w * 0.8, 0.8)

    entries = [e for e in tray_entries(conf) if e["image"]]
    todo = [e for e in entries if e["tray"] in images]
    if not todo:
        raise PipelineError("no thresholded images were uploaded for any tray in color_order")

    # gcodes=[] on purpose: Copicograf's default argument is a shared mutable
    # list, so leaving it out would append this run onto the previous one.
    copicograf = Copicograf(conf=conf, gcodes=[])
    stats = {"trays": [], "strokes": 0}

    for entry in todo:
        tray = entry["tray"]
        log(f"[{tray}] tracing")
        src = images[tray]
        pbm = workdir / f"threshold_{tray}.pbm"
        svg = workdir / f"threshold_{tray}.svg"
        scad = workdir / f"threshold_{tray}.scad"
        stl = workdir / f"threshold_{tray}.stl"
        sliced = workdir / f"threshold_{tray}_slicer.gcode"
        adapted = workdir / f"threshold_{tray}_adapted.gcode"

        to_pbm(src, pbm, log)
        _run([pre["tools"]["potrace"], pbm.name, "-s", "-o", svg.name], log, cwd=workdir)
        _scad(scad, svg, width_mm, height_mm, layer_h, log)
        _run([pre["tools"]["openscad"], "-o", stl.name, scad.name], log, cwd=workdir)

        log(f"[{tray}] slicing")
        # OpenSCAD already emits the artwork in canvas coordinates (0,0)-(w,h).
        # Without an explicit bed and centre PrusaSlicer would re-centre it on
        # its own default bed and the painting would land in the wrong place.
        bed_w = max(float(bg.get("max_width", width_mm)), width_mm)
        bed_h = max(float(bg.get("max_height", height_mm)), height_mm)
        _run(
            [
                pre["tools"]["slicer"], "--export-gcode", "--output", sliced.name,
                "--bed-shape", f"0x0,{bed_w}x0,{bed_w}x{bed_h},0x{bed_h}",
                "--center", f"{width_mm / 2},{height_mm / 2}",
                "--layer-height", f"{layer_h}", "--first-layer-height", f"{layer_h}",
                "--perimeters", str(int(float(slicer_conf.get("wall_line_count", 1) or 1))),
                "--top-solid-layers", "0", "--bottom-solid-layers", "0",
                "--fill-pattern", str(slicer_conf.get("infill_pattern", "concentric")),
                "--fill-density", "100%",
                "--skirts", "0", "--brim-width", "0",
                "--nozzle-diameter", f"{line_w}",
                "--extrusion-width", f"{line_w}",
                "--filament-diameter", "1",
                "--temperature", "0", "--first-layer-temperature", "0",
                stl.name,
            ],
            log, cwd=workdir,
        )

        if not sliced.is_file():
            # PrusaSlicer reports some rejected settings on stdout and still
            # exits 0, so a missing file is the only reliable signal.
            raise PipelineError(
                f"the slicer produced no G-code for {tray}. Check Slicer Options — "
                f"infill line distance {line_w:g} mm."
            )
        n = adapt_for_copicograf(sliced, adapted, log)
        log(f"[{tray}] brush choreography at tray ({entry['x']}, {entry['y']})")
        copicograf.prepare_path(str(adapted), float(entry["x"]), float(entry["y"]))
        stats["trays"].append({"tray": tray, "color": entry["color"], "strokes": n})
        stats["strokes"] += n

    copicograf.save_gcode(str(out_path))

    lines = out_path.read_text().splitlines()
    if bg.get("backlash_compensation"):
        before = len(lines)
        lines = apply_backlash(lines, float(bg.get("backlash_x", 0)), float(bg.get("backlash_y", 0)))
        log(f"backlash compensation: +{len(lines) - before} corrective moves")

    header = [
        "; Brushograph WebUI",
        f"; controller: {conf.get('controller', {}).get('controller_type', 'unspecified')}",
        f"; trays: {', '.join(t['tray'] for t in stats['trays'])}",
        f"; image area: {width_mm:g} x {height_mm:g} mm",
    ]
    out_path.write_text("\n".join(header + lines) + "\n")
    stats["lines"] = len(lines) + len(header)
    stats["bytes"] = out_path.stat().st_size
    log(f"wrote {out_path.name}: {stats['lines']} lines, {stats['bytes'] / 1024:.0f} KB")
    return stats
