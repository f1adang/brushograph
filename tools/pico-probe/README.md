# Probe Pico

A 3D Touch (a BLTouch clone, Twotrees / MKS) on a Raspberry Pi Pico 2 W, which
maps a brushograph's bed over WiFi with nothing wired to the machine. It is
carried from machine to machine and mounted in place of the brush. It writes
the same CSV as `../probescan.py`, so the file loads with **Probe map** in the
Bed levelling group like any other probe scan.

It is an addition to `probescan.py` and `laserscan.py`, not a replacement.
`probescan.py` has FluidNC's probe input and G38.2, and stops on the step; this
has neither, and gets round that (below).

## Wiring

| Pico 2 W | Sensor |
|---|---|
| pin 40, VBUS | red, +5 V; capacitor + leg |
| pin 38, GND | brown, GND; capacitor − leg |
| pin 20, GP15 | orange, control (servo pulses) |
| pin 19, GP14 | white, trigger out, **through 1 kΩ** |
| pin 18, GND | black, GND |
| pin 36, 3V3(OUT) | optional 10 kΩ pull-up to pin 19 |

A 220–470 µF electrolytic across 5 V and GND keeps the solenoid's spikes off
the Pico's supply. No level shifter: the RP2350's GPIOs are 5 V-tolerant while
it is powered, and sensor and Pico are powered from the same USB. No pull-down
on GP14 — RP2350 erratum E9. The colours are the usual BLTouch ones; clones
vary, and the sensor's own board says which is which.

### The display (optional)

A 0.91″ OLED (SSD1306, 128 × 32, I²C) on I²C1, on the right-hand side:

| Pico 2 W | OLED |
|---|---|
| pin 36, 3V3(OUT) | VCC — **3.3 V, never 5 V** |
| pin 33, GND | GND |
| pin 32, GP27 | SCL |
| pin 31, GP26 | SDA |

The modules carry pull-ups on SDA and SCL to their own VCC, so at 5 V they
would put 5 V on GP26 and GP27, which are among the RP2350 pins that are *not*
5 V-tolerant. The four pins come in different orders on different boards; go
by the labels on the module.

It shows four lines: the Pico's address (so nobody needs `probepico.local`,
which many phones cannot look up), the machine and its state, then Z and the
pin, or during a scan the point and the minutes left. `display.py` is the few
commands a 128 × 32 SSD1306 needs, on MicroPython's own `framebuf`; the rp2
firmware has no `ssd1306` module. Without a display, or with one that stops
answering, it does nothing. It is not refreshed during a coarse descent: a
refresh holds the loop for 13 ms, which at 200 mm/min would add 0.04 mm to
the coarse stop's overshoot.

## Installing

1. Hold BOOTSEL while plugging the Pico in; it mounts as `RP2350`.
2. Copy MicroPython for the Pico 2 W onto it (`RPI_PICO2_W-…-v1.29.0.uf2` from
   micropython.org was used). It reboots as a serial port.
3. Copy the firmware:

   ```bash
   pip install mpremote
   mpremote cp probe.py fluidnc.py scan.py display.py index.html main.py : + reset
   ```

   and the h4xx0r theme's fonts, from the WebUI rather than a second copy in
   the repo:

   ```bash
   mpremote mkdir :fonts + cp ../../webui/static/VT323.ttf ../../webui/static/Silkscreen.ttf \
       ../../webui/static/PressStart2P.ttf :fonts/
   ```

4. With no WiFi set it opens its own network, `probepico-setup`
   (password `brushograph`): join it, open http://192.168.4.1/, and set the
   workshop WiFi under Settings. It then lives at http://probepico.local/.
   `config.json` on the Pico holds the WiFi, the machines and the scan
   settings; it is not in the repo.

The onboard LED is on steadily when it is on the WiFi and blinks while it
offers its setup network.

## Using it

Add each machine under Settings with its FluidNC address (`parang.local`) and,
if the pin is not where the brush would be, its offset. Connect, jog the probe
to a few mm above the first point, and **Touch here** a few times to see how
repeatable the sensor is before a full scan. **Stop** stops a scan between
steps; the points so far are already in the file.

The theme is chosen at the foot of the page and remembered per browser:
**Default** follows the device, **Dark mode** holds dark, and **h4xx0r** is the
Brushograph WebUI's green phosphor terminal, ported value for value from
`webui/static/webui.css` (webui/README.md, *Themes*), with the cursor blinking
at the end of the log. Its fonts are served by the Pico and cached by the
browser; everything else is sent `no-store`.

The grid is kept per machine and starts at the calibration dot, X 5 and
Canvas Start Y + 5 (Y 30 on a Mini), because that is where the map is read as
nought (webui/README.md, *Where nought is*). A file is named after the machine
and the browser's clock: `picoprobe-parang.local-20261109-183000.csv`.

**The grid reaches both edges.** It started as `probescan.py`'s: from the
first edge, a step at a time, while not past the second, which stops short of
it whenever the step does not divide the span. A scan of X 0–152, Y 30–140 at
23 mm took 35 points and ended at X 138, Y 122, leaving 14 mm along X and 18
along Y unmeasured, read off the map's edge instead. Now each span is cut into
as many equal gaps as the step needs, so the step is the widest gap there can
be: that scan is 8 × 6 = 48 points, 21.71 × 22 mm apart, and the page says so
beside the fields. A span the step divides comes out as it did. The map takes
uneven figures as they come (`levelmap.surface` keys its columns on the X
values as written, the same in every row).

## Continuing a scan

A scan that ended early -- stopped, failed, or the Pico restarted -- goes on
in the same file: **Continue** beside it in Scans, or **Load a CSV to
continue…** for a copy kept elsewhere, which is put on the Pico first under
its own name (a browser's ` (1)` taken off; a different file of the same name
already there is refused, not overwritten).

The file holds the points, not the grid they came from, so the grid on the
page has to be the one the scan was started with, and every point in the file
is checked against it, in order, to a micrometre or two. A wrong X range or
step shows at the file's second point and is refused, naming the point and
the grid. A Y range that ends sooner or later than the scan's cannot be told
from a file that stops partway, so the page says which grid it is about to
finish.

It goes on after the last point with a reading. The misses after that are
measured again: a scan that stops by itself stops on a run of them, and
they are the probe's failing, not the bed's. A nan further back stays.

Before going on, it touches the last point measured again. Z has to read as
it did there, within two fine steps, or the two halves are two maps: FluidNC
zeroes where it stands at power-on, and the paper may have been moved. If it
reads otherwise, every reading from there on is shifted by the difference,
and the log says by how much. So the probe goes a few mm above that point
first; **Move above it** takes it there at the height it stands.

Pinkograph's stopped 2236-point scan (*Three misses in a row*, below) checks
out as 883 points kept (882 readings and one miss among them, at X 88.8
Y 36), the 185 misses after them to go again, and goes on at X 151 Y 78 after
touching X 148.039 Y 78, which read −5.639.

## The sensor, measured

On the bench, MicroPython 1.29, internal pull-up, 1 kΩ in the trigger line:

| | Trigger output |
|---|---|
| At rest, deployed, stowed | low |
| Touch | a **9 ms** high pulse; the sensor pulls its pin up by itself |
| ~290 ms after a touch | high, and stays high through deploy and stow |
| Reset (2190 µs) | low again |

While the output is held high the sensor ignores deploy, so every probe is
reset → deploy → touch. The touch is caught by an interrupt: the scan's loop
spends most of its time waiting on the network and could miss 9 ms polling.
Servo pulse widths are Klipper's (`bltouch.py`): deploy 650 µs, stow 1475,
self-test 1780, reset 2190. Each is held 700 ms.

## How a reading is made without the probe input

FluidNC never sees the touch, so it cannot stop on it. Stopping the axis from
the Pico stops it late by however long the WiFi takes, and that varies: at
200 mm/min every 10 ms of it is 0.03 mm. So each point is two passes:

- **Coarse.** Jog down (`$J=`); on the touch, send jog-cancel (0x85), which
  stops without an alarm and keeps the position. Where the axis stops is
  below the contact by the network's delay. It is used only to know roughly
  where the bed is, and written as `z_fast_mm`.
- **Fine.** Back off (Backoff, 2.5 mm), put the pin down again, go down to
  Margin (0.6 mm) above the coarse stop, and step down Fine step at a time.
  After each step the Pico asks FluidNC for its state until two reports
  running say Idle at one position, then waits Settle (50 ms) for the sensor
  to answer, and only then looks at the pin. So the axis is standing still
  when the pin is looked at, and the contact lies within the last step. The
  network's delay decides how long a step takes, not where the reading is.
  That Z is `z_mm`.

  The fine step is rounded to whole motor steps of the machine's Z, which is
  read from it on connecting (`$/axes/z/steps_per_mm`). Parang's is 106
  steps/mm, 0.0094 mm a step: 0.02 mm was two motor steps or three by turns,
  and is 0.0189 now. Nothing finer than one motor step means anything.

  **`G4 P0` is not a wait.** The first version sent each step with a `G4 P0`
  and took its `ok` to mean the axis had stopped, which is what it means on
  GRBL. Parang's FluidNC (v4.1.1, a `bulletproof-webui-uploads` build)
  answered a 1 mm G0 and the `G4 P0` after it both at once, 0.29 s in, while
  its own status report still said Run, X 0.022 of the way to 1. An `ok` there
  means the line was taken, not that it has run. So the first tests' fine
  steps were queued rather than taken one at a time, and status reports are
  the wait now.

The fine pass always comes down, so play in Z drops out. The reading is low by
up to one step, the same at every point, which drops out too: the map is read
as differences from its own height at the calibration dot.

If the coarse stop overshoots the contact by more than Margin, the pin touches
on the way down to the first step; Margin is doubled, up to 0.1 mm short of
Backoff, and the fine pass tried again. With **Touches per point** above 1 the
point is touched again from just above the first contact, and readings further apart than Agree make it `nan`,
as `probescan.py` does. A point with no touch within Max depth is `nan` and
the probe goes back up to where it started.

**Margin is meant to be overshot now and then.** Every millimetre of it is
fine steps at every point, about 0.1-0.15 s each at 0.028 mm; an overshoot
past it costs one retry, about 2 s, at that point alone. Over four scans
(1867 points on Parang, Barbie and Pinkograph) the coarse stop overshot by
0.435 mm median, past 0.6 at 4.2 % of points, past 0.75 at 1.0 %, never past
0.973. That makes the fine pass about 0.7-1.0 s a point at Margin 0.6,
1.1-1.7 s at 0.75 and 2.0-3.0 s at 1.0: the retries are the cheap side, and
the default is 0.6. A log with a "touched less than ... above the coarse
stop" line every twenty-odd points is that working as meant.

**Three misses in a row end a scan.** One is a hole in the bed or a pin that
stuck once. Pinkograph's 2236-point scan (2026-11-10) touched at 882 points,
then went 10 mm down and back up without a touch at 185 points in a row, 18
minutes of them, because a miss was only counted. Now the third in a row
stops the scan, and the page says what to look at.

**A status report that does not come is asked for again**, up to three times
2 s each, before the scan gives up. A scan makes thousands of them; that same
scan ended on the first one to take more than 2 s, though the machine was
Idle and answering when asked afterwards.

**The pin is pushed in before it reports a touch.** So after a touch the pin
tip is less above the paper than the axis has risen, by however far that is —
and how far depends on the machine as well as the sensor, because whatever
the probe is held in gives a little too. On Parang, Backoff 1.5 mm was
enough. On Barbie it failed and 2.0 worked, so the push there is 1.1–1.5 mm;
and Clearance 1.5 mm, suggested to save time on the strength of the bed
rising no more than 0.31 mm from one point to the next, put the pin down onto
the paper at every other point of a scan. Every point after a good touch
failed; the failure lifted Clearance again, so the point after it was 3 mm
up and worked. The two settings have to cover the push as well: Clearance 3,
Backoff 2.5 (the push, and up to 0.66 mm of coarse overshoot).

And when they do not, the probe no longer gives the point up. If the pin
reports a touch the moment it is put down, it goes up 0.5 mm and tries again,
up to 3 mm, and the log says by how much it fell short of which setting
(`Scanner._deploy_clear`). A log full of those is the sign to raise it: each
retry costs a reset and a deploy, 1.4 s.

Rows are written in the order probed, serpentine, as `probescan.py` writes
them: `levelmap.where_probed` reads each row's direction off that order to
undo the play in X.

The WiFi's power saving is turned off (`PM_NONE`): it holds packets for the
radio's sleep interval, and the coarse stop would be late by all of it.

## On a machine

Parang, 2026-11-09, two repeatability tests of five touches each at
X 12 Y 53, 0.02 mm fine steps, coarse feed 200 mm/min:

- Every touch read the same, 0.217 mm, in both tests. The steps are 0.02 mm,
  so that says the sensor repeats to better than one step, not that it is
  perfect; a finer step is what would say by how much.
- The coarse stop came to rest 0.443 and 0.462 mm below the contact: about
  135 ms of travel at 3.3 mm/s, the network's delay and the axis braking
  together. The defaults were Margin 0.5 mm and Backoff 1.0 then, which left
  a twentieth of a millimetre to spare, so they became 0.75 and 1.5 (Margin
  is 0.6 again since, for speed; see above).

A test now also reports the WiFi's round trip (the median of ten status
requests), how long the coarse pass took and how long each fine pass took.

A third test, three touches, spread 0.019 mm: one 0.02 mm step, with the steps
still queued behind `G4 P0` (above). Its WiFi round trip was 22 ms, worst
36. Parang's Z brakes at 90 mm/s², which from 3.3 mm/s is 0.06 mm, so of the
0.47 mm the coarse stop overshot about 0.41 is delay: some 120 ms, against a
22 ms round trip. The rest may be the sensor's own time from being pushed to
answering, which is what Settle is for, and why it is a setting until it is
measured: touches at a few Settle times say whether the reading moves.

**error:9 at the first point of a scan.** The first scan stopped at once:
`G4 P0 -> error:9`, which is FluidNC refusing G-code in Jog or Alarm. The
machine reported neither before or after, and the same lines sent again by
hand, with and without a move, were taken. What put it there is not known. A
line refused with error:9 has not run, so it is now sent again, once, after
the machine has come to rest, and the log says so when it happens.

Still to measure: the sensor's spread now that steps are taken one at a time,
what Settle needs to be, and how long a scan's point takes.
