#!/usr/bin/python3
from pygcode import Line, GCodeLinearMove, GCodeRapidMove
import math
import random
import re
from collections import namedtuple

# A bare G0/G1 made only of X Y Z E F words, the form the WebUI's adapted
# paths are written in. Parsing each of those with pygcode was most of the
# time a job took, so they are read here and anything else still goes to
# pygcode.
_PLAIN_MOVE = re.compile(r"G0*([01])((?: [XYZEF]-?(?:\d+\.?\d*|\.\d+))*)")
_PLAIN_WORD = re.compile(r" ([XYZEF])(\S+)")
_XY = namedtuple("_XY", "X Y")

# Written just before every descent into a cup, so the WebUI preview can count
# dips and tell time in the paint from painting. Heights cannot: a dip depth
# equal to the canvas height puts both at the same Z.
DIP_MARKER = "; dip"

# How many chords a Z ramp is drawn with, so its rate eases to nothing where
# the level leg beside the containers takes over instead of stopping dead.
# On Pinkograph a ramp is 9 mm of Z over 103 of bed: straight, that is 4.99°
# all the way and a 4.99° step into the level leg. Eased over twelve chords,
# the step is 1.18° and the sharpest join inside the ramp 2.08°. Sixteen buys
# 0.4° more and past that it is all file and no smoothness.
RAMP_CHORDS = 12

# How many places across a rectangular bay the dips are spread over, when the
# config does not say. Odd on purpose: the stride below wants a lane count it
# is coprime with, and an odd one always has 2 to hand.
DEFAULT_DIP_LANES = 5


def dip_lanes(tray_x, width, lanes, x_limits=(0.0, float("inf"))):
    """The X positions successive dips into one bay use, in visiting order.

    A bay is loaded by going straight down and drawing the brush up the
    stairs, which works the paint along one line across the bay and leaves
    the rest of it alone. Moving that line for each pickup is what mixes the
    cup: the pigment that settles gets lifted wherever the brush lands next,
    and no single lane is scraped bare while the paint beside it is untouched.

    The lanes are evenly spaced over the same 70% of the width the stir used,
    which keeps 15% of the bay off each wall, and they are stepped through a
    stride at a time rather than left to right, so one pickup and the next
    land at opposite ends of the bay instead of creeping across it. The stride
    is the largest one coprime with the count, so every lane is still visited
    once per cycle: five lanes go 0 2 4 1 3, which is -r, 0, +r, -r/2, +r/2.

    Kept inside x_limits the way the stir was, and by shrinking rather than
    clipping: a bay at the end of the axis gives up the same distance on each
    side, so its lanes stay centred on the cup instead of bunching against the
    near rim. Under half a millimetre of reach there is nothing to spread, and
    every pickup goes down the middle.
    """
    lanes = max(1, int(lanes))
    lo, hi = x_limits
    reach = min(width / 2 * 0.7, tray_x - lo, hi - tray_x)
    if lanes == 1 or reach < 0.5:
        return [tray_x]
    stride = next(s for s in range(lanes // 2, 0, -1) if math.gcd(s, lanes) == 1)
    return [tray_x - reach + 2 * reach * ((i * stride) % lanes) / (lanes - 1)
            for i in range(lanes)]


def _read_plain_move(line_text):
    """(text, xy) for a plain move, as the pygcode path would have seen it.

    text is what the pen-up / pen-down checks compare against, which pygcode
    normalises to "G01 Z6 F600" whatever the word order or spelling of the
    numbers; for any other move it only has to match neither. xy carries X
    and Y when the line has both, and is None otherwise. A blank line gives
    (None, None). None means the line is not plain and needs pygcode.
    """
    body = line_text.strip()
    if not body:
        return None, None
    m = _PLAIN_MOVE.fullmatch(body)
    if m is None:
        return None
    words = {}
    for letter, value in _PLAIN_WORD.findall(m.group(2)):
        if letter in words:
            return None
        words[letter] = float(value)
    text = ""
    if m.group(1) == "1" and words.keys() == {"Z", "F"} and words["F"] == 600:
        if words["Z"] == 6:
            text = "G01 Z6 F600"
        elif words["Z"] == 1:
            text = "G01 Z1 F600"
    xy = _XY(words["X"], words["Y"]) if "X" in words and "Y" in words else None
    return text, xy


def _mm(v):
    """A container coordinate, kept to a hundredth of a millimetre.

    These were cut to whole millimetres with int(), which on a holder with
    half-millimetre centres — the Micro's colours sit 20.5 mm from the water —
    put every colour 0.5 mm off where the holder has it, and on the Micro's
    11.4 mm crucibles that is felt.
    """
    return round(float(v), 2)


def _linear_xy(x, y):
    """str(GCodeLinearMove(X=x, Y=y)), without building one per stroke point."""
    return f"G01 X{round(float(x), 3):g} Y{round(float(y), 3):g}"


class Copicograf:
    def __init__(self, conf, gcodes=[]):
        self.conf = conf

        self.gcodes = gcodes

        self.water_tray_x = _mm(self.conf["trays"]["water"]["x"])
        self.water_tray_y = _mm(self.conf["trays"]["water"]["y"])

        self.canvas_height = int(self.conf["brushograph"]["canvas_height"])
        self.go_in_tray_lift = int(self.conf["brushograph"]["go_in_tray_lift"])
        self.move_to_other_shape_lift = int(self.conf["brushograph"]["move_to_other_shape_lift"])

        # The three figures that describe a round cup: how wide a chord the
        # brush sweeps down in the paint, and how far out and how high it drags
        # the bristles over the rim afterwards. They are read where a round cup
        # is used and nowhere else -- a rectangular bay is swiped up its stairs
        # and wipes itself -- so a machine that has no petri dish holder should
        # not have to carry figures describing one. The Mikro is exactly that
        # machine: the dishes span 173 mm against its 65 of X, it is given no
        # Classic option, and its holder preset sets the three heights a
        # crucible fixes and none of these. Demanded outright, they made a
        # freshly created Mikro config fail every run with a KeyError before
        # anything was painted.
        #
        # Absent, they are nothing: a sweep of no radius is the plain dip the
        # brush would make anyway, and a wipe of no radius is a move to the
        # middle of the cup, which is where the brush already is. That is the
        # right answer for a machine with no dishes and a poor one for a
        # classic machine that has simply lost them, so the WebUI says so in
        # the run log rather than leaving a shape-defining figure at zero
        # quietly.
        def dish(key):
            value = self.conf["brushograph"].get(key)
            return int(value) if value not in (None, "") else 0

        self.remove_drops_lift = dish("remove_drops_lift")
        self.tray_enter_radius = dish("tray_enter_radius")
        self.remove_drops_radius = dish("remove_drops_radius")
        # How far the brush descends into a cup. Was fixed at -4, which is deeper
        # than a shallow petri dish wants. Absent from a config, that stays the
        # behaviour.
        self.dip_depth = float(self.conf["brushograph"].get("dip_depth", -4))
        bg = self.conf["brushograph"]
        self.cup_shape = str(bg.get("cup_shape", "classic")).strip().lower()
        # The modern holder's crucibles are fixed by the print: the swipe runs
        # 23.5 mm of the Mini's 27.6 mm crucible. Not a setting, so not read
        # from the config; the WebUI sets it for the model it is painting on.
        self.cup_depth = 23.5
        # How wide a crucible is across X, and the water one, which is wider.
        # Fixed by the print like the length, and set the same way.
        self.cup_width = 16.2
        self.water_cup_width = 27.6
        # The X the stir may use, low and high. The WebUI sets it from the
        # model's travel, keeping the near end off the endstop by the backlash
        # take-up; on its own copicograf only knows about the endstop.
        self.x_limits = (0.0, float("inf"))
        # The lowest Y any trip into a container may ask for. A bay is deeper
        # than the strip of Y it stands in on more than one machine, so its
        # near end comes out south of the origin -- Brushparang's cups sit at
        # Y -3 and their 30 mm bays reach to Y -13.5 -- and there is no ground
        # down there. A move that finishes against a stop loses what it loses
        # for the whole of the rest of the file: the axis stalls, the counter
        # keeps going, and every coordinate after it lands that much out. It
        # is a dip that crashes and the far end of the canvas that shows it.
        # Set by the caller, the way x_limits is, to the take-up where
        # backlash compensation is on: that pass writes coordinates low by up
        # to the play while the axis travels down.
        self.y_floor = 0.0
        self.cup_swipe_exit_z = float(bg.get("cup_swipe_exit_z", 1.0))
        # How many places across the bay the dips are spread over. 1 puts every
        # one of them down the middle, which is what a rectangular bay did
        # before there was anything to mix the paint.
        try:
            self.cup_dip_lanes = max(1, int(bg.get("cup_dip_lanes", DEFAULT_DIP_LANES)))
        except (TypeError, ValueError):
            self.cup_dip_lanes = DEFAULT_DIP_LANES
        # Which lane each cup is due next, keyed by where the cup is. Per cup,
        # so every one of them works its own paint evenly however often the
        # job visits it — the water is dipped three times a wash and a colour
        # once a pickup.
        self._next_lane = {}

        self.offset_y = float(self.conf["brushograph"]["offset_y"])
        self.offset_x = float(self.conf["brushograph"]["offset_x"])
        self.paint_per_run_min = int(self.conf["brushograph"]["paint_per_run_min"])
        self.paint_per_run_max = int(self.conf["brushograph"]["paint_per_run_max"])
        self.randomize_paint_per_run()
        self.result_file = "copicograf.gcode"

        self.prepare_paint_count = int(self.conf["brushograph"]["prepare_paint_count"])

        self.initial_gcode_acc = self.conf["brushograph"]["moves"]["normal"]["acc"]
        self.initial_gcode_feedrate_1 = self.conf["brushograph"]["moves"]["normal"]["feedrate_1"]
        self.initial_gcode_feedrate_2 = self.conf["brushograph"]["moves"]["normal"]["feedrate_2"]

        self.paint_gcode_acc = self.conf["brushograph"]["moves"]["fast"]["acc"]
        self.paint_gcode_feedrate_1 = self.conf["brushograph"]["moves"]["fast"]["feedrate_1"]
        self.paint_gcode_feedrate_2 = self.conf["brushograph"]["moves"]["fast"]["feedrate_2"]

        self.remove_drops_gcode_acc = self.conf["brushograph"]["moves"]["remove_drops"]["acc"]
        self.remove_drops_gcode_feedrate_1 = self.conf["brushograph"]["moves"]["remove_drops"]["feedrate_1"]
        self.remove_drops_gcode_feedrate_2 = self.conf["brushograph"]["moves"]["remove_drops"]["feedrate_2"]

    def randomize_paint_per_run(self):
        # randomize paint per run
        self.paint_per_run = random.randrange(self.paint_per_run_min, self.paint_per_run_max)

        # self.paint_per_run = 300

    # def run_machine(self, gcode_result):

    # p = printcore('/dev/cu.usbserial-2130', 115200)
    # or pass in your own array of gcode lines instead of reading from a file
    # gcode = [i.strip() for i in open(gcode_result)]
    # gcode = gcoder.LightGCode(gcode)

    # startprint silently exits if not connected yet
    # while not p.online:
    #     time.sleep(0.1)

    # p.startprint(gcode)

    def save_gcode(self, result_file):
        gcfh = open(result_file, "w+")
        gcfh.write("\n".join(str(g) for g in self.gcodes))
        gcfh.close()

    def prepare_path(self, gcode_path, color_tray_x, color_tray_y, calibrate=True,
                     pickup_at=None, park=True, wash_from=None):
        def set_normal_speed():
            self.gcodes.append(self.initial_gcode_acc)
            self.gcodes.append(self.initial_gcode_feedrate_1)
            self.gcodes.append(self.initial_gcode_feedrate_2)

        def set_fast_speed():
            self.gcodes.append(self.paint_gcode_acc)
            self.gcodes.append(self.paint_gcode_feedrate_1)
            self.gcodes.append(self.paint_gcode_feedrate_2)

        def set_remove_drops_speed():
            self.gcodes.append(self.remove_drops_gcode_acc)
            self.gcodes.append(self.remove_drops_gcode_feedrate_1)
            self.gcodes.append(self.remove_drops_gcode_feedrate_2)

        set_normal_speed()
        self.gcodes.append("G90 ; sets absolute positioning")
        self.gcodes.append("G21 ; set units to millimeters")
        self.gcodes.append("M400 ; finish moves")
        self.gcodes.append(GCodeRapidMove(z=self.go_in_tray_lift))
        self.gcodes.append("G28 X Y ; home the X and Y axes only")

        self.dist_painted = 0

        def get_coords_in_tray(tray_x, tray_y):
            """Calculate entering and leaving point of brush in tray."""
            angle = random.uniform(0, 2 * math.pi)
            # The chord is swept from both ends, so whichever end runs out of
            # ground first sets the radius for all four quadrants -- shrunk
            # rather than clipped, because clipping one end alone leaves the
            # sweep working one side of the dish and leaving the rest of the
            # paint alone, which is the same argument the stir across X makes.
            # A dish sits in the strip along the front, and a sweep wider than
            # that strip is deep reaches south of the origin: on the Mini's
            # dish, 15 mm of enter radius around a tray at Y 6 asks for Y -9.
            radius = min(self.tray_enter_radius, max(0.0, tray_y - self.y_floor))
            delta_x = abs(radius * math.cos(angle))
            delta_y = abs(radius * math.sin(angle))

            first_coords = (0, 0)
            second_coords = (0, 0)

            #########################################################
            # 4 possible ways for brush to enter tray (4 quadrants) #
            #########################################################
            quadrant = random.randrange(4)

            # 1. quadrant
            if quadrant == 0:
                first_coords = (_mm(tray_x + delta_x), _mm(tray_y + delta_y))
                second_coords = (_mm(tray_x - delta_x), _mm(tray_y - delta_y))

            # 2. quadrant
            if quadrant == 1:
                first_coords = (_mm(tray_x - delta_x), _mm(tray_y + delta_y))
                second_coords = (_mm(tray_x + delta_x), _mm(tray_y - delta_y))

            # 3. quadrant
            if quadrant == 2:
                first_coords = (_mm(tray_x - delta_x), _mm(tray_y - delta_y))
                second_coords = (_mm(tray_x + delta_x), _mm(tray_y + delta_y))

            # 4. quadrant
            if quadrant == 3:
                first_coords = (_mm(tray_x + delta_x), _mm(tray_y - delta_y))
                second_coords = (_mm(tray_x - delta_x), _mm(tray_y + delta_y))

            if first_coords[1] > 1000 or second_coords[1] > 1000:
                print("big second")

            return first_coords, second_coords

        def get_relative_point(tray_x, tray_y, x, y, ratio):
            delta_x = abs(tray_x - x)
            delta_y = abs(tray_y - y)

            x_operator = 1
            if tray_x > x:
                x_operator = -1

            y_operator = 1
            if y < tray_y:
                y_operator = -1

            point_x = int(tray_x + (x_operator * delta_x * ratio))
            point_y = int(tray_y + (y_operator * delta_y * ratio))

            # print('tray x: ', tray_x, ', tray y: ', tray_y,
            #       ', x: ', x, ', y: ', y, ', ratio: ', ratio, ', point x: ', point_x, ', point y: ', point_y)

            return point_x, point_y

        def wipe_axis(tray_x, tray_y):
            """Which way the two wipes run for the cup at this position.

            Along the row the cups sit in, taken from the nearest other cup
            rather than assumed to be X, so a machine that arranges its cups
            differently still wipes along its own row. Square to the way the
            brush leaves would be the other reading of "each side", and it is
            wrong here: the brush leaves towards the canvas, so square to that
            runs along the front edge of the bed and off it.
            """
            nearest, ux, uy = None, 1.0, 0.0
            for name, t in (self.conf.get("trays", {}) or {}).items():
                if name == "additionals" or not isinstance(t, dict):
                    continue
                tx, ty = _mm(t.get("x", 0)), _mm(t.get("y", 0))
                d = calculate_dist(tray_x, tray_y, tx, ty)
                if d > 1 and (nearest is None or d < nearest):
                    nearest, ux, uy = d, (tx - tray_x) / d, (ty - tray_y) / d
            return ux, uy

        def remove_drops(tray_x, tray_y, x, y):
            """Drag the bristles over the rim, once on each side.

            Wiping only where the brush happens to be leaving strips the drop
            off one side and leaves it on the other, and that one falls on the
            painting. How far out the drag goes is remove_drops_radius, and how
            fast is the config's remove_drops speed group; neither is decided
            here.
            """
            ux, uy = wipe_axis(tray_x, tray_y)
            inner = self.tray_enter_radius
            outer = self.remove_drops_radius

            for side in (1, -1):
                self.gcodes.append(GCodeLinearMove(
                    X=_mm(tray_x + ux * inner * side),
                    Y=_mm(tray_y + uy * inner * side)))
                self.gcodes.append(GCodeLinearMove(Z=self.remove_drops_lift))
                set_remove_drops_speed()
                self.gcodes.append(GCodeLinearMove(
                    X=_mm(tray_x + ux * outer * side),
                    Y=_mm(tray_y + uy * outer * side)))
                self.gcodes.append(GCodeRapidMove(Z=self.go_in_tray_lift))
                set_fast_speed()

        # The containers as seen from above, a little larger than they are, so
        # the walls count as part of them. A bay is its rectangle; a round dish
        # is squared off, which is the generous way round.
        def cup_mouths():
            rect = self.cup_shape in ("modern", "custom")
            for name, tray in self.conf.get("trays", {}).items():
                if name == "additionals" or not isinstance(tray, dict) or "x" not in tray:
                    continue
                tx, ty = float(tray["x"]), float(tray.get("y", 0))
                if rect:
                    w = self.water_cup_width if name == "water" else self.cup_width
                    d = self.cup_depth
                else:
                    w = d = 2 * self.remove_drops_radius
                w, d = w * 1.15, d * 1.15
                yield tx - w / 2, tx + w / 2, ty - d / 2, ty + d / 2

        def _box_span(ax, ay, bx, by, box):
            """Which part of A->B lies inside the box, as (t0, t1), or None."""
            x0, x1, y0, y1 = box
            lo, hi = 0.0, 1.0
            for a, b, q0, q1 in ((ax, bx, x0, x1), (ay, by, y0, y1)):
                span = b - a
                if abs(span) < 1e-9:
                    if not q0 <= a <= q1:
                        return None
                    continue
                t0, t1 = (q0 - a) / span, (q1 - a) / span
                if t0 > t1:
                    t0, t1 = t1, t0
                lo, hi = max(lo, t0), min(hi, t1)
                if lo > hi:
                    return None
            return lo, hi

        def ramp_z(ax, ay, az, bx, by, bz):
            """Straight from A to B, with Z easing in and out of its change.

            Z on one straight line changes rate in a single step where the ramp
            meets the level leg beside the containers, and the planner reads
            that as a corner and slows through it — a hesitation in the middle
            of the bed, which is the thing running Z with the travel was meant
            to be rid of. So Z is eased: it moves slowest at both ends of the
            ramp and quickest in the middle, which leaves it already still
            where the level leg picks it up, and the two read as one move.

            The line in X and Y is the same line as before, cut into chords —
            a controller draws any curve as chords in the end. A dozen of them,
            which leaves no join above about two degrees for the planner to
            slow for, and each chord long enough not to starve it.

            The easing is also the safer curve. It holds Z nearer the tray lift
            at the container end of the ramp than a straight line does, which
            is the end where the rims are.
            """
            span = max(abs(bx - ax), abs(by - ay))
            steps = RAMP_CHORDS if span >= 2 * RAMP_CHORDS else 1
            for k in range(1, steps + 1):
                t = k / steps
                ease = t * t * (3 - 2 * t)
                self.gcodes.append(GCodeLinearMove(
                    X=_mm(ax + (bx - ax) * t),
                    Y=_mm(ay + (by - ay) * t),
                    Z=round(az + (bz - az) * ease, 2)))

        def travel_with_z(from_x, from_y, to_x, to_y, z_hold, z_end,
                          to_cup, ramp=True):
            """Cross the bed while Z changes, the change ending as it arrives.

            Z used to be set standing still and the trip flown level, which is
            a pause at each end. It runs with the travel instead: one ramp, at
            one steady rate, finishing exactly where the brush is going —
            against the container on the way out, on the spot it paints on the
            way back.

            What it may not do is ramp over the containers. A ramp stretched
            across the whole trip is below the rims while it is crossing them:
            from the black crucible to the near corner of a canvas offset 25 mm
            out, an even descent passes over the yellow crucible at Z 6.2 with
            the rims at 9. So the ramp runs over the open bed and stops where
            the path first meets a container's mouth; the rest is flown level
            at `z_hold`, which is the tray lift and clears the rims by design.
            Going the other way it is the same line read backwards: level until
            the last mouth is behind it, then the ramp, arriving at the paper.

            That makes the ramp as long as it can be — the whole trip bar the
            few millimetres over the cups — rather than ending early at the
            canvas offset, which was this first and is a good deal shorter.

            `ramp=False` is for a caller that cannot promise the brush is
            standing where the trip is written from: the trip that loads the
            brush before a tray's first stroke starts whereever the job was
            parked, and ramping from there climbs out through the water
            crucible's far wall. Such a trip lifts clear and flies level, as
            every trip used to.
            """
            if ramp:
                spans = [s for s in (_box_span(from_x, from_y, to_x, to_y, box)
                                     for box in cup_mouths()) if s is not None]
            else:
                spans = None
            if not spans:
                lift = max(z_hold, z_end)
                self.gcodes.append(GCodeRapidMove(Z=lift))
                self.gcodes.append(GCodeRapidMove(X=_mm(to_x), Y=_mm(to_y)))
                if z_end < lift:
                    self.gcodes.append(GCodeRapidMove(Z=z_end))
                return

            t = min(s[0] for s in spans) if to_cup else max(s[1] for s in spans)
            if not 0.0 < t < 1.0:
                # A mouth under the brush at the moment it sets off, or under
                # the spot it is going to: there is no open bed to ramp over,
                # so lift clear and fly it level, as a trip with no ramp does.
                lift = max(z_hold, z_end)
                self.gcodes.append(GCodeRapidMove(Z=lift))
                self.gcodes.append(GCodeRapidMove(X=_mm(to_x), Y=_mm(to_y)))
                if z_end < lift:
                    self.gcodes.append(GCodeRapidMove(Z=z_end))
                return
            mid_x = from_x + (to_x - from_x) * t
            mid_y = from_y + (to_y - from_y) * t
            if to_cup:
                # Ramp over the open bed, arriving at the tray lift with Z
                # already still, then level in over the mouths.
                ramp_z(from_x, from_y, z_hold, mid_x, mid_y, z_end)
                self.gcodes.append(GCodeLinearMove(X=_mm(to_x), Y=_mm(to_y), Z=z_end))
            else:
                # Level while the mouths are still under it, then ramp home,
                # Z leaving and arriving as gently as it took off.
                self.gcodes.append(GCodeLinearMove(X=_mm(mid_x), Y=_mm(mid_y), Z=z_hold))
                ramp_z(mid_x, mid_y, z_hold, to_x, to_y, z_end)

        def append_go_in_tray(tray_x, tray_y, x, y, num_of_entries=1, remove_drop=True,
                              return_to_canvas=True, water=False, from_canvas=False,
                              ramp=None):
            # No entries is no trip at all, not a trip that dips nothing: the
            # rim wipe and the journey home sit outside the loop, so a count of
            # zero would otherwise wipe a rim the brush is nowhere near and
            # then fly home from a cup it never went to. prepare_paint_count is
            # documented as "0 for plotter", and a plotter wants neither.
            if num_of_entries <= 0:
                return
            set_fast_speed()
            clear = self.move_to_other_shape_lift + self.canvas_height
            # Where the cup is entered and left again: the two ends of a
            # rectangular bay, the middle of a round one both times.
            if self.cup_shape in ("modern", "custom"):
                margin = self.cup_depth * 0.15
                entry_y = tray_y - self.cup_depth / 2 + margin
                exit_y = tray_y + self.cup_depth / 2 - margin
            else:
                entry_y = exit_y = tray_y
            # Kept on the bed, the way the stir across X is. The brush then
            # enters further back along the bay than the deep end and the
            # swipe is shorter by what was clipped, which is less paint worked
            # into the bristles; it is still a dip, and the alternative is a
            # dip that stalls against the stop and throws off every move after
            # it. exit_y too, so a bay whose whole length is off the bed
            # collapses to one point rather than swiping backwards.
            entry_y = max(entry_y, self.y_floor)
            exit_y = max(exit_y, entry_y)
            # Where across the bay each of these dips goes down. A round cup
            # is entered in the middle however often it is visited — that is
            # the point furthest from the wall in every direction — and it
            # mixes its own paint with the chord it sweeps down there.
            if self.cup_shape in ("modern", "custom"):
                lanes = dip_lanes(tray_x,
                                  self.water_cup_width if water else self.cup_width,
                                  self.cup_dip_lanes, self.x_limits)
            else:
                lanes = [tray_x]
            # Carried on from wherever this cup was last left off, so the lanes
            # advance across a whole job rather than restarting at the same
            # place every pickup. Keyed by the cup, to a tenth of a millimetre:
            # a trip is asked for in the coordinates the config gives, and the
            # water cup and a colour are different cups.
            cup = (round(tray_x, 1), round(tray_y, 1))
            lane_at = self._next_lane.get(cup, 0)
            last_x = tray_x
            for i in range(num_of_entries):
                dip_x = lanes[lane_at % len(lanes)]
                lane_at += 1
                last_x = dip_x
                first_coords, second_coords = get_coords_in_tray(tray_x, tray_y)
                if i == 0:
                    # Straight up off the paper first, because the brush is
                    # standing on it, and the rest of the climb is made on the
                    # way. Only then: a trip that is not starting from the
                    # paper has nothing to get off, and dropping to the
                    # clearance to climb back out of it was a dip in the air
                    # at the start of every run and before every wash.
                    if from_canvas:
                        self.gcodes.append(GCodeRapidMove(Z=clear))
                    # Ramping and lifting off the paper are asked for
                    # separately. They coincide for a trip that begins on a
                    # stroke, but the wash at the end of a tray is already
                    # standing at the clearance — the stroke it just finished
                    # lifted it there — so it wants the ramp without a second
                    # lift, which was a hop in the air when they were one flag.
                    travel_with_z(x + self.offset_x, y + self.offset_y,
                                  dip_x, entry_y, clear, self.go_in_tray_lift,
                                  to_cup=True,
                                  ramp=from_canvas if ramp is None else ramp)
                else:
                    # Already over the tray, and already at the tray lift: the
                    # entry before this one ended there. Across to this dip's
                    # lane on the way down the bay, in the air over the rim.
                    self.gcodes.append(GCodeRapidMove(X=_mm(dip_x), Y=_mm(entry_y)))

                if first_coords[1] > 1000 or second_coords[1] > 1000:
                    print("napaka")

                if self.cup_shape in ("modern", "custom"):
                    ###########################################################
                    # A rectangular cup whose floor climbs towards the back.  #
                    # One swipe: enter at the deep end, then draw the brush   #
                    # the length of the bay while Z rises with it, so it      #
                    # leaves the paint by walking up the stairs rather than   #
                    # being lifted out of it.                                 #
                    #                                                         #
                    # It is one interpolated move rather than a tread-by-     #
                    # tread staircase. The bristles flex over the steps, and  #
                    # a stepped path would need the step count and their      #
                    # heights, which the holder's STL does not carry: its     #
                    # bays are open, the floor is not part of that model.     #
                    ###########################################################
                    far = exit_y
                    self.gcodes.append(DIP_MARKER)
                    self.gcodes.append(GCodeRapidMove(Z=self.dip_depth))

                    #######################################################
                    # Straight down and straight up the stairs, and       #
                    # nothing else while the brush is in the paint.       #
                    #                                                     #
                    # There used to be a stir here, a sweep or two across #
                    # the bay at dip depth before the swipe. It mixed the #
                    # cup and it spoiled the load: a sweep picks pigment  #
                    # up on the way out and wipes it off against the      #
                    # paint on the way back, and it does it by dragging   #
                    # the bristles sideways along the floor, which splays #
                    # a brush that is about to be asked for a 1 mm line.  #
                    # The swipe up the stairs decides what leaves the cup #
                    # on the brush, so it is the only thing that should   #
                    # touch the paint.                                    #
                    #                                                     #
                    # The mixing is moving the whole pickup instead: this #
                    # dip is a lane or more across the bay from the last  #
                    # one. See dip_lanes().                               #
                    #######################################################
                    self.gcodes.append(GCodeLinearMove(
                        X=_mm(dip_x), Y=_mm(far), Z=self.cup_swipe_exit_z))
                    self.gcodes.append(GCodeRapidMove(Z=self.go_in_tray_lift))
                else:
                    ###########################################################
                    # Go down and come back up over the middle of the cup.    #
                    # The cups are round, so the centre is the point furthest #
                    # from the wall in every direction; descending or lifting #
                    # out at tray_enter_radius puts the brush against the rim.#
                    # The loading sweep still runs the full chord, but it     #
                    # happens down in the paint where the brush is inside.    #
                    ###########################################################
                    self.gcodes.append(DIP_MARKER)
                    self.gcodes.append(GCodeRapidMove(Z=self.dip_depth))
                    self.gcodes.append(GCodeRapidMove(X=first_coords[0], Y=first_coords[1]))
                    self.gcodes.append(GCodeRapidMove(X=second_coords[0], Y=second_coords[1]))
                    self.gcodes.append(GCodeRapidMove(X=_mm(tray_x), Y=_mm(tray_y)))
                    self.gcodes.append(GCodeRapidMove(Z=self.go_in_tray_lift))

            self._next_lane[cup] = lane_at % len(lanes)

            # The rim wipe is for a round cup, where the brush comes straight
            # up out of the paint carrying a drop. A modern bay has already
            # wiped it: the swipe climbs the stairs with the bristles dragging
            # along the floor, which is the same motion over a better edge, and
            # the two passes over the rim afterwards only put paint back on a
            # brush that has just been drawn clean — and, on 23.6 mm centres,
            # reach into the bay next door to do it.
            if remove_drop and self.cup_shape not in ("modern", "custom"):
                remove_drops(tray_x, tray_y, x, y)

            ########################
            # Return where left of #
            ########################
            # Not when the trip was the end-of-tray wash: there is nothing to
            # go back to, and returning meant crossing to the paper and
            # touching it with a wet brush, which left a water mark in the
            # corner of the artwork at every colour change.
            if return_to_canvas:
                # Out of the containers at the tray lift, then down to the
                # between-shapes clearance as it crosses the canvas, so the
                # brush arrives one short drop above the paper rather than
                # standing still at the far end while Z comes down.
                travel_with_z(last_x, exit_y, x + self.offset_x, y + self.offset_y,
                              self.go_in_tray_lift, clear, to_cup=False)
                self.gcodes.append(GCodeRapidMove(Z=self.canvas_height))
            set_normal_speed()

        def append_go_for_paint(x, y, from_canvas=True, entries=1):
            # from_canvas says the brush is standing at (x, y) on the paper, so
            # the climb to the tray can be made on the way there. The trip that
            # loads the brush before the first stroke is the exception: it is
            # made from wherever the last job left it.
            #
            # One entry re-inks a brush that is already carrying the colour.
            # Loading a clean one takes the mixing routine, which is what
            # `entries` is for.
            append_go_in_tray(color_tray_x, color_tray_y, x, y, entries,
                              from_canvas=from_canvas)

            # self.randomize_paint_per_run()

            self.dist_painted = 0

        def wash_the_brush(x, y, return_to_canvas=True, ramp=None):
            append_go_in_tray(self.water_tray_x, self.water_tray_y, x, y, 3, False,
                              return_to_canvas, water=True, ramp=ramp)

        def prepare_paint(x, y):
            append_go_in_tray(color_tray_x, color_tray_y, x, y, self.prepare_paint_count, True)

        def append_first_intermediate_point(first_point_dist, dist, x1, y1, x2, y2):
            full_delta_x = abs(x1 - x2)
            full_delta_y = abs(y1 - y2)

            quotient = first_point_dist / dist

            first_delta_x = full_delta_x * quotient
            first_delta_y = full_delta_y * quotient

            x_operator = 1
            if x1 > x2:
                x_operator = -1

            y_operator = 1
            if y1 > y2:
                y_operator = -1

            first_point_x = int(x1 + (x_operator * first_delta_x))
            first_point_y = int(y1 + (y_operator * first_delta_y))

            self.gcodes.append(GCodeLinearMove(X=first_point_x + self.offset_x, Y=first_point_y + self.offset_y))

            append_go_for_paint(first_point_x, first_point_y)

            return first_point_x, first_point_y

        def append_intermediate_point(previous_point_x, previous_point_y, x2, y2):
            line_dist = self.paint_per_run

            full_delta_x = abs(previous_point_x - x2)
            full_delta_y = abs(previous_point_y - y2)

            rest_dist = calculate_dist(previous_point_x, previous_point_y, x2, y2)

            quotient = line_dist / rest_dist

            delta_x = full_delta_x * quotient
            delta_y = full_delta_y * quotient

            x_operator = 1
            if previous_point_x > x2:
                x_operator = -1

            y_operator = 1
            if previous_point_y > y2:
                y_operator = -1

            new_point_x = previous_point_x + (int(delta_x) * x_operator)
            new_point_y = previous_point_y + (int(delta_y) * y_operator)

            self.gcodes.append(GCodeLinearMove(X=new_point_x + self.offset_x, Y=new_point_y + self.offset_y))

            append_go_for_paint(new_point_x, new_point_y)

            return new_point_x, new_point_y

        def append_intermediate_points(dist, x1, y1, x2, y2):
            first_point_dist = self.paint_per_run - self.dist_painted

            first_point_x, first_point_y = append_first_intermediate_point(first_point_dist, dist, x1, y1, x2, y2)

            long_strokes_dist = dist - first_point_dist
            num_of_long_strokes = int(long_strokes_dist / self.paint_per_run)
            previous_point_x = first_point_x
            previous_point_y = first_point_y

            for i in range(num_of_long_strokes):
                previous_point_x, previous_point_y = append_intermediate_point(previous_point_x, previous_point_y, x2, y2)

            self.gcodes.append(GCodeLinearMove(X=x2 + self.offset_x, Y=y2 + self.offset_y))

            remaining_dist = calculate_dist(previous_point_x, previous_point_y, x2, y2)
            return remaining_dist

        def calculate_dist(x1, y1, x2, y2):
            return math.hypot(x2 - x1, y2 - y1)

        def append_dist_painted(dist):
            self.dist_painted += dist

        def get_linear_moves(line):
            result = []
            for gcode in line.block.gcodes:
                if isinstance(gcode, GCodeRapidMove):
                    result.append(gcode)
                if isinstance(gcode, GCodeLinearMove):
                    result.append(gcode)
            return result

        def get_coords(line):
            moves = get_linear_moves(line)
            for move in moves:
                if move.X is not None and move.Y is not None:
                    return move, line.block.modal_params
            return None, None

        # The opening sequence: mix the colour, wash, and load the brush. Each
        # trip ends by touching the paper at the origin, so it leaves three
        # dots. Optional because repeating it once per tray inside a job puts
        # those dots in the middle of the artwork.
        if calibrate:
            # Mix the color
            prepare_paint(0, 0)

            # Wash the brush in water before starting to paint
            wash_the_brush(0, 0)

            # Go for paint before starting
            append_go_for_paint(0, 0)

        # One trip to the colour before the first stroke. Re-inking only happens
        # once paint_per_run has been laid down, so without this the opening
        # strokes of a job are painted with whatever the brush was left with
        # last time — which is nothing, if it was washed. Given the point the
        # painting starts at, the trip ends with the brush arriving there
        # loaded, so it leaves no mark of its own.
        #
        # It is the mixing routine rather than the single dip a re-ink makes,
        # because the brush arriving here has just been washed: it is clean and
        # full of water, and one dip charges it weakly, so a tray opened its
        # painting pale and came up to colour somewhere in the first strokes.
        # prepare_paint_count is the same figure the opening sequence mixes
        # with, and it is honoured to the letter — 0 is a plotter, and a
        # plotter has nothing to pick up.
        if pickup_at is not None:
            append_go_for_paint(pickup_at[0], pickup_at[1], from_canvas=False,
                                entries=self.prepare_paint_count)

        self.last_draw_gcode = None
        self.last_draw_params = None
        self.append_paint_dist = False
        self.lines_painted = 0

        self.brush_on_canvas = False
        self.extruding = False
        self.move_to_other_shape = False

        self.brush_above_canvas_gcode = GCodeRapidMove(Z=self.move_to_other_shape_lift + self.canvas_height)

        self.brush_on_canvas_gcode = GCodeRapidMove(Z=self.canvas_height)

        counter = 0

        self.gcodes.append(self.brush_above_canvas_gcode)
        with open(gcode_path) as fh:
            for line_text in fh.readlines():
                fast = _read_plain_move(line_text)
                if fast is not None:
                    text, xy = fast
                    if text is None:
                        continue
                    line = None
                else:
                    try:
                        line = Line(line_text)
                    except AssertionError:
                        continue
                    text = str(line)
                # print("text: ",text)

                if text.strip() == "G1 F600 Z6" or text.strip() == "G01 Z6 F600":  # G01 Z6 F600
                    # print("going up")
                    self.gcodes.append(self.brush_above_canvas_gcode)
                    self.brush_on_canvas = False

                    set_fast_speed()

                if text.strip() == "G01 Z1 F600" or text.strip() == "G1 F600 Z1":  # G1 F600 Z1
                    # print("going down")
                    # self.gcodes.append(self.brush_on_canvas_gcode)
                    self.brush_on_canvas = True
                    self.move_to_other_shape = True

                if text.strip() == "G92 E0" and self.brush_on_canvas:
                    # print("start extrusion")
                    self.extruding = True
                    self.gcodes.append(self.brush_above_canvas_gcode)
                    set_fast_speed()
                    continue

                if line is None:
                    gcode, params = xy, None
                else:
                    gcode, params = get_coords(line)
                if gcode is None:
                    continue

                x = float(gcode.X)
                y = float(gcode.Y)

                if x > 1000 and y > 1000:
                    print("napaka 2, x: ", x, ", y: ", y)

                # print("x: ",x,", y: ",y,", params: ",line.block.modal_params)
                # if len(line.block.modal_params)==1 and get_E_value(params) == 13652.6:
                # print("line ",line)

                if self.brush_on_canvas == True:
                    # if len(line.block.modal_params)==0:
                    #     # print("skip drawing this move")
                    #     continue
                    if self.move_to_other_shape == True:
                        self.move_to_other_shape = False
                        self.last_draw_params = params
                        self.last_draw_gcode = gcode
                        self.gcodes.append(_linear_xy(x + self.offset_x, y + self.offset_y))
                        self.gcodes.append(self.brush_on_canvas_gcode)
                        set_normal_speed()
                        continue
                    # G92 E0

                    if self.extruding == True:
                        self.extruding = False
                        self.last_draw_params = params
                        self.last_draw_gcode = gcode
                        self.gcodes.append(_linear_xy(x + self.offset_x, y + self.offset_y))
                        self.gcodes.append(self.brush_on_canvas_gcode)
                        set_normal_speed()
                        continue

                    dist = 0
                    if self.last_draw_gcode is not None:
                        # print("calculate dist")
                        prev_x = self.last_draw_gcode.X
                        prev_y = self.last_draw_gcode.Y
                        dist = calculate_dist(prev_x, prev_y, x, y)

                    ################################
                    # what if line is longer then than self.paint_per_run
                    ################################
                    if dist > self.paint_per_run:
                        dist = append_intermediate_points(dist, prev_x, prev_y, x, y)
                        self.randomize_paint_per_run()
                    else:
                        self.gcodes.append(_linear_xy(x + self.offset_x, y + self.offset_y))

                    append_dist_painted(dist)

                    if self.dist_painted > self.paint_per_run:
                        # print("go for paint")
                        append_go_for_paint(x, y)
                        self.randomize_paint_per_run()

                    self.last_draw_gcode = gcode
                    self.last_draw_params = params

                if self.brush_on_canvas == False:
                    self.gcodes.append(_linear_xy(x + self.offset_x, y + self.offset_y))
                    # print("continue")
                    continue

                # print("came here")

                counter += 1
                # if counter>5:
                #     break

        # Wash the colour out at the end of the tray, and stop there. The brush
        # used to travel to the canvas origin first, and the wash used to end by
        # touching the paper before parking — two trips across the bed and a
        # water mark on the artwork, for a brush that is about to be dipped in
        # the next colour anyway.
        # No lift written here: the trip to the water starts by making sure of
        # one, and two of them in a row was the second half of a hop in the air.
        #
        # `wash_from` is where the painting actually finished, so the climb to
        # the water is made on the way there like every other trip across the
        # bed, rather than standing still to lift and then flying level. It has
        # to be told: the brush ends wherever the last stroke left it, and this
        # was written from the canvas origin, which is a line the brush is not
        # on. Without it there is nothing to promise the ramp is being drawn
        # from where the brush is standing, so the trip stays flat.
        if wash_from is not None:
            wash_the_brush(wash_from[0], wash_from[1],
                           return_to_canvas=False, ramp=True)
        else:
            wash_the_brush(0, 0, return_to_canvas=False)

        ##############################################
        # Park at the origin, at the very end        #
        ##############################################
        # Only worth doing when nothing follows: between colours the brush is
        # already over the water and the next thing it does is go for paint.
        #
        # X0 Y0 and then Dip Depth + 1, which is where home.g, clean.g and
        # zero.g all leave the brush — a job now ends where the macros do, so
        # there is one parking place to know rather than two. It used to stop
        # over the water container at Z 0, which was a second convention, and
        # on a holder whose water crucible is wide enough to cover the origin
        # it was very nearly this spot anyway.
        if park:
            set_fast_speed()
            self.gcodes.append(GCodeRapidMove(X=0, Y=0))
            self.gcodes.append(GCodeRapidMove(Z=self.dip_depth + 1))
            set_normal_speed()
