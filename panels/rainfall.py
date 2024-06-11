""" Defines the Rainfall panel required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2023 Peter Davis

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
from kivy.properties         import NumericProperty
from kivy.animation          import Animation

# Load required panel modules
from panels.template         import panelTemplate

# Load required system modules
import math


# ==============================================================================
# RainfallPanel AND RainfallButton CLASS
# ==============================================================================
class RainfallPanel(panelTemplate):

    # Define RainfallPanel class properties
    rain_rate_x  = NumericProperty(+0)
    rain_rate_y  = NumericProperty(-1)

    # Initialise RainfallPanel
    def __init__(self, mode=None, **kwargs):
        super().__init__(mode, **kwargs)
        self.animate_rain_rate()

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
                if hasattr(self, 'animation'):
                    self.animation.stop(self)
                    delattr(self, 'animation')
            else:
                if not hasattr(self, 'animation'):
                    self.animation  = Animation(rain_rate_x=-0.875, duration=12)
                    self.animation += Animation(rain_rate_x=-0.875, duration=12)
                    self.animation.repeat = True
                    self.animation.start(self)

        # Else, stop animation if it is running
        else:
            if hasattr(self, 'animation'):
                self.rain_rate_y = -1.00
                self.animation.stop(self)
                delattr(self, 'animation')

    # Loop RainRate animation in the x direction
    def on_rain_rate_x(self, item, rain_rate_x):
        if round(rain_rate_x, 3) == -0.875:
            item.rain_rate_x = 0


class RainfallButton(RelativeLayout):
    pass
