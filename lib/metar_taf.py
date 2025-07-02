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
        #if int(self.app.config['System']['rest_api']):
        #    self.fetch_metar_data()

    def fetch_metar_data(self, *largs):

        """ Fetch the METAR forecast data using the CheckWX API
        """            
        # Fetch latest METAR data
        if int(self.app.config['System']['rest_api']):
            URL    = 'https://api.checkwx.com/metar/lat/{}/lon/{}/decoded'
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
            URL    = 'https://api.checkwx.com/taf/lat/{}/lon/{}/decoded'
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
        self.met_data['response'] = response
        self.parse_metar_taf('metar')

    def success_taf(self, request, response):

        """ Sucessfully fetched METAR data from the CheckWXAPI. Parse TAF 
        response

        INPUTS:
            request             Urlrequest object
            response            Urlrequest response

        """

        # Parse the latest daily and hourly weather forecast data
        self.metar_taf_data['taf'] = response['data'][0]
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

        # PARSE TAF DATA FROM CHECKWX API
        # --------------------------------------------------------------------------
        # Extract TAF dictionary
        if 'taf' in self.metar_taf_data:
            taf_data = self.metar_taf_data['taf']
        else:
            return
        print(taf_data)

        # Get station time zone
        Tz  = pytz.timezone(self.app.config['Station']['Timezone'])

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

        # Extract all TAF data from CheckWX API JSON object
        try:
            # Extract location and timing information   
            location    = taf_data['station']['location']
            issued_time = datetime.fromisoformat(taf_data['timestamp']['issued'] + "+00:00")
            from_time   = datetime.fromisoformat(taf_data['timestamp']['from'] + "+00:00")
            to_time     = datetime.fromisoformat(taf_data['timestamp']['to'] + "+00:00")

            # Define required variables
            trend_from_time         = []
            trend_to_time           = []
            trend_type              = []
            trend_wind_direction    = []
            trend_wind_speed        = []
            trend_wind_gust         = []
            trend_visibility        = []
            trend_cloud_type        = []
            trend_cloud_level       = []
            trend_conditions        = []
            main_cloud_type         = []
            main_cloud_level        = []

            # Extract each individual forecast in TAF
            for forecast in taf_data['forecast']:
                
                # Parse main forecast data from TAF
                if 'change' not in forecast:

                    # Extract wind forecast variables
                    main_wind_direction = [forecast['wind']['degrees']   if 'wind' in forecast and 'degrees'   in forecast['wind'] else None, 'degrees']
                    main_wind_speed     = [forecast['wind']['speed_mps'] if 'wind' in forecast and 'speed_mps' in forecast['wind'] else None, 'mps']
                    main_wind_gust      = [forecast['wind']['gust_mps']  if 'wind' in forecast and 'gust_mps'  in forecast['wind'] else None, 'mps']    

                    # Extract visibility forecast variables
                    main_visibility = [forecast['visibility']['meters_text'], 'm'] if self.app.config['Units']['Distance'] == 'km' else [forecast['visibility']['miles_text'], 'miles']

                    # Extract cloud forecast variables
                    for cloud in forecast['clouds']:
                        main_cloud_type.append(cloud['text'])
                        main_cloud_level.append([cloud['base_meters_agl'], 'm'] if self.app.config['Units']['Distance'] == 'km' else [cloud['base_feet_agl'], 'ft'])

                # Parse trend forecast data from TAF
                elif 'change' in forecast:

                    # Extract timing information
                    trend_from_time.append(datetime.fromisoformat(forecast['timestamp']['from'] + "+00:00"))
                    trend_to_time.append(datetime.fromisoformat(forecast['timestamp']['to']   + "+00:00"))

                    # Extract trend type variable
                    trend_type.append(forecast['change']['indicator']['text'])

                    # Extract wind forecast variables
                    trend_wind_direction.append([forecast['wind']['degrees'] if 'wind' in forecast and 'degrees'   in forecast['wind'] else None, 'degrees'])
                    trend_wind_speed.append([forecast['wind']['speed_mps']   if 'wind' in forecast and 'speed_mps' in forecast['wind'] else None, 'mps'])
                    trend_wind_gust.append([forecast['wind']['gust_mps']     if 'wind' in forecast and 'gust_mps'  in forecast['wind'] else None, 'mps']  )  

                    # Extract visibility forecast variables
                    trend_visibility.append([forecast['visibility']['meters_text'] if 'visibility' in forecast else None, 'm'] if self.app.config['Units']['Distance'] == 'km' else 
                                            [forecast['visibility']['miles_text']  if 'visibility' in forecast else None, 'miles'])

                    # Extract cloud forecast variables
                    cloud_type  = []
                    cloud_level = []
                    if 'clouds' in forecast:
                        for cloud in forecast['clouds']:
                            cloud_type.append(cloud['text'])
                            cloud_level.append([cloud['base_meters_agl'], 'm'])
                    else:
                        cloud_type.append(None)
                        cloud_level.append([None, 'm'])
                    trend_cloud_type.append(cloud_type)
                    trend_cloud_level.append(cloud_level)

                    # Extract conditions forecast
                    conditions = []
                    if 'conditions' in forecast:
                        for condition in forecast['conditions']:
                            conditions.append(condition['text'] if 'text' in condition else None)
                    trend_conditions.append(conditions)

            # Convert forecast units as required
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
            # print(trend_type, flush=True)      
            # print(trend_from_time, flush=True)
            # print(trend_to_time, flush=True)   
            #print(trend_wind_direction, flush=True)
            #print(trend_wind_speed, flush=True)
            #print(trend_wind_gust, flush=True)  
            # print(trend_visibility, flush=True)
            # print(trend_cloud_type, flush=True)
            # print(trend_cloud_level, flush=True) 
            #print(trend_conditions, flush=True) 


            # Construct main forecast taf string
            taf_forecast_string   = ""
            location_string       = (f"TAF forecast for {location}") 
            timing_string         = (f"Issued at {issued_time.astimezone(Tz).strftime(time_format)} "
                                     f"and valid until {to_time.astimezone(Tz).strftime(time_format)} on {to_time.astimezone(Tz).strftime(date_format)}\n")
            wind_direction_string = (f"Wind {main_wind_direction[0]}" if self.app.config['Units']['Direction'] == 'cardinal' else f"Wind {main_wind_direction[0] + main_wind_direction[1]}")
            wind_speed_string     = (f" at {main_wind_speed[0]} {main_wind_speed[1]}")
            wind_gust_string      = (f" gusting {main_wind_gust[0]} {main_wind_gust[1]}" if main_wind_gust[0] != '-' else f"")
            visibility_string     = (f", {main_visibility[0].lower()} {main_visibility[1]} visibility")
            if main_cloud_type:
                for ii, cloud in enumerate(main_cloud_type):
                    if cloud is not None:
                        if ii == 0:
                            cloud_string = ", cloud "
                        else:
                            cloud_string = cloud_string + ", "
                        cloud_string = cloud_string + f"{main_cloud_type[ii].lower()} at {main_cloud_level[ii][0]} {main_cloud_level[ii][1]}"
                    else:
                        cloud_string = f""
            else:
                cloud_string = f""
            taf_forecast_string = (taf_forecast_string + 
                                   wind_direction_string + 
                                   wind_speed_string + 
                                   wind_gust_string +
                                   visibility_string + 
                                   cloud_string + "\n")

            # Construct trend forecast taf string
            for ii, type in enumerate(trend_type):
                trend_time_string           = (f"{type} {trend_from_time[ii].astimezone(Tz).strftime(time_format)} {trend_from_time[ii].astimezone(Tz).strftime('%d %b')} to " 
                                               f"{trend_to_time[ii].astimezone(Tz).strftime(time_format)} {trend_to_time[ii].astimezone(Tz).strftime('%d %b')}")
                trend_wind_direction_string = ((f", wind {trend_wind_direction[ii][0]}" if self.app.config['Units']['Direction'] == 'cardinal' else 
                                                f"Wind {trend_wind_direction[ii][0] + trend_wind_direction[ii][1]}") if trend_wind_direction[ii][0] != '-' else f"")
                trend_wind_speed_string     = (f" at {trend_wind_speed[ii][0]} {trend_wind_speed[ii][1]}" if trend_wind_speed[ii][0] != '-' else f"")
                trend_gust_speed_string     = (f" gusting {trend_wind_gust[ii][0]} {trend_wind_gust[ii][1]}" if trend_wind_gust[ii][0] != '-' else f"")
                trend_visibility_string     = (f", {trend_visibility[ii][0].lower()} {trend_visibility[ii][1]} visibility" if trend_visibility[ii][0] is not None else f"")
                if trend_cloud_type[ii]:
                    for jj, cloud in enumerate(trend_cloud_type[ii]):
                        if cloud is not None:
                            if jj == 0:
                                trend_cloud_string = ", cloud "
                            else:
                                trend_cloud_string = trend_cloud_string + ", "
                            trend_cloud_string = trend_cloud_string + f"{trend_cloud_type[ii][jj].lower()} at {trend_cloud_level[ii][jj][0]} {trend_cloud_level[ii][jj][1]}"
                        else:
                            trend_cloud_string = f""
                else:
                            trend_cloud_string = f""
                if trend_conditions[ii]:
                    for jj, condition in enumerate(trend_conditions[ii]):
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
                taf_forecast_string = (taf_forecast_string + "\n" + 
                                       trend_time_string + 
                                       trend_wind_direction_string + 
                                       trend_wind_speed_string + 
                                       trend_gust_speed_string + 
                                       trend_visibility_string + 
                                       trend_cloud_string +
                                       trend_condition_string + "\n")

            # Define and format labels
            self.metar_taf_data['taf_location_string'] = location_string
            self.metar_taf_data['taf_timing_string']   = timing_string
            self.metar_taf_data['taf_forecast_string'] = taf_forecast_string

            # Update display
            self.update_display()

            # Schedule new forecast
            Clock.schedule_once(self.schedule_metar_taf)

        # Unable to extract TAF data from JSON object. Set forecast
        # variables to blank and indicate to user that forecast is unavailable
        except (IndexError, KeyError, ValueError):
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
