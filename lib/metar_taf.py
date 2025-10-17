""" Returns the METAR/TAF variables required by the Raspberry Pi
Python app for WeatherFlow Tempest and Smart Home Weather stations.
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
from lib.system import system
from lib        import observation_format as observation
from lib        import derived_variables  as derive
from lib        import properties

# Import required Kivy modules
from kivy.network.urlrequest import UrlRequest
from kivy.logger             import Logger
from kivy.clock              import Clock
from kivy.app                import App

# Import required system modules
from datetime   import datetime, timedelta, time
import time     as UNIX
import certifi
import bisect
import pytz


class metar_taf():

    def __init__(self):
        self.app = App.get_running_app()
        self.metar_taf_data = properties.metar_taf()

    def reset_metar_taf(self):

        """ Reset the METAR/TAF forecast displayed on screen to default values 
        and fetch new METAR/TAF data from the CheckWX API
        """

        # Reset the METAR/TAF data and schedule new METAR/TAF data to be 
        # fetched
        self.metar_taf_data = properties.metar_taf()
        self.update_display()
        Clock.schedule_once(self.fetch_metar_taf)

    def fetch_metar_taf(self, *largs):

        """ Fetch the METAR/TAF forecast data using the CheckWX API
        """

        # Fetch latest TAF data
        if int(self.app.config['System']['rest_api']):
            self.fetch_taf_data()
            
        # Fetch latest METAR data
        if int(self.app.config['System']['rest_api']):
            self.fetch_metar_data()

    def fetch_metar_data(self, *largs):

        """ Fetch the METAR forecast data using the CheckWX API
        """            
        # Fetch latest METAR data
        if int(self.app.config['System']['rest_api']):
            URL    = 'https://api.checkwx.com/metar/lat/{}/lon/{}/radius/100/decoded'
            URL    = URL.format(self.app.config['Station']['Latitude'], self.app.config['Station']['Longitude'])
            header = {'X-API-Key': self.app.config['Keys']['CheckWX']}
            UrlRequest(URL,
                       on_success=self.success_metar,
                       on_failure=self.fail_metar,
                       on_error=self.fail_metar,
                       timeout=int(self.app.config['System']['Timeout']),
                       ca_file=certifi.where(),
                       req_headers=header)  
        
    def fetch_taf_data(self, *largs):

        """ Fetch the TAF forecast data using the CheckWX API
        """            
        # Fetch latest TAF data
        if int(self.app.config['System']['rest_api']):
            URL    = 'https://api.checkwx.com/taf/lat/{}/lon/{}/radius/100/decoded'   
            URL    = URL.format(self.app.config['Station']['Latitude'], self.app.config['Station']['Longitude'])
            header = {'X-API-Key': self.app.config['Keys']['CheckWX']}
            UrlRequest(URL,
                       on_success=self.success_taf,
                       on_failure=self.fail_taf,
                       on_error=self.fail_taf,
                       timeout=int(self.app.config['System']['Timeout']),
                       ca_file=certifi.where(),
                       req_headers=header)         

    def schedule_metar_taf(self, dt):

        """ Schedule new METAR/TAF forecast to be fetched from the CheckWX API
        at the top of the next hour
        """

        # Calculate next forecast time for the top of the next hour
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        now = datetime.now(pytz.utc).astimezone(Tz)
        sched_time = Tz.localize(datetime.combine(now.date(), time(now.hour, 0, 0)) + timedelta(hours=1))

        # Schedule next forecast
        seconds_sched = (sched_time - now).total_seconds()
        self.app.schedule.taf_metar_download.cancel()
        self.app.schedule.taf_metar_download = Clock.schedule_once(self.fetch_metar_taf, seconds_sched)

    def success_metar(self, request, response):

        """ Sucessfully fetched METAR data from the CheckWXAPI. Parse METAR 
        response

        INPUTS:
            request             Urlrequest object
            response            Urlrequest response
        """

        # Parse the latest daily and hourly weather forecast data
        self.metar_taf_data['metar'] = response['data']
        self.parse_metar_taf('metar')

    def fail_metar(self, *largs):

        """ Failed to fetch METAR data from the CheckWX API. Reschedule fetch_metar 
        in 300 seconds

        INPUTS:
            request             Urlrequest object
            response            Urlrequest response
        """

        # Set METAR forecast variables to blank and indicate to user that METAR 
        # is unavailable
        self.metar_taf_data['metar_location_string']    = "METAR observation currently unavailable"
        self.metar_taf_data['metar_timing_string']      = ""
        self.metar_taf_data['metar_observation_string'] = ""

        # Update display
        self.update_display()

        # Schedule new METAR data to be downloaded in 5 minutes
        self.app.schedule.taf_metar_download.cancel()
        self.app.schedule.taf_metar_download = Clock.schedule_once(self.fetch_metar_taf, timedelta(minutes=5).total_seconds())        

    def success_taf(self, request, response):

        """ Sucessfully fetched METAR data from the CheckWXAPI. Parse TAF 
        response

        INPUTS:
            request             Urlrequest object
            response            Urlrequest response
        """

        # Parse the latest daily and hourly weather forecast data
        self.metar_taf_data['taf'] = response['data']
        self.parse_metar_taf('taf')        

    def fail_taf(self, *largs):

        """ Failed to fetch TAF data from the CheckWX API. Reschedule fetch_taf 
        in 300 seconds

        INPUTS:
            request             Urlrequest object
            response            Urlrequest response
        """

        # Set TAF forecast variables to blank and indicate to user that TAF is
        # unavailable
        self.metar_taf_data['taf_location_string'] = "TAF forecast currently unavailable"
        self.metar_taf_data['taf_timing_string']   = ""
        self.metar_taf_data['taf_forecast_string'] = ""

        # Update display
        self.update_display()

        # Schedule new TAF data to be downloaded in 5 minutes
        self.app.schedule.taf_metar_download.cancel()
        self.app.schedule.taf_metar_download = Clock.schedule_once(self.fetch_metar_taf, timedelta(minutes=5).total_seconds())

    def parse_metar_taf(self, type):

        """ Parse the latest daily and hourly weather forecast from the
        WeatherFlow BetterForecast API and format for display based on user
        specified units
        """

        # Get station time zone
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])
        now = datetime.now(pytz.utc).astimezone(Tz)

        # Set time format based on user configuration
        if 'TimeFormat' in self.app.config['Display'] and 'DateFormat' in self.app.config['Display']:
            if self.app.config['Display']['TimeFormat'] == '12 hr':
                if self.app.config['System']['Hardware'] == 'Other':
                    time_format = '%#I:%M %p'
                else:
                    time_format = '%-I:%M %p'
            else:
                time_format = '%H:%M'
            if self.app.config['Display']['DateFormat']  == 'Mon, Jan 01 0000':
                date_format = '%a, %b %d %Y'
            elif self.app.config['Display']['DateFormat'] == 'Monday, 01 Jan 0000':
                date_format = '%A, %d %b %Y'
            elif self.app.config['Display']['DateFormat'] == 'Monday, Jan 01 0000':
                date_format = '%A, %b %d %Y'
            else:
                date_format = '%a, %d %b %Y'

        # PARSE METAR OBSERVATION DATA FROM CHECKWX API
        # ----------------------------------------------------------------------
        # Extract METAR dictionary
        if type == 'metar':
            if 'metar' in self.metar_taf_data:
                metar_data = self.metar_taf_data['metar']
            else:
                return
            
            # Define required variables
            metar_cloud_type  = []
            metar_cloud_code  = []
            metar_cloud_level = []

            # Extract all METAR data from CheckWX API JSON object for closest 
            # location with a observation issued less than two hours ago
            try:
                for METAR in metar_data:
                    issued_time = datetime.fromisoformat(METAR['observed'] + "+00:00").astimezone(Tz)
                    if (now - issued_time).total_seconds() <= 1*3600:
                        metar_data = METAR
                        break

                # Extract location and timing information   
                metar_location    = metar_data['station']['location']
                metar_issued_time = datetime.fromisoformat(metar_data['observed'] + "+00:00").astimezone(Tz)

                # Extract wind observation variables
                metar_wind_direction = [metar_data['wind']['degrees']   if 'wind' in metar_data and 'degrees'   in metar_data['wind'] else None, 'degrees']
                metar_wind_speed     = [metar_data['wind']['speed_mps'] if 'wind' in metar_data and 'speed_mps' in metar_data['wind'] else None, 'mps']
                metar_wind_gust      = [metar_data['wind']['gust_mps']  if 'wind' in metar_data and 'gust_mps'  in metar_data['wind'] else None, 'mps']    

                # Extract visibility observation variables
                metar_visibility = [metar_data['visibility']['meters_text'].replace(',', ''), 'm'] if self.app.config['Units']['Distance'] == 'km' else [metar_data['visibility']['miles_text'].replace(',', ''), 'miles']
        
                # Extract cloud observation variables
                for ii, cloud in enumerate(metar_data['clouds']):
                    metar_cloud_type.append(cloud['text'])
                    metar_cloud_code.append(cloud['code'])
                    if metar_cloud_code[ii] not in ['CAVOK', 'CLR']:
                        metar_cloud_level.append([cloud['base_meters_agl'] if 'visibility' in metar_data else None, 'm'] if self.app.config['Units']['Distance'] == 'km' else 
                                                [cloud['base_feet_agl']   if 'visibility' in metar_data else None, 'ft'])
                    else:
                        metar_cloud_level.append(None)

                # Extract barometer, dewpoint and humidity
                metar_baromter = [metar_data['barometer']['mb']     if 'barometer' in metar_data else None, 'mb']
                metar_dewpoint = [metar_data['dewpoint']['celsius'] if 'dewpoint'  in metar_data else None, 'c']
                metar_humidity = [metar_data['humidity']['percent'] if 'humidity'  in metar_data else None, '%']

                # Convert METAR units as required
                metar_wind_direction  = observation.units(metar_wind_direction,  self.app.config['Units']['Direction'])
                metar_wind_speed      = observation.units(metar_wind_speed,      self.app.config['Units']['Wind'])
                metar_wind_gust       = observation.units(metar_wind_gust,       self.app.config['Units']['Wind'])
                metar_baromter        = observation.units(metar_baromter,        self.app.config['Units']['Pressure'])
                metar_dewpoint        = observation.units(metar_dewpoint,        self.app.config['Units']['Temp'])
                metar_humidity        = observation.units(metar_humidity,        self.app.config['Units']['Other'])
                metar_wind_direction  = observation.format(metar_wind_direction, 'Direction')
                metar_wind_speed      = observation.format(metar_wind_speed,     'Wind')
                metar_wind_gust       = observation.format(metar_wind_gust,      'Wind')
                metar_baromter        = observation.format(metar_baromter,       'Pressure')
                metar_dewpoint        = observation.format(metar_dewpoint,       'Temp')
                metar_humidity        = observation.format(metar_humidity,       'Humidity')            
                
                # print(metar_location, flush=True)
                # print(metar_issued_time, flush=True)
                # print(metar_wind_direction, flush=True)
                # print(metar_wind_speed, flush=True)
                # print(metar_wind_gust, flush=True)
                # print(metar_visibility, flush=True)
                #print(metar_cloud_type, flush=True)
                #print(metar_cloud_code, flush=True)
                #print(metar_cloud_level, flush=True)
                # print(metar_baromter, flush=True)
                # print(metar_dewpoint, flush=True)
                # print(metar_humidity, flush=True)

                # Construct main observation METAR string
                metar_observation_string = ""
                location_string          = (f"METAR for {metar_location}") 
                timing_string            = (f"Issued at {metar_issued_time.strftime(time_format)} on {metar_issued_time.strftime(date_format)}")
                wind_direction_string    = (f"Wind {metar_wind_direction[0]}" if self.app.config['Units']['Direction'] == 'cardinal' else f"Wind {metar_wind_direction[0] + metar_wind_direction[1]}")
                wind_speed_string        = (f" at {metar_wind_speed[0]} {metar_wind_speed[1]}")
                wind_gust_string         = (f" gusting {metar_wind_gust[0]} {metar_wind_gust[1]}" if metar_wind_gust[0] != '-' else f"")
                visibility_string        = (f", {metar_visibility[0].lower()} {metar_visibility[1]} visibility" if metar_visibility[0] is not None else f"")
                barometer_string         = (f"barometer {metar_baromter[0].lower()}{metar_baromter[1]}, " if metar_baromter[0] is not None else f"")
                humidty_string           = (f"humidity {metar_humidity[0].lower()}{metar_humidity[1]}, "  if metar_humidity[0] is not None else f"")
                dewpoint_string          = (f"dew point {metar_dewpoint[0].lower()}{metar_dewpoint[1]}."  if metar_dewpoint[0] is not None else f"")
                if metar_cloud_type:
                    for ii, cloud in enumerate(metar_cloud_type):
                        if cloud is not None:
                            if ii == 0 and 'clear' in metar_cloud_type[ii].lower():
                                cloud_string = ", "
                            elif ii == 0:
                                cloud_string = ", cloud "
                            cloud_string = (cloud_string + 
                                            f"{metar_cloud_type[ii].lower()}" + 
                                           (f" at {metar_cloud_level[ii][0]} {metar_cloud_level[ii][1]}, " if 'clear' not in metar_cloud_type[ii].lower() else f", "))
                        else:
                            cloud_string = f""
                else:
                    cloud_string = f""  
                metar_observation_string = (wind_direction_string + 
                                            wind_speed_string + 
                                            wind_gust_string +
                                            visibility_string + 
                                            cloud_string +
                                            barometer_string +
                                            humidty_string +
                                            dewpoint_string + "\n")

                # Define and format labels
                self.metar_taf_data['metar_location_string']    = location_string
                self.metar_taf_data['metar_timing_string']      = timing_string
                self.metar_taf_data['metar_observation_string'] = metar_observation_string

                # Update display
                self.update_display()

                # Schedule new forecast
                Clock.schedule_once(self.schedule_metar_taf)

            # Unable to extract METAR data from JSON object. Set METAR
            # variables to blank and indicate to user that forecast is 
            # unavailable
            except (IndexError, KeyError, ValueError, TypeError):
                Clock.schedule_once(self.fail_metar)    

        # PARSE TAF FORECAST DATA FROM CHECKWX API
        # ----------------------------------------------------------------------
        # Extract TAF dictionary
        if type == 'taf':
            if 'taf' in self.metar_taf_data:
                taf_data = self.metar_taf_data['taf']
            else:
                return

            # Define required variables
            main_cloud_code         = []
            main_cloud_type         = []
            main_cloud_level        = []
            trend_from_time         = []
            trend_to_time           = []
            trend_type_text         = []
            trend_wind_direction    = []
            trend_wind_speed        = []
            trend_wind_gust         = []
            trend_visibility        = []
            trend_cloud_code        = []
            trend_cloud_type        = []
            trend_cloud_level       = []
            trend_conditions_text   = []
            trend_conditions_code   = []

            # Extract all TAF data from CheckWX API JSON object for closest 
            # location with a forecast issued less than 6 hours ago
            try:
                for taf in taf_data:
                    issued_time = datetime.fromisoformat(taf['timestamp']['issued'] + "+00:00").astimezone(Tz)
                    if (now - issued_time).total_seconds() <= 6*3600:
                        taf_data = taf
                        break

                # Extract location and timing information   
                location    = taf_data['station']['location']
                issued_time = datetime.fromisoformat(taf_data['timestamp']['issued'] + "+00:00").astimezone(Tz)
                to_time     = datetime.fromisoformat(taf_data['timestamp']['to'] + "+00:00").astimezone(Tz)

                # Extract each individual forecast in TAF
                for forecast in taf_data['forecast']:
                    
                    # Parse main forecast data from TAF
                    if 'change' not in forecast:

                        # Extract wind forecast variables
                        main_wind_direction = [forecast['wind']['degrees']   if 'wind' in forecast and 'degrees'   in forecast['wind'] else None, 'degrees']
                        main_wind_speed     = [forecast['wind']['speed_mps'] if 'wind' in forecast and 'speed_mps' in forecast['wind'] else None, 'mps']
                        main_wind_gust      = [forecast['wind']['gust_mps']  if 'wind' in forecast and 'gust_mps'  in forecast['wind'] else None, 'mps']    

                        # Extract visibility forecast variables
                        main_visibility = ([forecast['visibility']['meters_text'].replace(',', '') if 'visibility' in forecast else None, 'm'] if self.app.config['Units']['Distance'] == 'km' else 
                                            [forecast['visibility']['miles_text'].replace(',', '')  if 'visibility' in forecast else None, 'miles' 'miles'])

                        # Extract cloud forecast variables
                        for ii, cloud in enumerate(forecast['clouds']):
                            main_cloud_code.append(cloud['code'])
                            main_cloud_type.append(cloud['text'])
                            if main_cloud_code[ii] not in ['CAVOK', 'CLR', 'SKC']:
                                main_cloud_level.append([cloud['base_meters_agl'] if 'visibility' in forecast else None, 'm'] if self.app.config['Units']['Distance'] == 'km' else 
                                                        [cloud['base_feet_agl']   if 'visibility' in forecast else None, 'ft'])
                            else:
                                main_cloud_level.append(None)

                    # Parse trend forecast data from TAF
                    elif 'change' in forecast:

                        # Extract timing information
                        trend_from_time.append(datetime.fromisoformat(forecast['timestamp']['from'] + "+00:00").astimezone(Tz))
                        trend_to_time.append(datetime.fromisoformat(forecast['timestamp']['to']   + "+00:00").astimezone(Tz))

                        # Extract trend type variable
                        trend_type_text.append(forecast['change']['indicator']['text'])

                        # Extract wind forecast variables
                        trend_wind_direction.append([forecast['wind']['degrees'] if 'wind' in forecast and 'degrees'   in forecast['wind'] else None, 'degrees'])
                        trend_wind_speed.append([forecast['wind']['speed_mps']   if 'wind' in forecast and 'speed_mps' in forecast['wind'] else None, 'mps'])
                        trend_wind_gust.append([forecast['wind']['gust_mps']     if 'wind' in forecast and 'gust_mps'  in forecast['wind'] else None, 'mps']  )  

                        # Extract visibility forecast variables
                        trend_visibility.append([forecast['visibility']['meters_text'].replace(',', '') if 'visibility' in forecast else None, 'm'] if self.app.config['Units']['Distance'] == 'km' else 
                                                [forecast['visibility']['miles_text'].replace(',', '')  if 'visibility' in forecast else None, 'miles'])

                        # Extract cloud forecast variables
                        cloud_type  = []
                        cloud_level = []
                        cloud_code  = []
                        if 'clouds' in forecast:
                            for ii, cloud in enumerate(forecast['clouds']):
                                cloud_code.append(cloud['code'])
                                cloud_type.append(cloud['text'])
                                if cloud_code[ii] not in ['CAVOK', 'CLR', 'SKC']:
                                    cloud_level.append([cloud['base_meters_agl'] if 'base_meters_agl' in cloud else None, 'm'] if self.app.config['Units']['Distance'] == 'km' else 
                                                       [cloud['base_feet_agl']   if 'base_feet_agl'   in cloud else None, 'ft'])
                                else:
                                    cloud_level.append(None)
                        else:
                            cloud_code.append(None)
                            cloud_type.append(None)
                            cloud_level.append([None, 'm'])
                        trend_cloud_code.append(cloud_code)     
                        trend_cloud_type.append(cloud_type)
                        trend_cloud_level.append(cloud_level)

                        # Extract conditions forecast
                        conditions_text = []
                        conditions_code = []
                        if 'conditions' in forecast:
                            for condition in forecast['conditions']:
                                conditions_text.append(condition['text'] if 'text' in condition else None)
                                conditions_code.append(condition['code'] if 'code' in condition else None)
                        trend_conditions_text.append(conditions_text)
                        trend_conditions_code.append(conditions_text)

                # Convert TAF units as required
                main_wind_direction  = observation.units(main_wind_direction,  self.app.config['Units']['Direction'])
                main_wind_speed      = observation.units(main_wind_speed,      self.app.config['Units']['Wind'])
                main_wind_gust       = observation.units(main_wind_gust,       self.app.config['Units']['Wind'])
                main_wind_direction  = observation.format(main_wind_direction, 'Direction')
                main_wind_speed      = observation.format(main_wind_speed,     'Wind')
                main_wind_gust       = observation.format(main_wind_gust,      'Wind')
                for ii, jj in enumerate(trend_wind_direction):
                    trend_wind_direction[ii] = observation.units(trend_wind_direction[ii],  self.app.config['Units']['Direction'])
                    trend_wind_speed[ii]     = observation.units(trend_wind_speed[ii],      self.app.config['Units']['Wind'])
                    trend_wind_gust[ii]      = observation.units(trend_wind_gust[ii],       self.app.config['Units']['Wind'])            
                    trend_wind_direction[ii] = observation.format(trend_wind_direction[ii], 'Direction')
                    trend_wind_speed[ii]     = observation.format(trend_wind_speed[ii],     'Wind')
                    trend_wind_gust[ii]      = observation.format(trend_wind_gust[ii],      'Wind')

                # print(issued_time, flush=True)
                # print(from_time, flush=True)
                # print(to_time, flush=True)
                # print(main_wind_direction, flush=True)
                # print(main_wind_speed, flush=True)
                # print(main_wind_gust, flush=True)
                # print(main_visibility, flush=True)
                # print(main_cloud_type, flush=True)
                # print(main_cloud_level, flush=True)
                #print(trend_type_text, flush=True)      
                # print(trend_from_time, flush=True)
                # print(trend_to_time, flush=True)   
                #print(trend_wind_direction, flush=True)
                #print(trend_wind_speed, flush=True)
                #print(trend_wind_gust, flush=True)  
                # print(trend_visibility, flush=True)
                #print(trend_cloud_code, flush=True) 
                #print(trend_cloud_type, flush=True)
                #print(trend_cloud_level, flush=True) 
                #print(trend_conditions, flush=True) 

                # Construct main forecast taf string
                taf_forecast_string   = ""
                location_string       = (f"TAF for {location}") 
                timing_string         = (f"Issued at {issued_time.astimezone(Tz).strftime(time_format)} on {issued_time.strftime(date_format)} "
                                         f"and valid until {to_time.astimezone(Tz).strftime(time_format)} on {to_time.astimezone(Tz).strftime(date_format)}\n")
                wind_direction_string = (f"Wind {main_wind_direction[0]}" if self.app.config['Units']['Direction'] == 'cardinal' else f"Wind {main_wind_direction[0] + main_wind_direction[1]}")
                wind_speed_string     = (f" at {main_wind_speed[0]} {main_wind_speed[1]}")
                wind_gust_string      = (f" gusting {main_wind_gust[0]} {main_wind_gust[1]}" if main_wind_gust[0] != '-' else f"")
                visibility_string     = (f", {main_visibility[0].lower()} {main_visibility[1]} visibility" if main_visibility[0] is not None else f"")
                if main_cloud_type:
                    for ii, cloud in enumerate(main_cloud_type):
                        if cloud is not None:
                            if ii == 0 and main_cloud_code[ii] in ['CAVOK', 'CLR', 'SKC']:
                                cloud_string = ", "
                            elif ii == 0:
                                cloud_string = ", cloud "
                            else:
                                cloud_string = cloud_string + ", "    
                            cloud_string = (cloud_string + 
                                            f"{main_cloud_type[ii].lower()}" + 
                                           (f" at {main_cloud_level[ii][0]} {main_cloud_level[ii][1]}" if main_cloud_code[ii] not in ['CAVOK', 'CLR', 'SKC'] else f""))
                        else:
                            cloud_string = f""
                else:
                    cloud_string = f""
                taf_forecast_string = (taf_forecast_string +
                                    wind_direction_string + 
                                    wind_speed_string + 
                                    wind_gust_string +
                                    visibility_string + 
                                    cloud_string + "\n\n")

                # Construct trend forecast taf string
                for ii, type in enumerate(trend_type_text):
                    trend_time_string           = (f"{type} {trend_from_time[ii].astimezone(Tz).strftime(time_format)} {trend_from_time[ii].astimezone(Tz).strftime('%d %b')} until " 
                                                f"{trend_to_time[ii].astimezone(Tz).strftime(time_format)} {trend_to_time[ii].astimezone(Tz).strftime('%d %b')}")
                    trend_wind_direction_string = ((f", wind {trend_wind_direction[ii][0]}" if self.app.config['Units']['Direction'] == 'cardinal' else 
                                                    f"Wind {trend_wind_direction[ii][0] + trend_wind_direction[ii][1]}") if trend_wind_direction[ii][0] != '-' else f"")
                    trend_wind_speed_string     = (f" at {trend_wind_speed[ii][0]} {trend_wind_speed[ii][1]}" if trend_wind_speed[ii][0] != '-' else f"")
                    trend_gust_speed_string     = (f" gusting {trend_wind_gust[ii][0]} {trend_wind_gust[ii][1]}" if trend_wind_gust[ii][0] != '-' else f"")
                    trend_visibility_string     = (f", {trend_visibility[ii][0].lower()} {trend_visibility[ii][1]} visibility" if trend_visibility[ii][0] is not None else f"")
                    if trend_cloud_type[ii]:
                        for jj, cloud in enumerate(trend_cloud_type[ii]):
                            if cloud is not None:
                                if jj == 0 and trend_cloud_code[ii][jj] in ['CAVOK', 'CLR', 'SKC']:
                                    trend_cloud_string = ", "
                                elif jj == 0:
                                    trend_cloud_string = ", cloud "
                                else:
                                    trend_cloud_string = trend_cloud_string + ", "
                                trend_cloud_string = (trend_cloud_string + 
                                                      f"{trend_cloud_type[ii][jj].lower()}" + 
                                                     (f" at {trend_cloud_level[ii][jj][0]} {trend_cloud_level[ii][jj][1]}" if trend_cloud_code[ii][jj] not in ['CAVOK', 'CLR', 'SKC'] else f""))
                            else:
                                trend_cloud_string = f""
                    else:
                        trend_cloud_string = f""
                    if trend_conditions_text[ii]:
                        for jj, condition in enumerate(trend_conditions_text[ii]):
                            if condition is not None:
                                if jj == 0:
                                    trend_condition_string = ", conditions "
                                else:
                                    trend_condition_string = trend_condition_string + ", "
                                trend_condition_string = trend_condition_string + f"{condition.lower()}"
                            else:
                                trend_condition_string = f""
                    else:
                                trend_condition_string = f""            
                    taf_forecast_string = (taf_forecast_string +
                                        trend_time_string + 
                                        trend_wind_direction_string + 
                                        trend_wind_speed_string + 
                                        trend_gust_speed_string + 
                                        trend_visibility_string + 
                                        trend_cloud_string +
                                        trend_condition_string + "\n\n")

                # Define and format labels
                self.metar_taf_data['taf_location_string'] = location_string
                self.metar_taf_data['taf_timing_string']   = timing_string
                self.metar_taf_data['taf_forecast_string'] = taf_forecast_string

                # Update display
                self.update_display()

                # Schedule new forecast
                Clock.schedule_once(self.schedule_metar_taf)

            # Unable to extract TAF data from JSON object. Set forecast
            # variables to blank and indicate to user that forecast is 
            # unavailable
            except (IndexError, KeyError, ValueError, TypeError):
                Clock.schedule_once(self.fail_taf)

    def update_display(self):

        """ Update display with new forecast variables. Catch ReferenceErrors to
        prevent console crashing
        """

        # Update display values with new derived observations
        reference_error = False
        for key, value in list(self.metar_taf_data.items()):
            try:
                self.app.CurrentConditions.metar_taf[key] = value
            except ReferenceError:
                if not reference_error:
                    Logger.warning(f'astro: {system().log_time()} - Reference error')
                    reference_error = True
