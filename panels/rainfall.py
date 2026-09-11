""" Defines the Rainfall panel required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2025 Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

# Load required Kivy modules
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties         import NumericProperty, StringProperty
from kivy.clock              import Clock

# Load required panel modules
from panels.template         import panelTemplate

# Load required system modules
import math

# Rain rate animation parameters. The icon sweeps from rain_rate_x = 0 to
# RAIN_RATE_TRAVEL over RAIN_RATE_PERIOD seconds and then restarts. The sweep is
# driven by a scheduled callback at RAIN_RATE_FPS rather than by a per-frame
# Animation, so that the redraw rate of a slow 12 second sweep does not follow
# the configured maxfps of the window
RAIN_RATE_TRAVEL = -0.875
RAIN_RATE_PERIOD = 12
RAIN_RATE_FPS    = 12


# ==============================================================================
# RainfallPanel AND RainfallButton CLASS
# ==============================================================================
class RainfallPanel(panelTemplate):

    # Define RainfallPanel class properties
    rain_rate_x  = NumericProperty(+0)
    rain_rate_y  = NumericProperty(-1)
    nc_rain_icon = StringProperty('-')

    # Initialise RainfallPanel
    def __init__(self, mode=None, **kwargs):
        super().__init__(mode, **kwargs)
        self.animate_rain_rate()
        self.set_nc_rain_icon()

    # Set whether to display NC rain icon
    def set_nc_rain_icon(self):
        self.nc_rain_icon = self.app.config['System']['nc_rain']

    # Animate RainRate level
    def animate_rain_rate(self):

        # If available, get current rain rate and convert to float
        if self.app.CurrentConditions.Obs['RainRate'][0] != '-':

            # Get current rain rate and convert to float
            rain_rate = float(self.app.CurrentConditions.Obs['RainRate'][3])

            # Set RainRate level y position
            y0 = -1.00
            yt = 0
            t = 50
            if rain_rate == 0:
                self.rain_rate_y = y0
            elif rain_rate < 50.0:
                A = (yt - y0) / t**0.5 * rain_rate**0.5 + y0
                B = (yt - y0) / t**0.3 * rain_rate**0.3 + y0
                C = (1 + math.tanh(rain_rate - 3)) / 2
                self.rain_rate_y = (A + C * (B - A))
            else:
                self.rain_rate_y = yt

            # Animate RainRate level x position
            if rain_rate == 0:
                self.stop_rain_rate_animation()
            else:
                self.start_rain_rate_animation()

        # Else, stop animation if it is running
        else:
            self.rain_rate_y = -1.00
            self.stop_rain_rate_animation()

    # Start the RainRate animation if it is not already running
    def start_rain_rate_animation(self):
        if not hasattr(self, 'animation'):
            self.animation = Clock.schedule_interval(self.update_rain_rate_x,
                                                     1 / RAIN_RATE_FPS)

    # Stop the RainRate animation if it is running
    def stop_rain_rate_animation(self):
        if hasattr(self, 'animation'):
            self.animation.cancel()
            delattr(self, 'animation')
            self.rain_rate_x = 0

    # Advance the RainRate animation in the x direction, looping back to the
    # start of the sweep once the icon has travelled its full width. The step is
    # derived from the elapsed time rather than from a fixed increment, so the
    # sweep still takes RAIN_RATE_PERIOD seconds if a frame is late or
    # RAIN_RATE_FPS is changed
    def update_rain_rate_x(self, dt):
        rain_rate_x = self.rain_rate_x + RAIN_RATE_TRAVEL / RAIN_RATE_PERIOD * dt
        if rain_rate_x <= RAIN_RATE_TRAVEL:
            rain_rate_x -= RAIN_RATE_TRAVEL
        self.rain_rate_x = rain_rate_x


class RainfallButton(RelativeLayout):
    pass
