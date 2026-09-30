"""Thirteen small utility routines.

home.g parks the brush, paper.g moves it out of the way for replacing the
paper, and clean.g washes the brush the way a real job does before parking
too. The wash in clean.g follows whichever container shape
`brushograph.cup_shape` names, classic, modern or custom. All three, plus zero.g's
own last line, end the same way — parked at the water cup, Z = Dip Depth + 1 — via
the shared `_park_at_origin()`.

zero.g is the machine's own self-zero dance — a fixed sequence tuned on the
actual hardware, reproduced here verbatim, with the config read for nothing
but the model's far corner, that final park, and the ceiling every macro's
feedrates are held under (`_cap_feeds`).

calibrate.g is the odd one out on purpose: no wash, just the dot and a park
over it, at two literal heights that are neither `canvas_height` nor
`go_in_tray_lift`.

containercenter.g paints a tick on the canvas at the X of every container
the config names, so the positions typed into the form can be held against
the holder they claim to describe. It is the one macro here that paints:
black loads the brush, a tick at a time, and the brush is washed and parked
at the end the way a job leaves it. A machine with no black cup -- a classic
one, whose four dishes hold water and three colours -- gets a file that says
so and paints nothing. Its file name keeps the spelling it was asked for;
renaming it now would strand the copy already sitting in a machine's flash.

mix-c.g, mix-m.g, mix-y.g and mix-k.g each stir one colour cup: the brush goes
in, hops about the floor at the Fast rate to put the settled pigment back
through the water and methylcellulose above it, comes out, and is rinsed and
parked. The stairs at the back of a bay are left out of the hopping -- a brush
hurried up them is climbing out of the cup rather than stirring what is in it.

backlash.g is one of the two drawn with a pen: a sheet of paired strokes for
reading the play in each axis off, one pair arriving from each side, against a
gauge of known gaps. It is drawn with a pen fitted where the brush goes, so it
visits no cup and dips for nothing -- the machine needs no paint in it. Five
stations, each answering both axes where it stands: the four corners of
everything the machine can paint, which is wider than the canvas a job uses,
and the middle. It wants a pen in the holder and paper under all of it.

speedtest.g asks whether the motors keep up when the machine is driven as hard
as its config allows, and it is the one macro that fits nothing at all: no
brush, no pen, no paint, no paper, nothing below the canvas height. It sweeps
end to end, runs both diagonals, reverses at full speed, and hops Z with X and
Y crossing the bed through it; between every leg it returns to the water cup
and stands still for a few seconds. What moved between one stop and the next is
steps -- read off a tape mark the operator puts across carriage and rail, which
is a tool-free instrument better than a millimetre. Where backlash.g needs a
printed gauge because play does not accumulate, this needs none because steps
do.

trump.g signs the lower right corner of the canvas with a pen, in the spiky
upright hand of Donald Trump's autograph -- a stylised impression drawn from a
handful of polylines, not a traced facsimile.

None of the thirteen carries an M-code or a G28, so none needs the controller
dialect handling `gcode_pipeline.sanitize_for_controller` does for a real job:
G90/G0/G1/G10 are understood the same way by Marlin, GRBL and FluidNC.
"""
from __future__ import annotations

import math
import random
import re

from configspec import (CMYK_LABEL, CMYK_TO_TRAY, MODELS,  # noqa: E501
                        RECTANGULAR_SHAPES, accel_rate,
                        canvas_origin, feed_line, feed_rate, fit_cups_to_shape,
                        holder_of,
                        in_cup_order, model_of, tray_entries, with_defaults,
                        workable_x)
from gcode_pipeline import to_ascii
# After gcode_pipeline, which is what puts the repo root on sys.path: the
# choreographer lives a directory up, beside the command-line ancestors.
from copicograf import (DEFAULT_DIP_LANES, DIP_DWELL,  # noqa: E402
                        RIM_CATCH, RIM_DROP, dip_lanes)
from version import gcode_note

MACRO_NAMES = ["zero.g", "home.g", "paper.g", "clean.g", "calibrate.g",
               "containercenter.g",
               "mix-c.g", "mix-m.g", "mix-y.g", "mix-k.g",
               "backlash.g", "speedtest.g", "trump.g"]

# The two kinds of macro, and which kind a machine is sent unless told
# otherwise. The split is about the flash filesystem, which is small and is
# already holding the controller's own dashboard: twelve macros is 42 KB on
# Pinkograph and there are boards with no room for that, so the page asks which
# of them to send rather than sending the lot and failing at the ninth.
#
# It divides on how often a file is wanted. The operation macros are what an
# operator reaches for between jobs -- zero the machine, park it, get the
# gantry out of the way of a sheet of paper, wash the brush, drop a dot to see
# where the fresh sheet is sitting, stir a cup that has stood overnight -- and
# they are wanted on every machine, always. The testing and calibration ones
# are run when the machine is being set up or is under suspicion, and what they
# produce is figures that then live in the config rather than on the machine.
# There is no reason for them to be taking up flash between one setting-up and
# the next, and every reason for the default not to be the twelve that will not
# fit.
#
# calibrate.g is on the operation side of that line and not the calibration
# side its name suggests. It is a dot, put down with the brush already fitted,
# and it is put down every time a new sheet goes on the bed -- which is a thing
# done between jobs and not when the machine is set up.
# Each file carries its own line, and that line is the whole of what the page
# says about it. The paragraph these replaced tried to describe all twelve in
# one breath and read as a list of subordinate clauses; a sentence sitting
# beside the box you tick is read, and is also the only place it could go
# without being read twice.
MACRO_SECTIONS = [
    ("Operation", True, [
        ("zero.g", "Zeroes the controller through its fixed sequence, then parks."),
        ("home.g", "Parks over the water cup, just above dipping depth."),
        ("paper.g", "Takes the gantry out of the way for changing the paper."),
        ("clean.g", "Washes the brush in the water cup, then parks it."),
        ("calibrate.g", "Puts one dot near the canvas origin, to check where the paper sits."),
        ("mix-c.g", "Stirs settled pigment back through the cyan cup, then rinses and parks."),
        ("mix-m.g", "Stirs settled pigment back through the magenta cup, then rinses and parks."),
        ("mix-y.g", "Stirs settled pigment back through the yellow cup, then rinses and parks."),
        ("mix-k.g", "Stirs settled pigment back through the black cup, then rinses and parks."),
    ]),
    ("Testing & calibration", False, [
        ("containercenter.g",
         "A tick at the X of every container, to check the positions. Pen."),
        ("backlash.g", "The sheet the play in each axis is read off. Pen, full sheet."),
        ("speedtest.g",
         "Drives all three axes hard and stops where it started, so you can see "
         "if steps were lost. Nothing fitted, 5 min."),
        ("trump.g", "Signs the lower right of the canvas in Donald Trump's hand. Pen."),
    ]),
]

# Every macro in exactly one section, checked here rather than trusted. A
# thirteenth macro added to MACRO_NAMES and forgotten here would generate
# perfectly well and then never appear in the form for anyone to tick, which
# is the kind of fault that is noticed a release later.
_SECTIONED = [name for _, _, files in MACRO_SECTIONS for name, _blurb in files]
assert sorted(_SECTIONED) == sorted(MACRO_NAMES), (
    "every macro belongs in exactly one MACRO_SECTIONS entry; missing "
    f"{sorted(set(MACRO_NAMES) - set(_SECTIONED))}, unknown "
    f"{sorted(set(_SECTIONED) - set(MACRO_NAMES))}")

# How many hops around the floor of a cup a mixing macro makes. Sixty is about
# a minute on a machine that accelerates at 20 mm/s^2, which is long enough to
# see it working and short enough to run again -- and running it again is how
# it is meant to be made longer, rather than by a figure nobody can judge from
# the form.
MIX_HOPS = 60

# The gauges of backlash.g, in millimetres. A half-millimetre gap between
# two drawn lines is not something a ruler settles, whether they were drawn
# with a pen or painted a millimetre wide with a brush: each gauge prints
# known gaps, drawn so the play cannot affect them,
# and the test pairs are matched against it by eye. There is one per axis,
# each in its own axis's orientation -- a gap between two horizontal lines is
# not judged against a gap between two vertical ones, and which of the two
# axes carries the larger play is the machine's own business.
_GAUGE_GAPS = (0.5, 1.0, 1.5, 2.0, 2.5)

# How long a leg of a test station is, in millimetres: at most _TEST_LEG, and
# never less than _LEG_MIN. A pen is not working out of a dip, so the figure
# is about reading and not about paint. The cap is where more length stops
# telling you anything; the floor is where a pair of lines stops being a pair
# you can look along, and it is the one figure here allowed to push the
# gauges into showing fewer pairs. Between them the legs take what is left
# once both gauges have their room -- 30 mm on a Mini, and just over the
# floor on a Mikro, whose 65 mm of X has to hold two gauges and a station.
_TEST_LEG = 30.0
_LEG_MIN = 10.0

# How much clear paper is left between a station and a gauge, and between the
# gauges. Enough that nothing reads as belonging to its neighbour.
_CLEAR = 3.0

# The room a gauge is given before anything else gets any: its own gaps plus
# 2 mm of clear paper between each pair. The stations are sized around it, so
# a station is as long as the paper allows once both gauges are legible --
# rather than as long as it likes, with the gauges taking what is left.
_GAUGE_MIN = sum(_GAUGE_GAPS) + 2.0 * (len(_GAUGE_GAPS) - 1)

# The figure written under each X gauge pair, so the ruler is read off the
# sheet and not counted from the narrowest end. Digits are drawn as strokes
# of a seven-segment display, _LABEL_H tall at most and smaller where the
# paper will not hold that, _LABEL_GAP clear of the lines they name.
# Seven segments because a pen draws straight lines well and nothing else
# needs to be read here: the figures are 0.5 to 2.5, and a digit that only
# has to be told from nine others does not need a curve.
_LABEL_H = 3.0
_LABEL_GAP = 1.5
_DIGIT_W = 0.6   # of the height
_POINT_W = 0.15   # of the height; how wide the decimal comma leans
_GLYPH_SPACE = 0.35   # of the height, between one glyph and the next
# Every stroke runs rightward, upward or both, and never back on either axis:
# the figures are written on a sheet that measures the play, on a machine
# whose play is not known yet, so they are drawn the way the gauge is -- with
# the play taken up the same way on both axes at every mark (see `_text`).
# A seven-segment glyph splits into such strokes naturally; a "0" is two
# L-shapes, bottom-then-right and left-then-top, rather than one loop that
# would reverse on both axes on the way round.
_GLYPHS = {
    "0": [[(0, 0), (1, 0), (1, 1)], [(0, 0), (0, 1), (1, 1)]],
    # "1" and "7" as a display shows them, the right-hand segments and no
    # serif: one stroke for a "1" rather than two.
    "1": [[(1, 0), (1, 1)]],
    "2": [[(0, 0), (0, 0.5), (1, 0.5), (1, 1)], [(0, 0), (1, 0)],
          [(0, 1), (1, 1)]],
    "3": [[(0, 0), (1, 0), (1, 1)], [(0, 0.5), (1, 0.5)], [(0, 1), (1, 1)]],
    "4": [[(0, 0.5), (0, 1)], [(0, 0.5), (1, 0.5)], [(1, 0), (1, 1)]],
    "5": [[(0, 0), (1, 0), (1, 0.5)], [(0, 0.5), (1, 0.5)],
          [(0, 0.5), (0, 1), (1, 1)]],
    "6": [[(0, 0), (1, 0), (1, 0.5)], [(0, 0), (0, 1), (1, 1)],
          [(0, 0.5), (1, 0.5)]],
    "7": [[(1, 0), (1, 1)], [(0, 1), (1, 1)]],
    "8": [[(0, 0), (1, 0), (1, 1)], [(0, 0), (0, 1), (1, 1)],
          [(0, 0.5), (1, 0.5)]],
    "9": [[(0, 0), (1, 0), (1, 1)], [(0, 0.5), (0, 1), (1, 1)],
          [(0, 0.5), (1, 0.5)]],
    # The decimal point is written as a comma: one stroke, drawn upward from
    # its tail, where a square point took two and a touch leaves next to
    # nothing with a fine tip. Its x is in units of its own width.
    ".": [[(0, -0.2), (1, 0.1)]],
}
assert all(x1 >= x0 and y1 >= y0
           for strokes in _GLYPHS.values() for stroke in strokes
           for (x0, y0), (x1, y1) in zip(stroke, stroke[1:])), \
    "a glyph stroke runs back on an axis, which lets the play into the figure"

# How far a stroke backs off before it comes in, so the axis is certainly
# travelling the way the test means it to when it arrives. It only has to
# exceed the play itself, and 3 mm is what a very poor machine has. 10 mm is
# that with plenty to spare, and 2 mm less at each edge of the bed than the
# 12 it was; 4 mm was tried and was too tight a margin to trust. It is
# clamped to the bed for a machine with no room to give it, and the test
# still holds as long as something is left.
_RUN_UP = 10.0

# speedtest.g's approach, which is not a take-up of the play but a timed
# distance: the acceleration is read off five of them (_SPEED_APPROACHES), and
# a shorter one would be over too quickly to time by hand.
_SPEED_RUN_UP = 12.0

# How long a containercenter.g tick is, in millimetres, and the shortest one
# worth painting. 20 is long enough to sight along and to lay a rule against,
# and short enough to come out of one pickup with room to spare -- the kept
# configs carry 150 to 180 mm of painting between dips, and the shortest
# canvas of the two machines is 70 mm deep, so the tick fits on the paper as
# well as in the brush.
_TICK = 20.0
_TICK_MIN = 2.0

# trump.g's signature, as pen strokes in units of its own height: the first
# name, the surname with its stem, and the crossbar of the T. Not a trace of
# any real autograph -- a stylised impression of the one everybody knows, a
# tall first capital and then a picket fence of narrow spikes, which is what
# makes it read at a glance. Each stroke is one pen-down.
_SIGNATURE = [
    [(0.00, 0.10), (0.06, 1.00), (0.22, 0.70), (0.12, 0.08), (0.00, 0.20),
     (0.30, 0.55), (0.36, 0.05), (0.42, 0.75), (0.48, 0.05), (0.54, 0.62),
     (0.60, 0.05), (0.66, 0.85), (0.72, 0.05), (0.78, 0.55), (0.84, 0.10),
     (0.92, 0.35)],
    [(1.20, 0.05), (1.30, 1.10), (1.34, 0.05), (1.42, 0.60), (1.48, 0.05),
     (1.56, 0.70), (1.62, 0.05), (1.70, 0.58), (1.76, 0.05), (1.84, 0.66),
     (1.90, 0.05), (1.98, 0.50), (2.10, 0.15), (2.30, 0.25)],
    [(1.05, 0.95), (1.60, 1.08)],
]
_SIGNATURE_W = max(x for stroke in _SIGNATURE for x, _ in stroke)
# How wide the signature is drawn, at most, and how far in from the canvas
# edges. Forty millimetres is a signature, not a slogan, and a fifth of the
# canvas keeps it a corner mark on a Mikro's 65 mm width.
_SIGN_MAX_W = 40.0
_SIGN_MARGIN = 5.0

# speedtest.g's legs, in the order it runs them. Each figure is the number of
# times that leg is repeated, and none of them is an endurance test: a motor
# that cannot hold the rate it is being driven at gives up in the first dozen
# reversals, not the hundredth. They are sized to be long enough to see a loss
# and short enough that the whole file is about seven minutes of machine time
# on Pinkograph -- ten on a config that accelerates at 20 mm/s^2 rather than
# 100 -- which is what gets it run again after a belt is tightened, rather than
# put off.
#
# The two traverse legs are the cheapest to lengthen and the least worth
# lengthening, so they are the shortest: ten full-length accelerations to top
# speed an axis either survive or they do not, and going round twenty more
# times only spends the four minutes that were what stopped anyone running it.
# The reversals were forty while each one was a 2 mm twitch and cost nothing.
# Now that each is a full run up to the feedrate and back, five of them in each
# of three directions is the right number and not a compromise: a block of five
# is a block you can count and put a watch on, and the reversal is the one leg
# whose duration means something -- each is a known distance covered by
# accelerating to the feedrate and stopping again, so timing the block is
# measuring the acceleration. Forty of them measured nothing forty times and
# took four of the file's seven minutes doing it.
_SPEED_SWEEPS = 3
_SPEED_JABS = 3
_SPEED_HOPS = 50

# How many times the approach to the reference point is made at the opening
# stop. Everywhere else it is made once, which is all it takes to fix the side
# the carriage arrives from; at the opening it is made five times because that
# short back-off and arrival is the best acceleration measurement in the file,
# and one block of it at the top is a measurement rather than a tic the machine
# has developed. Five of them in front of every leg was the same figure read
# five times over, and mostly it was the file taking longer.
#
# Every other move here is long enough to reach the Fast feedrate, so its
# duration is a run-up plus a cruise plus a stop and the cruise is the larger
# part of it. The approach is _SPEED_RUN_UP on each axis -- 17 mm of diagonal -- which
# is short enough to be all getting up to speed and slowing down again, or very
# nearly: a Mikro at 20 mm/s^2 peaks at 18.4 mm/s against a Fast rate of 25 and
# never cruises at all, so its 1.84 s is 2*sqrt(d/a) and nothing else. Time five
# of those and the acceleration falls out with no feedrate term in it.
#
# Five costs nothing -- 85 mm of travel a stop, against the thousands each leg
# covers -- and the last arrival is still from the same side as every other, so
# the play cancels exactly as it did when there was one.
_SPEED_APPROACHES = 5

# How long one reversal of speedtest.g's third leg is, and it is worked out
# rather than chosen. The first version of this used a flat 2 mm, on the
# argument that a move too short to reach the feedrate is all acceleration and
# so all torque -- which is true of the profile and wrong about the motor. A
# stepper's torque falls with speed, and steps are lost where the demand meets
# that falling curve: at speed. Two millimetres at Pinkograph's 100 mm/s^2
# peaks at 14 mm/s against a Fast rate of 35, so the motor never leaves the
# flat part of its curve and the leg could not have failed if the machine were
# in pieces.
#
# The shortest move that does reach the feedrate is v^2/a -- v^2/2a to get
# there and as much again to stop -- and _SPEED_JAB_MARGIN over that buys a
# moment of holding it before the reversal. Pinkograph: 35 mm/s and
# 100 mm/s^2 make 12.3 mm, and 18.4 with the margin. A Mikro at 25 mm/s and
# 20 mm/s^2 wants 31.3, and 46.9 with it, which is most of its X -- so it is
# clamped to the ground there is, and the header says the figure it used.
_SPEED_JAB_MARGIN = 1.5

# What a reversal falls back to where the config names no acceleration for it
# to be worked out from. Long enough to be a run rather than a twitch on every
# machine here, and short enough to fit across a Mikro.
_SPEED_JAB_MIN = 20.0

# How long speedtest.g stands still at its reference point, in seconds, so
# there is time to look at it. G4 P is seconds to GRBL and FluidNC, which is
# the reading copicograf's own dip dwell is written for, and milliseconds to
# Marlin -- a whole number here so a Marlin machine's three milliseconds is at
# least harmless rather than a long stop nobody asked for.
_SPEED_DWELL = 3

# What each dash of a speedtest.g comb after the first one says, in the order
# the legs run. There is one dash a leg plus the reference, and the combs are
# sized from the count, so the two are one list rather than two figures that
# have to be kept agreeing.
_SPEED_LEG_NOTES = (
    "after end to end on each axis",
    "after both diagonals",
    "after the reversals",
    "after Z and all three together",
)

# The classic dip sweep in copicograf picks a random quadrant each time, which
# suits a real job's hundreds of pickups — spreading the wear across the cup —
# but not a canned macro someone downloads and reads. Cycling through the four
# quadrants by repetition index keeps the same config always producing the
# same macro, while still covering the cup the way the random version does.
_QUADRANTS = [(1, 1), (-1, 1), (-1, -1), (1, -1)]

# How many times wash_the_brush() dips in copicograf's own choreography — see
# copicograf.py's wash_the_brush(), which is not itself reusable here because
# its motion lives in closures nested inside Copicograf.prepare_path().
_WASH_REPS = 3

# How clean.g washes: four dips in the water, each leaving the cup a different
# way. Up the stairs to begin with, which is the wipe a job gives the brush
# every pickup; then out over each side wall in turn, which is the wipe it
# never gets, since the swipe draws the same one line of the bristles every
# time; then up the stairs again, so the brush comes out of the water shaped
# the way a job expects to find it.
_WASH_ROUTINE = ["stairs", "left", "right", "stairs"]

# How far below Dip Depth a wash pushes the brush, in millimetres. Dip Depth
# puts the bristles on the floor of the cup and no harder, because a pickup
# wants the paint that is on the floor and not the floor itself. A wash wants
# the floor: water gets into a brush that is bent against something, and a
# couple of millimetres of bend is the difference between rinsing the tip and
# rinsing the brush.
WASH_PRESS = 2.0


def _num(d: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(d.get(key, default))
    except (TypeError, ValueError):
        return default


def _fmt(v: float) -> str:
    """3 decimal places, trailing zeros trimmed — "47", not "47.000"."""
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _gap_list(gaps: list[float]) -> str:
    """"0.5, 1, 1.5, 2 and 2.5" -- a gauge's gaps, for its own header."""
    shown = [_fmt(g) for g in gaps]
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


def _feed(bg: dict, group: str, fallback: str = "G0 F1000") -> str:
    """A speed group's rate as the line that sets it.

    The setting holds millimetres a minute, so `feed_line` writes the G-code
    round it; a config still carrying a whole line is passed through as it is.
    """
    moves = bg.get("moves", {})
    g = moves.get(group, {}) if isinstance(moves, dict) else {}
    val = g.get("feedrate_1", "") if isinstance(g, dict) else ""
    return feed_line(val, fallback) if str(val).strip() else fallback


# An F word: the feedrate a move is made at.
_FEED_WORD = re.compile(r"\bF(\d+(?:\.\d+)?)\b")


def _fast_feed(bg: dict) -> float | None:
    """The figure in the Fast speed group's feedrate, if the config names one."""
    found = _FEED_WORD.search(_feed(bg, "fast", ""))
    return float(found.group(1)) if found else None


def _with_note(text: str, note: str) -> str:
    """`note` under whatever a macro says about itself, and above its first move."""
    lines = text.splitlines()
    at = 0
    while at < len(lines) and (not lines[at].strip() or lines[at].lstrip().startswith(";")):
        at += 1
    return "\n".join(lines[:at] + [note] + lines[at:]) + "\n"


def _cap_feeds(text: str, ceiling: float) -> tuple[str, bool]:
    """Every feedrate in a macro held at or below the machine's fast rate.

    Fast is the quickest the config says this machine is to be driven, and a
    macro is the machine being driven: there is no reason for one of these to
    cross the bed faster than a job does, and one good reason not to. zero.g
    swept to the far corner at F2100 on a machine whose fast group says F2000,
    because that figure came off the hardware zero.g was first tuned on and has
    been carried verbatim ever since. A sweep that ends in the endstops on
    purpose is the last move that wants to be going quicker than the machine
    was set up for.

    Held, not scaled: a macro that already runs slower than fast keeps its own
    figure. The rim wipe is meant to be slow and the jog steps in zero.g are
    meant to be deliberate, and both would be spoiled by being brought up to a
    ceiling.
    """
    lowered = False

    def hold(word):
        nonlocal lowered
        if float(word.group(1)) <= ceiling:
            return word.group(0)
        lowered = True
        return "F" + _fmt(ceiling)

    return _FEED_WORD.sub(hold, text), lowered


def _preamble(bg: dict) -> list[str]:
    """Absolute, millimetres, and the fastest this machine is configured to move.

    The Fast group, not Normal, for every one of these. A macro is not a
    painting: it parks the brush, moves the gantry out of the way for a sheet
    of paper, washes, zeroes, and puts one dot or a row of ticks down. All of
    that is waiting, and there is no reason to wait at the rate a stroke is
    painted at when the config says the machine is driven half as fast again.

    What it changes depends on the controller. Marlin takes G0 as G1 and feeds
    both from F, so everything here moves at this rate. GRBL and FluidNC run G0
    at their own configured maximum and read F for G1 alone, so there it is the
    fed moves that change: the swipe out of a cup, a drawn tick, a gauge line.
    home.g on a FluidNC machine has no G1 in it at all, and its feed line is a
    line that does nothing -- which is the shape of the whole fault: the figure
    was being written without much thought about what reads it.
    """
    return ["G90 ; absolute positioning", "G21 ; millimetres", _feed(bg, "fast")]


def _park(wx: float, wy: float, park_z: float) -> list[str]:
    """Park at the water cup center, Z = Dip Depth + 1.

    How home.g, clean.g and zero.g all finish once whatever they were doing is
    done and the brush is already lifted clear — a shared ending rather than
    three copies of the same two lines.
    """
    return [
        f"G00 X{_fmt(wx)} Y{_fmt(wy)}",
        f"G00 Z{_fmt(park_z)} ; Dip Depth + 1",
    ]


def _stir(hops: int, seed: int, xs: tuple[float, float],
          ys: tuple[float, float], from_x: float, from_y: float) -> list[str]:
    """`hops` jumps around the floor of a cup, and back where it started.

    Paint settles, and the water and methylcellulose that were stirred into it
    sit on top; what puts them back together is something dragged through the
    lot of it, and on this machine the only thing there is to drag is the
    brush. So it goes down to Dip Depth and hops about the floor at the Fast
    rate -- quickly, because a slow sweep pushes the paint aside where a fast
    one rolls it over, and randomly, because a pattern stirs the ground it
    covers and leaves the rest.

    Random, but not different every time the macro is generated: the seed is
    fixed, the way the roughening noise in a woodcut is, so the same config
    writes the same file. Each hop is thrown until it lands at least a third of
    the way across the cup from the last one, which is what keeps them from
    being a shiver in one corner -- an even scatter of points is not an even
    scatter of *moves*, and it is the moves that do the mixing.

    It ends where it started, so whatever the caller does next -- the swipe up
    the stairs, a wall -- it does from the place it would have anyway.
    """
    lo_x, hi_x = xs
    lo_y, hi_y = ys
    span = math.hypot(hi_x - lo_x, hi_y - lo_y)
    if hops <= 0 or span < 1.0:
        return []
    rng = random.Random(seed)
    lines, at_x, at_y = [], from_x, from_y
    for _ in range(max(0, hops)):
        for _try in range(12):
            x = rng.uniform(lo_x, hi_x)
            y = rng.uniform(lo_y, hi_y)
            if math.hypot(x - at_x, y - at_y) >= span / 3:
                break
        lines.append(f"G01 X{_fmt(x)} Y{_fmt(y)}")
        at_x, at_y = x, y
    lines.append(f"G01 X{_fmt(from_x)} Y{_fmt(from_y)} ; back to where the dip left off")
    return lines


def _stair_climb(holder: dict, tray_y: float, dip: float,
                 press: float) -> list[tuple[float, float, str]]:
    """A wash's way up the stairs: along each step, `press` into it, to the top.

    A pickup leaves a bay in one straight line from the floor to
    cup_swipe_exit_z, and that is right for a pickup, which wants the brush
    drawn lightly out of the paint. A wash does not. On the Mini that line is
    1.1 mm clear of the first step, only just touches the edge of the second, and
    finishes on the third at no pressure at all. It lifts off the floor almost
    as soon as it starts moving, so for most of its length the brush is not
    touching anything.

    So this follows the steps instead. Along the floor to the foot of the
    stairs, then through the front edge of every step `press` below its top,
    and out along the top step, which is level with the rim. Each edge is
    dragged across the bristles with them bent against it, and between edges
    the line is still below the tread it crosses (a step rises 1.76 mm on the
    Mini, 1.36 on the Mikro, both less than the 2 mm press), so the brush is on
    the stairs from the bottom to the top.

    The heights are counted from the config's Dip Depth, not the holder's
    drawing: the design puts Dip Depth 0.2 mm under the floor, and a machine
    whose Z was set up differently has moved Dip Depth to suit and moved the
    floor with it. The Y figures are the same back-40%, five-step arithmetic
    `configspec._crucible_settings` sets cup_swipe_exit_z by.

    Empty for a holder nobody drew stairs for (custom containers); the caller
    then leaves the way a pickup does.
    """
    crucible = holder.get("crucible")
    if not crucible:
        return []
    rim, floor, length = crucible
    floor_z = dip + (floor - round(floor - 0.2, 1))
    rise = (rim - floor) / 5
    tread = length * 0.4 / 5
    foot = tray_y + length / 2 - length * 0.4
    points = [(foot, dip - press, "along the floor to the foot of the stairs, pressed")]
    for k in range(1, 6):
        points.append((foot + (k - 1) * tread, floor_z + k * rise - press,
                       f"over the edge of step {k}, {_fmt(press)} mm into it"))
    points.append((foot + 4.5 * tread, floor_z + 5 * rise - press,
                   "along the top step, level with the rim"))
    return points


def _container_motion(conf: dict, tray_x: float, tray_y: float, reps: int = 1,
                      exits: list[str] | None = None,
                      width: float | None = None, stir: int = 0,
                      seed: int = 0, bend: bool = True,
                      press: float = 0.0) -> list[str]:
    """Dips at (tray_x, tray_y), classic or modern, each leaving the way `exits` says.

    A dip is the same wherever it is made: in over the rim, down onto the floor,
    a moment standing there. What can differ is how the brush comes out of a
    rectangular bay, and `exits` says, one word a dip --

    - `stairs`, up the shallow end, which is how a job always leaves a cup and
      what wipes the brush along its length;
    - `left` or `right`, out over that side wall, which is an edge drawn across
      the sides of the bristles instead. The swipe only ever wipes one line of
      the brush, and it is the same line every time; the side walls are the
      only edges of a rectangular bay it never touches.

    Absent, every dip leaves up the stairs, which is what a wash was before
    clean.g asked for the walls.

    `stir` is how many hops the brush makes around the floor of the cup while
    it is down there, which is what the mixing macros are: paint settles, and
    water and methylcellulose sit on top of it, and the only thing on this
    machine that can put them back together is the brush. Nought is a dip.

    `bend` is the way in. A pickup comes down outside the cup and drives in
    across the rim, which bends the bristles back against the way the swipe
    sets them (copicograf.RIM_CATCH). A wash does not: those are two moves out
    past the wall and back for a brush that is about to be rinsed and drawn
    over three edges anyway, so it goes over the mouth and straight down.

    `press` is how far below Dip Depth the brush is pushed, in millimetres.
    Nought for a pickup, which wants the paint that is on the floor and not the
    floor. A wash wants the floor: water gets into a brush that is bent against
    something. For the same reason a pressed dip leaves up the stairs by
    following them (`_stair_climb`) rather than in a pickup's straight line.

    No rim wipe on the way out either way: the callers are a wash and a tick's
    pickup, and — like copicograf's own wash_the_brush() — a brush being rinsed
    has nothing to shed.
    """
    bg = conf.get("brushograph", {})
    shape = str(bg.get("cup_shape", "classic")).strip().lower()
    dip = _num(bg, "dip_depth", -4)
    lift = _num(bg, "go_in_tray_lift", 8)
    lines: list[str] = []

    if shape in RECTANGULAR_SHAPES:
        holder = holder_of(conf)
        depth = holder["swipe_length"]
        exit_z = _num(bg, "cup_swipe_exit_z", 1.0)
        margin = depth * 0.15
        near, far = tray_y - depth / 2 + margin, tray_y + depth / 2 - margin
        # The near edge gets the clamp the stir across X already has. A bay
        # deeper than the strip it stands in reaches south of the origin — on
        # Pinkograph the water crucible puts this edge at Y -4.5 — and there
        # is no ground down there to reach: zero.g backs three millimetres off
        # the Y endstop and calls that spot Y0, so Y -3 is the stop itself.
        # Every wash drove into it, and what a move loses against a stop it
        # loses for the whole of the rest of the file.
        near = max(near, 0.0)
        # The lanes copicograf spreads its dips over, worked out the same way
        # and kept on the bed the same way — the water crucible is wider than
        # the colours', and wide enough on some holders to hang over the
        # endstop. The macro's own dips walk along them the way a job's do, so
        # a wash works the width of the water rather than the same line of it
        # three times.
        #
        # The caller says which cup this is, because the two widths are not the
        # same figure and this was reading the water's for every cup. On
        # Pinkograph that spread the black cup's dips over +/-13.7 mm of a bay
        # 29.2 mm across: not into the wall -- the inside half-width is 14.6 --
        # but 0.9 mm off it, where the 15% margin means to leave 4.4.
        bay = holder["water_bay_width"] if width is None else width
        lanes = dip_lanes(tray_x, bay,
                          _num(bg, "cup_dip_lanes", DEFAULT_DIP_LANES),
                          (0.0, workable_x(conf)))
        # In over the far wall and down, the way a job does it: the swipe runs
        # one way every time, so the brush is brought in bent the other way
        # against the rim rather than dropped in over the mouth. See
        # copicograf.RIM_CATCH.
        approach = tray_y + depth / 2 + margin
        # How low the brush is as it crosses the rim, and never lower than a
        # millimetre over the stairs at the far end: the bend has to be over
        # before the brush crosses the bay, or it arrives still folded. See
        # copicograf.RIM_CATCH.
        rim_z = max(exit_z + 1.0, lift - 2.0 - RIM_CATCH)
        rim_z = min(lift, max(dip + 1.0, rim_z))
        # How far out a wall wipe reaches, and whether the machine can get
        # there. The water crucible is the wide one and it stands at the near
        # end of the row, so its left wall can be off the bed -- Pinkograph's
        # is 39.2 mm across at X 15, which puts that wall at X -6.6. A wall
        # that cannot be reached is not wiped on; that dip leaves up the
        # stairs instead, so the brush still comes out of the cup properly.
        walls = {}
        for side, at in (("left", tray_x - bay / 2 - RIM_CATCH),
                         ("right", tray_x + bay / 2 + RIM_CATCH)):
            if 0.0 <= at <= workable_x(conf):
                walls[side] = at

        plan = list(exits or []) or ["stairs"] * max(1, reps)
        floor = dip - press
        for i, leaves in enumerate(plan):
            dip_x = lanes[i % len(lanes)]
            if bend:
                lines += [
                    f"G00 X{_fmt(dip_x)} Y{_fmt(approach)}",
                    f"G00 Z{_fmt(rim_z + RIM_DROP)} ; over the rim, still outside the cup",
                    f"G01 X{_fmt(dip_x)} Y{_fmt(far)} Z{_fmt(rim_z)}"
                    " ; in across the rim, going down -- bends the brush the other way",
                    f"G01 X{_fmt(dip_x)} Y{_fmt(near)} Z{_fmt(rim_z)}"
                    " ; the bay in clear air, so the bristles come back",
                ]
            else:
                lines.append(f"G00 X{_fmt(dip_x)} Y{_fmt(near)}"
                             " ; over the mouth -- a wash needs no run at the rim")
            lines += [
                f"G01 Z{_fmt(floor)} ; straight down, at Dip Depth"
                + (f" less {_fmt(press)}, pressed into the floor" if press else ""),
                f"G4 P{DIP_DWELL:g} ; stand on the floor",
            ]
            if stir:
                # The flat floor of the bay, which is all of it in front of the
                # stairs: they take the back 40%, and a brush hurried up and
                # down them is a brush climbing out of the cup rather than
                # stirring what is in it.
                lines += _stir(
                    stir, seed + i,
                    (max(0.0, tray_x - bay / 2 + bay * 0.15),
                     min(workable_x(conf), tray_x + bay / 2 - bay * 0.15)),
                    (near, tray_y + depth * 0.1), dip_x, near)
            if leaves in walls:
                # Out and up over the side wall from where it stands, the way
                # the swipe goes out and up over the stairs: the bristles are
                # drawn across the edge rather than lifted off it.
                lines.append(f"G01 X{_fmt(walls[leaves])} Y{_fmt(near)} Z{_fmt(rim_z)}"
                             f" ; out over the {leaves} wall -- wipes the side of the brush")
            else:
                if leaves in ("left", "right"):
                    lines.append(f"; no room to wipe on the {leaves} wall --"
                                 " it is off the bed, so this one leaves up the stairs")
                climb = _stair_climb(holder, tray_y, dip, press) if press else []
                if climb:
                    lines += [f"G01 X{_fmt(dip_x)} Y{_fmt(y)} Z{_fmt(z)} ; {why}"
                              for y, z, why in climb]
                else:
                    lines.append(f"G01 X{_fmt(dip_x)} Y{_fmt(far)} Z{_fmt(exit_z)}"
                                 " ; up the stairs -- wipes itself")
            lines.append(f"G00 Z{_fmt(lift)}")
        return lines

    # Classic: down the middle, a diagonal sweep, back up. The real dance
    # picks a random quadrant each pickup; this cycles through the four so the
    # same config always produces the same macro.
    radius = _num(bg, "tray_enter_radius", 10)
    d = radius * 0.70711
    # The chord is swept from both corners, so whichever side runs out of
    # ground first sets it for all four quadrants — the same bound the
    # rectangular stir gets, and for the same reason. A dish sits in the strip
    # along the front, and a sweep wider than the strip is deep reaches south
    # of the origin, where there is nothing but the Y endstop: on the Mini's
    # dish, 15 mm of enter radius around a tray at Y 6 asks for Y -4.6.
    d = min(d, tray_x, tray_y, workable_x(conf) - tray_x)
    for i in range(max(1, reps)):
        qx, qy = _QUADRANTS[i % 4]
        lines += [
            f"G00 X{_fmt(tray_x)} Y{_fmt(tray_y)}",
            f"G00 Z{_fmt(dip)}",
        ]
        if stir and d >= 0.5:
            # A dish is round and has no stairs, so the whole of the chord's
            # square is fair ground -- corners and all, since the dish is wider
            # than the chord the sweep keeps to.
            lines += _stir(stir, seed + i, (tray_x - d, tray_x + d),
                           (tray_y - d, tray_y + d), tray_x, tray_y)
        elif d >= 0.5:
            lines += [
                f"G00 X{_fmt(tray_x + qx * d)} Y{_fmt(tray_y + qy * d)}",
                f"G00 X{_fmt(tray_x - qx * d)} Y{_fmt(tray_y - qy * d)}",
                f"G00 X{_fmt(tray_x)} Y{_fmt(tray_y)}",
            ]
        lines.append(f"G00 Z{_fmt(lift)}")
    return lines


def _run_up(pos: float, approach: int, lo: float, hi: float) -> float:
    """How far a stroke at `pos` may back off before it comes in.

    _RUN_UP, or whatever of it there is room for: the point is only that the
    axis is certainly travelling the way the stroke means it to when it
    arrives, so a short one still holds, and a move that backed off past the
    end of an axis would finish against a stop instead.
    """
    room = (pos - lo) if approach > 0 else (hi - pos)
    return max(0.0, min(_RUN_UP, room))


def _comb_stroke(bg: dict, vertical: bool, pos: float, start: float, end: float,
                 approach: int, run_up: float, canvas_z: float,
                 lift: float) -> list[str]:
    """One stroke of the comb, arrived at from the side `approach` names.

    Got to at the machine's top speed and drawn at the rate a job paints at,
    which is the same division copicograf makes: travel on the Fast group,
    strokes on Normal. It matters in both directions here. A painted tick laid
    at travel speed is a thinner mark than the same tick in a job, and the
    lines on the backlash sheet are a measuring instrument whose figures are
    applied to painting moves -- measuring them at one speed to compensate
    moves made at another is the kind of tidiness that is worth the two extra
    lines in the file.

    The last move before the brush goes down is along the axis under test, so
    that axis is definitely travelling the way this stroke wants it to. The
    move before that is along the other one, in the same direction the stroke
    itself runs, which keeps the play out of the end of the line: a stroke that
    began with a reversal would start a millimetre and a half short of where it
    says, and the ends of these lines are what is being read.
    """
    pre = pos - approach * run_up
    # The settle backs off along the axis the stroke runs, and by the same
    # distance as the run-up rather than a token millimetre or two: this
    # macro exists because the play is not known, so a settle that assumed it
    # was small would displace the start of every stroke on a machine loose
    # enough to be worth measuring. Clamped, because on a canvas starting at
    # the origin it backs straight into the endstop -- the first pair of a
    # Mikro's Y test asked for X -0.6, and what a move loses against a stop it
    # loses for the rest of the file.
    settle = max(0.0, start - run_up)
    if vertical:
        travel = [
            f"G00 X{_fmt(pre)} Y{_fmt(settle)}",
            f"G00 X{_fmt(pre)} Y{_fmt(start)} ; settle Y before the stroke",
            f"G00 X{_fmt(pos)} Y{_fmt(start)} ; arrive from the "
            + ("left" if approach > 0 else "right"),
        ]
        draw = f"G01 X{_fmt(pos)} Y{_fmt(end)}"
    else:
        travel = [
            f"G00 X{_fmt(settle)} Y{_fmt(pre)}",
            f"G00 X{_fmt(start)} Y{_fmt(pre)} ; settle X before the stroke",
            f"G00 X{_fmt(start)} Y{_fmt(pos)} ; arrive from "
            + ("below" if approach > 0 else "above"),
        ]
        draw = f"G01 X{_fmt(end)} Y{_fmt(pos)}"
    return [*travel, _feed(bg, "normal") + " ; the rate a job paints at",
            f"G01 Z{_fmt(canvas_z)}", draw,
            _feed(bg, "fast") + " ; back to travel speed", f"G00 Z{_fmt(lift)}"]


def _glyph_w(ch: str) -> float:
    """A glyph's width in units of the text height."""
    return _POINT_W if ch == "." else _DIGIT_W


def _text_w(text: str) -> float:
    """How wide `text` is drawn, in units of its height."""
    return sum(_glyph_w(ch) for ch in text) + _GLYPH_SPACE * (len(text) - 1)


def _text(bg: dict, text: str, x: float, y: float, h: float,
          canvas_z: float, lift: float, reach_x: float,
          reach_y: float) -> list[str]:
    """`text` written with the pen, `h` tall, its bottom left corner at (x, y).

    Written free of the play. Every stroke of a glyph runs rightward and
    upward only (`_GLYPHS`), and the pen comes to the start of each one from
    below and to the left, backed off by the run-up on both axes. So when the
    pen goes down, and all the way along the stroke, both axes have last
    moved the positive way. The play then shifts every mark of every figure
    by the same amount, which moves a figure and leaves its shape alone. A
    loop would reverse on both axes on the way round and open its corners by
    the play.

    Drawn at the rate a job paints at, like the gauge strokes.
    """
    lines = []
    for ch in text:
        w = _glyph_w(ch) * h
        for stroke in _GLYPHS[ch]:
            pts = [(x + px * w, y + py * h) for px, py in stroke]
            sx, sy = pts[0]
            back_x = sx - _run_up(sx, 1, 0.0, reach_x)
            back_y = sy - _run_up(sy, 1, 0.0, reach_y)
            lines += [f"G00 X{_fmt(back_x)} Y{_fmt(back_y)}",
                      f"G00 X{_fmt(sx)} Y{_fmt(sy)} ; arrive from below left",
                      _feed(bg, "normal"), f"G01 Z{_fmt(canvas_z)}",
                      *(f"G01 X{_fmt(px)} Y{_fmt(py)}" for px, py in pts[1:]),
                      _feed(bg, "fast"), f"G00 Z{_fmt(lift)}"]
        x += w + _GLYPH_SPACE * h
    return lines


def _mix_macro(conf: dict, channel: str, tray: str) -> str:
    """Stir one colour cup, then wash the brush and park it.

    The brush goes in the way it goes in for a pickup, hops about the floor of
    the cup at the Fast rate (`_stir`), comes out up the stairs and is then
    rinsed in the water and parked -- because what is on it at the end of this
    is a brushful of paint, and the routine that leaves it clean is the one a
    job would run next anyway.

    It is hard on a brush, which is the honest thing to say about it: dragging
    bristles sideways through settled pigment is exactly the motion the pickup
    stopped making, for exactly that reason. The difference is that this is a
    thing done on purpose to a cup, once, rather than a hundred times a job.
    """
    bg = conf.get("brushograph", {})
    trays = conf.get("trays", {})
    holder = holder_of(conf)
    cup = trays.get(tray) if isinstance(trays, dict) else None
    label = CMYK_LABEL.get(channel, tray)
    go_lift = _num(bg, "go_in_tray_lift", 8)
    park_z = _num(bg, "dip_depth", -4) + 1
    water = trays.get("water", {}) if isinstance(trays, dict) else {}
    wx, wy = _num(water, "x", 0), _num(water, "y", 0)

    head = [
        f"; mix-{channel.lower()}.g -- stir the {label} cup, then wash and park",
        ";",
        "; Watercolour in a crucible separates: pigment to the floor, water and",
        "; the methylcellulose that thickens it above. This drags the brush",
        f"; about the floor of the cup {MIX_HOPS} times at the Fast rate, which is",
        "; as quick and as untidy as this machine can be asked to be, and the",
        "; two together are what mix rather than merely swirl. About 750 mm of",
        "; travel: a minute and a half on a machine that accelerates at",
        "; 20 mm/s^2, and less on a quicker one.",
        ";",
        "; The stairs at the back are left out of it: a brush hurried up them",
        "; is a brush climbing out of the cup, not stirring what is in it.",
        ";",
        "; It ends by rinsing the brush in the water and parking it, because",
        "; what is on it by then is a cupful of paint. Run it again for a",
        "; longer stir -- it is the same file twice.",
    ]

    if not isinstance(cup, dict) or "x" not in cup:
        return "\n".join(head + [
            ";",
            f"; This machine has no {label} container, so there is nothing here",
            "; to stir and this file does nothing. The petri dish holder has",
            "; four places -- water and three colours -- and black is the one",
            "; it does not have.",
            *_preamble(bg),
        ]) + "\n"

    cx, cy = _num(cup, "x"), _num(cup, "y")
    if not 0 <= cx <= workable_x(conf):
        return "\n".join(head + [
            ";",
            f"; The {label} cup is at X{_fmt(cx)}, which is past the ground this",
            "; machine covers, so this file does nothing rather than stirring",
            "; somewhere that is not the cup.",
            *_preamble(bg),
        ]) + "\n"

    return "\n".join(head + [
        ";",
        f"; {label} at X{_fmt(cx)} Y{_fmt(cy)}.",
        *_preamble(bg),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- clear before crossing the bed",
        *_container_motion(conf, cx, cy, reps=1, width=holder["bay_width"],
                           stir=MIX_HOPS, seed=sum(map(ord, tray))),
        "; wash and park, the way a job leaves the brush",
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- the water cup",
        *_container_motion(conf, wx, wy, reps=_WASH_REPS,
                           width=holder["water_bay_width"],
                           bend=False, press=WASH_PRESS),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift",
        *_park(wx, wy, park_z),
    ]) + "\n"


def generate_macros(conf: dict) -> dict[str, str]:
    """The macros, as {filename: text}, in MACRO_NAMES order."""
    # fit_cups_to_shape as well as with_defaults, the way new_config and
    # apply_form both normalise a config: with_defaults offers a black cup to
    # every config, because the form is built once and the container shape can
    # change under it, and on a classic machine there is no fifth petri dish
    # for it to be. Left in, it is a cup nothing can dip in, guessed one step
    # past yellow -- off the end of the dish holder, and marked on the paper by
    # containercenter.g as though it were somewhere.
    conf = fit_cups_to_shape(with_defaults(conf))
    bg = conf.get("brushograph", {})
    trays = conf.get("trays", {})
    water = trays.get("water", {}) if isinstance(trays, dict) else {}
    wx, wy = _num(water, "x", 0), _num(water, "y", 0)
    shape = str(bg.get("cup_shape", "classic")).strip().lower()
    # Every move to somewhere new — a tray, the canvas, the origin — is preceded
    # by a lift to this, and only this: not the larger of it and some other
    # height, so a macro's travel Z is always the one the config names for it.
    go_lift = _num(bg, "go_in_tray_lift", 8)
    dip = _num(bg, "dip_depth", -4)
    park_z = dip + 1  # Dip Depth + 1 — where home.g, clean.g and zero.g all end
    # A config need not carry a travel limit distinct from the painted size —
    # sketch.py falls back the same way for the same reason.
    max_w = _num(bg, "max_width", _num(bg, "width", 200))
    max_h = _num(bg, "max_height", _num(bg, "height", 200))
    # The corner the canvas starts at: the offset in X, and in Y the machine's
    # canvas start plus this painting's offset from it. calibrate.g's dot and
    # containercenter.g's ticks are painted on the canvas, so they follow it.
    ox, oy = canvas_origin(conf)

    out: dict[str, str] = {}

    # zero.g — the machine's own self-zero dance: touch the near corner off at
    # 0,0,0, sweep to the far corner and back to confirm nothing is fouled,
    # re-zero at a travel height, then a short jog sequence that ends by
    # declaring the offset X10 Y0 Z10 point. The jog's last step is 1 mm more
    # on Y, so later moves to Y0 stop short of the endstop instead of hitting it. A fixed routine tuned on the
    # actual hardware, not derived from the config, except for three things: the
    # far corner is the model's — a Micro's racks end well short of the Mini's
    # 160 — its very last line finishes the same way home.g and clean.g do,
    # parked at the water cup, Z = Dip Depth + 1, and its feedrates are held under the
    # Fast group's on the way out, which is what takes these F2100s down to
    # whatever the machine is actually set up to be driven at.
    sweep_x, sweep_y, sweep_z = MODELS[model_of(conf)]["zero_sweep"]
    out["zero.g"] = "\n".join([
        "G10 P0 L20 X0 Y0 Z0;",
        "G0 Z10 F1000;",
        "G90;",
        f"G0 X{sweep_x} Y{sweep_y} Z{sweep_z} F2100;",
        f"G0 X0 Y0 Z{sweep_z} F2100;",
        "G10 P0 L20 X0 Y0 Z10;",
        "G1 Z15 F1000;",
        "G1 Z10 F1000;",
        "G0 X-10 Y-10 F1200;",
        "G0 X+2 Y-8 F2100;",
        "G0 Y-7 F2100;",
        "G10 P0 L20 X10 Y0 Z10;",
        f"G0 X{_fmt(wx)} Y{_fmt(wy)} Z{_fmt(park_z)} F2100;",
    ]) + "\n"

    # home.g — park at the water cup, Z = Dip Depth + 1.
    lines = [
        "; home.g — park over the water cup, just above dipping depth",
        *_preamble(bg),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift — clear before crossing the bed",
        *_park(wx, wy, park_z),
    ]
    out["home.g"] = "\n".join(lines) + "\n"

    # paper.g — half of Max Width on X, all of Max Height on Y.
    px, py = max_w / 2, max_h
    lines = [
        "; paper.g — move the brush out of the way for replacing paper",
        *_preamble(bg),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift — clear before crossing the bed",
        f"G00 X{_fmt(px)} Y{_fmt(py)} ; half of Max Width, all of Max Height",
    ]
    out["paper.g"] = "\n".join(lines) + "\n"

    # clean.g — wash the brush at the water container, then park. Three dips,
    # no rim wipe, matching copicograf's own wash_the_brush(); the park at the
    # end matches home.g's, so a clean brush is also a homed one.
    lines = [
        "; clean.g — wash the brush in the water container, then park",
        f"; containers: {shape}",
        *_preamble(bg),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift",
        # No move to the middle of the cup first. The motion makes its own
        # approach now, to the back of the bay, which is where a brush comes in
        # from; going to the centre first crossed the mouth for no reason, and
        # on a holder whose cups sit south of the origin it was a move into the
        # Y endstop -- Brushparang's water cup is at Y -3.
        *_container_motion(conf, wx, wy, exits=_WASH_ROUTINE,
                           width=holder_of(conf)["water_bay_width"],
                           bend=False, press=WASH_PRESS),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift",
        *_park(wx, wy, park_z),
    ]
    out["clean.g"] = "\n".join(lines) + "\n"

    # calibrate.g — place the dot and park over it. No wash and nothing else:
    # this one is meant to do only the dot. It lifts first all the same, the
    # way every other macro here does, because it is run from wherever the
    # brush was left and where these macros leave it is the water cup at Dip Depth + 1
    # — inside the water container, under its rim. Crossing to the canvas
    # origin from there at that height drags the brush through the container
    # wall, so the trip starts at Go In Tray Lift, the height that clears the
    # rims. Z0 and Z10 stay literal for this macro specifically, not
    # canvas_height or go_in_tray_lift: the dot is the canvas itself, and the
    # park is only high enough to see it.
    lines = [
        "; calibrate.g — place the dot, then park over it",
        *_preamble(bg),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift — clear before crossing the bed",
        f"G00 X5 Y{_fmt(_num(bg, 'canvas_start_y', 0) + 5)} ; 5mm above Canvas Start Y",
        "G00 Z0 ; touch down — the single dot",
        "G00 Z10 ; park over the dot",
    ]
    out["calibrate.g"] = "\n".join(lines) + "\n"

    # What the two macros that draw have in common. Both touch down at
    # canvas_height, the figure the brush already paints the paper at, so a pen
    # fitted in its place draws at the height the config names and neither
    # macro has to invent a pen height nobody has a setting for.
    cz = _num(bg, "canvas_height", 0)
    wx_lim = workable_x(conf)
    # How far either of them may command, run-ups included: a few millimetres
    # short of the ends, so that nothing finishes against a stop. What a move
    # loses against a stop it loses for the rest of the file, and every line
    # after it lands short of where it says -- which in a file whose whole
    # content is where lines land would not look like a fault at all.
    reach_x, reach_y = wx_lim - _CLEAR, max_h - _CLEAR

    # containercenter.g -- the X of every container, painted on the canvas in
    # black, so the container positions in the form can be held against the
    # holder they claim to describe. A container position is the one setting
    # with nothing to check it against: where a cup is, is a measurement
    # somebody took with a rule and typed in, and the only way to read it back
    # was to watch a dip and judge by eye whether the brush went into the
    # middle of the cup or into a wall.
    #
    # Only X, and only on the canvas. The containers and the canvas share the
    # X axis and nothing else -- the cups sit in the strip of Y below the
    # paper -- so X is the whole of what a mark up on the paper can say about
    # them, and it is the interesting half: it is the spacing along the row
    # that auto-spacing guesses and a rule measures badly. The marks are
    # painted where a job paints, on paper that is already there, with no
    # container lifted out and nothing dismantled.
    #
    # Drawn with a pen fitted in the holder in place of the brush. This way
    # there is no need to pick up paint or wash the brush, and the macro
    # can mark every container regardless of which holder is in use.
    trays = conf.get("trays", {})
    cups = [(e, _num(e, "x")) for e in in_cup_order(tray_entries(conf))]
    # The canvas: where the paper is, and the near edge of it is where the
    # ticks stand. That edge is the closest the paper comes to the containers,
    # so a tick can be sighted down to the cup it belongs to without anything
    # in between.
    can_w, can_h = _num(bg, "width", max_w), _num(bg, "height", max_h)
    tick = min(_TICK, max(0.0, can_h))

    lines = [
        "; containercenter.g -- draw the X of every container on the canvas,",
        "; to check the container positions in the form against the holder.",
        ";",
        "; Drawn with a pen fitted in the holder in place of the brush.",
        "; Nothing is lifted out and nothing is dismantled: the",
        "; marks go where a job paints. Each tick stands at one container's X,",
        "; on the near edge of the canvas, which is the closest the paper comes",
        "; to the containers.",
        ";",
        "; Only X is marked, because X is all the canvas can say about a",
        "; container: the cups sit in the strip of Y below the paper. It is the",
        "; interesting half -- the spacing along the row is what auto-spacing",
        "; guesses, and what a rule measures worst.",
        ";",
        "; Sight each tick down to the cup it belongs to, or lay the holder",
        "; along the row of them. A tick that does not line up with the middle",
        "; of its cup is a position that wants correcting, and how far it",
        "; misses by is the correction, in millimetres, into that container's",
        "; X. Water is ticked too, and it is the one to correct first: every",
        "; other cup is spaced from it.",
    ]

    if tick < _TICK_MIN:
        lines += [
            ";",
            f"; The canvas is {_fmt(can_h)} mm deep, which is not enough to",
            "; draw a tick in, so this file does nothing.",
            *_preamble(bg),
        ]
    else:
        off_canvas = [e["label"] for e, ex in cups
                      if not ox <= ex <= ox + can_w]
        if off_canvas:
            lines += [
                ";",
                "; One tick or more stands past the end of the canvas and",
                "; lands off the paper unless a wider sheet is laid for it.",
                "; They are drawn anyway: a row of ticks missing its last one",
                "; says least about the end of the row, which is where the",
                "; spacing has had furthest to drift. Past the end here: "
                + ", ".join(off_canvas) + ".",
            ]
        lines += [
            ";",
            f"; {len(cups)} containers, in the order they stand on the bed.",
            f"; {_fmt(tick)} mm a tick.",
            *_preamble(bg),
            f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- clear before crossing the bed",
        ]
        for entry, ex in cups:
            head = f"; {entry['label']} [{entry['tray']}] -- X{_fmt(ex)}"
            if not 0 <= ex <= wx_lim:
                lines.append(head + " -- out of reach, not drawn")
                continue
            lines.append(head)
            lines += _comb_stroke(bg, True, ex, oy, oy + tick, 1,
                                  _run_up(ex, 1, 0.0, wx_lim), cz, go_lift)
        lines += [
            "; park",
            f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift",
            *_park(wx, wy, park_z),
        ]
    out["containercenter.g"] = "\n".join(lines) + "\n"

    # trump.g -- sign the lower right corner of the canvas, with a pen fitted
    # in the holder in place of the brush, like containercenter.g's ticks:
    # nothing to pick up and nothing to wash. Lower right is the canvas's far
    # X and its near Y, the edge nearest the containers, which is the bottom
    # of the painting as the plan and the preview show it.
    sign_w = min(_SIGN_MAX_W, can_w * 0.4)
    sign_h = sign_w / _SIGNATURE_W
    margin = min(_SIGN_MARGIN, can_w * 0.05, can_h * 0.05)
    sx0 = min(ox + can_w - margin - sign_w, reach_x - sign_w)
    sy0 = oy + margin
    lines = [
        "; trump.g -- sign the lower right of the canvas in Donald Trump's",
        "; hand: a stylised impression, not a traced facsimile.",
        ";",
        "; Drawn with a pen fitted in the holder in place of the brush.",
    ]
    if sign_h * 1.1 + margin > can_h or sx0 < 0:
        lines += [
            ";",
            "; The canvas is too small to sign, so this file does nothing.",
            *_preamble(bg),
        ]
    else:
        lines += [
            f"; {_fmt(sign_w)} mm wide, {_fmt(sign_h * 1.1)} mm tall, its lower "
            f"left at X{_fmt(sx0)} Y{_fmt(sy0)}.",
            *_preamble(bg),
            f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- clear before crossing the bed",
        ]
        for stroke in _SIGNATURE:
            pts = [(sx0 + px * sign_h, sy0 + py * sign_h) for px, py in stroke]
            lines += [f"G00 X{_fmt(pts[0][0])} Y{_fmt(pts[0][1])}",
                      _feed(bg, "normal") + " ; the rate a job paints at",
                      f"G01 Z{_fmt(cz)}",
                      *(f"G01 X{_fmt(px)} Y{_fmt(py)}" for px, py in pts[1:]),
                      _feed(bg, "fast"), f"G00 Z{_fmt(go_lift)}"]
        lines += ["; park", *_park(wx, wy, park_z)]
    out["trump.g"] = "\n".join(lines) + "\n"

    # mix-c.g, mix-m.g, mix-y.g, mix-k.g -- stir one colour cup.
    #
    # Watercolour in a crucible separates: pigment to the floor, water and the
    # methylcellulose that thickens it above. A job painted from a cup that has
    # stood overnight starts pale and comes up to colour somewhere in its first
    # strokes, which is the same fault the opening pickup was given
    # prepare_paint_count dips for, one cup further back.
    #
    # One file a colour rather than one file with four cups in it, because
    # mixing is a thing you do to the cup you have just topped up.
    for channel, tray in CMYK_TO_TRAY.items():
        out[f"mix-{channel.lower()}.g"] = _mix_macro(conf, channel, tray)

    # backlash.g -- the calibration sheet for Backlash X and Backlash Y,
    # drawn dry with a pen fitted in the holder in place of the brush.
    #
    # It was painted until v2.10.3. Measuring the play does not need paint:
    # the sheet is lines on paper and the reading is the gap between two of
    # them, which a pen makes as well as a brush does, and without a cup of
    # colour, a dip, or a wash afterwards. What the paint cost was the sheet itself -- every pair had
    # to come out of one pickup, 150 mm of painting on Pinkograph, so no
    # stroke could be longer than 55 mm and no station could be anywhere the
    # brush could not be fed from a cup.
    #
    # Backlash does not accumulate. Alternating moves lose the play once and
    # get it back on the next reversal, and a staircase with a net direction
    # loses it on the way out and regains it on the way back, so there is no
    # arrangement of moves that turns a half millimetre into a visible ten.
    # That rules out a drift test and leaves reading a gap, which is why this
    # prints a gauge alongside: the eye is poor at half a millimetre in the
    # open and good at telling two lines from one against a known example.
    #
    # Five stations -- the four corners of the sheet and its middle -- because
    # neither axis has one play. X changes along X, which is the belt; Y
    # changes along X too, which is the beam twisting. Both of those a row
    # across the bed could see. What a row cannot see is either of them
    # changing along Y, and a corner at each end of both axes can: two
    # stations at the same X that disagree say the play depends on where the
    # gantry is standing, which no pair of figures in the form can describe.
    # The middle is the check -- with the play a straight line across the bed
    # it falls halfway between the corners.
    # The sheet is laid out on everything the machine can paint, not on the
    # canvas the config happens to be set to. The figures it produces are
    # applied to every job on the machine, whatever size that job is, so they
    # are read across the whole of the ground those jobs can cover: a Mini
    # asked to paint 132 by 89 in the middle of a 151 by 156 bed would
    # otherwise be measured over two thirds of its X and well under half its
    # Y, and the play at the ends -- which is the whole point of the far-end
    # boxes -- read where the belt is not at its longest.
    #
    # The far edge is the paintable width or workable_x, whichever is nearer:
    # workable_x is how far a job already asks the machine to go and so how
    # far it is known to reach, and it is never the axis travel, because that
    # is where zero.g drives into the stops on purpose. The near edge is the
    # canvas offset, which is what keeps the pen out of the containers: on a
    # Mini they sit in the 32 mm of Y below the paper.
    paint_w = max(0.0, min(max_w, wx_lim) - ox)
    paint_h = max(0.0, max_h - oy)

    def pair(vertical, pos, start, end, lo, hi):
        """The two strokes of one test pair: one commanded line, drawn once
        arriving from each side, so the gap between the marks is the play."""
        lines = []
        for approach in (1, -1):
            lines += _comb_stroke(bg, vertical, pos, start, end, approach,
                                  _run_up(pos, approach, lo, hi), cz, go_lift)
        return lines

    def gauge(vertical, at, gap, start, end, lo, hi):
        """One gauge pair: the same stroke twice, `gap` apart, same side both
        times, so what is printed is the number and not the number plus the
        play."""
        lines = []
        for edge in (at, at + gap):
            lines += _comb_stroke(bg, vertical, edge, start, end, 1,
                                  _run_up(edge, 1, lo, hi), cz, go_lift)
        return lines

    def gauge_gaps(span: float) -> list[float]:
        """Which gaps a gauge with `span` millimetres to draw in can show.

        All five where there is room, and otherwise the widest are dropped
        one at a time until the clear space between pairs is at least as wide
        as the widest gap drawn. A reader who cannot tell the space after a
        pair from the pair itself has no ruler, and the gaps that go are the
        ones least needed: a gap of 2.5 mm is wide enough to lay a rule
        across, which is what a gauge is for saving you from at half a
        millimetre. The remaining pairs always run 0.5, 1, 1.5 ... from the
        narrowest, so they are counted from that end and none is ambiguous.
        """
        for n in range(len(_GAUGE_GAPS), 1, -1):
            gaps = _GAUGE_GAPS[:n]
            clear = (span - sum(gaps)) / (n - 1)
            if clear >= gaps[-1]:
                return list(gaps)
        return list(_GAUGE_GAPS[:2])

    def gauge_slots(lo: float, hi: float, gaps: list[float]) -> list[float]:
        """Where each gauge pair starts, with the same clear space between
        every pair whatever gap it is drawing.

        Spread evenly instead, the 0.5 mm pair sits in a slot as wide as the
        2.5 mm pair does and the clear space after the widest one shrinks
        towards its own gap, which is the one place a reader must not have to
        guess which line belongs to which pair.
        """
        clear = max(0.0, hi - lo - sum(gaps)) / max(1, len(gaps) - 1)
        at, out = lo, []
        for gap in gaps:
            out.append(at)
            at += gap + clear
        return out

    # The corners. Every stroke backs off _RUN_UP before it comes in, so a
    # station can stand at the very edge of the paintable area only where the
    # machine can reach that far past it: the outermost ones go to the corners
    # and are pulled in exactly as far as the run-up needs, and no further.
    # Pinkograph's stations come out at X10 and X138 of a bed that paints 0 to
    # 151, and at Y33 -- the bottom of the paper, with the containers in the
    # Y below it -- and Y143 of 156.
    x0 = max(ox, _RUN_UP)
    x1 = max(x0, min(ox + paint_w, reach_x - _RUN_UP))
    y0 = max(oy, _RUN_UP)
    y1 = max(y0, min(oy + paint_h, reach_y - _RUN_UP))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def station(px: float, py: float, sx: int, sy: int, note: str) -> list[str]:
        """One station: an upright pair and a flat pair meeting at (px, py).

        The upright pair is that station's X figure and the flat pair its Y
        figure, so one station answers both axes at one place on the bed.

        Both legs are drawn in the positive direction whichever corner they
        belong to, the corner ones running inward and the middle's centred on
        it. `_comb_stroke` settles by backing off before the start of a line,
        and at the far end of an axis backing off is backing into the stop.
        """
        span = leg / 2 if (sx == 0 or sy == 0) else leg
        vy = (py, py + span) if sy >= 0 else (py - span, py)
        hx = (px, px + span) if sx >= 0 else (px - span, px)
        if sx == 0 and sy == 0:
            vy, hx = (py - span, py + span), (px - span, px + span)
        return [
            f"; station at X{_fmt(px)} Y{_fmt(py)} -- {note}",
            *pair(True, px, vy[0], vy[1], 0.0, reach_x),
            *pair(False, py, hx[0], hx[1], 0.0, reach_y),
        ]

    # Where the two gauges go, and how long a station's leg is, which is one
    # question and not two. The stations hold the corners and the middle; what
    # is left for the gauges is the band between the top and bottom pairs of
    # them, either side of the middle station. Both rulers get their room
    # first and the legs take what remains, so the answer on a small machine
    # is short legs and a legible gauge rather than the reverse. The Mini's
    # legs come out at the 30 mm cap and the Mikro's just over the 10 mm
    # floor, and on the Mikro it is the gauges that then give way: its X
    # gauge shows four pairs where the Mini's shows five.
    usable_w, usable_h = x1 - x0, y1 - y0
    leg = max(_LEG_MIN, min(_TEST_LEG,
                            0.25 * min(paint_w, paint_h),
                            usable_w - 2 * _GAUGE_MIN - 2 * _CLEAR,
                            (usable_h - 2 * _CLEAR - _GAUGE_MIN) / 2))
    # The Y gauge's rows to the left of the middle station, the X gauge's
    # columns to its right, both drawn the height of the band. A gauge is a
    # ruler and can sit anywhere it is legible; these two places are simply
    # the paper the stations do not want.
    band = (y0 + leg + _CLEAR, y1 - leg - _CLEAR)
    left = (x0, cx - leg / 2 - _CLEAR)
    right = (cx + leg / 2 + _CLEAR, x1)
    yg_slots, yg_run = band, (left[0], min(left[1], left[0] + leg * 2))
    xg_slots, xg_run = right, (band[0], min(band[1], band[0] + leg * 2))
    xg_gaps = gauge_gaps(xg_slots[1] - xg_slots[0])
    yg_gaps = gauge_gaps(yg_slots[1] - yg_slots[0])
    xg_at = gauge_slots(*xg_slots, xg_gaps)
    yg_at = gauge_slots(*yg_slots, yg_gaps)

    # The figures, under the X gauge's columns only: the Y gauge's rows are
    # the same pairs in the same order, and figures beside them and above the
    # X columns as well were clutter. A row under the columns where the pairs
    # stand far enough apart for that, as they do on a Mini; where they do
    # not -- the Mikro's stand 4 to 5 mm apart -- every other figure goes a
    # row further down, so each is only beside the next but one. The columns
    # start above the figures and give up the room, down to _LEG_MIN.
    #
    # A figure may reach past its own column sideways. To the left it stops
    # short of the middle station's upright leg, which stands in the band; to
    # the right, at the edge of the paint or 3 mm short of the end of travel.
    x_names = [_fmt(g) for g in xg_gaps]
    x_mid = [a + g / 2 for a, g in zip(xg_at, xg_gaps)]
    x_w = [_text_w(n) for n in x_names]
    x_lo, x_hi = cx + _CLEAR, min(ox + paint_w, reach_x)
    band_h = band[1] - band[0]

    def label_fit(rows: int) -> float:
        """How tall the figures can be with `rows` rows under the columns."""
        h = _LABEL_H
        for i, (c, w) in enumerate(zip(x_mid, x_w)):
            h = min(h, (c - x_lo) / (w / 2), (x_hi - c) / (w / 2))
            j = i + rows   # the next figure in the same row
            if j < len(x_mid):
                # A digit and a half of clear paper between them, so two
                # figures in a row are not read as one number: with one
                # digit's width the Mikro's still read "0.51.5".
                h = min(h, (x_mid[j] - c) / ((w + x_w[j]) / 2 + 1.5 * _DIGIT_W))
        # The figures shrink before the columns drop below _LEG_MIN.
        return max(0.5, min(h, (band_h - _LEG_MIN) / rows - _LABEL_GAP))

    # Two rows only for figures a quarter larger, not for a hair: each row
    # costs the columns a figure's height.
    x_rows = 2 if label_fit(2) > 1.25 * label_fit(1) else 1
    xh = label_fit(x_rows)
    start = band[0] + x_rows * (xh + _LABEL_GAP)
    xg_run = (start, min(band[1], start + 2 * leg))

    lines = [
        "; backlash.g -- measure the play in X and Y with a pen, to fill in",
        "; Backlash X, Backlash X far end, Backlash Y and Backlash Y far end.",
        "; Needs a pen fitted where the brush goes, and paper under all of it:",
        "; it is drawn over everything the machine can paint and not over the",
        "; canvas a job happens to be set to, so lay a full sheet on the bed or",
        "; the outer marks will land on the bed itself. It visits no cup and",
        "; dips for nothing, so the machine needs no paint in it and there is",
        "; nothing to wash afterwards.",
        ";",
        "; Every pair is one commanded position drawn twice, arrived at from",
        "; each side in turn, and the gap between the two marks is the play.",
        ";",
        "; Five stations: the corners of the paintable area and its middle --",
        f"; here X{_fmt(x0)} to X{_fmt(x1)} and Y{_fmt(y0)} to Y{_fmt(y1)}."
        " Each is an",
        "; upright pair and a flat pair meeting at a corner: the upright one",
        "; is that station's X figure, read across the line, and the flat one",
        "; its Y figure, read up and down it.",
        ";",
        "; Backlash X is the two upright pairs at the X0 end and Backlash X far",
        "; end the two at the other; Backlash Y is the two flat pairs at the X0",
        "; end and Backlash Y far end the two at the other. Two stations at the",
        "; same end should agree: where they do not, the play depends on where",
        "; the gantry is standing along Y as well, which no pair of figures can",
        "; describe -- take the middle station's reading for both boxes and",
        "; expect the compensation to be right in the middle and light at the",
        "; edges. The middle station is the check either way: with the play a",
        "; straight line across the bed it falls halfway between the corners.",
        ";",
        "; Then the two gauges, each in its own direction: the Y gauge's rows",
        "; to the left of the middle station and the X gauge's columns to its",
        "; right. Both strokes of a gauge pair arrive from the same side, so",
        "; the play cannot open or close them: they are the ruler. Find the",
        "; gauge pair a test pair looks like and that is the figure, to a",
        "; tenth or so. Do not read one gauge against the other's pairs -- a",
        "; gap between two horizontal lines does not look like the same gap",
        "; between two vertical ones.",
        (f"; Both gauges are drawn {_gap_list(xg_gaps)} mm apart, narrowest"
         if xg_gaps == yg_gaps else
         f"; The X gauge is drawn {_gap_list(xg_gaps)} mm apart and the Y one"),
        ("; first, so count from that end. A" if xg_gaps == yg_gaps else
         f"; {_gap_list(yg_gaps)}, narrowest first, so count from that end. A"),
        "; gap wider than the widest pair drawn is wide enough to lay a rule",
        "; across, which is what a gauge is for saving you from at half a",
        "; millimetre and not at three -- so where the paper is too narrow to",
        "; keep the widest pairs apart from their neighbours, they are the",
        "; ones dropped. The X gauge's pairs have their gaps written under",
        "; them, drawn so the play cannot bend the figures; the Y gauge's are",
        "; the same gaps in the same order, counted from its narrowest pair.",
        ";",
        "; The corners stand as far out as the machine can measure, which is",
        "; not always the edge of the paint: every stroke backs off 10 mm and",
        "; comes in along the axis under test, so a station can only stand",
        "; where there is 10 mm of ground beyond it, and nothing here is",
        "; commanded within 3 mm of either far end. A move that finishes",
        "; against a stop loses what it loses for the rest of the file.",
        *_preamble(bg),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- clear before crossing the bed",
    ]

    # Round the sheet and then the middle, which is also the shortest way
    # between them.
    for px, py, sx, sy, note in (
        (x0, y0, 1, 1, "near X, near Y"),
        (x1, y0, -1, 1, "far X, near Y"),
        (x1, y1, -1, -1, "far X, far Y"),
        (x0, y1, 1, -1, "near X, far Y"),
        (cx, cy, 0, 0, "the middle"),
    ):
        lines += station(px, py, sx, sy, note)

    for i, (at, gap, name) in enumerate(zip(xg_at, xg_gaps, x_names)):
        lines.append(f"; X gauge pair {name} mm")
        lines += gauge(True, at, gap, xg_run[0], xg_run[1], 0.0, reach_x)
        # Under the column, every other one a row further down when there
        # are two rows.
        ty = xg_run[0] - (i % x_rows + 1) * (xh + _LABEL_GAP)
        lines += _text(bg, name, at + gap / 2 - _text_w(name) * xh / 2,
                       ty, xh, cz, go_lift, reach_x, reach_y)
    for at, gap in zip(yg_at, yg_gaps):
        lines.append(f"; Y gauge pair {_fmt(gap)} mm")
        lines += gauge(False, at, gap, yg_run[0], yg_run[1], 0.0, reach_y)

    lines.append(f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift")
    # Not the shared park: that one ends at Dip Depth + 1, which is below the
    # paper, and on a holder whose water crucible covers the origin it is
    # under the rim. A brush left there is a brush kept wet; a pen left there
    # is a pen pressed into whatever is under it.
    lines.append(f"G00 X{_fmt(wx)} Y{_fmt(wy)} ; park lifted -- a pen has no cup to hang in")
    out["backlash.g"] = "\n".join(lines) + "\n"

    # speedtest.g -- drive all three axes as hard as this config allows and
    # show whether the motors kept up.
    #
    # It fits nothing, touches nothing and marks nothing. The holder is empty:
    # no brush, no pen, no paint, no paper. That is the whole difference from
    # the first version of this, which drew two combs of dashes with a pen and
    # read the loss off the paper -- a fine instrument, and the wrong one for a
    # test whose whole point is that something is wrong with the machine. A
    # machine that is losing steps is a machine you do not want carrying a
    # loaded brush across a sheet, and asking for a pen and a full sheet before
    # it will tell you anything is asking for the setting-up you are in the
    # middle of failing at.
    #
    # A motor asked for more than it can give does not stop. It slips a step
    # and carries on, the controller never learns of it, and every move after
    # that lands short by whatever was lost -- for the rest of the file. That
    # is the fault behind a job whose last tray sits a few millimetres off its
    # first, and behind the black plate that moved 3 mm when a move in the cups
    # ran the carriage into the stop.
    #
    # Lost steps accumulate, which is what makes them readable without an
    # instrument. Play is given up at a reversal and handed back at the next,
    # so no arrangement of moves turns half a millimetre into a visible ten and
    # reading it needs the printed gauge backlash.g draws. Steps do not come
    # back. So this drives the machine hard, returns to one commanded position
    # and stands there long enough to be looked at; drives it hard again, and
    # comes back to the same place. What moved between one stop and the next is
    # steps.
    #
    # The reference is the water cup, because it is a thing on the bed to sight
    # the holder against and it is where every other macro parks anyway. The
    # precise reading is a mark the operator makes: a strip of tape across the
    # join of carriage and rail, one line drawn over both, on each axis. That
    # is a tool-free instrument better than a millimetre, and it is why the
    # macro stands still for _SPEED_DWELL seconds at every return rather than
    # touching the reference and moving on.
    #
    # Every return is arrived at from the same side over the same run-up, the
    # way backlash.g's gauge pairs are, so the play is identical at every stop
    # and cancels. Without that the reference would wander by the backlash on
    # each axis -- 0.9 mm on Pinkograph's X -- which is larger than most of what
    # this is looking for.
    #
    # Z never goes below `canvas_height`, the height the machine already holds
    # the tool at over the paper, and `dip_depth` -- the one height that wants a
    # crucible under it -- appears nowhere in the file. The legs stop at the
    # canvas origin in Y and so never cross the container strip; the return to
    # the water cup does cross it, at Go In Tray Lift, which is the height
    # home.g and clean.g already go to the same cup at.
    sx0, sx1 = _CLEAR, reach_x
    sy0, sy1 = max(oy, _CLEAR), reach_y
    smx, smy = (sx0 + sx1) / 2, (sy0 + sy1) / 2

    # The Y above which no container reaches, with clear air over it. The Z leg
    # is the only one that goes below Go In Tray Lift, so it is the only one
    # that has to be sure of this -- and the canvas origin is not the line to
    # be sure of. On a Mikro the bays are 26 mm deep about Y6 and so reach
    # Y21, while the paper starts at Y19: the first two millimetres of canvas
    # are over the lip of a crucible, and a hop that began there would come
    # down on it.
    cup_top = max((_num(e, "y") + _num(bg, "cup_depth", 26) / 2
                   for e in tray_entries(conf)), default=0.0)
    zy0 = min(sy1, max(sy0, cup_top + _CLEAR))

    # How long a reversal is. Worked out from the Fast group -- the shortest
    # move that reaches that feedrate is v^2/a, and the margin buys a moment of
    # holding it -- and then clamped to the ground each axis has, since a jab
    # that will not fit is not a jab.
    fast_v = (feed_rate(bg.get("moves", {}).get("fast", {}).get("feedrate_1", ""))
              if isinstance(bg.get("moves"), dict) else None)
    fast_a = (accel_rate(bg.get("moves", {}).get("fast", {}).get("acc", ""))
              if isinstance(bg.get("moves"), dict) else None)
    if fast_v and fast_a:
        want_jab = _SPEED_JAB_MARGIN * (fast_v / 60.0) ** 2 / fast_a
        jab_why = (f"v^2/a from F{_fmt(fast_v)} and {_fmt(fast_a)} mm/s^2, "
                   f"x{_fmt(_SPEED_JAB_MARGIN)}")
    else:
        want_jab = _SPEED_JAB_MIN
        jab_why = "the fallback -- this config names no Fast acceleration"
    jab_x = max(1.0, min(want_jab, sx1 - sx0))
    jab_y = max(1.0, min(want_jab, sy1 - sy0))
    short = [name for name, got in (("X", jab_x), ("Y", jab_y)) if got < want_jab - 1e-6]

    def at(x: float, y: float, times: int = 1) -> list[str]:
        """Back off and arrive, `times` over.

        Both run-ups come down from above so no approach has to back off past
        the origin end of an axis: the water cup sits at Y2 on Pinkograph, and
        a run-up below it would be a move into the Y stop.

        Once is enough to fix the side the carriage arrives from, which is
        what makes the play cancel between one stop and the next, and that is
        what every stop but the first gets. The opening stop gets
        _SPEED_APPROACHES of them, which is the acceleration measurement.
        """
        rx = max(0.0, min(_SPEED_RUN_UP, reach_x - x))
        ry = max(0.0, min(_SPEED_RUN_UP, reach_y - y))
        out = []
        for _ in range(max(1, times)):
            out.append(f"G00 X{_fmt(x + rx)} Y{_fmt(y + ry)}")
            out.append(f"G00 X{_fmt(x)} Y{_fmt(y)}")
        out[-1] += " ; arrive from the far side, as always"
        return out

    def reference(note: str, times: int = 1) -> list[str]:
        """Back to the water cup and stand there long enough to be read."""
        out = [
            f"; reference -- {note}",
            f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift",
        ]
        if times > 1:
            out += [
                f"; {times} back-offs and arrivals -- short enough to be all",
                "; acceleration, so put a watch on them",
            ]
        return out + at(wx, wy, times) + [
            f"G4 P{_SPEED_DWELL} ; stand still -- look at the marks",
        ]

    def shuttle(a: tuple[float, float], b: tuple[float, float],
                trips: int) -> list[str]:
        """`trips` round trips between two points, at the machine's top rate.

        The first move carries both words, because it arrives from wherever the
        last leg finished. The round trips carry only the words that change, so
        a leg that works one axis says so -- `G00 Y153`, not `G00 X75.5 Y153`
        with an X word that has read the same since the leg began. It makes no
        difference to the motion; it makes the difference between a file that
        describes what it is doing and one that leaves a reader wondering what
        the X motor is being asked for.
        """
        moves = [i for i, (p, q) in enumerate(zip(a, b)) if abs(p - q) > 1e-9]
        if not moves:
            return []
        out = [f"G00 X{_fmt(a[0])} Y{_fmt(a[1])}"]
        for _ in range(trips):
            for end in (b, a):
                out.append("G00 " + " ".join(
                    f"{'XY'[i]}{_fmt(end[i])}" for i in moves))
        return out

    def leg_sweeps() -> list[str]:
        """End to end on each axis in turn: top speed, one motor at a time."""
        return [
            "; leg 1 -- end to end on X and then on Y, "
            f"{_SPEED_SWEEPS} round trips each.",
            "; The longest run either axis has in it, and the only leg that",
            "; spends real time holding the feedrate rather than getting there",
            "; and stopping again. On a Cartesian machine each half of it is",
            "; one motor working while the other only holds its position --",
            "; a stepper draws current standing still, which is what holding",
            "; is. On a CoreXY both motors turn for either half, and it is the",
            "; diagonals of leg 2 that single one of them out instead.",
            *shuttle((sx0, smy), (sx1, smy), _SPEED_SWEEPS),
            *shuttle((smx, sy0), (smx, sy1), _SPEED_SWEEPS),
        ]

    def leg_diagonals() -> list[str]:
        """Both diagonals: the two motors together, and the corners."""
        return [
            f"; leg 2 -- both diagonals, {_SPEED_SWEEPS} round trips each.",
            "; A corner to corner run is the longest move the bed holds, and",
            "; it is both motors at once on a Cartesian machine -- the most",
            "; current the supply is ever asked for. On one belted CoreXY it is",
            "; instead one motor doing the whole of it while the other stands",
            "; still, which is the harder half of the same question.",
            *shuttle((sx0, sy0), (sx1, sy1), _SPEED_SWEEPS),
            *shuttle((sx0, sy1), (sx1, sy0), _SPEED_SWEEPS),
        ]

    def leg_reversals() -> list[str]:
        """Full-speed reversals: up to the feedrate and straight back down."""
        out = [
            f"; leg 3 -- {_SPEED_JABS} reversals on X, then on Y, then on both",
            f"; together, {_fmt(jab_x)} mm on X and {_fmt(jab_y)} mm on Y ({jab_why}).",
            "; Each one is long enough to reach the Fast feedrate and no",
            "; longer, so the axis is at the top of its speed at the moment it",
            "; is asked to turn round. That is where steps go: a stepper's",
            "; torque falls away as it speeds up, and what loses them is the",
            "; demand meeting that falling curve, not acceleration on its own.",
            ";",
            "; This is also the leg to put a watch on. Five is a number you can",
            "; count, and every reversal is a known distance covered by getting",
            "; to the feedrate and stopping again -- so the time a block takes",
            "; is the acceleration, and it is the only leg here whose duration",
            "; says anything. A block that runs long is an axis not reaching",
            "; the figure the config claims for it.",
        ]
        for dx, dy in ((1, 0), (0, 1), (1, 1)):
            lo = (smx - dx * jab_x / 2, smy - dy * jab_y / 2)
            hi = (smx + dx * jab_x / 2, smy + dy * jab_y / 2)
            out += shuttle(lo, hi, _SPEED_JABS)
        return out

    def leg_z() -> list[str]:
        """Z hopped its full canvas range with X and Y moving through it."""
        out = [
            f"; leg 4 -- {_SPEED_HOPS} hops of Z between the canvas height and",
            "; Go In Tray Lift, with X and Y crossing the bed through every one",
            "; of them: all three motors in every single move, which is the",
            "; most this machine is ever asked for at once. The holder is",
            "; empty, so the low end of the hop is air.",
            ";",
            "; Out of the containers first, and only then down. The reference",
            "; stop leaves the tool over the water cup, and a move that set off",
            "; for the canvas while already dropping Z would be under the rim",
            "; well before it had cleared it -- the bay is deep in Y and the",
            "; first hop would cross its lip two thirds of the way down. This",
            f"; leg therefore starts at Y{_fmt(zy0)}, which is clear of every cup",
            "; rather than merely on the paper: the two are not the same line",
            "; on every machine. Every Z below Go In Tray Lift in this file",
            "; happens here, and these are the figures that keep it true.",
            f"G00 X{_fmt(sx0)} Y{_fmt(zy0)} Z{_fmt(go_lift)} ; clear of the cups before any Z",
        ]
        for i in range(_SPEED_HOPS):
            down = i / max(1, _SPEED_HOPS - 1)
            up = min(1.0, (i + 0.5) / max(1, _SPEED_HOPS - 1))
            out.append(f"G00 X{_fmt(sx0 + (sx1 - sx0) * down)} "
                       f"Y{_fmt(zy0 + (sy1 - zy0) * down)} Z{_fmt(cz)}")
            out.append(f"G00 X{_fmt(sx0 + (sx1 - sx0) * up)} "
                       f"Y{_fmt(zy0 + (sy1 - zy0) * up)} Z{_fmt(go_lift)}")
        return out

    lines = [
        "; speedtest.g -- drive all three axes as hard as this config allows,",
        "; and show whether the motors kept up.",
        ";",
        "; Fit nothing. No brush, no pen, no paint, no paper: this marks",
        "; nothing and touches nothing, and it is the one macro you want to be",
        "; able to run on a machine you do not yet trust. Zero or home it",
        "; first, though -- what this reads is where the machine believes it is",
        "; against where it actually is, and that has to start out true.",
        ";",
        "; A motor asked for more than it can give does not stop. It slips a",
        "; step and carries on, the controller never learns of it, and every",
        "; move after that lands short by whatever was lost -- for the rest of",
        "; the file. That is the fault behind a job whose last tray sits a few",
        "; millimetres off its first.",
        ";",
        "; Before you start, mark the machine: a strip of tape across the join",
        "; of carriage and rail on each axis, and one line drawn over both",
        "; halves of it. That is the instrument, it costs nothing, and it reads",
        "; better than a millimetre.",
        ";",
        f"; The macro then returns to the water cup at X{_fmt(wx)} Y{_fmt(wy)} and stands",
        f"; still for {_SPEED_DWELL} seconds -- once before anything is asked of the",
        "; machine, and once after each of the four legs. At every stop, look:",
        "; the holder should sit over the middle of the cup and the two halves",
        "; of each tape mark should still line up. The first stop where they do",
        "; not names the leg that cost it, and every stop after it carries that",
        "; loss as well, because nothing ever tells the machine it lost",
        "; anything. Unlike play, steps do not come back.",
        ";",
        f"; The opening stop is reached {_SPEED_APPROACHES} times over -- back off and arrive,",
        f"; {_SPEED_APPROACHES} times, and then the dwell. That short pair is the one motion",
        "; in this file worth putting a watch on for acceleration: everything",
        "; else is long enough to reach the Fast feedrate, so its time is a",
        "; run-up plus a cruise plus a stop and the cruise is most of it, while",
        "; the back-off and the arrival are short enough to be all getting up",
        "; to speed and slowing down again. Time them at the top of the run and",
        "; the acceleration falls out with no feedrate term in it. Every later",
        "; stop is arrived at once, which is all that is needed to fix the side",
        "; it comes from.",
        ";",
        "; Every return is arrived at from the same side over the same run-up,",
        "; so the play is identical at every stop and cancels. What moves",
        "; between one stop and the next is steps and not backlash -- read",
        "; backlash.g's sheet for that, which is a different measurement and",
        "; wants a pen and a gauge.",
        ";",
        "; Nothing here goes below the canvas height, and Dip Depth appears",
        "; nowhere in this file: the one height that wants a crucible under it",
        "; is the one height this never asks for. The legs stop at the canvas",
        "; origin in Y and never cross the container strip; the trip back to",
        "; the water cup does cross it, at Go In Tray Lift -- the height home.g",
        "; and clean.g already reach that same cup at.",
        ";",
        "; The four legs are driven over all the ground the machine has, and",
        f"; not over the canvas a job happens to be set to: here X{_fmt(sx0)} to",
        f"; X{_fmt(sx1)}, and Y{_fmt(sy0)} to Y{_fmt(sy1)}. They stop {_fmt(_CLEAR)} mm short of the far end",
        "; of each axis and no closer, because a move that finishes against a",
        "; stop loses steps by definition and this file would then be reporting",
        "; the very fault it came to look for.",
        ";",
        "; Nothing here is driven faster than the machine is configured for.",
        "; On Marlin every move runs at the Fast feedrate. On GRBL and FluidNC",
        "; a G0 runs at the controller's own rapid rate, whatever that is set",
        "; to -- which is the real limit of the machine, and the honest thing to",
        "; ask it for.",
    ]
    if short:
        lines += [
            ";",
            f"; {' and '.join(short)} {'have' if len(short) > 1 else 'has'} less ground than a full-speed",
            "; reversal wants, so the jabs there are as long as the bed allows.",
            "; That axis is tested a little below its top speed, which is the",
            "; most this machine can be asked for without finishing against a",
            "; stop.",
        ]
    lines += [
        *_preamble(bg),
        f"G00 Z{_fmt(go_lift)} ; Go In Tray Lift -- clear before crossing the bed",
        *reference("before anything is asked of the machine", _SPEED_APPROACHES),
    ]
    for leg, note in zip((leg_sweeps, leg_diagonals, leg_reversals, leg_z),
                         _SPEED_LEG_NOTES):
        lines += leg()
        lines += reference(note)
    out["speedtest.g"] = "\n".join(lines) + "\n"

    # Nothing here crosses the bed faster than the config's Fast group says the
    # machine is driven -- zero.g's own figures included, which is the whole
    # point: they came off the machine it was first tuned on. The file says so
    # where it made a difference, because a macro is read and a feed that is
    # not the one in the file is the kind of thing that is looked for later.
    ceiling = _fast_feed(bg)
    held = {}
    for name, text in out.items():
        if ceiling:
            text, lowered = _cap_feeds(text, ceiling)
            if lowered:
                text = _with_note(text, f"; feeds held at F{_fmt(ceiling)}, the "
                                        f"Fast feedrate this machine is set to")
        held[name] = text

    # Every macro, zero.g's fixed routine included, says what made it — and
    # goes out in ASCII, like everything else the machine is sent.
    return {name: to_ascii(gcode_note() + "\n" + held[name])
            for name in MACRO_NAMES}
