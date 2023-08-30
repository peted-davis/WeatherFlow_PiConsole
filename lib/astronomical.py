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
        self.observer          = ephem.Observer()
        self.observer.lat      = str(self.app.config['Station']['Latitude'])
        self.observer.lon      = str(self.app.config['Station']['Longitude'])

        # Define body properties
        self.sun  = ephem.Sun()
        self.moon = ephem.Moon()

        Tz = pytz.timezone(self.app.config['Station']['Timezone'])
        self.date = Tz.localize(datetime.now().replace(hour=23, minute=1, second=0, microsecond=0, day=18, month=8))

        # Define sunrise/sunset event dictionary
        self.sun_events = {}

    def reset_astro(self):

        ''' Reset the Astro data when the station ID changes
        '''
        print("RESEST")
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

    def get_sunrise_sunset(self, *args):

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
            # midnight_local = Tz.localize(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
            # self.date += timedelta(days=1)
            midnight_local = self.date.replace(hour=0, minute=0, second=0)
            print(midnight_local)
            self.observer.date = midnight_local.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S')

        # Dusk has passed. Calculate sunset/sunrise times for tomorrow starting
        # at time of Dusk in station timezone
        else:

            # THIS IS NOT RIGHT. THE TIME SWITCH IS NOT OCCURING CORRECTLY

            # CALCULATE MIDNIGHT_LOCAL FURTHER DOWN

            tz = pytz.timezone(self.app.config['Station']['Timezone'])
            #time_now = datetime.now(pytz.utc).astimezone(tz) + timedelta(seconds=1)
            time_now = self.date + timedelta(seconds=1)
            midnight_local = self.date.replace(hour=0, minute=0, second=0)
            print(midnight_local)
            self.observer.date = time_now.astimezone(pytz.utc).strftime('%Y/%m/%d %H:%M:%S')

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
                event_time = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(Tz)
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

            self.sun_events[event] = {}
            self.sun_events[event]['time'] = event_time
            self.astro_data[event.capitalize()][0] = event_time

        # If sun is always up or never up, or sunset occurs before sunrise,
        # calculate time of next sunset or sunrise
        if ((self.sun_up_no_set or self.sun_down_no_rise)
           or (self.sun_events['sunset']['time'] < self.sun_events['sunrise']['time'])):
            self.observer.horizon = '-0:34'
            center = False
            observer_date = datetime.strptime(str(self.observer.date), '%Y/%m/%d %H:%M:%S') + timedelta(hours=12)
            self.observer.date = observer_date.strftime('%Y/%m/%d %H:%M:%S')
            if (self.sun_up_no_set
               or self.sun_events['sunset']['time'] < self.sun_events['sunrise']['time']):
                event = 'next_sunset'
                event_function = self.observer.next_setting
            elif self.sun_down_no_rise:
                event = 'next_sunrise'
                event_function = self.observer.next_rising
            while True:
                try:
                    event_time = event_function(self.sun, use_center=center)
                    event_time = pytz.utc.localize(event_time.datetime().replace(second=0, microsecond=0)).astimezone(Tz)
                    self.sun_events[event] = {}
                    self.sun_events[event]['time'] = event_time
                    self.astro_data[event] = event_time
                    break
                except (ephem.AlwaysUpError, ephem.NeverUpError):
                    observer_date = datetime.strptime(str(self.observer.date), '%Y/%m/%d %H:%M:%S') + timedelta(hours=12)
                    self.observer.date = observer_date.strftime('%Y/%m/%d %H:%M:%S')

        pprint.pprint(self.sun_events, sort_dicts=False)

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
                                    max((self.sun_events['dawn']['time'] - midnight_local).total_seconds() / 86400, 0),
                                    min((self.sun_events['dusk']['time'] - midnight_local).total_seconds() / 86400, 1)]
        elif self.sun_up_no_dusk:
            if self.sun_events['sunset']['time'] < self.sun_events['sunrise']['time']:
                self.day_night_order = ['daylight', 'twilight']
                self.twilight        = [True,
                                        max((self.sun_events['sunset']['time']  - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['sunrise']['time'] - midnight_local).total_seconds() / 86400, 1)]
                self.daylight        = [True, 0, 1]
            else:
                self.day_night_order = ['twilight', 'daylight']
                self.twilight        = [True, 0, 1]
                self.daylight        = [True,
                                        max((self.sun_events['sunrise']['time'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['sunset']['time']  - midnight_local).total_seconds() / 86400, 1)]
        else:
            if self.sun_events['dusk']['time'] < self.sun_events['dawn']['time']:
                self.day_night_order = ['twilight', 'night', 'daylight']
                self.night           = [True,
                                        max((self.sun_events['dusk']['time'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['dawn']['time'] - midnight_local).total_seconds() / 86400, 1)]
                self.twilight        = [True, 0, 1]
                self.daylight        = [True,
                                        max((self.sun_events['sunrise']['time'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['sunset']['time']  - midnight_local).total_seconds() / 86400, 1)]
            else:
                self.day_night_order = ['night', 'twilight', 'daylight']
                self.night           = [True, 0, 1]
                self.twilight        = [True,
                                        max((self.sun_events['dawn']['time'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['dusk']['time'] - midnight_local).total_seconds() / 86400, 1)]
                self.daylight        = [True,
                                        max((self.sun_events['sunrise']['time'] - midnight_local).total_seconds() / 86400, 0),
                                        min((self.sun_events['sunset']['time']  - midnight_local).total_seconds() / 86400, 1)]

        print("self.sun_down_no_dawn: ", self.sun_down_no_dawn)
        print("self.sun_down_no_rise: ", self.sun_down_no_rise)
        print("self.sun_up_no_set:    ", self.sun_up_no_set)
        print("self.sun_up_no_dusk:   ", self.sun_up_no_dusk)
        print("self.night:    ", self.night)
        print("self.twilight: ", self.twilight)
        print("self.daylight: ", self.daylight)

        # Format sunrise/sunset labels based on date of next sunrise
        self.format_event_labels('sun')
        self.sun_transit()

    def sun_transit(self, *largs):

        """ Calculate the sun transit between sunrise and sunset

        INPUTS:
            self.astro_data           Dictionary holding sunrise and sunset data
            Config              Station configuration

        OUTPUT:
            self.astro_data           Dictionary holding moonrise and moonset data
        """
        # Get current time in station time zone
        # Tz = pytz.timezone(self.app.config['Station']['Timezone'])
        # Now = datetime.now(pytz.utc).astimezone(Tz)
        # Now = Tz.localize(datetime.now().replace(day=15, month=8))
        self.date += timedelta(minutes=1)
        Now = self.date
        #print(Now)

        # Calculate sun icon position on daytime/nightime bar
        seconds_to_midnight = (Now.replace(microsecond=0) - Now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        sun_position        = seconds_to_midnight / 86400

        # If sun is always up calculate number of days until sunset
        if not self.night[0] and not self.twilight[0]:

            # Determine number of days until next sunset
            seconds_to_sunset = (self.astro_data['next_sunset'] - Now.replace(second=0, microsecond=0)).total_seconds()
            days, remainder = divmod(seconds_to_sunset, 86400)
            hours, minutes  = divmod(remainder, 3600)

            # Determine whether time of day is daytime or twilight
            if self.sun_up_no_dusk:
                description = 'Daytime'
            else:
                if Now <= self.astro_data['Dawn'][0] and Now >= self.astro_data['Dusk'][0]:
                    description = 'Twilight'
                else:
                    description = 'Daytime'

            # Define Kivy labels
            if days > 0:
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(days), 'days', '{:02.0f}'.format(hours), 'hrs', description]
            else:
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', description]
            self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]

        # If sun is never up calculate number of days until sunrise
        elif not self.daylight[0]:

            # Determine number of days until next sunrise
            seconds_to_sunrise = (self.astro_data['next_sunrise'] - Now.replace(second=0, microsecond=0)).total_seconds()
            days, remainder    = divmod(seconds_to_sunrise, 86400)
            hours, remainder   = divmod(remainder, 3600)
            minutes, remainder = divmod(remainder, 60)

            # Determine whether time of day is nighttime or twilight
            if self.sun_down_no_dawn:
                description = 'Nighttime'
            else:
                if Now >= self.astro_data['Dawn'][0] and Now <= self.astro_data['Dusk'][0]:
                    description = 'Twilight'
                else:
                    description = 'Nighttime'

            # Define Kivy labels
            if days > 0:
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunrise[/color]', '{:02.0f}'.format(days), 'days', '{:02.0f}'.format(hours), 'hrs', description]
            else:
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunrise[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', description]
            self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # If there is no night
        elif not self.night[0] and self.twilight[0] and self.daylight[0]:

            # and time is between sunrise and sunset, calculate time until next
            # sunset
            if (self.astro_data['Sunrise'][0] < self.astro_data['Sunset'][0]
               and Now >= self.astro_data['Sunrise'][0] and Now <= self.astro_data['Sunset'][0]):

                # Determine number of daylight hours remaining
                seconds_to_sunset  = (self.astro_data['Sunset'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
                hours, remainder = divmod(seconds_to_sunset, 3600)
                minutes, seconds = divmod(remainder, 60)

                # Define Kivy labels
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Daytime']
                self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]
            elif (self.astro_data['Sunrise'][0] > self.astro_data['Sunset'][0]
                  and Now <= self.astro_data['Sunset'][0]):

                # Determine number of daylight hours remaining
                seconds_to_sunset  = (self.astro_data['Sunset'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
                hours, remainder = divmod(seconds_to_sunset, 3600)
                minutes, seconds = divmod(remainder, 60)

                # Define Kivy labels
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Daytime']
                self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]
            elif (self.astro_data['Sunrise'][0] > self.astro_data['Sunset'][0]
                  and Now >= self.astro_data['Sunrise'][0]):

                # Determine number of daylight hours remaining
                seconds_to_sunset  = (self.sun_events['next_sunset']['time'] - Now.replace(second=0, microsecond=0)).total_seconds()
                hours, remainder = divmod(seconds_to_sunset, 3600)
                minutes, seconds = divmod(remainder, 60)

                # Define Kivy labels
                self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Daytime']
                self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]

            # Else, calculate time until next sunrise
            else:

                # Determine number of twilight hours remaining
                seconds_to_sunrise  = (self.astro_data['Sunrise'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
                hours, remainder  = divmod(seconds_to_sunrise, 3600)
                minutes, seconds  = divmod(remainder, 60)

                # Define Kivy labels
                self.astro_data['sunEvent'] = ['[color=FF8841FF]Sunrise[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Twilight']
                self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # If time is before dawn, calculate number of night time hours remaining
        elif Now < self.astro_data['Dawn'][0]:

            # Determine number of nighttime hours remaining
            seconds_to_dawn    = (self.astro_data['Dawn'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder = divmod(seconds_to_dawn, 3600)
            minutes, seconds = divmod(remainder, 60)

            # Define Kivy labels
            self.astro_data['sunEvent'] = ['[color=00A4B4FF]Dawn[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Nighttime']
            self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # If time is before sunrise, calculate number of dawn hours remaining
        elif Now < self.astro_data['Sunrise'][0]:

            # Determine number of nighttime hours remaining
            seconds_to_sunrise  = (self.astro_data['Sunrise'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder  = divmod(seconds_to_sunrise, 3600)
            minutes, seconds  = divmod(remainder, 60)

            # Define Kivy labels
            self.astro_data['sunEvent'] = ['[color=FF8841FF]Sunrise[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Dawn']
            self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # If time is between sunrise and sunset, calculate number of daylight hours
        # remaining
        elif Now >= self.astro_data['Sunrise'][0] and Now <= self.astro_data['Sunset'][0]:

            # Determine number of daylight hours remaining
            seconds_to_sunset  = (self.astro_data['Sunset'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder = divmod(seconds_to_sunset, 3600)
            minutes, seconds = divmod(remainder, 60)

            # Define Kivy labels
            self.astro_data['sunEvent'] = ['[color=F05E40FF]Sunset[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Daytime']
            self.astro_data['sunIcon']  = ['sunUp', 0, sun_position]

        # If time after sunset, calculate number of dusk hours remaining
        elif Now < self.astro_data['Dusk'][0]:

            # Determine hours and minutes left until sunrise
            secondsToNightfall  = (self.astro_data['Dusk'][0] - Now.replace(second=0, microsecond=0)).total_seconds()
            hours, remainder    = divmod(secondsToNightfall, 3600)
            minutes, seconds    = divmod(remainder, 60)

            # Define Kivy labels
            self.astro_data['sunEvent'] = ['[color=00A4B4FF]Nightfall[/color]', '{:02.0f}'.format(hours), 'hrs', '{:02.0f}'.format(minutes), 'mins', 'Dusk']
            self.astro_data['sunIcon']  = ['-', 1, sun_position]

        # Update display
        self.update_display()
        #print(self.astro_data['sunEvent'])
        #try:
        panels = getattr(self.app, 'SunriseSunsetPanel')
        for panel in panels:
            panel.draw_day_night_bar()
        #except AttributeError:
        #    pass

        # Once dusk has passed calculate new sunrise/sunset times

        # IF DUSK IS PAST MIDNIGHT AND SUNSET HAS PASSED


        if self.night[0] and not self.daylight[0]:
            #print("RESET AT MIDNIGHT")
            if Now.replace(second=0, microsecond=0).time() == time(0, 0, 0):
                self.get_sunrise_sunset()
        elif not self.night[0] and self.twilight[0] and self.daylight[0]:
            if (self.astro_data['Sunset'][0].date() > Now.date()
               or self.astro_data['Sunset'][0] < self.astro_data['Sunrise'][0]):
                #print("RESET AT MIDNIGHT")
                if Now.replace(second=0, microsecond=0).time() == time(0, 0, 0):
                    self.get_sunrise_sunset()
            else:
                #print("RESET AT SUNSET")
                if Now.replace(microsecond=0) >= self.astro_data['Sunset'][0]:
                    self.get_sunrise_sunset()
        elif self.night[0] and self.twilight[0] and self.daylight[0]:
            if (self.astro_data['Dusk'][0].date() > Now.date()
               or self.astro_data['Dusk'][0] < self.astro_data['Dawn'][0]):
                #print("RESET AT SUNSET")
                if Now.replace(microsecond=0) >= self.astro_data['Sunset'][0]:
                    self.get_sunrise_sunset()
            else:
                #print("RESET AT DUSK")
                if Now.replace(microsecond=0) >= self.astro_data['Dusk'][0]:
                    self.get_sunrise_sunset()



        #elif self.night[0]:
        #    if (self.astro_data['Dusk'][0].date() > Now.date()
        #       or self.astro_data['Dusk'][0] < self.astro_data['Dawn'][0]):
        #        if Now.replace(microsecond=0) >= self.astro_data['Sunset'][0]:
        #            self.get_sunrise_sunset()

        #elif Now.replace(microsecond=0) >= self.astro_data['Dusk'][0]:
        #    self.get_sunrise_sunset()


        #     if Now.replace(microsecond=0) >= self.astro_data['Sunset'][0]:
        #         self.sunrise_sunset()
        # elif not self.no_sunrise and not self.no_sunset:
        #if Now.replace(microsecond=0) >= self.astro_data['Dusk'][0]:
        #    self.get_sunrise_sunset()
        # if self.no_sunrise and Now.replace(second=0).replace(microsecond=0).time() == time(0, 0, 0):
        #    pass

        # # Once moonset has passed, calculate new moonrise/moonset times
        # if Now.replace(microsecond=0) > self.astro_data['Moonset'][0]:
        #     self.moonrise_moonset()

        # # At midnight update sunrise/sunset times
        # if self.astro_data['Reformat'] and Now.replace(second=0).replace(microsecond=0).time() == time(0, 0, 0):
        #    self.format_labels('sun')
        #    self.format_labels('moon')

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

    def format_event_labels(self, type):

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
        #Now = datetime.now(pytz.utc).astimezone(Tz)
        Now = self.date

        # Set time format based on user configuration
        if self.app.config['Display']['TimeFormat'] == '12 hr':
            if self.app.config['System']['Hardware'] == 'Other':
                time_format = '%#I:%M %p'
            else:
                time_format = '%-I:%M %p'
        else:
            time_format = '%H:%M'

        # Format sunrise/sunset event data
        if type == 'sun':
            if (self.sun_down_no_rise or self.sun_up_no_set):
                self.astro_data['Sunrise'][1] = '-'
                self.astro_data['Sunrise'][1] = '-'
                self.astro_data['Reformat']   = 0
            else:
                if Now.date() == self.astro_data['Sunrise'][0].date():
                    self.astro_data['Sunrise'][1] = self.astro_data['Sunrise'][0].strftime(time_format)
                else:
                    self.astro_data['Sunrise'][1] = self.astro_data['Sunrise'][0].strftime(time_format) + ' (+1)'
                if Now.date() == self.astro_data['Sunset'][0].date():
                    self.astro_data['Sunset'][1]  = self.astro_data['Sunset'][0].strftime(time_format)
                else:
                    self.astro_data['Sunset'][1]  = self.astro_data['Sunset'][0].strftime(time_format)  + ' (+1)'

        # Format moonrise/moonset data
        elif type == 'moon':

            # Update Moonrise Kivy Label based on date of next moonrise
            if Now.date() == self.astro_data['Moonrise'][0].date():
                self.astro_data['Moonrise'][1] = self.astro_data['Moonrise'][0].strftime(time_format)
            elif Now.date() < self.astro_data['Moonrise'][0].date():
                self.astro_data['Moonrise'][1] = self.astro_data['Moonrise'][0].strftime(time_format) + ' (+1)'
            else:
                self.astro_data['Moonrise'][1] = self.astro_data['Moonrise'][0].strftime(time_format) + ' (-1)'

            # Update Moonset Kivy Label based on date of next moonset
            if Now.date() == self.astro_data['Moonset'][0].date():
                self.astro_data['Moonset'][1] = self.astro_data['Moonset'][0].strftime(time_format)
            elif Now.date() < self.astro_data['Moonset'][0].date():
                self.astro_data['Moonset'][1] = self.astro_data['Moonset'][0].strftime(time_format) + ' (+1)'
            else:
                self.astro_data['Moonset'][1] = self.astro_data['Moonset'][0].strftime(time_format) + ' (-1)'

            # Update New Moon Kivy Label based on date of next new moon
            if self.astro_data['FullMoon'][1].date() == Now.date():
                self.astro_data['FullMoon'] = ['[color=ff8837ff]Today[/color]', self.astro_data['FullMoon'][1]]

            # Update Full Moon Kivy Label based on date of next full moon
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
        for key, value in list(self.astro_data.items()):
            try:
                self.app.CurrentConditions.Astro[key] = value
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'astro: {system().log_time()} - Reference error')
                    reference_error = True
