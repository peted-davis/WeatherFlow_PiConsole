""" Defines the Barometer panel required by the Raspberry Pi Python console for
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
from kivy.properties         import StringProperty

# Load required panel modules
from panels.template         import panelTemplate


# ==============================================================================
# BarometerPanel AND BarometerButton CLASS
# ==============================================================================
class BarometerPanel(panelTemplate):

    # Define BarometerPanel class properties
    barometer_arrow = StringProperty('-')
    barometer_max   = StringProperty('-')
    barometer_min   = StringProperty('-')

    # Initialise BarometerPanel
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setBarometerArrow()
        self.set_barometer_max_min()

    # Set Barometer arrow rotation angle to match current sea level pressure
    def setBarometerArrow(self):
        SLP = self.app.CurrentConditions.Obs['SLP'][2]
        if SLP is None or SLP == '-':
            self.barometer_arrow = '-'
        else:
            self.barometer_arrow = '{:.1f}'.format(max(min(1050, SLP), 950))

    # Set maximum and minimum barometer limits based on selected units
    def set_barometer_max_min(self):
        value = self.app.config['Units']['Pressure']
        units = ['mb', 'hpa', 'inhg', 'mmhg']
        max   = ['1050', '1050', '31.0', '788']
        min   = ['950', '950', '28.0', '713']
        self.barometer_max = max[units.index(value)]
        self.barometer_min = min[units.index(value)]


class BarometerButton(RelativeLayout):
    pass
