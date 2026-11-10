# Probe Pico: a 3D Touch on a Raspberry Pi Pico 2 W that maps a brushograph's
# bed over WiFi, with nothing wired to the machine. See README.md.
#
# Joins the WiFi in config.json and serves its page at http://probepico.local/.
# With no WiFi set, or one it cannot join, it opens its own network,
# `probepico-setup` (password `brushograph`), at http://192.168.4.1/, where the
# WiFi can be set.

import asyncio
import json
import os
import time

import machine
import network

from display import Display
from fluidnc import JOG_CANCEL, FluidNC
from probe import COMMANDS, Probe
from scan import HEADER, Scanner, plan_resume, safe_name

VERSION = "1.7"
# The h4xx0r theme's faces, copied from webui/static/ (see README.md).
FONTS = ("VT323.ttf", "Silkscreen.ttf", "PressStart2P.ttf")
CONFIG = "config.json"
AP_SSID = "probepico-setup"
AP_KEY = "brushograph"

SCAN_DEFAULTS = {
    "step": 6.0,          # grid spacing, mm
    "clearance": 3.0,     # lift above the last touch before moving XY, mm
    "max_depth": 10.0,    # furthest the coarse pass goes down, mm
    "coarse_feed": 200.0, # mm/min
    # The coarse stop overshot the contact by 0.44 and 0.46 mm on Parang at
    # 200 mm/min (two tests, 2026-11-09). Margin has to clear that with room
    # to spare, and Backoff has to clear Margin, so the pin comes down clear.
    # Backoff also has to clear how far the pin is pushed in before the sensor
    # reports a touch: on Barbie 1.5 failed and 2.0 worked, and the coarse stop
    # overshoots by up to 0.66 mm besides, so 2.5. Too little is not fatal any
    # more (Scanner._deploy_clear), just slower.
    #
    # Margin is not "clear every overshoot". Every millimetre of it is fine
    # steps at every point, ~0.1-0.15 s each at 0.028 mm, while an overshoot
    # past it costs one retry, ~2 s, at that point only. Over four scans
    # (1867 points, three machines) the overshoot was 0.435 mm median, past
    # 0.6 at 4.2 % of points, past 0.75 at 1.0 %, never past 0.973. Per
    # point that is ~0.7-1.0 s of fine pass at 0.6, ~1.1-1.7 s at 0.75 and
    # ~2.0-3.0 s at 1.0: the retries are the cheap side.
    "backoff": 2.5,       # up from the coarse stop to put the pin down again, mm
    "margin": 0.6,        # fine steps start this far above the coarse stop, mm
    "fine_step": 0.02,    # mm
    "fine_feed": 60.0,    # mm/min
    # After each fine step has come to rest, wait this long before looking
    # at the pin: the sensor's own delay from being pushed to answering. Not
    # measured yet; the coarse stop's overshoot leaves ~100 ms unaccounted for.
    "settle_ms": 50,
    "probes": 1,          # fine readings per point
    "agree": 0.1,         # fine readings further apart than this make the point nan, mm
}
# A Mini: the grid starts at the calibration dot (X 5, Canvas Start Y + 5),
# which is where the map is read as nought (README, "Where nought is").
MACHINE_DEFAULTS = {"name": "", "host": "", "port": 23, "dx": 0.0, "dy": 0.0,
                    "x0": 5.0, "x1": 149.0, "y0": 30.0, "y1": 174.0}

LOG = []

# The log is kept on flash as well as in memory, so a restart -- a dip in the
# supply when the solenoid pulls, say -- does not take with it the lines that
# would say what happened. At start-up the last run's file becomes PREV_FILE
# and the page shows its tail.
LOG_FILE = "log.txt"
PREV_FILE = "log.prev.txt"
LOG_FILE_LINES = 2000
_logged = 0


def _rotate_log():
    try:
        os.rename(LOG_FILE, PREV_FILE)
    except OSError:
        pass


def _read_prev(n=25):
    try:
        with open(PREV_FILE) as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    return lines[-n:]


_rotate_log()
PREV = _read_prev()


def log(msg):
    global _logged
    t = time.localtime()
    line = "%02d:%02d:%02d %s" % (t[3], t[4], t[5], msg)
    print(line)
    LOG.append(line)
    if len(LOG) > 80:
        del LOG[0]
    try:
        _logged += 1
        if _logged > LOG_FILE_LINES:
            _rotate_log()
            _logged = 1
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def reset_cause():
    c = machine.reset_cause()
    return {machine.PWRON_RESET: "power-on (power was lost or the board unplugged)",
            machine.WDT_RESET: "a software restart"}.get(c, "cause %d" % c)


def load_config():
    try:
        with open(CONFIG) as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    cfg.setdefault("hostname", "probepico")
    cfg.setdefault("wifi", {"ssid": "", "password": ""})
    cfg.setdefault("machines", [])
    scan = cfg.setdefault("scan", {})
    for k, v in SCAN_DEFAULTS.items():
        scan.setdefault(k, v)
    for m in cfg["machines"]:
        for k, v in MACHINE_DEFAULTS.items():
            m.setdefault(k, v)
    return cfg


def save_config(cfg):
    with open(CONFIG + ".new", "w") as f:
        json.dump(cfg, f)
    os.rename(CONFIG + ".new", CONFIG)


cfg = load_config()
probe = Probe()
cnc = FluidNC(log)
scanner = Scanner(cnc, probe, log)
wifi = {"mode": "off", "ssid": "", "ip": ""}
led = machine.Pin("LED", machine.Pin.OUT)
oled = Display()


# ------------------------------------------------------------------ WiFi
async def wifi_up():
    network.hostname(cfg["hostname"])
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    # Power saving holds packets for the radio's sleep interval: tens of ms on
    # every reply, and the coarse pass's stop is late by all of it.
    sta.config(pm=network.WLAN.PM_NONE)
    ssid = cfg["wifi"].get("ssid")
    if ssid:
        log("joining %s" % ssid)
        sta.connect(ssid, cfg["wifi"].get("password", ""))
        for _ in range(40):
            if sta.isconnected():
                break
            await asyncio.sleep_ms(500)
    if sta.isconnected():
        wifi.update(mode="station", ssid=ssid, ip=sta.ifconfig()[0])
        log("on %s as %s, signal %d dBm, http://%s.local/"
            % (ssid, wifi["ip"], sta.status("rssi"), cfg["hostname"]))
        led.on()
        asyncio.create_task(wifi_watch(sta, ssid))
        return
    sta.active(False)
    ap = network.WLAN(network.AP_IF)
    ap.config(ssid=AP_SSID, key=AP_KEY)
    ap.active(True)
    while not ap.active():
        await asyncio.sleep_ms(100)
    wifi.update(mode="setup", ssid=AP_SSID, ip=ap.ifconfig()[0])
    log("no WiFi%s: join %s (password %s) and open http://%s/"
        % (" (could not join %s)" % ssid if ssid else " set", AP_SSID, AP_KEY, wifi["ip"]))
    while True:
        led.toggle()
        await asyncio.sleep_ms(700)


async def wifi_watch(sta, ssid):
    """Join again if the WiFi drops. Without this a dropped connection was
    for good: the Pico stayed off the network until it was restarted."""
    while True:
        await asyncio.sleep(5)
        if sta.isconnected():
            continue
        led.off()
        log("WiFi lost (status %d); joining %s again" % (sta.status(), ssid))
        sta.disconnect()
        sta.connect(ssid, cfg["wifi"].get("password", ""))
        for _ in range(40):
            if sta.isconnected():
                break
            await asyncio.sleep_ms(500)
        if sta.isconnected():
            wifi["ip"] = sta.ifconfig()[0]
            log("back on %s as %s, signal %d dBm" % (ssid, wifi["ip"], sta.status("rssi")))
            led.on()


# ------------------------------------------------------------------ HTTP
REASONS = {200: "OK", 400: "Bad Request", 404: "Not Found", 409: "Conflict",
           500: "Internal Server Error"}


def no_nan(o):
    """NaN as None, all the way down. MicroPython's json writes a NaN as a bare
    `nan`, which is not JSON: once a point had failed, the job's `last` was
    [x, y, nan, nan], every /api/state was unreadable, and the page sat at
    "Lost the Pico" until a good point replaced it."""
    if isinstance(o, float):
        return None if o != o else o
    if isinstance(o, dict):
        return {k: no_nan(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [no_nan(v) for v in o]
    return o


async def respond(w, code, body=b"", ctype="application/json", extra=""):
    if not isinstance(body, (bytes, bytearray)):
        body = (body if isinstance(body, str) else json.dumps(no_nan(body))).encode()
    head = ("HTTP/1.0 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
            "Cache-Control: no-store\r\n%s\r\n" % (code, REASONS.get(code, ""), ctype,
                                                   len(body), extra))
    w.write(head.encode())
    w.write(body)
    await w.drain()


async def send_file(w, path, ctype, extra="", cache="no-store"):
    size = os.stat(path)[6]
    w.write(("HTTP/1.0 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
             "Cache-Control: %s\r\n%s\r\n" % (ctype, size, cache, extra)).encode())
    buf = bytearray(1024)
    with open(path, "rb") as f:
        while True:
            n = f.readinto(buf)
            if not n:
                break
            w.write(buf[:n])
            await w.drain()


def scans():
    out = []
    for name in os.listdir("scans"):
        st = os.stat("scans/" + name)
        out.append({"name": name, "size": st[6], "mtime": st[8]})
    out.sort(key=lambda s: s["mtime"], reverse=True)
    return out


def state():
    st = cnc.status
    return {
        "version": VERSION,
        "wifi": wifi,
        "cnc": {"connected": cnc.connected, "host": cnc.host, "ip": cnc.ip,
                "state": st.state if cnc.connected else "disconnected",
                "pos": st.pos, "frame": st.frame, "alarm": cnc.alarm,
                "z_steps_per_mm": cnc.z_steps_per_mm},
        "probe": {"level": probe.level(), "deployed": probe.deployed},
        "job": scanner.job,
        "log": LOG[-40:],
        "previous": PREV,
        "uptime_s": time.ticks_ms() // 1000,
        # The Pico has no clock of its own across a restart; the page sets it,
        # and does again whenever this is false. Scan files are named by it.
        "clock_set": time.localtime()[0] >= 2025,
        "scans": scans(),
        "config": {"hostname": cfg["hostname"], "wifi": {"ssid": cfg["wifi"].get("ssid", "")},
                   "machines": cfg["machines"], "scan": cfg["scan"],
                   "current": cfg.get("current")},
    }


def num(v, kind=float):
    return kind(float(v))


def merged_scan(params):
    p = dict(cfg["scan"])
    for k in SCAN_DEFAULTS:
        if k in params:
            p[k] = num(params[k], int if k in ("probes", "settle_ms") else float)
    if p["step"] <= 0 or p["fine_step"] <= 0 or p["probes"] < 1:
        raise ValueError("step, fine step and probes must be above 0")
    if p["margin"] >= p["backoff"]:
        raise ValueError("Margin must be smaller than Backoff")
    return p


def upload_name(name):
    """A file's name from the browser, fit for scans/: the browser's " (1)"
    for a second download taken off, and nothing that is not a letter,
    digit, dot, dash or underscore."""
    name = str(name).rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not name.lower().endswith(".csv"):
        raise ValueError("%s is not a .csv file" % name)
    stem = name[:-4]
    if stem.endswith(")") and " (" in stem:
        stem = stem[:stem.rindex(" (")]
    return safe_name(stem) + ".csv"


def same_file(path, text):
    """Whether the file holds exactly `text`, read a piece at a time."""
    i = 0
    with open(path) as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                return i == len(text)
            if text[i:i + len(chunk)] != chunk:
                return False
            i += len(chunk)


def stamp():
    t = time.localtime()
    return "%04d%02d%02d-%02d%02d%02d" % t[:6]


class Busy(Exception):
    pass


def idle_needed():
    if scanner.busy:
        raise Busy("a %s is running" % scanner.job["kind"])


async def api(method, path, data):
    """(code, body) for an /api/ call."""
    if path == "/api/state":
        if cnc.connected:
            cnc.poll()
        return 200, state()
    if method != "POST":
        return 404, {"error": "not found"}

    if path == "/api/clock":
        y, mo, d, h, mi, s = (int(v) for v in data["t"])
        machine.RTC().datetime((y, mo, d, 0, h, mi, s, 0))
        return 200, {"ok": True}

    if path == "/api/settings":
        if "machines" in data:
            ms = []
            for m in data["machines"]:
                out = dict(MACHINE_DEFAULTS)
                out["name"] = str(m.get("name", "")).strip()
                out["host"] = str(m.get("host", "")).strip()
                for k in ("port",):
                    out[k] = num(m.get(k, 23), int)
                for k in ("dx", "dy", "x0", "x1", "y0", "y1"):
                    out[k] = num(m.get(k, MACHINE_DEFAULTS[k]))
                if out["host"]:
                    ms.append(out)
            cfg["machines"] = ms
        if "scan" in data:
            cfg["scan"] = merged_scan(data["scan"])
        if "wifi" in data:
            w = data["wifi"]
            cfg["wifi"]["ssid"] = str(w.get("ssid", "")).strip()
            if w.get("password"):
                cfg["wifi"]["password"] = w["password"]
        save_config(cfg)
        log("settings saved")
        return 200, state()

    if path == "/api/restart":
        asyncio.create_task(_restart())
        return 200, {"ok": True}

    if path == "/api/stop":
        if scanner.busy:
            scanner.stop()
            log("stop requested")
        else:
            cnc.realtime(JOG_CANCEL)
        return 200, {"ok": True}

    idle_needed()

    if path == "/api/connect":
        m = cfg["machines"][int(data["machine"])]
        cfg["current"] = int(data["machine"])
        save_config(cfg)
        await cnc.connect(m["host"], m.get("port", 23))
        return 200, state()

    if path == "/api/disconnect":
        await cnc.disconnect()
        log("disconnected")
        return 200, state()

    if path == "/api/probe":
        us = COMMANDS[data["cmd"]]
        await probe.command(us)
        probe.arm()
        return 200, state()

    if path == "/api/unlock":
        await cnc.send("$X")
        cnc.alarm = None
        return 200, state()

    if path == "/api/jog":
        axis = data["axis"].upper()
        if axis not in "XYZ" or len(axis) != 1:
            raise ValueError("axis must be X, Y or Z")
        dist = max(-50.0, min(50.0, num(data["dist"])))
        feed = 300 if axis == "Z" else 2000
        await cnc.send("$J=G91 G21 %s%.3f F%d" % (axis, dist, feed))
        return 200, state()

    if path == "/api/test":
        p = merged_scan(data.get("scan", {}))
        n = max(1, min(20, num(data.get("n", 5), int)))
        asyncio.create_task(scanner.run_test(p, n))
        return 200, state()

    if path == "/api/scan":
        if not cnc.connected:
            raise ValueError("connect to a machine first")
        p = merged_scan(data.get("scan", {}))
        m = cfg["machines"][int(data["machine"])]
        asyncio.create_task(scanner.run_scan(m, p, stamp()))
        return 200, state()

    if path == "/api/goto":
        # Above a point at the height it stands, as a scan's first move is:
        # to put the probe over where a continued scan starts.
        if not cnc.connected:
            raise ValueError("connect to a machine first")
        await cnc.send("G21", "G90", "G0 X%.3f Y%.3f" % (num(data["x"]), num(data["y"])))
        return 200, state()

    if path == "/api/upload":
        name = upload_name(data["name"])
        # A 3 mm scan of a Mini is ~80 KB, held here as the request and as
        # this string already: no more copies of it than need be.
        text = data.pop("csv")
        if "\r" in text:
            text = text.replace("\r\n", "\n")
        if not text.startswith(HEADER):
            raise ValueError("%s is not a probe scan: its first line is not %s" % (name, HEADER))
        if name in os.listdir("scans"):
            if not same_file("scans/" + name, text):
                raise ValueError("a different %s is on the Pico already: continue that one "
                                 "from the list, or delete it first" % name)
        else:
            with open("scans/" + name, "w") as f:
                f.write(text)
            log("loaded %s from the browser" % name)
        out = state()
        out["loaded"] = name
        return 200, out

    if path == "/api/resume":
        name = data["name"]
        if "/" in name or name not in os.listdir("scans"):
            raise ValueError("no scan called %s on the Pico" % name)
        i = int(data["machine"])
        m = dict(cfg["machines"][i])
        for k in ("x0", "x1", "y0", "y1"):
            if k in data.get("grid", {}):
                m[k] = num(data["grid"][k])
        host = m.get("host") or m["name"]
        if not name.startswith("picoprobe-%s-" % safe_name(host)):
            raise ValueError("%s is not a scan of %s" % (name, host))
        p = merged_scan(data.get("scan", {}))
        plan = plan_resume("scans/" + name, m, p["step"])
        plan["name"] = name
        if not data.get("go"):
            return 200, {"plan": plan}
        if not cnc.connected or cnc.host != m["host"]:
            raise ValueError("connect to %s first" % host)
        asyncio.create_task(scanner.run_scan(m, p, resume=plan))
        return 200, state()

    if path == "/api/delete":
        name = data["name"]
        if "/" in name or name.startswith("."):
            raise ValueError("bad name")
        os.remove("scans/" + name)
        log("deleted %s" % name)
        return 200, state()

    return 404, {"error": "not found"}


async def _restart():
    await asyncio.sleep_ms(500)
    machine.reset()


async def handle(r, w):
    try:
        line = await r.readline()
        if not line:
            return
        method, path, _ = line.decode().split(" ", 2)
        length = 0
        while True:
            h = await r.readline()
            if h in (b"\r\n", b"\n", b""):
                break
            k, _, v = h.decode().partition(":")
            if k.strip().lower() == "content-length":
                length = int(v.strip())
        body = await r.readexactly(length) if length else b""
        path = path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            await send_file(w, "index.html", "text/html; charset=utf-8")
        elif path.startswith("/fonts/") and method == "GET":
            # h4xx0r's three faces, 294 KB together. Unlike everything else
            # here they never change, so the browser may keep them: sent on
            # every load they cost the Pico a second or so each time.
            name = path[7:]
            if name not in FONTS:
                await respond(w, 404, {"error": "no such font"})
            else:
                await send_file(w, "fonts/" + name, "font/ttf", cache="max-age=31536000, immutable")
        elif path.startswith("/scans/") and method == "GET":
            name = path[7:]
            if "/" in name or name not in os.listdir("scans"):
                await respond(w, 404, {"error": "no such scan"})
            else:
                await send_file(w, "scans/" + name, "text/csv",
                                'Content-Disposition: attachment; filename="%s"\r\n' % name)
        elif path.startswith("/api/"):
            try:
                data = json.loads(body) if body else {}
                body = None     # a loaded CSV is in `data` now; not twice
                code, out = await api(method, path, data)
            except Busy as e:
                code, out = 409, {"error": str(e)}
            except (ValueError, KeyError, IndexError, TypeError) as e:
                code, out = 400, {"error": str(e) or "bad request"}
            except Exception as e:
                log("%s failed: %s" % (path, e))
                code, out = 500, {"error": str(e)}
            await respond(w, code, out)
        else:
            await respond(w, 404, {"error": "not found"})
    except Exception as e:
        print("http:", e)
    finally:
        try:
            w.close()
            await w.wait_closed()
        except Exception:
            pass


async def main():
    try:
        os.mkdir("scans")
    except OSError:
        pass
    log("Probe Pico %s, started after %s" % (VERSION, reset_cause()))
    log("display at 0x%02X" % oled.addr if oled.ok else "no display on GP26/GP27")
    asyncio.create_task(display_task())
    await probe.reset()
    await wifi_up_once()
    await asyncio.start_server(handle, "0.0.0.0", 80)
    while True:
        await asyncio.sleep(3600)


def screen():
    """The four lines on the OLED: where to find the Pico, the machine, and
    what is happening. Sixteen characters each."""
    if wifi["mode"] == "station":
        top = wifi["ip"]
    elif wifi["mode"] == "setup":
        top = "setup " + wifi["ip"]
    else:
        top = "joining WiFi"
    if cnc.connected:
        name = (cnc.host or "").split(".")[0]
        st = cnc.status.state.split(":")[0]
        mid = "%s %s" % (name[:16 - len(st) - 1], st)
    else:
        mid = "no machine"
    job = scanner.job
    if job and job.get("running") and job["kind"] == "scan":
        third = "pt %d/%d" % (job["i"] + 1, job["n"])
        eta = job.get("eta")
        fourth = ("%d min left" % int((eta + 59) // 60)) if eta else "scanning"
    elif job and job.get("running"):
        third, fourth = "touch test", "%d touches" % job.get("n", 0)
    else:
        pos = cnc.status.pos if cnc.connected else None
        third = ("Z %.3f" % pos[2]) if pos else ""
        fourth = "touched" if probe.level() else ("pin down" if probe.deployed else "pin up")
    return [top, mid, third, fourth]


async def display_task():
    while True:
        if oled.ok and not scanner.in_coarse:
            if cnc.connected and not scanner.busy:
                cnc.poll()   # keep Z fresh while nothing else asks for it
            oled.lines(screen())
        await asyncio.sleep_ms(500)


async def wifi_up_once():
    # wifi_up never returns in setup mode (it blinks the LED), so it runs as
    # its own task and the server starts once an address is up.
    asyncio.create_task(wifi_up())
    while not wifi["ip"]:
        await asyncio.sleep_ms(200)


asyncio.run(main())
