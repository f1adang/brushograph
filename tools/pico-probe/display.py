# The 0.91" OLED: SSD1306, 128 x 32, on I2C1 (GP26 SDA, GP27 SCL, 3V3 and
# GND beside them). Four lines of sixteen characters in MicroPython's own
# 8 x 8 font.
#
# Optional: with no display, or one that stops answering, everything here does
# nothing, and the probe works as it did. The driver is the few commands a
# 128 x 32 panel needs, written against framebuf rather than pulling in
# micropython-lib's ssd1306 (which the rp2 firmware does not include).

import framebuf
from machine import I2C, Pin

WIDTH, HEIGHT = 128, 32
COLS = WIDTH // 8

# Power-on sequence for a 128 x 32 SSD1306 with its charge pump.
INIT = (
    0xAE,              # display off
    0x20, 0x00,        # horizontal addressing
    0x40,              # start line 0
    0xA1,              # columns mirrored: the module's text reads the right way up
    0xA8, HEIGHT - 1,  # multiplex ratio
    0xC8,              # rows scanned downward
    0xD3, 0x00,        # no vertical offset
    0xDA, 0x02,        # COM pins: sequential, which is what a 32-row panel is wired as
    0xD5, 0x80,        # clock
    0xD9, 0xF1,        # pre-charge
    0xDB, 0x30,        # VCOM detect
    0x81, 0x8F,        # contrast
    0xA4,              # show RAM
    0xA6,              # not inverted
    0x8D, 0x14,        # charge pump on
    0xAF,              # display on
)


class Display:
    def __init__(self, sda=26, scl=27, bus=1):
        self.ok = False
        self.addr = None
        self._last = None
        self.buf = bytearray(WIDTH * HEIGHT // 8)
        self.fb = framebuf.FrameBuffer(self.buf, WIDTH, HEIGHT, framebuf.MONO_VLSB)
        try:
            self.i2c = I2C(bus, sda=Pin(sda), scl=Pin(scl), freq=400_000)
            found = self.i2c.scan()
        except OSError:
            return
        # 0x3C is what these modules ship as; 0x3D is the other strap.
        for addr in (0x3C, 0x3D):
            if addr in found:
                self.addr = addr
                break
        if self.addr is None:
            return
        try:
            for c in INIT:
                self._cmd(c)
            self.ok = True
            self.lines(["Probe Pico", "starting"])
        except OSError:
            self.ok = False

    def _cmd(self, c):
        self.i2c.writeto(self.addr, bytes((0x80, c)))

    def _show(self):
        for c in (0x21, 0, WIDTH - 1, 0x22, 0, HEIGHT // 8 - 1):
            self._cmd(c)
        self.i2c.writevto(self.addr, (b"\x40", self.buf))

    def lines(self, rows):
        """Up to four lines, each cut to sixteen characters. Sent only when
        they change: a full screen is 512 bytes, 13 ms of the bus."""
        if not self.ok:
            return
        rows = tuple(str(r)[:COLS] for r in rows[:HEIGHT // 8])
        if rows == self._last:
            return
        self.fb.fill(0)
        for i, r in enumerate(rows):
            self.fb.text(r, 0, i * 8, 1)
        try:
            self._show()
            self._last = rows
        except OSError:
            # Unplugged, or the bus upset: stop trying rather than slow
            # everything else down with timeouts.
            self.ok = False
