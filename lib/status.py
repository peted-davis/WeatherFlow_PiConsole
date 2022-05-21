""" Contains station status functions required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2022 Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

# Import required library modules
from lib.system              import system
from lib                     import properties

# Import required Kivy modules
from kivy.network.urlrequest import UrlRequest
from kivy.uix.boxlayout      import BoxLayout
from kivy.logger             import Logger
from kivy.uix.widget         import Widget
from kivy.app                import App

# Import required Python modules
from datetime                import datetime
import certifi
import time
import math
import pytz
import re

# Define global variables
NaN = float('NaN')


# ==============================================================================
# Station STATUS CLASS
# ==============================================================================
class station(Widget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status_data = properties.Status()
        self.app = App.get_running_app()
        self.set_status_panels()

    def set_status_panels(self):

        self.station_status_panel = station_status()
        self.tempest_status_panel = tempest_status()
        self.sky_status_panel     = sky_status()
        self.out_air_status_panel = out_air_status()
        self.in_air_status_panel  = in_air_status()

    def get_hub_firmware(self):

        """ Get the hub firmware_revision for the hub associated with the
            Station ID
        """

        URL = 'https://swd.weatherflow.com/swd/rest/stations?token=' + self.app.config['Keys']['WeatherFlow']
        UrlRequest(URL,
                   on_success=self.parse_hub_firmware,
                   on_failure=self.fail_hub_firmware,
                   on_error=self.fail_hub_firmware,
                   timeout=int(self.app.config['System']['Timeout']),
                   ca_file=certifi.where())

    def parse_hub_firmware(self, request, response):

        """ Parse hub firmware_revision from response returned by request.url
        """
        try:
            for station in response['stations']:
                if station['station_id'] == int(self.app.config['Station']['StationID']):
                    for device in station['devices']:
                        if 'device_type' in device:
                            if device['device_type'] == 'HB':
                                self.status_data['hub_firmware'] = device['firmware_revision']
                                self.update_display()
        except Exception:
            pass

    def fail_hub_firmware(self, request, response):

        """ Failed to get hub firmware_revision from response returned by
            request.url
        """

        self.status_data['hub_firmware'] = '[color=d73027ff]Error[/color]'

    def get_observation_count(self):

        """ Get last 24 hour observation count for all devices associated with
            the Station ID
        """

        # Calculate timestamp 24 hours past
        endTime   = int(time.time())
        startTime = endTime - int(3600 * 24)

        # Get device observation counts
        urlList  = []
        Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&token={}'
        if self.app.config['Station']['TempestID']:
            urlList.append(Template.format(self.app.config['Station']['TempestID'], startTime, endTime, self.app.config['Keys']['WeatherFlow']))
        if self.app.config['Station']['SkyID']:
            urlList.append(Template.format(self.app.config['Station']['SkyID'],     startTime, endTime, self.app.config['Keys']['WeatherFlow']))
        if self.app.config['Station']['OutAirID']:
            urlList.append(Template.format(self.app.config['Station']['OutAirID'],  startTime, endTime, self.app.config['Keys']['WeatherFlow']))
        if self.app.config['Station']['InAirID']:
            urlList.append(Template.format(self.app.config['Station']['InAirID'],  startTime, endTime, self.app.config['Keys']['WeatherFlow']))
        for URL in urlList:
            UrlRequest(URL,
                       on_success=self.parse_observation_count,
                       on_failure=self.fail_observation_count,
                       on_error=self.fail_observation_count,
                       timeout=int(self.app.config['System']['Timeout']),
                       ca_file=certifi.where())

    def parse_observation_count(self, request, response):

        """ Parse observation count from response returned by request.url """

        if 'Station' in self.app.config:
            if 'obs' in response and response['obs'] is not None:
                if str(response['device_id']) == self.app.config['Station']['TempestID']:
                    self.status_data['tempest_ob_count'] = str(len(response['obs']))
                elif str(response['device_id']) == self.app.config['Station']['SkyID']:
                    self.status_data['sky_ob_count'] = str(len(response['obs']))
                elif str(response['device_id']) == self.app.config['Station']['OutAirID']:
                    self.status_data['out_air_ob_count'] = str(len(response['obs']))
                elif str(response['device_id']) == self.app.config['Station']['InAirID']:
                    self.status_data['in_air_ob_count'] = str(len(response['obs']))
                self.update_display()

    def fail_observation_count(self, request, response):

        """ Failed to get observation count from response returned by
            request.url
        """

        deviceID = re.search(r'device\/(.*)\?', request.url).group(1)
        if deviceID == self.app.config['Station']['TempestID']:
            self.status_data['tempest_ob_count'] = '[color=d73027ff]Error[/color]'
        elif deviceID == self.app.config['Station']['SkyID']:
            self.status_data['sky_ob_count'] = '[color=d73027ff]Error[/color]'
        elif deviceID == self.app.config['Station']['OutAirID']:
            self.status_data['out_air_ob_count'] = '[color=d73027ff]Error[/color]'
        elif deviceID == self.app.config['Station']['InAirID']:
            self.status_data['in_air_ob_count'] = '[color=d73027ff]Error[/color]'
        self.update_display()

    def get_device_status(self, dt):

        """ Gets the current status of the devices and hub associated with the
            Station ID
        """

        # Define current station timezone
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])

        # Get TEMPEST device status
        if 'obs_st' in self.app.CurrentConditions.Obs:
            latestOb       = self.app.CurrentConditions.Obs['obs_st']['obs'][0]
            sampleTimeDiff = time.time() - latestOb[0]
            deviceVoltage  = float(latestOb[16])
            if sampleTimeDiff < 300 and deviceVoltage > 2.355:
                deviceStatus = '[color=9aba2fff]OK[/color]'
                sampleDelay  = ''
            else:
                if sampleTimeDiff < 3600:
                    sampleDelay = str(math.floor(sampleTimeDiff / 60)) + ' mins ago'
                elif sampleTimeDiff < 7200:
                    sampleDelay = str(math.floor(sampleTimeDiff / 3600)) + ' hour ago'
                elif sampleTimeDiff < 86400:
                    sampleDelay = str(math.floor(sampleTimeDiff / 3600)) + ' hours ago'
                else:
                    sampleDelay = str(math.floor(sampleTimeDiff / 86400)) + ' days ago'
                deviceStatus = '[color=d73027ff]Error[/color]'

            # Store TEMPEST device status variables
            self.status_data['tempest_sample_time'] = datetime.fromtimestamp(latestOb[0], Tz).strftime('%H:%M:%S')
            self.status_data['tempest_last_sample'] = sampleDelay
            self.status_data['tempest_voltage']     = '{:.2f}'.format(deviceVoltage)
            self.status_data['tempest_status']      = deviceStatus

        # Get SKY device status
        if 'obs_sky' in self.app.CurrentConditions.Obs:
            latestOb       = self.app.CurrentConditions.Obs['obs_sky']['obs'][0]
            sampleTimeDiff = time.time() - latestOb[0]
            deviceVoltage  = float(latestOb[8])
            if sampleTimeDiff < 300 and deviceVoltage > 2.0:
                deviceStatus = '[color=9aba2fff]OK[/color]'
                sampleDelay  = ''
            else:
                if sampleTimeDiff < 3600:
                    sampleDelay = str(math.floor(sampleTimeDiff / 60)) + ' mins ago'
                elif sampleTimeDiff < 7200:
                    sampleDelay = str(math.floor(sampleTimeDiff / 3600)) + ' hour ago'
                elif sampleTimeDiff < 86400:
                    sampleDelay = str(math.floor(sampleTimeDiff / 3600)) + ' hours ago'
                else:
                    sampleDelay = str(math.floor(sampleTimeDiff / 86400)) + ' days ago'
                deviceStatus = '[color=d73027ff]Error[/color]'

            # Store SKY device status variables
            self.status_data['sky_sample_time'] = datetime.fromtimestamp(latestOb[0], Tz).strftime('%H:%M:%S')
            self.status_data['sky_last_sample'] = sampleDelay
            self.status_data['sky_voltage']     = '{:.2f}'.format(deviceVoltage)
            self.status_data['sky_status']      = deviceStatus

        # Get outdoor AIR device status
        if 'obs_out_air' in self.app.CurrentConditions.Obs:
            latestOb       = self.app.CurrentConditions.Obs['obs_out_air']['obs'][0]
            sampleTimeDiff = time.time() - latestOb[0]
            deviceVoltage  = float(latestOb[6])
            if sampleTimeDiff < 300 and deviceVoltage > 1.9:
                deviceStatus = '[color=9aba2fff]OK[/color]'
                sampleDelay  = ''
            else:
                if sampleTimeDiff < 3600:
                    sampleDelay = str(math.floor(sampleTimeDiff / 60)) + ' mins ago'
                elif sampleTimeDiff < 7200:
                    sampleDelay = str(math.floor(sampleTimeDiff / 3600)) + ' hour ago'
                elif sampleTimeDiff < 86400:
                    sampleDelay = str(math.floor(sampleTimeDiff / 3600)) + ' hours ago'
                else:
                    sampleDelay = str(math.floor(sampleTimeDiff / 86400)) + ' days ago'
                deviceStatus = '[color=d73027ff]Error[/color]'

            # Store outdoor AIR device status variables
            self.status_data['out_air_sample_time'] = datetime.fromtimestamp(latestOb[0], Tz).strftime('%H:%M:%S')
            self.status_data['out_air_last_sample'] = sampleDelay
            self.status_data['out_air_voltage']     = '{:.2f}'.format(deviceVoltage)
            self.status_data['out_air_status']      = deviceStatus

        # Get indoor AIR device status
        if 'obs_in_air' in self.app.CurrentConditions.Obs:
            latestOb       = self.app.CurrentConditions.Obs['obs_in_air']['obs'][0]
            sampleTimeDiff = time.time() - latestOb[0]
            deviceVoltage  = float(latestOb[6])
            if sampleTimeDiff < 300 and deviceVoltage > 1.9:
                deviceStatus = '[color=9aba2fff]OK[/color]'
                sampleDelay  = ''
            else:
                if sampleTimeDiff < 3600:
                    sampleDelay = str(math.floor(sampleTimeDiff / 60)) + ' mins ago'
                elif sampleTimeDiff < 7200:
                    sampleDelay = str(math.floor(sampleTimeDiff / 3600)) + ' hour ago'
                elif sampleTimeDiff < 86400:
                    sampleDelay = str(math.floor(sampleTimeDiff / 3600)) + ' hours ago'
                else:
                    sampleDelay = str(math.floor(sampleTimeDiff / 86400)) + ' days ago'
                deviceStatus = '[color=d73027ff]Error[/color]'

            # Store AIR device status variables
            self.status_data['in_air_sample_time'] = datetime.fromtimestamp(latestOb[0], Tz).strftime('%H:%M:%S')
            self.status_data['in_air_last_sample'] = sampleDelay
            self.status_data['in_air_voltage']     = '{:.2f}'.format(deviceVoltage)
            self.status_data['in_air_status']      = deviceStatus

        # Set hub status (i.e. station_status) based on device status
        deviceStatus = []
        if 'obs_st' in self.app.CurrentConditions.Obs:
            deviceStatus.append(self.status_data['tempest_status'])
        if 'obs_sky' in self.app.CurrentConditions.Obs:
            deviceStatus.append(self.status_data['sky_status'])
        if 'obs_out_air' in self.app.CurrentConditions.Obs:
            deviceStatus.append(self.status_data['out_air_status'])
        if 'obs_in_air' in self.app.CurrentConditions.Obs:
            deviceStatus.append(self.status_data['in_air_status'])
        if not deviceStatus or all('-' in Status for Status in deviceStatus):
            self.status_data['station_status'] = '-'
        elif all('Error' in Status for Status in deviceStatus):
            self.status_data['station_status'] = 'Offline'
        elif all('OK' in Status for Status in deviceStatus):
            self.status_data['station_status'] = 'Online'
        else:
            self.status_data['station_status'] = 'Error'

        # Update display with new status
        self.update_display()

    def update_display(self):

        """ Update display with new Status variables. Catch ReferenceErrors to
        prevent console crashing
        """

        # Update display values with new derived observations
        reference_error = False
        for Key, Value in list(self.status_data.items()):
            try:
                self.app.CurrentConditions.Status[Key] = Value
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'status: {system().log_time()} - Reference error')
                    reference_error = True


# =============================================================================
# station_status STATUS PANEL CLASS
# =============================================================================
class station_status(BoxLayout):
    pass


# =============================================================================
# [device]_status STATUS PANEL CLASSES
# =============================================================================
class tempest_status(BoxLayout):
    pass


class sky_status(BoxLayout):
    pass


class out_air_status(BoxLayout):
    pass


class in_air_status(BoxLayout):
    pass
