""" Returns the WeatherFlow forecast variables required by the Raspberry Pi
Python app for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2021 Peter Davis

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
from lib import requestAPI
from lib import properties

# Import required Kivy modules
from kivy.network.urlrequest import UrlRequest
from kivy.clock              import Clock
from kivy.app                import App

# Import required Python modules
from datetime   import datetime, timedelta, time
import time     as UNIX
import certifi
import bisect
import pytz
import math


class forecast():


    def __init__(self):

        # Define instance variables
        self.funcCalled = []

        # Create reference to app object
        App.get_running_app().forecast = self
        self.app = App.get_running_app()


    def fetch_forecast(self, *largs):

        """ Fetch the latest daily and hourly weather forecast data using the
        WeatherFlow BetterForecast API
        """

        # Get current time in station time zone
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        self.funcCalled = datetime.now(pytz.utc).astimezone(Tz)

        # Fetch latest hourly and daily forecast
        URL = 'https://swd.weatherflow.com/swd/rest/better_forecast?token={}&station_id={}'
        URL = URL.format(self.app.config['Keys']['WeatherFlow'], self.app.config['Station']['StationID'])
        UrlRequest(URL,
                   on_success=self.success_forecast,
                   on_failure=self.fail_forecast,
                   on_error=self.fail_forecast,
                   ca_file=certifi.where())


    def fail_forecast(self, Request, Response):

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
        downloadTime = Now + timedelta(minutes=5)
        secondsSched = (downloadTime - Now).total_seconds()
        self.app.Sched.metDownload.cancel()
        self.app.Sched.metDownload = Clock.schedule_once(self.fetch_forecast, secondsSched)


    def success_forecast(self, Request, Response):

        """ Sucessfully fetched forecast from the WeatherFlow BetterForecast API.
        Schedule fetch_forecast for the top of the next hour and parse forecast
        response

        INPUTS:
            Request             UrlRequest object
            Response            UrlRequest response

        """

        # Schedule new forecast to be downloaded at the top of the next hour. Note
        #secondsSched refers to number of seconds since the function was last called
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)
        downloadTime = Tz.localize(datetime.combine(Now.date(), time(Now.hour, 0, 0)) + timedelta(hours=1))
        secondsSched = (downloadTime - Now).total_seconds()
        self.app.Sched.metDownload.cancel()
        self.app.Sched.metDownload = Clock.schedule_once(self.fetch_forecast, secondsSched)

        # Parse the latest daily and hourly weather forecast data
        self.app.CurrentConditions.Met['Response'] = Response
        self.parse_forecast()

    def parse_forecast(self):

        """ Parse the latest daily and hourly weather forecast from the
        WeatherFlow BetterForecast API and format for display based on user
        specified units
        """

        # Extract metData dictionary and configuration from self.app object
        metData = self.app.CurrentConditions.Met
        config  = self.app.config

        # Get current time in station time zone
        Tz  = pytz.timezone(config['Station']['Timezone'])
        #Now = datetime.now(pytz.utc).astimezone(Tz)
        funcError  = 0

        # Set time format based on user configuration
        if config['Display']['TimeFormat'] == '12 hr':
            if config['System']['Hardware'] == 'Other':
                TimeFormat = '%#I %p'
            else:
                TimeFormat = '%-I %p'
        else:
            TimeFormat = '%H:%M'

        # Extract all forecast data from WeatherFlow JSON object
        try:
            # Extract all hourly and daily forecasts
            hourlyForecasts  = (metData['Response']['forecast']['hourly'])
            dailyForecasts   = (metData['Response']['forecast']['daily'])

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
            if Time.date() == self.funcCalled.date():
                Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time, TimeFormat) + ' today'
            elif Time.date() == self.funcCalled.date() + timedelta(days=1):
                Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time, TimeFormat) + ' tomorrow'
            else:
                Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time, TimeFormat) + ' on ' + Time.strftime('%A')

            # Calculate derived variables from forecast
            WindDir = derive.cardinalWindDir(WindDir, WindSpd)

            # Convert forecast units as required
            Temp         = observation.Units(Temp,         config['Units']['Temp'])
            highTemp     = observation.Units(highTemp,     config['Units']['Temp'])
            lowTemp      = observation.Units(lowTemp,      config['Units']['Temp'])
            WindSpd      = observation.Units(WindSpd,      config['Units']['Wind'])
            WindGust     = observation.Units(WindGust,     config['Units']['Wind'])
            WindDir      = observation.Units(WindDir,      config['Units']['Direction'])
            PrecipAmount = observation.Units(PrecipAmount, config['Units']['Precip'])

            # Define and format labels
            metData['Valid']        = datetime.strftime(Valid,          TimeFormat)
            metData['Temp']         = observation.Format(Temp,         'forecastTemp')
            metData['highTemp']     = observation.Format(highTemp,     'forecastTemp')
            metData['lowTemp']      = observation.Format(lowTemp,      'forecastTemp')
            metData['WindSpd']      = observation.Format(WindSpd,      'forecastWind')
            metData['WindGust']     = observation.Format(WindGust,     'forecastWind')
            metData['WindDir']      = observation.Format(WindDir,      'Direction')
            metData['PrecipPercnt'] = observation.Format(PrecipPercnt, 'Humidity')
            metData['PrecipDay']    = observation.Format(precipDay,    'Humidity')
            metData['PrecipAmount'] = observation.Format(PrecipAmount, 'Precip')
            metData['PrecipType']   = PrecipType
            metData['Conditions']   = Conditions
            metData['Icon']         = Icon
            metData['Status']       = ''

            # Check expected conditions icon is recognised
            if Icon in ['clear-day', 'clear-night', 'rainy', 'possibly-rainy-day',
                        'possibly-rainy-night', 'snow', 'possibly-snow-day',
                        'possibly-snow-night', 'sleet', 'possibly-sleet-day',
                        'possibly-sleet-night', 'thunderstorm', 'possibly-thunderstorm-day',
                        'possibly-thunderstorm-night', 'windy', 'foggy', 'cloudy',
                        'partly-cloudy-day', 'partly-cloudy-night']:
                metData['Icon'] = Icon
            else:
                metData['Icon'] = '-'

        # Unable to extract forecast data from JSON object. Set forecast
        # variables to blank and indicate to user that forecast is unavailable
        except (IndexError, KeyError, ValueError):
            metData['Valid']        = '--'
            metData['Temp']         = '--'
            metData['highTemp']     = '--'
            metData['lowTemp']      = '--'
            metData['WindSpd']      = '--'
            metData['WindGust']     = '--'
            metData['WindDir']      = '--'
            metData['PrecipPercnt'] = '--'
            metData['PrecipDay']    = '--'
            metData['PrecipAmount'] = '--'
            metData['PrecipType']   = '--'
            metData['Conditions']   = ''
            metData['Icon']         = '-'
            metData['Status']       = 'Forecast currently\nunavailable...'
            funcError               = 1

        # Update forecast icon in mainthread
        if hasattr(self.app, 'ForecastPanel'):
            for panel in getattr(self.app, 'ForecastPanel'):
                panel.setForecastIcon()

        # If error is detected, download forecast again in 5 minutes
        if funcError:
            self.fail_forecast(None, None)

    def resetDisplay(self):

        """ Reset the weather forecast displayed on screen to default values and
        fetch new forecast from WeatherFlow BetterForecast API
        """

        self.app.CurrentConditions.Met = properties.Met()
        if hasattr(self.app, 'ForecastPanel'):
            for panel in getattr(self.app, 'ForecastPanel'):
                panel.setForecastIcon()
        self.fetch_forecast()
