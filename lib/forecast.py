""" Returns the WeatherFlow forecast variables required by the Raspberry Pi
Python app for WeatherFlow Tempest and Smart Home Weather stations.
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

# Import required library modules
from lib.system import system
from lib        import observation_format as observation
from lib        import derived_variables  as derive
from lib        import properties

# Import required Kivy modules
from kivy.network.urlrequest import UrlRequest
from kivy.logger             import Logger
from kivy.clock              import Clock
from kivy.app                import App

# Import required system modules
from datetime   import datetime, timedelta, time
import time     as UNIX
import certifi
import bisect
import pytz


class forecast():

    def __init__(self):
        self.app = App.get_running_app()
        self.met_data = properties.Met()

    def reset_forecast(self):

        """ Reset the weather forecast displayed on screen to default values and
        fetch new forecast from WeatherFlow BetterForecast API
        """

        # Reset the forecast and schedule new forecast to be generated
        self.met_data = properties.Met()
        self.update_display()
        if hasattr(self.app, 'ForecastPanel'):
            for panel in getattr(self.app, 'ForecastPanel'):
                panel.set_forecast_icon()
        Clock.schedule_once(self.fetch_forecast)

    def fetch_forecast(self, *largs):

        """ Fetch the latest daily and hourly weather forecast data using the
        WeatherFlow BetterForecast API
        """

        # Fetch latest hourly and daily forecast
        if int(self.app.config['System']['rest_api']):
            URL = 'https://swd.weatherflow.com/swd/rest/better_forecast?token={}&station_id={}'
            URL = URL.format(self.app.config['Keys']['WeatherFlow'],
                             self.app.config['Station']['StationID'])
            UrlRequest(URL,
                       on_success=self.success_forecast,
                       on_failure=self.fail_forecast,
                       on_error=self.fail_forecast,
                       timeout=int(self.app.config['System']['Timeout']),
                       ca_file=certifi.where())

    def schedule_forecast(self, dt):

        """ Schedule new Forecast to be fetched from the WeatherFlow
        BetterForecast API at the top of the next hour
        """

        # Calculate next forecast time for the top of the next hour
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        now = datetime.now(pytz.utc).astimezone(Tz)
        sched_time = Tz.localize(datetime.combine(now.date(), time(now.hour, 0, 0)) + timedelta(hours=1))

        # Schedule next forecast
        seconds_sched = (sched_time - now).total_seconds()
        self.app.schedule.metDownload.cancel()
        self.app.schedule.metDownload = Clock.schedule_once(self.fetch_forecast, seconds_sched)

    def success_forecast(self, request, response):

        """ Sucessfully fetched forecast from the WeatherFlow BetterForecast
        API. Parse forecast response

        INPUTS:
            request             UrlRequest object
            response            UrlRequest response

        """

        # Extract all required forecast data
        self.met_data['response'] = response
        self.extract_forecasts()

    def fail_forecast(self, *largs):

        """ Failed to fetch forecast from the WeatherFlow BetterForecast API.
        Reschedule fetch_forecast in 300 seconds

        INPUTS:
            request             UrlRequest object
            response            UrlRequest response

        """

        # Set forecast variables to blank and indicate to user that forecast is
        # unavailable
        self.met_data['Valid']        = '--'
        self.met_data['Temp']         = '--'
        self.met_data['highTemp']     = '--'
        self.met_data['lowTemp']      = '--'
        self.met_data['WindSpd']      = '--'
        self.met_data['WindGust']     = '--'
        self.met_data['WindDir']      = '--'
        self.met_data['PrecipPercnt'] = '--'
        self.met_data['PrecipDay']    = '--'
        self.met_data['PrecipAmount'] = '--'
        self.met_data['PrecipType']   = '--'
        self.met_data['Conditions']   = ''
        self.met_data['Icon']         = '-'
        self.met_data['Status']       = 'Forecast currently\nunavailable...'

        # Update display
        self.update_display()

        # Update forecast icon
        if hasattr(self.app, 'ForecastPanel'):
            for panel in getattr(self.app, 'ForecastPanel'):
                panel.set_forecast_icon()

        # Schedule new forecast to be downloaded in 5 minutes. 
        # Note seconds_sched refers to number of seconds since the function was 
        # last called.
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        now = datetime.now(pytz.utc).astimezone(Tz)
        sched_time = now + timedelta(minutes=5)
        seconds_sched = (sched_time - now).total_seconds()
        self.app.schedule.metDownload.cancel()
        self.app.schedule.metDownload = Clock.schedule_once(self.fetch_forecast, seconds_sched)

    def extract_forecasts(self):

        """ Extract all required forecasts (latest daily, latest hourly, 
        12-hourly and 5-day) WeatherFlow BetterForecast API
        """  

        # Extract full WeatherFlow BetterForecast dictionary
        if 'response' in self.met_data:
            full_forecast = self.met_data['response']
        else:
            return  

        # Get current time in station time zone
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        now = datetime.now(pytz.utc).astimezone(Tz)  

        # EXTRACT ALL REQUIRED FORCASTS
        # ======================================================================
        try:
            # Extract all hourly and daily forecasts
            self.met_data['all_hourly_forecasts'] = full_forecast['forecast']['hourly']
            self.met_data['all_daily_forecasts']  = full_forecast['forecast']['daily']

            # Extract current conditions
            self.met_data['current_conditions']  = full_forecast['current_conditions']

            # EXTRACT LATEST HOURLY AND NEXT 12 HOURLY FORECASTS
            # ------------------------------------------------------------------
            # Extract 'valid from' time of all available hourly forecasts 
            self.met_data['hourly_forecast_time'] = list(forecast['time'] for forecast in self.met_data['all_hourly_forecasts']) 
            
            # Extract forecast for the current hour
            self.met_data['current_hourly_idx'] = bisect.bisect_left(self.met_data['hourly_forecast_time'], int(UNIX.time()))
            self.met_data['current_hour']       = self.met_data['all_hourly_forecasts'][self.met_data['current_hourly_idx']]

            # Extract hourly forecasts for the next 12 hours
            self.met_data['12_hour'] = []
            for ii in range(12):
                self.met_data['12_hour'].append(self.met_data['all_hourly_forecasts'][self.met_data['current_hourly_idx'] + ii])

            # EXTRACT LATEST DAILY AND NEXT 5 DAILY FORECASTS
            # ------------------------------------------------------------------
            # Extract 'day_start_local' time of all available daily forecasts 
            daily_day_number = list(forecast['day_num'] for forecast in self.met_data['all_daily_forecasts'])

            # Extract forecast for the current day
            current_day_number = self.met_data['current_hour']['local_day']
            self.met_data['current_daily_idx'] = daily_day_number.index(current_day_number)
            self.met_data['current_day'] = self.met_data['all_daily_forecasts'][self.met_data['current_daily_idx']]

            # Extract daily forecasts for the next 5 days
            self.met_data['5_day'] = []
            for ii in range(5):
                self.met_data['5_day'].append(self.met_data['all_daily_forecasts'][self.met_data['current_daily_idx'] + ii])           

        # Unable to extract forecast data from JSON object. Set forecast
        # variables to blank and indicate to user that forecast is unavailable
        except (IndexError, KeyError, ValueError, TypeError):
            Clock.schedule_once(self.fail_forecast)

        # Parse forecast variables
        self.parse_forecast()

    def parse_forecast(self):

        """ Parse the latest daily and hourly weather forecast from the
        WeatherFlow BetterForecast API and format for display based on user
        specified units
        """

        # Get current time in station time zone
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        now = datetime.now(pytz.utc).astimezone(Tz)

        # Set time format based on user configuration
        if self.app.config['Display']['TimeFormat'] == '12 hr':
            if self.app.config['System']['Hardware'] == 'Other':
                time_format = '%#I %p'
            else:
                time_format = '%-I %p'
        else:
            time_format = '%H:%M'

        # EXTRACT ALL WEATHER VARIABLES FROM MET_DATA
        # ======================================================================
        #try:

        # EXTRACT WEATHER VARIABLES FROM CURRENT HOURLY FORECAST
        # ------------------------------------------------------------------
        # Extract temperature, wind speed, forecast icon and valid_time 
        # variables
        temperature    = [self.met_data['current_hour']['air_temperature'], 'c']
        wind_speed     = [self.met_data['current_hour']['wind_avg'], 'mps']
        wind_gust      = [self.met_data['current_hour']['wind_gust'], 'mps']
        wind_direction = [self.met_data['current_hour']['wind_direction'], 'degrees']
        forecast_icon  =  self.met_data['current_hour']['icon']
        valid_time     =  datetime.fromtimestamp(self.met_data['current_hour']['time'], pytz.utc).astimezone(Tz)

        # Extract precipitation type, percent, and amount variables
        if 'precip_type' in self.met_data['current_hour']:
            if self.met_data['current_hour']['precip_type'] in ['rain', 'snow']:
                precipitation_type = self.met_data['current_hour']['precip_type'].title() + 'fall'
            else:
                precipitation_type = self.met_data['current_hour']['precip_type'].title()
        else:
            precipitation_type = 'Rainfall'
        if 'precip_probability' in self.met_data['current_hour']:
            precipitation_percent = [self.met_data['current_hour']['precip_probability'], '%']
        else:
            precipitation_percent = [0, '%']
        if 'precip' in self.met_data['current_hour']:
            precipitation_amount = [self.met_data['current_hour']['precip'], 'mm']
        else:
            precipitation_amount = [0, 'mm']

        # Extract list of expected conditions and find time when current 
        # hourly forecast conditions will change
        conditions_list = list(forecast['conditions'] for forecast in self.met_data['all_hourly_forecasts'][self.met_data['current_hourly_idx']:])
        try:
            condition_change_idx = next(i for i, C in enumerate(conditions_list) if C != self.met_data['current_hour']['conditions'])
        except StopIteration:
            condition_change_idx = len(conditions_list) - 1
        time = datetime.fromtimestamp(self.met_data['hourly_forecast_time'][condition_change_idx], pytz.utc).astimezone(Tz)
        if time.date() == now.date():
            conditions = self.met_data['current_hour']['conditions'].capitalize() + ' until ' + datetime.strftime(time, time_format) + ' today'
        elif time.date() == now.date() + timedelta(days=1):
            conditions = self.met_data['current_hour']['conditions'].capitalize() + ' until ' + datetime.strftime(time, time_format) + ' tomorrow'
        else:
            conditions = self.met_data['current_hour']['conditions'].capitalize() + ' until ' + datetime.strftime(time, time_format) + ' on ' + time.strftime('%A')

        # Calculate derived variables from forecast
        wind_direction = derive.cardinal_wind_dir(wind_direction, wind_speed)

        # Convert forecast units as required
        temperature          = observation.units(temperature,          self.app.config['Units']['Temp'])
        wind_speed           = observation.units(wind_speed,           self.app.config['Units']['Wind'])
        wind_gust            = observation.units(wind_gust,            self.app.config['Units']['Wind'])
        wind_direction       = observation.units(wind_direction,       self.app.config['Units']['Direction'])
        precipitation_amount = observation.units(precipitation_amount, self.app.config['Units']['Precip'])

        # Define and format labels
        self.met_data['parsed'] = {}
        self.met_data['parsed']['current_hour'] = {}
        self.met_data['parsed']['current_hour']['valid_time']    = datetime.strftime(valid_time,             time_format)
        self.met_data['parsed']['current_hour']['temperature']   = observation.format(temperature,           'forecast_temp')
        self.met_data['parsed']['current_hour']['wind_speed']    = observation.format(wind_speed,            'forecast_wind')
        self.met_data['parsed']['current_hour']['wind_gust']     = observation.format(wind_gust,             'forecast_wind')
        self.met_data['parsed']['current_hour']['wind_dir']      = observation.format(wind_direction,        'Direction')
        self.met_data['parsed']['current_hour']['precip_percnt'] = observation.format(precipitation_percent, 'Humidity')
        self.met_data['parsed']['current_hour']['precip_amount'] = observation.format(precipitation_amount,  'Precip')
        self.met_data['parsed']['current_hour']['precip_type']   = precipitation_type
        self.met_data['parsed']['current_hour']['conditions']    = conditions
        self.met_data['parsed']['current_hour']['status']        = ''

        # Check expected conditions icon is recognised
        if forecast_icon in ['clear-day', 'clear-night', 'rainy', 'possibly-rainy-day',
                    'possibly-rainy-night', 'snow', 'possibly-snow-day',
                    'possibly-snow-night', 'sleet', 'possibly-sleet-day',
                    'possibly-sleet-night', 'thunderstorm', 'possibly-thunderstorm-day',
                    'possibly-thunderstorm-night', 'windy', 'foggy', 'cloudy',
                    'partly-cloudy-day', 'partly-cloudy-night']:
            self.met_data['parsed']['current_hour']['forecast_icon'] = forecast_icon
        else:
            self.met_data['parsed']['current_hour']['forecast_icon'] = '-'

        # EXTRACT WEATHER VARIABLES FROM NEXT 12 HOURLY FORECASTS
        # ------------------------------------------------------------------
        # Define required variables
        temperature           = []
        feels_like            = []
        wind_speed            = []
        wind_gust             = []
        wind_direction        = []
        forecast_icon         = []
        valid_time            = []
        precipitation_type    = []
        precipitation_percent = []
        precipitation_amount  = []
        conditions            = []

        # Loop over all available forecasts
        for ii, forecast in enumerate(self.met_data['12_hour']): 

            # Extract temperature, wind speed, forecast icon and valid_time 
            # variables
            temperature.append([forecast['air_temperature'], 'c'])
            feels_like.append([forecast['feels_like'], 'c'])
            wind_speed.append([forecast['wind_avg'], 'mps'])
            wind_gust.append([forecast['wind_gust'], 'mps'])
            wind_direction.append([forecast['wind_direction'], 'degrees'])
            forecast_icon.append(forecast['icon'])
            valid_time.append(datetime.fromtimestamp(forecast['time'], pytz.utc).astimezone(Tz))

            # Extract precipitation type, percent, and amount variables
            if 'precip_type' in forecast:
                precipitation_type.append(forecast['precip_type'])
            else:
                precipitation_type.append('rain')
            if 'precip_probability' in forecast:
                precipitation_percent.append([forecast['precip_probability'], '%'])
            else:
                precipitation_percent.append([0, '%'])
            if 'precip' in forecast:
                precipitation_amount.append([forecast['precip'], 'mm'])
            else:
                precipitation_amount.append([0, 'mm'])

            # Extract expected conditions
            conditions.append(forecast['conditions'].capitalize())

            # Calculate derived variables from forecast
            wind_direction[ii] = derive.cardinal_wind_dir(wind_direction[ii], wind_speed[ii])

            # Extract required color code
            color_code = ['#4575B4', '#74ADD1', '#ABD9E9','#E0F3F8', '#FFFFBF', '#FEE090', '#FDAE61', '#F46D43']
            color_cutoffs = [float(item) for item in list(self.app.config['FeelsLike'].values())]
            temperature[ii].append(color_code[bisect.bisect(color_cutoffs, forecast['air_temperature'])])
            feels_like[ii].append(color_code[bisect.bisect(color_cutoffs, forecast['feels_like'])])

        # Convert forecast units as required
        temperature          = observation.units(temperature,          self.app.config['Units']['Temp'])
        feels_like           = observation.units(feels_like,          self.app.config['Units']['Temp'])
        wind_speed           = observation.units(wind_speed,           self.app.config['Units']['Wind'])
        wind_gust            = observation.units(wind_gust,            self.app.config['Units']['Wind'])
        wind_direction       = observation.units(wind_direction,       self.app.config['Units']['Direction'])
        precipitation_amount = observation.units(precipitation_amount, self.app.config['Units']['Precip'])

        # Define and format labels
        self.met_data['parsed']['12_hour'] = {}
        self.met_data['parsed']['12_hour']['valid_time']    = [datetime.strftime(time, time_format) for time in valid_time]
        self.met_data['parsed']['12_hour']['temperature']   = observation.format(temperature,           'forecast_temp')
        self.met_data['parsed']['12_hour']['feels_like']    = observation.format(feels_like,           'forecast_temp')
        self.met_data['parsed']['12_hour']['wind_speed']    = observation.format(wind_speed,            'forecast_wind')
        self.met_data['parsed']['12_hour']['wind_gust']     = observation.format(wind_gust,             'forecast_wind')
        self.met_data['parsed']['12_hour']['wind_dir']      = observation.format(wind_direction,        'Direction')
        self.met_data['parsed']['12_hour']['precip_percnt'] = observation.format(precipitation_percent, 'Humidity')
        self.met_data['parsed']['12_hour']['precip_amount'] = observation.format(precipitation_amount,  'Precip')
        self.met_data['parsed']['12_hour']['precip_type']   = precipitation_type
        self.met_data['parsed']['12_hour']['conditions']    = conditions

        # Check expected conditions icon is recognised
        self.met_data['parsed']['12_hour']['forecast_icon'] = []
        for icon in forecast_icon:
            if icon in ['clear-day', 'clear-night', 'rainy', 'possibly-rainy-day',
                        'possibly-rainy-night', 'snow', 'possibly-snow-day',
                        'possibly-snow-night', 'sleet', 'possibly-sleet-day',
                        'possibly-sleet-night', 'thunderstorm', 'possibly-thunderstorm-day',
                        'possibly-thunderstorm-night', 'windy', 'foggy', 'cloudy',
                        'partly-cloudy-day', 'partly-cloudy-night']:
                self.met_data['parsed']['12_hour']['forecast_icon'].append(icon)
            else:
                self.met_data['parsed']['12_hour']['forecast_icon'].append('-')   

        # EXTRACT WEATHER VARIABLES FROM CURRENT DAILY FORECAST
        # ------------------------------------------------------------------
        # Extract weather variables from current daily forecast
        high_temperature  = [self.met_data['current_day']['air_temp_high'],      'c']
        low_temperature   = [self.met_data['current_day']['air_temp_low'],       'c']
        precipitation_day = [self.met_data['current_day']['precip_probability'], '%']

        # Convert forecast units as required
        high_temperature     = observation.units(high_temperature,     self.app.config['Units']['Temp'])
        low_temperature      = observation.units(low_temperature,      self.app.config['Units']['Temp'])

        # Define and format labels
        self.met_data['parsed']['current_day'] = {}
        self.met_data['parsed']['current_day']['high_temperature'] = observation.format(high_temperature,  'forecast_temp')
        self.met_data['parsed']['current_day']['low_temperature']  = observation.format(low_temperature,   'forecast_temp')
        self.met_data['parsed']['current_day']['precip_percnt']    = observation.format(precipitation_day, 'Humidity')

        # Update display
        self.update_display()

        # Update forecast icon
        if hasattr(self.app, 'ForecastPanel'):
            for panel in getattr(self.app, 'ForecastPanel'):
                panel.set_forecast_icon()

        # Schedule new forecast
        Clock.schedule_once(self.schedule_forecast)

        # Unable to extract forecast data from JSON object. Set forecast
        # variables to blank and indicate to user that forecast is unavailable
        #except (IndexError, KeyError, ValueError, TypeError):
        #    Clock.schedule_once(self.fail_forecast)

    def update_display(self):

        """ Update display with new forecast variables. Catch ReferenceErrors to
        prevent console crashing
        """

        # Update display values with new derived observations
        for forecast in self.met_data['parsed']:
            forecast_dict = {}
            for key, value in list(self.met_data['parsed'][forecast].items()):
                forecast_dict[key] = value 
            try:
                self.app.CurrentConditions.Met[forecast] = forecast_dict      
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'forecast: {system().log_time()} - Reference error')
                    reference_error = True
