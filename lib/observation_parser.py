""" Handles Websocket messages received by the Raspberry Pi Python console for
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
from lib.request_api import weatherflow_api
from lib.system      import system
from lib             import derived_variables  as derive
from lib             import observation_format as observation
from lib             import properties

# Import required Kivy modules
from kivy.logger  import Logger
from kivy.clock   import mainthread
from kivy.app     import App

# Define empty deviceObs dictionary
device_obs = {'obTime':       [None, 's'],                'pressure':     [None, 'mb'],              'outTemp':      [None, 'c'],
              'inTemp':       [None, 'c'],                'humidity':     [None, '%'],               'windSpd':      [None, 'mps'],
              'windGust':     [None, 'mps'],              'windDir':      [None, 'degrees'],         'rapidWindSpd': [None, 'mps'],
              'rapidWindDir': [None, 'degrees'],          'uvIndex':      [None, 'index'],           'radiation':    [None, 'Wm2'],
              'minuteRain':   [None, 'mm'],               'dailyRain':    [None, 'mm'],              'strikeMinute': [None, 'count'],
              'strikeTime':   [None, 's'],                'strikeDist':   [None, 'km'],              'strike3hr':    [None, 'count'],
              }

# Define empty deriveObs dictionary
derive_obs = {'dewPoint':     [None, 'c'],                  'feelsLike':    [None, 'c', '-', '-'],        'outTempMax':   [None, 'c', '-'],
              'outTempMin':   [None, 'c', '-'],             'outTempDiff':  [None, 'dc', '-'],            'outTempTrend': [None, 'c/hr', 'c8c8c8ff'],
              'inTempMax':    [None, 'c', '-'],             'inTempMin':    [None, 'c', '-'],             'SLP':          [None, 'mb', None],
              'SLPTrend':     [None, 'mb/hr', '-', '-'],    'SLPMin':       [None, 'mb', '-'],            'SLPMax':       [None, 'mb', '-'],
              'windSpd':      [None, 'mps', '-', '-', '-'], 'windAvg':      [None, 'mps'],                'gustMax':      [None, 'mps'],
              'windDir':      [None, 'degrees', '-', '-'],  'rapidWindDir': [None, 'degrees', '-', '-'],  'rainRate':     [None, 'mm/hr', '-'],
              'uvIndex':      [None, 'index'],              'peakSun':      [None, 'hrs', '-'],           'strikeDeltaT': [None, 's', None],
              'strikeFreq':   [None, '/min', None, '/min'],
              'strikeCount':  {'today': [None, 'count'],
                               'month': [None, 'count'],
                               'year':  [None, 'count']
                               },
              'rainAccum':    {'today':     [None, 'mm'],
                               'yesterday': [None, 'mm'],
                               'month':     [None, 'mm'],
                               'year':      [None, 'mm']
                               }
              }


# =============================================================================
# DEFINE 'obsParser' CLASS
# =============================================================================
class obs_parser():

    def __init__(self):

        # Define instance variables
        self.display_obs = properties.Obs()
        self.api_data    = {}
        self.transmit    = 1
        self.flag_api    = [1, 1, 1, 1]

        # Create reference to app object
        self.app = App.get_running_app()
        self.app.obsParser = self

        # Define device and derived observations dictionary
        self.device_obs = device_obs.copy()
        self.derive_obs = derive_obs.copy()

    def parse_obs_st(self, message, config):

        """ Parse obs_st Websocket messages from TEMPEST module

        INPUTS:
            message             obs_sky Websocket message
            config              Console configuration object
        """

        # Extract latest TEMPEST Websocket JSON
        if 'obs' in message:
            latest_ob = message['obs'][0]
        else:
            return

        # Extract TEMPEST device_id. Initialise API data dictionary
        if 'device_id' in message:
            device_id = message['device_id']
        elif 'serial_number' in message:
            device_id = message['serial_number']
        if config['System']['rest_api'] == '1' and config['Station']['TempestID']:
            api_device_id = config['Station']['TempestID']
            self.api_data[device_id] = {'flagAPI': self.flag_api[0]}

        # Discard duplicate TEMPEST Websocket messages
        if 'obs_st' in self.display_obs:
            if self.display_obs['obs_st']['obs'][0] == latest_ob[0]:
                return

        # Extract required observations from latest TEMPEST Websocket JSON
        self.device_obs['obTime']       = [latest_ob[0],  's']
        self.device_obs['windSpd']      = [latest_ob[2],  'mps']
        self.device_obs['windGust']     = [latest_ob[3],  'mps']
        self.device_obs['windDir']      = [latest_ob[4],  'degrees']
        self.device_obs['pressure']     = [latest_ob[6],  'mb']
        self.device_obs['outTemp']      = [latest_ob[7],  'c']
        self.device_obs['humidity']     = [latest_ob[8],  '%']
        self.device_obs['uvIndex']      = [latest_ob[10], 'index']
        self.device_obs['radiation']    = [latest_ob[11], 'Wm2']
        self.device_obs['minuteRain']   = [latest_ob[12], 'mm']
        self.device_obs['strikeMinute'] = [latest_ob[15], 'count']
        if len(latest_ob) > 18:
            self.device_obs['dailyRain']    = [latest_ob[18], 'mm']

        # Extract lightning strike data from the latest TEMPEST Websocket JSON
        # "summary" object
        if 'summary' in message:
            self.device_obs['strikeTime'] = [message['summary']['strike_last_epoch'] if 'strike_last_epoch' in message['summary'] else None, 's']
            self.device_obs['strikeDist'] = [message['summary']['strike_last_dist']  if 'strike_last_dist'  in message['summary'] else None, 'km']
            self.device_obs['strike3hr']  = [message['summary']['strike_count_3h']   if 'strike_count_3h'   in message['summary'] else None, 'count']

        # Request required TEMPEST data from the WeatherFlow API
        if config['System']['rest_api'] == '1' and config['Station']['TempestID']:
            self.api_data[device_id]['24Hrs'] = weatherflow_api.last_24h(api_device_id, latest_ob[0], config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['SLPMin'][0] is None
                    or self.derive_obs['SLPMax'][0] is None
                    or self.derive_obs['outTempMin'][0] is None
                    or self.derive_obs['outTempMax'][0] is None
                    or self.derive_obs['windAvg'][0] is None
                    or self.derive_obs['gustMax'][0] is None
                    or self.derive_obs['peakSun'][0] is None
                    or self.derive_obs['rainAccum']['today'][0] is None
                    or self.derive_obs['strikeCount']['today'][0] is None):
                self.api_data[device_id]['today'] = weatherflow_api.today(api_device_id, config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['rainAccum']['yesterday'][0] is None):
                self.api_data[device_id]['yesterday'] = weatherflow_api.yesterday(api_device_id, config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['rainAccum']['month'][0] is None
                    or self.derive_obs['strikeCount']['month'][0] is None):
                self.api_data[device_id]['month'] = weatherflow_api.month(api_device_id, config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['rainAccum']['year'][0] is None
                    or self.derive_obs['strikeCount']['year'][0] is None):
                self.api_data[device_id]['year']  = weatherflow_api.year(api_device_id, config)
            self.flag_api[0] = 0

        # Store latest TEMPEST JSON message
        self.display_obs['obs_st'] = message

        # Calculate derived observations
        self.calc_derived_variables(device_id, config, 'obs_st')

    def parse_obs_sky(self, message, config):

        """ Parse obs_sky Websocket messages from SKY module

        INPUTS:
            message             obs_sky Websocket message
            config              Console configuration object
        """

        # Extract latest SKY Websocket JSON
        if 'obs' in message:
            latest_ob = message['obs'][0]
        else:
            return

        # Extract SKY device_id. Initialise API data dictionary
        if 'device_id' in message:
            device_id = message['device_id']
        elif 'serial_number' in message:
            device_id = message['serial_number']
        if config['System']['rest_api'] == '1' and config['Station']['SkyID']:
            api_device_id = config['Station']['SkyID']
            self.api_data[device_id] = {'flagAPI': self.flag_api[1]}

        # Discard duplicate SKY Websocket messages
        if 'obs_sky' in self.display_obs:
            if self.display_obs['obs_sky']['obs'][0] == latest_ob[0]:
                return

        # Extract required observations from latest SKY Websocket JSON
        self.device_obs['uvIndex']    = [latest_ob[2],  'index']
        self.device_obs['minuteRain'] = [latest_ob[3],  'mm']
        self.device_obs['windSpd']    = [latest_ob[5],  'mps']
        self.device_obs['windGust']   = [latest_ob[6],  'mps']
        self.device_obs['windDir']    = [latest_ob[7],  'degrees']
        self.device_obs['radiation']  = [latest_ob[10], 'Wm2']
        if latest_ob[11] is not None:
            self.device_obs['dailyRain']  = [latest_ob[11], 'mm']

        # Request required SKY data from the WeatherFlow API
        if config['System']['rest_api'] == '1' and config['Station']['SkyID']:
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['windAvg'][0] is None
                    or self.derive_obs['gustMax'][0] is None
                    or self.derive_obs['peakSun'][0] is None):
                self.api_data[device_id]['today'] = weatherflow_api.today(api_device_id, config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['rainAccum']['yesterday'][0] is None):
                self.api_data[device_id]['yesterday'] = weatherflow_api.yesterday(api_device_id, config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['rainAccum']['month'][0] is None):
                self.api_data[device_id]['month'] = weatherflow_api.month(api_device_id, config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['rainAccum']['year'][0] is None):
                self.api_data[device_id]['year'] = weatherflow_api.year(api_device_id, config)
            self.flag_api[1] = 0

        # Store latest SKY JSON message
        self.display_obs['obs_sky'] = message

        # Calculate derived observations
        self.calc_derived_variables(device_id, config, 'obs_sky')

    def parse_obs_out_air(self, message, config):

        """ Parse obs_air Websocket messages from outdoor AIR module

        INPUTS:
            message             obs_air Websocket message
            config              Console configuration object
        """

        # Extract latest outdoor AIR Websocket JSON
        if 'obs' in message:
            latest_ob = message['obs'][0]
        else:
            return

        # Extract outdoor AIR device_id. Initialise API data dictionary
        if 'device_id' in message:
            device_id = message['device_id']
        elif 'serial_number' in message:
            device_id = message['serial_number']
        if config['System']['rest_api'] == '1' and config['Station']['OutAirID']:
            api_device_id = config['Station']['OutAirID']
            self.api_data[device_id] = {'flagAPI': self.flag_api[2]}

        # Discard duplicate outdoor AIR Websocket messages
        if 'obs_out_air' in self.display_obs:
            if self.display_obs['obs_out_air']['obs'][0] == latest_ob[0]:
                return

        # Extract required observations from latest outdoor AIR Websocket JSON
        self.device_obs['obTime']       = [latest_ob[0], 's']
        self.device_obs['pressure']     = [latest_ob[1], 'mb']
        self.device_obs['outTemp']      = [latest_ob[2], 'c']
        self.device_obs['humidity']     = [latest_ob[3], '%']
        self.device_obs['strikeMinute'] = [latest_ob[4], 'count']

        # Extract lightning strike data from the latest outdoor AIR Websocket
        # JSON "Summary" object
        if 'summary' in message:
            self.device_obs['strikeTime'] = [message['summary']['strike_last_epoch'] if 'strike_last_epoch' in message['summary'] else None, 's']
            self.device_obs['strikeDist'] = [message['summary']['strike_last_dist']  if 'strike_last_dist'  in message['summary'] else None, 'km']
            self.device_obs['strike3hr']  = [message['summary']['strike_count_3h']   if 'strike_count_3h'   in message['summary'] else None, 'count']

        # Request required outdoor AIR data from the WeatherFlow API
        if config['System']['rest_api'] == '1' and config['Station']['OutAirID']:
            self.api_data[device_id]['24Hrs'] = weatherflow_api.last_24h(api_device_id, latest_ob[0], config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['SLPMin'][0] is None
                    or self.derive_obs['SLPMax'][0] is None
                    or self.derive_obs['outTempMin'][0] is None
                    or self.derive_obs['outTempMax'][0] is None
                    or self.derive_obs['strikeCount']['today'][0] is None):
                self.api_data[device_id]['today'] = weatherflow_api.today(api_device_id, config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['strikeCount']['month'][0] is None):
                self.api_data[device_id]['month'] = weatherflow_api.month(api_device_id, config)
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['strikeCount']['year'][0] is None):
                self.api_data[device_id]['year']  = weatherflow_api.year(api_device_id, config)
            self.flag_api[2] = 0

        # Store latest outdoor AIR JSON message
        self.display_obs['obs_out_air'] = message

        # Calculate derived observations
        self.calc_derived_variables(device_id, config, 'obs_out_air')

    def parse_obs_in_air(self, message, config):

        """ Parse obs_air Websocket messages from indoor AIR module

        INPUTS:
            message             obs_air Websocket message
            config              Console configuration object
        """

        # Extract latest indoor AIR Websocket JSON
        if 'obs' in message:
            latest_ob = message['obs'][0]
        else:
            return

        # Extract indoor AIR device_id. Initialise API data dictionary
        if 'device_id' in message:
            device_id = message['device_id']
        elif 'serial_number' in message:
            device_id = message['serial_number']
        if config['System']['rest_api'] == '1' and config['Station']['InAirID']:
            api_device_id = config['Station']['InAirID']
            self.api_data[device_id] = {'flagAPI': self.flag_api[3]}

        # Discard duplicate indoor AIR Websocket messages
        if 'obs_in_air' in self.display_obs:
            if self.display_obs['obs_in_air']['obs'][0] == latest_ob[0]:
                return

        # Extract required observations from latest indoor AIR Websocket JSON
        self.device_obs['obTime'] = [latest_ob[0], 's']
        self.device_obs['inTemp'] = [latest_ob[2], 'c']

        # Request required indoor AIR data from the WeatherFlow API
        if config['System']['rest_api'] == '1' and config['Station']['InAirID']:
            if (self.api_data[device_id]['flagAPI']
                    or self.derive_obs['inTempMin'][0] is None
                    or self.derive_obs['inTempMax'][0] is None):
                self.api_data[device_id]['today'] = weatherflow_api.today(api_device_id, config)
        self.flag_api[3] = 0

        # Store latest indoor AIR JSON message
        self.display_obs['obs_in_air'] = message

        # Calculate derived observations
        self.calc_derived_variables(device_id, config, 'obs_in_air')

    def parse_rapid_wind(self, message, config):

        """ Parse rapid_wind Websocket messages from SKY or TEMPEST module

        INPUTS:
            message             rapid_wind Websocket message received from
                                SKY or TEMPEST module
            config              Console configuration object
        """

        # Extract latest rapid_wind Websocket JSON
        if 'ob' in message:
            latest_ob = message['ob']
        else:
            return

        # Extract device ID
        if 'device_id' in message:
            device_id = message['device_id']
        elif 'serial_number' in message:
            device_id = message['serial_number']

        # Discard duplicate rapid_wind Websocket messages
        if 'rapid_wind' in self.display_obs:
            if self.display_obs['rapid_wind']['ob'][0] == latest_ob[0]:
                return

        # Extract required observations from latest rapid_wind Websocket JSON
        self.device_obs['rapidWindSpd'] = [latest_ob[1], 'mps']
        self.device_obs['rapidWindDir'] = [latest_ob[2], 'degrees']

        # Extract wind direction from previous rapid_wind Websocket JSON
        if 'rapid_wind' in self.device_obs:
            previous_ob = self.device_obs['rapid_wind']['ob']
            rapidWindDirOld = [previous_ob[2], 'degrees']
        else:
            rapidWindDirOld = [0, 'degrees']

        # If windspeed is zero, freeze direction at last direction of non-zero
        # wind speed and edit latest rapid_wind Websocket JSON message.
        if self.device_obs['rapidWindSpd'][0] == 0:
            self.device_obs['rapidWindDir'] = rapidWindDirOld
            message['ob'][2] = rapidWindDirOld[0]

        # Store latest rapid_wind Websocket JSON message
        self.display_obs['rapid_wind'] = message

        # Calculate derived observations
        self.calc_derived_variables(device_id, config, 'rapid_wind')

    def parse_evt_strike(self, message, config):

        """ Parse lightning strike event Websocket messages received from AIR
        or TEMPEST module

        INPUTS:
            message             evt_strike Websocket message received from
                                AIR or TEMPEST module
            config              Console configuration object
        """

        # Extract latest evt_strike Websocket JSON
        if 'evt' in message:
            latest_evt = message['evt']
        else:
            return

        # Extract device ID
        if 'device_id' in message:
            device_id = message['device_id']
        elif 'serial_number' in message:
            device_id = message['serial_number']

        # Discard duplicate evt_strike Websocket messages
        if 'evt_strike' in self.display_obs:
            if self.display_obs['evt_strike']['evt'][0] == latest_evt[0]:
                return

        # Extract required observations from latest evt_strike Websocket JSON
        self.device_obs['strikeTime'] = [latest_evt[0], 's']
        self.device_obs['strikeDist'] = [latest_evt[1], 'km']

        # Store latest evt_strike JSON message
        self.display_obs['evt_strike'] = message

        # Calculate derived observations
        self.calc_derived_variables(device_id, config, 'evt_strike')

    def calc_derived_variables(self, device, config, device_type):

        """ Calculate derived variables from available device observations

        INPUTS:
            device              Device ID
            config              Console configuration object
            device_type         Device type
        """

        # Derive variables from available obs_out_air and obs_st observations
        # Derive variables from available obs_out_air and obs_st observations
        if device_type in ('obs_out_air', 'obs_st'):
            self.derive_obs['feelsLike']    = derive.feels_like(self.device_obs['outTemp'], self.device_obs['humidity'], self.device_obs['windSpd'], config)
            self.derive_obs['dewPoint']     = derive.dew_point(self.device_obs['outTemp'],  self.device_obs['humidity'])
            self.derive_obs['outTempDiff']  = derive.temp_diff(self.device_obs['outTemp'],  self.device_obs['obTime'], device, self.api_data, config)
            self.derive_obs['outTempTrend'] = derive.temp_trend(self.device_obs['outTemp'], self.device_obs['obTime'], device, self.api_data, config)
            self.derive_obs['outTempMax']   = derive.temp_max(self.device_obs['outTemp'],   self.device_obs['obTime'], self.derive_obs['outTempMax'],   device, self.api_data, config)
            self.derive_obs['outTempMin']   = derive.temp_min(self.device_obs['outTemp'],   self.device_obs['obTime'], self.derive_obs['outTempMin'],   device, self.api_data, config)
            self.derive_obs['SLP']          = derive.SLP(self.device_obs['pressure'],      device, config)
            self.derive_obs['SLPTrend']     = derive.SLP_trend(self.device_obs['pressure'], self.device_obs['obTime'], device, self.api_data, config)
            self.derive_obs['SLPMax']       = derive.SLP_max(self.device_obs['pressure'],   self.device_obs['obTime'], self.derive_obs['SLPMax'], device, self.api_data, config)
            self.derive_obs['SLPMin']       = derive.SLP_min(self.device_obs['pressure'],   self.device_obs['obTime'], self.derive_obs['SLPMin'], device, self.api_data, config)
            self.derive_obs['strikeCount']  = derive.strike_count(self.device_obs['strikeMinute'], self.derive_obs['strikeCount'], device, self.api_data, config)
            self.derive_obs['strikeFreq']   = derive.strike_frequency(self.device_obs['obTime'],   device, self.api_data, config)
            self.derive_obs['strikeDeltaT'] = derive.strike_delta_t(self.device_obs['strikeTime'], config)

        # Derive variables from available obs_sky and obs_st observations
        if device_type in ('obs_sky', 'obs_st'):
            self.derive_obs['uvIndex']   = derive.uv_index(self.device_obs['uvIndex'])
            self.derive_obs['peakSun']   = derive.peak_sun_hours(self.device_obs['radiation'],  self.derive_obs['peakSun'], device, self.api_data, config)
            self.derive_obs['windSpd']   = derive.beaufort_scale(self.device_obs['windSpd'])
            self.derive_obs['windDir']   = derive.cardinal_wind_dir(self.device_obs['windDir'], self.device_obs['windSpd'])
            self.derive_obs['windAvg']   = derive.avg_wind_speed(self.device_obs['windSpd'],    self.derive_obs['windAvg'], device, self.api_data, config)
            self.derive_obs['gustMax']   = derive.max_wind_gust(self.device_obs['windGust'],    self.derive_obs['gustMax'], device, self.api_data, config)
            self.derive_obs['rainRate']  = derive.rain_rate(self.device_obs['minuteRain'])
            self.derive_obs['rainAccum'] = derive.rain_accumulation(self.device_obs['minuteRain'], self.device_obs['dailyRain'], self.derive_obs['rainAccum'], device, self.api_data, config)

        # Derive variables from available obs_out_air and obs_st observations
        if device_type == 'obs_in_air':
            self.derive_obs['inTempMax']   = derive.temp_max(self.device_obs['inTemp'], self.device_obs['obTime'], self.derive_obs['inTempMax'], device, self.api_data, config)
            self.derive_obs['inTempMin']   = derive.temp_min(self.device_obs['inTemp'], self.device_obs['obTime'], self.derive_obs['inTempMin'], device, self.api_data, config)

        # Derive variables from available rapid_wind observations
        if device_type == 'rapid_wind':
            self.derive_obs['rapidWindDir'] = derive.cardinal_wind_dir(self.device_obs['rapidWindDir'], self.device_obs['rapidWindSpd'])

        # Derive variables from available evt_strike observations
        if device_type == 'evt_strike':
            self.derive_obs['strikeDeltaT'] = derive.strike_delta_t(self.device_obs['strikeTime'], config)

        # Format derived observations
        self.format_derived_variables(config, device_type)

    def format_derived_variables(self, config, device_type):

        """ Format derived variables from available device observations

        INPUTS:
            config              Console configuration object
            device_type         Device type
        """

        # Convert derived variable units from obs_out_air and obs_st observations
        if device_type in ('obs_out_air', 'obs_st', 'obs_all'):
            outTemp        = observation.units(self.device_obs['outTemp'],              config['Units']['Temp'])
            feelsLike      = observation.units(self.derive_obs['feelsLike'],            config['Units']['Temp'])
            dewPoint       = observation.units(self.derive_obs['dewPoint'],             config['Units']['Temp'])
            outTempDiff    = observation.units(self.derive_obs['outTempDiff'],          config['Units']['Temp'])
            outTempTrend   = observation.units(self.derive_obs['outTempTrend'],         config['Units']['Temp'])
            outTempMax     = observation.units(self.derive_obs['outTempMax'],           config['Units']['Temp'])
            outTempMin     = observation.units(self.derive_obs['outTempMin'],           config['Units']['Temp'])
            humidity       = observation.units(self.device_obs['humidity'],             config['Units']['Other'])
            SLP            = observation.units(self.derive_obs['SLP'],                  config['Units']['Pressure'])
            SLPTrend       = observation.units(self.derive_obs['SLPTrend'],             config['Units']['Pressure'])
            SLPMax         = observation.units(self.derive_obs['SLPMax'],               config['Units']['Pressure'])
            SLPMin         = observation.units(self.derive_obs['SLPMin'],               config['Units']['Pressure'])
            strikeDist     = observation.units(self.device_obs['strikeDist'],           config['Units']['Distance'])
            strikeDeltaT   = observation.units(self.derive_obs['strikeDeltaT'],         config['Units']['Other'])
            strikeFreq     = observation.units(self.derive_obs['strikeFreq'],           config['Units']['Other'])
            strike3hr      = observation.units(self.device_obs['strike3hr'],            config['Units']['Other'])
            strikeToday    = observation.units(self.derive_obs['strikeCount']['today'], config['Units']['Other'])
            strikeMonth    = observation.units(self.derive_obs['strikeCount']['month'], config['Units']['Other'])
            strikeYear     = observation.units(self.derive_obs['strikeCount']['year'],  config['Units']['Other'])

        # Convert derived variable units from obs_sky and obs_st observations
        if device_type in ('obs_sky', 'obs_st', 'obs_all'):
            rainRate       = observation.units(self.derive_obs['rainRate'],               config['Units']['Precip'])
            todayRain      = observation.units(self.derive_obs['rainAccum']['today'],     config['Units']['Precip'])
            yesterdayRain  = observation.units(self.derive_obs['rainAccum']['yesterday'], config['Units']['Precip'])
            monthRain      = observation.units(self.derive_obs['rainAccum']['month'],     config['Units']['Precip'])
            yearRain       = observation.units(self.derive_obs['rainAccum']['year'],      config['Units']['Precip'])
            radiation      = observation.units(self.device_obs['radiation'],              config['Units']['Other'])
            uvIndex        = observation.units(self.derive_obs['uvIndex'],                config['Units']['Other'])
            peakSun        = observation.units(self.derive_obs['peakSun'],                config['Units']['Other'])
            windSpd        = observation.units(self.derive_obs['windSpd'],                config['Units']['Wind'])
            windDir        = observation.units(self.derive_obs['windDir'],                config['Units']['Direction'])
            windGust       = observation.units(self.device_obs['windGust'],               config['Units']['Wind'])
            windAvg        = observation.units(self.derive_obs['windAvg'],                config['Units']['Wind'])
            windMax        = observation.units(self.derive_obs['gustMax'],                config['Units']['Wind'])

        # Convert derived variable units from obs_in_air observations
        if device_type in ('obs_in_air',  'obs_all'):
            inTemp         = observation.units(self.device_obs['inTemp'],    config['Units']['Temp'])
            inTempMax      = observation.units(self.derive_obs['inTempMax'], config['Units']['Temp'])
            inTempMin      = observation.units(self.derive_obs['inTempMin'], config['Units']['Temp'])

        # Convert derived variable units from rapid_wind observations
        if device_type in ('rapid_wind', 'obs_all'):
            rapidWindSpd   = observation.units(self.device_obs['rapidWindSpd'], config['Units']['Wind'])
            rapidWindDir   = observation.units(self.derive_obs['rapidWindDir'], 'degrees')

        # Convert derived variable units from available evt_strike observations
        if device_type in ('evt_strike', 'obs_all'):
            strikeDist     = observation.units(self.device_obs['strikeDist'],   config['Units']['Distance'])
            strikeDeltaT   = observation.units(self.derive_obs['strikeDeltaT'], config['Units']['Other'])

        # Format derived variables from obs_air and obs_st observations
        if device_type in ('obs_out_air', 'obs_st', 'obs_all'):
            self.display_obs['outTemp']       = observation.format(outTemp,      'Temp')
            self.display_obs['FeelsLike']     = observation.format(feelsLike,    'Temp')
            self.display_obs['DewPoint']      = observation.format(dewPoint,     'Temp')
            self.display_obs['outTempDiff']   = observation.format(outTempDiff,  'Temp')
            self.display_obs['outTempTrend']  = observation.format(outTempTrend, 'Temp')
            self.display_obs['outTempMax']    = observation.format(outTempMax,   ['Temp', 'Time'], config)
            self.display_obs['outTempMin']    = observation.format(outTempMin,   ['Temp', 'Time'], config)
            self.display_obs['Humidity']      = observation.format(humidity,     'Humidity')
            self.display_obs['SLP']           = observation.format(SLP,          'Pressure')
            self.display_obs['SLPTrend']      = observation.format(SLPTrend,     'Pressure')
            self.display_obs['SLPMax']        = observation.format(SLPMax,       ['Pressure', 'Time'], config)
            self.display_obs['SLPMin']        = observation.format(SLPMin,       ['Pressure', 'Time'], config)
            self.display_obs['StrikeDist']    = observation.format(strikeDist,   'StrikeDistance')
            self.display_obs['StrikeDeltaT']  = observation.format(strikeDeltaT, 'TimeDelta')
            self.display_obs['StrikeFreq']    = observation.format(strikeFreq,   'StrikeFrequency')
            self.display_obs['Strikes3hr']    = observation.format(strike3hr,    'StrikeCount')
            self.display_obs['StrikesToday']  = observation.format(strikeToday,  'StrikeCount')
            self.display_obs['StrikesMonth']  = observation.format(strikeMonth,  'StrikeCount')
            self.display_obs['StrikesYear']   = observation.format(strikeYear,   'StrikeCount')

        # Format derived variables from obs_sky and obs_st observations
        if device_type in ('obs_sky', 'obs_st', 'obs_all'):
            self.display_obs['Radiation']     = observation.format(radiation,     'Radiation')
            self.display_obs['UVIndex']       = observation.format(uvIndex,       'UV')
            self.display_obs['peakSun']       = observation.format(peakSun,       'peakSun')
            self.display_obs['RainRate']      = observation.format(rainRate,      'Precip')
            self.display_obs['TodayRain']     = observation.format(todayRain,     'Precip')
            self.display_obs['YesterdayRain'] = observation.format(yesterdayRain, 'Precip')
            self.display_obs['MonthRain']     = observation.format(monthRain,     'Precip')
            self.display_obs['YearRain']      = observation.format(yearRain,      'Precip')
            self.display_obs['WindSpd']       = observation.format(windSpd,       'Wind')
            self.display_obs['WindGust']      = observation.format(windGust,      'Wind')
            self.display_obs['AvgWind']       = observation.format(windAvg,       'Wind')
            self.display_obs['MaxGust']       = observation.format(windMax,       'Wind')
            self.display_obs['WindDir']       = observation.format(windDir,       'Direction')

        # Format derived variables from obs_in_air observations
        if device_type in ('obs_in_air', 'obs_all'):
            self.display_obs['inTemp']        = observation.format(inTemp,    'Temp')
            self.display_obs['inTempMax']     = observation.format(inTempMax, ['Temp', 'Time'], config)
            self.display_obs['inTempMin']     = observation.format(inTempMin, ['Temp', 'Time'], config)

        # Format derived variables from rapid_wind observations
        if device_type in ('rapid_wind', 'obs_all'):
            self.display_obs['rapidSpd']      = observation.format(rapidWindSpd, 'Wind')
            self.display_obs['rapidDir']      = observation.format(rapidWindDir, 'Direction')

        # Format derived variables from evt_strike observations
        if device_type in ('evt_strike', 'obs_all'):
            self.display_obs['StrikeDist']    = observation.format(strikeDist,   'StrikeDistance')
            self.display_obs['StrikeDeltaT']  = observation.format(strikeDeltaT, 'TimeDelta')

        # Update display with new variables
        self.update_display(device_type)

    def reformat_display(self):
        while self.app.connection_client.activeThreads():
            pass
        self.format_derived_variables(self.app.config, 'obs_all')

    def resetDisplay(self):
        while self.app.connection_client.activeThreads():
            pass
        self.display_obs = properties.Obs()
        self.device_obs  = device_obs.copy()
        self.derive_obs  = derive_obs.copy()
        self.api_data    = {}
        self.update_display('obs_reset')

    @mainthread
    def update_display(self, ob_type):

        """ Update display with new variables derived from latest websocket
        message

        INPUTS:
            ob_type             Latest Websocket message type
        """

        # Update display values with new derived observations
        reference_error = False
        for key, value in list(self.display_obs.items()):
            if not (ob_type == 'obs_all' and 'rapid' in key):
                try:                                                            # Don't update rapidWind display when type is 'all'
                    self.app.CurrentConditions.Obs[key] = value                 # as the RapidWind rose is not animated in this case
                except ReferenceError:
                    if not reference_error:
                        Logger.warning(f'obs_parser: {system().log_time()} - Reference error {ob_type}')
                        reference_error = True

        # Update display graphics with new derived observations
        if ob_type == 'rapid_wind':
            if hasattr(self.app, 'WindSpeedPanel'):
                for panel in getattr(self.app, 'WindSpeedPanel'):
                    panel.animateWindRose()
        elif ob_type == 'evt_strike':
            if self.app.config['Display']['LightningPanel'] == '1':
                for ii, button in enumerate(self.app.CurrentConditions.button_list):
                    if "Lightning" in button[2]:
                        self.app.CurrentConditions.switchPanel([], button)
            if hasattr(self.app, 'LightningPanel'):
                for panel in getattr(self.app, 'LightningPanel'):
                    panel.setLightningBoltIcon()
                    panel.animateLightningBoltIcon()
        else:
            if ob_type in ['obs_st', 'obs_air', 'obs_all', 'obs_reset']:
                if hasattr(self.app, 'TemperaturePanel'):
                    for panel in getattr(self.app, 'TemperaturePanel'):
                        panel.set_feels_like_icon()
                if hasattr(self.app, 'LightningPanel'):
                    for panel in getattr(self.app, 'LightningPanel'):
                        panel.setLightningBoltIcon()
                if hasattr(self.app, 'BarometerPanel'):
                    for panel in getattr(self.app, 'BarometerPanel'):
                        panel.setBarometerArrow()
            if ob_type in ['obs_st', 'obs_sky', 'obs_all', 'obs_reset']:
                if hasattr(self.app, 'WindSpeedPanel'):
                    for panel in getattr(self.app, 'WindSpeedPanel'):
                        panel.setWindIcons()
                if hasattr(self.app, 'SunriseSunsetPanel'):
                    for panel in getattr(self.app, 'SunriseSunsetPanel'):
                        panel.setUVBackground()
                if hasattr(self.app, 'RainfallPanel'):
                    for panel in getattr(self.app, 'RainfallPanel'):
                        panel.animate_rain_rate()
                if hasattr(self.app, 'TemperaturePanel'):
                    for panel in getattr(self.app, 'TemperaturePanel'):
                        panel.set_feels_like_icon()
