#!/usr/bin/env python3
"""
laserscan.py - XY raster scan on a FluidNC machine, measuring distance with a
Waveshare TOF Mini-F (B) on the Pi's UART. Writes a CSV for heatmap plotting.

FluidNC link (the Pi's UART is taken by the sensor):
  USB:   --cnc /dev/ttyUSB0   (or /dev/ttyACM0)
  WiFi:  --cnc socket://192.168.1.50:23   (FluidNC telnet)

Example:
  python3 heightscan.py --cnc /dev/ttyUSB0 --x0 0 --x1 200 --y0 0 --y1 150 --step 5 --home
"""
import argparse, csv, statistics, sys, time
import serial

# ---------------------------------------------------------------- TOF sensor
FRAME_LEN = 16

def read_tof_frame(ser):
    """Sensor sends ASCII lines like ' 103, 100\\n' (distance, quality).
    Returns (distance, 0, quality)."""
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        line = ser.readline().decode("ascii", errors="ignore").strip()
        parts = line.split(",")
        if len(parts) != 2:
            continue
        try:
            return float(parts[0]), 0, float(parts[1])
        except ValueError:
            continue
    raise TimeoutError("no valid TOF line within 1 s")


def measure(ser, n, discard):
    """Median + stdev of n readings, taken only after the machine stopped."""
    ser.reset_input_buffer()            # drop lines buffered during the move
    ser.readline()                      # throw away the (possibly cut) first line
    for _ in range(discard):
        read_tof_frame(ser)
    frames = [read_tof_frame(ser) for _ in range(n)]
    d = [fr[0] for fr in frames]
    s = [fr[2] for fr in frames]
    return (statistics.median(d),
            statistics.stdev(d) if n > 1 else 0.0,
            statistics.median(s))


# ------------------------------------------------------------------ FluidNC
class FluidNC:
    def __init__(self, url, baud=115200, verbose=False):
        self.ser = serial.serial_for_url(url, baudrate=baud, timeout=0.2)
        self.verbose = verbose
        time.sleep(2)                   # opening USB serial may reset the ESP32
        self.ser.write(b"\r\n\r\n")
        time.sleep(1)
        self.ser.reset_input_buffer()

    def _readline(self):
        return self.ser.readline().decode(errors="replace").strip()

    def send(self, line, timeout=30):
        """Send one G-code line and block until 'ok'."""
        if self.verbose:
            print(">>", line)
        self.ser.write((line + "\n").encode())
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            r = self._readline()
            if not r or r.startswith("<"):
                continue
            if self.verbose:
                print("<<", r)
            if r == "ok":
                return
            if r.startswith(("error", "ALARM")):
                raise RuntimeError(f"{line!r} -> {r}")
        raise TimeoutError(f"no 'ok' for {line!r}")

    def status(self):
        self.ser.write(b"?")            # realtime command, no 'ok'
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            r = self._readline()
            if r.startswith("<"):
                return r
        return ""

    def wait_idle(self, timeout=120):
        """G4 P0 syncs the planner; then confirm Idle via status report."""
        self.send("G4 P0", timeout)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            s = self.status()
            if s.startswith("<Idle"):
                return
            if s.startswith("<Alarm"):
                raise RuntimeError(s)
            time.sleep(0.05)
        raise TimeoutError("machine did not become Idle")

    def feed_hold(self):
        self.ser.write(b"!")


# --------------------------------------------------------------------- grid
def axis(a, b, step):
    n = int((b - a) / step + 1e-9)
    return [round(a + i * step, 3) for i in range(n + 1)]


def grid(args):
    xs, ys = axis(args.x0, args.x1, args.step), axis(args.y0, args.y1, args.step)
    for row, y in enumerate(ys):        # serpentine: fewer long travel moves
        for x in (xs if row % 2 == 0 else reversed(xs)):
            yield x, y


def write_preview(args):
    """Path only, for checking in a G-code viewer. Measuring needs the live run."""
    with open(args.gcode_only, "w") as f:
        f.write("G21\nG90\n")
        if args.home:
            f.write("$H\n")
        if args.z is not None:
            f.write(f"G0 Z{args.z:.3f}\n")
        for x, y in grid(args):
            f.write(f"G1 X{x:.3f} Y{y:.3f} F{args.feed}\nG4 P{args.settle:.2f}\n")
    print("wrote", args.gcode_only)


# --------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cnc", default="/dev/ttyUSB0")
    p.add_argument("--tof", default="/dev/serial0")
    p.add_argument("--x0", type=float, required=True)
    p.add_argument("--x1", type=float, required=True)
    p.add_argument("--y0", type=float, required=True)
    p.add_argument("--y1", type=float, required=True)
    p.add_argument("--step", type=float, default=5.0, help="grid spacing mm")
    p.add_argument("--feed", type=float, default=3000, help="mm/min")
    p.add_argument("--z", type=float, help="fixed Z for the scan (omit if no Z)")
    p.add_argument("--home", action="store_true", help="run $H first")
    p.add_argument("--settle", type=float, default=0.3, help="s after stop")
    p.add_argument("--samples", type=int, default=9)
    p.add_argument("--discard", type=int, default=2)
    p.add_argument("--sensor-dx", type=float, default=0.0,
                   help="sensor X offset from machine position, mm")
    p.add_argument("--sensor-dy", type=float, default=0.0)
    p.add_argument("--out", default="heightmap.csv")
    p.add_argument("--gcode-only", metavar="FILE",
                   help="just write the path as G-code and exit")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    if args.gcode_only:
        write_preview(args)
        return

    tof = serial.Serial(args.tof, 115200, timeout=0.2)
    cnc = FluidNC(args.cnc, verbose=args.verbose)
    points = list(grid(args))

    try:
        cnc.send("G21")
        cnc.send("G90")
        if args.home:
            cnc.send("$H", timeout=180)
        if args.z is not None:
            cnc.send(f"G0 Z{args.z:.3f}")
            cnc.wait_idle()

        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["x", "y", "dist_mm", "std_mm", "strength"])
            t0 = time.monotonic()
            for i, (x, y) in enumerate(points, 1):
                cnc.send(f"G1 X{x:.3f} Y{y:.3f} F{args.feed}")
                cnc.wait_idle()
                time.sleep(args.settle)
                d, sd, st = measure(tof, args.samples, args.discard)
                w.writerow([f"{x + args.sensor_dx:.3f}", f"{y + args.sensor_dy:.3f}",
                            f"{d:.1f}", f"{sd:.2f}", f"{st:.0f}"])
                f.flush()
                eta = (time.monotonic() - t0) / i * (len(points) - i)
                print(f"[{i}/{len(points)}] X{x:.1f} Y{y:.1f}  {d:.1f} mm "
                      f"(sd {sd:.1f})  ETA {eta/60:.1f} min")
    except KeyboardInterrupt:
        cnc.feed_hold()
        print("\nfeed hold sent; partial data is in", args.out)
        sys.exit(1)


if __name__ == "__main__":
    main()
