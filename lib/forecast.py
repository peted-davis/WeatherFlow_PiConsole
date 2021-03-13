""" Returns the WeatherFlow forecast variables required by the Raspberry Pi
Python console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2020 Peter Davis

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
from lib        import observationFormat  as observation
from lib        import derivedVariables   as derive
from lib        import requestAPI

# Import required modules
from datetime   import datetime, timedelta, time
from functools  import partial
from kivy.clock import Clock
import time     as UNIX
import threading
import bisect
import pytz
import math


def startDownload(console, forceDownload, *largs):

    """ Start weather forecast download thread, or schedule next download time

    INPUTS:
        console         console object
        forceDownload       Boolean specifying whether to force a new download

    OUTPUT:
        metData             Dictionary holding weather forecast data
    """

    # Get current time in station time zone
    Tz  = pytz.timezone(console.config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Fetch latest hourly forecast if required
    if forceDownload or console.CurrentConditions.Met['Valid'] == '--' or console.CurrentConditions.Met['Time'] <= Now:
        threading.Thread(target=Download, args=(console, ), name='weatherDownload').start()

    # Else, schedule the latest forecast to be fetched at the top of the hour
    else:
        downloadTime = Tz.localize(datetime.combine(Now.date(), time(Now.hour, 0, 0)) + timedelta(hours=1))
        secondsSched = math.ceil((downloadTime - Now).total_seconds())
        console.Sched.metDownload.cancel()
        console.Sched.metDownload = Clock.schedule_once(partial(startDownload, console), secondsSched)


def Download(console):

    """ Download the latest daily and hourly weather forecast data using the
    WeatherFlow BetterForecast API

    INPUTS:
        console         console object

    OUTPUT:
        metData             Dictionary holding weather forecast data
    """

    # Extract metData dictionary and configuration from console object
    metData = console.CurrentConditions.Met
    config  = console.config

    # Get current time in station time zone
    Tz         = pytz.timezone(config['Station']['Timezone'])
    funcCalled = datetime.now(pytz.utc).astimezone(Tz)
    funcError  = 0

    # Set time format based on user configuration
    if config['Display']['TimeFormat'] == '12 hr':
        if config['System']['Hardware'] != 'Other':
            TimeFormat = '%-I %P'
        else:
            TimeFormat = '%I %p'
    else:
        TimeFormat = '%H:%M'

    # Download latest forecast data
    Data = requestAPI.weatherflow.Forecast(config)

    # Verify API response and extract forecast
    if requestAPI.weatherflow.verifyResponse(Data, 'forecast'):
        metData['Dict'] = Data.json()
    else:
        funcError = 1
        if 'Dict' not in metData:
            metData['Dict'] = {}

    # Extract all forecast data from WeatherFlow JSON object
    try:
        # Extract all hourly and daily forecasts
        hourlyForecasts  = (metData['Dict']['forecast']['hourly'])
        dailyForecasts   = (metData['Dict']['forecast']['daily'])

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
        Icon         =  hourlyCurrent['icon'].replace('cc-', '')

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
        if Time.date() == funcCalled.date():
            Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time, TimeFormat) + ' today'
        elif Time.date() == funcCalled.date() + timedelta(days=1):
            Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time, TimeFormat) + ' tomorrow'
        else:
            Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time, TimeFormat) + ' on ' + Time.strftime('%A')

        # Calculate derived variables from forecast
        WindDir = derive.cardinalWindDir(WindDir, WindSpd)

        # Convert forecast units as required
        Temp         = observation.Units(Temp, config['Units']['Temp'])
        highTemp     = observation.Units(highTemp, config['Units']['Temp'])
        lowTemp      = observation.Units(lowTemp, config['Units']['Temp'])
        WindSpd      = observation.Units(WindSpd, config['Units']['Wind'])
        WindGust     = observation.Units(WindGust, config['Units']['Wind'])
        WindDir      = observation.Units(WindDir, config['Units']['Direction'])
        PrecipAmount = observation.Units(PrecipAmount, config['Units']['Precip'])

        # Define and format labels
        #metData['Time']         = Valid
        metData['Valid']        = datetime.strftime(Valid, TimeFormat)
        metData['Temp']         = observation.Format(Temp, 'forecastTemp')
        metData['highTemp']     = observation.Format(highTemp, 'forecastTemp')
        metData['lowTemp']      = observation.Format(lowTemp, 'forecastTemp')
        metData['WindSpd']      = observation.Format(WindSpd, 'forecastWind')
        metData['WindGust']     = observation.Format(WindGust, 'forecastWind')
        metData['WindDir']      = observation.Format(WindDir, 'Direction')
        metData['PrecipPercnt'] = observation.Format(PrecipPercnt, 'Humidity')
        metData['PrecipDay']    = observation.Format(precipDay, 'Humidity')
        metData['PrecipAmount'] = observation.Format(PrecipAmount, 'Precip')
        metData['PrecipType']   = PrecipType
        metData['Conditions']   = Conditions
        metData['Icon']         = Icon
        metData['Status']       = ''

        # Check expected conditions icon is recognised
        if Icon in ['clear-day', 'clear-night', 'rainy', 'possibly-rainy-day',
                    'possibly-rainy-night', 'snow', 'possibly-snow-day',
                    'possibly-snow-night', 'sleet', 'possibly-sleet-day',
                    'possibly-sleet-night', 'thunderstorm', 'possibly-thunderstorm-day'
                    'possibly-thunderstorm-night', 'windy', 'foggy', 'cloudy',
                    'partly-cloudy-day', 'partly-cloudy-night']:
            metData['Icon'] = Icon
        else:
            metData['Icon'] = '--'

    # Unable to extract forecast data from JSON object. Set set forecast
    # variables to blank and indicate to user that forecast is unavailable
    except (IndexError, KeyError, ValueError):
        #metData['Time']         = funcCalled
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
    if hasattr(console, 'ForecastPanel'):
        for panel in getattr(console, 'ForecastPanel'):
            panel.setForecastIcon()

    # Schedule new forecast to be downloaded at the top of the next hour, or in
    # 5 minutes if error was detected. Note secondsSched refers to number of
    # seconds since the function was last called.
    Now = datetime.now(pytz.utc).astimezone(Tz)
    downloadTime = Tz.localize(datetime.combine(Now.date(), time(Now.hour, 0, 0)) + timedelta(hours=1))
    if not funcError:
        secondsSched = math.ceil((downloadTime - funcCalled).total_seconds())
    else:
        secondsSched = 300 + math.ceil((funcCalled - Now).total_seconds())
    console.Sched.metDownload.cancel()
    console.Sched.metDownload = Clock.schedule_once(partial(startDownload, console), secondsSched)
