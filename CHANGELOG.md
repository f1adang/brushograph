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
