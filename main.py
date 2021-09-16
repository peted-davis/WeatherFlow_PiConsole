# WeatherFlow PiConsole: Raspberry Pi Python console for WeatherFlow Tempest
# and Smart Home Weather stations.
# Copyright (C) 2018-2020 Peter Davis

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
# ==============================================================================
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
    if int(config['Display']['Border']):
        kivyconfig.set('graphics', 'borderless', '0')
    else:
        kivyconfig.set('graphics', 'borderless', '1')

# ==============================================================================
# INITIALISE MOUSE SUPPORT IF OPTION SET in wfpiconsole.ini
# ==============================================================================
# Enable mouse support on Raspberry Pi 3 if not already set
if config['System']['Hardware'] in ['PiB','Pi3']:
    if not config.has_option('modules','cursor'):
        kivyconfig.set('modules','cursor','1')

# Initialise mouse support if required
if int(config['Display']['Cursor']):
    kivyconfig.set('graphics', 'show_cursor', '1')
else:
    kivyconfig.set('graphics', 'show_cursor', '0')

# Save wfpiconsole Kivy configuration file
kivyconfig.write()

# ==============================================================================
# IMPORT REQUIRED CORE KIVY MODULES
# ==============================================================================
from kivy.network.urlrequest import UrlRequest
from kivy.properties         import DictProperty, NumericProperty, BooleanProperty
from kivy.properties         import ConfigParserProperty, StringProperty
from kivy.properties         import ListProperty
from kivy.animation          import Animation
from kivy.core.window        import Window
from kivy.factory            import Factory
from kivy.metrics            import dp, sp
from kivy.clock              import Clock, mainthread
from kivy.utils              import platform
from kivy.lang               import Builder
from kivy.app                import App

# ==============================================================================
# IMPORT REQUIRED LIBRARY MODULES
# ==============================================================================
from lib import astronomical      as astro
from lib import sager             as sagerForecast
from lib import settingScreens
from lib import properties
from lib import forecast
from lib import station
from lib import system
from lib import config

# ==============================================================================
# IMPORT REQUIRED SERVICE MODULES
# ==============================================================================
from service.websocket import websocketClient

# ==============================================================================
# IMPORT REQUIRED USER MODULES
# ==============================================================================
if Path('user/customPanels.py').is_file():
    from user.customPanels import *

# ==============================================================================
# IMPORT REQUIRED SYSTEM MODULES
# ==============================================================================
from oscpy.server  import OSCThreadServer
from oscpy.client  import OSCClient
from functools     import partial
from runpy         import run_path
import subprocess
import threading
import certifi
import socket
import math
import json

# ==============================================================================
# IMPORT REQUIRED KIVY GRAPHICAL AND SETTINGS MODULES
# ==============================================================================
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.screenmanager  import ScreenManager, Screen, NoTransition
from kivy.uix.togglebutton   import ToggleButton
from kivy.uix.scrollview     import ScrollView
from kivy.uix.gridlayout     import GridLayout
from kivy.uix.modalview      import ModalView
from kivy.uix.boxlayout      import BoxLayout
from kivy.uix.behaviors      import ToggleButtonBehavior
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

    # Define App class dictionary properties
    System  = DictProperty([('Time', '-'), ('Date', '-')])
    Sched   = DictProperty([])

    # Define App class configParser properties
    BarometerMax = ConfigParserProperty('-', 'System',  'BarometerMax', 'app')
    BarometerMin = ConfigParserProperty('-', 'System',  'BarometerMin', 'app')
    IndoorTemp   = ConfigParserProperty('-', 'Display', 'IndoorTemp',   'app')

    # Define display properties
    scaleFactor = NumericProperty(1)
    scaleSuffix = StringProperty('_lR.png')

    # BUILD 'WeatherFlowPiConsole' APP CLASS
    # --------------------------------------------------------------------------
    def build(self):

        # Calculate initial ScaleFactor and bind self.setScaleFactor to Window
        # on_resize
        self.window = Window
        self.setScaleFactor(self.window, self.window.width, self.window.height)
        self.window.bind(on_resize=self.setScaleFactor)

        # Initialise realtime clock
        self.Sched.realtimeClock = Clock.schedule_interval(partial(system.realtimeClock, self.System, self.config), 1.0)

        # Set Settings syle class
        self.settings_cls = SettingsWithSidebar

        # Initialise oscSERVER and oscCLIENT
        self.oscSERVER = OSCThreadServer()
        self.oscCLIENT = OSCClient('localhost', 3001)
        self.oscSERVER.listen(address=b'localhost', port=3002, default=True)
        self.oscSERVER.bind(b'/updateDisplay', self.updateDisplay)

        # Load Custom Panel KV file if present
        if Path('user/customPanels.py').is_file():
            Builder.load_file('user/customPanels.kv')

        # Initialise ScreenManager
        self.screenManager = screenManager(transition=NoTransition())
        self.screenManager.add_widget(CurrentConditions())
        return self.screenManager

    # SET DISPLAY SCALE FACTOR BASED ON SCREEN DIMENSIONS
    # --------------------------------------------------------------------------
    def setScaleFactor(self,instance,x,y):
        self.scaleFactor = max(min(x/800, y/480), 1)
        if self.scaleFactor > 1:
            self.scaleSuffix = '_hR.png'
        else:
            self.scaleSuffix = '_lR.png'

    # LOAD APP CONFIGURATION FILE
    # --------------------------------------------------------------------------
    def build_config(self, config):
        config.optionxform = str
        config.read('wfpiconsole.ini')

    # BUILD 'WeatherFlowPiConsole' APP CLASS SETTINGS
    # --------------------------------------------------------------------------
    def build_settings(self, settings):

        # Register setting types
        settings.register_type('ScrollOptions',     SettingScrollOptions)
        settings.register_type('FixedOptions',      SettingFixedOptions)
        settings.register_type('ToggleTemperature', SettingToggleTemperature)
        settings.register_type('ToggleHours',       SettingToggleHours)
        settings.register_type('TextScale',         SettingTextScale)

        # Add required panels to setting screen. Remove Kivy settings panel
        settings.add_json_panel('Display',          self.config, data=settingScreens.JSON('Display'))
        settings.add_json_panel('Primary Panels',   self.config, data=settingScreens.JSON('Primary'))
        settings.add_json_panel('Secondary Panels', self.config, data=settingScreens.JSON('Secondary'))
        settings.add_json_panel('Units',            self.config, data=settingScreens.JSON('Units'))
        settings.add_json_panel('Feels Like',       self.config, data=settingScreens.JSON('FeelsLike'))
        settings.add_json_panel('System',           self.config, data=settingScreens.JSON('System'))
        self.use_kivy_settings = False
        self.settings = settings

    # OVERLOAD 'display_settings' TO OPEN SETTINGS SCREEN WITH SCREEN MANAGER
    # --------------------------------------------------------------------------
    def display_settings(self, settings):
        self.mainMenu.dismiss(animation=False)
        if not self.screenManager.has_screen('Settings'):
            self.settingsScreen = Screen(name='Settings')
            self.screenManager.add_widget(self.settingsScreen)
        self.settingsScreen.add_widget(self.settings)
        self.screenManager.current = 'Settings'
        return True

    # OVERLOAD 'close_settings' TO CLOSE SETTINGS SCREEN WITH SCREEN MANAGER
    # --------------------------------------------------------------------------
    def close_settings(self, *args):
        if self.screenManager.current == 'Settings':
            mainMenu().open(animation=False)
            self.screenManager.current = self.screenManager.previous()
            self.settingsScreen.remove_widget(self.settings)
            return True

    # OVERLOAD 'on_config_change' TO MAKE NECESSARY CHANGES TO CONFIG VALUES
    # WHEN REQUIRED
    # --------------------------------------------------------------------------
    def on_config_change(self, config, section, key, value):

        # Update current weather forecast when temperature or wind speed units
        # are changed
        if section == 'Units' and key in ['Temp', 'Wind']:
            self.Sched.metDownload = Clock.schedule_once(partial(forecast.startDownload, self, True))

        # Update current weather forecast, sunrise/sunset and moonrise/moonset
        # times when time format changed
        if section == 'Display' and key in 'TimeFormat':
            self.Sched.metDownload = Clock.schedule_once(partial(forecast.startDownload, self, True))
            astro.Format(self.CurrentConditions.Astro,   self.config, 'Sun')
            astro.Format(self.CurrentConditions.Astro,   self.config, 'Moon')

        # Update "Feels Like" temperature cutoffs in wfpiconsole.ini and the
        # settings screen when temperature units are changed
        if section == 'Units' and key == 'Temp':
            for Field in self.config['FeelsLike']:
                if 'c' in value:
                    Temp = str(round((float(self.config['FeelsLike'][Field]) - 32) * (5 / 9)))
                    self.config.set('FeelsLike', Field, Temp)
                elif 'f' in value:
                    Temp = str(round(float(self.config['FeelsLike'][Field]) * (9 / 5) + 32))
                    self.config.set('FeelsLike', Field, Temp)
            self.config.write()
            panels = self._app_settings.children[0].content.panels
            for Field in self.config['FeelsLike']:
                for panel in panels.values():
                    if panel.title == 'Feels Like':
                        for item in panel.children:
                            if isinstance(item, Factory.SettingToggleTemperature):
                                if item.title.replace(' ', '') == Field:
                                    item.value = self.config['FeelsLike'][Field]

        # Update barometer limits when pressure units are changed
        if section == 'Units' and key == 'Pressure':
            Units = ['mb', 'hpa', 'inhg', 'mmhg']
            Max   = ['1050', '1050', '31.0', '788']
            Min   = ['950', '950', '28.0', '713']
            self.config.set('System', 'BarometerMax', Max[Units.index(value)])
            self.config.set('System', 'BarometerMin', Min[Units.index(value)])

        # Update primary and secondary panels displayed on CurrentConditions
        # screen
        if section in ['PrimaryPanels', 'SecondaryPanels']:
            for Panel, Type in App.get_running_app().config['PrimaryPanels'].items():
                if Panel == key:
                    self.CurrentConditions.ids[Panel].clear_widgets()
                    self.CurrentConditions.ids[Panel].add_widget(eval(Type + 'Panel')())
                    break

        # Update button layout displayed on CurrentConditions screen
        if section == 'SecondaryPanels':
            ii = 0
            self.CurrentConditions.buttonList = []
            buttonList = ['Button' + Num for Num in ['One', 'Two', 'Three', 'Four', 'Five', 'Six']]
            for button in buttonList:
                self.CurrentConditions.ids[button].clear_widgets()
            for Panel, Type in App.get_running_app().config['SecondaryPanels'].items():
                if Type and Type != 'None':
                    self.CurrentConditions.ids[buttonList[ii]].add_widget(eval(Type + 'Button')())
                    self.CurrentConditions.buttonList.append([buttonList[ii], Panel, Type, 'Primary'])
                    ii += 1

            # Change 'None' for secondary panel selection to blank in config
            # file
            if value == 'None':
                self.config.set(section, key, '')
                self.config.write()
                panels = self._app_settings.children[0].content.panels
                for panel in panels.values():
                    if panel.title == 'Secondary Panels':
                        for item in panel.children:
                            if isinstance(item, Factory.SettingOptions):
                                if item.title.replace(' ', '') == key:
                                    item.value = ''
                                    break

        # Update Sager Forecast schedule
        if section == 'System' and key == 'SagerInterval':
            sagerForecast.Schedule(self.CurrentConditions.Sager, True, self)

        # Send configuration changed notification to Websocket service
        Retries = 0
        while Retries < 3:
            try:
                self.oscCLIENT.send_message(b'/websocket', [('reload_config').encode('utf8')])
                break
            except Exception:
                Retries += 1

    # START WEBSOCKET SERVICE
    # --------------------------------------------------------------------------
    def startWebsocketService(self, *largs):
        self.websocket = threading.Thread(target=websocketClient,
                                          daemon=True,
                                          name='Websocket')
        self.websocket.start()

    # STOP WEBSOCKET SERVICE
    # --------------------------------------------------------------------------
    def stopWebsocketService(self):
        self._websocket_is_running = False
        self.websocket.join()
        del self.websocket
        del self._websocket_is_running

    # UPDATE DISPLAY WITH NEW OBSERVATIONS SENT FROM WEBSOCKET SERVICE
    # --------------------------------------------------------------------------
    def updateDisplay(self, *payload):
        try:
            message = json.loads(payload[0].decode('utf8'))
            type    = payload[1].decode('utf8')
        except Exception:
            pass
        system.updateDisplay(type, message, self)


# ==============================================================================
# CurrentConditions SCREEN CLASS
# ==============================================================================
class CurrentConditions(Screen):

    Sager = DictProperty([])
    Astro = DictProperty([])
    Obs   = DictProperty([])
    Met   = DictProperty([])

    def __init__(self, **kwargs):
        super(CurrentConditions, self).__init__(**kwargs)
        app = App.get_running_app()
        app.CurrentConditions = self
        app.Station  = station.Station(app)
        self.Sager   = properties.Sager()
        self.Astro   = properties.Astro()
        self.Met     = properties.Met()
        self.Obs     = properties.Obs()

        # Add display panels
        self.addPanels()

        # Start Websocket service
        app.startWebsocketService()

        # Schedule Station.getDeviceStatus to be called each second
        app.Sched.deviceStatus = Clock.schedule_interval(app.Station.get_deviceStatus, 1.0)

        # Initialise Sunrise, Sunset, Moonrise and Moonset times
        astro.SunriseSunset(self.Astro,   app.config)
        astro.MoonriseMoonset(self.Astro, app.config)

        # Schedule sunTransit and moonPhase functions to be called each second
        app.Sched.sunTransit = Clock.schedule_interval(partial(astro.sunTransit, self.Astro, app.config), 1)
        app.Sched.moonPhase  = Clock.schedule_interval(partial(astro.moonPhase,  self.Astro, app.config), 1)

        # Schedule WeatherFlow weather forecast download
        app.Sched.metDownload = Clock.schedule_once(partial(forecast.startDownload, app, False))

        # Generate Sager Weathercaster forecast
        threading.Thread(target=sagerForecast.Generate, args=(self.Sager, app), name="Sager", daemon=True).start()

    # ADD USER SELECTED PANELS TO CURRENT CONDITIONS SCREEN
    # --------------------------------------------------------------------------
    def addPanels(self):

        # Add primary panels to CurrentConditions screen
        for Panel, Type in App.get_running_app().config['PrimaryPanels'].items():
            self.ids[Panel].add_widget(eval(Type + 'Panel')())

        # Add secondary panel buttons to CurrentConditions screen
        self.buttonList = []
        ii = 0
        buttonList = ['Button' + Num for Num in ['One', 'Two', 'Three', 'Four', 'Five', 'Six']]
        for Panel, Type in App.get_running_app().config['SecondaryPanels'].items():
            if Type:
                self.ids[buttonList[ii]].add_widget(eval(Type + 'Button')())
                self.buttonList.append([buttonList[ii], Panel, Type, 'Primary'])
                ii += 1

    # SWITCH BETWEEN PRIMARY AND SECONDARY PANELS ON CURRENT CONDITIONS SCREEN
    # --------------------------------------------------------------------------
    def switchPanel(self, Instance, overideButton=None):

        # Determine ID of button that has been pressed
        for id, Object in App.get_running_app().CurrentConditions.ids.items():
            if Instance:
                if Object == Instance.parent.parent:
                    break
            else:
                if Object == overideButton:
                    break

        # Extract entry in buttonList that correponds to the button that has
        # been pressed
        for ii, button in enumerate(App.get_running_app().CurrentConditions.buttonList):
            if button[0] == id:
                break

        # Extract panel object the corresponds to the button that has been
        # pressed and determine new button type required
        Panel = App.get_running_app().CurrentConditions.ids[button[1]].children
        newButton = App.get_running_app().config[button[3] + 'Panels'][button[1]]

        # Destroy reference to old panel class attribute
        if hasattr(App.get_running_app(), newButton + 'Panel'):
            if len(getattr(App.get_running_app(), newButton + 'Panel')) > 1:
                try:
                    getattr(App.get_running_app(), newButton + 'Panel').remove(Panel[0])
                except ValueError:
                    print('Unable to remove panel reference from wfpiconsole class')
            else:
                delattr(App.get_running_app(), newButton + 'Panel')

        # Switch panel
        App.get_running_app().CurrentConditions.ids[button[1]].clear_widgets()
        App.get_running_app().CurrentConditions.ids[button[1]].add_widget(eval(button[2] + 'Panel')())
        App.get_running_app().CurrentConditions.ids[button[0]].clear_widgets()
        App.get_running_app().CurrentConditions.ids[button[0]].add_widget(eval(newButton + 'Button')())

        # Update button list
        if button[3] == 'Primary':
            App.get_running_app().CurrentConditions.buttonList[ii] = [button[0], button[1], newButton, 'Secondary']
        elif button[3] == 'Secondary':
            App.get_running_app().CurrentConditions.buttonList[ii] = [button[0], button[1], newButton, 'Primary']


# ==============================================================================
# screenManager SCREEN MANAGER CLASS
# ==============================================================================
class screenManager(ScreenManager):
    pass


# ==============================================================================
# ForecastPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class ForecastPanel(RelativeLayout):

    # Define TemperaturePanel class properties
    forecastIcon = StringProperty('-')

    # Initialise 'ForecastPanel' relative layout class
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(App.get_running_app(), self.__class__.__name__):
            panelList = []
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)
        else:
            panelList = getattr(App.get_running_app(), self.__class__.__name__, 'panelList')
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)

        # Run required class functions
        self.setForecastIcon()

    # Set Forecast icon
    @mainthread
    def setForecastIcon(self):
        self.forecastIcon = App.get_running_app().CurrentConditions.Met['Icon']


class ForecastButton(RelativeLayout):
    pass


# ==============================================================================
# SagerPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class SagerPanel(RelativeLayout):

    # Initialise 'SagerPanel' relative layout class
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(App.get_running_app(), self.__class__.__name__):
            panelList = []
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)
        else:
            panelList = getattr(App.get_running_app(), self.__class__.__name__, 'panelList')
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)

class SagerButton(RelativeLayout):
    pass


# ==============================================================================
# TemperaturePanel RELATIVE LAYOUT CLASS
# ==============================================================================
class TemperaturePanel(RelativeLayout):

    # Define TemperaturePanel class properties
    feelsLikeIcon = StringProperty('-')

    # Initialise 'TemperaturePanel' relative layout class
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(App.get_running_app(), self.__class__.__name__):
            panelList = []
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)
        else:
            panelList = getattr(App.get_running_app(), self.__class__.__name__, 'panelList')
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)

        # Run required class functions
        self.setFeelsLikeIcon()

    # Set "Feels Like" icon
    def setFeelsLikeIcon(self):
        self.feelsLikeIcon = App.get_running_app().CurrentConditions.Obs['FeelsLike'][3]


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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(App.get_running_app(), self.__class__.__name__):
            panelList = []
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)
        else:
            panelList = getattr(App.get_running_app(), self.__class__.__name__, 'panelList')
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)

        # Run required class functions
        if App.get_running_app().CurrentConditions.Obs['rapidDir'][0] != '-':
            self.rapidWindDir = App.get_running_app().CurrentConditions.Obs['rapidDir'][0]
        self.setWindIcons()

    # Animate rapid wind rose
    def animateWindRose(self):

        # Get current wind direction, old wind direction and change in wind
        # direction over last Rapid-Wind period
        if App.get_running_app().CurrentConditions.Obs['rapidDir'][0] != '-':
            rapidWindDir_New = int(App.get_running_app().CurrentConditions.Obs['rapidDir'][0])
            rapidWindDir_Old = self.rapidWindDir
            rapidWindShift   = rapidWindDir_New - self.rapidWindDir

            # Animate Wind Rose at constant speed between old and new Rapid-Wind
            # wind direction
            if rapidWindShift >= -180 and rapidWindShift <= 180:
                Anim = Animation(rapidWindDir=rapidWindDir_New, duration=2 * abs(rapidWindShift) / 360)
                Anim.start(self)
            elif rapidWindShift > 180:
                Anim = Animation(rapidWindDir=0.1, duration=2 * rapidWindDir_Old / 360) + Animation(rapidWindDir=rapidWindDir_New, duration=2 * (360 - rapidWindDir_New) / 360)
                Anim.start(self)
            elif rapidWindShift < -180:
                Anim = Animation(rapidWindDir=359.9, duration=2 * (360 - rapidWindDir_Old) / 360) + Animation(rapidWindDir=rapidWindDir_New, duration=2 * rapidWindDir_New / 360)
                Anim.start(self)

    # Fix Wind Rose angle at 0/360 degree discontinuity
    def on_rapidWindDir(self, item, rapidWindDir):
        if rapidWindDir == 0.1:
            item.rapidWindDir = 360
        if rapidWindDir == 359.9:
            item.rapidWindDir = 0

    # Set mean windspeed and direction icons
    def setWindIcons(self):
        self.windDirIcon = App.get_running_app().CurrentConditions.Obs['WindDir'][2]
        self.windSpdIcon = App.get_running_app().CurrentConditions.Obs['WindSpd'][3]


class WindSpeedButton(RelativeLayout):
    pass


# ==============================================================================
# SunriseSunsetPanel RELATIVE LAYOUT CLASS
# ==============================================================================
class SunriseSunsetPanel(RelativeLayout):

    # Define SunriseSunsetPanel class properties
    uvBackground = StringProperty('-')

    # Initialise 'SunriseSunsetPanel' relative layout class
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(App.get_running_app(), self.__class__.__name__):
            panelList = []
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)
        else:
            panelList = getattr(App.get_running_app(), self.__class__.__name__, 'panelList')
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)

        # Run required class functions
        self.setUVBackground()

    # Set current UV index backgroud
    def setUVBackground(self):
        self.uvBackground = App.get_running_app().CurrentConditions.Obs['UVIndex'][3]


class SunriseSunsetButton(RelativeLayout):
    pass


# ==============================================================================
# MoonPhasePanel RELATIVE LAYOUT CLASS
# ==============================================================================
class MoonPhasePanel(RelativeLayout):

    # Initialise 'MoonPhasePanel' relative layout class
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(App.get_running_app(), self.__class__.__name__):
            panelList = []
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)
        else:
            panelList = getattr(App.get_running_app(), self.__class__.__name__, 'panelList')
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)


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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(App.get_running_app(), self.__class__.__name__):
            panelList = []
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)
        else:
            panelList = getattr(App.get_running_app(), self.__class__.__name__, 'panelList')
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)

        # Run required class functions
        self.animateRainRate()

    # Animate RainRate level
    def animateRainRate(self):

        # Get current rain rate and convert to float
        if App.get_running_app().CurrentConditions.Obs['RainRate'][0] != '-':
            RainRate = float(App.get_running_app().CurrentConditions.Obs['RainRate'][3])

            # Set RainRate level y position
            y0 = -1.00
            yt = 0
            t = 50
            if RainRate == 0:
                self.rainRatePosY = y0
            elif RainRate < 50.0:
                A = (yt - y0) / t**0.5 * RainRate**0.5 + y0
                B = (yt - y0) / t**0.3 * RainRate**0.3 + y0
                C = (1 + math.tanh(RainRate - 3)) / 2
                self.rainRatePosY = (A + C * (B - A))
            else:
                self.rainRatePosY = yt

            # Animate RainRate level x position
            if RainRate == 0:
                if hasattr(self, 'Anim'):
                    self.Anim.stop(self)
                    delattr(self, 'Anim')
            else:
                if not hasattr(self, 'Anim'):
                    self.Anim  = Animation(rainRatePosX=-0.875, duration=12)
                    self.Anim += Animation(rainRatePosX=-0.875, duration=12)
                    self.Anim.repeat = True
                    self.Anim.start(self)

    # Loop RainRate animation in the x direction
    def on_rainRatePosX(self, item, rainRatePosX):
        if round(rainRatePosX, 3) == -0.875:
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(App.get_running_app(), self.__class__.__name__):
            panelList = []
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)
        else:
            panelList = getattr(App.get_running_app(), self.__class__.__name__, 'panelList')
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)

        # Run required class functions
        self.setLightningBoltIcon()

    # Set lightning bolt icon
    def setLightningBoltIcon(self):
        if App.get_running_app().CurrentConditions.Obs['StrikeDeltaT'][0] != '-':
            if App.get_running_app().CurrentConditions.Obs['StrikeDeltaT'][4] < 360:
                self.lightningBoltIcon = 'lightningBoltStrike'
            else:
                self.lightningBoltIcon = 'lightningBolt'

    # Animate lightning bolt icon
    def animateLightningBoltIcon(self):
        Anim = Animation(lightningBoltPosX=dp(10), t='out_quad', d=0.02) + Animation(lightningBoltPosX=dp(0), t='out_elastic', d=0.5)
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not hasattr(App.get_running_app(), self.__class__.__name__):
            panelList = []
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)
        else:
            panelList = getattr(App.get_running_app(), self.__class__.__name__, 'panelList')
            panelList.append(self)
            setattr(App.get_running_app(), self.__class__.__name__, panelList)

        # Run required class functions
        self.setBarometerArrow()

    # Set Barometer arrow rotation angle to match current sea level pressure
    def setBarometerArrow(self):
        SLP = App.get_running_app().CurrentConditions.Obs['SLP'][2]
        if SLP == '-':
            pass
        elif SLP is None:
            self.barometerArrow = '-'
        else:
            self.barometerArrow = '{:.1f}'.format(SLP)


class BarometerButton(RelativeLayout):
    pass


# =============================================================================
# mainMenu CLASS
# =============================================================================
class mainMenu(ModalView):

    stationMetaData = DictProperty([])
    stationList     = ListProperty([])
    tempestList     = ListProperty([])
    deviceList      = DictProperty([])
    skyList         = ListProperty([])
    airList         = ListProperty([])

    # Initialise 'mainMenu' ModalView class
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.initialiseStatusPanels()
        self.get_stationList()

    def on_open(self):
        self.app.mainMenu = self

    # Initialise device status panels based on devices connected to station
    def initialiseStatusPanels(self):

        # Add device status panels based on devices connected to station
        if self.app.config['Station']['TempestID']:
            self.ids.devicePanel.add_widget(self.app.Station.tempestStatusPanel)
        if self.app.config['Station']['SkyID']:
            self.ids.devicePanel.add_widget(self.app.Station.skyStatusPanel)
        if self.app.config['Station']['OutAirID']:
            self.ids.devicePanel.add_widget(self.app.Station.outAirStatusPanel)
        if self.app.config['Station']['InAirID']:
            self.ids.devicePanel.add_widget(self.app.Station.inAirStatusPanel)

        # Populate status fields
        self.app.Station.get_observationCount()
        self.app.Station.get_hubFirmware()

    # Fetch list of stations associated with WeatherFlow key
    def get_stationList(self):
        URL = 'https://swd.weatherflow.com/swd/rest/stations?token={}'
        URL = URL.format(self.app.config['Keys']['WeatherFlow'])
        UrlRequest(URL,
                   on_success=self.parse_stationList,
                   on_failure=self.fail_stationList,
                   on_error=self.fail_stationList,
                   ca_file=certifi.where())

    # Parse list of stations associated with WeatherFlow key
    def parse_stationList(self, Request, Response):
        if 'status' in Response:
            if 'SUCCESS' in Response['status']['status_message']:
                self.stationDetails = {}
                for Station in Response['stations']:
                    self.stationDetails[Station['name']] = Station
                self.stationList = list(self.stationDetails.keys())
                self.ids.stationList.text = self.app.config['Station']['Name']

    # FALIED TO FETCH LIST OF STATIONS
    # -------------------------------------------------------------------------
    def fail_stationList(self, Request, Response):
        if isinstance(Response, socket.gaierror):
            self.ids.loginButton.text = 'Host name error. Please try again'
        else:
            self.ids.loginButton.text = f'Error {Request.resp_status}. Please try again'

    # GET DEVICES ASSOCIATED WITH SELECTED STATION
    # -------------------------------------------------------------------------
    def get_stationDevices(self):

        # Define required variables
        #self.ids.continueButton.text = 'Fetching Station information'
        self.stationMetaData = {}
        self.deviceMetaData = {}
        self.deviceList = {}
        self.tempestList = []
        self.skyList = []
        self.airList = []
        self.retries = 0

        # Fetch all devices associated with Station
        if self.stationDetails:
            self.get_stationMetaData()
            for Device in self.stationDetails[self.ids.stationList.text]['devices']:
                if 'device_type' in Device:
                    if Device['device_type'] == 'ST':
                        self.tempestList.append(Device['device_meta']['name'] + ': ' + str(Device['device_id']))
                        self.deviceMetaData[str(Device['device_id'])] = Device
                    if Device['device_type'] == 'SK':
                        self.skyList.append(Device['device_meta']['name'] + ': ' + str(Device['device_id']))
                        self.deviceMetaData[str(Device['device_id'])] = Device
                    if Device['device_type'] == 'AR':
                        self.airList.append(Device['device_meta']['name'] + ': ' + str(Device['device_id']))
                        self.deviceMetaData[str(Device['device_id'])] = Device

        # Initialise device selection lists based on the number and type of
        # devices associated with the station.
        # [1] Tempest AND (Sky OR Air)
        if self.tempestList and (self.skyList or self.airList):
            self.ids.tempestDropdown.disabled = 0
            self.tempestList.insert(len(self.tempestList), 'Clear')
            if (self.app.config['Station']['TempestID'] and
                self.ids.stationList.text == self.app.config['Station']['Name']):
                for tempest in self.tempestList:
                    if self.app.config['Station']['TempestID'] in tempest:
                        self.ids.tempestDropdown.text = tempest
                self.ids.skyDropdown.text     = self.ids.airDropdown.text     = 'Tempest selected'
                self.ids.skyDropdown.disabled = self.ids.airDropdown.disabled = 1
            else:
                self.ids.tempestDropdown.text = 'Please select'

                if self.skyList:
                    if (self.app.config['Station']['SkyID'] and
                        self.ids.stationList.text == self.app.config['Station']['Name']):
                        self.ids.skyDropdown.disabled = 0
                        for sky in self.skyList:
                            if self.app.config['Station']['SkyID'] in sky:
                                self.ids.skyDropdown.text = sky
                        self.ids.tempestDropdown.text = 'Sky selected'
                        self.ids.tempestDropdown.disabled = 0
                    else:
                        self.ids.skyDropdown.text = 'Please select'
                        self.ids.skyDropdown.disabled = 0
                    self.skyList.insert(len(self.skyList), 'Clear')
                else:
                    self.ids.skyDropdown.text = 'No device available'
                    self.ids.skyDropdown.disabled = 1

                if self.airList:
                    if (self.app.config['Station']['OutAirID'] and
                        self.ids.stationList.text == self.app.config['Station']['Name']):
                        self.ids.airDropdown.disabled = 0
                        for air in self.airList:
                            if self.app.config['Station']['OutAirID'] in air:
                                self.ids.airDropdown.text = air
                        self.ids.tempestDropdown.text = 'Air selected'
                        self.ids.tempestDropdown.disabled = 0
                    else:
                        self.ids.airDropdown.text = 'Please select'
                        self.ids.airDropdown.disabled = 0
                    self.airList.insert(len(self.airList), 'Clear')
                else:
                    self.ids.airDropdown.text = 'No device available'
                    self.ids.airDropdown.disabled = 1

        # [2] Tempest ONLY
        elif self.tempestList:
            self.ids.tempestDropdown.disabled = 0
            self.ids.airDropdown.disabled = self.ids.skyDropdown.disabled = 1
            self.ids.airDropdown.text     = self.ids.skyDropdown.text     = 'No device available'
            if self.ids.stationList.text == self.app.config['Station']['Name']:
                for tempest in self.tempestList:
                    if self.app.config['Station']['TempestID'] in tempest:
                        self.ids.tempestDropdown.text = tempest
            else:
                self.ids.tempestDropdown.text = 'Please select'
            self.tempestList.insert(len(self.tempestList), 'Clear')

        # [3] Sky OR Air ONLY
        elif self.skyList or self.airList:
            self.ids.tempestDropdown.disabled = 1
            self.ids.tempestDropdown.text = 'No device available'

            if self.airList:
                self.ids.airDropdown.disabled = 0
                if (self.app.config['Station']['OutAirID'] and
                    self.ids.stationList.text == self.app.config['Station']['Name']):
                    for air in self.airList:
                        if self.app.config['Station']['OutAirID'] in air:
                            self.ids.airDropdown.text = air
                else:
                    self.ids.airDropdown.text = 'Please select'
                self.tempestList.insert(len(self.airList), 'Clear')
            else:
                self.ids.airDropdown.text = 'No device available'
                self.ids.airDropdown.disabled = 1

            if self.skyList:
                self.ids.skyDropdown.disabled = 0
                if (self.app.config['Station']['SkyID'] and
                    self.ids.stationList.text == self.app.config['Station']['Name']):
                    for sky in self.skyList:
                        if self.app.config['Station']['SkyID'] in sky:
                            self.ids.skyDropdown.text = sky
                else:
                    self.ids.skyDropdown.text = 'Please select'
                self.tempestList.insert(len(self.skyList), 'Clear')
            else:
                self.ids.skyDropdown.text = 'No device available'
                self.ids.skyDropdown.disabled = 1

    # SET BEHAVIOUR OF DEVICE SELECTION LISTS AS USER SELECTS THEIR DEVICES
    # --------------------------------------------------------------------------
    def on_deviceSelection(self, instance):
        instance_id = list(self.ids.keys())[list(self.ids.values()).index(instance)]
        if instance.text == 'Clear':
            for device in ['tempest', 'sky', 'air']:
                if getattr(self, device + 'List'):
                    getattr(self.ids, device + 'Dropdown').text = 'Please select'
                    getattr(self.ids, device + 'Dropdown').disabled = 0
            self.ids.switchButton.disabled = 1
            self.ids.switchButton.text = 'Please select devices'
            self.deviceList = {}
        else:
            Device = self.deviceMetaData[instance.text.split(':')[1].strip()]
            self.deviceList[Device['device_type']] = Device
            if instance_id == 'tempestDropdown':
                self.ids.skyDropdown.disabled = self.ids.airDropdown.disabled = 1
                if self.airList:
                    self.ids.airDropdown.text = 'Tempest selected'
                if self.skyList:
                    self.ids.skyDropdown.text = 'Tempest selected'
            elif instance_id in ['skyDropdown', 'airDropdown']:
                self.ids.tempestDropdown.disabled = 1
                if self.tempestList:
                    self.ids.tempestDropdown.text = 'Air or Sky selected'
        if self.ids.switchButton.text != 'Fetching Station information':
            self.set_switchButton()

    # GET METADATA ASSOCIATED WITH SELECTED STATION
    # -------------------------------------------------------------------------
    def get_stationMetaData(self):
        self.ids.switchButton.text = 'Fetching Station information'
        self.ids.switchButton.disabled = 1
        if hasattr(self, 'pendingRequest'):
            self.pendingRequest.cancel()
        if hasattr(self, 'activeRequest'):
            self.activeRequest.cancel()
        if self.stationDetails:
            station = self.ids.stationList.text
            URL = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?token={}'
            URL = URL.format(self.stationDetails[station]['station_id'], App.get_running_app().config['Keys']['WeatherFlow'])
            self.activeRequest = UrlRequest(URL,
                                            on_success=self.parse_stationMetaData,
                                            on_failure=self.fail_stationMetaData,
                                            on_error=self.fail_stationMetaData,
                                            ca_file=certifi.where())

    # PARSE METADATA ASSOCIATED WITH SELECTED STATION
    # -------------------------------------------------------------------------
    def parse_stationMetaData(self, Request, Response):

        # Parse Station metadata received from API request
        self.retries += 1
        if 'status' in Response:
            if 'SUCCESS' in Response['status']['status_message']:
                self.stationMetaData = Response
            elif self.retries <= 3:
                self.ids.switchButton.text = 'Bad response. Retrying...'
                self.pendingRequest = Clock.schedule_once(lambda dt: self.get_stationMetaData(), 2)
                return
            else:
                self.ids.switchButton.text = 'Failed to fetch Station information'
                self.ids.switchButton.disabled = 1
                return
        self.set_switchButton()

    # FAILED TO GET METADATA ASSOCIATED WITH SELECTED STATION
    # -------------------------------------------------------------------------
    def fail_stationMetaData(self, Request, Response):
        self.retries += 1
        if self.retries <= 3:
            self.ids.switchButton.text = 'Bad response. Retrying...'
            Clock.schedule_once(lambda dt: self.get_stationMetaData(), 2)
        else:
            self.ids.switchButton.text = 'Failed to fetch Station information'

    # SET TEXT OF continueButton BASED ON STATUS OF DEVICE SELECTION LISTS
    # -------------------------------------------------------------------------
    def set_switchButton(self):
        newStation = self.ids.stationList.text != self.app.config['Station']['Name']
        newDevice  = (self.app.config['Station']['TempestID'] not in self.ids.tempestDropdown.text or
                      self.app.config['Station']['SkyID']     not in self.ids.skyDropdown.text     or
                      self.app.config['Station']['OutAirID']  not in self.ids.airDropdown.text)
        deviceSelected = (self.ids.tempestDropdown.selected or
                          self.ids.skyDropdown.selected     or
                          self.ids.airDropdown.selected)
        if newStation:
            if deviceSelected:
                self.ids.switchButton.disabled = 0
                self.ids.switchButton.text = 'Switch station'
            else:
                self.ids.switchButton.text = 'Please select devices'
        else:
            if deviceSelected and newDevice:
                self.ids.switchButton.disabled = 0
                self.ids.switchButton.text = 'Switch devices'
            else:
                if deviceSelected:
                    self.ids.switchButton.disabled = 1
                    self.ids.switchButton.text = 'Station & Devices unchanged'
                else:
                    self.ids.switchButton.disabled = 1
                    self.ids.switchButton.text = 'Please select devices'


    def switchStations(self):
        self.dismiss(animation=False)
        # Retries = 0
        # while Retries < 3:
        #     try:
        #         self.app.oscCLIENT.send_message(b'/websocket', [('listen_stop').encode('utf8')])
        #         break
        #     except Exception:
        #         Retries += 1
        #
        #
        #
        # config.switch(self.stationMetaData, self.deviceList, self.app.config)
        #
        # Retries = 0
        # while Retries < 3:
        #     try:
        #         self.app.oscCLIENT.send_message(b'/websocket', [('reload_config').encode('utf8')])
        #         break
        #     except Exception:
        #         Retries += 1



        Retries = 0
        while Retries < 3:
            try:
                self.app.oscCLIENT.send_message(b'/websocket', [('switch_device').encode('utf8'),
                                                                json.dumps(self.stationMetaData).encode('utf8'),
                                                                json.dumps(self.deviceList).encode('utf8')])
                break
            except Exception:
                Retries += 1



        #self.app.stopWebsocketService()
        #self.app.Sched.deviceStatus.cancel()
        #del(self.app.Station)


        config.switch(self.stationMetaData, self.deviceList, self.app.config)
        #self.app.CurrentConditions.Obs = properties.Obs()

        #print(dict(properties.Obs()))
        #print()
        #print(self.app.CurrentConditions.Obs)
        system.updateDisplay('obs_all', dict(properties.Obs()), self.app)

        #self.app.startWebsocketService()
        #self.app.Station = station.Station(self.app)
        #self.app.Sched.deviceStatus = Clock.schedule_interval(self.app.Station.get_deviceStatus, 1.0)





    # Exit console and shutdown system
    def shutdownSystem(self):
        global SHUTDOWN
        SHUTDOWN = 1
        App.get_running_app().stop()

    # Exit console and reboot system
    def rebootSystem(self):
        global REBOOT
        REBOOT = 1
        App.get_running_app().stop()

    # Delete device status panel widgets when closing main menu
    def on_dismiss(self):
        self.ids.devicePanel.clear_widgets()


# =============================================================================
# SettingScrollOptions SETTINGS CLASS
# =============================================================================
class SettingScrollOptions(SettingOptions):

    def _create_popup(self, instance):

        # Create the popup and scrollview
        content         = BoxLayout(orientation='vertical', spacing='5dp')
        scrollview      = ScrollView(do_scroll_x=False, bar_inactive_color=[.7, .7, .7, 0.9], bar_width=4)
        scrollcontent   = GridLayout(cols=1, spacing='5dp', size_hint=(0.95, None))
        self.popup      = Popup(content=content,
                                title=self.title,
                                size_hint=(0.25, 0.8),
                                auto_dismiss=False,
                                separator_color=[1, 1, 1, 1])

        # Add all the options to the ScrollView
        scrollcontent.bind(minimum_height=scrollcontent.setter('height'))
        content.add_widget(Widget(size_hint_y=None, height=dp(1)))
        uid = str(self.uid)
        for option in self.options:
            state = 'down' if option == self.value else 'normal'
            btn = ToggleButton(text=option,
                               state=state,
                               group=uid,
                               height=dp(58),
                               size_hint=(0.9, None))
            btn.bind(on_release=self._set_option)
            scrollcontent.add_widget(btn)

        # Finally, add a cancel button to return on the previous panel
        scrollview.add_widget(scrollcontent)
        content.add_widget(scrollview)
        content.add_widget(SettingSpacer())
        btn = Button(text='Cancel',
                     height=dp(58),
                     size_hint=(1, None))
        btn.bind(on_release=self.popup.dismiss)
        content.add_widget(btn)
        self.popup.open()


# =============================================================================
# SettingFixedOptions SETTINGS CLASS
# =============================================================================
class SettingFixedOptions(SettingOptions):

    def _create_popup(self, instance):

        # Create the popup
        content     = BoxLayout(orientation='vertical', spacing='5dp')
        self.popup  = Popup(content=content,
                            title=self.title,
                            size_hint=(0.25, None),
                            auto_dismiss=False,
                            separator_color=[1, 1, 1, 1],
                            height=dp(134) + dp(min(len(self.options), 4) * 63))

        # Add all the options to the Popup
        content.add_widget(Widget(size_hint_y=None, height=dp(1)))
        uid = str(self.uid)
        for option in self.options:
            state = 'down' if option == self.value else 'normal'
            btn = ToggleButton(text=option,
                               state=state,
                               group=uid,
                               height=dp(58),
                               size_hint=(1, None))
            btn.bind(on_release=self._set_option)
            content.add_widget(btn)

        # Add a cancel button to return on the previous panel
        content.add_widget(SettingSpacer())
        btn = Button(text='Cancel',
                     height=dp(58),
                     size_hint=(1, None))
        btn.bind(on_release=self.popup.dismiss)
        content.add_widget(btn)
        self.popup.open()


# =============================================================================
# SettingFixedOptions SETTINGS CLASS
# =============================================================================
class SettingTextScale(SettingString):

    def _create_popup(self, instance):

        # Create Popup layout
        content     = BoxLayout(orientation='vertical', spacing=dp(5))
        self.popup  = Popup(content=content,
                            title=self.title,
                            size_hint=(0.6, None),
                            auto_dismiss=False,
                            separator_color=[1, 1, 1, 0.3],
                            height=dp(150))

        # Add toggle buttons to change the text scale
        self.toggles = BoxLayout()
        text  = ['Smallest', 'Smaller', 'Normal', 'Larger', 'Largest']
        scale = [0.50, 0.75, 1.00, 1.25, 1.50]
        display = [0.70, 0.85, 1.00, 1.15, 1.30]
        for index, value in enumerate(text):
            self.toggles.add_widget(TextScaleLabel(text=value,
                                                   font_size=sp(18 * display[index]),
                                                   on_press=self._set_value,
                                                   _scale=scale[index],
                                                   on_release=self.popup.dismiss))
        content.add_widget(BoxLayout(size_hint_y=0.05))
        content.add_widget(self.toggles)

        # Add cancel button
        self.closeButton = BoxLayout(padding=[dp(150), dp(0)])
        btn = Button(text='Cancel', font_size=sp(18))
        btn.bind(on_release=self.popup.dismiss)
        self.closeButton.add_widget(btn)
        content.add_widget(SettingSpacer())
        content.add_widget(self.closeButton)

        # Open the popup
        self.popup.open()

    def _set_value(self, instance):
        self.value = str(instance._scale)


# =============================================================================
# SettingToggleTemperature SETTINGS CLASS
# =============================================================================
class SettingToggleTemperature(SettingString):

    def _create_popup(self, instance):

        # Get temperature units from config file
        config = App.get_running_app().config
        self.units = '[sup]o[/sup]' + config['Units']['Temp'].upper()

        # Create Popup layout
        content     = BoxLayout(orientation='vertical', spacing=dp(5))
        self.popup  = Popup(content=content,
                            title=self.title,
                            size_hint=(0.25, None),
                            auto_dismiss=False,
                            separator_color=[1, 1, 1, 0],
                            height=dp(234))
        content.add_widget(SettingSpacer())

        # Create the label to show the numeric value
        self.Label = Label(text=self.value + self.units,
                           markup=True,
                           font_size=sp(24),
                           size_hint_y=None,
                           height=dp(50),
                           halign='left')
        content.add_widget(self.Label)

        # Add a plus and minus increment button to change the value by +/- one
        btnlayout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(50))
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
        btnlayout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(5))
        btn = Button(text='Ok')
        btn.bind(on_release=self._set_value)
        btnlayout.add_widget(btn)
        btn = Button(text='Cancel')
        btn.bind(on_release=self.popup.dismiss)
        btnlayout.add_widget(btn)
        content.add_widget(btnlayout)

        # Open the popup
        self.popup.open()

    def _set_value(self, instance):
        self.value = self.Label.text.replace(self.units, '')
        self.popup.dismiss()

    def _minus_value(self, instance):
        Value = int(self.Label.text.replace(self.units, '')) - 1
        self.Label.text = str(Value) + self.units

    def _plus_value(self, instance):
        Value = int(self.Label.text.replace(self.units, '')) + 1
        self.Label.text = str(Value) + self.units

# =============================================================================
# SettingToggleHours SETTINGS CLASS
# =============================================================================
class SettingToggleHours(SettingString):

    def _create_popup(self, instance):

        # Get temperature units from config file
        config = App.get_running_app().config
        self.units = ' hours'

        # Create Popup layout
        content     = BoxLayout(orientation='vertical', spacing=dp(5))
        self.popup  = Popup(content=content,
                            title=self.title,
                            size_hint=(0.25, None),
                            auto_dismiss=False,
                            separator_color=[1, 1, 1, 0],
                            height=dp(234))
        content.add_widget(SettingSpacer())

        # Create the label to show the numeric value
        self.Label = Label(text=self.value + self.units,
                           markup=True,
                           font_size=sp(24),
                           size_hint_y=None,
                           height=dp(50),
                           halign='left')
        content.add_widget(self.Label)

        # Add a plus and minus increment button to change the value by +/- one
        btnlayout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(50))
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
        btnlayout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(5))
        btn = Button(text='Ok')
        btn.bind(on_release=self._set_value)
        btnlayout.add_widget(btn)
        btn = Button(text='Cancel')
        btn.bind(on_release=self.popup.dismiss)
        btnlayout.add_widget(btn)
        content.add_widget(btnlayout)

        # Open the popup
        self.popup.open()

    def _set_value(self, instance):
        self.value = self.Label.text.replace(self.units, '')
        self.popup.dismiss()

    def _minus_value(self, instance):
        Value = int(self.Label.text.replace(self.units, '')) - 1
        self.Label.text = str(Value) + self.units

    def _plus_value(self, instance):
        Value = int(self.Label.text.replace(self.units, '')) + 1
        self.Label.text = str(Value) + self.units


# ==============================================================================
# RUN APP
# ==============================================================================
if __name__ == '__main__':
    try:
        wfpiconsole().run()
        if REBOOT:
            subprocess.call('sudo shutdown -r now', shell = True)
        elif SHUTDOWN:
            subprocess.call('sudo shutdown -h now', shell = True)
    except KeyboardInterrupt:
        wfpiconsole().stop()
