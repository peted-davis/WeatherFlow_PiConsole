""" Returns MetOffice/DarkSky API requests required by the Raspberry Pi Python 
console for Weather Flow Smart Home Weather Stations. Copyright (C) 2018-2019 
Peter Davis

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
from datetime   import datetime, date, time, timedelta
import requests
import pytz

def verifyResponse(Response,Field):

    """ Verifies the validity of the API response response 
	
	INPUTS: 
		Response			Response from API request
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
            if Field in Response and Response[Field] is not None:
                return True
            else:
                return False
        else:
            return False

def metOffice(Config):

    """ API Request for latest MetOffice three hourly forecasr
	
	INPUTS: 
		Config              Station configuration

	OUTPUT:
        Response            API response containing latest three-hourly forecast
	"""
    
    # Download latest MetOffice three-hourly forecast
    Template = 'http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/json/{}?res=3hourly&key={}'
    URL = Template.format(Config['Station']['MetOfficeID'],Config['Keys']['MetOffice'])
    try:
        Response = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Response = None

    # Return latest MetOffice three-hourly forecast
    return Response
       
def darkSky(Config):

    """ API Request for latest DarkSky hourly forecasr
	
	INPUTS: 
		Config              Station configuration

	OUTPUT:
        Response            API response containing latest hourly forecast
	"""
    
    # Download latest DarkSky hourly forecast
    Template = 'https://api.darksky.net/forecast/{}/{},{}?exclude=currently,minutely,alerts,flags&units=uk2'
    URL = Template.format(Config['Keys']['DarkSky'],Config['Station']['Latitude'],Config['Station']['Longitude'])
    try:
        Response = requests.get(URL,timeout=int(Config['System']['Timeout']))
    except:
        Response = None

    # Return latest DarkSky hourly forecast
    return Response