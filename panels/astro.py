""" Defines the SunriseSunset and MoonPhase panels required by the Raspberry Pi
Python console for WeatherFlow Tempest and Smart Home Weather stations.
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
from kivy.properties         import StringProperty

# Load required panel modules
from panels.template         import panelTemplate


# ==============================================================================
# SunriseSunsetPanel AND SunriseSunsetButton CLASS
# ==============================================================================
class SunriseSunsetPanel(panelTemplate):

    # Define SunriseSunsetPanel class properties
    uvBackground = StringProperty('-')

    # Initialise SunriseSunsetPanel
    def __init__(self, mode=None, **kwargs):
        super().__init__(mode, **kwargs)
        self.setUVBackground()

    # Set current UV index backgroud
    def setUVBackground(self):
        self.uvBackground = self.app.CurrentConditions.Obs['UVIndex'][3]


class SunriseSunsetButton(RelativeLayout):
    pass


# ==============================================================================
# MoonPhasePanel AND MoonPhaseButton CLASS
# ==============================================================================
class MoonPhasePanel(panelTemplate):
    pass


class MoonPhaseButton(RelativeLayout):
    pass
