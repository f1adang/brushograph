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
  `color_order`, each with tray X/Y and an image upload. Each tray's image is
  either **already thresholded** or a **photo**, in which case it is converted to
  a woodcut first (see below).
- **Brushograph Options** — every key under `brushograph`, including the nested
  `moves` speed groups, with explanatory tooltips.
- **Slicer Options** / **Controller Options** — rendered when the config has them.
- **Machine sketch** — a to-scale drawing of bed, image area and trays with
  their entry and drip radii, redrawn as you edit. Trays parked outside the bed
  are called out rather than quietly cropped.
- **Match image** — sets Height, in whole millimetres, from the configured Width
  and the uploaded image's aspect ratio. The pixel grid is mapped onto width x height regardless
  of aspect, so a mismatch stretches the painting rather than fitting it. Warns
  when the uploaded images disagree on ratio, or when the result exceeds
  `max_height`.

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
- **The slicer is told to leave the artwork alone.** OpenSCAD emits it at
  `(0,0)-(width,height)` already, so the slicer gets `--dont-arrange`. Not
  `--center`: that places the *traced content* rather than the canvas, so any
  image whose subject does not run to the edges gets shifted within the frame,
  and on some geometry it refuses to slice at all.
- **The bed is a fiction, so it gets margin.** An object flush with the bed edge
  is rejected as outside the print volume — and PrusaSlicer says so on stdout
  while still exiting 0, which is why an empty result has to be read back out of
  its own output rather than guessed at.
- **`infill_line_distance` is an extrusion width, not a nozzle bore.** Passing it
  as a nozzle diameter makes PrusaSlicer silently reject any value below the
  layer height, exit 0, and write nothing.
- **One layer only.** The extrusion is the painting, so the SCAD extrude height
  is matched to the layer height to avoid slicing the same artwork twice.

### Photo to woodcut

Set a tray's *Image Type* to **Photo** and the upload is converted to woodcut /
linocut black and white before anything else sees it. The rest of the pipeline is
unchanged: it still receives a bold two-tone image to trace.

The output must be pure two-tone with nothing finer than the brush can lay down,
so detail cannot come from grey. It comes the way it does in a real cut, from
**hatching whose density carries the tone** — which also suits the machine, since
hatching is long parallel strokes.

The picture is cut into three bands, at percentiles of its own tones rather than
at a fixed level, so coverage holds steady whether the photograph is bright or
dim:

- **shadows** become solid black,
- **midtones** become hatching that thickens as the tone darkens, cross-hatched
  in the darkest third,
- **highlights** are left as paper.

Hatch spacing is derived from `infill_line_distance` and the output width, so the
thinnest line is always one the brush can paint. Contours are added as knife
lines, but only where they run far enough to be a real boundary: Canny fires on
grass and cloud as readily as on a jawline, and short fragments would become
hundreds of unpaintable dabs.

Five controls — Detail, Hatching, Black/White, Edge Roughness, Contour Lines —
with a **Preview woodcut** button. Painted area is what drives run time, so it is
worth watching: Black/White moves it a long way.

**Detail** drives every stage that discards fine structure, not just the
smoothing: the working resolution, how hard the morphological cleanup presses,
the smallest speck kept, how short a contour may be and still count, and how
many scales of contour are traced (a third, sharper pass appears above 85). At
0 the picture is deliberately coarsened to a poster; at 100 nothing limits what
survives except the brush itself. Across that range the boundary detail in the
finished cut roughly doubles.

Brush width is handed to the conversion in millimetres rather than pixels,
because the working resolution follows Detail — a pixel size computed outside
would be wrong as soon as the slider moved. The picture is never scaled up past
the source: enlarging it would add pixels but no detail.

The noise seed is fixed, so the same photo and settings always print the same.

### Isolating a person or object

When a photo is chosen it is inspected for a subject. If one is found, an
**Isolate** option appears naming what it is ("Isolate 3 people", "Isolate a
prominent object") and how much of the frame it covers. Ticking it leaves
everything outside the subject as bare paper.

Segmentation is done by a salient-object network run through **OpenCV's own ONNX
support**, so it costs no new Python dependency. Two are tried in order and the
first that can be had is used:

| model | size | notes |
|---|---|---|
| `isnet-general-use` | 170 MB | markedly better on cluttered scenes and machinery |
| `u2netp` | 4.4 MB | light second choice, fine on people |

Both are downloaded once into `webui/models/`, which is gitignored, and the
startup banner names the one in use. The larger is worth its size on anything
that is not a person: on a photograph of the machine on a workbench it follows
the gantry rail, the toothed rack and the wiring that the small one blobs over.

**Naming what was found** is a separate question from cutting it out, and takes
two cheap steps:

- Haar cascades find faces. Present means *person*. They are held to a strict
  vote, because at the usual setting the profile cascade found a face on a
  stepper motor and the upper-body cascade agreed — enough to have a photograph
  of a machine announced as a person. Across the test images the frontal cascade
  at its normal setting is right every time and the other two only ever
  contributed that false positive.
- Otherwise a small ImageNet classifier (SqueezeNet, 4.7 MB) is run on the
  cut-out subject. The first 398 ImageNet classes are organisms and the rest are
  artifacts, so the confidence below that boundary separates *animal* from
  *object* directly. The subject is cropped before classifying: a cat fills
  little of a photograph, and asking about the whole frame asks the wrong
  question. Measured across the test set the split is clean — 0.58, 0.60 and
  1.00 for two cats and a dog, 0.00 for the machine, the logo and both photos of
  people. ImageNet has no "person" class, which is why faces are asked first.

### Turning the map into a mask

Two details decide whether the cut-out is usable:

- **Hysteresis, not a single threshold.** The network scores a dark circuit
  board bolted to a machine well below its confident regions, so a level high
  enough to exclude the workbench also excludes the board, while a level low
  enough to keep the board also keeps the clutter behind it. Confident regions
  are grown outward into their doubtful parts instead, which keeps whatever is
  attached to the subject and nothing that merely scores similarly elsewhere.
- **The boundary is snapped to the picture's own edges.** The network answers
  "what is the subject" well and "exactly where does it end" only roughly; on a
  busy background its outline can sweep out into scaffolding and foliage beside
  a head. GrabCut is then given the inside of the mask as certain subject, the
  outside as certain background, and only a band either side of the boundary to
  decide — so it cannot re-open the question of *what* the subject is, only
  where its edge runs. A pass that would eat half the subject is discarded as
  having gone wrong rather than right.
- **Only pinholes are filled.** An enclosed background region is usually a hole
  in the mask — but that description also fits the gap between an arm and a
  torso, which is real background. Filling those indiscriminately put a patch of
  grass between someone's arm and her hip. Only holes small against the subject
  are closed now.

This replaced a GrabCut-based attempt. GrabCut segments on colour, and no amount
of seeding got it past two failures: dark hair against dark foliage was read as
background, so heads came out cropped, and patches of grass and wall that
happened to match the subject's colours were kept. Those are not tuning
problems, they are what a colour model cannot do.

**Without the model** — no network on first run, or the download refused — the
GrabCut path is still there and is used automatically, with the reason logged.
It is noticeably worse; it exists so the feature degrades rather than breaks.

The option stays hidden when nothing is found, or when what is found covers
almost none or almost all of the frame, since isolating gains nothing there.
Tonal bands are measured from the subject alone, so isolating does not wash the
result out.

### Long brush strokes

A watercolour brush wants few long strokes, not raster fill: every extra stroke
costs a lift, a travel and often a trip to the paint tray. Three things shape
that, and the biggest is not in this code.

**`infill_line_distance` is the dominant lever.** It is the gap between fill
lines, so it should be roughly the width the brush actually lays down. Set to a
pen-plotter 0.5 mm it paints the same area ten times over. On the SGMK logo at
151 mm wide:

| spacing | strokes | median stroke | brush lifts | tray dips | painted |
|---|---|---|---|---|---|
| 0.5 mm | 286 | 25 mm | 598 | 318 | 23.8 m |
| 5 mm | 35 | 79 mm | 103 | 74 | 4.5 m |

**Strokes are chained, and every bridge is checked against the shape.** A slicer
emits a fill as many separate extrusion runs even where they are physically
continuous. The adapter rejoins them: exact shared endpoints first, then ends
within `BRIDGE_MULTIPLE` (1.5) line widths — but a bridge is only taken when the
straight move between the two ends stays inside the ink, tested against the
source mask. Bridging without that test drew across bare paper and cost 7% extra
paint; with it the cost is 1.1% and the shape is preserved exactly.

**Bridging further does not pay**, which is worth knowing before reaching for it.
A bridge replaces a lift and a travel with painted distance, and painted distance
is what forces trips to the paint tray. Reaching 120 mm through solid ink saved 5
lifts but added 0.35 m of painting and two tray trips — a clear loss, since a
tray trip costs far more than a lift.

**Strokes are ordered** nearest-first so the brush travels less between them.

### Where the time actually goes

Measured on the SGMK logo at 5 mm spacing: 4.0 m painted, 7.2 m travelled. The
travel is almost entirely round trips to the paint tray, and the number of those
is `painted distance / paint_per_run`. So the two levers that matter are both in
the config:

| `paint_per_run` | tray trips | travel | rough run time |
|---|---|---|---|
| 120-140 (default) | 35 | 7.2 m | 8.8 min |
| 250-300 | 22 | 4.9 m | 7.2 min |
| 500-600 | 16 | 3.4 m | 6.3 min |
| very high (no re-inking) | 10 | 2.2 m | 5.5 min |

Set it to how far the brush can actually paint before running dry. Combined with
`infill_line_distance` matched to the brush, that is where the time goes.

`wall_line_count` is already right at 1: dropping to 0 covers only 65% of the
shape, and raising it to 2 costs 19% more paint for 1% more coverage.

**Paths are simplified** with Douglas-Peucker at a tenth of a line width,
cutting point count by roughly two thirds so the machine moves smoothly rather
than in tiny segments.

### Infill pattern names

The configs use Cura's vocabulary, which PrusaSlicer does not share; and at 100%
density PrusaSlicer rejects its own sparse-only patterns (gyroid, honeycomb,
grid, ...) outright. Of the six names the configs offered, only `concentric`
ever sliced — the rest failed the run. Names are now mapped
(`lines` to `rectilinear`, `zigzag` to `alignedrectilinear`, ...) with a logged
fallback, and the dropdown offers only patterns that work, ordered with the ones
best suited to a brush first.

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
- Backlash compensation is on unless a config turns it off. A config carrying no
  backlash figures still goes through that step, but compensating by zero is a
  no-op, so nothing changes for it.
- `copicograf` emits `G28 X Y` once, near the top. Marlin reads bare axis words
  as "home these axes" and keeps it. GRBL and FluidNC require a value after each
  word and reject the line outright (`Bad GCode number format`, ALARM:17), so it
  is replaced with a comment. It is not rewritten to `$H`: that needs limit
  switches, and a machine without them is zeroed where it stands via FluidNC's
  `startup_line0: G10 P0 L20 …`. Home or zero before streaming.
