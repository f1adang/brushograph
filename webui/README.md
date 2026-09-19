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

Everything is driven by a machine config (`.conf`, JSON). Pick one that someone
has kept on the server, or upload your own, and the whole options form is
**generated from that file** — sections, fields, types and defaults all come from the config, so
a config carrying different keys brings its own fields with it.

The form is organised by how often a setting changes, not by how the config
file is laid out. Which pictures, what they are, how a photo is cut, how large
it is painted and how the brush fills a shape change every run; tray positions,
brush heights, dip depth, radii, backlash and feedrates are set once for a
machine and left alone.

- **The machine** — a to-scale plan of bed, image area and trays with their
  entry and drip radii, redrawn as you edit. Trays parked outside the bed are
  called out rather than quietly cropped. One collapsed panel sits under the
  plan, **Machine setup**, because all of it is about the machine rather than
  about a picture: the **Model** first, then the connection and controller
  type, containers, their positions, **Canvas** (where the artwork sits
  on the bed), **Brush control**, **Paint management**, backlash and the
  `moves` speed groups. Then **Download Machine Config**, which writes all of
  it back out as a `.conf`, and last the **Macro generator** — `zero.g`,
  `home.g`, `paper.g`, `clean.g` and `calibrate.g`, built from the settings
  above it (see below). A config carrying keys this map has never heard of
  still shows them, under **Other settings**.
- **Artwork** — a **colour photograph** that is converted to CMYK and thresholded
  into the four process plates, and/or one card per colour in `color_order`, each
  taking a picture and saying whether it is **already black and white** or a
  **photo**, in which case it is cut first (see below) with the tuning controls
  appearing inline. A per-tray picture replaces the plate that colour would have
  received from the photograph. Then the painted size: Height follows, in whole
  millimetres, from the configured Width and the aspect ratio of the first
  picture loaded, recomputed whenever a picture is chosen or Width changes. The
  pixel grid is mapped onto width x height regardless of aspect, so a mismatch
  stretches the painting rather than fitting it; a note warns when the uploaded
  images disagree on ratio, or when the result exceeds `max_height`.
- **Run** — the fill settings, then Generate G-code, then the path preview. The
  fill settings sit here rather than in machine setup because the stroke
  spacing, the pattern and the wall count are decided per picture about as often
  as per machine, and they belong beside the button that consumes them.

The two submit buttons report where they are: each has its own status and error
line, because a "Downloaded pinkograph.conf" written into the Run step would be
off screen for someone reading it at the bottom of machine setup.

### Settings the form always offers

The options form is built from the config's own keys, which means a machine file
written before a setting existed — or by hand, or by an older version — simply
has no control for it, and no way to gain one. A short list is therefore always
offered whatever the config carries: dip depth, and the five backlash settings.

A config that names them keeps its own values; one that does not gets a dip no
deeper than the old fixed one and a modest 0.5 mm of backlash either way to tune
from. The two far-end figures are the exception to a flat default: a config
carrying 1.9 mm of X play and no reading at the far end of the bed is one whose
play was measured once, so it is given 1.9 there too — filling in 0.5 beside it
would invent a slope nobody read off a sheet, and the file would come out
compensated for a machine that had not been measured. Downloading the config
writes them out, so a setting made in the form is not silently dropped on the
way back.

These are filled in, never overridden. A config that states a value keeps it,
including a `false`: backlash compensation opens ticked when the config says so
or says nothing, and unticked when the config says not to. The defaults exist so
a setting the config never mentions still has a control, not to overrule one it
does.

### Model: Mini or 𝔐𝔦𝔨𝔯𝔬

openBrushograph_hardware V6.0 builds two machines from one parametric gantry:
the **Mini**, which every config so far was written for, and the **𝔐𝔦𝔨𝔯𝔬**. The
Model picker sits at the top of Machine setup, and a config that
names no `brushograph.model` is a Mini.

What differs, from the parts in the release's `Standard_STLs.zip` and
`Mikro_STLs.zip`, and the `params` spreadsheet in `brushograf_V6.FCStd`:

| | Mini | 𝔐𝔦𝔨𝔯𝔬 |
|---|---|---|
| pinion | 14 mm, 11 teeth | 11 mm, 8 teeth |
| racks X / Y | 46 / 46 teeth, 183.9 / 183.9 mm | 23 / 34 teeth, 99.3 / 146.9 mm |
| Z travel | 18 mm | 12 mm |
| CMYK holder (`colourContainers.scad` preset) | `Standard_CMYK`: 30 / 18.6 mm crucibles (27.6 / 16.2 inside) on 23.6 mm centres, in a 144.4 × 39.2 mm plate | `mikro_container`: 22 / 13 mm crucibles (19.6 / 10.6 inside) on 16 mm centres, in a 96 × 30.2 mm plate |
| painting area (max width × height) | 151 × 156 | 65 × 100 |
| canvas offset Y | 25 | 19 |
| water container at | X12 Y6 | X2 Y6 |
| swipe | 23.5 mm | 17.5 mm |
| go in tray lift / dip depth / swipe exit Z | 11 / 1.0 / 5.9 | 10 / 1.0 / 5.3 |
| zero.g far corner | X160 Y160 Z32 | X75 Y123 Z21 |
| petri dish holder | yes | none |

The 𝔐𝔦𝔨𝔯𝔬's painting area is 65 × 100 mm, above the colours along the bottom,
as found on the machine; the racks agree. They are counted off the STLs in
`Mikro_STLs.zip`, because the spreadsheet's 𝔐𝔦𝔨𝔯𝔬 column still gives 120 mm for
the X rack that was printed at 99.3 — taking it at its word promised 88 mm
across. Its holder is the `mikro_container`
preset of `Extras/colourContainers.scad`, checked against
`Extras/CMYK_ColourContainers/mikro_CMYK_holder.stl` and `mikro_containers_steps.stl`; the
swipe is 17.5 mm, the same proportion of its 20.6 mm crucible as the Mini's 23.5 mm
is of 27.6. Water and black are 68.5 mm apart on a machine with about 66 mm
of X, so the water starts at X 2 rather than the Mini's 12, where black came
out at 80.5, out of reach. zero.g's sweep is shortened by the racks and scaled to the Z
travel. Apart from the painting area, these are derived rather than measured on
a built 𝔐𝔦𝔨𝔯𝔬.

Choosing a model puts its travel limits and canvas offset in the form, sets up
its holder's heights (below), puts the water container where the model has room for its holder and spaces
the others along from it, and shrinks the painted size to fit the bed
keeping its proportions. Going back to the model the config opened as puts back
what the config said. The 𝔐𝔦𝔨𝔯𝔬 has no petri dish holder — the classic dishes
span 173 mm, more than twice its X travel — so Classic is disabled for it and the server
treats a 𝔐𝔦𝔨𝔯𝔬 as CMYK whatever the config says. The plan, clean.g and the job's
swipes use the model's holder.

Steps per millimetre live in the controller, not here: the 𝔐𝔦𝔨𝔯𝔬's smaller
pinion moves 34.6 mm per revolution against the Mini's 44.0, so its firmware
needs about 1.27 times the Mini's steps/mm.

### Dip depth

How far the brush descends into a cup was fixed at Z −4 in `copicograf`, which
is deeper than a shallow petri dish wants — the brush went in past its ferrule.
It is now `brushograph.dip_depth` in the config, so it appears in the form like
any other setting. A config that does not mention it still gets −4.

The preview does not work out dips from heights. `copicograf` writes a `; dip`
comment before every descent into a cup, and the preview counts those. The moves
from the marker until the brush first rises, the swipe up the stairs included,
are drawn as time in the cups rather than as painting.

Heights were tried twice and failed both times. *Any Z below the canvas* held
while the dip was −4, but once the heights were measured from the surface the
cups stand on, the dip became Z 1 over paper at Z 0, and a three-hour job showed
0 cup dips. Reading the form's `dip_depth` fixed that, until a machine
calibrated to a dip depth of 0, the canvas height itself: its dips were counted
as brush-downs and drawn as strokes inside the cups. The generator is the one
thing that knows a dip is a dip.

A file from before the markers still gets the height reading: a descent to the
form's `dip_depth`, or anything below the canvas when the form has none.

### What the preview leaves out

Backlash compensation injects a corrective move at every reversal — 148 of them
in a small test job. Those are for the machine's slack, not part of the path that
was asked for, and drawing them buries the artwork in strokes that are not in
it. The preview skips them, and shows the path as it would be without
compensation — and it now really is the path that was asked for, not the file
with some lines left out. Dropping the take-up moves stopped being enough when
compensation started shifting the coordinates *between* them: while an axis
travels one way they are the path's, while it travels the other they are the
path's less the play, and drawn straight that is a step of the play at every
reversal — a sawtooth across the artwork that nobody asked to paint.

So the generator writes the shift into the file where it changes: in the
take-up's own comment (`; backlash take-up, shift X-1.7 Y0`), and on a line of
its own the first time an axis settles on a direction, which shifts the
coordinates with no take-up to carry the note. The preview reads it and
subtracts it.

Stated outright rather than worked out from the take-up moves, because working
it out does not survive the clamp: a take-up cut short at the end of an axis
steps by less than the shift really took, and a reader adding those steps up
carries the error to the end of the file. Measured on a job of 866 moves with
Pinkograph's 1.7 and 2.3 mm of play: reading the steps, 858 endpoints came out
wrong and the drift reached 5.04 mm by the last move. Reading the stated shift,
15 do, every one of them within the play of the X0 end where the compensation
itself is clipped by the endstop — and there the preview is drawing where the
brush will really be, which is the more honest of the two.

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
prepared in parallel and painted lightest first: **yellow, magenta, cyan, then
black**, whatever order the config's `color_order` lists them in. A light colour
over a dark one barely shows, and the key plate goes on last to sharpen what is
under it. Colours that are not process colours keep the config's order, between
cyan and black. The tray cards, the plan's painting order and the file name
follow the same order, and a saved config's `color_order` is written in it.

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
- **Large pictures are shrunk before anything else sees them, and turned
  upright first.** A phone photograph is 8000 px or more, and nothing downstream
  uses that much: the woodcut never works finer than 2400 px on the long side,
  and the stroke geometry stops enlarging at 4000. So every upload is turned the
  right way up from the camera's orientation tag and then shrunk, keeping its
  proportions to the pixel — to 2400 px for a photograph (the colour photograph,
  a photo card, subject detection and both previews), to 4000 for a picture
  already black and white (`images.prepare`). On an 8000 × 6000 photograph the
  CMYK G-code went from 31.9 s to 2.6 s, its preview from 7.9 s to 1.6 s and
  subject detection from 4.6 s to 1.8 s, with each plate's ink within 0.2 points
  of full size. Upright before shrinking, because the browser measures the
  picture the right way up to set the painted height: a tray card used to be
  painted from the pixels as stored, so a phone photograph stored sideways was
  painted sideways and stretched to the upright proportions. Placement and
  orientation are the original's; only the detail it is worked from changes.
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

### Colour photograph to CMYK

Artwork also takes a single colour photograph. It is converted to CMYK with
`SC_paper_eci.icc` (the same profile `i2gc` uses) and each channel is then
**thresholded** into a two-tone plate: a tint below the ink cutoff stays paper,
anything at or above becomes that tray's ink. Those four pictures are handed to
the rest of the pipeline exactly as if they had been uploaded already
thresholded onto Cyan, Magenta, Yellow and Black.

A photograph taller than it is wide is turned 90° onto its side first (after
applying the camera's orientation tag). Width is fixed and Height follows the
ratio, so lying a portrait down paints it across the whole width instead of in
a narrow strip that may run past `max_height`. The painted size on the page
measures the photograph already turned.

The cutoff is not dithered. A Floyd–Steinberg plate is thousands of specks, and
the brush cannot lay those down. 0% keeps any non-zero tint (`i2gc` with one
level); 100% keeps only a channel that is already solid. Empty plates are
skipped rather than failing the run.

**The four colour cards are put away while a photograph is loaded**, and come
back when it is removed. The photograph makes those four plates, so a card
offering to upload one of them beside it is offering to do the same job twice —
and the server let a tray picture win for its colour, which meant a file chosen
before the photograph was loaded quietly replaced one of its plates. Their file
inputs are not cleared, only hidden, so a picture chosen earlier is still there
if the photograph goes; what makes hiding mean something is that the run drops
the file inputs of hidden cards on its way out. A fifth colour keeps its card
whatever else is loaded: the separation only ever makes C, M, Y and K, so an
additional tray has nothing to be replaced by. The G-code file is named after
the photograph.

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

### Backlash compensation

An axis with slack in it does not go where it is told the moment it turns round.
Coming from the right and asked for X40, the first half millimetre of the move
only takes the nut across its own play, and the brush stops at X40.5 — ahead of
the commanded point, on the side it came from. So the file is written in the
axis's terms rather than the path's, which is openBrushograph Studio's scheme:
while the axis travels left every coordinate is written half a millimetre low,
while it travels right they are written as they are, and at each reversal a move
between the two is inserted. That move is half a millimetre of commanded motion
which the slack swallows whole, so the brush does not follow it.

What was here before did the opposite, and did not work. It moved the brush half
a millimetre *past* each corner, the way it had been going, and left every
coordinate after it alone — so the corner was overshot, and then missed by
exactly as much as it would have been missed with no compensation at all.
Simulated against a lost-motion axis over 10 → 50 → 40 → 60 → 20 with 0.5 mm of
play, it carried the brush out to 50.5 and 60.5 as tails painted past the two
corners, and then landed those corners at 40.5 and 20.5 — which is, to the
micron, where no compensation at all puts them. A small job makes about 140
reversals. The scheme here lands all five points on the number.

Measured on a generated job — two trays, 864 lines, 686 commanded points, 0.5 mm
of X play and 1.6 mm of Y — against the same path on a machine with no slack,
modelling the nut's position within the gap rather than assuming every reversal
crosses all of it: one point in X and six in Y are off by more than 0.1 mm. The
six are the opening dip, before the Y axis has turned round once and while the
brush is in the water; the one is the park at the very end, a move shorter than
the play itself. Everything in between is exact. The old scheme missed all 686,
by as much as it would have missed them uncompensated.

The figure matters more than it used to. Under the old scheme it only set how
long a tail was painted past each corner; now it shifts the coordinates, so
what is left at each reversal is the difference between the figure and the
truth, and an over-estimate costs exactly what an under-estimate of the same
size does. Simulated: 0.5 mm of real play compensated as 1.6 leaves 1.1 mm at
every reversal, worse than the 0.5 of leaving compensation off altogether.

The remaining ambiguity is not fixable from G-code and is not worth fixing: what
the slack does on the *first* move of a job depends on which face the nut was
resting on when the machine was zeroed, which the file cannot know. Either
convention leaves the whole painting translated by up to the play — 0.5 mm
across 151 mm of canvas, a rigid shift of the picture rather than a distortion
of it, and invisible next to a brush stroke a millimetre wide.

Two details of Studio's version are deliberately not copied. It sends the
take-up at a slow feedrate of its own, but `F` is modal and it never puts the
old one back, so every move after a reversal crawls until something sets `F`
again — here the move goes at the prevailing feed, and it is over in the time it
takes to cross the slack. And it clamps only at zero. The sign of the scheme is
chosen so the compensated file never asks for more X or Y than the path itself
did, which is the end that hurt: leaving the black crucible, which on Pinkograph
sits at X 156 with the axis ending there, the old take-up asked for X 156.5 and
the carriage found the stop instead. What it lost there it did not get back —
every move after it landed short by as much, which on a file that paints black
last was the whole black plate, shifted 3 mm. The same job now reaches X 156.0
and Y 101.864, both exactly the path's own extremes, where the old one reached
Y 103.464. `workable_x` remains as a floor under the near end, where a
coordinate written low could otherwise ask for less than zero; the stir keeps
off that end by the take-up and no longer gives up anything at the far one.

Reversals shorter than 0.05 mm, Studio's figure, are not reversals. On a job out
of this pipeline that is nearly free — 148 take-ups against 149 without it,
because `planar`'s `SIMPLIFY_PX` has already dropped the moves that small — so
it is insurance for paths that have not been simplified rather than a saving.

### The play is not one number

Pinkograph's sheet reads **1.9 mm of X play at the X0 end of the paper and 1.3
at the other**, with Y at 1.3 falling to 1.2. It is the X axis that changes
across this bed; Y is near enough one figure, which is what the far-end boxes
are for saying.

An axis like that cannot be compensated with one number. The best single figure
is the mean, and the mean is 0.3 mm out at each end — a third of a brush stroke,
and since the coordinates started moving an over-estimate costs exactly what an
under-estimate does. **Backlash X far end** and **Backlash Y far end** are the
same two readings taken at the other end of the paper, and the compensation runs
a straight line between each pair across the painting, holding the end figure
outside it. Two figures because two are what a sheet can be read for, and a
straight line because both faults are linear in X. Equal figures are a constant,
which is what every config written before this says, and its file comes out as
it always did.

Measured on a two-tray job, 1,061 moves and 336 painted points, against a
machine carrying those figures — the nut's position modelled within the gap
rather than every reversal assumed to cross all of it:

| Compensation | Mean X error | Points over 0.1 mm |
|---|---|---|
| None | 0.907 mm | 91.9% |
| One figure, the mean (1.6) | 0.077 mm | 36.5% |
| Two figures (1.9 → 1.3) | 0.019 mm | 6.6% |

What is left is two classes and neither is the model: the park at X0 Y0, where
the compensated file is clipped by the endstop and there is nothing to
compensate with, and a handful of moves shorter than the play itself, which no
scheme lands — the worst of them is 0.47 mm at X 13, where the play is at its
widest.

**The shift follows X rather than being fixed at each reversal.** Neither axis's
play is something the machine carries away from a reversal and keeps. Y is the
gantry beam, driven from one side, so a Y play that changes along X is the beam
racking: how much of the twist reaches the brush is a matter of where the
carriage is standing, and it changes as X moves with no reversal anywhere. X is
the carriage running along that beam, where what is lost at a reversal is the
slack and the stretch of the belt between the drive and the carriage — also a
matter of position, because it is the free length that changes.

That was worth testing rather than asserting, since the two would part company
if an axis really did keep what a reversal gave it. Simulated both ways —
the lost motion as a local clearance, and then as an offset the drive keeps
however far it travels — the two come out identical to the micron on this
machine's figures, because a play that is widest at X0 lets the offset grow to
the local figure while the axis travels that way and holds it at zero coming
back. Freezing the figure at the reversal instead is measurably worse on the
same job: 0.076 mm of mean X error against 0.019, and a fifth of the painted
points out by more than 0.1 mm against a fifteenth. A scanline fill is long X
strokes between reversals, so a frozen figure carries the whole spread out to
the far end of every stroke.

Following the play also makes the compensation exact along a stroke and not
only at its ends: the model is a straight line in X and a G1 is a straight line
in X, so compensating the two endpoints compensates every point between them.

**No extra moves.** The same 296 take-ups either way: slack is crossed at a
reversal, and the drift between reversals is the belt and the beam following the
carriage, which the coordinates already carry. What the file gains is notes —
the shift is stated where it changes, and it now changes on nearly every move.
Stating every change costs 251 of them, 42 KB against the flat file's 34.
Stating it when it has drifted by 0.05 mm costs 123 and 38 KB, and leaves the
preview drawing the path to within 0.048 mm, a twentieth of a brush stroke. At
0.2 mm it would be 37 notes and 36 KB: 2 KB for a fifth of a stroke, which is
the wrong end of that curve.

The two figures are the ends of the **painting**, not of the axis. They are read
off a sheet, the sheet is painted on the paper, and a line drawn through two
readings says nothing about ground neither was taken on — so the containers,
which on Pinkograph stand at X 156 to the canvas's 132, get the figure for the
edge of the paper rather than one extrapolated a fifth further out. Nothing is
painted out there.

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

The form follows suit: each speed group's Acc and Feedrate 2 are shown only
while the controller is Marlin. They are hidden rather than disabled, so a
config switched to another controller and back keeps its figures.

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

Six, chosen in the footer and remembered per browser. **Default** follows the
machine it is read on, light or dark. **Dark mode** holds dark whatever the room
is doing. **Coconut mode** is husk, flesh and a palm lit from behind, and the
mark in the corner is a coconut. **UwU** is a neon sign with all the lights up:
the ground glows, every edge is lit, and the rules under the headings and the
Generate button run the rainbow. **𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘** is black
print on aged paper, set in UniFraktur, and speaks German (see below).

### The mark in the corner

`.mark` is the crossed-brushes-and-gear logo (`webui/static/logo-mark.png`,
cut from `brušograf_logo.png`: luminance thresholded to alpha, cropped tight
to the ink, ink itself recoloured white so the same file reads correctly
whichever masking convention a browser uses — some older WebKit builds treat
a raster mask source by luminance rather than alpha, and white ink stays
opaque under either). It is applied as a CSS `mask-image`, not an `<img>`:
`background` paints it, so every theme below recolours the same silhouette
rather than swapping pictures.

Default and Dark mode fill it with `--ink` — whatever this theme already
calls its own ink colour, the same rule the rest of the page follows, rather
than a fixed brand navy that would need its own contrast check against every
future theme. Pinkograph and UwU fill it with the gradient their old colour
wheel already used, so the swap from a plain wheel to the actual logo cost
those two themes nothing — the pink-to-cyan and the rainbow both still read,
now shaped like the mark instead of a circle, and UwU's slow spin now turns
an actual gear. **Coconut alone keeps its own mark**, the 🥥 an earlier
request asked for: its override sets `mask: none` as well as `background:
none`, because a mask left active would have clipped the coconut emoji to
the brush-and-gear silhouette instead of leaving it whole.

At 56px (was 32) it reads as a mark rather than a favicon-sized dot; Coconut's
emoji scales with it via its own `font-size`, kept at the same ratio.

The favicon and `apple-touch-icon` are a separate pair of files
(`favicon.png`/`.ico`, `apple-touch-icon.png`) rather than the same
`logo-mark.png` the header uses, because a favicon is drawn wherever the OS
puts it — a light tab, a dark one, a bookmarks bar — with no theme and no
`--ink` to read from. Solid black ink is the one choice that reads on
everything a browser or a phone's home screen might put behind it; the mask
technique above only works because the header always knows its own
background.

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

One thing stays fixed across all six: **colour means pigment.** Cyan, magenta,
yellow and water identify trays and nothing else in the interface is saturated,
so a coloured mark always stands for paint in a cup. The themes restyle every
surface and every annotation, and leave the paint alone. **𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘**
brings a stark black-and-white print aesthetic with sharp rectilinear frames, high
monochrome contrast on aged paper, and UniFraktur typography across every control.

Black is the one paint that cannot be left alone. On the three dark papers it is
the paper — `#23282f` on `#1d2120` is a contrast ratio of 1.08, which is to say
invisible — and that is not only the preview: the same colour draws the tray
dot, the left edge of the artwork card and the bay in the plan view, so a black
cup had no mark anywhere in three of the six themes. `--k` is therefore a
per-theme colour like the rest of the surface, the plan's palettes carry a
`key` beside their `accent`, and the preview reads `--k` rather than holding a
black of its own. The rule survives with one exception, and the exception is what lets
black read as paint at all rather than as nothing.

**The edition in the slogan flies for one theme only.** The header reads
"Brušograf GCode Generator" everywhere and adds "- Edition 𝖅𝖜𝖊𝖎𝖙𝖊𝖗
𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘" under Kongress and nowhere else: it is that
congress's edition, and a dark-mode header announcing it was announcing
someone else's. It is a `.edition-note` span the stylesheet shows or hides,
rather than markup the script adds and removes, so there is nothing to keep in
step and nothing to restore.

Coconut declares `color-scheme: light` although its ground is dark, because
every panel is pale and the form controls sit on those; under a dark scheme the
browser drew unchecked boxes as filled dark squares on cream, which read as
ticked. Pinkograph and UwU declare dark, because their panels are. Kongress
declares light with stark monochrome surfaces and zero corner radii.

Everything that moves stops under `prefers-reduced-motion` — the machine's own
theme says the same, in the same words: flashing signs are a migraine risk.
Every text colour in every palette clears 4.5:1 against what it sits on.

### The theme that speaks German

𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘 is a language as well as a look: while it is on,
every word of the interface is German, and when it goes off every word is
English again. It is the only theme that does this, which is what makes the
mechanism worth describing — nothing here is about German, only about there
being a second language at all.

**All of the German is in `static/de.js`**, so translating is reading a
dictionary rather than hunting through markup and JavaScript. It holds three
maps. `text` is an English string to its German, keyed by the English with its
whitespace collapsed, so a sentence a template wraps over four lines is one
entry. `html` is a `data-i18n` id to German markup, for the prose that has tags
inside it. `patterns` is a regexp and a replacement, for the handful of
messages the server builds with a detail interpolated into them.

**The page's text arrives two ways, so it is translated two ways.** Text that
came from a template or from the server is already in the DOM: `webui.js` walks
it and swaps it in place, keeping the English in a `WeakMap` beside it so the
swap can be undone. Text the script writes itself never sits in the DOM as
English at all, so it goes through `t()` at the point it is written —
`t("height {height} mm from {tray}", {height, tray})`, with the English as the
key, so the call site still reads as the sentence it prints. Those are also
remembered as the English they were written from, so a status line written in
one language is rewritten rather than left standing when the theme changes.

A `data-i18n` block is replaced whole, so **it must not contain anything the
script listens on**: swapping the markup destroys the element the listener was
attached to, and the control goes dead. "Already have a file? Open a .gcode"
was written that way first and stopped opening files the moment the theme
changed. It has no tags inside it worth keeping, so it went back to being two
plain entries in `text` and the file input stayed where it was.

Three things are deliberately **not** translated. The config's own keys — the
`kroma` and `cyan` on the tray cards — are identifiers, and the About page
explains them as such. An enum's stored value stays as the slicer and the
firmware spell it; only the word the picker shows is translated. And an error
that carries its own detail from deep in the pipeline stays in the words it
arrived in: guessing at it would be worse than reading it in English.

The mechanism is reversible by construction, which is the part worth keeping.
A translation applied over the top of the page and never recorded would make
the theme a one-way door — switch away and the interface is in German for the
rest of the session, or until a reload throws the form and everything uploaded
to it away.

**The two server-drawn pictures translate themselves**, because they are drawn
rather than marked up: the browser already posts its theme with both requests,
so `sketch.py` and `cmyk_sep.py` carry their own small dictionaries and letter
themselves in UniFraktur through the shared `sketch.font_for()`. That is also
why the plan view's words are not in `de.js` with everything else — they are
not the page's text, they are pixels in a PNG.

Rendered German is longer than English and Fraktur is wider than the sans, so
the theme lets out the two places a label sits in a fixed width — the button
beside the height field, and the painted-size grid — rather than clipping them.

**One control the page does not letter: the file input.** A browser draws
"No file selected" and the word on the button beside it from its own locale,
and nothing the page can say reaches them — not the stylesheet, not the
document's `lang`. So under this theme the native control is taken out of sight
and `proxyFileInputs()` shows one of ours in its place, which is a sibling of
the input inside the same `<label>`: clicking it opens the picker through
label activation, with no script involved. The input is moved out of sight
rather than `display: none`, so it keeps its focus and its place in the
accessibility tree, and the focus ring is drawn on the proxy instead. Every
other theme keeps the browser's own control and never shows this one, which is
also why this is not a general improvement quietly made everywhere.

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

That pickup makes **`prepare_paint_count` dips, not one**. One dip is a re-ink,
and it is enough for a brush already carrying the colour; the brush arriving
here is not, it has just been washed and is full of water, and one dip charges
it so weakly that a tray opened pale and came up to colour somewhere in its
first strokes. The mixing routine is the same one the opening sequence uses and
the same figure from the config, honoured to the letter: `0` is what that
setting means by a plotter, and a plotter has nothing to pick up, so it makes
no trip at all. A count of zero used to make the trip anyway and dip nothing in
it — the rim wipe and the journey home sit outside the dipping loop, so it
wiped a rim the brush was nowhere near and then flew home from a cup it had
never entered.

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

**The wash climbs on its way to the water**, like every other trip across the
bed. Ramping and lifting off the paper were one flag: a trip that begins on a
stroke wants both, so `from_canvas` asked for both. The wash at the end of a
tray is the case where they part — the stroke it has just finished has already
lifted it clear — and with one flag it either hopped a second time or flew the
bed level and dropped at the far end. They are asked for separately now, and
the wash takes the ramp without the lift.

For that the trip has to know where it starts, and the wash was being written
from the canvas origin, which is a line the brush is not standing on. The
pipeline reads the end of the last stroke out of the adapted file
(`last_stroke_point`, the mirror of `first_stroke_point`) and passes it as
`wash_from`, so the climb is drawn from where the painting actually finished.

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
23.6 mm centres they reach into the crucible next door to do it. So `remove_drop` is
ignored when the containers are modern, and `remove_drops_radius` is a
round-cup setting that nothing else reads.

### Round cups and rectangular ones

Three container setups exist, and `brushograph.cup_shape` picks between them.

**Classic** is the round cup the machine was built around. The brush goes down
the middle — the point furthest from the wall in every direction — sweeps a
chord down in the paint where the bristles are inside the cup, returns to the
middle and lifts.

**CMYK** (`modern` in the config) is the printed CMYK holder: five crucibles
with stairs in their floors, in a holder labelled W C M Y K. The design is
`Extras/colourContainers.scad` in openBrushograph_hardware (once
`mini_petri.scad`), with its presets in `colourContainers.json`, one per model —
`Standard_CMYK` for the Mini, `mikro_container` for the 𝔐𝔦𝔨𝔯𝔬 (see **Model**
above). For the Mini that is a **30 mm** water crucible and four of **18.6**,
5 mm apart: centres 23.6 mm apart and the first colour 29.3 mm from the water.
Slicing `Extras/CMYK_ColourContainers/standard_CMYK_holder.stl` (once
`Gandi_petri_holder.stl`) finds its slots centred at 25.0, 54.3, 77.9, 101.5 and
125.1, which is those figures exactly. Inside their 1.2 mm walls the crucibles
are **27.6** and **16.2 mm** across and 27.6 long. The 𝔐𝔦𝔨𝔯𝔬's are 22 and 13 mm
on 16 mm centres, 19.6 and 10.6 inside, 23 long.

The crucibles stand in a plate: 144.4 × 39.2 mm on the Mini, its slots opening
9 mm back from the front edge, and 96 × 30.2 on the 𝔐𝔦𝔨𝔯𝔬, 7 mm back. The plan
draws the plate under the crucibles, placed off the water container.

An earlier, bigger holder, `CMYK_holder_big.stl`, had 39.2 and 29.2 mm bays on
34 mm centres, and the Mini used its figures until they were checked against
the design.

The water crucible is the wide one so that the brush has room to be rinsed.
The plan view draws each at its own outside size — 30 × 30 and 18.6 × 30 mm on
the Mini, 22 × 23 and 13 × 23 on the 𝔐𝔦𝔨𝔯𝔬 — with its five stairs across the back
and the swipe as an arrow at its own length. Drawn at the inside size and only
as long as the swipe, the crucibles came out well short of what sits on the
bed; drawn alike, the one cup that is a different size was the one you could
not pick out. The swipe is 23.5 mm, which
keeps it inside the 27.6 mm crucible.

For CMYK the print fixes these sizes, so they are not settings: they come from
the model's holder in `MODELS`. The round cups have theirs from the dish,
`CLASSIC_DISH_RADIUS` and `CLASSIC_DISH_RIM_RADIUS`, and the plan view draws each
dish's rim. The shape picker itself is labelled **Container setup**.

**Custom** is rectangular cups swiped exactly as the CMYK ones are, for a holder
nobody has a preset for. Four settings, shown only while Custom is selected,
size and lay them out:

| setting | default | meaning |
|---|---|---|
| `cup_width_water` | 39.2 | the water cup's width across X, inside |
| `cup_width` | 29.2 | each colour cup's width across X, inside |
| `cup_depth` | 30 | how far the swipe runs along Y |
| `cup_spacing` | 34 | centre to centre between colour cups |

The defaults are Pinkograph's holder, `CMYK_holder_big.stl`, the one the CMYK
setup used before the design holders. The water cup is parted from cyan by the
same wall as the colours are from each other, so cyan sits half of each width
plus `cup_spacing − cup_width` from the water — 39 mm on those figures, then 34,
which is that holder exactly. **Auto-space containers** spaces custom cups that
way from the water cup. A custom holder is nobody's design, so it sets no lift,
dip or swipe exit, and the plan draws no plate for it; the four figures stay in
a config whichever setup is picked, so switching away and back keeps them.

Its floor is a staircase, so loading is one swipe from the deep end to the
shallow one, rising as it goes:

    G00 X53 Y-4      ; deep end, in front
    G00 Z-4          ; down into the paint, at dip_depth
    G01 X53 Y16 Z1   ; draw the length of the bay, climbing to cup_swipe_exit_z
    G00 Z8           ; clear

It is one interpolated move rather than a tread-by-tread staircase. The bristles
flex over the steps, and a stepped path would need the step count and their
heights — which the holder STL does not carry, since its slots are open through
the plate. The crucibles' SCAD does: five steps over the back 40% of the
crucible, rising to the rim. The swipe's far end, 35% of its length past the
centre, is over the third step on both models, so **Auto-space containers** sets
`cup_swipe_exit_z` to that step's top — 5.9 mm on the Mini, 5.3 on the 𝔐𝔦𝔨𝔯𝔬.
With them it sets the tray lift 2 mm over the rim (11 and 10) and the dip just
under the 1.2 mm floor (1.0 on both), bristles flexing, as the petri dish does. A config
that names none of it still defaults the exit to 1 mm rather than 0, because 0
is `canvas_height` here, and a brush leaving the cup at paper level is both wrong
physically and drawn as painting in the preview.

The swipe runs front to back, finishing on the canvas side, so the brush leaves
the cup already pointed at the paper. With the stock config its near end is
Y −4.5, which looks like the off-the-bed fault the wipe had — it is not: the
classic sweep reaches Y −4 from the same `tray_y` of 6 and `tray_enter_radius`
of 10, and has done so on this machine all along. Both then read lower again in
the file by Pinkograph's 1.6 mm of Y play, which is what **Backlash
compensation** writes while the axis travels that way.

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

The spacing is not a machine measurement, because the holder is one piece:
on the Mini its crucibles are 23.6 mm apart centre to centre, the first colour
29.3 mm from the water, and only where the whole thing sits is anyone's to
decide. Those offsets
are `MODERN_BAY_OFFSETS`, and **Auto-space containers** under the container
positions applies them from wherever the water cup has been put — these, or the
petri dish holder's below, whichever shape is selected — along with the heights
that holder fixes, for the model selected.

Round cups have a holder too: the low petri dishes of
[openBrushograph_hardware](https://github.com/openBrushograph/openBrushograph_hardware/tree/main/Extras)
sit in `4xPetri_rounded_new.stl`, a 188 mm plate with four holes labelled WASH,
C 1, C 2 and C 3. Slicing it at mid-plate finds holes of 20.14 mm radius at
45, 44 and 44 mm centres. Those are `CLASSIC_DISH_OFFSETS`: 0, 45, 89 and 133
from the water.

Four holes is water and three colours, so **a classic machine has no black**.
The form is built once and the picker can change under it, so `with_defaults`
still offers the black cup whatever the shape, and the form hides its position
and its picture card — and disables them, so they are not posted — while Classic
is selected. `fit_cups_to_shape` runs after the form is read and takes the
`kroma` tray and `K` out of the config when the cups are classic, so the plan
view, the G-code and a saved config all have three colours. A CMYK photograph
still separates into four plates; with no black cup, the K plate is not painted.
Switching back to CMYK offers black again at its guessed position.

The dish itself is in `Extras_openBrushograph.scad`: a cylinder of r 17 grown
by a 2 mm sphere inside and r 18 grown by 2.1 outside, cut off 11.2 mm above
its base — 19 mm inside radius, 20.1 outside, a 1.1 mm floor. Unlike the
stepped bays, that is enough to derive the settings, taking Z 0 as the surface
the dishes stand on (`CLASSIC_DISH_SETTINGS`):

| Setting               | Value | Why                                       |
|-----------------------|-------|-------------------------------------------|
| `dip_depth`           | 1     | onto the 1.1 mm floor, bristles flexing   |
| `tray_enter_radius`   | 15    | the sweep stays 4 mm off the wall         |
| `remove_drops_radius` | 21    | dragged clear past the 20.1 mm rim        |
| `remove_drops_lift`   | 9     | tip 2 mm below the rim, so it catches     |
| `go_in_tray_lift`     | 14    | clears the 11.2 mm rim                    |

Choosing **Classic** in the form applies all of it at once — the settings, and
the spacing from wherever the water cup is — and choosing **CMYK** does the same
for the crucibles, so switching either way leaves none of the other holder's
figures behind. A config that opens already set up keeps its own figures;
**Auto-space containers** applies the selected holder's again.

Five cups on the old holder's 34 mm centres spanned 141 mm, which is why the
`pinkograph.conf` preset started its water bay at X 8: the bed is 151 mm wide,
so anything past 10 put the black cup out of reach. The design holder spans
100.1 mm, so the Mini's water starts at X 12 with room to spare. (The presets have since gone — see **Keeping a
config on the server** — but a Pinkograph config kept there wants the same.)

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
holder, quite apart from being redundant after the stairs. At the old holder's
34 mm centres a `remove_drops_radius` over 17 mm carried the wipe into the bay next door: the
20 mm that suited cups 45 mm apart put the wipe from the black bay at X 129,
inside the yellow bay, and at X 169, which is 18 mm past the end of a 151 mm
machine. Round cups 45 mm apart still wipe, and still read that setting.

The machine view draws whichever is configured — circles with their sweep, or
rectangles with their treads and an arrow along the swipe — and redraws as soon
as the picker changes. It draws each bay at the holder's own width, the water
one wider, and each round cup inside its dish's rim.

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

## Macro generator

At the end of Machine setup, below Save these settings — it is about the
machine rather than about a picture, so it lives with its plan drawing rather
than down by Run — the **Macro generator** builds six small routines:
`zero.g`, `home.g`, `paper.g`, `clean.g`, `calibrate.g` and `backlash.g`. All
six come from `webui/macros.py`, a module the pipeline never imports and that
never touches a tray image, so generating them needs none of the pictures a
G-code run refuses to proceed without. Five of the six are built from the
config; `zero.g` is not (see below).

- **zero.g** is the machine's own self-zero dance, reproduced verbatim: zero
  the near corner, lift, sweep out to the far corner and back to confirm
  nothing is fouled along the way, re-zero at a travel height, jog down and
  back up, jog to two more points and 1 mm further on Y, and declare the offset
  `X10 Y0 Z10` point. That last millimetre keeps later moves to Y0 off the
  endstop, which they otherwise hit.
  Fixed and tuned on the actual hardware, except its very last line, which is
  not: it ends the same way `home.g` and `clean.g` do, parked at X0 Y0,
  Z = Dip Depth + 1 — the one figure in this file that reads the config.
- **home.g** parks at X0 Y0, Z at `dip_depth + 1` — a literal reading of that
  spec, so it lands just above dipping depth rather than at travel height. It
  still lifts to `go_in_tray_lift` *before* crossing the bed, and only
  descends to the park height once it is over X0 Y0.
- **paper.g** moves to half of `max_width` on X and all of `max_height` on Y,
  at `go_in_tray_lift`, out of the way for replacing paper — not a touch: it does not descend to
  `canvas_height`. Absent `max_width`/`max_height`, it falls back to
  `width`/`height`, the always-present painted size — the same fallback
  `sketch.py` already uses for the plan view, for the same reason: a config
  need not carry a travel limit distinct from what it paints.
- **clean.g** washes the brush at the water container, three dips or swipes
  with no rim wipe — matching the `3` and the `False` hardcoded into
  copicograf's own `wash_the_brush()` — then parks the same way `home.g` does,
  so a clean brush is also a homed one.
- **calibrate.g** does only one thing: touch the canvas origin down to `Z0`
  and park at `Z10`, both literal heights rather than `canvas_height` or
  `go_in_tray_lift`. No wash, just the dot and a park over it. It does lift to
  `go_in_tray_lift` before crossing the bed, like the rest — it is run from
  where the other macros leave the brush, X0 Y0 at Dip Depth + 1, which on a
  holder whose water crucible covers the origin is under the rim.
- **backlash.g** paints a sheet for measuring the play in each axis at both
  ends of the bed, the one macro that puts the brush on the paper for anything
  but a dot. Every pair is one commanded position drawn twice, arrived at from
  each side in turn, so the gap between the two marks is the play.

  Four groups. Two **rows of test pairs**, each spread across the whole width
  of the paper: the **X row** is three vertical pairs at the left, the middle
  and the right, and the **Y row** three horizontal pairs across the same
  width. The left-hand pair of each row is the near figure and the right-hand
  pair the far one; the middle pair is the check, and falls halfway between
  them if the play really is a straight line across the bed. Both rows span the
  width because the play changes along X and a group huddled in one corner
  reads a fraction of the difference and calls the rest even, which is the one
  thing this sheet must not do — it is what the old layout did, with all three
  Y pairs at one X and the X pairs in the left quarter of their own box.

  A Y pair is read at its **outer end**, because it opens out along its own
  length: both strokes are drawn at one commanded Y with the gantry twisted
  opposite ways, and the twist that reaches the brush grows along X. That is
  the fault this sheet is here to size, drawn as a picture of itself.

  Then a **gauge** an axis: five more pairs, drawn 0.5, 1, 1.5, 2 and 2.5 mm
  apart, both strokes of each arriving from the same side so the play cannot
  open or close them. Find the gauge pair a test pair looks like and that is
  the figure, to a tenth. A gauge per axis rather than one for the sheet
  because a gap between two horizontal lines does not look like the same gap
  between two vertical ones, and the axis with the larger play is the one that
  most needs its own ruler. A gap wider than the widest gauge pair is wide
  enough to lay a rule across, which is what a gauge is for saving you from at
  half a millimetre and not at three.

  The gauge pairs are laid out with the same **clear space between every pair**
  whatever gap each one draws, rather than in slots of equal width: spread
  evenly, the 0.5 mm pair gets as much room as the 2.5 mm pair and the space
  after the widest one closes towards its own gap, which is the one place a
  reader must not have to guess which line belongs to which pair. The Y gauge
  is 5.5 mm clear between rows on the Mini and 3.0 on the 𝔐𝔦𝔨𝔯𝔬, against gaps
  of at most 2.5. Evenly spaced in the same room the 𝔐𝔦𝔨𝔯𝔬's widest pair had
  1.5 mm to the next one, which is narrower than the pair itself. The Mini had
  8.0 and now has 5.5, because the band it sits in is shorter than the box it
  used to share with the test pairs — still more than twice the widest gap.

  A gauge rather than a rule because a ruler will not settle this. A brush
  stroke is about a millimetre wide, and half a millimetre between two wet
  marks is not a measurement anyone takes off a sheet with a rule — but
  telling which of five known pairs a test pair resembles is easy. And a gauge
  rather than something cleverer because there is nothing cleverer to do:
  backlash does not accumulate. Alternating moves lose the play once and get
  it back at the next reversal, and a staircase with a net direction loses it
  going out and regains it coming back. No arrangement of moves turns half a
  millimetre into a visible ten, so a drift test — the obvious idea, and the
  one tried first — cannot work, and reading a gap is what is left.

  Both test rows take the full width, so what is left to lay out is the two
  gauges, and they are rulers that can sit anywhere. On a canvas wider than it
  is tall they share the bottom band, the Y gauge's rows on the left and the X
  gauge's columns beside them; on a taller one there is no width to spare — the
  𝔐𝔦𝔨𝔯𝔬's 65 mm is one gauge stroke and nothing else — so they take a band
  each. That is the difference between the Mini at 132 × 89 and the 𝔐𝔦𝔨𝔯𝔬 at
  65 × 100.

  The outer pairs stand a run-up in from the edges of the paper rather than on
  them: a stroke at the very end of an axis has nothing to back off into but
  the endstop and would be measuring that. On the Mini they fall at X 12 and
  X 130.7 of the 132 the figures are meant for, so reading them as the edges
  overstates the difference by about a tenth of itself — finer than the gauge
  can be read to, and the macro says so in its own header.

  Every stroke backs off 12 mm and comes in along the axis under test, so that
  axis is certainly travelling the right way when it arrives; the move before
  that runs along the *other* axis in the same direction as the stroke, which
  keeps the play out of the ends of the lines. A stroke that began with a
  reversal would start 1.6 mm short of where it says on Pinkograph, and the
  ends of these lines are part of what is being read. That settle backs off by
  the full 12 mm too, not a token millimetre: the macro exists because the
  play is *not* known, and a settle sized for a small one would displace every
  stroke on exactly the machine worth measuring. Both are clamped to the bed,
  and each section keeps off the near edges by the run-up where the canvas can
  spare it — laid out hard against the origin, the 𝔐𝔦𝔨𝔯𝔬's first Y pair asked
  for X −0.6, which is the endstop.

  Strokes are capped at 55 mm because a pair has to come out of one dip:
  at the full height of the canvas a pair came to 163 mm against Pinkograph's
  `paint_per_run_max` of 150. The Y row is three pairs rather than one the
  whole way across for the same reason — one pair spanning 132 mm would read
  the play everywhere at once, which is what it wants to be, but two strokes of
  it is 264 mm out of a single dip. Three short ones are the same reading with
  gaps in it. As drawn the sheet is 32 strokes and 1242 mm of paint over 16
  dips, 78 mm a dip and 110 at the worst of them. One dip a pair, from the last cup in painting
  order — black where there is a black cup, cyan on a classic holder with no
  room for one.

  Macros never go through `apply_backlash` — only `gcode_pipeline.generate`
  does — so the sheet paints raw whatever **Backlash compensation** is set to,
  and measures the machine rather than the setting.

`home.g`, `paper.g`, `clean.g`, `calibrate.g` and `backlash.g` share one rule: every move to somewhere
new — a tray, the canvas, the origin — is preceded by a lift to
`go_in_tray_lift`, and only that: never the larger of it and
`move_to_other_shape_lift + canvas_height`, the way copicograf's own travel
height for a real job is computed. A macro's travel Z is always the one
figure the config names for it, so raising `move_to_other_shape_lift` does
not quietly raise how high these clear the bed. `zero.g`'s own heights
(`Z10`, `Z32`, `Z15`) are none of the config's — they are part of the fixed
routine — and `calibrate.g` follows no lift-first rule at all, on purpose.

`clean.g`'s wash follows whichever shape `cup_shape` names, and is meant to
read as a real pickup's motion, not merely approximate it: a modern container
gets the same swipe up the stairs `append_go_in_tray()` emits for a real job,
margin and all, and a classic one gets the same down-sweep-up dance, with no
rim wipe afterward — matching the `False` copicograf's own `wash_the_brush()`
passes, since a brush being rinsed has nothing to shed on the way out. The
one deliberate difference from copicograf is that the classic dip's quadrant
is no longer random: it spreads wear across a real cup by picking one of four
quadrants at random on every pickup, which suits hundreds of pickups but not
a macro generated once and kept, so `_container_motion()` cycles the same
four quadrants by repetition index instead — the same coverage, without two
downloads of the same config ever differing.

None of the five macros carries an M-code or a `G28`: no `sanitize_for_controller`
pass is needed, because `G90`/`G21`/`G0`/`G1`/`G10`/`G92` mean the same thing to
Marlin, GRBL and FluidNC.

**Generate macros** posts the form to `/macros` — the same `apply_form()` a
config download goes through, so a macro reflects whatever is currently typed
into the form, saved or not, the way Download Machine Config already does.
**Download macros** saves the five as separate files rather than a zip; five
small text files did not seem worth a new dependency. **Upload to machine**
sends them the same shape `gcode-send` sends a job in — one `POST` per file,
`multipart/form-data` carrying `path` (`/`) and `myfile`, `mode: "no-cors"`,
opaque reply — but to `<host>/files`, not `<host>/upload`. FluidNC's web
server registers the two as separate routes onto the same handler
(`WebUIServer.cpp`: `"/files"` → `LocalFSFileupload`, `"/upload"` →
`SDFileUpload`, both calling the shared `fileUpload()`): `/upload` writes to
the SD card, which is where a job's G-code belongs and where `$SD/Run` looks;
`/files` writes to the flash filesystem, which is where the controller's own
dashboard theme already lives (see **Pinkograph**, above) and where a
standing macro belongs — a card can be swapped or reformatted, and a job's
G-code is not meant to survive that, but these five are. There is no
`$SD/Run` here either: these are routines an operator runs by hand from the
controller's own interface, not a job meant to start the moment it lands.

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

Kept configs, below, are unaffected either way: they belong to the server, not
to a session.

## Keeping a config on the server

An upload is normally yours alone and lasts as long as your session. Tick **Keep
it on this server, for everyone** before choosing the file and it goes into
`webui_configs/` instead: it joins the machine pulldown straight away, for anyone
who opens the page afterwards, and stays through restarts. The directory is
gitignored beside `webui_sessions/`, so updating the code never touches it, and
it keeps a version history of its own (see **Version history** below).

**The pulldown lists kept configs and nothing else.** No configs ship with the
repository: the two presets that used to sit in the repo root
(`pinkograph.conf`, `small_machineM2.conf`) were removed, so a machine is in the
list because somebody using this server put it there. A fresh server's list is
empty, and its prompt reads *No machines kept yet* until the first one is kept.
The old presets are still in git history for anyone who wants to keep one.

Every config has a mode that says where it lives — `uploaded` (the session) or
`saved` (`webui_configs/`) — carried on every request after it is chosen.
`config_path()` is the one place a name and a mode become a file. The name is
checked against `SAFE_NAME` before it is joined to anything, so no mode can be
talked out of its directory, and an unknown mode is refused. The two places that
used to do this each did `session if mode == "uploaded" else repo root`, which
read any mode it did not recognise as a preset.

**Keeping never overwrites.** This is a shared server, and a name already
taken is somebody else's machine, so a second `workshop.conf` is kept as
`workshop-2.conf` and the page says which name it got. Changing a kept config
is a different, deliberate act — **Update**, below. Uploading the very same bytes again finds the copy already kept rather than
adding another beside it, so pressing it twice does not fill the list.

The file is written whole under a name the pulldown ignores and then hard-linked
into place. A link fails if the name exists, so two uploads racing for one name
cannot overwrite each other, and nobody is ever offered a half-written config.

Anything kept is kept for good and offered to everyone, so it gets limits of its
own rather than the photograph-sized upload limit: **256 KB** a file (a real
config is a couple of kilobytes) and **200** files. Past either, keeping is
refused with a message saying so, and the same file can still be used for the
session without keeping it. Re-keeping a config already there still works at the
limit, since it adds nothing.

### Version history

`webui_configs/` is a git repository of its own, started the first time the
server runs (the code's repository ignores the directory, so the two never
meet). The configs already there go into a first commit, and from then on every
write to a kept config is a commit naming the file, what was done and where the
request came from:

    Upload workshop-2.conf from 203.0.113.42
    Update pinkograph.conf from 198.51.100.7

so `git -C webui_configs log -p pinkograph.conf` shows who changed a shared
machine when, and what it said before. Nothing is committed when a write
changes nothing — the same bytes kept again, or an Update with nothing edited.
The commits are authored by *Brushograph WebUI* whatever git is configured with
on the server; the person is the address in the message.

**The address.** Deployed, gunicorn listens on loopback behind nginx, so every
request's peer is 127.0.0.1 and the client is in `X-Real-IP`, which nginx sets
from its own `$remote_addr` and so cannot be supplied by the client. The header
is believed only from a loopback peer: sent straight to the app, it could claim
any address. Run without nginx, the peer is the client and is used as it is.

**History never blocks a save.** If git is missing or a commit fails, the
config is written all the same and the failure goes to the log.

### Updating a kept config

**Save these settings** in Machine setup offers **Update workshop.conf** beside
Download, whichever way that config arrived. Putting the settings on the server
is the whole of what the button is for, and it used to refuse a config that had
been uploaded rather than kept — which left the only way of keeping an edited
machine being to download the file and upload it again with the box ticked.

A config already kept there is written over in place: the settings as they
stand, exactly the bytes Download would have given you, so everyone who picks
that machine from the list gets them.

An uploaded config has nothing on the server yet, so the button puts it there,
kept exactly the way an upload with the box ticked is kept. That means a name
already taken is never written over — it belongs to somebody else's machine, so
this one goes in beside it as `workshop-2.conf`, and the page says under what
name rather than leaving you to guess which of the two is yours. The form then
carries on as a kept config: the next Update goes to the same place, and Delete
can reach it.

**Update does not overwrite blind.** Two people can load `workshop.conf`, both
tune it, and both press Update; the second would quietly throw away the first
one's changes. So the form carries a version of the file it was built from — a
hash of the very bytes it was parsed from, taken in the same read — and an
update whose version no longer matches the file is refused with *changed on the
server since you loaded it*, the file untouched. A kept config that has gone
from the server altogether cannot be written back either: a kept one leaves no
copy in your session, so there is no base left to fold the form into — what the
form posts is the settings it was built to offer, not a whole machine. Picking the config from the list
again loads the current one. A successful update hands back the new version, so
the same page can update again without reloading.

The compare and the write happen under one lock, so simultaneous updates from
the same version cannot both pass: one wins and the rest are refused. The new
file is written beside the old one and swapped in with `os.replace`, so anyone
loading it meanwhile gets the old config or the new one, never half of each.
Kept configs' size limit applies to what an update writes, too.

There is **no authentication** on keeping, updating or deleting a kept config —
like everything else here, anyone who can reach the page can do it. A list that other people's uploads join only
refreshes on a page load; the one you just kept appears at once.

## Assets are never cached

Static URLs carry the file's modification time (`webui.js?v=1788098129`) and
every response is sent `no-store`. Editing a script and reloading is otherwise
not enough — the page keeps the copy it already parsed, and a stale copy is
indistinguishable from a bug in the new one. Changing a file changes its URL, so
the browser has to fetch it.

The favicon is the one asset also served from a second, unversioned place:
`GET /favicon.ico` returns `static/favicon.ico` directly, because some
browsers and crawlers request that exact path regardless of what `<link
rel="icon">` says. Both pages still carry the `<link>` tags too — a PNG for
anything that reads them, the `.ico` again for anything that only trusts a
literal `favicon.ico`, and an `apple-touch-icon` for a phone's home screen.

## Versions

Every feature that lands on `autonomy` is tagged with an annotated
`vMAJOR.MINOR` tag whose message says what that version brings. v1.0 is the
first commit on `main`, the command-line converter this grew from; v2.0 is the
Kongress edition (`938badf`). A new feature bumps the minor number; a change
that reshapes the whole thing bumps the major.

The header shows the version ("v2.4") at the end of the slogan's line, linking
to that tag on GitHub. The number comes from `git describe --tags --abbrev=0` when the server
starts, so tagging is the only step — there is no version file to keep in step.
It is the newest tag reachable from the checked-out commit, which means a
server restarted on an untagged commit still names the version it builds on.
With no git or no tag the line is left out. Tags only resolve on GitHub once
pushed: `git push fork --tags`.

Every generated G-code file, the five macros included, opens with the same
version and a link to the site: `; Generated by Brushograph WebUI v2.4:
http://xn--bruograf-7wb.ignore.net/`. The host is brušograf.ignore.net in
punycode, because GRBL and FluidNC read any byte above 127 as a realtime command and a sender streams comments like any other
line. For the same reason the pipeline's own comments are plain ASCII.

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
