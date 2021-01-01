# WeatherFlow PiConsole: Raspberry Pi Python console for WeatherFlow Tempest and
# Smart Home Weather stations.
# Copyright (C) 2018-2021 Peter Davis

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
# DEFINE GOBAL VARIABLES
# =============================================================================
SHUTDOWN = 0
REBOOT = 0

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
# INITIALISE KIVY GRAPHICS WINDOW BASED ON CURRENT HARDWARE TYPE
# ==============================================================================
# Import required modules
import configparser
import os

# Load wfpiconsole.ini config file
config = configparser.ConfigParser()
config.read('wfpiconsole.ini')

# Initialise Kivy backend based on current hardware
if config['System']['Hardware'] in ['Pi4','Linux']:
    os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '1'
    os.environ['KIVY_GRAPHICS'] = 'gles'
    os.environ['KIVY_WINDOW']   = 'sdl2'
elif config['System']['Hardware'] in ['PiB','Pi3']:
    os.environ['KIVY_GL_BACKEND'] = 'gl'

# ==============================================================================
# INITIALISE KIVY WINDOW PROPERTIES BASED ON OPTIONS SET IN wfpiconsole.ini
# ==============================================================================
# Import required modules
from kivy.config import Config as kivyconfig

# Generate default wfpiconsole Kivy config file. Config file is always
# regenerated to ensure changes to the default file are always copied across
defaultconfig = configparser.ConfigParser()
defaultconfig.read(os.path.expanduser('~/.kivy/') + 'config.ini')
with open(os.path.expanduser('~/.kivy/') + 'config_wfpiconsole.ini','w') as cfg:
    defaultconfig.write(cfg)

# Load wfpiconsole Kivy configuration file
kivyconfig.read(os.path.expanduser('~/.kivy/') + 'config_wfpiconsole.ini')

# Set Kivy window properties
if config['System']['Hardware'] in ['Pi4', 'Linux', 'Other']:
    kivyconfig.set('graphics', 'minimum_width',  '800')
    kivyconfig.set('graphics', 'minimum_height', '480')
    if int(config['Display']['Fullscreen']):
        kivyconfig.set('graphics', 'fullscreen', 'auto')
    else:
        kivyconfig.set('graphics', 'fullscreen', '0')
        kivyconfig.set('graphics', 'width',  config['Display']['Width'])
        kivyconfig.set('graphics', 'height', config['Display']['Height'])
    if not int(config['Display']['Border']):
        kivyconfig.set('graphics', 'borderless', '1')
    else:
        kivyconfig.set('graphics', 'borderless', '0')

# ==============================================================================
# INITIALISE MOUSE SUPPORT IF OPTION SET in wfpiconsole.ini
# ==============================================================================
# Enable mouse support on Raspberry Pi 3 if not already set
if config['System']['Hardware'] in ['PiB','Pi3']:
    if not config.has_option('modules','cursor'):
        kivyconfig.set('modules','cursor','1')

# Initialise mouse support if required
if not int(config['Display']['Cursor']):
    kivyconfig.set('graphics', 'show_cursor', '0')
else:
    kivyconfig.set('graphics', 'show_cursor', '1')

# Save wfpiconsole Kivy configuration file
kivyconfig.write()

# ==============================================================================
# INITIALISE KIVY TWISTED WEBSOCKET CLIENT
# ==============================================================================
from kivy.support import install_twisted_reactor
install_twisted_reactor()

from twisted.python             import log
from twisted.internet.protocol  import ReconnectingClientFactory
from twisted.protocols.policies import TimeoutMixin
from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory, connectWS

# Specifies behaviour of Websocket Client
class WeatherFlowClientProtocol(WebSocketClientProtocol,TimeoutMixin):

    def onOpen(self):

        # Reset websocket reconnection delay and start timeout counter
        print("Websocket connection open")
        self.factory._proto = self
        self.factory.resetDelay()
        self.setTimeout(300)

        # Set flags for required API calls after Websocket connection
        self.factory._app.flagAPI = [1,1,1,1]

    def onMessage(self,payload,isBinary):

        # Decode message and pass to Websocket functions for processing
        Message = json.loads(payload.decode('utf8'))
        self.factory._app.WebsocketDecodeMessage(Message)

        # Reset websocket timeout
        self.resetTimeout()

    def timeoutConnection(self):
        print("Websocket connection timeout")
        self.transport.abortConnection()

    def onClose(self,wasClean,code,reason):
        print("Websocket connection closed")
        self.factory._proto = None

# Specifies Websocket Factory
class WeatherFlowClientFactory(WebSocketClientFactory,ReconnectingClientFactory):

    # Define protocol and reconnection properties
    protocol     = WeatherFlowClientProtocol
    maxDelay     = 60
    factor       = 5
    jitter       = 0

    def clientConnectionFailed(self,connector,reason):
        print('Websocket connection retrying')
        self.retry(connector)

    def clientConnectionLost(self,connector,reason):
        print('Websocket connection retrying')
        self.retry(connector)

    def __init__(self, url, app):
        WebSocketClientFactory.__init__(self,url)
        self._app         = app
        self._proto       = None

# ==============================================================================
# IMPORT REQUIRED CORE KIVY MODULES
# ==============================================================================
from kivy.core.window import Window
from kivy.properties  import DictProperty, NumericProperty, ConfigParserProperty, ObjectProperty
from kivy.properties  import StringProperty
from kivy.animation   import Animation
from kivy.factory     import Factory
from kivy.metrics     import dp
from kivy.config      import ConfigParser
from kivy.clock       import Clock, mainthread
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
from lib import station
from lib import system

# ==============================================================================
# IMPORT REQUIRED SYSTEM MODULES
# ==============================================================================
from twisted.internet import reactor, ssl
from functools        import partial
from threading        import Thread
from datetime         import datetime, date, time, timedelta
import subprocess
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
from kivy.uix.tabbedpanel    import TabbedPanel
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

# ==============================================================================
# DEFINE 'WeatherFlowPiConsole' APP CLASS
# ==============================================================================
class wfpiconsole(App):

    # Define App class observation dictionary properties
    Obs     = DictProperty  ([('rapidSpd','--'),       ('rapidDir','----'),    ('rapidShift','-'),
                              ('WindSpd','-----'),     ('WindGust','--'),      ('WindDir','---'),
                              ('AvgWind','--'),        ('MaxGust','--'),       ('RainRate','---'),
                              ('TodayRain','--'),      ('YesterdayRain','--'), ('MonthRain','--'),
                              ('YearRain','--'),       ('Radiation','----'),   ('UVIndex','----'),
                              ('peakSun','-----'),     ('outTemp','--'),       ('outTempMin','---'),
                              ('outTempMax','---'),    ('inTemp','--'),        ('inTempMin','---'),
                              ('inTempMax','---'),     ('Humidity','--'),      ('DewPoint','--'),
                              ('Pres','---'),          ('MaxPres','---'),      ('MinPres','---'),
                              ('PresTrend','----'),    ('FeelsLike','----'),   ('StrikeDeltaT','-----'),
                              ('StrikeDist','--'),     ('StrikeFreq','----'),  ('Strikes3hr','-'),
                              ('StrikesToday','-'),    ('StrikesMonth','-'),   ('StrikesYear','-')
                             ])
    Astro   = DictProperty  ([('Sunrise',['-','-',0]), ('Sunset',['-','-',0]), ('Dawn',['-','-',0]),
                              ('Dusk',['-','-',0]),    ('sunEvent','----'),    ('sunIcon',['-',0,0]),
                              ('Moonrise',['-','-']),  ('Moonset',['-','-']),  ('NewMoon','--'),
                              ('FullMoon','--'),       ('Phase','---'),        ('Reformat','-'),
                             ])
    MetData = DictProperty  ([('Valid','--'),          ('Temp','--'),          ('highTemp','--'),
                              ('lowTemp','--'),        ('WindSpd','--'),       ('WindGust','--'),
                              ('WindDir','--'),        ('PrecipPercnt','--'),  ('PrecipDay','--'),
                              ('PrecipAmount','--'),   ('PrecipType','--'),    ('Conditions','-'),
                              ('Icon','--'),           ('Status','--')
                             ])
    Sager   = DictProperty  ([('Forecast','--'),       ('Issued','--')])
    System  = DictProperty  ([('Time','-'),            ('Date','-')])
    Version = DictProperty  ([('Latest','-')])

    # Define App class configParser properties
    BarometerMax = ConfigParserProperty('-','System', 'BarometerMax','wfpiconsole')
    BarometerMin = ConfigParserProperty('-','System', 'BarometerMin','wfpiconsole')
    IndoorTemp   = ConfigParserProperty('-','Display','IndoorTemp',  'wfpiconsole')

    # Define display properties
    scaleFactor = NumericProperty(1)
    scaleSuffix = StringProperty('_lR')

    # BUILD 'WeatherFlowPiConsole' APP CLASS
    # --------------------------------------------------------------------------
    def build(self):

        # Load user configuration from wfpiconsole.ini and define Settings panel
        # type
        self.config = ConfigParser(allow_no_value=True,name='wfpiconsole')
        self.config.optionxform = str
        self.config.read('wfpiconsole.ini')
        self.settings_cls = SettingsWithSidebar

        # Calculate initial ScaleFactor and bind self.setScaleFactor to Window
        # on_resize
        self.window = Window
        self.setScaleFactor(self.window, self.window.width, self.window.height)
        self.window.bind(on_resize=self.setScaleFactor)

        # Initialise real time clock
        Clock.schedule_interval(partial(system.realtimeClock,self.System,self.config),1.0)

        # Initialise Sunrise, Sunset, Moonrise and Moonset times
        astro.SunriseSunset(self.Astro,self.config)
        astro.MoonriseMoonset(self.Astro,self.config)

        # Fetch WeatherFlow weather forecast
        Clock.schedule_once(partial(forecast.Download,self.MetData,self.config))

        # Generate Sager Weathercaster forecast
        Thread(target=sagerForecast.Generate, args=(self.Sager,self.config), name="Sager", daemon=True).start()

        # Initialise websocket connection
        self.WebsocketConnect()

        # Check for latest version
        Clock.schedule_once(partial(system.checkVersion,self.Version,self.config,updateNotif))

        # Initialise Station class, and set device status to be checked every
        # second
        self.Station = Station()
        Clock.schedule_interval(self.Station.getDeviceStatus,1.0)

        # Schedule sunTransit and moonPhase functions to be called each second
        Clock.schedule_interval(partial(astro.sunTransit,self.Astro,self.config),1.0)
        Clock.schedule_interval(partial(astro.moonPhase ,self.Astro,self.config),1.0)

    # SET DISPLAY SCALE FACTOR BASED ON SCREEN DIMENSIONS
    # --------------------------------------------------------------------------
    def setScaleFactor(self,instance,x,y):
        self.scaleFactor = max(min(x/800, y/480), 1)
        if self.scaleFactor > 1:
            self.scaleSuffix = '_hR'
        else:
            self.scaleSuffix = '_lR'

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
        settingsScreen.add_json_panel('Station IDs',      self.config, data = settings.JSON('Station'))
        self.use_kivy_settings = False

    # OVERLOAD 'on_config_change' TO MAKE NECESSARY CHANGES TO CONFIG VALUES
    # WHEN REQUIRED
    # --------------------------------------------------------------------------
    def on_config_change(self,config,section,key,value):

        # Update current weather forecast and Sager Weathercaster forecast when
        # temperature or wind speed units are changed
        if section == 'Units' and key in ['Temp','Wind']:
            forecast.Download(self.MetData, self.config, None)
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

        # Update primary and secondary panels displayed on CurrentConditions
        # screen
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
            buttonList = ['Button' + Num for Num in ['One','Two','Three','Four','Five','Six']]
            for Button in buttonList:
                self.CurrentConditions.ids[Button].clear_widgets()
            for Panel, Type in App.get_running_app().config['SecondaryPanels'].items():
                if Type and Type != 'None':
                    self.CurrentConditions.ids[buttonList[ii]].add_widget(eval(Type + 'Button')())
                    self.CurrentConditions.buttonList.append([buttonList[ii],Panel,Type,'Primary'])
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
        Server = 'wss://ws.weatherflow.com/swd/data?api_key=' + self.config['Keys']['WeatherFlow']
        self._factory = WeatherFlowClientFactory(Server,self)
        reactor.connectSSL('ws.weatherflow.com',443,self._factory,ssl.ClientContextFactory(),20)

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
        if 'type' in Msg:
            Type = Msg['type']
        else:
            Type = 'Unknown'

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

        # Extract observations from obs_st websocket message
        elif Type == 'obs_st':
            Thread(target=websocket.Tempest, args=(Msg,self), name="Tempest", daemon=True).start()

        # Extract observations from obs_sky websocket message
        elif Type == 'obs_sky':
            Thread(target=websocket.Sky, args=(Msg,self), name="Sky", daemon=True).start()

        # Extract observations from obs_air websocket message based on device
        # ID
        elif Type == 'obs_air':
            if self.config['Station']['InAirID'] and Msg['device_id'] == int(self.config['Station']['InAirID']):
                Thread(target=websocket.indoorAir, args=(Msg,self),  name="indoorAir",  daemon=True).start()
            if self.config['Station']['OutAirID'] and Msg['device_id'] == int(self.config['Station']['OutAirID']):
                Thread(target=websocket.outdoorAir, args=(Msg,self), name="outdoorAir", daemon=True).start()

        # Extract observations from rapid_wind websocket message
        elif Type == 'rapid_wind':
            websocket.rapidWind(Msg,self)

        # Extract observations from evt_strike websocket message
        elif Type == 'evt_strike':
            websocket.evtStrike(Msg,self)

        # Unknown message type, print message to terminal and restart Websocket
        # connection
        elif Type == 'Unknown':
            print('Unknown message type: ' + json.dumps(Msg))

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
        buttonList = ['Button' + Num for Num in ['One','Two','Three','Four','Five','Six']]
        for Panel, Type in App.get_running_app().config['SecondaryPanels'].items():
            if Type:
                self.manager.ids.CurrentConditions.ids[buttonList[ii]].add_widget(eval(Type + 'Button')())
                self.buttonList.append([buttonList[ii],Panel,Type,'Primary'])
                ii += 1

    # SWITCH BETWEEN DIFFERENT PANELS ON CURRENT CONDITIONS SCREEN
    # --------------------------------------------------------------------------
    def SwitchPanel(self,Instance,overideButton=None):

        # Determine ID of button that has been pressed
        for id,Object in App.get_running_app().CurrentConditions.ids.items():
            if Instance:
                if Object == Instance.parent.parent:
                    break
            else:
                if Object == overideButton:
                    break

        # Extract entry in buttonList that correponds to the button that has
        # been pressed
        for ii,Button in enumerate(App.get_running_app().CurrentConditions.buttonList):
            if Button[0] == id:
                break

        # Extract panel object the corresponds to the button that has been
        # pressed and determine new button type required
        Panel = App.get_running_app().CurrentConditions.ids[Button[1]].children
        newButton = App.get_running_app().config[Button[3] + 'Panels'][Button[1]]

        # Destroy reference to old panel class attribute
        if hasattr(App.get_running_app(),newButton + 'Panel'):
            if len(getattr(App.get_running_app(), newButton + 'Panel')) > 1:
                try:
                    getattr(App.get_running_app(), newButton + 'Panel').remove(Panel[0])
                except ValueError:
                    log.msg('Unable to remove panel reference from wfpiconsole class')
            else:
                delattr(App.get_running_app(), newButton + 'Panel')

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

    # Initialise 'ForecastPanel' relative layout class
    def __init__(self,**kwargs):
        super(ForecastPanel,self).__init__(**kwargs)
        if not hasattr(App.get_running_app(),'ForecastPanel'):
            App.get_running_app().ForecastPanel = []
            App.get_running_app().ForecastPanel.append(self)
        else:
            App.get_running_app().ForecastPanel.append(self)

class ForecastButton(RelativeLayout):
    pass

# ==============================================================================
# SagerPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class SagerPanel(RelativeLayout):

    # Initialise 'SagerPanel' relative layout class
    def __init__(self,**kwargs):
        super(SagerPanel,self).__init__(**kwargs)
        if not hasattr(App.get_running_app(),'SagerPanel'):
            App.get_running_app().SagerPanel = []
            App.get_running_app().SagerPanel.append(self)
        else:
            App.get_running_app().SagerPanel.append(self)

class SagerButton(RelativeLayout):
    pass

# ==============================================================================
# TemperaturePanel RELATIVE LAYOUT CLASS
# ==============================================================================
class TemperaturePanel(RelativeLayout):

    # Define TemperaturePanel class properties
    feelsLikeIcon = StringProperty('-')

    # Initialise 'TemperaturePanel' relative layout class
    def __init__(self,**kwargs):
        super(TemperaturePanel,self).__init__(**kwargs)
        if not hasattr(App.get_running_app(),'TemperaturePanel'):
            App.get_running_app().TemperaturePanel = []
            App.get_running_app().TemperaturePanel.append(self)
        else:
            App.get_running_app().TemperaturePanel.append(self)
        self.setFeelsLikeIcon()

    # Set "Feels Like" icon
    @mainthread
    def setFeelsLikeIcon(self):
        self.feelsLikeIcon = App.get_running_app().Obs['FeelsLike'][3]

class TemperatureButton(RelativeLayout):
    pass

# ==============================================================================
# WindSpeedPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class WindSpeedPanel(RelativeLayout):

    # Define WindSpeedPanel class properties
    rapidWindDir = NumericProperty(0)
    windDirIcon  = StringProperty('-')
    windSpdIcon  = StringProperty('-')

    # Initialise 'WindSpeedPanel' relative layout class
    def __init__(self,**kwargs):
        super(WindSpeedPanel,self).__init__(**kwargs)
        if not hasattr(App.get_running_app(),'WindSpeedPanel'):
            App.get_running_app().WindSpeedPanel = []
            App.get_running_app().WindSpeedPanel.append(self)
        else:
            App.get_running_app().WindSpeedPanel.append(self)
        if App.get_running_app().Obs['rapidDir'][0] != '-':
            self.rapidWindDir = App.get_running_app().Obs['rapidDir'][0]
        self.setWindIcons()

    # Animate rapid wind rose
    def animateWindRose(self):

        # Get current wind direction, old wind direction and change in wind
        # direction over last Rapid-Wind period
        windShift = App.get_running_app().Obs['rapidShift']
        newDirec = App.get_running_app().Obs['RapidMsg']['ob'][2]
        oldDirec = newDirec - windShift

        # Animate Wind Rose at constant speed between old and new Rapid-Wind
        # wind direction
        if windShift >= -180 and windShift <= 180:
            Anim = Animation(rapidWindDir=newDirec,duration=2*abs(windShift)/360)
            Anim.start(self)
        elif windShift > 180:
            Anim = Animation(rapidWindDir=0.1,duration=2*oldDirec/360) + Animation(rapidWindDir=newDirec,duration=2*(360-newDirec)/360)
            Anim.start(self)
        elif windShift < -180:
            Anim = Animation(rapidWindDir=359.9,duration=2*(360-oldDirec)/360) + Animation(rapidWindDir=newDirec,duration=2*newDirec/360)
            Anim.start(self)

    # Fix Wind Rose angle at 0/360 degree discontinuity
    def on_rapidWindDir(self,item,rapidWindDir):
        if rapidWindDir == 0.1:
            item.rapidWindDir = 360
        if rapidWindDir == 359.9:
            item.rapidWindDir = 0

    # Set mean windspeed and direction icons
    @mainthread
    def setWindIcons(self):
        self.windDirIcon = App.get_running_app().Obs['WindDir'][2]
        self.windSpdIcon = App.get_running_app().Obs['WindSpd'][3]

class WindSpeedButton(RelativeLayout):
    pass

# ==============================================================================
# SunriseSunsetPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class SunriseSunsetPanel(RelativeLayout):

    # Define SunriseSunsetPanel class properties
    uvBackground = StringProperty('-')

    # Initialise 'SunriseSunsetPanel' relative layout class
    def __init__(self,**kwargs):
        super(SunriseSunsetPanel,self).__init__(**kwargs)
        if not hasattr(App.get_running_app(),'SunriseSunsetPanel'):
            App.get_running_app().SunriseSunsetPanel = []
            App.get_running_app().SunriseSunsetPanel.append(self)
        else:
            App.get_running_app().SunriseSunsetPanel.append(self)
        self.setUVBackground()

    # Set current UV index backgroud
    @mainthread
    def setUVBackground(self):
        self.uvBackground = App.get_running_app().Obs['UVIndex'][3]

class SunriseSunsetButton(RelativeLayout):
    pass

# ==============================================================================
# MoonPhasePanel RELATIVE LAYOUT CLASS
# ==============================================================================
class MoonPhasePanel(RelativeLayout):

    # Initialise 'MoonPhasePanel' relative layout class
    def __init__(self,**kwargs):
        super(MoonPhasePanel,self).__init__(**kwargs)
        if not hasattr(App.get_running_app(),'MoonPhasePanel'):
            App.get_running_app().MoonPhasePanel = []
            App.get_running_app().MoonPhasePanel.append(self)
        else:
            App.get_running_app().MoonPhasePanel.append(self)

class MoonPhaseButton(RelativeLayout):
    pass

# ==============================================================================
# RainfallPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class RainfallPanel(RelativeLayout):

    # Define RainfallPanel class properties
    rainRatePosX  = NumericProperty(+0)
    rainRatePosY  = NumericProperty(-1)

    # Initialise 'RainfallPanel' relative layout class
    def __init__(self,**kwargs):
        super(RainfallPanel,self).__init__(**kwargs)
        if not hasattr(App.get_running_app(),'RainfallPanel'):
            App.get_running_app().RainfallPanel = []
            App.get_running_app().RainfallPanel.append(self)
        else:
            App.get_running_app().RainfallPanel.append(self)
        self.animateRainRate()

    # Animate rain rate level
    @mainthread
    def animateRainRate(self):

        # Get current rain rate and convert to float
        if App.get_running_app().Obs['RainRate'][0] == '-':
            return
        RainRate = float(App.get_running_app().Obs['RainRate'][3])

        # Define required animation variables
        x0 = -1.00
        xt = -0.01
        t = 50

        # Set RainRate level y position
        if RainRate == 0:
            self.rainRatePosY = x0
        elif RainRate < 50.0:
            A = (xt-x0)/t**0.5 * RainRate**0.5 + x0
            B = (xt-x0)/t**0.3 * RainRate**0.3 + x0
            C = (1 + math.tanh(RainRate-3))/2
            self.rainRatePosY = (A + C * (B-A))
        else:
            self.rainRatePosY = xt

        # Animate RainRate level x position
        if RainRate == 0:
            if hasattr(self,'Anim'):
                self.Anim.stop(self)
                delattr(self,'Anim')
        else:
            if not hasattr(self,'Anim'):
                self.Anim  = Animation(rainRatePosX=-0.875,duration=12)
                self.Anim += Animation(rainRatePosX=-0.875,duration=12)
                self.Anim.repeat = True
                self.Anim.start(self)

    # Loop RainRate animation in the x direction
    def on_rainRatePosX(self,item,rainRatePosX):
        if round(rainRatePosX,3) == -0.875:
            item.rainRatePosX = 0

class RainfallButton(RelativeLayout):
    pass

# ==============================================================================
# LightningPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class LightningPanel(RelativeLayout):

    # Define LightningPanel class properties
    lightningBoltPosX = NumericProperty(0)
    lightningBoltIcon = StringProperty('lightningBolt')

    # Initialise 'LightningPanel' relative layout class
    def __init__(self,**kwargs):
        super(LightningPanel,self).__init__(**kwargs)
        if not hasattr(App.get_running_app(),'LightningPanel'):
            App.get_running_app().LightningPanel = []
            App.get_running_app().LightningPanel.append(self)
        else:
            App.get_running_app().LightningPanel.append(self)
        self.setLightningBoltIcon()

    # Set lightning bolt icon
    @mainthread
    def setLightningBoltIcon(self):
        if App.get_running_app().Obs['StrikeDeltaT'][4] != '-':
            if App.get_running_app().Obs['StrikeDeltaT'][4] < 360:
                self.lightningBoltIcon = 'lightningBoltStrike'
            else:
                self.lightningBoltIcon = 'lightningBolt'

    # Animate lightning bolt icon
    def animateLightningBoltIcon(self):
        Anim = Animation(lightningBoltPosX=10,t='out_quad',d=0.02) + Animation(lightningBoltPosX=0,t='out_elastic',d=0.5)
        Anim.start(self)

class LightningButton(RelativeLayout):
    pass

# ==============================================================================
# BarometerPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class BarometerPanel(RelativeLayout):

    # Define BarometerPanel class properties
    barometerArrow = StringProperty('-')

    # Initialise 'BarometerPanel' relative layout class
    def __init__(self,**kwargs):
        super(BarometerPanel,self).__init__(**kwargs)
        if not hasattr(App.get_running_app(),'BarometerPanel'):
            App.get_running_app().BarometerPanel = []
            App.get_running_app().BarometerPanel.append(self)
        else:
            App.get_running_app().BarometerPanel.append(self)
        self.setBarometerArrow()

    # Set Barometer arrow to current sea level pressure
    @mainthread
    def setBarometerArrow(self):
        self.barometerArrow = App.get_running_app().Obs['Pres'][2]

class BarometerButton(RelativeLayout):
    pass

# ==============================================================================
# UpdateNotification POPUP CLASS
# ==============================================================================
class updateNotif(ModalView):
    pass

# ==============================================================================
# Station CLASS
# ==============================================================================
class Station(Widget):

    # Define Station class Device properties
    Device = DictProperty([('tempestSampleTime','-'), ('tempestVoltage','-'), ('tempestStatus','-'),
                           ('tempestObCount','-'),    ('skySampleTime','-'),  ('skyVoltage','-'),
                           ('skyStatus','-'),         ('skyObCount','-'),     ('outAirSampleTime','-'),
                           ('outAirVoltage','-'),     ('outAirStatus','-'),   ('outAirObCount','-'),
                           ('inAirSampleTime','-'),   ('inAirVoltage','-'),   ('inAirStatus','-'),
                           ('inAirObCount','-'),      ('stationStatus','-'),  ('hubFirmware','-')
                          ])

    # Get hub status from device status
    def getStationStatus(self):
        Thread(target=station.getHubStatus, args=(self.Device,App.get_running_app()), name="getHubStatus", daemon=True).start()

    # Get device status from last observation time
    def getDeviceStatus(self,dt):
        station.getDeviceStatus(self.Device,App.get_running_app())

    # Get device observation count from WeatherFlow API
    def getObservationCount(self):
        Thread(target=station.getObservationCount, args=(self.Device,App.get_running_app()), name="getObservationCount", daemon=True).start()

# ==============================================================================
# mainMenu AND [module]Status CLASSES
# ==============================================================================
class mainMenu(ModalView):

    # Initialise 'BarometerPanel' ModalView class
    def __init__(self,**kwargs):
        super(mainMenu,self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.initialiseStatusPanels()

    # Initialise device status panels based on devices connected to station
    def initialiseStatusPanels(self):

        # Add device status panels based on devices connected to station
        statusPanel = BoxLayout(orientation='vertical', padding=[dp(0),dp(0),dp(0),dp(10)], size_hint=(1,.4))
        if self.app.config['Station']['TempestID']:
            statusPanel.add_widget(tempestStatus())
        if self.app.config['Station']['SkyID']:
            statusPanel.add_widget(skyStatus())
        if self.app.config['Station']['OutAirID']:
            statusPanel.add_widget(outAirStatus())
        if self.app.config['Station']['InAirID']:
            statusPanel.add_widget(inAirStatus())
        self.ids.statusPanel.add_widget(statusPanel)

        # Add 'Close', 'Settings', and 'Exit' buttons below device status panel
        Buttons = BoxLayout(orientation='horizontal',  size_hint=(1,.1), spacing=dp(10), padding=[dp(0),dp(0),dp(0),dp(2)])
        Buttons.add_widget(MenuButton(text='Close',    on_release=self.dismiss))
        Buttons.add_widget(MenuButton(text='Settings', on_release=self.app.open_settings))
        Buttons.add_widget(MenuButton(text='Exit',     on_release=self.app.stop))
        Buttons.add_widget(MenuButton(text='Reboot',   on_release=self.rebootSystem))
        Buttons.add_widget(MenuButton(text='Shutdown', on_release=self.shutdownSystem))
        self.ids.statusPanel.add_widget(Buttons)

        # Populate status fields
        self.app.Station.getObservationCount()
        self.app.Station.getStationStatus()

    # Exit console and shutdown system
    def shutdownSystem(self,instance):
        global SHUTDOWN
        SHUTDOWN = 1
        App.get_running_app().stop()

    # Exit console and reboot system
    def rebootSystem(self,instance):
        global REBOOT
        REBOOT = 1
        App.get_running_app().stop()

class tempestStatus(BoxLayout):
    pass

class skyStatus(BoxLayout):
    pass

class outAirStatus(BoxLayout):
    pass

class inAirStatus(BoxLayout):
    pass

class MenuButton(Button):
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
    try:
        wfpiconsole().run()
        if REBOOT:
            subprocess.call('sudo shutdown -r now', shell = True)
        elif SHUTDOWN:
            subprocess.call('sudo shutdown -h now', shell = True)
    except KeyboardInterrupt:
        wfpiconsole().stop()
