# Brushograph WebUI

A browser interface to the Brushograph software in this repo: upload thresholded
images, get G-code for a brush plotter. It mirrors the workflow of
brushograph.pro.

## Run

```bash
cd webui
../venv/bin/python app.py            # http://127.0.0.1:8080
../venv/bin/python app.py --port 8765 --host 0.0.0.0
```

Flask is the only added Python dependency. The G-code step also needs
`potrace`, `openscad` and a slicer on the system; `/about` shows what was found.

## How it works

Everything is driven by a machine config (`.conf`, JSON). Pick a preset from the
repo root or upload your own, and the whole options form is **generated from
that file** — sections, fields, types and defaults all come from the config, so
a config carrying different keys brings its own fields with it.

- **Trays and Images** — the water tray, then one entry per colour in
  `color_order`, each with tray X/Y and a thresholded image upload.
- **Brushograph Options** — every key under `brushograph`, including the nested
  `moves` speed groups, with explanatory tooltips.
- **Slicer Options** / **Controller Options** — rendered when the config has them.
- **Machine sketch** — a to-scale drawing of bed, image area and trays with
  their entry and drip radii, redrawn as you edit. Trays parked outside the bed
  are called out rather than quietly cropped.

Two actions:

- **Download Config** returns the edited config as a `.conf`. Types are
  preserved and keys the form does not cover are passed through untouched.
- **Generate Gcode** runs the pipeline and returns one G-code file.

## The G-code pipeline

Per tray: threshold → `potrace` → SVG → OpenSCAD → STL → slicer → adapter →
`copicograf`, then all trays are concatenated and optionally backlash-compensated.

Notes on things that needed care:

- **Ink is anything not white.** Keying on "dark" would drop light inks such as
  yellow entirely.
- **Scale comes from the traced SVG, not the source image.** potrace writes one
  point per pixel and OpenSCAD honours the declared unit, so the PNG's DPI
  metadata is irrelevant. Reading the SVG's own width/height is what keeps the
  painting at the size the config asks for.
- **The slicer is pinned to the config's coordinates.** OpenSCAD emits the
  artwork at `(0,0)-(width,height)`; without an explicit `--bed-shape` and
  `--center` PrusaSlicer re-centres it on its default bed and the painting lands
  in the wrong place.
- **`infill_line_distance` is an extrusion width, not a nozzle bore.** Passing it
  as a nozzle diameter makes PrusaSlicer silently reject any value below the
  layer height, exit 0, and write nothing.
- **One layer only.** The extrusion is the painting, so the SCAD extrude height
  is matched to the layer height to avoid slicing the same artwork twice.

### Controller dialect

`copicograf` takes its acceleration and feedrate lines straight from the config's
`moves` blocks, which are written for Marlin: `M204` (acceleration), `M203` (max
feedrate) and `M400` (wait for moves). GRBL and FluidNC answer an unknown M-code
with an error and stop executing, and copicograf emits `M204` as the very first
line of a run — so nothing after it ever runs.

`controller.controller_type` now decides. Marlin keeps them; anything else has
them stripped (about 1,400 lines in a one-tray run, since every speed change
re-emits the pair). The `G0 F…` feedrate in each block is understood everywhere
and survives either way, so motion speed is unaffected.

A config with no `controller` section is treated as GRBL. That way round is
safe: emitting Marlin-only codes to a GRBL board halts it, while dropping them
costs a Marlin board only its acceleration tuning.

Output also opens with an explicit start sequence — `G90`/`G21`, the normal
feedrate, then a lift to the config's own safe Z — because copicograf's own
`G90`/`G21` come *after* that first `M204` and are never reached on a strict
controller.

### The slicer adapter

`copicograf.prepare_path()` decides the brush is on the canvas by matching two
exact lines, `G1 F600 Z1` and `G1 F600 Z6`, which only `cura-slicer` emits. With
PrusaSlicer — the fallback this repo actually falls back to — those never appear,
`brush_on_canvas` stays `False`, and the result is one continuous scribble with
no dips. Rather than change that matching, `gcode_pipeline.adapt_for_copicograf`
re-emits the slicer's extruding runs around those markers, so `copicograf.py` is
untouched and any installed slicer works.

`Copicograf.__init__` also takes `gcodes=[]` as a mutable default, shared across
instances; the pipeline always passes an explicit list so one run cannot append
onto the previous one.

## Limits

- **One generation at a time**, behind a lock: `copicograf` keeps state on the
  instance and the pipeline shells out through a shared working directory.
- **Only the default `copicograf` generator can be built.** A config naming a
  different one (for example `wide2depth`) renders its options here — the form is
  config-driven — but generation is refused, because that generator is not part
  of this repository.
- The form never invents config keys: a posted field that does not already exist
  in the config is ignored.
- `copicograf` emits `G28 X Y` once, near the top. On Marlin that homes X and Y;
  on GRBL and FluidNC `G28` instead means "move to the stored G28 position", and
  homing is `$H`. That line is left exactly as copicograf writes it — changing
  what a machine does at the start of a run is not something to guess at.
