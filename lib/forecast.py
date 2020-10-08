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

# Import required modules
from datetime   import datetime, date, timedelta, time
from lib        import observationFormat  as observation
from lib        import derivedVariables   as derive
from lib        import requestAPI
from kivy.clock import Clock
import requests
import bisect
import pytz
import time

def Download(metData,Config):

    """ Download the weather forecast data using the WeatherFlow BetterForecast
    API

    INPUTS:
        metData             Dictionary holding weather forecast data
        Config              Station configuration

    OUTPUT:
        metData             Dictionary holding weather forecast data
    """

    # Download latest forecast data
    Data = requestAPI.weatherflow.Forecast(Config)

    # Verify API response and extract forecast
    if requestAPI.weatherflow.verifyResponse(Data,'forecast'):
        metData['Dict'] = Data.json()
    else:
        Clock.schedule_once(lambda dt: Download(metData,Config),600)
        if not 'Dict' in metData:
            metData['Dict'] = {}
    Extract(metData,Config)

    # Return metData dictionary
    return metData

def Extract(metData,Config):

    # Get current time in station time zone
    Tz       = pytz.timezone(Config['Station']['Timezone'])
    Now      = datetime.now(pytz.utc).astimezone(Tz)
    Midnight = int(Tz.localize(datetime(Now.year,Now.month,Now.day)).timestamp())

    # Set time format based on user configuration
    if Config['Display']['TimeFormat'] == '12 hr':
        if Config['System']['Hardware'] != 'Other':
            TimeFormat = '%-I %P'
        else:
            TimeFormat = '%I %p'
    else:
        TimeFormat = '%H:%M'

    # Extract all forecast data from WeatherFlow JSON object. If  forecast is
    # unavailable, set forecast variables to blank and indicate to user that
    # forecast is unavailable
    try:
        # Extract all hourly and daily forecasts
        hourlyForecasts  = (metData['Dict']['forecast']['hourly'])
        dailyForecasts   = (metData['Dict']['forecast']['daily'])

        # Extract 'valid from' time of all available hourly forecasts and
        # retrieve forecast for the current hour
        Hours         = list(forecast['time'] for forecast in hourlyForecasts)
        hourlyCurrent = hourlyForecasts[bisect.bisect(Hours,int(time.time()))]

        # Extract 'Valid' until time of forecast for current hour
        Valid = Hours[bisect.bisect(Hours,int(time.time()))]
        Valid = datetime.fromtimestamp(Valid,pytz.utc).astimezone(Tz)

        # Extract 'day_start_local' time of all available daily forecasts and
        # retrieve forecast for the current day
        Days         = list(forecast['day_start_local'] for forecast in dailyForecasts)
        dailyCurrent = dailyForecasts[Days.index(Midnight)]

    except (IndexError, KeyError, ValueError):
        metData['Time']         = Now
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
        metData['Icon']         = '--'  
        metData['Status']       = 'Forecast currently\nunavailable...'

        # Attempt to download forecast again in 5 minutes and return metData 
        # dictionary
        Clock.schedule_once(lambda dt: Download(metData,Config),300)
        return metData

    # Extract weather variables from current hourly forecast
    Temp         = [hourlyCurrent['air_temperature'],'c']
    WindSpd      = [hourlyCurrent['wind_avg'],'mps']
    WindGust     = [hourlyCurrent['wind_gust'],'mps']
    WindDir      = [hourlyCurrent['wind_direction'],'degrees']
    PrecipPercnt = [hourlyCurrent['precip_probability'],'%']
    PrecipAmount = [hourlyCurrent['precip'],'mm']
    PrecipType   =  hourlyCurrent['precip_type']
    Icon         =  hourlyCurrent['icon'].replace('cc-','')

    # Extract weather variables from current daily forecast
    highTemp  = [dailyCurrent['air_temp_high'],'c']
    lowTemp   = [dailyCurrent['air_temp_low'],'c']
    precipDay = [dailyCurrent['precip_probability'],'%']

    # Extract list of expected conditions and find time when expected conditions
    # will change
    conditionList = list(forecast['conditions'] for forecast in hourlyForecasts)
    try:
        Ind = next(i for i,C in enumerate(conditionList) if C != hourlyCurrent['conditions'])
    except StopIteration:
        Ind = len(conditionList)-1
    Time = datetime.fromtimestamp(Hours[Ind],pytz.utc).astimezone(Tz)
    if Time.date() == Now.date():
        Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time,TimeFormat) + ' today'
    elif Time.date() == Now.date() + timedelta(days=1):
        Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time,TimeFormat) + ' tomorrow'
    else:
        Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time,TimeFormat) + 'on' + Time.strftime('%A')

    # Calculate derived variables from forecast
    WindDir = derive.CardinalWindDirection(WindDir,WindSpd)

    # Convert forecast units as required
    Temp         = observation.Units(Temp,Config['Units']['Temp'])
    highTemp     = observation.Units(highTemp,Config['Units']['Temp'])
    lowTemp      = observation.Units(lowTemp,Config['Units']['Temp'])
    WindSpd      = observation.Units(WindSpd,Config['Units']['Wind'])
    WindGust     = observation.Units(WindGust,Config['Units']['Wind'])
    WindDir      = observation.Units(WindDir,Config['Units']['Direction'])
    PrecipAmount = observation.Units(PrecipAmount,Config['Units']['Precip'])

    # Define and format labels
    metData['Time']         = Now
    metData['Valid']        = datetime.strftime(Valid,TimeFormat)
    metData['Temp']         = observation.Format(Temp,'forecastTemp')
    metData['highTemp']     = observation.Format(highTemp,'forecastTemp')
    metData['lowTemp']      = observation.Format(lowTemp,'forecastTemp')
    metData['WindSpd']      = observation.Format(WindSpd,'forecastWind')
    metData['WindGust']     = observation.Format(WindGust,'forecastWind')
    metData['WindDir']      = observation.Format(WindDir,'Direction')
    metData['PrecipPercnt'] = observation.Format(PrecipPercnt,'Humidity')
    metData['PrecipDay']    = observation.Format(precipDay,'Humidity')
    metData['PrecipAmount'] = observation.Format(PrecipAmount,'Precip')
    metData['PrecipType']   = PrecipType
    metData['Conditions']   = Conditions
    metData['Icon']         = Icon
    metData['Status']       = ''

    # Check expected conditions icon is recognised
    if Icon in  ['clear-day', 'clear-night', 'rainy', 'possibly-rainy-day',
                 'possibly-rainy-night', 'snow', 'possibly-snow-day',
                 'possibly-snow-night', 'sleet', 'possibly-sleet-day',
                 'possibly-sleet-night', 'thunderstorm', 'possibly-thunderstorm-day'
                 'possibly-thunderstorm-night', 'windy', 'foggy', 'cloudy',
                 'partly-cloudy-day','partly-cloudy-night']:
        metData['Icon'] = Icon
    else:
        metData['Icon'] = '--'

    # Return metData dictionary
    return metData