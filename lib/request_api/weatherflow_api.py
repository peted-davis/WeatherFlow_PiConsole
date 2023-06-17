""" Returns WeatherFlow API requests required by the Raspberry Pi Python console
for WeatherFlow Tempest and Smart Home Weather stations.
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

# Import required libray modules
from lib.system  import system

# Import required Kivy modules
from kivy.logger import Logger

# Import required system modules
from datetime    import datetime, timedelta
import requests
import pytz


def verify_response(Response, Field):

    """ Verifies the validity of the API response response

    INPUTS:
        Response        Response from API request
        Field           Field in API that is required to confirm validity

    OUTPUT:
        Flag            True or False flag confirming validity of response

    """
    if Response is None:
        return False
    if not Response.ok:
        return False
    try:
        Response.json()
    except ValueError:
        return False
    else:
        Response = Response.json()
        if isinstance(Response, dict):
            if 'SUCCESS' in Response['status']['status_message'] and Field in Response and Response[Field] is not None:
                return True
            else:
                return False
        else:
            return False


def last_6h(Device, endTime, Config):

    """ API Request for last six hours of data from a WeatherFlow Smart Home
    Weather Station device

    INPUTS:
        Device              Device ID
        endTime             End time of six hour window as a UNIX timestamp
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Calculate timestamp three hours past
    startTime = endTime - int(3600 * 6)

    # Download WeatherFlow data for last three hours
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=a&time_start={}&time_end={}&token={}'
    URL = Template.format(Device, startTime, endTime, Config['Keys']['WeatherFlow'])
    try:
        api_data = requests.get(URL, timeout=int(Config['System']['Timeout']))
    except Exception:
        api_data = None

    # Verify response
    if Config['Keys']['WeatherFlow']:
      if api_data is None or not verify_response(api_data, 'obs'):
          Logger.warning(f'request_api: {system().log_time()} - last_6h call failed')

    # Return observations from the last six hours
    return api_data


def last_24h(Device, endTime, Config):

    """ API Request for last twenty fouts hours of data from a WeatherFlow Smart
    Home Weather Station device

    INPUTS:
        Device              Device ID
        endTime             End time of 24 hour window as a UNIX timestamp
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Calculate timestamp 24 hours past
    startTime = endTime - int(3600 * 24)

    # Download WeatherFlow data for last three hours
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=a&time_start={}&time_end={}&token={}'
    URL = Template.format(Device, startTime, endTime, Config['Keys']['WeatherFlow'])
    try:
        apiData = requests.get(URL, timeout=int(Config['System']['Timeout']))
    except Exception:
        apiData = None

    # Verify response
    if Config['Keys']['WeatherFlow']:
        if apiData is None or not verify_response(apiData, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - last_24h call failed')

    # Return observations from the last twenty-four hours
    return apiData


def today(Device, Config):

    """ API Request for data from the current calendar day in the station
        timezone from a WeatherFlow Smart Home Weather Station device

    INPUTS:
        Device              Device ID
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Convert midnight today in Station timezone to midnight today in UTC.
    # Convert UTC time into UNIX timestamp.
    startTime = int(Tz.localize(datetime(Now.year, Now.month, Now.day)).timestamp())

    # Convert current time in Station timezone to current time in UTC.
    # Convert UTC time into UNIX timestamp
    endTime = int(Now.timestamp())

    # Download WeatherFlow data
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=a&time_start={}&time_end={}&token={}'
    URL = Template.format(Device, startTime, endTime, Config['Keys']['WeatherFlow'])
    try:
        apiData = requests.get(URL, timeout=int(Config['System']['Timeout']))
    except Exception:
        apiData = None

    # Verify response
    if Config['Keys']['WeatherFlow']:
        if apiData is None or not verify_response(apiData, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - Today call failed')

    # Return observations from today
    return apiData


def yesterday(Device, Config):

    """ API Request for data from yesterday in the station timezone from a
    WeatherFlow Smart Home Weather Station device

    INPUTS:
        Device              Device ID
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Convert midnight yesterday in Station timezone to midnight yesterday in
    # UTC. Convert UTC time into UNIX timestamp
    Yesterday = Tz.localize(datetime(Now.year, Now.month, Now.day)) - timedelta(days=1)
    startTime = int(Yesterday.timestamp())

    # Convert midnight today in Station timezone to midnight yesterday in UTC.
    # Convert UTC time into UNIX timestamp
    Today = Tz.localize(datetime(Now.year, Now.month, Now.day))
    endTime = int(Today.timestamp()) - 1

    # Download WeatherFlow data
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=a&time_start={}&time_end={}&token={}'
    URL = Template.format(Device, startTime, endTime, Config['Keys']['WeatherFlow'])
    try:
        apiData = requests.get(URL, timeout=int(Config['System']['Timeout']))
    except Exception:
        apiData = None

    # Verify response
    if Config['Keys']['WeatherFlow']:
        if apiData is None or not verify_response(apiData, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - Yesterday call failed')

    # Return observations from yesterday
    return apiData


def month(Device, Config):

    """ API Request for data from the last month in the station timezone from a
        WeatherFlow Smart Home Weather Station device

    INPUTS:
        Device              Device ID
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Convert start of current month in Station timezone to start of
    # current month in UTC. Convert UTC time into UNIX timestamp
    monthStart = Tz.localize(datetime(Now.year, Now.month, 1))
    startTime  = int(monthStart.timestamp())

    # If today is not the first day of the month, convert midnight yesterday
    # in Station timezone to midnight yesterday in UTC. Convert UTC time into
    # UNIX timestamp.
    if Now.day != 1:
        Yesterday = Tz.localize(datetime(Now.year, Now.month, Now.day)) - timedelta(days=1)
        endTime = int(Yesterday.timestamp()) - 1

    # If today is the first day of the month, set the endTime to one second
    # more than the startTime
    else:
        endTime = startTime + 1

    # Download WeatherFlow data
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=e&time_start={}&time_end={}&token={}'
    URL = Template.format(Device, startTime, endTime, Config['Keys']['WeatherFlow'])
    try:
        apiData = requests.get(URL, timeout=int(Config['System']['Timeout']))
    except Exception:
        apiData = None

    # Verify response
    if Config['Keys']['WeatherFlow']:
        if apiData is None or not verify_response(apiData, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - Month call failed')

    # Return observations from the last month
    return apiData


def year(Device, Config):

    """ API Request for data from the last year in the station timezone from a
        WeatherFlow Smart Home Weather Station device

    INPUTS:
        Device              Device type (AIR/SKY/TEMPEST)
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Convert start of current year in Station timezone to start of current year
    # in UTC. Convert UTC time into time timestamp
    yearStart = Tz.localize(datetime(Now.year, 1, 1))
    startTime = int(yearStart.timestamp())

    # # If today is not the first day of the year, convert midnight yesterday
    # in Station timezone to midnight yesterday in UTC. Convert UTC time into
    # UNIX timestamp.
    if Now.timetuple().tm_yday != 1:
        yearEnd = Tz.localize(datetime(Now.year, Now.month, Now.day)) - timedelta(days=1)
        endTime = int(yearEnd.timestamp()) - 1

    # If today is the first day of the month, set the endTime to one second
    # more than the startTime
    else:
        endTime = startTime + 1

    # Download WeatherFlow data
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?bucket=e&time_start={}&time_end={}&token={}'
    URL = Template.format(Device, startTime, endTime, Config['Keys']['WeatherFlow'])
    try:
        apiData = requests.get(URL, timeout=int(Config['System']['Timeout']))
    except Exception:
        apiData = None

    # Verify response
    if Config['Keys']['WeatherFlow']:
        if apiData is None or not verify_response(apiData, 'obs'):
            Logger.warning(f'request_api: {system().log_time()} - Year call failed')

    # Return observations from the last year
    return apiData


def station_meta_data(Station, Config):

    """ API Request for station meta data from a WeatherFlow Smart Home Weather
    Station

    INPUTS:
        Station              Device type (AIR/SKY/TEMPEST)
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Download station meta data
    Template = 'https://swd.weatherflow.com/swd/rest/stations/{}?token={}'
    URL = Template.format(Station, Config['Keys']['WeatherFlow'])
    try:
        apiData = requests.get(URL, timeout=int(Config['System']['Timeout']))
    except Exception:
        apiData = None

    # Verify response
    if apiData is None or not verify_response(apiData, 'obs'):
        Logger.warning(f'request_api: {system().log_time()} - stationMetaData call failed')

    # Return station meta data
    return apiData


def forecast(Config):

    """ API Request for a weather forecast from WeatherFlow's BetterForecast API

    INPUTS:
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest WeatherFlow forecast
    """

    # Download WeatherFlow forecast
    Template = 'https://swd.weatherflow.com/swd/rest/better_forecast?token={}&station_id={}&lat={}&lon={}'
    URL = Template.format(Config['Keys']['WeatherFlow'], Config['Station']['StationID'], Config['Station']['Latitude'], Config['Station']['Longitude'])
    print(URL)
    try:
        apiData = requests.get(URL, timeout=int(Config['System']['Timeout']))
    except Exception:
        apiData = None

    # Verify response
    if apiData is None or not verify_response(apiData, 'forecast'):
        Logger.warning(f'request_api: {system().log_time()} - Forecast call failed')

    # Return WeatherFlow forecast data
    return apiData
