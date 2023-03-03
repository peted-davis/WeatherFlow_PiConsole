""" Returns the derived weather variables required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
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
from lib.request_api import weatherflow_api
from lib.system      import system
from lib             import derivedVariables as derive

# Import required Python modules
from kivy.logger  import Logger
from datetime     import datetime
import bisect
import ephem
import math
import pytz
import time


def dewPoint(outTemp, humidity):

    """ Calculate the dew point from the temperature and relative humidity

    INPUTS:
        outTemp             Temperature from AIR module         [C]
        humidity            Relative humidity from AIR module   [%]

    OUTPUT:
        DewPoint            Dew point                           [C]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'c']
    if outTemp[0] is None:
        Logger.warning(f'dewPoint: {system().log_time()} - outTemp is None')
        return errorOutput
    elif humidity[0] is None:
        Logger.warning(f'dewPoint: {system().log_time()} - humidity is None')
        return errorOutput

    # Calculate dew point
    if humidity[0] > 0:
        A = 17.625
        B = 243.04
        N = B * (math.log(humidity[0] / 100.0) + (A * outTemp[0]) / (B + outTemp[0]))
        D = A - math.log(humidity[0] / 100.0) - (A * outTemp[0]) / (B + outTemp[0])
        dewPoint = N / D
    else:
        dewPoint = None

    # Return Dew Point
    return [dewPoint, 'c']


def feelsLike(outTemp, humidity, windSpd, config):

    """ Calculate the Feels Like temperature from the temperature, relative
    humidity, and wind speed

    INPUTS:
        Temp                Temperature from AIR module         [C]
        Humidity            Relative humidity from AIR module   [%]
        windSpd             Wind speed from SKY module          [m/s]
        config              Station configuration

    OUTPUT:
        FeelsLike           Feels Like temperature              [C]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'c', '-', '-']
    if outTemp[0] is None:
        Logger.warning(f'feelsLike: {system().log_time()} - outTemp is None')
        return errorOutput
    elif humidity[0] is None:
        Logger.warning(f'feelsLike: {system().log_time()} - humidity is None')
        return errorOutput
    elif windSpd[0] is None:
        Logger.warning(f'feelsLike: {system().log_time()} - windSpd is None')
        return errorOutput

    # Convert observation units as required
    TempF   = [outTemp[0] * (9 / 5) + 32, 'f']
    WindMPH = [windSpd[0] * 2.2369362920544, 'mph']
    WindKPH = [windSpd[0] * 3.6, 'kph']

    # If temperature is less than 10 degrees celcius and wind speed is higher
    # than 3 mph, calculate wind chill using the Joint Action Group for
    # Temperature Indices formula
    if outTemp[0] <= 10 and WindMPH[0] > 3:
        WindChill = (+ 13.12 + 0.6215 * outTemp[0]
                     - 11.37 * (WindKPH[0])**0.16 + 0.3965 * outTemp[0]
                     * (WindKPH[0])**0.16)
        FeelsLike = [WindChill, 'c']

    # If temperature is at or above 80 degress farenheit (26.67 C), and humidity
    # is at or above 40%, calculate the Heat Index
    elif TempF[0] >= 80 and humidity[0] >= 40:
        HeatIndex = (-42.379 + (2.04901523 * TempF[0])
                     + (10.1433127 * humidity[0])
                     - (0.22475541 * TempF[0] * humidity[0])
                     - (6.83783e-3 * TempF[0]**2)
                     - (5.481717e-2 * humidity[0]**2)
                     + (1.22874e-3 * TempF[0]**2 * humidity[0])
                     + (8.5282e-4 * TempF[0] * humidity[0]**2)
                     - (1.99e-6 * TempF[0]**2 * humidity[0]**2))
        FeelsLike = [(HeatIndex - 32) * (5 / 9), 'c']

    # Else set Feels Like temperature to observed temperature
    else:
        FeelsLike = outTemp

    # Define 'FeelsLike' temperature cutoffs
    Cutoffs = [float(item) for item in list(config['FeelsLike'].values())]

    # Define 'FeelsLike temperature text and icon
    Description = ['Feeling extremely cold', 'Feeling freezing cold', 'Feeling very cold',
                   'Feeling cold', 'Feeling mild', 'Feeling warm', 'Feeling hot',
                   'Feeling very hot', 'Feeling extremely hot', '-']
    Icon =        ['ExtremelyCold', 'FreezingCold', 'VeryCold', 'Cold', 'Mild', 'Warm',
                   'Hot', 'VeryHot', 'ExtremelyHot', '-']
    if config['Units']['Temp'] == 'f':
        Ind = bisect.bisect(Cutoffs, FeelsLike[0] * (9 / 5) + 32)
    else:
        Ind = bisect.bisect(Cutoffs, FeelsLike[0])

    # Return 'Feels Like' temperature
    return [FeelsLike[0], FeelsLike[1], Description[Ind], Icon[Ind]]


def SLP(pressure, device, config):

    """ Calculate the sea level pressure from the station pressure

    INPUTS:
        pressure            Station pressure from AIR/TEMPEST module    [mb]
        device              Device ID that observation originates from
        config              Station configuration

    OUTPUT:
        SLP                 Sea level pressure                  [mb]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'mb', None]
    if pressure[0] is None:
        Logger.warning(f'SLP: {system().log_time()} - pressure is None')
        return errorOutput

    # Extract required configuration variables
    elevation = config['Station']['Elevation']
    if str(device) == config['Station']['OutAirID']:
        height = config['Station']['OutAirHeight']
    elif str(device) == config['Station']['TempestID']:
        height = config['Station']['TempestHeight']

    # Define required constants
    P0 = 1013.25
    Rd = 287.05
    GammaS = 0.0065
    g = 9.80665
    T0 = 288.15
    elevation = float(elevation) + float(height)

    # Calculate and return sea level pressure
    SLP = (pressure[0]
           * (1 + ((P0 / pressure[0])**((Rd * GammaS) / g))
           * ((GammaS * elevation) / T0))**(g / (Rd * GammaS))
           )
    return [SLP, 'mb', SLP]


def SLPTrend(pressure, obTime, device, apiData, config):

    """ Calculate the pressure trend from the sea level pressure over the last
        three hours

    INPUTS:
        pressure            Current station pressure                    [mb]
        obTime              Time of latest observation                  [s]
        device              Device ID that observation originates from
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        Trend               Sea level pressure trend                    [mb]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'mb/hr', '-', '-']
    if pressure[0] is None:
        Logger.warning(f'SLPTrend: {system().log_time()} - pressure is None')
        return errorOutput
    elif obTime[0] is None:
        Logger.warning(f'SLPTrend: {system().log_time()} - obTime is None')
        return errorOutput

    # Define index of pressure in websocket packets
    if str(device) == config['Station']['OutAirID']:
        index_bucket_a  = 1
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a  = 6

    # Extract required observations from WeatherFlow API data based on device
    # type indicated in API call
    if '24Hrs' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['24Hrs'], 'obs'):
            data24hrs = apiData[device]['24Hrs'].json()['obs']
            apiTime   = [ob[0]              for ob in data24hrs if ob[index_bucket_a] is not None]
            apiPres   = [ob[index_bucket_a] for ob in data24hrs if ob[index_bucket_a] is not None]
            try:
                dTime = [abs(T - (obTime[0] - 3 * 3600)) for T in apiTime]
                if min(dTime) < 5 * 60:
                    pres3h  = [apiPres[dTime.index(min(dTime))], 'mb']
                    time3h  = [apiTime[dTime.index(min(dTime))], 's']
                    pres0h  = pressure
                    time0h  = obTime
                else:
                    Logger.warning(f'SLPTrend: {system().log_time()} - no data in 3 hour window')
                    return errorOutput
            except Exception as Error:
                Logger.warning(f'SLPTrend: {system().log_time()} - {Error}')
                return errorOutput
        else:
            return errorOutput

    # Convert station pressure into sea level pressure
    pres3h = SLP(pres3h, device, config)
    pres0h = SLP(pres0h, device, config)

    # Calculate three hour temperature trend
    try:
        Trend = (pres0h[0] - pres3h[0]) / ((time0h[0] - time3h[0]) / 3600)
    except Exception as Error:
        Logger.warning(f'SLPTrend: {system().log_time()} - {Error}')
        return errorOutput

    # Define pressure trend text
    if Trend > 2 / 3:
        TrendTxt = '[color=ff8837ff]Rising rapidly[/color]'
    elif Trend >= 1 / 3:
        TrendTxt = '[color=ff8837ff]Rising[/color]'
    elif Trend <= -2 / 3:
        TrendTxt = '[color=00a4b4ff]Falling rapidly[/color]'
    elif Trend <= -1 / 3:
        TrendTxt = '[color=00a4b4ff]Falling[/color]'
    else:
        TrendTxt = '[color=9aba2fff]Steady[/color]'

    # Define weather tendency based on pressure and trend
    if pres0h[0] >= 1023:
        if 'Falling rapidly' in TrendTxt:
            Tendency = 'Becoming cloudy and warmer'
        else:
            Tendency = 'Fair conditions likely'
    elif 1009 < pres0h[0] < 1023:
        if 'Falling rapidly' in TrendTxt:
            Tendency = 'Rainy conditions likely'
        else:
            Tendency = 'Conditions unchanged'
    elif pres0h[0] <= 1009:
        if 'Falling rapidly' in TrendTxt:
            Tendency = 'Stormy conditions likely'
        elif 'Falling' in TrendTxt:
            Tendency = 'Rainy conditions likely'
        else:
            Tendency = 'Becoming clearer and cooler'
    else:
        Tendency = '-'

    # Return pressure trend
    return [Trend, 'mb/hr', TrendTxt, Tendency]


def SLPMax(pressure, obTime, maxPres, device, apiData, config):

    """ Calculate maximum pressure since midnight station time

    INPUTS:
        Time                Current observation time                    [s]
        Temp                Current pressure                            [mb]
        maxPres             Current maximum pressure                    [mb]
        device              Device ID that observation originates from
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        maxPres             Maximum pressure                            [mb]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'mb', '-', None, time.time()]
    if pressure[0] is None:
        Logger.warning(f'SLPMax: {system().log_time()} - pressure is None')
        return errorOutput
    elif obTime[0] is None:
        Logger.warning(f'SLPMax: {system().log_time()} - obTime is None')
        return errorOutput

    # Calculate sea level pressure
    SLP = derive.SLP(pressure, device, config)

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of temperature in websocket packets
    if str(device) == config['Station']['OutAirID']:
        index_bucket_a  = 1
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a  = 6

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily maximum and minimum pressure
    if 'today' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['today'], 'obs'):
            dataToday = apiData[device]['today'].json()['obs']
            obTime    = [item[0]                       for item in dataToday if item[index_bucket_a] is not None]
            pressure  = [[item[index_bucket_a], 'mb']  for item in dataToday if item[index_bucket_a] is not None]
            SLP       = [derive.SLP(P, device, config) for P    in pressure]
            try:
                maxPres   = [max(SLP)[0], 'mb', obTime[SLP.index(max(SLP))], 's', max(SLP)[0], obTime[SLP.index(max(SLP))]]
            except Exception as Error:
                Logger.warning(f'SLPMax: {system().log_time()} - {Error}')
                maxPres = errorOutput
        else:
            maxPres = errorOutput

    # Else if midnight has passed, reset maximum pressure
    elif Now.date() > datetime.fromtimestamp(maxPres[5], Tz).date():
        maxPres = [SLP[0], 'mb', obTime[0], 's', SLP[0], obTime[0]]

    # Else if current pressure is greater than maximum recorded pressure, update
    # maximum pressure
    elif SLP[0] > maxPres[4]:
        maxPres = [SLP[0], 'mb', obTime[0], 's', SLP[0], obTime[0]]

    # Else maximum pressure unchanged, return existing values
    else:
        maxPres = [maxPres[4], 'mb', maxPres[2], 's', maxPres[4], obTime[0]]

    # Return required variables
    return maxPres


def SLPMin(pressure, obTime, minPres, device, apiData, config):

    """ Calculate minimum pressure since midnight station time

    INPUTS:
        pressure            Current pressure                            [mb]
        obTime              Current observation time                    [s]
        minPres             Current minimum pressure                    [mb]
        device              Device ID that observation originates from
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        minPres             Minumum pressure                            [mb]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'mb', '-', None, time.time()]
    if pressure[0] is None:
        Logger.warning(f'SLPMin: {system().log_time()} - pressure is None')
        return errorOutput
    elif obTime[0] is None:
        Logger.warning(f'SLPMin: {system().log_time()} - obTime is None')
        return errorOutput

    # Calculate sea level pressure
    SLP = derive.SLP(pressure, device, config)

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of temperature in websocket packets
    if str(device) == config['Station']['OutAirID']:
        index_bucket_a  = 1
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a  = 6

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily maximum and minimum pressure
    if 'today' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['today'], 'obs'):
            dataToday = apiData[device]['today'].json()['obs']
            obTime    = [item[0]                       for item in dataToday if item[index_bucket_a] is not None]
            pressure  = [[item[index_bucket_a], 'mb']  for item in dataToday if item[index_bucket_a] is not None]
            SLP       = [derive.SLP(P, device, config) for P    in pressure]
            try:
                minPres   = [min(SLP)[0], 'mb', obTime[SLP.index(min(SLP))], 's', min(SLP)[0], obTime[SLP.index(min(SLP))]]
            except Exception as Error:
                Logger.warning(f'SLPMin: {system().log_time()} - {Error}')
                minPres = errorOutput
        else:
            minPres = errorOutput

    # Else if midnight has passed, reset maximum and minimum pressure
    elif Now.date() > datetime.fromtimestamp(minPres[5], Tz).date():
        minPres = [SLP[0], 'mb', obTime[0], 's', SLP[0], obTime[0]]

    # Else if current pressure is less than minimum recorded pressure, update
    # minimum pressure and time
    elif SLP[0] < minPres[4]:
        minPres = [SLP[0], 'mb', obTime[0], 's', SLP[0], obTime[0]]

    # Else minimum pressure unchanged, return existing values
    else:
        minPres = [minPres[4], 'mb', minPres[2], 's', minPres[4], obTime[0]]

    # Return required variables
    return minPres


def tempDiff(outTemp, obTime, device, apiData, config):

    """ Calculate 24 hour temperature difference

    INPUTS:
        outTemp             Current temperature                         [deg C]
        obTime              Current observation time                    [s]
        device              Device ID that observation originates from
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        dTemp               24 hour temperature difference              [deg C]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'dc', '-']
    if outTemp[0] is None:
        Logger.warning(f'tempDiff: {system().log_time()} - outTemp is None')
        return errorOutput
    elif obTime[0] is None:
        Logger.warning(f'tempDiff: {system().log_time()} - obTime is None')
        return errorOutput

    # Define index of temperature in websocket packets
    if str(device) == config['Station']['OutAirID']:
        index_bucket_a  = 2
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a  = 7

    # Extract required observations from WeatherFlow API data based on device
    # type indicated in API call
    if '24Hrs' in apiData[device] and weatherflow_api.verify_response(apiData[device]['24Hrs'], 'obs'):
        data24hrs = apiData[device]['24Hrs'].json()['obs']
        apiTime   = [ob[0]              for ob in data24hrs if ob[index_bucket_a] is not None]
        apiTemp   = [ob[index_bucket_a] for ob in data24hrs if ob[index_bucket_a] is not None]
        try:
            dTime   = obTime[0] - apiTime[0]
            if dTime > 86400 - (5 * 60) and dTime < 86400 + (5 * 60):
                temp24h = apiTemp[0]
                temp0h  = outTemp[0]
            else:
                Logger.warning(f'tempDiff: {system().log_time()} - no data in 24 hour window')
                return errorOutput
        except Exception as Error:
            Logger.warning(f'tempDiff: {system().log_time()} - {Error}')
            return errorOutput
    else:
        return errorOutput

    # Calculate 24 hour temperature Difference
    try:
        dTemp = temp0h - temp24h
    except Exception as Error:
        Logger.warning(f'tempDiff: {system().log_time()} - {Error}')
        return errorOutput

    # Define temperature difference text
    if abs(dTemp) < 0.05:
        diffTxt = '[color=c8c8c8ff][/color]'
    elif dTemp > 0:
        diffTxt = '[color=f05e40ff]  warmer[/color]'
    elif dTemp < 0:
        diffTxt = '[color=00a4b4ff]  colder[/color]'

    # Return 24 hour temperature difference
    return [dTemp, 'dc', diffTxt]


def tempTrend(outTemp, obTime, device, apiData, config):

    """ Calculate 3 hour temperature trend

    INPUTS:
        outTemp             Current temperature                         [deg C]
        obTime              Current observation time                    [s]
        device              Device ID that observation originates from
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        Trend               24 hour temperature difference              [deg C]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'c/hr', 'c8c8c8ff']
    if outTemp[0] is None:
        Logger.warning(f'tempTrend: {system().log_time()} - outTemp is None')
        return errorOutput
    elif obTime[0] is None:
        Logger.warning(f'tempTrend: {system().log_time()} - obTime is None')
        return errorOutput

    # Define index of temperature in websocket packets
    if str(device) == config['Station']['OutAirID']:
        index_bucket_a  = 2
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a  = 7

    # Extract required observations from WeatherFlow API data based on device
    # type indicated in API call
    if '24Hrs' in apiData[device] and weatherflow_api.verify_response(apiData[device]['24Hrs'], 'obs'):
        data24hrs = apiData[device]['24Hrs'].json()['obs']
        apiTime   = [ob[0]              for ob in data24hrs if ob[index_bucket_a] is not None]
        apiTemp   = [ob[index_bucket_a] for ob in data24hrs if ob[index_bucket_a] is not None]
        try:
            dTime   = [abs(T - (obTime[0] - 3 * 3600)) for T in apiTime]
            if min(dTime) < 5 * 60:
                temp3h  = apiTemp[dTime.index(min(dTime))]
                time3h  = apiTime[dTime.index(min(dTime))]
                temp0h  = outTemp[0]
                time0h  = obTime[0]
            else:
                Logger.warning(f'tempTrend: {system().log_time()} - no data in 3 hour window')
                return errorOutput
        except Exception as Error:
            Logger.warning(f'tempTrend: {system().log_time()} - {Error}')
            return errorOutput
    else:
        return errorOutput

    # Calculate three hour temperature trend
    try:
        Trend = (temp0h - temp3h) / ((time0h - time3h) / 3600)
    except Exception as Error:
        Logger.warning(f'tempTrend: {system().log_time()} - {Error}')
        return errorOutput

    # Define temperature trend color
    if abs(Trend) < 0.05:
        Color = 'c8c8c8ff'
    elif Trend > 0:
        Color = 'f05e40ff'
    elif Trend < 1 / 3:
        Color = '00a4b4ff'

    # Return temperature trend
    return [Trend, 'c/hr', Color]


def tempMax(Temp, obTime, maxTemp, device, apiData, config):

    """ Calculate maximum temperature for specified device since midnight
        station time

    INPUTS:
        Temp                Current temperature                         [deg C]
        obTime              Current observation time                    [s]
        maxTemp             Current maximum temperature                 [deg C]
        device              Device ID that observation originates from
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        maxTemp             Maximum temperature                         [deg C]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'c', '-', None, time.time()]
    if Temp[0] is None:
        Logger.warning(f'tempMax: {system().log_time()} - Temp is None')
        return errorOutput
    elif obTime[0] is None:
        Logger.warning(f'tempMax: {system().log_time()} - obTime is None')
        return errorOutput

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of temperature in websocket packets
    if (str(device) == config['Station']['OutAirID']
            or str(device) == config['Station']['InAirID']):
        index_bucket_a  = 2
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a  = 7

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily maximum temperature
    if 'today' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['today'], 'obs'):
            dataToday = apiData[device]['today'].json()['obs']
            apiTime   = [item[0]              for item in dataToday if item[index_bucket_a] is not None]
            apiTemp   = [item[index_bucket_a] for item in dataToday if item[index_bucket_a] is not None]
            try:
                maxTemp = [max(apiTemp), 'c', apiTime[apiTemp.index(max(apiTemp))], 's', max(apiTemp), apiTime[apiTemp.index(max(apiTemp))]]
            except Exception as Error:
                Logger.warning(f'tempMax: {system().log_time()} - {Error}')
                maxTemp = errorOutput
        else:
            maxTemp = errorOutput

    # Else if midnight has passed, reset maximum temperature
    elif Now.date() > datetime.fromtimestamp(maxTemp[5], Tz).date():
        maxTemp = [Temp[0], 'c', obTime[0], 's', Temp[0], obTime[0]]

    # Else if current temperature is greater than maximum recorded temperature,
    # update maximum temperature
    elif Temp[0] > maxTemp[4]:
        maxTemp = [Temp[0], 'c', obTime[0], 's', Temp[0], obTime[0]]

    # Else maximum temperature unchanged, return existing values
    else:
        maxTemp = [maxTemp[4], 'c', maxTemp[2], 's', maxTemp[4], obTime[0]]

    # Return required variables
    return maxTemp


def tempMin(Temp, obTime, minTemp, device, apiData, config):

    """ Calculate minimum temperature for specified device since midnight
        station time

    INPUTS:
        Temp                Current temperature                         [deg C]
        obTime              Current observation time                    [s]
        minTemp             Current minimum temperature                 [deg C]
        device              Device ID
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        minTemp             Minumum temperature                         [deg C]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'c', '-', None, time.time()]
    if Temp[0] is None:
        Logger.warning(f'tempMin: {system().log_time()} - Temp is None')
        return errorOutput
    elif obTime[0] is None:
        Logger.warning(f'tempMin: {system().log_time()} - obTime is None')
        return errorOutput

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of temperature in websocket packets
    if (str(device) == config['Station']['OutAirID']
            or str(device) == config['Station']['InAirID']):
        index_bucket_a  = 2
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a  = 7

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily minimum temperature
    if 'today' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['today'], 'obs'):
            dataToday = apiData[device]['today'].json()['obs']
            apiTime   = [item[0]              for item in dataToday if item[index_bucket_a] is not None]
            apiTemp   = [item[index_bucket_a] for item in dataToday if item[index_bucket_a] is not None]
            try:
                minTemp = [min(apiTemp), 'c', apiTime[apiTemp.index(min(apiTemp))], 's', min(apiTemp), apiTime[apiTemp.index(min(apiTemp))]]
            except Exception as Error:
                Logger.warning(f'tempMin: {system().log_time()} - {Error}')
                minTemp = errorOutput
        else:
            minTemp = errorOutput

    # Else if midnight has passed, reset minimum temperature
    elif Now.date() > datetime.fromtimestamp(minTemp[5], Tz).date():
        minTemp = [Temp[0], 'c', obTime[0], 's', Temp[0], obTime[0]]

    # Else if current temperature is less than minimum recorded temperature,
    # update minimum temperature
    elif Temp[0] < minTemp[4]:
        minTemp = [Temp[0], 'c', obTime[0], 's', Temp[0], obTime[0]]

    # Else minimum temperature unchanged, return existing values
    else:
        minTemp = [minTemp[4], 'c', minTemp[2], 's', minTemp[4], obTime[0]]

    # Return required variables
    return minTemp


def strikeDeltaT(strikeTime):

    """ Calculate time since last lightning strike

    INPUTS:
        strikeTime          Time of last lightning strike               [s]

    OUTPUT:
        strikeDeltaT        Time since last lightning strike            [s]
    """

    # Return None if required variables are missing
    errorOutput = [None, 's', None]
    if strikeTime[0] is None:
        Logger.warning(f'strikeDeltaT: {system().log_time()} - strikeTime is None')
        return errorOutput

    # Calculate time since last lightning strike
    deltaT = time.time() - strikeTime[0]
    deltaT = [deltaT, 's', deltaT]

    # Return time since and distance to last lightning strike
    return deltaT


def strikeFrequency(obTime, device, apiData, config):

    """ Calculate lightning strike frequency over the previous 10 minutes and
        three hours

    INPUTS:
        obTime              Time of latest observation
        device              Device ID
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        strikeFrequency     Strike frequency over the previous 10       [Count]
                            minutes and three hours
    """

    # Return None if required variables are missing
    errorOutput = [None, '/min', None, '/min']
    if obTime[0] is None:
        Logger.warning(f'strikeFreq: {system().log_time()} - obTime is None')
        return errorOutput

    # Define index of total lightning strike counts in websocket packets
    if str(device) == config['Station']['OutAirID']:
        index_bucket_a  = 4
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a  = 15

    # Extract lightning strike count over the last three hours. Return None for
    # strikeFrequency if API call has failed
    if '24Hrs' in apiData[device] and weatherflow_api.verify_response(apiData[device]['24Hrs'], 'obs'):
        data24hrs = apiData[device]['24Hrs'].json()['obs']
        apiTime   = [ob[0] for ob in data24hrs if ob[index_bucket_a] is not None]
        try:
            dTime   = [abs(T - (obTime[0] - 3 * 3600)) for T in apiTime]
            if min(dTime) < 5 * 60:
                count3h = [ob[index_bucket_a] for ob in data24hrs[dTime.index(min(dTime)):] if ob[index_bucket_a] is not None]
            else:
                Logger.warning(f'strikeFreq: {system().log_time()} - no data in 3 hour window')
                count3h = None
        except Exception as Error:
            Logger.warning(f'strikeFreq: {system().log_time()} - {Error}')
            count3h = None
    else:
        count3h = None

    # Calculate average strike frequency over the last three hours
    if count3h is not None:
        activeStrikes = [count for count in count3h if count > 0]
        if len(activeStrikes) > 0:
            strikeFrequency3h = [sum(activeStrikes) / len(activeStrikes), '/min']
        else:
            strikeFrequency3h = [0.0, '/min']
    else:
        strikeFrequency3h = [None, '/min']

    # Extract lightning strike count over the last 10 minutes. Return None for
    # strikeFrequency if API call has failed
    if '24Hrs' in apiData[device] and weatherflow_api.verify_response(apiData[device]['24Hrs'], 'obs'):
        data24hrs = apiData[device]['24Hrs'].json()['obs']
        apiTime   = [ob[0] for ob in data24hrs if ob[index_bucket_a] is not None]
        try:
            dTime   = [abs(T - (obTime[0] - 600)) for T in apiTime]
            if min(dTime) < 2 * 60:
                count10m = [ob[index_bucket_a] for ob in data24hrs[dTime.index(min(dTime)):] if ob[index_bucket_a] is not None]
            else:
                Logger.warning(f'strikeFreq: {system().log_time()} - no data in 10 minute window')
                count10m = None
        except Exception as Error:
            Logger.warning(f'strikeFreq: {system().log_time()} - {Error}')
            count10m = None
    else:
        count10m = None

    # Calculate average strike frequency over the last 10 minutes
    if count10m is not None:
        activeStrikes = [count for count in count10m if count > 0]
        if len(activeStrikes) > 0:
            strikeFrequency10m = [sum(activeStrikes) / len(activeStrikes), '/min']
        else:
            strikeFrequency10m = [0.0, '/min']
    else:
        strikeFrequency10m = [None, '/min']

    # Return strikeFrequency for last 10 minutes and last three hours
    return strikeFrequency10m + strikeFrequency3h


def strikeCount(count, strikeCount, device, apiData, config):

    """ Calculate the number of lightning strikes for the last day/month/year

    INPUTS:
        count               Number of lightning strikes in the past minute  [Count]
        strikeCount         Dictionary containing fields:
            Today               Number of lightning strikes today           [Count]
            Yesterday           Number of lightning strikes in last month   [Count]
            Year                Number of lightning strikes in last year    [Count]
        device              Device ID
        apiData             WeatherFlow REST API data
        config              Station configuration


    OUTPUT:
        strikeCount         Dictionary containing fields:
            Today               Number of lightning strikes today           [Count]
            Yesterday           Number of lightning strikes in last month   [Count]
            Year                Number of lightning strikes in last year    [Count]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'count', None, time.time()]
    if count[0] is None:
        Logger.warning(f'strikeCount: {system().log_time()} - count is None')
        todayStrikes = monthStrikes = yearStrikes = errorOutput
        return {'today': todayStrikes, 'month': monthStrikes, 'year': yearStrikes}

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of total lightning strike counts in websocket packets
    if str(device) == config['Station']['OutAirID']:
        index_bucket_a = 4
        index_bucket_e = 4
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a = 15
        index_bucket_e = 24

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate total daily lightning strikes
    if 'today' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['today'], 'obs'):
            dataToday  = apiData[device]['today'].json()['obs']
            apiStrikes = [item[index_bucket_a] for item in dataToday if item[index_bucket_a] is not None]
            try:
                todayStrikes = [sum(x for x in apiStrikes), 'count', sum(x for x in apiStrikes), time.time()]
            except Exception as Error:
                Logger.warning(f'strikeCount: {system().log_time()} - {Error}')
                todayStrikes = errorOutput
        else:
            todayStrikes = errorOutput

    # Else if midnight has passed, reset daily lightning strike count to zero
    elif Now.date() > datetime.fromtimestamp(strikeCount['today'][3], Tz).date():
        todayStrikes = [count[0], 'count', count[0], time.time()]

    # Else, calculate current daily lightning strike count
    else:
        currentCount = strikeCount['today'][2]
        updatedCount = currentCount + count[0] if count[0] is not None else currentCount
        todayStrikes = [updatedCount, 'count', updatedCount, time.time()]

    # If console is initialising and today is the first day on the month, set
    # monthly lightning strikes to current daily lightning strikes
    if strikeCount['month'][0] is None and Now.day == 1:
        monthStrikes = [todayStrikes[0], 'count', todayStrikes[0], time.time()]

    # Else if console is initialising, calculate total monthly lightning strikes
    # from the WeatherFlow API data
    elif 'month' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['month'], 'obs'):
            dataMonth  = apiData[device]['month'].json()['obs']
            apiStrikes = [item[index_bucket_e] for item in dataMonth if item[index_bucket_e] is not None]
            try:
                monthStrikes = [sum(x for x in apiStrikes), 'count', sum(x for x in apiStrikes), time.time()]
                if todayStrikes[0] is not None:
                    monthStrikes[0] += todayStrikes[0]
                    monthStrikes[2] += todayStrikes[2]
            except Exception as Error:
                Logger.warning(f'strikeCount: {system().log_time()} - {Error}')
                monthStrikes = errorOutput
        else:
            monthStrikes = errorOutput

    # Else if the end of the month has passed, reset monthly lightning strike
    # count to zero
    elif Now.month > datetime.fromtimestamp(strikeCount['month'][3], Tz).month:
        monthStrikes = [count[0], 'count', count[0], time.time()]

    # Else, calculate current monthly lightning strike count
    else:
        currentCount = strikeCount['month'][2]
        updatedCount = currentCount + count[0] if count[0] is not None else currentCount
        monthStrikes = [updatedCount, 'count', updatedCount, time.time()]

    # If console is initialising and today is the first day on the year, set
    # yearly lightning strikes to current daily lightning strikes
    if strikeCount['year'][0] is None and Now.timetuple().tm_yday == 1:
        yearStrikes = [todayStrikes[0], 'count', todayStrikes[0], time.time()]

    # Else if console is initialising, calculate total yearly lightning strikes
    # from the WeatherFlow API data
    elif 'year' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['year'], 'obs'):
            dataYear   = apiData[device]['year'].json()['obs']
            apiStrikes = [item[index_bucket_e] for item in dataYear if item[index_bucket_e] is not None]
            try:
                yearStrikes = [sum(x for x in apiStrikes), 'count', sum(x for x in apiStrikes), time.time()]
                if todayStrikes[0] is not None:
                    yearStrikes[0] += todayStrikes[0]
                    yearStrikes[2] += todayStrikes[2]
            except Exception as Error:
                Logger.warning(f'strikeCount: {system().log_time()} - {Error}')
                yearStrikes = errorOutput
        else:
            yearStrikes = errorOutput

    # Else if the end of the year has passed, reset monthly and yearly lightning
    # strike count to zero
    elif Now.year > datetime.fromtimestamp(strikeCount['year'][3], Tz).year:
        monthStrikes = [count[0], 'count', count[0], time.time()]
        yearStrikes  = [count[0], 'count', count[0], time.time()]

    # Else, calculate current yearly lightning strike count
    else:
        currentCount = strikeCount['year'][2]
        updatedCount = currentCount + count[0] if count[0] is not None else currentCount
        yearStrikes = [updatedCount, 'count', updatedCount, time.time()]

    # Return Daily, Monthly, and Yearly lightning strike counts
    return {'today': todayStrikes, 'month': monthStrikes, 'year': yearStrikes}


def rainRate(minuteRain):

    """ Calculate the average windspeed since midnight station time

    INPUTS:
        windSpd             Rain accumulation for the current minute     [mm]

    OUTPUT:
        rainRate            Current instantaneous rain rate              [mm/hr]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'mm/hr', '-', None]
    if minuteRain[0] is None:
        Logger.warning(f'rainRate: {system().log_time()} - minuteRain is None')
        return errorOutput

    # Calculate instantaneous rain rate from instantaneous rain accumulation
    Rate = minuteRain[0] * 60

    # Define rain rate text based on calculated
    if Rate == 0:
        RateText = 'Currently Dry'
    elif Rate < 0.25:
        RateText = 'Very Light Rain'
    elif Rate < 1.0:
        RateText = 'Light Rain'
    elif Rate < 4.0:
        RateText = 'Moderate Rain'
    elif Rate < 16.0:
        RateText = 'Heavy Rain'
    elif Rate < 50.0:
        RateText = 'Very Heavy Rain'
    else:
        RateText = 'Extreme Rain'

    # Return instantaneous rain rate and text
    return [Rate, 'mm/hr', RateText, Rate]


def rainAccumulation(dailyRain, rainAccum, device, apiData, config):

    """ Calculate the rain accumulation for today/yesterday/month/year

    INPUTS:
        dailyRain           Daily rain accumulation                         [mm]
        rainAccum           Dictionary containing fields:
            Today               Rain accumulation for the current day       [mm]
            Yesterday           Rain accumulation yesterday                 [mm]
            Month               Rain accumulation for the current month     [mm]
            Year                Rain accumulation for the current year      [mm]
        device              Device ID
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        rainAccum           Dictionary containing fields:
            Today               Rain accumulation for the current day       [mm]
            Yesterday           Rain accumulation yesterday                 [mm]
            Month               Rain accumulation for the current month     [mm]
            Year                Rain accumulation for the current year      [mm]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'mm', None, time.time()]
    if dailyRain[0] is None:
        Logger.warning(f'rainAccum: {system().log_time()} - dailyRain is None')
        todayRain = yesterdayRain = monthRain = yearRain = errorOutput
        return {'today': todayRain, 'yesterday': yesterdayRain, 'month': monthRain, 'year': yearRain}

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of total daily rain accumulation in websocket packets
    if str(device) == config['Station']['SkyID']:
        index_bucket_a = 3
        index_bucket_e = 3
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a = 12
        index_bucket_e = 28

    # Set current daily rainfall accumulation
    todayRain = [dailyRain[0], 'mm', dailyRain[0], time.time()]

    # If console is initialising, calculate yesterday's rainfall from the
    # WeatherFlow API data
    if 'yesterday' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['yesterday'], 'obs'):
            yesterdayData = apiData[device]['yesterday'].json()['obs']
            rainData = [item[index_bucket_a] for item in yesterdayData if item[index_bucket_a] is not None]
            try:
                yesterdayRain = [sum(x for x in rainData), 'mm', sum(x for x in rainData), time.time()]
            except Exception as Error:
                Logger.warning(f'rainAccum: {system().log_time()} - {Error}')
                yesterdayRain = errorOutput
        else:
            yesterdayRain = errorOutput

    # Else if midnight has passed, set yesterday rainfall accumulation equal to
    # rainAccum['today'] (which still contains yesterday's accumulation)
    elif Now.date() > datetime.fromtimestamp(rainAccum['today'][3], Tz).date():
        yesterdayRain = [rainAccum['today'][2], 'mm', rainAccum['today'][2], time.time()]

    # Else, set yesterday rainfall accumulation as unchanged
    else:
        yesterdayRain = [rainAccum['yesterday'][2], 'mm', rainAccum['yesterday'][2], time.time()]

    # If console is initialising and today is the first day on the month, set
    # monthly rainfall to current daily rainfall
    if rainAccum['month'][0] is None and Now.day == 1:
        monthRain = [dailyRain[0], 'mm', 0, time.time()]

    # Else if console is initialising, calculate total monthly rainfall from
    # the WeatherFlow API data
    elif 'month' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['month'], 'obs'):
            monthData = apiData[device]['month'].json()['obs']
            rainData = [item[index_bucket_e] for item in monthData if item[index_bucket_e] is not None]
            try:
                monthRain = [sum(x for x in rainData), 'mm', sum(x for x in rainData), time.time()]
                if not math.isnan(dailyRain[0]):
                    monthRain[0] += dailyRain[0]
            except Exception as Error:
                Logger.warning(f'rainAccum: {system().log_time()} - {Error}')
                monthRain = errorOutput
        else:
            monthRain = errorOutput

    # Else if the end of the month has passed, reset monthly rain accumulation
    # to current daily rain accumulation
    elif Now.month > datetime.fromtimestamp(rainAccum['month'][3], Tz).month:
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        monthRain  = [dailyAccum, 'mm', 0, time.time()]

    # Else if midnight has passed, permanently add rainAccum['Today'] (which
    # still contains yesterday's accumulation) and current daily rainfall to
    # monthly rain accumulation
    elif Now.date() > datetime.fromtimestamp(rainAccum['month'][3], Tz).date():
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        monthRain  = [rainAccum['month'][2] + rainAccum['today'][2] + dailyAccum, 'mm', rainAccum['month'][2] + rainAccum['today'][2], time.time()]

    # Else, update current monthly rainfall accumulation
    else:
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        monthRain  = [rainAccum['month'][2] + dailyAccum, 'mm', rainAccum['month'][2], time.time()]

    # If console is initialising and today is the first day on the year, set
    # yearly rainfall to current daily rainfall
    if rainAccum['year'][0] is None and Now.timetuple().tm_yday == 1:
        yearRain = [dailyRain[0], 'mm', 0, time.time()]

    # Else if console is initialising, calculate total yearly rainfall from the
    # WeatherFlow API data
    elif 'year' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['year'], 'obs'):
            yearData = apiData[device]['year'].json()['obs']
            rainData = [item[index_bucket_e] for item in yearData if item[index_bucket_e] is not None]
            try:
                yearRain = [sum(x for x in rainData), 'mm', sum(x for x in rainData), time.time()]
                if not math.isnan(dailyRain[0]):
                    yearRain[0] += dailyRain[0]
            except Exception as Error:
                Logger.warning(f'rainAccum: {system().log_time()} - {Error}')
                yearRain = errorOutput
        else:
            yearRain = errorOutput

    # Else if the end of the year has passed, reset monthly and yearly rain
    # accumulation to current daily rain accumulation
    elif Now.year > datetime.fromtimestamp(rainAccum['year'][3], Tz).year:
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        yearRain   = [dailyAccum, 'mm', 0, time.time()]
        monthRain  = [dailyAccum, 'mm', 0, time.time()]

    # Else if midnight has passed, permanently add rainAccum['Today'] (which
    # still contains yesterday's accumulation) and current daily rainfall to
    # yearly rain accumulation
    elif Now.date() > datetime.fromtimestamp(rainAccum['year'][3], Tz).date():
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        yearRain  = [rainAccum['year'][2] + rainAccum['year'][2] + dailyAccum, 'mm', rainAccum['year'][2] + rainAccum['today'][2], time.time()]

    # Else, calculate current yearly rain accumulation
    else:
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        yearRain   = [rainAccum['year'][2] + dailyAccum, 'mm', rainAccum['year'][2], time.time()]

    # Return Daily, Monthly, and Yearly rainfall accumulation totals
    return {'today': todayRain, 'yesterday': yesterdayRain, 'month': monthRain, 'year': yearRain}


def avgWindSpeed(windSpd, avgWind, device, apiData, config):

    """ Calculate the average windspeed since midnight station time

    INPUTS:
        windSpd             Current wind speed                            [m/s]
        avgWind             Current average wind speed since midnight     [m/s]
        device              Device ID
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        AvgWind             Average wind speed since midnight             [m/s]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'mps', None, None, time.time()]
    if windSpd[0] is None:
        Logger.warning(f'avgSpeed: {system().log_time()} - windSpd is None')
        return errorOutput

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of wind speed in websocket packets
    if str(device) == config['Station']['SkyID']:
        index_bucket_a = 5
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a = 2

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily averaged windspeed
    if 'today' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['today'], 'obs'):
            todayData = apiData[device]['today'].json()['obs']
            windSpd = [item[index_bucket_a] for item in todayData if item[index_bucket_a] is not None]
            try:
                average = sum(x for x in windSpd) / len(windSpd)
                windAvg = [average, 'mps', average, len(windSpd), time.time()]
            except Exception as Error:
                Logger.warning(f'avgSpeed: {system().log_time()} - {Error}')
                windAvg = errorOutput
        else:
            windAvg = errorOutput

    # Else if midnight has passed, reset daily averaged wind speed
    elif Now.date() > datetime.fromtimestamp(avgWind[4], Tz).date():
        windAvg = [windSpd[0], 'mps', windSpd[0], 1, time.time()]

    # Else, calculate current daily averaged wind speed
    else:
        length = avgWind[3] + 1
        currentAvg = avgWind[2]
        updatedAvg = (length - 1) / length * currentAvg + 1 / length * windSpd[0]
        windAvg = [updatedAvg, 'mps', updatedAvg, length, time.time()]

    # Return daily averaged wind speed
    return windAvg


def maxWindGust(windGust, maxGust, device, apiData, config):

    """ Calculate the maximum wind gust since midnight station time

    INPUTS:
        windGust            Current wind gust                             [m/s]
        maxGust             Current maximum wind gust since midnight      [m/s]
        device              Device ID
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        maxGust             Maximum wind gust since midnight              [m/s]
    """

    # Return None if required variables are missing
    errorOutput = [None, 'mps', None, time.time()]
    if windGust[0] is None:
        Logger.warning(f'maxGust: {system().log_time()} - windGust is None')
        return errorOutput

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of wind speed in websocket packets
    if str(device) == config['Station']['SkyID']:
        index_bucket_a = 6
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a = 3

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily maximum wind gust
    if 'today' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['today'], 'obs'):
            todayData = apiData[device]['today'].json()['obs']
            windGust = [item[index_bucket_a] for item in todayData if item[index_bucket_a] is not None]
            try:
                maxGust  = [max(x for x in windGust), 'mps', max(x for x in windGust), time.time()]
            except Exception as Error:
                Logger.warning(f'maxGust: {system().log_time()} - {Error}')
                maxGust = errorOutput
        else:
            maxGust = errorOutput

    # Else if midnight has passed, reset maximum recorded wind gust
    elif Now.date() > datetime.fromtimestamp(maxGust[3], Tz).date():
        maxGust = [windGust[0], 'mps', windGust[0], time.time()]

    # Else if current gust speed is greater than maximum recorded gust speed,
    # update maximum gust speed
    elif windGust[0] > maxGust[2]:
        maxGust = [windGust[0], 'mps', windGust[0], time.time()]

    # Else maximum gust speed is unchanged, return existing value
    else:
        maxGust = [maxGust[2], 'mps', maxGust[2], time.time()]

    # Return maximum wind gust
    return maxGust


def cardinalWindDir(windDir, windSpd=[1, 'mps']):

    """ Defines the cardinal wind direction from the current wind direction in
        degrees. Sets the wind direction as "Calm" if current wind speed is zero

    INPUTS:
        windDir             Current wind direction                     [degrees]
        windSpd             Current wind speed                             [m/s]

    OUTPUT:
        cardinalWind        Cardinal wind direction
    """

    # Return None if required variables are missing
    errorOutput = [windDir[0], windDir[1], '-', '-']
    if windDir[0] is None and windSpd[0] != 0.0:
        Logger.warning(f'cardWindDir: {system().log_time()} - windDir is None')
        return errorOutput
    elif windSpd[0] is None:
        Logger.warning(f'cardWindDir: {system().log_time()} - windSpd is None')
        return errorOutput

    # Define all possible cardinal wind directions and descriptions
    Direction = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N']
    Description = ['Due North', 'North NE', 'North East', 'East NE', 'Due East', 'East SE', 'South East', 'South SE',
                   'Due South', 'South SW', 'South West', 'West SW', 'Due West', 'West NW', 'North West', 'North NW',
                   'Due North']

    # Define actual cardinal wind direction and description based on current
    # wind direction in degrees
    if windSpd[0] == 0:
        Direction = 'Calm'
        Description = '[color=9aba2fff]Calm[/color]'
        cardinalWind = [windDir[0], windDir[1], Direction, Description]
    else:
        Ind = int(round(windDir[0] / 22.5))
        Direction = Direction[Ind]
        Description = Description[Ind].split()[0] + ' [color=9aba2fff]' + Description[Ind].split()[1] + '[/color]'
        cardinalWind = [windDir[0], windDir[1], Direction, Description]

    # Return cardinal wind direction and description
    return cardinalWind


def beaufortScale(windSpd):

    """ Defines the Beaufort scale value from the current wind speed

    INPUTS:
        windSpd             Current wind speed                             [m/s]

    OUTPUT:
        beaufortScale       Beaufort Scale speed, description, and icon
    """

    # Return None if required variables are missing
    errorOutput = windSpd + ['-', '-', '-']
    if windSpd[0] is None:
        Logger.warning(f'beaufScale: {system().log_time()} - windSpd is None')
        return errorOutput

    # Define Beaufort scale cutoffs and Force numbers
    Cutoffs = [0.5, 1.5, 3.3, 5.5, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6]
    Force = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    Description = ['Calm Conditions', 'Light Air',         'Light Breeze',  'Gentle Breeze',
                   'Moderate Breeze', 'Fresh Breeze',      'Strong Breeze', 'Near Gale Force',
                   'Gale Force',      'Severe Gale Force', 'Storm Force',   'Violent Storm',
                   'Hurricane Force']

    # Define Beaufort Scale wind speed, description, and icon
    Ind = bisect.bisect(Cutoffs, windSpd[0])
    Beaufort = [float(Force[Ind]), str(Force[Ind]), Description[Ind]]

    # Return Beaufort Scale speed, description, and icon
    return windSpd + Beaufort


def UVIndex(uvLevel):

    """ Defines the UV index from the current UV level

    INPUTS:
        uvLevel             Current UV level                               [m/s]

    OUTPUT:
        uvIndex             UV index
    """

    # Return None if required variables are missing
    errorOutput = [None, 'index', '-', '#646464']
    if uvLevel[0] is None:
        Logger.warning(f'UVIndex: {system().log_time()} - uvLevel is None')
        return errorOutput

    # Define UV Index cutoffs and level descriptions
    Cutoffs = [0, 3, 6, 8, 11]
    Level   = ['None', 'Low', 'Moderate', 'High', 'Very High', 'Extreme']

    # Define UV index colours
    Grey   = '#646464'
    Green  = '#558B2F'
    Yellow = '#F9A825'
    Orange = '#EF6C00'
    Red    = '#B71C1C'
    Violet = '#6A1B9A'
    Color  = [Grey, Green, Yellow, Orange, Red, Violet]

    # Set the UV index
    if uvLevel[0] > 0:
        Ind = bisect.bisect(Cutoffs, round(uvLevel[0], 1))
    else:
        Ind = 0
    uvIndex = [round(uvLevel[0], 1), 'index', Level[Ind], Color[Ind]]

    # Return UV Index icon
    return uvIndex


def peakSunHours(radiation, peakSun, device, apiData, config):

    """ Calculate peak sun hours since midnight and daily solar potential

    INPUTS:
        Radiation           Current solar radiation                        [W/m^2]
        peakSun             Current peak sun hours since midnight          [hours]
        device              Device ID
        apiData             WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        peakSun             Peak sun hours since midnight and solar potential
    """

    # Return None if required variables are missing
    errorOutput = [None, 'hrs', '-']
    if radiation[0] is None:
        Logger.warning(f'peakSun: {system().log_time()} - radiation is None')
        return errorOutput

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Calculate time of sunrise and sunset or use existing values
    if peakSun[0] is None or Now > datetime.fromtimestamp(peakSun[5], Tz):
        Observer          = ephem.Observer()
        Observer.pressure = 0
        Observer.lat      = str(config['Station']['Latitude'])
        Observer.lon      = str(config['Station']['Longitude'])
        Observer.horizon  = '-0:34'
        sunrise           = Observer.next_rising(ephem.Sun()).datetime().timestamp()
        sunset            = Observer.next_setting(ephem.Sun()).datetime().timestamp()
    else:
        sunrise           = peakSun[4]
        sunset            = peakSun[5]

    # Define index of radiation in websocket packets
    if str(device) == config['Station']['SkyID']:
        index_bucket_a = 10
    elif str(device) == config['Station']['TempestID']:
        index_bucket_a = 11

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate Peak Sun Hours
    if 'today' in apiData[device]:
        if weatherflow_api.verify_response(apiData[device]['today'], 'obs'):
            dataToday = apiData[device]['today'].json()['obs']
            radiation = [item[index_bucket_a] for item in dataToday if item[index_bucket_a] is not None]
            try:
                watthrs = sum([item * (1 / 60) for item in radiation])
                peakSun = [watthrs / 1000, 'hrs', watthrs, sunrise, sunset, time.time()]
            except Exception as Error:
                Logger.warning(f'peakSun: {system().log_time()} - {Error}')
                return errorOutput
        else:
            return errorOutput

    # Else if midnight has passed, reset Peak Sun Hours
    elif Now.date() > datetime.fromtimestamp(peakSun[6], Tz).date():
        watthrs = radiation[0] * (1 / 60)
        peakSun = [watthrs / 1000, 'hrs', watthrs, sunrise, sunset, time.time()]

    # Else calculate current Peak Sun Hours
    else:
        watthrs = peakSun[3] + radiation[0] * (1 / 60)
        peakSun = [watthrs / 1000, 'hrs', watthrs, sunrise, sunset, time.time()]

    # Calculate proportion of daylight hours that have passed
    if datetime.fromtimestamp(sunrise, Tz) <= Now <= datetime.fromtimestamp(sunset, Tz):
        daylightFactor = (time.time() - sunrise) / (sunset - sunrise)
    else:
        daylightFactor = 1

    # Define daily solar potential
    if peakSun[0] / daylightFactor == 0:
        peakSun.insert(2, '[color=#646464ff]None[/color]')
    elif peakSun[0] / daylightFactor < 2:
        peakSun.insert(2, '[color=#4575b4ff]Limited[/color]')
    elif peakSun[0] / daylightFactor < 4:
        peakSun.insert(2, '[color=#fee090ff]Moderate[/color]')
    elif peakSun[0] / daylightFactor < 6:
        peakSun.insert(2, '[color=#f46d43ff]Good[/color]')
    else:
        peakSun.insert(2, '[color=#d73027ff]Excellent[/color]')

    # Return Peak Sun Hours
    return peakSun
