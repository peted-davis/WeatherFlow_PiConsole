""" Defines the Forecast and Sager panel required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
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
from kivy.uix.modalview      import ModalView
from kivy.properties         import StringProperty
from kivy.app                import App

# Load required panel modules
from panels.template         import panelTemplate


# ==============================================================================
# ForecastPanel AND ForecastButton CLASS
# ==============================================================================
class ForecastPanel(panelTemplate):

    # Define ForecastPanel class properties
    forecast_icon = StringProperty('-')

    # Initialise ForecastPanel
    def __init__(self, mode=None, **kwargs):
        super().__init__(mode, **kwargs)
        self.set_forecast_icon()
        self.forecast_detail_panel = forecast_detail()

    # Set Forecast icon
    def set_forecast_icon(self):
        self.forecast_icon = self.app.CurrentConditions.Met['current_hour']['forecast_icon']


class ForecastButton(RelativeLayout):
    pass


# ==============================================================================
# SagerPanel AND SagerButton CLASS
# ==============================================================================
class SagerPanel(panelTemplate):
    pass


class SagerButton(RelativeLayout):
    pass


# ==============================================================================
# forecast_detail POPUP CLASS
# ==============================================================================
from kivy.uix.boxlayout      import BoxLayout
from kivy.uix.button         import Button

class forecast_detail(ModalView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()

        for forecast_panel in self.ids:
            forecast_idx = forecast_panel.split('_')[1]
            self.ids[forecast_panel]._forecast_idx = int(forecast_idx)
        
        
        
