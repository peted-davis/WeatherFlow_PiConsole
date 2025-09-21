""" Returns the derived weather variables required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
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
from lib.request_api import weatherflow_api
from lib.system      import system
from lib             import derived_variables as derive

# Import required Python modules
from kivy.logger  import Logger
from datetime     import datetime, timedelta
import bisect
import ephem
import math
import pytz
import time


def dew_point(out_temp, humidity):

    """ Calculate the dew point from the temperature and relative humidity

    INPUTS:
        out_temp            Outdoor temperature from AIR/TEMPEST device      [C]
        humidity            Relative humidity from AIR/TEMPEST module        [%]

    OUTPUT:
        dew_point           Dew point                                        [C]
    """

    # Return None if required variables are missing
    error_output = [None, 'c']
    if out_temp[0] is None:
        Logger.warning(f'dewPoint: {system().log_time()} - out_temp is None')
        return error_output
    elif humidity[0] is None:
        Logger.warning(f'dewPoint: {system().log_time()} - humidity is None')
        return error_output

    # Calculate dew point
    if humidity[0] > 0:
        A = 17.625
        B = 243.04
        N = B * (math.log(humidity[0] / 100.0) + (A * out_temp[0]) / (B + out_temp[0]))
        D = A - math.log(humidity[0] / 100.0) - (A * out_temp[0]) / (B + out_temp[0])
        dew_point = N / D
    else:
        dew_point = None

    # Return Dew Point
    return [dew_point, 'c']


def feels_like(out_temp, humidity, wind_spd, config):

    """ Calculate the Feels Like temperature from the temperature, relative
    humidity, and wind speed

    INPUTS:
        out_temp            Outdoor temperature from AIR/TEMPEST device    [C]
        humidity            Relative humidity from AIR/TEMPEST device      [%]
        wind_spd            Wind speed from SKY/TEMPEST device             [m/s]
        config              Station configuration

    OUTPUT:
        feels_like          Feels Like temperature                         [C]
    """

    # Return None if required variables are missing
    error_output = [None, 'c', '-', '-']
    if out_temp[0] is None:
        Logger.warning(f'feelsLike: {system().log_time()} - out_temp is None')
        return error_output
    elif humidity[0] is None:
        Logger.warning(f'feelsLike: {system().log_time()} - humidity is None')
        return error_output
    elif wind_spd[0] is None:
        Logger.warning(f'feelsLike: {system().log_time()} - wind_spd is None')
        return error_output

    # Convert observation units as required
    temp_F   = [out_temp[0] * (9 / 5) + 32, 'f']
    wind_mph = [wind_spd[0] * 2.2369362920544, 'mph']
    wind_kph = [wind_spd[0] * 3.6, 'kph']

    # If temperature is less than 10 degrees celcius and wind speed is higher
    # than 3 mph, calculate wind chill using the Joint Action Group for
    # Temperature Indices formula
    if out_temp[0] <= 10 and wind_mph[0] > 3:
        wind_chill = (+ 13.12 + 0.6215 * out_temp[0]
                      - 11.37 * (wind_kph[0])**0.16 + 0.3965 * out_temp[0]
                      * (wind_kph[0])**0.16)
        feels_like = [wind_chill, 'c']

    # If temperature is at or above 80 degress farenheit (26.67 C), and humidity
    # is at or above 40%, calculate the Heat Index
    elif temp_F[0] >= 80 and humidity[0] >= 40:
        heat_index = (-42.379 + (2.04901523 * temp_F[0])
                      + (10.1433127 * humidity[0])
                      - (0.22475541 * temp_F[0] * humidity[0])
                      - (6.83783e-3 * temp_F[0]**2)
                      - (5.481717e-2 * humidity[0]**2)
                      + (1.22874e-3 * temp_F[0]**2 * humidity[0])
                      + (8.5282e-4 * temp_F[0] * humidity[0]**2)
                      - (1.99e-6 * temp_F[0]**2 * humidity[0]**2))
        feels_like = [(heat_index - 32) * (5 / 9), 'c']

    # Else set Feels Like temperature to observed temperature
    else:
        feels_like = out_temp

    # Define 'FeelsLike' temperature cutoffs
    cutoffs = [float(item) for item in list(config['FeelsLike'].values())]

    # Define 'FeelsLike temperature text and icon
    description = ['Feeling extremely cold', 'Feeling freezing cold', 'Feeling very cold',
                   'Feeling cold', 'Feeling mild', 'Feeling warm', 'Feeling hot',
                   'Feeling very hot', 'Feeling extremely hot', '-']
    icon =        ['ExtremelyCold', 'FreezingCold', 'VeryCold', 'Cold', 'Mild', 'Warm',
                   'Hot', 'VeryHot', 'ExtremelyHot', '-']
    if config['Units']['Temp'] == 'f':
        idx = bisect.bisect(cutoffs, feels_like[0] * (9 / 5) + 32)
    else:
        idx = bisect.bisect(cutoffs, feels_like[0])

    # Return 'Feels Like' temperature
    return [feels_like[0], feels_like[1], description[idx], icon[idx]]


def SLP(pressure, device, config):

    """ Calculate sea level pressure from station pressure

    INPUTS:
        pressure            Station pressure from AIR/TEMPEST device        [mb]
        device              Device ID
        config              Station configuration

    OUTPUT:
        SLP                 Sea level pressure                              [mb]
    """

    # Return None if required variables are missing
    error_output = [None, 'mb', None]
    if pressure[0] is None:
        Logger.warning(f'SLP: {system().log_time()} - pressure is None')
        return error_output

    # Extract required configuration variables
    elevation = config['Station']['Elevation']
    if str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]:
        height = config['Station']['OutAirHeight']
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        height = config['Station']['TempestHeight']

    # Define required constants
    P0      = 1013.25
    Rd      = 287.05
    gamma_s = 0.0065
    g       = 9.80665
    T0      = 288.15
    elevation = float(elevation) + float(height)

    # Calculate and return sea level pressure
    SLP = (pressure[0]
           * (1 + ((P0 / pressure[0])**((Rd * gamma_s) / g))
           * ((gamma_s * elevation) / T0))**(g / (Rd * gamma_s))
           )
    return [SLP, 'mb', SLP]


def SLP_trend(pressure, ob_time, device, api_data, config):

    """ Calculate the pressure trend from the sea level pressure over the last
        three hours

    INPUTS:
        pressure            Station pressure from AIR/TEMPEST device        [mb]
        ob_time             Time of latest observation                      [s]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        trend               Sea level pressure trend                        [mb]
    """

    # Return None if required variables are missing
    error_output = [None, 'mb/hr', '-', '-']
    if pressure[0] is None:
        Logger.warning(f'SLP_trend: {system().log_time()} - pressure is None')
        return error_output
    elif ob_time[0] is None:
        Logger.warning(f'SLP_trend: {system().log_time()} - ob_time is None')
        return error_output

    # Define index of pressure in websocket packets
    if str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]:
        index_bucket_a  = 1
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a  = 6

    # If REST API services are enabled, extract required observations from
    # WeatherFlow API data based on device type indicated in API call
    if (int(config['System']['rest_api'])
            and '24Hrs' in api_data[device]
            and weatherflow_api.verify_response(api_data[device]['24Hrs'], 'obs')):
        data_24hrs = api_data[device]['24Hrs'].json()['obs']
        api_time   = [ob[0]              for ob in data_24hrs if ob[index_bucket_a] is not None]
        api_pres   = [ob[index_bucket_a] for ob in data_24hrs if ob[index_bucket_a] is not None]
        try:
            d_time = [abs(T - (ob_time[0] - 3 * 3600)) for T in api_time]
            if min(d_time) < 5 * 60:
                pres_3h  = [api_pres[d_time.index(min(d_time))], 'mb']
                time_3h  = [api_time[d_time.index(min(d_time))], 's']
                pres_0h  = pressure
                time_0h  = ob_time
            else:
                Logger.warning(f'SLP_trend: {system().log_time()} - no data in 3 hour window')
                return error_output
        except Exception as error:
            Logger.warning(f'SLP_trend: {system().log_time()} - {error}')
            return error_output
    else:
        return error_output

    # Convert station pressure into sea level pressure
    pres_3h = SLP(pres_3h, device, config)
    pres_0h = SLP(pres_0h, device, config)

    # Calculate three hour temperature trend
    try:
        trend = (pres_0h[0] - pres_3h[0]) / ((time_0h[0] - time_3h[0]) / 3600)
    except Exception as error:
        Logger.warning(f'SLP_trend: {system().log_time()} - {error}')
        return error_output

    # Define pressure trend text
    if trend > 2 / 3:
        trend_txt = '[color=ff8837ff]Rising rapidly[/color]'
    elif trend >= 1 / 3:
        trend_txt = '[color=ff8837ff]Rising[/color]'
    elif trend <= -2 / 3:
        trend_txt = '[color=00a4b4ff]Falling rapidly[/color]'
    elif trend <= -1 / 3:
        trend_txt = '[color=00a4b4ff]Falling[/color]'
    else:
        trend_txt = '[color=9aba2fff]Steady[/color]'

    # Define weather tendency based on pressure and trend
    if pres_0h[0] >= 1023:
        if 'Falling rapidly' in trend_txt:
            tendency = 'Becoming cloudy and warmer'
        else:
            tendency = 'Fair conditions likely'
    elif 1009 < pres_0h[0] < 1023:
        if 'Falling rapidly' in trend_txt:
            tendency = 'Rainy conditions likely'
        else:
            tendency = 'Conditions unchanged'
    elif pres_0h[0] <= 1009:
        if 'Falling rapidly' in trend_txt:
            tendency = 'Stormy conditions likely'
        elif 'Falling' in trend_txt:
            tendency = 'Rainy conditions likely'
        else:
            tendency = 'Becoming clearer and cooler'
    else:
        tendency = '-'

    # Return pressure trend
    return [trend, 'mb/hr', trend_txt, tendency]


def SLP_max(pressure, ob_time, max_pres, device, api_data, config):

    """ Calculate maximum SLP pressure since midnight station time

    INPUTS:
        pressure            Station pressure from AIR/TEMPEST device        [mb]
        ob_time             Time of latest observation                      [s]
        max_pres            Daily maximum SLP pressure                      [mb]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        max_pres            Daily maximum SLP pressure                      [mb]
    """

    # Return None if required variables are missing
    error_output = [None, 'mb', '-', None, time.time()]
    if pressure[0] is None:
        Logger.warning(f'SLP_max: {system().log_time()} - pressure is None')
        return error_output
    elif ob_time[0] is None:
        Logger.warning(f'SLP_max: {system().log_time()} - ob_time is None')
        return error_output

    # Calculate sea level pressure
    SLP = derive.SLP(pressure, device, config)

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    time_now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of temperature in websocket packets
    if str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]:
        index_bucket_a  = 1
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a  = 6

    # If console is initialising and REST API services are enabled, download all
    # data for current day using Weatherflow API and calculate daily maximum
    # pressure
    if int(config['System']['rest_api']) and max_pres[0] is None:
        if ('today' in api_data[device]
                and weatherflow_api.verify_response(api_data[device]['today'], 'obs')):
            data_today = api_data[device]['today'].json()['obs']
            ob_time    = [item[0]                       for item in data_today if item[index_bucket_a] is not None]
            pressure   = [[item[index_bucket_a], 'mb']  for item in data_today if item[index_bucket_a] is not None]
            SLP        = [derive.SLP(P, device, config) for P    in pressure]
            try:
                max_pres   = [max(SLP)[0], 'mb', ob_time[SLP.index(max(SLP))], 's', max(SLP)[0], ob_time[SLP.index(max(SLP))]]
            except Exception as error:
                Logger.warning(f'SLP_max: {system().log_time()} - {error}')
                max_pres = error_output
        else:
            max_pres = error_output

    # If console is initialising and REST API services are disabled, set daily
    # minimum pressure to current temperature
    elif not int(config['System']['rest_api']) and max_pres[0] is None:
        max_pres = [SLP[0], 'mb', ob_time[0], 's', SLP[0], ob_time[0]]

    # Else if midnight has passed, reset maximum pressure
    elif time_now.date() > datetime.fromtimestamp(max_pres[5], Tz).date():
        max_pres = [SLP[0], 'mb', ob_time[0], 's', SLP[0], ob_time[0]]

    # Else if current pressure is greater than maximum recorded pressure, update
    # maximum pressure
    elif SLP[0] > max_pres[4]:
        max_pres = [SLP[0], 'mb', ob_time[0], 's', SLP[0], ob_time[0]]

    # Else maximum pressure unchanged, return existing values
    else:
        max_pres = [max_pres[4], 'mb', max_pres[2], 's', max_pres[4], ob_time[0]]

    # Return required variables
    return max_pres


def SLP_min(pressure, ob_time, min_pres, device, api_data, config):

    """ Calculate minimum SLP pressure since midnight station time

    INPUTS:
        pressure            Station pressure from AIR/TEMPEST device        [mb]
        ob_time             Time of latest observation                      [s]
        max_pres            Daily minimum SLP pressure                      [mb]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        max_pres            Daily minimum SLP pressure                      [mb]
    """

    # Return None if required variables are missing
    error_output = [None, 'mb', '-', None, time.time()]
    if pressure[0] is None:
        Logger.warning(f'SLP_min: {system().log_time()} - pressure is None')
        return error_output
    elif ob_time[0] is None:
        Logger.warning(f'SLP_min: {system().log_time()} - ob_time is None')
        return error_output

    # Calculate sea level pressure
    SLP = derive.SLP(pressure, device, config)

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    time_now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of temperature in websocket packets
    if str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]:
        index_bucket_a  = 1
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a  = 6

    # If console is initialising and REST API services are enabled, download all
    # data for current day using Weatherflow API and calculate daily minimum
    # pressure
    if int(config['System']['rest_api']) and min_pres[0] is None:
        if ('today' in api_data[device]
                and weatherflow_api.verify_response(api_data[device]['today'], 'obs')):
            data_today = api_data[device]['today'].json()['obs']
            ob_time    = [item[0]                       for item in data_today if item[index_bucket_a] is not None]
            pressure   = [[item[index_bucket_a], 'mb']  for item in data_today if item[index_bucket_a] is not None]
            SLP        = [derive.SLP(P, device, config) for P    in pressure]
            try:
                min_pres   = [min(SLP)[0], 'mb', ob_time[SLP.index(min(SLP))], 's', min(SLP)[0], ob_time[SLP.index(min(SLP))]]
            except Exception as error:
                Logger.warning(f'SLP_min: {system().log_time()} - {error}')
                min_pres = error_output
        else:
            min_pres = error_output

    # If console is initialising and REST API services are disabled, set daily
    # minimum pressure to current temperature
    elif not int(config['System']['rest_api']) and min_pres[0] is None:
        min_pres = [SLP[0], 'mb', ob_time[0], 's', SLP[0], ob_time[0]]

    # Else if midnight has passed, reset maximum and minimum pressure
    elif time_now.date() > datetime.fromtimestamp(min_pres[5], Tz).date():
        min_pres = [SLP[0], 'mb', ob_time[0], 's', SLP[0], ob_time[0]]

    # Else if current pressure is less than minimum recorded pressure, update
    # minimum pressure and time
    elif SLP[0] < min_pres[4]:
        min_pres = [SLP[0], 'mb', ob_time[0], 's', SLP[0], ob_time[0]]

    # Else minimum pressure unchanged, return existing values
    else:
        min_pres = [min_pres[4], 'mb', min_pres[2], 's', min_pres[4], ob_time[0]]

    # Return required variables
    return min_pres


def temp_diff(out_temp, ob_time, device, api_data, config):

    """ Calculate 24 hour temperature difference

    INPUTS:
        out_temp            Current temperature from AIR/TEMPEST device  [deg C]
        ob_time             Observation time                             [s]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        d_temp              24 hour temperature difference               [deg C]
    """

    # Return None if required variables are missing
    error_output = [None, 'dc', '-']
    if out_temp[0] is None:
        Logger.warning(f'temp_diff: {system().log_time()} - out_temp is None')
        return error_output
    elif ob_time[0] is None:
        Logger.warning(f'temp_diff: {system().log_time()} - ob_time is None')
        return error_output

    # Define index of temperature in websocket packets
    if str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]:
        index_bucket_a  = 2
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a  = 7

    # If REST API services are enabled, extract required observations from
    # WeatherFlow API data based on device type indicated in API call
    if (int(config['System']['rest_api'])
            and '24Hrs' in api_data[device]
            and weatherflow_api.verify_response(api_data[device]['24Hrs'], 'obs')):
        data_24hrs = api_data[device]['24Hrs'].json()['obs']
        api_time   = [ob[0]              for ob in data_24hrs if ob[index_bucket_a] is not None]
        api_temp   = [ob[index_bucket_a] for ob in data_24hrs if ob[index_bucket_a] is not None]
        try:
            d_time   = ob_time[0] - api_time[0]
            if d_time > 86400 - (5 * 60) and d_time < 86400 + (5 * 60):
                temp_24h = api_temp[0]
                temp_0h  = out_temp[0]
            else:
                Logger.warning(f'temp_diff: {system().log_time()} - no data in 24 hour window')
                return error_output
        except Exception as error:
            Logger.warning(f'temp_diff: {system().log_time()} - {error}')
            return error_output
    else:
        return error_output

    # Calculate 24 hour temperature Difference
    try:
        d_temp = temp_0h - temp_24h
    except Exception as error:
        Logger.warning(f'temp_diff: {system().log_time()} - {error}')
        return error_output

    # Define temperature difference text
    if abs(d_temp) < 0.05:
        diff_txt = '[color=c8c8c8ff][/color]'
    elif d_temp > 0:
        diff_txt = '[color=f05e40ff]  warmer[/color]'
    elif d_temp < 0:
        diff_txt = '[color=00a4b4ff]  colder[/color]'

    # Return 24 hour temperature difference
    return [d_temp, 'dc', diff_txt]


def temp_trend(out_temp, ob_time, device, api_data, config):

    """ Calculate 3 hour temperature trend

    INPUTS:
        out_temp            Current temperature from AIR/TEMPEST device  [deg C]
        ob_time             Observation time                             [s]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        Trend               24 hour temperature difference              [deg C]
    """

    # Return None if required variables are missing
    error_output = [None, 'c/hr', 'c8c8c8ff']
    if out_temp[0] is None:
        Logger.warning(f'temp_trend: {system().log_time()} - out_temp is None')
        return error_output
    elif ob_time[0] is None:
        Logger.warning(f'temp_trend: {system().log_time()} - ob_time is None')
        return error_output

    # Define index of temperature in websocket packets
    if str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]:
        index_bucket_a  = 2
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a  = 7

    # If REST API services are enabled, extract required observations from
    # WeatherFlow API data based on device type indicated in API call
    if (int(config['System']['rest_api'])
            and '24Hrs' in api_data[device]
            and weatherflow_api.verify_response(api_data[device]['24Hrs'], 'obs')):
        data_24hrs = api_data[device]['24Hrs'].json()['obs']
        api_time   = [ob[0]              for ob in data_24hrs if ob[index_bucket_a] is not None]
        api_temp   = [ob[index_bucket_a] for ob in data_24hrs if ob[index_bucket_a] is not None]
        try:
            d_time   = [abs(T - (ob_time[0] - 3 * 3600)) for T in api_time]
            if min(d_time) < 5 * 60:
                temp_3h  = api_temp[d_time.index(min(d_time))]
                time_3h  = api_time[d_time.index(min(d_time))]
                temp_0h  = out_temp[0]
                time_0h  = ob_time[0]
            else:
                Logger.warning(f'temp_trend: {system().log_time()} - no data in 3 hour window')
                return error_output
        except Exception as error:
            Logger.warning(f'temp_trend: {system().log_time()} - {error}')
            return error_output
    else:
        return error_output

    # Calculate three hour temperature trend
    try:
        trend = (temp_0h - temp_3h) / ((time_0h - time_3h) / 3600)
    except Exception as error:
        Logger.warning(f'temp_trend: {system().log_time()} - {error}')
        return error_output

    # Define temperature trend color
    if abs(trend) < 0.05:
        Color = 'c8c8c8ff'
    elif trend > 0:
        Color = 'f05e40ff'
    elif trend < 1 / 3:
        Color = '00a4b4ff'

    # Return temperature trend
    return [trend, 'c/hr', Color]


def temp_max(temp, ob_time, max_temp, device, api_data, config):

    """ Calculate maximum temperature since midnight station time

    INPUTS:
        temp                Current temperature  from AIR/TEMPEST device [deg C]
        ob_time             Observation time                             [s]
        max_temp            Daily maximum temperature                    [deg C]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        max_temp            Daily maximum temperature                    [deg C]
    """

    # Return None if required variables are missing
    error_output = [None, 'c', '-', None, time.time()]
    if temp[0] is None:
        Logger.warning(f'temp_max: {system().log_time()} - temp is None')
        return error_output
    elif ob_time[0] is None:
        Logger.warning(f'temp_max: {system().log_time()} - ob_time is None')
        return error_output

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    time_now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of temperature in websocket packets
    if (str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]
            or str(device) in [config['Station']['InAirID'], config['Station']['InAirSN']]):
        index_bucket_a  = 2
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a  = 7

    # If console is initialising and REST API services are enabled, download all
    # data for current day using Weatherflow API and calculate daily maximum
    # temperature
    if int(config['System']['rest_api']) and max_temp[0] is None:
        if ('today' in api_data[device]
                and weatherflow_api.verify_response(api_data[device]['today'], 'obs')):
            data_today = api_data[device]['today'].json()['obs']
            api_time   = [item[0]              for item in data_today if item[index_bucket_a] is not None]
            api_temp   = [item[index_bucket_a] for item in data_today if item[index_bucket_a] is not None]
            try:
                max_temp = [max(api_temp), 'c', api_time[api_temp.index(max(api_temp))], 's', max(api_temp), api_time[api_temp.index(max(api_temp))]]
            except Exception as error:
                Logger.warning(f'temp_max: {system().log_time()} - {error}')
                max_temp = error_output
        else:
            max_temp = error_output

    # If console is initialising and REST API services are disabled, set daily
    # maximum temperature to current temperature
    elif not int(config['System']['rest_api']) and max_temp[0] is None:
        max_temp = [temp[0], 'c', ob_time[0], 's', temp[0], ob_time[0]]

    # Else if midnight has passed, reset maximum temperature to current
    # temperature
    elif time_now.date() > datetime.fromtimestamp(max_temp[5], Tz).date():
        max_temp = [temp[0], 'c', ob_time[0], 's', temp[0], ob_time[0]]

    # Else if current temperature is greater than maximum recorded temperature,
    # update maximum temperature
    elif temp[0] > max_temp[4]:
        max_temp = [temp[0], 'c', ob_time[0], 's', temp[0], ob_time[0]]

    # Else maximum temperature unchanged, return existing values
    else:
        max_temp = [max_temp[4], 'c', max_temp[2], 's', max_temp[4], ob_time[0]]

    # Return required variables
    return max_temp


def temp_min(temp, ob_time, min_temp, device, api_data, config):

    """ Calculate minimum temperature since midnight station time

    INPUTS:
        temp                Current temperature  from AIR/TEMPEST device [deg C]
        ob_time             Observation time                             [s]
        min_temp            Daily minimum temperature                    [deg C]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        min_temp            Daily minimum temperature                    [deg C]
    """

    # Return None if required variables are missing
    error_output = [None, 'c', '-', None, time.time()]
    if temp[0] is None:
        Logger.warning(f'temp_min: {system().log_time()} - Temp is None')
        return error_output
    elif ob_time[0] is None:
        Logger.warning(f'temp_min: {system().log_time()} - ob_time is None')
        return error_output

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    time_now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of temperature in websocket packets
    if (str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]
            or str(device) in [config['Station']['InAirID'], config['Station']['InAirSN']]):
        index_bucket_a  = 2
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a  = 7

    # If console is initialising and REST API services are enabled, download all
    # data for current day using Weatherflow API and calculate daily minimum
    # temperature
    if int(config['System']['rest_api']) and min_temp[0] is None:
        if 'today' in api_data[device] and weatherflow_api.verify_response(api_data[device]['today'], 'obs'):
            data_today = api_data[device]['today'].json()['obs']
            api_time   = [item[0]              for item in data_today if item[index_bucket_a] is not None]
            api_temp   = [item[index_bucket_a] for item in data_today if item[index_bucket_a] is not None]
            try:
                min_temp = [min(api_temp), 'c', api_time[api_temp.index(min(api_temp))], 's', min(api_temp), api_time[api_temp.index(min(api_temp))]]
            except Exception as error:
                Logger.warning(f'temp_min: {system().log_time()} - {error}')
                min_temp = error_output
        else:
            min_temp = error_output

    # If console is initialising and REST API services are disabled, set daily
    # minimum temperature to current temperature
    elif not int(config['System']['rest_api']) and min_temp[0] is None:
        min_temp = [temp[0], 'c', ob_time[0], 's', temp[0], ob_time[0]]

    # Else if midnight has passed, reset minimum temperature to current
    # temperature
    elif time_now.date() > datetime.fromtimestamp(min_temp[5], Tz).date():
        min_temp = [temp[0], 'c', ob_time[0], 's', temp[0], ob_time[0]]

    # Else if current temperature is less than minimum recorded temperature,
    # update minimum temperature
    elif temp[0] < min_temp[4]:
        min_temp = [temp[0], 'c', ob_time[0], 's', temp[0], ob_time[0]]

    # Else minimum temperature unchanged, return existing values
    else:
        min_temp = [min_temp[4], 'c', min_temp[2], 's', min_temp[4], ob_time[0]]

    # Return required variables
    return min_temp


def strike_delta_t(strike_time, config):

    """ Calculate time since last lightning strike

    INPUTS:
        strike_time          Time of last lightning strike               [s]

    OUTPUT:
        delta_t              Time since last lightning strike            [s]
    """

    # Return None if required variables are missing
    error_output = [None, 's', None]
    if strike_time[0] is None:
        if config['System']['Connection'] != 'UDP':
            Logger.warning(f'strike_delta_t: {system().log_time()} - strike_time is None')
        return error_output

    # Calculate time since last lightning strike
    delta_t = time.time() - strike_time[0]
    delta_t = [delta_t, 's', delta_t]

    # Return time since and distance to last lightning strike
    return delta_t


def strike_frequency(ob_time, device, api_data, config):

    """ Calculate lightning strike frequency over the previous 10 minutes and
        three hours

    INPUTS:
        ob_time             Time of latest observation
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        frequency           Strike frequency over the previous 10       [Count]
                            minutes and three hours
    """

    # Return None if required variables are missing
    error_output = [None, '/min', None, '/min']
    if ob_time[0] is None:
        Logger.warning(f'strike_freq: {system().log_time()} - ob_time is None')
        return error_output

    # Define index of total lightning strike counts in websocket packets
    if str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]:
        index_bucket_a  = 4
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a  = 15

    # If REST API services are enabled, extract lightning strike count over the
    # last three hours
    if (int(config['System']['rest_api'])
            and '24Hrs' in api_data[device]
            and weatherflow_api.verify_response(api_data[device]['24Hrs'], 'obs')):
        data_24hrs = api_data[device]['24Hrs'].json()['obs']
        api_time   = [ob[0] for ob in data_24hrs if ob[index_bucket_a] is not None]
        try:
            d_time   = [abs(T - (ob_time[0] - 3 * 3600)) for T in api_time]
            if min(d_time) < 5 * 60:
                count_3h = [ob[index_bucket_a] for ob in data_24hrs[d_time.index(min(d_time)):] if ob[index_bucket_a] is not None]
            else:
                Logger.warning(f'strike_freq: {system().log_time()} - no data in 3 hour window')
                count_3h = None
        except Exception as error:
            Logger.warning(f'strike_freq: {system().log_time()} - {error}')
            count_3h = None
    else:
        count_3h = None

    # Calculate average strike frequency over the last three hours
    if count_3h is not None:
        active_strikes = [count for count in count_3h if count > 0]
        if len(active_strikes) > 0:
            frequency_3h = [sum(active_strikes) / len(active_strikes), '/min']
        else:
            frequency_3h = [0.0, '/min']
    else:
        frequency_3h = [None, '/min']

    # If REST API services are enabled, extract lightning strike count over the
    # last 10 minutes
    if (int(config['System']['rest_api'])
            and '24Hrs' in api_data[device]
            and weatherflow_api.verify_response(api_data[device]['24Hrs'], 'obs')):
        data_24hrs = api_data[device]['24Hrs'].json()['obs']
        data_24hrs = api_data[device]['24Hrs'].json()['obs']
        api_time   = [ob[0] for ob in data_24hrs if ob[index_bucket_a] is not None]
        try:
            d_time   = [abs(T - (ob_time[0] - 600)) for T in api_time]
            if min(d_time) < 2 * 60:
                count_10m = [ob[index_bucket_a] for ob in data_24hrs[d_time.index(min(d_time)):] if ob[index_bucket_a] is not None]
            else:
                Logger.warning(f'strike_freq: {system().log_time()} - no data in 10 minute window')
                count_10m = None
        except Exception as error:
            Logger.warning(f'strike_freq: {system().log_time()} - {error}')
            count_10m = None
    else:
        count_10m = None

    # Calculate average strike frequency over the last 10 minutes
    if count_10m is not None:
        active_strikes = [count for count in count_10m if count > 0]
        if len(active_strikes) > 0:
            frequency_10m = [sum(active_strikes) / len(active_strikes), '/min']
        else:
            frequency_10m = [0.0, '/min']
    else:
        frequency_10m = [None, '/min']

    # Return frequency for last 10 minutes and last three hours
    return frequency_10m + frequency_3h


def strike_count(count, strike_count, device, api_data, config):

    """ Calculate the number of lightning strikes for the last day/month/year

    INPUTS:
        count               Number of lightning strikes in the past minute  [Count]
        strike_count        Dictionary containing fields:
            Today               Number of lightning strikes today           [Count]
            Yesterday           Number of lightning strikes in last month   [Count]
            Year                Number of lightning strikes in last year    [Count]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration


    OUTPUT:
        strike_count         Dictionary containing fields:
            Today               Number of lightning strikes today           [Count]
            Yesterday           Number of lightning strikes in last month   [Count]
            Year                Number of lightning strikes in last year    [Count]
    """

    # Return None if required variables are missing
    error_output = [None, 'count', None, time.time()]
    if count[0] is None:
        Logger.warning(f'strike_count: {system().log_time()} - count is None')
        today_strikes = month_strikes = year_strikes = error_output
        return {'today': today_strikes, 'month': month_strikes, 'year': year_strikes}

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    time_now = datetime.now(pytz.utc).astimezone(Tz)
    day_date = time_now.strftime("%Y-%m-%d")
    month_date = time_now.replace(day=1).strftime("%Y-%m-%d")
    year_date  = time_now.replace(day=1, month=1).strftime("%Y-%m-%d")

    # Define index of total lightning strike counts in websocket packets
    if str(device) in [config['Station']['OutAirID'], config['Station']['OutAirSN']]:
        index_bucket_a = 4
        index_bucket_e = 4
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a = 15
        index_bucket_e = 24

    # ==========================================================================
    # TODAY STRIKES
    # ==========================================================================
    # If console is initialising and REST API services are enabled, calculate
    # total daily lightning strikes using WeatherFlow API
    if int(config['System']['rest_api']) and strike_count['today'][0] is None:
        if not int(config['System']['stats_endpoint']):
            if 'today' in api_data[device] and weatherflow_api.verify_response(api_data[device]['today'], 'obs'):
                data_today = api_data[device]['today'].json()['obs']
                strikes = [item[index_bucket_a] for item in data_today if item[index_bucket_a] is not None]
                try:
                    today_strikes = [sum(x for x in strikes), 'count', sum(x for x in strikes), time.time()]
                except Exception as error:
                    Logger.warning(f'strike_count: {system().log_time()} - {error}')
                    today_strikes = error_output
            else:
                today_strikes = error_output
        elif int(config['System']['stats_endpoint']):
            if 'statistics' in api_data[device] and weatherflow_api.verify_response(api_data[device]['statistics'], 'stats_day'):
                statistics = api_data[device]['statistics'].json()
                if statistics["stats_day"][-1][0] == day_date:
                    strikes = statistics["stats_day"][-1][24]
                    try:
                        today_strikes = [strikes, 'count', strikes, time.time()]
                    except Exception as error:
                        Logger.warning(f'strike_count: {system().log_time()} - {error}')
                        today_strikes = error_output
                else:
                    today_strikes = error_output
            else:
                today_strikes = error_output

    # Else if console is initialising and REST API services are not enabled,
    # set total daily lightning strikes equal to last minute count
    elif not int(config['System']['rest_api']) and strike_count['today'][0] is None:
        today_strikes = [count[0], 'count', count[0], time.time()]

    # Else if midnight has passed, reset daily lightning strike count to zero
    elif time_now.date() > datetime.fromtimestamp(strike_count['today'][3], Tz).date():
        today_strikes = [count[0], 'count', count[0], time.time()]

    # Else, calculate current daily lightning strike count
    else:
        current_count = strike_count['today'][2]
        updated_count = current_count + count[0] if count[0] is not None else current_count
        today_strikes = [updated_count, 'count', updated_count, time.time()]

    # ==========================================================================
    # MONTH COUNTS
    # ==========================================================================
    # If console is initialising and today is the first day on the month, set
    # monthly lightning strikes to current daily lightning strikes
    if strike_count['month'][0] is None and time_now.day == 1:
        month_strikes = [today_strikes[0], 'count', today_strikes[0], time.time()]

    # Else if console is initialising and REST API services are enabled,
    # calculate total monthly lightning strikes using WeatherFlow API
    elif int(config['System']['rest_api']) and strike_count['month'][0] is None:
        if not int(config['System']['stats_endpoint']):
            if 'month' in api_data[device] and weatherflow_api.verify_response(api_data[device]['month'], 'obs'):
                month_data  = api_data[device]['month'].json()['obs']
                strikes     = [item[index_bucket_e] for item in month_data if item[index_bucket_e] is not None]
                try:
                    month_strikes = [sum(x for x in strikes), 'count', sum(x for x in strikes), time.time()]
                    if today_strikes[0] is not None:
                        month_strikes[0] += today_strikes[0]
                        month_strikes[2] += today_strikes[2]
                except Exception as error:
                    Logger.warning(f'strike_count: {system().log_time()} - {error}')
                    month_strikes = error_output
            else:
                month_strikes = error_output
        elif int(config['System']['stats_endpoint']):
            if 'statistics' in api_data[device] and weatherflow_api.verify_response(api_data[device]['statistics'], 'stats_month'):
                statistics = api_data[device]['statistics'].json()
                if statistics["stats_month"][-1][0] == month_date:
                    strikes = statistics["stats_month"][-1][24]
                    try:
                        month_strikes = [strikes, 'count', strikes, time.time()]
                    except Exception as error:
                        Logger.warning(f'strike_count: {system().log_time()} - {error}')
                        month_strikes = error_output
                else:
                    month_strikes = error_output
            else:
                month_strikes = error_output

    # Else if console is initialising and REST API services are not enabled, set
    # total daily lightning strikes equal to last minute count
    elif not int(config['System']['rest_api']) and strike_count['month'][0] is None:
        month_strikes = [count[0], 'count', count[0], time.time()]

    # Else if the end of the month has passed, reset monthly lightning strike
    # count to zero
    elif time_now.month > datetime.fromtimestamp(strike_count['month'][3], Tz).month:
        month_strikes = [count[0], 'count', count[0], time.time()]

    # Else, calculate current monthly lightning strike count
    else:
        current_count = strike_count['month'][2]
        updated_count = current_count + count[0] if count[0] is not None else current_count
        month_strikes = [updated_count, 'count', updated_count, time.time()]

    # ==========================================================================
    # YEAR COUNTS
    # ==========================================================================
    # If console is initialising and today is the first day on the year, set
    # yearly lightning strikes to current daily lightning strikes
    if strike_count['year'][0] is None and time_now.timetuple().tm_yday == 1:
        year_strikes = [today_strikes[0], 'count', today_strikes[0], time.time()]

    # Else if console is initialising and REST API services are enabled,
    # calculate total yearly lightning strikes using WeatherFlow API
    elif int(config['System']['rest_api']) and strike_count['year'][0] is None:
        if not int(config['System']['stats_endpoint']):
            if 'year' in api_data[device] and weatherflow_api.verify_response(api_data[device]['year'], 'obs'):
                year_data = api_data[device]['year'].json()['obs']
                strikes   = [item[index_bucket_e] for item in year_data if item[index_bucket_e] is not None]
                try:
                    year_strikes = [sum(x for x in strikes), 'count', sum(x for x in strikes), time.time()]
                    if today_strikes[0] is not None:
                        year_strikes[0] += today_strikes[0]
                        year_strikes[2] += today_strikes[2]
                except Exception as error:
                    Logger.warning(f'strike_count: {system().log_time()} - {error}')
                    year_strikes = error_output
            else:
                year_strikes = error_output
        elif int(config['System']['stats_endpoint']):
            if 'statistics' in api_data[device] and weatherflow_api.verify_response(api_data[device]['statistics'], 'stats_year'):
                statistics = api_data[device]['statistics'].json()
                if statistics["stats_year"][-1][0] == year_date:
                    strikes = statistics["stats_year"][-1][24]
                    try:
                        year_strikes = [strikes, 'count', strikes, time.time()]
                    except Exception as error:
                        Logger.warning(f'strike_count: {system().log_time()} - {error}')
                        year_strikes = error_output
                else:
                    year_strikes = error_output
            else:
                year_strikes = error_output

    # Else if console is initialising and REST API services are not enabled, set
    # total yearly lightning strikes equal to last minute count
    elif not int(config['System']['rest_api']) and strike_count['month'][0] is None:
        year_strikes = [count[0], 'count', count[0], time.time()]

    # Else if the end of the year has passed, reset monthly and yearly lightning
    # strike count to zero
    elif time_now.year > datetime.fromtimestamp(strike_count['year'][3], Tz).year:
        month_strikes = [count[0], 'count', count[0], time.time()]
        year_strikes  = [count[0], 'count', count[0], time.time()]

    # Else, calculate current yearly lightning strike count
    else:
        current_count = strike_count['year'][2]
        updated_count = current_count + count[0] if count[0] is not None else current_count
        year_strikes = [updated_count, 'count', updated_count, time.time()]

    # Return Daily, Monthly, and Yearly lightning strike counts
    return {'today': today_strikes, 'month': month_strikes, 'year': year_strikes}


def rain_rate(minute_rain):

    """ Calculate the instantaneous rain rate over the period of an hour

    INPUTS:
        minute_rain         Rain accumulation over previous minute      [mm]

    OUTPUT:
        rainRate            Instantaneous rain rate                     [mm/hr]
    """

    # Return None if required variables are missing
    error_output = [None, 'mm/hr', '-', None]
    if minute_rain[0] is None:
        Logger.warning(f'rainRate: {system().log_time()} - minute_rain is None')
        return error_output

    # Calculate instantaneous rain rate from instantaneous rain accumulation
    rate = minute_rain[0] * 60

    # Define rain rate text based on calculated
    if rate == 0:
        rate_text = 'Currently Dry'
    elif rate < 0.25:
        rate_text = 'Very Light Rain'
    elif rate < 1.0:
        rate_text = 'Light Rain'
    elif rate < 4.0:
        rate_text = 'Moderate Rain'
    elif rate < 16.0:
        rate_text = 'Heavy Rain'
    elif rate < 50.0:
        rate_text = 'Very Heavy Rain'
    else:
        rate_text = 'Extreme Rain'

    # Return instantaneous rain rate and text
    return [rate, 'mm/hr', rate_text, rate]


def rain_accumulation(minute_rain, daily_rain, rain_accum, device, api_data, config):

    """ Calculate the rain accumulation for today/yesterday/month/year

    INPUTS:
        minute_rain         Rain accumulation over previous minute          [mm]
        daily_rain          Daily rain accumulation                         [mm]
        rain_accum          Dictionary containing fields:
            today               Rain accumulation for current day           [mm]
            yesterday           Rain accumulation for yesterday             [mm]
            month               Rain accumulation for current month         [mm]
            year                Rain accumulation for current year          [mm]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        rain_accum          Dictionary containing fields:
            today               Rain accumulation for current day           [mm]
            yesterday           Rain accumulation for yesterday             [mm]
            month               Rain accumulation for current month         [mm]
            year                Rain accumulation for current year          [mm]
    """

    # Return None if required variables are missing
    error_output = [None, 'mm', None, time.time()]
    if minute_rain[0] is None and daily_rain[0] is None:
        Logger.warning(f'rain_accum: {system().log_time()} - minute_rain and daily_rain are None')
        today_rain = yesterday_rain = month_rain = year_rain = error_output
        return {'today': today_rain, 'yesterday': yesterday_rain, 'month': month_rain, 'year': year_rain}

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    time_now = datetime.now(pytz.utc).astimezone(Tz)
    day_date = time_now.strftime("%Y-%m-%d")
    yesterday_date = (time_now - timedelta(days=1)).strftime("%Y-%m-%d")
    month_date = time_now.replace(day=1).strftime("%Y-%m-%d")
    year_date  = time_now.replace(day=1, month=1).strftime("%Y-%m-%d")

    # Define index of total daily rain accumulation in websocket packets
    if str(device) in [config['Station']['SkyID'], config['Station']['SkySN']]:
        index_bucket_a = 3
        index_bucket_e = 3
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a = 12
        index_bucket_e = 28

    # ==========================================================================
    # TODAY RAIN
    # ==========================================================================
    # Set current daily rainfall accumulation for websocket connections
    if config['System']['Connection'] == 'Websocket':
        if daily_rain[0] is not None:
            today_rain = [daily_rain[0], 'mm', daily_rain[0], time.time()]
        else:
            today_rain = error_output

    # Else, set current daily rainfall accumulation for UDP connections
    elif config['System']['Connection'] == 'UDP':

        # If console is initialising and REST API services are enabled, download
        # all data for current day using Weatherflow API and calculate todays's
        # rainfall
        if int(config['System']['rest_api']) and rain_accum['today'][0] is None:
            if not int(config['System']['stats_endpoint']):
                if 'today' in api_data[device] and weatherflow_api.verify_response(api_data[device]['today'], 'obs'):
                    today_data = api_data[device]['today'].json()['obs']
                    rain_data = [item[index_bucket_a] for item in today_data if item[index_bucket_a] is not None]
                    try:
                        today_rain = [sum(x for x in rain_data), 'mm', sum(x for x in rain_data), time.time()]
                    except Exception as error:
                        Logger.warning(f'rain_accum: {system().log_time()} - {error}')
                        today_rain = error_output
                else:
                    today_rain = error_output
            elif int(config['System']['stats_endpoint']):    
                if ('statistics' in api_data[device] and weatherflow_api.verify_response(api_data[device]['statistics'], 'stats_day')):
                    statistics = api_data[device]['statistics'].json()
                    if statistics["stats_day"][-1][0] == day_date:
                        rain_data = statistics["stats_day"][-1][28]
                        try:
                            today_rain = [rain_data, 'mm', rain_data, time.time()]
                        except Exception as error:
                            Logger.warning(f'rain_accum: {system().log_time()} - {error}')
                            today_rain = error_output
                    else:
                        today_rain = error_output
                else:
                    today_rain = error_output              

        # Else if console is initialising and REST API services are not enabled,
        # set today's rainfall accumulation equal to minute_rain
        elif not int(config['System']['rest_api']) and rain_accum['today'][0] is None:
            today_rain = [minute_rain[0], 'mm', minute_rain[0], time.time()]

        # Else if midnight has passed, set today's rainfall accumulation equal
        # to minute_rain
        elif time_now.date() > datetime.fromtimestamp(rain_accum['today'][3], Tz).date():
            today_rain = [minute_rain[0], 'mm', minute_rain[0], time.time()]

        # Else, update today's rainfall with latest minute_rain
        else:
            today_rain = [rain_accum['today'][2] + minute_rain[0], 'mm', rain_accum['today'][2] + minute_rain[0], time.time()]

    # ==========================================================================
    # YESTERDAY RAIN
    # ==========================================================================
    # If console is initialising and REST API services are enabled, download
    # all data for yesterday using Weatherflow API and calculate yesterday's
    # rainfall
    if int(config['System']['rest_api']) and rain_accum['yesterday'][0] is None:
        if not int(config['System']['stats_endpoint']):
            if 'yesterday' in api_data[device] and weatherflow_api.verify_response(api_data[device]['yesterday'], 'obs'):
                yesterday_data = api_data[device]['yesterday'].json()['obs']
                rain_data = [item[index_bucket_a] for item in yesterday_data if item[index_bucket_a] is not None]
                try:
                    yesterday_rain = [sum(x for x in rain_data), 'mm', sum(x for x in rain_data), time.time()]
                except Exception as error:
                    Logger.warning(f'rain_accum: {system().log_time()} - {error}')
                    yesterday_rain = error_output
            else:
                yesterday_rain = error_output
        elif int(config['System']['stats_endpoint']):   
            if ('statistics' in api_data[device] and weatherflow_api.verify_response(api_data[device]['statistics'], 'stats_day')):
                statistics = api_data[device]['statistics'].json()
                if statistics["stats_day"][-2][0] == yesterday_date:
                    rain_data = statistics["stats_day"][-2][28]
                    try:
                        yesterday_rain = [rain_data, 'mm', rain_data, time.time()]
                    except Exception as error:
                        Logger.warning(f'rain_accum: {system().log_time()} - {error}')
                        yesterday_rain = error_output
                else:
                    yesterday_rain = error_output
            else:
                yesterday_rain = error_output   

    # Else if midnight has passed, set yesterday's rainfall accumulation equal
    # to rain_accum['today'] (which still contains yesterday's accumulation)
    elif (rain_accum['today'][0] is not None
            and time_now.date() > datetime.fromtimestamp(rain_accum['today'][3], Tz).date()):
        yesterday_rain = [rain_accum['today'][2], 'mm', rain_accum['today'][2], time.time()]

    # Else if console is initialising and REST API services are not enabled, set
    # yesterday's rainfall accumulation equal to None
    elif not int(config['System']['rest_api']) and rain_accum['yesterday'][0] is None:
        yesterday_rain = error_output

    # Else, set yesterday rainfall accumulation as unchanged
    else:
        yesterday_rain = [rain_accum['yesterday'][2], 'mm', rain_accum['yesterday'][2], time.time()]

    # ==========================================================================
    # MONTH RAIN
    # ==========================================================================
    # If console is initialising and today is the first day on the month, set
    # monthly rainfall to current daily rainfall
    if rain_accum['month'][0] is None and time_now.day == 1:
        month_rain = [today_rain[0], 'mm', 0, time.time()]

    # Else if console is initialising and REST API services are enabled,
    # download all data for the current month using Weatherflow API and
    # calculate the monthly rainfall
    elif int(config['System']['rest_api']) and rain_accum['month'][0] is None:
        if today_rain[0] is not None:
            if not int(config['System']['stats_endpoint']):
                if 'month' in api_data[device] and weatherflow_api.verify_response(api_data[device]['month'], 'obs'):
                    month_data = api_data[device]['month'].json()['obs']
                    rain_data  = [item[index_bucket_e] for item in month_data if item[index_bucket_e] is not None]
                    try:
                        month_rain = [sum(x for x in rain_data), 'mm', sum(x for x in rain_data), time.time()]
                        month_rain[0] += today_rain[0]
                    except Exception as error:
                        Logger.warning(f'rain_accum: {system().log_time()} - {error}')
                        month_rain = error_output
                else:
                    month_rain = error_output
            elif int(config['System']['stats_endpoint']):
                if ('statistics' in api_data[device] and weatherflow_api.verify_response(api_data[device]['statistics'], 'stats_month')):
                    statistics = api_data[device]['statistics'].json()
                    if statistics["stats_month"][-1][0] == month_date:
                        rain_data = statistics["stats_month"][-1][28]
                        try:
                            month_rain = [rain_data, 'mm', rain_data, time.time()]
                            month_rain[2] -= today_rain[0]
                        except Exception as error:
                            Logger.warning(f'rain_accum: {system().log_time()} - {error}')
                            month_rain = error_output
                    else:
                        month_rain = error_output
                else:
                    month_rain = error_output 
        else:
            month_rain = error_output 
     
    # Else if console is initialising and REST API services are not enabled, set
    # monthly rainfall accumulation equal to minute_rain
    elif not int(config['System']['rest_api']) and rain_accum['month'][0] is None:
        month_rain = [minute_rain[0], 'mm', minute_rain[0], time.time()]

    # Else if the end of the month has passed, reset monthly rain accumulation
    # to current daily rain accumulation
    elif time_now.month > datetime.fromtimestamp(rain_accum['month'][3], Tz).month:
        daily_accum = today_rain[0] if not today_rain[0] is None else 0
        month_rain  = [daily_accum, 'mm', 0, time.time()]

    # Else if midnight has passed, permanently add rain_accum['Today'] (which
    # still contains yesterday's accumulation) and current daily rainfall to
    # monthly rain accumulation
    elif time_now.date() > datetime.fromtimestamp(rain_accum['month'][3], Tz).date():
        daily_accum = today_rain[0] if not today_rain[0] is None else 0
        month_rain  = [rain_accum['month'][2] + rain_accum['today'][2] + daily_accum, 'mm', rain_accum['month'][2] + rain_accum['today'][2], time.time()]

    # Else, update current monthly rainfall accumulation
    else:
        daily_accum = today_rain[0] if not today_rain[0] is None else 0
        month_rain  = [rain_accum['month'][2] + daily_accum, 'mm', rain_accum['month'][2], time.time()]

    # ==========================================================================
    # YEAR RAIN
    # ==========================================================================
    # If console is initialising and today is the first day on the year, set
    # yearly rainfall to current daily rainfall
    if rain_accum['year'][0] is None and time_now.timetuple().tm_yday == 1:
        year_rain = [today_rain[0], 'mm', 0, time.time()]

    # Else if console is initialising, and REST API services are enabled,
    # download all data for the current year using Weatherflow API and
    # calculate the yearly rainfall
    elif int(config['System']['rest_api']) and rain_accum['year'][0] is None:
        if today_rain[0] is not None:
            if not int(config['System']['stats_endpoint']):
                if 'year' in api_data[device] and weatherflow_api.verify_response(api_data[device]['year'], 'obs'):
                    year_data = api_data[device]['year'].json()['obs']
                    rain_data = [item[index_bucket_e] for item in year_data if item[index_bucket_e] is not None]
                    try:
                        year_rain = [sum(x for x in rain_data), 'mm', sum(x for x in rain_data), time.time()]
                        year_rain[0] += today_rain[0]
                    except Exception as error:
                        Logger.warning(f'rain_accum: {system().log_time()} - {error}')
                        year_rain = error_output
                else:
                    year_rain = error_output
            elif int(config['System']['stats_endpoint']):
                if ('statistics' in api_data[device] and weatherflow_api.verify_response(api_data[device]['statistics'], 'stats_month')):
                    statistics = api_data[device]['statistics'].json()
                    if statistics["stats_year"][-1][0] == year_date:
                        rain_data = statistics["stats_year"][-1][28]
                        try:
                            year_rain = [rain_data, 'mm', rain_data, time.time()]
                            year_rain[2] -= today_rain[0]
                        except Exception as error:
                            Logger.warning(f'rain_accum: {system().log_time()} - {error}')
                            year_rain = error_output
                    else:
                        year_rain = error_output
                else:
                    year_rain = error_output 
        else:
            year_rain = error_output 

    # Else if console is initialising and REST API services are not enabled, set
    # yearly rainfall accumulation equal to minute_rain
    elif not int(config['System']['rest_api']) and rain_accum['year'][0] is None:
        year_rain = [minute_rain[0], 'mm', minute_rain[0], time.time()]

    # Else if the end of the year has passed, reset monthly and yearly rain
    # accumulation to current daily rain accumulation
    elif time_now.year > datetime.fromtimestamp(rain_accum['year'][3], Tz).year:
        daily_accum = today_rain[0] if not today_rain[0] is None else 0
        year_rain   = [daily_accum, 'mm', 0, time.time()]
        month_rain  = [daily_accum, 'mm', 0, time.time()]

    # Else if midnight has passed, permanently add rain_accum['Today'] (which
    # still contains yesterday's accumulation) and current daily rainfall to
    # yearly rain accumulation
    elif time_now.date() > datetime.fromtimestamp(rain_accum['year'][3], Tz).date():
        daily_accum = today_rain[0] if not today_rain[0] is None else 0
        year_rain  = [rain_accum['year'][2] + rain_accum['year'][2] + daily_accum, 'mm', rain_accum['year'][2] + rain_accum['today'][2], time.time()]

    # Else, calculate current yearly rain accumulation
    else:
        daily_accum = today_rain[0] if not today_rain[0] is None else 0
        year_rain   = [rain_accum['year'][2] + daily_accum, 'mm', rain_accum['year'][2], time.time()]

    # Return Daily, Monthly, and Yearly rainfall accumulation totals
    return {'today': today_rain, 'yesterday': yesterday_rain, 'month': month_rain, 'year': year_rain}


def avg_wind_speed(wind_spd, avg_wind, device, api_data, config):

    """ Calculate the average windspeed since midnight station time

    INPUTS:
        wind_spd            Wind speed                                  [m/s]
        avg_wind            Average wind speed since midnight           [m/s]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        AvgWind             Average wind speed since midnight           [m/s]
    """

    # Return None if required variables are missing
    error_output = [None, 'mps', None, None, time.time()]
    if wind_spd[0] is None:
        Logger.warning(f'avgSpeed: {system().log_time()} - wind_spd is None')
        return error_output

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    time_now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of wind speed in websocket packets
    if str(device) in [config['Station']['SkyID'], config['Station']['SkySN']]:
        index_bucket_a = 5
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a = 2

    # If console is initialising and REST API services are enabled, download all
    # data for current day using Weatherflow API and calculate daily averaged
    # windspeed
    if int(config['System']['rest_api']) and avg_wind[0] is None:
        if ('today' in api_data[device]
                and weatherflow_api.verify_response(api_data[device]['today'], 'obs')):
            today_data = api_data[device]['today'].json()['obs']
            wind_spd = [item[index_bucket_a] for item in today_data if item[index_bucket_a] is not None]
            try:
                average = sum(x for x in wind_spd) / len(wind_spd)
                wind_avg = [average, 'mps', average, len(wind_spd), time.time()]
            except Exception as error:
                Logger.warning(f'avgSpeed: {system().log_time()} - {error}')
                wind_avg = error_output
        else:
            wind_avg = error_output

    # If console is initialising and REST API services are not enabled,
    # set daily averaged wind speed to current wind speed
    elif not int(config['System']['rest_api']) and avg_wind[0] is None:
        wind_avg = [wind_spd[0], 'mps', wind_spd[0], 1, time.time()]

    # Else if midnight has passed, reset daily averaged wind speed
    elif time_now.date() > datetime.fromtimestamp(avg_wind[4], Tz).date():
        wind_avg = [wind_spd[0], 'mps', wind_spd[0], 1, time.time()]

    # Else, calculate current daily averaged wind speed
    else:
        length = avg_wind[3] + 1
        current_avg = avg_wind[2]
        updated_avg = (length - 1) / length * current_avg + 1 / length * wind_spd[0]
        wind_avg    = [updated_avg, 'mps', updated_avg, length, time.time()]

    # Return daily averaged wind speed
    return wind_avg


def max_wind_gust(wind_gust, max_gust, device, api_data, config):

    """ Calculate the maximum wind gust since midnight station time

    INPUTS:
        wind_gust           Wind gust                               [m/s]
        max_gust            Maximum wind gust since midnight        [m/s]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        max_gust            Maximum wind gust since midnight        [m/s]
    """

    # Return None if required variables are missing
    error_output = [None, 'mps', None, time.time()]
    if wind_gust[0] is None:
        Logger.warning(f'max_gust: {system().log_time()} - wind_gust is None')
        return error_output

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    time_now = datetime.now(pytz.utc).astimezone(Tz)

    # Define index of wind speed in websocket packets
    if str(device) in [config['Station']['SkyID'], config['Station']['SkySN']]:
        index_bucket_a = 6
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a = 3

    # If console is initialising and REST API services are enabled, download all
    # data for current day using Weatherflow API and calculate maximum wind gust
    if int(config['System']['rest_api']) and max_gust[0] is None:
        if ('today' in api_data[device]
                and weatherflow_api.verify_response(api_data[device]['today'], 'obs')):
            today_data = api_data[device]['today'].json()['obs']
            wind_gust = [item[index_bucket_a] for item in today_data if item[index_bucket_a] is not None]
            try:
                max_gust  = [max(x for x in wind_gust), 'mps', max(x for x in wind_gust), time.time()]
            except Exception as error:
                Logger.warning(f'max_gust: {system().log_time()} - {error}')
                max_gust = error_output
        else:
            max_gust = error_output

    # If console is initialising and REST API services are not enabled,
    # set maximum wind gust to current wind gust
    elif not int(config['System']['rest_api']) and max_gust[0] is None:
        max_gust = [wind_gust[0], 'mps', wind_gust[0], time.time()]

    # Else if midnight has passed, reset maximum recorded wind gust
    elif time_now.date() > datetime.fromtimestamp(max_gust[3], Tz).date():
        max_gust = [wind_gust[0], 'mps', wind_gust[0], time.time()]

    # Else if current gust speed is greater than maximum recorded gust speed,
    # update maximum gust speed
    elif wind_gust[0] > max_gust[2]:
        max_gust = [wind_gust[0], 'mps', wind_gust[0], time.time()]

    # Else maximum gust speed is unchanged, return existing value
    else:
        max_gust = [max_gust[2], 'mps', max_gust[2], time.time()]

    # Return maximum wind gust
    return max_gust


def cardinal_wind_dir(wind_dir, wind_spd=[1, 'mps']):

    """ Defines the cardinal wind direction from the current wind direction in
        degrees. Sets the wind direction as "Calm" if current wind speed is zero

    INPUTS:
        wind_dir             Wind direction                     [degrees]
        wind_spd             Wind speed                             [m/s]

    OUTPUT:
        cardinal_wind        Cardinal wind direction
    """

    # Return None if required variables are missing
    error_output = [wind_dir[0], wind_dir[1], '-', '-']
    if wind_dir[0] is None and wind_spd[0] != 0.0:
        Logger.warning(f'cardWindDir: {system().log_time()} - wind_dir is None')
        return error_output
    elif wind_spd[0] is None:
        Logger.warning(f'cardWindDir: {system().log_time()} - wind_spd is None')
        return error_output

    # Define all possible cardinal wind directions and descriptions
    direction   = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N']
    description = ['Due North', 'North NE', 'North East', 'East NE', 'Due East', 'East SE', 'South East', 'South SE',
                   'Due South', 'South SW', 'South West', 'West SW', 'Due West', 'West NW', 'North West', 'North NW',
                   'Due North']

    # Define actual cardinal wind direction and description based on current
    # wind direction in degrees
    if wind_spd[0] == 0:
        direction = 'Calm'
        description = '[color=9aba2fff]Calm[/color]'
        cardinal_wind = [wind_dir[0], wind_dir[1], direction, description]
    else:
        idx = int(round(wind_dir[0] / 22.5))
        direction = direction[idx]
        description = description[idx].split()[0] + ' [color=9aba2fff]' + description[idx].split()[1] + '[/color]'
        cardinal_wind = [wind_dir[0], wind_dir[1], direction, description]

    # Return cardinal wind direction and description
    return cardinal_wind


def beaufort_scale(wind_spd):

    """ Defines the Beaufort scale value from the current wind speed

    INPUTS:
        wind_spd            Wind speed                             [m/s]

    OUTPUT:
        scale               Beaufort Scale, description, and icon
    """

    # Return None if required variables are missing
    error_output = wind_spd + ['-', '-', '-']
    if wind_spd[0] is None:
        Logger.warning(f'beauf_Scale: {system().log_time()} - wind_spd is None')
        return error_output

    # Define Beaufort scale cutoffs and Force numbers
    cutoffs = [0.5, 1.5, 3.3, 5.5, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6]
    force   = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    description = ['Calm Conditions', 'Light Air',         'Light Breeze',  'Gentle Breeze',
                   'Moderate Breeze', 'Fresh Breeze',      'Strong Breeze', 'Near Gale Force',
                   'Gale Force',      'Severe Gale Force', 'Storm Force',   'Violent Storm',
                   'Hurricane Force']

    # Define Beaufort Scale wind speed, description, and icon
    Ind = bisect.bisect(cutoffs, wind_spd[0])
    beaufort = [float(force[Ind]), str(force[Ind]), description[Ind]]

    # Return Beaufort Scale speed, description, and icon
    return wind_spd + beaufort


def uv_index(uv_level):

    """ Defines the UV index from the current UV level

    INPUTS:
        uv_level          UV level

    OUTPUT:
        index             UV index
    """

    # Return None if required variables are missing
    error_output = [None, 'index', '-', '#646464']
    if uv_level[0] is None:
        Logger.warning(f'uv_index: {system().log_time()} - uv_level is None')
        return error_output

    # Define UV Index cutoffs and level descriptions
    cutoffs = [0, 3, 6, 8, 11]
    level   = ['None', 'Low', 'Moderate', 'High', 'Very High', 'Extreme']

    # Define UV index colours
    grey   = '#646464'
    green  = '#558B2F'
    yellow = '#F9A825'
    orange = '#EF6C00'
    red    = '#B71C1C'
    violet = '#6A1B9A'
    Color  = [grey, green, yellow, orange, red, violet]

    # Set the UV index
    if uv_level[0] > 0:
        Ind = bisect.bisect(cutoffs, round(uv_level[0], 1))
    else:
        Ind = 0
    index = [round(uv_level[0], 1), 'index', level[Ind], Color[Ind]]

    # Return UV index and icon
    return index


def peak_sun_hours(radiation, peak_sun, device, api_data, config):

    """ Calculate peak sun hours since midnight and daily solar potential

    INPUTS:
        Radiation           Solar radiation                        [W/m^2]
        peak_sun            Peak sun hours since midnight          [hours]
        device              Device ID
        api_data            WeatherFlow REST API data
        config              Station configuration

    OUTPUT:
        peak_sun            Peak sun hours since midnight and solar potential
    """

    # Return None if required variables are missing
    error_output = [None, 'hrs', '-']
    if radiation[0] is None:
        Logger.warning(f'peak_sun: {system().log_time()} - radiation is None')
        return error_output

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    time_now = datetime.now(pytz.utc).astimezone(Tz)

    # Calculate time of sunrise and sunset or use existing values
    if peak_sun[0] is None or time_now > datetime.fromtimestamp(peak_sun[5], Tz):
        observer          = ephem.Observer()
        observer.pressure = 0
        observer.lat      = str(config['Station']['Latitude'])
        observer.lon      = str(config['Station']['Longitude'])
        observer.horizon  = '-0:34'
        sunrise           = observer.next_rising(ephem.Sun()).datetime().timestamp()
        sunset            = observer.next_setting(ephem.Sun()).datetime().timestamp()
    else:
        sunrise           = peak_sun[4]
        sunset            = peak_sun[5]

    # Define index of radiation in websocket packets
    if str(device) in [config['Station']['SkyID'], config['Station']['SkySN']]:
        index_bucket_a = 10
    elif str(device) in [config['Station']['TempestID'], config['Station']['TempestSN']]:
        index_bucket_a = 11

    # If console is initialising and REST API services are enabled, download all
    # data for current day using Weatherflow API and calculate Peak Sun Hours
    if int(config['System']['rest_api']) and peak_sun[0] is None:
        if ('today' in api_data[device]
                and weatherflow_api.verify_response(api_data[device]['today'], 'obs')):
            data_today = api_data[device]['today'].json()['obs']
            radiation = [item[index_bucket_a] for item in data_today if item[index_bucket_a] is not None]
            try:
                watt_hrs = sum([item * (1 / 60) for item in radiation])
                peak_sun = [watt_hrs / 1000, 'hrs', watt_hrs, sunrise, sunset, time.time()]
            except Exception as error:
                Logger.warning(f'peak_sun: {system().log_time()} - {error}')
                return error_output
        else:
            return error_output

    # If console is initialising and REST API services are not enabled,
    # calculate current Peak Sun Hours
    elif not int(config['System']['rest_api']) and peak_sun[0] is None:
        watt_hrs = radiation[0] * (1 / 60)
        peak_sun = [watt_hrs / 1000, 'hrs', watt_hrs, sunrise, sunset, time.time()]

    # Else if midnight has passed, reset Peak Sun Hours
    elif time_now.date() > datetime.fromtimestamp(peak_sun[6], Tz).date():
        watt_hrs = radiation[0] * (1 / 60)
        peak_sun = [watt_hrs / 1000, 'hrs', watt_hrs, sunrise, sunset, time.time()]

    # Else calculate current Peak Sun Hours
    else:
        watt_hrs = peak_sun[3] + radiation[0] * (1 / 60)
        peak_sun = [watt_hrs / 1000, 'hrs', watt_hrs, sunrise, sunset, time.time()]

    # Calculate proportion of daylight hours that have passed
    if datetime.fromtimestamp(sunrise, Tz) <= time_now <= datetime.fromtimestamp(sunset, Tz):
        daylight_factor = (time.time() - sunrise) / (sunset - sunrise)
    else:
        daylight_factor = 1

    # Define daily solar potential
    if peak_sun[0] / daylight_factor == 0:
        peak_sun.insert(2, '[color=#646464ff]None[/color]')
    elif peak_sun[0] / daylight_factor < 2:
        peak_sun.insert(2, '[color=#4575b4ff]Limited[/color]')
    elif peak_sun[0] / daylight_factor < 4:
        peak_sun.insert(2, '[color=#fee090ff]Moderate[/color]')
    elif peak_sun[0] / daylight_factor < 6:
        peak_sun.insert(2, '[color=#f46d43ff]Good[/color]')
    else:
        peak_sun.insert(2, '[color=#d73027ff]Excellent[/color]')

    # Return Peak Sun Hours
    return peak_sun
