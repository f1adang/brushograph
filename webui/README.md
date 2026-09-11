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

The form is organised by how often a setting changes, not by how the config
file is laid out. Which pictures, what they are, how a photo is cut, how large
it is painted and how the brush fills a shape change every run; tray positions,
brush heights, dip depth, radii, backlash and feedrates are set once for a
machine and left alone.

- **The machine** — a to-scale plan of bed, image area and trays with their
  entry and drip radii, redrawn as you edit. Trays parked outside the bed are
  called out rather than quietly cropped.
- **Artwork** — one card per colour in `color_order`, each taking a picture and
  saying whether it is **already black and white** or a **photo**, in which case
  it is cut first (see below) with the tuning controls appearing inline. Then the
  painted size, with **Match image**: it sets Height, in whole millimetres, from
  the configured Width and the uploaded image's aspect ratio. The pixel grid is
  mapped onto width x height regardless of aspect, so a mismatch stretches the
  painting rather than fitting it; it warns when the uploaded images disagree on
  ratio, or when the result exceeds `max_height`.
- **Run** — the fill settings, then Generate G-code, then the path preview. The
  fill settings sit here rather than in machine setup because the stroke
  spacing, the pattern and the wall count are decided per picture about as often
  as per machine, and they belong beside the button that consumes them.
- **Machine setup**, collapsed — tray positions, where the artwork sits on the
  bed, brush heights, loading the brush, backlash, the `moves` speed groups and
  the controller type, and at the end **Download Machine Config**, which writes
  all of it back out as a `.conf`. A config carrying keys this map has never heard of
  still shows them, under **Other settings**.

The two submit buttons report where they are: each has its own status and error
line, because a "Downloaded pinkograph.conf" written into the Run step would be
off screen for someone reading it at the bottom of machine setup.

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
- **Transparency is paper, not black.** An uploaded picture is composited onto
  white before anything looks at it (`images.flatten`). Dropping the alpha
  channel instead leaves whatever is stored underneath, which in a PNG is very
  often black: a logo arrived with a transparent background whose hidden pixels
  were (0.8, 0.8, 0.8), so the whole picture came through nearly black, its
  lettering stopped being darker than what surrounded it, and the counters in
  its O and R disappeared into the letters they belong to. Every entry point
  flattens — the woodcut, the subject finder, the face filter and `to_pbm` —
  because a photo with an alpha channel reaches all four.
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

### Themes

Five, chosen in the footer and remembered per browser. **Default** follows the
machine it is read on, light or dark. **Dark mode** holds dark whatever the room
is doing. **Coconut mode** is husk, flesh and a palm lit from behind, and the
mark in the corner is a coconut. **UwU** is a neon sign with all the lights up:
the ground glows, every edge is lit, and the rules under the headings and the
Generate button run the rainbow.

**Pinkograph** is a port of the machine's own theme rather than an impression of
one. `theme-Pinkograph.gz` sits on the controller's flash and is served over
HTTP, so its values are read from the source rather than sampled from a
screenshot: ground `#0B0014`, panel `#16032A`, strip `#22064A`, control
`#2C0857`, pink `#FF6BB5`, text `#FFEAF4`, dim `#E3A0C0`, cyan `#00F5FF`. The
body carries the same two washes — pink from the top left, cyan from the bottom
right — and every panel is bordered and glowed like a lit tube with the same
three shadows.

The one thing that moves there is `pinkograph-hum`: the navbar's glow swelling
and settling on a 2.6 s ease-in-out. That is what makes the sign look as though
it is breathing — the logo itself has no animation at all, only a recolour. The
same hum runs under the separators here, under the top and bottom bars, and
through the buttons — a filled one throws light around itself and brightens as
it does, an outlined one lights from within and its border comes up with it, so
the whole interface pulses to one clock rather than several. A button that
cannot be pressed does neither, and reduced motion stops all of it.

It is applied to a one-pixel strip beneath each rule rather than to the heading
block: animating the block's own shadow lit a rectangle behind the words and
read as a panel. A button's face is animated as a colour rather than through
`filter: brightness`, which applies to the element's shadow as well and made the
halo shrink as the face brightened, the two halves of the pulse working against
each other. Measured at rest and at the swell, the glow under a rule goes from
33.1 to 48.7, and a button with its halo differs by 25% across half a cycle.

An inline script in `<head>` puts the remembered theme on `<html>` before the
first paint, so a chosen theme never flashes the default one first. Anyone who
had chosen Pinkograph before the rename gets the new one, which is the point of
the name.

**The three drawings follow the theme.** The machine plan is rendered
server-side, so the browser posts its theme with the sketch request and
`sketch.py` picks a palette to match — surfaces and annotation only. The G-code
preview is a canvas, so it reads `--sheet`, `--line-soft`, `--bad` and
`--preview-cup` off the stylesheet at draw time. The cut in the photo-tuning
panel is the third: it is two tones and both are surfaces of the interface — the
paper it will be painted on and the mark the brush leaves — so `app.py` prints
it on the theme's paper in the theme's ink, reusing `sketch.PALETTES` so there
is one set of server-side theme colours rather than two. Changing the theme
redraws all three, though the cut only when one is already on screen: that one
is a round trip and a reconversion.

`--preview-cup` is a named token rather than a borrowed one. The trips into the
cups were briefly drawn in `--ink-dim`, which in a dark theme is the brightest
thing on the canvas: the dips shouted over the painting. Each theme now names a
colour that is present but quieter than paint — Pinkograph names the theme's own
green `#39FF14`, which no tray holds.

One thing stays fixed across all five: **colour means pigment.** Cyan, magenta,
yellow and water identify trays and nothing else in the interface is saturated,
so a coloured mark always stands for paint in a cup. The themes restyle every
surface and every annotation, and leave the paint alone.

Black is the one paint that cannot be left alone. On the three dark papers it is
the paper — `#23282f` on `#1d2120` is a contrast ratio of 1.08, which is to say
invisible — and that is not only the preview: the same colour draws the tray
dot, the left edge of the artwork card and the bay in the plan view, so a black
cup had no mark anywhere in three of the five themes. `--k` is therefore a
per-theme colour like the rest of the surface, the plan's palettes carry a
`key` beside their `accent`, and the preview reads `--k` rather than holding a
black of its own. The rule survives with one exception, and the exception is what lets
black read as paint at all rather than as nothing.

Coconut declares `color-scheme: light` although its ground is dark, because
every panel is pale and the form controls sit on those; under a dark scheme the
browser drew unchecked boxes as filled dark squares on cream, which read as
ticked. Pinkograph and UwU declare dark, because their panels are.

Everything that moves stops under `prefers-reduced-motion` — the machine's own
theme says the same, in the same words: flashing signs are a migraine risk.
Every text colour in every palette clears 4.5:1 against what it sits on.

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

### The opening of a job

Two things happen before the first stroke.

**The brush is lifted before anything moves sideways.** The file opens with
`G90`/`G21`, the normal feedrate and `G00 Z<safe>` — the safe height is the
larger of `go_in_tray_lift` and `move_to_other_shape_lift + canvas_height`.
Where the brush was left by the last job is not known, so nothing may travel
across the bed until it is up.

**The brush is loaded before the first stroke of every colour.** copicograf
re-inks only after `paint_per_run` (120-140 mm) has been laid down, so the
opening strokes used to be painted with whatever was on the brush — which is
nothing, because each tray *ends* by washing it and parking it in the water.
That is what a colour change wants, but it means the next colour starts by
painting with water. `prepare_path` now takes `pickup_at`, and the pipeline
passes the point that colour's painting starts from, so the trip to the tray
ends with the brush arriving there loaded rather than touching down somewhere
else and leaving a mark.

A colour change therefore reads: wash (three dips in the water), lift clear,
dip the next colour, shed the drip it comes up with, travel to the first stroke
of that colour, and paint. How the drip is shed depends on the containers: a
round cup is wiped on its rim afterwards, a rectangular one has done it already
on the way up its stairs.

Two things used to happen in the middle of that and no longer do. The wash
ended by crossing back to the canvas origin and touching the paper, which left
a water mark in the corner of the artwork at every colour change — it is now
told not to return (`append_go_in_tray(..., return_to_canvas=False)`), and stops
over the water where it already is. And the brush was then parked down in the
water, which is worth doing only when nothing follows: between colours it is
already over the water and the next thing it does is go for paint. `park` is
now passed only for the last tray, so a job still ends with the brush standing
in water rather than drying with paint in it.

This is also what keeps the first cross-bed travel at the safe height. The trip
to the tray lifts to `go_in_tray_lift` before it moves, where the first move of
the painting itself only lifts by `move_to_other_shape_lift` — two millimetres,
which is clearance over the paper, not over a tray rim.

### Wiping the brush

After a pickup from a **round** cup the brush carries a drop that would
otherwise land on the paper. It is wiped by dragging the bristles over the rim
at `remove_drops_lift`, and it happens **twice, once on each side**: wiping only
where the brush happens to be leaving strips the drop off one side and leaves it
on the other, and that one falls on the painting.

How far the drag goes is `remove_drops_radius` and how fast is the config's
`moves.remove_drops` group. Neither is decided in the code — an earlier version
carried the brush a few millimetres past the radius and crossed the rim at a
fixed 300 mm/min, which took both settings out of the config's hands.

The direction is along the row the cups sit in, taken from the nearest other cup
rather than assumed to be X, so a machine that arranges its cups differently
still wipes along its own row. Square to the way the brush leaves is the other
reading of "each side" and it is wrong here: the brush leaves towards the
canvas, so square to that runs along the front edge of the bed and off it — the
first attempt wiped to Y = -13.

The wash dips do not wipe at all: they pass `remove_drop=False`, because a brush
being rinsed has nothing to shed on the way out.

Neither does a pickup from a **rectangular** bay, and for the same kind of
reason: it has already been wiped. The swipe up the stairs drags the bristles
along the floor and out of the paint over the length of the bay, which is the
rim wipe's own motion over a better edge. Two more passes over the rim
afterwards put paint back on a brush that has just been drawn clean — and on
34 mm centres they reach into the bay next door to do it. So `remove_drop` is
ignored when the containers are modern, and `remove_drops_radius` is a
round-cup setting that nothing else reads.

### Round cups and rectangular ones

Two paint holders exist, and `brushograph.cup_shape` picks between them.

**Classic** is the round cup the machine was built around. The brush goes down
the middle — the point furthest from the wall in every direction — sweeps a
chord down in the paint where the bristles are inside the cup, returns to the
middle and lifts.

**Modern** is the printed CMYK holder, a 192 × 46.5 × 4 mm plate with five bays
labelled W C M Y K. Slicing the model at mid-height shows six 1 mm ribs at X
−24, 20, 54, 88, 122 and 156, and the bays are the gaps between them. Bisecting
to each wall gives the design figures exactly: the water bay **39.2 mm** across,
the four colour bays **29.2 mm**, centres at −2, 37, 71, 105 and 139, and every
bay opening **35.1 mm** deep in Y, out through the back edge of the plate.

The water bay is the wide one, by 10 mm, so that the brush has room to be
rinsed. That is `cup_width_water`, separate from `cup_width`, and the plan view
draws each bay at its own — drawn alike, the one cup that is a different size
was the one you could not pick out. `cup_depth` stays at 30 rather than the
measured 35.1, which keeps the swipe inside the opening.

Its floor is a staircase, so loading is one swipe from the deep end to the
shallow one, rising as it goes:

    G00 X53 Y-4      ; deep end, in front
    G00 Z-4          ; down into the paint, at dip_depth
    G01 X53 Y16 Z1   ; draw the length of the bay, climbing to cup_swipe_exit_z
    G00 Z8           ; clear

It is one interpolated move rather than a tread-by-tread staircase. The bristles
flex over the steps, and a stepped path would need the step count and their
heights — which **the STL does not carry**. Its bays are open through the plate:
the model is a frame, the stepped floor is not part of it. So `cup_swipe_exit_z`
is measured on the machine, not derived. It defaults to 1 mm rather than 0
because 0 is `canvas_height` here, and a brush leaving the cup at paper level is
both wrong physically and drawn as painting in the preview.

The swipe runs front to back, finishing on the canvas side, so the brush leaves
the cup already pointed at the paper. With the stock config its near end is
Y −4.5, which looks like the off-the-bed fault the wipe had — it is not: the
classic sweep reaches Y −4 from the same `tray_y` of 6 and `tray_enter_radius`
of 10, and has done so on this machine all along. Both then read about a
millimetre lower in the file as Y backlash take-up.

The wash goes through the same motion, so in a rectangular bay its three dips
become three swipes the length of the water. That rinses more, not less, and
it still wipes nothing on the way out (`remove_drop=False`).

### The fifth cup

The holder has a bay for black, so the machine paints CMYK rather than CMY. Very
little had to be taught that: `CMYK_TO_TRAY` has mapped `K` to the `kroma` tray
since the original project, and the form, the pipeline and the preview are all
built from `color_order`, so a fourth colour flows through them on its own. What
was missing was everything that had only ever been written for three.

The first thing missing was the cup itself. The form is built from the config,
so a machine file written before the black bay existed has no `kroma` tray, no
`K` in `color_order`, and therefore no card to upload a black picture to and no
row to put its position in — with no way to gain either, which is the same
reason `ALWAYS_OFFERED` exists for settings. `with_defaults` now offers the
black cup the same way. Where it *is* remains a measurement, so the offered
position is a guess: one more step along the row the other cups are in, the gap
between the last two of them. On a holder-spaced config that lands it exactly
right; on a config still using round cups 45 mm apart it lands at 188 on a
151 mm bed, which the plan view flags as off the bed. A wrong number in front of
you beats a missing one. Nothing is painted from the cup until a picture is
uploaded for it — a tray in `color_order` with no image is skipped — so an
unused black cup costs one row in the setup and nothing else.

The bay spacing is not a machine measurement, because the holder is one piece:
its five bays are 34 mm apart centre to centre, the first colour 39 mm from the
water, and only where the whole thing sits is anyone's to decide. Those offsets
are `MODERN_BAY_OFFSETS`, and **Auto-space containers for modern holder** under
the container positions applies them from wherever the water cup has been put.
It shows itself only when the modern holder is the one selected; there is no
such thing as the holder's spacing for loose round cups.

Five cups on 34 mm centres span 141 mm, which is why `pinkograph.conf` now
starts its water bay at X 8: the bed is 151 mm wide, so anything past 10 puts
the black cup out of reach. `small_machineM2.conf` was already far enough left.

Three things had been written for CMY alone and are not any more:

- **The tray dot** was styled for `[data-tray="black"]` and `[data-tray="key"]`,
  neither of which is the key this project uses. The K cup is keyed `kroma`
  everywhere, so its dot fell through to the default grey. Underneath that, the
  colour of black was written once, for white paper, in three separate places —
  `--k` in the stylesheet, `TRAY_FILL` in the plan view, `TRAY_COLOURS` in the
  preview. At `#23282f` on the dark themes' `#1d2120` that is a ratio of 1.04,
  so the dot, the card's left edge, the bay in the plan and the painted stroke
  were all simply the background. Each of the three now takes black from its
  own theme, and the preview reads `--k` rather than keeping a fourth copy.
- **Tray numbering** counted `additionals`, which sits in the `trays` dict but
  is a group of colours rather than a cup. With four trays declared before it
  nothing showed; the fifth came out as "Tray 5". Colour trays are now named
  after the channel — Cyan (C), Black (K) — and the positional name is the
  fallback for the additionals, which have no channel to be named after.
- **The plan view** called the cup `kroma`, which is this project's word and not
  one stamped on the holder. It says `black`.

Cups this close together are also why the rim wipe had to go for the modern
holder, quite apart from being redundant after the stairs. At 34 mm centres a
`remove_drops_radius` over 17 mm carries the wipe into the bay next door: the
20 mm that suited cups 45 mm apart put the wipe from the black bay at X 129,
inside the yellow bay, and at X 169, which is 18 mm past the end of a 151 mm
machine. Round cups 45 mm apart still wipe, and still read that setting.

The machine view draws whichever is configured — circles with their sweep, or
rectangles with their treads and an arrow along the swipe — and redraws as soon
as the picker changes. It draws every bay at `cup_width`, including the water
one, which on the printed holder is the wider of the two.

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

## Sending a job to the machine

Once a run has produced G-code the preview offers three things: download it,
**Send to machine**, or **Upload & start**. The approach is
[openBatak-Assembler](https://github.com/openBrushograph/openBatak-Assembler)'s,
which does this from the page:

- `POST <host>/upload` with a `FormData` carrying `path` (`/`) and `myfile`
  (the blob, named). The controller's own web UI sends a more elaborate form —
  `myfiles`, a size field named after the full path with an `S` appended, a `T`
  for the timestamp — and an earlier version of this copied that. The short form
  is what openBatak-Assembler uses and it is enough.
- `GET <host>/command?cmd=$SD/Run=/<name>` to start it, **with a websocket
  open to `ws://<host>/` (subprotocol `webui-v3`) while it goes**. FluidNC will
  not take a command otherwise: with none open, `/command` answers
  `500 WebSocket dead`. That is precisely what an upload which lands but never
  starts looks like, and it is why the file appeared on the card while the job
  did not begin. The websocket is not a transport for the file — that is still
  a plain POST — it is what makes the controller listen.
- **Two seconds between the two.** The card needs a moment to commit the file
  before the controller can be told to run it.

What comes back over that websocket is the machine's own console, so the page
reports what the machine said rather than what it was told: `$SD/Run sent. The
machine says: <Run|MPos:0.000,0.000,0.000|FS:0,0|SD:0.00,/fabrik_c1_infill.gcode>`.

Both go out as `mode: "no-cors"`. FluidNC answers a cross-origin preflight
without an allow-origin header, so a normal fetch cannot read its reply — but a
no-cors request is still delivered, and `multipart/form-data` is CORS-safelisted
so it needs no preflight at all. The cost is an opaque response: the page can
say a file was sent, never that it arrived, which is why **Send to machine**
suggests checking the machine's file list.

Sending from the page rather than from this server is what makes it work at
all. The machine shares a network with whoever is reading the page, not
necessarily with wherever the server is.

**The name is resolved here, not in the browser.** Chromium looks a `.local`
name up through mDNS; Firefox returns a bare `NetworkError` for the same
address. So the page asks `GET /machine/resolve?host=` first and then talks to
the address it gets back. This server is on the same network and its resolver
does know the name. Nothing is fetched from the machine by that endpoint — only
its name looked up — and if it cannot answer, because the server is elsewhere or
the hostname is already an address, the page carries on with what was typed.

The one thing no amount of no-cors fixes: a page served over https may not
reach a machine over http, and the browser blocks it as mixed content. That is
detected and said plainly rather than failing silently.

### The preview is swept, not spread

The drawing's bounds used to come from `Math.min(...xs)` over one argument per
coordinate. A real job has hundreds of thousands of them, and past about 124,000
arguments — some 62,000 moves — the call stack gives out and the preview dies
with *Maximum call stack size exceeded*. A small job draws, a large one does
not. The bounds are swept in a loop now, and a 100,000-move file draws.

### The preview says when it cannot draw

The file is offered for download before the preview is drawn, so a preview that
fails leaves a working download button above an empty box. It used to fail into
`console.error` alone, which is no use to anyone not holding the console open;
it now says so on the page. And a file with no `G0`/`G1` movement in it gave
infinite bounds, a NaN scale, and a canvas whose every draw call was quietly
ignored — an empty box and no complaint. That case is named now rather than
drawn.

The hostname lives in the config under **Connection**, defaulting to
`fluidnc.local`. A config written before that section existed gains it, like
every other always-offered setting.

## Sessions outlive a restart

An uploaded config is written to `webui_sessions/<session id>/` and addressed by
the session id in the cookie, so the id has to mean the same thing tomorrow that
it meant today. The secret key that signs that cookie is therefore kept in
`webui_sessions/.secret_key` (mode 600, and the directory is gitignored) rather
than generated per process.

Generating it per process is what the app used to do, and it fails in a way that
does not look like a session problem at all: restart the service, every open
page gets a new session id, and the next thing it asks for is a config the
server can no longer find. The file is still on disk — under the previous id.
The error read `config not found: pinkograph.conf` while the config sat right
there, which sends you looking in entirely the wrong place. A missing upload now
says that it is a missing upload, and what to do about it.

Presets are unaffected either way: they are read from the repo root and have
nothing to do with the session.

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
