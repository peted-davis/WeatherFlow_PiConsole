""" Returns the WeatherFlow forecast variables required by the Raspberry Pi
Python app for WeatherFlow Tempest and Smart Home Weather stations.
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

# Import required library modules
from lib import observationFormat  as observation
from lib import derivedVariables   as derive
from lib import properties

# Import required Kivy modules
from kivy.network.urlrequest import UrlRequest
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
        self.funcCalled = []
        self.app = App.get_running_app()

    def reset_forecast(self):

        """ Reset the weather forecast displayed on screen to default values and
        fetch new forecast from WeatherFlow BetterForecast API
        """

        # Reset the forecast and schedule new forecast to be generated
        self.app.CurrentConditions.Met =  properties.Met()
        if hasattr(self.app, 'ForecastPanel'):
            for panel in getattr(self.app, 'ForecastPanel'):
                panel.setForecastIcon()
        Clock.schedule_once(self.fetch_forecast)

    def fetch_forecast(self, *largs):

        """ Fetch the latest daily and hourly weather forecast data using the
        WeatherFlow BetterForecast API
        """

        # Fetch latest hourly and daily forecast
        URL = 'https://swd.weatherflow.com/swd/rest/better_forecast?token={}&station_id={}'
        URL = URL.format(self.app.config['Keys']['WeatherFlow'],
                         self.app.config['Station']['StationID'])
        UrlRequest(URL,
                   on_success=self.success_forecast,
                   on_failure=self.fail_forecast,
                   on_error=self.fail_forecast,
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
        self.app.CurrentConditions.Met['Response'] = Response
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
        self.app.CurrentConditions.Met['Valid']        = '--'
        self.app.CurrentConditions.Met['Temp']         = '--'
        self.app.CurrentConditions.Met['highTemp']     = '--'
        self.app.CurrentConditions.Met['lowTemp']      = '--'
        self.app.CurrentConditions.Met['WindSpd']      = '--'
        self.app.CurrentConditions.Met['WindGust']     = '--'
        self.app.CurrentConditions.Met['WindDir']      = '--'
        self.app.CurrentConditions.Met['PrecipPercnt'] = '--'
        self.app.CurrentConditions.Met['PrecipDay']    = '--'
        self.app.CurrentConditions.Met['PrecipAmount'] = '--'
        self.app.CurrentConditions.Met['PrecipType']   = '--'
        self.app.CurrentConditions.Met['Conditions']   = ''
        self.app.CurrentConditions.Met['Icon']         = '-'
        self.app.CurrentConditions.Met['Status']       = 'Forecast currently\nunavailable...'

        # Update forecast icon in mainthread
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
        Forecast = self.app.CurrentConditions.Met['Response']

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
            WindDir = derive.cardinalWindDir(WindDir, WindSpd)

            # Convert forecast units as required
            Temp         = observation.Units(Temp,         self.app.config['Units']['Temp'])
            highTemp     = observation.Units(highTemp,     self.app.config['Units']['Temp'])
            lowTemp      = observation.Units(lowTemp,      self.app.config['Units']['Temp'])
            WindSpd      = observation.Units(WindSpd,      self.app.config['Units']['Wind'])
            WindGust     = observation.Units(WindGust,     self.app.config['Units']['Wind'])
            WindDir      = observation.Units(WindDir,      self.app.config['Units']['Direction'])
            PrecipAmount = observation.Units(PrecipAmount, self.app.config['Units']['Precip'])

            # Define and format labels
            self.app.CurrentConditions.Met['Valid']        = datetime.strftime(Valid,          TimeFormat)
            self.app.CurrentConditions.Met['Temp']         = observation.Format(Temp,         'forecastTemp')
            self.app.CurrentConditions.Met['highTemp']     = observation.Format(highTemp,     'forecastTemp')
            self.app.CurrentConditions.Met['lowTemp']      = observation.Format(lowTemp,      'forecastTemp')
            self.app.CurrentConditions.Met['WindSpd']      = observation.Format(WindSpd,      'forecastWind')
            self.app.CurrentConditions.Met['WindGust']     = observation.Format(WindGust,     'forecastWind')
            self.app.CurrentConditions.Met['WindDir']      = observation.Format(WindDir,      'Direction')
            self.app.CurrentConditions.Met['PrecipPercnt'] = observation.Format(PrecipPercnt, 'Humidity')
            self.app.CurrentConditions.Met['PrecipDay']    = observation.Format(precipDay,    'Humidity')
            self.app.CurrentConditions.Met['PrecipAmount'] = observation.Format(PrecipAmount, 'Precip')
            self.app.CurrentConditions.Met['PrecipType']   = PrecipType
            self.app.CurrentConditions.Met['Conditions']   = Conditions
            self.app.CurrentConditions.Met['Icon']         = Icon
            self.app.CurrentConditions.Met['Status']       = ''

            # Check expected conditions icon is recognised
            if Icon in ['clear-day', 'clear-night', 'rainy', 'possibly-rainy-day',
                        'possibly-rainy-night', 'snow', 'possibly-snow-day',
                        'possibly-snow-night', 'sleet', 'possibly-sleet-day',
                        'possibly-sleet-night', 'thunderstorm', 'possibly-thunderstorm-day',
                        'possibly-thunderstorm-night', 'windy', 'foggy', 'cloudy',
                        'partly-cloudy-day', 'partly-cloudy-night']:
                self.app.CurrentConditions.Met['Icon'] = Icon
            else:
                self.app.CurrentConditions.Met['Icon'] = '-'

            # Update forecast icon in mainthread
            if hasattr(self.app, 'ForecastPanel'):
                for panel in getattr(self.app, 'ForecastPanel'):
                    panel.setForecastIcon()

            # Schedule new forecast
            Clock.schedule_once(self.schedule_forecast)

        # Unable to extract forecast data from JSON object. Set forecast
        # variables to blank and indicate to user that forecast is unavailable
        except (IndexError, KeyError, ValueError):
            Clock.schedule_once(self.fail_forecast)
