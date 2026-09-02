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

Flask, Pillow, NumPy and OpenCV are the dependencies. Nothing else has to be
installed on the machine — the G-code step is pure Python and OpenCV.

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

### Settings the form always offers

The options form is built from the config's own keys, which means a machine file
written before a setting existed — or by hand, or by an older version — simply
has no control for it, and no way to gain one. A short list is therefore always
offered whatever the config carries: dip depth, and the three backlash settings.

A config that names them keeps its own values; one that does not gets a dip no
deeper than the old fixed one and a modest 0.5 mm of backlash either way to tune
from. Downloading the config writes them out, so a setting made in the form is
not silently dropped on the way back.

These are filled in, never overridden. A config that states a value keeps it,
including a `false`: backlash compensation opens ticked when the config says so
or says nothing, and unticked when the config says not to. The defaults exist so
a setting the config never mentions still has a control, not to overrule one it
does.

### Dip depth

How far the brush descends into a cup was fixed at Z −4 in `copicograf`, which
is deeper than a shallow petri dish wants — the brush went in past its ferrule.
It is now `brushograph.dip_depth` in the config, so it appears in the form like
any other setting. A config that does not mention it still gets −4.

The preview reads a dip as *any* Z below the canvas rather than a fixed depth.
Keyed to −4, a shallower dip would have been drawn as painting and left out of
the dip count.

### What the preview leaves out

Backlash compensation injects a corrective move at every reversal — 130 of them
in a small test job. Those are for the machine's slack, not part of the path that
was asked for, and drawing them buries the artwork in strokes that are not in
it. The preview skips them, and shows the path as it would be without
compensation. Checked against the same file with those lines physically removed:
the parsed moves are identical.

### No calibration preamble

`copicograf` opened every run by mixing the colour, washing the brush and
loading it, each trip ending with a touch on the paper at the origin. In a job
that repeated once per tray and left the dots inside the artwork's coordinate
space, so generated jobs are produced without it.

**A job therefore does not prime the brush.** It starts painting with whatever is
on it, so a dip has to come first.

The closing wash at the end of each tray is untouched, and still leaves one dot
at the origin per tray.

### G-code preview

Below the options is a preview of the path the brush will take, drawn as soon as
a file is generated. Painting strokes are coloured per tray, travel is faint
grey, and trips into the cups show up as orange bursts. Play or scrub through
the job to see the order of work, with a marker on the brush's position.

Alongside it: metres painted, metres travelled, brush-downs, cup dips, move
count and a rough time estimate from the config's own feed rates. A `.gcode`
file from anywhere can be dropped in to inspect it, whether or not this made it.

Each tray's block is marked in the output with a `; tray <name>` comment, which
is what lets the preview — or a person reading the file — tell which colour goes
where.

Two actions:

- **Download Config** returns the edited config as a `.conf`. Types are
  preserved and keys the form does not cover are passed through untouched.
- **Generate Gcode** runs the pipeline and offers one G-code file, named after
  the picture and the colours that painted it:
  `vali_letten_c1_infill.gcode`. The numbers are the tray numbers shown in the
  form, so a file can be matched to the run that made it without opening it, and
  `_infill` says whether the shapes were filled or only outlined. With several
  trays the name carries each in painting order — `photo_c1_c2.gcode`. The file
  is not saved automatically: it is drawn in the preview first and downloaded
  from a button, so a run can be looked at before it is kept.

An **infill line distance of 0** means no infill: outlines only. The brush still
has a width — the perimeter and the woodcut's finest mark are both measured in
it — so a nominal 1 mm stands in, the config offering no other figure to take
one from. On the test logo, at the same stroke width, that is 4.4 m of painting
against 11.9 m filled.

## The G-code pipeline

Per tray: threshold → distance transform → rings → chaining → `copicograf`, then
all trays are concatenated and optionally backlash-compensated. Trays are
prepared in parallel and painted in `color_order`.

This used to run threshold → `potrace` → SVG → OpenSCAD → STL → PrusaSlicer →
adapter, which meant three external programs, a 2D → 3D → 2D round trip, and
about 13 s a tray. It is gone; see **Why the 3D round trip went** below.

Notes on things that needed care:

- **The ink/paper split is found per image**, with Otsu's method, on the darkest
  colour channel. Not a fixed "anything not almost-white": a stylised or scanned
  print is often on cream paper — one measured (237, 229, 216) — and the fixed
  rule turned 99.9% of such a file into one solid shape that painted the whole
  canvas. Thresholding the darkest channel rather than the brightness keeps a
  saturated ink like yellow on the ink side, since it is dark in at least one
  channel however bright it looks. A file that comes out more than 97% ink is
  flagged in the log.
- **Small pictures are enlarged before the geometry is worked out.** The
  distance transform, the contours and the rescue pass all resolve to whole
  pixels, so when a picture is small and the painting is large the brush is
  barely one pixel wide and there is nothing left to place an outline with. A
  259 px picture painted 151 mm wide puts the brush at 0.86 px. Measured over a
  corpus of ten photographs, working at six pixels to the brush brought the
  worst cases from 12% and 16% of the ink left unpainted down to 3.3% and 2.4%,
  and cut the paint landing on bare paper by half; pictures already above that
  resolution are untouched. It costs about a third more time on the small ones.
- **Scale comes from the pixel grid.** The image is mapped onto exactly
  `(0,0)-(width,height)` in millimetres, so the PNG's DPI metadata is irrelevant
  and the painting comes out at the size the config asks for.
- **The outline sits slightly further in than half a stroke** (`EDGE_BIAS`,
  0.8). Exactly half would put the brush's edge on the shape's edge in theory;
  in practice both the stroke and the traced edge are quantised, which leaves a
  hairline of bare paper all the way round. Measured over a woodcut and a line
  drawing, 0.8 gives the best coverage for the least paint over bare paper.
- **Rings are simplified by 0.75 px at source** (`SIMPLIFY_PX`). A contour read
  off a raster climbs every diagonal as a staircase and each step is a point in
  the G-code. Straightening within a pixel cut the points by 42% and the file by
  30%, and moved coverage by 0.1 points.
- **`infill_line_distance` is the stroke width** — the gap between adjacent fill
  strokes, which for a brush is the same thing.

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
- **midtones** become hatching that thickens as the tone darkens,
- **highlights** are left as paper.

#### The hatching follows the form

A cut is made with a knife travelling along the shape, so its lines curve around
a cheek and run the length of a limb. Straight stripes at a fixed angle — and
the lattice you get from crossing two of them — read as a screen laid over the
picture rather than as something carved.

So the lines follow the picture's own directions. The structure tensor gives, at
every pixel, the direction the form runs in; a coarse noise field is then
smeared along that flow, and the streaks that come out are continuous, bend with
the contours and fan around features. Where an image has no direction of its own
— an open sky, a flat wall — the field falls back to a steady diagonal, so those
areas still read as cut rather than blank.

Two ratios decide whether a mark looks carved. Spacing comes from the brush, so
the lines stay paintable. Length against width comes from how far the noise is
smeared against how coarse it is: short smears over coarse noise give dabs, long
smears over fine noise give lines. The streaks are grown at a reduced working
size and scaled up — following a flow field costs with the square of the
resolution, and the pattern is smooth enough to lose nothing on the way back.

This suits the machine as well as the eye: flowing lines are long and
continuous, where a cross-hatch lattice is thousands of short crossing segments.
One photograph that way is 125 brush-downs for 3.1 m of painting.

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
much of the gradient range counts as an interior line. At 0 the picture is
deliberately coarsened to a poster; at 100 nothing limits what survives except
the brush itself.

The control has to *feel* gradual, which means no stage may switch on at a
point. Three things had to go for that:

- Extra Canny passes gated on `detail > 55` and `detail > 85`. A whole layer of
  edges appearing at once took a face from line drawing to near-solid in one
  step of the slider — 16% more ink between 55 and 60. Interior lines now come
  from gradient strength above a percentile that slides the whole way, so they
  arrive a few at a time.
- The bilateral filter's pixel window, which has to be a whole odd number and
  jumped from 5 to 3 between 80 and 81. Smoothing is set by a continuous sigma
  instead, and OpenCV derives its own window.
- Rounded Canny thresholds. Its hysteresis is sensitive enough that one integer
  step in the level moved the ink by 2.5%, so they are passed as floats.

Measured on the photograph that showed the problem: stepping the slider one
percent at a time, the largest change in painted area is now 2.4%, against 16%
before, and the curve rises steadily from 28% to 47% rather than sitting flat to
55 and then leaping.

Brush width is handed to the conversion in millimetres rather than pixels,
because the working resolution follows Detail — a pixel size computed outside
would be wrong as soon as the slider moved. The picture is never scaled up past
the source: enlarging it would add pixels but no detail.

The noise seed is fixed, so the same photo and settings always print the same.

#### Stroke width

Every mark and every gap between marks is measured in `min_feature`, the brush's
width in working pixels. `woodcut.STROKE_BOLDNESS` (1.35) scales that, so the
whole cut scales together — broader strokes, laid proportionally further apart —
rather than fattening lines over an unchanged layout. It darkens the picture a
little (50% ink to 57% on a test portrait), because marks grow at the ends as
well as across and speckle that was separate dots merges. Past about 1.5 the
merging starts eating fine structure such as hair.

#### Insta Face Filter

Offered when a face is detected. A woodcut has two tones, so everything the
photograph does with grey has to fall on one side of a threshold, and a face lit
from one side lands mostly on the black side: half of it fills in as one solid
shape and the likeness goes with it.

**Finding the face.** The Haar cascades OpenCV bundles only see a face looking
at the camera or squarely side-on. A photograph of someone glancing down was
reported as an "object" and the filter did nothing at all. Rotating the picture
to chase the tilt is not the fix — the sweep found a face on a photograph of a
machine, which is exactly the false positive the cascades are tuned to avoid.
YuNet (`cv2.FaceDetectorYN`, a 230 KB download) finds the downturned head at
0.91 confidence, gives tighter boxes on every test image, and still finds
nothing on the machine. The cascades remain the fallback when the model cannot
be fetched.

**Evening the light.** The lighting is estimated by blurring and divided back
out. Dividing rather than subtracting keeps dark features dark *in proportion* —
an eye at a third of the brightness of the cheek is still a third of it
afterwards. Two details decide whether it works:

- **It is estimated over skin only**, by blurring the skin and its weight
  together and dividing (a normalised convolution). Blurring the picture flat
  instead let the dark hair above and the collar below drag the estimate down,
  and the face came out lifted past level — the shadowed side brighter than the
  lit one.
- **The scale matters more than anything else here.** `_SIGMA_FRAC` is the
  width the lighting is estimated at, as a fraction of the face. Too wide and
  the estimate flattens out the very gradient it is meant to find; too narrow
  and it follows the eye sockets instead of the light. Measured as the
  brightness difference across the skin of a portrait:

  | scale | portrait | second portrait |
  |---|---|---|
  | 0.35 | −51.6 → −34.9 | 32.6 → 22.2 |
  | 0.22 | −51.6 → −22.9 | 32.6 → 10.2 |
  | **0.12** | **−51.6 → −8.9** | **32.6 → 6.3** |

**Smoothing puts the features back.** A bilateral filter takes out pore-scale
texture; whatever it removed that was *strong* was a feature rather than skin,
so it is added back with a weight that rises with the size of the detail. An
eyelash returns in full, a pore not at all.

**Only skin is touched.** The face's own colour is measured from the ellipse and
used as a weight, so hair, glasses, a collar and the background behind the head
keep the tone they had — without this the division hauled the dark background up
towards mid grey and left a bright halo round the head (drift with it: 0.5 grey
levels). On a greyscale photograph there is no colour to tell skin from anything
else, and a clamp on the gain is what keeps the halo away then (drift: 0.1).

Applied repeatedly the correction settles rather than running away
(−51.6 → −8.9 → 3.3 → 6.0), so a face that is already evenly lit may still be
moved a few levels either way. One pass is what the checkbox does.

### Checkboxes post two values

Every checkbox in the form is paired with a hidden field carrying `false`, since
an unticked box posts nothing at all. A ticked one therefore arrives as
`["false", "true"]`, and anything reading it with `form.get()` — which returns
the *first* value — sees every box as off, however it was set. Read them with
`getlist()[-1]`. `apply_form` and `_flag` both do.

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
  where its edge runs. The refinement may only *retract* the boundary, never
  extend it: allowed to push out as well, it claimed sunlit boardwalk beside an
  arm, which matches skin closely enough to fool a colour model. What the subject
  reaches is the network's call. A pass that would eat half the subject is
  discarded as having gone wrong rather than right.
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

**Strokes are chained, and every bridge is checked against the shape.** A fill
comes out as many separate rings even where they are physically
continuous. They are rejoined: exact shared endpoints first, then ends
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

The configs use Cura's vocabulary, which named more patterns than a brush can
usefully draw. They collapse onto the two that mean something here —
`concentric`, rings following the shape, and `lines`, straight parallel strokes
— with a logged fallback, and the dropdown offers only patterns that work,
ordered with the ones
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

### Every shape gets a stroke

A shape narrower than the brush gets no outline — there is nowhere to put one —
so a rib, a hairline or a stroke of lettering would simply disappear.

Whatever the strokes leave unpainted is therefore skeletonised, and its
centreline is added as a stroke. The centreline is the one line a brush can lay
in a shape thinner than itself, and laying it is closer to the drawing than
leaving the shape blank. Specks below about half a brush width are left alone: a
stroke there is a blot.

This matters most with infill off, where perimeters are the only paths, but it
runs either way — a thin shape is no more paintable when the fill is on.

### The stroke's first segment

`copicograf` treats the first coordinate after a pen-down marker as "go there,
then lower". The adapter was emitting the start point before the marker and the
rest after, so the brush came down at the *second* point and the opening segment
of every stroke was travelled dry. On a stroke of many points that is a small
loss at one end; on a two-point stroke — which is what a thin shape's centreline
simplifies to — it is the whole stroke.

The start point is now repeated after the marker. On the line drawing this took
painted distance from 2.66 m to 3.67 m, and it is why the centrelines above
appeared to do nothing until it was fixed.

### Why the 3D round trip went

The pipeline used to trace the bitmap to vectors (potrace), extrude those to a
solid (OpenSCAD), and slice the solid back to 2D paths (PrusaSlicer) — three
external programs to do a job that is entirely two-dimensional. On one tray,
85% of the time went to two of them:

```
  5.20s  53.2%  openscad
  3.10s  31.8%  PrusaSlicer
  0.29s   3.0%  adapt_for_copicograf
  0.06s   0.6%  to_pbm
```

Both are single-threaded on one object with one layer, which is what made
generation feel single-threaded on a many-core box.

**Splitting the work does not help.** Three separate attempts all hit the same
wall — in a real picture one connected shape is most of the drawing:

| approach | speedup | why it stops there |
|---|---|---|
| slice connected components in parallel | 1.16× | largest component is 68–82% of the boundary |
| Shapely offsetting across threads | 1.05× | scalar `buffer` holds the GIL |
| Shapely offsetting across processes | 1.06× | one polygon is 92–96% of the work |

So the answer was a better algorithm rather than more cores.

**The distance transform.** Label every ink pixel with its distance to the
nearest bare paper. An outline inset by *d* is then simply the contour of "at
least *d* from the edge", and a concentric fill is the same thing at
*w*/2, 3*w*/2, 5*w*/2 … So one distance transform plus a threshold per ring
yields the whole fill — and the rings do not depend on each other, so they are
traced in parallel, which OpenCV does with the GIL released.

That is 7–11× quicker than the polygon offsetting on its own, and 9–15× with
threads. End to end against the chain it replaced:

| | external chain | distance transform |
|---|---|---|
| woodcut, one tray | 13.1 s | **1.8 s** |
| line drawing, one tray | 19.2 s | **2.3 s** |
| woodcut, three trays | 29.3 s | **5.3 s** |

It also paints better, which was not the point but is the more useful result.
Two bugs turned up on the way: the concentric fill offset before emitting, so
the ring just inside the perimeter was never drawn; and the thin-shape rescue
judged whole shapes rather than what was actually left bare, so a line whose
broad part got an outline kept its thin part blank. On a woodcut:

| | external chain | distance transform |
|---|---|---|
| ink left unpainted | 9.5% | **1.6%** |
| strokes (each one a lift and a re-ink) | 1672 | **1017** |
| median stroke | 3.6 mm | **9.6 mm** |
| longest stroke | 1753 mm | **3941 mm** |

Longer strokes and fewer of them is exactly what a brush wants. On line art the
coverage still improves (6.2% → 4.2% unpainted) but it takes more strokes than
the slicer did (2371 against 1740), because a drawing made of hairlines is
mostly centrelines however it is worked out.

### Writing what copicograf expects

`copicograf.prepare_path()` decides the brush is on the canvas by matching two
exact lines, `G1 F600 Z1` and `G1 F600 Z6`, which only `cura-slicer` emits.
Anything else leaves `brush_on_canvas` at `False`, and the result is one
continuous scribble with no dips. Rather than change that matching,
`gcode_pipeline.write_brush_paths` emits strokes around those markers, so
`copicograf.py` is untouched.

It also repeats the first point after the pen-down marker: `prepare_path`
consumes the first coordinate it sees as "move there, then lower", so without
the repeat the first segment of every stroke was being lost.

`Copicograf.__init__` also takes `gcodes=[]` as a mutable default, shared across
instances; the pipeline always passes an explicit list so one run cannot append
onto the previous one.

## Assets are never cached

Static URLs carry the file's modification time (`webui.js?v=1788098129`) and
every response is sent `no-store`. Editing a script and reloading is otherwise
not enough — the page keeps the copy it already parsed, and a stale copy is
indistinguishable from a bug in the new one. Changing a file changes its URL, so
the browser has to fetch it.

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
