""" Returns WeatherFlow API requests required by the Raspberry Pi Python console
for WeatherFlow Tempest and Smart Home Weather stations.
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
from datetime   import datetime, date, time, timedelta
import requests
import pytz

def verifyResponse(Response,Field):

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
        if isinstance(Response,dict):
            if 'SUCCESS' in Response['status']['status_message'] and Field in Response and Response[Field] is not None:
                return True
            else:
                return False
        else:
            return False

def Last3h(Device,endTime,Config):

    """ API Request for last three hours of data from a WeatherFlow Smart Home
    Weather Station device

    INPUTS:
        Device              Device ID
        endTime             End time of three hour window as a UNIX timestamp
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Calculate timestamp three hours past
    startTime = endTime - int((3600*3+59))

    # Download WeatherFlow data for last three hours
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
    URL = Template.format(Device,startTime,endTime,Config['Keys']['WeatherFlow'])
    try:
        Data = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Data = None

    # Return observations from the last three hours
    return Data

def Last6h(Device,endTime,Config):

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
    startTime = endTime - int((3600*6+59))

    # Download WeatherFlow data for last three hours
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
    URL = Template.format(Device,startTime,endTime,Config['Keys']['WeatherFlow'])
    try:
        Data = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Data = None

    # Return observations from the last three hours
    return Data
    
def Last24h(Device,endTime,Config):

    """ API Request for last twenty fouts hours of data from a WeatherFlow Smart 
    Home Weather Station device

    INPUTS:
        Device              Device ID
        endTime             End time of six hour window as a UNIX timestamp
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Calculate timestamp three hours past
    startTime = endTime - int((3600*24))

    # Download WeatherFlow data for last three hours
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
    URL = Template.format(Device,startTime,endTime,Config['Keys']['WeatherFlow'])
    try:
        Data = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Data = None

    # Return observations from the last three hours
    return Data    

def Today(Device,Config):

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

    # Convert midnight today in Station timezone to midnight today in
    # UTC. Convert UTC time into UNIX timestamp.
    startTime = int(Tz.localize(datetime(Now.year,Now.month,Now.day)).timestamp())

    # Convert current time in Station timezone to current time in UTC.
    # Convert UTC time into UNIX timestamp
    endTime = int(Now.timestamp())

    # Download WeatherFlow data
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
    URL = Template.format(Device,startTime,endTime,Config['Keys']['WeatherFlow'])
    try:
        Data = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Data = None

    # Return observations from today
    return Data

def Yesterday(Device,Config):

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

    # Convert midnight yesterday in Station timezone to midnight
    # yesterday in UTC. Convert UTC time into UNIX timestamp
    Yesterday = Tz.localize(datetime(Now.year,Now.month,Now.day)) - timedelta(days=1)
    startTime = int(Yesterday.timestamp())

    # Convert midnight today in Station timezone to midnight
    # yesterday in UTC. Convert UTC time into UNIX timestamp
    Today = Tz.localize(datetime(Now.year,Now.month,Now.day))
    endTime = int(Today.timestamp())

    # Download WeatherFlow data
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
    URL = Template.format(Device,startTime,endTime,Config['Keys']['WeatherFlow'])
    try:
        Data = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Data = None

    # Return observations from yesterday
    return Data

def Month(Device,Config):

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
    startTime = int(Tz.localize(datetime(Now.year,Now.month,1)).timestamp())

    # Convert midnight today in Station timezone to midnight today in
    # UTC. Convert UTC time into UNIX timestamp.
    endTime = int(Tz.localize(datetime(Now.year,Now.month,Now.day)).timestamp())

    # Download WeatherFlow data
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
    URL = Template.format(Device,startTime,endTime,Config['Keys']['WeatherFlow'])
    try:
        Data = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Data = None

    # Return observations from the last month
    return Data

def Year(Device,Config):

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
    startTime = int(Tz.localize(datetime(Now.year,1,1)).timestamp())

    # Convert midnight today in Station timezone to midnight today in
    # UTC. Convert UTC time into UNIX timestamp.
    endTime = int(Tz.localize(datetime(Now.year,Now.month,Now.day)).timestamp())

    # Download WeatherFlow data
    Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
    URL = Template.format(Device,startTime,endTime,Config['Keys']['WeatherFlow'])
    try:
        Data = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Data = None

    # Return observations from the last year
    return Data
    
def stationMetaData(Station,Config):

    """ API Request for station meta data from a WeatherFlow Smart Home Weather 
    Station

    INPUTS:
        Device              Device type (AIR/SKY/TEMPEST)
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Download station meta data
    Template = 'https://swd.weatherflow.com/swd/rest/stations/{}?api_key={}'
    URL = Template.format(Station,Config['Keys']['WeatherFlow'])
    try:
        Data = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Data = None
        
    # Return station meta data
    return Data
