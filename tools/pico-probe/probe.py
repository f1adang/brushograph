# The 3D Touch, driven from the Pico: servo pulses out on GP15, the touch in
# on GP14. A BLTouch clone (Twotrees / MKS "3D Touch").
#
# Measured on the bench (MicroPython 1.29, Pico 2 W, 1 kOhm in the trigger
# line, internal pull-up):
#   - at rest, deployed and stowed the output reads low;
#   - a touch is a 9 ms high pulse; the sensor pulls its pin up by itself;
#   - about 290 ms later the output goes high and stays high, through
#     deploy and stow, until a reset (2190 us) clears it. While it is high
#     the sensor ignores deploy.
# So every probe is reset -> deploy -> touch, and the touch is caught by an
# interrupt: polling could miss a 9 ms pulse while the loop is waiting on the
# network.

import asyncio
import time

from machine import PWM, Pin

# Servo pulse widths, microseconds. Klipper's figures (bltouch.py); the clone
# answers to them.
DEPLOY = 650
TOUCH_MODE = 1165
STOW = 1475
SELF_TEST = 1780
RESET = 2190

# How long a command is held before the PWM is stopped. Klipper's
# pin_move_time default is 0.68 s.
MOVE_MS = 700

COMMANDS = {"deploy": DEPLOY, "stow": STOW, "reset": RESET, "selftest": SELF_TEST}


class Probe:
    def __init__(self, servo_pin=15, trigger_pin=14):
        self.trigger = Pin(trigger_pin, Pin.IN, Pin.PULL_UP)
        self.servo = PWM(Pin(servo_pin), freq=50)
        self.servo.duty_ns(0)
        self.touched = False
        self.touched_ms = 0
        self.flag = asyncio.ThreadSafeFlag()
        self.lock = asyncio.Lock()
        self.deployed = False
        self.trigger.irq(self._edge, Pin.IRQ_RISING)

    def _edge(self, pin):
        if not self.touched:
            self.touched = True
            self.touched_ms = time.ticks_ms()
        self.flag.set()

    def arm(self):
        """Forget any earlier touch; the next rising edge is the one."""
        self.touched = False
        self.flag.clear()

    def level(self):
        return self.trigger.value()

    def hit(self):
        """A touch since arming, or the output latched high after one."""
        return self.touched or self.trigger.value() == 1

    async def command(self, us):
        async with self.lock:
            self.servo.duty_ns(us * 1000)
            await asyncio.sleep_ms(MOVE_MS)
            self.servo.duty_ns(0)
        self.deployed = us == DEPLOY

    async def reset(self):
        await self.command(RESET)

    async def deploy(self, reset=True):
        """Pin down, ready for a touch. False if the sensor still reports
        triggered afterwards: the pin came down onto something, or did not
        come down at all."""
        if reset:
            await self.reset()
        await self.command(DEPLOY)
        await asyncio.sleep_ms(30)
        self.arm()
        return self.trigger.value() == 0

    async def stow(self):
        await self.command(STOW)

    async def wait_touch(self, timeout_ms):
        """True as soon as the pin is touched, False after timeout_ms."""
        if self.touched:
            return True
        try:
            await asyncio.wait_for_ms(self.flag.wait(), timeout_ms)
        except asyncio.TimeoutError:
            pass
        return self.touched
