# WeatherFlow PiConsole: Raspberry Pi Python console for Weather Flow
# Smart Home Weather Station. Copyright (C) 2018-2019  Peter Davis

# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.

# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

# ==============================================================================
# CREATE OR UPDATE wfpiconsole.ini FILE
# ==============================================================================
from lib import configCreate
from pathlib import Path
if not Path('wfpiconsole.ini').is_file():
    configCreate.create_ini()
else:
    configCreate.update_ini()

# ==============================================================================
# INITIALISE KIVY BACKEND BASED ON CURRENT HARDWARE TYPE
# ==============================================================================
import configparser
import os

# Load config file
config = configparser.ConfigParser()
config.read('wfpiconsole.ini')

# Initialise Kivy backend based on current hardware
if config['System']['Hardware'] == 'Pi4':
    os.environ['KIVY_GRAPHICS'] = 'gles'
    os.environ['KIVY_WINDOW'] = 'sdl2'
    os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '1'
elif 'Pi' in config['System']['Hardware']:
    os.environ['KIVY_GL_BACKEND'] = 'gl'

# ==============================================================================
# INITIALISE KIVY TWISTED WEBSOCKET CLIENT
# ==============================================================================
from kivy.support import install_twisted_reactor
install_twisted_reactor()

from twisted.python import log
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.policies import TimeoutMixin
from autobahn.twisted.websocket import WebSocketClientProtocol,WebSocketClientFactory

# Specifies behaviour of Websocket Client
class WeatherFlowClientProtocol(WebSocketClientProtocol,TimeoutMixin):

    def onConnect(self, response):
        self.factory.resetDelay()
        self.setTimeout(300)

    def onOpen(self):
        self.factory._proto = self

    def onMessage(self,payload,isBinary):
        Message = json.loads(payload.decode('utf8'))
        self.factory._app.WebsocketDecodeMessage(Message)
        self.resetTimeout()

    def timeoutConnection(self):
        self.transport.loseConnection()

    def onClose(self,wasClean,code,reason):
        self.factory._proto = None

# Specifies Websocket Factory
class WeatherFlowClientFactory(WebSocketClientFactory,ReconnectingClientFactory):

    # Define protocol and reconnection properties
    protocol = WeatherFlowClientProtocol
    initialDelay = 60
    maxDelay = 60
    jitter = 0

    def clientConnectionFailed(self,connector,reason):
        print('Client connection failed .. retrying ..')
        self.retry(connector)

    def clientConnectionLost(self,connector,reason):
        print('Client connection lost .. retrying ..')
        self.retry(connector)

    def __init__(self, url, app):
        WebSocketClientFactory.__init__(self,url)
        self._app = app
        self._proto = None

# ==============================================================================
# IMPORT REQUIRED CORE KIVY MODULES
# ==============================================================================
from kivy.app import App
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.config import ConfigParser
from kivy.metrics import dp
from kivy.properties import DictProperty, NumericProperty, ConfigParserProperty

# ==============================================================================
# IMPORT REQUIRED SYSTEM MODULES
# ==============================================================================
from twisted.internet import reactor,ssl
from datetime import datetime, date, time, timedelta
from packaging import version
from lib import sager
import time as UNIX
import numpy as np
import pytz
import math
import bisect
import json
import requests
import ephem
import sys

# ==============================================================================
# IMPORT REQUIRED KIVY GRAPHICAL AND SETTINGS MODULES
# ==============================================================================
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.settings import SettingsWithSidebar, SettingOptions
from kivy.uix.settings import SettingString, SettingSpacer, SettingItem
from kivy.uix.screenmanager import ScreenManager,Screen

# ==============================================================================
# DEFINE GLOBAL FUNCTIONS AND VARIABLES
# ==============================================================================
# Define global variables
NaN = float('NaN')

# CIRCULAR MEAN
# ------------------------------------------------------------------------------
def CircularMean(angles):
    angles = np.radians(angles)
    r = np.nanmean(np.exp(1j*angles))
    return np.angle(r, deg=True) % 360

# VERIFY IF DATA IS VALID JSON STRING, AND FIELD IS NOT NONE
# ------------------------------------------------------------------------------
def VerifyJSON(Data,Type,Field):
    if not Data.ok:
        return False
    try:
        Data.json()
    except ValueError:
        return False
    else:
        Data = Data.json()
        if isinstance(Data,dict):
            if Type == 'WeatherFlow':
                if 'SUCCESS' in Data['status']['status_message'] and Field in Data and Data[Field] is not None:
                    return True
                else:
                    return False
            elif Type == 'CheckWX':
                if Field in Data and Data[Field] is not None:
                    return True
                else:
                    return False
        else:
            return False

# ==============================================================================
# DEFINE 'WeatherFlowPiConsole' APP CLASS
# ==============================================================================
class wfpiconsole(App):

    # Define App class dictionary properties
    Sky = DictProperty          ([('WindSpd','----'),('WindGust','--'),('WindDir','---'),
                                  ('AvgWind','--'),('MaxGust','--'),('RainRate','---'),
                                  ('TodayRain','--'),('YesterdayRain','--'),('MonthRain','--'),
                                  ('YearRain','--'),('Radiation','----'),('UV','---'),
                                  ('Time','-'),('Battery','--'),('StatusIcon','Error')])
    Air = DictProperty          ([('Temp','--'),('MinTemp','---'),('MaxTemp','---'),
                                  ('Humidity','--'),('DewPoint','--'),('Pres','---'),
                                  ('MaxPres','---'),('MinPres','---'),('PresTrend','----'),
                                  ('FeelsLike','----'),('StrikeDeltaT','----'),('StrikeDist','--'),
                                  ('Strikes3hr','-'),('StrikesToday','-'),('StrikesMonth','-'),
                                  ('StrikesYear','-'),('Time','-'),('Battery','--'),
                                  ('StatusIcon','Error')])
    Rapid = DictProperty        ([('Time','-'),('Speed','--'),('Direc','----')])
    Breathe = DictProperty      ([('Temp','--'),('MinTemp','---'),('MaxTemp','---')])
    SunData = DictProperty      ([('Sunrise',['-','-']),('Sunset',['-','-']),('SunAngle','-'),
                                  ('Event',['-','-','-']),('ValidDate','--')])
    MoonData = DictProperty     ([('Moonrise',['-','-']),('Moonset',['-','-']),('NewMoon','--'),
                                  ('FullMoon','--'),('Phase','---')])
    MetData = DictProperty      ([('Temp','--'),('Precip','--'),('WindSpd','--'),
                                  ('WindDir','--'),('Weather','Building'),('Valid','--')])
    Sager = DictProperty        ([('Forecast','--'),('Issued','--')])
    System = DictProperty       ([('LatestVer','--')])

    # Define App class configParser properties
    BarometerMax = ConfigParserProperty('-','System','BarometerMax','wfpiconsole')
    BarometerMin = ConfigParserProperty('-','System','BarometerMin','wfpiconsole')
    ForecastLocn = ConfigParserProperty('-','Station','ForecastLocn','wfpiconsole')
    TimeFormat = ConfigParserProperty('-','Display','TimeFormat','wfpiconsole')
    DateFormat = ConfigParserProperty('-','Display','DateFormat','wfpiconsole')
    Version = ConfigParserProperty('-','System','Version','wfpiconsole')

    # Define App class numeric properties
    RapidIcon = NumericProperty(0)

    # BUILD 'WeatherFlowPiConsole' APP CLASS
    # --------------------------------------------------------------------------
    def build(self):

        # Load user configuration from wfpiconsole.ini and define Settings panel
        # type
        self.config = ConfigParser(allow_no_value=True,name='wfpiconsole')
        self.config.optionxform = str
        self.config.read('wfpiconsole.ini')
        self.settings_cls = SettingsWithSidebar

        # Force window size if required based on hardware type
        if self.config['System']['Hardware'] == 'Pi4':
            Window.size = (800,480)
            Window.borderless = 1
            Window.top = 0
        elif self.config['System']['Hardware'] == 'Other':
            Window.size = (800,480)

        # Initialise Sunrise and Sunset time, Moonrise andMoonset time, and
        # MetOffice or DarkSky weather forecast data
        self.SunriseSunset()
        self.MoonriseMoonset()
        self.DownloadForecast()

        # Initialise Sager Weathercaster forecast, and check for latest version
        Clock.schedule_once(self.SagerForecast)
        Clock.schedule_once(self.CheckVersion)

        # Initialise websocket connection
        self.WebsocketConnect()

        # Define Kivy loop schedule
        Clock.schedule_interval(self.SkyAirStatus,1.0)
        Clock.schedule_interval(self.UpdateMethods,1.0)
        Clock.schedule_interval(self.SunTransit,1.0)
        Clock.schedule_interval(self.MoonPhase,1.0)

        # Store required links items in CurrentConditions class
        self.CurrentConditions = self.root.children[0]
        self.LightningPanel = self.root.children[0].ids.LightningPanel
        self.LightningPanelBackground = self.root.children[0].ids.LightningPanelBackground
        self.LightningPanelIcon = self.root.children[0].ids.LightningPanelIcon
        self.RainLightningButton = self.root.children[0].ids.RainLightningButton

    # BUILD 'WeatherFlowPiConsole' APP CLASS SETTINGS
    # --------------------------------------------------------------------------
    def build_settings(self,settings):

        # Register setting types
        settings.register_type('ScrollOptions',SettingScrollOptions)
        settings.register_type('FixedOptions',SettingFixedOptions)
        settings.register_type('ToggleTemperature',SettingToggleTemperature)

        # Add required panels to setting screen. Remove Kivy settings panel
        settings.add_json_panel('Display',self.config,data=configCreate.settings_json('Display'))
        settings.add_json_panel('Units',self.config,data=configCreate.settings_json('Units'))
        settings.add_json_panel('Feels Like',self.config,data=configCreate.settings_json('FeelsLike'))
        self.use_kivy_settings  =  False

    # OVERLOAD 'on_config_change' TO MAKE NECESSARY CHANGES TO CONFIG VALUES
    # WHEN REQUIRED
    # --------------------------------------------------------------------------
    def on_config_change(self,config,section,key,value):

        # Update current weather forecast and Sager Weathercaster forecast when
        # temperature or wind speed units are changed
        if section == 'Units' and key in ['Temp','Wind']:
            if self.config['Station']['Country'] == 'GB':
                self.ExtractMetOfficeForecast()
            else:
                self.ExtractDarkSkyForecast()
            if key == 'Wind':
                self.Sager['Dial']['Units'] = value
                self.Sager['Forecast'] = sager.Forecast(self.Sager['Dial'])

        # Update "Feels Like" temperature cutoffs in wfpiconsole.ini and the
        # settings screen when temperature units are changed
        if section == 'Units' and key == 'Temp':
            for Field in self.config['FeelsLike']:
                if 'c' in value:
                    Temp = str(round((float(self.config['FeelsLike'][Field])-32) * 5/9))
                    self.config.set('FeelsLike',Field,Temp)
                elif 'f' in value:
                    Temp = str(round(float(self.config['FeelsLike'][Field])*9/5 + 32))
                    self.config.set('FeelsLike',Field,Temp)
            self.config.write()
            panels = self._app_settings.children[0].content.panels
            for Field in self.config['FeelsLike']:
                for panel in panels.values():
                    if panel.title == 'Feels Like':
                        for item in panel.children:
                            if isinstance(item,Factory.SettingToggleTemperature):
                                if item.title.replace(' ','') == Field:
                                    item.value = self.config['FeelsLike'][Field]

        # Update barometer limits when pressure units are changed
        if section == 'Units' and key == 'Pressure':
            Units = ['mb','hpa','inhg','mmhg']
            Max = ['1050','1050','31.0','788']
            Min = ['950','950','28.0','713']
            self.config.set('System','BarometerMax',Max[Units.index(value)])
            self.config.set('System','BarometerMin',Min[Units.index(value)])

    # CONNECT TO THE WEATHER FLOW WEBSOCKET SERVER
    # --------------------------------------------------------------------------
    def WebsocketConnect(self):
        Template = 'ws://ws.weatherflow.com/swd/data?api_key={}'
        Server = Template.format(self.config['Keys']['WeatherFlow'])
        self._factory = WeatherFlowClientFactory(Server,self)
        reactor.connectTCP('ws.weatherflow.com',80,self._factory)

    # SEND MESSAGE TO THE WEATHER FLOW WEBSOCKET SERVER
    # --------------------------------------------------------------------------
    def WebsocketSendMessage(self,Message):
        Message = Message.encode('utf8')
        proto = self._factory._proto
        if Message and proto:
            proto.sendMessage(Message)

    # DECODE THE WEATHER FLOW WEBSOCKET MESSAGE
    # --------------------------------------------------------------------------
    def WebsocketDecodeMessage(self,Msg):

        # Extract type of received message
        Type = Msg['type']

        # Initialise data streaming upon connection of websocket
        if Type == 'connection_opened':
            self.WebsocketSendMessage('{"type":"listen_start",' +
                                      ' "device_id":' + self.config['Station']['SkyID'] + ',' +
                                       ' "id":"Sky"}')
            self.WebsocketSendMessage('{"type":"listen_rapid_start",' +
                                      ' "device_id":' + self.config['Station']['SkyID'] + ',' +
                                       ' "id":"RapidSky"}')
            self.WebsocketSendMessage('{"type":"listen_start",' +
                                      ' "device_id":' + self.config['Station']['OutdoorID'] + ',' +
                                       ' "id":"Outdoor"}')

        # Extract observations from obs_sky websocket message
        elif Type == 'obs_sky':
            self.WebsocketObsSky(Msg)

        # Extract observations from obs_air websocket message
        elif Type == 'obs_air':
            self.WebsocketObsAir(Msg)

        # Extract observations from rapid_wind websocket message
        elif Type == 'rapid_wind':
            self.WebsocketRapidWind(Msg)

        # Extract observations from evt_strike websocket message
        elif Type == 'evt_strike':
            self.WebsocketEvtStrike(Msg)

    # EXTRACT OBSERVATIONS FROM OBS_SKY WEBSOCKET JSON MESSAGE
    # --------------------------------------------------------------------------
    def WebsocketObsSky(self,Msg):

        # Replace missing observations from latest SKY Websocket JSON with NaN
        Obs = [x if x != None else NaN for x in Msg['obs'][0]]

        # Extract required observations from latest SKY Websocket JSON
        Time = [Obs[0],'s']
        UV = [Obs[2],'index']
        Rain = [Obs[3],'mm']
        WindSpd = [Obs[5],'mps']
        WindGust = [Obs[6],'mps']
        WindDir = [Obs[7],'degrees']
        Battery = [Obs[8],'v']
        Radiation = [Obs[10],' W m[sup]-2[/sup]']

        # Store latest SKY Websocket JSON
        self.Sky['Obs'] = Obs

        # Extract required observations from latest AIR Websocket JSON
        if 'Obs' in self.Air:
            Temp = [self.Air['Obs'][2],'c']
            Humidity = [self.Air['Obs'][3],'%']
        else:
            Temp = None
            Humidity = None

        # Set wind direction to None if wind speed is zero
        if WindSpd[0] == 0:
            WindDir = [None,'degrees']

        # Calculate derived variables from SKY observations
        FeelsLike = self.FeelsLike(Temp,Humidity,WindSpd)
        RainRate = self.RainRate(Rain)
        TodayRain,YesterdayRain,MonthRain,YearRain = self.RainAccumulation(Rain)
        AvgWind = self.MeanWindSpeed(WindSpd)
        MaxGust = self.SkyObsMaxMin(WindSpd,WindGust)
        Beaufort = self.BeaufortScale(WindSpd)
        WindDir = self.CardinalWindDirection(WindDir,WindSpd)
        UV = self.UVIndex(UV)

        # Convert observation units as required
        RainRate = self.ObservationUnits(RainRate,self.config['Units']['Precip'])
        TodayRain = self.ObservationUnits(TodayRain,self.config['Units']['Precip'])
        YesterdayRain = self.ObservationUnits(YesterdayRain,self.config['Units']['Precip'])
        MonthRain = self.ObservationUnits(MonthRain,self.config['Units']['Precip'])
        YearRain = self.ObservationUnits(YearRain,self.config['Units']['Precip'])
        WindSpd = self.ObservationUnits(WindSpd,self.config['Units']['Wind'])
        WindDir = self.ObservationUnits(WindDir,self.config['Units']['Direction'])
        WindGust = self.ObservationUnits(WindGust,self.config['Units']['Wind'])
        AvgWind = self.ObservationUnits(AvgWind,self.config['Units']['Wind'])
        MaxGust = self.ObservationUnits(MaxGust,self.config['Units']['Wind'])
        FeelsLike = self.ObservationUnits(FeelsLike,self.config['Units']['Temp'])

        # Define station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])

        # Define SKY Kivy label binds
        self.Sky['Time'] =  datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M:%S')
        self.Sky['RainRate'] = self.ObservationFormat(RainRate,'Precip')
        self.Sky['TodayRain'] = self.ObservationFormat(TodayRain,'Precip')
        self.Sky['YesterdayRain'] = self.ObservationFormat(YesterdayRain,'Precip')
        self.Sky['MonthRain'] = self.ObservationFormat(MonthRain,'Precip')
        self.Sky['YearRain'] = self.ObservationFormat(YearRain,'Precip')
        self.Sky['WindSpd'] = self.ObservationFormat(WindSpd,'Wind') + Beaufort
        self.Sky['WindGust'] = self.ObservationFormat(WindGust,'Wind')
        self.Sky['AvgWind'] = self.ObservationFormat(AvgWind,'Wind')
        self.Sky['MaxGust'] = self.ObservationFormat(MaxGust,'Wind')
        self.Sky['Radiation'] = self.ObservationFormat(Radiation,'Radiation')
        self.Sky['UV'] = self.ObservationFormat(UV,'UV')
        self.Sky['Battery'] = self.ObservationFormat(Battery,'Battery')
        self.Sky['WindDir'] = self.ObservationFormat(WindDir,'Direction')

        # Define AIR Kivy label binds
        self.Air['FeelsLike'] = self.ObservationFormat(FeelsLike,'Temp')

    # EXTRACT OBSERVATIONS FROM OBS_AIR WEBSOCKET JSON MESSAGE
    # --------------------------------------------------------------------------
    def WebsocketObsAir(self,Msg):

        # Replace missing observations in latest AIR Websocket JSON with NaN
        Obs = [x if x != None else NaN for x in Msg['obs'][0]]

        # Extract required observations from latest AIR Websocket JSON "Obs"
        # object
        Time = [Obs[0],'s']
        Pres = [Obs[1],'mb']
        Temp = [Obs[2],'c']
        Humidity = [Obs[3],' %']
        Battery = [Obs[6],' v']
        StrikeCount = [Obs[4],'count']

        # Extract lightning strike data from the latest AIR Websocket JSON
        # "Summary" object
        StrikeTime = [Msg['summary']['strike_last_epoch'] if 'strike_last_epoch' in Msg['summary'] else NaN,'s']
        StrikeDist = [Msg['summary']['strike_last_dist'] if 'strike_last_dist' in Msg['summary'] else NaN,'km']
        Strikes3hr = [Msg['summary']['strike_count_3h'] if 'strike_count_3h' in Msg['summary'] else NaN,'count']

        # Store latest AIR Websocket JSON
        self.Air['Obs'] = Obs

        # Extract required observations from latest SKY Websocket JSON
        if 'Obs' in self.Sky:
            WindSpd = [self.Sky['Obs'][5],'mps']
        else:
            WindSpd = None

        # Get last three hours of AIR data using WeatherFlow API
        Data3h = self.GetData3h('Air',Obs)

        # Calculate derived variables from AIR observations
        DewPoint = self.DewPoint(Temp,Humidity)
        FeelsLike = self.FeelsLike(Temp,Humidity,WindSpd)
        SLP = self.SeaLevelPressure(Pres)
        PresTrend = self.PressureTrend(Pres,Data3h)
        MaxTemp,MinTemp,MaxPres,MinPres = self.AirObsMaxMin(Time,Temp,Pres)
        StrikeDeltaT = self.LightningStrikeDeltaT(StrikeTime)
        StrikesToday,StrikesMonth,StrikesYear = self.LightningStrikeCount(StrikeCount)

        # Convert observation units as required
        Temp = self.ObservationUnits(Temp,self.config['Units']['Temp'])
        MaxTemp = self.ObservationUnits(MaxTemp,self.config['Units']['Temp'])
        MinTemp = self.ObservationUnits(MinTemp,self.config['Units']['Temp'])
        DewPoint = self.ObservationUnits(DewPoint,self.config['Units']['Temp'])
        FeelsLike = self.ObservationUnits(FeelsLike,self.config['Units']['Temp'])
        SLP = self.ObservationUnits(SLP,self.config['Units']['Pressure'])
        MaxPres = self.ObservationUnits(MaxPres,self.config['Units']['Pressure'])
        MinPres = self.ObservationUnits(MinPres,self.config['Units']['Pressure'])
        PresTrend = self.ObservationUnits(PresTrend,self.config['Units']['Pressure'])
        StrikeDist = self.ObservationUnits(StrikeDist,self.config['Units']['Distance'])

        # Define station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])

        # Define AIR Kivy label binds
        self.Air['Time'] = datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M:%S')
        self.Air['Temp'] = self.ObservationFormat(Temp,'Temp')
        self.Air['MaxTemp'] = self.ObservationFormat(MaxTemp,'Temp')
        self.Air['MinTemp'] = self.ObservationFormat(MinTemp,'Temp')
        self.Air['DewPoint'] = self.ObservationFormat(DewPoint,'Temp')
        self.Air['FeelsLike'] = self.ObservationFormat(FeelsLike,'Temp')
        self.Air['Pres'] = self.ObservationFormat(SLP,'Pressure')
        self.Air['MaxPres'] = self.ObservationFormat(MaxPres,'Pressure')
        self.Air['MinPres'] = self.ObservationFormat(MinPres,'Pressure')
        self.Air['PresTrend'] = self.ObservationFormat(PresTrend,'Pressure')
        self.Air['StrikeDeltaT'] = self.ObservationFormat(StrikeDeltaT,'TimeDelta')
        self.Air['StrikeDist'] = self.ObservationFormat(StrikeDist,'StrikeDistance')
        self.Air['Strikes3hr'] = self.ObservationFormat(Strikes3hr,'StrikeCount')
        self.Air['StrikesToday'] = self.ObservationFormat(StrikesToday,'StrikeCount')
        self.Air['StrikesMonth'] = self.ObservationFormat(StrikesMonth,'StrikeCount')
        self.Air['StrikesYear'] = self.ObservationFormat(StrikesYear,'StrikeCount')
        self.Air['Humidity'] = self.ObservationFormat(Humidity,'Humidity')
        self.Air['Battery'] = self.ObservationFormat(Battery,'Battery')

    # EXTRACT OBSERVATIONS FROM RAPID_WIND WEBSOCKET JSON MESSAGE
    # --------------------------------------------------------------------------
    def WebsocketRapidWind(self,Msg):

        # Replace missing observations from SKY Rapid-Wind Websocket JSON
        # with NaN
        Obs = [x if x != None else NaN for x in Msg['ob']]

        # Extract observations from latest SKY Rapid-Wind Websocket JSON
        Time = [Obs[0],'s']
        WindSpd = [Obs[1],'mps']
        WindDir = [Obs[2],'degrees']

        # Extract wind direction from previous SKY Rapid-Wind Websocket JSON
        if 'Obs' in self.Rapid:
            WindDirOld = [self.Rapid['Obs'][2],'degrees']
        else:
            WindDirOld = [0,'degrees']

        # If windspeed is zero, freeze direction at last direction of
        # non-zero wind speed, and edit latest SKY Rapid-Wind Websocket JSON
        if WindSpd[0] == 0:
            WindDir = WindDirOld
            Obs[2] = WindDirOld[0]

        # Store latest SKY Observation JSON message
        self.Rapid['Obs'] = Obs

        # Calculate derived variables from Rapid SKY observations
        WindDir = self.CardinalWindDirection(WindDir,WindSpd)

        # Convert observation units as required
        WindSpd = self.ObservationUnits(WindSpd,self.config['Units']['Wind'])
        WindDir = self.ObservationUnits(WindDir,'degrees')

        # Define station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])

        # Define Rapid-SKY Kivy label binds
        self.Rapid['Time'] = datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M:%S')
        self.Rapid['Speed'] = self.ObservationFormat(WindSpd,'Wind')
        self.Rapid['Direc'] = self.ObservationFormat(WindDir,'Direction')

        # Animate wind rose arrow
        self.CurrentConditions.WindRoseAnimation(WindDir[0],WindDirOld[0])

    # EXTRACT OBSERVATIONS FROM EVT_STRIKE WEBSOCKET JSON MESSAGE
    # --------------------------------------------------------------------------
    def WebsocketEvtStrike(self,Msg):

        # Extract required observations from latest evt_strike Websocket JSON
        StrikeTime = [Msg['evt'][0],'s']
        StrikeDist = [Msg['evt'][1],'km']

        # Calculate derived variables from evt_strike observations
        StrikeDeltaT = self.LightningStrikeDeltaT(StrikeTime)

        # Convert observation units as required
        StrikeDist = self.ObservationUnits(StrikeDist,self.config['Units']['Distance'])

        # Define AIR Kivy label binds
        self.Air['StrikeDeltaT'] = self.ObservationFormat(StrikeDeltaT,'TimeDelta')
        self.Air['StrikeDist'] = self.ObservationFormat(StrikeDist,'StrikeDistance')

        # Open lightning panel to show strike has been detected if required
        # based on user settings
        if self.config['Display']['LightningPanel'] == '1':
            self.LightningPanel.opacity = 1
            self.RainLightningButton.background_normal = 'buttons/rainfall.png'
            self.RainLightningButton.background_down = 'buttons/rainfallPressed.png'

        # Animate lightning bolt icon to show strike has been detected
        self.CurrentConditions.LightningBoltAnim()

    # GET LAST THREE HOURS OF DATA FROM WEATHERLOW API
    # --------------------------------------------------------------------------
    def GetData3h(self,Device,Obs):

        # Get last three hours of data from AIR module
        if Device == 'Air':

            # Calculate timestamp three hours past
            TimeStart = Obs[0] - int((3600*3+59))
            TimeEnd = Obs[0]

            # Download data for last three hours
            Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
            URL = Template.format(self.config['Station']['OutdoorID'],TimeStart,TimeEnd,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Return observations from last three hours
            return Data

    # CONVERT STATION OBSERVATIONS INTO REQUIRED UNITS
    # --------------------------------------------------------------------------
    def ObservationUnits(self,Obs,Unit):

        # Convert temperature observations
        cObs = Obs[:]
        if Unit in ['f','c']:
            for ii,T in enumerate(Obs):
                if T == 'c':
                    if Unit == 'f':
                        cObs[ii-1] = Obs[ii-1] * 9/5 + 32
                        cObs[ii] = ' [sup]o[/sup]F'
                    else:
                        cObs[ii-1] = Obs[ii-1]
                        cObs[ii] = ' [sup]o[/sup]C'

        # Convert pressure and pressure trend observations
        elif Unit in ['inhg','mmhg','hpa','mb']:
            for ii,P in enumerate(Obs):
                if P in ['mb','mb/hr']:
                    if Unit == 'inhg':
                        cObs[ii-1] = Obs[ii-1] * 0.0295301
                        if P == 'mb':
                            cObs[ii] = ' inHg'
                        else:
                            cObs[ii] = ' inHg/hr'

                    elif Unit == 'mmhg':
                        cObs[ii-1] = Obs[ii-1] * 0.750063
                        if P == 'mb':
                            cObs[ii] = ' mmHg'
                        else:
                            cObs[ii] = ' mmHg/hr'
                    elif Unit == 'hpa':
                        cObs[ii-1] = Obs[ii-1]
                        if P == 'mb':
                            cObs[ii] = ' hpa'
                        else:
                            cObs[ii] = ' hpa/hr'
                    else:
                        cObs[ii-1] = Obs[ii-1]
                        if P == 'mb':
                            cObs[ii] = ' mb'
                        else:
                            cObs[ii] = ' mb/hr'

        # Convert windspeed observations
        elif Unit in ['mph','lfm','kts','kph','bft','mps']:
            for ii,W in enumerate(Obs):
                if W == 'mps':
                    if Unit == 'mph' or Unit == 'lfm':
                        cObs[ii-1] = Obs[ii-1] * 2.2369362920544
                        cObs[ii] = 'mph'
                    elif Unit == 'kts':
                        cObs[ii-1] = Obs[ii-1] * 1.9438
                        cObs[ii] = 'kts'
                    elif Unit == 'kph':
                        cObs[ii-1] = Obs[ii-1] * 3.6
                        cObs[ii] = 'km/h'
                    elif Unit == 'bft':
                        cObs[ii-1] = self.BeaufortScale(Obs[ii-1:ii+1])[2]
                        cObs[ii] = 'bft'
                    else:
                        cObs[ii-1] = Obs[ii-1]
                        cObs[ii] = 'm/s'

        # Convert wind direction observations
        elif Unit in ['degrees','cardinal']:
            for ii,W in enumerate(Obs):
                if W == 'degrees':
                    if cObs[ii-1] is None:
                        cObs[ii-1] = 'Calm'
                        cObs[ii] = ''
                    elif Unit == 'cardinal':
                        cObs[ii-1] = self.CardinalWindDirection(Obs[ii-1:ii+1])[2]
                        cObs[ii] = ''
                    else:
                        cObs[ii-1] = Obs[ii-1]
                        cObs[ii] = '[sup]o[/sup]'

        # Convert rain accumulation and rain rate observations
        elif Unit in ['in','cm','mm']:
            for ii,Prcp in enumerate(Obs):
                if Prcp in ['mm','mm/hr']:
                    if Unit == 'in':
                        cObs[ii-1] = Obs[ii-1] * 0.0393701
                        if Prcp == 'mm':
                            cObs[ii] = '"'
                        else:
                            cObs[ii] = ' in/hr'
                    elif Unit == 'cm':
                        cObs[ii-1] = Obs[ii-1] * 0.1
                        if Prcp == 'mm':
                            cObs[ii] = ' cm'
                        else:
                            cObs[ii] = ' cm/hr'
                    else:
                        cObs[ii-1] = Obs[ii-1]
                        if Prcp == 'mm':
                            cObs[ii] = ' mm'
                        else:
                            cObs[ii] = ' mm/hr'

        # Convert distance observations
        elif Unit in ['km','mi']:
            for ii,Dist in enumerate(Obs):
                if Dist == 'km':
                    if Unit == 'mi':
                        cObs[ii-1] = Obs[ii-1] * 0.62137
                        cObs[ii] = 'miles'

        # Return converted observations
        return cObs

    # FORMAT STATION OBSERVATIONS AND DERIVED VARIABLES FOR DISPLAY
    # --------------------------------------------------------------------------
    def ObservationFormat(self,Obs,Type):

        # Format temperature observations
        cObs = Obs[:]
        if Type == 'Temp':
            for ii,T in enumerate(Obs):
                if isinstance(T,str) and T.strip() in ['[sup]o[/sup]F','[sup]o[/sup]C']:
                    if math.isnan(cObs[ii-1]):
                        cObs[ii-1] = '-'
                    elif cObs[ii-1] == 0:
                        cObs[ii-1] = '{:.1f}'.format(abs(cObs[ii-1]))
                    else:
                        cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])

        # Format pressure observations
        elif Type == 'Pressure':
            for ii,P in enumerate(Obs):
                if isinstance(P,str) and P.strip() in ['inHg/hr','inHg','mmHg/hr','mmHg','hpa/hr','mb/hr','hpa','mb']:
                    if math.isnan(cObs[ii-1]):
                        cObs[ii-1] = '-'
                    else:
                        if P.strip() in ['inHg/hr','inHg']:
                            cObs[ii-1] = '{:2.3f}'.format(cObs[ii-1])
                        elif P.strip() in ['mmHg/hr','mmHg']:
                            cObs[ii-1] = '{:3.2f}'.format(cObs[ii-1])
                        elif P.strip() in ['hpa/hr','mb/hr','hpa','mb']:
                            cObs[ii-1] = '{:4.1f}'.format(cObs[ii-1])

        # Format windspeed observations
        elif Type == 'Wind':
            for ii,W in enumerate(Obs):
                if isinstance(W,str) and W.strip() in ['mph','kts','km/h','bft','m/s']:
                    if math.isnan(cObs[ii-1]):
                        cObs[ii-1] = '-'
                    else:
                        if cObs[ii-1] < 10:
                            cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])
                        else:
                            cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])

        # Format wind direction observations
        elif Type == 'Direction':
            for ii,D in enumerate(Obs):
                if isinstance(D,str) and D.strip() in ['[sup]o[/sup]']:
                    if math.isnan(cObs[ii-1]):
                        cObs[ii-1] = '-'
                    else:
                        cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])

        # Format rain accumulation and rain rate observations
        elif Type == 'Precip':
            for ii,Prcp in enumerate(Obs):
                if isinstance(Prcp,str):
                    if Prcp.strip() in ['mm','mm/hr']:
                        if math.isnan(cObs[ii-1]):
                            cObs[ii-1] = '-'
                        else:
                            if cObs[ii-1] == 0:
                                cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])
                            elif cObs[ii-1] < 0.1:
                                cObs[ii-1] = 'Trace'
                                cObs[ii] = ''
                            elif cObs[ii-1] < 10:
                                cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])
                            else:
                                cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])
                    elif Prcp.strip() in ['"','in/hr','cm/hr','cm']:
                        if math.isnan(cObs[ii-1]):
                            cObs[ii-1] = '-'
                        else:
                            if cObs[ii-1] == 0:
                                cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])
                            elif cObs[ii-1] < 0.01:
                                cObs[ii-1] = 'Trace'
                                cObs[ii] = ''
                            elif cObs[ii-1] < 10:
                                cObs[ii-1] = '{:.2f}'.format(cObs[ii-1])
                            elif cObs[ii-1] < 100:
                                cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])
                            else:
                                cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])

        # Format humidity observations
        elif Type == 'Humidity':
            for ii,H in enumerate(Obs):
                if isinstance(H,str) and H.strip() == '%':
                    if math.isnan(cObs[ii-1]):
                        cObs[ii-1] = '-'
                    else:
                        cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])

        # Format solar radiation observations
        elif Type == 'Radiation':
            for ii,Rad in enumerate(Obs):
                if isinstance(Rad,str) and Rad.strip() == 'W m[sup]-2[/sup]':
                    if math.isnan(cObs[ii-1]):
                        cObs[ii-1] = '-'
                    else:
                        cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])

        # Format UV observations
        elif Type == 'UV':
            for ii,UV in enumerate(Obs):
                if isinstance(UV,str) and UV.strip() == 'index':
                    if math.isnan(cObs[ii-1]):
                        cObs[ii-1] = '-'
                    else:
                        cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])

        # Format battery voltage observations
        elif Type == 'Battery':
            for ii,V in enumerate(Obs):
                if isinstance(V,str) and V.strip() == 'v':
                    if math.isnan(cObs[ii-1]):
                        cObs[ii-1] = '-'
                    else:
                        cObs[ii-1] = '{:.2f}'.format(cObs[ii-1])

        # Format lightning strike count observations
        elif Type == 'StrikeCount':
            for ii,L in enumerate(Obs):
                if isinstance(L,str) and L.strip() == 'count':
                    if math.isnan(cObs[ii-1]):
                        cObs[ii-1] = '-'
                    elif cObs[ii-1] < 1000:
                        cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])
                    else:
                        cObs[ii-1] = '{:.1f}'.format(cObs[ii-1]/1000) + ' k'

        # Format lightning strike distance observations
        elif Type == 'StrikeDistance':
            for ii,StrikeDist in enumerate(Obs):
                if isinstance(StrikeDist,str):
                    if StrikeDist.strip() in ['km']:
                        if math.isnan(cObs[ii-1]):
                            cObs[ii-1] = '-'
                        else:
                            DistValues = [0,5,6,8,10,12,14,17,20,24,27,31,34,37,40]
                            DispValues = ['0-5','2-8','3-9','5-11','7-13','9-15','11-17','14-20','17-23','21-27','24-30','28-34','31-37','34-40','37-43']
                            cObs[ii-1] = DispValues[bisect.bisect(DistValues,cObs[ii-1])-1]
                    elif StrikeDist.strip() in ['miles']:
                        if math.isnan(cObs[ii-1]):
                            cObs[ii-1] = '-'
                        else:
                            DistValues = [0,3.1,3.7,5,6.2,7.5,8.7,10.6,12.4,14.9,16.8,19.3,21.1,23,24.9]
                            DispValues = ['0-3','1-5','2-6','3-7','4-8','6-9','7-11','9-12','11-14','13-17','15-19','17-21','19-23','21-25','37-43']
                            cObs[ii-1] = DispValues[bisect.bisect(DistValues,cObs[ii-1])-1]

        # Format time difference observations
        elif Type == 'TimeDelta':
            for ii,Delta in enumerate(Obs):
                if isinstance(Delta,str) and Delta.strip() in ['s']:
                    if math.isnan(cObs[ii-1]):
                        cObs = ['-','-','-','-',cObs[2]]
                    else:
                        days,remainder = divmod(cObs[ii-1],86400)
                        hours,remainder = divmod(remainder,3600)
                        minutes,seconds = divmod(remainder,60)
                        if days >= 1:
                            if days == 1:
                                if hours == 1:
                                    cObs = ['{:.0f}'.format(days),'day','{:.0f}'.format(hours),'hour',cObs[2]]
                                else:
                                    cObs = ['{:.0f}'.format(days),'day','{:.0f}'.format(hours),'hours',cObs[2]]
                            elif days <= 99:
                                if hours == 1:
                                    cObs = ['{:.0f}'.format(days),'days','{:.0f}'.format(hours),'hour',cObs[2]]
                                else:
                                    cObs = ['{:.0f}'.format(days),'days','{:.0f}'.format(hours),'hours',cObs[2]]
                            elif days >= 100:
                                    cObs = ['{:.0f}'.format(days),'days','-','-',cObs[2]]
                        elif hours >= 1:
                            if hours == 1:
                                if minutes == 1:
                                    cObs = ['{:.0f}'.format(hours),'hour','{:.0f}'.format(minutes),'min',cObs[2]]
                                else:
                                    cObs = ['{:.0f}'.format(hours),'hour','{:.0f}'.format(minutes),'mins',cObs[2]]
                            elif hours > 1:
                                if minutes == 1:
                                    cObs = ['{:.0f}'.format(hours),'hours','{:.0f}'.format(minutes),'min',cObs[2]]
                                else:
                                    cObs = ['{:.0f}'.format(hours),'hours','{:.0f}'.format(minutes),'mins',cObs[2]]
                        else:
                            if minutes == 0:
                                cObs = ['< 1','minute','-','-',cObs[2]]
                            elif minutes == 1:
                                cObs = ['{:.0f}'.format(minutes),'minute','-','-',cObs[2]]
                            else:
                                cObs = ['{:.0f}'.format(minutes),'minutes','-','-',cObs[2]]

        # Return formatted observations
        return cObs

    # CALCULATE DEW POINT FROM HUMIDITY AND TEMPERATURE
    # --------------------------------------------------------------------------
    def DewPoint(self,Temp,Humidity):

        # Calculate dew point unless humidity equals zero
        if Humidity != 0:
            A = 17.625
            B = 243.04
            N = B*(math.log(Humidity[0]/100.0) + (A*Temp[0])/(B+Temp[0]))
            D = A-math.log(Humidity[0]/100.0) - (A*Temp[0])/(B+Temp[0])
            DewPoint = N/D
        else:
            DewPoint = NaN

        # Return Dew Point
        return [DewPoint,'c']

    # CALCULATE 'FEELS LIKE' TEMPERATURE FROM TEMPERATURE, RELATIVE HUMIDITY,
    # AND WIND SPEED
    # --------------------------------------------------------------------------
    def FeelsLike(self,TempC,RH,WindSpd):

        # Skip calculation during initialisation
        if None in [TempC,RH,WindSpd]:
            FeelsLike = [NaN,'c','-','-']

        # Calculate 'Feels Like' temperature
        else:

            # Convert observation units as required
            TempF = self.ObservationUnits(TempC,'f')
            WindMPH = self.ObservationUnits(WindSpd,'mph')
            WindKPH = self.ObservationUnits(WindSpd,'kph')

            # If temperature is less than 10 degrees celcius and wind speed is
            # higher than 3 mph, calculate wind chill using the Joint Action
            # Group for Temperature Indices formula
            if TempC[0] <= 10 and WindMPH[0] > 3:

                # Calculate wind chill
                WindChill = 13.12 + 0.6215*TempC[0] - 11.37*(WindKPH[0])**0.16 + 0.3965*TempC[0]*(WindKPH[0])**0.16
                FeelsLike = [WindChill,'c']

            # If temperature is at or above 80 degress farenheit (26.67 C), and
            # humidity is at or above 40%, calculate the Heat Index
            elif TempF[0] >= 80 and RH[0] >= 40:

                # Calculate Heat Index
                HeatIndex = -42.379 + (2.04901523*TempF[0]) + (10.1433127*RH[0]) - (0.22475541*TempF[0]*RH[0]) - (6.83783e-3*TempF[0]**2) - (5.481717e-2*RH[0]**2) + (1.22874e-3*TempF[0]**2*RH[0]) + (8.5282e-4*TempF[0]*RH[0]**2) - (1.99e-6*TempF[0]**2*RH[0]**2)
                FeelsLike = [(HeatIndex-32)*5/9,'c']

            # Else set 'Feels Like' temperature to observed temperature
            else:
                FeelsLike = TempC

            # Define 'FeelsLike' temperature cutoffs
            Cutoff = list(self.config['FeelsLike'].values())
            Cutoff = [float(item) for item in Cutoff]

            # Define 'FeelsLike temperature text and icon
            Description = ['Feeling extremely cold', 'Feeling freezing cold', 'Feeling very cold',
                           'Feeling cold', 'Feeling mild', 'Feeling warm', 'Feeling hot',
                           'Feeling very hot', 'Feeling extremely hot']
            Icon = ['ExtremelyCold', 'FreezingCold', 'VeryCold', 'Cold', 'Mild', 'Warm',
                    'Hot', 'VeryHot', 'ExtremelyHot']

            # Extract required 'FeelsLike' description and icon
            if self.config['Units']['Temp'] == 'f':
                Ind = bisect.bisect(Cutoff,FeelsLike[0]* 9/5 + 32)
            else:
                Ind = bisect.bisect(Cutoff,FeelsLike[0])
            FeelsLike = [FeelsLike[0],FeelsLike[1],Description[Ind],Icon[Ind]]

        # Return 'Feels Like' temperature
        return FeelsLike

    # CALCULATE SEA LEVEL PRESSURE FROM AMBIENT PRESSURE AND STATION ELEVATION
    # --------------------------------------------------------------------------
    def SeaLevelPressure(self,Pres):

        # Extract required meteorological fields
        Psta = Pres[0]

        # Define required constants
        P0 = 1013.25
        Rd = 287.05
        GammaS = 0.0065
        g = 9.80665
        Elev = float(self.config['Station']['Elevation']) + float(self.config['Station']['OutdoorHeight'])
        T0 = 288.15

        # Calculate sea level pressure
        SLP = Psta * (1 + ((P0/Psta)**((Rd*GammaS)/g)) * ((GammaS*Elev)/T0))**(g/(Rd*GammaS))

        # Return Sea Level Pressure
        return [SLP,'mb','{:.1f}'.format(SLP)]

    # CALCULATE THE PRESSURE TREND AND SET THE PRESSURE TREND TEXT
    # --------------------------------------------------------------------------
    def PressureTrend(self,Pres0h,Data3h):

        # Extract pressure observation from three hours ago. Return NaN for
        # pressure trend if API call has failed       
        if VerifyJSON(Data3h,'WeatherFlow','obs'):
            Data3h = Data3h.json()['obs']
            Pres3h = [Data3h[0][1],'mb']
        else:
            Pres3h = [NaN,'mb']

        # Convert station pressure into sea level pressure
        Pres0h = self.SeaLevelPressure(Pres0h)
        Pres3h = self.SeaLevelPressure(Pres3h)

        # Calculate pressure trend
        Trend = (Pres0h[0] - Pres3h[0])/3

        # Remove sign from pressure trend if it rounds to 0.0
        if abs(Trend) < 0.05:
            Trend = abs(Trend)

        # Define pressure trend text
        if math.isnan(Trend):
            TrendTxt = '-'
        elif Trend > 2/3:
            TrendTxt = '[color=ff8837ff]Rising rapidly[/color]'
        elif Trend >= 1/3:
            TrendTxt = '[color=ff8837ff]Rising[/color]'
        elif Trend <= -2/3:
            TrendTxt = '[color=00a4b4ff]Falling rapidly[/color]'
        elif Trend <= -1/3:
            TrendTxt = '[color=00a4b4ff]Falling[/color]'
        else:
            TrendTxt = '[color=9aba2fff]Steady[/color]'

        # Define weather tendency based on pressure and trend
        if Pres0h[0] >= 1023:
            if 'Falling rapidly' in TrendTxt:
                Tendency = 'Becoming cloudy and warmer'
            else:
                Tendency = 'Fair conditions likely'
        elif 1009 < Pres0h[0] < 1023:
            if 'Falling rapidly' in TrendTxt:
                Tendency = 'Rainy conditions likely'
            else:
                Tendency = 'Conditions unchanged'
        elif Pres0h[0] <= 1009:
            if 'Falling rapidly' in TrendTxt:
                Tendency = 'Stormy conditions likely'
            elif 'Falling' in TrendTxt:
                Tendency = 'Rainy conditions likely'
            else:
                Tendency = 'Becoming clearer and cooler'

        # Return pressure trend
        return [Trend,'mb/hr',TrendTxt,Tendency]

    # CALCULATE RAIN ACCUMULATION LEVELS FOR TODAY/YESTERDAY/MONTH/YEAR
    # --------------------------------------------------------------------------
    def RainAccumulation(self,Rain):

        # Define current time in station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Code initialising. Download all data for current day using Weatherflow
        # API. Calculate total daily rainfall
        if self.Sky['TodayRain'][0] == '-':

            # Convert midnight today in Station timezone to midnight today in
            # UTC. Convert UTC time into UNIX timestamp.
            Date = date.today()
            Start = int(Tz.localize(datetime(Date.year,Date.month,Date.day)).timestamp())

            # Convert current time in Station timezone to current time in  UTC.
            # Convert current time into UNIX timestamp
            End = int(Tz.localize(datetime.now()).timestamp())

            # Download rainfall data for current day
            Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['SkyID'],Start,End,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate daily rainfall total. Return NaN if API call has failed
            if VerifyJSON(Data,'WeatherFlow','obs'):
                Data = Data.json()['obs']
                Rain = [[item[3],'mm'] if item[3] != None else NaN for item in Data]
                TodayRain = [sum([x for x,y in Rain]),'mm',sum([x for x,y in Rain]),Now]
            else:
                TodayRain = [NaN,'mm',NaN,Now]

        # Code initialising. Download all data for yesterday using Weatherflow
        # API. Calculate total daily rainfall
        if self.Sky['YesterdayRain'][0] == '-':

            # Convert midnight yesterday in Station timezone to midnight
            # yesterday in UTC. Convert UTC time into UNIX timestamp
            Date = date.today() - timedelta(days=1)
            Start = int(Tz.localize(datetime.combine(Date,time())).timestamp())

            # Convert midnight today in Station timezone to midnight
            # yesterday in UTC. Convert UTC time into UNIX timestamp
            End = Start + (60*60*24)-1

            # Download rainfall data for current month
            Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['SkyID'],Start,End,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate yesterday rainfall total. Return NaN if API call has
            # failed
            if VerifyJSON(Data,'WeatherFlow','obs'):
                Data = Data.json()['obs']
                Rain = [[item[3],'mm'] if item[3] != None else NaN for item in Data]
                YesterdayRain = [sum([x for x,y in Rain]),'mm',sum([x for x,y in Rain]),Now]
            else:
                YesterdayRain = [NaN,'mm',NaN,Now]

        # Code initialising. Download all data for current month using
        # Weatherflow API. Calculate total monthly rainfall
        if self.Sky['MonthRain'][0] == '-':

            # Convert start of current month in Station timezone to start of
            # current month in UTC. Convert UTC time into UNIX timestamp
            Date = date.today()
            Start = int(Tz.localize(datetime(Date.year,Date.month,1)).timestamp())

            # Convert current time in Station timezone to current time in  UTC.
            # Convert current time into UNIX timestamp
            End = int(Tz.localize(datetime.now()).timestamp())

            # Download rainfall data for current month.
            Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['SkyID'],Start,End,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate monthly rainfall total. Return NaN if API call has
            # failed
            if VerifyJSON(Data,'WeatherFlow','obs'):
                Data = Data.json()['obs']
                Rain = [[item[3],'mm'] if item[3] != None else NaN for item in Data]
                MonthRain = [sum([x for x,y in Rain]),'mm',sum([x for x,y in Rain]),Now]
            else:
                MonthRain = [NaN,'mm',NaN,Now]

        # Code initialising. Download all data for current year using
        # Weatherflow API. Calculate total yearly rainfall
        if self.Sky['YearRain'][0] == '-':

            # Convert start of current year in Station timezone to start of
            # current year in UTC. Convert UTC time into UNIX timestamp
            Date = date.today()
            Start = int(Tz.localize(datetime(Date.year,1,1)).timestamp())

            # Convert current time in Station timezone to current time in  UTC.
            # Convert current time into UNIX timestamp
            End = int(Tz.localize(datetime.now()).timestamp())

            # Download rainfall data for current year
            Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['SkyID'],Start,End,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate yearly rainfall total. Return NaN if API call has failed
            if VerifyJSON(Data,'WeatherFlow','obs'):
                Data = Data.json()['obs']
                Rain = [[item[3],'mm'] if item[3] != None else NaN for item in Data]
                YearRain = [sum([x for x,y in Rain]),'mm',sum([x for x,y in Rain]),Now]
            else:
                YearRain = [NaN,'mm',NaN,Now]

            # Return Daily, Monthly, and Yearly rainfall accumulation totals
            return TodayRain,YesterdayRain,MonthRain,YearRain

        # At midnight, reset daily rainfall accumulation to zero, else add
        # current rainfall to current daily rainfall accumulation
        if Now.date() > self.Sky['TodayRain'][3].date():
            TodayRain = [Rain[0],'mm',Rain[0],Now]
            YesterdayRain = [self.Sky['TodayRain'][2],'mm',self.Sky['TodayRain'][2],Now]
        else:
            RainAccum = self.Sky['TodayRain'][2]+Rain[0]
            TodayRain = [RainAccum,'mm',RainAccum,Now]
            YesterdayRain = [self.Sky['YesterdayRain'][2],'mm',self.Sky['YesterdayRain'][2],Now]

        # At end of month, reset monthly rainfall accumulation to zero, else add
        # current rainfall to current monthly rainfall accumulation
        if Now.month > self.Sky['MonthRain'][3].month:
            MonthRain = [Rain[0],'mm',Rain[0],Now]
        else:
            RainAccum = self.Sky['MonthRain'][2]+Rain[0]
            MonthRain = [RainAccum,'mm',RainAccum,Now]

        # At end of year, reset monthly and yearly rainfall accumulation to zero,
        # else add current rainfall to current yearly rainfall accumulation
        if Now.year > self.Sky['YearRain'][3].year:
            YearRain = [Rain[0],'mm',Rain[0],Now]
            MonthRain = [Rain[0],'mm',Rain[0],Now]
        else:
            RainAccum = self.Sky['YearRain'][2]+Rain[0]
            YearRain = [RainAccum,'mm',RainAccum,Now]

        # Return Daily, Monthly, and Yearly rainfall accumulation totals
        return TodayRain,YesterdayRain,MonthRain,YearRain

    # CALCULATE THE RAIN RATE FROM THE PREVIOUS 1 MINUTE RAIN ACCUMULATION
    # --------------------------------------------------------------------------
    def RainRate(self,RainAccum):

        # Calculate instantaneous rain rate from instantaneous rain accumulation
        RainRate = RainAccum[0]*60

        # Define rain rate text based on calculated
        if RainRate == 0:
            RainRateTxt = 'Currently Dry'
        elif RainRate < 0.25:
            RainRateTxt = 'Very Light Rain'
        elif RainRate < 1.0:
            RainRateTxt = 'Light Rain'
        elif RainRate < 4.0:
            RainRateTxt = 'Moderate Rain'
        elif RainRate < 16.0:
            RainRateTxt = 'Heavy Rain'
        elif RainRate < 50.0:
            RainRateTxt = 'Very Heavy Rain'
        else:
            RainRateTxt = 'Extreme Rain'

        # Return instantaneous rain rate and text
        return [RainRate,'mm/hr',RainRateTxt]

    # CALCULATE TIME SINCE LAST LIGHTNING STRIKE
    # --------------------------------------------------------------------------
    def LightningStrikeDeltaT(self,StrikeTime):

        # Calculate time since last lightning strike
        Now = int(UNIX.time())
        deltaT = Now - StrikeTime[0]
        StrikeDeltaT = [deltaT,'s',deltaT]

        # Switch Lightning Panel background if deltaT is greater than 5 minutes
        if deltaT < 360:
            self.LightningPanelBackground.source = 'background/lightningDetected.png'
            self.LightningPanelIcon.source = 'icons/lightning/lightningBoltStrike.png'
        else:
            self.LightningPanelBackground.source = 'background/lightning.png'
            self.LightningPanelIcon.source = 'icons/lightning/lightningBolt.png'

        # Return time since and distance to last lightning strike
        return StrikeDeltaT

    # CALCULATE NUMBER OF LIGHTNING STRIKES FOR LAST 3 HOURS/TODAY/MONTH/YEAR
    # --------------------------------------------------------------------------
    def LightningStrikeCount(self,Count):

        # Define current time in station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Code initialising. Download all data for current day using Weatherflow
        # API. Calculate total daily lightning strikes
        if self.Air['StrikesToday'][0] == '-':

            # Convert midnight today in Station timezone to midnight today in
            # UTC. Convert UTC time into UNIX timestamp
            Date = date.today()
            Start = int(Tz.localize(datetime(Date.year,Date.month,Date.day)).timestamp())

            # Convert current time in Station timezone to current time in  UTC.
            # Convert current time into UNIX timestamp
            End = int(Tz.localize(datetime.now()).timestamp())

            # Download lightning strike data for current day
            Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['OutdoorID'],Start,End,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate daily lightning strike total. Return NaN if API call has
            # failed
            if VerifyJSON(Data,'WeatherFlow','obs'):
                Data = Data.json()['obs']
                Strikes = [item[4] if item[4] != None else NaN for item in Data]
                StrikesToday = [sum(x for x in Strikes),'count',sum(x for x in Strikes),Now]
            else:
                StrikesToday = [NaN,'count',NaN,Now]

        # Code initialising. Download all data for current month using
        # Weatherflow API. Calculate total monthly lightning strikes
        if self.Air['StrikesMonth'][0] == '-':

            # Convert start of current month in Station timezone to start of
            # current month in UTC. Convert UTC time into UNIX timestamp
            Date = date.today()
            Start = int(Tz.localize(datetime(Date.year,Date.month,1)).timestamp())

            # Convert current time in Station timezone to current time in  UTC.
            # Convert current time into UNIX timestamp
            End = int(Tz.localize(datetime.now()).timestamp())

            # Download lightning strike data for current month.
            Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['OutdoorID'],Start,End,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate monthly lightning strike total. Return NaN if API call
            # has failed
            if VerifyJSON(Data,'WeatherFlow','obs'):
                Data = Data.json()['obs']
                Strikes = [item[4] if item[4] != None else NaN for item in Data]
                StrikesMonth = [sum(x for x in Strikes),'count',sum(x for x in Strikes),Now]
            else:
                StrikesMonth = [NaN,'count',NaN,Now]

        # Code initialising. Download all data for current year using
        # Weatherflow API. Calculate total yearly lightning strikes
        if self.Air['StrikesYear'][0] == '-':

            # Convert start of current year in Station timezone to start of
            # current year in UTC. Convert UTC time into UNIX timestamp
            Date = date.today()
            Start = int(Tz.localize(datetime(Date.year,1,1)).timestamp())

            # Convert current time in Station timezone to current time in  UTC.
            # Convert current time into UNIX timestamp
            End = int(Tz.localize(datetime.now()).timestamp())

            # Download lightning strike data for current year
            Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['OutdoorID'],Start,End,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate yearly lightning strikes total. Return NaN if API call
            # has failed
            if VerifyJSON(Data,'WeatherFlow','obs'):
                Data = Data.json()['obs']
                Strikes = [item[4] if item[4] != None else NaN for item in Data]
                StrikesYear = [sum(x for x in Strikes),'count',sum(x for x in Strikes),Now]
            else:
                StrikesYear = [NaN,'count',NaN,Now]

            # Return Daily, Monthly, and Yearly lightning strike counts
            return StrikesToday,StrikesMonth,StrikesYear

        # At midnight, reset daily lightning strike count to zero, else return
        # current daily lightning strike count.
        if Now.date() > self.Air['StrikesToday'][3].date():
            StrikesToday = [0,'count',0,Now]
        else:
            StrikeCount = self.Air['StrikesToday'][2]+Count[0]
            StrikesToday = [StrikeCount,'count',StrikeCount,Now]

        # At end of month, reset monthly lightning strike count to zero, else
        # return current monthly lightning strike count
        if Now.month > self.Air['StrikesMonth'][3].month:
            StrikesMonth = [0,'count',0,Now]
        else:
            StrikeCount = self.Air['StrikesMonth'][2]+Count[0]
            StrikesMonth = [StrikeCount,'count',StrikeCount,Now]

        # At end of year, reset monthly and yearly lightning strike counts to
        # zero, else return current monthly and yearly lightning strike count
        if Now.year > self.Air['StrikesYear'][3].year:
            StrikesMonth = [0,'count',0,Now]
            StrikesYear = [0,'count',0,Now]
        else:
            StrikeCount = self.Air['StrikesYear'][2]+Count[0]
            StrikesYear = [StrikeCount,'count',StrikeCount,Now]

        # Return Daily, Monthly, and Yearly lightning strike accumulation totals
        return StrikesToday,StrikesMonth,StrikesYear

    # CALCULATE DAILY AVERAGED WIND SPEED
    # --------------------------------------------------------------------------
    def MeanWindSpeed(self,WindSpd):

        # Define current time in station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # CODE INITIALISING. DOWNLOAD DATA FOR CURRENT DAY USING WEATHERFLOW API
        if self.Sky['AvgWind'][0] == '-':

            # Convert midnight today in Station timezone to midnight today in
            # UTC. Convert UTC time into UNIX timestamp
            Date = date.today()
            Midnight = Tz.localize(datetime.combine(Date,time()))
            Midnight_UTC = int(Midnight.timestamp())

            # Convert current time in Station timezone to current time in UTC.
            # Convert current time time into UNIX timestamp
            Now = Tz.localize(datetime.now())
            Now_UTC = int(Now.timestamp())

            # Download data from current day using Weatherflow API and extract
            # wind speed and wind gust data
            Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['SkyID'],Midnight_UTC,Now_UTC,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate daily averaged wind speed. Return NaN if API call has
            # failed
            if VerifyJSON(Data,'WeatherFlow','obs'):
                Data = Data.json()['obs']
                WindSpd = [[item[5],'mps'] for item in Data if item[5] != None]
                Sum = sum([x for x,y in WindSpd])
                Length = len(WindSpd)
                AvgWind = [Sum/Length,'mps',Sum/Length,Length,Now]
            else:
                AvgWind = [NaN,'mps',NaN,NaN,Now]

            # Return daily averaged wind speed
            return AvgWind

        # At midnight, reset daily averaged wind speed to zero
        if Now.date() > self.Sky['AvgWind'][4].date():
            AvgWind = [WindSpd[0],'mps',WindSpd[0],1,Now]

        # Update current daily averaged wind speed with new wind speed
        # observation
        else:
            Len = self.Sky['AvgWind'][3] + 1
            CurrentAvg = self.Sky['AvgWind'][2]
            NewAvg = (Len-1)/Len * CurrentAvg + 1/Len * WindSpd[0]
            AvgWind = [NewAvg,'mps',NewAvg,Len,Now]

        # Return daily averaged wind speed
        return AvgWind

    # CALCULATE MAXIMUM AND MINIMUM OBSERVED OUTDOOR TEMPERATURE AND PRESSURE
    # --------------------------------------------------------------------------
    def AirObsMaxMin(self,Time,Temp,Pres):

        # Calculate sea level pressure
        SLP = self.SeaLevelPressure(Pres)

        # Define current time in station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # CODE INITIALISING. DOWNLOAD DATA FOR CURRENT DAY USING WEATHERFLOW API
        if self.Air['MaxTemp'][0] == '-':

            # Convert midnight today in Station timezone to midnight today in
            # UTC. Convert UTC time into UNIX timestamp
            Date = date.today()
            Midnight = Tz.localize(datetime.combine(Date,time()))
            Midnight_UTC = int(Midnight.timestamp())

            # Convert current time in Station timezone to current time in
            # UTC. Convert current time time into UNIX timestamp
            Now = Tz.localize(datetime.now())
            Now_UTC = int(Now.timestamp())

            # Download data from current day using Weatherflow API and extract
            # temperature, pressure and time data
            Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['OutdoorID'],Midnight_UTC,Now_UTC,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate maximum and minimum temperature and pressure. Return NaN
            # if API call has failed
            if VerifyJSON(Data,'WeatherFlow','obs'):

                # Extract data from API call
                Data = Data.json()['obs']
                Time = [[item[0],'s'] if item[0] != None else NaN for item in Data]
                Temp = [[item[2],'c'] if item[2] != None else [NaN,'c'] for item in Data]
                Pres = [[item[1],'mb'] if item[1] != None else [NaN,'mb'] for item in Data]

                # Calculate sea level pressure
                SLP = [self.SeaLevelPressure(P) for P in Pres]

                # Define maximum and minimum temperature and time
                MaxTemp = [max(Temp)[0],'c',datetime.fromtimestamp(Time[Temp.index(max(Temp))][0],Tz).strftime('%H:%M'),max(Temp)[0],Now]
                MinTemp = [min(Temp)[0],'c',datetime.fromtimestamp(Time[Temp.index(min(Temp))][0],Tz).strftime('%H:%M'),min(Temp)[0],Now]

                # Define maximum and minimum pressure
                MaxPres = [max(SLP)[0],'mb',datetime.fromtimestamp(Time[SLP.index(max(SLP))][0],Tz).strftime('%H:%M'),max(SLP)[0],Now]
                MinPres = [min(SLP)[0],'mb',datetime.fromtimestamp(Time[SLP.index(min(SLP))][0],Tz).strftime('%H:%M'),min(SLP)[0],Now]

            # API call has failed. Return NaN
            else:
                MaxTemp = [NaN,'c','-',NaN,Now]
                MinTemp = [NaN,'c','-',NaN,Now]
                MaxPres = [NaN,'mb','-',NaN,Now]
                MinPres = [NaN,'mb','-',NaN,Now]

            # Return required variables
            return MaxTemp,MinTemp,MaxPres,MinPres

        # AT MIDNIGHT RESET MAXIMUM AND MINIMUM TEMPERATURE AND PRESSURE
        if Now.date() > self.Air['MaxTemp'][4].date():

            # Reset maximum and minimum temperature
            MaxTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M'),Temp[0],Now]
            MinTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M'),Temp[0],Now]

            # Reset maximum and minimum pressure
            MaxPres = [SLP[0],'mb',datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M'),SLP[0],Now]
            MinPres = [SLP[0],'mb',datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M'),SLP[0],Now]

            # Return required variables
            return MaxTemp,MinTemp,MaxPres,MinPres

        # Current temperature is greater than maximum recorded temperature.
        # Update maximum temperature and time
        if Temp[0] > self.Air['MaxTemp'][3]:
            MaxTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M'),Temp[0],Now]
            MinTemp = [self.Air['MinTemp'][3],'c',self.Air['MinTemp'][2],self.Air['MinTemp'][3],Now]

        # Current temperature is less than minimum recorded temperature. Update
        # minimum temperature and time
        elif Temp[0] < self.Air['MinTemp'][3]:
            MaxTemp = [self.Air['MaxTemp'][3],'c',self.Air['MaxTemp'][2],self.Air['MaxTemp'][3],Now]
            MinTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M'),Temp[0],Now]

        # Maximum and minimum temperature unchanged. Return existing values
        else:
            MaxTemp = [self.Air['MaxTemp'][3],'c',self.Air['MaxTemp'][2],self.Air['MaxTemp'][3],Now]
            MinTemp = [self.Air['MinTemp'][3],'c',self.Air['MinTemp'][2],self.Air['MinTemp'][3],Now]

        # Current pressure is greater than maximum recorded pressure. Update
        # maximum pressure
        if SLP[0] > self.Air['MaxPres'][3]:
            MaxPres = [SLP[0],'mb',datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M'),SLP[0],Now]
            MinPres = [self.Air['MinPres'][3],'mb',self.Air['MinPres'][2],self.Air['MinPres'][3],Now]

        # Current pressure is less than minimum recorded pressure. Update
        # minimum pressure and time
        elif SLP[0] < self.Air['MinPres'][3]:
            MaxPres = [self.Air['MaxPres'][3],'mb',self.Air['MaxPres'][2],self.Air['MaxPres'][3],Now]
            MinPres = [SLP[0],'mb',datetime.fromtimestamp(Time[0],Tz).strftime('%H:%M'),SLP[0],Now]

        # Maximum and minimum pressure unchanged. Return existing values
        else:
            MaxPres = [self.Air['MaxPres'][3],'mb',self.Air['MaxPres'][2],self.Air['MaxPres'][3],Now]
            MinPres = [self.Air['MinPres'][3],'mb',self.Air['MinPres'][2],self.Air['MinPres'][3],Now]

        # Return required variables
        return MaxTemp,MinTemp,MaxPres,MinPres

    # CALCULATE MAXIMUM OBSERVED WIND SPEED AND GUST STRENGTH
    # --------------------------------------------------------------------------
    def SkyObsMaxMin(self,WindSpd,WindGust):

        # Define current time in station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # CODE INITIALISING. DOWNLOAD DATA FOR CURRENT DAY USING WEATHERFLOW API
        if self.Sky['MaxGust'] == '--':

            # Convert midnight today in Station timezone to midnight today in
            # UTC. Convert UTC time into UNIX timestamp
            Date = date.today()
            Midnight = Tz.localize(datetime.combine(Date,time()))
            Midnight_UTC = int(Midnight.timestamp())

            # Convert current time in Station timezone to current time in UTC.
            # Convert current time time into UNIX timestamp
            Now = Tz.localize(datetime.now())
            Now_UTC = int(Now.timestamp())

            # Download data from current day using Weatherflow API and extract
            # wind speed and wind gust data
            Template = ('https://swd.weatherflow.com/swd/rest/observations/?device_id={}&time_start={}&time_end={}&api_key={}')
            URL = Template.format(self.config['Station']['SkyID'],Midnight_UTC,Now_UTC,self.config['Keys']['WeatherFlow'])
            Data = requests.get(URL)

            # Calculate daily maximum wind gust. Return NaN if API call has
            # failed
            if VerifyJSON(Data,'WeatherFlow','obs'):
                Data = Data.json()['obs']
                WindGust = [[item[6],'mps'] for item in Data if item[6] != None]
                MaxGust = [max([x for x,y in WindGust]),'mps',max([x for x,y in WindGust]),Now]
            else:
                TodayRain = [NaN,'mps',NaN,Now]

            # Return maximum wind gust
            return MaxGust

        # AT MIDNIGHT RESET MAXIMUM RECORDED WIND GUST
        if Now.date() > self.Sky['MaxGust'][3].date():
            MaxGust = [WindGust[0],'mps',WindGust[0],Now]

            # Return maximum wind gust
            return MaxGust

        # Current gust speed is greater than maximum recorded gust speed. Update
        # maximum gust speed
        if WindGust[0] > self.Sky['MaxGust'][2]:
            MaxGust = [WindGust[0],'mps',WindGust[0],Now]

        # Maximum gust speed is unchanged. Return existing value
        else:
            MaxGust = [self.Sky['MaxGust'][2],'mps',self.Sky['MaxGust'][2],Now]

        # Return maximum wind speed and gust
        return MaxGust

    # CALCULATE CARDINAL WIND DIRECTION FROM WIND DIRECTION IN DEGREES
    # --------------------------------------------------------------------------
    def CardinalWindDirection(self,Dir,Spd=[1,'mps']):

        # Define all possible cardinal wind directions and descriptions
        Direction = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW','N']
        Description = ['Due North','North NE','North East','East NE','Due East','East SE','South East','South SE',
                       'Due South','South SW','South West','West SW','Due West','West NW','North West','North NW',
                       'Due North']

        # Define actual cardinal wind direction and description based on current
        # wind direction in degrees
        if Spd[0] == 0:
            Direction = 'Calm'
            Description = '[color=9aba2fff]Calm[/color]'
        else:
            Ind = int(round(Dir[0]/22.5))
            Direction = Direction[Ind]
            Description = Description[Ind].split()[0] + ' [color=9aba2fff]' + Description[Ind].split()[1] + '[/color]'

        # Return cardinal wind direction and description
        return [Dir[0],Dir[1],Direction,Description]

    # SET THE BEAUFORT SCALE WIND SPEED, DESCRIPTION, AND ICON
    # --------------------------------------------------------------------------
    def BeaufortScale(self,Wind):

        # Define Beaufort Scale wind speed, description, and icon
        if Wind[0] <= 0.3:
            Speed = 0.0
            Icon = '0'
            Description = 'Calm Conditions'
        elif Wind[0] <= 1.6:
            Speed = 1.0
            Icon = '1'
            Description = 'Light Air'
        elif Wind[0] <= 3.5:
            Speed = 2.0
            Icon = '2'
            Description = 'Light Breeze'
        elif Wind[0] <= 5.5:
            Speed = 3.0
            Icon = '3'
            Description = 'Gentle Breeze'
        elif Wind[0] <= 8.0:
            Speed = 4.0
            Icon = '4'
            Description = 'Moderate Breeze'
        elif Wind[0] <= 10.8:
            Speed = 5.0
            Icon = '5'
            Description = 'Fresh Breeze'
        elif Wind[0] <= 13.9:
            Speed = 6.0
            Icon = '6'
            Description = 'Strong Breeze'
        elif Wind[0] <= 17.2:
            Speed = 7.0
            Icon = '7'
            Description = 'Near Gale Force'
        elif Wind[0] <= 20.8:
            Speed = 8.0
            Icon = '8'
            Description = 'Gale Force'
        elif Wind[0] <= 24.5:
            Speed = 9.0
            Icon = '9'
            Description = 'Severe Gale Force'
        elif Wind[0] <= 28.5:
            Speed = 10.0
            Icon = '10'
            Description = 'Storm Force'
        elif Wind[0] <= 32.7:
            Speed = 11.0
            Icon = '11'
            Description = 'Violent Storm'
        else:
            Speed = 12.0
            Icon = '12'
            Description = 'Hurricane Force'

        # Return Beaufort Scale speed, description, and icon
        return [Icon,Description,Speed]

    # SET THE UV INDEX ICON
    # --------------------------------------------------------------------------
    def UVIndex(self,UV):

        # Set the UV index icon
        if UV[0] < 1:
            UVIcon = '0'
        elif 1 <= UV[0] < 3:
            UVIcon = '1'
        elif 3 <= UV[0] < 6:
            UVIcon = '2'
        elif 6 <= UV[0] < 8:
            UVIcon = '3'
        elif 8 <= UV[0] < 11:
            UVIcon = '4'
        else:
            UVIcon = '5'

        # Return UV Index icon
        return [round(UV[0],1),'index',UVIcon]

    # CALCULATE SUNRISE/SUNSET TIMES
    # --------------------------------------------------------------------------
    def SunriseSunset(self):

        # Define Sunrise/Sunset location properties
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Ob = ephem.Observer()
        Ob.lat = str(self.config['Station']['Latitude'])
        Ob.lon = str(self.config['Station']['Longitude'])

        # The code is initialising. Calculate sunset/sunrise times for current
        # day starting at midnight in Station timezone
        if self.SunData['Sunset'][0] == '-':

            # Convert midnight today in Station timezone to midnight
            # today in UTC
            Date = date.today()
            Midnight = Tz.localize(datetime.combine(Date,time()))
            Midnight_UTC = Midnight.astimezone(pytz.utc)
            Ob.date = Midnight_UTC.strftime('%Y/%m/%d %H:%M:%S')

            # Sunrise time in station time zone
            Sunrise = Ob.next_rising(ephem.Sun())
            Sunrise = pytz.utc.localize(Sunrise.datetime())

            # Sunset time in station time zone
            Sunset = Ob.next_setting(ephem.Sun())
            Sunset = pytz.utc.localize(Sunset.datetime())

            # Define Kivy label binds
            self.SunData['Sunrise'][0] = Sunrise.astimezone(Tz)
            self.SunData['Sunset'][0] = Sunset.astimezone(Tz)

        # Sunset has passed. Calculate sunset/sunrise times for tomorrow
        # starting at midnight in Station timezone
        else:

            # Convert midnight tomorrow in Station timezone to midnight
            # tomorrow in UTC
            Date = date.today() + timedelta(days=1)
            Midnight = Tz.localize(datetime.combine(Date,time()))
            Midnight_UTC = Midnight.astimezone(pytz.utc)
            Ob.date = Midnight_UTC.strftime('%Y/%m/%d %H:%M:%S')

            # Sunrise time in station time zone
            Sunrise = Ob.next_rising(ephem.Sun())
            Sunrise = pytz.utc.localize(Sunrise.datetime())

            # Sunset time in station time zone
            Sunset = Ob.next_setting(ephem.Sun())
            Sunset = pytz.utc.localize(Sunset.datetime())

            # Define Kivy label binds
            self.SunData['Sunrise'][0] = Sunrise.astimezone(Tz)
            self.SunData['Sunset'][0] = Sunset.astimezone(Tz)

        # Update Kivy label binds based on date of next sunrise
        self.UpdateSunriseSunset()

    # CALCULATE MOONRISE/MOONSET TIMES
    # --------------------------------------------------------------------------
    def MoonriseMoonset(self):

        # Define Moonrise/Moonset location properties
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)
        Ob = ephem.Observer()
        Ob.lat = str(self.config['Station']['Latitude'])
        Ob.lon = str(self.config['Station']['Longitude'])

        # The code is initialising. Calculate moonrise time for current day
        # starting at midnight in station time zone
        if self.MoonData['Moonrise'][0] == '-':

            # Convert midnight in Station timezone to midnight in UTC
            Date = date.today()
            Midnight = Tz.localize(datetime.combine(Date,time()))
            Midnight_UTC = Midnight.astimezone(pytz.utc)
            Ob.date = Midnight_UTC.strftime('%Y/%m/%d %H:%M:%S')

            # Calculate Moonrise time in Station time zone
            Moonrise = Ob.next_rising(ephem.Moon())
            Moonrise = pytz.utc.localize(Moonrise.datetime())
            self.MoonData['Moonrise'][0] = Moonrise.astimezone(Tz)

        # Moonset has passed. Calculate time of next moonrise in station
        # timezone
        else:

            # Convert moonset time in Station timezone to moonset time in UTC
            Moonset = self.MoonData['Moonset'][0].astimezone(pytz.utc)
            Ob.date = Moonset.strftime('%Y/%m/%d %H:%M:%S')

            # Calculate Moonrise time in Station time zone
            Moonrise = Ob.next_rising(ephem.Moon())
            Moonrise = pytz.utc.localize(Moonrise.datetime())
            self.MoonData['Moonrise'][0] = Moonrise.astimezone(Tz)

        # Convert Moonrise time in Station timezone to Moonrise time in UTC
        Moonrise = self.MoonData['Moonrise'][0].astimezone(pytz.utc)
        Ob.date = Moonrise.strftime('%Y/%m/%d %H:%M:%S')

        # Calculate time of next Moonset in station timezone based on current
        # Moonrise time in UTC
        Moonset = Ob.next_setting(ephem.Moon())
        Moonset = pytz.utc.localize(Moonset.datetime())
        self.MoonData['Moonset'][0] = Moonset.astimezone(Tz)

        # Calculate date of next full moon in UTC
        Ob.date = Now.strftime('%Y/%m/%d')
        FullMoon = ephem.next_full_moon(Ob.date)
        FullMoon = pytz.utc.localize(FullMoon.datetime())

        # Calculate date of next new moon in UTC
        NewMoon = ephem.next_new_moon(Ob.date)
        NewMoon = pytz.utc.localize(NewMoon.datetime())

        # Define Kivy label binds for next new/full moon in station time zone
        self.MoonData['FullMoon'] = [FullMoon.astimezone(Tz).strftime('%b %d'),FullMoon]
        self.MoonData['NewMoon'] = [NewMoon.astimezone(Tz).strftime('%b %d'),NewMoon]

        # Update Kivy label binds based on date of next moonrise
        self.UpdateMoonriseMoonset()

    # UPDATE SUNSET AND SUNRISE KIVY LABEL BINDS BASED ON DATE OF NEXT SUNRISE
    # --------------------------------------------------------------------------
    def UpdateSunriseSunset(self):
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)
        if Now.date() == self.SunData['Sunrise'][0].date():
            self.SunData['Sunrise'][1] = self.SunData['Sunrise'][0].strftime('%H:%M')
            self.SunData['Sunset'][1] = self.SunData['Sunset'][0].strftime('%H:%M')
        else:
            self.SunData['Sunrise'][1] = self.SunData['Sunrise'][0].strftime('%H:%M') + ' (+1)'
            self.SunData['Sunset'][1] = self.SunData['Sunset'][0].strftime('%H:%M') + ' (+1)'

    # UPDATE MOONRISE AND MOONSET KIVY LABEL BINDS BASED ON DATE OF NEXT
    # MOONRISE
    # --------------------------------------------------------------------------
    def UpdateMoonriseMoonset(self):

        # Get current time in station time zone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Update Moonrise Kivy Label bind based on date of next moonrise
        if Now.date() == self.MoonData['Moonrise'][0].date():
            self.MoonData['Moonrise'][1] = self.MoonData['Moonrise'][0].strftime('%H:%M')
        elif Now.date() < self.MoonData['Moonrise'][0].date():
            self.MoonData['Moonrise'][1] = self.MoonData['Moonrise'][0].strftime('%H:%M') + ' (+1)'
        else:
            self.MoonData['Moonrise'][1] = self.MoonData['Moonrise'][0].strftime('%H:%M') + ' (-1)'

        # Update Moonset Kivy Label bind based on date of next moonset
        if Now.date() == self.MoonData['Moonset'][0].date():
            self.MoonData['Moonset'][1] = self.MoonData['Moonset'][0].strftime('%H:%M')
        elif Now.date() < self.MoonData['Moonset'][0].date():
            self.MoonData['Moonset'][1] = self.MoonData['Moonset'][0].strftime('%H:%M') + ' (+1)'
        else:
            self.MoonData['Moonset'][1] = self.MoonData['Moonset'][0].strftime('%H:%M') + ' (-1)'

        # Update New Moon Kivy Label bind based on date of next new moon
        if self.MoonData['FullMoon'][1].date() == Now.date():
            self.MoonData['FullMoon'] = ['[color=ff8837ff]Today[/color]',self.MoonData['FullMoon'][1]]

        # Update Full Moon Kivy Label bind based on date of next full moon
        elif self.MoonData['NewMoon'][1].date() == Now.date():
            self.MoonData['NewMoon'] = ['[color=ff8837ff]Today[/color]',self.MoonData['NewMoon'][1]]

    # CALCULATE THE SUN TRANSIT ANGLE AND THE TIME UNTIL SUNRISE OR SUNSET
    # --------------------------------------------------------------------------
    def SunTransit(self,dt):

        # Get current time in station time zone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # If time is between sunrise and sun set, calculate sun
        # transit angle
        if Now >= self.SunData['Sunrise'][0] and Now <= self.SunData['Sunset'][0]:

            # Determine total length of daylight, amount of daylight
            # that has passed, and amount of daylight left
            DaylightTotal = self.SunData['Sunset'][0] - self.SunData['Sunrise'][0]
            DaylightLapsed = Now - self.SunData['Sunrise'][0]
            DaylightLeft = self.SunData['Sunset'][0] - Now

            # Determine sun transit angle
            Angle = DaylightLapsed.total_seconds() / DaylightTotal.total_seconds() * 180
            Angle = int(Angle*10)/10.0

            # Determine hours and minutes left until sunset
            hours,remainder = divmod(DaylightLeft.total_seconds(), 3600)
            minutes,seconds = divmod(remainder,60)

            # Define Kivy Label binds
            self.SunData['SunAngle'] = '{:.1f}'.format(Angle)
            self.SunData['Event'] = ['Till [color=f05e40ff]Sunset[/color]','{:02.0f}'.format(hours),'{:02.0f}'.format(minutes)]

        # When not daylight, set sun transit angle to building
        # value. Define time until sunrise
        elif Now <= self.SunData['Sunrise'][0]:

            # Determine hours and minutes left until sunrise
            NightLeft = self.SunData['Sunrise'][0] - Now
            hours,remainder = divmod(NightLeft.total_seconds(), 3600)
            minutes,seconds = divmod(remainder,60)

            # Define Kivy Label binds
            self.SunData['SunAngle'] = '-'
            self.SunData['Event'] = ['Till [color=f0b240ff]Sunrise[/color]','{:02.0f}'.format(hours),'{:02.0f}'.format(minutes)]

    # CALCULATE THE PHASE OF THE MOON
    # --------------------------------------------------------------------------
    def MoonPhase(self,dt):

        # Define current time and date in UTC and station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        UTC = datetime.now(pytz.utc)
        Now = UTC.astimezone(Tz)

        # Define moon phase location properties
        Ob = ephem.Observer()
        Ob.lat = str(self.config['Station']['Latitude'])
        Ob.lon = str(self.config['Station']['Longitude'])

        # Calculate date of next full moon in station time zone
        Ob.date = Now.strftime('%Y/%m/%d')
        FullMoon = ephem.next_full_moon(Ob.date)
        FullMoon = pytz.utc.localize(FullMoon.datetime())
        FullMoon = FullMoon.astimezone(Tz)

        # Calculate date of next new moon in station time zone
        NewMoon = ephem.next_new_moon(Ob.date)
        NewMoon = pytz.utc.localize(NewMoon.datetime())
        NewMoon = NewMoon.astimezone(Tz)

        # Calculate phase of moon
        Moon = ephem.Moon()
        Moon.compute(UTC.strftime('%Y/%m/%d %H:%M:%S'))

        # Define Moon phase icon
        if FullMoon < NewMoon:
            PhaseIcon = 'Waxing_' + '{:.0f}'.format(Moon.phase)
        elif NewMoon < FullMoon:
            PhaseIcon = 'Waning_' + '{:.0f}'.format(Moon.phase)

        # Define Moon phase text
        if self.MoonData['NewMoon'] == '[color=ff8837ff]Today[/color]':
            PhaseTxt = 'New Moon'
        elif self.MoonData['FullMoon'] == '[color=ff8837ff]Today[/color]':
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
        self.MoonData['Phase'] = [PhaseIcon,PhaseTxt,Illumination]

    # DOWNLOAD THE LATEST FORECAST FOR STATION LOCATION
    # --------------------------------------------------------------------------
    def DownloadForecast(self):

        # If Station is located in Great Britain, download latest
        # MetOffice three-hourly forecast
        if self.config['Station']['Country'] == 'GB':
            Template = 'http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/json/{}?res=3hourly&key={}'
            URL = Template.format(self.config['Station']['MetOfficeID'],self.config['Keys']['MetOffice'])
            try:
                self.MetDict = requests.get(URL).json()
            except:
                if not hasattr(self, 'MetDict'):
                    self.MetDict = {}
            self.ExtractMetOfficeForecast()

        # If station is located outside of Great Britain, download the latest
        # DarkSky hourly forecast
        else:
            Template = 'https://api.darksky.net/forecast/{}/{},{}?exclude=currently,minutely,alerts,flags&units=uk2'
            URL = Template.format(self.config['Keys']['DarkSky'],self.config['Station']['Latitude'],self.config['Station']['Longitude'])
            try:
                self.MetDict = requests.get(URL).json()
            except:
                if not hasattr(self, 'MetDict'):
                    self.MetDict = {}
            self.ExtractDarkSkyForecast()

    # EXTRACT THE LATEST THREE-HOURLY METOFFICE FORECAST FOR THE STATION
    # LOCATION
    # --------------------------------------------------------------------------
    def ExtractMetOfficeForecast(self):

        # Get current time in station time zone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Extract all forecast data from DarkSky JSON file. If  forecast is
        # unavailable, set forecast variables to blank and indicate to user that
        # forecast is unavailable
        try:
            MetData = (self.MetDict['SiteRep']['DV']['Location']['Period'])
        except KeyError:
            self.MetData['Time'] = Now
            self.MetData['Temp'] = '--'
            self.MetData['WindDir'] = '--'
            self.MetData['WindSpd'] = '--'
            self.MetData['Weather'] = 'ForecastUnavailable'
            self.MetData['Precip'] = '--'
            self.MetData['Issued'] = '--'
            self.MetData['Valid'] = '--'

            # Attempt to download forecast again in 1 minute
            Clock.schedule_once(lambda dt: self.DownloadForecast(),600)
            return

        # Extract issue time of forecast data
        Issued = str(self.MetDict['SiteRep']['DV']['dataDate'][11:-4])

        # Extract date of all available forecasts, and retrieve forecast for
        # today
        Dates = list(item['value'] for item in MetData)
        MetData = MetData[Dates.index(Now.strftime('%Y-%m-%dZ'))]['Rep']

        # Extract 'valid from' time of all available three-hourly forecasts, and
        # retrieve forecast for the current three-hour period
        Times = list(int(item['$'])//60 for item in MetData)
        MetData = MetData[bisect.bisect(Times,Now.hour)-1]

        # Extract 'valid until' time for the retrieved forecast
        Valid = Times[bisect.bisect(Times,Now.hour)-1] + 3
        if Valid == 24:
            Valid = 0

        # Extract weather variables from MetOffice forecast
        Temp = [float(MetData['T']),'c']
        WindSpd = [float(MetData['S'])/2.2369362920544,'mps']
        WindDir = [MetData['D'],'cardinal']
        Precip = [MetData['Pp'],'%']
        Weather = MetData['W']

        # Convert forecast units as required
        Temp = self.ObservationUnits(Temp,self.config['Units']['Temp'])
        WindSpd = self.ObservationUnits(WindSpd,self.config['Units']['Wind'])

        # Define and format Kivy label binds
        self.MetData['Time'] = Now
        self.MetData['Issued'] = Issued
        self.MetData['Valid'] = '{:02.0f}'.format(Valid) + ':00'
        self.MetData['Temp'] = ['{:.1f}'.format(Temp[0]),Temp[1]]
        self.MetData['WindDir'] = WindDir[0]
        self.MetData['WindSpd'] = ['{:.0f}'.format(WindSpd[0]),WindSpd[1]]
        self.MetData['Weather'] = Weather
        self.MetData['Precip'] = Precip[0]

    # EXTRACT THE LATEST HOURLY DARK SKY FORECAST FOR THE STATION LOCATION
    # --------------------------------------------------------------------------
    def ExtractDarkSkyForecast(self):

        # Get current time in station time zone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Extract all forecast data from DarkSky JSON file. If  forecast is
        # unavailable, set forecast variables to blank and indicate to user that
        # forecast is unavailable
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        try:
            MetData = (self.MetDict['hourly']['data'])
        except KeyError:
            self.MetData['Time'] = Now
            self.MetData['Temp'] = '--'
            self.MetData['WindDir'] = '--'
            self.MetData['WindSpd'] = '--'
            self.MetData['Weather'] = 'ForecastUnavailable'
            self.MetData['Precip'] = '--'
            self.MetData['Issued'] = '--'
            self.MetData['Valid'] = '--'

            # Attempt to download forecast again in 1 minute
            Clock.schedule_once(lambda dt: self.DownloadForecast(),600)
            return

        # Extract 'valid from' time of all available hourly forecasts, and
        # retrieve forecast for the current hourly period
        Times = list(item['time'] for item in MetData)
        MetData = MetData[bisect.bisect(Times,int(UNIX.time()))-1]

        # Extract 'Issued' and 'Valid' times
        Issued = Times[0]
        Valid = Times[bisect.bisect(Times,int(UNIX.time()))]
        Issued = datetime.fromtimestamp(Issued,pytz.utc).astimezone(Tz)
        Valid = datetime.fromtimestamp(Valid,pytz.utc).astimezone(Tz)

        # Extract weather variables from DarkSky forecast
        Temp = [MetData['temperature'],'c']
        WindSpd = [MetData['windSpeed']/2.2369362920544,'mps']
        WindDir = [MetData['windBearing'],'degrees']
        Precip = [MetData['precipProbability']*100,'%']
        Weather = MetData['icon']

        # Convert forecast units as required
        Temp = self.ObservationUnits(Temp,self.config['Units']['Temp'])
        WindSpd = self.ObservationUnits(WindSpd,self.config['Units']['Wind'])

        # Define and format Kivy label binds
        self.MetData['Time'] = Now
        self.MetData['Issued'] = datetime.strftime(Issued,'%H:%M')
        self.MetData['Valid'] = datetime.strftime(Valid,'%H:%M')
        self.MetData['Temp'] = ['{:.1f}'.format(Temp[0]),Temp[1]]
        self.MetData['WindDir'] = self.CardinalWindDirection(WindDir)[2]
        self.MetData['WindSpd'] = ['{:.0f}'.format(WindSpd[0]),WindSpd[1]]
        self.MetData['Precip'] = '{:.0f}'.format(Precip[0])

        # Define weather icon
        if Weather == 'clear-day':
            self.MetData['Weather'] = '1'
        elif Weather == 'clear-night':
            self.MetData['Weather'] = '0'
        elif Weather == 'rain':
            self.MetData['Weather'] = '12'
        elif Weather == 'snow':
            self.MetData['Weather'] = '27'
        elif Weather == 'sleet':
            self.MetData['Weather'] = '18'
        elif Weather == 'wind':
            self.MetData['Weather'] = 'wind'
        elif Weather == 'fog':
            self.MetData['Weather'] = '6'
        elif Weather == 'cloudy':
            self.MetData['Weather'] = '7'
        elif Weather == 'partly-cloudy-day':
            self.MetData['Weather'] = '3'
        elif Weather == 'partly-cloudy-night':
            self.MetData['Weather'] = '2'
        else:
            self.MetData['Weather'] = 'ForecastUnavailable'

    # CALCULATE SAGER WEATHERCASTER FORECAST USING OBSERVED WEATHER TREND OVER
    # THE PREVIOUS SIX HOURS
    # --------------------------------------------------------------------------
    def SagerForecast(self,dt):

        # Get current UNIX timestamp in UTC
        Now = int(UNIX.time())
        Hours_6 = (6*60*60)+60

        # Get station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])

        # Download Sky data from last 6 hours using Weatherflow API
        Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
        URL = Template.format(self.config['Station']['SkyID'],Now-Hours_6,Now,self.config['Keys']['WeatherFlow'])
        Data = requests.get(URL)
        Sky = {}

        # Extract observation times, wind speed, wind direction, and rainfall.
        # If API call has failed, return blank Sager Forecast
        if VerifyJSON(Data,'WeatherFlow','obs'):
            Sky['obs'] = Data.json()['obs']
            Sky['Time'] = [item[0] if item[0] != None else NaN for item in Sky['obs']]
            Sky['WindSpd'] = [item[5]*2.23694 if item[5] != None else NaN for item in Sky['obs']]
            Sky['WindDir'] = [item[7] if item[7] != None else NaN for item in Sky['obs']]
            Sky['Rain'] = [item[3] if item[3] != None else NaN for item in Sky['obs']]
        else:
            self.Sager['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing Sky data. Forecast will be regenerated in 60 minutes'
            self.Sager['Issued'] = datetime.now(pytz.utc).astimezone(Tz).strftime('%H:%M')
            Clock.schedule_once(self.SagerForecast,3600)
            return

        # Convert SKY data to Numpy arrays
        Sky['Time'] = np.array(Sky['Time'],dtype=np.int64)
        Sky['WindSpd'] = np.array(Sky['WindSpd'],dtype=np.float64)
        Sky['WindDir'] = np.array(Sky['WindDir'],dtype=np.float64)
        Sky['Rain'] = np.array(Sky['Rain'],dtype=np.float64)

        # Download AIR data from from last 6 hours using Weatherflow API
        Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
        URL = Template.format(self.config['Station']['OutdoorID'],Now-Hours_6,Now,self.config['Keys']['WeatherFlow'])
        Data = requests.get(URL)
        Air = {}

        # Extract observation times, pressure and temperature. If API call has
        # failed, return blank Sager Forecast
        if VerifyJSON(Data,'WeatherFlow','obs'):
            Air['obs'] = Data.json()['obs']
            Air['Time'] = [item[0] if item[0] != None else NaN for item in Air['obs']]
            Air['Pres'] = [item[1] if item[1] != None else NaN for item in Air['obs']]
            Air['Temp'] = [item[2] if item[2] != None else NaN for item in Air['obs']]
        else:
            self.Sager['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing Air data. Forecast will be regenerated in 60 minutes'
            self.Sager['Issued'] = datetime.now(pytz.utc).astimezone(Tz).strftime('%H:%M')
            Clock.schedule_once(self.SagerForecast,3600)
            return

        # Convert AIR data to Numpy arrays
        Air['Time'] = np.array(Air['Time'],dtype=np.int64)
        Air['Pres'] = np.array(Air['Pres'],dtype=np.float64)
        Air['Temp'] = np.array(Air['Temp'],dtype=np.float64)

        # Define required station variables for the Sager Weathercaster Forecast
        self.Sager['Lat'] = float(self.config['Station']['Latitude'])
        self.Sager['Units'] = self.config['Units']['Wind']

        # Define required wind direction variables for the Sager Weathercaster
        # Forecast
        WindDir6 = Sky['WindDir'][:15]
        WindDir = Sky['WindDir'][-15:]
        if not np.all(np.isnan(WindDir6)) or np.all(np.isnan(WindDir)):
            self.Sager['WindDir6'] = CircularMean(WindDir6)
            self.Sager['WindDir'] = CircularMean(WindDir)
        else:
            self.Sager['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing wind direction data. Forecast will be regenerated in 60 minutes'
            self.Sager['Issued'] = datetime.now(pytz.utc).astimezone(Tz).strftime('%H:%M')
            Clock.schedule_once(self.SagerForecast,3600)
            return

        # Define required wind speed variables for the Sager Weathercaster
        # Forecast
        WindSpd6 = Sky['WindSpd'][:15]
        WindSpd = Sky['WindSpd'][-15:]
        if not np.all(np.isnan(WindSpd6)) or np.all(np.isnan(WindSpd)):
            self.Sager['WindSpd6'] = np.nanmean(WindSpd6)
            self.Sager['WindSpd'] = np.nanmean(WindSpd)
        else:
            self.Sager['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing wind speed data. Forecast will be regenerated in 60 minutes'
            self.Sager['Issued'] = datetime.now(pytz.utc).astimezone(Tz).strftime('%H:%M')
            Clock.schedule_once(self.SagerForecast,3600)
            return

        # Define required pressure variables for the Sager Weathercaster
        # Forecast
        Pres6 = Air['Pres'][:15]
        Pres = Air['Pres'][-15:]
        if not np.all(np.isnan(Pres6)) or np.all(np.isnan(Pres)):
            self.Sager['Pres6'] = self.SeaLevelPressure([np.nanmean(Pres6).tolist(),'mb'])[0]
            self.Sager['Pres'] = self.SeaLevelPressure([np.nanmean(Pres).tolist(),'mb'])[0]
        else:
            self.Sager['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing pressure data. Forecast will be regenerated in 60 minutes'
            self.Sager['Issued'] = datetime.now(pytz.utc).astimezone(Tz).strftime('%H:%M')
            Clock.schedule_once(self.SagerForecast,3600)
            return

        # Define required temperature variables for the Sager Weathercaster
        # Forecast
        Temp = Air['Temp'][-15:]
        if not np.all(np.isnan(Temp)):
            self.Sager['Temp'] = np.nanmean(Temp)
        else:
            self.Sager['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing temperature data. Forecast will be regenerated in 60 minutes'
            self.Sager['Issued'] = datetime.now(pytz.utc).astimezone(Tz).strftime('%H:%M')
            Clock.schedule_once(self.SagerForecast,3600)
            return

        # Define required present weather variables for the Sager Weathercaster
        # Forecast
        Now = datetime.now(pytz.utc).astimezone(Tz)
        LastRain = np.where(Sky['Rain'] > 0)[0]
        if LastRain.size == 0:
            self.Sager['LastRain'] = math.inf
        else:
            LastRain = Sky['Time'][LastRain.max()]
            LastRain = datetime.fromtimestamp(LastRain,Tz)
            LastRain = Now - LastRain
            self.Sager['LastRain'] = LastRain.total_seconds()/60

        # Download closet METAR information to station location
        header = {'X-API-Key':self.config['Keys']['CheckWX']}
        Template = 'https://api.checkwx.com/metar/lat/{}/lon/{}/decoded'
        URL = Template.format(self.config['Station']['Latitude'],self.config['Station']['Longitude'])
        Data = requests.get(URL,headers=header)
        if VerifyJSON(Data,'CheckWX','data'):
            self.Sager['METAR'] = Data.json()['data'][0]
        else:
            self.Sager['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing METAR information. Forecast will be regenerated in 60 minutes'
            self.Sager['Issued'] = Now.strftime('%H:%M')
            Clock.schedule_once(self.SagerForecast,3600)
            return

        # Calculate Sager Weathercaster Forecast
        self.Sager['Dial'] = sager.DialSetting(self.Sager)
        if self.Sager['Dial'] is not None:
            self.Sager['Forecast'] = sager.Forecast(self.Sager['Dial'])
            self.Sager['Issued'] = Now.strftime('%H:%M')
        else:
            self.Sager['Forecast'] = '[color=f05e40ff]ERROR:[/color] Missing METAR information. Forecast will be regenerated in 60 minutes'
            self.Sager['Issued'] = Now.strftime('%H:%M')
            Clock.schedule_once(self.SagerForecast,3600)
            return

        # Schedule generation of next Sager Weathercaster forecast
        if Now.hour < 6:
            Date = Now.date()
            Time = time(6,0,0)
            ForecastTime = Tz.localize(datetime.combine(Date,Time))
        elif Now.hour < 18:
            Date = Now.date()
            Time = time(18,0,0)
            ForecastTime = Tz.localize(datetime.combine(Date,Time))
        else:
            Date = Now.date() + timedelta(days=1)
            Time = time(6,0,0)
            ForecastTime = Tz.localize(datetime.combine(Date,Time))
        Seconds = (ForecastTime - Now).total_seconds()
        Clock.schedule_once(self.SagerForecast,Seconds)

    # CHECK STATUS OF SKY AND AIR MODULES
    # --------------------------------------------------------------------------
    def SkyAirStatus(self,dt):

        # Define current time in station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Check latest AIR observation time is less than 5 minutes old and
        # battery voltage is greater than 1.9 v
        if 'Obs' in self.Air:
            AirTime = datetime.fromtimestamp(self.Air['Obs'][0],Tz)
            AirDiff = (Now - AirTime).total_seconds()
            if self.Air['Battery'][0] != '-':
                AirVoltage = float(self.Air['Battery'][0])
            else:
                AirVoltage = 0;
            if AirDiff < 300 and AirVoltage > 1.9:
                self.Air['StatusIcon'] = 'OK'

            # Latest AIR observation time is greater than 5 minutes old
            else:
                self.Air['StatusIcon'] = 'Error'

        # Check latest Sky observation time is less than 5 minutes old and
        # battery voltage is greater than 2.0 v
        if 'Obs' in self.Sky:
            SkyTime = datetime.fromtimestamp(self.Sky['Obs'][0],Tz)
            SkyDiff = (Now - SkyTime).total_seconds()
            if self.Sky['Battery'][0] != '-':
                SkyVoltage = float(self.Sky['Battery'][0])
            else:
                SkyVoltage = 0;
            if SkyDiff < 300 and SkyVoltage > 2.0:
                self.Sky['StatusIcon'] = 'OK'

            # Latest Sky observation time is greater than 5 minutes old
            else:
                self.Sky['StatusIcon'] = 'Error'

    # UPDATE 'WeatherFlowPiConsole' METHODS AT REQUIRED INTERVALS
    # --------------------------------------------------------------------------
    def UpdateMethods(self,dt):

        # Get current time in station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)
        Now = Now.replace(microsecond=0)

        # At 5 minutes past each hour, download a new forecast for the Station
        # location
        if (Now.minute,Now.second) == (5,0):
            self.DownloadForecast()

        # At the top of each hour update the on-screen forecast for the Station
        # location
        if Now.hour > self.MetData['Time'].hour or Now.date() > self.MetData['Time'].date():
            if self.config['Station']['Country'] == 'GB':
                self.ExtractMetOfficeForecast()
            else:
                self.ExtractDarkSkyForecast()
            self.MetData['Time'] = Now

        # Once sunset has passed, calculate new sunrise/sunset times
        if Now > self.SunData['Sunset'][0]:
            self.SunriseSunset()

        # Once moonset has passed, calculate new moonrise/moonset times
        if Now > self.MoonData['Moonset'][0]:
            self.MoonriseMoonset()

        # At midnight, update Sunset, Sunrise, Moonrise and Moonset Kivy Labels
        if Now.time() == time(0,0,0):
            self.UpdateSunriseSunset()
            self.UpdateMoonriseMoonset()

    # CHECK CURRENT VERSION OF CODE AGAINST LATEST AVAILABLE VERSION
    # --------------------------------------------------------------------------
    def CheckVersion(self,dt):

        # Get latest verion tag from Github API
        header = {'Accept': 'application/vnd.github.v3+json'}
        Template = 'https://api.github.com/repos/{}/{}/releases/latest'
        URL = Template.format('peted-davis','WeatherFlow_PiConsole')
        Data = requests.get(URL,headers=header).json()
        self.System['LatestVer'] = Data['tag_name']

        # Get current time in station time zone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # If current version and latest version do not match, open update
        # notification
        if version.parse(self.Version) < version.parse(self.System['LatestVer']):

            # Check if update notification is already open. Close if required
            if 'UpdateNotif' in self.System:
                self.System['UpdateNotif'].dismiss()

            # Open update notification
            self.System['UpdateNotif'] = Version()
            self.System['UpdateNotif'].open()

        # Schedule next Version Check
        Next = Tz.localize(datetime.combine(date.today()+timedelta(days=1),time(0,0,0)))
        Clock.schedule_once(self.CheckVersion,(Next-Now).total_seconds())

# ==============================================================================
# DEFINE 'CurrentConditions' SCREEN
# ==============================================================================
class CurrentConditions(Screen):

    # Define CurrentConditions class dictionary properties
    Screen = DictProperty([('Clock','--'),('xRainAnim',471),('yRainAnim',11)])

    # Define CurrentConditions class numeric properties
    xLightningBolt = NumericProperty(0)
    WindRoseDir = NumericProperty(0)

    # INITIALISE 'CurrentConditions' SCREEN CLASS
    # --------------------------------------------------------------------------
    def __init__(self,**kwargs):
        super(CurrentConditions,self).__init__(**kwargs)
        Clock.schedule_interval(self.Clock,1.0)
        Clock.schedule_interval(self.RainRateAnimation,1/10)

    # DEFINE DATE AND TIME FOR CLOCK IN STATION TIMEZONE
    # --------------------------------------------------------------------------
    def Clock(self,dt):

        # Define time and date format based on user settings
        if App.get_running_app().TimeFormat == '12 hr':
            TimeFormat = '%I:%M:%S %p'
        else:
            TimeFormat = '%H:%M:%S'
        if  App.get_running_app().DateFormat == 'Mon, Jan 01 0000':
            DateFormat = '%a, %b %d %Y'
        elif App.get_running_app().DateFormat == 'Monday, 01 Jan 0000':
            DateFormat = '%A, %d %b %Y'
        elif App.get_running_app().DateFormat == 'Monday, Jan 01 0000':
            DateFormat = '%A, %b %d %Y'
        else:
            DateFormat = '%a, %d %b %Y'

        # Get current time in station time zone
        Tz = pytz.timezone(App.get_running_app().config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)

        # Format current time
        self.Screen['Clock'] = Now.strftime(DateFormat + '\n' + TimeFormat)

    # ANIMATE RAPID-WIND WIND ROSE DIRECTION ARROW
    # --------------------------------------------------------------------------
    def WindRoseAnimation(self,newDirec,oldDirec):

        # Calculate change in wind direction over last Rapid-Wind period
        WindShift = newDirec - oldDirec

        # Animate Wind Rose at constant speed between old and new Rapid-Wind
        # wind direction
        if WindShift >= -180 and WindShift <= 180:
            Anim = Animation(WindRoseDir=newDirec,duration=2*abs(WindShift)/360)
            Anim.start(self)
        elif WindShift > 180:
            Anim = Animation(WindRoseDir=0.1,duration=2*oldDirec/360) + Animation(WindRoseDir=newDirec,duration=2*(360-newDirec)/360)
            Anim.start(self)
        elif WindShift < -180:
            Anim = Animation(WindRoseDir=359.9,duration=2*(360-oldDirec)/360) + Animation(WindRoseDir=newDirec,duration=2*newDirec/360)
            Anim.start(self)

    # Fix Wind Rose angle at 0/360 degree discontinuity
    def on_WindRoseDir(self,item,WindRoseDir):
        if WindRoseDir == 0.1:
            item.WindRoseDir = 360
        if WindRoseDir == 359.9:
            item.WindRoseDir = 0

    # ANIMATE RAIN RATE ICON
    # --------------------------------------------------------------------------
    def RainRateAnimation(self,dt):

        # Calculate current rain rate
        if 'Obs' in App.get_running_app().Sky:
            RainRate = App.get_running_app().Sky['Obs'][3] * 60
        else:
            return

        # Define required animation variables
        x0 = 11
        xt = 124
        t = 50

        # Calculate rain rate animation y position
        if RainRate == 0:
            self.Screen['yRainAnim'] = x0
        elif RainRate < 50.0:
            A = (xt-x0)/t**0.5 * RainRate**0.5 + x0
            B = (xt-x0)/t**0.3 * RainRate**0.3 + x0
            C = (1 + np.tanh(RainRate-3))/2
            self.Screen['yRainAnim'] = np.asscalar(A + C * (B-A))
        else:
            self.Screen['yRainAnim'] = xt

        # Rain rate animation x position
        if self.Screen['xRainAnim']-1 == 240:
            self.Screen['xRainAnim'] = 471
        else:
            self.Screen['xRainAnim'] -= 1

    # ANIMATE LIGHTNING BOLT ICON WHEN STRIKE IS DETECTED
    # --------------------------------------------------------------------------
    def LightningBoltAnim(self):
        Anim = Animation(xLightningBolt=5,t='out_quad',d=0.02) + Animation(xLightningBolt=0,t='out_elastic',d=0.5)
        Anim.start(self)

    # SWITCH BETWEEN PANELS BASED ON USER INPUT
    # --------------------------------------------------------------------------
    def SwitchPanel(self,Instance,Panel):

        # Switch between MetOffice and Sager Forecast panels
        if Panel == 'MetSager':
            if self.ids.Sager.opacity == 0:
                self.ids.MetOffice.opacity = 0
                self.ids.Sager.opacity = 1
            else:
                self.ids.MetOffice.opacity = 1
                self.ids.Sager.opacity = 0

        # Switch between Sunrise/Sunset and Moonrise/Moonset panels
        elif Panel == 'SunMoon':
            if self.ids.Moon.opacity == 0:
                self.ids.Sunrise.opacity = 0
                self.ids.Moon.opacity = 1
            else:
                self.ids.Sunrise.opacity = 1
                self.ids.Moon.opacity = 0

        # Switch between Rainfall and Lightning panels
        elif Panel == 'RainLightning':
            if self.ids.LightningPanel.opacity == 0:
                self.ids.LightningPanel.opacity = 1
                self.ids.RainLightningButton.background_normal = 'buttons/rainfall.png'
                self.ids.RainLightningButton.background_down = 'buttons/rainfallPressed.png'
            else:
                self.ids.LightningPanel.opacity = 0
                self.ids.RainLightningButton.background_normal = 'buttons/lightning.png'
                self.ids.RainLightningButton.background_down = 'buttons/lightningPressed.png'





# ==============================================================================
# DEFINE CREDITS POPUP
# ==============================================================================
class Credits(Popup):
    pass

# ==============================================================================
# DEFINE VERSION POPUP
# ==============================================================================
class Version(Popup):
    pass

# ==============================================================================
# DEFINE 'SettingScrollOptions' SETTINGS CLASS
# ==============================================================================
class SettingScrollOptions(SettingOptions):

    def _create_popup(self,instance):

        # Create the popup and scrollview
        content         = BoxLayout(orientation='vertical', spacing='5dp')
        scrollview      = ScrollView(do_scroll_x=False, bar_inactive_color=[.7, .7, .7, 0.9], bar_width=4)
        scrollcontent   = GridLayout(cols=1, spacing='5dp', size_hint=(0.95, None))
        self.popup      = Popup(content=content, title=self.title, size_hint=(0.25, 0.8),
                                auto_dismiss=False, separator_color=[1,1,1,1])

        # Add all the options to the ScrollView
        scrollcontent.bind(minimum_height=scrollcontent.setter('height'))
        content.add_widget(Widget(size_hint_y=None, height=dp(1)))
        uid = str(self.uid)
        for option in self.options:
            state = 'down' if option == self.value else 'normal'
            btn = ToggleButton(text=option, state=state, group=uid, height=dp(58), size_hint=(0.9, None))
            btn.bind(on_release=self._set_option)
            scrollcontent.add_widget(btn)

        # Finally, add a cancel button to return on the previous panel
        scrollview.add_widget(scrollcontent)
        content.add_widget(scrollview)
        content.add_widget(SettingSpacer())
        btn = Button(text='Cancel', height=dp(58), size_hint=(1, None))
        btn.bind(on_release=self.popup.dismiss)
        content.add_widget(btn)
        self.popup.open()

# ==============================================================================
# DEFINE 'SettingFixedOptions' SETTINGS CLASS
# ==============================================================================
class SettingFixedOptions(SettingOptions):

    def _create_popup(self, instance):

        # Create the popup
        content     = BoxLayout(orientation='vertical', spacing='5dp')
        self.popup  = Popup(content=content, title=self.title, size_hint=(0.25, None),
                            auto_dismiss=False, separator_color=[1,1,1,1], height=129+min(len(self.options),4) * 63)

        # Add all the options to the Popup
        content.add_widget(Widget(size_hint_y=None, height=1))
        uid = str(self.uid)
        for option in self.options:
            state = 'down' if option == self.value else 'normal'
            btn = ToggleButton(text=option, state=state, group=uid, height=dp(58), size_hint=(1, None))
            btn.bind(on_release=self._set_option)
            content.add_widget(btn)

        # Add a cancel button to return on the previous panel
        content.add_widget(SettingSpacer())
        btn = Button(text='Cancel', height=dp(58), size_hint=(1, None))
        btn.bind(on_release=self.popup.dismiss)
        content.add_widget(btn)
        self.popup.open()

# ==============================================================================
# DEFINE 'SettingToggleTemperature' SETTINGS CLASS
# ==============================================================================
class SettingToggleTemperature(SettingString):

    def _create_popup(self, instance):

        # Get temperature units from config file
        config = App.get_running_app().config
        Units = '[sup]o[/sup]' + config['Units']['Temp'].upper()

        # Create Popup layout
        content     = BoxLayout(orientation='vertical', spacing='5dp')
        self.popup  = Popup(content=content, title=self.title, size_hint=(0.25, None),
                            auto_dismiss=False, separator_color=[1,1,1,0], height='234dp')
        content.add_widget(SettingSpacer())

        # Create the label to show the numeric value
        self.Label = Label(text=self.value+Units, markup=True, font_size='24sp', size_hint_y=None, height='50dp', halign='left')
        content.add_widget(self.Label)

        # Add a plus and minus increment button to change the value by +/- one
        btnlayout = BoxLayout(size_hint_y=None, height='50dp', spacing='5dp')
        btn = Button(text='-')
        btn.bind(on_press=self.minus)
        btnlayout.add_widget(btn)
        btn = Button(text='+')
        btn.bind(on_press=self.plus)
        btnlayout.add_widget(btn)
        content.add_widget(btnlayout)
        content.add_widget(SettingSpacer())

        # Add an OK button to set the value, and a cancel button to return to
        # the previous panel
        btnlayout = BoxLayout(size_hint_y=None, height='50dp', spacing='5dp')
        btn = Button(text='Ok')
        btn.bind(on_release=self._set_value)
        btnlayout.add_widget(btn)
        btn = Button(text='Cancel')
        btn.bind(on_release=self.popup.dismiss)
        btnlayout.add_widget(btn)
        content.add_widget(btnlayout)

        # Open the popup
        self.popup.open()

    def _set_value(self,instance):
        if '[sup]o[/sup]C' in self.Label.text:
            Units = '[sup]o[/sup]C'
        else:
            Units = '[sup]o[/sup]F'
        self.value = self.Label.text.replace(Units,'')
        self.popup.dismiss()

    def minus(self,instance):
        if '[sup]o[/sup]C' in self.Label.text:
            Units = '[sup]o[/sup]C'
        else:
            Units = '[sup]o[/sup]F'
        Value = int(self.Label.text.replace(Units,'')) - 1
        self.Label.text =str(Value) + Units

    def plus(self,instance):
        if '[sup]o[/sup]C' in self.Label.text:
            Units = '[sup]o[/sup]C'
        else:
            Units = '[sup]o[/sup]F'
        Value = int(self.Label.text.replace(Units,'')) + 1
        self.Label.text =str(Value) + Units

# ==============================================================================
# RUN APP
# ==============================================================================
if __name__ == '__main__':
    log.startLogging(sys.stdout)
    wfpiconsole().run()
