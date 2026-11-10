# FluidNC over its telnet port, from MicroPython's asyncio.
#
# Nothing is wired to the machine: the probe's touch never reaches FluidNC's
# probe input, so there is no G38.2 here. The scan moves the axis and the Pico
# watches the pin; see scan.py for how a reading is made independent of the
# network's delay.

import asyncio
import socket
import struct
import time

TELNET_PORT = 23
JOG_CANCEL = b"\x85"
FEED_HOLD = b"!"


class CNCError(Exception):
    pass


def mdns_resolve(name, timeout_ms=1500):
    """A `.local` name to an IPv4 address, by one mDNS query.

    Asked from a port other than 5353, which makes it a one-shot legacy query
    (RFC 6762 6.7): the responder answers straight back to that port, so a
    plain socket hears it."""
    q = b"\x12\x34\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    for part in name.rstrip(".").split("."):
        q += bytes([len(part)]) + part.encode()
    q += b"\x00\x00\x01\x00\x01"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(timeout_ms / 1000)
        s.sendto(q, socket.getaddrinfo("224.0.0.251", 5353)[0][-1])
        end = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            try:
                data, _ = s.recvfrom(512)
            except OSError:
                break
            ip = _answer_a(data)
            if ip:
                return ip
    finally:
        s.close()
    return None


def _skip_name(d, i):
    while True:
        n = d[i]
        if n == 0:
            return i + 1
        if n & 0xC0 == 0xC0:
            return i + 2
        i += n + 1


def _answer_a(d):
    if len(d) < 12:
        return None
    qd, an = struct.unpack(">HH", d[4:8])
    i = 12
    for _ in range(qd):
        i = _skip_name(d, i) + 4
    for _ in range(an):
        i = _skip_name(d, i)
        typ, _cls, _ttl, ln = struct.unpack(">HHIH", d[i:i + 10])
        i += 10
        if typ == 1 and ln == 4:
            return "%d.%d.%d.%d" % tuple(d[i:i + 4])
        i += ln
    return None


def resolve(host):
    """An address open_connection can use. A `.local` name is asked for by
    mDNS first, which lwIP's own resolver may not do; anything else, or a
    name nobody answered for, goes to the ordinary resolver."""
    if host.endswith(".local"):
        ip = mdns_resolve(host)
        if ip:
            return ip
    return host


class Status:
    def __init__(self):
        self.state = "?"
        self.pos = None          # (x, y, z): MPos, or WPos if that is what is reported
        self.frame = ""
        self.seq = 0


class FluidNC:
    def __init__(self, log):
        self.log = log
        self.reader = self.writer = None
        self.host = None
        self.ip = None
        self.status = Status()
        self._status_evt = asyncio.Event()
        self._replies = []
        self._reply_evt = asyncio.Event()
        self._lock = asyncio.Lock()
        self._task = None
        self._info = []
        self.alarm = None
        self.z_steps_per_mm = None

    @property
    def connected(self):
        return self.writer is not None

    async def connect(self, host, port=TELNET_PORT):
        await self.disconnect()
        ip = resolve(host)
        self.log(f"connecting to {host} ({ip}:{port})")
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), 8)
        self.host, self.ip = host, ip
        self._replies = []
        self.alarm = None
        self._task = asyncio.create_task(self._read())
        self.writer.write(b"\r\n")
        await self.writer.drain()
        await asyncio.sleep_ms(300)
        self._replies = []
        await self.query()
        # The fine pass steps in whole motor steps, so it needs to know what
        # one is. Parang's Z is 106 steps/mm: 0.0094 mm a step, and a 0.02 mm
        # step was two motor steps or three by turns.
        self.z_steps_per_mm = None
        try:
            for line in await self.send("$/axes/z/steps_per_mm", timeout_ms=3000):
                if "=" in line:
                    self.z_steps_per_mm = float(line.split("=", 1)[1])
        except (CNCError, ValueError) as e:
            self.log(f"could not read Z steps/mm ({e}); fine steps are taken as set")
        self.log(f"connected to {host}: {self.status.state}"
                 + (f", Z {self.z_steps_per_mm:g} steps/mm" if self.z_steps_per_mm else ""))

    async def disconnect(self):
        if self._task:
            self._task.cancel()
            self._task = None
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        self.reader = self.writer = None
        self.status = Status()

    async def _read(self):
        try:
            while True:
                raw = await self.reader.readline()
                if not raw:
                    break
                line = bytes(b for b in raw if 31 < b < 127).decode().strip()
                if not line:
                    continue
                if line[0] == "<":
                    self._parse_status(line)
                elif line == "ok" or line.startswith("error"):
                    self._replies.append(line)
                    self._reply_evt.set()
                elif line.startswith("ALARM"):
                    self.alarm = line
                    self.log(f"machine: {line}")
                    self._replies.append(line)
                    self._reply_evt.set()
                else:
                    self._info.append(line)
                    self.log(f"machine: {line}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.log(f"connection lost: {e}")
        self.reader = self.writer = None
        self.status.state = "disconnected"
        self._reply_evt.set()

    def _parse_status(self, line):
        st = self.status
        fields = line.strip("<>").split("|")
        st.state = fields[0]
        for f in fields[1:]:
            key, _, val = f.partition(":")
            if key in ("MPos", "WPos"):
                try:
                    st.pos = tuple(float(v) for v in val.split(",")[:3])
                    st.frame = key
                except ValueError:
                    pass
        st.seq += 1
        self._status_evt.set()

    def realtime(self, byte):
        if self.writer:
            self.writer.write(byte)

    def poll(self):
        """Ask for a status report without waiting for it."""
        self.realtime(b"?")

    async def query(self, timeout_ms=2000, tries=3):
        """A fresh status report.

        Asked for again when one does not come, rather than given up on: a
        scan makes thousands of these, and Pinkograph's 2236-point scan
        (2026-11-10) ended on the first that took more than 2 s, and the
        machine was Idle and answering when asked afterwards. A `?` is a realtime
        command, so asking twice does nothing twice."""
        if not self.writer:
            raise CNCError("not connected")
        for attempt in range(tries):
            seq = self.status.seq
            self._status_evt.clear()
            self.writer.write(b"?")
            await self.writer.drain()
            end = time.ticks_add(time.ticks_ms(), timeout_ms)
            while self.status.seq == seq:
                left = time.ticks_diff(end, time.ticks_ms())
                if left <= 0 or not self.writer:
                    break
                try:
                    await asyncio.wait_for_ms(self._status_evt.wait(), left)
                except asyncio.TimeoutError:
                    pass
                self._status_evt.clear()
            if self.status.seq != seq:
                if attempt:
                    self.log(f"status report came on asking {attempt + 1} times")
                return self.status
            if not self.writer:
                raise CNCError("connection lost")
        raise CNCError(f"no status report, asked {tries} times, {timeout_ms} ms each")

    async def _reply(self, timeout_ms):
        end = time.ticks_add(time.ticks_ms(), timeout_ms)
        while not self._replies:
            if not self.writer:
                raise CNCError("connection lost")
            left = time.ticks_diff(end, time.ticks_ms())
            if left <= 0:
                raise CNCError("no reply from the machine")
            self._reply_evt.clear()
            try:
                await asyncio.wait_for_ms(self._reply_evt.wait(), left)
            except asyncio.TimeoutError:
                pass
        return self._replies.pop(0)

    async def send(self, *lines, timeout_ms=60000):
        """Send lines and wait for each one's reply; returns the other lines
        that came back with them (a setting's value, say).

        An `ok` says the line was accepted, not that it has run: Parang's
        FluidNC (v4.1.1, a bulletproof-webui-uploads build) answered a G0 and
        the G4 P0 after it both at once while the axis was still moving. Use
        wait_idle() to know a move is over.

        error:9 is FluidNC refusing G-code while it is in Jog or Alarm. It
        came back from the first move of a scan, once, with nothing jogging
        that the Pico had sent. A refused line has not run, so it is sent
        again, once, after the machine has come to rest."""
        if not self.writer:
            raise CNCError("not connected")
        async with self._lock:
            out = await self._send(lines, timeout_ms)
        refused = [l for l, r in out if r == "error:9"]
        if refused:
            st = self.status.state
            self.log(f"machine refused {refused} in state {st}; trying again once it is still")
            await self.wait_idle()
            async with self._lock:
                out = [x for x in out if x[1] != "error:9"] + await self._send(refused, timeout_ms)
        for l, r in out:
            if r != "ok":
                raise CNCError(f"{l} -> {r} (machine {self.status.state})")
        return self._info

    async def _send(self, lines, timeout_ms):
        self._replies = []
        self._info = []
        self.writer.write("".join(l + "\n" for l in lines).encode())
        await self.writer.drain()
        # A loop, not a comprehension: MicroPython runs a comprehension as a
        # function of its own, where `await` is a SyntaxError.
        out = []
        for l in lines:
            out.append((l, await self._reply(timeout_ms)))
        return out

    async def wait_idle(self, timeout_ms=120000):
        """Until the machine is standing still: Idle in two status reports
        running, at the same position. Two, because a line that has been
        acknowledged may not have started moving yet when the first report
        is made. Returns the position. G4 P0 used to be the wait, and it does
        not wait on Parang's FluidNC (see send())."""
        end = time.ticks_add(time.ticks_ms(), timeout_ms)
        last = None
        while True:
            st = await self.query()
            if st.state.startswith("Alarm"):
                raise CNCError(f"the machine is in alarm ({st.state})")
            if st.state.startswith("Idle"):
                if last is not None and st.pos == last:
                    return st.pos
                last = st.pos
            else:
                last = None
            if time.ticks_diff(end, time.ticks_ms()) <= 0:
                raise CNCError(f"the machine did not come to rest ({st.state})")
            await asyncio.sleep_ms(10)
