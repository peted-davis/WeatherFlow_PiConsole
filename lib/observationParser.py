""" Handles Websocket messages received by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2022 Peter Davis

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
from lib             import derivedVariables  as derive
from lib             import observationFormat as observation
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
class obsParser():

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
            latestOb = message['obs'][0]
        else:
            return

        # Extract TEMPEST device_id. Initialise API data dictionary
        device_id = message['device_id']
        self.api_data[device_id] = {'flagAPI': self.flag_api[0]}

        # Discard duplicate TEMPEST Websocket messages
        if 'obs_st' in self.display_obs:
            if self.display_obs['obs_st']['obs'][0] == latestOb[0]:
                return

        # Extract required observations from latest TEMPEST Websocket JSON
        self.device_obs['obTime']       = [latestOb[0],  's']
        self.device_obs['windSpd']      = [latestOb[2],  'mps']
        self.device_obs['windGust']     = [latestOb[3],  'mps']
        self.device_obs['windDir']      = [latestOb[4],  'degrees']
        self.device_obs['pressure']     = [latestOb[6],  'mb']
        self.device_obs['outTemp']      = [latestOb[7],  'c']
        self.device_obs['humidity']     = [latestOb[8],  '%']
        self.device_obs['uvIndex']      = [latestOb[10], 'index']
        self.device_obs['radiation']    = [latestOb[11], 'Wm2']
        self.device_obs['minuteRain']   = [latestOb[12], 'mm']
        self.device_obs['strikeMinute'] = [latestOb[15], 'count']
        self.device_obs['dailyRain']    = [latestOb[18], 'mm']

        # Extract lightning strike data from the latest TEMPEST Websocket JSON
        # "Summary" object
        self.device_obs['strikeTime'] = [message['summary']['strike_last_epoch'] if 'strike_last_epoch' in message['summary'] else None, 's']
        self.device_obs['strikeDist'] = [message['summary']['strike_last_dist']  if 'strike_last_dist'  in message['summary'] else None, 'km']
        self.device_obs['strike3hr']  = [message['summary']['strike_count_3h']   if 'strike_count_3h'   in message['summary'] else None, 'count']

        # Request required TEMPEST data from the WeatherFlow API
        self.api_data[device_id]['24Hrs'] = weatherflow_api.last_24h(device_id, latestOb[0], config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['SLPMin'][0] is None
                or self.derive_obs['SLPMax'][0] is None
                or self.derive_obs['outTempMin'][0] is None
                or self.derive_obs['outTempMax'][0] is None
                or self.derive_obs['windAvg'][0] is None
                or self.derive_obs['gustMax'][0] is None
                or self.derive_obs['peakSun'][0] is None
                or self.derive_obs['strikeCount']['today'][0] is None):
            self.api_data[device_id]['today'] = weatherflow_api.today(device_id, config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['rainAccum']['yesterday'][0] is None):
            self.api_data[device_id]['yesterday'] = weatherflow_api.yesterday(device_id, config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['rainAccum']['month'][0] is None
                or self.derive_obs['strikeCount']['month'][0] is None):
            self.api_data[device_id]['month'] = weatherflow_api.month(device_id, config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['rainAccum']['year'][0] is None
                or self.derive_obs['strikeCount']['year'][0] is None):
            self.api_data[device_id]['year']  = weatherflow_api.year(device_id, config)
        self.flag_api[0] = 0

        # Store latest TEMPEST JSON message
        self.display_obs['obs_st'] = message

        # Calculate derived observations
        self.calcDerivedVariables(device_id, config, 'obs_st')

    def parse_obs_sky(self, message, config):

        """ Parse obs_sky Websocket messages from SKY module

        INPUTS:
            message             obs_sky Websocket message
            config              Console configuration object
        """

        # Extract latest SKY Websocket JSON
        if 'obs' in message:
            latestOb = message['obs'][0]
        else:
            return

        # Extract SKY device_id. Initialise API data dictionary
        device_id = message['device_id']
        self.api_data[device_id] = {'flagAPI': self.flag_api[1]}

        # Discard duplicate SKY Websocket messages
        if 'obs_sky' in self.display_obs:
            if self.display_obs['obs_sky']['obs'][0] == latestOb[0]:
                return

        # Extract required observations from latest SKY Websocket JSON
        self.device_obs['uvIndex']    = [latestOb[2],  'index']
        self.device_obs['minuteRain'] = [latestOb[3],  'mm']
        self.device_obs['windSpd']    = [latestOb[5],  'mps']
        self.device_obs['windGust']   = [latestOb[6],  'mps']
        self.device_obs['windDir']    = [latestOb[7],  'degrees']
        self.device_obs['radiation']  = [latestOb[10], 'Wm2']
        self.device_obs['dailyRain']  = [latestOb[11], 'mm']

        # Request required SKY data from the WeatherFlow API
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['windAvg'][0] is None
                or self.derive_obs['gustMax'][0] is None
                or self.derive_obs['peakSun'][0] is None):
            self.api_data[device_id]['today'] = weatherflow_api.today(device_id, config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['rainAccum']['yesterday'][0] is None):
            self.api_data[device_id]['yesterday'] = weatherflow_api.yesterday(device_id, config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['rainAccum']['month'][0] is None):
            self.api_data[device_id]['month'] = weatherflow_api.month(device_id, config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['rainAccum']['year'][0] is None):
            self.api_data[device_id]['year'] = weatherflow_api.year(device_id, config)
        self.flag_api[1] = 0

        # Store latest SKY JSON message
        self.display_obs['obs_sky'] = message

        # Calculate derived observations
        self.calcDerivedVariables(device_id, config, 'obs_sky')

    def parse_obs_out_air(self, message, config):

        """ Parse obs_air Websocket messages from outdoor AIR module

        INPUTS:
            message             obs_air Websocket message
            config              Console configuration object
        """

        # Extract latest outdoor AIR Websocket JSON
        if 'obs' in message:
            latestOb = message['obs'][0]
        else:
            return

        # Extract outdoor AIR device_id. Initialise API data dictionary
        device_id = message['device_id']
        self.api_data[device_id] = {'flagAPI': self.flag_api[2]}

        # Discard duplicate outdoor AIR Websocket messages
        if 'obs_out_air' in self.display_obs:
            if self.display_obs['obs_out_air']['obs'][0] == latestOb[0]:
                return

        # Extract required observations from latest outdoor AIR Websocket JSON
        self.device_obs['obTime']       = [latestOb[0], 's']
        self.device_obs['pressure']     = [latestOb[1], 'mb']
        self.device_obs['outTemp']      = [latestOb[2], 'c']
        self.device_obs['humidity']     = [latestOb[3], '%']
        self.device_obs['strikeMinute'] = [latestOb[4], 'count']

        # Extract lightning strike data from the latest outdoor AIR Websocket
        # JSON "Summary" object
        self.device_obs['strikeTime'] = [message['summary']['strike_last_epoch'] if 'strike_last_epoch' in message['summary'] else None, 's']
        self.device_obs['strikeDist'] = [message['summary']['strike_last_dist']  if 'strike_last_dist'  in message['summary'] else None, 'km']
        self.device_obs['strike3hr']  = [message['summary']['strike_count_3h']   if 'strike_count_3h'   in message['summary'] else None, 'count']

        # Request required outdoor AIR data from the WeatherFlow API
        self.api_data[device_id]['24Hrs'] = weatherflow_api.last_24h(device_id, latestOb[0], config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['SLPMin'][0] is None
                or self.derive_obs['SLPMax'][0] is None
                or self.derive_obs['outTempMin'][0] is None
                or self.derive_obs['outTempMax'][0] is None
                or self.derive_obs['strikeCount']['today'][0] is None):
            self.api_data[device_id]['today'] = weatherflow_api.today(device_id, config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['strikeCount']['month'][0] is None):
            self.api_data[device_id]['month'] = weatherflow_api.month(device_id, config)
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['strikeCount']['year'][0] is None):
            self.api_data[device_id]['year']  = weatherflow_api.year(device_id, config)
        self.flag_api[2] = 0

        # Store latest outdoor AIR JSON message
        self.display_obs['obs_out_air'] = message

        # Calculate derived observations
        self.calcDerivedVariables(device_id, config, 'obs_out_air')

    def parse_obs_in_air(self, message, config):

        """ Parse obs_air Websocket messages from indoor AIR module

        INPUTS:
            message             obs_air Websocket message
            config              Console configuration object
        """

        # Extract latest indoor AIR Websocket JSON
        if 'obs' in message:
            latestOb = message['obs'][0]
        else:
            return

        # Extract indoor AIR device_id. Initialise API data dictionary
        device_id = message['device_id']
        self.api_data[device_id] = {'flagAPI': self.flag_api[3]}

        # Discard duplicate indoor AIR Websocket messages
        if 'obs_in_air' in self.display_obs:
            if self.display_obs['obs_in_air']['obs'][0] == latestOb[0]:
                return

        # Extract required observations from latest indoor AIR Websocket JSON
        self.device_obs['obTime'] = [latestOb[0], 's']
        self.device_obs['inTemp'] = [latestOb[2], 'c']

        # Request required indoor AIR data from the WeatherFlow API
        if (self.api_data[device_id]['flagAPI']
                or self.derive_obs['inTempMin'][0] is None
                or self.derive_obs['inTempMax'][0] is None):
            self.api_data[device_id]['today'] = weatherflow_api.today(device_id, config)
        self.flag_api[3] = 0

        # Store latest indoor AIR JSON message
        self.display_obs['obs_in_air'] = message

        # Calculate derived observations
        self.calcDerivedVariables(device_id, config, 'obs_in_air')

    def parse_rapid_wind(self, message, config):

        """ Parse rapid_wind Websocket messages from SKY or TEMPEST module

        INPUTS:
            message             rapid_wind Websocket message received from
                                SKY or TEMPEST module
            config              Console configuration object
        """

        # Extract latest rapid_wind Websocket JSON
        if 'ob' in message:
            latestOb = message['ob']
        else:
            return

        # Extract device ID
        device_id = message['device_id']

        # Discard duplicate rapid_wind Websocket messages
        if 'rapid_wind' in self.display_obs:
            if self.display_obs['rapid_wind']['ob'][0] == latestOb[0]:
                return

        # Extract required observations from latest rapid_wind Websocket JSON
        self.device_obs['rapidWindSpd'] = [latestOb[1], 'mps']
        self.device_obs['rapidWindDir'] = [latestOb[2], 'degrees']

        # Extract wind direction from previous rapid_wind Websocket JSON
        if 'rapid_wind' in self.device_obs:
            previousOb = self.device_obs['rapid_wind']['ob']
            rapidWindDirOld = [previousOb[2], 'degrees']
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
        self.calcDerivedVariables(device_id, config, 'rapid_wind')

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
            latestEvt = message['evt']
        else:
            return

        # Extract device ID
        device_id = message['device_id']

        # Discard duplicate evt_strike Websocket messages
        if 'evt_strike' in self.display_obs:
            if self.display_obs['evt_strike']['evt'][0] == latestEvt[0]:
                return

        # Extract required observations from latest evt_strike Websocket JSON
        self.device_obs['strikeTime'] = [latestEvt[0], 's']
        self.device_obs['strikeDist'] = [latestEvt[1], 'km']

        # Store latest evt_strike JSON message
        self.display_obs['evt_strike'] = message

        # Calculate derived observations
        self.calcDerivedVariables(device_id, config, 'evt_strike')

    def calcDerivedVariables(self, device, config, device_type):

        """ Calculate derived variables from available device observations

        INPUTS:
            device              Device ID
            config              Console configuration object
            device_type         Device type
        """

        # Derive variables from available obs_out_air and obs_st observations
        # Derive variables from available obs_out_air and obs_st observations
        if device_type in ('obs_out_air', 'obs_st'):
            self.derive_obs['feelsLike']    = derive.feelsLike(self.device_obs['outTemp'], self.device_obs['humidity'], self.device_obs['windSpd'], config)
            self.derive_obs['dewPoint']     = derive.dewPoint(self.device_obs['outTemp'],  self.device_obs['humidity'])
            self.derive_obs['outTempDiff']  = derive.tempDiff(self.device_obs['outTemp'],  self.device_obs['obTime'], device, self.api_data, config)
            self.derive_obs['outTempTrend'] = derive.tempTrend(self.device_obs['outTemp'], self.device_obs['obTime'], device, self.api_data, config)
            self.derive_obs['outTempMax']   = derive.tempMax(self.device_obs['outTemp'],   self.device_obs['obTime'], self.derive_obs['outTempMax'], device, self.api_data, config)
            self.derive_obs['outTempMin']   = derive.tempMin(self.device_obs['outTemp'],   self.device_obs['obTime'], self.derive_obs['outTempMin'], device, self.api_data, config)
            self.derive_obs['SLP']          = derive.SLP(self.device_obs['pressure'],      device, config)
            self.derive_obs['SLPTrend']     = derive.SLPTrend(self.device_obs['pressure'], self.device_obs['obTime'], device, self.api_data, config)
            self.derive_obs['SLPMax']       = derive.SLPMax(self.device_obs['pressure'],   self.device_obs['obTime'], self.derive_obs['SLPMax'], device, self.api_data, config)
            self.derive_obs['SLPMin']       = derive.SLPMin(self.device_obs['pressure'],   self.device_obs['obTime'], self.derive_obs['SLPMin'], device, self.api_data, config)
            self.derive_obs['strikeCount']  = derive.strikeCount(self.device_obs['strikeMinute'], self.derive_obs['strikeCount'], device, self.api_data, config)
            self.derive_obs['strikeFreq']   = derive.strikeFrequency(self.device_obs['obTime'],   device, self.api_data, config)
            self.derive_obs['strikeDeltaT'] = derive.strikeDeltaT(self.device_obs['strikeTime'])

        # Derive variables from available obs_sky and obs_st observations
        if device_type in ('obs_sky', 'obs_st'):
            self.derive_obs['uvIndex']   = derive.UVIndex(self.device_obs['uvIndex'])
            self.derive_obs['peakSun']   = derive.peakSunHours(self.device_obs['radiation'],  self.derive_obs['peakSun'], device, self.api_data, config)
            self.derive_obs['windSpd']   = derive.beaufortScale(self.device_obs['windSpd'])
            self.derive_obs['windDir']   = derive.cardinalWindDir(self.device_obs['windDir'], self.device_obs['windSpd'])
            self.derive_obs['windAvg']   = derive.avgWindSpeed(self.device_obs['windSpd'],    self.derive_obs['windAvg'], device, self.api_data, config)
            self.derive_obs['gustMax']   = derive.maxWindGust(self.device_obs['windGust'],    self.derive_obs['gustMax'], device, self.api_data, config)
            self.derive_obs['rainRate']  = derive.rainRate(self.device_obs['minuteRain'])
            self.derive_obs['rainAccum'] = derive.rainAccumulation(self.device_obs['dailyRain'], self.derive_obs['rainAccum'], device, self.api_data, config)

        # Derive variables from available obs_out_air and obs_st observations
        if device_type == 'obs_in_air':
            self.derive_obs['inTempMax']   = derive.tempMax(self.device_obs['inTemp'], self.device_obs['obTime'], self.derive_obs['inTempMax'], device, self.api_data, config)
            self.derive_obs['inTempMin']   = derive.tempMin(self.device_obs['inTemp'], self.device_obs['obTime'], self.derive_obs['inTempMin'], device, self.api_data, config)

        # Derive variables from available rapid_wind observations
        if device_type == 'rapid_wind':
            self.derive_obs['rapidWindDir'] = derive.cardinalWindDir(self.device_obs['rapidWindDir'], self.device_obs['rapidWindSpd'])

        # Derive variables from available evt_strike observations
        if device_type == 'evt_strike':
            self.derive_obs['strikeDeltaT'] = derive.strikeDeltaT(self.device_obs['strikeTime'])

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
            outTemp        = observation.Units(self.device_obs['outTemp'],              config['Units']['Temp'])
            feelsLike      = observation.Units(self.derive_obs['feelsLike'],            config['Units']['Temp'])
            dewPoint       = observation.Units(self.derive_obs['dewPoint'],             config['Units']['Temp'])
            outTempDiff    = observation.Units(self.derive_obs['outTempDiff'],          config['Units']['Temp'])
            outTempTrend   = observation.Units(self.derive_obs['outTempTrend'],         config['Units']['Temp'])
            outTempMax     = observation.Units(self.derive_obs['outTempMax'],           config['Units']['Temp'])
            outTempMin     = observation.Units(self.derive_obs['outTempMin'],           config['Units']['Temp'])
            humidity       = observation.Units(self.device_obs['humidity'],             config['Units']['Other'])
            SLP            = observation.Units(self.derive_obs['SLP'],                  config['Units']['Pressure'])
            SLPTrend       = observation.Units(self.derive_obs['SLPTrend'],             config['Units']['Pressure'])
            SLPMax         = observation.Units(self.derive_obs['SLPMax'],               config['Units']['Pressure'])
            SLPMin         = observation.Units(self.derive_obs['SLPMin'],               config['Units']['Pressure'])
            strikeDist     = observation.Units(self.device_obs['strikeDist'],           config['Units']['Distance'])
            strikeDeltaT   = observation.Units(self.derive_obs['strikeDeltaT'],         config['Units']['Other'])
            strikeFreq     = observation.Units(self.derive_obs['strikeFreq'],           config['Units']['Other'])
            strike3hr      = observation.Units(self.device_obs['strike3hr'],            config['Units']['Other'])
            strikeToday    = observation.Units(self.derive_obs['strikeCount']['today'], config['Units']['Other'])
            strikeMonth    = observation.Units(self.derive_obs['strikeCount']['month'], config['Units']['Other'])
            strikeYear     = observation.Units(self.derive_obs['strikeCount']['year'],  config['Units']['Other'])

        # Convert derived variable units from obs_sky and obs_st observations
        if device_type in ('obs_sky', 'obs_st', 'obs_all'):
            rainRate       = observation.Units(self.derive_obs['rainRate'],               config['Units']['Precip'])
            todayRain      = observation.Units(self.derive_obs['rainAccum']['today'],     config['Units']['Precip'])
            yesterdayRain  = observation.Units(self.derive_obs['rainAccum']['yesterday'], config['Units']['Precip'])
            monthRain      = observation.Units(self.derive_obs['rainAccum']['month'],     config['Units']['Precip'])
            yearRain       = observation.Units(self.derive_obs['rainAccum']['year'],      config['Units']['Precip'])
            radiation      = observation.Units(self.device_obs['radiation'],              config['Units']['Other'])
            uvIndex        = observation.Units(self.derive_obs['uvIndex'],                config['Units']['Other'])
            peakSun        = observation.Units(self.derive_obs['peakSun'],                config['Units']['Other'])
            windSpd        = observation.Units(self.derive_obs['windSpd'],                config['Units']['Wind'])
            windDir        = observation.Units(self.derive_obs['windDir'],                config['Units']['Direction'])
            windGust       = observation.Units(self.device_obs['windGust'],               config['Units']['Wind'])
            windAvg        = observation.Units(self.derive_obs['windAvg'],                config['Units']['Wind'])
            windMax        = observation.Units(self.derive_obs['gustMax'],                config['Units']['Wind'])

        # Convert derived variable units from obs_in_air observations
        if device_type in ('obs_in_air',  'obs_all'):
            inTemp         = observation.Units(self.device_obs['inTemp'],    config['Units']['Temp'])
            inTempMax      = observation.Units(self.derive_obs['inTempMax'], config['Units']['Temp'])
            inTempMin      = observation.Units(self.derive_obs['inTempMin'], config['Units']['Temp'])

        # Convert derived variable units from rapid_wind observations
        if device_type in ('rapid_wind', 'obs_all'):
            rapidWindSpd   = observation.Units(self.device_obs['rapidWindSpd'], config['Units']['Wind'])
            rapidWindDir   = observation.Units(self.derive_obs['rapidWindDir'], 'degrees')

        # Convert derived variable units from available evt_strike observations
        if device_type in ('evt_strike', 'obs_all'):
            strikeDist     = observation.Units(self.device_obs['strikeDist'],   config['Units']['Distance'])
            strikeDeltaT   = observation.Units(self.derive_obs['strikeDeltaT'], config['Units']['Other'])

        # Format derived variables from obs_air and obs_st observations
        if device_type in ('obs_out_air', 'obs_st', 'obs_all'):
            self.display_obs['outTemp']       = observation.Format(outTemp,      'Temp')
            self.display_obs['FeelsLike']     = observation.Format(feelsLike,    'Temp')
            self.display_obs['DewPoint']      = observation.Format(dewPoint,     'Temp')
            self.display_obs['outTempDiff']   = observation.Format(outTempDiff,  'Temp')
            self.display_obs['outTempTrend']  = observation.Format(outTempTrend, 'Temp')
            self.display_obs['outTempMax']    = observation.Format(outTempMax,   ['Temp', 'Time'], config)
            self.display_obs['outTempMin']    = observation.Format(outTempMin,   ['Temp', 'Time'], config)
            self.display_obs['Humidity']      = observation.Format(humidity,     'Humidity')
            self.display_obs['SLP']           = observation.Format(SLP,          'Pressure')
            self.display_obs['SLPTrend']      = observation.Format(SLPTrend,     'Pressure')
            self.display_obs['SLPMax']        = observation.Format(SLPMax,       ['Pressure', 'Time'], config)
            self.display_obs['SLPMin']        = observation.Format(SLPMin,       ['Pressure', 'Time'], config)
            self.display_obs['StrikeDist']    = observation.Format(strikeDist,   'StrikeDistance')
            self.display_obs['StrikeDeltaT']  = observation.Format(strikeDeltaT, 'TimeDelta')
            self.display_obs['StrikeFreq']    = observation.Format(strikeFreq,   'StrikeFrequency')
            self.display_obs['Strikes3hr']    = observation.Format(strike3hr,    'StrikeCount')
            self.display_obs['StrikesToday']  = observation.Format(strikeToday,  'StrikeCount')
            self.display_obs['StrikesMonth']  = observation.Format(strikeMonth,  'StrikeCount')
            self.display_obs['StrikesYear']   = observation.Format(strikeYear,   'StrikeCount')

        # Format derived variables from obs_sky and obs_st observations
        if device_type in ('obs_sky', 'obs_st', 'obs_all'):
            self.display_obs['Radiation']     = observation.Format(radiation,     'Radiation')
            self.display_obs['UVIndex']       = observation.Format(uvIndex,       'UV')
            self.display_obs['peakSun']       = observation.Format(peakSun,       'peakSun')
            self.display_obs['RainRate']      = observation.Format(rainRate,      'Precip')
            self.display_obs['TodayRain']     = observation.Format(todayRain,     'Precip')
            self.display_obs['YesterdayRain'] = observation.Format(yesterdayRain, 'Precip')
            self.display_obs['MonthRain']     = observation.Format(monthRain,     'Precip')
            self.display_obs['YearRain']      = observation.Format(yearRain,      'Precip')
            self.display_obs['WindSpd']       = observation.Format(windSpd,       'Wind')
            self.display_obs['WindGust']      = observation.Format(windGust,      'Wind')
            self.display_obs['AvgWind']       = observation.Format(windAvg,       'Wind')
            self.display_obs['MaxGust']       = observation.Format(windMax,       'Wind')
            self.display_obs['WindDir']       = observation.Format(windDir,       'Direction')

        # Format derived variables from obs_in_air observations
        if device_type in ('obs_in_air', 'obs_all'):
            self.display_obs['inTemp']        = observation.Format(inTemp,    'Temp')
            self.display_obs['inTempMax']     = observation.Format(inTempMax, ['Temp', 'Time'], config)
            self.display_obs['inTempMin']     = observation.Format(inTempMin, ['Temp', 'Time'], config)

        # Format derived variables from rapid_wind observations
        if device_type in ('rapid_wind', 'obs_all'):
            self.display_obs['rapidSpd']      = observation.Format(rapidWindSpd, 'Wind')
            self.display_obs['rapidDir']      = observation.Format(rapidWindDir, 'Direction')

        # Format derived variables from evt_strike observations
        if device_type in ('evt_strike', 'obs_all'):
            self.display_obs['StrikeDist']    = observation.Format(strikeDist,   'StrikeDistance')
            self.display_obs['StrikeDeltaT']  = observation.Format(strikeDeltaT, 'TimeDelta')

        # Update display with new variables
        self.update_display(device_type)

    def reformat_display(self):
        while self.app.websocket_client.activeThreads():
            pass
        self.format_derived_variables(self.app.config, 'obs_all')

    def resetDisplay(self):
        while self.app.websocket_client.activeThreads():
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
        for Key, Value in list(self.display_obs.items()):
            if not (ob_type == 'obs_all' and 'rapid' in Key):
                try:                                                            # Don't update rapidWind display when type is 'all'
                    self.app.CurrentConditions.Obs[Key] = Value                 # as the RapidWind rose is not animated in this case
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
                        panel.setFeelsLikeIcon()
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
                        panel.setFeelsLikeIcon()
