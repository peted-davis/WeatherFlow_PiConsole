""" Contains system functions required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2023 Peter Davis

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
from lib.request_api import github_api
from lib             import properties

# Import required panels
from panels.update  import update_notification

# Import required Kivy modules
from kivy.logger    import Logger
from kivy.clock     import Clock
from kivy.app       import App

# Import required Python modules
from datetime       import datetime, timedelta
from packaging      import version
import time
import pytz


# ==============================================================================
# system CLASS
# ==============================================================================
class system():

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.system_data = properties.System()
        self.app = App.get_running_app()

    def realtimeClock(self, dt):

        """ Format Realtime clock and date in station timezone
        """

        # Define time and date format based on user settings
        if 'Display' in self.app.config:
            if 'TimeFormat' in self.app.config['Display'] and 'DateFormat' in self.app.config['Display']:
                if self.app.config['Display']['TimeFormat'] == '12 hr':
                    if self.app.config['System']['Hardware'] == 'Other':
                        TimeFormat = '%#I:%M:%S %p'
                    else:
                        TimeFormat = '%-I:%M:%S %p'
                else:
                    TimeFormat = '%H:%M:%S'
                if self.app.config['Display']['DateFormat']  == 'Mon, Jan 01 0000':
                    DateFormat = '%a, %b %d %Y'
                elif self.app.config['Display']['DateFormat'] == 'Monday, 01 Jan 0000':
                    DateFormat = '%A, %d %b %Y'
                elif self.app.config['Display']['DateFormat'] == 'Monday, Jan 01 0000':
                    DateFormat = '%A, %b %d %Y'
                else:
                    DateFormat = '%a, %d %b %Y'

                # Get station time zone
                Tz = pytz.timezone(self.app.config['Station']['Timezone'])

                # Format realtime Clock
                self.system_data['Time'] = datetime.fromtimestamp(time.time(), Tz).strftime(TimeFormat)
                self.system_data['Date'] = datetime.fromtimestamp(time.time(), Tz).strftime(DateFormat)
                self.update_display()

    def check_version(self, dt):

        """ Checks current version of the PiConsole against the latest available
        version on Github
        """

        # Get current time in station time zone
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Get version information from Github API
        Data = github_api.version(self.app.config)

        # Extract version number from API response
        if github_api.verify_response(Data, 'tag_name'):
            latest_ver = Data.json()['tag_name']
        else:
            Next = Tz.localize(datetime(Now.year, Now.month, Now.day) + timedelta(days=1))
            Clock.schedule_once(self.check_version, (Next - Now).total_seconds())
            return

        # If current and latest version numbers do not match, open update
        # notification
        if version.parse(self.app.config['System']['Version']) < version.parse(latest_ver):

            # Check if update notification is already open. Close if required
            try:
                App.get_running_self.app.update_notification.dismiss()
            except AttributeError:
                pass

            # Open update notification
            if self.app.config['Display']['UpdateNotification'] == '1':
                update_notification(latest_ver).open()
                Logger.info(f'System: {self.log_time()} - New version available: {latest_ver}')
            else:
                Logger.info(f'System: {self.log_time()} - New version available: {latest_ver}')

        # Schedule next Version Check
        Next = Tz.localize(datetime(Now.year, Now.month, Now.day) + timedelta(days=1))
        Clock.schedule_once(self.check_version, (Next - Now).total_seconds())

    def log_time(self):

        """ Return current time in station timezone in correct format for console
            log file
        """

        Tz = pytz.timezone(self.app.config['Station']['Timezone'])
        return datetime.fromtimestamp(time.time(), Tz).strftime('%Y-%m-%d %H:%M:%S')

    def update_display(self):

        """ Update display with new System variables. Catch ReferenceErrors to
        prevent console crashing
        """

        # Update display values with new derived observations
        reference_error = False
        for Key, Value in list(self.system_data.items()):
            try:
                self.app.CurrentConditions.System[Key] = Value
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'System: {self.log_time()} - Reference error')
                    reference_error = True
