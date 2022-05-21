""" Defines the mainMenu Panel required by the Raspberry Pi Python console for
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

# Load required library modules
from lib                      import config

# Load required Kivy modules
from kivy.network.urlrequest  import UrlRequest
from kivy.uix.modalview       import ModalView
from kivy.properties          import ListProperty, DictProperty
from kivy.clock               import Clock
from kivy.app                 import App

# Load required system modules
import certifi
import socket


# ==============================================================================
# mainMenu CLASS
# ==============================================================================
class mainMenu(ModalView):

    station_meta_data = DictProperty()
    device_meta_data  = DictProperty()
    station_list      = ListProperty()
    device_list       = DictProperty()
    tempest_list      = ListProperty()
    sky_list          = ListProperty()
    out_air_list      = ListProperty()
    in_air_list       = ListProperty()
    in_air_cleared    = False

    # Initialise 'mainMenu' ModalView class
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.app.mainMenu = self

    def on_pre_open(self):

        """ Get list of stations associated with WeatherFlow Key and add
            required device status panels to devicePanel BoxLayout
        """

        # Get list of stations associated with WeatherFlow Key
        self.get_station_list()

        # Populate status fields
        self.app.station.get_observation_count()
        self.app.station.get_hub_firmware()

        # Add station status panels to main menu
        self.ids.station_panel.add_widget(self.app.station.station_status_panel)

        # Add device status panels to main menu
        if self.app.config['Station']['TempestID']:
            self.ids.device_panel.add_widget(self.app.station.tempest_status_panel)
        if self.app.config['Station']['SkyID']:
            self.ids.device_panel.add_widget(self.app.station.sky_status_panel)
        if self.app.config['Station']['OutAirID']:
            self.ids.device_panel.add_widget(self.app.station.out_air_status_panel)
        if self.app.config['Station']['InAirID']:
            self.ids.device_panel.add_widget(self.app.station.in_air_status_panel)

    def on_dismiss(self):

        """ Remove all device status panels from devicePanel Box Layout
        """

        self.ids.station_panel.clear_widgets()
        self.ids.device_panel.clear_widgets()

    def get_station_list(self):

        """ Get list of all stations associated with WeatherFlow key
        """

        URL = 'https://swd.weatherflow.com/swd/rest/stations?token={}'
        URL = URL.format(self.app.config['Keys']['WeatherFlow'])
        UrlRequest(URL,
                   on_success=self.parse_station_list,
                   on_failure=self.fail_station_list,
                   on_error=self.fail_station_list,
                   ca_file=certifi.where()
                   )

    def parse_station_list(self, Request, Response):

        """ Parse list of all stations associated with WeatherFlow key
        """

        if 'status' in Response:
            if 'SUCCESS' in Response['status']['status_message']:
                self.station_details = {}
                for Station in Response['stations']:
                    self.station_details[Station['name'].strip()] = Station
                self.station_list = list(self.station_details.keys())
                self.ids.station_dropdown.text = self.app.config['Station']['Name']

    def fail_station_list(self, Request, Response):

        """ Failed to fetch list of all stations associated with WeatherFlow key
        """

        if isinstance(Response, socket.gaierror):
            self.ids.switch_button.text = 'Host name error. Please try again'
        else:
            self.ids.switch_button.text = f'Error {Request.resp_status}. Please try again'

    def get_station_devices(self):

        """ Get list of all devices associated with currently selected station.
            Initialise device selection dropdowns based on the number and type of
            devices associated with station
        """

        # Reset station data
        self.station_meta_data = {}
        self.device_meta_data  = {}

        # Reset device data
        self.clear_device_list('reset')
        self.tempest_list = []
        self.sky_list     = []
        self.out_air_list = []
        self.in_air_list  = []
        self.retries      = 0

        # Fetch all devices associated with Station
        if self.station_details:
            self.get_station_metadata()
            for station in self.station_details:
                try:
                    for device in self.station_details[station]['devices']:
                        if station == self.ids.station_dropdown.text:
                            if device['device_type'] == 'ST':
                                self.tempest_list.append(device['device_meta']['name'] + ': ' + str(device['device_id']))
                                self.device_meta_data[str(device['device_id'])] = device
                            if device['device_type'] == 'SK':
                                self.sky_list.append(device['device_meta']['name'] + ': ' + str(device['device_id']))
                                self.device_meta_data[str(device['device_id'])] = device
                            if device['device_type'] == 'AR':
                                if device['device_meta']['environment'] == 'outdoor':
                                    self.out_air_list.append(device['device_meta']['name'] + ': ' + str(device['device_id']))
                                    self.device_meta_data[str(device['device_id'])] = device
                                elif device['device_meta']['environment'] == 'indoor':
                                    self.in_air_list.append(device['device_meta']['name'] + ': ' + str(device['device_id']))
                                    self.device_meta_data[str(device['device_id'])] = device
                        else:
                            if device['device_type'] == 'AR' and device['device_meta']['environment'] == 'indoor':
                                self.in_air_list.append(device['device_meta']['name'] + ': ' + str(device['device_id']))
                                self.device_meta_data[str(device['device_id'])] = device
                except KeyError:
                    pass

        # Initialise device selection dropdowns based on the number and type of
        # devices associated with the station.
        # [1] Tempest AND (Sky OR Outdoor Air)
        if self.tempest_list and (self.sky_list or self.out_air_list):
            self.ids.tempest_dropdown.disabled = 0
            self.tempest_list.insert(len(self.tempest_list), 'Clear')
            if (self.app.config['Station']['TempestID']
                    and self.ids.station_dropdown.text == self.app.config['Station']['Name']):
                for tempest in self.tempest_list:
                    if tempest.split(':')[1].strip() == self.app.config['Station']['TempestID']:
                        self.ids.tempest_dropdown.text = tempest
                self.ids.sky_dropdown.text     = self.ids.out_air_dropdown.text     = 'Tempest selected'
                self.ids.sky_dropdown.disabled = self.ids.out_air_dropdown.disabled = 1
            else:
                self.ids.tempest_dropdown.text = 'Please select'

                if self.sky_list:
                    if (self.app.config['Station']['SkyID']
                            and self.ids.station_dropdown.text == self.app.config['Station']['Name']):
                        self.ids.sky_dropdown.disabled = 0
                        for sky in self.sky_list:
                            if sky.split(':')[1].strip() == self.app.config['Station']['SkyID']:
                                self.ids.sky_dropdown.text = sky
                        self.ids.tempest_dropdown.text = 'Sky selected'
                        self.ids.tempest_dropdown.disabled = 0
                    else:
                        self.ids.sky_dropdown.text = 'Please select'
                        self.ids.sky_dropdown.disabled = 0
                    self.sky_list.insert(len(self.sky_list), 'Clear')
                else:
                    self.ids.sky_dropdown.text = 'No device available'
                    self.ids.sky_dropdown.disabled = 1

                if self.out_air_list:
                    if (self.app.config['Station']['OutAirID']
                            and self.ids.station_dropdown.text == self.app.config['Station']['Name']):
                        self.ids.out_air_dropdown.disabled = 0
                        for air in self.out_air_list:
                            if air.split(':')[1].strip() == self.app.config['Station']['OutAirID']:
                                self.ids.out_air_dropdown.text = air
                        self.ids.tempest_dropdown.text = 'Air selected'
                        self.ids.tempest_dropdown.disabled = 0
                    else:
                        self.ids.out_air_dropdown.text = 'Please select'
                        self.ids.out_air_dropdown.disabled = 0
                    self.out_air_list.insert(len(self.out_air_list), 'Clear')
                else:
                    self.ids.out_air_dropdown.text = 'No device available'
                    self.ids.out_air_dropdown.disabled = 1

        # [2] Tempest ONLY
        elif self.tempest_list:
            self.ids.tempest_dropdown.disabled = 0
            self.ids.out_air_dropdown.disabled = self.ids.sky_dropdown.disabled = 1
            self.ids.out_air_dropdown.text     = self.ids.sky_dropdown.text     = 'No device available'
            if (self.app.config['Station']['TempestID']
                    and self.ids.station_dropdown.text == self.app.config['Station']['Name']):
                for tempest in self.tempest_list:
                    if tempest.split(':')[1].strip() == self.app.config['Station']['TempestID']:
                        self.ids.tempest_dropdown.text = tempest
            else:
                self.ids.tempest_dropdown.text = 'Please select'
            self.tempest_list.insert(len(self.tempest_list), 'Clear')

        # [3] Sky OR Outdoor Air ONLY
        elif self.sky_list or self.out_air_list:
            self.ids.tempest_dropdown.disabled = 1
            self.ids.tempest_dropdown.text = 'No device available'

            if self.out_air_list:
                self.ids.out_air_dropdown.disabled = 0
                if (self.app.config['Station']['OutAirID']
                        and self.ids.station_dropdown.text == self.app.config['Station']['Name']):
                    for air in self.out_air_list:
                        if air.split(':')[1].strip() == self.app.config['Station']['OutAirID']:
                            self.ids.out_air_dropdown.text = air
                else:
                    self.ids.out_air_dropdown.text = 'Please select'
                self.out_air_list.insert(len(self.out_air_list), 'Clear')
            else:
                self.ids.out_air_dropdown.text = 'No device available'
                self.ids.out_air_dropdown.disabled = 1

            if self.sky_list:
                self.ids.sky_dropdown.disabled = 0
                if (self.app.config['Station']['SkyID']
                        and self.ids.station_dropdown.text == self.app.config['Station']['Name']):
                    for sky in self.sky_list:
                        if sky.split(':')[1].strip() == self.app.config['Station']['SkyID']:
                            self.ids.sky_dropdown.text = sky
                else:
                    self.ids.sky_dropdown.text = 'Please select'
                self.sky_list.insert(len(self.sky_list), 'Clear')
            else:
                self.ids.sky_dropdown.text = 'No device available'
                self.ids.sky_dropdown.disabled = 1

        # [4] No devices associated with station, or failed to fetch station
        # metadata
        else:
            for device in ['tempest', 'sky', 'out_air']:
                dropdown = getattr(self.ids, device + '_dropdown')
                setattr(dropdown, 'text', 'No device available')
                setattr(dropdown, 'disabled', 1)

        # [5] Indoor Air
        if self.in_air_list:
            self.ids.in_air_dropdown.disabled = 0
            if self.app.config['Station']['InAirID']:
                for air in self.in_air_list:
                    if (air.split(':')[1].strip() == self.app.config['Station']['InAirID']
                            and not self.in_air_cleared):
                        self.ids.in_air_dropdown.text = air
            else:
                self.ids.in_air_dropdown.text = 'Please select'
            self.in_air_list.insert(len(self.in_air_list), 'Clear')
        else:
            self.ids.in_air_dropdown.text = 'No device available'
            self.ids.in_air_dropdown.disabled = 1

    def on_device_selection(self, instance):

        """ Add selected device to device selection list and set the behaviour of
            the device selection dropdowns as the user selects different
            combinations of devices
        """

        instance_id = list(self.ids.keys())[list(self.ids.values()).index(instance)]
        if instance.text == 'Clear':
            self.clear_device_list(instance_id)
            getattr(self.ids, instance_id).text = 'Please select'
            getattr(self.ids, instance_id).disabled = 0
        else:
            device = self.device_meta_data[instance.text.split(':')[1].strip()]
            environment = device['device_meta']['environment']
            if device['device_type'] == 'AR' and environment == 'indoor':
                self.device_list[device['device_type'] + '_in'] = device
            elif device['device_type'] == 'AR' and environment == 'outdoor':
                self.device_list[device['device_type'] + '_out'] = device
            else:
                self.device_list[device['device_type']] = device
            if instance_id == 'tempestDropdown':
                self.ids.sky_dropdown.disabled = self.ids.out_air_dropdown.disabled = 1
                if self.out_air_list:
                    self.ids.out_air_dropdown.text = 'Tempest selected'
                if self.sky_list:
                    self.ids.sky_dropdown.text = 'Tempest selected'
            elif instance_id in ['skyDropdown', 'airDropdown']:
                self.ids.tempest_dropdown.disabled = 1
                if self.tempest_list:
                    self.ids.tempest_dropdown.text = 'Air or Sky selected'
        if self.ids.switch_button.text != 'Fetching Station information':
            self.set_switch_button()

    def clear_device_list(self, device_type):

        for device in list(self.device_list):
            if device_type == 'reset':
                if not device == 'AR_in':
                    self.device_list.pop(device)
            else:
                if device == 'ST' and 'tempest' in device_type:
                    self.device_list.pop(device)
                    break
                elif device == 'SK' and 'sky' in device_type:
                    self.device_list.pop(device)
                    break
                elif device == 'AR_out' and 'outAir' in device_type:
                    self.device_list.pop(device)
                    break
                elif device == 'AR_in' and 'inAir' in device_type:
                    self.device_list.pop(device)
                    self.in_air_cleared = True
                    break

    def get_station_metadata(self):

        """ Get the metadata associated with the selected station
        """

        self.ids.switch_button.text = 'Fetching Station information'
        self.ids.switch_button.disabled = 1
        if hasattr(self, 'pendingRequest'):
            self.pendingRequest.cancel()
        if hasattr(self, 'activeRequest'):
            self.activeRequest.cancel()
        if self.station_details:
            station = self.ids.station_dropdown.text
            URL = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?token={}'
            URL = URL.format(self.station_details[station]['station_id'], App.get_running_app().config['Keys']['WeatherFlow'])
            self.activeRequest = UrlRequest(URL,
                                            on_success=self.parse_station_metadata,
                                            on_failure=self.fail_station_metadata,
                                            on_error=self.fail_station_metadata,
                                            ca_file=certifi.where())

    def parse_station_metadata(self, Request, Response):

        """ Parse the metadata associated with the selected station
        """

        self.retries += 1
        if 'status' in Response:
            if 'SUCCESS' in Response['status']['status_message']:
                self.station_meta_data = Response
            elif self.retries < 3:
                self.ids.switch_button.text = 'Bad response. Retrying...'
                self.pendingRequest = Clock.schedule_once(lambda dt: self.get_station_metadata(), 2)
                return
            else:
                self.ids.switch_button.text = 'Failed to fetch Station information'
                self.ids.switch_button.disabled = 1
                return
        self.set_switch_button()

    def fail_station_metadata(self, Request, Response):

        """ Failed to fetch the metadata associated with the selected station
        """

        self.retries += 1
        if self.retries <= 3:
            self.ids.switch_button.text = 'Bad response. Retrying...'
            Clock.schedule_once(lambda dt: self.get_station_metadata(), 2)
        else:
            self.ids.switch_button.text = 'Failed to fetch Station information'

    def set_switch_button(self):

        """ Set the text of the 'switchButton' based on the status of the
            device selection dropdowns
        """

        new_station = True if self.ids.station_dropdown.text != self.app.config['Station']['Name'] else False
        new_device  = True if ((self.ids.tempest_dropdown.selected
                               and (not self.app.config['Station']['TempestID']
                                    or self.app.config['Station']['TempestID'] not in self.ids.tempest_dropdown.text))
                               or (self.ids.sky_dropdown.selected
                               and (not self.app.config['Station']['SkyID']
                                    or self.app.config['Station']['SkyID']     not in self.ids.sky_dropdown.text))
                               or (self.ids.out_air_dropdown.selected
                               and (not self.app.config['Station']['OutAirID']
                                    or self.app.config['Station']['OutAirID']  not in self.ids.out_air_dropdown.text))
                               or (self.ids.in_air_dropdown.selected
                               and (not self.app.config['Station']['InAirID']
                                    or self.app.config['Station']['InAirID']   not in self.ids.in_air_dropdown.text))) else False
        remove_device = True if ((not self.ids.tempest_dropdown.selected   and self.app.config['Station']['TempestID'])
                                 or (not self.ids.sky_dropdown.selected    and self.app.config['Station']['SkyID'])
                                 or (not self.ids.out_air_dropdown.selected and self.app.config['Station']['OutAirID'])
                                 or (not self.ids.in_air_dropdown.selected  and self.app.config['Station']['InAirID'])) else False
        device_selected = True if (self.ids.tempest_dropdown.selected
                                   or self.ids.sky_dropdown.selected
                                   or self.ids.out_air_dropdown.selected
                                   or self.ids.in_air_dropdown.selected) else False
        if new_station:
            if device_selected or new_device:
                self.ids.switch_button.disabled = 0
                self.ids.switch_button.text = 'Continue'
            else:
                self.ids.switch_button.disabled = 1
                self.ids.switch_button.text = 'Please select devices'
        elif new_device or remove_device:
            self.ids.switch_button.disabled = 0
            self.ids.switch_button.text = 'Continue'
        else:
            if device_selected:
                self.ids.switch_button.disabled = 1
                self.ids.switch_button.text = 'Station & Devices unchanged'
            else:
                self.ids.switch_button.disabled = 1
                self.ids.switch_button.text = 'Please select devices'

    def switchStations(self):

        """ Switch Stations/Devices for the Websocket connection
        """

        self.dismiss(animation=False)
        current_station = self.app.config['Station']['StationID']
        config.switch(self.station_meta_data, self.device_list, self.app.config)
        self.app.obsParser.resetDisplay()
        self.app.websocket_client._switch_device = True
        if current_station != str(self.station_meta_data['station_id']):
            self.app.forecast.reset_forecast()
            self.app.astro.reset_astro()
            self.app.sager.reset_forecast()
