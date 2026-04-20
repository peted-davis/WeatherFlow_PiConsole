""" Contains system functions required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2025 Peter Davis

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

    def realtime_clock(self, dt):

        """ Format Realtime clock and date in station timezone
        """

        # Define time and date format based on user settings
        if 'Display' in self.app.config:
            if 'TimeFormat' in self.app.config['Display'] and 'DateFormat' in self.app.config['Display']:
                if self.app.config['Display']['TimeFormat'] == '12 hr':
                    if self.app.config['System']['Hardware'] == 'Other':
                        time_format = '%#I:%M:%S %p'
                    else:
                        time_format = '%-I:%M:%S %p'
                else:
                    time_format = '%H:%M:%S'
                if self.app.config['Display']['DateFormat']  == 'Mon, Jan 01 0000':
                    date_format = '%a, %b %d %Y'
                elif self.app.config['Display']['DateFormat'] == 'Monday, 01 Jan 0000':
                    date_format = '%A, %d %b %Y'
                elif self.app.config['Display']['DateFormat'] == 'Monday, Jan 01 0000':
                    date_format = '%A, %b %d %Y'
                else:
                    date_format = '%a, %d %b %Y'

                # Get station time zone
                tz = pytz.timezone(self.app.config['Station']['Timezone'])

                # Format realtime Clock
                self.system_data['time'] = datetime.fromtimestamp(time.time(), tz).strftime(time_format)
                self.system_data['date'] = datetime.fromtimestamp(time.time(), tz).strftime(date_format)
                self.update_display()

    def check_version(self, dt):

        """ Checks current version of the PiConsole against the latest available
        version on Github
        """

        # Get current time in station time zone
        tz = pytz.timezone(self.app.config['Station']['Timezone'])
        now = datetime.now(pytz.utc).astimezone(tz)

        # Get version information from Github API
        github_data = github_api.version(self.app.config)

        # Extract version number from API response
        if github_api.verify_response(github_data, 'tag_name'):
            latest_ver = github_data.json()['tag_name']
        else:
            next = tz.localize(datetime(now.year, now.month, now.day) + timedelta(days=1))
            Clock.schedule_once(self.check_version, (next - now).total_seconds())
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
            if int(self.app.config['Display']['UpdateNotification']):
                update_notification(latest_ver).open()
                Logger.info(f'System: {self.log_time()} - New version available: {latest_ver}')
            else:
                Logger.info(f'System: {self.log_time()} - New version available: {latest_ver}')

        # Schedule next Version Check
        next = tz.localize(datetime(now.year, now.month, now.day) + timedelta(days=1))
        Clock.schedule_once(self.check_version, (next - now).total_seconds())

    def log_time(self):

        """ Return current time in station timezone in correct format for console
            log file
        """

        tz = pytz.timezone(self.app.config['Station']['Timezone'])
        return datetime.fromtimestamp(time.time(), tz).strftime('%Y-%m-%d %H:%M:%S')

    def update_display(self):

        """ Update display with new System variables. Catch ReferenceErrors to
        prevent console crashing
        """

        # Update display values with new derived observations
        reference_error = False
        for key, value in list(self.system_data.items()):
            try:
                self.app.CurrentConditions.System[key] = value
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'System: {self.log_time()} - Reference error')
                    reference_error = True
