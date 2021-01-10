""" Returns Github API requests required by the Raspberry Pi Python console
for WeatherFlow Tempest and Smart Home Weather stations.
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

# Import required modules
import requests

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
            if Field in Response and Response[Field] is not None:
                return True
            else:
                return False
        else:
            return False

def version(Config):

    """ API Request to retrieve the latest PiConsole version info from Github

    INPUTS:
        Device              Device type (AIR/SKY/TEMPEST)
        endTime             End time of three hour window as a UNIX timestamp
        Config              Station configuration

    OUTPUT:
        Response            API response containing latest three-hourly forecast
    """

    # Get latest version info from Github
    header = {'Accept': 'application/vnd.github.v3+json'}
    Template = 'https://api.github.com/repos/{}/{}/releases/latest'
    URL = Template.format('peted-davis','WeatherFlow_PiConsole')
    try:
        Data = requests.get(URL,headers=header,timeout=int(Config['System']['Timeout']))
    except:
        Data = None

    # Return latest version info from Github
    return Data
