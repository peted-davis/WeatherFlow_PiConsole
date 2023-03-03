# WeatherFlow PiConsole: Raspberry Pi Python console for WeatherFlow Tempest
# and Smart Home Weather stations.
# Copyright (C) 2018-2023 Peter Davis

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
if config['System']['Hardware'] in ['Pi4', 'Linux']:
    os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '1'
    os.environ['KIVY_GRAPHICS'] = 'gles'
    os.environ['KIVY_WINDOW']   = 'sdl2'
elif config['System']['Hardware'] in ['PiB', 'Pi3']:
    os.environ['KIVY_GL_BACKEND'] = 'gl'

# ==============================================================================
# INITIALISE KIVY WINDOW PROPERTIES BASED ON OPTIONS SET IN wfpiconsole.ini
# ==============================================================================
# Import required modules
from kivy.config import Config as kivyconfig                                    # type: ignore

# Generate default wfpiconsole Kivy config file. Config file is always
# regenerated to ensure changes to the default file are always copied across
defaultconfig = configparser.ConfigParser()
defaultconfig.read(os.path.expanduser('~/.kivy/') + 'config.ini')
with open(os.path.expanduser('~/.kivy/') + 'config_wfpiconsole.ini', 'w') as cfg:
    defaultconfig.write(cfg)

# Load wfpiconsole Kivy configuration file
kivyconfig.read(os.path.expanduser('~/.kivy/') + 'config_wfpiconsole.ini')

# Set Kivy window properties
if config['System']['Hardware'] in ['Pi4', 'Linux', 'Other']:
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
if config['System']['Hardware'] in ['PiB', 'Pi3']:
    if not config.has_option('modules', 'cursor'):
        kivyconfig.set('modules', 'cursor', '1')

# Initialise mouse support if required
if int(config['Display']['Cursor']):
    kivyconfig.set('graphics', 'show_cursor', '1')
    if config['System']['Hardware'] == 'Pi4':
        kivyconfig.set('input', 'mouse', 'mouse')
        kivyconfig.remove_option('input', 'mtdev_%(name)s')
        # kivyconfig.remove_option('input', 'hid_%(name)s')
else:
    kivyconfig.set('graphics', 'show_cursor', '0')
    if config['System']['Hardware'] == 'Pi4':
        kivyconfig.remove_option('input', 'mouse')

# Save wfpiconsole Kivy configuration file
kivyconfig.write()

# ==============================================================================
# IMPORT REQUIRED CORE KIVY MODULES
# ==============================================================================
from kivy.properties         import ConfigParserProperty, StringProperty
from kivy.properties         import DictProperty, NumericProperty
from kivy.core.window        import Window
from kivy.factory            import Factory
from kivy.logger             import Logger
from kivy.clock              import Clock
from kivy.lang               import Builder
from kivy.app                import App

# ==============================================================================
# IMPORT REQUIRED LIBRARY MODULES
# ==============================================================================
from lib.system       import system
from lib.astronomical import astro
from lib.forecast     import forecast
from lib.sager        import sager_forecast
from lib.status       import station
from lib              import settings     as userSettings
from lib              import properties
from lib              import config

# ==============================================================================
# IMPORT REQUIRED PANELS
# ==============================================================================
from panels.temperature import TemperaturePanel,   TemperatureButton            # type: ignore # noqa: F401
from panels.barometer   import BarometerPanel,     BarometerButton              # type: ignore # noqa: F401
from panels.lightning   import LightningPanel,     LightningButton              # type: ignore # noqa: F401
from panels.wind        import WindSpeedPanel,     WindSpeedButton              # type: ignore # noqa: F401
from panels.forecast    import ForecastPanel,      ForecastButton               # type: ignore # noqa: F401
from panels.forecast    import SagerPanel,         SagerButton                  # type: ignore # noqa: F401
from panels.rainfall    import RainfallPanel,      RainfallButton               # type: ignore # noqa: F401
from panels.astro       import SunriseSunsetPanel, SunriseSunsetButton          # type: ignore # noqa: F401
from panels.astro       import MoonPhasePanel,     MoonPhaseButton              # type: ignore # noqa: F401
from panels.menu        import mainMenu

# ==============================================================================
# IMPORT CUSTOM USER PANELS
# ==============================================================================
if Path('user/customPanels.py').is_file():
    from user.customPanels import *                                              # noqa: F401,F403

# ==============================================================================
# IMPORT REQUIRED SYSTEM MODULES
# ==============================================================================
from runpy         import run_path
import subprocess
import threading

# ==============================================================================
# IMPORT REQUIRED KIVY GRAPHICAL AND SETTINGS MODULES
# ==============================================================================
from kivy.uix.screenmanager  import ScreenManager, Screen, NoTransition
from kivy.uix.settings       import SettingsWithSidebar


# ==============================================================================
# DEFINE 'WeatherFlowPiConsole' APP CLASS
# ==============================================================================
class wfpiconsole(App):

    # Define App class dictionary properties
    Sched = DictProperty([])

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

        # Load Custom Panel KV file if present
        if Path('user/customPanels.py').is_file():
            Builder.load_file('user/customPanels.kv')

        # Initialise ScreenManager
        self.screenManager = screenManager(transition=NoTransition())
        self.screenManager.add_widget(CurrentConditions())

        # Start Websocket service
        self.startWebsocketService()

        # Check for latest version
        self.system = system()
        Clock.schedule_once(self.system.check_version)

        # Set Settings syle class
        self.settings_cls = SettingsWithSidebar

        # Initialise realtime clock
        self.Sched.realtimeClock = Clock.schedule_interval(self.system.realtimeClock, 1.0)

        # Return ScreenManager
        return self.screenManager

    # SET DISPLAY SCALE FACTOR BASED ON SCREEN DIMENSIONS
    # --------------------------------------------------------------------------
    def setScaleFactor(self, instance, x, y):
        self.scaleFactor = min(x / 800, y / 480)
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
        settings.register_type('ScrollOptions',     userSettings.ScrollOptions)
        settings.register_type('FixedOptions',      userSettings.FixedOptions)
        settings.register_type('ToggleTemperature', userSettings.ToggleTemperature)
        settings.register_type('ToggleHours',       userSettings.ToggleHours)

        # Add required panels to setting screen. Remove Kivy settings panel
        settings.add_json_panel('Display',          self.config, data=userSettings.JSON('Display'))
        settings.add_json_panel('Primary Panels',   self.config, data=userSettings.JSON('Primary'))
        settings.add_json_panel('Secondary Panels', self.config, data=userSettings.JSON('Secondary'))
        settings.add_json_panel('Units',            self.config, data=userSettings.JSON('Units'))
        settings.add_json_panel('Feels Like',       self.config, data=userSettings.JSON('FeelsLike'))
        settings.add_json_panel('System',           self.config, data=userSettings.JSON('System'))
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
            self.forecast.parse_forecast()
            self.sager.get_forecast_text()

        # Update current weather forecast, sunrise/sunset and moonrise/moonset
        # times when time format changed
        if section == 'Display' and key in 'TimeFormat':
            self.forecast.parse_forecast()
            self.astro.format_labels('Sun')
            self.astro.format_labels('Moon')

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
                            if isinstance(item, Factory.ToggleTemperature):
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
            panel_list = ['panel_' + Num for Num in ['one', 'two', 'three', 'four', 'five', 'six']]
            for ii, (panel, type) in enumerate(self.config['PrimaryPanels'].items()):
                if panel == key:
                    old_panel = self.CurrentConditions.ids[panel_list[ii]].children[0]
                    self.CurrentConditions.ids[panel_list[ii]].clear_widgets()
                    self.CurrentConditions.ids[panel_list[ii]].add_widget(eval(type + 'Panel')())
                    break
            if hasattr(self, old_panel.__class__.__name__):
                try:
                    getattr(self,  old_panel.__class__.__name__).remove(old_panel)
                except ValueError:
                    Logger.warning('Unable to remove panel reference from wfpiconsole class')

        # Update button layout displayed on CurrentConditions screen
        if section == 'SecondaryPanels':
            self.CurrentConditions.button_list = []
            button_list = ['button_' + Num for Num in ['one', 'two', 'three', 'four', 'five', 'six']]
            button_number = 0
            for button in button_list:
                self.CurrentConditions.ids[button].clear_widgets()
            for ii, (panel, type) in enumerate(self.config['SecondaryPanels'].items()):
                if type and type != 'None':
                    self.CurrentConditions.ids[button_list[button_number]].add_widget(eval(type + 'Button')())
                    self.CurrentConditions.button_list.append([button_list[button_number], panel_list[ii], type, 'Primary'])
                    button_number += 1

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
            Clock.schedule_once(self.sager.schedule_forecast)

        # Update derived variables to reflect configuration changes
        self.obsParser.reformat_display()

    # START WEBSOCKET SERVICE
    # --------------------------------------------------------------------------
    def startWebsocketService(self, *largs):
        self.websocket_thread = threading.Thread(target=run_path,
                                                 args=['service/websocket.py'],
                                                 kwargs={'run_name': '__main__'},
                                                 daemon=True,
                                                 name='Websocket')
        self.websocket_thread.start()

    # STOP WEBSOCKET SERVICE
    # --------------------------------------------------------------------------
    def stopWebsocketService(self):
        self.websocket_client._keep_running = False
        self.websocket_thread.join()
        del self.websocket_client

    # EXIT CONSOLE AND SHUTDOWN SYSTEM
    # --------------------------------------------------------------------------
    def shutdown_system(self):
        global SHUTDOWN
        SHUTDOWN = 1
        self.stop()

    # EXIT CONSOLE AND REBOOT SYSTEM
    # --------------------------------------------------------------------------
    def reboot_system(self):
        global REBOOT
        REBOOT = 1
        self.stop()


# ==============================================================================
# screenManager CLASS
# ==============================================================================
class screenManager(ScreenManager):
    pass


# ==============================================================================
# CurrentConditions CLASS
# ==============================================================================
class CurrentConditions(Screen):

    System = DictProperty()
    Status = DictProperty()
    Sager  = DictProperty()
    Astro  = DictProperty()
    Obs    = DictProperty()
    Met    = DictProperty()

    def __init__(self, **kwargs):
        super(CurrentConditions, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.app.CurrentConditions = self
        self.System = properties.System()
        self.Status = properties.Status()
        self.Sager  = properties.Sager()
        self.Astro  = properties.Astro()
        self.Met    = properties.Met()
        self.Obs    = properties.Obs()

        # Add display panels
        self.addPanels()

        # Schedule Station.getDeviceStatus to be called each second
        self.app.station = station()
        self.app.Sched.deviceStatus = Clock.schedule_interval(self.app.station.get_device_status, 1.0)

        # Initialise Sunrise, Sunset, Moonrise and Moonset times
        self.app.astro = astro()
        self.app.astro.sunrise_sunset()
        self.app.astro.moonrise_moonset()

        # Schedule sunTransit and moonPhase functions to be called each second
        self.app.Sched.sun_transit = Clock.schedule_interval(self.app.astro.sun_transit, 1)
        self.app.Sched.moon_phase  = Clock.schedule_interval(self.app.astro.moon_phase, 1)

        # Schedule WeatherFlow weather forecast download
        self.app.forecast = forecast()
        self.app.Sched.metDownload = Clock.schedule_once(self.app.forecast.fetch_forecast)

        # Generate Sager Weathercaster forecast
        self.app.sager = sager_forecast()
        self.app.Sched.sager = Clock.schedule_once(self.app.sager.fetch_forecast)

    # ADD USER SELECTED PANELS TO CURRENT CONDITIONS SCREEN
    # --------------------------------------------------------------------------
    def addPanels(self):

        # Add primary panels to CurrentConditions screen
        panel_list = ['panel_' + Num for Num in ['one', 'two', 'three', 'four', 'five', 'six']]
        for ii, (Panel, Type) in enumerate(self.app.config['PrimaryPanels'].items()):
            self.ids[panel_list[ii]].add_widget(eval(Type + 'Panel')())

        # Add secondary panel buttons to CurrentConditions screen
        self.button_list = []
        button_list = ['button_' + Num for Num in ['one', 'two', 'three', 'four', 'five', 'six']]
        button_number = 0
        for ii, (Panel, Type) in enumerate(self.app.config['SecondaryPanels'].items()):
            if Type:
                self.ids[button_list[button_number]].add_widget(eval(Type + 'Button')())
                self.button_list.append([button_list[button_number], panel_list[ii], Type, 'Primary'])
                button_number += 1

    # SWITCH BETWEEN PRIMARY AND SECONDARY PANELS ON CURRENT CONDITIONS SCREEN
    # --------------------------------------------------------------------------
    def switchPanel(self, button_pressed, button_overide=None):

        # Determine ID of button that has been pressed and extract corresponding
        # entry in buttonList
        if button_pressed:
            for id, Object in self.ids.items():
                if Object == button_pressed.parent.parent:
                    break
        else:
            id = button_overide[0]
        for ii, button in enumerate(self.button_list):
            if button[0] == id:
                break

        # Extract panel object that corresponds to the button that has been
        # pressed and determine new button type required
        panel_object = self.ids[button[1]].children
        panel_number = 'Panel' + button[1].split('_')[1].title()
        panel_type   = button[3] + 'Panels'
        new_button   = self.app.config[panel_type][panel_number]

        # Destroy reference to old panel class attribute
        if hasattr(self.app, new_button + 'Panel'):
            try:
                getattr(self.app, new_button + 'Panel').remove(panel_object[0])
            except ValueError:
                Logger.warning('Unable to remove panel reference from wfpiconsole class')

        # Switch panel
        self.ids[button[1]].clear_widgets()
        self.ids[button[1]].add_widget(eval(button[2] + 'Panel')())
        self.ids[button[0]].clear_widgets()
        self.ids[button[0]].add_widget(eval(new_button + 'Button')())

        # Update button list
        if button[3] == 'Primary':
            self.button_list[ii] = [button[0], button[1], new_button, 'Secondary']
        elif button[3] == 'Secondary':
            self.button_list[ii] = [button[0], button[1], new_button, 'Primary']


# ==============================================================================
# RUN APP
# ==============================================================================
if __name__ == '__main__':
    try:
        wfpiconsole().run()
        if REBOOT:
            subprocess.call('sudo shutdown -r now', shell=True)
        elif SHUTDOWN:
            subprocess.call('sudo shutdown -h now', shell=True)
    except KeyboardInterrupt:
        wfpiconsole().stop()
