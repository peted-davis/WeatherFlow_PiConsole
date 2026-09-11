""" Measures how many times rain_rate_x changes per second of animation, which
    is the number of full-window redraws the rain rate sweep asks Kivy for.

    Runs headless with the mock window and GL backends and a synthetic clock: no
    Pi, no display, no real time. The window frame rate is simulated by
    advancing the clock's time source in 1/maxfps steps and processing events
    once per step, which is what the console's event loop does per frame.
"""

import os

os.environ['KIVY_NO_ARGS']     = '1'
os.environ['KIVY_WINDOW']      = 'mock'
os.environ['KIVY_GL_BACKEND']  = 'mock'

import kivy.clock                                                    # noqa: E402
from kivy.animation  import Animation                                # noqa: E402
from kivy.event      import EventDispatcher                          # noqa: E402
from kivy.properties import NumericProperty                          # noqa: E402

TRAVEL  = -0.875   # sweep width, in pos_hint units
PERIOD  = 12       # seconds for one sweep, as in panels/rainfall.py
FPS     = 12       # scheduled animation rate of the patch
MAXFPS  = 60       # window frame rate, as reported in issue #186
SECONDS = 12       # measure one full sweep


class FakeClock(kivy.clock.ClockBase):
    """ A clock whose time is advanced by the caller rather than by sleeping """

    def __init__(self, **kwargs):
        self._now = 0.0
        super().__init__(**kwargs)

    def time(self):
        return self._now

    def advance(self, dt):
        """ One window frame: move time on and run whatever is now due """
        self._now += dt
        self._dt = dt
        self._last_tick = self._now
        self._process_events()


Clock = FakeClock()


class Counter(EventDispatcher):
    """ Stands in for RainfallPanel: counts every rain_rate_x dispatch, which is
        what invalidates the canvas and forces a redraw
    """
    rain_rate_x = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.redraws = 0

    def on_rain_rate_x(self, item, value):
        self.redraws += 1


def run(label, start, stop):
    c = Counter()
    start(c)
    tick = 1.0 / MAXFPS
    for _ in range(int(SECONDS / tick)):
        Clock.advance(tick)
    stop(c)
    rate = c.redraws / SECONDS
    print(f'{label:<28} {c.redraws:>5} updates / {SECONDS}s = {rate:>5.1f} per second')
    return c.redraws


def start_animation(c):
    # Current implementation: a per-frame Animation, repeating
    a  = Animation(rain_rate_x=TRAVEL, duration=PERIOD)
    a += Animation(rain_rate_x=TRAVEL, duration=PERIOD)
    a.repeat = True
    a.start(c)
    c._anim = a


def stop_animation(c):
    c._anim.stop(c)


def start_clock(c):
    # Patched implementation: a scheduled step at a fixed rate
    def step(dt):
        x = c.rain_rate_x + TRAVEL / PERIOD * dt
        if x <= TRAVEL:
            x -= TRAVEL
        c.rain_rate_x = x
    c._ev = Clock.schedule_interval(step, 1.0 / FPS)


def stop_clock(c):
    c._ev.cancel()


if __name__ == '__main__':
    # Animation binds to the global Clock at import time, so point it here
    kivy.clock.Clock = Clock
    import kivy.animation
    kivy.animation.Clock = Clock

    print(f'window maxfps = {MAXFPS}, sweep duration = {PERIOD}s, '
          f'patch rate = {FPS} fps\n')
    before = run('Animation (current)', start_animation, stop_animation)
    after  = run('schedule_interval (patch)', start_clock, stop_clock)
    if before:
        print(f'\n{before} -> {after}: '
              f'{100 * (before - after) / before:.0f}% fewer redraws per sweep')
