#!/usr/bin/env python3
"""
probescan.py - Z heightmap with a touch probe on FluidNC (G38.2).

Before starting: jog the probe a few mm above the surface over the first
grid point. No homing or Z zero needed - all Z moves are relative.

Example:
  python3 probescan.py --cnc socket://parang.local:23 \
      --x0 0 --x1 150 --y0 30 --y1 130 --step 5
"""
import argparse, csv, math, re, sys, time
import serial

PRB_RE = re.compile(r"\[PRB:([^:\]]+):(\d)\]")


class Alarm(RuntimeError):
    def __init__(self, line, code):
        super().__init__(f"{line!r} -> ALARM:{code}")
        self.code = code


class FluidNC:
    def __init__(self, url, baud=115200, verbose=False):
        self.ser = serial.serial_for_url(url, baudrate=baud, timeout=0.2)
        self.verbose = verbose
        time.sleep(2)
        self.ser.write(b"\r\n\r\n")
        time.sleep(1)
        self.ser.reset_input_buffer()

    def _readline(self):
        return self.ser.readline().decode(errors="replace").strip()

    def send(self, line, timeout=60):
        """Send one line, block until 'ok'. Returns the other lines received."""
        if self.verbose:
            print(">>", line)
        self.ser.write((line + "\n").encode())
        got = []
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            r = self._readline()
            if not r or r.startswith("<"):
                continue
            if self.verbose:
                print("<<", r)
            if r == "ok":
                return got
            if r.startswith("error"):
                raise RuntimeError(f"{line!r} -> {r}")
            if r.startswith("ALARM:"):
                code = r[6:]
                raise Alarm(line, int(code) if code.isdigit() else -1)
            got.append(r)
        raise TimeoutError(f"no 'ok' for {line!r}")

    def probe(self, dist, feed, timeout=120):
        """Relative G38.2 downwards by dist mm. Returns machine Z of contact."""
        cmd = f"G91 G38.2 Z{-dist:.3f} F{feed:.0f}"
        lines = self.send(cmd, timeout)
        end = time.monotonic() + 2.0
        while True:
            for l in lines:
                m = PRB_RE.search(l)
                if m:
                    if m.group(2) != "1":
                        raise Alarm(cmd, 5)
                    return float(m.group(1).split(",")[2])
            if time.monotonic() > end:
                raise TimeoutError("no [PRB:...] report after probing")
            r = self._readline()
            lines = [r] if r else []

    def unlock(self):
        time.sleep(0.5)
        self.ser.reset_input_buffer()
        self.send("$X")

    def wait_idle(self, timeout=120):
        self.send("G4 P0", timeout)

    def feed_hold(self):
        self.ser.write(b"!")


def axis(a, b, step):
    n = int((b - a) / step + 1e-9)
    return [round(a + i * step, 3) for i in range(n + 1)]


def grid(args):
    xs, ys = axis(args.x0, args.x1, args.step), axis(args.y0, args.y1, args.step)
    for row, y in enumerate(ys):        # serpentine
        for x in (xs if row % 2 == 0 else reversed(xs)):
            yield x, y


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cnc", default="socket://parang.local:23")
    p.add_argument("--x0", type=float, required=True)
    p.add_argument("--x1", type=float, required=True)
    p.add_argument("--y0", type=float, required=True)
    p.add_argument("--y1", type=float, required=True)
    p.add_argument("--step", type=float, default=5.0, help="grid spacing mm")
    p.add_argument("--clearance", type=float, default=3.0,
                   help="lift above last contact before moving XY, mm")
    p.add_argument("--max-depth", type=float, default=10.0,
                   help="max probing travel per point, mm")
    p.add_argument("--backoff", type=float, default=1.5,
                   help="retract between fast and slow probe, mm (must release switch)")
    p.add_argument("--fast-feed", type=float, default=300, help="mm/min")
    p.add_argument("--slow-feed", type=float, default=50, help="mm/min")
    p.add_argument("--probe-dx", type=float, default=0.0,
                   help="probe X offset from machine position, mm")
    p.add_argument("--probe-dy", type=float, default=0.0)
    p.add_argument("--out", default="probemap.csv")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    cnc = FluidNC(args.cnc, verbose=args.verbose)
    points = list(grid(args))
    misses = 0

    try:
        cnc.send("G21")
        cnc.send("G90")
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["x", "y", "z_mm", "z_fast_mm"])
            t0 = time.monotonic()
            for i, (x, y) in enumerate(points, 1):
                cnc.send(f"G90 G0 X{x:.3f} Y{y:.3f}")
                stage = "fast"
                try:
                    z_fast = cnc.probe(args.max_depth, args.fast_feed)
                    cnc.send(f"G91 G0 Z{args.backoff:.3f}")
                    stage = "slow"
                    z = cnc.probe(args.backoff + 1.0, args.slow_feed)
                    cnc.send(f"G91 G0 Z{args.clearance:.3f}")
                except Alarm as e:
                    if e.code == 4:
                        cnc.unlock()
                        sys.exit("ALARM:4 - probe already triggered before probing. "
                                 "Raise Z, or increase --backoff if this happened "
                                 "on the slow probe.")
                    if e.code != 5:
                        raise
                    # no contact within travel: unlock, return to hover height
                    cnc.unlock()
                    lift = args.max_depth if stage == "fast" else args.clearance + 1.0
                    cnc.send(f"G91 G0 Z{lift:.3f}")
                    z = z_fast = math.nan
                    misses += 1

                w.writerow([f"{x + args.probe_dx:.3f}", f"{y + args.probe_dy:.3f}",
                            f"{z:.3f}", f"{z_fast:.3f}"])
                f.flush()
                eta = (time.monotonic() - t0) / i * (len(points) - i)
                print(f"[{i}/{len(points)}] X{x:.1f} Y{y:.1f}  Z {z:.3f}"
                      f"  ETA {eta/60:.1f} min")

        cnc.send("G90")
        cnc.wait_idle()
        print(f"done, {misses} points without contact -> {args.out}")
    except KeyboardInterrupt:
        cnc.feed_hold()
        print("\nfeed hold sent; partial data is in", args.out)
        sys.exit(1)


if __name__ == "__main__":
    main()
