""" Returns WeatherFlow API requests required by the Raspberry Pi Python console
for WeatherFlow Tempest and Smart Home Weather stations.
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

# Import required libray modules
from lib.system  import system

# Import required Kivy modules
from kivy.logger import Logger

# Import required system modules
from datetime    import datetime, timedelta
import requests
import pytz


def verify_response(api_data, field):

    """ Verifies the validity of the API response response

    INPUTS:
        api_data        api_data from API request
        field           Field in API that is required to confirm validity

    OUTPUT:
        flag            True or False flag confirming validity of response

    """
    if api_data is None:
        return False
    if not api_data.ok:
        return False
    try:
        api_data.json()
    except ValueError:
        return False
    else:
        api_data = api_data.json()
        if isinstance(api_data, dict):
            if 'SUCCESS' in api_data['status']['status_message'] and field in api_data and api_data[field] is not None:
                return True
            else:
                return False
        else:
            return False


def statistics(station, config):
    import json
    url_template = 'https://swd.weatherflow.com/swd/rest/stats/station/{}?token={}'
    URL = url_template.format(station, 
                              config['Keys']['WeatherFlow'])
    try:
        api_data = requests.get(URL, timeout=int(config['System']['Timeout']))
    except Exception:
        api_data = None

    return api_data

def last_6h(device, end_time, config):

    """ API Request for last six hours of data from a WeatherFlow Smart Home
    Weather Station device

    INPUTS:
        device              Device ID
        end_time            End time of six hour window as a UNIX timestamp
        config              Station configuration

    OUTPUT:
        api_data            API response containing latest three-hourly forecast
    """

    # Calculate timestamp three hours past
    start_time = end_time - int(3600 * 6)

    # Download WeatherFlow data for last three hours
    url_template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=a&time_start={}&time_end={}&token={}'
    URL = url_template.format(device, 
                              start_time, 
                              end_time, 
                              config['Keys']['WeatherFlow'])
    try:
        api_data = requests.get(URL, timeout=int(config['System']['Timeout']))
    except Exception:
        api_data = None

    # Verify response
    if config['Keys']['WeatherFlow']:
      if api_data is None or not verify_response(api_data, 'obs'):
          Logger.warning(f'request_api: {system().log_time()} - last_6h call failed')

    # Return observations from the last six hours
    return api_data


def last_24h(device, end_time, config):

    """ API Request for last twenty fouts hours of data from a WeatherFlow Smart
    Home Weather Station device

    INPUTS:
        device              Device ID
        end_time            End time of 24 hour window as a UNIX timestamp
        config              Station configuration

    OUTPUT:
        api_data            API response containing latest three-hourly forecast
    """

    # Calculate timestamp 24 hours past
    start_time = end_time - int(3600 * 24)

    # Download WeatherFlow data for last three hours
    url_template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=a&time_start={}&time_end={}&token={}'
    URL = url_template.format(device, 
                              start_time, 
                              end_time, 
                              config['Keys']['WeatherFlow'])
    try:
        api_data = requests.get(URL, timeout=int(config['System']['Timeout']))
    except Exception:
        api_data = None

    # Verify response
    if config['Keys']['WeatherFlow']:
        if api_data is None or not verify_response(api_data, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - last_24h call failed')

    # Return observations from the last twenty-four hours
    return api_data


def today(device, config):

    """ API Request for data from the current calendar day in the station
        timezone from a WeatherFlow Smart Home Weather Station device

    INPUTS:
        device              Device ID
        config              Station configuration

    OUTPUT:
        api_data            API response containing latest three-hourly forecast
    """

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    now = datetime.now(pytz.utc).astimezone(Tz)

    # Convert midnight today in Station timezone to midnight today in UTC.
    # Convert UTC time into UNIX timestamp.
    start_time = int(Tz.localize(datetime(now.year, now.month, now.day)).timestamp())

    # Convert current time in Station timezone to current time in UTC.
    # Convert UTC time into UNIX timestamp
    end_time = int(now.timestamp())

    # Download WeatherFlow data
    url_template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=a&time_start={}&time_end={}&token={}'
    URL = url_template.format(device, 
                              start_time, 
                              end_time, 
                              config['Keys']['WeatherFlow'])
    try:
        api_data = requests.get(URL, timeout=int(config['System']['Timeout']))
    except Exception:
        api_data = None

    # Verify response
    if config['Keys']['WeatherFlow']:
        if api_data is None or not verify_response(api_data, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - Today call failed')

    # Return observations from today
    return api_data


def yesterday(device, config):

    """ API Request for data from yesterday in the station timezone from a
    WeatherFlow Smart Home Weather Station device

    INPUTS:
        device              Device ID
        config              Station configuration

    OUTPUT:
        api_data            API response containing latest three-hourly forecast
    """

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    now = datetime.now(pytz.utc).astimezone(Tz)

    # Convert midnight yesterday in Station timezone to midnight yesterday in
    # UTC. Convert UTC time into UNIX timestamp
    yesterday = Tz.localize(datetime(now.year, now.month, now.day)) - timedelta(days=1)
    start_time = int(yesterday.timestamp())

    # Convert midnight today in Station timezone to midnight yesterday in UTC.
    # Convert UTC time into UNIX timestamp
    today = Tz.localize(datetime(now.year, now.month, now.day))
    end_time = int(today.timestamp()) - 1

    # Download WeatherFlow data
    url_template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=a&time_start={}&time_end={}&token={}'
    URL = url_template.format(device, 
                              start_time, 
                              end_time, 
                              config['Keys']['WeatherFlow'])
    try:
        api_data = requests.get(URL, timeout=int(config['System']['Timeout']))
    except Exception:
        api_data = None

    # Verify response
    if config['Keys']['WeatherFlow']:
        if api_data is None or not verify_response(api_data, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - Yesterday call failed')

    # Return observations from yesterday
    return api_data


def month(device, config):

    """ API Request for data from the last month in the station timezone from a
        WeatherFlow Smart Home Weather Station device

    INPUTS:
        device              Device ID
        config              Station configuration

    OUTPUT:
        api_data            API response containing latest three-hourly forecast
    """

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    now = datetime.now(pytz.utc).astimezone(Tz)

    # Convert start of current month in Station timezone to start of
    # current month in UTC. Convert UTC time into UNIX timestamp
    month_start = Tz.localize(datetime(now.year, now.month, 1))
    start_time  = int(month_start.timestamp())

    # If today is not the first day of the month, convert midnight yesterday
    # in Station timezone to midnight yesterday in UTC. Convert UTC time into
    # UNIX timestamp.
    if now.day != 1:
        yesterday = Tz.localize(datetime(now.year, now.month, now.day)) - timedelta(days=1)
        end_time = int(yesterday.timestamp()) - 1

    # If today is the first day of the month, set the end_time to one second
    # more than the start_time
    else:
        end_time = start_time + 1

    # Download WeatherFlow data
    url_template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=e&time_start={}&time_end={}&token={}'
    URL = url_template.format(device, 
                              start_time, 
                              end_time, 
                              config['Keys']['WeatherFlow'])
    try:
        api_data = requests.get(URL, timeout=int(config['System']['Timeout']))
    except Exception:
        api_data = None

    # Verify response
    if config['Keys']['WeatherFlow']:
        if api_data is None or not verify_response(api_data, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - Month call failed')

    # Return observations from the last month
    return api_data


def year(device, config):

    """ API Request for data from the last year in the station timezone from a
        WeatherFlow Smart Home Weather Station device

    INPUTS:
        device              Device ID
        config              Station configuration

    OUTPUT:
        api_data            API response containing latest three-hourly forecast
    """

    # Define current time in station timezone
    Tz = pytz.timezone(config['Station']['Timezone'])
    now = datetime.now(pytz.utc).astimezone(Tz)

    # Convert start of current year in Station timezone to start of current year
    # in UTC. Convert UTC time into time timestamp
    year_start = Tz.localize(datetime(now.year, 1, 1))
    start_time = int(year_start.timestamp())

    # # If today is not the first day of the year, convert midnight yesterday
    # in Station timezone to midnight yesterday in UTC. Convert UTC time into
    # UNIX timestamp.
    if now.timetuple().tm_yday != 1:
        year_end = Tz.localize(datetime(now.year, now.month, now.day)) - timedelta(days=1)
        end_time = int(year_end.timestamp()) - 1

    # If today is the first day of the month, set the end_time to one second
    # more than the start_time
    else:
        end_time = start_time + 1

    # Download WeatherFlow data
    url_template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=e&time_start={}&time_end={}&token={}'
    URL = url_template.format(device, 
                              start_time, 
                              end_time, 
                              config['Keys']['WeatherFlow'])
    try:
        api_data = requests.get(URL, timeout=int(config['System']['Timeout']))
    except Exception:
        api_data = None

    # Verify response
    if config['Keys']['WeatherFlow']:
        if api_data is None or not verify_response(api_data, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - Year call failed')

    # Return observations from the last year
    return api_data


def station_meta_data(station, config):

    """ API Request for station meta data from a WeatherFlow Smart Home Weather
    Station

    INPUTS:
        station             Station ID
        config              Station configuration

    OUTPUT:
        api_data            API response containing latest three-hourly forecast
    """

    # Download station meta data
    url_template = 'https://swd.weatherflow.com/swd/rest/stations/{}?token={}'
    URL = url_template.format(station, 
                              config['Keys']['WeatherFlow'])
    try:
        api_data = requests.get(URL, timeout=int(config['System']['Timeout']))
    except Exception:
        api_data = None

    # Verify response
    if api_data is None or not verify_response(api_data, 'obs'):
        Logger.warning(f'request_api: {system().log_time()} - stationMetaData call failed')

    # Return station meta data
    return api_data


def forecast(config):

    """ API Request for a weather forecast from WeatherFlow's BetterForecast API

    INPUTS:
        config              Station configuration

    OUTPUT:
        api_data            API response containing latest WeatherFlow forecast
    """

    # Download WeatherFlow forecast
    url_template = 'https://swd.weatherflow.com/swd/rest/better_forecast?token={}&station_id={}&lat={}&lon={}'
    URL = url_template.format(config['Keys']['WeatherFlow'], 
                              config['Station']['StationID'], 
                              config['Station']['Latitude'], 
                              config['Station']['Longitude'])
    print(URL)
    try:
        api_data = requests.get(URL, timeout=int(config['System']['Timeout']))
    except Exception:
        api_data = None

    # Verify response
    if api_data is None or not verify_response(api_data, 'forecast'):
        Logger.warning(f'request_api: {system().log_time()} - Forecast call failed')

    # Return WeatherFlow forecast data
    return api_data
