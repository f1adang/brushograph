# Measuring the bed with nothing wired to the machine.
#
# probescan.py has FluidNC's probe input: G38.2 stops the step generator on
# the touch and reports Z at that step. Here the touch reaches only the Pico,
# and the Pico reaches FluidNC over WiFi. Stopping the axis from the Pico
# stops it late, by however long the network takes, and that varies: at
# 200 mm/min every 10 ms of it is 0.03 mm.
#
# So a reading is made in two passes:
#
#   coarse  jog down; on the touch, send jog-cancel (0x85, which stops
#           without an alarm and keeps the position). Where the axis came to
#           rest is below the contact by the network's delay -- sloppy, and
#           used only to know where the bed roughly is.
#   fine    back off, put the pin down again, and step down by `fine_step`
#           at a time, each step sent only once the one before has finished
#           and the sensor has had `settle_ms` to answer. The touch happens
#           during a step, the axis is standing still when its Z is read, and
#           the contact lies within that one step. The network's delay decides
#           how long a step takes, not where the reading is.
#
# "Finished" is FluidNC reporting Idle twice running at one position
# (FluidNC.wait_idle). It was G4 P0 at first, which does not wait on Parang's
# FluidNC: its ok came back with the move's while the axis was still running,
# so the first tests' fine steps were queued, not taken one at a time.
#
# The fine step is rounded to whole motor steps of the machine's Z (read from
# it on connecting): Parang's is 106 steps/mm, and 0.02 mm was two motor steps
# or three by turns.
#
# The fine reading is always made coming down, so play in Z drops out, and it
# carries a constant bias of up to one step, which drops out too: a map is
# read as differences from its own height at the calibration dot.
#
# The CSV is probescan.py's: x, y, z_mm (the fine reading), z_fast_mm (the
# coarse stop), z_spread_mm (how far apart the fine readings were when a
# point is probed more than once). Rows are written in the order probed,
# serpentine, because levelmap.where_probed reads each row's direction off
# that order to undo the play in X.

import asyncio
import os
import time

from fluidnc import JOG_CANCEL, CNCError

NAN = float("nan")

# Errors at this many points in a row end the scan: the same thing is going
# wrong every time.
MAX_ERRORS_IN_A_ROW = 3

# And so do misses, points with no touch within Max depth. One is a hole in
# the bed or a pin that stuck once; several running is the probe no longer
# probing. Pinkograph's 2236-point scan (2026-11-10) touched at 882 points,
# then went 10 mm down and back up without a touch at 185 in a row, 18
# minutes of them, because a miss was only counted.
MAX_MISSES_IN_A_ROW = 3

# When the pin comes down onto the paper, go up this much and try again, up to
# this much in all (see Scanner._deploy_clear).
RAISE_STEP = 0.5
RAISE_LIMIT = 3.0


class Stopped(Exception):
    pass


class ProbeError(Exception):
    pass


def axis(a, b, step):
    """Points from a to b, both ends included, evenly spaced no further apart
    than `step`.

    It was probescan.py's: a, a + step, a + 2 step ... while not past b,
    which stops short of b whenever the step does not divide the span. A scan
    of X 0-152, Y 30-140 at 23 mm ended at X 138, Y 122 and left 14 mm of the
    bed one side and 18 the other unmeasured, read off the map's edge instead.
    Now the span is cut into as many equal gaps as the step needs: 7 of
    21.714 mm along that X, 5 of 22 mm along that Y.

    The map takes uneven figures as they come (levelmap.surface keys its
    columns on the X values as written, the same in every row)."""
    if b <= a:
        return [round(a, 3)]
    n = max(1, -int(-((b - a) / step - 1e-9) // 1))   # ceil, without math
    return [round(a + (b - a) * i / n, 3) for i in range(n + 1)]


HEADER = "x,y,z_mm,z_fast_mm,z_spread_mm"


def point(xs, ys, i):
    """The grid's i-th point, from 0, serpentine as probescan.py: rows along
    X, every other one right to left. Worked out rather than listed: a
    3 mm grid on a Mini is 2236 points, and a list of them is ~100 KB of a
    heap that has WiFi in it too."""
    row, col = divmod(i, len(xs))
    return (xs[col] if row % 2 == 0 else xs[-1 - col]), ys[row]


def plan_resume(path, machine, step):
    """How a scan that ended early would go on: the points in its file are
    checked one by one against the grid set now, which has to be the one it
    was started with, and it goes on after the last point that has a
    reading. The misses after that are measured again: a scan that stops on
    its own stops on a run of them (MAX_MISSES_IN_A_ROW), and they are the
    probe's failing, not the bed's. A nan further back stays: it was a miss
    among touches, or touches that disagreed.

    Read a line at a time, not loaded: 2236 rows of floats would not fit."""
    xs = axis(machine["x0"], machine["x1"], step)
    ys = axis(machine["y0"], machine["y1"], step)
    total = len(xs) * len(ys)
    dx, dy = machine.get("dx", 0.0), machine.get("dy", 0.0)
    rows = done = 0
    ref = None
    with open(path) as f:
        if f.readline().strip() != HEADER:
            raise ValueError("not a probe scan: its first line is not " + HEADER)
        n = 1
        for line in f:
            n += 1
            line = line.strip()
            if not line:
                continue
            v = line.split(",")
            try:
                # The file has where the pin was; the grid is where the
                # machine was sent.
                x, y, z = float(v[0]) - dx, float(v[1]) - dy, float(v[2])
            except (ValueError, IndexError):
                raise ValueError("its line %d is not a point: %s" % (n, line[:40]))
            if rows >= total:
                raise ValueError("it has more points than the grid set now, %d: set the grid "
                                 "the scan was started with" % total)
            gx, gy = point(xs, ys, rows)
            if abs(x - gx) > 0.002 or abs(y - gy) > 0.002:
                raise ValueError("its point %d is X%.3f Y%.3f, where the grid set now (X %g to "
                                 "%g, Y %g to %g, step %g) has X%.3f Y%.3f: set the grid the "
                                 "scan was started with"
                                 % (rows + 1, x, y, machine["x0"], machine["x1"], machine["y0"],
                                    machine["y1"], step, gx, gy))
            rows += 1
            if z == z:
                done = rows
                ref = (x, y, z)
    if ref is None:
        raise ValueError("there is no reading in it to go on from: start the scan again")
    if done >= total:
        raise ValueError("all %d points of the grid are in it already" % total)
    nx, ny = point(xs, ys, done)
    return {"done": done, "total": total, "dropped": rows - done,
            "ref": [ref[0], ref[1]], "ref_z": ref[2], "next": [nx, ny]}


def truncate_scan(path, keep):
    """The file cut back to its first `keep` points. Written whole beside it
    and renamed over it (littlefs replaces the old file in one step), so a
    restart halfway leaves one or the other, not half of each."""
    tmp = "scan.tmp"
    with open(path) as src:
        with open(tmp, "w") as dst:
            dst.write(src.readline())
            n = 0
            while n < keep:
                line = src.readline()
                if not line:
                    break
                if line.strip():
                    dst.write(line if line.endswith("\n") else line + "\n")
                    n += 1
    os.rename(tmp, path)


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def safe_name(s):
    out = "".join(c if c.isalpha() or c.isdigit() or c in "._-" else "-" for c in s)
    return out.strip("-.") or "machine"


class Scanner:
    def __init__(self, cnc, probe, log):
        self.cnc = cnc
        self.probe = probe
        self.log = log
        self.job = None
        self.stop_requested = False
        self.timing = {"coarse_s": None, "fine_s": []}
        self.in_coarse = False

    @property
    def busy(self):
        return bool(self.job and self.job.get("running"))

    def stop(self):
        self.stop_requested = True
        self.cnc.realtime(JOG_CANCEL)

    def _check(self):
        if self.stop_requested:
            raise Stopped()

    async def _z(self):
        st = await self.cnc.query()
        if st.pos is None:
            raise CNCError("the machine reports no position")
        return st.pos[2]

    async def _coarse(self, p):
        """Jog down until the pin is touched. The Z the axis stopped at, or
        None if nothing was touched within max_depth.

        `in_coarse` is up meanwhile, and the display leaves the bus alone: a
        refresh holds the loop for 13 ms, which at 200 mm/min would add
        0.04 mm to how far the stop overshoots."""
        self.in_coarse = True
        try:
            return await self._descend(p)
        finally:
            self.in_coarse = False

    async def _descend(self, p):
        cnc, probe = self.cnc, self.probe
        probe.arm()
        await cnc.send("$J=G91 G21 Z%.3f F%.0f" % (-p["max_depth"], p["coarse_feed"]))
        t0 = time.ticks_ms()
        limit = int(p["max_depth"] / p["coarse_feed"] * 60000) + 5000
        touched = False
        while True:
            cnc.poll()
            if await probe.wait_touch(100):
                cnc.realtime(JOG_CANCEL)
                touched = True
                break
            if self.stop_requested:
                cnc.realtime(JOG_CANCEL)
                await cnc.wait_idle()
                raise Stopped()
            el = time.ticks_diff(time.ticks_ms(), t0)
            state = cnc.status.state
            if state.startswith("Alarm"):
                raise CNCError("the machine went into alarm during the descent")
            if el > 300 and state.startswith("Idle"):
                # The jog ran its full length; make sure it is really over.
                await cnc.wait_idle()
                touched = probe.hit()
                break
            if el > limit:
                cnc.realtime(JOG_CANCEL)
                raise CNCError("the descent did not finish")
        await cnc.wait_idle()
        z = await self._z()
        return z if touched else None

    async def _move(self, line):
        """One move, waited out. Returns where the machine came to rest."""
        await self.cnc.send(line)
        return await self.cnc.wait_idle()

    async def _lift(self, dz):
        """Up by dz, putting the sensor right (reset) while the axis moves."""
        await asyncio.gather(self.probe.reset(), self._move("G91 G0 Z%.3f" % dz))

    def fine_step(self, p):
        """Fine step rounded to whole motor steps of Z, at least one."""
        step = p["fine_step"]
        spm = self.cnc.z_steps_per_mm
        if spm:
            step = max(1, round(step * spm)) / spm
        return step

    async def _deploy_clear(self, reset, setting):
        """Put the pin down, and if it comes down onto the bed, go up and try
        again. Returns how far it had to go up.

        The sensor reports a touch only once its pin has been pushed some way
        back into its body, so after a touch the pin tip is that far less
        above the paper than the axis has risen. On Barbie that push was
        1.1-1.5 mm: Backoff 1.5 failed and 2.0 worked, and Clearance 1.5 put
        the pin down onto the paper at every other point of a scan, the ones
        after a good touch (the point after each failure had been lifted
        Clearance again, and worked). On Parang Backoff 1.5 was enough. So
        rather than make every machine's figures right in advance, the probe
        goes up `RAISE_STEP` at a time, up to `RAISE_LIMIT`, and says so; a
        log full of these is the sign to raise the setting it names."""
        raised = 0.0
        while not await self.probe.deploy(reset=reset):
            if raised >= RAISE_LIMIT:
                raise ProbeError("the pin still reports a touch after going up %.1f mm more "
                                 "than %s: look for something under the pin"
                                 % (raised, setting))
            await self._lift(RAISE_STEP)     # resets the sensor on the way
            raised += RAISE_STEP
            reset = False
        if raised:
            self.log("the pin came down onto the paper; went up %.1f mm more than %s"
                     % (raised, setting))
        return raised

    async def measure(self, p, probes):
        """One point, at the current XY, starting with the pin up above the
        bed. Returns (z, z_coarse, spread, fine readings). z is NaN when
        nothing was touched, or when the fine readings disagree by more than
        `agree`. Leaves the axis where the last touch was."""
        cnc, probe = self.cnc, self.probe
        t0 = time.ticks_ms()
        self.timing = {"coarse_s": None, "fine_s": []}
        await self._deploy_clear(True, "Clearance")
        z_coarse = await self._coarse(p)
        t_fine = time.ticks_ms()
        self.timing["coarse_s"] = time.ticks_diff(t_fine, t0) / 1000
        if z_coarse is None:
            await self._lift(p["max_depth"])
            return NAN, NAN, NAN, []

        fines = []
        ref = z_now = z_coarse
        margin = p["margin"]
        while len(fines) < probes:
            self._check()
            await self._lift(ref + p["backoff"] - z_now)
            raised = await self._deploy_clear(False, "Backoff")
            down = p["backoff"] + raised - margin
            z_now = (await self._move("G91 G1 Z%.3f F%.0f" % (-down, p["coarse_feed"])))[2]
            await asyncio.sleep_ms(p["settle_ms"])
            if probe.hit():
                # Touched before the fine steps began: the coarse stop was
                # more than `margin` below the contact. Start higher, as high
                # as the room the pin came down clear in leaves, before giving up.
                top = p["backoff"] + raised - 0.1
                if margin >= top:
                    raise ProbeError("the coarse stop overshot the contact by more than "
                                     "Backoff: lower Coarse feed, or raise Backoff.")
                self.log("touched less than %.2f mm above the coarse stop; starting the "
                         "fine steps %.2f mm up" % (margin, min(margin * 2, top)))
                margin = min(margin * 2, top)
                continue
            step = self.fine_step(p)
            hit = False
            for _ in range(int((margin + 0.3) / step) + 1):
                z_now = (await self._move("G1 Z%.4f F%.0f" % (-step, p["fine_feed"])))[2]
                await asyncio.sleep_ms(p["settle_ms"])
                if probe.hit():
                    hit = True
                    break
                self._check()
            if not hit:
                raise ProbeError("no touch in the fine steps, %.2f mm below where the "
                                 "coarse pass stopped" % (z_coarse - z_now))
            fines.append(z_now)
            now = time.ticks_ms()
            self.timing["fine_s"].append(time.ticks_diff(now, t_fine) / 1000)
            t_fine = now
            # The contact is now known to within a step: a repeat starts just
            # above it.
            ref = z_now
            margin = max(0.1, 3 * step)

        spread = max(fines) - min(fines) if len(fines) > 1 else 0.0
        z = median(fines)
        if len(fines) > 1 and spread > p["agree"]:
            z = NAN
        return z, z_coarse, spread, fines

    def _begin(self, kind, **extra):
        self.stop_requested = False
        self.job = {"kind": kind, "running": True, "started": time.ticks_ms(),
                    "error": None, "stopped": False}
        self.job.update(extra)

    async def _finish(self, p, lift):
        try:
            if lift:
                await self._lift(p["clearance"])
            await self.cnc.send("G90")
        except Exception as e:
            self.log("could not lift at the end: %s" % e)

    async def run_test(self, p, n):
        """Probe the current spot n times: how repeatable the sensor is."""
        self._begin("test", n=n, result=None)
        lifted = False
        try:
            await self.cnc.send("G21")
            # The WiFi's round trip, Pico to FluidNC and back: what the
            # coarse stop's overshoot is made of, besides the axis braking.
            rtts = []
            for _ in range(10):
                t = time.ticks_us()
                await self.cnc.query()
                rtts.append(time.ticks_diff(time.ticks_us(), t) / 1000)
            rtt = median(rtts)
            _z, zc, spread, fines = await self.measure(p, n)
            if not fines:
                # measure() has already gone back up to where it started.
                lifted = True
                raise ProbeError("nothing touched within %.1f mm (Max depth): start lower, "
                                 "or raise Max depth" % p["max_depth"])
            await self._lift(p["clearance"])
            lifted = True
            mean = sum(fines) / len(fines)
            sd = (sum((f - mean) ** 2 for f in fines) / len(fines)) ** 0.5
            tm = self.timing
            self.job["result"] = {"coarse": zc, "fines": fines, "spread": spread,
                                  "sd": sd, "overshoot": fines[0] - zc, "rtt_ms": rtt,
                                  "rtt_max_ms": max(rtts), "coarse_s": tm["coarse_s"],
                                  "fine_s": tm["fine_s"], "step": self.fine_step(p),
                                  "settle_ms": p["settle_ms"]}
            self.log("test: %d touches, spread %.3f mm, sd %.3f mm, coarse stop %.3f mm "
                     "below the first; fine step %.4f mm, settle %d ms; WiFi round trip "
                     "%.0f ms (max %.0f); coarse pass %.1f s, fine passes %s s"
                     % (len(fines), spread, sd, fines[0] - zc, self.fine_step(p),
                        p["settle_ms"], rtt, max(rtts), tm["coarse_s"],
                        " ".join("%.1f" % s for s in tm["fine_s"])))
        except Stopped:
            self.job["stopped"] = True
            self.log("test stopped")
        except Exception as e:
            self.job["error"] = str(e)
            self.log("test failed: %s" % e)
        finally:
            await self._finish(p, not lifted)
            self.job["running"] = False

    async def _rejoin(self, p, plan):
        """Touch the last point the file has a reading for, before going on.
        If Z reads otherwise there by more than two fine steps -- the machine
        zeroed again where it stood after a restart, say, which FluidNC does
        at power-on -- the readings from here on are shifted by the
        difference, so the two halves make one map. Returns the shift."""
        x, y = plan["ref"]
        await self._move("G90 G0 X%.3f Y%.3f" % (x, y))
        z, _zc, _spread, fines = await self.measure(p, p["probes"])
        if not fines:
            raise ProbeError("nothing touched within %.1f mm (Max depth) at X%.3f Y%.3f, the "
                             "last point measured: put the probe a few mm above it"
                             % (p["max_depth"], x, y))
        await self._lift(p["clearance"])
        if z != z:
            raise ProbeError("the touches at X%.3f Y%.3f, the last point measured, disagree "
                             "by more than Agree" % (x, y))
        diff = z - plan["ref_z"]
        if abs(diff) <= 2 * self.fine_step(p):
            self.log("X%.3f Y%.3f reads %.3f, and read %.3f: Z is where it was"
                     % (x, y, z, plan["ref_z"]))
            return 0.0
        self.log("X%.3f Y%.3f reads %.3f, and read %.3f: Z has moved by %+.3f mm since "
                 "(zeroed again, or the paper moved), so the readings from here on are "
                 "shifted by that to match" % (x, y, z, plan["ref_z"], diff))
        return diff

    async def run_scan(self, machine, p, stamp=None, resume=None):
        """A scan over the machine's grid, or with `resume` (plan_resume's
        plan, with the file's name) the rest of one that ended early, written
        on to the end of its file."""
        xs = axis(machine["x0"], machine["x1"], p["step"])
        ys = axis(machine["y0"], machine["y1"], p["step"])
        total = len(xs) * len(ys)
        if resume:
            name, start = resume["name"], resume["done"]
        else:
            name = "picoprobe-%s-%s.csv" % (safe_name(machine.get("host") or machine["name"]),
                                            stamp)
            start = 0
        self._begin("scan", i=start, n=total, file=name, last=None,
                    misses=0, unsure=0, errors=0, start=start)
        job = self.job
        dx, dy = machine.get("dx", 0.0), machine.get("dy", 0.0)
        f = None
        in_row = 0
        missed_in_row = 0
        shift = 0.0
        try:
            await self.cnc.send("G21", "G90")
            path = "scans/" + name
            if resume:
                truncate_scan(path, start)
                self.log("continuing %s at point %d of %d%s"
                         % (name, start + 1, total,
                            "; the %d unmeasured at its end go again" % resume["dropped"]
                            if resume["dropped"] else ""))
                shift = await self._rejoin(p, resume)
                f = open(path, "a")
            else:
                f = open(path, "w")
                f.write(HEADER + "\n")
                self.log("scan: %d points -> %s" % (total, name))
            for i in range(start + 1, total + 1):
                x, y = point(xs, ys, i - 1)
                self._check()
                await self._move("G90 G0 X%.3f Y%.3f" % (x, y))
                failed = False
                try:
                    z, zc, spread, fines = await self.measure(p, p["probes"])
                    in_row = 0
                except ProbeError as e:
                    job["errors"] += 1
                    in_row += 1
                    self.log("X%.1f Y%.1f: %s" % (x, y, e))
                    if in_row >= MAX_ERRORS_IN_A_ROW:
                        raise
                    z = zc = spread = NAN
                    fines = []
                    failed = True
                if fines or failed:
                    # A miss has already gone back up to where it started.
                    await self._lift(p["clearance"])
                z -= shift
                zc -= shift
                if not fines and not failed:
                    job["misses"] += 1
                    missed_in_row += 1
                else:
                    missed_in_row = 0
                    if z != z and not failed:
                        job["unsure"] += 1
                f.write("%.3f,%.3f,%.3f,%.3f,%.3f\n" % (x + dx, y + dy, z, zc, spread))
                f.flush()
                job["i"] = i
                job["last"] = [x, y, z, zc]
                if missed_in_row >= MAX_MISSES_IN_A_ROW:
                    raise ProbeError("nothing touched within %.1f mm (Max depth) at %d points "
                                     "in a row: is the pin coming down, the sensor's light "
                                     "steady, and Z moving?" % (p["max_depth"], missed_in_row))
                el = time.ticks_diff(time.ticks_ms(), job["started"]) / 1000
                job["eta"] = el / (i - start) * (total - i)
            self.log("scan done: %d points, %d without a touch, %d left as nan, %d errors"
                     % (total, job["misses"], job["unsure"], job["errors"]))
        except Stopped:
            job["stopped"] = True
            self.log("scan stopped after %d points; they are in %s" % (job["i"], name))
        except Exception as e:
            job["error"] = str(e)
            self.log("scan failed at point %d: %s" % (job["i"] + 1, e))
        finally:
            if f:
                f.close()
            await self._finish(p, job["error"] is not None or job["stopped"])
            job["running"] = False
