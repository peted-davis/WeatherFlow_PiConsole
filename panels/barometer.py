""" Defines the Barometer panel required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
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
from kivy.properties         import StringProperty

# Load required panel modules
from panels.template         import panelTemplate


# ==============================================================================
# BarometerPanel AND BarometerButton CLASS
# ==============================================================================
class BarometerPanel(panelTemplate):

    # Define BarometerPanel class properties
    barometerArrow = StringProperty('-')

    # Initialise BarometerPanel
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setBarometerArrow()

    # Set Barometer arrow rotation angle to match current sea level pressure
    def setBarometerArrow(self):
        SLP = self.app.CurrentConditions.Obs['SLP'][2]
        if SLP is None or SLP == '-':
            self.barometerArrow = '-'
        else:
            self.barometerArrow = '{:.1f}'.format(max(min(1050, SLP), 950))


class BarometerButton(RelativeLayout):
    pass
