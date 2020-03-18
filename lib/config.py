""" Defines the configuration .ini files required by the Raspberry Pi Python
console for Weather Flow Smart Home Weather Stations.
Copyright (C) 2018-2019  Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# Import required modules
from geopy          import distance as geopy
from packaging      import version
from pathlib        import Path
import configparser
import collections
import requests
import json
import math
import sys
import os

# Define wfpiconsole version number
Version = 'v3.0'

# Define required variables
TEMPEST       = False
INDOORAIR     = False
STATION     = None
OBSERVATION = None
GEONAMES      = None
METOFFICE     = None
NaN           = float('NaN')

# Determine hardware version
try:
    Hardware = os.popen("cat /proc/device-tree/model").read()
    if "Raspberry Pi 4" in Hardware:
        Hardware = "Pi4"
    elif "Raspberry Pi 3" in Hardware:
        Hardware = "Pi3"
    else:
        Hardware = "Other"
except:
    Hardware = "Other"

def create():

    """ Generates a new user configuration file from the default configuration
        dictionary. Saves the new user configuration file to wfpiconsole.ini
    """

    # Load default configuration dictionary
    defaultINI = defaultConfig()

    # CONVERT DEFAULT CONFIGURATION DICTIONARY INTO .ini FILE
    # --------------------------------------------------------------------------
    # Print progress dialogue to screen
    print('')
    print('  ===================================================')
    print('  Starting wfpiconsole configuration wizard          ')
    print('  ===================================================')
    print('')
    print('  Required fields are marked with an asterix (*)     ')
    print('')

    # Open new user configuration file
    Config = configparser.ConfigParser(allow_no_value=True)
    Config.optionxform = str

    # Loop through all sections in default configuration dictionary
    for Section in defaultINI:

        # Add section to user configuration file
        Config.add_section(Section)

        # Add remaining sections to user configuration file
        for Key in defaultINI[Section]:
            if Key == 'Description':
                print(defaultINI[Section][Key])
                print('  ---------------------------------')
            else:
                writekeyValue(Config,Section,Key,defaultINI[Section][Key])
        print('')

    # WRITES USER CONFIGURATION FILE TO wfpiconsole.ini
    # --------------------------------------------------------------------------
    with open('wfpiconsole.ini','w') as configfile:
        Config.write(configfile)

def update():

    """ Updates an existing user configuration file by comparing it against the
        default configuration dictionary. Saves the updated user configuration
        file to wfpiconsole.ini
    """

    # Load default configuration dictionary
    defaultINI = defaultConfig()
    defaultVersion = defaultINI['System']['Version']['Value']

    # Load current user configuration file
    currentConfig = configparser.ConfigParser(allow_no_value=True)
    currentConfig.optionxform = str
    currentConfig.read('wfpiconsole.ini')
    currentVersion = currentConfig['System']['Version']

    # Create new config parser object to hold updated user configuration file
    newConfig = configparser.ConfigParser(allow_no_value=True)
    newConfig.optionxform = str

    # CONVERT DEFAULT CONFIGURATION DICTIONARY INTO .ini FILE
    # --------------------------------------------------------------------------
    # Check if version numbers are different
    if version.parse(currentVersion) < version.parse(defaultVersion):
    
        # Print progress dialogue to screen
        print('')
        print('  ===================================================')
        print('  New version detected                               ')
        print('  Starting wfpiconsole configuration wizard          ')
        print('  ===================================================')
        print('')
        print('  Required fields are marked with an asterix (*)     ')
        print('')

        # Loop through all sections in default configuration dictionary. Take 
        # existing key values from current configuration file
        for Section in defaultINI:
            Changes = False
            newConfig.add_section(Section)
            for Key in defaultINI[Section]:
                if Key == 'Description':
                    print(defaultINI[Section][Key])
                    print('  ---------------------------------')
                else:
                    if defaultINI[Section][Key]['Type'] in ['fixed']:
                        newConfig.set(Section,Key,defaultINI[Section][Key]['Value'])
                    if currentConfig.has_option(Section,Key):
                        newConfig.set(Section,Key,currentConfig[Section][Key])
                    if not currentConfig.has_option(Section,Key):
                        Changes = True
                        writekeyValue(newConfig,Section,Key,defaultINI[Section][Key])
                    elif Key == 'Version':
                        newConfig.set(Section,Key,defaultVersion)
                        print('  Updating version number to: ' + defaultVersion)
            if not Changes:
                print('  No changes required')
            print('')

        # WRITE UPDATED USER .INI FILE TO DISK
        # ----------------------------------------------------------------------
        with open('wfpiconsole.ini','w') as configfile:
            newConfig.write(configfile)

def writekeyValue(Config,Section,Key,keyDetails):

    """ Gets and writes the key value pair to the specified section of the
        station configuration file

    INPUTS
        Config              Station configuration
        Section             Section of station configuration containing key
                            value pair
        Key                 Name of key value pair
        keyDetails          Details (type/description) of key value pair

    """

    # Define required variables
    keyRequired = True

    # GET VALUE OF userInput KEY TYPE
    # --------------------------------------------------------------------------
    if keyDetails['Type'] in ['userInput']:

        # Define global variables
        global TEMPEST, INDOORAIR

        # Request user input to determine which modules are present
        if Key == 'TempestID':
            if queryUser('Do you own a Tempest module?*',default=None):
                TEMPEST = True
            else:
                Value = ''
                keyRequired = False
        elif Key == 'InAirID':
            if queryUser('Do you own an Indoor module?*',default=None):
                INDOORAIR = True
            else:
                Value = ''
                keyRequired = False

        # Skip module ID keys for modules that are not present
        if Key == 'SkyID' and TEMPEST:
            Value = ''
            keyRequired = False
        elif Key == 'OutAirID' and TEMPEST:
            Value = ''
            keyRequired = False

        # Get value of userInput key type from user
        while keyRequired:
            if keyDetails['State'] == 'required':
                String = '  Please enter your ' + keyDetails['Desc'] + '*: '
            else:
                String = '  Please enter your ' + keyDetails['Desc'] + ': '
            Value = input(String)
            if not Value and keyDetails['State'] == 'required':
                print('    ' + keyDetails['Desc'] + ' cannot be empty. Please try again.')
                continue
            elif not Value and keyDetails['State'] == 'optional':
                break
            try:
                Value = keyDetails['Format'](Value)
                break
            except ValueError:
                print('    ' + keyDetails['Desc'] + ' not valid. Please try again.')

        # Write userInput Key value pair to configuration file
        Config.set(Section,Key,str(Value))

    # GET VALUE OF dependent KEY TYPE
    # --------------------------------------------------------------------------
    elif keyDetails['Type'] in ['dependent']:

        # Get dependent Key value
        if Key in ['BarometerMax']:
            Units = ['mb','hpa','inhg','mmhg']
            Max = ['1050','1050','31.0','788']
            Value = Max[Units.index(Config['Units']['Pressure'])]
        elif Key in ['BarometerMin']:
            Units = ['mb','hpa','inhg','mmhg']
            Min = ['950','950','28.0','713']
            Value = Min[Units.index(Config['Units']['Pressure'])]
        print('  Adding ' + keyDetails['Desc'] + ': ' + Value)

        # Write dependent Key value pair to configuration file
        Config.set(Section,Key,str(Value))

    # GET VALUE OF default OR fixed KEY TYPE
    # --------------------------------------------------------------------------
    elif keyDetails['Type'] in ['default','fixed']:

        # Get default or fixed Key value
        if Key in ['ExtremelyCold','FreezingCold','VeryCold','Cold','Mild','Warm','Hot','VeryHot']:
            if 'c' in Config['Units']['Temp']:
                Value = keyDetails['Value']
            elif 'f' in Config['Units']['Temp']:
                Value = str(int(float(keyDetails['Value'])*9/5 + 32))
        else:
            Value = keyDetails['Value']

        # Write default or fixed Key value pair to configuration file
        print('  Adding ' + keyDetails['Desc'] + ': ' + Value)
        Config.set(Section,Key,str(Value))

    # GET VALUE OF request KEY TYPE
    # --------------------------------------------------------------------------
    elif keyDetails['Type'] in ['request']:

        # Define global variables
        global STATION
        global OBSERVATION
        global GEONAMES
        global METOFFICE

        # Ensure all necessary API keys have been provided
        if 'Country' in Config['Station']:
            if not Config['Keys']['MetOffice'] and not Config['Keys']['DarkSky']:
                print('      MetOffice and DarkSky API keys cannot both be empty')
                if Config['Station']['Country'] in ['GB']:
                    while True:
                        Value = input('      Station located in UK. Please enter your MetOffice API Key (required): ')
                        if not Value:
                            print('      MetOffice API Key cannot be empty. Please try again..... ')
                            continue
                        break
                    Config.set('Keys','MetOffice',str(Value))
                else:
                    while True:
                        Value = input('      Station located outside UK. Please enter your DarkSky API Key (required): ')
                        if not Value:
                            print('      DarkSky API Key cannot be empty. Please try again..... ')
                            continue
                        break
                    Config.set('Keys','DarkSky',str(Value))

        # Make required API requests
        if keyDetails['Source'] == 'station' and STATION is None:
            while True:
                Template = 'https://swd.weatherflow.com/swd/rest/stations/{}?api_key={}'
                URL = Template.format(Config['Station']['StationID'],Config['Keys']['WeatherFlow'])
                STATION = requests.get(URL).json()
                if 'NOT FOUND' in STATION['status']['status_message']:
                    Value = input('      Station ID not recognised. Please re-enter your Station ID (required): ')
                    Config.set('Station','StationID',str(Value))
                    continue
                elif 'SUCCESS' in STATION['status']['status_message']:
                    break
        elif keyDetails['Source'] == 'observation' and OBSERVATION is None:
            Template = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?api_key={}'
            URL = Template.format(Config['Station']['StationID'],Config['Keys']['WeatherFlow'])
            OBSERVATION = requests.get(URL).json()
        elif keyDetails['Source'] == 'GeoNames' and GEONAMES is None:
            Template = 'http://api.geonames.org/findNearbyPlaceName?lat={}&lng={}&username={}&radius=10&featureClass=P&maxRows=20&type=json'
            URL = Template.format(Config['Station']['Latitude'],Config['Station']['Longitude'],Config['Keys']['GeoNames'])
            GEONAMES = requests.get(URL).json()
        elif keyDetails['Source'] == 'MetOffice' and METOFFICE is None and Config['Station']['Country'] in ['GB']:
            Template = 'http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/json/sitelist?&Key={}'
            header = {'User-Agent': "Magic Browser"}
            URL = Template.format(Config['Keys']['MetOffice'])
            METOFFICE = requests.get(URL,headers=header).json()

        # Get height above ground of TEMPEST module
        if Section == 'Station':
            Value = ''
            if Key == 'TempestHeight' and Config['Station']['TempestID']:
                Value = None
                while True:
                    for Device in STATION['stations'][0]['devices']:
                        if 'device_type' in Device:
                            if str(Device['device_id']) == Config['Station']['TempestID']:
                                if Device['device_type'] == 'ST':
                                    Value = Device['device_meta']['agl']
                    if Value is None:
                        while True:
                            ID = input('    TEMPEST ID not found. Please re-enter your TEMPEST ID: ')
                            if not ID:
                                print('    TEMPEST ID cannot be empty. Please try again..... ')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                print('    TEMPEST ID not valid. Please try again..... ')
                        Config.set('Station','OutdoorID',str(ID))
                    else:
                        break

            # Get height above ground of Outdoor AIR module
            elif Key == 'OutAirHeight' and Config['Station']['OutAirID']:
                Value = None
                while True:
                    for Device in STATION['stations'][0]['devices']:
                        if 'device_type' in Device:
                            if str(Device['device_id']) == Config['Station']['OutAirID']:
                                if Device['device_type'] == 'AR':
                                    Value = Device['device_meta']['agl']
                    if Value is None:
                        while True:
                            ID = input('    Outdoor AIR ID not found. Please re-enter your Outdoor AIR ID: ')
                            if not ID:
                                print('    Outdoor AIR ID cannot be empty. Please try again..... ')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                print('    Outdoor AIR ID not valid. Please try again..... ')
                        Config.set('Station','OutdoorID',str(ID))
                    else:
                        break

            # Get height above ground of SKY module
            elif Key == 'SkyHeight' and Config['Station']['SkyID']:
                Value = None
                while True:
                    for Device in STATION['stations'][0]['devices']:
                        if 'device_type' in Device:
                            if str(Device['device_id']) == Config['Station']['SkyID']:
                                if Device['device_type'] == 'SK':
                                    Value = Device['device_meta']['agl']
                    if Value is None:
                        while True:
                            ID = input('    SKY module ID not found. Please re-enter your SKY module ID: ')
                            if not ID:
                                print('    SKY module ID cannot be empty. Please try again..... ')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                print('      SKY module ID not valid. Please try again..... ')
                        Config.set('Station','SkyID',str(ID))
                    else:
                        break

            # Get UK MetOffice forecast location
            elif Key in ['ForecastLocn','MetOfficeID']:
                if Config['Station']['Country'] in ['GB']:
                    MinDist = math.inf
                    for Locn in METOFFICE['Locations']['Location']:
                        ForecastLocn = (float(Locn['latitude']),float(Locn['longitude']))
                        StationLocn = (float(Config['Station']['Latitude']),float(Config['Station']['Longitude']))
                        LatDiff = abs(StationLocn[0] - ForecastLocn[0])
                        LonDiff = abs(StationLocn[1] - ForecastLocn[1])
                        if (LatDiff and LonDiff) < 0.5:
                            Dist = geopy.distance(StationLocn,ForecastLocn).km
                            if Dist < MinDist:
                                MinDist = Dist
                                if Key in ['ForecastLocn']:
                                    Value = Locn['name']
                                elif Key in ['MetOfficeID']:
                                    Value = Locn['id']

                # Get DarkSky forecast location
                else:
                    if Key in ['ForecastLocn']:
                        Locns = [Item['name'] for Item in GEONAMES['geonames']]
                        Len = [len(Item) for Item in Locns]
                        Ind = next((Item for Item in Len if Item<=20),NaN)
                        if Ind != NaN:
                            Value = Locns[Len.index(Ind)]
                        else:
                            Value = ''
                    elif Key in ['MetOfficeID']:
                        Value = ''

            # Get station latitude/longitude
            elif Key in ['Latitude','Longitude']:
                Value = STATION['stations'][0][Key.lower()]

            # Get station timezone
            elif Key in ['Timezone']:
                Value = STATION['stations'][0]['timezone']

            # Get station elevation
            elif Key in ['Elevation']:
                Value = STATION['stations'][0]['station_meta']['elevation']

            # Get station country code
            elif Key in ['Country']:
                Value = GEONAMES['geonames'][0]['countryCode']

        # Get station units
        elif Section in ['Units']:
            Value = OBSERVATION['station_units']['units_' + Key.lower()]

        # Write request Key value pair to configuration file
        if Value:
            print('  Adding ' + keyDetails['Desc'] + ': ' + str(Value))
        Config.set(Section,Key,str(Value))

def queryUser(question,default=None):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write('  ' + question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write('    Please respond with "yes"/"no" or "y"/"n".\n')

def defaultConfig():

    """ Generates the default configuration required by the Raspberry Pi Python
        console for Weather Flow Smart Home Weather Stations.

    OUTPUT:
        Default         Default configuration required by PiConsole

    """

    # DEFINE DEFAULT CONFIGURATION SECTIONS, KEY NAMES, AND KEY DETAILS AS
    # ORDERED DICTS
    # --------------------------------------------------------------------------
    Default =                    collections.OrderedDict()
    Default['Keys'] =            collections.OrderedDict([('Description',    '  API keys'),
                                                          ('GeoNames',       {'Type': 'userInput', 'State': 'required', 'Format': str, 'Desc': 'GeoNames API Key'}),
                                                          ('MetOffice',      {'Type': 'userInput', 'State': 'optional', 'Format': str, 'Desc': 'UK MetOffice API Key'}),
                                                          ('DarkSky',        {'Type': 'userInput', 'State': 'optional', 'Format': str, 'Desc': 'DarkSky API Key',}),
                                                          ('CheckWX',        {'Type': 'userInput', 'State': 'required', 'Format': str, 'Desc': 'CheckWX API Key',}),
                                                          ('WeatherFlow',    {'Type': 'fixed',     'Value': '146e4f2c-adec-4244-b711-1aeca8f46a48', 'Desc': 'WeatherFlow API Key'})])
    Default['Station'] =         collections.OrderedDict([('Description',    '  Station and module IDs'),
                                                          ('StationID',      {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'Station ID'}),
                                                          ('TempestID',      {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'TEMPEST module ID'}),
                                                          ('SkyID',          {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'SKY module ID'}),
                                                          ('OutAirID',       {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'outdoor AIR module ID'}),
                                                          ('InAirID',        {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'indoor AIR module ID'}),
                                                          ('TempestHeight',  {'Type': 'request', 'Source': 'station', 'Desc': 'height of TEMPEST module'}),
                                                          ('SkyHeight',      {'Type': 'request', 'Source': 'station', 'Desc': 'height of SKY module'}),
                                                          ('OutAirHeight',   {'Type': 'request', 'Source': 'station', 'Desc': 'height of outdoor AIR module'}),
                                                          ('Latitude',       {'Type': 'request', 'Source': 'station', 'Desc': 'station latitude'}),
                                                          ('Longitude',      {'Type': 'request', 'Source': 'station', 'Desc': 'station longitude'}),
                                                          ('Elevation',      {'Type': 'request', 'Source': 'station', 'Desc': 'station elevation'}),
                                                          ('Timezone',       {'Type': 'request', 'Source': 'station', 'Desc': 'station timezone'}),
                                                          ('Country',        {'Type': 'request', 'Source': 'GeoNames',  'Desc': 'station country'}),
                                                          ('ForecastLocn',   {'Type': 'request', 'Source': 'MetOffice', 'Desc': 'station forecast location'}),
                                                          ('MetOfficeID',    {'Type': 'request', 'Source': 'MetOffice', 'Desc': 'station forecast ID'})])
    Default['Units'] =           collections.OrderedDict([('Description',    '  Observation units'),
                                                          ('Temp',           {'Type': 'request', 'Source': 'observation', 'Desc': 'station temperature units'}),
                                                          ('Pressure',       {'Type': 'request', 'Source': 'observation', 'Desc': 'station pressure units'}),
                                                          ('Wind',           {'Type': 'request', 'Source': 'observation', 'Desc': 'station wind units'}),
                                                          ('Direction',      {'Type': 'request', 'Source': 'observation', 'Desc': 'station direction units'}),
                                                          ('Precip',         {'Type': 'request', 'Source': 'observation', 'Desc': 'station precipitation units'}),
                                                          ('Distance',       {'Type': 'request', 'Source': 'observation', 'Desc': 'station distance units'}),
                                                          ('Other',          {'Type': 'request', 'Source': 'observation', 'Desc': 'station other units'})])
    Default['Display'] =         collections.OrderedDict([('Description',    '  Display settings'),
                                                          ('TimeFormat',     {'Type': 'default', 'Value': '24 hr', 'Desc': 'time format'}),
                                                          ('DateFormat',     {'Type': 'default', 'Value': 'Mon, 01 Jan 0000', 'Desc': 'date format'}),
                                                          ('LightningPanel', {'Type': 'default', 'Value': '1',  'Desc': 'lightning panel toggle'}),
                                                          ('IndoorTemp',     {'Type': 'default', 'Value': '1',  'Desc': 'indoor temperature toggle'})])
    Default['FeelsLike'] =       collections.OrderedDict([('Description',    '  "Feels Like" temperature cut-offs'),
                                                          ('ExtremelyCold',  {'Type': 'default', 'Value': '-4', 'Desc': '"Feels extremely cold" cut-off temperature'}),
                                                          ('FreezingCold',   {'Type': 'default', 'Value': '0',  'Desc': '"Feels freezing cold" cut-off temperature'}),
                                                          ('VeryCold',       {'Type': 'default', 'Value': '4',  'Desc': '"Feels very cold" cut-off temperature'}),
                                                          ('Cold',           {'Type': 'default', 'Value': '9',  'Desc': '"Feels cold" cut-off temperature'}),
                                                          ('Mild',           {'Type': 'default', 'Value': '14', 'Desc': '"Feels mild" cut-off temperature'}),
                                                          ('Warm',           {'Type': 'default', 'Value': '18', 'Desc': '"Feels warm" cut-off temperature'}),
                                                          ('Hot',            {'Type': 'default', 'Value': '23', 'Desc': '"Feels hot" cut-off temperature'}),
                                                          ('VeryHot',        {'Type': 'default', 'Value': '28', 'Desc': '"Feels very hot" cut-off temperature'})])
    Default['PrimaryPanels'] =   collections.OrderedDict([('Description',    '  Primary panel layout'),
                                                          ('PanelOne',       {'Type': 'default', 'Value': 'Forecast',      'Desc':'Primary display for Panel One'}),
                                                          ('PanelTwo',       {'Type': 'default', 'Value': 'Temperature',   'Desc':'Primary display for Panel Two'}),
                                                          ('PanelThree',     {'Type': 'default', 'Value': 'WindSpeed',     'Desc':'Primary display for Panel Three'}),
                                                          ('PanelFour',      {'Type': 'default', 'Value': 'SunriseSunset', 'Desc':'Primary display for Panel Four'}),
                                                          ('PanelFive',      {'Type': 'default', 'Value': 'Rainfall',      'Desc':'Primary display for Panel Five'}),
                                                          ('PanelSix',       {'Type': 'default', 'Value': 'Barometer',     'Desc':'Primary display for Panel Six'})])
    Default['SecondaryPanels'] = collections.OrderedDict([('Description',    '  Secondary panel layout'),
                                                          ('PanelOne',       {'Type': 'default', 'Value': 'Sager',         'Desc':'Secondary display for Panel One'}),
                                                          ('PanelTwo',       {'Type': 'default', 'Value': '',              'Desc':'Secondary display for Panel Two'}),
                                                          ('PanelThree',     {'Type': 'default', 'Value': '',              'Desc':'Secondary display for Panel Three'}),
                                                          ('PanelFour',      {'Type': 'default', 'Value': 'MoonPhase',     'Desc':'Secondary display for Panel Four'}),
                                                          ('PanelFive',      {'Type': 'default', 'Value': 'Lightning',     'Desc':'Secondary display for Panel Five'}),
                                                          ('PanelSix',       {'Type': 'default', 'Value': '',              'Desc':'Secondary display for Panel Six'})])
    Default['System'] =          collections.OrderedDict([('Description',    '  System settings layout'),
                                                          ('BarometerMax',   {'Type': 'dependent', 'Desc': 'maximum barometer pressure'}),
                                                          ('BarometerMin',   {'Type': 'dependent', 'Desc': 'minimum barometer pressure'}),
                                                          ('Timeout',        {'Type': 'default',   'Value': '20',    'Desc': 'Timeout in seconds for API requests'}),
                                                          ('Hardware',       {'Type': 'default',   'Value': Hardware,'Desc': 'Hardware type'}),
                                                          ('Version',        {'Type': 'default',   'Value': Version, 'Desc': 'Version number'})])

    # Return default configuration
    return Default