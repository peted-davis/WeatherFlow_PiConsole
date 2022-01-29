""" Contains system functions required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2021 Peter Davis

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

# Import required panels
from panels.update  import updateNotification

# Import required Kivy modules
from kivy.clock     import Clock
from kivy.app       import App

# Import required Python modules
from datetime       import datetime, timedelta
from packaging      import version
import time
import pytz


def realtimeClock(dt):

    """ Format Realtime clock and date in station timezone
    """

    # Extract app config and System dictionary
    Config = App.get_running_app().config
    System = App.get_running_app().CurrentConditions.System

    # Define time and date format based on user settings
    if 'Display' in Config:
        if 'TimeFormat' in Config['Display'] and 'DateFormat' in Config['Display']:
            if Config['Display']['TimeFormat'] == '12 hr':
                if Config['System']['Hardware'] == 'Other':
                    TimeFormat = '%#I:%M:%S %p'
                else:
                    TimeFormat = '%-I:%M:%S %p'
            else:
                TimeFormat = '%H:%M:%S'
            if Config['Display']['DateFormat']  == 'Mon, Jan 01 0000':
                DateFormat = '%a, %b %d %Y'
            elif Config['Display']['DateFormat'] == 'Monday, 01 Jan 0000':
                DateFormat = '%A, %d %b %Y'
            elif Config['Display']['DateFormat'] == 'Monday, Jan 01 0000':
                DateFormat = '%A, %b %d %Y'
            else:
                DateFormat = '%a, %d %b %Y'

            # Get station time zone
            Tz = pytz.timezone(Config['Station']['Timezone'])

            # Format realtime Clock
            System['Time'] = datetime.fromtimestamp(time.time(), Tz).strftime(TimeFormat)
            System['Date'] = datetime.fromtimestamp(time.time(), Tz).strftime(DateFormat)


def checkVersion(dt):

    """ Checks current version of the PiConsole against the latest available
    version on Github
    """

    # Get current time in station time zone
    config = App.get_running_app().config
    Tz = pytz.timezone(config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Get version information from Github API
    Data = requestAPI.github.version(config)

    # Extract version number from API response
    if requestAPI.github.verifyResponse(Data, 'tag_name'):
        latest_ver = Data.json()['tag_name']
    else:
        Next = Tz.localize(datetime(Now.year, Now.month, Now.day) + timedelta(days=1))
        Clock.schedule_once(checkVersion, (Next - Now).total_seconds())

    # If current and latest version numbers do not match, open update
    # notification
    if version.parse(config['System']['Version']) < version.parse(latest_ver):

        # Check if update notification is already open. Close if required
        try:
            App.get_running_app().updateNotification.dismiss()
        except AttributeError:
            pass

        # Open update notification
        updateNotification(latest_ver).open()

    # Schedule next Version Check
    Next = Tz.localize(datetime(Now.year, Now.month, Now.day) + timedelta(days=1))
    Clock.schedule_once(checkVersion, (Next - Now).total_seconds())


def logTime():

    """ Return current time in station timezone in correct format for console
        log file
    """

    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
