""" Returns the WeatherFlow forecast variables required by the Raspberry Pi
Python app for WeatherFlow Tempest and Smart Home Weather stations.
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
                panel.setForecastIcon()
        Clock.schedule_once(self.fetch_forecast)

    def fetch_forecast(self, *largs):

        """ Fetch the latest daily and hourly weather forecast data using the
        WeatherFlow BetterForecast API
        """

        # Fetch latest hourly and daily forecast
        if self.app.config['System']['rest_api'] == '1':
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
        Now = datetime.now(pytz.utc).astimezone(Tz)
        sched_time = Tz.localize(datetime.combine(Now.date(), time(Now.hour, 0, 0)) + timedelta(hours=1))

        # Schedule next forecast
        seconds_sched = (sched_time - Now).total_seconds()
        self.app.Sched.metDownload.cancel()
        self.app.Sched.metDownload = Clock.schedule_once(self.fetch_forecast, seconds_sched)

    def success_forecast(self, Request, Response):

        """ Sucessfully fetched forecast from the WeatherFlow BetterForecast
        API. Parse forecast response

        INPUTS:
            Request             UrlRequest object
            Response            UrlRequest response

        """

        # Parse the latest daily and hourly weather forecast data
        self.met_data['Response'] = Response
        self.parse_forecast()

    def fail_forecast(self, *largs):

        """ Failed to fetch forecast from the WeatherFlow BetterForecast API.
        Reschedule fetch_forecast in 300 seconds

        INPUTS:
            Request             UrlRequest object
            Response            UrlRequest response

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
                panel.setForecastIcon()

        # Schedule new forecast to be downloaded in 5 minutes. Note secondsSched
        # refers to number of seconds since the function was last called.
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)
        sched_time = Now + timedelta(minutes=5)
        secondsSched = (sched_time - Now).total_seconds()
        self.app.Sched.metDownload.cancel()
        self.app.Sched.metDownload = Clock.schedule_once(self.fetch_forecast, secondsSched)

    def parse_forecast(self):

        """ Parse the latest daily and hourly weather forecast from the
        WeatherFlow BetterForecast API and format for display based on user
        specified units
        """

        # Extract Forecast dictionary
        if 'Response' in self.met_data:
            Forecast = self.met_data['Response']
        else:
            return

        # Get current time in station time zone
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Set time format based on user configuration
        if self.app.config['Display']['TimeFormat'] == '12 hr':
            if self.app.config['System']['Hardware'] == 'Other':
                TimeFormat = '%#I %p'
            else:
                TimeFormat = '%-I %p'
        else:
            TimeFormat = '%H:%M'

        # Extract all forecast data from WeatherFlow JSON object
        try:
            # Extract all hourly and daily forecasts
            hourlyForecasts  = (Forecast['forecast']['hourly'])
            dailyForecasts   = (Forecast['forecast']['daily'])

            # Extract 'valid from' time of all available hourly forecasts and
            # retrieve forecast for the current hour
            Hours          = list(forecast['time'] for forecast in hourlyForecasts)
            hoursInd       = bisect.bisect(Hours, int(UNIX.time()))
            hourlyCurrent  = hourlyForecasts[hoursInd]
            hourlyLocalDay = hourlyCurrent['local_day']

            # Extract 'Valid' until time of forecast for current hour
            Valid = Hours[bisect.bisect(Hours, int(UNIX.time()))]
            Valid = datetime.fromtimestamp(Valid, pytz.utc).astimezone(Tz)

            # Extract 'day_start_local' time of all available daily forecasts and
            # retrieve forecast for the current day
            dailyDayNum  = list(forecast['day_num'] for forecast in dailyForecasts)
            dailyCurrent = dailyForecasts[dailyDayNum.index(hourlyLocalDay)]

            # Extract weather variables from current hourly forecast
            Temp         = [hourlyCurrent['air_temperature'], 'c']
            WindSpd      = [hourlyCurrent['wind_avg'], 'mps']
            WindGust     = [hourlyCurrent['wind_gust'], 'mps']
            WindDir      = [hourlyCurrent['wind_direction'], 'degrees']
            Icon         =  hourlyCurrent['icon']

            # Extract Precipitation Type, Percent, and Amount from current hourly
            # forecast
            if 'precip_type' in hourlyCurrent:
                if hourlyCurrent['precip_type'] in ['rain', 'snow']:
                    PrecipType = hourlyCurrent['precip_type'].title() + 'fall'
                else:
                    PrecipType = hourlyCurrent['precip_type'].title()
            else:
                PrecipType = 'Rainfall'
            if 'precip_probability' in hourlyCurrent:
                PrecipPercnt = [hourlyCurrent['precip_probability'], '%']
            else:
                PrecipPercnt = [0, '%']
            if 'precip' in hourlyCurrent:
                PrecipAmount = [hourlyCurrent['precip'], 'mm']
            else:
                PrecipAmount = [0, 'mm']

            # Extract weather variables from current daily forecast
            highTemp  = [dailyCurrent['air_temp_high'], 'c']
            lowTemp   = [dailyCurrent['air_temp_low'], 'c']
            precipDay = [dailyCurrent['precip_probability'], '%']

            # Extract list of expected conditions and find time when expected conditions
            # will change
            conditionList = list(forecast['conditions'] for forecast in hourlyForecasts[hoursInd:])
            try:
                Ind = next(i for i, C in enumerate(conditionList) if C != hourlyCurrent['conditions'])
            except StopIteration:
                Ind = len(conditionList) - 1
            Time = datetime.fromtimestamp(Hours[Ind], pytz.utc).astimezone(Tz)
            if Time.date() == Now.date():
                Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time, TimeFormat) + ' today'
            elif Time.date() == Now.date() + timedelta(days=1):
                Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time, TimeFormat) + ' tomorrow'
            else:
                Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time, TimeFormat) + ' on ' + Time.strftime('%A')

            # Calculate derived variables from forecast
            WindDir = derive.cardinal_wind_dir(WindDir, WindSpd)

            # Convert forecast units as required
            Temp         = observation.units(Temp,         self.app.config['Units']['Temp'])
            highTemp     = observation.units(highTemp,     self.app.config['Units']['Temp'])
            lowTemp      = observation.units(lowTemp,      self.app.config['Units']['Temp'])
            WindSpd      = observation.units(WindSpd,      self.app.config['Units']['Wind'])
            WindGust     = observation.units(WindGust,     self.app.config['Units']['Wind'])
            WindDir      = observation.units(WindDir,      self.app.config['Units']['Direction'])
            PrecipAmount = observation.units(PrecipAmount, self.app.config['Units']['Precip'])

            # Define and format labels
            self.met_data['Valid']        = datetime.strftime(Valid,          TimeFormat)
            self.met_data['Temp']         = observation.format(Temp,         'forecastTemp')
            self.met_data['highTemp']     = observation.format(highTemp,     'forecastTemp')
            self.met_data['lowTemp']      = observation.format(lowTemp,      'forecastTemp')
            self.met_data['WindSpd']      = observation.format(WindSpd,      'forecastWind')
            self.met_data['WindGust']     = observation.format(WindGust,     'forecastWind')
            self.met_data['WindDir']      = observation.format(WindDir,      'Direction')
            self.met_data['PrecipPercnt'] = observation.format(PrecipPercnt, 'Humidity')
            self.met_data['PrecipDay']    = observation.format(precipDay,    'Humidity')
            self.met_data['PrecipAmount'] = observation.format(PrecipAmount, 'Precip')
            self.met_data['PrecipType']   = PrecipType
            self.met_data['Conditions']   = Conditions
            self.met_data['Icon']         = Icon
            self.met_data['Status']       = ''

            # Check expected conditions icon is recognised
            if Icon in ['clear-day', 'clear-night', 'rainy', 'possibly-rainy-day',
                        'possibly-rainy-night', 'snow', 'possibly-snow-day',
                        'possibly-snow-night', 'sleet', 'possibly-sleet-day',
                        'possibly-sleet-night', 'thunderstorm', 'possibly-thunderstorm-day',
                        'possibly-thunderstorm-night', 'windy', 'foggy', 'cloudy',
                        'partly-cloudy-day', 'partly-cloudy-night']:
                self.met_data['Icon'] = Icon
            else:
                self.met_data['Icon'] = '-'

            # Update display
            self.update_display()

            # Update forecast icon
            if hasattr(self.app, 'ForecastPanel'):
                for panel in getattr(self.app, 'ForecastPanel'):
                    panel.setForecastIcon()

            # Schedule new forecast
            Clock.schedule_once(self.schedule_forecast)

        # Unable to extract forecast data from JSON object. Set forecast
        # variables to blank and indicate to user that forecast is unavailable
        except (IndexError, KeyError, ValueError):
            Clock.schedule_once(self.fail_forecast)

    def update_display(self):

        """ Update display with new forecast variables. Catch ReferenceErrors to
        prevent console crashing
        """

        # Update display values with new derived observations
        reference_error = False
        for Key, Value in list(self.met_data.items()):
            try:
                self.app.CurrentConditions.Met[Key] = Value
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'astro: {system().log_time()} - Reference error')
                    reference_error = True
