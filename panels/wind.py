""" Defines the WindSpeed panel required by the Raspberry Pi Python console for
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
from kivy.properties         import StringProperty, NumericProperty
from kivy.animation          import Animation

# Load required panel modules
from panels.template         import panelTemplate


# ==============================================================================
# WindSpeedPanel AND WindSpeedButton CLASS
# ==============================================================================
class WindSpeedPanel(panelTemplate):

    # Define WindSpeedPanel class properties
    rapidWindDir = NumericProperty(0)
    windDirIcon  = StringProperty('-')
    windSpdIcon  = StringProperty('-')

    # Initialise WindSpeedPanel
    def __init__(self, mode=None, **kwargs):
        super().__init__(mode, **kwargs)
        if self.app.CurrentConditions.Obs['rapidDir'][0] != '-':
            self.rapidWindDir = self.app.CurrentConditions.Obs['rapidDir'][0]
        self.setWindIcons()

    # Animate rapid wind rose
    def animateWindRose(self):

        # Get current wind direction, old wind direction and change in wind
        # direction over last Rapid-Wind period
        if self.app.CurrentConditions.Obs['rapidDir'][0] != '-':
            rapidWindDir_New = int(self.app.CurrentConditions.Obs['rapidDir'][0])
            rapidWindDir_Old = self.rapidWindDir
            rapidWindShift   = rapidWindDir_New - self.rapidWindDir

            # Animate Wind Rose at constant speed between old and new Rapid-Wind
            # wind direction
            if rapidWindShift >= -180 and rapidWindShift <= 180:
                Anim = Animation(rapidWindDir=rapidWindDir_New, duration=2 * abs(rapidWindShift) / 360)
                Anim.start(self)
            elif rapidWindShift > 180:
                Anim = Animation(rapidWindDir=0.1, duration=2 * rapidWindDir_Old / 360) + Animation(rapidWindDir=rapidWindDir_New, duration=2 * (360 - rapidWindDir_New) / 360)
                Anim.start(self)
            elif rapidWindShift < -180:
                Anim = Animation(rapidWindDir=359.9, duration=2 * (360 - rapidWindDir_Old) / 360) + Animation(rapidWindDir=rapidWindDir_New, duration=2 * rapidWindDir_New / 360)
                Anim.start(self)

    # Fix Wind Rose angle at 0/360 degree discontinuity
    def on_rapidWindDir(self, item, rapidWindDir):
        if rapidWindDir == 0.1:
            item.rapidWindDir = 360
        if rapidWindDir == 359.9:
            item.rapidWindDir = 0

    # Set mean windspeed and direction icons
    def setWindIcons(self):
        self.windDirIcon = self.app.CurrentConditions.Obs['WindDir'][2]
        self.windSpdIcon = self.app.CurrentConditions.Obs['WindSpd'][3]


class WindSpeedButton(RelativeLayout):
    pass
