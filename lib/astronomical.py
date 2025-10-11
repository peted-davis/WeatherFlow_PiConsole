""" Returns the astronomical variables required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2022 Peter Davis

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
import pprint


class astro():

    def __init__(self):

        # Store reference to app class
        self.app = App.get_running_app()
        self.astro_data = properties.Astro()

        # Define observer properties
        self.observer      = ephem.Observer()
        self.observer.lat  = str(self.app.config['Station']['Latitude'])
        self.observer.lon  = str(self.app.config['Station']['Longitude'])

        # Define body properties
        self.sun  = ephem.Sun()
        self.moon = ephem.Moon()

        # Define date property
        self.tz = pytz.timezone(self.app.config['Station']['Timezone'])
        self.date = self.tz.localize(datetime.now().replace(minute=0,second=0, microsecond=0)).astimezone(pytz.utc)

        # Define sunrise/sunset and moonrise/moonset event dictionary
        self.sun_events  = {}
        self.moon_events = {}

    def reset_astro(self):

        ''' Reset the Astro data when the station ID changes
        '''

        # Cancel sun_transit and moon_phase schedules
        self.app.Sched.sun_transit.cancel()
        self.app.Sched.moon_phase.cancel()

        # Reset the astro data 
        self.astro_data = properties.Astro()
        self.sun_events  = {}
        self.moon_events = {}

        # Generate new sunrise/sunset, moonrise/moonset and full moon/new 
        # moon times
        self.update_astro_data()
        self.get_sunrise_sunset()
        self.get_moonrise_moonset()
        self.get_full_new_moon()

        # Force update sun_transit to correct sunrise/sunset times and then
        # reschedule sun_transit and moon_phase
        self.sun_transit()
        self.app.Sched.sun_transit = Clock.schedule_interval(self.sun_transit, 1)
        self.app.Sched.moon_phase  = Clock.schedule_interval(self.moon_phase,  1)

    def get_sunrise_sunset(self, *args):

        """ Calculate sunrise and sunset times n the station timezone

        INPUTS:
            self.astro_data           Dictionary holding sunrise and sunset data

        OUTPUT:
            self.astro_data           Dictionary holding sunrise and sunset data
        """

        # Set pressure to 0 to match the United States Naval Observatory
        # Astronomical Almanac
        self.observer.pressure = 0

        # Set sun event conditions
        self.sun_down_no_dawn = False
        self.sun_down_no_rise = False
        self.sun_up_no_set    = False
        self.sun_up_no_dusk   = False
        self.night    = [False]
        self.twilight = [False]
        self.daylight = [False]

        # The code is initialising. Calculate sunset/sunrise times for current
        # day starting at midnight today in station timezone
        if self.astro_data['Sunset'][0] == '-':
            midnight_local = self.date.astimezone(self.tz).replace(hour=0, minute=0, second=0)
            self.observer.date = midnight_local.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S')

        # Dusk has passed. Calculate sunset/sunrise times for tomorrow starting
        # at time of Dusk in station timezone
        else:
            time_now = self.date.astimezone(self.tz)
            if time_now.replace(second=0, microsecond=0).time() == time(0, 0, 0):
                midnight_local = self.date.astimezone(self.tz).replace(hour=0, minute=0, second=0)
            else:
                midnight_local = self.date.astimezone(self.tz).replace(hour=0, minute=0, second=0) + timedelta(days=1)
            self.observer.date = midnight_local.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S')

        # Reset sun events list
        self.sun_events = {}

        # Loop over all required sun events for current day
        for event in ['dawn', 'sunrise', 'sunset', 'dusk']:

            # Define required horizons based on current event
            if event == 'dawn' or event == 'dusk':
                self.observer.horizon = '-6'
                center = True
            elif event == 'sunrise' or event == 'sunset':
                self.observer.horizon = '-0:34'
                center = False
            if event == 'dawn' or event == 'sunrise':
                event_function = self.observer.next_rising
            elif event == 'dusk' or event == 'sunset':
                event_function = self.observer.next_setting

            # Calculate time of event for current day
            try:
                event_time = event_function(self.sun, use_center=center)
                event_time = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(self.tz)
            except ephem.AlwaysUpError:
                event_time = None
                if event == 'sunset':
                    self.sun_up_no_set = True
                elif event == 'dusk':
                    self.sun_up_no_dusk = True
            except ephem.NeverUpError:
                event_time = None
                if event == 'sunrise':
                    self.sun_down_no_rise = True
                elif event == 'dawn':
                    self.sun_down_no_dawn = True

            # Store time of event for current day
            self.sun_events[event] = event_time
            self.astro_data[event.capitalize()][0] = event_time

        # If sun is always up or never up, or sunset occurs before sunrise,
        # calculate time of next sunset or sunrise
        if ((self.sun_up_no_set or self.sun_down_no_rise)
           or (self.sun_events['sunset'] < self.sun_events['sunrise'])):
            self.observer.horizon = '-0:34'
            center = False
            observer_date = datetime.strptime(str(self.observer.date), '%Y/%m/%d %H:%M:%S') + timedelta(hours=12)
            self.observer.date = observer_date.strftime('%Y/%m/%d %H:%M:%S')
            if self.sun_up_no_set:
                event = 'next_sunset'
                event_function = self.observer.next_setting
            elif self.sun_down_no_rise:
                event = 'next_sunrise'
                event_function = self.observer.next_rising
            elif self.sun_events['sunset'] < self.sun_events['sunrise']:
                event = 'next_sunset'
                event_function = self.observer.next_setting
            while True:
                try:
                    event_time = event_function(self.sun, use_center=center)
                    event_time = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(self.tz)
                    self.sun_events[event] = event_time
                    break
                except (ephem.AlwaysUpError, ephem.NeverUpError):
                    observer_date = datetime.strptime(str(self.observer.date), '%Y/%m/%d %H:%M:%S') + timedelta(hours=12)
                    self.observer.date = observer_date.strftime('%Y/%m/%d %H:%M:%S')

        # Calculate midnight in station timezone from dawn/sunrise time
        if self.sun_events['dawn'] is not None:
            midnight_local = self.sun_events['dawn'].replace(hour=0, minute=0, second=0)
        elif self.sun_events['sunrise'] is not None:
            midnight_local = self.sun_events['sunrise'].replace(hour=0, minute=0, second=0)

        # Calculate length and position of the dawn/dusk and sunrise/sunset
        # lines on the day/night bar
        if self.sun_down_no_dawn and self.sun_down_no_rise:
            self.day_night_order = ['night']
            self.night           = [True, 0, 1]
        elif self.sun_up_no_set and self.sun_up_no_dusk:
            self.day_night_order = ['daylight']
            self.daylight        = [True, 0, 1]
        elif self.sun_down_no_rise:
            self.day_night_order = ['night', 'twilight']
            self.night           = [True, 0, 1]
            self.twilight        = [True,
                                    max((self.sun_events['dawn'] - midnight_local).total_seconds() / 86400, 0),
                                    min((self.sun_events['dusk'] - midnight_local).total_seconds() / 86400, 1)]
        elif self.sun_up_no_dusk:
            if self.sun_events['sunset'] < self.sun_events['sunrise']:
                self.day_night_order = ['daylight', 'twilight']
                self.twilight        = [True,
                                        max((self.sun_events['sunset']  - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['sunrise'] - midnight_local).total_seconds() / 86400, 1)]
                self.daylight        = [True, 0, 1]
            else:
                self.day_night_order = ['twilight', 'daylight']
                self.twilight        = [True, 0, 1]
                self.daylight        = [True,
                                        max((self.sun_events['sunrise'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['sunset']  - midnight_local).total_seconds() / 86400, 1)]
        else:
            if self.sun_events['dusk'] < self.sun_events['dawn']:
                self.day_night_order = ['twilight', 'night', 'daylight']
                self.night           = [True,
                                        max((self.sun_events['dusk'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['dawn'] - midnight_local).total_seconds() / 86400, 1)]
                self.twilight        = [True, 0, 1]
                self.daylight        = [True,
                                        max((self.sun_events['sunrise'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['sunset']  - midnight_local).total_seconds() / 86400, 1)]
            else:
                self.day_night_order = ['night', 'twilight', 'daylight']
                self.night           = [True, 0, 1]
                self.twilight        = [True,
                                        max((self.sun_events['dawn'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['dusk'] - midnight_local).total_seconds() / 86400, 1)]
                self.daylight        = [True,
                                        max((self.sun_events['sunrise'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['sunset']  - midnight_local).total_seconds() / 86400, 1)]

        # Format sunrise/sunset labels based on date of next sunrise
        self.format_event_labels('sun')

    def sun_transit(self, *largs):

        """ Calculate the sun transit between sunrise and sunset

        INPUTS:
            self.astro_data           Dictionary holding sunrise and sunset data

        OUTPUT:
            self.astro_data           Dictionary holding moonrise and moonset data
        """
        # Get current time in station time zone
        self.date = self.tz.localize(datetime.now()).astimezone(pytz.utc)
        time_now  = self.date.astimezone(self.tz)

        # Calculate sun icon position on daytime/nightime bar
        seconds_to_midnight = (time_now.replace(microsecond=0) - time_now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        sun_position        = seconds_to_midnight / 86400

        # If sun is always up calculate number of days until sunset
        if not self.night[0] and not self.twilight[0]:

            # Determine number of days until next sunset
            seconds_to_sunset = (self.sun_events['next_sunset'] - time_now.replace(second=0, microsecond=0)).total_seconds()
            days, remainder = divmod(seconds_to_sunset, 86400)
            hours, remainder   = divmod(remainder, 3600)
            minutes, remainder = divmod(remainder, 60)

            # Define Kivy labels
            if days > 0:
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(days), 'days', '{:02.0f}'.format(hours), 'hrs', 'Daytime']
            else:
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Daytime']
            self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]

        # If sun is never up calculate number of days until sunrise
        elif not self.daylight[0]:

            # Determine number of days until next sunrise
            seconds_to_sunrise = (self.sun_events['next_sunrise'] - time_now.replace(second=0, microsecond=0)).total_seconds()
            days, remainder    = divmod(seconds_to_sunrise, 86400)
            hours, remainder   = divmod(remainder, 3600)
            minutes, remainder = divmod(remainder, 60)

            # Determine whether time of day is nighttime or twilight
            if self.sun_down_no_dawn:
                description = 'Nighttime'
            else:
                if time_now >= self.sun_events['dawn'] and time_now <= self.sun_events['dusk']:
                    description = 'Twilight'
                else:
                    description = 'Nighttime'

            # Define Kivy labels
            if days > 0:
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunrise[/color]', '{:02.0f}'.format(days), 'days', '{:02.0f}'.format(hours), 'hrs', description]
            else:
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunrise[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', description]
            self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # If there is no night or twilight
        elif not self.night[0] and self.twilight[0] and self.daylight[0]:

            # sunrise occurs before sunset and time is between sunrise and
            # sunset, calculate time until sunset
            if (self.sun_events['sunrise'] < self.sun_events['sunset']
               and time_now >= self.sun_events['sunrise'] and time_now <= self.sun_events['sunset']):

                # Determine number of daylight hours remaining
                seconds_to_sunset  = (self.sun_events['sunset'] - time_now.replace(second=0, microsecond=0)).total_seconds()
                hours, remainder = divmod(seconds_to_sunset, 3600)
                minutes, seconds = divmod(remainder, 60)

                # Define Kivy labels
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Daytime']
                self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]

            # sunrise occurs after sunset and time is before sunset, calculate
            # time until sunset
            elif (self.sun_events['sunrise'] > self.sun_events['sunset']
                  and time_now <= self.sun_events['sunset']):

                # Determine number of daylight hours remaining
                seconds_to_sunset  = (self.sun_events['sunset'] - time_now.replace(second=0, microsecond=0)).total_seconds()
                hours, remainder = divmod(seconds_to_sunset, 3600)
                minutes, seconds = divmod(remainder, 60)

                # Define Kivy labels
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Daytime']
                self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]

            # sunrise occurs after sunset and time is after sunrise, calculate
            # time until next sunset
            elif (self.sun_events['sunrise'] > self.sun_events['sunset']
                  and time_now >= self.sun_events['sunrise']):

                # Determine number of daylight hours remaining
                seconds_to_sunset  = (self.sun_events['next_sunset'] - time_now.replace(second=0, microsecond=0)).total_seconds()
                days, remainder    = divmod(seconds_to_sunset, 86400)
                hours, remainder   = divmod(remainder, 3600)
                minutes, remainder = divmod(remainder, 60)

                # Define Kivy labels
                if days > 0:
                    self.astro_data['sunEvent']  = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(days), 'days', '{:02.0f}'.format(hours), 'hrs', 'Daytime']
                else:
                    self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Daytime']
                self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]

            # Else, calculate time until sunrise
            else:

                # Determine number of twilight hours remaining
                seconds_to_sunrise  = (self.sun_events['sunrise'] - time_now.replace(second=0, microsecond=0)).total_seconds()
                hours, remainder  = divmod(seconds_to_sunrise, 3600)
                minutes, seconds  = divmod(remainder, 60)

                # Define Kivy labels
                self.astro_data['sunEvent'] = ['[color=FF8841FF]Sunrise[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Twilight']
                self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # If dawn is after dusk and time is before dusk, calculate number of
        # night time hours remaining
        elif self.night[0] and self.sun_events['dawn'] > self.sun_events['dusk'] and time_now < self.sun_events['dusk']:

            # Determine hours and minutes left until dusk
            secondsToNightfall  = (self.sun_events['dusk'] - time_now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder    = divmod(secondsToNightfall, 3600)
            minutes, seconds    = divmod(remainder, 60)

            # Define Kivy labels
            self.astro_data['sunEvent'] = ['[color=00A4B4FF]Nightfall[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Dusk']
            self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # If dawn is before dusk and time is before dawn, calculate number of
        # night time hours remaining
        elif time_now < self.sun_events['dawn']:

            # Determine number of nighttime hours remaining
            seconds_to_dawn    = (self.sun_events['dawn'] - time_now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder = divmod(seconds_to_dawn, 3600)
            minutes, seconds = divmod(remainder, 60)

            # Define Kivy labels
            self.astro_data['sunEvent'] = ['[color=00A4B4FF]Dawn[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Nighttime']
            self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # If time is before sunrise, calculate number of dawn hours remaining
        elif time_now < self.sun_events['sunrise']:

            # Determine number of nighttime hours remaining
            seconds_to_sunrise  = (self.sun_events['sunrise'] - time_now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder  = divmod(seconds_to_sunrise, 3600)
            minutes, seconds  = divmod(remainder, 60)

            # Define Kivy labels
            self.astro_data['sunEvent'] = ['[color=FF8841FF]Sunrise[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Dawn']
            self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # If time is between sunrise and sunset, calculate number of daylight
        # hours remaining
        elif time_now >= self.sun_events['sunrise'] and time_now <= self.sun_events['sunset']:

            # Determine number of daylight hours remaining
            seconds_to_sunset  = (self.sun_events['sunset'] - time_now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder = divmod(seconds_to_sunset, 3600)
            minutes, seconds = divmod(remainder, 60)

            # Define Kivy labels
            self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Daytime']
            self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]

        # If time after sunset, calculate number of dusk hours remaining
        elif time_now < self.sun_events['dusk']:

            # Determine hours and minutes left until dusk
            secondsToNightfall  = (self.sun_events['dusk'] - time_now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder    = divmod(secondsToNightfall, 3600)
            minutes, seconds    = divmod(remainder, 60)

            # Define Kivy labels
            self.astro_data['sunEvent'] = ['[color=00A4B4FF]Nightfall[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Dusk']
            self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # Update display
        self.update_astro_data()
        self.update_day_night_bar()

        # Calculate new sunrise and sunset times
        if not self.night[0] and self.twilight[0] and self.daylight[0]:
            if self.sun_events['sunset'] < self.sun_events['sunrise']:
                if time_now > self.sun_events['sunrise']:
                    self.format_event_labels('next_sunset')
        if self.night[0] and not self.daylight[0]:
            if time_now.replace(second=0, microsecond=0).time() == time(0, 0, 0):
                self.get_sunrise_sunset()
        elif not self.night[0] and not self.twilight[0] and self.daylight[0]:
            if time_now.replace(second=0, microsecond=0).time() == time(0, 0, 0):
                self.get_sunrise_sunset()
        elif not self.night[0] and self.twilight[0] and self.daylight[0]:
            if (self.sun_events['sunset'].date() > self.sun_events['sunrise'].date()
               or self.sun_events['sunset'] < self.sun_events['sunrise']):
                if time_now.replace(second=0, microsecond=0).time() == time(0, 0, 0):
                    self.get_sunrise_sunset()
            else:
                if time_now.replace(microsecond=0) >= self.sun_events['sunset']:
                    self.get_sunrise_sunset()
        elif self.night[0] and self.twilight[0] and self.daylight[0]:
            if (self.sun_events['dusk'].date() > time_now.date()
               or self.sun_events['dusk'] < self.sun_events['dawn']):
                if time_now.replace(microsecond=0) >= self.sun_events['sunset']:
                    self.get_sunrise_sunset()
            else:
                if time_now.replace(microsecond=0) >= self.sun_events['dusk']:
                    self.get_sunrise_sunset()

        # Calculate new moonrise and moonset times
        if self.moon_events['set'] is not None and time_now >= self.moon_events['set']:
            self.get_moonrise_moonset()
        elif self.moon_events['set'] is None and time_now.replace(second=0, microsecond=0).time() == time(0, 0, 0):
            self.get_moonrise_moonset()

        # Calculate new full moon and new moon times
        if (time_now.date() > self.moon_events['full_moon'].date() or
            time_now.date() > self.moon_events['new_moon'].date()):
            self.get_full_new_moon()

        # At midnight update sunrise/sunset and moonrise/moonset times
        if self.astro_data['Reformat'] and time_now.replace(second=0, microsecond=0).time() == time(0, 0, 0):
            self.format_event_labels('sun')
            self.format_event_labels('moon')

    def get_moonrise_moonset(self):

        """ Calculate moonrise and moonset times in the station timezone

        INPUTS:
            self.astro_data           Dictionary holding moonrise and moonset data

        OUTPUT:
            self.astro_data           Dictionary holding moonrise and moonset data
        """

        # Define moonrise/moonset observer properties
        self.observer.horizon = '0'
        self.observer.pressure = 1013.25

        # Set moon event conditions
        self.moon_always_up = False
        self.moon_always_dn = False

        # The code is initialising. Calculate moonrise time for current day
        # starting at midnight today in UTC
        if 'set' not in self.moon_events:

            # Set Observer time to midnight today in UTC
            midnight_local = self.date.astimezone(self.tz).replace(hour=0, minute=0, second=0)
            self.observer.date = midnight_local.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S')

        # Moonset has passed. Calculate time of next moonrise starting at
        # time of last Moonset in UTC
        else:

            # Set Observer time to last Moonset time in UTC
            observer_time = self.date.astimezone(self.tz) + timedelta(minutes=1)
            self.observer.date = observer_time.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S')

        # Calculate time of next moonrise
        try:
            event_time = self.observer.next_rising(self.moon)
        except ephem.NeverUpError: 
            event_time = None
            self.moon_always_dn = True
        except ephem.AlwaysUpError:
            event_time = None
        if event_time is not None:
            self.moon_events['rise'] = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(self.tz)
            self.astro_data['Moonrise'][0] = self.moon_events['rise']
        else:
            self.moon_events['rise'] = None
            self.astro_data['Moonrise'][0] = '-'

        # Calculate time of next moonset
        try:
            event_time = self.observer.next_setting(self.moon)
        except ephem.AlwaysUpError:
            event_time = None
            self.moon_always_up = True
        except ephem.NeverUpError:
            event_time = None
        if event_time is not None:
            self.moon_events['set'] = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(self.tz)
            self.astro_data['Moonset'][0] = self.moon_events['set']
        else:
            self.moon_events['set'] = None
            self.astro_data['Moonset'][0] = '-'

        # If moon is always up or never up calculate time of next moonset or moonrise
        if self.moon_always_up or self.moon_always_dn:
            observer_date = datetime.strptime(str(self.observer.date), '%Y/%m/%d %H:%M:%S') + timedelta(hours=1)
            self.observer.date = observer_date.strftime('%Y/%m/%d %H:%M:%S')
            if self.moon_always_up:
                event = 'next_set'
                event_function = self.observer.next_setting
            elif self.moon_always_dn:
                event = 'next_rise'
                event_function = self.observer.next_rising
            while True:
                try:
                    event_time = event_function(self.moon)
                    event_time = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(self.tz)
                    self.moon_events[event] = event_time
                    break
                except (ephem.AlwaysUpError, ephem.NeverUpError):
                    observer_date = datetime.strptime(str(self.observer.date), '%Y/%m/%d %H:%M:%S') + timedelta(hours=1)
                    self.observer.date = observer_date.strftime('%Y/%m/%d %H:%M:%S')

        # Format sunrise/sunset labels based on date of next sunrise
        self.format_event_labels('moon')

    def get_full_new_moon(self):

        """ Calculate dates of next full moon and next new moon in station timezone

        INPUTS:
            self.astro_data           Dictionary holding full moon and new moon data

        OUTPUT:
            self.astro_data           Dictionary holding full moon and new moon data
        """

        # Define Moonrise/Moonset location properties
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])

        # Define moonrise/moonset observer properties
        self.observer.horizon = '0'
        self.observer.pressure = 1013.25

        # Calculate date of next full moon
        if 'full_moon' not in self.moon_events:
            observer_time = self.date.astimezone(Tz)
            self.observer.date = observer_time.astimezone(pytz.utc).strftime('%Y/%m/%d')
            event_time = ephem.next_full_moon(self.observer.date)
            event_time = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(Tz)
            self.moon_events['full_moon'] = event_time
        elif self.date.astimezone(Tz).date() > self.moon_events['full_moon'].date(): 
            observer_time = self.date.astimezone(Tz)
            self.observer.date = observer_time.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S')
            event_time = ephem.next_full_moon(self.observer.date)
            event_time = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(Tz)
            self.moon_events['full_moon'] = event_time
            
        # Calculate date of next new moon
        if 'new_moon' not in self.moon_events:
            observer_time = self.date.astimezone(Tz)
            self.observer.date = observer_time.astimezone(pytz.utc).strftime('%Y/%m/%d')
            event_time = ephem.next_new_moon(self.observer.date)
            event_time = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(Tz)
            self.moon_events['new_moon'] = event_time
        elif self.date.astimezone(Tz).date() > self.moon_events['new_moon'].date(): 
            observer_time = self.date.astimezone(Tz)
            self.observer.date = observer_time.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S')
            event_time = ephem.next_new_moon(self.observer.date)
            event_time = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(Tz)
            self.moon_events['new_moon'] = event_time

        # Format sunrise/sunset labels based on date of next sunrise
        self.format_event_labels('moon')

    def moon_phase(self, *largs):

        """ Calculate the moon phase for the current time in station timezone

        INPUTS:
            self.astro_data           Dictionary holding moonrise and moonset data
            Config              Station configuration

        OUTPUT:
            self.astro_data           Dictionary holding moonrise and moonset data
        """

        # Get date of next full moon in station time zone
        full_moon = self.moon_events['full_moon']

        # Get date of next new moon in station time zone
        new_moon = self.moon_events['new_moon']

        # Calculate phase of moon
        self.moon.compute(self.date.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S'))

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
        self.observer.date = self.date.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S')
        self.moon.compute(self.observer)
        self.sun.compute(self.observer)
        dLon = self.sun.az - self.moon.az
        y = math.sin(dLon) * math.cos(self.sun.alt)
        x = math.cos(self.moon.alt) * math.sin(self.sun.alt) - math.sin(self.moon.alt) * math.cos(self.sun.alt) * math.cos(dLon)
        tilt = tilt_sign * 90 - math.degrees(math.atan2(y, x))

        # Define Kivy labels and update display
        self.astro_data['Phase'] = [phase_icon, phase_text, illumination, tilt]
        self.update_astro_data()

    def format_event_labels(self, event_type):

        """ Format the sunrise/sunset labels and moonrise/moonset labels based on
        the current time of day in the station timezone

        INPUTS:
            self.astro_data     Dictionary holding sunrise/sunset and moonrise/moonset
                                data
            event_type          Flag specifying whether to format sun or moon data

        OUTPUT:
            self.astro_data           Dictionary holding moonrise and moonset data
        """

        # Get current time in Station timezone
        Tz = pytz.timezone(self.app.config['Station']['Timezone'])
        #time_now = datetime.now(pytz.utc).astimezone(Tz)
        time_now = self.date.astimezone(Tz)

        # Set time format based on user configuration
        if self.app.config['Display']['TimeFormat'] == '12 hr':
            if self.app.config['System']['Hardware'] == 'Other':
                time_format = '%#I:%M %p'
            else:
                time_format = '%-I:%M %p'
        else:
            time_format = '%H:%M'

        # Format sunrise/sunset event data
        if event_type == 'next_sunset':
            if time_now.date() == self.sun_events['next_sunset'].date():
                self.astro_data['Sunset'][1] = self.sun_events['next_sunset'].strftime(time_format)
            elif (time_now.date() + timedelta(days=1)) == self.sun_events['next_sunset'].date():
                self.astro_data['Sunset'][1] = self.sun_events['next_sunset'].strftime(time_format) + ' (+1)'
            else:
                self.astro_data['Sunset'][1] = '-'
        elif event_type == 'sun':
            if (self.sun_down_no_rise or self.sun_up_no_set):
                if self.sun_up_no_set:
                    if (self.date.date() + timedelta(days=1)) == self.sun_events['next_sunset'].date():
                        self.astro_data['Sunset'][1] = self.sun_events['next_sunset'].strftime(time_format) + ' (+1)'
                    else:
                        self.astro_data['Sunset'][1] = '-'
                    self.astro_data['Sunrise'][1]  = '-'
                if self.sun_down_no_rise:
                    if (self.date.date() + timedelta(days=1)) == self.sun_events['next_sunrise'].date():
                        self.astro_data['Sunrise'][1] = self.sun_events['next_sunrise'].strftime(time_format) + ' (+1)'
                    else:
                        self.astro_data['Sunrise'][1] = '-'
                    self.astro_data['Sunset'][1]  = '-'
                self.astro_data['Reformat']   = 0
            else:
                if time_now.date() == self.sun_events['sunrise'].date():
                    self.astro_data['Sunrise'][1] = self.sun_events['sunrise'].strftime(time_format)
                    self.astro_data['Reformat']   = 0
                elif (time_now.date() + timedelta(days=1)) == self.sun_events['sunrise'].date():
                    self.astro_data['Sunrise'][1] = self.sun_events['sunrise'].strftime(time_format) + ' (+1)'
                    self.astro_data['Reformat']   = 1
                else:
                    self.astro_data['Sunrise'][1] = '-'
                    self.astro_data['Reformat']   = 0
                if time_now.date() == self.sun_events['sunset'].date():
                    self.astro_data['Sunset'][1]  = self.sun_events['sunset'].strftime(time_format)
                    self.astro_data['Reformat']   = 0
                elif (time_now.date() + timedelta(days=1)) == self.sun_events['sunset'].date():
                    self.astro_data['Sunset'][1]  = self.sun_events['sunset'].strftime(time_format)  + ' (+1)'
                    self.astro_data['Reformat']   = 1
                else:
                    self.astro_data['Sunset'][1] = '-'
                    self.astro_data['Reformat']   = 0

        # Format moonrise/moonset data
        elif event_type == 'moon':

            # Update Moonrise Kivy Label based on date of next moonrise
            if 'rise' in self.moon_events:
                if self.moon_events['rise'] is None and self.moon_always_up:
                    self.astro_data['Moonrise'][1] = '-'
                elif self.moon_events['rise'] is None and self.moon_always_dn:
                    if self.date.date() == self.moon_events['next_rise'].date():
                        self.astro_data['Moonrise'][1] = self.moon_events['next_rise'].strftime(time_format)
                        self.moon_events['rise'] = self.moon_events['next_rise']
                    else:   
                        self.astro_data['Moonrise'][1] = 'Never up'
                elif time_now.date() == self.moon_events['rise'].date():
                    self.astro_data['Moonrise'][1] = self.moon_events['rise'].strftime(time_format)
                elif time_now.date() < self.moon_events['rise'].date():
                    self.astro_data['Moonrise'][1] = self.moon_events['rise'].strftime(time_format) + ' (+1)'
                else:
                    self.astro_data['Moonrise'][1] = self.moon_events['rise'].strftime(time_format) + ' (-1)'

            # Update Moonset Kivy Label based on date of next moonset
            if 'set' in self.moon_events:
                if self.moon_events['set'] is None and self.moon_always_dn:
                    self.astro_data['Moonset'][1] = '-'
                elif self.moon_events['set'] is None and self.moon_always_up:
                    if self.date.date() == self.moon_events['next_set'].date():
                        self.astro_data['Moonset'][1] = self.moon_events['next_set'].strftime(time_format)
                        self.moon_events['set'] = self.moon_events['next_set']
                    else:    
                        self.astro_data['Moonset'][1] = 'Always up'
                elif self.moon_events['set'] is None and self.moon_always_up:
                    self.astro_data['Moonset'][1] = '-'
                elif time_now.date() == self.moon_events['set'].date():
                    self.astro_data['Moonset'][1] = self.moon_events['set'].strftime(time_format)
                elif time_now.date() < self.moon_events['set'].date():
                    self.astro_data['Moonset'][1] = self.moon_events['set'].strftime(time_format) + ' (+1)'
                else:
                    self.astro_data['Moonset'][1] = self.moon_events['set'].strftime(time_format) + ' (-1)'

            # Update Full Moon Kivy Label based on date of next new moon
            if 'full_moon' in self.moon_events:
                if self.moon_events['full_moon'].date() == time_now.date():
                    self.astro_data['FullMoon'] = ['[color=ff8837ff]Today[/color]', self.moon_events['full_moon']]
                else:
                    self.astro_data['FullMoon'] = [self.moon_events['full_moon'].strftime('%b %d'), self.moon_events['full_moon']]

            # Update New Moon Kivy Label based on date of next new moon
            if 'new_moon' in self.moon_events:
                if self.moon_events['new_moon'].date() == time_now.date():
                    self.astro_data['NewMoon'] = ['[color=ff8837ff]Today[/color]', self.moon_events['new_moon']]
                else:
                    self.astro_data['NewMoon'] = [self.moon_events['new_moon'].strftime('%b %d'), self.moon_events['new_moon']]

        # Update display with formatted variables
        self.update_astro_data()

    def update_astro_data(self):

        """ Update display with new astro variables. Catch ReferenceErrors to
        prevent console crashing
        """

        reference_error = False
        for key, value in list(self.astro_data.items()):
            try:
                self.app.CurrentConditions.Astro[key] = value
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'astro: {system().log_time()} - Reference error')
                    reference_error = True

    def update_day_night_bar(self):

        """ Update day-night bar with new sunrise/sunset times. Catch 
        AttributeErrors to prevent console crashing
        """

        try:
            panels = getattr(self.app, 'SunriseSunsetPanel')
            for panel in panels:
                panel.draw_day_night_bar()
        except AttributeError:
            pass            
