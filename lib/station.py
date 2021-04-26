""" Contains station functions required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2020 Peter Davis

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
from lib import properties

# Import required Python modules
from kivy.network.urlrequest import UrlRequest
from kivy.properties         import DictProperty
from kivy.uix.widget         import Widget
from datetime                import datetime
import certifi
import time
import math
import pytz
import re

# Define global variables
NaN = float('NaN')


# =============================================================================
# DEFINE 'Station' CLASS
# =============================================================================
class Station(Widget):

    Status = DictProperty([])

    def __init__(self, App, **kwargs):
        super(Station, self).__init__(**kwargs)
        self.Status = properties.Status()
        self.app = App

    def get_hubFirmware(self):

        """ Get the hub firmware_revision for the hub associated with the
            Station ID
        """

        URL = 'https://swd.weatherflow.com/swd/rest/stations?token=' + self.app.config['Keys']['WeatherFlow']
        UrlRequest(URL,
                   on_success=self.parse_hubFirmware,
                   on_failure=self.fail_hubFirmware,
                   on_error=self.fail_hubFirmware,
                   timeout=int(self.app.config['System']['Timeout']),
                   ca_file=certifi.where())

    def parse_hubFirmware(self, request, response):

        """ Parse hub firmware_revision from response returned by request.url
        """
        try:
            for station in response['stations']:
                if station['station_id'] == int(self.app.config['Station']['StationID']):
                    for device in station['devices']:
                        if 'device_type' in device:
                            if device['device_type'] == 'HB':
                                self.Status['hubFirmware'] = device['firmware_revision']
        except Exception:
            pass

    def fail_hubFirmware(self, request, response):

        """ Failed to get hub firmware_revision from response returned by
            request.url
        """

        self.Status['hubFirmware'] = '[color=d73027ff]Error[/color]'

    def get_observationCount(self):

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
            urlList.append(Template.format(self.app.config['Station']['OutAirID'],     startTime, endTime, self.app.config['Keys']['WeatherFlow']))
        for URL in urlList:
            UrlRequest(URL,
                       on_success=self.parse_observationCount,
                       on_failure=self.fail_observationCount,
                       on_error=self.fail_observationCount,
                       timeout=int(self.app.config['System']['Timeout']),
                       ca_file=certifi.where())

    def parse_observationCount(self, request, response):

        """ Parse observation count from response returned by request.url """

        if 'Station' in self.app.config:
            if 'obs' in response and response['obs'] is not None:
                if str(response['device_id']) == self.app.config['Station']['TempestID']:
                    self.Status['tempestObCount'] = str(len(response['obs']))
                elif str(response['device_id']) == self.app.config['Station']['SkyID']:
                    self.Status['skyObCount'] = str(len(response['obs']))
                elif str(response['device_id']) == self.app.config['Station']['OutAirID']:
                    self.Status['airObCount'] = str(len(response['obs']))

    def fail_observationCount(self, request, response):

        """ Failed to get observation count from response returned by
            request.url
        """

        deviceID = re.search(r'device\/(.*)\?', request.url).group(1)
        if deviceID == self.app.config['Station']['TempestID']:
            self.Status['tempestObCount'] = '[color=d73027ff]Error[/color]'
        elif deviceID == self.app.config['Station']['SkyID']:
            self.Status['skyObCount'] = '[color=d73027ff]Error[/color]'
        elif deviceID == self.app.config['Station']['OutAirID']:
            self.Status['airObCount'] = '[color=d73027ff]Error[/color]'

    def get_deviceStatus(self, dt):

        """ Gets the current status of the devices and hub associated with the
            Station ID
        """

        # Define current station timezone
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])

        # Get TEMPEST device status
        if 'obs_st' in self.app.CurrentConditions.Obs:
            latestOb       = self.app.CurrentConditions.Obs['obs_st']['obs'][0]
            sampleTimeDiff = time.time() - latestOb[0]
            deviceVoltage = float(latestOb[16])
            if sampleTimeDiff < 300 and deviceVoltage > 2.355:
                deviceStatus = '[color=9aba2fff]OK[/color]'
                sampleDelay = ''
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
            self.Status['tempestSampleTime'] = datetime.fromtimestamp(latestOb[0], Tz).strftime('%H:%M:%S')
            self.Status['tempestLastSample'] = sampleDelay
            self.Status['tempestVoltage']    = '{:.2f}'.format(deviceVoltage)
            self.Status['tempestStatus']     = deviceStatus

        # Get SKY device status
        if 'obs_sky' in self.app.CurrentConditions.Obs:
            latestOb       = self.app.CurrentConditions.Obs['obs_sky']['obs'][0]
            sampleTimeDiff = time.time() - latestOb[0]
            deviceVoltage = float(latestOb[8])
            if sampleTimeDiff < 300 and deviceVoltage > 2.0:
                deviceStatus = '[color=9aba2fff]OK[/color]'
                sampleDelay = ''
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
            self.Status['skySampleTime'] = datetime.fromtimestamp(latestOb[0], Tz).strftime('%H:%M:%S')
            self.Status['skyLastSample'] = sampleDelay
            self.Status['skyVoltage']    = '{:.2f}'.format(deviceVoltage)
            self.Status['skyStatus']     = deviceStatus

        # Get AIR device status
        if 'obs_air' in self.app.CurrentConditions.Obs:
            latestOb       = self.app.CurrentConditions.Obs['obs_air']['obs'][0]
            sampleTimeDiff = time.time() - latestOb[0]
            deviceVoltage = float(latestOb[6])
            if sampleTimeDiff < 300 and deviceVoltage > 1.9:
                deviceStatus = '[color=9aba2fff]OK[/color]'
                sampleDelay = ''
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
            self.Status['outAirSampleTime'] = datetime.fromtimestamp(latestOb[0], Tz).strftime('%H:%M:%S')
            self.Status['outAirLastSample'] = sampleDelay
            self.Status['outAirVoltage']    = '{:.2f}'.format(deviceVoltage)
            self.Status['outAirStatus']     = deviceStatus

        # Set hub status (i.e. stationStatus) based on device status
        deviceStatus = []
        if self.app.config['Station']['TempestID']:
            deviceStatus.append(self.Status['tempestStatus'])
        if self.app.config['Station']['SkyID']:
            deviceStatus.append(self.Status['skyStatus'])
        if self.app.config['Station']['OutAirID']:
            deviceStatus.append(self.Status['airStatus'])
        if all('-' in Status for Status in deviceStatus):
            self.Status['stationStatus'] = '-'
        elif all('Error' in Status for Status in deviceStatus):
            self.Status['stationStatus'] = '[color=d73027ff]Offline[/color]'
        elif all('OK' in Status for Status in deviceStatus):
            self.Status['stationStatus'] = '[color=9aba2fff]Online[/color]'
        else:
            self.Status['stationStatus'] = '[color=d73027ff]Error[/color]'
