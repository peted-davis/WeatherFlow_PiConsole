""" Defines the Rainfall panel required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2021 Peter Davis

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
from kivy.app                import App

# Load required panel modules
from panels.template         import panelTemplate

# Load required system modules
import math


# ==============================================================================
# RainfallPanel AND RainfallButton CLASS
# ==============================================================================
class RainfallPanel(panelTemplate):

    # Define RainfallPanel class properties
    rainRatePosX  = NumericProperty(+0)
    rainRatePosY  = NumericProperty(-1)

    # Initialise RainfallPanel
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.animateRainRate()

    # Animate RainRate level
    def animateRainRate(self):

        # Get current rain rate and convert to float
        if App.get_running_app().CurrentConditions.Obs['RainRate'][0] != '-':
            RainRate = float(App.get_running_app().CurrentConditions.Obs['RainRate'][3])

            # Set RainRate level y position
            y0 = -1.00
            yt = 0
            t = 50
            if RainRate == 0:
                self.rainRatePosY = y0
            elif RainRate < 50.0:
                A = (yt - y0) / t**0.5 * RainRate**0.5 + y0
                B = (yt - y0) / t**0.3 * RainRate**0.3 + y0
                C = (1 + math.tanh(RainRate - 3)) / 2
                self.rainRatePosY = (A + C * (B - A))
            else:
                self.rainRatePosY = yt

            # Animate RainRate level x position
            if RainRate == 0:
                if hasattr(self, 'Anim'):
                    self.Anim.stop(self)
                    delattr(self, 'Anim')
            else:
                if not hasattr(self, 'Anim'):
                    self.Anim  = Animation(rainRatePosX=-0.875, duration=12)
                    self.Anim += Animation(rainRatePosX=-0.875, duration=12)
                    self.Anim.repeat = True
                    self.Anim.start(self)

    # Loop RainRate animation in the x direction
    def on_rainRatePosX(self, item, rainRatePosX):
        if round(rainRatePosX, 3) == -0.875:
            item.rainRatePosX = 0


class RainfallButton(RelativeLayout):
    pass
