""" Defines the settings screen JSON object and custom settings types required
by the Raspberry Pi Python console for WeatherFlow Tempest and Smart Home
Weather stations.
Copyright (C) 2018-2023 Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http: //www.gnu.org/licenses/>.
"""

# Import required core kivy modules
from kivy.metrics            import dp, sp
from kivy.app                import App

# Import required Kivy settings modules
from kivy.uix.togglebutton   import ToggleButton
from kivy.uix.scrollview     import ScrollView
from kivy.uix.gridlayout     import GridLayout
from kivy.uix.boxlayout      import BoxLayout
from kivy.uix.settings       import SettingOptions
from kivy.uix.settings       import SettingString, SettingSpacer
from kivy.uix.button         import Button
from kivy.uix.widget         import Widget
from kivy.uix.popup          import Popup
from kivy.uix.label          import Label

# Import required modules
from pathlib    import Path
import inspect
import json

# Import required user modules
if Path('user/customPanels.py').is_file():
    import user.customPanels

# Define panel list including custom user panels if required
customPanels = []
if Path('user/customPanels.py').is_file():
    for cls in inspect.getmembers(user.customPanels, inspect.isclass):
        if cls[1].__module__ == 'user.customPanels' and 'Panel' in cls[0]:
            customPanels.append(cls[0].split('Panel')[0])
PanelList = ['Forecast', 'Sager', 'Temperature', 'WindSpeed', 'SunriseSunset', 'MoonPhase', 'Rainfall', 'Lightning', 'Barometer']
primaryPanelList = PanelList + customPanels
secondaryPanelList = ['None'] + PanelList + customPanels


class ScrollOptions(SettingOptions):

    """ Define the ScrollOptions settings type """

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


class FixedOptions(SettingOptions):

    """ Define the FixedOptions settings type """

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


class SettingToggle(SettingString):

    """ Define the base class for the SettingToggle settings type """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _create_popup(self, instance):

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
        self._set_unit()
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
        value = int(self.Label.text.replace(self.units, '')) - 1
        self.Label.text = str(value) + self.units

    def _plus_value(self, instance):
        value = int(self.Label.text.replace(self.units, '')) + 1
        self.Label.text = str(value) + self.units


class ToggleTemperature(SettingToggle):

    """ Define the ToggleTemperature settings type """

    def _set_unit(self):
        self.units = '[sup]o[/sup]' + App.get_running_app().config['Units']['Temp'].upper()


class ToggleHours(SettingToggle):

    """ Define the ToggleHours settings type """

    def _set_unit(self):
        self.units = ' hours'

class ToggleMinutes(SettingToggle):

    """ Define the ToggleHours settings type """

    def _set_unit(self):
        self.units = ' minutes'

    def _minus_value(self, instance):
        value = max(int(self.Label.text.replace(self.units, '')) - 1, 0)
        self.Label.text = str(value) + self.units


def JSON(Section):

    """ Define the settings screen JSON object for specified section

    INPUTS
        Section             Settings section

    OUTPUTS
        Data                JSON object containing settings for specified
                            section
    """

    if 'Display' in Section:
        Data =  [{'type': 'FixedOptions', 'options': ['24 hr', '12 hr'],
                  'title': 'Time format', 'desc': 'Set time to display in 12 hr or 24 hr format', 'section': 'Display', 'key': 'TimeFormat'},
                 {'type': 'FixedOptions', 'options': ['Mon, 01 Jan 0000', 'Mon, Jan 01 0000', 'Monday, 01 Jan 0000', 'Monday, Jan 01 0000'],
                  'title': 'Date format', 'desc': 'Set date format', 'section': 'Display', 'key': 'DateFormat'},
                 {'type': 'bool', 'desc': 'Show a notification when an update is available',
                  'title': 'Update Notification', 'section': 'Display', 'key': 'UpdateNotification'},
                 {'type': 'FixedOptions', 'options': ['1', '4', '6'],
                  'title': 'Number of panels', 'desc': 'Set the number of display panels', 'section': 'Display', 'key': 'PanelCount'},
                 {'type': 'bool', 'desc': 'Switch to lightning panel when a strike is detected',
                  'title': 'Lightning panel', 'section': 'Display', 'key': 'LightningPanel'},
                 {'type': 'ToggleMinutes', 'desc': 'Lightning panel timeout after strike is detected',
                  'title': 'Lightning timeout', 'section': 'Display', 'key': 'lightning_timeout'},
                 {'type': 'bool', 'desc': 'Show indoor temperature',
                  'title': 'Indoor temperature', 'section': 'Display', 'key': 'IndoorTemp'},
                 {'type': 'bool', 'desc': 'Show cursor',
                  'title': 'Cursor', 'section': 'Display', 'key': 'Cursor'},
                 {'type': 'bool', 'desc': 'Set console to run fullscreen',
                  'title': 'Fullscreen', 'section': 'Display', 'key': 'Fullscreen'},
                 {'type': 'bool', 'desc': 'Display console window with border',
                  'title': 'Border', 'section': 'Display', 'key': 'Border'}
                 ]
    elif 'Units' in Section:
        Data =  [{'type': 'FixedOptions', 'options': ['c', 'f'], 'title': 'Temperature',
                  'desc': 'Set console temperature units', 'section': 'Units', 'key': 'Temp'},
                 {'type': 'FixedOptions', 'options': ['inhg', 'mmhg', 'hpa', 'mb'], 'title': 'Pressure',
                  'desc': 'Set console pressure units', 'section': 'Units', 'key': 'Pressure'},
                 {'type': 'ScrollOptions', 'options': ['mph', 'kph', 'kts', 'bft', 'mps', 'lfm'], 'title': 'Wind speed',
                  'desc': 'Set console wind speed units', 'section': 'Units', 'key': 'Wind'},
                 {'type': 'FixedOptions', 'options': ['degrees', 'cardinal'], 'title': 'Wind direction',
                  'desc': 'Set console wind direction units', 'section': 'Units', 'key': 'Direction'},
                 {'type': 'FixedOptions', 'options': ['in', 'cm', 'mm'], 'title': 'Rainfall',
                  'desc': 'Set console rainfall units', 'section': 'Units', 'key': 'Precip'},
                 {'type': 'FixedOptions', 'options': ['km', 'mi'], 'title': 'Distance',
                  'desc': 'Set console distance units', 'section': 'Units', 'key': 'Distance'},
                 {'type': 'FixedOptions', 'options': ['metric', 'imperial'], 'title': 'Other',
                  'desc': 'Set console other units', 'section': 'Units', 'key': 'Other'}
                 ]
    elif 'Primary' in Section:
        Data =  [{'type': 'ScrollOptions', 'options': primaryPanelList, 'title': 'Panel One',
                  'desc': 'Set primary display for Panel One', 'section': 'PrimaryPanels', 'key': 'PanelOne'},
                 {'type': 'ScrollOptions', 'options': primaryPanelList, 'title': 'Panel Two',
                  'desc': 'Set primary display for Panel Two', 'section': 'PrimaryPanels', 'key': 'PanelTwo'},
                 {'type': 'ScrollOptions', 'options': primaryPanelList, 'title': 'Panel Three',
                  'desc': 'Set primary display for Panel Three', 'section': 'PrimaryPanels', 'key': 'PanelThree'},
                 {'type': 'ScrollOptions', 'options': primaryPanelList, 'title': 'Panel Four',
                  'desc': 'Set primary display for Panel Four', 'section': 'PrimaryPanels', 'key': 'PanelFour'},
                 {'type': 'ScrollOptions', 'options': primaryPanelList, 'title': 'Panel Five',
                  'desc': 'Set primary display for Panel Five', 'section': 'PrimaryPanels', 'key': 'PanelFive'},
                 {'type': 'ScrollOptions', 'options': primaryPanelList, 'title': 'Panel Six',
                  'desc': 'Set primary display for Panel Six', 'section': 'PrimaryPanels', 'key': 'PanelSix'}
                 ]
    elif 'Secondary' in Section:
        Data =  [{'type': 'ScrollOptions', 'options': secondaryPanelList, 'title': 'Panel One',
                  'desc': 'Set secondary display for Panel One', 'section': 'SecondaryPanels', 'key': 'PanelOne'},
                 {'type': 'ScrollOptions', 'options': secondaryPanelList, 'title': 'Panel Two',
                  'desc': 'Set secondary display for Panel Two', 'section': 'SecondaryPanels', 'key': 'PanelTwo'},
                 {'type': 'ScrollOptions', 'options': secondaryPanelList, 'title': 'Panel Three',
                  'desc': 'Set secondary display for Panel Three', 'section': 'SecondaryPanels', 'key': 'PanelThree'},
                 {'type': 'ScrollOptions', 'options': secondaryPanelList, 'title': 'Panel Four',
                  'desc': 'Set secondary display for Panel Four', 'section': 'SecondaryPanels', 'key': 'PanelFour'},
                 {'type': 'ScrollOptions', 'options': secondaryPanelList, 'title': 'Panel Five',
                  'desc': 'Set secondary display for Panel Five', 'section': 'SecondaryPanels', 'key': 'PanelFive'},
                 {'type': 'ScrollOptions', 'options': secondaryPanelList, 'title': 'Panel Six',
                  'desc': 'Set secondary display for Panel Six', 'section': 'SecondaryPanels', 'key': 'PanelSix'}
                 ]
    elif 'FeelsLike' in Section:
        Data =  [{'type': 'ToggleTemperature', 'title': 'Extremely Cold',
                  'desc': 'Set the maximum temperature for "Feeling extremely cold"', 'section': 'FeelsLike', 'key': 'ExtremelyCold'},
                 {'type': 'ToggleTemperature', 'title': 'Freezing Cold',
                  'desc': 'Set the maximum temperature for "Feeling freezing cold"', 'section': 'FeelsLike', 'key': 'FreezingCold'},
                 {'type': 'ToggleTemperature', 'title': 'Very Cold',
                  'desc': 'Set the maximum temperature for "Feeling very cold"', 'section': 'FeelsLike', 'key': 'VeryCold'},
                 {'type': 'ToggleTemperature', 'title': 'Cold',
                  'desc': 'Set the maximum temperature for "Feeling cold"', 'section': 'FeelsLike', 'key': 'Cold'},
                 {'type': 'ToggleTemperature', 'title': 'Mild',
                  'desc': 'Set the maximum temperature for "Feeling mild"', 'section': 'FeelsLike', 'key': 'Mild'},
                 {'type': 'ToggleTemperature', 'title': 'Warm',
                  'desc': 'Set the maximum temperature for "Feeling warm"', 'section': 'FeelsLike', 'key': 'Warm'},
                 {'type': 'ToggleTemperature', 'title': 'Hot',
                  'desc': 'Set the maximum temperature for "Feeling hot"', 'section': 'FeelsLike', 'key': 'Hot'},
                 {'type': 'ToggleTemperature', 'title': 'Very Hot',
                  'desc': 'Set the maximum temperature for "Feeling very hot"', 'section': 'FeelsLike', 'key': 'VeryHot'}
                 ]
    elif 'System' in Section:
        Data =  [{'type': 'FixedOptions', 'options': ['Websocket', 'UDP'], 'title': 'Connection',
                  'desc': 'Set the console connection type', 'section': 'System', 'key': 'Connection'},
                 {'type': 'bool', 'desc': 'Use the WeatherFlow REST API to fetch data & forecast',
                  'title': 'REST API', 'section': 'System', 'key': 'rest_api'},
                 {'type': 'bool', 'desc': 'Use the Statistics API to fetch rain accumulation',
                  'title': 'Statistics API endpoint', 'section': 'System', 'key': 'stats_endpoint'}, 
                 {'type': 'ToggleHours', 'title': 'Sager Forecast interval',
                  'desc': 'Set the interval in hours between Sager Forecasts', 'section': 'System', 'key': 'SagerInterval'},
                 ]

    # Returns JSON object for settings section
    return json.dumps(Data)
