""" Contains system functions required by the Raspberry Pi Python console for 
WeatherFlow Tempest and Smart Home Weather stations. 
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

# Import required library modules
from lib import requestAPI

# Import required Python modules
from kivy.clock import Clock
from packaging  import version
from functools  import partial
from datetime   import datetime, date, time, timedelta
import pytz

def checkVersion(verData,Config,updateNotif,*largs):

    """ Checks current version of the PiConsole against the latest available
    version on Github
	
	INPUTS: 
        verData                 Dictionary holding version information
		Config                  Station configuration
        updateNotif             Instance of the updateNotif widget
		
	OUTPUT: 
        verData                 Dictionary holding version information
	"""

    # Get version information from Github API
    Data = requestAPI.github.version(Config)

    # Get current time in station time zone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)
    
    # Extract version number from API response
    if requestAPI.github.verifyResponse(Data,'tag_name'):
        verData['Latest'] = Data.json()['tag_name']
    else:
        Next = Tz.localize(datetime(Now.year,Now.month,Now.day,0,0,0)+timedelta(days=1))
        Clock.schedule_once(partial(checkVersion,verData,Config,updateNotif),(Next-Now).total_seconds())
        return verData
    
    # If current and latest version numbers do not match, open update
    # notification
    if version.parse(Config['System']['Version']) < version.parse(verData['Latest']):

        # Check if update notification is already open. Close if required
        if 'updateNotif' in verData:
            verData['updateNotif'].dismiss()

        # Open update notification
        verData['updateNotif'] = updateNotif()
        verData['updateNotif'].open()

    # Schedule next Version Check
    Next = Tz.localize(datetime(Now.year,Now.month,Now.day,0,0,0)+timedelta(days=1))
    Clock.schedule_once(partial(checkVersion,verData,Config,updateNotif),(Next-Now).total_seconds())
    
    # Return system variables
    return verData
    
