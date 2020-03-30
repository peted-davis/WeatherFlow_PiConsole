""" Returns the UK MetOffice or DarkSky forecast variables required by the 
Raspberry Pi Python console for Weather Flow Smart Home Weather Stations. 
Copyright (C) 2018-2020 Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

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

    """ Download the weather forecast from either the UK MetOffice or
    DarkSky
	
	INPUTS: 
		metData				Dictionary holding weather forecast data
		Config              Station configuration
		
	OUTPUT: 
        metData             Dictionary holding weather forecast data
	"""

    # If Station is located in Great Britain, download latest
    # MetOffice three-hourly forecast
    if Config['Station']['Country'] == 'GB':
    
        # Download latest three-hourly forecast
        Data = requestAPI.forecast.metOffice(Config)
        
        # Verify API response and extract forecast
        if requestAPI.forecast.verifyResponse(Data,'SiteRep'):
            metData['Dict'] = Data.json()
        else:
            Clock.schedule_once(lambda dt: Download(metData,Config),600)
            if not 'Dict' in metData:
                metData['Dict'] = {}  
        ExtractMetOffice(metData,Config)

    # If station is located outside of Great Britain, download the latest
    # DarkSky hourly forecast
    else:
    
        # Download latest three-hourly forecast
        Data = requestAPI.forecast.darkSky(Config)
    
        # Verify API response and extract forecast
        if requestAPI.forecast.verifyResponse(Data,'hourly'):
            metData['Dict'] = Data.json()
        else:
            Clock.schedule_once(lambda dt: Download(metData,Config),600)
            if not 'Dict' in metData:
                metData['Dict'] = {}  
        ExtractDarkSky(metData,Config)
    
    # Return metData dictionary
    return metData

def ExtractMetOffice(metData,Config):

    """ Parse the weather forecast from the UK MetOffice
	
	INPUTS: 
		metData				Dictionary holding weather forecast data
		Config              Station configuration
		
	OUTPUT: 
        metData             Dictionary holding weather forecast data
	"""

    # Get current time in station time zone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Extract all forecast data from MetOffice JSON file. If  forecast is
    # unavailable, set forecast variables to blank and indicate to user that
    # forecast is unavailable
    try:
        Issued  = str(metData['Dict']['SiteRep']['DV']['dataDate'][11:-4])
        metDict = (metData['Dict']['SiteRep']['DV']['Location']['Period'])       
    except KeyError:
        metData['Time']    = Now
        metData['Temp']    = '--'
        metData['WindDir'] = '--'
        metData['WindSpd'] = '--'
        metData['Weather'] = 'ForecastUnavailable'
        metData['Precip']  = '--'
        metData['Valid']   = '--'

        # Attempt to download forecast again in 10 minutes and return
        # metData dictionary
        Clock.schedule_once(lambda dt: Download(metData,Config),600)       
        return metData

    # Extract date of all available forecasts, and retrieve forecast for
    # today
    Dates = list(item['value'] for item in metDict)
    metDict = metDict[Dates.index(Now.strftime('%Y-%m-%dZ'))]['Rep']

    # Extract 'valid from' time of all available three-hourly forecasts, and
    # retrieve forecast for the current three-hour period
    Times = list(int(item['$'])//60 for item in metDict)
    metDict = metDict[bisect.bisect(Times,Now.hour)-1]

    # Extract 'valid until' time for the retrieved forecast
    Valid = Times[bisect.bisect(Times,Now.hour)-1] + 3
    if Valid == 24:
        Valid = 0

    # Extract weather variables from MetOffice forecast
    Temp    = [float(metDict['T']),'c']
    WindSpd = [float(metDict['S'])/2.2369362920544,'mps']
    WindDir = [metDict['D'],'cardinal']
    Precip  = [metDict['Pp'],'%']
    Weather = metDict['W']

    # Convert forecast units as required
    Temp    = observation.Units(Temp,Config['Units']['Temp'])
    WindSpd = observation.Units(WindSpd,Config['Units']['Wind'])

    # Define and format labels
    metData['Time']    = Now
    metData['Issued']  = Issued
    metData['Valid']   = '{:02.0f}'.format(Valid) + ':00'
    metData['Temp']    = ['{:.1f}'.format(Temp[0]),Temp[1]]
    metData['WindDir'] = WindDir[0]
    metData['WindSpd'] = ['{:.0f}'.format(WindSpd[0]),WindSpd[1]]
    metData['Weather'] = Weather
    metData['Precip']  = Precip[0]
    
    # Return metData dictionary
    return metData

def ExtractDarkSky(metData,Config):

    """ Parse the weather forecast from DarkSky
	
	INPUTS: 
		metData				Dictionary holding weather forecast data
		Config              Station configuration
		
	OUTPUT: 
        metData             Dictionary holding weather forecast data
	"""

    # Get current time in station time zone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Extract all forecast data from DarkSky JSON file. If  forecast is
    # unavailable, set forecast variables to blank and indicate to user that
    # forecast is unavailable
    Tz = pytz.timezone(Config['Station']['Timezone'])
    try:
        metDict = (metData['Dict']['hourly']['data'])
    except KeyError:
        metData['Time']    = Now
        metData['Temp']    = '--'
        metData['WindDir'] = '--'
        metData['WindSpd'] = '--'
        metData['Weather'] = 'ForecastUnavailable'
        metData['Precip']  = '--'
        metData['Valid']   = '--'

        # Attempt to download forecast again in 10 minutes and return
        # metData dictionary
        Clock.schedule_once(lambda dt: Download(metData,Config),600)  
        return metData

    # Extract 'valid from' time of all available hourly forecasts, and
    # retrieve forecast for the current hourly period
    Times = list(item['time'] for item in metDict)
    metDict = metDict[bisect.bisect(Times,int(time.time()))-1]

    # Extract 'Issued' and 'Valid' times
    Issued = Times[0]
    Valid = Times[bisect.bisect(Times,int(time.time()))]
    Issued = datetime.fromtimestamp(Issued,pytz.utc).astimezone(Tz)
    Valid = datetime.fromtimestamp(Valid,pytz.utc).astimezone(Tz)

    # Extract weather variables from DarkSky forecast
    Temp    = [metDict['temperature'],'c']
    WindSpd = [metDict['windSpeed']/2.2369362920544,'mps']
    WindDir = [metDict['windBearing'],'degrees']
    Precip  = [metDict['precipProbability']*100,'%']
    Weather =  metDict['icon']

    # Convert forecast units as required
    Temp = observation.Units(Temp,Config['Units']['Temp'])
    WindSpd = observation.Units(WindSpd,Config['Units']['Wind'])

    # Define and format labels
    metData['Time']    = Now
    metData['Issued']  = datetime.strftime(Issued,'%H:%M')
    metData['Valid']   = datetime.strftime(Valid,'%H:%M')
    metData['Temp']    = ['{:.1f}'.format(Temp[0]),Temp[1]]
    metData['WindDir'] = derive.CardinalWindDirection(WindDir)[2]
    metData['WindSpd'] = ['{:.0f}'.format(WindSpd[0]),WindSpd[1]]
    metData['Precip']  = '{:.0f}'.format(Precip[0])

    # Define weather icon
    if Weather == 'clear-day':
        metData['Weather'] = '1'
    elif Weather == 'clear-night':
        metData['Weather'] = '0'
    elif Weather == 'rain':
        metData['Weather'] = '12'
    elif Weather == 'snow':
        metData['Weather'] = '27'
    elif Weather == 'sleet':
        metData['Weather'] = '18'
    elif Weather == 'wind':
        metData['Weather'] = 'wind'
    elif Weather == 'fog':
        metData['Weather'] = '6'
    elif Weather == 'cloudy':
        metData['Weather'] = '7'
    elif Weather == 'partly-cloudy-day':
        metData['Weather'] = '3'
    elif Weather == 'partly-cloudy-night':
        metData['Weather'] = '2'
    else:
        metData['Weather'] = 'ForecastUnavailable'
    
    # Return metData dictionary    
    return metData    