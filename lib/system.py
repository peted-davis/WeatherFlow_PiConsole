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

# Import required Python modules
from datetime     import datetime
import time
import pytz


def realtimeClock(System, Config, *largs):

    """ Realtime clock in station timezone

    INPUTS:
        System                 Dictionary holding system information
        Config                 Station configuration

    OUTPUT:
        System                 Dictionary holding system information
    """

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


def logTime():

    """ Return current time in station timezone in correct format for console
        log file
    """

    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
