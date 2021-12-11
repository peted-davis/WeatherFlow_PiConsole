""" Handles Websocket messages received by the Raspberry Pi Python console for
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

# Import required library modules
from lib import derivedVariables   as derive
from lib import observationFormat  as observation
from lib import requestAPI
from lib import properties

# Import required Python modules
from kivy.logger  import Logger
from kivy.clock   import mainthread
from kivy.app     import App
import time
import json

# Define empty deviceObs dictionary
deviceObs = {
        'obTime':       [None, 's'],                'pressure':     [None, 'mb'],              'outTemp':      [None, 'c'],
        'inTemp':       [None, 'c'],                'humidity':     [None, '%'],               'windSpd':      [None, 'mps'],
        'windGust':     [None, 'mps'],              'windDir':      [None, 'degrees'],         'rapidWindSpd': [None, 'mps'],
        'rapidWindDir': [None, 'degrees'],          'uvIndex':      [None, 'index'],           'radiation':    [None, 'Wm2'],
        'minuteRain':   [None, 'mm'],               'dailyRain':    [None, 'mm'],              'strikeMinute': [None, 'count'],
        'strikeTime':   [None, 's'],                'strikeDist':   [None, 'km'],              'strike3hr':    [None, 'count'],
        }

# Define empty deriveObs dictionary
deriveObs = {
        'dewPoint':     [None, 'c'],                'feelsLike':    [None, 'c', '-', '-'],        'outTempMax':   [None, 'c', '-'],
        'outTempMin':   [None, 'c', '-'],           'outTempDiff':  [None, 'dc', '-'],            'outTempTrend': [None, 'c/hr', 'c8c8c8ff'],
        'inTempMax':    [None, 'c', '-'],           'inTempMin':    [None, 'c', '-'],             'SLP':          [None, 'mb', None],
        'SLPTrend':     [None, 'mb/hr', '-', '-'],  'SLPMin':       [None, 'mb', '-'],            'SLPMax':       [None, 'mb', '-'],
        'rainRate':     [None, 'mm/hr', '-'],       'windSpd':      [None, 'mps', '-', '-', '-'], 'windAvg':      [None, 'mps'],
        'gustMax':      [None, 'mps'],              'windDir':      [None, 'degrees', '-', '-'],  'rapidWindDir': [None, 'degrees', '-', '-'],
        'rainRate':     [None, 'mm/hr', '-'],       'uvIndex':      [None, 'index'],              'peakSun':      [None, 'hrs', '-'],
        'strikeDeltaT': [None, 's', None],          'strikeFreq':   [None, '/min', None, '/min'],
        'strikeCount':
            {
            'today': [None, 'count'],
            'month': [None, 'count'],
            'year':  [None, 'count']
        },
        'rainAccum':
            {
            'today':     [None, 'mm'],
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
        self.displayObs = dict(properties.Obs())
        self.apiData    = {}
        self.transmit   = 1
        self.flagAPI    = [1, 1, 1, 1]

        # Create reference to app object
        App.get_running_app().obsParser = self
        self.app = App.get_running_app()

        # Define device and derived observations dictionary
        self.deviceObs = deviceObs.copy()
        self.deriveObs = deriveObs.copy()


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
        self.apiData[device_id] = {'flagAPI': self.flagAPI[0],
                                   '24Hrs': None,
                                   'today': None,
                                   'yesterday': None,
                                   'month': None,
                                   'year': None}

        # Discard duplicate TEMPEST Websocket messages
        if 'obs_st' in self.displayObs:
            if self.displayObs['obs_st']['obs'][0] == latestOb[0]:
                return

        # Extract required observations from latest TEMPEST Websocket JSON
        self.deviceObs['obTime']       = [latestOb[0],  's']
        self.deviceObs['windSpd']      = [latestOb[2],  'mps']
        self.deviceObs['windGust']     = [latestOb[3],  'mps']
        self.deviceObs['windDir']      = [latestOb[4],  'degrees']
        self.deviceObs['pressure']     = [latestOb[6],  'mb']
        self.deviceObs['outTemp']      = [latestOb[7],  'c']
        self.deviceObs['humidity']     = [latestOb[8],  '%']
        self.deviceObs['uvIndex']      = [latestOb[10], 'index']
        self.deviceObs['radiation']    = [latestOb[11], 'Wm2']
        self.deviceObs['minuteRain']   = [latestOb[12], 'mm']
        self.deviceObs['strikeMinute'] = [latestOb[15], 'count']
        self.deviceObs['dailyRain']    = [latestOb[18], 'mm']

        # Set wind direction to None if wind speed is zero
        #if self.deviceObs['windSpd'][0] == 0:
        #    self.deviceObs['windDir'] = [None, 'degrees']

        # Extract lightning strike data from the latest TEMPEST Websocket JSON
        # "Summary" object
        self.deviceObs['strikeTime'] = [message['summary']['strike_last_epoch'] if 'strike_last_epoch' in message['summary'] else None, 's']
        self.deviceObs['strikeDist'] = [message['summary']['strike_last_dist']  if 'strike_last_dist'  in message['summary'] else None, 'km']
        self.deviceObs['strike3hr']  = [message['summary']['strike_count_3h']   if 'strike_count_3h'   in message['summary'] else None, 'count']

        # Request required TEMPEST data from the WeatherFlow API
        self.apiData[device_id]['24Hrs'] = requestAPI.weatherflow.Last24h(device_id, latestOb[0], config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['SLPMin'][0] is None
                or self.deriveObs['SLPMax'][0] is None
                or self.deriveObs['outTempMin'][0] is None
                or self.deriveObs['outTempMax'][0] is None
                or self.deriveObs['windAvg'][0] is None
                or self.deriveObs['gustMax'][0] is None
                or self.deriveObs['peakSun'][0] is None
                or self.deriveObs['strikeCount']['today'][0] is None):
            self.apiData[device_id]['today'] = requestAPI.weatherflow.Today(device_id, config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['rainAccum']['yesterday'][0] is None):
            self.apiData[device_id]['yesterday'] = requestAPI.weatherflow.Yesterday(device_id, config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['rainAccum']['month'][0] is None
                or self.deriveObs['strikeCount']['month'][0] is None):
            self.apiData[device_id]['month'] = requestAPI.weatherflow.Month(device_id, config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['rainAccum']['year'][0] is None
                or self.deriveObs['strikeCount']['year'][0] is None):
            self.apiData[device_id]['year']  = requestAPI.weatherflow.Year(device_id, config)
        self.flagAPI[0] = 0

        # Store latest TEMPEST JSON message
        self.displayObs['obs_st'] = message

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
        self.apiData[device_id] = {'flagAPI': self.flagAPI[1],
                                   'today': None,
                                   'yesterday': None,
                                   'month': None,
                                   'year': None}

        # Discard duplicate SKY Websocket messages
        if 'obs_sky' in self.displayObs:
            if self.displayObs['obs_sky']['obs'][0] == latestOb[0]:
                return

        # Extract required observations from latest SKY Websocket JSON
        self.deviceObs['uvIndex']    = [latestOb[2],  'index']
        self.deviceObs['minuteRain'] = [latestOb[3],  'mm']
        self.deviceObs['windSpd']    = [latestOb[5],  'mps']
        self.deviceObs['windGust']   = [latestOb[6],  'mps']
        self.deviceObs['windDir']    = [latestOb[7],  'degrees']
        self.deviceObs['radiation']  = [latestOb[10], 'Wm2']
        self.deviceObs['dailyRain']  = [latestOb[11], 'mm']

        # Set wind direction to None if wind speed is zero
        #if self.deviceObs['windSpd'][0] == 0:
        #   self.deviceObs['windDir'] = [None, 'degrees']

        # Request required SKY data from the WeatherFlow API
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['windAvg'][0] is None
                or self.deriveObs['gustMax'][0] is None
                or self.deriveObs['peakSun'][0] is None):
            self.apiData[device_id]['today'] = requestAPI.weatherflow.Today(device_id, config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['rainAccum']['yesterday'][0] is None):
            self.apiData[device_id]['yesterday'] = requestAPI.weatherflow.Yesterday(device_id, config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['rainAccum']['month'][0] is None):
            self.apiData[device_id]['month'] = requestAPI.weatherflow.Month(device_id, config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['rainAccum']['year'][0] is None):
            self.apiData[device_id]['year'] = requestAPI.weatherflow.Year(device_id, config)
        self.flagAPI[1] = 0

        # Store latest SKY JSON message
        self.displayObs['obs_sky'] = message

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
        self.apiData[device_id] = {'flagAPI': self.flagAPI[2],
                                   '24Hrs': None,
                                   'today': None,
                                   'month': None,
                                   'year': None}

        # Discard duplicate outdoor AIR Websocket messages
        if 'obs_out_air' in self.displayObs:
            if self.displayObs['obs_out_air']['obs'][0] == latestOb[0]:
                return

        # Extract required observations from latest outdoor AIR Websocket JSON
        self.deviceObs['obTime']       = [latestOb[0], 's']
        self.deviceObs['pressure']     = [latestOb[1], 'mb']
        self.deviceObs['outTemp']      = [latestOb[2], 'c']
        self.deviceObs['humidity']     = [latestOb[3], '%']
        self.deviceObs['strikeMinute'] = [latestOb[4], 'count']

        # Extract lightning strike data from the latest outdoor AIR Websocket
        # JSON "Summary" object
        self.deviceObs['strikeTime'] = [message['summary']['strike_last_epoch'] if 'strike_last_epoch' in message['summary'] else None, 's']
        self.deviceObs['strikeDist'] = [message['summary']['strike_last_dist']  if 'strike_last_dist'  in message['summary'] else None, 'km']
        self.deviceObs['strike3hr']  = [message['summary']['strike_count_3h']   if 'strike_count_3h'   in message['summary'] else None, 'count']

        # Request required outdoor AIR data from the WeatherFlow API
        self.apiData[device_id]['24Hrs'] = requestAPI.weatherflow.Last24h(device_id, latestOb[0], config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['SLPMin'][0] is None
                or self.deriveObs['SLPMax'][0] is None
                or self.deriveObs['outTempMin'][0] is None
                or self.deriveObs['outTempMax'][0] is None
                or self.deriveObs['strikeCount']['today'][0] is None):
            self.apiData[device_id]['today'] = requestAPI.weatherflow.Today(device_id, config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['strikeCount']['month'][0] is None):
            self.apiData[device_id]['month'] = requestAPI.weatherflow.Month(device_id, config)
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['strikeCount']['year'][0] is None):
            self.apiData[device_id]['year']  = requestAPI.weatherflow.Year(device_id, config)
        self.flagAPI[2] = 0

        # Store latest outdoor AIR JSON message
        self.displayObs['obs_out_air'] = message

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
        self.apiData[device_id] = {'flagAPI': self.flagAPI[3],
                                   'today': None}

        # Discard duplicate indoor AIR Websocket messages
        if 'obs_in_air' in self.displayObs:
            if self.displayObs['obs_in_air']['obs'][0] == latestOb[0]:
                return

        # Extract required observations from latest indoor AIR Websocket JSON
        self.deviceObs['obTime'] = [latestOb[0], 's']
        self.deviceObs['inTemp'] = [latestOb[2], 'c']

        # Request required indoor AIR data from the WeatherFlow API
        if (self.apiData[device_id]['flagAPI']
                or self.deriveObs['inTempMin'][0] is None
                or self.deriveObs['inTempMax'][0] is None):
            self.apiData[device_id]['today'] = requestAPI.weatherflow.Today(device_id, config)
        self.flagAPI[3] = 0

        # Store latest indoor AIR JSON message
        self.displayObs['obs_in_air'] = message

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
        if 'rapid_wind' in self.displayObs:
            if self.displayObs['rapid_wind']['ob'][0] == latestOb[0]:
                return

        # Extract required observations from latest rapid_wind Websocket JSON
        self.deviceObs['rapidWindSpd'] = [latestOb[1], 'mps']
        self.deviceObs['rapidWindDir'] = [latestOb[2], 'degrees']

        # Extract wind direction from previous rapid_wind Websocket JSON
        if 'rapid_wind' in self.deviceObs:
            previousOb = self.deviceObs['rapid_wind']['ob']
            rapidWindDirOld = [previousOb[2], 'degrees']
        else:
            rapidWindDirOld = [0, 'degrees']

        # If windspeed is zero, freeze direction at last direction of non-zero
        # wind speed and edit latest rapid_wind Websocket JSON message.
        if self.deviceObs['rapidWindSpd'][0] == 0:
            self.deviceObs['rapidWindDir'] = rapidWindDirOld
            message['ob'][2] = rapidWindDirOld[0]

        # Store latest rapid_wind Websocket JSON message
        self.displayObs['rapid_wind'] = message

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
        if 'evt_strike' in self.displayObs:
            if self.displayObs['evt_strike']['evt'][0] == latestEvt[0]:
                return

        # Extract required observations from latest evt_strike Websocket JSON
        self.deviceObs['strikeTime'] = [latestEvt[0], 's']
        self.deviceObs['strikeDist'] = [latestEvt[1], 'km']

        # Store latest evt_strike JSON message
        self.displayObs['evt_strike'] = message

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
            self.deriveObs['feelsLike']    = derive.feelsLike(self.deviceObs['outTemp'], self.deviceObs['humidity'], self.deviceObs['windSpd'], config)
            self.deriveObs['dewPoint']     = derive.dewPoint(self.deviceObs['outTemp'], self.deviceObs['humidity'])
            self.deriveObs['outTempDiff']  = derive.tempDiff(self.deviceObs['outTemp'], self.deviceObs['obTime'], device, self.apiData, config)
            self.deriveObs['outTempTrend'] = derive.tempTrend(self.deviceObs['outTemp'], self.deviceObs['obTime'], device, self.apiData, config)
            self.deriveObs['outTempMax']   = derive.tempMax(self.deviceObs['outTemp'], self.deviceObs['obTime'], self.deriveObs['outTempMax'], device, self.apiData, config)
            self.deriveObs['outTempMin']   = derive.tempMin(self.deviceObs['outTemp'], self.deviceObs['obTime'], self.deriveObs['outTempMin'], device, self.apiData, config)
            self.deriveObs['SLP']          = derive.SLP(self.deviceObs['pressure'], device, config)
            self.deriveObs['SLPTrend']     = derive.SLPTrend(self.deviceObs['pressure'], self.deviceObs['obTime'], device, self.apiData, config)
            self.deriveObs['SLPMax']       = derive.SLPMax(self.deviceObs['pressure'], self.deviceObs['obTime'], self.deriveObs['SLPMax'], device, self.apiData, config)
            self.deriveObs['SLPMin']       = derive.SLPMin(self.deviceObs['pressure'], self.deviceObs['obTime'], self.deriveObs['SLPMin'], device, self.apiData, config)
            self.deriveObs['strikeCount']  = derive.strikeCount(self.deviceObs['strikeMinute'], self.deriveObs['strikeCount'], device, self.apiData, config)
            self.deriveObs['strikeFreq']   = derive.strikeFrequency(self.deviceObs['obTime'], device, self.apiData, config)
            self.deriveObs['strikeDeltaT'] = derive.strikeDeltaT(self.deviceObs['strikeTime'])

        # Derive variables from available obs_sky and obs_st observations
        if device_type in ('obs_sky', 'obs_st'):
            self.deriveObs['uvIndex']   = derive.UVIndex(self.deviceObs['uvIndex'])
            self.deriveObs['peakSun']   = derive.peakSunHours(self.deviceObs['radiation'], self.deriveObs['peakSun'], device, self.apiData, config)
            self.deriveObs['windSpd']   = derive.beaufortScale(self.deviceObs['windSpd'])
            self.deriveObs['windDir']   = derive.cardinalWindDir(self.deviceObs['windDir'], self.deviceObs['windSpd'])
            self.deriveObs['windAvg']   = derive.avgWindSpeed(self.deviceObs['windSpd'], self.deriveObs['windAvg'], device, self.apiData, config)
            self.deriveObs['gustMax']   = derive.maxWindGust(self.deviceObs['windGust'], self.deriveObs['gustMax'], device, self.apiData, config)
            self.deriveObs['rainRate']  = derive.rainRate(self.deviceObs['minuteRain'])
            self.deriveObs['rainAccum'] = derive.rainAccumulation(self.deviceObs['dailyRain'], self.deriveObs['rainAccum'], device, self.apiData, config)

        # Derive variables from available obs_out_air and obs_st observations
        if device_type == 'obs_in_air':
            self.deriveObs['inTempMax']   = derive.tempMax(self.deviceObs['inTemp'], self.deviceObs['obTime'], self.deriveObs['inTempMax'], device, self.apiData, config)
            self.deriveObs['inTempMin']   = derive.tempMin(self.deviceObs['inTemp'], self.deviceObs['obTime'], self.deriveObs['inTempMin'], device, self.apiData, config)

        # Derive variables from available rapid_wind observations
        if device_type == 'rapid_wind':
            self.deriveObs['rapidWindDir'] = derive.cardinalWindDir(self.deviceObs['rapidWindDir'], self.deviceObs['rapidWindSpd'])

        # Derive variables from available evt_strike observations
        if device_type == 'evt_strike':
            self.deriveObs['strikeDeltaT'] = derive.strikeDeltaT(self.deviceObs['strikeTime'])

        # Format derived observations
        self.formatDerivedVariables(config, device_type)


    def formatDerivedVariables(self, config, device_type):

        """ Format derived variables from available device observations

        INPUTS:
            config              Console configuration object
            device_type         Device type
        """

        # Convert derived variable units from obs_out_air and obs_st observations
        if device_type in ('obs_out_air', 'obs_st', 'obs_all'):
            outTemp        = observation.Units(self.deviceObs['outTemp'],              config['Units']['Temp'])
            feelsLike      = observation.Units(self.deriveObs['feelsLike'],            config['Units']['Temp'])
            dewPoint       = observation.Units(self.deriveObs['dewPoint'],             config['Units']['Temp'])
            outTempDiff    = observation.Units(self.deriveObs['outTempDiff'],          config['Units']['Temp'])
            outTempTrend   = observation.Units(self.deriveObs['outTempTrend'],         config['Units']['Temp'])
            outTempMax     = observation.Units(self.deriveObs['outTempMax'],           config['Units']['Temp'])
            outTempMin     = observation.Units(self.deriveObs['outTempMin'],           config['Units']['Temp'])
            humidity       = observation.Units(self.deviceObs['humidity'],             config['Units']['Other'])
            SLP            = observation.Units(self.deriveObs['SLP'],                  config['Units']['Pressure'])
            SLPTrend       = observation.Units(self.deriveObs['SLPTrend'],             config['Units']['Pressure'])
            SLPMax         = observation.Units(self.deriveObs['SLPMax'],               config['Units']['Pressure'])
            SLPMin         = observation.Units(self.deriveObs['SLPMin'],               config['Units']['Pressure'])
            strikeDist     = observation.Units(self.deviceObs['strikeDist'],           config['Units']['Distance'])
            strikeDeltaT   = observation.Units(self.deriveObs['strikeDeltaT'],         config['Units']['Other'])
            strikeFreq     = observation.Units(self.deriveObs['strikeFreq'],           config['Units']['Other'])
            strike3hr      = observation.Units(self.deviceObs['strike3hr'],            config['Units']['Other'])
            strikeToday    = observation.Units(self.deriveObs['strikeCount']['today'], config['Units']['Other'])
            strikeMonth    = observation.Units(self.deriveObs['strikeCount']['month'], config['Units']['Other'])
            strikeYear     = observation.Units(self.deriveObs['strikeCount']['year'],  config['Units']['Other'])

        # Convert derived variable units from obs_sky and obs_st observations
        if device_type in ('obs_sky', 'obs_st', 'obs_all'):
            rainRate       = observation.Units(self.deriveObs['rainRate'],               config['Units']['Precip'])
            todayRain      = observation.Units(self.deriveObs['rainAccum']['today'],     config['Units']['Precip'])
            yesterdayRain  = observation.Units(self.deriveObs['rainAccum']['yesterday'], config['Units']['Precip'])
            monthRain      = observation.Units(self.deriveObs['rainAccum']['month'],     config['Units']['Precip'])
            yearRain       = observation.Units(self.deriveObs['rainAccum']['year'],      config['Units']['Precip'])
            radiation      = observation.Units(self.deviceObs['radiation'],              config['Units']['Other'])
            uvIndex        = observation.Units(self.deriveObs['uvIndex'],                config['Units']['Other'])
            peakSun        = observation.Units(self.deriveObs['peakSun'],                config['Units']['Other'])
            windSpd        = observation.Units(self.deriveObs['windSpd'],                config['Units']['Wind'])
            windDir        = observation.Units(self.deriveObs['windDir'],                config['Units']['Direction'])
            windGust       = observation.Units(self.deviceObs['windGust'],               config['Units']['Wind'])
            windAvg        = observation.Units(self.deriveObs['windAvg'],                config['Units']['Wind'])
            windMax        = observation.Units(self.deriveObs['gustMax'],                config['Units']['Wind'])

        # Convert derived variable units from obs_in_air observations
        if device_type in ('obs_in_air',  'obs_all'):
            inTemp         = observation.Units(self.deviceObs['inTemp'],    config['Units']['Temp'])
            inTempMax      = observation.Units(self.deriveObs['inTempMax'], config['Units']['Temp'])
            inTempMin      = observation.Units(self.deriveObs['inTempMin'], config['Units']['Temp'])

        # Convert derived variable units from rapid_wind observations
        if device_type in ('rapid_wind', 'obs_all'):
            rapidWindSpd   = observation.Units(self.deviceObs['rapidWindSpd'], config['Units']['Wind'])
            rapidWindDir   = observation.Units(self.deriveObs['rapidWindDir'], 'degrees')

        # Convert derived variable units from available evt_strike observations
        if device_type in ('evt_strike', 'obs_all'):
            strikeDist     = observation.Units(self.deviceObs['strikeDist'],   config['Units']['Distance'])
            strikeDeltaT   = observation.Units(self.deriveObs['strikeDeltaT'], config['Units']['Other'])

        # Format derived variables from obs_air and obs_st observations
        if device_type in ('obs_out_air', 'obs_st', 'obs_all'):
            self.displayObs['outTemp']       = observation.Format(outTemp,      'Temp')
            self.displayObs['FeelsLike']     = observation.Format(feelsLike,    'Temp')
            self.displayObs['DewPoint']      = observation.Format(dewPoint,     'Temp')
            self.displayObs['outTempDiff']   = observation.Format(outTempDiff,  'Temp')
            self.displayObs['outTempTrend']  = observation.Format(outTempTrend, 'Temp')
            self.displayObs['outTempMax']    = observation.Format(outTempMax,   ['Temp', 'Time'], config)
            self.displayObs['outTempMin']    = observation.Format(outTempMin,   ['Temp', 'Time'], config)
            self.displayObs['Humidity']      = observation.Format(humidity,     'Humidity')
            self.displayObs['SLP']           = observation.Format(SLP,          'Pressure')
            self.displayObs['SLPTrend']      = observation.Format(SLPTrend,     'Pressure')
            self.displayObs['SLPMax']        = observation.Format(SLPMax,       ['Pressure', 'Time'], config)
            self.displayObs['SLPMin']        = observation.Format(SLPMin,       ['Pressure', 'Time'], config)
            self.displayObs['StrikeDist']    = observation.Format(strikeDist,   'StrikeDistance')
            self.displayObs['StrikeDeltaT']  = observation.Format(strikeDeltaT, 'TimeDelta')
            self.displayObs['StrikeFreq']    = observation.Format(strikeFreq,   'StrikeFrequency')
            self.displayObs['Strikes3hr']    = observation.Format(strike3hr,    'StrikeCount')
            self.displayObs['StrikesToday']  = observation.Format(strikeToday,  'StrikeCount')
            self.displayObs['StrikesMonth']  = observation.Format(strikeMonth,  'StrikeCount')
            self.displayObs['StrikesYear']   = observation.Format(strikeYear,   'StrikeCount')

        # Format derived variables from obs_sky and obs_st observations
        if device_type in ('obs_sky', 'obs_st', 'obs_all'):
            self.displayObs['Radiation']     = observation.Format(radiation,     'Radiation')
            self.displayObs['UVIndex']       = observation.Format(uvIndex,       'UV')
            self.displayObs['peakSun']       = observation.Format(peakSun,       'peakSun')
            self.displayObs['RainRate']      = observation.Format(rainRate,      'Precip')
            self.displayObs['TodayRain']     = observation.Format(todayRain,     'Precip')
            self.displayObs['YesterdayRain'] = observation.Format(yesterdayRain, 'Precip')
            self.displayObs['MonthRain']     = observation.Format(monthRain,     'Precip')
            self.displayObs['YearRain']      = observation.Format(yearRain,      'Precip')
            self.displayObs['WindSpd']       = observation.Format(windSpd,       'Wind')
            self.displayObs['WindGust']      = observation.Format(windGust,      'Wind')
            self.displayObs['AvgWind']       = observation.Format(windAvg,       'Wind')
            self.displayObs['MaxGust']       = observation.Format(windMax,       'Wind')
            self.displayObs['WindDir']       = observation.Format(windDir,       'Direction')

        # Format derived variables from obs_in_air observations
        if device_type in ('obs_in_air', 'obs_all'):
            self.displayObs['inTemp']        = observation.Format(inTemp,    'Temp')
            self.displayObs['inTempMax']     = observation.Format(inTempMax, ['Temp', 'Time'], config)
            self.displayObs['inTempMin']     = observation.Format(inTempMin, ['Temp', 'Time'], config)

        # Format derived variables from rapid_wind observations
        if device_type in ('rapid_wind', 'obs_all'):
            self.displayObs['rapidSpd']      = observation.Format(rapidWindSpd, 'Wind')
            self.displayObs['rapidDir']      = observation.Format(rapidWindDir, 'Direction')

        # Format derived variables from evt_strike observations
        if device_type in ('evt_strike', 'obs_all'):
            self.displayObs['StrikeDist']    = observation.Format(strikeDist,   'StrikeDistance')
            self.displayObs['StrikeDeltaT']  = observation.Format(strikeDeltaT, 'TimeDelta')

        # Update display with new variables
        self.updateDisplay(device_type)


    def reformatDisplay(self):
        while self.app.websocket_client.activeThreads():
            pass
        self.formatDerivedVariables(self.app.config, 'obs_all')


    def resetDisplay(self):
        while self.app.websocket_client.activeThreads():
            pass
        self.app.CurrentConditions.Obs = properties.Obs()
        self.displayObs = dict(properties.Obs())
        self.deviceObs = deviceObs.copy()
        self.deriveObs = deriveObs.copy()
        self.updateDisplay('obs_reset')


    @mainthread
    def updateDisplay(self, type):

        """ Update display with new variables derived from latest websocket message

        INPUTS:
            type                Latest Websocket message type
            derivedObs          Derived variables from latest Websocket message
            Console             Console object
        """

        # Update display values with new derived observations
        for Key, Value in self.displayObs.items():
            if not (type == 'obs_all' and 'rapid' in Key):                  # Don't update rapidWind display when type is 'all'
                self.app.CurrentConditions.Obs[Key] = Value                 # as the RapidWind rose is not animated in this case

        # Update display graphics with new derived observations
        if type == 'rapid_wind':
            if hasattr(self.app, 'WindSpeedPanel'):
                for panel in getattr(self.app, 'WindSpeedPanel'):
                    panel.animateWindRose()
        elif type == 'evt_strike':
            if self.app.config['Display']['LightningPanel'] == '1':
                for ii, Button in enumerate(self.app.CurrentConditions.buttonList):
                    if "Lightning" in Button[2]:
                        self.app.CurrentConditions.switchPanel([], Button)
            if hasattr(self.app, 'LightningPanel'):
                for panel in getattr(self.app, 'LightningPanel'):
                    panel.setLightningBoltIcon()
                    panel.animateLightningBoltIcon()
        else:
            if type in ['obs_st', 'obs_air', 'obs_all', 'obs_reset']:
                if hasattr(self.app, 'TemperaturePanel'):
                    for panel in getattr(self.app, 'TemperaturePanel'):
                        panel.setFeelsLikeIcon()
                if hasattr(self.app, 'LightningPanel'):
                    for panel in getattr(self.app, 'LightningPanel'):
                        panel.setLightningBoltIcon()
                if hasattr(self.app, 'BarometerPanel'):
                    for panel in getattr(self.app, 'BarometerPanel'):
                        panel.setBarometerArrow()
            if type in ['obs_st', 'obs_sky', 'obs_all', 'obs_reset']:
                if hasattr(self.app, 'WindSpeedPanel'):
                    for panel in getattr(self.app, 'WindSpeedPanel'):
                        panel.setWindIcons()
                if hasattr(self.app, 'SunriseSunsetPanel'):
                    for panel in getattr(self.app, 'SunriseSunsetPanel'):
                        panel.setUVBackground()
                if hasattr(self.app, 'RainfallPanel'):
                    for panel in getattr(self.app, 'RainfallPanel'):
                        panel.animateRainRate()
                if hasattr(self.app, 'TemperaturePanel'):
                    for panel in getattr(self.app, 'TemperaturePanel'):
                        panel.setFeelsLikeIcon()
