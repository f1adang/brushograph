# Changelog

Changes on `autonomy` since it forked off `main` at `216288c`. Each heading
links to its tag on GitHub, and the tag's message describes that version.

Versions are `vMAJOR.MINOR.PATCH`, and what moves says what changed:

- **MAJOR** for a different machine to use. v2.0 was the
  𝖅𝖜𝖊𝖎𝖙𝖊𝖗 𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘 Sonderedition; a release that earns
  one may carry its name in the heading as that one does.
- **MINOR** for a feature you would notice from the page or the paper — a new
  control, a new macro, a way of painting that was not there before.
- **PATCH** for work on a feature already released: a fault in it, a figure
  corrected, a motion made safer. Patches start at v2.7.1; before that there
  were none, and a version with nothing after the minor, such as v2.8, is one
  of those rather than a `.0` written short.

A version collects however many features are released together, one bullet
each, and is tagged once they are all agreed rather than per commit. Every
feature commit is followed by the commit that adds its bullet here, so a
version's heading appears with its first bullet and grows until it is tagged.

## [v2.14.0](https://github.com/f1adang/brushograph/releases/tag/v2.14.0) — 2026-09-22

- **The preview draws a stroke as wide as the brush lays it.** It used to draw
  every stroke at the same hairline width whatever the brush, so a filled shape
  came out as a bundle of separate lines with paper between them — the path was
  all there, and the picture looked hollow. Whether the fill covers is the one
  thing a preview is for.

- **Bed levelling, copied from openBrushograph Studio.** Canvas Height is one
  figure and a sheet of paper is not one height, and a watercolour brush shows
  the difference at a tenth of a millimetre — thin and dry where the paper is
  high, wide and wet where it is low. Take five readings, at the corners of the
  canvas and its middle, type each as its difference from Canvas Height, and
  every move made on the paper is written at the height the paper is at there.
  The plan view marks the five spots and prints the readings beside them. It is
  Studio's own scheme: four triangles about the middle reading rather than one
  plane through all five, because three points cannot see a twist and a corner
  that sits high is what a taped sheet does. Off until the five are measured.

- **Uploading the macros waits a moment between files, and tries a file again
  if it drops.** With eleven macros to send rather than seven, the machine
  started refusing part way through: it is an ESP32 finishing one file on its
  flash while being asked for the next. If it still gives up, the message now
  names the file it stopped at and mentions the other likely cause — a flash
  filesystem with no room left, which fails at the same file however long the
  wait.

- **A painting keeps 2 mm clear of the far end of each axis.** Max Width and
  Max Height are where the machine stops, and a painting that ran to one of
  them ended on the endstop: a photograph at full size on a 140 mm axis put 142
  strokes at exactly Y 140, and the machine hit the upper Y stop. The two size
  boxes are capped short of the limit now, and a machine file that asks for
  more has its painting scaled down to fit — both sides by the same amount, so
  the picture keeps its shape — with the run log saying so.

- **A concentric fill spirals inwards instead of painting a stack of separate
  rings.** Each ring used to cost a brush-down, and after outlining a big shape
  the machine would go and pick at the rings of a sliver beside it rather than
  work inwards, because that sliver was nearer. A shape is now one stroke that
  winds in to the middle: on a test photograph, 191 fewer brush-downs for the
  same picture and slightly less paint.

- **Clean Brush goes into the water in one move and presses 2 mm below Dip
  Depth.** It used to come down outside the cup and drive in across the rim,
  which is what a *pickup* does to bend the bristles back — needless for a
  brush that is about to be rinsed four times and wiped on three edges. And it
  stopped at Dip Depth, which rinses the tip; water gets into a brush that is
  bent against something, so it now leans on the floor for a moment each dip.

- **Four new macros stir the paint: mix-c, mix-m, mix-y and mix-k.** Watercolour
  in a crucible separates — pigment to the floor, water and methylcellulose
  above — and a cup that has stood overnight paints pale until the brush has
  worked it. Each file takes the brush into one cup and hops it about the floor
  sixty times at the Fast rate, quickly and at random, which mixes where a
  tidy sweep only swirls; then it rinses the brush and parks it. The stairs at
  the back of the cup are left out of the hopping. Run one again for a longer
  stir.

- **A dip into a colour cup is spread across that cup's width**, not the water
  cup's. The two are not the same size, and the colour cups were being dipped as
  though they were 10 mm wider than they are — not into the wall, but a
  millimetre off it where four were intended.

## [v2.13.0](https://github.com/f1adang/brushograph/releases/tag/v2.13.0) — 2026-09-22

- **Clean Brush washes in four dips, leaving the cup a different way each
  time**: up the stairs, over the left wall, over the right wall, up the stairs,
  and then the park at X0 Y0. The stairs are the wipe a job gives the brush at
  every pickup, so the wash begins and ends with it shaped the way a job expects
  to find it; the two in the middle are the wipe it never gets, since the swipe
  draws the same one line of the bristles every time. Note that on every machine
  here the water cup's **left** wall is off the end of the bed — it is the
  widest cup and it stands hard against the X origin — so that dip leaves up the
  stairs and the file says why. Moving the water cup a few millimetres to the
  right brings it in reach.

- **The rough time is the time the machine will actually take.** It was
  distance divided by feedrate, which is out by a factor of three on a real
  bed: a job reported at an hour and a half took about five. Almost nothing in
  a painting is long enough to reach the feedrate — at 20 mm/s² the machine
  needs 28 mm to get up to 2000 mm/min, and the middle stroke of a photograph
  is 6 mm — so what decides the time is how hard the machine accelerates. The
  estimate now does the arithmetic a controller's planner does, corner by
  corner, and counts the backlash take-ups, which are thousands of short
  stop-start moves and were being left out altogether.

- **Acceleration is a setting in mm/s², and every machine shows it.** It used
  to be the `M204` line it is written into, and it was hidden unless the
  controller was Marlin — but GRBL and FluidNC hold their own acceleration and
  have that line stripped, and it is the figure the time estimate turns on more
  than any other. If the estimate is out on your machine, that is the box to
  correct: one timed run tells you by how much.

## [v2.12.1](https://github.com/f1adang/brushograph/releases/tag/v2.12.1) — 2026-09-22

- **Clean Brush wipes the brush on the sides of the water cup.** The swipe up
  the stairs wipes one line of the brush, the same line every time, and a
  rinsed brush still holds water in the sides of the bristles. After its first
  swipe the wash now draws the brush out over the left wall and back, then the
  right — the two edges of a rectangular cup the swipe never touches. A wall
  that is off the end of the machine is not wiped, and the file says so.

- **The bend now lets go of the brush before it dips.** It crosses the rim —
  which is where the bending happens — and then travels the length of the
  container in clear air, so the bristles come back to themselves, and only
  then goes straight down to Dip Depth and stands there a moment before
  swiping out. Carrying the bend on down into the cup was why the brush never
  reached the bottom: a folded brush is a shorter brush, and pushing it further
  down does not unfold it. **The bend is also left off the first pickup of a
  run**: it undoes a set the swipe puts in, and at the start of a job nothing
  has swiped the brush.

## [v2.12.0](https://github.com/f1adang/brushograph/releases/tag/v2.12.0) — 2026-09-22

- **A photograph is cut into long strokes now, not into shapes to fill in.** The
  woodcut used to fill its shadows in solid and carry its midtones as hatching
  that broke into dashes wherever the tone lightened — and a brush is poor at
  both. It covers a solid by going round and round inside it, so a shadow came
  out as a map of nested rings, and every dash costs a lift, a trip for paint
  and a blot where the brush lands again. The strokes are traced along the
  picture's own directions now, and the tone is carried by how far apart they
  run: packed about two brush widths apart in the deepest shadow, opening out
  through the midtones, gone by the highlights. Nothing is filled in solid, a
  stroke is about a brush wide, and anything too short to be worth a brush-down
  is left out. On a test portrait at 132 mm with a 2 mm brush that is 48 strokes
  down to 33, with the middle one 11.5 mm long before and 40.2 mm now, for
  slightly less paint. **Hatching at 0** still fills the shadows in, since with
  no strokes to draw one with that is all that is left.

- **The speed settings ask for a number now.** Each of the three speed groups
  held a line of G-code — `G0 F1200` — in a text box, which on a FluidNC or
  GRBL machine was the only setting in the group you could see: the other two
  are Marlin commands and are hidden. It is a plain **Feedrate (mm/minute)**
  box, and the G-code is written around it. A machine file written before this
  opens with the numbers already in the boxes, and one carrying something more
  elaborate than `G0 F…` keeps it and is used exactly as it reads. The three
  boxes also have help on them now.

- **The brush is bent back the other way on its way into the cup.** Every swipe
  out of a container runs the same way — deep end, up the stairs, out — so the
  bristles were combed the same way on every pickup of every job and took a set
  that way. A pickup now comes down *outside* the container, on the side the
  brush returns from and low enough that the bristles meet the rim rather than
  clearing it, and drives in and down in one diagonal move: the rim bends them
  forward, and the run down the bay drags them forward again. It follows the
  swipe's own line backwards, so the bristles get only the flex they already
  survive, and it costs one move. clean.g and the container-tick macro dip the
  same way. Round cups are unchanged.

- **The macros move at the top speed the machine is set up for.** Six of the
  seven crossed the bed at the rate a stroke is painted at — F1200 where the
  machine is driven at F2000 — and a macro is not a painting: parking the
  brush, clearing the bed for a sheet of paper, washing and zeroing are all
  waiting. They travel at the Fast rate now and drop to the painting rate only
  for the marks they actually put on the paper, which is what a job does too.
  On a GRBL or FluidNC machine, where G0 already runs at the controller's own
  maximum, what this speeds up are the fed moves: the swipe out of a cup, a
  drawn tick, a gauge line.

- **No macro drives faster than the machine's own Fast feedrate.** zero.g swept
  to the far corner at F2100 whatever the machine was set to — that figure came
  off the hardware it was first tuned on — and a sweep that ends in the
  endstops on purpose is the last move that should be going quicker than the
  rest. Every feedrate in every macro is now held at or below the Fast speed
  group's. Anything already slower keeps its own figure, and a machine whose
  Fast rate is higher than the macro was written with is left alone. A macro
  that had a feed lowered says so in its header.

- **A photo is turned a quarter turn when that fills more of the paper.** The
  picture is painted onto the width and height whatever their proportions, so a
  portrait photograph on a wide bed used to come out narrow — and stretched. It
  is now laid so its long side runs along the canvas's: on a 151 × 124 mm bed a
  3:4 photograph goes from 93 × 124 mm to 151 × 113, half as much paper again.
  A colour photograph has always been laid out this way; a photo uploaded to one
  tray now is too, and on a machine whose bed is taller than it is wide it is a
  landscape photograph that gets turned. A picture that is **already black and
  white** is left the way up it arrived — it is your own artwork, not a
  photograph to be fitted — so switching a tray between the two changes the
  painted size, and the note under it says when a picture has been turned.

- **The black cup gets its colour picked up in a different place each time,
  like the others.** Black sits at the far end of the holder, and the spread of
  pickup positions was held inside the ground a job already covers by giving up
  the same distance on each side of the cup — which for the outermost cup is
  all of it. Every pickup from black went down the same line, on every job since
  the feature was added. The spread now uses whatever room there is on each
  side: on a holder whose black crucible is at the end of the travel that is
  half the bay instead of none of it, and the machine still never reaches
  further than it already did.

- **Detail means something at the top of the slider now.** It used to be nearly
  inert: everything in the cut is measured in brush widths, and the working
  resolution follows the slider, so the brush grew with it and the cut came out
  the same. Sliding it from end to end changed a test portrait from 19 strokes
  to 27, and hardly at all between 25 and 92. Detail now decides how much
  broader than the brush the cut's marks are drawn — half again as broad at 0,
  the brush itself at 100 — and with it the stroke spacing in the half-tones,
  how closely the strokes follow fine structure, and how short a stroke is
  worth keeping. The same portrait now goes from 13 strokes to 56, for the same
  amount of paint: the detail is bought with finer strokes, not with more
  painting time.

- **The woodcut preview comes back about twenty times faster** — 0.25 s instead
  of 4.8 s on a test portrait, 1.5 s instead of 8 s on a 3000-pixel one —
  because tracing strokes costs with how much line there is, where smearing a
  field along the flow cost a full pass over the picture for every step of it.

## [v2.11.0](https://github.com/f1adang/brushograph/releases/tag/v2.11.0) — 2026-09-21

- **Where the canvas starts and where a painting sits are two settings now.**
  Offset Y used to be both at once: the strip the containers stand in, which is
  a fact about the machine, and however far up the bed you wanted this picture.
  Moving a picture 5 mm up the paper therefore read as claiming the holder took
  5 mm more room, and cost the picture 5 mm of height. **Canvas Start Y**, under
  Machine setup → Canvas, is where the paintable area begins — the model sets
  it, 25 mm on the Mini and 19 on the 𝔐𝔦𝔨𝔯𝔬 — and **Offset Y** is how far
  past that this painting goes, 0 meaning flush with the start. A machine file
  written before the split opens with its old figure as the start and an offset
  of 0, so it paints exactly where it always did. The plan draws the start,
  labelled, whenever the painting does not begin there, and the run log says so
  before anything is painted if the canvas starts inside the containers.

- **Painting dimensions sits under the plan now**, outside the Machine setup
  fold, and carries the offsets and the canvas height along with the painted
  width and height. It is the one group that changes from one run to the next,
  and it is what the picture above it draws.

- **A painting opens at the width of the bed.** Width used to open at whatever
  the machine config was last saved with — a figure from some other picture on
  some other day, and on Pinkograph 132 mm of a bed that paints 151. It is now
  the widest the machine paints, with the height following the picture as
  before and the width narrowing again if the proportions make it too tall.
  Type a width and it stays yours: nothing after that moves it, not a new
  picture and not a wider bed. Both size fields also refuse a figure larger
  than the bed instead of taking it.

## [v2.10.6](https://github.com/f1adang/brushograph/releases/tag/v2.10.6) — 2026-09-21

- **The brush no longer stirs a rectangular cup. It picks the colour up in a
  different place each time instead.** A pickup is now a straight drop into the
  paint and the swipe up the stairs, and nothing else while the brush is down
  there — the swipe is what decides how much colour leaves the cup, and the
  stir before it picked pigment up on the way out and wiped it off against the
  paint on the way back, dragging the bristles sideways along the floor to do
  it. What mixes the cup now is that the whole motion moves: the dips are
  spread over five places across the bay, one pickup to the next taking
  opposite ends of it, so the paint is worked over its width rather than down
  one line of it. **Cup Dip Lanes**, where Cup Mix Sweeps was, says how many; 1
  puts every pickup down the middle. A cup too near the end of the axis to
  spread over — black on a holder that reaches the last of the travel — is
  dipped in the middle and said so in the run log. The same three-plate job
  came out 365 lines shorter and 3.4 m less travel, and 3.67 m of motion in the
  paint became none. clean.g's wash walks the lanes as well, so it rinses the
  width of the water.

## [v2.10.5](https://github.com/f1adang/brushograph/releases/tag/v2.10.5) — 2026-09-21

- **A photograph no longer fails with "nothing to paint" when most of it is
  paintable.** A tray whose picture has no shape wider than a single brush
  stroke is skipped now, named in the run log with the reason, and the other
  colours are painted. Before, one thin plate ended the whole run: a photograph
  at 30 × 30 mm with a 12 mm stroke lost cyan and black that way while magenta
  and yellow still had plenty of ink, and the message said neither which tray
  nor why. When every tray really is empty the run still stops, but it now
  names the two figures that decide it — the painted size and the stroke width
  under Infill line distance — since what can be painted is the picture's
  finest shape measured in stroke widths, and shrinking the painting does the
  same thing as widening the brush.

- **A painted size of zero is refused with a sentence** instead of a 500 and a
  traceback, and a negative one is refused at all — it used to flip the picture
  and paint it off the bed, which looked like it had worked.

- **The container messages in the run log are reported once per row**, not once
  per cup. Every holder is one straight row, so all five share a Y, and a
  clipped swipe used to say so five times over. Fifteen lines became two on the
  machine that prompted it.

## [v2.10.4](https://github.com/f1adang/brushograph/releases/tag/v2.10.4) — 2026-09-20

- **A job no longer drives into the endstop every time it dips.** On a machine
  whose containers sit at or below Y 0 — Brushparang's are at Y −3 — the brush
  entered each bay at its deep end, which was 13.5 mm below the bed, and hit
  the bottom stop instead. The axis stalls there and the controller's counter
  does not, so everything after the first dip was commanded 11 mm lower than
  the carriage actually stood, and what you saw was the *far* end of the canvas
  running into the **top** stop near the end of the painting. Dips are now kept
  on the bed. Where a bay's deep end is off it the brush enters further back
  and the swipe is shorter, which loads it with less paint: the run log says so
  when it happens, and the cure is to correct that container's Y in the form.
  The park at the end of a job could also be written half a millimetre below
  zero by backlash compensation, and no longer is.

- **A newly created 𝔐𝔦𝔨𝔯𝔬 can paint.** Every run on one failed outright, before
  a stroke was traced, because the generator demanded three settings that
  describe a round petri dish — how wide a chord the brush sweeps in the paint,
  and how far out and how high it wipes the rim — and the 𝔐𝔦𝔨𝔯𝔬 has no dish
  holder to have them for. Nothing uses them with the CMYK or custom
  containers, and they are optional now. A machine that does use round cups and
  is missing one is told so in the run log, since the sweep or the rim wipe
  quietly becomes no motion at all.

## [v2.10.3](https://github.com/f1adang/brushograph/releases/tag/v2.10.3) — 2026-09-20

- **`backlash.g` is drawn with a pen now instead of being painted.** Fit a pen
  where the brush goes, put paper on the bed and run it: it visits no cup and
  dips for nothing, so there is no paint to mix, nothing to wash, and no
  waiting for a cup to be filled before the machine can be measured. It is the
  same file under the same name, and its figures go in the same four boxes as
  before.

- **It measures at five places instead of two rows: the four corners and the
  middle.** Each is an upright pair and a flat pair meeting at a corner, so
  every station answers both axes where it stands. Backlash X and Backlash Y
  are the two stations at the X0 end, and the far-end boxes the two at the
  other; the middle is the check. Two stations at the same end that disagree
  tell you something two rows could not: that the play depends on where the
  gantry is standing along Y as well.

- **The sheet is spread over everything the machine can paint, not over the
  canvas the config is set to.** The figures go into the machine config and
  are used by every job on it, so they are read over all the ground those jobs
  can cover. The old sheet stayed inside the canvas: on a Mini set to paint
  132 × 89 it read X at 12 and 130.7 and took the whole of its Y reading at
  one height. The stations now stand at X 12 and 141, and at Y 32 and 141, of
  a bed that paints 151 × 156 — and a job's canvas sits inside them, so the
  compensation works between the figures rather than past them. Lay a full
  sheet of paper on the bed for it: it draws outside the canvas on purpose.
  Nothing, run-ups included, is commanded within 3 mm of either far end, since
  a move that finishes against a stop throws off every line after it.

- **Each gauge now prints as many pairs as its paper can keep apart**, widest
  dropped first, and the station legs are sized from what the gauges need
  rather than the other way round. On the 𝔐𝔦𝔨𝔯𝔬 that means an X gauge of four
  pairs, 0.5 to 2 mm, instead of five crowded ones. The file's own header
  names the gaps it was drawn with.

- **The version in the header links to this file now**, rather than to its own
  tag on GitHub. A tag's page says what the tag message says and nothing else;
  clicking a version number is asking what changed, and that is what is here.

- **A seventh macro, `containercenter.g`, paints a tick on the canvas at the
  X of every container.** A container position is the one setting with nothing
  to check it against: until now the only way to read one back was to watch a
  dip and judge by eye whether the brush went into the middle of the cup or
  into a wall. Put paint in the black cup and paper on the canvas and run it —
  nothing is lifted out and nothing is dismantled, and the marks go where a
  job paints. Sight each tick down to the cup it belongs to, or lay the holder
  along the row of them: a tick that does not line up with the middle of its
  cup is a position that wants correcting, and how far it misses by is the
  correction, in millimetres, into that container's X. Water is ticked too,
  and it is the one to correct first — every other cup is spaced from it. Only
  X is marked, because the cups sit in the strip of Y below the paper, so X is
  all a mark on the canvas can say about them; it is also the half that
  matters, since the spacing along the row is what auto-spacing guesses and
  what a rule measures worst. A container whose X falls past the end of the
  canvas is painted anyway and named in the file's header, so a wider sheet
  can be laid for it. A Classic machine has no black container, and there the
  file says so and paints nothing rather than dipping into a cup that is not
  there.

## [v2.10.2](https://github.com/f1adang/brushograph/releases/tag/v2.10.2) — 2026-09-20

- **The Choose file button on Black (K) opens a file picker again.** With the
  Classic dishes selected there is no black cup, so black's picture card is put
  away and everything on it switched off. A colour photograph puts the same card
  away for its own reason — it makes all four plates itself — and when the
  photograph went, it brought black's card back without switching it on again.
  The card sat there looking ordinary with a button that did nothing. The two
  reasons now agree with each other, so with Classic selected the card stays
  away, and with a CMYK holder it comes back working.

- **A colour photograph's file is called `photo-cmyk.gcode`.** It used to be
  called `photo_c3_c2_c1_c4_infill.gcode`: every tray number in painting order,
  which tells you which cups were dipped but not what the run was. A photograph
  separated into all four plates now says so. Fewer trays still list their
  numbers, `photo-c1_c2.gcode`, and those are the numbers on the form, so a file
  still matches its run without being opened. The trailing `_infill` has gone
  from every name — infill is a distance in millimetres, and the word said only
  that it was not zero.

- **Container positions are listed in the order the cups sit in the holder**,
  water first and then cyan, magenta, yellow — and black where the holder has a
  fifth place. They used to be listed in painting order, Water, Yellow, Magenta,
  Cyan, which is the opposite way round to the holder in front of you, so
  reading a position off the machine meant counting up from the bottom of the
  form. The picture cards are unchanged and still follow painting order, which
  is the order the job paints them in.

## [v2.10.1](https://github.com/f1adang/brushograph/releases/tag/v2.10.1) — 2026-09-19

- **The macros are plain ASCII now, like the jobs always were.** Five of the
  six opened with an em dash in their first comment, and every dip in any of
  them printed one more — sixteen in a backlash.g sheet. GRBL and FluidNC read
  any byte above 127 as a realtime command and a sender streams a comment like
  any other line, so those were characters the board acted on, in the one place
  nothing looks at the file on the way past: uploaded to the machine and run
  from its own SD card. Everything written for the machine now goes through one
  pass that keeps it inside ASCII, whatever it was typed with and whatever a
  config happens to be called. Job files are unchanged, byte for byte.

## [v2.10.0](https://github.com/f1adang/brushograph/releases/tag/v2.10.0) — 2026-09-19

- The **preview shows the picture again** rather than the picture with a
  sawtooth through it. Compensation writes the coordinates in the machine's
  terms — low by the play while an axis travels one way, as they are while it
  travels the other — and the preview was drawing them as they stood, which
  put a step of the play at every reversal. It now reads the shift the file
  states at each change and takes it back off, so what you see is the path
  that was asked for. On Pinkograph that step was 2.3 mm of jitter across
  every plate; there is none now.

- **The wash climbs on its way to the water.** At the end of every colour the
  brush either hopped in the air before setting off for the wash or crossed
  the bed flat and dropped at the far end of it, where every other trip to a
  container lifts as it travels. It now ramps from wherever the painting
  finished, which is one move instead of two and no height held over the
  paper on the way.

- **A colour starts at full strength.** Every tray begins by going for paint,
  because the tray before it left the brush washed and standing in water — and
  that trip made a single dip, which is a re-ink and not a loading. The first
  strokes of each colour came out pale and came up to strength somewhere along
  the way. It now mixes the way the opening sequence does, Prepare Paint Count
  dips of it. Set that to 0, as a plotter does, and the trip is not made at
  all: it used to be made anyway and dip nothing, wiping a rim the brush was
  nowhere near.

- **Update puts an uploaded machine on the server too.** The button only ever
  offered to write back a machine that was already kept there, so keeping one
  you had uploaded and edited meant downloading the file and uploading it
  again with the box ticked. Now it keeps it from where it is. A name already
  taken is still never written over — that is somebody else's machine, and
  yours goes in beside it as workshop-2.conf, with the page saying which name
  it got.

- **The colour cards step aside for a photograph.** Load a colour photograph
  and the Cyan, Magenta, Yellow and Black cards are put away until you remove
  it, because the photograph makes those four plates itself. A picture left on
  one of those cards used to replace the plate the photograph had made for it,
  with nothing on the page to say so. Anything chosen there is kept, and comes
  back with the card. A fifth colour keeps its card either way.

- The play in an axis can now be given at **both ends of the bed**, and the
  compensation follows a straight line between them. It is not the same figure
  at both ends: Pinkograph's sheet reads 1.9 mm of X play at one end of the bed
  and 1.3 at the other, with Y steady at 1.3 to 1.2. One figure cannot
  compensate an axis like that — the best of them, the mean, is still 0.3 mm
  out at each end of every plate, which is a third of a brush stroke and is
  what makes the colours miss each other. Two figures bring the average error
  on a test job from 0.077 mm to 0.019, and the points more than a tenth of a
  millimetre out from a third of them to a fifteenth. **Backlash X** and
  **Backlash Y** are now the readings at the X0 end, and there are two new
  boxes for the far end; a config that names only the old two is compensated
  with one figure everywhere, exactly as it was before, and its file comes out
  unchanged. Paint backlash.g to fill the new boxes in. The job gains no extra
  moves and runs no slower — only the coordinates change.

- **backlash.g measures across the whole bed.** Its test pairs used to sit in
  one corner of the paper: all three Y pairs at the same X, and the X pairs in
  the left quarter of their own box. A play that changes from one side of the
  bed to the other is invisible there, which is the fault it most needs to
  show — Pinkograph's X play runs 1.9 mm at one end and 1.3 at the other, and
  that sheet read it as the same figure three times. Both rows now run the
  full width, three pairs each, and the left and right pairs of each row are
  the two figures to type in, with the middle one as the check that the play
  really does run in a straight line. A pair that opens out along its own
  length is the change drawn as a picture of itself, not a fault in the
  painting. The two gauges keep their five known gaps and are laid out with
  the same clear space after every pair whatever gap it draws: the 𝔐𝔦𝔨𝔯𝔬's
  widest pair used to have less room to the next pair than the gap it was
  printing.

## [v2.9.0](https://github.com/f1adang/brushograph/releases/tag/v2.9.0) — 2026-09-19 — Backlash Studio Release

- Backlash compensation compensates. It never did: it added a corrective move
  at every reversal, but sent it the way the brush was already going, so the
  brush was dragged half a millimetre past each corner and then landed on the
  corner exactly as far out as it would have with the setting switched off.
  Every reversal in a job — about 140 in a small one — got a little tail
  painted past it for nothing. The file is now written in the machine's terms
  instead of the picture's: while an axis is travelling one way its
  coordinates are written low by the play, while it travels the other they are
  written as they are, and at each turn a short move crosses the slack without
  the brush following it. On a test job of 686 points, seven are more than a
  tenth of a millimetre out and all seven are in the opening dip or the park
  at the end, with the brush over water or in the air. Before, all 686 were
  out. Nothing is sent past the far end of an axis any more either, which is
  what once put the black plate 3 mm to the left of the colours.

  Worth knowing if you had a figure in the box already: it used to change only
  how long that stray tail was, and it now moves the painting, so a figure
  that is too large costs exactly what one that is too small does. If you have
  never measured yours, paint backlash.g below and read it off.

- A sixth macro, backlash.g, paints a sheet for measuring that play, which
  until now there was no way to find out. It draws two blocks of paired
  strokes, one for each axis, set apart and read on their own: each pair is
  the same position painted twice, come at from one side and then the other,
  so the gap between the two marks is the play. Three pairs an axis, spread
  across the bed, because a belt slack at one end and a nut loose all the way
  along do not look the same.

  Beside each block is a gauge — five more pairs at 0.5, 1, 1.5, 2 and 2.5 mm,
  drawn so that the play cannot open or close them. Find the gauge pair your
  test pair looks like, and that is the number for the box, to about a tenth.
  A rule is no use here: a brush stroke is a millimetre wide and half a
  millimetre between two wet marks is not something anyone measures off paper,
  but matching one pair against five known ones is easy. Each block has its
  own gauge in its own direction, because a gap between two flat lines does
  not look like the same gap between two upright ones.

  Put paper on the bed and paint in the cups, and expect 32 strokes and
  16 dips. It paints uncompensated whatever the Backlash compensation box
  says, so it measures the machine and not the setting.

## [v2.8.6](https://github.com/f1adang/brushograph/releases/tag/v2.8.6) — 2026-09-19

- A kept config can be deleted from the page, beside the Download and Update
  that already act on it. Machines could be added to the list and written
  over but never taken off it, so a bed that was dismantled, a name typed
  wrong, or a config made to try something out stayed in everyone's pulldown
  until somebody went to the server and removed the file by hand. Delete asks
  first, and says what it is asking: a kept config is in the machine list for
  everyone using this server, so it goes for them too and not only from the
  page it was pressed on. Escape and the backdrop both count as no. The file
  goes, the pulldown loses it and the form goes back to its placeholder rather
  than standing there editing a machine that is no longer there — but
  webui_configs is a git repository of its own, and the removal is committed
  to it like every other write, so what was under that name can still be
  recovered. Offered only for a config kept on the server: an uploaded one is
  the session's own and there is nothing on the server to remove.

- calibrate.g lifts to Go In Tray Lift before it crosses to the canvas. It was
  the one macro here that set off from wherever it found the brush without
  clearing anything first, on the grounds that it is meant to do only the dot.
  But where these macros leave the brush is X0 Y0 at Dip Depth + 1, which on a
  holder whose water container covers the origin — Pinkograph's does — is
  inside that container, under a rim at Z9. Going straight to the canvas
  origin from there dragged the brush through the container wall, and the
  calibration dot it then placed was measured against a brush that had just
  been shoved sideways. The trip begins at the height that clears the rims
  now. The dot itself is unchanged: still Z0 at the canvas origin, still
  parked at Z10 above it.

- A machine can be started from a model instead of from a file. The pulldown
  was a list of machines with no way to add one that did not already exist
  somewhere: a new bed meant finding somebody else's config, editing every
  figure in it, and hoping nothing was left over. “+ New machine…” sits at the
  bottom of that list, asks for a model and a name, and writes out that
  model's own defaults under it — travel limits, canvas offset, the containers
  spaced along from where the holder has room for them, and the container
  heights of the shape that model can actually hold: the petri dish's if it
  takes one, the printed crucibles' if it does not. The rest is what the form
  always offers, so every control is present; a config that omits a section
  simply has no control for it, and a new machine would have no way to gain
  one. It is kept the way an upload with “Persist config on server” is kept,
  including never writing over a name that is already taken — that config is
  somebody else's machine — so it joins the list, is selected, and opens in
  the form ready to be checked against the bed it was named for.

- The wash stays on ground the machine can reach, whichever containers it
  washes in. A container is deeper than the strip it stands in, so both shapes
  reached south of the origin: the rectangular bay put its near edge at Y -4.5
  on Pinkograph, and the round dish's diagonal sweep — 15 mm of enter radius
  around a tray at Y 6 — asked for Y -4.6 on Brushparang. There is nothing
  down there to dip into. zero.g backs three millimetres off the Y endstop and
  calls that spot Y0, so Y -3 is the stop itself, and every wash drove into it
  three times a file. What a move loses against a stop it loses for the whole
  of the rest of the file, which is how a wash ends up moving the painting
  that follows it. Both are clipped to the origin now, the clamp the stir
  across X was already given and for the same reason, and the round sweep is
  skipped outright where there is no room left for one. clean.g dips at Y0 on
  both machines; the swipe up the stairs to Y16.5, which is what wipes the
  brush, is untouched.

## [v2.8.5](https://github.com/f1adang/brushograph/releases/tag/v2.8.5) — 2026-09-19

- The brush stirs a rectangular cup before it climbs out of it. A round cup has
  always swept a chord down in the paint; a crucible was entered at the deep end
  and drawn straight up the stairs, one pass through the paint, mixing nothing
  and picking up what one pass picks up. It now sweeps across the bay at dip
  depth first — across X, the one direction that stays down in the paint, since
  the stairs climb along Y — and only then swipes out. Before rather than after,
  because the swipe up the stairs is also what wipes the brush. Cup Mix Sweeps,
  beside Cup Swipe Exit Z, says how many; 0 is the old motion. The sweep keeps
  15% of the cup's width off each wall and uses the water cup's greater width
  when it is in the water. clean.g's wash stirs to match.
- No more hop in the air at the start of a run or before the wash at the end of
  one. The trip to a container begins by lifting off the paper, which is right
  when the brush is standing on it and nonsense when it is not: at the start of
  a run and on the way to the end-of-tray wash it dropped to the between-shapes
  clearance and immediately climbed back out of it. It is only made from the
  paper now. Two more no-op lines went with it — a second lift written before
  the wash, where the trip to the water lifts anyway, and a lift between the
  wash's three entries, which the entry before it already ended at.
- The lift and the trip to the containers run together, and so do the trip back
  and the descent. The brush used to stand still while Z went to Go In Tray
  Lift, fly across level, and stand still again at the far end while Z came
  down; now Z runs with the travel. Going for paint it lifts clear of the paper
  where it stands, then climbs to Go In Tray Lift as it crosses the canvas.
  Coming back it holds that height until it is out of the containers, then
  comes down to Move To Other Shape Lift as it crosses the canvas, arriving one
  short drop above the paper.
- Z eases in and out of the ramp rather than starting and stopping dead. At
  one steady rate it changed rate in a single step where the ramp met the
  level leg beside the containers, and a planner reads that as a corner and
  slows through it — the hesitation the ramp was meant to be rid of. Z now
  moves slowest at both ends of a ramp and quickest in the middle, so it is
  already still where the level leg picks up and the two read as one move.
  Drawn as a dozen chords, which is what a controller makes of any curve. On
  the 103 mm ramp Pinkograph runs, the step into the level leg goes from 4.99°
  to 1.18° and no join inside the ramp passes 2.08°; across every ramp in a
  four-plate job the worst join is smaller than the single step it replaces,
  by about two and a half times. It is also the safer curve, holding Z nearer
  the tray lift at the container end, which is the end with the rims.
- The ramp runs at one steady rate and finishes where the brush arrives: hard
  against the container going out, on the spot it is about to paint coming
  back. What it may not do is ramp over the containers — stretched across the
  whole trip it is below their rims while it is crossing them, passing over the
  yellow crucible at Z 6.2 with the rims at 9 on a canvas offset 25 mm out. So
  it runs over the open bed and stops where the path first meets a container's
  mouth, the few millimetres from there being flown level at Go In Tray Lift,
  which clears the rims by design. That is the mouths themselves, taken 15%
  large so the walls count: on Pinkograph the climb now runs to Y 23 rather
  than stopping at Offset Y 60, which is 103 mm of the 130 mm trip against 66.
  The trip that loads the brush before a tray's first stroke is made from
  wherever the brush was parked rather than from the canvas, so that one still
  lifts clear before it sets off.
- A job parks the brush at X0 Y0, then at Dip Depth + 1 — where home.g,
  clean.g and zero.g all leave it, so there is one parking place to know
  rather than two. It used to stop over the water container at Z 0. On a
  holder whose water crucible is wide enough to cover the origin, as
  Pinkograph's is, that was very nearly this spot already.
- Nothing goes past the ground a job already covers: the containers it dips in
  and the canvas it paints. The stir was bounded by the model's zero.g corner
  instead, which is not a limit at all — zero.g drives into the endstops on
  purpose, that being what zeroes the machine. So the stir in the black
  crucible, the outermost one, ran the carriage into the stop. Steps lost there
  are lost for the rest of the file, and black is painted last, so the whole
  black plate came out about 3 mm to the left of the colours.
- The same bound is put on the backlash take-up, which was the other way into
  the stop and is older than the stir. A take-up overshoots the way the head
  was already going, so leaving the black crucible at X 156 on a machine that
  ends at 156 it asked for X 156.5 — every time the brush went for black. It is
  clipped to the end of the range now, and skipped where there is no room, so a
  correction is only ever as large as there is room for.
- A stir stays centred on its cup, and gives up the same distance on each side
  when one side runs out first, rather than being cut on the far side alone and
  left working the near rim. Black's crucible now has no room to stir at all —
  it is the furthest thing out — and is dipped without one; the log says which
  cups those are.
- The painted size is fitted to what the machine can actually paint. Max Width
  and Max Height are the machine's limits measured from the origin, and a
  painting starts at the canvas offset — the strip the containers stand in — so
  the largest painting is the limit less that offset: 131 mm tall on
  Pinkograph, not 156. Matching the height to an uploaded picture's proportions
  compared it against the limit alone, so a photograph 151 mm wide came out
  149 mm tall and ran 18 mm past the end of the bed. It now narrows the
  painting until it fits instead of squashing it — that photograph becomes
  132 × 130 — and says so. Switching model fits against the same figures, and
  the Height field carries the limit as its own, so a height typed by hand is
  refused rather than painted off the bed.
- The machine sketch draws the bed at Max Width and Max Height, where it drew
  it at the offset plus the limit. That was a bed 25 mm longer than the machine,
  added because a full-size picture otherwise hung over the edge of it — which
  it did, because the size was not being fitted. A canvas that still overshoots
  is now drawn overshooting. The two kept configs carried such a size, 151 mm
  tall against 131 and 119 paintable, and are corrected; every config saved
  from an actual session was already inside the limit.

## [v2.8.4](https://github.com/f1adang/brushograph/releases/tag/v2.8.4) — 2026-09-18

- Black knocks out the colour plates, a new switch beside Ink cutoff, on by
  default. A paper profile writes a press black — pure black converts to C 60%,
  M 50%, Y 54%, K 95% — because on paper those tints are a colour bed that keeps
  the key plate from looking brown. A press screens them; the cutoff here makes
  each one a solid brush pass, laid down and then covered by the solid black
  pass that follows. Leaving them off changes nothing you can see and more than
  halves the painting: a test photograph goes from 50.1% of the page painted to
  21.2%, with the yellow plate — 99% of it under the black — dropping from 9.6%
  to nothing, one tray fewer to dip and drag. Untick it where the trays are out
  of register: painting the bed means a black pass that lands a little off shows
  colour at its edge rather than bare paper.

## [v2.8.3](https://github.com/f1adang/brushograph/releases/tag/v2.8.3) — 2026-09-17

- The G-code preview counts cup dips again. It took any Z below the canvas for
  a dip, and the dip now sits at or above the paper, so every job showed 0 dips
  and its cup trips as travel or painting. The G-code now marks each dip with a
  `; dip` comment, which the preview counts, drawing the moves made down in the
  cups in the cup colour. That holds whatever the dip depth, including one equal
  to the canvas height. Files generated before this are read by height, from
  the form's Canvas Height and Dip Depth.
- zero.g sets its zero point 1 mm further from the Y endstop, so moves to Y0
  no longer bang into it.
- Machine setup shows each speed group's Acc and Feedrate 2 only when the
  controller is Marlin. Other controllers have those lines stripped from the
  G-code, so the fields changed nothing. Hidden, not cleared: switching back
  to Marlin brings the figures back.

## [v2.8.2](https://github.com/f1adang/brushograph/releases/tag/v2.8.2) — 2026-09-17

- Large uploads are shrunk before processing — to 2400 px on the long side for a
  photograph, 4000 for a black-and-white picture — keeping their proportions, so
  placement and orientation are the original's. An 8000 × 6000 photograph's CMYK
  G-code takes 2.6 s instead of 31.9 s, and its preview 1.6 s instead of 7.9 s.
- Pictures on the tray cards are turned upright from the camera's orientation
  tag, as the browser already did when setting the painted height: a phone photo
  stored sideways is no longer painted sideways and stretched.

## [v2.8.1](https://github.com/f1adang/brushograph/releases/tag/v2.8.1) — 2026-09-17

- Multi-colour jobs are painted yellow, magenta, cyan, then black, whatever
  order the config lists its colours in; other colours go before black. The
  tray cards, the plan's painting order, the G-code file name and a saved
  config's `color_order` follow it.

## [v2.8](https://github.com/f1adang/brushograph/releases/tag/v2.8) — 2026-09-17

The 𝔐𝔦𝔨𝔯𝔬 release.

- The 𝔐𝔦𝔨𝔯𝔬, the small openBrushograph of openBrushograph_hardware, is a model
  alongside the Mini. Its painting area is 65 × 100 mm, as found on the machine,
  above the colours along the bottom. Its travel is counted off the racks the
  hardware release actually ships, and zero.g sweeps to a far corner it can
  reach.
- Both models' CMYK holders and cups follow the settled design in
  openBrushograph_hardware's `Extras/CMYK_ColourContainers` and
  `colourContainers.scad`: the Mini's crucibles on 23.6 mm centres, the
  𝔐𝔦𝔨𝔯𝔬's on 16 mm. The plan draws each crucible at its outside size, with its
  stairs and swipe, in its holder plate.
- **Auto-space containers**, the Container setup picker (either way) and the
  Model picker set up the whole holder: positions in line with the water
  container, and the lift, dip depth and swipe exit its design gives.
- A **Custom** container setup takes cup widths, swipe depth and a new cup
  spacing from the form, defaulting to Pinkograph's holder.
- The Model picker is the first thing in Machine setup, followed by the
  connection and controller type, then the containers. The Macro generator is
  part of Machine setup, below Save these settings, and calls paper.g the
  routine for replacing paper.
- Container positions reach the machine to a hundredth of a millimetre instead
  of being cut to whole millimetres.
- Configs kept on the server are under version control: every upload and update
  is a commit in `webui_configs/`, naming the address it came from.

## [v2.7.1](https://github.com/f1adang/brushograph/releases/tag/v2.7.1) — 2026-09-17

- The machine plan draws the bed from the origin to the canvas offset plus
  Max Width and Max Height, so a full-size picture on a Mini sits inside the
  bed instead of running past its top. The bed's label sits above its edge.
- **Auto-space containers** lines every container up on the water
  container's Y as well as spacing them along X.

## [v2.7](https://github.com/f1adang/brushograph/releases/tag/v2.7) — 2026-09-16

- G-code generation is about three times faster: a four-tray job that took
  8 s takes under 3 s. The G-code produced is unchanged.
- Playing the G-code preview no longer bogs the browser down: a large job
  plays smoothly in Firefox too.
- The G-code preview and the colour photograph's plates are shown on white
  in every theme, so the paint colours read true.
- The status line while generating no longer says it takes a few seconds per
  tray.
- A Model picker at the top of The machine chooses between the Mini and the
  𝔐𝔦𝔨𝔯𝔬 of openBrushograph_hardware V6.0. Choosing one sets the travel limits,
  canvas offset, tray lift and container spacing, and shrinks the painted size
  to fit; going back restores what the config said. The 𝔐𝔦𝔨𝔯𝔬 uses its own
  five-crucible CMYK holder and has no Classic containers. The plan, clean.g,
  zero.g's far corner and the swipes in a job follow the model.

## [v2.6](https://github.com/f1adang/brushograph/releases/tag/v2.6) — 2026-09-16

- The CMYK container setup is called CMYK instead of Modern in the picker.
- With a colour photograph loaded, the note under the painted size says the
  picture is auto-rotated and scaled as needed to maximize the printing area.

## [v2.5](https://github.com/f1adang/brushograph/releases/tag/v2.5) — 2026-09-16

- Choosing Classic containers sets the machine up for the low petri dishes of
  openBrushograph_hardware: dip depth, sweep and wipe radii and lifts from the
  dish, with Z 0 where the dishes stand.
- Classic containers have four cups, so no black: its position and picture are
  hidden while Classic is selected, and the plan view, G-code and saved config
  leave it out. The plan view draws each petri dish.
- **Auto-space containers** spaces the cups off the water cup at the CAD
  positions of whichever holder is selected: 45, 89 and 133 mm for the petri
  dish holder, 39, 73, 107 and 141 mm for the modern one. One short note above
  it replaces the holder descriptions.
- Cup Width, Cup Width Water and Cup Depth are gone from the form and the config;
  the holders' CAD sizes are used instead. Cup Shape is now called Container
  setup.
- The checkbox for keeping an uploaded config reads "Persist config on server".

## [v2.4](https://github.com/f1adang/brushograph/releases/tag/v2.4) — 2026-09-16

- The page header shows the WebUI version at the end of the tagline, linked to
  its tag.
- Every generated G-code file and macro opens with the WebUI version and a link
  to the Brušograf site. The G-code header drops its bare "Brushograph WebUI"
  and controller lines, and its remaining comments start with a capital letter.
- This changelog.

## [v2.3](https://github.com/f1adang/brushograph/releases/tag/v2.3) — 2026-09-16

- Machine setup sections renamed to Canvas, Brush control and Paint management.

## [v2.2](https://github.com/f1adang/brushograph/releases/tag/v2.2) — 2026-09-16

- A portrait colour photograph is turned on its side so it fills the painted
  width.
- The painted height follows the picture's aspect ratio automatically; the
  Match image button is gone.

## [v2.1](https://github.com/f1adang/brushograph/releases/tag/v2.1) — 2026-09-16

- Machine configs can be kept on the server for everyone, picked from the
  machine list, and updated in place.

## [v2.0](https://github.com/f1adang/brushograph/releases/tag/v2.0) — 2026-09-16 — 𝖅𝖜𝖊𝖎𝖙𝖊𝖗 𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘 Sonderedition

- The Kongress theme, set in UniFraktur, with the whole interface in German.

## [v1.10](https://github.com/f1adang/brushograph/releases/tag/v1.10) — 2026-09-12

- A single colour photograph is converted to CMYK and thresholded into four
  plates, with a preview of the plates.

## [v1.9](https://github.com/f1adang/brushograph/releases/tag/v1.9) — 2026-09-11

- Macro generator: `zero.g`, `home.g`, `paper.g`, `clean.g` and `calibrate.g`
  are built from the machine setup and uploaded to the controller.
- Machine setup and macros are grouped under The machine; the real logo and a
  favicon.

## [v1.8](https://github.com/f1adang/brushograph/releases/tag/v1.8) — 2026-09-11

- CMYK painting: rectangular containers loaded with one swipe up the stairs, a
  bay for black, and a measured water bay.

## [v1.7](https://github.com/f1adang/brushograph/releases/tag/v1.7) — 2026-09-09

- A finished job can be sent to the machine and started from the page.

## [v1.6](https://github.com/f1adang/brushograph/releases/tag/v1.6) — 2026-09-08

- The interface is regrouped around the job, not the config file.
- Themes chosen in the footer: Pinkograph, Coconut and UwU, with the plan and
  preview drawn in the theme's colours.
- Sessions survive a server restart, transparency is laid over paper, and the
  config is saved with Download Machine Config.

## [v1.5](https://github.com/f1adang/brushograph/releases/tag/v1.5) — 2026-09-05

- The brush is loaded before the first stroke and for every colour, lifts
  before travelling, and stays off the paper after a wash.

## [v1.4](https://github.com/f1adang/brushograph/releases/tag/v1.4) — 2026-09-02

- A planar geometry engine draws the fill from a distance transform, replacing
  OpenSCAD and PrusaSlicer.
- Trays are prepared in parallel; faces are found with a DNN; Insta face
  filter for portraits.

## [v1.3](https://github.com/f1adang/brushograph/releases/tag/v1.3) — 2026-09-01

- Configurable dip depth and backlash compensation.
- Shapes too thin to outline are painted as a centreline.

## [v1.2](https://github.com/f1adang/brushograph/releases/tag/v1.2) — 2026-08-30

- Photos are cut into two-tone woodcuts, with hatching that follows the form
  and optional subject isolation.
- G-code preview, files named after the picture and colours, and a calibration
  macro.

## [v1.1](https://github.com/f1adang/brushograph/releases/tag/v1.1) — 2026-08-30

- The Brushograph WebUI: load a machine config, upload pictures per tray, and
  download brush G-code.
- Honours `controller_type` (no Marlin-only codes for GRBL/FluidNC), chains
  brush strokes, and matches the painted height to the picture.

## [v1.0](https://github.com/f1adang/brushograph/releases/tag/v1.0) — 2025-04-27

- The command-line converter on `main` this fork builds on.
