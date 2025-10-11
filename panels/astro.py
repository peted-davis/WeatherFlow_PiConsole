""" Defines the SunriseSunset and MoonPhase panels required by the Raspberry Pi
Python console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2022 Peter Davis

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
from kivy.uix.boxlayout      import BoxLayout
from kivy.properties         import StringProperty
from kivy.graphics           import Color, Rectangle
from kivy.clock import Clock

# Load required panel modules
from panels.template         import panelTemplate


# ==============================================================================
# SunriseSunsetPanel AND SunriseSunsetButton CLASS
# ==============================================================================
class SunriseSunsetPanel(panelTemplate):

    # Define SunriseSunsetPanel class properties
    uvBackground = StringProperty('-')

    # Initialise SunriseSunsetPanel
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setUVBackground()
        self.ids['day_night_bar'].bind(pos=self.draw_day_night_bar)
        self.ids['day_night_bar'].bind(size=self.draw_day_night_bar)

    # Set current UV index backgroud
    def setUVBackground(self):
        self.uvBackground = self.app.CurrentConditions.Obs['UVIndex'][3]

    def draw_day_night_bar(self, *args):

        self.ids['day_night_bar'].canvas.after.clear()
        for type in self.app.astro.day_night_order:
            if self.app.astro.night[0] and type == 'night':
                start_x = self.app.astro.night[1]
                width   = self.app.astro.night[2] - self.app.astro.night[1]
                with self.ids['day_night_bar'].canvas.after:
                    Color(100 / 255, 100 / 255, 100 / 255, 1)
                    self.ids['day_night_bar'].night_bar = Rectangle(pos=(self.ids['day_night_bar'].x + start_x * self.ids['day_night_bar'].width,
                                                                         self.ids['day_night_bar'].y),
                                                                    size=(self.ids['day_night_bar'].width * width,
                                                                          self.ids['day_night_bar'].height))
            if self.app.astro.twilight and type == 'twilight':
                start_x = self.app.astro.twilight[1]
                width   = self.app.astro.twilight[2] - self.app.astro.twilight[1]
                with self.ids['day_night_bar'].canvas.after:
                    Color(29 / 255, 74 / 255, 87 / 255, 1)
                    self.ids['day_night_bar'].day_bar = Rectangle(pos=(self.ids['day_night_bar'].x + start_x * self.ids['day_night_bar'].width,
                                                                       self.ids['day_night_bar'].y),
                                                                  size=(self.ids['day_night_bar'].width * width,
                                                                        self.ids['day_night_bar'].height))
            if self.app.astro.daylight and type == 'daylight':
                start_x = self.app.astro.daylight[1]
                width   = self.app.astro.daylight[2] - self.app.astro.daylight[1]
                with self.ids['day_night_bar'].canvas.after:
                    Color(0 / 255, 113 / 255, 123 / 255, 1)
                    self.ids['day_night_bar'].day_bar = Rectangle(pos=(self.ids['day_night_bar'].x + start_x * self.ids['day_night_bar'].width,
                                                                       self.ids['day_night_bar'].y),
                                                                  size=(self.ids['day_night_bar'].width * width,
                                                                        self.ids['day_night_bar'].height))



    #def resize_day_night_bar(self, *args):
    #    self.ids['day_night_bar'].night_bar.pos  = self.ids['day_night_bar'].pos
    #    self.ids['day_night_bar'].night_bar.size = self.ids['day_night_bar'].size


class SunriseSunsetButton(RelativeLayout):
    pass


# ==============================================================================
# MoonPhasePanel AND MoonPhaseButton CLASS
# ==============================================================================
class MoonPhasePanel(panelTemplate):
    pass


class MoonPhaseButton(RelativeLayout):
    pass
