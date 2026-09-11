""" Behaviour tests for the rain rate animation in panels/rainfall.py.

    Runs headless with the mock window and GL backends and a synthetic clock: no
    Pi, no display, no real time, no weather station. The panel is constructed
    without Kivy language rules, so it has no canvas; what is exercised is the
    animation state machine and the value of rain_rate_x over time.

    Run with:  python -m unittest discover tests -v
"""

import os
import sys

# Import the console's modules from the repository root, wherever the test is
# run from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['KIVY_NO_ARGS']    = '1'
os.environ['KIVY_WINDOW']     = 'mock'
os.environ['KIVY_GL_BACKEND'] = 'mock'

import unittest                                                      # noqa: E402

import kivy.base                                                     # noqa: E402
import kivy.clock                                                    # noqa: E402

# A widget asks the event loop for a window when it is constructed. These tests
# construct the panel in order to exercise its animation, never to draw it, so
# there is nothing for a window to do here
kivy.base.EventLoop.ensure_window = lambda *args, **kwargs: None


class FakeClock(kivy.clock.ClockBase):
    """ A clock whose time is advanced by the caller rather than by sleeping """

    def __init__(self, **kwargs):
        self._now = 0.0
        super().__init__(**kwargs)

    def time(self):
        return self._now

    def advance(self, dt, fps=60):
        """ Advance dt seconds, processing events once per window frame """
        tick = 1.0 / fps
        for _ in range(int(round(dt / tick))):
            self._now += tick
            self._dt = tick
            self._last_tick = self._now
            self._process_events()


clock = FakeClock()
kivy.clock.Clock = clock

import panels.rainfall as rainfall                                   # noqa: E402
import panels.template as template                                  # noqa: E402

rainfall.Clock = clock


class FakeConditions:
    def __init__(self, rain_rate=None):
        # Obs['RainRate'] is [value, unit, text, float-as-string]
        self.Obs = {'RainRate': ['-', '', '', '-']}
        self.set(rain_rate)

    def set(self, rain_rate):
        if rain_rate is None:
            self.Obs['RainRate'] = ['-', 'mm/hr', '-', '-']
        else:
            self.Obs['RainRate'] = [rain_rate, 'mm/hr', str(rain_rate),
                                    str(float(rain_rate))]


class FakeApp:
    def __init__(self, rain_rate=None):
        self.config = {'System': {'nc_rain': '0'}}
        self.CurrentConditions = FakeConditions(rain_rate)


class RainfallPanelTest(unittest.TestCase):

    def panel(self, rain_rate=None):
        app = FakeApp(rain_rate)
        template.App.get_running_app = staticmethod(lambda: app)
        panel = rainfall.RainfallPanel()
        self.addCleanup(panel.stop_rain_rate_animation)
        return panel, app

    # --- the animation state machine ------------------------------------

    def test_no_animation_when_rain_rate_unavailable(self):
        panel, _ = self.panel(None)
        self.assertFalse(hasattr(panel, 'animation'))
        self.assertEqual(panel.rain_rate_y, -1.00)

    def test_no_animation_at_zero_rain_rate(self):
        panel, _ = self.panel(0)
        self.assertFalse(hasattr(panel, 'animation'))
        self.assertEqual(panel.rain_rate_y, -1.00)

    def test_animation_starts_when_it_rains(self):
        panel, _ = self.panel(2.5)
        self.assertTrue(hasattr(panel, 'animation'))

    def test_animation_stops_when_rain_stops(self):
        panel, app = self.panel(2.5)
        self.assertTrue(hasattr(panel, 'animation'))
        app.CurrentConditions.set(0)
        panel.animate_rain_rate()
        self.assertFalse(hasattr(panel, 'animation'))
        self.assertEqual(panel.rain_rate_x, 0)

    def test_animation_stops_when_rain_rate_becomes_unavailable(self):
        panel, app = self.panel(2.5)
        app.CurrentConditions.set(None)
        panel.animate_rain_rate()
        self.assertFalse(hasattr(panel, 'animation'))
        self.assertEqual(panel.rain_rate_y, -1.00)

    def test_repeated_observations_do_not_stack_animations(self):
        panel, _ = self.panel(2.5)
        first = panel.animation
        for _ in range(5):
            panel.animate_rain_rate()
        self.assertIs(panel.animation, first)

    def test_stop_is_idempotent(self):
        panel, _ = self.panel(2.5)
        panel.stop_rain_rate_animation()
        panel.stop_rain_rate_animation()
        self.assertFalse(hasattr(panel, 'animation'))

    # --- the sweep ------------------------------------------------------

    def test_sweep_advances_and_loops_back(self):
        panel, _ = self.panel(2.5)
        clock.advance(rainfall.RAIN_RATE_PERIOD / 2)
        halfway = panel.rain_rate_x
        self.assertLess(halfway, 0)
        self.assertGreater(halfway, rainfall.RAIN_RATE_TRAVEL)
        # A full further sweep returns to roughly where it was, never past the
        # end of the travel
        clock.advance(rainfall.RAIN_RATE_PERIOD)
        self.assertAlmostEqual(panel.rain_rate_x, halfway, delta=0.05)

    def test_sweep_stays_within_travel(self):
        panel, _ = self.panel(10)
        for _ in range(60):
            clock.advance(0.5)
            self.assertLessEqual(panel.rain_rate_x, 0.0001)
            self.assertGreater(panel.rain_rate_x, rainfall.RAIN_RATE_TRAVEL - 0.0001)

    def test_sweep_takes_the_configured_period(self):
        """ The sweep is driven by elapsed time, so the period holds regardless
            of how often the step actually runs
        """
        panel, _ = self.panel(2.5)
        clock.advance(rainfall.RAIN_RATE_PERIOD * 0.99, fps=120)
        self.assertAlmostEqual(panel.rain_rate_x, rainfall.RAIN_RATE_TRAVEL,
                               delta=0.05)

    # --- the point of the change: redraw rate ---------------------------

    def test_redraw_rate_is_independent_of_window_fps(self):
        """ Issue #186: the sweep used to update rain_rate_x once per frame, so
            a 12 second sweep redrew the window at maxfps for the whole of the
            rainfall. It should now be bounded by RAIN_RATE_FPS instead, whatever
            maxfps the window is configured with
        """
        budget = rainfall.RAIN_RATE_PERIOD * rainfall.RAIN_RATE_FPS
        for window_fps in (30, 60, 120):
            panel, _ = self.panel(2.5)
            updates = []
            panel.bind(rain_rate_x=lambda *a: updates.append(1))
            clock.advance(rainfall.RAIN_RATE_PERIOD, fps=window_fps)
            panel.stop_rain_rate_animation()
            at = f'at maxfps={window_fps}'
            # Never more often than the scheduled rate asks for. A scheduled
            # interval can only run on a frame, so at a low maxfps it runs
            # slightly less often than that, which is fine - the sweep is driven
            # by elapsed time and so keeps its period either way
            self.assertLessEqual(len(updates), budget * 1.05, at)
            self.assertGreater(len(updates), budget * 0.75, at)
            # And decisively less often than once per frame, which is the defect
            per_frame = rainfall.RAIN_RATE_PERIOD * window_fps
            if window_fps > rainfall.RAIN_RATE_FPS:
                self.assertLess(len(updates), per_frame * 0.9, at)

    # --- the level, which this change must not alter --------------------

    def test_rain_rate_y_is_monotonic_in_rain_rate(self):
        last = -1.01
        for rain_rate in (0, 0.1, 1, 3, 10, 25, 49.9, 50, 200):
            panel, _ = self.panel(rain_rate)
            self.assertGreaterEqual(panel.rain_rate_y, last)
            self.assertGreaterEqual(panel.rain_rate_y, -1.00)
            self.assertLessEqual(panel.rain_rate_y, 0)
            last = panel.rain_rate_y

    def test_rain_rate_y_saturates_above_the_cut_off(self):
        panel, _ = self.panel(50)
        self.assertEqual(panel.rain_rate_y, 0)
        panel, _ = self.panel(500)
        self.assertEqual(panel.rain_rate_y, 0)


if __name__ == '__main__':
    unittest.main()
