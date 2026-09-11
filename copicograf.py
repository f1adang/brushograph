#!/usr/bin/python3
from pygcode import Line, GCodeLinearMove, GCodeRapidMove
import math
import random


class Copicograf:
    def __init__(self, conf, gcodes=[]):
        self.conf = conf

        self.gcodes = gcodes

        self.water_tray_x = int(self.conf["trays"]["water"]["x"])
        self.water_tray_y = int(self.conf["trays"]["water"]["y"])

        self.canvas_height = int(self.conf["brushograph"]["canvas_height"])
        self.go_in_tray_lift = int(self.conf["brushograph"]["go_in_tray_lift"])
        self.remove_drops_lift = int(self.conf["brushograph"]["remove_drops_lift"])
        self.move_to_other_shape_lift = int(self.conf["brushograph"]["move_to_other_shape_lift"])

        self.tray_enter_radius = int(self.conf["brushograph"]["tray_enter_radius"])
        # How far the brush descends into a cup. Was fixed at -4, which is deeper
        # than a shallow petri dish wants. Absent from a config, that stays the
        # behaviour.
        self.dip_depth = float(self.conf["brushograph"].get("dip_depth", -4))
        self.remove_drops_radius = int(self.conf["brushograph"]["remove_drops_radius"])
        bg = self.conf["brushograph"]
        self.cup_shape = str(bg.get("cup_shape", "classic")).strip().lower()
        self.cup_width = float(bg.get("cup_width", 29.0))
        self.cup_depth = float(bg.get("cup_depth", 30.0))
        self.cup_swipe_exit_z = float(bg.get("cup_swipe_exit_z", 1.0))

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
                     pickup_at=None, park=True):
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
            delta_x = abs(self.tray_enter_radius * math.cos(angle))
            delta_y = abs(self.tray_enter_radius * math.sin(angle))

            first_coords = (0, 0)
            second_coords = (0, 0)

            #########################################################
            # 4 possible ways for brush to enter tray (4 quadrants) #
            #########################################################
            quadrant = random.randrange(4)

            # 1. quadrant
            if quadrant == 0:
                first_coords = (int(tray_x + delta_x), int(tray_y + delta_y))
                second_coords = (int(tray_x - delta_x), int(tray_y - delta_y))

            # 2. quadrant
            if quadrant == 1:
                first_coords = (int(tray_x - delta_x), int(tray_y + delta_y))
                second_coords = (int(tray_x + delta_x), int(tray_y - delta_y))

            # 3. quadrant
            if quadrant == 2:
                first_coords = (int(tray_x - delta_x), int(tray_y - delta_y))
                second_coords = (int(tray_x + delta_x), int(tray_y + delta_y))

            # 4. quadrant
            if quadrant == 3:
                first_coords = (int(tray_x + delta_x), int(tray_y - delta_y))
                second_coords = (int(tray_x - delta_x), int(tray_y + delta_y))

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
                tx, ty = int(t.get("x", 0)), int(t.get("y", 0))
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
                    X=int(round(tray_x + ux * inner * side)),
                    Y=int(round(tray_y + uy * inner * side))))
                self.gcodes.append(GCodeLinearMove(Z=self.remove_drops_lift))
                set_remove_drops_speed()
                self.gcodes.append(GCodeLinearMove(
                    X=int(round(tray_x + ux * outer * side)),
                    Y=int(round(tray_y + uy * outer * side))))
                self.gcodes.append(GCodeRapidMove(Z=self.go_in_tray_lift))
                set_fast_speed()

        def append_go_in_tray(tray_x, tray_y, x, y, num_of_entries=1, remove_drop=True,
                              return_to_canvas=True):
            set_fast_speed()
            for i in range(num_of_entries):
                first_coords, second_coords = get_coords_in_tray(tray_x, tray_y)
                if i == 0:
                    if self.move_to_other_shape_lift + self.canvas_height > self.go_in_tray_lift:
                        self.gcodes.append(GCodeRapidMove(Z=self.move_to_other_shape_lift + self.canvas_height))
                    else:
                        self.gcodes.append(GCodeRapidMove(Z=self.go_in_tray_lift))
                else:
                    self.gcodes.append(GCodeRapidMove(Z=self.go_in_tray_lift))

                if first_coords[1] > 1000 or second_coords[1] > 1000:
                    print("napaka")

                if self.cup_shape == "modern":
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
                    margin = self.cup_depth * 0.15
                    near = tray_y - self.cup_depth / 2 + margin
                    far = tray_y + self.cup_depth / 2 - margin
                    self.gcodes.append(GCodeRapidMove(X=int(tray_x), Y=int(round(near))))
                    self.gcodes.append(GCodeRapidMove(Z=self.dip_depth))
                    self.gcodes.append(GCodeLinearMove(
                        X=int(tray_x), Y=int(round(far)), Z=self.cup_swipe_exit_z))
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
                    self.gcodes.append(GCodeRapidMove(X=int(tray_x), Y=int(tray_y)))
                    self.gcodes.append(GCodeRapidMove(Z=self.dip_depth))
                    self.gcodes.append(GCodeRapidMove(X=first_coords[0], Y=first_coords[1]))
                    self.gcodes.append(GCodeRapidMove(X=second_coords[0], Y=second_coords[1]))
                    self.gcodes.append(GCodeRapidMove(X=int(tray_x), Y=int(tray_y)))
                    self.gcodes.append(GCodeRapidMove(Z=self.go_in_tray_lift))

            if remove_drop == True:
                remove_drops(tray_x, tray_y, x, y)

            ########################
            # Return where left of #
            ########################
            # Not when the trip was the end-of-tray wash: there is nothing to
            # go back to, and returning meant crossing to the paper and
            # touching it with a wet brush, which left a water mark in the
            # corner of the artwork at every colour change.
            if return_to_canvas:
                if self.move_to_other_shape_lift + self.canvas_height > self.go_in_tray_lift:
                    self.gcodes.append(GCodeRapidMove(Z=self.move_to_other_shape_lift + self.canvas_height))
                else:
                    self.gcodes.append(GCodeRapidMove(Z=self.go_in_tray_lift))

                self.gcodes.append(GCodeRapidMove(X=x + self.offset_x, Y=y + self.offset_y))
                self.gcodes.append(GCodeRapidMove(Z=self.canvas_height))
            set_normal_speed()

        def append_go_for_paint(x, y):
            append_go_in_tray(color_tray_x, color_tray_y, x, y)

            # self.randomize_paint_per_run()

            self.dist_painted = 0

        def wash_the_brush(x, y, return_to_canvas=True):
            append_go_in_tray(self.water_tray_x, self.water_tray_y, x, y, 3, False,
                              return_to_canvas)

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
        if pickup_at is not None:
            append_go_for_paint(pickup_at[0], pickup_at[1])

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
                line = None
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
                        self.gcodes.append(GCodeLinearMove(X=float(x + self.offset_x), Y=float(y + self.offset_y)))
                        self.gcodes.append(self.brush_on_canvas_gcode)
                        set_normal_speed()
                        continue
                    # G92 E0

                    if self.extruding == True:
                        self.extruding = False
                        self.last_draw_params = params
                        self.last_draw_gcode = gcode
                        self.gcodes.append(GCodeLinearMove(X=float(x + self.offset_x), Y=float(y + self.offset_y)))
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
                        self.gcodes.append(GCodeLinearMove(X=float(x + self.offset_x), Y=float(y + self.offset_y)))

                    append_dist_painted(dist)

                    if self.dist_painted > self.paint_per_run:
                        # print("go for paint")
                        append_go_for_paint(x, y)
                        self.randomize_paint_per_run()

                    self.last_draw_gcode = gcode
                    self.last_draw_params = params

                if self.brush_on_canvas == False:
                    self.gcodes.append(GCodeLinearMove(X=float(x + self.offset_x), Y=float(y + self.offset_y)))
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
        if self.move_to_other_shape_lift + self.canvas_height > self.go_in_tray_lift:
            self.gcodes.append(GCodeRapidMove(Z=self.move_to_other_shape_lift + self.canvas_height))
        else:
            self.gcodes.append(GCodeRapidMove(Z=self.go_in_tray_lift))

        wash_the_brush(0, 0, return_to_canvas=False)

        ##############################################
        # Park the brush in water, at the very end   #
        ##############################################
        # Only worth doing when nothing follows: between colours the brush is
        # already over the water and the next thing it does is go for paint.
        if park:
            set_fast_speed()
            self.gcodes.append(GCodeRapidMove(X=self.water_tray_x, Y=self.water_tray_y))
            self.gcodes.append(GCodeRapidMove(Z=0))
            set_normal_speed()
