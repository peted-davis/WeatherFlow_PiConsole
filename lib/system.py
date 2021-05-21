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

# Import required Python modules
from kivy.clock   import mainthread
from datetime     import datetime
import time
import pytz

# Define global variables
NaN = float('NaN')


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
                TimeFormat = '%I:%M:%S %p'
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
            System['Time'] = [datetime.fromtimestamp(time.time(), Tz).strftime(TimeFormat), '-']
            System['Date'] = [datetime.fromtimestamp(time.time(), Tz).strftime(DateFormat), '-']
            print(System['Date'][0])

@mainthread
def updateDisplay(type, derivedObs, Console):

    """ Update display with new variables derived from latest websocket message

    INPUTS:
        type                Latest Websocket message type
        derivedObs          Derived variables from latest Websocket message
        Console             Console object
    """

    # Update display values with new derived observations
    for Key, Value in derivedObs.items():
        if not (type == 'all' and 'rapid' in Key):                  # Don't update rapidWind display when type is 'all'
            Console.CurrentConditions.Obs[Key] = Value              # as the RapidWind rose is not animated in this case

    # Update display graphics with new derived observations
    if type == 'rapid_wind':
        if hasattr(Console, 'WindSpeedPanel'):
            for panel in getattr(Console, 'WindSpeedPanel'):
                panel.animateWindRose()
    elif type == 'evt_strike':
        if Console.config['Display']['LightningPanel'] == '1':
            for ii, Button in enumerate(Console.CurrentConditions.buttonList):
                if "Lightning" in Button[2]:
                    Console.CurrentConditions.switchPanel([], Button)
        if hasattr(Console, 'LightningPanel'):
            for panel in getattr(Console, 'LightningPanel'):
                panel.setLightningBoltIcon()
                panel.animateLightningBoltIcon()
    else:
        if type in ['obs_st', 'obs_air', 'obs_all']:
            if hasattr(Console, 'TemperaturePanel'):
                for panel in getattr(Console, 'TemperaturePanel'):
                    panel.setFeelsLikeIcon()
            if hasattr(Console, 'LightningPanel'):
                for panel in getattr(Console, 'LightningPanel'):
                    panel.setLightningBoltIcon()
            if hasattr(Console, 'BarometerPanel'):
                for panel in getattr(Console, 'BarometerPanel'):
                    panel.setBarometerArrow()
        if type in ['obs_st', 'obs_sky', 'obs_all']:
            if hasattr(Console, 'WindSpeedPanel'):
                for panel in getattr(Console, 'WindSpeedPanel'):
                    panel.setWindIcons()
            if hasattr(Console, 'SunriseSunsetPanel'):
                for panel in getattr(Console, 'SunriseSunsetPanel'):
                    panel.setUVBackground()
            if hasattr(Console, 'RainfallPanel'):
                for panel in getattr(Console, 'RainfallPanel'):
                    panel.animateRainRate()
            if hasattr(Console, 'TemperaturePanel'):
                for panel in getattr(Console, 'TemperaturePanel'):
                    panel.setFeelsLikeIcon()


def logTime():

    return datetime.now().strftime('%Y-%M-%d %H:%M:%S')
