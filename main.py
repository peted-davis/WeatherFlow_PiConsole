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
# SET KIVY_LOG_MODE TO MIXED
# ==============================================================================
# Import required modules
import os

# Set KIVY_LOG_MODE environment variable
os.environ['KIVY_LOG_MODE'] = 'MIXED'

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

# Load wfpiconsole.ini config file
config = configparser.ConfigParser()
config.read('wfpiconsole.ini')

# Initialise Kivy backend based on current hardware
if config['System']['Hardware'] != 'Other':
    os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '1'
    os.environ['KIVY_GRAPHICS'] = 'gles'
    os.environ['KIVY_WINDOW']   = 'sdl2'

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
if config['Display']['Fullscreen'] == '1':
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
# Initialise mouse support if required
if int(config['Display']['Cursor']):
    kivyconfig.set('graphics', 'show_cursor', '1')
    if 'Pi' in config['System']['Hardware']:
        kivyconfig.set('input', 'mouse', 'mouse')
        kivyconfig.remove_option('input', 'mtdev_%(name)s')
else:
    kivyconfig.set('graphics', 'show_cursor', '0')
    if 'Pi' in config['System']['Hardware']:
        kivyconfig.remove_option('input', 'mouse')

# Save wfpiconsole Kivy configuration file
kivyconfig.write()

# ==============================================================================
# IMPORT REQUIRED CORE KIVY MODULES
# ==============================================================================
from kivy.uix.boxlayout      import BoxLayout
from kivy.properties         import StringProperty
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
from kivy.uix.settings       import SettingsWithSidebar, SettingBoolean
from kivy.uix.switch         import Switch


# ==============================================================================
# DEFINE 'WeatherFlowPiConsole' APP CLASS
# ==============================================================================
class wfpiconsole(App):

    # Define App class dictionary properties
    Sched = DictProperty([])

    # Define display properties
    scaleFactor = NumericProperty(1)
    scaleSuffix = StringProperty('_lR.png')

    # BUILD 'WeatherFlowPiConsole' APP CLASS
    # --------------------------------------------------------------------------
    def build(self):

        # Calculate initial ScaleFactor and bind self.set_scale_factor to Window
        # on_resize
        self.window = Window
        self.set_scale_factor(self.window, self.window.width, self.window.height)
        self.window.bind(on_resize=self.set_scale_factor)
        from kivy.modules import inspector
        inspector.create_inspector(Window, self)

        # Load Custom Panel KV file if present
        if Path('user/customPanels.py').is_file():
            Builder.load_file('user/customPanels.kv')

        # Initialise ScreenManager
        self.screenManager = screenManager(transition=NoTransition())
        self.screenManager.add_widget(CurrentConditions())

        # Start Websocket or UDP service
        self.start_connection_service()

        # Check for latest version
        self.system = system()
        Clock.schedule_once(self.system.check_version)

        # Set Settings syle class
        self.settings_cls = SettingsWithSidebar

        # Initialise realtime clock
        self.Sched.realtimeClock = Clock.schedule_interval(self.system.realtimeClock, 1.0)

        # Return ScreenManager
        return self.screenManager

    # DISCONNECT connection_client WHEN CLOSING APP
    # --------------------------------------------------------------------------
    def on_stop(self):
        self.stop_connection_service()

    # SET DISPLAY SCALE FACTOR BASED ON SCREEN DIMENSIONS
    # --------------------------------------------------------------------------
    def set_scale_factor(self, instance, x, y):
        self.scaleFactor = min(x / 800, y / 480)
        if self.scaleFactor > 1 or int(self.config['Display']['PanelCount']) < 6:
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
        if section == 'Display' and key == 'TimeFormat':
            self.forecast.parse_forecast()
            self.astro.format_labels('Sun')
            self.astro.format_labels('Moon')

        # Show or hide indoor temperature when setting is changed
        if section == 'Display' and key == 'IndoorTemp':
            if hasattr(self, 'TemperaturePanel'):
                for panel in getattr(self, 'TemperaturePanel'):
                    panel.set_indoor_temp_display()

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
            if hasattr(self, 'BarometerPanel'):
                for panel in getattr(self, 'BarometerPanel'):
                    panel.set_barometer_max_min()

        # Update number of panels displayed on CurrentConditions screen
        if section == 'Display' and key == 'PanelCount':
            self.set_scale_factor(self.window, self.window.width, self.window.height)
            Clock.schedule_once(self.CurrentConditions.add_panels)

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
            secondary_panels  = tuple(self.config['SecondaryPanels'].items())
            button_list = ['button_' + Num for Num in ['one', 'two', 'three', 'four', 'five', 'six']]
            button_number = 0
            for button in button_list:
                self.CurrentConditions.ids[button].clear_widgets()
            if int(self.config['Display']['PanelCount']) == 1:
                button_ids = ['button_' + number for number in ['one']]
            elif int(self.config['Display']['PanelCount']) == 4:
                button_ids = ['button_' + number for number in ['one',   'two',  'three', 'four']]
            elif int(self.config['Display']['PanelCount']) == 6:
                button_ids = ['button_' + number for number in ['one',   'two',  'three', 'four', 'five', 'six']]
            for ii, button_id in enumerate(button_ids):
                button_type = secondary_panels[ii][1]
                if button_type and button_type != 'None':
                    self.CurrentConditions.ids[button_ids[button_number]].add_widget(eval(button_type + 'Button')())
                    self.CurrentConditions.button_list.append([button_ids[button_number], panel_list[ii], button_type, 'Primary'])
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

        # Force rest_api services if Websocket connection is selected
        if ((section == 'System' and key == 'Connection' and value == 'Websocket')
                or (section == 'System' and key == 'rest_api' and self.config['System']['Connection'] == 'Websocket')):
            if self.config['System']['rest_api'] == '0':
                self.config.set('System', 'rest_api', '1')
                self.config.write()
                panels = self._app_settings.children[0].content.panels
                for panel in panels.values():
                    if panel.title == 'System':
                        for item in panel.children:
                            if isinstance(item, SettingBoolean) and item.title == 'REST API':
                                for child in item.children[0].children:
                                    for child in child.children:
                                        if isinstance(child, Switch):
                                            child.active = True

        # Switch connection type
        if section == 'System' and key == 'Connection':
            self.stop_connection_service()
            self.start_connection_service()

        # Update derived variables to reflect configuration changes
        if hasattr(self, 'obsParser'):
            self.obsParser.reformat_display()

    # START WEBSOCKET OR UDP SERVICE
    # --------------------------------------------------------------------------
    def start_connection_service(self, *largs):
        self.connection_thread = None
        if self.config['System']['Connection'] == 'Websocket':
            self.connection_thread = threading.Thread(target=run_path,
                                                      args=['service/websocket.py'],
                                                      kwargs={'run_name': '__main__'},
                                                      name='Websocket')
        elif self.config['System']['Connection'] == 'UDP':
            self.connection_thread = threading.Thread(target=run_path,
                                                      args=['service/udp.py'],
                                                      kwargs={'run_name': '__main__'},
                                                      name='UDP')
        if self.connection_thread is not None:
            self.connection_thread.start()

    # STOP WEBSOCKET SERVICE
    # --------------------------------------------------------------------------
    def stop_connection_service(self):
        if hasattr(self, 'connection_client'):
            self.connection_client._keep_running = False

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
        self.add_panels()

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
    def add_panels(self, *args):

        # Clear existing panels
        if 'row_layout' in self.ids:
            button_list = ['button_' + Num for Num in ['one', 'two', 'three', 'four', 'five', 'six']]
            for button in button_list:
                self.ids[button].clear_widgets()
            self.ids['row_layout'].clear_widgets()

        # Define required variables
        panel_count  = 0
        button_count = 0
        self.button_list = []
        primary_panels    = tuple(self.app.config['PrimaryPanels'].items())
        secondary_panels  = tuple(self.app.config['SecondaryPanels'].items())
        if self.app.config['Display']['PanelCount'] == '1':
            panel_ids = [['panel_'  + number for number in ['one']]]
            button_ids = ['button_' + number for number in ['one']]
        elif self.app.config['Display']['PanelCount'] == '4':
            panel_ids = [['panel_'  + number for number in ['one',   'two']],
                         ['panel_'  + number for number in ['three', 'four']]]
            button_ids = ['button_' + number for number in ['one',   'two',  'three', 'four']]
        elif self.app.config['Display']['PanelCount'] == '6':
            panel_ids = [['panel_'  + number for number in ['one',   'two',  'three']],
                         ['panel_'  + number for number in ['four',  'five', 'six']]]
            button_ids = ['button_' + number for number in ['one',   'two',  'three', 'four', 'five', 'six']]

        # Add primary panels to screen and initialise required buttons
        for row in range(len(panel_ids)):
            row_box_layout = BoxLayout(spacing='5dp')
            self.ids['row_layout'].add_widget(row_box_layout)
            for panel_id in panel_ids[row]:
                button_id   = button_ids[button_count]
                panel_type  = primary_panels[panel_count][1]
                button_type = secondary_panels[panel_count][1]
                self.ids[panel_id] = BoxLayout()
                self.ids[panel_id].add_widget(eval(panel_type + 'Panel')())
                row_box_layout.add_widget(self.ids[panel_id])
                if button_type:
                    self.ids[button_id].add_widget(eval(button_type + 'Button')())
                    self.button_list.append([button_id, panel_id, button_type, 'Primary'])
                    button_count += 1
                panel_count += 1

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
        wfpiconsole_app = wfpiconsole()
        wfpiconsole_app.run()
        if REBOOT:
            subprocess.call('sudo shutdown -r now', shell=True)
        elif SHUTDOWN:
            subprocess.call('sudo shutdown -h now', shell=True)
    except KeyboardInterrupt:
        wfpiconsole_app.stop()
    except Exception:
        wfpiconsole_app.stop()
        raise
