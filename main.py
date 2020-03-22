# WeatherFlow PiConsole: Raspberry Pi Python console for WeatherFlow Smart Home
# Weather Station. Copyright (C) 2018-2019 Peter Davis

# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.

# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.

# ==============================================================================
# CREATE OR UPDATE wfpiconsole.ini FILE
# ==============================================================================
# Import required modules
from lib     import config as configFile
from pathlib import Path

# Create or update config file if required
if not Path('wfpiconsole.ini').is_file():
    configFile.create()
else:
    configFile.update()

# ==============================================================================
# INITIALISE KIVY GRAPHICS BACKEND BASED ON CURRENT HARDWARE TYPE
# ==============================================================================
# Import required modules
import configparser
import os

# Load config file
config = configparser.ConfigParser()
config.read('wfpiconsole.ini')

# Initialise Kivy backend based on current hardware
if config['System']['Hardware'] == 'Pi4':
    os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '1'
    os.environ['KIVY_GRAPHICS'] = 'gles'
    os.environ['KIVY_WINDOW']   = 'sdl2'
elif config['System']['Hardware'] == 'Pi3':
    os.environ['KIVY_GL_BACKEND'] = 'gl'

# ==============================================================================
# INITIALISE KIVY TWISTED WEBSOCKET CLIENT
# ==============================================================================
from kivy.support import install_twisted_reactor
install_twisted_reactor()

from twisted.python             import log
from twisted.internet.protocol  import ReconnectingClientFactory
from twisted.protocols.policies import TimeoutMixin
from autobahn.twisted.websocket import WebSocketClientProtocol,WebSocketClientFactory,connectWS

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
from kivy.core.window import Window
from kivy.properties  import DictProperty, NumericProperty, ConfigParserProperty
from kivy.properties  import StringProperty
from kivy.animation   import Animation
from kivy.factory     import Factory
from kivy.metrics     import dp
from kivy.config      import ConfigParser
from kivy.clock       import Clock
from kivy.app         import App

# ==============================================================================
# IMPORT REQUIRED LIBRARY MODULES
# ==============================================================================
from lib import astronomical       as astro
from lib import derivedVariables   as derive
from lib import observationFormat  as observation
from lib import sager              as sagerForecast
from lib import requestAPI
from lib import websocket
from lib import settings
from lib import forecast
from lib import system

# ==============================================================================
# IMPORT REQUIRED SYSTEM MODULES
# ==============================================================================
from twisted.internet import reactor, ssl
from functools        import partial
from datetime         import datetime, date, time, timedelta
from optparse         import OptionParser
import requests
import pytz
import math
import json
import sys

# ==============================================================================
# IMPORT REQUIRED KIVY GRAPHICAL AND SETTINGS MODULES
# ==============================================================================
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.screenmanager  import Screen
from kivy.uix.togglebutton   import ToggleButton
from kivy.uix.scrollview     import ScrollView
from kivy.uix.gridlayout     import GridLayout
from kivy.uix.modalview      import ModalView
from kivy.uix.boxlayout      import BoxLayout
from kivy.uix.settings       import SettingsWithSidebar, SettingOptions
from kivy.uix.settings       import SettingString, SettingSpacer
from kivy.uix.button         import Button
from kivy.uix.widget         import Widget
from kivy.uix.popup          import Popup
from kivy.uix.label          import Label
from kivy.graphics           import opengl_utils

# ==============================================================================
# DEFINE GLOBAL FUNCTIONS AND VARIABLES
# ==============================================================================
# Define global variables
NaN = float('NaN')

# ==============================================================================
# DEFINE 'WeatherFlowPiConsole' APP CLASS
# ==============================================================================
class wfpiconsole(App):

    # Define App class dictionary properties
    Obs = DictProperty      ([('rapidSpd','--'),       ('rapidDir','----'),  ('WindSpd','-----'),
                              ('WindGust','--'),       ('WindDir','---'),    ('AvgWind','--'),
                              ('MaxGust','--'),        ('RainRate','---'),   ('TodayRain','--'),
                              ('YesterdayRain','--'),  ('MonthRain','--'),   ('YearRain','--'),
                              ('Radiation','----'),    ('UVIndex','---'),    ('outTemp','--'),
                              ('outTempMin','---'),    ('outTempMax','---'), ('inTemp','--'),
                              ('inTempMin','---'),     ('inTempMax','---'),  ('Humidity','--'),
                              ('DewPoint','--'),       ('Pres','---'),       ('MaxPres','---'),
                              ('MinPres','---'),       ('PresTrend','----'), ('FeelsLike','----'),
                              ('StrikeDeltaT','-----'),('StrikeDist','--'),  ('StrikeFreq','----'),
                              ('Strikes3hr','-'),      ('StrikesToday','-'), ('StrikesMonth','-'),
                              ('StrikesYear','-')
                             ])
    Astro = DictProperty    ([('Sunrise',['-','-']),   ('Sunset',['-','-']), ('sunEvent',['-','-','-']),
                              ('SunAngle','-'),        ('ValidDate','--'),   ('Moonrise',['-','-']),
                              ('Moonset',['-','-']),   ('NewMoon','--'),     ('FullMoon','--'),
                              ('Phase','---')
                             ])
    MetData = DictProperty  ([('Weather','Building'),   ('Temp','--'),         ('Precip','--'),
                              ('WindSpd','--'),         ('WindDir','--'),      ('Valid','--')
                             ])
    Sager = DictProperty    ([('Forecast','--'),('Issued','--')])
    Version = DictProperty  ([('Latest','-')])

    # Define App class configParser properties
    BarometerMax = ConfigParserProperty('-','System', 'BarometerMax','wfpiconsole')
    BarometerMin = ConfigParserProperty('-','System', 'BarometerMin','wfpiconsole')
    TimeFormat   = ConfigParserProperty('-','Display','TimeFormat',  'wfpiconsole')
    DateFormat   = ConfigParserProperty('-','Display','DateFormat',  'wfpiconsole')
    IndoorTemp   = ConfigParserProperty('-','Display','IndoorTemp',  'wfpiconsole')

    # Define App class numeric properties
    unitChange = NumericProperty(0)

    # BUILD 'WeatherFlowPiConsole' APP CLASS
    # --------------------------------------------------------------------------
    def build(self):

        self.App = self

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

        # Initialise Sunrise and Sunset time, Moonrise and Moonset time, and
        # MetOffice or DarkSky weather forecast
        astro.SunriseSunset(self.Astro,self.config)
        astro.MoonriseMoonset(self.Astro,self.config)
        forecast.Download(self.MetData,self.config)

        # Generate Sager Weathercaster forecast
        sagerForecast.Generate(self.Sager,self.config)

        # Initialise websocket connection
        self.WebsocketConnect()

        # Schedule function calls
        Clock.schedule_interval(self.UpdateMethods,1.0)
        Clock.schedule_interval(partial(astro.sunTransit,self.Astro,self.config),1.0)
        Clock.schedule_interval(partial(astro.moonPhase ,self.Astro,self.config),1.0)
        Clock.schedule_once(lambda dt: system.checkVersion(self.Version,self.config,updateNotif))

    # BUILD 'WeatherFlowPiConsole' APP CLASS SETTINGS
    # --------------------------------------------------------------------------
    def build_settings(self,settingsScreen):

        # Register setting types
        settingsScreen.register_type('ScrollOptions',     SettingScrollOptions)
        settingsScreen.register_type('FixedOptions',      SettingFixedOptions)
        settingsScreen.register_type('ToggleTemperature', SettingToggleTemperature)

        # Add required panels to setting screen. Remove Kivy settings panel
        settingsScreen.add_json_panel('Display',          self.config, data = settings.JSON('Display'))
        settingsScreen.add_json_panel('Primary Panels',   self.config, data = settings.JSON('Primary'))
        settingsScreen.add_json_panel('Secondary Panels', self.config, data = settings.JSON('Secondary'))
        settingsScreen.add_json_panel('Units',            self.config, data = settings.JSON('Units'))
        settingsScreen.add_json_panel('Feels Like',       self.config, data = settings.JSON('FeelsLike'))
        self.use_kivy_settings = False

    # OVERLOAD 'on_config_change' TO MAKE NECESSARY CHANGES TO CONFIG VALUES
    # WHEN REQUIRED
    # --------------------------------------------------------------------------
    def on_config_change(self,config,section,key,value):

        # Update current weather forecast and Sager Weathercaster forecast when
        # temperature or wind speed units are changed
        if section == 'Units' and key in ['Temp','Wind']:
            if self.config['Station']['Country'] == 'GB':
                forecast.ExtractMetOffice(self.MetData,self.config)
            else:
                forecast.ExtractDarkSky(self.MetData,self.config)
            if key == 'Wind' and 'Dial' in self.Sager:
                self.Sager['Dial']['Units'] = value
                self.Sager['Forecast'] = sagerForecast.getForecast(self.Sager['Dial'])

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

        # Update display when any units are changed
        if section == 'Units' or section == 'FeelsLike':
            self.unitChange = 1

        # Update primary and secondary panels displayed on CurrentConditions
        # screen
        start = datetime.now()
        if section in ['PrimaryPanels','SecondaryPanels']:
            for Panel,Type in App.get_running_app().config['PrimaryPanels'].items():
                if Panel == key:
                    self.CurrentConditions.ids[Panel].clear_widgets()
                    self.CurrentConditions.ids[Panel].add_widget(eval(Type + 'Panel')())
                    break

        # Update button layout displayed on CurrentConditions screen
        if section == 'SecondaryPanels':
            ii = 0
            self.CurrentConditions.buttonList = []
            Button = ['Button' + Num for Num in ['One','Two','Three','Four','Five','Six']]
            for Panel, Type in App.get_running_app().config['SecondaryPanels'].items():
                self.CurrentConditions.ids[Button[ii]].clear_widgets()
                if Type and Type != 'None':
                    self.CurrentConditions.ids[Button[ii]].add_widget(eval(Type + 'Button')())
                    self.CurrentConditions.buttonList.append([Button[ii],Panel,Type,'Primary'])
                    ii += 1

            # Change 'None' for secondary panel selection to blank in config
            # file
            if value == 'None':
                self.config.set(section,key,'')
                self.config.write()
                panels = self._app_settings.children[0].content.panels
                for panel in panels.values():
                    if panel.title == 'Secondary Panels':
                        for item in panel.children:
                            if isinstance(item,Factory.SettingOptions):
                                if item.title.replace(' ','') == key:
                                    item.value = ''
                                    break

    # CONNECT TO THE SECURE WEATHERFLOW WEBSOCKET SERVER
    # --------------------------------------------------------------------------
    def WebsocketConnect(self):
        Parser = OptionParser()
        Server = 'wss://ws.weatherflow.com/swd/data?api_key=' + self.config['Keys']['WeatherFlow']
        Parser.add_option("-u", "--url", dest="url", help="Secure WeatherFlow websocket", default=Server)
        (Options, Args) = Parser.parse_args()
        self._factory = WeatherFlowClientFactory(Options.url,self)
        self._factory.protocol = WeatherFlowClientProtocol
        if self._factory.isSecure:
            contextFactory = ssl.ClientContextFactory()
        else:
            contextFactory = None
        connectWS(self._factory, contextFactory)

    # SEND MESSAGE TO THE WEATHERFLOW WEBSOCKET SERVER
    # --------------------------------------------------------------------------
    def WebsocketSendMessage(self,Message):
        Message = Message.encode('utf8')
        proto = self._factory._proto
        if Message and proto:
            proto.sendMessage(Message)

    # DECODE THE WEATHERFLOW WEBSOCKET MESSAGE
    # --------------------------------------------------------------------------
    def WebsocketDecodeMessage(self,Msg):

        # Extract type of received message
        Type = Msg['type']

        # Start listening for device observations and events upon connection of
        # websocket based on device IDs specified in user configuration file
        if Type == 'connection_opened':
            if self.config['Station']['TempestID']:
                self.WebsocketSendMessage('{"type":"listen_start",' +
                                          ' "device_id":' + self.config['Station']['TempestID'] + ',' +
                                          ' "id":"Sky"}')
                self.WebsocketSendMessage('{"type":"listen_rapid_start",' +
                                          ' "device_id":' + self.config['Station']['TempestID'] + ',' +
                                          ' "id":"rapidWind"}')
            elif self.config['Station']['SkyID']:
                self.WebsocketSendMessage('{"type":"listen_start",' +
                                          ' "device_id":' + self.config['Station']['SkyID'] + ',' +
                                          ' "id":"Sky"}')
                self.WebsocketSendMessage('{"type":"listen_rapid_start",' +
                                          ' "device_id":' + self.config['Station']['SkyID'] + ',' +
                                          ' "id":"rapidWind"}')
            if self.config['Station']['OutAirID']:
                self.WebsocketSendMessage('{"type":"listen_start",' +
                                          ' "device_id":' + self.config['Station']['OutAirID'] + ',' +
                                          ' "id":"OutdoorAir"}')
            if self.config['Station']['InAirID']:
                self.WebsocketSendMessage('{"type":"listen_start",' +
                                          ' "device_id":' + self.config['Station']['InAirID'] + ',' +
                                          ' "id":"IndoorAir"}')

        # Extract observations from obs_sky websocket message
        elif Type == 'obs_st':
            websocket.Tempest(Msg,self)

        # Extract observations from obs_sky websocket message
        elif Type == 'obs_sky':
            websocket.Sky(Msg,self)

        # Extract observations from obs_air websocket message based on device
        # ID
        elif Type == 'obs_air':
            if self.config['Station']['InAirID']:
                if Msg['device_id'] == int(self.config['Station']['InAirID']):
                    websocket.indoorAir(Msg,self)
            if self.config['Station']['OutAirID']:
                if Msg['device_id'] == int(self.config['Station']['OutAirID']):
                    websocket.outdoorAir(Msg,self)

        # Extract observations from rapid_wind websocket message
        elif Type == 'rapid_wind':
            websocket.rapidWind(Msg,self)

        # Extract observations from evt_strike websocket message and open
        # secondary lightning panel to show strike has been detected if required
        elif Type == 'evt_strike':

            # Extract observations from evt_strike websocket message
            websocket.evtStrike(Msg,self)

            # Open secondary lightning panel to show strike has been detected
            if self.config['Display']['LightningPanel'] == '1':
                for ii,Button in enumerate(self.CurrentConditions.buttonList):
                    if "Lightning" in Button[2]:
                        newButton = self.config[Button[3] + 'Panels'][Button[1]]
                        self.CurrentConditions.ids[Button[1]].clear_widgets()
                        self.CurrentConditions.ids[Button[1]].add_widget(eval(Button[2] + 'Panel')())
                        self.CurrentConditions.ids[Button[0]].clear_widgets()
                        self.CurrentConditions.ids[Button[0]].add_widget(eval(newButton + 'Button')())
                        self.CurrentConditions.buttonList[ii] = [Button[0],Button[1],newButton,'Secondary']
                        break

            # If lightning panel is open, animate lightning bolt icon
            if hasattr(self,'LightningPanel'):
                self.LightningPanel.LightningBoltAnim()

    # UPDATE 'WeatherFlowPiConsole' APP CLASS METHODS AT REQUIRED INTERVALS
    # --------------------------------------------------------------------------
    def UpdateMethods(self,dt):

        # Get current time in station timezone
        Tz = pytz.timezone(self.config['Station']['Timezone'])
        Now = datetime.now(pytz.utc).astimezone(Tz)
        Now = Now.replace(microsecond=0)

        # At 5 minutes past each hour, download a new forecast for the Station
        # location
        if (Now.minute,Now.second) == (5,0):
            forecast.Download(self.MetData,self.config)

        # At the top of each hour update the on-screen forecast for the Station
        # location
        if Now.hour > self.MetData['Time'].hour or Now.date() > self.MetData['Time'].date():
            if self.config['Station']['Country'] == 'GB':
                forecast.ExtractMetOffice(self.MetData,self.config)
            else:
                forecast.ExtractDarkSky(self.MetData,self.config)
            self.MetData['Time'] = Now

        # Once sunset has passed, calculate new sunrise/sunset times
        if Now > self.Astro['Sunset'][0]:
            self.Astro = astro.SunriseSunset(self.Astro,self.config)

        # Once moonset has passed, calculate new moonrise/moonset times
        if Now > self.Astro['Moonset'][0]:
            self.Astro = astro.MoonriseMoonset(self.Astro,self.config)

        # At midnight, update Sunset, Sunrise, Moonrise and Moonset Kivy Labels
        if Now.time() == time(0,0,0):
            self.Astro = astro.Format(self.Astro,self.config,"Sun")
            self.Astro = astro.Format(self.Astro,self.config,"Moon")

        # Update display if units have been changed
        if self.unitChange == 1:
            if self.config['Station']['TempestID']:
                websocket.Tempest(self.Obs['TempestMsg'],self)
                websocket.rapidWind(self.Obs['RapidMsg'],self)
            elif self.config['Station']['SkyID']:
                websocket.Sky(self.Obs['SkyMsg'],self)
                websocket.rapidWind(self.Obs['RapidMsg'],self)
            if self.config['Station']['OutAirID']:
                websocket.outdoorAir(self.Obs['outAirMsg'],self)
            if self.config['Station']['InAirID']:
                websocket.indoorAir(self.Obs['inAirMsg'],self)
            self.unitChange = 0

# ==============================================================================
# CurrentConditions SCREEN CLASS
# ==============================================================================
class CurrentConditions(Screen):

    # INITIALISE 'CurrentConditions' SCREEN CLASS
    # --------------------------------------------------------------------------
    def __init__(self,**kwargs):
        super(CurrentConditions,self).__init__(**kwargs)
        Clock.schedule_once(self.AddPanels)
        App.get_running_app().CurrentConditions = self

    # ADD PANELS TO CURRENT CONDITIONS SCREEN ACCORDING TO USER DEFINED LAYOUT
    # --------------------------------------------------------------------------
    def AddPanels(self,dt):

        # Add primary panels to CurrentConditions screen
        for Panel, Type in App.get_running_app().config['PrimaryPanels'].items():
            self.manager.ids.CurrentConditions.ids[Panel].add_widget(eval(Type + 'Panel')())

        # Add secondary panel buttons to CurrentConditions screen
        self.buttonList = []
        ii = 0
        Button = ['Button' + Num for Num in ['One','Two','Three','Four','Five','Six']]
        for Panel, Type in App.get_running_app().config['SecondaryPanels'].items():
            if Type:
                self.manager.ids.CurrentConditions.ids[Button[ii]].add_widget(eval(Type + 'Button')())
                self.buttonList.append([Button[ii],Panel,Type,'Primary'])
                ii += 1

    # SWITCH BETWEEN DIFFERENT PANELS ON CURRENT CONDITIONS SCREEN
    # --------------------------------------------------------------------------
    def SwitchPanel(self,Instance):

        # Determine ID of button that has been pressed
        for id,Object in App.get_running_app().CurrentConditions.ids.items():
            if Object == Instance.parent.parent:
                break

        # Extract entry in buttonList that correponds to the button that has
        # been pressed
        for ii,Button in enumerate(App.get_running_app().CurrentConditions.buttonList):
            if Button[0] == id:
                break

        # Determine new button type
        newButton = App.get_running_app().config[Button[3] + 'Panels'][Button[1]]

        # Switch panel
        App.get_running_app().CurrentConditions.ids[Button[1]].clear_widgets()
        App.get_running_app().CurrentConditions.ids[Button[1]].add_widget(eval(Button[2] + 'Panel')())
        App.get_running_app().CurrentConditions.ids[Button[0]].clear_widgets()
        App.get_running_app().CurrentConditions.ids[Button[0]].add_widget(eval(newButton + 'Button')())

        # Update button list
        if Button[3] == 'Primary':
            App.get_running_app().CurrentConditions.buttonList[ii] = [Button[0],Button[1],newButton,'Secondary']
        elif Button[3] == 'Secondary':
            App.get_running_app().CurrentConditions.buttonList[ii] = [Button[0],Button[1],newButton,'Primary']

# ==============================================================================
# ForecastPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class ForecastPanel(RelativeLayout):
    pass

class ForecastButton(RelativeLayout):
    pass

# ==============================================================================
# SagerPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class SagerPanel(RelativeLayout):
    pass

class SagerButton(RelativeLayout):
    pass

# ==============================================================================
# TemperaturePanel RELATIVE LAYOUT CLASS
# ==============================================================================
class TemperaturePanel(RelativeLayout):
    pass

class TemperatureButton(RelativeLayout):
    pass

# ==============================================================================
# WindSpeedPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class WindSpeedPanel(RelativeLayout):

    # Define WindSpeedPanel class numeric properties
    WindRoseDir = NumericProperty(0)

    # INITIALISE 'WindSpeedPanel' RELATIVE LAYOUT CLASS
    # --------------------------------------------------------------------------
    def __init__(self,**kwargs):
        super(WindSpeedPanel,self).__init__(**kwargs)
        App.get_running_app().WindSpeedPanel = self

    # ANIMATE WIND ROSE DIRECTION ARROW
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

class WindSpeedButton(RelativeLayout):
    pass

# ==============================================================================
# SunriseSunsetPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class SunriseSunsetPanel(RelativeLayout):
    pass

class SunriseSunsetButton(RelativeLayout):
    pass

# ==============================================================================
# MoonPhasePanel RELATIVE LAYOUT CLASS
# ==============================================================================
class MoonPhasePanel(RelativeLayout):
    pass

class MoonPhaseButton(RelativeLayout):
    pass

# ==============================================================================
# RainfallPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class RainfallPanel(RelativeLayout):

    # Define RainfallPanel class properties
    realtimeClock = StringProperty('--')
    xRainAnim     = NumericProperty(0)
    yRainAnim     = NumericProperty(-1)

    # INITIALISE 'RainfallPanel' RELATIVE LAYOUT CLASS
    # --------------------------------------------------------------------------
    def __init__(self,**kwargs):
        super(RainfallPanel,self).__init__(**kwargs)
        Clock.schedule_once(self.Clock)
        App.get_running_app().RainfallPanel = self

    # ANIMATE RAIN RATE ICON
    # --------------------------------------------------------------------------
    def RainRateAnimation(self):

        # Get current rain rate and convert to float
        RainRate = float(App.get_running_app().Obs['RainRate'][3])

        # Define required animation variables
        x0 = -1
        xt = 0
        t = 50

        # Set RainRate level y position
        if RainRate == 0:
            self.yRainAnim = x0
        elif RainRate < 50.0:
            A = (xt-x0)/t**0.5 * RainRate**0.5 + x0
            B = (xt-x0)/t**0.3 * RainRate**0.3 + x0
            C = (1 + math.tanh(RainRate-3))/2
            self.yRainAnim = (A + C * (B-A))
        else:
            self.yRainAnim = xt

        # Animate RainRate level x position
        if RainRate == 0:
            if hasattr(self,'Anim'):
                self.Anim.stop(self)
                delattr(self,'Anim')
        else:
            if not hasattr(self,'Anim'):
                self.Anim = Animation(xRainAnim=-0.875,duration=12)
                self.Anim += Animation(xRainAnim=-0.875,duration=12)
                self.Anim.repeat = True
                self.Anim.start(self)

    # Loop RainRate animation in the x direction
    def on_xRainAnim(self,item,xRainAnim):
        if round(xRainAnim,3) == -0.875:
            item.xRainAnim = 0

    # DEFINE DATE AND TIME IN STATION TIMEZONE
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

        # Format realtimeClock
        self.realtimeClock = Now.strftime(DateFormat + '\n' + TimeFormat)
        Clock.schedule_once(self.Clock,1)

class RainfallButton(RelativeLayout):
    pass

# ==============================================================================
# LightningPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class LightningPanel(RelativeLayout):

    # Define LightningPanel class properties
    xLightningBolt = NumericProperty(0)

    # INITIALISE 'LightningPanel' RELATIVE LAYOUT CLASS
    # --------------------------------------------------------------------------
    def __init__(self,**kwargs):
        super(LightningPanel,self).__init__(**kwargs)
        App.get_running_app().LightningPanel = self

    # ANIMATE LIGHTNING BOLT ICON WHEN STRIKE IS DETECTED
    # --------------------------------------------------------------------------
    def LightningBoltAnim(self):
        Anim = Animation(xLightningBolt=5,t='out_quad',d=0.02) + Animation(xLightningBolt=0,t='out_elastic',d=0.5)
        Anim.start(self)

class LightningButton(RelativeLayout):
    pass

# ==============================================================================
# BarometerPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class BarometerPanel(RelativeLayout):
    pass

class BarometerButton(RelativeLayout):
    pass

# ==============================================================================
# Credits AND UpdateNotification POPUP CLASSES
# ==============================================================================
class Credits(ModalView):
    pass

class updateNotif(ModalView):
    pass

# ==============================================================================
# SettingScrollOptions SETTINGS CLASS
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
# SettingFixedOptions SETTINGS CLASS
# ==============================================================================
class SettingFixedOptions(SettingOptions):

    def _create_popup(self, instance):

        # Create the popup
        content     = BoxLayout(orientation='vertical', spacing='5dp')
        self.popup  = Popup(content=content, title=self.title, size_hint=(0.25, None),
                            auto_dismiss=False, separator_color=[1,1,1,1], height=134+min(len(self.options),4) * 63)

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
# SettingToggleTemperature SETTINGS CLASS
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
        btn.bind(on_press=self._minus_value)
        btnlayout.add_widget(btn)
        btn = Button(text='+')
        btn.bind(on_press=self._plus_value)
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

    def _minus_value(self,instance):
        if '[sup]o[/sup]C' in self.Label.text:
            Units = '[sup]o[/sup]C'
        else:
            Units = '[sup]o[/sup]F'
        Value = int(self.Label.text.replace(Units,'')) - 1
        self.Label.text = str(Value) + Units

    def _plus_value(self,instance):
        if '[sup]o[/sup]C' in self.Label.text:
            Units = '[sup]o[/sup]C'
        else:
            Units = '[sup]o[/sup]F'
        Value = int(self.Label.text.replace(Units,'')) + 1
        self.Label.text = str(Value) + Units

# ==============================================================================
# RUN APP
# ==============================================================================
if __name__ == '__main__':
    log.startLogging(sys.stdout)
    wfpiconsole().run()
