""" Returns the astronomical variables required by the Raspberry Pi Python
console for Weather Flow Smart Home Weather Stations. Copyright (C) 2018-2020
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
from datetime import datetime, timedelta, date, time
import ephem
import pytz

def SunriseSunset(astroData,Config):

    """ Calculate sunrise and sunset times for the current day or tomorrow
    in the station timezone

    INPUTS:
        astroData           Dictionary holding sunrise and sunset data
        Config              Station configuration

    OUTPUT:
        astroData           Dictionary holding sunrise and sunset data
    """

    # Define Sunrise/Sunset observer properties to match the United States Naval 
    # Observatory Astronomical Almanac
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Observer          = ephem.Observer()
    Observer.pressure = 0
    Observer.lat      = str(Config['Station']['Latitude'])
    Observer.lon      = str(Config['Station']['Longitude'])

    # The code is initialising. Calculate sunset/sunrise times for current day
    # starting at midnight today in UTC
    if astroData['Sunset'][0] == '-':

        # Set Observer time to midnight today in UTC
        UTC = datetime.now(pytz.utc)
        Midnight = datetime(UTC.year,UTC.month,UTC.day,0,0,0)
        Observer.date = Midnight.strftime('%Y/%m/%d %H:%M:%S')
        
        # Calculate Dawn time in UTC
        Observer.horizon = '-6'
        Dawn             = Observer.next_rising(ephem.Sun(), use_center=True)
        Dawn             = pytz.utc.localize(Dawn.datetime())

        # Calculate Sunrise time in UTC
        Observer.horizon = '-0:34'
        Sunrise          = Observer.next_rising(ephem.Sun())
        Sunrise          = pytz.utc.localize(Sunrise.datetime())

        # Calculate Sunset time in UTC
        Observer.horizon = '-0:34'
        Sunset           = Observer.next_setting(ephem.Sun())
        Sunset           = pytz.utc.localize(Sunset.datetime())
        
        # Calculate Dusk time in UTC
        Observer.horizon = '-6'
        Dusk             = Observer.next_setting(ephem.Sun(), use_center=True)
        Dusk             = pytz.utc.localize(Dusk.datetime())

        # Define Dawn/Dusk and Sunrise/Sunset times in Station timezone
        astroData['Dawn'][0]    = Dawn.astimezone(Tz)
        astroData['Sunrise'][0] = Sunrise.astimezone(Tz)
        astroData['Sunset'][0]  = Sunset.astimezone(Tz)
        astroData['Dusk'][0]    = Dusk.astimezone(Tz)
        
        # Calculate length and position of the dawn/dusk and sunrise/sunset 
        # lines on the day/night bar
        dawnMidnight    = (astroData['Dawn'][0].hour*3600 + astroData['Dawn'][0].minute*60)
        sunriseMidnight = (astroData['Sunrise'][0].hour*3600 + astroData['Sunrise'][0].minute*60)
        sunsetMidnight  = (astroData['Sunset'][0].hour*3600 + astroData['Sunset'][0].minute*60)
        duskMidnight    = (astroData['Dusk'][0].hour*3600 + astroData['Dusk'][0].minute*60)
        astroData['Dawn'][2]    = dawnMidnight/86400
        astroData['Sunrise'][2] = sunriseMidnight/86400
        astroData['Sunset'][2]  = (sunsetMidnight-sunriseMidnight)/86400
        astroData['Dusk'][2]    = (duskMidnight-dawnMidnight)/86400

    # Sunset has passed. Calculate sunset/sunrise times for tomorrow starting at
    # time of last Sunset in UTC
    else:

        # Set Observer time to last Sunset time in UTC
        Sunset = astroData['Sunset'][0].astimezone(pytz.utc) + timedelta(seconds=1)
        Observer.date = Sunset.strftime('%Y/%m/%d %H:%M:%S')

        # Calculate Dawn time in UTC
        Observer.horizon = '-6'
        Dawn             = Observer.next_rising(ephem.Sun(), use_center=True)
        Dawn             = pytz.utc.localize(Dawn.datetime())

        # Calculate Sunrise time in UTC
        Observer.horizon = '-0:34'
        Sunrise          = Observer.next_rising(ephem.Sun())
        Sunrise          = pytz.utc.localize(Sunrise.datetime())

        # Calculate Sunset time in UTC
        Observer.horizon = '-0:34'
        Sunset           = Observer.next_setting(ephem.Sun())
        Sunset           = pytz.utc.localize(Sunset.datetime())
        
        # Calculate Dusk time in UTC
        Observer.horizon = '-6'
        Dusk             = Observer.next_setting(ephem.Sun(), use_center=True)
        Dusk             = pytz.utc.localize(Dusk.datetime())

        # Define Dawn/Dusk and Sunrise/Sunset times in Station timezone
        astroData['Dawn'][0]    = Dawn.astimezone(Tz)
        astroData['Sunrise'][0] = Sunrise.astimezone(Tz)
        astroData['Sunset'][0]  = Sunset.astimezone(Tz)
        astroData['Dusk'][0]    = Dusk.astimezone(Tz)
        
        # Calculate length and position of the dawn/dusk and sunrise/sunset 
        # lines on the day/night bar
        dawnMidnight    = (astroData['Dawn'][0].hour*3600 + astroData['Dawn'][0].minute*60)
        sunriseMidnight = (astroData['Sunrise'][0].hour*3600 + astroData['Sunrise'][0].minute*60)
        sunsetMidnight  = (astroData['Sunset'][0].hour*3600 + astroData['Sunset'][0].minute*60)
        duskMidnight    = (astroData['Dusk'][0].hour*3600 + astroData['Dusk'][0].minute*60)
        astroData['Dawn'][2]    = dawnMidnight/86400
        astroData['Sunrise'][2] = sunriseMidnight/86400
        astroData['Sunset'][2]  = (sunsetMidnight-sunriseMidnight)/86400
        astroData['Dusk'][2]    = (duskMidnight-dawnMidnight)/86400

    # Format sunrise/sunset labels based on date of next sunrise
    astroData = Format(astroData,Config,'Sun')

    # Return astroData
    return astroData

def MoonriseMoonset(astroData,Config):

    """ Calculate moonrise and moonset times for the current day or
    tomorrow in the station timezone

    INPUTS:
        astroData           Dictionary holding moonrise and moonset data
        Config              Station configuration

    OUTPUT:
        astroData           Dictionary holding moonrise and moonset data
    """

    # Define Moonrise/Moonset location properties
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Observer     = ephem.Observer()
    Observer.lat = str(Config['Station']['Latitude'])
    Observer.lon = str(Config['Station']['Longitude'])

    # The code is initialising. Calculate moonrise time for current day
    # starting at midnight today in UTC
    if astroData['Moonrise'][0] == '-':

        # Set Observer time to midnight today in UTC
        UTC = datetime.now(pytz.utc)
        Midnight = datetime(UTC.year,UTC.month,UTC.day,0,0,0)
        Observer.date = Midnight.strftime('%Y/%m/%d %H:%M:%S')

        # Calculate Moonrise time in UTC
        Moonrise = Observer.next_rising(ephem.Moon())
        Moonrise = pytz.utc.localize(Moonrise.datetime())

        # Define Moonrise time in Station timezone
        astroData['Moonrise'][0] = Moonrise.astimezone(Tz)

    # Moonset has passed. Calculate time of next moonrise starting at
    # time of last Moonset in UTC
    else:

        # Set Observer time to last Moonset time in UTC
        Moonset = astroData['Moonset'][0].astimezone(pytz.utc) + timedelta(seconds=1)
        Observer.date = Moonset.strftime('%Y/%m/%d %H:%M:%S')

        # Calculate Moonrise time in UTC
        Moonrise = Observer.next_rising(ephem.Moon())
        Moonrise = pytz.utc.localize(Moonrise.datetime())

        # Define Moonrise time in Station timezone
        astroData['Moonrise'][0] = Moonrise.astimezone(Tz)

    # Convert Moonrise time in Station timezone to Moonrise time in UTC
    Moonrise = astroData['Moonrise'][0].astimezone(pytz.utc)
    Observer.date = Moonrise.strftime('%Y/%m/%d %H:%M:%S')

    # Calculate time of next Moonset starting at time of last Moonrise in UTC
    Moonset = Observer.next_setting(ephem.Moon())
    Moonset = pytz.utc.localize(Moonset.datetime())

    # Define Moonset time in Station timezone
    astroData['Moonset'][0] = Moonset.astimezone(Tz)

    # Calculate date of next full moon in UTC
    Observer.date = datetime.now(pytz.utc).strftime('%Y/%m/%d')
    FullMoon = ephem.next_full_moon(Observer.date)
    FullMoon = pytz.utc.localize(FullMoon.datetime())

    # Calculate date of next new moon in UTC
    NewMoon = ephem.next_new_moon(Observer.date)
    NewMoon = pytz.utc.localize(NewMoon.datetime())

    # Define next new/full moon in station time zone
    astroData['FullMoon'] = [FullMoon.astimezone(Tz).strftime('%b %d'),FullMoon]
    astroData['NewMoon'] = [NewMoon.astimezone(Tz).strftime('%b %d'),NewMoon]

    # Format sunrise/sunset labels based on date of next sunrise
    astroData = Format(astroData,Config,'Moon')

    # Return astroData
    return astroData

def Format(astroData,Config,Type):

    """ Format the sunrise/sunset labels and moonrise/moonset labels based on
    the current time of day in the station timezone

    INPUTS:
        astroData           Dictionary holding sunrise/sunset and moonrise/moonset
                            data
        Config              Station configuration
        Type                Flag specifying whether to format sun or moon data

    OUTPUT:
        astroData           Dictionary holding moonrise and moonset data
    """

    # Get current time in Station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Format Sunrise/Sunset data
    if Type == 'Sun':
        if Now.date() == astroData['Sunrise'][0].date():
            astroData['Sunrise'][1] = astroData['Sunrise'][0].strftime('%H:%M')
            astroData['Sunset'][1] = astroData['Sunset'][0].strftime('%H:%M')
        else:
            astroData['Sunrise'][1] = astroData['Sunrise'][0].strftime('%H:%M') + ' (+1)'
            astroData['Sunset'][1] = astroData['Sunset'][0].strftime('%H:%M') + ' (+1)'

    # Format Moonrise/Moonset data
    elif Type == 'Moon':

        # Update Moonrise Kivy Label bind based on date of next moonrise
        if Now.date() == astroData['Moonrise'][0].date():
            astroData['Moonrise'][1] = astroData['Moonrise'][0].strftime('%H:%M')
        elif Now.date() < astroData['Moonrise'][0].date():
            astroData['Moonrise'][1] = astroData['Moonrise'][0].strftime('%H:%M') + ' (+1)'
        else:
            astroData['Moonrise'][1] = astroData['Moonrise'][0].strftime('%H:%M') + ' (-1)'

        # Update Moonset Kivy Label bind based on date of next moonset
        if Now.date() == astroData['Moonset'][0].date():
            astroData['Moonset'][1] = astroData['Moonset'][0].strftime('%H:%M')
        elif Now.date() < astroData['Moonset'][0].date():
            astroData['Moonset'][1] = astroData['Moonset'][0].strftime('%H:%M') + ' (+1)'
        else:
            astroData['Moonset'][1] = astroData['Moonset'][0].strftime('%H:%M') + ' (-1)'

        # Update New Moon Kivy Label bind based on date of next new moon
        if astroData['FullMoon'][1].date() == Now.date():
            astroData['FullMoon'] = ['[color=ff8837ff]Today[/color]',astroData['FullMoon'][1]]

        # Update Full Moon Kivy Label bind based on date of next full moon
        elif astroData['NewMoon'][1].date() == Now.date():
            astroData['NewMoon'] = ['[color=ff8837ff]Today[/color]',astroData['NewMoon'][1]]

    # Return dictionary holding sunrise/sunset and moonrise/moonset data
    return astroData

def sunTransit(astroData, Config, *largs):

    """ Calculate the sun transit between sunrise and sunset

    INPUTS:
        astroData           Dictionary holding sunrise and sunset data
        Config              Station configuration

    OUTPUT:
        astroData           Dictionary holding moonrise and moonset data
    """

    # Get current time in station time zone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)
    
    # Calculate sun icon position on daytime/nightime bar
    secondsMidnight = (Now.replace(microsecond=0) - Now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
    astroData['sunIconPosition'] = (secondsMidnight/86400)

    # If time is between sunrise and sun set, calculate number of daylight hours 
    # remaining 
    if Now >= astroData['Sunrise'][0] and Now <= astroData['Sunset'][0]:

        # Determine total length of daylight, amount of daylight that has passed
        # and amount of daylight left
        DaylightTotal = astroData['Sunset'][0] - astroData['Sunrise'][0]
        DaylightLapsed = Now - astroData['Sunrise'][0]
        DaylightLeft = astroData['Sunset'][0] - Now

        # Determine hours and minutes left until sunset
        hours,remainder = divmod(DaylightLeft.total_seconds(), 3600)
        minutes,seconds = divmod(remainder,60)

        # Define Kivy Label binds
        astroData['sunEvent']   = ['[color=f05e40ff]Sunset[/color]','{:02.0f}'.format(hours),'{:02.0f}'.format(minutes),'Daytime']
        astroData['sunIcon'][0] = 'sunUp'
        astroData['sunIcon'][1] = 0

    # When not daylight, calculate time until sunrise
    elif Now <= astroData['Sunrise'][0]:

        # Determine hours and minutes left until sunrise
        NightLeft = astroData['Sunrise'][0] - Now
        hours,remainder = divmod(NightLeft.total_seconds(), 3600)
        minutes,seconds = divmod(remainder,60)

        # Define Kivy Label binds
        astroData['sunEvent']   = ['[color=f0b240ff]Sunrise[/color]','{:02.0f}'.format(hours),'{:02.0f}'.format(minutes),'Nightime']
        astroData['sunIcon'][0] = '-'
        astroData['sunIcon'][1] = 1

    # Return dictionary containing sun transit data
    return astroData

def moonPhase(astroData, Config, *largs):

    """ Calculate the moon phase for the current time in station timezone

    INPUTS:
        astroData           Dictionary holding moonrise and moonset data
        Config              Station configuration

    OUTPUT:
        astroData           Dictionary holding moonrise and moonset data
    """

    # Get current time in UTC
    Tz = pytz.timezone(Config['Station']['Timezone'])
    UTC = datetime.now(pytz.utc)

    # Get date of next full moon in station time zone
    FullMoon = astroData['FullMoon'][1].astimezone(Tz)

    # Get date of next new moon in station time zone
    NewMoon = astroData['NewMoon'][1].astimezone(Tz)

    # Calculate phase of moon
    Moon = ephem.Moon()
    Moon.compute(UTC.strftime('%Y/%m/%d %H:%M:%S'))

    # Define Moon phase icon
    if FullMoon < NewMoon:
        PhaseIcon = 'Waxing_' + '{:.0f}'.format(Moon.phase)
    elif NewMoon < FullMoon:
        PhaseIcon = 'Waning_' + '{:.0f}'.format(Moon.phase)

    # Define Moon phase text
    if astroData['NewMoon'] == '[color=ff8837ff]Today[/color]':
        PhaseTxt = 'New Moon'
    elif astroData['FullMoon'] == '[color=ff8837ff]Today[/color]':
        PhaseTxt = 'Full Moon'
    elif FullMoon < NewMoon and Moon.phase < 49:
        PhaseTxt = 'Waxing crescent'
    elif FullMoon < NewMoon and 49 <= Moon.phase <= 51:
        PhaseTxt = 'First Quarter'
    elif FullMoon < NewMoon and Moon.phase > 51:
        PhaseTxt = 'Waxing gibbous'
    elif NewMoon < FullMoon and Moon.phase > 51:
        PhaseTxt = 'Waning gibbous'
    elif NewMoon < FullMoon and 49 <= Moon.phase <= 51:
        PhaseTxt = 'Last Quarter'
    elif NewMoon < FullMoon and Moon.phase < 49:
        PhaseTxt = 'Waning crescent'

    # Define Moon phase illumination
    Illumination = '{:.0f}'.format(Moon.phase)

    # Define Kivy Label binds
    astroData['Phase'] = [PhaseIcon,PhaseTxt,Illumination]

    # Return dictionary containing moon phase data
    return astroData
