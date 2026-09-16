# Changelog

Changes on `autonomy` since it forked off `main` at `216288c`. Every feature is
tagged `vMAJOR.MINOR`. Each heading links to its tag on GitHub, and the tag's
message describes that version.

## [v3.0](https://github.com/f1adang/brushograph/releases/tag/v3.0) — 2026-09-17

The 𝔐𝔦𝔨𝔯𝔬 release.

- The 𝔐𝔦𝔨𝔯𝔬, the small openBrushograph of openBrushograph_hardware V6.0, is a
  model alongside the Mini. Its painting area is 65 × 100 mm, as found on the
  machine, above the colours along the bottom; its five-crucible CMYK holder,
  tray lift and zero.g sweep come from the CAD.
- The Model picker is the first thing in Machine setup, followed by the
  connection and controller type, then the containers.
- The Macro generator is part of Machine setup, below Save these settings,
  instead of a panel of its own.

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
