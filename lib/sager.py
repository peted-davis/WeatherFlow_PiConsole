''' Returns The Sager Weathercaster forecast required by the Raspberry Pi Python
console for WeatherFlow temperatureest and Smart Home Weather stations.
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

Python code based on BT's Global Sager Weathercaster PHP Scripts For Cumulus by
'Buford T. Justice' / 'BTJustice'
http://www.freewebs.com/btjustice/bt-forecasters.html
2016-08-05
'''

# Import required library modules
from lib.request_api import weatherflow_api, checkwx_api
from lib.system      import system
from lib             import derived_variables as derive
from lib             import properties

# Import required Kivy modules
from kivy.logger import Logger
from kivy.clock  import Clock
from kivy.app    import App

# Import required system modules
from datetime    import datetime, timedelta
import threading
import time      as UNIX
import numpy     as np
import math
import pytz

# Define global variables
NaN = float('NaN')


# Define circular mean
def CircularMean(angles):
    angles = np.radians(angles)
    r = np.nanmean(np.exp(1j * angles))
    return np.angle(r, deg=True) % 360


class sager_forecast():

    def __init__(self):
        self.app = App.get_running_app()
        self.sager_data = properties.Sager()
        self.device_obs = {}

    def reset_forecast(self):

        ''' Reset the Sager Weathercaster forecast when station ID changes
        '''

        # Reset the Sager forecast and schedule new forecast to be generated
        self.sager_data = properties.Sager()
        self.update_display()
        Clock.schedule_once(self.fetch_forecast, 2)

    def fetch_forecast(self, dt):

        """ Generate new Sager Weathercaster forecast based on the current weather
        conditions and the trend in conditions over the previous 6 hours
        """

        # Initialise new thread task to generate Sager forecast
        threading.Thread(target=self.generate_forecast(), daemon=True).start()

    def fail_forecast(self, dt):

        """ Failed to generate the the Sager Weathercaster forecast using the
        current weather conditions and the trend in conditions over the previous
        6 hours. Reschedule fetch_forecast in 60 minutes
        """

        # Update display
        self.update_display()

        # Schedule new Sager forecast to be generated in 60 minutes.
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)
        self.sched_time = Now + timedelta(minutes=60)

        # Schedule next Sager forecast
        seconds_sched = (self.sched_time - Now).total_seconds()
        self.app.Sched.sager.cancel()
        self.app.Sched.sager = Clock.schedule_once(self.fetch_forecast, seconds_sched)

    def schedule_forecast(self, dt):

        ''' Schedules the Sager Weathercaster forecast based on the specified
        SagerInterval
        '''

        # Update display
        self.update_display()

        # Get current time in station timezone
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Calculate next forecast time based on specified interval
        curr_hour = Now.replace(minute=0, second=0, microsecond=0)
        time_list = [curr_hour + timedelta(hours=hour) for hour in range(1, 25)]
        hour_list = [time.hour for time in time_list]
        genr_list = [hour % int(self.app.config['System']['SagerInterval']) for hour in hour_list]
        self.sched_time = time_list[genr_list.index(0)]

        # Schedule next Sager forecast
        secondsSched = (self.sched_time - Now).total_seconds()
        self.app.Sched.sager.cancel()
        self.app.Sched.sager = Clock.schedule_once(self.fetch_forecast, secondsSched)

    def generate_forecast(self):

        ''' Generates the Sager Weathercaster forecast based on the current weather
        conditions and the trend in conditions over the previous 6 hours

        INPUTS:
            sagerDict               Dictionary to hold the forecast information
            app                     wfpiconsole App object

        OUTPUT:
            sagerDict               Dictionary containing the Sager Weathercaster
                                    forecast
        '''

        # Get station timezone, current UNIX timestamp in UTC and time that function
        # was called
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        sched_time = getattr(self, 'sched_time', datetime.now(pytz.utc).astimezone(Tz))

        # Define required station variables for the Sager Weathercaster Forecast
        self.sager_data['Lat']   = float(self.app.config['Station']['Latitude'])

        # Set time format based on user configuration
        if self.app.config['Display']['TimeFormat'] == '12 hr':
            if self.app.config['System']['Hardware'] != 'Other':
                time_format = '%-I:%M %P'
            else:
                time_format = '%I:%M %p'
        else:
            time_format = '%H:%M'

        # If no temperatureest or Sky/Air device combination are available forecast
        # cannot be generated
        if (not self.app.config['Station']['TempestID']
                and not (self.app.config['Station']['SkyID'] and self.app.config['Station']['OutAirID'])):
            self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] No devices available to generate forecast'
            self.sager_data['Issued']   = '-'
            return

        # Get device ID of pressure sensor
        pres_device = self.app.config['Station']['TempestID'] or self.app.config['Station']['OutAirID']

        # If applicable, download wind and rain data from last 6 hours from
        # TEMPEST module. If API call fails, return missing data error message
        if self.app.config['Station']['TempestID']:
            self.device_obs = {}
            self.get_tempest_data(int(UNIX.time()))
            if not self.device_obs:
                self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing TEMPEST data. Forecast will be regenerated in 60 minutes'
                self.sager_data['Issued']   = sched_time.strftime(time_format)
                Clock.schedule_once(self.fail_forecast)
                return

        # If applicable, download wind and rain data from last 6 hours from SKY
        # module. If API call fails, return missing data error message
        elif self.app.config['Station']['SkyID']:
            self.get_sky_data(int(UNIX.time()))
            if not self.device_obs:
                self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing SKY data. Forecast will be regenerated in 60 minutes'
                self.sager_data['Issued']   = sched_time.strftime(time_format)
                Clock.schedule_once(self.fail_forecast)
                return

        # Convert wind and rain data to Numpy arrays, and convert wind speed to
        # miles per hour
        self.device_obs['time']    = np.array(self.device_obs['time'],   dtype=np.int64)
        self.device_obs['wind_speed'] = np.array(self.device_obs['wind_speed'], dtype=np.float64) * 2.23694
        self.device_obs['wind_dir'] = np.array(self.device_obs['wind_dir'], dtype=np.float64)
        self.device_obs['Rain']    = np.array(self.device_obs['Rain'],   dtype=np.float64)

        # Define required wind direction variables for the Sager Weathercaster
        # Forecast
        wind_dir_6h = self.device_obs['wind_dir'][:15]
        wind_dir  = self.device_obs['wind_dir'][-15:]
        if np.all(np.isnan(wind_dir_6h)) or np.all(np.isnan(wind_dir)):
            self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing wind direction data. Forecast will be regenerated in 60 minutes'
            self.sager_data['Issued']   = sched_time.strftime(time_format)
            Clock.schedule_once(self.fail_forecast)
            return
        else:
            self.sager_data['wind_dir_6h'] = CircularMean(wind_dir_6h)
            self.sager_data['wind_dir']    = CircularMean(wind_dir)

        # Define required wind speed variables for the Sager Weathercaster
        # Forecast
        wind_speed_6h = self.device_obs['wind_speed'][:15]
        wind_speed    = self.device_obs['wind_speed'][-15:]
        if np.all(np.isnan(wind_speed_6h)) or np.all(np.isnan(wind_speed)):
            self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing wind speed data. Forecast will be regenerated in 60 minutes'
            self.sager_data['Issued']   = sched_time.strftime(time_format)
            Clock.schedule_once(self.fail_forecast)
            return
        else:
            self.sager_data['wind_speed_6h'] = np.nanmean(wind_speed_6h)
            self.sager_data['wind_speed']  = np.nanmean(wind_speed)

        # Define required rainfall variables for the Sager Weathercaster Forecast
        last_rain = np.where(self.device_obs['Rain'] > 0)[0]
        if last_rain.size == 0:
            self.sager_data['last_rain'] = math.inf
        else:
            last_rain = self.device_obs['time'][last_rain.max()]
            last_rain = datetime.fromtimestamp(last_rain, Tz)
            last_rain = datetime.now(pytz.utc).astimezone(Tz) - last_rain
            self.sager_data['last_rain'] = last_rain.total_seconds() / 60

        # If applicable, download temperature and pressure from last 6 hours
        # from AIR module. If API call fails, return missing data error message
        if self.app.config['Station']['OutAirID']:
            self.get_air_data(int(UNIX.time()))
            if not self.device_obs:
                self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing AIR data. Forecast will be regenerated in 60 minutes'
                self.sager_data['Issued']   = sched_time.strftime(time_format)
                Clock.schedule_once(self.fail_forecast)
                return

        # Convert temperature and pressure data to Numpy arrays
        self.device_obs['time'] = np.array(self.device_obs['time'], dtype=np.int64)
        self.device_obs['pressure'] = np.array(self.device_obs['pressure'], dtype=np.float64)
        self.device_obs['temperature'] = np.array(self.device_obs['temperature'], dtype=np.float64)

        # Define required pressure variables for the Sager Weathercaster
        # Forecast
        pressure_6h = self.device_obs['pressure'][:15]
        pressure    = self.device_obs['pressure'][-15:]
        if np.all(np.isnan(pressure_6h)) or np.all(np.isnan(pressure)):
            self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing pressure data. Forecast will be regenerated in 60 minutes'
            self.sager_data['Issued']   = sched_time.strftime(time_format)
            Clock.schedule_once(self.fail_forecast)
            return
        else:
            self.sager_data['pressure_6h'] = derive.SLP([np.nanmean(pressure_6h).tolist(), 'mb'], pres_device, self.app.config)[0]
            self.sager_data['pressure']  = derive.SLP([np.nanmean(pressure).tolist(), 'mb'],  pres_device, self.app.config)[0]

        # Define required temperature variables for the Sager Weathercaster
        # Forecast
        temperature = self.device_obs['temperature'][-15:]
        if np.all(np.isnan(temperature)):
            self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing temperature data. Forecast will be regenerated in 60 minutes'
            self.sager_data['Issued']   = sched_time.strftime(time_format)
            Clock.schedule_once(self.fail_forecast)
            return
        else:
            self.sager_data['temperature'] = np.nanmean(temperature)

        # Download closet METAR report to station location
        data = checkwx_api.METAR(self.app.config)
        if checkwx_api.verify_response(data, 'data'):
            METAR_data = data.json()['data']
            for METAR in METAR_data:
                if 'clouds' in METAR:
                    self.sager_data['METAR'] = METAR['raw_text']
                    break
        else:
            self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing METAR information. Forecast will be regenerated in 60 minutes'
            self.sager_data['Issued']   = sched_time.strftime(time_format)
            Clock.schedule_once(self.fail_forecast)
            return

        # Derive Sager Weathercaster forecast
        self.get_dial_setting()
        if self.sager_data['Dial'] is not None:
            self.get_forecast_text()
            self.sager_data['Issued']   = sched_time.strftime(time_format)
            Clock.schedule_once(self.schedule_forecast)
        else:
            self.sager_data['Forecast'] = '[color=f05e40ff]ERROR:[/color] Forecast will be regenerated in 60 minutes'
            self.sager_data['Issued']   = sched_time.strftime(time_format)
            Clock.schedule_once(self.fail_forecast)

    def update_display(self):

        """ Update display with new Sager Forecast variables. Catch
        ReferenceErrors to prevent console crashing
        """

        # Update display values with new derived observations
        reference_error = False
        for Key, Value in list(self.sager_data.items()):
            try:
                self.app.CurrentConditions.Sager[Key] = Value
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'sager: {system().log_time()} - Reference error')
                    reference_error = True

    def get_tempest_data(self, Now):

        ''' Fetch TEMPEST data required to generate the Sager Weathercaster
        forecast

        INPUTS:
            Obs                     Dictionary to hold TEMPEST observations
            Now                     Current time as UNIX timestamp
            Config                  Station configuration
        '''

        # Download TEMPEST data from last 6 hours
        data = weatherflow_api.last_6h(self.app.config['Station']['TempestID'], Now, self.app.config)

        # Extract observation times, wind speed, wind direction, and rainfall if API
        # call has not failed
        self.device_obs = {}
        if weatherflow_api.verify_response(data, 'obs'):
            self.device_obs['time']    = [item[0] if item[0]   is not None else NaN for item in data.json()['obs']]
            self.device_obs['wind_speed'] = [item[2] if item[2]   is not None else NaN for item in data.json()['obs']]
            self.device_obs['wind_dir'] = [item[4] if item[4]   is not None else NaN for item in data.json()['obs']]
            self.device_obs['pressure']    = [item[6] if item[6]   is not None else NaN for item in data.json()['obs']]
            self.device_obs['temperature']    = [item[7] if item[7]   is not None else NaN for item in data.json()['obs']]
            self.device_obs['Rain']    = [item[12] if item[12] is not None else NaN for item in data.json()['obs']]

    def get_sky_data(self, Now):

        ''' Fetch SKY data required to generate the Sager Weathercaster
        forecast

        INPUTS:
            Obs                     Dictionary to hold TEMPEST observations
            Now                     Current time as UNIX timestamp
            Config                  Station configuration
        '''

        # Download SKY data from last 6 hours
        data = weatherflow_api.last_6h(self.app.config['Station']['SkyID'], Now, self.app.config)

        # Extract observation times, wind speed, wind direction, and rainfall if API
        # call has not failed
        self.device_obs = {}
        if weatherflow_api.verify_response(data, 'obs'):
            self.device_obs['time']    = [item[0] if item[0] is not None else NaN for item in data.json()['obs']]
            self.device_obs['wind_speed'] = [item[5] if item[5] is not None else NaN for item in data.json()['obs']]
            self.device_obs['wind_dir'] = [item[7] if item[7] is not None else NaN for item in data.json()['obs']]
            self.device_obs['Rain']    = [item[3] if item[3] is not None else NaN for item in data.json()['obs']]

    def get_air_data(self, Now):

        ''' Fetch outdoor AIR data required to generate the Sager Weathercaster
        forecast

        INPUTS:
            Obs                     Dictionary to hold TEMPEST observations
            Now                     Current time as UNIX timestamp
            Config                  Station configuration
        '''

        # Download AIR data from last 6 hours and define AIR dictionary
        data = weatherflow_api.last_6h(self.app.config['Station']['OutAirID'], Now, self.app.config)

        # Extract observation times, pressure and temperature if API # call has not
        # failed
        self.device_obs = {}
        if weatherflow_api.verify_response(data, 'obs'):
            self.device_obs['time'] = [item[0] if item[0] is not None else NaN for item in data.json()['obs']]
            self.device_obs['pressure'] = [item[1] if item[1] is not None else NaN for item in data.json()['obs']]
            self.device_obs['temperature'] = [item[2] if item[2] is not None else NaN for item in data.json()['obs']]

    def get_dial_setting(self):

        ''' Calculates the position of the Sager Weathercaster Dial based on the
        current weather conditions and the trend in conditions over the previous 6
        hours

        INPUTS:
            met_obs:                Dictionary containing the following fields:
                Lat                 Weather observations latitude
                METARKey            Metar Key
                wind_dir_6h            Average wind direction 6 hours ago in degrees
                wind_dir             Current average wind direction in degrees
                wind_speed_6h            Average wind speed 6 hours ago in mph
                wind_speed             Current average wind speed in mph
                pressure                Current atmospheric pressure in hPa
                pressure_6h               Atmospheric pressure 6 hours ago in hPa
                last_rain            Minutes since last rain
                temperature                Current temperature
                METAR               Closet METAR information to station location

        OUTPUT:
            Sager                   Dictionary containing the position of the Sager
                                    Weathercaster Dial
        '''

        # Extract input location/meteorological variables
        Lat   = self.sager_data['Lat']                       # Weather station latitude
        wd6   = self.sager_data['wind_dir_6h']                  # Average wind direction 6 hours ago in degrees
        wd    = self.sager_data['wind_dir']                   # Current average wind direction in degrees
        ws6   = self.sager_data['wind_speed_6h']                  # Average wind speed 6 hours ago in mph
        ws    = self.sager_data['wind_speed']                   # Current average wind speed in mph
        p     = self.sager_data['pressure']                      # Current atmospheric pressure in hPa
        p6    = self.sager_data['pressure_6h']                     # Atmospheric pressure 6 hours ago in hPa
        lr    = self.sager_data['last_rain']                  # Minutes since last rain
        METAR = self.sager_data['METAR']                     # Closet METAR information to station location

        # Define required variables
        ccode  = {}
        pcode  = {}
        pcodes = ['FZDZ', 'FZRA', 'SHGR', 'SHGS', 'SHPL', 'SHRA', 'SHSN', 'TSGR', 'TSGS', 'TSPL', 'TSRA',
                  'TSSN', 'VCSH', 'VCTS', 'DZ', 'GR', 'GS', 'IC', 'PL', 'RA', 'SG', 'SN', 'UP']
        ccodes = ['CAVOK', 'CLR', 'NCD', 'NSC', 'SKC', 'FEW', 'SCT', 'BKN', 'OVC', 'VV']

        # Searches METAR information for Cloud Codes
        Ind = {}
        try:
            for count, code in enumerate(ccodes):
                if METAR.find(code) != -1:
                    Ind[count] = METAR.find(code)
        except Exception:
            return None
        if len(Ind) != 0:
            ccode = ccodes[min(Ind, key=Ind.get)]

        # Searches METAR information for Precipitation Codes
        Ind = {}
        try:
            for count, code in enumerate(pcodes):
                if METAR.find(code) != -1:
                    Ind[count] = METAR.find(code)
        except Exception:
            return None
        if len(Ind) != 0:
            pcode = pcodes[min(Ind, key=Ind.get)]

        # Determines the pressureent Weather result used with The Sager Weathercaster:
        if len(pcode) > 0:
            pw = 'Precipitation'
        if ccode == 'CAVOK' or ccode == 'CLR' or ccode == 'NCD' or ccode == 'NSC' or ccode == 'SKC':
            pw = 'Clear'
        elif ccode == 'FEW' or ccode == 'SCT':
            pw = 'Partly Cloudy'
        elif ccode == 'BKN':
            pw = 'Mostly Cloudy'
        elif ccode == 'OVC':
            pw = 'Overcast'
        elif ccode == 'VV':
            pw = 'Precipitation'
        else:
            pw = None

        # Convert the average wind direction in degrees from 6 hours
        # ago into a direction. An average direction of exactly zero
        # is assumed to indicate calm conditions
        if ws6 <= 1:
            wd6 = 'Calm'
        elif wd6 >= 0 and wd6 < 22.5 or wd6 >= 337.5:
            wd6 = 'N'
        elif wd6 >= 22.5 and wd6 < 67.5:
            wd6 = 'NE'
        elif wd6 >= 67.5 and wd6 < 112.5:
            wd6 = 'E'
        elif wd6 >= 112.5 and wd6 < 157.5:
            wd6 = 'SE'
        elif wd6 >= 157.5 and wd6 < 202.5:
            wd6 = 'S'
        elif wd6 >= 202.5 and wd6 < 247.5:
            wd6 = 'SW'
        elif wd6 >= 247.5 and wd6 < 292.5:
            wd6 = 'W'
        elif wd6 >= 292.5 and wd6 < 337.5:
            wd6 = 'NW'

        # Convert the current average wind direction in degrees into
        # a direction. An average direction of exactly zero is
        # assumed to indicate calm conditions
        if ws <= 1:
            wd = 'Calm'
        elif wd >= 0 and wd < 22.5 or wd >= 337.5:
            wd = 'N'
        elif wd >= 22.5 and wd < 67.5:
            wd = 'NE'
        elif wd >= 67.5 and wd < 112.5:
            wd = 'E'
        elif wd >= 112.5 and wd < 157.5:
            wd = 'SE'
        elif wd >= 157.5 and wd < 202.5:
            wd = 'S'
        elif wd >= 202.5 and wd < 247.5:
            wd = 'SW'
        elif wd >= 247.5 and wd < 292.5:
            wd = 'W'
        elif wd >= 292.5 and wd < 337.5:
            wd = 'NW'

        # Compare the change in wind direction over the last 6 hours
        # to determine if the wind is:
        #   - Backing changing counter-clockwise
        #   - Steady same direction or opposite direction
        #   - Veering changing clockwise
        #   - Calm
        if wd == 'N':
            if wd6 == 'NE' or wd6 == 'E' or wd6 == 'SE':
                wdc = 'Backing'
            elif wd6 == 'N' or wd6 == 'S' or wd6 == 'Calm':
                wdc = 'Steady'
            elif wd6 == 'NW' or wd6 == 'W' or wd6 == 'SW':
                wdc = 'Veering'
        elif wd == 'NE':
            if wd6 == 'E' or wd6 == 'SE' or wd6 == 'S':
                wdc = 'Backing'
            elif wd6 == 'NE' or wd6 == 'SW' or wd6 == 'Calm':
                wdc = 'Steady'
            elif wd6 == 'N' or wd6 == 'NW' or wd6 == 'W':
                wdc = 'Veering'
        elif wd == 'E':
            if wd6 == 'SE' or wd6 == 'S' or wd6 == 'SW':
                wdc = 'Backing'
            elif wd6 == 'E' or wd6 == 'W' or wd6 == 'Calm':
                wdc = 'Steady'
            elif wd6 == 'NE' or wd6 == 'N' or wd6 == 'NW':
                wdc = 'Veering'
        elif wd == 'SE':
            if wd6 == 'S' or wd6 == 'SW' or wd6 == 'W':
                wdc = 'Backing'
            elif wd6 == 'SE' or wd6 == 'NW' or wd6 == 'Calm':
                wdc = 'Steady'
            elif wd6 == 'E' or wd6 == 'NE' or wd6 == 'N':
                wdc = 'Veering'
        elif wd == 'S':
            if wd6 == 'SW' or wd6 == 'W' or wd6 == 'NW':
                wdc = 'Backing'
            elif wd6 == 'S' or wd6 == 'N' or wd6 == 'Calm':
                wdc = 'Steady'
            elif wd6 == 'SE' or wd6 == 'E' or wd6 == 'NE':
                wdc = 'Veering'
        elif wd == 'SW':
            if wd6 == 'W' or wd6 == 'NW' or wd6 == 'N':
                wdc = 'Backing'
            elif wd6 == 'SW' or wd6 == 'NE' or wd6 == 'Calm':
                wdc = 'Steady'
            elif wd6 == 'S' or wd6 == 'SE' or wd6 == 'E':
                wdc = 'Veering'
        elif wd == 'W':
            if wd6 == 'NW' or wd6 == 'N' or wd6 == 'NE':
                wdc = 'Backing'
            elif wd6 == 'W' or wd6 == 'E' or wd6 == 'Calm':
                wdc = 'Steady'
            elif wd6 == 'SW' or wd6 == 'S' or wd6 == 'SE':
                wdc = 'Veering'
        elif wd == 'NW':
            if wd6 == 'N' or wd6 == 'NE' or wd6 == 'E':
                wdc = 'Backing'
            elif wd6 == 'NW' or wd6 == 'SE' or wd6 == 'Calm':
                wdc = 'Steady'
            elif wd6 == 'W' or wd6 == 'SW' or wd6 == 'S':
                wdc = 'Veering'
        elif wd == 'Calm':
            wdc = 'Calm'

        # Determine the Wind Dial position from the current wind direction and whether
        # the change from 6 hours ago is Backing/Steady/Veering/Calm modified by the
        # weather station latitude. The Sager Weathercaster is designed for use in the
        # Northern temperatureerate Zone. The relationship between the wind direction and the
        # setting on the Wind Dial changes with latitude due to the Coriolis effect.

        # Northern Hemisphere: Polar Zone & Tropical Zone
        if Lat >= 0:
            if Lat < 23.5 or Lat >= 66.6:
                if wd == 'S':
                    if wdc == 'Backing':
                        d1 = 'A'
                    elif wdc == 'Steady':
                        d1 = 'B'
                    elif wdc == 'Veering':
                        d1 = 'C'
                elif wd == 'SW':
                    if wdc == 'Backing':
                        d1 = 'D'
                    elif wdc == 'Steady':
                        d1 = 'E'
                    elif wdc == 'Veering':
                        d1 = 'F'
                elif wd == 'W':
                    if wdc == 'Backing':
                        d1 = 'G'
                    elif wdc == 'Steady':
                        d1 = 'H'
                    elif wdc == 'Veering':
                        d1 = 'J'
                elif wd == 'NW':
                    if wdc == 'Backing':
                        d1 = 'K'
                    elif wdc == 'Steady':
                        d1 = 'L'
                    elif wdc == 'Veering':
                        d1 = 'M'
                elif wd == 'N':
                    if wdc == 'Backing':
                        d1 = 'N'
                    elif wdc == 'Steady':
                        d1 = 'O'
                    elif wdc == 'Veering':
                        d1 = 'P'
                elif wd == 'NE':
                    if wdc == 'Backing':
                        d1 = 'Q'
                    elif wdc == 'Steady':
                        d1 = 'R'
                    elif wdc == 'Veering':
                        d1 = 'S'
                elif wd == 'E':
                    if wdc == 'Backing':
                        d1 = 'T'
                    elif wdc == 'Steady':
                        d1 = 'U'
                    elif wdc == 'Veering':
                        d1 = 'V'
                elif wd == 'SE':
                    if wdc == 'Backing':
                        d1 = 'W'
                    elif wdc == 'Steady':
                        d1 = 'X'
                    elif wdc == 'Veering':
                        d1 = 'Y'
                elif wd == 'Calm':
                    d1 = 'Z'

            # Northern Hemisphere: temperatureerate Zone
            elif Lat >= 23.5 and Lat < 66.6:
                if wd == 'N':
                    if wdc == 'Backing':
                        d1 = 'A'
                    elif wdc == 'Steady':
                        d1 = 'B'
                    elif wdc == 'Veering':
                        d1 = 'C'
                elif wd == 'NE':
                    if wdc == 'Backing':
                        d1 = 'D'
                    elif wdc == 'Steady':
                        d1 = 'E'
                    elif wdc == 'Veering':
                        d1 = 'F'
                elif wd == 'E':
                    if wdc == 'Backing':
                        d1 = 'G'
                    elif wdc == 'Steady':
                        d1 = 'H'
                    elif wdc == 'Veering':
                        d1 = 'J'
                elif wd == 'SE':
                    if wdc == 'Backing':
                        d1 = 'K'
                    elif wdc == 'Steady':
                        d1 = 'L'
                    elif wdc == 'Veering':
                        d1 = 'M'
                elif wd == 'S':
                    if wdc == 'Backing':
                        d1 = 'N'
                    elif wdc == 'Steady':
                        d1 = 'O'
                    elif wdc == 'Veering':
                        d1 = 'P'
                elif wd == 'SW':
                    if wdc == 'Backing':
                        d1 = 'Q'
                    elif wdc == 'Steady':
                        d1 = 'R'
                    elif wdc == 'Veering':
                        d1 = 'S'
                elif wd == 'W':
                    if wdc == 'Backing':
                        d1 = 'T'
                    elif wdc == 'Steady':
                        d1 = 'U'
                    elif wdc == 'Veering':
                        d1 = 'V'
                elif wd == 'NW':
                    if wdc == 'Backing':
                        d1 = 'W'
                    elif wdc == 'Steady':
                        d1 = 'X'
                    elif wdc == 'Veering':
                        d1 = 'Y'
                elif wd == 'Calm':
                    d1 = 'Z'

        # Southern Hemisphere: Polar Zone & Tropical Zone
        elif Lat < 0:
            if Lat > -23.5 or Lat <= -66.6:
                if wd == 'N':
                    if wdc == 'Backing':
                        d1 = 'A'
                    elif wdc == 'Steady':
                        d1 = 'B'
                    elif wdc == 'Veering':
                        d1 = 'C'
                elif wd == 'NW':
                    if wdc == 'Backing':
                        d1 = 'D'
                    elif wdc == 'Steady':
                        d1 = 'E'
                    elif wdc == 'Veering':
                        d1 = 'F'
                elif wd == 'W':
                    if wdc == 'Backing':
                        d1 = 'G'
                    elif wdc == 'Steady':
                        d1 = 'H'
                    elif wdc == 'Veering':
                        d1 = 'J'
                elif wd == 'SW':
                    if wdc == 'Backing':
                        d1 = 'K'
                    elif wdc == 'Steady':
                        d1 = 'L'
                    elif wdc == 'Veering':
                        d1 = 'M'
                elif wd == 'S':
                    if wdc == 'Backing':
                        d1 = 'N'
                    elif wdc == 'Steady':
                        d1 = 'O'
                    elif wdc == 'Veering':
                        d1 = 'P'
                elif wd == 'SE':
                    if wdc == 'Backing':
                        d1 = 'Q'
                    elif wdc == 'Steady':
                        d1 = 'R'
                    elif wdc == 'Veering':
                        d1 = 'S'
                elif wd == 'E':
                    if wdc == 'Backing':
                        d1 = 'T'
                    elif wdc == 'Steady':
                        d1 = 'U'
                    elif wdc == 'Veering':
                        d1 = 'V'
                elif wd == 'NE':
                    if wdc == 'Backing':
                        d1 = 'W'
                    elif wdc == 'Steady':
                        d1 = 'X'
                    elif wdc == 'Veering':
                        d1 = 'Y'
                elif wd == 'Calm':
                    d1 = 'Z'

            # Southern Hemisphere: temperatureerate Zone
            elif Lat <= -23.5 and Lat > -66.6:
                if wd == 'S':
                    if wdc == 'Backing':
                        d1 = 'A'
                    elif wdc == 'Steady':
                        d1 = 'B'
                    elif wdc == 'Veering':
                        d1 = 'C'
                elif wd == 'SE':
                    if wdc == 'Backing':
                        d1 = 'D'
                    elif wdc == 'Steady':
                        d1 = 'E'
                    elif wdc == 'Veering':
                        d1 = 'F'
                elif wd == 'E':
                    if wdc == 'Backing':
                        d1 = 'G'
                    elif wdc == 'Steady':
                        d1 = 'H'
                    elif wdc == 'Veering':
                        d1 = 'J'
                elif wd == 'NE':
                    if wdc == 'Backing':
                        d1 = 'K'
                    elif wdc == 'Steady':
                        d1 = 'L'
                    elif wdc == 'Veering':
                        d1 = 'M'
                elif wd == 'N':
                    if wdc == 'Backing':
                        d1 = 'N'
                    elif wdc == 'Steady':
                        d1 = 'O'
                    elif wdc == 'Veering':
                        d1 = 'P'
                elif wd == 'NW':
                    if wdc == 'Backing':
                        d1 = 'Q'
                    elif wdc == 'Steady':
                        d1 = 'R'
                    elif wdc == 'Veering':
                        d1 = 'S'
                elif wd == 'W':
                    if wdc == 'Backing':
                        d1 = 'T'
                    elif wdc == 'Steady':
                        d1 = 'U'
                    elif wdc == 'Veering':
                        d1 = 'V'
                elif wd == 'SW':
                    if wdc == 'Backing':
                        d1 = 'W'
                    elif wdc == 'Steady':
                        d1 = 'X'
                    elif wdc == 'Veering':
                        d1 = 'Y'
                elif wd == 'Calm':
                    d1 = 'Z'

        # Determine the Barometer Dial position from the current atmospheric pressure
        if p >= 1029.5:
            d2 = '1'
        elif p >= 1019.3 and p < 1029.5:
            d2 = '2'
        elif p >= 1012.5 and p < 1019.3:
            d2 = '3'
        elif p >= 1005.8 and p < 1012.5:
            d2 = '4'
        elif p >= 999.0 and p < 1005.8:
            d2 = '5'
        elif p >= 988.8 and p < 999.0:
            d2 = '6'
        elif p >= 975.3 and p < 988.8:
            d2 = '7'
        elif p < 975.3:
            d2 = '8'

        # Determine the Barometer Change Dial position using the current atmospheric
        # pressure trend in hPa/6 hours.
        pt = p - p6
        if pt >= 1.4:                           # Rising Rapidly
            d3 = '1'
        elif pt >= 0.7 and pt < 1.4:            # Rising Slowly
            d3 = '2'
        elif pt < 0.7 and pt > -0.7:            # Normal
            d3 = '3'
        elif pt <= -0.7 and pt > -1.4:          # Falling Slowly
            d3 = '4'
        elif pt <= -1.4:                        # Falling Rapidly
            d3 = '5'

        # Determine the pressureent Weather Dial position using the current weather
        # conditions
        if lr <= 30:
            pw = 'Precipitation'
            d4 = '5'
        elif pw == 'Clear':
            d4 = '1'
        elif pw == 'Partly Cloudy':
            d4 = '2'
        elif pw == 'Mostly Cloudy':
            d4 = '3'
        elif pw == 'Overcast':
            d4 = '4'
        elif pw == 'Precipitation':
            d4 = '5'
        elif pw is None:
            d4 = 'x'

        # Return SagerWeathercaster dial setting as function output
        try:
            self.sager_data['Dial'] = d1 + d2 + d3 + d4
        except Exception:
            return None

    def get_forecast_text(self):

        ''' Gets the Sager Weathercaster Forecast based on the specified Sager
        Weathercaster Dial position

        INPUTS:
            Sager - Dictionary containing the following fields:
                Dial                Weather observations latitude
                Lat                 Weather observations latitude
                temperature                Current temperature

        OUTPUT:
            WeatherPredictionKey - Sager Weathercaster Forecast
        '''

        # Extract Sager Weathercast units, dial settings, station latitude, and
        # temperature
        try:
            Units = self.app.config['Units']['Wind']
            Dial = self.sager_data['Dial']
            Lat  = self.sager_data['Lat']
            t    = self.sager_data['temperature']
        except KeyError:
            return

        # Define precipitation type based on current temperature
        if t <= -1.5:
            fp1 = 'Snow'
            fp2 = 'snow'
        elif t > -1.5 and t < 1.5:
            fp1 = 'Rain or Snow (possibly mixed)'
            fp2 = 'rain or snow (possibly mixed)'
        elif t >= 1.5:
            fp1 = 'Rain'
            fp2 = 'rain'

        # Define Expected Weather as listed in The Sager Weathercaster with
        # modifications based on current temperature
        Expected = [None] * 21
        Expected[0] = 'Fair; '
        Expected[1] = 'Fair and warmer; '
        Expected[2] = 'Fair and cooler; '
        Expected[3] = 'Unsettled; '
        Expected[4] = 'Unsettled and warmer; '
        Expected[5] = 'Unsettled and cooler; '
        Expected[6] = 'Increasing cloudiness or overcast, possibly followed by ' + fp2 + ' or showers; '                    # Possibly added and rain changed to fp2.
        Expected[7] = 'Increasing cloudiness or overcast and warmer, possibly followed by ' + fp2 + ' or showers; '         # Changed from 'Increasing cloudiness or overcast followed by rain or showers and warmer'.
        Expected[8] = 'Showers; '
        Expected[9] = 'Showers and warmer; '
        Expected[10] = 'Showers and cooler; '
        Expected[11] = fp1 + '; '                                                                                           # Rain changed to fp1.
        Expected[12] = fp1 + ' and warmer; '                                                                                # Rain changed to fp1.
        Expected[13] = fp1 + ' and turning cooler then improvement likely in 24 hours; '                                    # Changed from 'Rain and turning cooler; then improvement likely in 24 hours.'.
        Expected[14] = fp1 + ' or showers followed by improvement (within 12 hours); '                                      # Rain changed to fp1.
        Expected[15] = fp1 + ' or showers followed by improvement (within 12 hours) and becoming cooler; '                  # Rain changed to fp1.
        Expected[16] = fp1 + ' or showers followed by improvement early in period (within 6 hours); '                       # Rain changed to fp1.
        Expected[17] = fp1 + ' or showers followed by improvement early in period (within 6 hours) and becoming cooler; '   # Rain changed to fp1.
        Expected[18] = fp1 + ' or showers followed by fair early in period (within 6 hours) and becoming cooler; '          # Rain changed to fp1.
        Expected[19] = 'Unsettled followed by fair; '
        Expected[20] = 'Unsettled followed by fair early in period (within 6 hours) and becoming cooler; '

        # Define Wind Velocities as listed in The Sager Weathercaster with
        # modifications based on Beaufort Scale terminology and users choice of wind
        # speed units
        Wind = [None] * 8
        if Units in ['mph', 'lfm']:
            Wind[0] = 'Wind probably increasing. '
            Wind[1] = 'Wind moderate to fresh (13-24 mph). '                                                                    # Changed from 'Moderate to fresh'.
            Wind[2] = 'Wind strong to near gale (25-38 mph). '                                                                  # Changed from 'Strong'.
            Wind[3] = 'Wind gale to strong gale (39-54 mph). '                                                                  # Changed from 'Gale'.
            Wind[4] = 'Wind storm to violent storm (55-73 mph). '                                                               # Changed from 'Dangerous gale (whole gale)'.
            Wind[5] = 'Wind hurricane (74+ mph). '
            Wind[6] = 'Wind diminishing, or moderating somewhat if current winds are of fresh to strong velocity. '
            Wind[7] = 'Wind unchanged. Some tendency for slight increase during day, diminishing in evening. '
        elif Units == 'kph':
            Wind[0] = 'Wind probably increasing. '
            Wind[1] = 'Wind moderate to fresh (20-39 km/h). '
            Wind[2] = 'Wind strong to near gale (40-61 km/h). '
            Wind[3] = 'Wind gale to strong gale (62-88 km/h). '
            Wind[4] = 'Wind storm to violent storm (89-117 km/h). '
            Wind[5] = 'Wind hurricane (118+ km/h). '
            Wind[6] = 'Wind diminishing, or moderating somewhat if current winds are of fresh to strong velocity. '
            Wind[7] = 'Wind unchanged. Some tendency for slight increase during day, diminishing in evening. '
        elif Units == 'kts':
            Wind[0] = 'Wind probably increasing. '
            Wind[1] = 'Wind moderate to fresh (11-21 kts). '
            Wind[2] = 'Wind strong to near gale (22-33 kts). '
            Wind[3] = 'Wind gale to strong gale (34-47 kts). '
            Wind[4] = 'Wind storm to violent storm (47-63 kts). '
            Wind[5] = 'Wind hurricane (64+ kts). '
            Wind[6] = 'Wind diminishing, or moderating somewhat if current winds are of fresh to strong velocity. '
            Wind[7] = 'Wind unchanged. Some tendency for slight increase during day, diminishing in evening. '
        elif Units == 'bft':
            Wind[0] = 'Wind probably increasing. '
            Wind[1] = 'Wind moderate to fresh (4-5 bft). '
            Wind[2] = 'Wind strong to near gale (6-7 bft). '
            Wind[3] = 'Wind gale to strong gale (8-9 bft). '
            Wind[4] = 'Wind storm to violent storm (10-11 bft). '
            Wind[5] = 'Wind hurricane (12+ bft). '
            Wind[6] = 'Wind diminishing, or moderating somewhat if current winds are of fresh to strong velocity. '
            Wind[7] = 'Wind unchanged. Some tendency for slight increase during day, diminishing in evening. '
        elif Units == 'mps':
            Wind[0] = 'Wind probably increasing. '
            Wind[1] = 'Wind moderate to fresh (5.5-10.7 m/s). '
            Wind[2] = 'Wind strong to near gale (10.8-17.1 m/s). '
            Wind[3] = 'Wind gale to strong gale (17.2-24.4 m/s). '
            Wind[4] = 'Wind storm to violent storm (24.5-32.6 m/s). '
            Wind[5] = 'Wind hurricane (32.7+ m/s). '
            Wind[6] = 'Wind diminishing, or moderating somewhat if current winds are of fresh to strong velocity. '
            Wind[7] = 'Wind unchanged. Some tendency for slight increase during day, diminishing in evening. '

        # Define Wind Direction as listed in The Sager Weathercaster with
        # modifications based on latitude of station
        # Northern Hemisphere: Polar & Tropical Zone
        Direction = [None] * 9
        if Lat >= 0:
            if Lat < 23.5 or Lat >= 66.6:
                Direction[0] = 'South or southwest'
                Direction[1] = 'Southwest or west'
                Direction[2] = 'West or northwest'
                Direction[3] = 'Northwest or north'
                Direction[4] = 'North or northeast'
                Direction[5] = 'Northeast or east'
                Direction[6] = 'East or Southeast'
                Direction[7] = 'Southeast or south'
                Direction[8] = 'Shifting (or variable)'

            # Northern Hemisphere: temperatureerate Zone
            elif Lat >= 23.5 and Lat < 66.6:
                Direction[0] = 'North or northeast'
                Direction[1] = 'Northeast or east'
                Direction[2] = 'East or southeast'
                Direction[3] = 'Southeast or south'
                Direction[4] = 'South or southwest'
                Direction[5] = 'Southwest or west'
                Direction[6] = 'West or northwest'
                Direction[7] = 'Northwest or north'
                Direction[8] = 'Shifting (or variable)'

        # Southern Hemisphere: Polar & Tropical Zone
        elif Lat < 0:
            if Lat > -23.5 or Lat <= -66.6:
                Direction[0] = 'North or northwest'
                Direction[1] = 'Northwest or west'
                Direction[2] = 'West or southwest'
                Direction[3] = 'Southwest or south'
                Direction[4] = 'South or southeast'
                Direction[5] = 'Southeast or east'
                Direction[6] = 'East or northeast'
                Direction[7] = 'Northeast or north'
                Direction[8] = 'Shifting (or variable)'

            # Southern Hemisphere: temperatureerate Zone
            elif Lat <= -23.5 and Lat > -66.6:
                Direction[0] = 'South or southeast'
                Direction[1] = 'Southeast or east'
                Direction[2] = 'East or northeast'
                Direction[3] = 'Northeast or north'
                Direction[4] = 'North or northwest'
                Direction[5] = 'Northwest or west'
                Direction[6] = 'West or southwest'
                Direction[7] = 'Southwest or south'
                Direction[8] = 'Shifting (or variable)'

        # Define the forecast for each Sager Weather Prediction Key
        AD1 = Expected[0] + Wind[6] + Direction[0] + '.'
        AD6 = Expected[0] + Wind[6] + Direction[5] + '.'
        AD7 = Expected[0] + Wind[6] + Direction[6] + '.'
        AD8 = Expected[0] + Wind[6] + Direction[7] + '.'
        AF1 = Expected[0] + Wind[1] + Direction[0] + '.'
        AF2 = Expected[0] + Wind[1] + Direction[1] + '.'
        AF3 = Expected[0] + Wind[1] + Direction[2] + '.'
        AF4 = Expected[0] + Wind[1] + Direction[3] + '.'
        AF5 = Expected[0] + Wind[1] + Direction[4] + '.'
        AF6 = Expected[0] + Wind[1] + Direction[5] + '.'
        AF7 = Expected[0] + Wind[1] + Direction[6] + '.'
        AF8 = Expected[0] + Wind[1] + Direction[7] + '.'
        AF9 = Expected[0] + Wind[1] + Direction[8] + '.'
        AN6 = Expected[0] + Wind[0] + Direction[5] + '.'
        AN7 = Expected[0] + Wind[0] + Direction[6] + '.'
        AS1 = Expected[0] + Wind[2] + Direction[0] + '.'
        AS2 = Expected[0] + Wind[2] + Direction[1] + '.'
        AS21 = Expected[0] + Wind[2] + Direction[1] + ', becoming ' + Direction[0] + ' later.'
        AU1 = Expected[0] + Wind[7] + Direction[0] + '.'
        AU2 = Expected[0] + Wind[7] + Direction[1] + '.'
        AU3 = Expected[0] + Wind[7] + Direction[2] + '.'
        AU4 = Expected[0] + Wind[7] + Direction[3] + '.'
        AU5 = Expected[0] + Wind[7] + Direction[4] + '.'
        AU6 = Expected[0] + Wind[7] + Direction[5] + '.'
        AU7 = Expected[0] + Wind[7] + Direction[6] + '.'
        AU8 = Expected[0] + Wind[7] + Direction[7] + '.'
        AU9 = Expected[0] + Wind[7] + Direction[8] + '.'
        BD6 = Expected[1] + Wind[6] + Direction[5] + '.'
        BD7 = Expected[1] + Wind[6] + Direction[6] + '.'
        BN4 = Expected[1] + Wind[0] + Direction[3] + '.'
        BN5 = Expected[1] + Wind[0] + Direction[4] + '.'
        BN6 = Expected[1] + Wind[0] + Direction[5] + '.'
        BN7 = Expected[1] + Wind[0] + Direction[6] + '.'
        BN9 = Expected[1] + Wind[0] + Direction[8] + '.'
        BU4 = Expected[1] + Wind[7] + Direction[3] + '.'
        BU5 = Expected[1] + Wind[7] + Direction[4] + '.'
        BU6 = Expected[1] + Wind[7] + Direction[5] + '.'
        BU7 = Expected[1] + Wind[7] + Direction[6] + '.'
        CD8 = Expected[2] + Wind[6] + Direction[7] + '.'
        CF1 = Expected[2] + Wind[1] + Direction[0] + '.'
        CF6 = Expected[2] + Wind[1] + Direction[5] + '.'
        CF7 = Expected[2] + Wind[1] + Direction[6] + '.'
        CF8 = Expected[2] + Wind[1] + Direction[7] + '.'
        CF9 = Expected[2] + Wind[1] + Direction[8] + '.'
        CG7 = Expected[2] + Wind[3] + Direction[6] + '.'
        CG8 = Expected[2] + Wind[3] + Direction[7] + '.'
        CS1 = Expected[2] + Wind[2] + Direction[0] + '.'
        CS6 = Expected[2] + Wind[2] + Direction[5] + '.'
        CS67 = Expected[2] + Wind[2] + Direction[5] + ', becoming ' + Direction[6] + ' later.'
        CS7 = Expected[2] + Wind[2] + Direction[6] + '.'
        CS8 = Expected[2] + Wind[2] + Direction[7] + '.'
        CS9 = Expected[2] + Wind[2] + Direction[8] + '.'
        CU1 = Expected[2] + Wind[7] + Direction[0] + '.'
        CU7 = Expected[2] + Wind[7] + Direction[6] + '.'
        CU8 = Expected[2] + Wind[7] + Direction[7] + '.'
        CW8 = Expected[2] + Wind[4] + Direction[7] + '.'
        DD1 = Expected[3] + Wind[6] + Direction[0] + '.'
        DD6 = Expected[3] + Wind[6] + Direction[5] + '.'
        DD7 = Expected[3] + Wind[6] + Direction[6] + '.'
        DF1 = Expected[3] + Wind[1] + Direction[0] + '.'
        DF2 = Expected[3] + Wind[1] + Direction[1] + '.'
        DF3 = Expected[3] + Wind[1] + Direction[2] + '.'
        DF4 = Expected[3] + Wind[1] + Direction[3] + '.'
        DF5 = Expected[3] + Wind[1] + Direction[4] + '.'
        DF56 = Expected[3] + Wind[1] + Direction[4] + ', becoming ' + Direction[5] + ' later.'
        DF6 = Expected[3] + Wind[1] + Direction[5] + '.'
        DF7 = Expected[3] + Wind[1] + Direction[6] + '.'
        DF8 = Expected[3] + Wind[1] + Direction[7] + '.'
        DF9 = Expected[3] + Wind[1] + Direction[8] + '.'
        DN1 = Expected[3] + Wind[0] + Direction[0] + '.'
        DN2 = Expected[3] + Wind[0] + Direction[1] + '.'
        DN6 = Expected[3] + Wind[0] + Direction[5] + '.'
        DN7 = Expected[3] + Wind[0] + Direction[6] + '.'
        DS1 = Expected[3] + Wind[2] + Direction[0] + '.'
        DS2 = Expected[3] + Wind[2] + Direction[1] + '.'
        DS21 = Expected[3] + Wind[2] + Direction[1] + ', becoming ' + Direction[0] + ' later.'
        DS3 = Expected[3] + Wind[2] + Direction[2] + '.'
        DS4 = Expected[3] + Wind[2] + Direction[3] + '.'
        DS56 = Expected[3] + Wind[2] + Direction[4] + ', becoming ' + Direction[5] + ' later.'
        DU1 = Expected[3] + Wind[7] + Direction[0] + '.'
        DU2 = Expected[3] + Wind[7] + Direction[1] + '.'
        DU3 = Expected[3] + Wind[7] + Direction[2] + '.'
        DU4 = Expected[3] + Wind[7] + Direction[3] + '.'
        DU5 = Expected[3] + Wind[7] + Direction[4] + '.'
        DU6 = Expected[3] + Wind[7] + Direction[5] + '.'
        DU7 = Expected[3] + Wind[7] + Direction[6] + '.'
        DU8 = Expected[3] + Wind[7] + Direction[7] + '.'
        ED6 = Expected[4] + Wind[6] + Direction[5] + '.'
        ED7 = Expected[4] + Wind[6] + Direction[6] + '.'
        EN2 = Expected[4] + Wind[0] + Direction[1] + '.'
        EN3 = Expected[4] + Wind[0] + Direction[2] + '.'
        EN4 = Expected[4] + Wind[0] + Direction[3] + '.'
        EN5 = Expected[4] + Wind[0] + Direction[4] + '.'
        EN6 = Expected[4] + Wind[0] + Direction[5] + '.'
        EN7 = Expected[4] + Wind[0] + Direction[6] + '.'
        EN9 = Expected[4] + Wind[0] + Direction[8] + '.'
        EU4 = Expected[4] + Wind[7] + Direction[3] + '.'
        EU5 = Expected[4] + Wind[7] + Direction[4] + '.'
        EU6 = Expected[4] + Wind[7] + Direction[5] + '.'
        EU7 = Expected[4] + Wind[7] + Direction[6] + '.'
        FF1 = Expected[5] + Wind[1] + Direction[0] + '.'
        FF6 = Expected[5] + Wind[1] + Direction[5] + '.'
        FF7 = Expected[5] + Wind[1] + Direction[6] + '.'
        FF8 = Expected[5] + Wind[1] + Direction[7] + '.'
        FF9 = Expected[5] + Wind[1] + Direction[8] + '.'
        FG67 = Expected[5] + Wind[3] + Direction[5] + ', becoming ' + Direction[6] + ' later.'
        FG7 = Expected[5] + Wind[3] + Direction[6] + '.'
        FG8 = Expected[5] + Wind[3] + Direction[7] + '.'
        FG97 = Expected[5] + Wind[3] + Direction[8] + ', becoming ' + Direction[6] + ' later.'
        FN7 = Expected[5] + Wind[0] + Direction[6] + '.'
        FS1 = Expected[5] + Wind[2] + Direction[0] + '.'
        FS18 = Expected[5] + Wind[2] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        FS6 = Expected[5] + Wind[2] + Direction[5] + '.'
        FS67 = Expected[5] + Wind[2] + Direction[5] + ', becoming ' + Direction[6] + ' later.'
        FS7 = Expected[5] + Wind[2] + Direction[6] + '.'
        FS8 = Expected[5] + Wind[2] + Direction[7] + '.'
        FS9 = Expected[5] + Wind[2] + Direction[8] + '.'
        FU1 = Expected[5] + Wind[7] + Direction[0] + '.'
        FU7 = Expected[5] + Wind[7] + Direction[6] + '.'
        FU8 = Expected[5] + Wind[7] + Direction[7] + '.'
        FW7 = Expected[5] + Wind[4] + Direction[6] + '.'
        FW8 = Expected[5] + Wind[4] + Direction[7] + '.'
        FW97 = Expected[5] + Wind[4] + Direction[8] + ', becoming ' + Direction[6] + ' later.'
        GF1 = Expected[6] + Wind[1] + Direction[0] + '.'
        GF2 = Expected[6] + Wind[1] + Direction[1] + '.'
        GF3 = Expected[6] + Wind[1] + Direction[2] + '.'
        GF4 = Expected[6] + Wind[1] + Direction[3] + '.'
        GF5 = Expected[6] + Wind[1] + Direction[4] + '.'
        GF6 = Expected[6] + Wind[1] + Direction[5] + '.'
        GN1 = Expected[6] + Wind[0] + Direction[0] + '.'
        GN2 = Expected[6] + Wind[0] + Direction[1] + '.'
        GN3 = Expected[6] + Wind[0] + Direction[2] + '.'
        GN4 = Expected[6] + Wind[0] + Direction[3] + '.'
        GN5 = Expected[6] + Wind[0] + Direction[4] + '.'
        GN6 = Expected[6] + Wind[0] + Direction[5] + '.'
        GN7 = Expected[6] + Wind[0] + Direction[6] + '.'
        GN8 = Expected[6] + Wind[0] + Direction[7] + '.'
        GN9 = Expected[6] + Wind[0] + Direction[8] + '.'
        GS1 = Expected[6] + Wind[2] + Direction[0] + '.'
        GS2 = Expected[6] + Wind[2] + Direction[1] + '.'
        GS3 = Expected[6] + Wind[2] + Direction[2] + '.'
        GS4 = Expected[6] + Wind[2] + Direction[3] + '.'
        GU1 = Expected[6] + Wind[7] + Direction[0] + '.'
        GU2 = Expected[6] + Wind[7] + Direction[1] + '.'
        GU3 = Expected[6] + Wind[7] + Direction[2] + '.'
        GU4 = Expected[6] + Wind[7] + Direction[3] + '.'
        HN2 = Expected[7] + Wind[0] + Direction[1] + '.'
        HN3 = Expected[7] + Wind[0] + Direction[2] + '.'
        HN4 = Expected[7] + Wind[0] + Direction[3] + '.'
        HN5 = Expected[7] + Wind[0] + Direction[4] + '.'
        HN6 = Expected[7] + Wind[0] + Direction[5] + '.'
        HN7 = Expected[7] + Wind[0] + Direction[6] + '.'
        HN9 = Expected[7] + Wind[0] + Direction[8] + '.'
        HU4 = Expected[7] + Wind[7] + Direction[3] + '.'
        JD1 = Expected[8] + Wind[6] + Direction[0] + '.'
        JF1 = Expected[8] + Wind[1] + Direction[0] + '.'
        JF2 = Expected[8] + Wind[1] + Direction[1] + '.'
        JF3 = Expected[8] + Wind[1] + Direction[2] + '.'
        JF4 = Expected[8] + Wind[1] + Direction[3] + '.'
        JF5 = Expected[8] + Wind[1] + Direction[4] + '.'
        JF56 = Expected[8] + Wind[1] + Direction[4] + ', becoming ' + Direction[5] + ' later.'
        JF6 = Expected[8] + Wind[1] + Direction[5] + '.'
        JF7 = Expected[8] + Wind[1] + Direction[6] + '.'
        JN1 = Expected[8] + Wind[0] + Direction[0] + '.'
        JN4 = Expected[8] + Wind[0] + Direction[3] + '.'
        JN5 = Expected[8] + Wind[0] + Direction[4] + '.'
        JN6 = Expected[8] + Wind[0] + Direction[5] + '.'
        JN7 = Expected[8] + Wind[0] + Direction[6] + '.'
        JN8 = Expected[8] + Wind[0] + Direction[7] + '.'
        JS1 = Expected[8] + Wind[2] + Direction[0] + '.'
        JS2 = Expected[8] + Wind[2] + Direction[1] + '.'
        JS21 = Expected[8] + Wind[2] + Direction[1] + ', becoming ' + Direction[0] + ' later.'
        JS3 = Expected[8] + Wind[2] + Direction[2] + '.'
        JS4 = Expected[8] + Wind[2] + Direction[3] + '.'
        JS5 = Expected[8] + Wind[2] + Direction[4] + '.'
        JS56 = Expected[8] + Wind[2] + Direction[4] + ', becoming ' + Direction[5] + ' later.'
        JS6 = Expected[8] + Wind[2] + Direction[5] + '.'
        JS9 = Expected[8] + Wind[2] + Direction[8] + '.'
        JU1 = Expected[8] + Wind[7] + Direction[0] + '.'
        JU2 = Expected[8] + Wind[7] + Direction[1] + '.'
        JU3 = Expected[8] + Wind[7] + Direction[2] + '.'
        JU4 = Expected[8] + Wind[7] + Direction[3] + '.'
        JU5 = Expected[8] + Wind[7] + Direction[4] + '.'
        JU6 = Expected[8] + Wind[7] + Direction[5] + '.'
        JU7 = Expected[8] + Wind[7] + Direction[6] + '.'
        KN4 = Expected[9] + Wind[0] + Direction[3] + '.'
        KN5 = Expected[9] + Wind[0] + Direction[4] + '.'
        KN6 = Expected[9] + Wind[0] + Direction[5] + '.'
        KN7 = Expected[9] + Wind[0] + Direction[6] + '.'
        KU4 = Expected[9] + Wind[7] + Direction[3] + '.'
        KU5 = Expected[9] + Wind[7] + Direction[4] + '.'
        KU6 = Expected[9] + Wind[7] + Direction[5] + '.'
        KU7 = Expected[9] + Wind[7] + Direction[6] + '.'
        LF1 = Expected[10] + Wind[1] + Direction[0] + '.'
        LF6 = Expected[10] + Wind[1] + Direction[5] + '.'
        LG1 = Expected[10] + Wind[3] + Direction[0] + '.'
        LG18 = Expected[10] + Wind[3] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        LG21 = Expected[10] + Wind[3] + Direction[1] + ', becoming ' + Direction[0] + ' later.'
        LG28 = Expected[10] + Wind[3] + Direction[1] + ', becoming ' + Direction[7] + ' later.'
        LG3 = Expected[10] + Wind[3] + Direction[2] + '.'
        LG45 = Expected[10] + Wind[3] + Direction[3] + ', becoming ' + Direction[4] + ' later.'
        LG46 = Expected[10] + Wind[3] + Direction[3] + ', becoming ' + Direction[5] + ' later.'
        LG57 = Expected[10] + Wind[3] + Direction[4] + ', becoming ' + Direction[6] + ' later.'
        LG8 = Expected[10] + Wind[3] + Direction[7] + '.'
        LG97 = Expected[10] + Wind[3] + Direction[8] + ', becoming ' + Direction[6] + ' later.'
        LN1 = Expected[10] + Wind[0] + Direction[0] + '.'
        LN8 = Expected[10] + Wind[0] + Direction[7] + '.'
        LS1 = Expected[10] + Wind[2] + Direction[0] + '.'
        LS18 = Expected[10] + Wind[2] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        LS2 = Expected[10] + Wind[2] + Direction[1] + '.'
        LS21 = Expected[10] + Wind[2] + Direction[1] + ', becoming ' + Direction[0] + ' later.'
        LS3 = Expected[10] + Wind[2] + Direction[2] + '.'
        LS45 = Expected[10] + Wind[2] + Direction[3] + ', becoming ' + Direction[4] + ' later.'
        LS56 = Expected[10] + Wind[2] + Direction[4] + ', becoming ' + Direction[5] + ' later.'
        LS57 = Expected[10] + Wind[2] + Direction[4] + ', becoming ' + Direction[6] + ' later.'
        LS6 = Expected[10] + Wind[2] + Direction[5] + '.'
        LS7 = Expected[10] + Wind[2] + Direction[6] + '.'
        LS8 = Expected[10] + Wind[2] + Direction[7] + '.'
        LS9 = Expected[10] + Wind[2] + Direction[8] + '.'
        LW18 = Expected[10] + Wind[4] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        LW28 = Expected[10] + Wind[4] + Direction[1] + ', becoming ' + Direction[7] + ' later.'
        LW3 = Expected[10] + Wind[4] + Direction[2] + '.'
        LW46 = Expected[10] + Wind[4] + Direction[3] + ', becoming ' + Direction[5] + ' later.'
        LW57 = Expected[10] + Wind[4] + Direction[4] + ', becoming ' + Direction[6] + ' later.'
        LW8 = Expected[10] + Wind[4] + Direction[7] + '.'
        LW97 = Expected[10] + Wind[4] + Direction[8] + ', becoming ' + Direction[6] + ' later.'
        MF2 = Expected[11] + Wind[1] + Direction[1] + '.'
        MF3 = Expected[11] + Wind[1] + Direction[2] + '.'
        MN1 = Expected[11] + Wind[0] + Direction[0] + '.'
        MN2 = Expected[11] + Wind[0] + Direction[1] + '.'
        MN3 = Expected[11] + Wind[0] + Direction[2] + '.'
        MN4 = Expected[11] + Wind[0] + Direction[3] + '.'
        MN5 = Expected[11] + Wind[0] + Direction[4] + '.'
        MN9 = Expected[11] + Wind[0] + Direction[8] + '.'
        MS1 = Expected[11] + Wind[2] + Direction[0] + '.'
        MS2 = Expected[11] + Wind[2] + Direction[1] + '.'
        MS3 = Expected[11] + Wind[2] + Direction[2] + '.'
        MS4 = Expected[11] + Wind[2] + Direction[3] + '.'
        MS5 = Expected[11] + Wind[2] + Direction[4] + '.'
        MS56 = Expected[11] + Wind[2] + Direction[4] + ', becoming ' + Direction[5] + ' later.'
        MS9 = Expected[11] + Wind[2] + Direction[8] + '.'
        MU2 = Expected[11] + Wind[7] + Direction[1] + '.'
        MU3 = Expected[11] + Wind[7] + Direction[2] + '.'
        NN2 = Expected[12] + Wind[0] + Direction[1] + '.'
        NN3 = Expected[12] + Wind[0] + Direction[2] + '.'
        NN4 = Expected[12] + Wind[0] + Direction[3] + '.'
        NN5 = Expected[12] + Wind[0] + Direction[4] + '.'
        NN9 = Expected[12] + Wind[0] + Direction[8] + '.'
        PG1 = Expected[13] + Wind[3] + Direction[0] + '.'
        PG18 = Expected[13] + Wind[3] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        PG2 = Expected[13] + Wind[3] + Direction[1] + '.'
        PG21 = Expected[13] + Wind[3] + Direction[1] + ', becoming ' + Direction[0] + ' later.'
        PG28 = Expected[13] + Wind[3] + Direction[1] + ', becoming ' + Direction[7] + ' later.'
        PG3 = Expected[13] + Wind[3] + Direction[2] + '.'
        PG45 = Expected[13] + Wind[3] + Direction[3] + ', becoming ' + Direction[4] + ' later.'
        PG46 = Expected[13] + Wind[3] + Direction[3] + ', becoming ' + Direction[5] + ' later.'
        PG57 = Expected[13] + Wind[3] + Direction[4] + ', becoming ' + Direction[6] + ' later.'
        PG8 = Expected[13] + Wind[3] + Direction[7] + '.'
        PG97 = Expected[13] + Wind[3] + Direction[8] + ', becoming ' + Direction[6] + ' later.'
        PH1 = Expected[13] + Wind[5] + Direction[0] + '.'
        PH18 = Expected[13] + Wind[5] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        PH21 = Expected[13] + Wind[5] + Direction[1] + ', becoming ' + Direction[0] + ' later.'
        PH3 = Expected[13] + Wind[5] + Direction[2] + '.'
        PH46 = Expected[13] + Wind[5] + Direction[3] + ', becoming ' + Direction[5] + ' later.'
        PN1 = Expected[13] + Wind[0] + Direction[0] + '.'
        PS1 = Expected[13] + Wind[2] + Direction[0] + '.'
        PS56 = Expected[13] + Wind[2] + Direction[4] + ', becoming ' + Direction[5] + ' later.'
        PS57 = Expected[13] + Wind[2] + Direction[4] + ', becoming ' + Direction[6] + ' later.'
        PS8 = Expected[13] + Wind[2] + Direction[7] + '.'
        PS9 = Expected[13] + Wind[2] + Direction[8] + '.'
        PW1 = Expected[13] + Wind[4] + Direction[0] + '.'
        PW18 = Expected[13] + Wind[4] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        PW21 = Expected[13] + Wind[4] + Direction[1] + ', becoming ' + Direction[0] + ' later.'
        PW28 = Expected[13] + Wind[4] + Direction[1] + ', becoming ' + Direction[7] + ' later.'
        PW3 = Expected[13] + Wind[4] + Direction[2] + '.'
        PW45 = Expected[13] + Wind[4] + Direction[3] + ', becoming ' + Direction[4] + ' later.'
        PW46 = Expected[13] + Wind[4] + Direction[3] + ', becoming ' + Direction[5] + ' later.'
        PW57 = Expected[13] + Wind[4] + Direction[4] + ', becoming ' + Direction[6] + ' later.'
        PW8 = Expected[13] + Wind[4] + Direction[7] + '.'
        PW97 = Expected[13] + Wind[4] + Direction[8] + ', becoming ' + Direction[6] + ' later.'
        RD1 = Expected[13] + Wind[6] + Direction[0] + '.'
        RD8 = Expected[14] + Wind[6] + Direction[7] + '.'
        RF6 = Expected[14] + Wind[1] + Direction[5] + '.'
        RF7 = Expected[14] + Wind[1] + Direction[6] + '.'
        RF8 = Expected[14] + Wind[1] + Direction[7] + '.'
        RF9 = Expected[14] + Wind[1] + Direction[8] + '.'
        RN7 = Expected[14] + Wind[0] + Direction[6] + '.'
        RU1 = Expected[14] + Wind[7] + Direction[0] + '.'
        RU2 = Expected[14] + Wind[7] + Direction[1] + '.'
        RU5 = Expected[14] + Wind[7] + Direction[4] + '.'
        RU6 = Expected[14] + Wind[7] + Direction[5] + '.'
        RU7 = Expected[14] + Wind[7] + Direction[6] + '.'
        RU8 = Expected[14] + Wind[7] + Direction[7] + '.'
        RU9 = Expected[14] + Wind[7] + Direction[8] + '.'
        SF1 = Expected[15] + Wind[1] + Direction[0] + '.'
        SF56 = Expected[15] + Wind[1] + Direction[4] + ', becoming ' + Direction[5] + ' later.'
        SF6 = Expected[15] + Wind[1] + Direction[5] + '.'
        SF7 = Expected[15] + Wind[1] + Direction[6] + '.'
        SF8 = Expected[15] + Wind[1] + Direction[7] + '.'
        SF9 = Expected[15] + Wind[1] + Direction[8] + '.'
        SG18 = Expected[15] + Wind[3] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        SG57 = Expected[15] + Wind[3] + Direction[4] + ', becoming ' + Direction[6] + ' later.'
        SG67 = Expected[15] + Wind[3] + Direction[5] + ', becoming ' + Direction[6] + ' later.'
        SG7 = Expected[15] + Wind[3] + Direction[6] + '.'
        SG8 = Expected[15] + Wind[3] + Direction[7] + '.'
        SG97 = Expected[15] + Wind[3] + Direction[8] + ', becoming ' + Direction[6] + ' later.'
        SN7 = Expected[15] + Wind[0] + Direction[6] + '.'
        SS1 = Expected[15] + Wind[2] + Direction[0] + '.'
        SS18 = Expected[15] + Wind[2] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        SS56 = Expected[15] + Wind[2] + Direction[4] + ', becoming ' + Direction[5] + ' later.'
        SS57 = Expected[15] + Wind[2] + Direction[4] + ', becoming ' + Direction[6] + ' later.'
        SS6 = Expected[15] + Wind[2] + Direction[5] + '.'
        SS67 = Expected[15] + Wind[2] + Direction[5] + ', becoming ' + Direction[6] + ' later.'
        SS7 = Expected[15] + Wind[2] + Direction[6] + '.'
        SS8 = Expected[15] + Wind[2] + Direction[7] + '.'
        SS9 = Expected[15] + Wind[2] + Direction[8] + '.'
        SU1 = Expected[15] + Wind[7] + Direction[0] + '.'
        SW57 = Expected[15] + Wind[4] + Direction[4] + ', becoming ' + Direction[6] + ' later.'
        SW67 = Expected[15] + Wind[4] + Direction[5] + ', becoming ' + Direction[6] + ' later.'
        SW7 = Expected[15] + Wind[4] + Direction[6] + '.'
        SW8 = Expected[15] + Wind[4] + Direction[7] + '.'
        SW97 = Expected[15] + Wind[4] + Direction[8] + ', becoming ' + Direction[6] + ' later.'
        TD8 = Expected[16] + Wind[6] + Direction[7] + '.'
        TF6 = Expected[16] + Wind[1] + Direction[5] + '.'
        TF7 = Expected[16] + Wind[1] + Direction[6] + '.'
        TF9 = Expected[16] + Wind[1] + Direction[8] + '.'
        TU1 = Expected[16] + Wind[7] + Direction[0] + '.'
        TU6 = Expected[16] + Wind[7] + Direction[5] + '.'
        TU7 = Expected[16] + Wind[7] + Direction[6] + '.'
        TU8 = Expected[16] + Wind[7] + Direction[7] + '.'
        TU9 = Expected[16] + Wind[7] + Direction[8] + '.'
        UD8 = Expected[17] + Wind[6] + Direction[7] + '.'
        UF1 = Expected[17] + Wind[1] + Direction[0] + '.'
        UF6 = Expected[17] + Wind[1] + Direction[5] + '.'
        UF7 = Expected[17] + Wind[1] + Direction[6] + '.'
        UF8 = Expected[17] + Wind[1] + Direction[7] + '.'
        UG7 = Expected[17] + Wind[3] + Direction[6] + '.'
        UG8 = Expected[17] + Wind[3] + Direction[7] + '.'
        US6 = Expected[17] + Wind[2] + Direction[5] + '.'
        US7 = Expected[17] + Wind[2] + Direction[6] + '.'
        US8 = Expected[17] + Wind[2] + Direction[7] + '.'
        UU1 = Expected[17] + Wind[7] + Direction[0] + '.'
        UU8 = Expected[17] + Wind[7] + Direction[7] + '.'
        UW8 = Expected[17] + Wind[4] + Direction[7] + '.'
        WD8 = Expected[18] + Wind[6] + Direction[7] + '.'
        WF7 = Expected[18] + Wind[1] + Direction[6] + '.'
        WF8 = Expected[18] + Wind[1] + Direction[7] + '.'
        WS7 = Expected[18] + Wind[2] + Direction[6] + '.'
        WS8 = Expected[18] + Wind[2] + Direction[7] + '.'
        WU8 = Expected[18] + Wind[7] + Direction[7] + '.'
        XD1 = Expected[19] + Wind[6] + Direction[0] + '.'
        XD7 = Expected[19] + Wind[6] + Direction[6] + '.'
        XD8 = Expected[19] + Wind[6] + Direction[7] + '.'
        XF6 = Expected[19] + Wind[1] + Direction[5] + '.'
        XF7 = Expected[19] + Wind[1] + Direction[6] + '.'
        XF8 = Expected[19] + Wind[1] + Direction[7] + '.'
        XF9 = Expected[19] + Wind[1] + Direction[8] + '.'
        XN7 = Expected[19] + Wind[0] + Direction[6] + '.'
        XS1 = Expected[19] + Wind[2] + Direction[0] + '.'
        XU1 = Expected[19] + Wind[7] + Direction[0] + '.'
        XU6 = Expected[19] + Wind[7] + Direction[5] + '.'
        XU7 = Expected[19] + Wind[7] + Direction[6] + '.'
        XU8 = Expected[19] + Wind[7] + Direction[7] + '.'
        YF1 = Expected[20] + Wind[1] + Direction[0] + '.'
        YF6 = Expected[20] + Wind[1] + Direction[5] + '.'
        YF7 = Expected[20] + Wind[1] + Direction[6] + '.'
        YF8 = Expected[20] + Wind[1] + Direction[7] + '.'
        YF9 = Expected[20] + Wind[1] + Direction[8] + '.'
        YG7 = Expected[20] + Wind[3] + Direction[6] + '.'
        YG8 = Expected[20] + Wind[3] + Direction[7] + '.'
        YS18 = Expected[20] + Wind[2] + Direction[0] + ', becoming ' + Direction[7] + ' later.'
        YS6 = Expected[20] + Wind[2] + Direction[5] + '.'
        YS7 = Expected[20] + Wind[2] + Direction[6] + '.'
        YS8 = Expected[20] + Wind[2] + Direction[7] + '.'
        YS9 = Expected[20] + Wind[2] + Direction[8] + '.'
        YU1 = Expected[20] + Wind[7] + Direction[0] + '.'
        YU7 = Expected[20] + Wind[7] + Direction[6] + '.'
        YU8 = Expected[20] + Wind[7] + Direction[7] + '.'

        # Determine the Sager Weather Prediction Key that corresponds to the
        # current Weather Dial settings
        WeatherPredictionKey = {'A111': CU8,
                                'A112': CU8,
                                'A113': CU8,
                                'A114': CU8,
                                'A115': WU8,
                                'A121': AU8,
                                'A122': AU8,
                                'A123': AU8,
                                'A124': AU8,
                                'A125': TU8,
                                'A131': AD8,
                                'A132': AD8,
                                'A133': AD8,
                                'A134': XD8,
                                'A135': RD8,
                                'A141': AU8,
                                'A142': AU8,
                                'A143': XU8,
                                'A144': DU8,
                                'A145': RU8,
                                'A151': GN8,
                                'A152': GN8,
                                'A153': GN8,
                                'A154': GN8,
                                'A155': JN8,
                                'A211': CU8,
                                'A212': CU8,
                                'A213': CU8,
                                'A214': CU8,
                                'A215': WU8,
                                'A221': AU8,
                                'A222': AU8,
                                'A223': AU8,
                                'A224': AU8,
                                'A225': TU8,
                                'A231': AU8,
                                'A232': AU8,
                                'A233': AU8,
                                'A234': XU8,
                                'A235': RU8,
                                'A241': AU8,
                                'A242': AU8,
                                'A243': XU8,
                                'A244': DU8,
                                'A245': RU8,
                                'A251': GN8,
                                'A252': GN8,
                                'A253': GN8,
                                'A254': GN8,
                                'A255': JN8,
                                'A311': CF8,
                                'A312': CF8,
                                'A313': CF8,
                                'A314': CF8,
                                'A315': WF8,
                                'A321': CU8,
                                'A322': CU8,
                                'A323': CU8,
                                'A324': CU8,
                                'A325': UU8,
                                'A331': AU8,
                                'A332': AU8,
                                'A333': AU8,
                                'A334': XU8,
                                'A335': RU8,
                                'A341': AU8,
                                'A342': AU8,
                                'A343': XU8,
                                'A344': DU8,
                                'A345': RU8,
                                'A351': GN8,
                                'A352': GN8,
                                'A353': GN8,
                                'A354': GN8,
                                'A355': JN8,
                                'A411': CF8,
                                'A412': CF8,
                                'A413': CF8,
                                'A414': CF8,
                                'A415': UF8,
                                'A421': CF8,
                                'A422': CF8,
                                'A423': CF8,
                                'A424': CF8,
                                'A425': UF8,
                                'A431': AF8,
                                'A432': AF8,
                                'A433': AF8,
                                'A434': XF8,
                                'A435': RF8,
                                'A441': AF8,
                                'A442': XF8,
                                'A443': XF8,
                                'A444': DF8,
                                'A445': RF8,
                                'A451': JN8,
                                'A452': JN8,
                                'A453': LN8,
                                'A454': LN8,
                                'A455': LN8,
                                'A511': CS8,
                                'A512': CS8,
                                'A513': CS8,
                                'A514': YS8,
                                'A515': US8,
                                'A521': CF8,
                                'A522': CF8,
                                'A523': CF8,
                                'A524': FF8,
                                'A525': SF8,
                                'A531': CF8,
                                'A532': CF8,
                                'A533': YF8,
                                'A534': FF8,
                                'A535': SF8,
                                'A541': FS8,
                                'A542': FS8,
                                'A543': FS8,
                                'A544': SS8,
                                'A545': SS8,
                                'A551': LS8,
                                'A552': LS8,
                                'A553': LS8,
                                'A554': LS8,
                                'A555': LS8,
                                'A611': CS8,
                                'A612': CS8,
                                'A613': CS8,
                                'A614': FS8,
                                'A615': SS8,
                                'A621': CS8,
                                'A622': CS8,
                                'A623': FS8,
                                'A624': FS8,
                                'A625': SS8,
                                'A631': CS8,
                                'A632': FS8,
                                'A633': FS8,
                                'A634': FS8,
                                'A635': SS8,
                                'A641': FS8,
                                'A642': SS8,
                                'A643': SS8,
                                'A644': SS8,
                                'A645': SS8,
                                'A651': LS8,
                                'A652': LS8,
                                'A653': LS8,
                                'A654': LS8,
                                'A655': LS8,
                                'A711': CG8,
                                'A712': CG8,
                                'A713': FG8,
                                'A714': FG8,
                                'A715': SG8,
                                'A721': CG8,
                                'A722': FG8,
                                'A723': FG8,
                                'A724': SG8,
                                'A725': SG8,
                                'A731': FG8,
                                'A732': FG8,
                                'A733': SG8,
                                'A734': SG8,
                                'A735': SG8,
                                'A741': SG8,
                                'A742': SG8,
                                'A743': SG8,
                                'A744': SG8,
                                'A745': SG8,
                                'A751': SG8,
                                'A752': SG8,
                                'A753': SG8,
                                'A754': SG8,
                                'A755': SG8,
                                'A811': FW8,
                                'A812': FW8,
                                'A813': FW8,
                                'A814': SW8,
                                'A815': SW8,
                                'A821': FW8,
                                'A822': FW8,
                                'A823': SW8,
                                'A824': SW8,
                                'A825': SW8,
                                'A831': SW8,
                                'A832': SW8,
                                'A833': SW8,
                                'A834': SW8,
                                'A835': SW8,
                                'A841': SW8,
                                'A842': SW8,
                                'A843': SW8,
                                'A844': SW8,
                                'A845': SW8,
                                'A851': SW8,
                                'A852': SW8,
                                'A853': SW8,
                                'A854': SW8,
                                'A855': SW8,
                                'B111': AD8,
                                'B112': AD8,
                                'B113': AD8,
                                'B114': AD8,
                                'B115': WD8,
                                'B121': AD8,
                                'B122': AD8,
                                'B123': AD8,
                                'B124': AD8,
                                'B125': TD8,
                                'B131': AD1,
                                'B132': AD1,
                                'B133': AD1,
                                'B134': XD1,
                                'B135': RD1,
                                'B141': AU1,
                                'B142': DU1,
                                'B143': GU1,
                                'B144': GU1,
                                'B145': JU1,
                                'B151': GN1,
                                'B152': GN1,
                                'B153': GN1,
                                'B154': GN1,
                                'B155': MN1,
                                'B211': CU8,
                                'B212': CU8,
                                'B213': CU8,
                                'B214': CU8,
                                'B215': WU8,
                                'B221': CD8,
                                'B222': CD8,
                                'B223': CD8,
                                'B224': CD8,
                                'B225': UD8,
                                'B231': AD1,
                                'B232': AD1,
                                'B233': AD1,
                                'B234': XD1,
                                'B235': RD1,
                                'B241': AU1,
                                'B242': DU1,
                                'B243': GU1,
                                'B244': GU1,
                                'B245': JU1,
                                'B251': GN1,
                                'B252': GN1,
                                'B253': GN1,
                                'B254': GN1,
                                'B255': MN1,
                                'B311': CF8,
                                'B312': CF8,
                                'B313': CF8,
                                'B314': CF8,
                                'B315': WF8,
                                'B321': CU8,
                                'B322': CU8,
                                'B323': CU8,
                                'B324': CU8,
                                'B325': UU8,
                                'B331': AU1,
                                'B332': AU1,
                                'B333': AU1,
                                'B334': XU1,
                                'B335': RU1,
                                'B341': DU1,
                                'B342': DU1,
                                'B343': GU1,
                                'B344': GU1,
                                'B345': JU1,
                                'B351': GN1,
                                'B352': GN1,
                                'B353': GN1,
                                'B354': GN1,
                                'B355': MN1,
                                'B411': CF8,
                                'B412': CF8,
                                'B413': CF8,
                                'B414': CF8,
                                'B415': UF8,
                                'B421': CF8,
                                'B422': CF8,
                                'B423': CF8,
                                'B424': CF8,
                                'B425': UF8,
                                'B431': AU8,
                                'B432': AU8,
                                'B433': AF8,
                                'B434': XF8,
                                'B435': RF8,
                                'B441': DF1,
                                'B442': DF1,
                                'B443': GF1,
                                'B444': JF1,
                                'B445': JF1,
                                'B451': JN1,
                                'B452': JN1,
                                'B453': LN1,
                                'B454': PN1,
                                'B455': PN1,
                                'B511': CS8,
                                'B512': CS8,
                                'B513': CS8,
                                'B514': YS8,
                                'B515': US8,
                                'B521': CF8,
                                'B522': CF8,
                                'B523': CF8,
                                'B524': FF8,
                                'B525': SF8,
                                'B531': CF8,
                                'B532': CF8,
                                'B533': YF8,
                                'B534': FF8,
                                'B535': SF8,
                                'B541': FS8,
                                'B542': LS8,
                                'B543': LS8,
                                'B544': LS8,
                                'B545': LS8,
                                'B551': LS8,
                                'B552': LS8,
                                'B553': LS8,
                                'B554': PS8,
                                'B555': PS8,
                                'B611': CS8,
                                'B612': CS8,
                                'B613': CS8,
                                'B614': FS8,
                                'B615': SS8,
                                'B621': CS8,
                                'B622': CS8,
                                'B623': FS8,
                                'B624': FS8,
                                'B625': SS8,
                                'B631': CS8,
                                'B632': FS8,
                                'B633': FS8,
                                'B634': FS8,
                                'B635': SS8,
                                'B641': SS8,
                                'B642': SS8,
                                'B643': SS8,
                                'B644': SS8,
                                'B645': SS8,
                                'B651': LS8,
                                'B652': LS8,
                                'B653': PS8,
                                'B654': PS8,
                                'B655': PS8,
                                'B711': CG8,
                                'B712': CG8,
                                'B713': FG8,
                                'B714': FG8,
                                'B715': SG8,
                                'B721': CG8,
                                'B722': FG8,
                                'B723': FG8,
                                'B724': SG8,
                                'B725': SG8,
                                'B731': FG8,
                                'B732': SG8,
                                'B733': SG8,
                                'B734': SG8,
                                'B735': SG8,
                                'B741': SG8,
                                'B742': SG8,
                                'B743': SG8,
                                'B744': SG8,
                                'B745': SG8,
                                'B751': LG8,
                                'B752': LG8,
                                'B753': PG8,
                                'B754': PG8,
                                'B755': PG8,
                                'B811': FW8,
                                'B812': FW8,
                                'B813': FW8,
                                'B814': SW8,
                                'B815': SW8,
                                'B821': FW8,
                                'B822': FW8,
                                'B823': SW8,
                                'B824': SW8,
                                'B825': SW8,
                                'B831': SW8,
                                'B832': SW8,
                                'B833': SW8,
                                'B834': SW8,
                                'B835': SW8,
                                'B841': SW8,
                                'B842': SW8,
                                'B843': SW8,
                                'B844': SW8,
                                'B845': SW8,
                                'B851': LW8,
                                'B852': LW8,
                                'B853': PW8,
                                'B854': PW8,
                                'B855': PW8,
                                'C111': CU1,
                                'C112': CU1,
                                'C113': CU1,
                                'C114': CU1,
                                'C115': UU1,
                                'C121': AU1,
                                'C122': AU1,
                                'C123': AU1,
                                'C124': XU1,
                                'C125': RU1,
                                'C131': AD1,
                                'C132': AD1,
                                'C133': AD1,
                                'C134': DD1,
                                'C135': JD1,
                                'C141': AU1,
                                'C142': DU1,
                                'C143': GU1,
                                'C144': GU1,
                                'C145': JU1,
                                'C151': GN1,
                                'C152': GN1,
                                'C153': GN1,
                                'C154': GN1,
                                'C155': MN1,
                                'C211': CU1,
                                'C212': CU1,
                                'C213': CU1,
                                'C214': CU1,
                                'C215': UU1,
                                'C221': CU1,
                                'C222': CU1,
                                'C223': CU1,
                                'C224': YU1,
                                'C225': SU1,
                                'C231': AU1,
                                'C232': AU1,
                                'C233': AU1,
                                'C234': DU1,
                                'C235': JU1,
                                'C241': AU1,
                                'C242': DU1,
                                'C243': GU1,
                                'C244': GU1,
                                'C245': JU1,
                                'C251': GN1,
                                'C252': GN1,
                                'C253': GN1,
                                'C254': GN1,
                                'C255': MN1,
                                'C311': CF1,
                                'C312': CF1,
                                'C313': CF1,
                                'C314': YF1,
                                'C315': UF1,
                                'C321': CU1,
                                'C322': CU1,
                                'C323': CU1,
                                'C324': YU1,
                                'C325': SU1,
                                'C331': AU1,
                                'C332': AU1,
                                'C333': AU1,
                                'C334': DU1,
                                'C335': JU1,
                                'C341': AU1,
                                'C342': DU1,
                                'C343': GU1,
                                'C344': GU1,
                                'C345': JU1,
                                'C351': GN1,
                                'C352': GN1,
                                'C353': GN1,
                                'C354': GN1,
                                'C355': MN1,
                                'C411': CF1,
                                'C412': CF1,
                                'C413': CF1,
                                'C414': YF1,
                                'C415': SF1,
                                'C421': CF1,
                                'C422': CF1,
                                'C423': CF1,
                                'C424': YF1,
                                'C425': SF1,
                                'C431': AF1,
                                'C432': AF1,
                                'C433': YF1,
                                'C434': FF1,
                                'C435': LF1,
                                'C441': DF1,
                                'C442': DF1,
                                'C443': GF1,
                                'C444': LF1,
                                'C445': LF1,
                                'C451': JN1,
                                'C452': JN1,
                                'C453': LN1,
                                'C454': PN1,
                                'C455': PN1,
                                'C511': CS1,
                                'C512': CS1,
                                'C513': CS1,
                                'C514': FS1,
                                'C515': SS1,
                                'C521': CF1,
                                'C522': CF1,
                                'C523': YF1,
                                'C524': FF1,
                                'C525': SF1,
                                'C531': CF1,
                                'C532': YF1,
                                'C533': FF1,
                                'C534': FF1,
                                'C535': SF1,
                                'C541': FS1,
                                'C542': LS1,
                                'C543': LS1,
                                'C544': LS1,
                                'C545': LS1,
                                'C551': LS1,
                                'C552': LS1,
                                'C553': LS1,
                                'C554': PS1,
                                'C555': PS1,
                                'C611': CS8,
                                'C612': CS8,
                                'C613': FS8,
                                'C614': FS8,
                                'C615': SS8,
                                'C621': CS8,
                                'C622': FS8,
                                'C623': SS8,
                                'C624': SS8,
                                'C625': SS8,
                                'C631': FS8,
                                'C632': FS8,
                                'C633': SS8,
                                'C634': SS8,
                                'C635': SS8,
                                'C641': SS8,
                                'C642': SS8,
                                'C643': SS8,
                                'C644': SS8,
                                'C645': SS8,
                                'C651': LS1,
                                'C652': LS1,
                                'C653': LS1,
                                'C654': PS1,
                                'C655': PS1,
                                'C711': FG8,
                                'C712': FG8,
                                'C713': SG8,
                                'C714': SG8,
                                'C715': SG8,
                                'C721': FG8,
                                'C722': FG8,
                                'C723': SG8,
                                'C724': SG8,
                                'C725': SG8,
                                'C731': FG8,
                                'C732': SG8,
                                'C733': SG8,
                                'C734': SG8,
                                'C735': SG8,
                                'C741': SG8,
                                'C742': SG8,
                                'C743': SG8,
                                'C744': SG8,
                                'C745': SG8,
                                'C751': LG1,
                                'C752': LG1,
                                'C753': LG1,
                                'C754': PG1,
                                'C755': PG1,
                                'C811': FW8,
                                'C812': FW8,            # Shown in The Sager Weathercaster as 'B812'.
                                'C813': SW8,
                                'C814': SW8,
                                'C815': SW8,
                                'C821': FW8,
                                'C822': FW8,
                                'C823': SW8,
                                'C824': SW8,
                                'C825': SW8,
                                'C831': SW8,
                                'C832': SW8,
                                'C833': SW8,
                                'C834': SW8,
                                'C835': SW8,
                                'C841': SW8,
                                'C842': SW8,
                                'C843': SW8,
                                'C844': SW8,
                                'C845': SW8,
                                'C851': LW8,
                                'C852': LW8,
                                'C853': LW8,
                                'C854': PW8,
                                'C855': PW8,
                                'D111': AU1,
                                'D112': AU1,
                                'D113': AU1,
                                'D114': AU1,
                                'D115': TU1,
                                'D121': AU1,
                                'D122': AU1,
                                'D123': AU1,
                                'D124': DU1,
                                'D125': RU1,
                                'D131': AU1,
                                'D132': AU1,
                                'D133': AU1,
                                'D134': GU1,
                                'D135': JU1,
                                'D141': DN1,
                                'D142': GN1,
                                'D143': GN1,
                                'D144': GN1,
                                'D145': MN1,
                                'D151': GN1,
                                'D152': GN1,
                                'D153': GN1,
                                'D154': GN1,
                                'D155': MN1,
                                'D211': CU1,
                                'D212': CU1,
                                'D213': CU1,
                                'D214': CU1,
                                'D215': UU1,
                                'D221': AU1,
                                'D222': AU1,
                                'D223': AU1,
                                'D224': DU1,
                                'D225': RU1,
                                'D231': AU1,
                                'D232': AU1,
                                'D233': AU1,
                                'D234': GU1,
                                'D235': JU1,
                                'D241': DN1,
                                'D242': GN1,
                                'D243': GN1,
                                'D244': GN1,
                                'D245': MN1,
                                'D251': GN1,
                                'D252': GN1,
                                'D253': GN1,
                                'D254': GN1,
                                'D255': MN1,
                                'D311': CF1,
                                'D312': CF1,
                                'D313': CF1,
                                'D314': CF1,
                                'D315': UF1,
                                'D321': AU1,
                                'D322': AU1,
                                'D323': AU1,
                                'D324': DU1,
                                'D325': RU1,
                                'D331': AU1,
                                'D332': AU1,
                                'D333': AU1,
                                'D334': GU1,
                                'D335': JU1,
                                'D341': GN1,
                                'D342': GN1,
                                'D343': GN1,
                                'D344': GN1,
                                'D345': MN1,
                                'D351': GN1,
                                'D352': GN1,
                                'D353': GN1,
                                'D354': GN1,
                                'D355': MN1,
                                'D411': CF1,
                                'D412': CF1,
                                'D413': CF1,
                                'D414': YF1,
                                'D415': SF1,
                                'D421': CF1,
                                'D422': CF1,
                                'D423': CF1,
                                'D424': FF1,
                                'D425': SF1,
                                'D431': AF1,
                                'D432': AF1,
                                'D433': AF1,
                                'D434': GF1,
                                'D435': JF1,
                                'D441': GN1,
                                'D442': GN1,
                                'D443': GN1,
                                'D444': MN1,
                                'D445': MN1,
                                'D451': GS1,
                                'D452': MS1,
                                'D453': MS1,
                                'D454': MS1,
                                'D455': MS1,
                                'D511': CS1,
                                'D512': CS1,
                                'D513': CS1,
                                'D514': FS1,
                                'D515': SS1,
                                'D521': CS1,
                                'D522': CS1,
                                'D523': CS1,
                                'D524': FS1,
                                'D525': SS1,
                                'D531': AS1,
                                'D532': XS1,
                                'D533': JS1,
                                'D534': JS1,
                                'D535': JS1,
                                'D541': JS1,
                                'D542': JS1,
                                'D543': MS1,
                                'D544': MS1,
                                'D545': MS1,
                                'D551': MS1,
                                'D552': MS1,
                                'D553': MS1,
                                'D554': MS1,
                                'D555': MS1,
                                'D611': YS18,
                                'D612': YS18,
                                'D613': FS18,
                                'D614': SS18,
                                'D615': SS18,
                                'D621': FS18,
                                'D622': FS18,
                                'D623': FS18,
                                'D624': SS18,
                                'D625': SS18,
                                'D631': LS18,
                                'D632': LS18,
                                'D633': LS18,
                                'D634': LS18,
                                'D635': LS18,
                                'D641': LG18,
                                'D642': PG18,
                                'D643': PG18,
                                'D644': PG18,
                                'D645': PG18,
                                'D651': PG18,
                                'D652': PG18,
                                'D653': PG18,
                                'D654': PG18,
                                'D655': PG18,
                                'D711': SG18,
                                'D712': SG18,
                                'D713': SG18,
                                'D714': SG18,
                                'D715': SG18,
                                'D721': SG18,
                                'D722': SG18,
                                'D723': SG18,
                                'D724': SG18,
                                'D725': SG18,
                                'D731': LG18,
                                'D732': LG18,
                                'D733': LG18,
                                'D734': PG18,
                                'D735': PG18,
                                'D741': PW18,
                                'D742': PW18,
                                'D743': PW18,
                                'D744': PW18,
                                'D745': PW18,
                                'D751': PW18,
                                'D752': PW18,
                                'D753': PW18,
                                'D754': PW18,
                                'D755': PW18,
                                'D811': LW18,
                                'D812': LW18,
                                'D813': LW18,
                                'D814': LW18,
                                'D815': LW18,
                                'D821': LW18,
                                'D822': LW18,
                                'D823': LW18,
                                'D824': LW18,
                                'D825': LW18,
                                'D831': PW18,
                                'D832': PW18,
                                'D833': PW18,
                                'D834': PW18,
                                'D835': PW18,
                                'D841': PW18,
                                'D842': PW18,
                                'D843': PW18,
                                'D844': PW18,
                                'D845': PW18,
                                'D851': PH18,
                                'D852': PH18,
                                'D853': PH18,
                                'D854': PH18,
                                'D855': PH18,
                                'E111': AU1,
                                'E112': AU1,
                                'E113': AU1,
                                'E114': AU1,
                                'E115': TU1,
                                'E121': AU1,
                                'E122': AU1,
                                'E123': AU1,
                                'E124': DU1,
                                'E125': RU1,
                                'E131': AU1,
                                'E132': AU1,
                                'E133': AU1,
                                'E134': GU1,
                                'E135': JU1,
                                'E141': DN2,
                                'E142': GN2,
                                'E143': GN2,
                                'E144': GN2,
                                'E145': MN2,
                                'E151': GN2,
                                'E152': GN2,
                                'E153': GN2,
                                'E154': GN2,
                                'E155': MN2,
                                'E211': CU1,
                                'E212': CU1,
                                'E213': CU1,
                                'E214': CU1,
                                'E215': UU1,
                                'E221': AU1,
                                'E222': AU1,
                                'E223': AU1,
                                'E224': DU1,
                                'E225': RU1,
                                'E231': AU1,
                                'E232': AU1,
                                'E233': AU1,
                                'E234': GU1,
                                'E235': JU1,
                                'E241': DN2,
                                'E242': GN2,
                                'E243': GN2,
                                'E244': GN2,
                                'E245': MN2,
                                'E251': GN2,
                                'E252': GN2,
                                'E253': GN2,
                                'E254': GN2,
                                'E255': MN2,
                                'E311': CF1,
                                'E312': CF1,
                                'E313': CF1,
                                'E314': CF1,
                                'E315': UF1,
                                'E321': AU1,
                                'E322': AU1,
                                'E323': AU1,
                                'E324': DU1,
                                'E325': RU1,
                                'E331': AU1,
                                'E332': AU1,
                                'E333': AU1,
                                'E334': GU1,
                                'E335': JU1,
                                'E341': GN2,
                                'E342': GN2,
                                'E343': GN2,
                                'E344': GN2,
                                'E345': MN2,
                                'E351': GN2,
                                'E352': GN2,
                                'E353': GN2,
                                'E354': GN2,
                                'E355': MN2,
                                'E411': CF1,
                                'E412': CF1,
                                'E413': CF1,
                                'E414': YF1,
                                'E415': SF1,
                                'E421': CF1,
                                'E422': CF1,
                                'E423': CF1,
                                'E424': FF1,
                                'E425': SF1,
                                'E431': AF1,
                                'E432': AF1,
                                'E433': AF1,
                                'E434': GF1,
                                'E435': JF1,
                                'E441': GN2,
                                'E442': GN2,
                                'E443': GN2,
                                'E444': MN2,
                                'E445': MN2,
                                'E451': GS2,
                                'E452': MS2,
                                'E453': MS2,
                                'E454': MS2,
                                'E455': MS2,
                                'E511': CS1,
                                'E512': CS1,
                                'E513': CS1,
                                'E514': FS1,
                                'E515': SS1,
                                'E521': CS1,
                                'E522': CS1,
                                'E523': CS1,
                                'E524': FS1,
                                'E525': SS1,
                                'E531': AS1,
                                'E532': XS1,
                                'E533': JS1,
                                'E534': JS1,
                                'E535': JS1,
                                'E541': JS1,
                                'E542': JS1,
                                'E543': MS1,
                                'E544': MS1,
                                'E545': MS1,
                                'E551': MS2,
                                'E552': MS2,
                                'E553': MS2,
                                'E554': MS2,
                                'E555': MS2,
                                'E611': YS18,
                                'E612': YS18,
                                'E613': FS18,
                                'E614': SS18,
                                'E615': SS18,
                                'E621': FS18,
                                'E622': FS18,
                                'E623': FS18,
                                'E624': SS18,
                                'E625': SS18,
                                'E631': LS18,
                                'E632': LS18,
                                'E633': LS18,
                                'E634': LS18,
                                'E635': LS18,
                                'E641': LG18,
                                'E642': PG18,
                                'E643': PG18,
                                'E644': PG18,
                                'E645': PG18,
                                'E651': PG18,
                                'E652': PG18,
                                'E653': PG18,
                                'E654': PG18,
                                'E655': PG18,
                                'E711': SG18,
                                'E712': SG18,
                                'E713': SG18,
                                'E714': SG18,
                                'E715': SG18,
                                'E721': SG18,
                                'E722': SG18,
                                'E723': SG18,
                                'E724': SG18,
                                'E725': SG18,
                                'E731': LG18,
                                'E732': LG18,
                                'E733': LG18,
                                'E734': PG18,
                                'E735': PG18,
                                'E741': PW18,
                                'E742': PW18,
                                'E743': PW18,
                                'E744': PW18,
                                'E745': PW18,
                                'E751': PW18,
                                'E752': PW18,
                                'E753': PW18,
                                'E754': PW18,
                                'E755': PW18,
                                'E811': LW18,
                                'E812': LW18,
                                'E813': LW18,
                                'E814': LW18,
                                'E815': LW18,
                                'E821': LW18,
                                'E822': LW18,
                                'E823': LW18,
                                'E824': LW18,
                                'E825': LW18,
                                'E831': PW18,
                                'E832': PW18,
                                'E833': PW18,
                                'E834': PW18,
                                'E835': PW18,
                                'E841': PW18,
                                'E842': PW18,
                                'E843': PW18,
                                'E844': PW18,
                                'E845': PW18,
                                'E851': PH18,
                                'E852': PH18,
                                'E853': PH18,
                                'E854': PH18,
                                'E855': PH18,
                                'F111': AU1,
                                'F112': AU1,
                                'F113': AU1,
                                'F114': DU1,
                                'F115': RU1,
                                'F121': AU2,
                                'F122': AU2,
                                'F123': AU2,
                                'F124': DU2,
                                'F125': JU2,
                                'F131': AU2,
                                'F132': AU2,
                                'F133': AU2,
                                'F134': GU2,
                                'F135': JU2,
                                'F141': DN2,
                                'F142': GN2,
                                'F143': GN2,
                                'F144': GN2,
                                'F145': MN2,
                                'F151': GN2,
                                'F152': GN2,
                                'F153': GN2,
                                'F154': GN2,
                                'F155': MN2,
                                'F211': CU1,
                                'F212': CU1,
                                'F213': CU1,
                                'F214': FU1,
                                'F215': SU1,
                                'F221': AU2,
                                'F222': AU2,
                                'F223': AU2,
                                'F224': DU2,
                                'F225': JU2,
                                'F231': AU2,
                                'F232': AU2,
                                'F233': AU2,
                                'F234': GU2,
                                'F235': MU2,
                                'F241': DN2,
                                'F242': GN2,
                                'F243': GN2,
                                'F244': GN2,
                                'F245': MN2,
                                'F251': GN2,
                                'F252': GN2,
                                'F253': GN2,
                                'F254': GN2,
                                'F255': MN2,
                                'F311': CF1,
                                'F312': CF1,
                                'F313': CF1,
                                'F314': FF1,
                                'F315': SF1,
                                'F321': AU1,
                                'F322': AU1,
                                'F323': XU1,
                                'F324': DU1,
                                'F325': JU1,
                                'F331': AU2,
                                'F332': AU2,
                                'F333': DU2,
                                'F334': GU2,
                                'F335': MU2,
                                'F341': GN2,
                                'F342': GN2,
                                'F343': GN2,
                                'F344': GN2,
                                'F345': MN2,
                                'F351': GN2,
                                'F352': GN2,
                                'F353': GN2,
                                'F354': GN2,
                                'F355': MN2,
                                'F411': CF1,
                                'F412': CF1,
                                'F413': FF1,
                                'F414': FF1,
                                'F415': SF1,
                                'F421': CF1,
                                'F422': CF1,
                                'F423': YF1,
                                'F424': FF1,
                                'F425': LF1,
                                'F431': AF2,
                                'F432': AF2,
                                'F433': DF2,
                                'F434': GF2,
                                'F435': MF2,
                                'F441': GN2,
                                'F442': GN2,
                                'F443': GN2,
                                'F444': MN2,
                                'F445': MN2,
                                'F451': GS2,
                                'F452': MS2,
                                'F453': MS2,
                                'F454': MS2,
                                'F455': MS2,
                                'F511': CS1,
                                'F512': CS1,
                                'F513': FS1,
                                'F514': FS1,
                                'F515': SS1,
                                'F521': CS1,
                                'F522': CS1,
                                'F523': FS1,
                                'F524': FS1,
                                'F525': LS1,
                                'F531': AS1,
                                'F532': DS1,
                                'F533': JS1,
                                'F534': JS1,
                                'F535': MS1,
                                'F541': JS2,
                                'F542': JS2,
                                'F543': MS2,
                                'F544': MS2,
                                'F545': MS2,
                                'F551': MS2,
                                'F552': MS2,
                                'F553': MS2,
                                'F554': MS2,
                                'F555': MS2,
                                'F611': FS18,
                                'F612': FS18,
                                'F613': FS18,
                                'F614': SS18,
                                'F615': SS18,
                                'F621': FS18,
                                'F622': FS18,
                                'F623': LS18,
                                'F624': LS18,
                                'F625': LS18,
                                'F631': LS18,
                                'F632': LS18,
                                'F633': LS18,
                                'F634': LS18,
                                'F635': LS18,
                                'F641': LG1,
                                'F642': PG1,
                                'F643': PG1,
                                'F644': PG1,
                                'F645': PG1,
                                'F651': PG1,
                                'F652': PG1,
                                'F653': PG1,
                                'F654': PG1,
                                'F655': PG1,
                                'F711': SG18,
                                'F712': SG18,
                                'F713': SG18,
                                'F714': SG18,
                                'F715': SG18,
                                'F721': LG18,
                                'F722': LG18,
                                'F723': LG18,
                                'F724': LG18,
                                'F725': LG18,
                                'F731': LG18,
                                'F732': LG18,
                                'F733': LG18,
                                'F734': PG18,
                                'F735': PG18,
                                'F741': PW18,
                                'F742': PW18,
                                'F743': PW18,
                                'F744': PW18,
                                'F745': PW18,
                                'F751': PW1,
                                'F752': PW1,
                                'F753': PW1,
                                'F754': PW1,
                                'F755': PW1,
                                'F811': LW18,
                                'F812': LW18,
                                'F813': LW18,
                                'F814': LW18,
                                'F815': LW18,
                                'F821': LW18,
                                'F822': LW18,
                                'F823': LW18,
                                'F824': LW18,
                                'F825': LW18,
                                'F831': PW18,
                                'F832': PW18,
                                'F833': PW18,
                                'F834': PW18,
                                'F835': PW18,
                                'F841': PW18,
                                'F842': PW18,
                                'F843': PW18,
                                'F844': PW18,
                                'F845': PW18,
                                'F851': PH1,
                                'F852': PH1,
                                'F853': PH1,
                                'F854': PH1,
                                'F855': PH1,
                                'G111': AU2,
                                'G112': AU2,
                                'G113': AU2,
                                'G114': DU2,
                                'G115': RU2,
                                'G121': AU2,
                                'G122': AU2,
                                'G123': AU2,
                                'G124': DU2,
                                'G125': JU2,
                                'G131': AU2,
                                'G132': AU2,
                                'G133': DU2,
                                'G134': GU2,
                                'G135': JU2,
                                'G141': EN2,
                                'G142': HN2,
                                'G143': HN2,
                                'G144': HN2,
                                'G145': NN2,
                                'G151': HN2,
                                'G152': HN2,
                                'G153': HN2,
                                'G154': HN2,
                                'G155': NN2,
                                'G211': AU2,
                                'G212': AU2,
                                'G213': AU2,
                                'G214': DU2,
                                'G215': RU2,
                                'G221': AU2,
                                'G222': AU2,
                                'G223': AU2,
                                'G224': DU2,
                                'G225': JU2,
                                'G231': AU2,
                                'G232': AU2,
                                'G233': DU2,
                                'G234': GU2,
                                'G235': JU2,
                                'G241': DN2,
                                'G242': GN2,
                                'G243': GN2,
                                'G244': GN2,
                                'G245': MN2,
                                'G251': GN2,
                                'G252': GN2,
                                'G253': GN2,
                                'G254': GN2,
                                'G255': MN2,
                                'G311': AU2,
                                'G312': AU2,
                                'G313': AU2,
                                'G314': DU2,
                                'G315': RU2,
                                'G321': AU2,
                                'G322': AU2,
                                'G323': AU2,
                                'G324': DU2,
                                'G325': JU2,
                                'G331': AU2,
                                'G332': AU2,
                                'G333': DU2,
                                'G334': GU2,
                                'G335': JU2,
                                'G341': GN2,
                                'G342': GN2,
                                'G343': GN2,
                                'G344': GN2,
                                'G345': MN2,
                                'G351': GN2,
                                'G352': GN2,
                                'G353': GN2,
                                'G354': GN2,
                                'G355': MN2,
                                'G411': AF2,
                                'G412': AF2,
                                'G413': AF2,
                                'G414': DF2,
                                'G415': JF2,
                                'G421': AF2,
                                'G422': AF2,
                                'G423': AF2,
                                'G424': GF2,
                                'G425': JF2,
                                'G431': AF2,
                                'G432': AF2,
                                'G433': DF2,
                                'G434': GF2,
                                'G435': JF2,
                                'G441': GN2,
                                'G442': GN2,
                                'G443': GN2,
                                'G444': MN2,
                                'G445': MN2,
                                'G451': GS2,
                                'G452': MS2,
                                'G453': MS2,
                                'G454': MS2,
                                'G455': MS2,
                                'G511': AS21,
                                'G512': DS21,
                                'G513': JS21,
                                'G514': JS21,
                                'G515': JS21,
                                'G521': DS21,
                                'G522': JS21,
                                'G523': JS21,
                                'G524': JS21,
                                'G525': JS21,
                                'G531': DS21,
                                'G532': JS21,
                                'G533': JS21,
                                'G534': JS21,
                                'G535': JS21,
                                'G541': JS2,
                                'G542': MS2,
                                'G543': MS2,
                                'G544': MS2,
                                'G545': MS2,
                                'G551': MS2,
                                'G552': MS2,
                                'G553': MS2,
                                'G554': MS2,
                                'G555': MS2,
                                'G611': LS21,
                                'G612': LS21,
                                'G613': LS21,
                                'G614': LS21,
                                'G615': LS21,
                                'G621': LS21,
                                'G622': LS21,
                                'G623': LS21,
                                'G624': LS21,
                                'G625': LS21,
                                'G631': LS21,
                                'G632': LS21,
                                'G633': LS21,
                                'G634': LS21,
                                'G635': LS21,
                                'G641': LG21,
                                'G642': PG21,
                                'G643': PG21,
                                'G644': PG21,
                                'G645': PG21,
                                'G651': PG2,
                                'G652': PG2,
                                'G653': PG2,
                                'G654': PG2,
                                'G655': PG2,
                                'G711': LG28,
                                'G712': LG28,
                                'G713': LG28,
                                'G714': LG28,
                                'G715': LG28,
                                'G721': LG28,
                                'G722': LG28,
                                'G723': LG28,
                                'G724': LG28,
                                'G725': LG28,
                                'G731': PG28,
                                'G732': PG28,
                                'G733': PG28,
                                'G734': PG28,
                                'G735': PG28,
                                'G741': PW21,
                                'G742': PW21,
                                'G743': PW21,
                                'G744': PW21,
                                'G745': PW21,
                                'G751': PW21,
                                'G752': PW21,
                                'G753': PW21,
                                'G754': PW21,
                                'G755': PW21,
                                'G811': LW28,
                                'G812': LW28,
                                'G813': LW28,
                                'G814': LW28,
                                'G815': LW28,
                                'G821': PW28,
                                'G822': PW28,
                                'G823': PW28,
                                'G824': PW28,
                                'G825': PW28,
                                'G831': PW28,
                                'G832': PW28,
                                'G833': PW28,
                                'G834': PW28,
                                'G835': PW28,
                                'G841': PW28,
                                'G842': PW28,
                                'G843': PW28,
                                'G844': PW28,
                                'G845': PW28,
                                'G851': PH21,
                                'G852': PH21,
                                'G853': PH21,
                                'G854': PH21,
                                'G855': PH21,
                                'H111': AU2,
                                'H112': AU2,
                                'H113': AU2,
                                'H114': DU2,
                                'H115': RU2,
                                'H121': AU2,
                                'H122': AU2,
                                'H123': AU2,
                                'H124': DU2,
                                'H125': JU2,
                                'H131': AU3,
                                'H132': AU3,
                                'H133': DU3,
                                'H134': GU3,
                                'H135': JU3,
                                'H141': EN3,
                                'H142': HN3,
                                'H143': HN3,
                                'H144': HN3,
                                'H145': NN3,
                                'H151': HN3,
                                'H152': HN3,
                                'H153': HN3,
                                'H154': HN3,
                                'H155': NN3,
                                'H211': AU2,
                                'H212': AU2,
                                'H213': AU2,
                                'H214': DU2,
                                'H215': RU2,
                                'H221': AU2,
                                'H222': AU2,
                                'H223': AU2,
                                'H224': DU2,
                                'H225': JU2,
                                'H231': AU3,
                                'H232': AU3,
                                'H233': DU3,
                                'H234': GU3,
                                'H235': JU3,
                                'H241': EN3,
                                'H242': HN3,
                                'H243': HN3,
                                'H244': HN3,
                                'H245': NN3,
                                'H251': HN3,
                                'H252': HN3,
                                'H253': HN3,
                                'H254': HN3,
                                'H255': NN3,
                                'H311': AU2,
                                'H312': AU2,
                                'H313': AU2,
                                'H314': DU2,
                                'H315': RU2,
                                'H321': AU2,
                                'H322': AU2,
                                'H323': AU2,
                                'H324': DU2,
                                'H325': JU2,
                                'H331': AU3,
                                'H332': AU3,
                                'H333': DU3,
                                'H334': GU3,
                                'H335': JU3,
                                'H341': HN3,
                                'H342': HN3,
                                'H343': HN3,
                                'H344': HN3,
                                'H345': NN3,
                                'H351': GN3,
                                'H352': GN3,
                                'H353': GN3,
                                'H354': GN3,
                                'H355': MN3,
                                'H411': AF2,
                                'H412': AF2,
                                'H413': AF2,
                                'H414': DF2,
                                'H415': JF2,
                                'H421': AF2,
                                'H422': AF2,
                                'H423': AF2,
                                'H424': GF2,
                                'H425': JF2,
                                'H431': AF2,
                                'H432': AF2,
                                'H433': DF2,
                                'H434': GF2,
                                'H435': JF2,
                                'H441': GN3,
                                'H442': GN3,
                                'H443': GN3,
                                'H444': MN3,
                                'H445': MN3,
                                'H451': GS3,
                                'H452': MS3,
                                'H453': MS3,
                                'H454': MS3,
                                'H455': MS3,
                                'H511': AS2,
                                'H512': DS2,
                                'H513': JS2,
                                'H514': JS2,
                                'H515': JS2,
                                'H521': DS2,
                                'H522': JS2,
                                'H523': JS2,
                                'H524': JS2,
                                'H525': JS2,
                                'H531': DS2,
                                'H532': JS2,
                                'H533': JS2,
                                'H534': JS2,
                                'H535': JS2,
                                'H541': JS3,
                                'H542': MS3,
                                'H543': MS3,
                                'H544': MS3,
                                'H545': MS3,
                                'H551': MS3,
                                'H552': MS3,
                                'H553': MS3,
                                'H554': MS3,
                                'H555': MS3,
                                'H611': LS21,
                                'H612': LS21,
                                'H613': LS21,
                                'H614': LS21,
                                'H615': LS21,
                                'H621': LS21,
                                'H622': LS21,
                                'H623': LS21,
                                'H624': LS21,
                                'H625': LS21,
                                'H631': LS21,
                                'H632': LS21,
                                'H633': LS21,
                                'H634': LS21,
                                'H635': LS21,
                                'H641': LG3,
                                'H642': PG3,
                                'H643': PG3,
                                'H644': PG3,
                                'H645': PG3,
                                'H651': PG3,
                                'H652': PG3,
                                'H653': PG3,
                                'H654': PG3,
                                'H655': PG3,
                                'H711': LG3,
                                'H712': LG3,
                                'H713': LG3,
                                'H714': LG3,
                                'H715': LG3,
                                'H721': LG3,
                                'H722': LG3,
                                'H723': LG3,
                                'H724': LG3,
                                'H725': LG3,
                                'H731': PG3,
                                'H732': PG3,
                                'H733': PG3,
                                'H734': PG3,
                                'H735': PG3,
                                'H741': PW3,
                                'H742': PW3,
                                'H743': PW3,
                                'H744': PW3,
                                'H745': PW3,
                                'H751': PW3,
                                'H752': PW3,
                                'H753': PW3,
                                'H754': PW3,
                                'H755': PW3,
                                'H811': LW3,
                                'H812': LW3,
                                'H813': LW3,
                                'H814': LW3,
                                'H815': LW3,
                                'H821': PW3,
                                'H822': PW3,
                                'H823': PW3,
                                'H824': PW3,
                                'H825': PW3,
                                'H831': PW3,
                                'H832': PW3,
                                'H833': PW3,
                                'H834': PW3,
                                'H835': PW3,
                                'H841': PW3,
                                'H842': PW3,
                                'H843': PW3,
                                'H844': PW3,
                                'H845': PW3,
                                'H851': PH3,
                                'H852': PH3,
                                'H853': PH3,
                                'H854': PH3,
                                'H855': PH3,
                                'J111': AU3,
                                'J112': AU3,
                                'J113': AU3,
                                'J114': DU3,
                                'J115': JU3,
                                'J121': AU3,
                                'J122': AU3,
                                'J123': AU3,
                                'J124': DU3,
                                'J125': JU3,
                                'J131': AU3,
                                'J132': AU3,
                                'J133': DU3,
                                'J134': GU3,
                                'J135': JU3,
                                'J141': EN3,
                                'J142': HN3,
                                'J143': HN3,
                                'J144': HN3,
                                'J145': NN3,
                                'J151': HN3,
                                'J152': HN3,
                                'J153': HN3,
                                'J154': HN3,
                                'J155': NN3,
                                'J211': AU3,
                                'J212': AU3,
                                'J213': AU3,
                                'J214': DU3,
                                'J215': JU3,
                                'J221': AU3,
                                'J222': AU3,
                                'J223': AU3,
                                'J224': DU3,
                                'J225': JU3,
                                'J231': AU3,
                                'J232': AU3,
                                'J233': DU3,
                                'J234': GU3,
                                'J235': MU3,
                                'J241': EN3,
                                'J242': HN3,
                                'J243': HN3,
                                'J244': HN3,
                                'J245': NN3,
                                'J251': HN3,
                                'J252': HN3,
                                'J253': HN3,
                                'J254': HN3,
                                'J255': NN3,
                                'J311': AU3,
                                'J312': AU3,
                                'J313': AU3,
                                'J314': DU3,
                                'J315': JU3,
                                'J321': AU3,
                                'J322': AU3,
                                'J323': AU3,
                                'J324': DU3,
                                'J325': JU3,
                                'J331': AU3,
                                'J332': AU3,
                                'J333': DU3,
                                'J334': GU3,
                                'J335': MU3,
                                'J341': HN3,
                                'J342': HN3,
                                'J343': HN3,
                                'J344': HN3,
                                'J345': NN3,
                                'J351': GN3,
                                'J352': GN3,
                                'J353': GN3,
                                'J354': GN3,
                                'J355': MN3,
                                'J411': AF3,
                                'J412': AF3,
                                'J413': AF3,
                                'J414': DF3,
                                'J415': JF3,
                                'J421': AF3,
                                'J422': AF3,
                                'J423': AF3,
                                'J424': GF3,
                                'J425': JF3,
                                'J431': AF3,
                                'J432': AF3,
                                'J433': DF3,
                                'J434': GF3,
                                'J435': MF3,
                                'J441': GN3,
                                'J442': GN3,
                                'J443': GN3,
                                'J444': MN3,
                                'J445': MN3,
                                'J451': GS3,
                                'J452': MS3,
                                'J453': MS3,
                                'J454': MS3,
                                'J455': MS3,
                                'J511': AS2,
                                'J512': DS2,
                                'J513': JS2,
                                'J514': JS2,
                                'J515': JS2,
                                'J521': DS2,
                                'J522': JS2,
                                'J523': JS2,
                                'J524': JS2,
                                'J525': JS2,
                                'J531': DS3,
                                'J532': JS3,
                                'J533': JS3,
                                'J534': JS3,
                                'J535': MS3,
                                'J541': JS3,
                                'J542': MS3,
                                'J543': MS3,
                                'J544': MS3,
                                'J545': MS3,
                                'J551': MS3,
                                'J552': MS3,
                                'J553': MS3,
                                'J554': MS3,
                                'J555': MS3,
                                'J611': LS2,
                                'J612': LS2,
                                'J613': LS2,
                                'J614': LS2,
                                'J615': LS2,
                                'J621': LS2,
                                'J622': LS2,
                                'J623': LS2,
                                'J624': LS2,
                                'J625': LS2,
                                'J631': LS3,
                                'J632': LS3,
                                'J633': LS3,
                                'J634': LS3,
                                'J635': LS3,
                                'J641': LG3,
                                'J642': LG3,
                                'J643': PG3,
                                'J644': PG3,
                                'J645': PG3,
                                'J651': PG3,
                                'J652': PG3,
                                'J653': PG3,
                                'J654': PG3,
                                'J655': PG3,
                                'J711': LG3,
                                'J712': LG3,
                                'J713': LG3,
                                'J714': LG3,
                                'J715': LG3,
                                'J721': LG3,
                                'J722': LG3,
                                'J723': LG3,
                                'J724': LG3,
                                'J725': LG3,
                                'J731': PG3,
                                'J732': PG3,
                                'J733': PG3,
                                'J734': PG3,
                                'J735': PG3,
                                'J741': PW3,
                                'J742': PW3,
                                'J743': PW3,
                                'J744': PW3,
                                'J745': PW3,
                                'J751': PW3,
                                'J752': PW3,
                                'J753': PW3,
                                'J754': PW3,
                                'J755': PW3,
                                'J811': LW3,
                                'J812': LW3,
                                'J813': LW3,
                                'J814': LW3,
                                'J815': LW3,
                                'J821': PW3,
                                'J822': PW3,
                                'J823': PW3,
                                'J824': PW3,
                                'J825': PW3,
                                'J831': PW3,
                                'J832': PW3,
                                'J833': PW3,
                                'J834': PW3,
                                'J835': PW3,
                                'J841': PW3,
                                'J842': PW3,
                                'J843': PW3,
                                'J844': PW3,
                                'J845': PW3,
                                'J851': PH3,
                                'J852': PH3,
                                'J853': PH3,
                                'J854': PH3,
                                'J855': PH3,
                                'K111': AU3,
                                'K112': AU3,
                                'K113': AU3,
                                'K114': DU3,
                                'K115': JU3,
                                'K121': AU3,
                                'K122': AU3,
                                'K123': AU3,
                                'K124': DU3,
                                'K125': JU3,
                                'K131': AU3,
                                'K132': AU3,
                                'K133': DU3,
                                'K134': GU3,
                                'K135': JU3,
                                'K141': EN3,
                                'K142': HN3,
                                'K143': HN3,
                                'K144': HN3,
                                'K145': NN3,
                                'K151': HN3,
                                'K152': HN3,
                                'K153': HN3,
                                'K154': HN3,
                                'K155': NN3,
                                'K211': AU3,
                                'K212': AU3,
                                'K213': AU3,
                                'K214': DU3,
                                'K215': JU3,
                                'K221': AU3,
                                'K222': AU3,
                                'K223': AU3,
                                'K224': DU3,
                                'K225': JU3,
                                'K231': AU3,
                                'K232': AU3,
                                'K233': DU3,
                                'K234': GU3,
                                'K235': MU3,
                                'K241': HN3,
                                'K242': HN3,
                                'K243': HN3,
                                'K244': HN3,
                                'K245': NN3,
                                'K251': HN3,
                                'K252': HN3,
                                'K253': HN3,
                                'K254': HN3,
                                'K255': NN3,
                                'K311': AU3,
                                'K312': AU3,
                                'K313': AU3,
                                'K314': DU3,
                                'K315': JU3,
                                'K321': AU3,
                                'K322': AU3,
                                'K323': AU3,
                                'K324': DU3,
                                'K325': JU3,
                                'K331': AU3,
                                'K332': AU3,
                                'K333': DU3,
                                'K334': GU3,
                                'K335': MU3,
                                'K341': HN3,
                                'K342': HN3,
                                'K343': HN3,
                                'K344': HN3,
                                'K345': NN3,
                                'K351': GN3,
                                'K352': GN3,
                                'K353': GN3,
                                'K354': GN3,
                                'K355': MN3,
                                'K411': AF3,
                                'K412': AF3,
                                'K413': AF3,
                                'K414': DF3,
                                'K415': JF3,
                                'K421': AF3,
                                'K422': AF3,
                                'K423': DF3,
                                'K424': GF3,
                                'K425': JF3,
                                'K431': AF3,
                                'K432': AF3,
                                'K433': GF3,
                                'K434': GF3,
                                'K435': JF3,
                                'K441': GN3,
                                'K442': GN3,
                                'K443': GN3,
                                'K444': MN3,
                                'K445': MN3,
                                'K451': GS3,
                                'K452': MS3,
                                'K453': MS3,
                                'K454': MS3,
                                'K455': MS3,
                                'K511': DS3,
                                'K512': JS3,
                                'K513': JS3,
                                'K514': JS3,
                                'K515': JS3,
                                'K521': JS3,
                                'K522': JS3,
                                'K523': JS3,
                                'K524': JS3,
                                'K525': JS3,
                                'K531': JS3,
                                'K532': JS3,
                                'K533': JS3,
                                'K534': JS3,
                                'K535': MS3,
                                'K541': JS3,
                                'K542': MS3,
                                'K543': MS3,
                                'K544': MS3,
                                'K545': MS3,
                                'K551': MS3,
                                'K552': MS3,
                                'K553': MS3,
                                'K554': MS3,
                                'K555': MS3,
                                'K611': LS3,
                                'K612': LS3,
                                'K613': LS3,
                                'K614': LS3,
                                'K615': LS3,
                                'K621': LS3,
                                'K622': LS3,
                                'K623': LS3,
                                'K624': LS3,
                                'K625': LS3,
                                'K631': LS3,
                                'K632': LS3,
                                'K633': LS3,
                                'K634': LS3,
                                'K635': LS3,
                                'K641': LG3,
                                'K642': PG3,
                                'K643': PG3,
                                'K644': PG3,
                                'K645': PG3,
                                'K651': PG3,
                                'K652': PG3,
                                'K653': PG3,
                                'K654': PG3,
                                'K655': PG3,
                                'K711': LG46,
                                'K712': LG46,
                                'K713': LG46,
                                'K714': LG46,
                                'K715': LG46,
                                'K721': LG46,
                                'K722': LG46,
                                'K723': LG46,
                                'K724': LG46,
                                'K725': LG46,
                                'K731': PG46,
                                'K732': PG46,
                                'K733': PG46,
                                'K734': PG46,
                                'K735': PG46,
                                'K741': PW46,
                                'K742': PW46,
                                'K743': PW46,
                                'K744': PW46,
                                'K745': PW46,
                                'K751': PW45,
                                'K752': PW45,
                                'K753': PW45,
                                'K754': PW45,
                                'K755': PW45,
                                'K811': LW46,
                                'K812': LW46,
                                'K813': LW46,
                                'K814': LW46,
                                'K815': LW46,
                                'K821': PW46,
                                'K822': PW46,
                                'K823': PW46,
                                'K824': PW46,
                                'K825': PW46,
                                'K831': PW46,
                                'K832': PW46,
                                'K833': PW46,
                                'K834': PW46,
                                'K835': PW46,
                                'K841': PW46,
                                'K842': PW46,
                                'K843': PW46,
                                'K844': PW46,
                                'K845': PW46,
                                'K851': PH46,
                                'K852': PH46,
                                'K853': PH46,
                                'K854': PH46,
                                'K855': PH46,
                                'L111': AU3,
                                'L112': AU3,
                                'L113': AU3,
                                'L114': DU3,
                                'L115': JU3,
                                'L121': AU4,
                                'L122': AU4,
                                'L123': AU4,
                                'L124': DU4,
                                'L125': JU4,
                                'L131': BU4,
                                'L132': BU4,
                                'L133': EU4,
                                'L134': HU4,
                                'L135': KU4,
                                'L141': EN4,
                                'L142': HN4,
                                'L143': HN4,
                                'L144': HN4,
                                'L145': NN4,
                                'L151': HN4,
                                'L152': HN4,
                                'L153': HN4,
                                'L154': HN4,
                                'L155': NN4,
                                'L211': AU3,
                                'L212': AU3,
                                'L213': AU3,
                                'L214': DU3,
                                'L215': JU3,
                                'L221': AU4,
                                'L222': AU4,
                                'L223': AU4,
                                'L224': DU4,
                                'L225': JU4,
                                'L231': AU4,
                                'L232': AU4,
                                'L233': DU4,
                                'L234': GU4,
                                'L235': JU4,
                                'L241': HN4,
                                'L242': HN4,
                                'L243': HN4,
                                'L244': HN4,
                                'L245': NN4,
                                'L251': HN4,
                                'L252': HN4,
                                'L253': HN4,
                                'L254': HN4,
                                'L255': NN4,
                                'L311': AU3,
                                'L312': AU3,
                                'L313': AU3,
                                'L314': DU3,
                                'L315': JU3,
                                'L321': AU4,
                                'L322': AU4,
                                'L323': AU4,
                                'L324': DU4,
                                'L325': JU4,
                                'L331': AU4,
                                'L332': AU4,
                                'L333': DU4,
                                'L334': GU4,
                                'L335': JU4,
                                'L341': HN4,
                                'L342': HN4,
                                'L343': HN4,
                                'L344': HN4,
                                'L345': NN4,
                                'L351': GN4,
                                'L352': GN4,
                                'L353': GN4,
                                'L354': GN4,
                                'L355': MN4,
                                'L411': AF3,
                                'L412': AF3,
                                'L413': AF3,
                                'L414': DF3,
                                'L415': JF3,
                                'L421': AF4,
                                'L422': AF4,            # Shown in The Sager Weathercaster as 'L 422'.
                                'L423': DF4,
                                'L424': GF4,
                                'L425': JF4,
                                'L431': AF4,
                                'L432': AF4,
                                'L433': GF4,
                                'L434': GF4,
                                'L435': JF4,
                                'L441': GN4,
                                'L442': GN4,
                                'L443': GN4,
                                'L444': MN4,
                                'L445': MN4,
                                'L451': GS4,
                                'L452': MS4,
                                'L453': MS4,
                                'L454': MS4,
                                'L455': MS4,
                                'L511': DS3,
                                'L512': JS3,
                                'L513': JS3,
                                'L514': JS3,
                                'L515': JS3,
                                'L521': JS4,
                                'L522': JS4,
                                'L523': JS4,
                                'L524': JS4,
                                'L525': JS4,
                                'L531': JS4,
                                'L532': JS4,
                                'L533': JS4,
                                'L534': JS4,
                                'L535': MS4,
                                'L541': JS4,
                                'L542': MS4,
                                'L543': MS4,
                                'L544': MS4,
                                'L545': MS4,
                                'L551': MS4,
                                'L552': MS4,
                                'L553': MS4,
                                'L554': MS4,
                                'L555': MS4,
                                'L611': LS45,
                                'L612': LS45,
                                'L613': LS45,
                                'L614': LS45,
                                'L615': LS45,
                                'L621': LS45,
                                'L622': LS45,
                                'L623': LS45,
                                'L624': LS45,
                                'L625': LS45,
                                'L631': LS45,
                                'L632': LS45,
                                'L633': LS45,
                                'L634': LS45,
                                'L635': LS45,
                                'L641': LG45,
                                'L642': PG45,
                                'L643': PG45,
                                'L644': PG45,
                                'L645': PG45,
                                'L651': PG45,
                                'L652': PG45,
                                'L653': PG45,
                                'L654': PG45,
                                'L655': PG45,
                                'L711': LG46,
                                'L712': LG46,
                                'L713': LG46,
                                'L714': LG46,
                                'L715': LG46,
                                'L721': LG46,
                                'L722': LG46,
                                'L723': LG46,
                                'L724': LG46,
                                'L725': LG46,
                                'L731': PG46,
                                'L732': PG46,
                                'L733': PG46,
                                'L734': PG46,
                                'L735': PG46,
                                'L741': PW46,
                                'L742': PW46,
                                'L743': PW46,
                                'L744': PW46,
                                'L745': PW46,
                                'L751': PW45,
                                'L752': PW45,
                                'L753': PW45,
                                'L754': PW45,
                                'L755': PW45,
                                'L811': LW46,
                                'L812': LW46,
                                'L813': LW46,
                                'L814': LW46,
                                'L815': LW46,
                                'L821': PW46,
                                'L822': PW46,
                                'L823': PW46,
                                'L824': PW46,
                                'L825': PW46,
                                'L831': PW46,
                                'L832': PW46,
                                'L833': PW46,
                                'L834': PW46,
                                'L835': PW46,
                                'L841': PW46,
                                'L842': PW46,
                                'L843': PW46,
                                'L844': PW46,
                                'L845': PW46,
                                'L851': PH46,
                                'L852': PH46,
                                'L853': PH46,
                                'L854': PH46,
                                'L855': PH46,
                                'M111': AU4,
                                'M112': AU4,
                                'M113': AU4,
                                'M114': DU4,
                                'M115': JU4,
                                'M121': AU4,
                                'M122': AU4,
                                'M123': AU4,
                                'M124': DU4,
                                'M125': JU4,
                                'M131': BU4,
                                'M132': BU4,
                                'M133': EU4,
                                'M134': HU4,
                                'M135': KU4,
                                'M141': EN4,
                                'M142': HN4,
                                'M143': HN4,
                                'M144': HN4,
                                'M145': NN4,
                                'M151': HN4,
                                'M152': HN4,
                                'M153': HN4,
                                'M154': HN4,
                                'M155': NN4,
                                'M211': AU4,
                                'M212': AU4,
                                'M213': AU4,
                                'M214': DU4,
                                'M215': JU4,
                                'M221': AU4,
                                'M222': AU4,
                                'M223': AU4,
                                'M224': DU4,
                                'M225': JU4,
                                'M231': AU4,
                                'M232': AU4,
                                'M233': DU4,
                                'M234': GU4,
                                'M235': JU4,
                                'M241': HN4,
                                'M242': HN4,
                                'M243': HN4,
                                'M244': HN4,
                                'M245': NN4,
                                'M251': HN4,
                                'M252': HN4,
                                'M253': HN4,
                                'M254': HN4,
                                'M255': NN4,
                                'M311': AU4,
                                'M312': AU4,
                                'M313': AU4,
                                'M314': DU4,
                                'M315': JU4,
                                'M321': AU4,
                                'M322': AU4,
                                'M323': AU4,
                                'M324': DU4,
                                'M325': JU4,
                                'M331': AU4,
                                'M332': AU4,
                                'M333': DU4,
                                'M334': GU4,
                                'M335': JU4,
                                'M341': HN4,
                                'M342': HN4,
                                'M343': HN4,
                                'M344': HN4,
                                'M345': NN4,
                                'M351': GN4,
                                'M352': GN4,
                                'M353': GN4,
                                'M354': GN4,
                                'M355': MN4,
                                'M411': AF4,
                                'M412': AF4,
                                'M413': AF4,
                                'M414': DF4,
                                'M415': JF4,
                                'M421': AF4,
                                'M422': AF4,
                                'M423': DF4,
                                'M424': GF4,
                                'M425': JF4,
                                'M431': AF4,
                                'M432': AF4,
                                'M433': GF4,
                                'M434': GF4,
                                'M435': JF4,
                                'M441': GN4,
                                'M442': GN4,
                                'M443': GN4,
                                'M444': MN4,
                                'M445': MN4,
                                'M451': GS4,
                                'M452': MS4,
                                'M453': MS4,
                                'M454': MS4,
                                'M455': MS4,
                                'M511': DS4,
                                'M512': JS4,
                                'M513': JS4,
                                'M514': JS4,
                                'M515': JS4,
                                'M521': JS4,
                                'M522': JS4,
                                'M523': JS4,
                                'M524': JS4,
                                'M525': JS4,
                                'M531': JS4,
                                'M532': JS4,
                                'M533': JS4,
                                'M534': JS4,
                                'M535': MS4,
                                'M541': JS4,
                                'M542': MS4,
                                'M543': MS4,
                                'M544': MS4,
                                'M545': MS4,
                                'M551': MS4,
                                'M552': MS4,
                                'M553': MS4,
                                'M554': MS4,
                                'M555': MS4,
                                'M611': LS45,
                                'M612': LS45,
                                'M613': LS45,
                                'M614': LS45,
                                'M615': LS45,
                                'M621': LS45,
                                'M622': LS45,
                                'M623': LS45,
                                'M624': LS45,
                                'M625': LS45,
                                'M631': LS45,
                                'M632': LS45,
                                'M633': LS45,
                                'M634': LS45,
                                'M635': LS45,
                                'M641': LG45,
                                'M642': PG45,
                                'M643': PG45,
                                'M644': PG45,
                                'M645': PG45,
                                'M651': PG45,
                                'M652': PG45,
                                'M653': PG45,
                                'M654': PG45,
                                'M655': PG45,
                                'M711': LG46,
                                'M712': LG46,
                                'M713': LG46,
                                'M714': LG46,
                                'M715': LG46,
                                'M721': LG46,
                                'M722': LG46,
                                'M723': LG46,
                                'M724': LG46,
                                'M725': LG46,
                                'M731': PG46,
                                'M732': PG46,
                                'M733': PG46,
                                'M734': PG46,
                                'M735': PG46,
                                'M741': PW46,
                                'M742': PW46,
                                'M743': PW46,
                                'M744': PW46,
                                'M745': PW46,
                                'M751': PW46,
                                'M752': PW46,
                                'M753': PW46,
                                'M754': PW46,
                                'M755': PW46,
                                'M811': LW46,
                                'M812': LW46,
                                'M813': LW46,
                                'M814': LW46,
                                'M815': LW46,
                                'M821': PW46,
                                'M822': PW46,
                                'M823': PW46,
                                'M824': PW46,
                                'M825': PW46,
                                'M831': PW46,
                                'M832': PW46,
                                'M833': PW46,
                                'M834': PW46,
                                'M835': PW46,
                                'M841': PW46,
                                'M842': PW46,
                                'M843': PW46,
                                'M844': PW46,
                                'M845': PW46,
                                'M851': PH46,
                                'M852': PH46,
                                'M853': PH46,
                                'M854': PH46,
                                'M855': PH46,
                                'N111': BU5,
                                'N112': BU5,
                                'N113': BU5,
                                'N114': BU5,
                                'N115': EU5,
                                'N121': BU5,
                                'N122': BU5,
                                'N123': BU5,
                                'N124': EU5,
                                'N125': EU5,
                                'N131': BU5,
                                'N132': BU5,
                                'N133': BU5,
                                'N134': EU5,
                                'N135': KU5,
                                'N141': EN4,
                                'N142': HN4,
                                'N143': HN4,
                                'N144': HN4,
                                'N145': NN4,
                                'N151': HN4,
                                'N152': HN4,
                                'N153': HN4,
                                'N154': HN4,
                                'N155': NN4,
                                'N211': AU5,
                                'N212': AU5,
                                'N213': AU5,
                                'N214': AU5,
                                'N215': DU5,
                                'N221': BU5,
                                'N222': BU5,
                                'N223': BU5,
                                'N224': EU5,
                                'N225': EU5,
                                'N231': BU5,
                                'N232': BU5,
                                'N233': BU5,
                                'N234': EU5,
                                'N235': KU5,
                                'N241': EN4,
                                'N242': HN4,
                                'N243': HN4,
                                'N244': HN4,
                                'N245': KN4,
                                'N251': HN4,
                                'N252': HN4,
                                'N253': HN4,
                                'N254': HN4,
                                'N255': NN4,
                                'N311': AU5,
                                'N312': AU5,
                                'N313': AU5,
                                'N314': AU5,
                                'N315': DU5,
                                'N321': AU5,
                                'N322': AU5,
                                'N323': AU5,
                                'N324': DU5,
                                'N325': JU5,
                                'N331': BU5,
                                'N332': BU5,
                                'N333': BU5,
                                'N334': EU5,
                                'N335': KU5,
                                'N341': HN4,
                                'N342': HN4,
                                'N343': HN4,
                                'N344': HN4,
                                'N345': KN4,
                                'N351': HN4,
                                'N352': HN4,
                                'N353': HN4,
                                'N354': HN4,
                                'N355': NN4,
                                'N411': AF5,
                                'N412': AF5,
                                'N413': AF5,
                                'N414': DF5,
                                'N415': JF5,
                                'N421': AF5,
                                'N422': AF5,
                                'N423': AF5,
                                'N424': DF5,
                                'N425': JF5,
                                'N431': AF5,
                                'N432': AF5,
                                'N433': DF5,
                                'N434': GF5,
                                'N435': JF5,
                                'N441': GN4,
                                'N442': GN4,
                                'N443': GN4,
                                'N444': JN4,
                                'N445': MN4,
                                'N451': GN4,
                                'N452': GN4,
                                'N453': GN4,
                                'N454': MN4,
                                'N455': MN4,
                                'N511': DS56,
                                'N512': JS56,
                                'N513': JS56,
                                'N514': JS56,
                                'N515': JS56,
                                'N521': DF5,
                                'N522': JF5,
                                'N523': JF5,
                                'N524': JF5,
                                'N525': JF5,
                                'N531': JF5,
                                'N532': JF5,
                                'N533': JF5,
                                'N534': JF5,
                                'N535': JF5,
                                'N541': JS5,
                                'N542': JS5,
                                'N543': JS5,
                                'N544': MS5,
                                'N545': MS5,
                                'N551': JS5,
                                'N552': JS5,
                                'N553': MS5,
                                'N554': MS5,
                                'N555': MS5,
                                'N611': SS56,
                                'N612': SS56,
                                'N613': SS56,
                                'N614': SS56,
                                'N615': SS56,
                                'N621': SS56,
                                'N622': SS56,
                                'N623': SS56,
                                'N624': SS56,
                                'N625': SS56,
                                'N631': SS56,
                                'N632': SS56,
                                'N633': SS56,
                                'N634': SS56,
                                'N635': SS56,
                                'N641': SS56,
                                'N642': SS56,
                                'N643': SS56,
                                'N644': SS56,
                                'N645': SS56,
                                'N651': LS56,
                                'N652': LS56,
                                'N653': PS56,
                                'N654': PS56,
                                'N655': PS56,
                                'N711': SG57,
                                'N712': SG57,
                                'N713': SG57,
                                'N714': SG57,
                                'N715': SG57,
                                'N721': SG57,
                                'N722': SG57,
                                'N723': SG57,
                                'N724': SG57,
                                'N725': SG57,
                                'N731': SG57,
                                'N732': SG57,
                                'N733': SG57,
                                'N734': SG57,
                                'N735': SG57,
                                'N741': SG57,
                                'N742': SG57,
                                'N743': SG57,
                                'N744': SG57,
                                'N745': SG57,
                                'N751': LG57,
                                'N752': LG57,
                                'N753': PG57,
                                'N754': PG57,
                                'N755': PG57,
                                'N811': SW57,
                                'N812': SW57,
                                'N813': SW57,
                                'N814': SW57,
                                'N815': SW57,
                                'N821': SW57,
                                'N822': SW57,
                                'N823': SW57,
                                'N824': SW57,
                                'N825': SW57,
                                'N831': SW57,
                                'N832': SW57,
                                'N833': SW57,
                                'N834': SW57,
                                'N835': SW57,
                                'N841': SW57,
                                'N842': SW57,
                                'N843': SW57,
                                'N844': SW57,
                                'N845': SW57,
                                'N851': LW57,
                                'N852': LW57,
                                'N853': PW57,
                                'N854': PW57,
                                'N855': PW57,
                                'O111': AU5,
                                'O112': AU5,
                                'O113': AU5,
                                'O114': AU5,
                                'O115': DU5,
                                'O121': BU5,
                                'O122': BU5,
                                'O123': BU5,
                                'O124': BU5,
                                'O125': EU5,
                                'O131': BU5,
                                'O132': BU5,
                                'O133': BU5,
                                'O134': EU5,
                                'O135': KU5,
                                'O141': BN4,
                                'O142': HN4,
                                'O143': HN4,
                                'O144': HN4,
                                'O145': NN4,
                                'O151': HN4,
                                'O152': HN4,
                                'O153': HN4,
                                'O154': HN4,
                                'O155': NN4,
                                'O211': AU5,
                                'O212': AU5,
                                'O213': AU5,
                                'O214': AU5,
                                'O215': DU5,
                                'O221': BU5,
                                'O222': BU5,
                                'O223': BU5,
                                'O224': BU5,
                                'O225': EU5,
                                'O231': BU5,
                                'O232': BU5,
                                'O233': BU5,
                                'O234': EU5,
                                'O235': KU5,
                                'O241': EN4,
                                'O242': HN4,
                                'O243': HN4,
                                'O244': HN4,
                                'O245': KN4,
                                'O251': HN4,
                                'O252': HN4,
                                'O253': HN4,
                                'O254': HN4,
                                'O255': NN4,
                                'O311': AU5,
                                'O312': AU5,
                                'O313': AU5,
                                'O314': AU5,
                                'O315': DU5,
                                'O321': AU5,
                                'O322': AU5,
                                'O323': AU5,
                                'O324': DU5,
                                'O325': JU5,
                                'O331': BU5,
                                'O332': BU5,
                                'O333': BU5,
                                'O334': EU5,
                                'O335': KU5,
                                'O341': HN5,
                                'O342': HN5,
                                'O343': HN5,
                                'O344': HN5,
                                'O345': KN5,
                                'O351': GN5,
                                'O352': GN5,
                                'O353': GN5,
                                'O354': GN5,
                                'O355': MN5,
                                'O411': AF5,
                                'O412': AF5,
                                'O413': AF5,
                                'O414': DF5,
                                'O415': JF5,
                                'O421': AF5,
                                'O422': AF5,
                                'O423': AF5,
                                'O424': DF5,
                                'O425': JF5,
                                'O431': AF5,
                                'O432': AF5,
                                'O433': DF5,
                                'O434': GF5,
                                'O435': JF5,
                                'O441': GN5,
                                'O442': GN5,
                                'O443': GN5,
                                'O444': JN5,
                                'O445': MN5,
                                'O451': GN5,
                                'O452': GN5,
                                'O453': GN5,
                                'O454': MN5,
                                'O455': MN5,
                                'O511': DS56,
                                'O512': JS56,
                                'O513': JS56,
                                'O514': SS56,
                                'O515': SS56,
                                'O521': DF56,
                                'O522': JF56,
                                'O523': JF56,
                                'O524': SF56,
                                'O525': SF56,
                                'O531': JF56,
                                'O532': JF56,
                                'O533': JF56,
                                'O534': JF56,
                                'O535': JF56,
                                'O541': JS56,
                                'O542': JS56,
                                'O543': JS56,
                                'O544': MS56,
                                'O545': MS56,
                                'O551': LS56,
                                'O552': LS56,
                                'O553': PS56,
                                'O554': PS56,
                                'O555': PS56,
                                'O611': SS57,
                                'O612': SS57,
                                'O613': SS57,
                                'O614': SS57,
                                'O615': SS57,
                                'O621': SS57,
                                'O622': SS57,
                                'O623': SS57,
                                'O624': SS57,
                                'O625': SS57,
                                'O631': SS57,
                                'O632': SS57,
                                'O633': SS57,
                                'O634': SS57,
                                'O635': SS57,
                                'O641': SS57,
                                'O642': SS57,
                                'O643': SS57,
                                'O644': SS57,
                                'O645': SS57,
                                'O651': LS57,
                                'O652': LS57,
                                'O653': PS57,
                                'O654': PS57,
                                'O655': PS57,
                                'O711': SG57,
                                'O712': SG57,
                                'O713': SG57,
                                'O714': SG57,
                                'O715': SG57,
                                'O721': SG57,
                                'O722': SG57,
                                'O723': SG57,
                                'O724': SG57,
                                'O725': SG57,
                                'O731': SG57,
                                'O732': SG57,
                                'O733': SG57,
                                'O734': SG57,
                                'O735': SG57,
                                'O741': SG57,
                                'O742': SG57,
                                'O743': SG57,
                                'O744': SG57,
                                'O745': SG57,
                                'O751': LG57,
                                'O752': LG57,
                                'O753': PG57,
                                'O754': PG57,
                                'O755': PG57,
                                'O811': SW57,
                                'O812': SW57,
                                'O813': SW57,
                                'O814': SW57,
                                'O815': SW57,
                                'O821': SW57,
                                'O822': SW57,
                                'O823': SW57,
                                'O824': SW57,
                                'O825': SW57,
                                'O831': SW57,
                                'O832': SW57,
                                'O833': SW57,
                                'O834': SW57,
                                'O835': SW57,
                                'O841': SW57,
                                'O842': SW57,
                                'O843': SW57,
                                'O844': SW57,
                                'O845': SW57,
                                'O851': LW57,
                                'O852': LW57,
                                'O853': PW57,
                                'O854': PW57,
                                'O855': PW57,
                                'P111': AU5,
                                'P112': AU5,
                                'P113': AU5,
                                'P114': AU5,
                                'P115': DU5,
                                'P121': BU5,
                                'P122': BU5,
                                'P123': BU5,
                                'P124': BU5,
                                'P125': EU5,
                                'P131': BU5,
                                'P132': BU5,
                                'P133': BU5,
                                'P134': EU5,
                                'P135': KU5,
                                'P141': BN5,
                                'P142': HN5,
                                'P143': HN5,
                                'P144': HN5,
                                'P145': KN5,
                                'P151': HN5,
                                'P152': HN5,
                                'P153': HN5,
                                'P154': HN5,
                                'P155': NN5,
                                'P211': AU5,
                                'P212': AU5,
                                'P213': AU5,
                                'P214': AU5,
                                'P215': DU5,
                                'P221': BU5,
                                'P222': BU5,
                                'P223': BU5,
                                'P224': BU5,
                                'P225': EU5,
                                'P231': BU5,
                                'P232': BU5,
                                'P233': BU5,
                                'P234': EU5,
                                'P235': KU5,
                                'P241': EN5,
                                'P242': HN5,
                                'P243': HN5,
                                'P244': HN5,
                                'P245': KN5,
                                'P251': HN5,
                                'P252': HN5,
                                'P253': HN5,
                                'P254': HN5,
                                'P255': NN5,
                                'P311': AU5,
                                'P312': AU5,
                                'P313': AU5,
                                'P314': AU5,
                                'P315': DU5,
                                'P321': AU5,
                                'P322': AU5,
                                'P323': AU5,
                                'P324': DU5,
                                'P325': JU5,
                                'P331': BU5,
                                'P332': BU5,
                                'P333': BU5,
                                'P334': EU5,
                                'P335': KU5,
                                'P341': HN5,
                                'P342': HN5,
                                'P343': HN5,
                                'P344': HN5,
                                'P345': KN5,
                                'P351': GN5,
                                'P352': GN5,
                                'P353': GN5,
                                'P354': GN5,
                                'P355': MN5,
                                'P411': AF5,
                                'P412': AF5,
                                'P413': AF5,
                                'P414': DF5,
                                'P415': JF5,
                                'P421': AF5,
                                'P422': AF5,
                                'P423': AF5,
                                'P424': DF5,
                                'P425': JF5,
                                'P431': AF5,
                                'P432': AF5,
                                'P433': DF5,
                                'P434': GF5,
                                'P435': JF5,
                                'P441': GN5,
                                'P442': GN5,
                                'P443': GN5,
                                'P444': JN5,
                                'P445': MN5,
                                'P451': GN5,
                                'P452': GN5,
                                'P453': GN5,
                                'P454': MN5,
                                'P455': MN5,
                                'P511': DS56,
                                'P512': JS56,
                                'P513': JS56,
                                'P514': SS56,
                                'P515': SS56,
                                'P521': DF56,
                                'P522': JF56,
                                'P523': JF56,
                                'P524': SF56,
                                'P525': SF56,
                                'P531': JF56,
                                'P532': JF56,
                                'P533': JF56,
                                'P534': JF56,
                                'P535': JF56,
                                'P541': JS56,
                                'P542': JS56,
                                'P543': JS56,
                                'P544': MS56,
                                'P545': MS56,
                                'P551': LS56,
                                'P552': LS56,
                                'P553': PS56,
                                'P554': PS56,
                                'P555': PS56,
                                'P611': SS57,
                                'P612': SS57,
                                'P613': SS57,
                                'P614': SS57,
                                'P615': SS57,
                                'P621': SS57,
                                'P622': SS57,
                                'P623': SS57,
                                'P624': SS57,
                                'P625': SS57,
                                'P631': SS57,
                                'P632': SS57,
                                'P633': SS57,
                                'P634': SS57,
                                'P635': SS57,
                                'P641': SS57,
                                'P642': SS57,
                                'P643': SS57,
                                'P644': SS57,
                                'P645': SS57,
                                'P651': LS57,
                                'P652': LS57,
                                'P653': PS57,
                                'P654': PS57,
                                'P655': PS57,
                                'P711': SG57,
                                'P712': SG57,
                                'P713': SG57,
                                'P714': SG57,
                                'P715': SG57,
                                'P721': SG57,
                                'P722': SG57,
                                'P723': SG57,
                                'P724': SG57,
                                'P725': SG57,
                                'P731': SG57,
                                'P732': SG57,
                                'P733': SG57,
                                'P734': SG57,
                                'P735': SG57,
                                'P741': SG57,
                                'P742': SG57,
                                'P743': SG57,
                                'P744': SG57,
                                'P745': SG57,
                                'P751': LG57,
                                'P752': LG57,
                                'P753': PG57,
                                'P754': PG57,
                                'P755': PG57,
                                'P811': SW57,
                                'P812': SW57,
                                'P813': SW57,
                                'P814': SW57,
                                'P815': SW57,
                                'P821': SW57,
                                'P822': SW57,
                                'P823': SW57,
                                'P824': SW57,
                                'P825': SW57,
                                'P831': SW57,
                                'P832': SW57,
                                'P833': SW57,
                                'P834': SW57,
                                'P835': SW57,
                                'P841': SW57,
                                'P842': SW57,
                                'P843': SW57,
                                'P844': SW57,
                                'P845': SW57,
                                'P851': LW57,
                                'P852': LW57,
                                'P853': PW57,
                                'P854': PW57,
                                'P855': PW57,
                                'Q111': BU5,
                                'Q112': BU5,
                                'Q113': BU5,
                                'Q114': BU5,
                                'Q115': EU5,
                                'Q121': BU5,
                                'Q122': BU5,
                                'Q123': BU5,
                                'Q124': BU5,
                                'Q125': EU5,
                                'Q131': BU5,
                                'Q132': BU5,
                                'Q133': BU5,
                                'Q134': BU5,
                                'Q135': KU5,
                                'Q141': BN5,
                                'Q142': EN5,
                                'Q143': HN5,
                                'Q144': HN5,
                                'Q145': KN5,
                                'Q151': EN5,
                                'Q152': HN5,
                                'Q153': HN5,
                                'Q154': HN5,
                                'Q155': KN5,
                                'Q211': AU5,
                                'Q212': AU5,
                                'Q213': AU5,
                                'Q214': AU5,
                                'Q215': DU5,
                                'Q221': BU5,
                                'Q222': BU5,
                                'Q223': BU5,
                                'Q224': BU5,
                                'Q225': EU5,
                                'Q231': BU5,
                                'Q232': BU5,
                                'Q233': BU5,
                                'Q234': EU5,
                                'Q235': KU5,
                                'Q241': BN5,
                                'Q242': EN5,
                                'Q243': HN5,
                                'Q244': HN5,
                                'Q245': KN5,
                                'Q251': HN5,
                                'Q252': HN5,
                                'Q253': HN5,
                                'Q254': HN5,
                                'Q255': KN5,
                                'Q311': AF5,
                                'Q312': AF5,
                                'Q313': AF5,
                                'Q314': AF5,
                                'Q315': DF5,
                                'Q321': AU5,
                                'Q322': AU5,
                                'Q323': AU5,
                                'Q324': DU5,
                                'Q325': RU5,
                                'Q331': BU5,
                                'Q332': BU5,
                                'Q333': BU5,
                                'Q334': EU5,
                                'Q335': KU5,
                                'Q341': EN5,
                                'Q342': HN5,
                                'Q343': HN5,
                                'Q344': HN5,
                                'Q345': KN5,
                                'Q351': HN5,
                                'Q352': HN5,
                                'Q353': HN5,
                                'Q354': HN5,
                                'Q355': KN5,
                                'Q411': CF6,
                                'Q412': CF6,
                                'Q413': CF6,
                                'Q414': YF6,
                                'Q415': UF6,
                                'Q421': AF6,
                                'Q422': AF6,
                                'Q423': AF6,
                                'Q424': DF6,
                                'Q425': JF6,
                                'Q431': AF6,
                                'Q432': AF6,
                                'Q433': DF6,
                                'Q434': DF6,
                                'Q435': JF6,
                                'Q441': GN5,
                                'Q442': GN5,
                                'Q443': GN5,
                                'Q444': JN5,
                                'Q445': JN5,
                                'Q451': GN5,
                                'Q452': GN5,
                                'Q453': GN5,
                                'Q454': JN5,
                                'Q455': JN5,
                                'Q511': CS6,
                                'Q512': CS6,
                                'Q513': FS6,
                                'Q514': FS6,
                                'Q515': SS6,
                                'Q521': FF6,
                                'Q522': FF6,
                                'Q523': FF6,
                                'Q524': FF6,
                                'Q525': SF6,
                                'Q531': JF6,
                                'Q532': JF6,
                                'Q533': JF6,
                                'Q534': JF6,
                                'Q535': JF6,
                                'Q541': JS6,
                                'Q542': JS6,
                                'Q543': JS6,
                                'Q544': JS6,
                                'Q545': JS6,
                                'Q551': JS6,
                                'Q552': JS6,
                                'Q553': JS6,
                                'Q554': JS6,
                                'Q555': JS6,
                                'Q611': FS6,
                                'Q612': FS6,
                                'Q613': FS6,
                                'Q614': SS6,
                                'Q615': SS6,
                                'Q621': FS6,
                                'Q622': FS6,
                                'Q623': FS6,
                                'Q624': SS6,
                                'Q625': SS6,
                                'Q631': SS6,
                                'Q632': SS6,
                                'Q633': SS6,
                                'Q634': SS6,
                                'Q635': SS6,
                                'Q641': SS6,
                                'Q642': SS6,
                                'Q643': SS6,
                                'Q644': SS6,
                                'Q645': SS6,
                                'Q651': SS6,
                                'Q652': SS6,
                                'Q653': SS6,
                                'Q654': SS6,
                                'Q655': SS6,
                                'Q711': FG67,
                                'Q712': SG67,
                                'Q713': SG67,
                                'Q714': SG67,
                                'Q715': SG67,
                                'Q721': SG67,
                                'Q722': SG67,
                                'Q723': SG67,
                                'Q724': SG67,
                                'Q725': SG67,
                                'Q731': SG67,
                                'Q732': SG67,
                                'Q733': SG67,
                                'Q734': SG67,
                                'Q735': SG67,
                                'Q741': SG67,
                                'Q742': SG67,
                                'Q743': SG67,
                                'Q744': SG67,
                                'Q745': SG67,
                                'Q751': SG67,
                                'Q752': SG67,
                                'Q753': SG67,
                                'Q754': SG67,
                                'Q755': SG67,
                                'Q811': SW67,
                                'Q812': SW67,
                                'Q813': SW67,
                                'Q814': SW67,
                                'Q815': SW67,
                                'Q821': SW67,
                                'Q822': SW67,
                                'Q823': SW67,
                                'Q824': SW67,
                                'Q825': SW67,
                                'Q831': SW67,
                                'Q832': SW67,
                                'Q833': SW67,
                                'Q834': SW67,
                                'Q835': SW67,
                                'Q841': SW67,
                                'Q842': SW67,
                                'Q843': SW67,
                                'Q844': SW67,
                                'Q845': SW67,
                                'Q851': SW67,
                                'Q852': SW67,
                                'Q853': SW67,
                                'Q854': SW67,
                                'Q855': SW67,
                                'R111': AU6,
                                'R112': AU6,
                                'R113': AU6,
                                'R114': AU6,
                                'R115': DU6,
                                'R121': BU6,
                                'R122': BU6,
                                'R123': BU6,
                                'R124': BU6,
                                'R125': EU6,
                                'R131': BU6,
                                'R132': BU6,
                                'R133': BU6,
                                'R134': BU6,
                                'R135': EU6,
                                'R141': BN5,
                                'R142': EN5,
                                'R143': HN5,
                                'R144': HN5,
                                'R145': KN5,
                                'R151': EN5,
                                'R152': HN5,
                                'R153': HN5,
                                'R154': HN5,
                                'R155': KN5,
                                'R211': AU6,
                                'R212': AU6,
                                'R213': AU6,
                                'R214': AU6,
                                'R215': DU6,
                                'R221': AU6,
                                'R222': AU6,
                                'R223': AU6,
                                'R224': AU6,
                                'R225': DU6,
                                'R231': BU6,
                                'R232': BU6,
                                'R233': BU6,
                                'R234': EU6,
                                'R235': RU6,
                                'R241': BN5,
                                'R242': EN5,
                                'R243': HN5,
                                'R244': HN5,
                                'R245': KN5,
                                'R251': HN5,
                                'R252': HN5,
                                'R253': HN5,
                                'R254': HN5,
                                'R255': KN5,
                                'R311': CF6,
                                'R312': CF6,
                                'R313': CF6,
                                'R314': CF6,
                                'R315': FF6,
                                'R321': AU6,
                                'R322': AU6,
                                'R323': AU6,
                                'R324': AU6,
                                'R325': TU6,
                                'R331': BU6,
                                'R332': BU6,
                                'R333': BU6,
                                'R334': XU6,
                                'R335': RU6,
                                'R341': EN5,
                                'R342': HN5,
                                'R343': HN5,
                                'R344': HN5,
                                'R345': KN5,
                                'R351': HN5,
                                'R352': HN5,
                                'R353': HN5,
                                'R354': GN5,
                                'R355': JN5,
                                'R411': CF6,
                                'R412': CF6,
                                'R413': CF6,
                                'R414': YF6,
                                'R415': UF6,
                                'R421': AF6,
                                'R422': AF6,
                                'R423': AF6,
                                'R424': XF6,
                                'R425': RF6,
                                'R431': AF6,
                                'R432': AF6,
                                'R433': XF6,
                                'R434': DF6,
                                'R435': RF6,
                                'R441': GN6,
                                'R442': GN6,
                                'R443': GN6,
                                'R444': JN6,
                                'R445': JN6,
                                'R451': GN6,
                                'R452': GN6,
                                'R453': GN6,
                                'R454': JN6,
                                'R455': JN6,
                                'R511': CS6,
                                'R512': CS6,
                                'R513': YS6,
                                'R514': FS6,
                                'R515': US6,
                                'R521': CF6,
                                'R522': CF6,
                                'R523': FF6,
                                'R524': FF6,
                                'R525': SF6,
                                'R531': DF6,
                                'R532': FF6,
                                'R533': LF6,
                                'R534': SF6,
                                'R535': SF6,
                                'R541': JS6,
                                'R542': LS6,
                                'R543': LS6,
                                'R544': SS6,
                                'R545': SS6,
                                'R551': SS6,
                                'R552': SS6,
                                'R553': SS6,
                                'R554': SS6,
                                'R555': SS6,
                                'R611': CS67,
                                'R612': FS67,
                                'R613': FS67,
                                'R614': SS67,
                                'R615': SS67,
                                'R621': FS67,
                                'R622': FS67,
                                'R623': FS67,
                                'R624': SS67,
                                'R625': SS67,
                                'R631': SS67,
                                'R632': SS67,
                                'R633': SS67,
                                'R634': SS67,
                                'R635': SS67,
                                'R641': SS67,
                                'R642': SS67,
                                'R643': SS67,
                                'R644': SS67,
                                'R645': SS67,
                                'R651': SS67,
                                'R652': SS67,
                                'R653': SS67,
                                'R654': SS67,
                                'R655': SS67,
                                'R711': FG67,
                                'R712': FG67,
                                'R713': SG67,
                                'R714': SG67,
                                'R715': SG67,
                                'R721': SG67,
                                'R722': SG67,
                                'R723': SG67,
                                'R724': SG67,
                                'R725': SG67,
                                'R731': SG67,
                                'R732': SG67,
                                'R733': SG67,
                                'R734': SG67,
                                'R735': SG67,
                                'R741': SG67,
                                'R742': SG67,
                                'R743': SG67,
                                'R744': SG67,
                                'R745': SG67,
                                'R751': SG67,
                                'R752': SG67,
                                'R753': SG67,
                                'R754': SG67,
                                'R755': SG67,
                                'R811': SW67,
                                'R812': SW67,
                                'R813': SW67,
                                'R814': SW67,
                                'R815': SW67,
                                'R821': SW67,
                                'R822': SW67,
                                'R823': SW67,
                                'R824': SW67,
                                'R825': SW67,
                                'R831': SW67,
                                'R832': SW67,
                                'R833': SW67,
                                'R834': SW67,
                                'R835': SW67,
                                'R841': SW67,
                                'R842': SW67,
                                'R843': SW67,
                                'R844': SW67,
                                'R845': SW67,
                                'R851': SW67,
                                'R852': SW67,
                                'R853': SW67,
                                'R854': SW67,
                                'R855': SW67,
                                'S111': AU6,
                                'S112': AU6,
                                'S113': AU6,
                                'S114': AU6,
                                'S115': DU6,
                                'S121': AU6,
                                'S122': AU6,
                                'S123': AU6,
                                'S124': AU6,
                                'S125': DU6,
                                'S131': BU6,
                                'S132': BU6,
                                'S133': BU6,
                                'S134': BU6,
                                'S135': EU6,
                                'S141': BN5,
                                'S142': EN5,
                                'S143': EN5,
                                'S144': EN5,
                                'S145': KN5,
                                'S151': EN5,
                                'S152': HN5,
                                'S153': HN5,
                                'S154': HN5,
                                'S155': KN5,
                                'S211': AU6,
                                'S212': AU6,
                                'S213': AU6,
                                'S214': AU6,
                                'S215': DU6,
                                'S221': AU6,
                                'S222': AU6,
                                'S223': AU6,
                                'S224': AU6,
                                'S225': DU6,
                                'S231': BU6,
                                'S232': BU6,
                                'S233': BU6,
                                'S234': XU6,
                                'S235': RU6,
                                'S241': BN5,
                                'S242': EN5,
                                'S243': EN5,
                                'S244': EN5,
                                'S245': KN5,
                                'S251': HN5,
                                'S252': HN5,
                                'S253': HN5,
                                'S254': HN5,
                                'S255': KN5,
                                'S311': CF6,
                                'S312': CF6,
                                'S313': CF6,
                                'S314': CF6,
                                'S315': FF6,
                                'S321': AU6,
                                'S322': AU6,
                                'S323': AU6,
                                'S324': AU6,
                                'S325': TU6,
                                'S331': AU6,
                                'S332': AU6,
                                'S333': AU6,
                                'S334': XU6,
                                'S335': RU6,
                                'S341': EN5,
                                'S342': EN5,
                                'S343': GN5,
                                'S344': GN5,
                                'S345': JN5,
                                'S351': GN5,
                                'S352': GN5,
                                'S353': GN5,
                                'S354': GN5,
                                'S355': JN5,
                                'S411': CF6,
                                'S412': CF6,
                                'S413': CF6,
                                'S414': YF6,
                                'S415': UF6,
                                'S421': AF6,
                                'S422': AF6,
                                'S423': AF6,
                                'S424': XF6,
                                'S425': RF6,
                                'S431': AF6,
                                'S432': AF6,
                                'S433': XF6,
                                'S434': DF6,
                                'S435': RF6,
                                'S441': GN6,
                                'S442': GN6,
                                'S443': GN6,
                                'S444': JN6,
                                'S445': JN6,
                                'S451': GN6,
                                'S452': GN6,
                                'S453': GN6,
                                'S454': JN6,
                                'S455': JN6,
                                'S511': CS6,
                                'S512': CS6,
                                'S513': YS6,
                                'S514': FS6,
                                'S515': US6,
                                'S521': CF6,
                                'S522': CF6,
                                'S523': FF6,
                                'S524': FF6,
                                'S525': SF6,
                                'S531': FF6,
                                'S532': FF6,
                                'S533': LF6,
                                'S534': SF6,
                                'S535': SF6,
                                'S541': LS6,
                                'S542': LS6,
                                'S543': LS6,
                                'S544': SS6,
                                'S545': SS6,
                                'S551': SS6,
                                'S552': SS6,
                                'S553': SS6,
                                'S554': SS6,
                                'S555': SS6,
                                'S611': CS67,
                                'S612': FS67,
                                'S613': FS67,
                                'S614': SS67,
                                'S615': SS67,
                                'S621': FS67,
                                'S622': FS67,
                                'S623': FS67,
                                'S624': SS67,
                                'S625': SS67,
                                'S631': SS67,
                                'S632': SS67,
                                'S633': SS67,
                                'S634': SS67,
                                'S635': SS67,
                                'S641': SS67,
                                'S642': SS67,
                                'S643': SS67,
                                'S644': SS67,
                                'S645': SS67,
                                'S651': SS67,
                                'S652': SS67,
                                'S653': SS67,
                                'S654': SS67,
                                'S655': SS67,
                                'S711': FG67,
                                'S712': FG67,
                                'S713': SG67,
                                'S714': SG67,
                                'S715': SG67,
                                'S721': SG67,
                                'S722': SG67,
                                'S723': SG67,
                                'S724': SG67,
                                'S725': SG67,
                                'S731': SG67,
                                'S732': SG67,
                                'S733': SG67,
                                'S734': SG67,
                                'S735': SG67,
                                'S741': SG67,
                                'S742': SG67,
                                'S743': SG67,
                                'S744': SG67,
                                'S745': SG67,
                                'S751': SG67,
                                'S752': SG67,
                                'S753': SG67,
                                'S754': SG67,
                                'S755': SG67,
                                'S811': SW67,
                                'S812': SW67,
                                'S813': SW67,
                                'S814': SW67,
                                'S815': SW67,
                                'S821': SW67,
                                'S822': SW67,
                                'S823': SW67,
                                'S824': SW67,
                                'S825': SW67,
                                'S831': SW67,
                                'S832': SW67,
                                'S833': SW67,
                                'S834': SW67,
                                'S835': SW67,
                                'S841': SW67,
                                'S842': SW67,
                                'S843': SW67,
                                'S844': SW67,
                                'S845': SW67,
                                'S851': SW67,
                                'S852': SW67,
                                'S853': SW67,
                                'S854': SW67,
                                'S855': SW67,
                                'T111': AU6,
                                'T112': AU6,
                                'T113': AU6,
                                'T114': AU6,
                                'T115': XU6,
                                'T121': BU6,
                                'T122': BU6,
                                'T123': BU6,
                                'T124': BU6,
                                'T125': EU6,
                                'T131': BU6,
                                'T132': BU6,
                                'T133': BU6,
                                'T134': BU6,
                                'T135': EU6,
                                'T141': BU6,
                                'T142': BU6,
                                'T143': EU6,
                                'T144': EU6,
                                'T145': KU6,
                                'T151': BN6,
                                'T152': BN6,
                                'T153': EN6,
                                'T154': HN6,
                                'T155': KN6,
                                'T211': AU6,
                                'T212': AU6,
                                'T213': AU6,
                                'T214': AU6,
                                'T215': XU6,
                                'T221': AU6,
                                'T222': AU6,
                                'T223': AU6,
                                'T224': AU6,
                                'T225': DU6,
                                'T231': BU6,
                                'T232': BU6,
                                'T233': BU6,
                                'T234': BU6,
                                'T235': EU6,
                                'T241': BU6,
                                'T242': BU6,
                                'T243': EU6,
                                'T244': EU6,
                                'T245': KU6,
                                'T251': BN6,
                                'T252': EN6,
                                'T253': HN6,
                                'T254': HN6,
                                'T255': KN6,
                                'T311': AF6,
                                'T312': AF6,
                                'T313': AF6,
                                'T314': AF6,
                                'T315': XF6,
                                'T321': AU6,
                                'T322': AU6,
                                'T323': AU6,
                                'T324': AU6,
                                'T325': DU6,
                                'T331': BU6,
                                'T332': BU6,
                                'T333': BU6,
                                'T334': BU6,
                                'T335': TU6,
                                'T341': BU6,
                                'T342': BU6,
                                'T343': EU6,
                                'T344': EU6,
                                'T345': KU6,
                                'T351': EN6,
                                'T352': EN6,
                                'T353': HN6,
                                'T354': HN6,
                                'T355': KN6,
                                'T411': CF7,
                                'T411': CF7,
                                'T412': CF7,
                                'T413': CF7,
                                'T414': CF7,
                                'T415': WF7,
                                'T421': AF7,
                                'T422': AF7,
                                'T423': AF7,
                                'T424': AF7,
                                'T425': WF7,
                                'T431': AF6,
                                'T432': AF6,
                                'T433': AF6,            # Shown in The Sager Weathercaster as '7433'.
                                'T434': AF6,
                                'T435': TF6,
                                'T441': AF6,
                                'T442': DF6,
                                'T443': GF6,
                                'T444': JF6,
                                'T445': JF6,
                                'T451': DN6,
                                'T452': GN6,
                                'T453': GN6,
                                'T454': JN6,
                                'T455': JN6,
                                'T511': CS7,
                                'T512': CS7,
                                'T513': CS7,
                                'T514': CS7,
                                'T515': WS7,
                                'T521': CF7,
                                'T522': CF7,
                                'T523': CF7,
                                'T524': CF7,
                                'T525': UF7,
                                'T531': AF7,
                                'T532': AF7,
                                'T533': AF7,
                                'T534': DF7,
                                'T535': SF7,
                                'T541': DF6,
                                'T542': DF6,
                                'T543': JF6,
                                'T544': RF6,
                                'T545': RF6,
                                'T551': JS6,
                                'T552': JS6,
                                'T553': JS6,
                                'T554': JS6,
                                'T555': SS6,
                                'T611': CS7,
                                'T612': CS7,
                                'T613': CS7,
                                'T614': CS7,
                                'T615': US7,
                                'T621': CS7,
                                'T622': CS7,
                                'T623': CS7,
                                'T624': FS7,
                                'T625': US7,
                                'T631': CS7,
                                'T632': CS7,
                                'T633': FS7,
                                'T634': FS7,
                                'T635': SS7,
                                'T641': FS7,
                                'T642': LS7,
                                'T643': SS7,
                                'T644': SS7,
                                'T645': SS7,
                                'T651': SS7,
                                'T652': SS7,
                                'T653': SS7,
                                'T654': SS7,
                                'T655': SS7,
                                'T711': CG7,
                                'T712': CG7,
                                'T713': YG7,
                                'T714': FG7,
                                'T715': UG7,
                                'T721': FG7,
                                'T722': FG7,
                                'T723': FG7,
                                'T724': UG7,
                                'T725': SG7,
                                'T731': FG7,
                                'T732': FG7,
                                'T733': SG7,
                                'T734': SG7,
                                'T735': SG7,
                                'T741': SG7,
                                'T742': SG7,
                                'T743': SG7,
                                'T744': SG7,
                                'T745': SG7,
                                'T751': SG7,
                                'T752': SG7,
                                'T753': SG7,
                                'T754': SG7,
                                'T755': SG7,
                                'T811': FW7,
                                'T812': FW7,
                                'T813': FW7,
                                'T814': SW7,
                                'T815': SW7,
                                'T821': FW7,
                                'T822': FW7,
                                'T823': SW7,
                                'T824': SW7,
                                'T825': SW7,
                                'T831': SW7,
                                'T832': SW7,
                                'T833': SW7,
                                'T834': SW7,
                                'T835': SW7,
                                'T841': SW7,
                                'T842': SW7,
                                'T843': SW7,
                                'T844': SW7,
                                'T845': SW7,
                                'T851': SW7,
                                'T852': SW7,
                                'T853': SW7,
                                'T854': SW7,
                                'T855': SW7,
                                'U111': AD7,
                                'U112': AD7,
                                'U113': AD7,
                                'U114': AD7,
                                'U115': XD7,
                                'U121': BD7,
                                'U122': BD7,
                                'U123': BD7,
                                'U124': BD7,
                                'U125': XD7,
                                'U131': BD6,
                                'U132': BD6,
                                'U133': BD6,
                                'U134': BD6,
                                'U135': ED6,
                                'U141': BU6,
                                'U142': BU6,
                                'U143': EU6,
                                'U144': EU6,
                                'U145': KU6,
                                'U151': BN6,
                                'U152': BN6,
                                'U153': EN6,
                                'U154': HN6,
                                'U155': KN6,
                                'U211': AU7,
                                'U212': AU7,
                                'U213': AU7,
                                'U214': AU7,
                                'U215': XU7,
                                'U221': AD7,
                                'U222': AD7,
                                'U223': AD7,
                                'U224': AD7,
                                'U225': XD7,
                                'U231': AD6,
                                'U232': AD6,
                                'U233': AD6,
                                'U234': AD6,
                                'U235': DD6,
                                'U241': BU6,
                                'U242': BU6,
                                'U243': EU6,
                                'U244': EU6,
                                'U245': KU6,
                                'U251': BN6,
                                'U252': EN6,
                                'U253': HN6,
                                'U254': HN6,
                                'U255': KN6,
                                'U311': CF7,
                                'U312': CF7,
                                'U313': CF7,
                                'U314': CF7,
                                'U315': XF7,
                                'U321': AU7,
                                'U322': AU7,
                                'U323': AU7,
                                'U324': AU7,
                                'U325': XU7,
                                'U331': AU6,
                                'U332': AU6,
                                'U333': AU6,
                                'U334': AU6,
                                'U335': TU6,
                                'U341': BU6,
                                'U342': BU6,
                                'U343': EU6,
                                'U344': DU6,
                                'U345': JU6,
                                'U351': EN6,
                                'U352': EN6,
                                'U353': HN6,
                                'U354': HN6,
                                'U355': JN6,
                                'U411': CF7,
                                'U412': CF7,
                                'U413': CF7,
                                'U414': CF7,
                                'U415': WF7,
                                'U421': CF7,
                                'U422': CF7,
                                'U423': CF7,
                                'U424': CF7,
                                'U425': WF7,
                                'U431': AU7,
                                'U432': AU7,
                                'U433': AF7,
                                'U434': AF7,
                                'U435': TF7,
                                'U441': AF6,
                                'U442': DF6,
                                'U443': GF6,
                                'U444': JF6,
                                'U445': JF6,
                                'U511': CS7,
                                'U512': CS7,
                                'U513': CS7,
                                'U514': CS7,
                                'U515': WS7,
                                'U521': CF7,
                                'U522': CF7,
                                'U523': CF7,
                                'U524': CF7,
                                'U525': UF7,
                                'U531': AF7,
                                'U532': CF7,
                                'U533': CF7,
                                'U534': YF7,
                                'U535': UF7,
                                'U541': DF7,
                                'U542': DF7,
                                'U543': JF7,
                                'U544': SF7,
                                'U545': SF7,
                                'U551': LS7,
                                'U552': SS7,
                                'U553': SS7,
                                'U554': SS7,
                                'U555': SS7,
                                'U611': CS7,
                                'U612': CS7,
                                'U613': CS7,
                                'U614': CS7,
                                'U615': US7,
                                'U621': CS7,
                                'U622': CS7,
                                'U623': CS7,
                                'U624': FS7,
                                'U625': US7,
                                'U631': CS7,
                                'U632': CS7,
                                'U633': FS7,
                                'U634': FS7,
                                'U635': SS7,
                                'U641': FS7,
                                'U642': LS7,
                                'U643': SS7,
                                'U644': SS7,
                                'U645': SS7,
                                'U651': SS7,
                                'U652': SS7,
                                'U653': SS7,
                                'U654': SS7,
                                'U655': SS7,
                                'U711': CG7,
                                'U712': CG7,
                                'U713': YG7,
                                'U714': FG7,
                                'U715': UG7,
                                'U721': FG7,
                                'U722': FG7,
                                'U723': FG7,
                                'U724': UG7,
                                'U725': UG7,
                                'U731': FG7,
                                'U732': FG7,
                                'U733': SG7,
                                'U734': SG7,
                                'U735': SG7,
                                'U741': SG7,
                                'U742': SG7,
                                'U743': SG7,
                                'U744': SG7,
                                'U745': SG7,
                                'U751': SG7,
                                'U752': SG7,
                                'U753': SG7,
                                'U754': SG7,
                                'U755': SG7,
                                'U811': FW7,
                                'U812': FW7,
                                'U813': FW7,
                                'U814': SW7,
                                'U815': SW7,
                                'U821': FW7,
                                'U822': FW7,
                                'U823': SW7,
                                'U824': SW7,
                                'U825': SW7,
                                'U831': SW7,
                                'U832': SW7,
                                'U833': SW7,
                                'U834': SW7,
                                'U835': SW7,
                                'U841': SW7,
                                'U842': SW7,
                                'U843': SW7,
                                'U844': SW7,
                                'U845': SW7,
                                'U851': SW7,
                                'U852': SW7,
                                'U853': SW7,
                                'U854': SW7,
                                'U855': SW7,
                                'V111': AU7,
                                'V112': AU7,
                                'V113': AU7,
                                'V114': AU7,
                                'V115': XU7,
                                'V121': AU7,
                                'V122': AU7,
                                'V123': AU7,
                                'V124': AU7,
                                'V125': DU7,
                                'V131': BD7,
                                'V132': BD7,
                                'V133': BD7,
                                'V134': BD7,
                                'V135': ED7,
                                'V141': BU6,
                                'V142': BU6,
                                'V143': XU6,
                                'V144': EU6,
                                'V145': EU6,
                                'V151': BN6,
                                'V152': BN6,
                                'V153': EN6,
                                'V154': HN6,
                                'V155': KN6,
                                'V211': AU7,
                                'V212': AU7,
                                'V213': AU7,
                                'V214': AU7,
                                'V215': XU7,
                                'V221': AU7,
                                'V222': AU7,
                                'V223': AU7,
                                'V224': AU7,
                                'V225': DU7,
                                'V231': AU7,
                                'V232': AU7,
                                'V233': AU7,
                                'V234': AU7,
                                'V235': DU7,
                                'V241': AU6,
                                'V242': AU6,
                                'V243': XU6,
                                'V244': DU6,
                                'V245': RU6,
                                'V251': AN6,
                                'V252': DN6,
                                'V253': DN6,
                                'V254': HN6,
                                'V255': JN6,
                                'V311': CF7,
                                'V312': CF7,
                                'V313': CF7,
                                'V314': CF7,
                                'V315': XF7,
                                'V321': CU7,
                                'V322': CU7,
                                'V323': CU7,
                                'V324': CU7,
                                'V325': FU7,
                                'V331': AU7,
                                'V332': AU7,
                                'V333': AU7,
                                'V334': XU7,
                                'V335': TU7,
                                'V341': AU7,
                                'V342': AU7,
                                'V343': XU7,
                                'V344': DU7,
                                'V345': RU7,
                                'V351': DN7,
                                'V352': DN7,
                                'V353': DN7,
                                'V354': HN7,
                                'V355': JN7,
                                'V411': CF7,
                                'V412': CF7,
                                'V413': CF7,
                                'V414': CF7,
                                'V415': WF7,
                                'V421': CF7,
                                'V422': CF7,
                                'V423': CF7,
                                'V424': YF7,
                                'V425': UF7,
                                'V431': AF7,
                                'V432': AF7,
                                'V433': AF7,
                                'V434': YF7,
                                'V435': UF7,
                                'V441': AF7,
                                'V442': XF7,
                                'V443': DF7,
                                'V444': DF7,
                                'V445': RF7,
                                'V451': DN7,
                                'V452': DN7,
                                'V453': DN7,
                                'V454': JN7,
                                'V455': RN7,
                                'V511': CS7,
                                'V512': CS7,
                                'V513': CS7,
                                'V514': YS7,
                                'V515': US7,
                                'V521': CF7,
                                'V522': CF7,
                                'V523': YF7,
                                'V524': YF7,
                                'V525': UF7,
                                'V531': CF7,
                                'V532': CF7,
                                'V533': YF7,
                                'V534': YF7,
                                'V535': SF7,
                                'V541': FF7,
                                'V542': FF7,
                                'V543': SF7,
                                'V544': SF7,
                                'V545': SF7,
                                'V551': FS7,
                                'V552': FS7,
                                'V553': SS7,
                                'V554': SS7,
                                'V555': SS7,
                                'V611': CS7,
                                'V612': CS7,
                                'V613': YS7,
                                'V614': YS7,
                                'V615': US7,
                                'V621': CS7,
                                'V622': YS7,
                                'V623': YS7,
                                'V624': FS7,
                                'V625': US7,
                                'V631': CS7,
                                'V632': YS7,
                                'V633': FS7,
                                'V634': FS7,
                                'V635': SS7,
                                'V641': FS7,
                                'V642': SS7,
                                'V643': SS7,
                                'V644': SS7,
                                'V645': SS7,
                                'V651': SS7,
                                'V652': SS7,
                                'V653': SS7,
                                'V654': SS7,
                                'V655': SS7,
                                'V711': CG7,
                                'V712': YG7,
                                'V713': FG7,
                                'V714': FG7,
                                'V715': UG7,
                                'V721': FG7,
                                'V722': FG7,
                                'V723': FG7,
                                'V724': UG7,
                                'V725': SG7,
                                'V731': FG7,
                                'V732': FG7,
                                'V733': SG7,
                                'V734': SG7,
                                'V735': SG7,
                                'V741': SG7,
                                'V742': SG7,
                                'V743': SG7,
                                'V744': SG7,
                                'V745': SG7,
                                'V751': SG7,
                                'V752': SG7,
                                'V753': SG7,
                                'V754': SG7,
                                'V755': SG7,
                                'V811': FW7,
                                'V812': FW7,
                                'V813': FW7,
                                'V814': SW7,
                                'V815': SW7,
                                'V821': FW7,
                                'V822': FW7,
                                'V823': SW7,
                                'V824': SW7,
                                'V825': SW7,
                                'V831': SW7,
                                'V832': SW7,
                                'V833': SW7,
                                'V834': SW7,
                                'V835': SW7,
                                'V841': SW7,
                                'V842': SW7,
                                'V843': SW7,
                                'V844': SW7,
                                'V845': SW7,
                                'V851': SW7,
                                'V852': SW7,
                                'V853': SW7,
                                'V854': SW7,
                                'V855': SW7,
                                'W111': AU7,
                                'W112': AU7,
                                'W113': AU7,
                                'W114': AU7,
                                'W115': XU7,
                                'W121': AU7,
                                'W122': AU7,
                                'W123': AU7,
                                'W124': AU7,
                                'W125': XU7,
                                'W131': AD7,
                                'W132': AD7,
                                'W133': AD7,
                                'W134': AD7,
                                'W135': XD7,
                                'W141': BU7,
                                'W142': AU7,
                                'W143': AU7,
                                'W144': XU7,
                                'W145': RU7,
                                'W151': BN7,
                                'W152': BN7,
                                'W153': DN7,
                                'W154': DN7,
                                'W155': RN7,
                                'W211': CU7,
                                'W212': CU7,
                                'W213': CU7,
                                'W214': CU7,
                                'W215': YU7,
                                'W221': AU7,
                                'W222': AU7,
                                'W223': AU7,
                                'W224': AU7,
                                'W225': XU7,
                                'W231': AU7,
                                'W232': AU7,
                                'W233': AU7,
                                'W234': AU7,
                                'W235': XU7,
                                'W241': AU7,
                                'W242': AU7,
                                'W243': AU7,
                                'W244': XU7,
                                'W245': RU7,
                                'W251': AN7,
                                'W252': AN7,
                                'W253': DN7,
                                'W254': DN7,
                                'W255': RN7,
                                'W311': CF7,
                                'W312': CF7,
                                'W313': CF7,
                                'W314': CF7,
                                'W315': YF7,
                                'W321': AU7,
                                'W322': AU7,
                                'W323': AU7,
                                'W324': AU7,
                                'W325': XU7,
                                'W331': AU7,
                                'W332': AU7,
                                'W333': AU7,
                                'W334': AU7,
                                'W335': TU7,
                                'W341': AU7,
                                'W342': AU7,
                                'W343': AU7,
                                'W344': XU7,
                                'W345': RU7,
                                'W351': AN7,
                                'W352': AN7,
                                'W353': DN7,
                                'W354': DN7,
                                'W355': RN7,
                                'W411': CF7,
                                'W412': CF7,
                                'W413': CF7,
                                'W414': CF7,
                                'W415': WF7,
                                'W421': CF7,
                                'W422': CF7,
                                'W423': CF7,
                                'W424': CF7,
                                'W425': WF7,
                                'W431': AF7,
                                'W432': AF7,
                                'W433': AF7,
                                'W434': AF7,
                                'W435': TF7,
                                'W441': AF7,
                                'W442': AF7,
                                'W443': XF7,
                                'W444': DF7,
                                'W445': RF7,
                                'W451': XN7,
                                'W452': XN7,
                                'W453': DN7,
                                'W454': RN7,
                                'W455': RN7,
                                'W511': CS8,
                                'W512': CS8,
                                'W513': CS8,
                                'W514': CS8,
                                'W515': WS8,
                                'W521': CF7,
                                'W522': CF7,
                                'W523': CF7,
                                'W524': CF7,
                                'W525': UF7,
                                'W531': AF7,
                                'W532': CF7,
                                'W533': CF7,
                                'W534': YF7,
                                'W535': UF7,
                                'W541': CF7,
                                'W542': YF7,
                                'W543': FF7,
                                'W544': FF7,
                                'W545': SF7,
                                'W551': FS7,
                                'W552': FS7,
                                'W553': FS7,
                                'W554': SS7,
                                'W555': SS7,
                                'W611': CS8,
                                'W612': CS8,
                                'W613': CS8,
                                'W614': YS8,
                                'W615': WS8,
                                'W621': CS8,
                                'W622': CS8,
                                'W623': CS8,
                                'W624': YS8,
                                'W625': US8,
                                'W631': CS8,
                                'W632': CS8,
                                'W633': YS8,
                                'W634': FS8,
                                'W635': US8,
                                'W641': CS8,
                                'W642': FS8,
                                'W643': FS8,
                                'W644': FS8,
                                'W645': SS8,
                                'W651': FS8,
                                'W652': FS8,
                                'W653': SS8,
                                'W654': SS8,
                                'W655': SS8,
                                'W711': CG8,
                                'W712': CG8,
                                'W713': YG8,
                                'W714': YG8,
                                'W715': UG8,
                                'W721': CG8,
                                'W722': CG8,
                                'W723': YG8,
                                'W724': FG8,
                                'W725': SG8,
                                'W731': FG8,
                                'W732': FG8,
                                'W733': FG8,
                                'W734': SG8,
                                'W735': SG8,
                                'W741': FG8,
                                'W742': FG8,
                                'W743': SG8,
                                'W744': SG8,
                                'W745': SG8,
                                'W751': SG8,
                                'W752': SG8,
                                'W753': SG8,
                                'W754': SG8,
                                'W755': SG8,
                                'W811': FW8,
                                'W812': FW8,
                                'W813': FW8,
                                'W814': FW8,
                                'W815': UW8,
                                'W821': FW8,
                                'W822': FW8,
                                'W823': FW8,
                                'W824': SW8,
                                'W825': SW8,
                                'W831': SW8,
                                'W832': SW8,
                                'W833': SW8,
                                'W834': SW8,
                                'W835': SW8,
                                'W841': FW8,
                                'W842': FW8,
                                'W843': SW8,
                                'W844': SW8,
                                'W845': SW8,
                                'W851': SW8,
                                'W852': SW8,
                                'W853': SW8,
                                'W854': SW8,
                                'W855': SW8,
                                'X111': AD8,
                                'X112': AD8,
                                'X113': AD8,
                                'X114': AD8,
                                'X115': XD8,
                                'X121': AD7,
                                'X122': AD7,
                                'X123': AD7,
                                'X124': AD7,
                                'X125': XD7,
                                'X131': AD7,
                                'X132': AD7,
                                'X133': AD7,
                                'X134': AD7,
                                'X135': XD7,
                                'X141': BU7,
                                'X142': BU7,
                                'X143': EU7,
                                'X144': EU7,
                                'X145': KU7,
                                'X151': BN7,
                                'X152': BN7,
                                'X153': EN7,
                                'X154': HN7,
                                'X155': KN7,
                                'X211': CU8,
                                'X212': CU8,
                                'X213': CU8,
                                'X214': CU8,
                                'X215': YU8,
                                'X221': AD8,
                                'X222': AD8,
                                'X223': AD8,
                                'X224': AD8,
                                'X225': XD8,
                                'X231': AD7,
                                'X232': AD7,
                                'X233': AD7,
                                'X234': AD7,
                                'X235': XD7,
                                'X241': BU7,
                                'X242': BU7,
                                'X243': EU7,
                                'X244': EU7,
                                'X245': KU7,
                                'X251': BN7,
                                'X252': EN7,
                                'X253': EN7,
                                'X254': HN7,
                                'X255': KN7,
                                'X311': CF8,
                                'X312': CF8,
                                'X313': CF8,
                                'X314': CF8,
                                'X315': YF8,
                                'X321': CU8,
                                'X322': CU8,
                                'X323': CU8,
                                'X324': CU8,
                                'X325': YU8,
                                'X331': AU7,
                                'X332': AU7,
                                'X333': AU7,
                                'X334': AU7,
                                'X335': TU7,
                                'X341': AU7,
                                'X342': AU7,
                                'X343': DU7,
                                'X344': DU7,
                                'X345': JU7,
                                'X351': BN7,
                                'X352': EN7,
                                'X353': DN7,
                                'X354': GN7,
                                'X355': JN7,
                                'X411': CF8,
                                'X412': CF8,
                                'X413': CF8,
                                'X414': CF8,
                                'X415': WF8,
                                'X421': CF8,
                                'X422': CF8,
                                'X423': CF8,
                                'X424': CF8,
                                'X425': WF8,
                                'X431': AU7,
                                'X432': AU7,
                                'X433': AF7,
                                'X434': AF7,
                                'X435': TF7,
                                'X441': AF7,
                                'X442': DF7,
                                'X443': DF7,
                                'X444': DF7,
                                'X445': JF7,
                                'X451': DN7,
                                'X452': DN7,
                                'X453': DN7,
                                'X454': JN7,
                                'X455': JN7,
                                'X511': CS8,
                                'X512': CS8,
                                'X513': CS8,
                                'X514': CS8,
                                'X515': WS8,
                                'X521': CF8,
                                'X522': CF8,
                                'X523': CF8,
                                'X524': CF8,
                                'X525': UF8,
                                'X531': AF8,
                                'X532': CF8,
                                'X533': CF8,
                                'X534': YF8,
                                'X535': UF8,
                                'X541': AF7,
                                'X542': DF7,
                                'X543': DF7,
                                'X544': SF7,
                                'X545': SF7,
                                'X551': FS7,
                                'X552': FS7,
                                'X553': SS7,
                                'X554': SS7,
                                'X555': SS7,
                                'X611': CS8,
                                'X612': CS8,
                                'X613': CS8,
                                'X614': CS8,
                                'X615': WS8,
                                'X621': CS8,
                                'X622': CS8,
                                'X623': CS8,
                                'X624': YS8,
                                'X625': US8,
                                'X631': CS8,
                                'X632': CS8,
                                'X633': FS8,
                                'X634': FS8,
                                'X635': US8,
                                'X641': FS8,
                                'X642': FS8,
                                'X643': FS8,
                                'X644': SS8,
                                'X645': SS8,
                                'X651': SS8,
                                'X652': SS8,
                                'X653': SS8,
                                'X654': SS8,
                                'X655': SS8,
                                'X711': CG8,
                                'X712': CG8,
                                'X713': CG8,
                                'X714': YG8,
                                'X715': UG8,
                                'X721': CG8,
                                'X722': CG8,
                                'X723': YG8,
                                'X724': FG8,
                                'X725': UG8,
                                'X731': FG8,
                                'X732': FG8,
                                'X733': FG8,
                                'X734': SG8,
                                'X735': SG8,
                                'X741': FG8,
                                'X742': SG8,
                                'X743': SG8,
                                'X744': SG8,
                                'X745': SG8,
                                'X751': SG8,
                                'X752': SG8,
                                'X753': SG8,
                                'X754': SG8,
                                'X755': SG8,
                                'X811': CW8,
                                'X812': FW8,
                                'X813': FW8,
                                'X814': FW8,
                                'X815': UW8,
                                'X821': FW8,
                                'X822': FW8,
                                'X823': FW8,
                                'X824': SW8,
                                'X825': UW8,
                                'X831': SW8,
                                'X832': SW8,
                                'X833': SW8,
                                'X834': SW8,
                                'X835': SW8,
                                'X841': SW8,
                                'X842': SW8,
                                'X843': SW8,
                                'X844': SW8,
                                'X845': SW8,
                                'X851': SW8,
                                'X852': SW8,
                                'X853': SW8,
                                'X854': SW8,
                                'X855': SW8,
                                'Y111': CU8,
                                'Y112': CU8,
                                'Y113': CU8,
                                'Y114': CU8,
                                'Y115': XU8,
                                'Y121': AU8,
                                'Y122': AU8,
                                'Y123': AU8,
                                'Y124': AU8,
                                'Y125': DU8,
                                'Y131': AD7,
                                'Y132': AD7,
                                'Y133': AD7,
                                'Y134': AD7,
                                'Y135': DD7,
                                'Y141': AU7,
                                'Y142': AU7,
                                'Y143': XU7,
                                'Y144': DU7,
                                'Y145': RU7,
                                'Y151': AN7,
                                'Y152': AN7,
                                'Y153': DN7,
                                'Y154': DN7,
                                'Y155': RN7,
                                'Y211': CU8,
                                'Y212': CU8,
                                'Y213': CU8,
                                'Y214': CU8,
                                'Y215': YU8,
                                'Y221': CU8,
                                'Y222': CU8,
                                'Y223': CU8,
                                'Y224': CU8,
                                'Y225': FU8,
                                'Y231': AU7,
                                'Y232': AU7,
                                'Y233': AU7,
                                'Y234': AU7,
                                'Y235': DU7,
                                'Y241': AU7,
                                'Y242': AU7,
                                'Y243': XU7,
                                'Y244': DU7,
                                'Y245': RU7,
                                'Y251': AN7,
                                'Y252': XN7,
                                'Y253': DN7,
                                'Y254': DN7,
                                'Y255': RN7,
                                'Y311': CF8,
                                'Y312': CF8,
                                'Y313': CF8,
                                'Y314': CF8,
                                'Y315': YF8,
                                'Y321': CU8,
                                'Y322': CU8,
                                'Y323': CU8,
                                'Y324': CU8,
                                'Y325': FU8,
                                'Y331': AU8,
                                'Y332': AU8,
                                'Y333': AU8,
                                'Y334': AU8,
                                'Y335': TU8,
                                'Y341': AU7,
                                'Y342': AU7,
                                'Y343': XU7,
                                'Y344': DU7,
                                'Y345': RU7,
                                'Y351': AN7,
                                'Y352': XN7,
                                'Y353': DN7,
                                'Y354': DN7,
                                'Y355': RN7,
                                'Y411': CF8,
                                'Y412': CF8,
                                'Y413': CF8,
                                'Y414': CF8,
                                'Y415': WF8,
                                'Y421': CF8,
                                'Y422': CF8,
                                'Y423': CF8,
                                'Y424': CF8,
                                'Y425': UF8,
                                'Y431': AF8,
                                'Y432': AF8,
                                'Y433': CF8,
                                'Y434': YF8,
                                'Y435': UF8,
                                'Y441': AF7,
                                'Y442': XF7,
                                'Y443': DF7,
                                'Y444': DF7,
                                'Y445': RF7,
                                'Y451': DN7,
                                'Y452': DN7,
                                'Y453': FN7,
                                'Y454': SN7,
                                'Y455': SN7,
                                'Y511': CS8,
                                'Y512': CS8,
                                'Y513': CS8,
                                'Y514': YS8,
                                'Y515': WS8,
                                'Y521': CF8,
                                'Y522': CF8,
                                'Y523': CF8,
                                'Y524': YF8,
                                'Y525': UF8,
                                'Y531': CF8,
                                'Y532': CF8,
                                'Y533': YF8,
                                'Y534': YF8,
                                'Y535': SF8,
                                'Y541': CF8,
                                'Y542': YS8,
                                'Y543': FF8,
                                'Y544': SF8,
                                'Y545': SF8,
                                'Y551': FS8,
                                'Y552': FS8,
                                'Y553': SS8,
                                'Y554': SS8,
                                'Y555': SS8,
                                'Y611': CS8,
                                'Y612': CS8,
                                'Y613': CS8,
                                'Y614': FS8,
                                'Y615': US8,
                                'Y621': CS8,
                                'Y622': CS8,
                                'Y623': YS8,
                                'Y624': FS8,
                                'Y625': US8,
                                'Y631': CS8,
                                'Y632': YS8,
                                'Y633': FS8,
                                'Y634': FS8,
                                'Y635': SS8,
                                'Y641': FS8,
                                'Y642': FS8,
                                'Y643': FS8,
                                'Y644': SS8,
                                'Y645': SS8,
                                'Y651': FS8,
                                'Y652': FS8,
                                'Y653': SS8,
                                'Y654': SS8,
                                'Y655': SS8,
                                'Y711': CG8,
                                'Y712': CG8,
                                'Y713': YG8,
                                'Y714': FG8,
                                'Y715': SG8,
                                'Y721': CG8,
                                'Y722': YG8,
                                'Y723': FG8,
                                'Y724': FG8,
                                'Y725': SG8,
                                'Y731': FG8,
                                'Y732': FG8,
                                'Y733': FG8,
                                'Y734': SG8,
                                'Y735': SG8,
                                'Y741': SG8,
                                'Y742': SG8,
                                'Y743': SG8,
                                'Y744': SG8,
                                'Y745': SG8,
                                'Y751': SG8,
                                'Y752': SG8,
                                'Y753': SG8,
                                'Y754': SG8,
                                'Y755': SG8,
                                'Y811': FW8,
                                'Y812': FW8,
                                'Y813': FW8,
                                'Y814': FW8,
                                'Y815': SW8,
                                'Y821': FW8,
                                'Y822': FW8,
                                'Y823': FW8,
                                'Y824': SW8,
                                'Y825': SW8,
                                'Y831': FW8,
                                'Y832': FW8,
                                'Y833': SW8,
                                'Y834': SW8,
                                'Y835': SW8,
                                'Y841': SW8,
                                'Y842': SW8,
                                'Y843': SW8,
                                'Y844': SW8,
                                'Y845': SW8,
                                'Y851': SW8,
                                'Y852': SW8,
                                'Y853': SW8,
                                'Y854': SW8,
                                'Y855': SW8,
                                'Z111': AU9,
                                'Z112': AU9,
                                'Z113': AU9,
                                'Z114': AU9,
                                'Z115': TU9,
                                'Z121': AU9,
                                'Z122': AU9,
                                'Z123': AU9,
                                'Z124': AU9,
                                'Z125': TU9,
                                'Z131': AU9,
                                'Z132': AU9,
                                'Z133': AU9,
                                'Z134': AU9,
                                'Z135': RU9,
                                'Z141': BN9,
                                'Z142': EN9,
                                'Z143': HN9,
                                'Z144': HN9,
                                'Z145': NN9,
                                'Z151': BN9,
                                'Z152': HN9,
                                'Z153': HN9,
                                'Z154': HN9,
                                'Z155': NN9,
                                'Z211': AU9,
                                'Z212': AU9,
                                'Z213': AU9,
                                'Z214': AU9,
                                'Z215': TU9,
                                'Z221': AU9,
                                'Z222': AU9,
                                'Z223': AU9,
                                'Z224': AU9,
                                'Z225': TU9,
                                'Z231': AU9,
                                'Z232': AU9,
                                'Z233': AU9,
                                'Z234': AU9,
                                'Z235': RU9,
                                'Z241': BN9,
                                'Z242': EN9,
                                'Z243': HN9,
                                'Z244': HN9,
                                'Z245': NN9,
                                'Z251': HN9,
                                'Z252': HN9,
                                'Z253': HN9,
                                'Z254': HN9,
                                'Z255': NN9,
                                'Z311': AU9,
                                'Z312': AU9,
                                'Z313': AU9,
                                'Z314': AU9,
                                'Z315': TU9,
                                'Z321': AU9,
                                'Z322': AU9,
                                'Z323': AU9,
                                'Z324': AU9,
                                'Z325': TU9,
                                'Z331': AU9,
                                'Z332': AU9,
                                'Z333': AU9,
                                'Z334': AU9,
                                'Z335': RU9,
                                'Z341': EN9,
                                'Z342': HN9,
                                'Z343': HN9,
                                'Z344': HN9,
                                'Z345': NN9,
                                'Z351': GN9,
                                'Z352': GN9,
                                'Z353': GN9,
                                'Z354': GN9,
                                'Z355': NN9,
                                'Z411': AF9,
                                'Z412': AF9,
                                'Z413': AF9,
                                'Z414': AF9,
                                'Z415': TF9,
                                'Z421': AF9,
                                'Z422': AF9,
                                'Z423': AF9,
                                'Z424': AF9,
                                'Z425': RF9,
                                'Z431': AF9,
                                'Z432': AF9,
                                'Z433': AF9,
                                'Z434': XF9,
                                'Z435': RF9,
                                'Z441': GN9,
                                'Z442': GN9,
                                'Z443': GN9,
                                'Z444': GN9,
                                'Z445': MN9,
                                'Z451': GN9,
                                'Z452': GN9,
                                'Z453': GN9,
                                'Z454': GN9,
                                'Z455': MN9,
                                'Z511': CS9,
                                'Z512': CS9,
                                'Z513': CS9,
                                'Z514': YS9,
                                'Z515': SS9,
                                'Z521': CF9,
                                'Z522': CF9,
                                'Z523': YF9,
                                'Z524': FF9,
                                'Z525': SF9,
                                'Z531': AF9,
                                'Z532': AF9,
                                'Z533': DF9,
                                'Z534': FF9,
                                'Z535': SF9,
                                'Z541': GN9,
                                'Z542': GN9,
                                'Z543': GN9,
                                'Z544': MN9,
                                'Z545': MN9,
                                'Z551': JS9,
                                'Z552': JS9,
                                'Z553': MS9,
                                'Z554': MS9,
                                'Z555': MS9,
                                'Z611': CS9,
                                'Z612': CS9,
                                'Z613': FS9,
                                'Z614': FS9,
                                'Z615': SS9,
                                'Z621': CS9,
                                'Z622': YS9,
                                'Z623': FS9,
                                'Z624': SS9,
                                'Z625': SS9,
                                'Z631': FS9,
                                'Z632': FS9,
                                'Z633': FS9,
                                'Z634': SS9,
                                'Z635': SS9,
                                'Z641': LS9,
                                'Z642': LS9,
                                'Z643': LS9,
                                'Z644': PS9,
                                'Z645': PS9,
                                'Z651': LS9,
                                'Z652': LS9,
                                'Z653': PS9,
                                'Z654': PS9,
                                'Z655': PS9,
                                'Z711': FW97,
                                'Z712': FW97,
                                'Z713': SW97,
                                'Z714': SW97,
                                'Z715': SW97,
                                'Z721': FG97,
                                'Z722': FG97,
                                'Z723': SG97,
                                'Z724': SG97,
                                'Z725': SG97,
                                'Z731': FG97,
                                'Z732': FG97,
                                'Z733': SG97,
                                'Z734': SG97,
                                'Z735': SG97,
                                'Z741': LG97,
                                'Z742': LG97,
                                'Z743': LG97,
                                'Z744': PG97,
                                'Z745': PG97,
                                'Z751': LG97,
                                'Z752': LG97,
                                'Z753': PG97,
                                'Z754': PG97,
                                'Z755': PG97,
                                'Z811': SW97,
                                'Z812': SW97,
                                'Z813': SW97,
                                'Z814': SW97,
                                'Z815': SW97,
                                'Z821': SW97,
                                'Z822': SW97,
                                'Z823': SW97,
                                'Z824': SW97,
                                'Z825': SW97,
                                'Z831': SW97,
                                'Z832': SW97,
                                'Z833': SW97,
                                'Z834': SW97,
                                'Z835': SW97,
                                'Z841': LW97,
                                'Z842': LW97,
                                'Z843': LW97,
                                'Z844': PW97,
                                'Z845': PW97,
                                'Z851': LW97,
                                'Z852': LW97,
                                'Z853': PW97,
                                'Z854': PW97,
                                'Z855': PW97}

        # Return SagerWeathercaster forecast text as function output
        self.sager_data['Forecast'] = WeatherPredictionKey.get(Dial, 'Forecast Unavailable')
