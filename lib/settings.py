""" Defines the settings screen JSON object required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2021 Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

# Import required modules
import json

def JSON(Section):

    """ Defines the settings screen JSON object for specified section

    INPUTS
        Section             Settings section

    OUTPUTS
        Data                JSON object containing settings for specified
                            section
    """

    if 'Display' in Section:
        Data =  [
                 {'type':'FixedOptions', 'options':['24 hr','12 hr'],
                  'title':'Time format', 'desc':'Set time to display in 12 hr or 24 hr format', 'section':'Display', 'key':'TimeFormat'},
                 {'type':'FixedOptions', 'options':['Mon, 01 Jan 0000','Mon, Jan 01 0000','Monday, 01 Jan 0000','Monday, Jan 01 0000'],
                  'title':'Date format', 'desc':'Set date format', 'section':'Display', 'key':'DateFormat'},
                 {'type': 'bool', 'desc': 'Switch to lightning panel when a strike is detected',
                  'title': 'Lightning panel','section': 'Display', 'key': 'LightningPanel'},
                 {'type': 'bool', 'desc': 'Show indoor temperature',
                  'title': 'Indoor temperature','section': 'Display', 'key': 'IndoorTemp'},
                 {'type': 'bool', 'desc': 'Show cursor',
                  'title': 'Cursor','section': 'Display', 'key': 'Cursor'},
                 {'type': 'bool', 'desc': 'Set console to run fullscreen',
                  'title': 'Fullscreen','section': 'Display', 'key': 'Fullscreen'},
                 {'type': 'bool', 'desc': 'Display console window with border',
                  'title': 'Border','section': 'Display', 'key': 'Border'}
                ]
    elif 'Units' in Section:
        Data =  [
                 {'type':'FixedOptions', 'options':['c','f'],'title':'Temperature',
                  'desc':'Set console temperature units', 'section':'Units', 'key':'Temp'},
                 {'type':'FixedOptions', 'options':['inhg','mmhg','hpa','mb'],'title':'Pressure',
                  'desc':'Set console pressure units', 'section':'Units', 'key':'Pressure'},
                 {'type':'ScrollOptions', 'options':['mph','kph','kts','bft','mps','lfm'],'title':'Wind speed',
                  'desc':'Set console wind speed units', 'section':'Units', 'key':'Wind'},
                 {'type':'FixedOptions', 'options':['degrees','cardinal'],'title':'Wind direction',
                  'desc':'Set console wind direction units', 'section':'Units', 'key':'Direction'},
                 {'type':'FixedOptions', 'options':['in','cm','mm'],'title':'Rainfall',
                  'desc':'Set console rainfall units', 'section':'Units', 'key':'Precip'},
                 {'type':'FixedOptions', 'options':['km','mi'],'title':'Distance',
                  'desc':'Set console distance units', 'section':'Units', 'key':'Distance'},
                 {'type':'FixedOptions', 'options':['metric','imperial'],'title':'Other',
                  'desc':'Set console other units', 'section':'Units', 'key':'Other'}
                ]
    elif 'Primary' in Section:
        Data =  [
                 {'type':'ScrollOptions', 'options':['Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel One',
                  'desc':'Set primary display for Panel One', 'section':'PrimaryPanels', 'key':'PanelOne'},
                 {'type':'ScrollOptions', 'options':['Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Two',
                  'desc':'Set primary display for Panel Two', 'section':'PrimaryPanels', 'key':'PanelTwo'},
                 {'type':'ScrollOptions', 'options':['Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Three',
                  'desc':'Set primary display for Panel Three', 'section':'PrimaryPanels', 'key':'PanelThree'},
                 {'type':'ScrollOptions', 'options':['Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Four',
                  'desc':'Set primary display for Panel Four', 'section':'PrimaryPanels', 'key':'PanelFour'},
                 {'type':'ScrollOptions', 'options':['Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Five',
                  'desc':'Set primary display for Panel Five', 'section':'PrimaryPanels', 'key':'PanelFive'},
                 {'type':'ScrollOptions', 'options':['Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Six',
                  'desc':'Set primary display for Panel Six', 'section':'PrimaryPanels', 'key':'PanelSix'}
                ]
    elif 'Secondary' in Section:
        Data =  [
                 {'type':'ScrollOptions', 'options':['None','Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel One',
                  'desc':'Set secondary display for Panel One', 'section':'SecondaryPanels', 'key':'PanelOne'},
                 {'type':'ScrollOptions', 'options':['None','Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Two',
                  'desc':'Set secondary display for Panel Two', 'section':'SecondaryPanels', 'key':'PanelTwo'},
                 {'type':'ScrollOptions', 'options':['None','Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Three',
                  'desc':'Set secondary display for Panel Three', 'section':'SecondaryPanels', 'key':'PanelThree'},
                 {'type':'ScrollOptions', 'options':['None','Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Four',
                  'desc':'Set secondary display for Panel Four', 'section':'SecondaryPanels', 'key':'PanelFour'},
                 {'type':'ScrollOptions', 'options':['None','Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Five',
                  'desc':'Set secondary display for Panel Five', 'section':'SecondaryPanels', 'key':'PanelFive'},
                 {'type':'ScrollOptions', 'options':['None','Forecast','Sager','Temperature','WindSpeed','SunriseSunset','MoonPhase','Rainfall','Lightning','Barometer'],'title':'Panel Six',
                  'desc':'Set secondary display for Panel Six', 'section':'SecondaryPanels', 'key':'PanelSix'}
                ]
    elif 'FeelsLike' in Section:
        Data =  [
                 {'type':'ToggleTemperature', 'title':'Extremely Cold',
                  'desc':'Set the maximum temperature for "Feeling extremely cold"', 'section':'FeelsLike', 'key':'ExtremelyCold'},
                 {'type':'ToggleTemperature', 'title':'Freezing Cold',
                  'desc':'Set the maximum temperature for "Feeling freezing cold"', 'section':'FeelsLike', 'key':'FreezingCold'},
                 {'type':'ToggleTemperature', 'title':'Very Cold',
                  'desc':'Set the maximum temperature for "Feeling very cold"', 'section':'FeelsLike', 'key':'VeryCold'},
                 {'type':'ToggleTemperature', 'title':'Cold',
                  'desc':'Set the maximum temperature for "Feeling cold"', 'section':'FeelsLike', 'key':'Cold'},
                 {'type':'ToggleTemperature', 'title':'Mild',
                  'desc':'Set the maximum temperature for "Feeling mild"', 'section':'FeelsLike', 'key':'Mild'},
                 {'type':'ToggleTemperature', 'title':'Warm',
                  'desc':'Set the maximum temperature for "Feeling warm"', 'section':'FeelsLike', 'key':'Warm'},
                 {'type':'ToggleTemperature', 'title':'Hot',
                  'desc':'Set the maximum temperature for "Feeling hot"', 'section':'FeelsLike', 'key':'Hot'},
                 {'type':'ToggleTemperature', 'title':'Very Hot',
                  'desc':'Set the maximum temperature for "Feeling very hot"', 'section':'FeelsLike', 'key':'VeryHot'}
                ]
    elif 'Station' in Section:
        Data =  [
                 {'type':'string', 'title':'Station ID',
                  'desc':'Set the Station ID', 'section':'Station', 'key':'StationID'},
                 {'type':'string', 'title':'Tempest ID',
                  'desc':'Set the Tempest ID', 'section':'Station', 'key':'TempestID'},
                 {'type':'string', 'title':'Sky ID',
                  'desc':'Set the Sky ID', 'section':'Station', 'key':'SkyID'},
                 {'type':'string', 'title':'Outdoor Air ID',
                  'desc':'Set the Outdoor Air ID', 'section':'Station', 'key':'OutAirID'},
                 {'type':'string', 'title':'Indoor Air ID',
                  'desc':'Set the Indoor Air ID', 'section':'Station', 'key':'InAirID'}
                ]

    # Returns JSON object for settings section
    return json.dumps(Data)