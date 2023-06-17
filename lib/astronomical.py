""" Returns the astronomical variables required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2023 Peter Davis

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

# Import required library modules
from lib.system  import system
from lib         import properties

# Import required Kivy modules
from kivy.logger import Logger
from kivy.clock  import Clock
from kivy.app    import App

# Import required modules
from datetime import datetime, timedelta, time
import ephem
import pytz
import math


class astro():

    def __init__(self):

        # Store reference to app class
        self.app = App.get_running_app()
        self.astro_data = properties.Astro()

        # Define observer properties
        self.observer          = ephem.Observer()
        self.observer.lat      = str(self.app.config['Station']['Latitude'])
        self.observer.lon      = str(self.app.config['Station']['Longitude'])

        # Define body properties
        self.sun  = ephem.Sun()
        self.moon = ephem.Moon()

    def reset_astro(self):

        ''' Reset the Astro data when the station ID changes
        '''
        # Cancel sun_transit and moon_phase schedules
        self.app.Sched.sun_transit.cancel()
        self.app.Sched.moon_phase.cancel()

        # Reset the astro data and generate new sunrise/sunset and
        # moonrise/moonset times
        self.astro_data = properties.Astro()
        self.update_display()
        self.sunrise_sunset()
        self.moonrise_moonset()

        # Force update sun_transit to correct sunrise/sunset times and then
        # reschedule sun_transit and moon_phase
        self.sun_transit()
        self.app.Sched.sun_transit = Clock.schedule_interval(self.sun_transit, 1)
        self.app.Sched.moon_phase  = Clock.schedule_interval(self.moon_phase,  1)

    def sunrise_sunset(self):

        """ Calculate sunrise and sunset times for the current day or tomorrow
        in the station timezone

        INPUTS:
            self.astro_data           Dictionary holding sunrise and sunset data
            Config              Station configuration

        OUTPUT:
            self.astro_data           Dictionary holding sunrise and sunset data
        """

        # Get station timezone
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])

        # Set pressure to 0 to match the United States Naval Observatory Astronomical
        # Almanac
        self.observer.pressure = 0

        # The code is initialising. Calculate sunset/sunrise times for current day
        # starting at midnight today in UTC
        if self.astro_data['Sunset'][0] == '-':

            # Set Observer time to midnight today in UTC
            UTC = datetime.now(pytz.utc)
            Midnight = datetime(UTC.year, UTC.month, UTC.day, 0, 0, 0)
            self.observer.date = Midnight.strftime('%Y/%m/%d %H:%M:%S')

        # Dusk has passed. Calculate sunset/sunrise times for tomorrow starting at
        # time of last Dusk in UTC
        else:

            # Set Observer time to last Sunset time in UTC
            Dusk = self.astro_data['Dusk'][0].astimezone(pytz.utc) + timedelta(minutes=1)
            self.observer.date = Dusk.strftime('%Y/%m/%d %H:%M:%S')

        # Calculate Dawn time in UTC
        self.observer.horizon = '-6'
        Dawn = self.observer.next_rising(self.sun, use_center=True)
        Dawn = pytz.utc.localize(Dawn.datetime().replace(second=0, microsecond=0))

        # Calculate Sunrise time in UTC
        self.observer.horizon = '-0:34'
        Sunrise = self.observer.next_rising(self.sun)
        Sunrise = pytz.utc.localize(Sunrise.datetime().replace(second=0, microsecond=0))

        # Calculate Sunset time in UTC
        self.observer.horizon = '-0:34'
        Sunset = self.observer.next_setting(self.sun)
        Sunset = pytz.utc.localize(Sunset.datetime().replace(second=0, microsecond=0))

        # Calculate Dusk time in UTC
        self.observer.horizon = '-6'
        Dusk = self.observer.next_setting(self.sun, use_center=True)
        Dusk = pytz.utc.localize(Dusk.datetime().replace(second=0, microsecond=0))

        # Define Dawn/Dusk and Sunrise/Sunset times in Station timezone
        self.astro_data['Dawn'][0]    = Dawn.astimezone(Tz)
        self.astro_data['Sunrise'][0] = Sunrise.astimezone(Tz)
        self.astro_data['Sunset'][0]  = Sunset.astimezone(Tz)
        self.astro_data['Dusk'][0]    = Dusk.astimezone(Tz)

        # Calculate length and position of the dawn/dusk and sunrise/sunset
        # lines on the day/night bar
        dawnMidnight    = (self.astro_data['Dawn'][0].hour * 3600    + self.astro_data['Dawn'][0].minute * 60)
        sunriseMidnight = (self.astro_data['Sunrise'][0].hour * 3600 + self.astro_data['Sunrise'][0].minute * 60)
        sunsetMidnight  = (self.astro_data['Sunset'][0].hour * 3600  + self.astro_data['Sunset'][0].minute * 60)
        duskMidnight    = (self.astro_data['Dusk'][0].hour * 3600    + self.astro_data['Dusk'][0].minute * 60)
        self.astro_data['Dawn'][2]    = dawnMidnight / 86400
        self.astro_data['Sunrise'][2] = sunriseMidnight / 86400
        self.astro_data['Sunset'][2]  = (sunsetMidnight - sunriseMidnight) / 86400
        self.astro_data['Dusk'][2]    = (duskMidnight - dawnMidnight) / 86400

        # Format sunrise/sunset labels based on date of next sunrise
        self.format_labels('sun')

    def moonrise_moonset(self):

        """ Calculate moonrise and moonset times for the current day or
        tomorrow in the station timezone

        INPUTS:
            self.astro_data           Dictionary holding moonrise and moonset data
            Config              Station configuration

        OUTPUT:
            self.astro_data           Dictionary holding moonrise and moonset data
        """

        # Define Moonrise/Moonset location properties
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])

        # Define Moonrise/Moonset location properties
        self.observer.horizon = '0'
        self.observer.pressure = 1010

        # The code is initialising. Calculate moonrise time for current day
        # starting at midnight today in UTC
        if self.astro_data['Moonrise'][0] == '-':

            # Set Observer time to midnight today in UTC
            UTC = datetime.now(pytz.utc)
            Midnight = datetime(UTC.year, UTC.month, UTC.day, 0, 0, 0)
            self.observer.date = Midnight.strftime('%Y/%m/%d %H:%M:%S')

        # Moonset has passed. Calculate time of next moonrise starting at
        # time of last Moonset in UTC
        else:

            # Set Observer time to last Moonset time in UTC
            Moonset = self.astro_data['Moonset'][0].astimezone(pytz.utc) + timedelta(minutes=1)
            self.observer.date = Moonset.strftime('%Y/%m/%d %H:%M:%S')

        # Calculate Moonrise time in UTC
        Moonrise = self.observer.next_rising(self.moon)
        Moonrise = pytz.utc.localize(Moonrise.datetime().replace(second=0, microsecond=0))

        # Define Moonrise time in Station timezone
        self.astro_data['Moonrise'][0] = Moonrise.astimezone(Tz)

        # Convert Moonrise time in Station timezone to Moonrise time in UTC
        Moonrise = self.astro_data['Moonrise'][0].astimezone(pytz.utc)
        self.observer.date = Moonrise.strftime('%Y/%m/%d %H:%M:%S')

        # Calculate time of next Moonset starting at time of last Moonrise in UTC
        Moonset = self.observer.next_setting(self.moon)
        Moonset = pytz.utc.localize(Moonset.datetime().replace(second=0, microsecond=0))

        # Define Moonset time in Station timezone
        self.astro_data['Moonset'][0] = Moonset.astimezone(Tz)

        # Calculate date of next full moon in UTC
        self.observer.date = datetime.now(pytz.utc).strftime('%Y/%m/%d')
        FullMoon = ephem.next_full_moon(self.observer.date)
        FullMoon = pytz.utc.localize(FullMoon.datetime())

        # Calculate date of next new moon in UTC
        NewMoon = ephem.next_new_moon(self.observer.date)
        NewMoon = pytz.utc.localize(NewMoon.datetime())

        # Define next new/full moon in station time zone
        self.astro_data['FullMoon'] = [FullMoon.astimezone(Tz).strftime('%b %d'), FullMoon]
        self.astro_data['NewMoon']  = [NewMoon.astimezone(Tz).strftime('%b %d'),  NewMoon]

        # Format sunrise/sunset labels based on date of next sunrise
        self.format_labels('moon')

    def sun_transit(self, *largs):

        """ Calculate the sun transit between sunrise and sunset

        INPUTS:
            self.astro_data           Dictionary holding sunrise and sunset data
            Config              Station configuration

        OUTPUT:
            self.astro_data           Dictionary holding moonrise and moonset data
        """

        # Get current time in station time zone
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Calculate sun icon position on daytime/nightime bar
        secondsMidnight = (Now.replace(microsecond=0) - Now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        sunPosition     = secondsMidnight / 86400

        # If time is before dawn, calculate number of nighttime hours remaining
        if Now < self.astro_data['Dawn'][0]:

            # Determine number of nighttime hours remaining
            secondsToDawn    = (self.astro_data['Dawn'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder = divmod(secondsToDawn, 3600)
            minutes, seconds = divmod(remainder, 60)

            # Define Kivy Label binds
            self.astro_data['sunEvent']   = ['[color=00A4B4FF]Dawn[/color]', '{:02.0f}'.format(hours), '{:02.0f}'.format(minutes), 'Nighttime']
            self.astro_data['sunIcon']    = ['-', 1, sunPosition]

        # If time is before sunrise, calculate number of dawn hours remaining
        elif Now < self.astro_data['Sunrise'][0]:

            # Determine number of nighttime hours remaining
            secondsToSunrise  = (self.astro_data['Sunrise'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder  = divmod(secondsToSunrise, 3600)
            minutes, seconds  = divmod(remainder, 60)

            # Define Kivy Label binds
            self.astro_data['sunEvent']   = ['[color=FF8841FF]Sunrise[/color]', '{:02.0f}'.format(hours), '{:02.0f}'.format(minutes), 'Dawn']
            self.astro_data['sunIcon']    = ['-', 1, sunPosition]

        # If time is between sunrise and sunset, calculate number of daylight hours
        # remaining
        elif Now >= self.astro_data['Sunrise'][0] and Now < self.astro_data['Sunset'][0]:

            # Determine number of daylight hours remaining
            secondsToSunset  = (self.astro_data['Sunset'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder = divmod(secondsToSunset, 3600)
            minutes, seconds = divmod(remainder, 60)

            # Define Kivy Label binds
            self.astro_data['sunEvent']   = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), '{:02.0f}'.format(minutes), 'Daytime']
            self.astro_data['sunIcon']    = ['sunUp', 0, sunPosition]

        # If time after sunset, calculate number of dusk hours remaining
        elif Now < self.astro_data['Dusk'][0]:

            # Determine hours and minutes left until sunrise
            secondsToNightfall  = (self.astro_data['Dusk'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder    = divmod(secondsToNightfall, 3600)
            minutes, seconds    = divmod(remainder, 60)

            # Define Kivy Label binds
            self.astro_data['sunEvent'] = ['[color=00A4B4FF]Nightfall[/color]', '{:02.0f}'.format(hours), '{:02.0f}'.format(minutes), 'Dusk']
            self.astro_data['sunIcon']  = ['-', 1, sunPosition]
            self.update_display()

        # Once dusk has passed calculate new sunrise/sunset times
        if Now.replace(microsecond=0) >= self.astro_data['Dusk'][0]:
            self.sunrise_sunset()

        # Once moonset has passed, calculate new moonrise/moonset times
        if Now.replace(microsecond=0) > self.astro_data['Moonset'][0]:
            self.moonrise_moonset()

        # At midnight update sunrise/sunset times
        if self.astro_data['Reformat'] and Now.replace(second=0).replace(microsecond=0).time() == time(0, 0, 0):
            self.format_labels('sun')
            self.format_labels('moon')

    def moon_phase(self, *largs):

        """ Calculate the moon phase for the current time in station timezone

        INPUTS:
            self.astro_data           Dictionary holding moonrise and moonset data
            Config              Station configuration

        OUTPUT:
            self.astro_data           Dictionary holding moonrise and moonset data
        """

        # Get current time in UTC
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])
        UTC = datetime.now(pytz.utc)

        # Get date of next full moon in station time zone
        full_moon = self.astro_data['FullMoon'][1].astimezone(Tz)

        # Get date of next new moon in station time zone
        new_moon = self.astro_data['NewMoon'][1].astimezone(Tz)

        # Calculate phase of moon
        self.moon.compute(UTC.strftime('%Y/%m/%d %H:%M:%S'))

        # Define Moon phase icon and tilt_sign
        if full_moon < new_moon:
            phase_icon = 'Waxing_' + '{:.0f}'.format(self.moon.phase)
            tilt_sign  = +1
        elif new_moon < full_moon:
            phase_icon = 'Waning_' + '{:.0f}'.format(self.moon.phase)
            tilt_sign  = -1

        # Define Moon phase text
        if self.astro_data['NewMoon'] == '[color=ff8837ff]Today[/color]':
            phase_text = 'New Moon'
        elif self.astro_data['FullMoon'] == '[color=ff8837ff]Today[/color]':
            phase_text = 'Full Moon'
        elif full_moon < new_moon and self.moon.phase < 49:
            phase_text = 'Waxing crescent'
        elif full_moon < new_moon and 49 <= self.moon.phase <= 51:
            phase_text = 'First Quarter'
        elif full_moon < new_moon and self.moon.phase > 51:
            phase_text = 'Waxing gibbous'
        elif new_moon < full_moon and self.moon.phase > 51:
            phase_text = 'Waning gibbous'
        elif new_moon < full_moon and 49 <= self.moon.phase <= 51:
            phase_text = 'Last Quarter'
        elif new_moon < full_moon and self.moon.phase < 49:
            phase_text = 'Waning crescent'

        # Define Moon phase illumination
        illumination = '{:.0f}'.format(self.moon.phase)

        # Calculate tilt of illuminated moon face
        self.observer.date = UTC.strftime('%Y/%m/%d %H:%M:%S')
        self.moon.compute(self.observer)
        self.sun.compute(self.observer)
        dLon = self.sun.az - self.moon.az
        y = math.sin(dLon) * math.cos(self.sun.alt)
        x = math.cos(self.moon.alt) * math.sin(self.sun.alt) - math.sin(self.moon.alt) * math.cos(self.sun.alt) * math.cos(dLon)
        tilt = tilt_sign * 90 - math.degrees(math.atan2(y, x))

        # Define Kivy labels
        self.astro_data['Phase'] = [phase_icon, phase_text, illumination, tilt]
        self.update_display()

    def format_labels(self, Type):

        """ Format the sunrise/sunset labels and moonrise/moonset labels based on
        the current time of day in the station timezone

        INPUTS:
            self.astro_data           Dictionary holding sunrise/sunset and moonrise/moonset
                                data
            Config              Station configuration
            Type                Flag specifying whether to format sun or moon data

        OUTPUT:
            self.astro_data           Dictionary holding moonrise and moonset data
        """

        # Get current time in Station timezone
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Set time format based on user configuration
        if self.app.config['Display']['TimeFormat'] == '12 hr':
            if self.app.config['System']['Hardware'] == 'Other':
                time_format = '%#I:%M %p'
            else:
                time_format = '%-I:%M %p'
        else:
            time_format = '%H:%M'

        # time_format Sunrise/Sunset data
        if Type == 'sun':
            if Now.date() == self.astro_data['Sunrise'][0].date():
                self.astro_data['Sunrise'][1] = self.astro_data['Sunrise'][0].strftime(time_format)
                self.astro_data['Sunset'][1]  = self.astro_data['Sunset'][0].strftime(time_format)
                self.astro_data['Reformat']   = 0
            else:
                self.astro_data['Sunrise'][1] = self.astro_data['Sunrise'][0].strftime(time_format) + ' (+1)'
                self.astro_data['Sunset'][1]  = self.astro_data['Sunset'][0].strftime(time_format)  + ' (+1)'
                self.astro_data['Reformat']   = 1

        # time_format Moonrise/Moonset data
        elif Type == 'moon':

            # Update Moonrise Kivy Label bind based on date of next moonrise
            if Now.date() == self.astro_data['Moonrise'][0].date():
                self.astro_data['Moonrise'][1] = self.astro_data['Moonrise'][0].strftime(time_format)
            elif Now.date() < self.astro_data['Moonrise'][0].date():
                self.astro_data['Moonrise'][1] = self.astro_data['Moonrise'][0].strftime(time_format) + ' (+1)'
            else:
                self.astro_data['Moonrise'][1] = self.astro_data['Moonrise'][0].strftime(time_format) + ' (-1)'

            # Update Moonset Kivy Label bind based on date of next moonset
            if Now.date() == self.astro_data['Moonset'][0].date():
                self.astro_data['Moonset'][1] = self.astro_data['Moonset'][0].strftime(time_format)
            elif Now.date() < self.astro_data['Moonset'][0].date():
                self.astro_data['Moonset'][1] = self.astro_data['Moonset'][0].strftime(time_format) + ' (+1)'
            else:
                self.astro_data['Moonset'][1] = self.astro_data['Moonset'][0].strftime(time_format) + ' (-1)'

            # Update New Moon Kivy Label bind based on date of next new moon
            if self.astro_data['FullMoon'][1].date() == Now.date():
                self.astro_data['FullMoon'] = ['[color=ff8837ff]Today[/color]', self.astro_data['FullMoon'][1]]

            # Update Full Moon Kivy Label bind based on date of next full moon
            elif self.astro_data['NewMoon'][1].date() == Now.date():
                self.astro_data['NewMoon'] = ['[color=ff8837ff]Today[/color]', self.astro_data['NewMoon'][1]]

        # Update display with formatted variables
        self.update_display()

    def update_display(self):

        """ Update display with new astro variables. Catch ReferenceErrors to
        prevent console crashing
        """

        # Update display values with new derived observations
        reference_error = False
        for Key, Value in list(self.astro_data.items()):
            try:
                self.app.CurrentConditions.Astro[Key] = Value
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'astro: {system().log_time()} - Reference error')
                    reference_error = True
