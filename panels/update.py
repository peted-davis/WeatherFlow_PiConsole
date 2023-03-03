""" Defines the update notification panel required by the Raspberry Pi
Python console for WeatherFlow Tempest and Smart Home Weather stations.
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
from kivy.uix.modalview      import ModalView
from kivy.properties         import StringProperty
from kivy.app                import App


# ==============================================================================
# UpdateNotification POPUP CLASS
# ==============================================================================
class updateNotification(ModalView):

    latest_ver = StringProperty('-')

    def __init__(self, latest_ver, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        setattr(self.app, self.__class__.__name__, self)
        self.latest_ver = latest_ver
