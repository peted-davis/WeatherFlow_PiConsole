""" Contains system functions required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2022 Peter Davis

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

    # Define time and date format based on user settings
    app = App.get_running_app
    if 'Display' in app().config:
        if 'TimeFormat' in app().config['Display'] and 'DateFormat' in app().config['Display']:
            if app().config['Display']['TimeFormat'] == '12 hr':
                if app().config['System']['Hardware'] == 'Other':
                    TimeFormat = '%#I:%M:%S %p'
                else:
                    TimeFormat = '%-I:%M:%S %p'
            else:
                TimeFormat = '%H:%M:%S'
            if app().config['Display']['DateFormat']  == 'Mon, Jan 01 0000':
                DateFormat = '%a, %b %d %Y'
            elif app().config['Display']['DateFormat'] == 'Monday, 01 Jan 0000':
                DateFormat = '%A, %d %b %Y'
            elif app().config['Display']['DateFormat'] == 'Monday, Jan 01 0000':
                DateFormat = '%A, %b %d %Y'
            else:
                DateFormat = '%a, %d %b %Y'

            # Get station time zone
            Tz = pytz.timezone(app().config['Station']['Timezone'])

            # Format realtime Clock
            app().CurrentConditions.System['Time'] = datetime.fromtimestamp(time.time(), Tz).strftime(TimeFormat)
            app().CurrentConditions.System['Date'] = datetime.fromtimestamp(time.time(), Tz).strftime(DateFormat)


def checkVersion(dt):

    """ Checks current version of the PiConsole against the latest available
    version on Github
    """

    # Get current time in station time zone
    app = App.get_running_app
    Tz = pytz.timezone(app().config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Get version information from Github API
    Data = requestAPI.github.version(app().config)

    # Extract version number from API response
    if requestAPI.github.verifyResponse(Data, 'tag_name'):
        latest_ver = Data.json()['tag_name']
    else:
        Next = Tz.localize(datetime(Now.year, Now.month, Now.day) + timedelta(days=1))
        Clock.schedule_once(checkVersion, (Next - Now).total_seconds())
        return

    # If current and latest version numbers do not match, open update
    # notification
    if version.parse(app().config['System']['Version']) < version.parse(latest_ver):

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

    Tz = pytz.timezone(App.get_running_app().config['Station']['Timezone'])
    return datetime.fromtimestamp(time.time(), Tz).strftime('%Y-%m-%d %H:%M:%S')
