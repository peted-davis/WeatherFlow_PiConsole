""" Defines the configuration .ini files required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2022 Peter Davis

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
from kivy.logger    import Logger
from packaging      import version
import configparser
import collections
import subprocess
import requests
import platform
import sys
import os

# Define wfpiconsole version number
Version = 'v22.5.1'

# Define required variables
TEMPEST       = False
INDOORAIR     = False
STATION       = None
OBSERVATION   = None
CHECKWX       = None
MAXRETRIES    = 3
NaN           = float('NaN')

# Determine current system
if os.path.exists('/proc/device-tree/model'):
    proc = subprocess.Popen(['cat', '/proc/device-tree/model'], stdout=subprocess.PIPE)
    Hardware = proc.stdout.read().decode('utf-8')
    proc.kill()
    if 'Raspberry Pi 4' in Hardware:
        Hardware = 'Pi4'
    elif 'Raspberry Pi 3' in Hardware:
        Hardware = 'Pi3'
    elif 'Raspberry Pi Model B' in Hardware:
        Hardware = 'PiB'
    else:
        Hardware = 'Other'
else:
    if platform.system() == 'Linux':
        Hardware = 'Linux'
    else:
        Hardware = 'Other'


def create():

    """ Generates a new user configuration file from the default configuration
        dictionary. Saves the new user configuration file to wfpiconsole.ini
    """

    # Load default configuration dictionary
    default = defaultConfig()

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
    for Section in default:

        # Add section to user configuration file
        Config.add_section(Section)

        # Add remaining sections to user configuration file
        for Key in default[Section]:
            if Key == 'Description':
                print(default[Section][Key])
                print('  ---------------------------------')
            else:
                writeConfigKey(Config, Section, Key, default[Section][Key])
        print('')

    # WRITES USER CONFIGURATION FILE TO wfpiconsole.ini
    # --------------------------------------------------------------------------
    with open('wfpiconsole.ini', 'w') as configfile:
        Config.write(configfile)


def update():

    """ Updates an existing user configuration file by comparing it against the
        default configuration dictionary. Saves the updated user configuration
        file to wfpiconsole.ini
    """

    # Fetch latest version number
    latestVersion = defaultConfig()['System']['Version']['Value']

    # Load current user configuration file
    currentConfig = configparser.ConfigParser(allow_no_value=True)
    currentConfig.optionxform = str
    currentConfig.read('wfpiconsole.ini')
    currentVersion = currentConfig['System']['Version']

    # NEW VERSION DETECTED. GENERATE UPDATED CONFIGURATION FILE
    # --------------------------------------------------------------------------
    if version.parse(currentVersion) < version.parse(latestVersion):

        # Print progress dialogue to screen
        print('')
        print('  ===================================================')
        print('  New version detected                               ')
        print('  Starting wfpiconsole configuration wizard          ')
        print('  ===================================================')
        print('')
        print('  Required fields are marked with an asterix (*)     ')
        print('')

        # Create new config parser object to hold updated user configuration file
        newConfig = configparser.ConfigParser(allow_no_value=True)
        newConfig.optionxform = str

        # Loop through all sections in default configuration dictionary. Take
        # existing key values from current configuration file
        for Section in defaultConfig():
            Changes = False
            newConfig.add_section(Section)
            for Key in defaultConfig()[Section]:
                if Key == 'Description':
                    print(defaultConfig()[Section][Key])
                    print('  ---------------------------------')
                else:
                    if currentConfig.has_option(Section, Key):
                        if updateRequired(Key, currentVersion):
                            Changes = True
                            writeConfigKey(newConfig, Section, Key, defaultConfig()[Section][Key])
                        else:
                            copyConfigKey(newConfig, currentConfig, Section, Key, defaultConfig()[Section][Key])
                    if not currentConfig.has_option(Section, Key):
                        Changes = True
                        writeConfigKey(newConfig, Section, Key, defaultConfig()[Section][Key])
                    elif Key == 'Version':
                        Changes = True
                        newConfig.set(Section, Key, latestVersion)
                        print('  Updating version number to: ' + latestVersion)
            if not Changes:
                print('  No changes required')
            print('')

        # Verify station details for updated configuration
        newConfig = verify_station(newConfig)

        # Write updated configuration file to disk
        with open('wfpiconsole.ini', 'w') as configfile:
            newConfig.write(configfile)

    #  VERSION UNCHANGED. VERIFY STATION DETAILS FOR EXISTING CONFIGURATION
    # --------------------------------------------------------------------------
    elif version.parse(currentVersion) == version.parse(latestVersion):
        currentConfig = verify_station(currentConfig)
        with open('wfpiconsole.ini', 'w') as configfile:
            currentConfig.write(configfile)


def verify_station(config):

    # Fetch latest station metadata
    Logger.info('Config: Verifying station details')
    RETRIES = 0
    while True:
        Template = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?api_key={}'
        URL = Template.format(config['Station']['StationID'], config['Keys']['WeatherFlow'])
        try:
            STATION = requests.get(URL).json()
        except Exception:
            STATION = None
        if STATION is not None and 'status' in STATION:
            if 'SUCCESS' in STATION['status']['status_message']:
                break
            else:
                RETRIES += 1
        else:
            RETRIES += 1
        if RETRIES >= MAXRETRIES:
            Logger.error('Config: Unable to fetch station metadata')
            sys.exit()

    # Confirm existing station name
    config.set('Station', 'Name', STATION['station_name'])

    # Return verified configuration
    return config


def switch(stationMetaData, deviceList, config):

    # Update Station section in configuration file to match new station details
    for key in config['Station']:
        Value = ''
        if key == 'StationID':
            Value = stationMetaData['station_id']
        elif key in ['Latitude', 'Longitude', 'Timezone', 'Elevation']:
            Value = stationMetaData[key.lower()]
        elif key == 'Name':
            Value = stationMetaData['station_name']
        elif key == 'TempestID' and 'ST' in deviceList:
            Value = deviceList['ST']['device_id']
        elif key == 'SkyID' and 'SK' in deviceList:
            Value = deviceList['SK']['device_id']
        elif key == 'OutAirID' and 'AR_out' in deviceList:
            Value = deviceList['AR_out']['device_id']
        elif key == 'InAirID' and 'AR_in' in deviceList:
            Value = deviceList['AR_in']['device_id']
        elif key == 'TempestHeight' and 'ST' in deviceList:
            Value = deviceList['ST']['device_meta']['agl']
        elif key == 'SkyHeight' and 'SK' in deviceList:
            Value = deviceList['SK']['device_meta']['agl']
        elif key == 'OutAirHeight' and 'AR_out' in deviceList:
            Value = deviceList['AR_out']['device_meta']['agl']
        config.set('Station', key, str(Value))

    # Write updated configuration file to disk
    try:
        config.write()
    except TypeError:
        with open('wfpiconsole.ini', 'w') as configfile:
            config.write(configfile)


def copyConfigKey(newConfig, currentConfig, Section, Key, keyDetails):

    # Define global variables
    global TEMPEST, INDOORAIR

    # Copy fixed key from default configuration
    if keyDetails['Type'] == 'fixed':
        Value = keyDetails['Value']

    # Copy key value from existing configuration. Ignore AIR/SKY device IDs if
    # switching to TEMPEST
    else:
        if (Key == 'SkyID' or Key == 'SkyHeight') and TEMPEST:
            Value = ''
        elif (Key == 'OutAirID' or Key == 'OutAirHeight') and TEMPEST:
            Value = ''
        else:
            Value = currentConfig[Section][Key]

    # Write key value to new configuration
    newConfig.set(Section, Key, str(Value))

    # Validate API keys
    validateAPIKeys(newConfig)


def writeConfigKey(Config, Section, Key, keyDetails):

    """ Gets and writes the key value pair to the specified section of the
        station configuration file

    INPUTS
        Config              Station configuration
        Section             Section of station configuration containing key
                            value pair
        Key                 Name of key value pair
        keyDetails          Details (type/description) of key value pair

    """

    # Define global variables
    global TEMPEST
    global INDOORAIR
    global STATION
    global OBSERVATION
    global CHECKWX

    # Define required variables
    keyRequired = True

    # GET VALUE OF userInput KEY TYPE
    # --------------------------------------------------------------------------
    if keyDetails['Type'] in ['userInput']:

        # Request user input to determine which devices are present
        if Key == 'TempestID':
            if queryUser('Do you own a TEMPEST?*', None):
                TEMPEST = True
            else:
                Value = ''
                keyRequired = False
        elif Key == 'InAirID':
            if queryUser('Do you own an Indoor AIR?*', None):
                INDOORAIR = True
            else:
                Value = ''
                keyRequired = False

        # Skip device ID keys for devices that are not present
        if Key == 'SkyID' and TEMPEST:
            Value = ''
            keyRequired = False
        elif Key == 'OutAirID' and TEMPEST:
            Value = ''
            keyRequired = False

        # userInput key required. Get value from user
        if keyRequired:
            while True:
                if keyDetails['State'] == 'required':
                    String = '  Please enter your ' + keyDetails['Desc'] + '*: '
                else:
                    String = '  Please enter your ' + keyDetails['Desc'] + ': '
                Value = input(String)

                # userInput key value is empty. Check if userInput key is
                # required
                if not Value and keyDetails['State'] == 'required':
                    print('    ' + keyDetails['Desc'] + ' cannot be empty. Please try again')
                    continue
                elif not Value and keyDetails['State'] == 'optional':
                    break

                # Check if userInput key value matches required format
                try:
                    Value = keyDetails['Format'](Value)
                    break
                except ValueError:
                    print('    ' + keyDetails['Desc'] + ' format is not valid. Please try again')

        # Write userInput Key value pair to configuration file
        Config.set(Section, Key, str(Value))

    # GET VALUE OF dependent KEY TYPE
    # --------------------------------------------------------------------------
    elif keyDetails['Type'] in ['dependent']:

        # Get dependent Key value
        if Key == 'IndoorTemp':
            if Config['Station']['InAirID']:
                Value = '1'
            else:
                Value = '0'
        elif Key == 'BarometerMax':
            Units = ['mb', 'hpa', 'inhg', 'mmhg']
            Max = ['1050', '1050', '31.0', '788']
            Value = Max[Units.index(Config['Units']['Pressure'])]
        elif Key == 'BarometerMin':
            Units = ['mb', 'hpa', 'inhg', 'mmhg']
            Min = ['950', '950', '28.0', '713']
            Value = Min[Units.index(Config['Units']['Pressure'])]
        print('  Adding ' + keyDetails['Desc'] + ': ' + Value)

        # Write dependent Key value pair to configuration file
        Config.set(Section, Key, str(Value))

    # GET VALUE OF default OR fixed KEY TYPE
    # --------------------------------------------------------------------------
    elif keyDetails['Type'] in ['default', 'fixed']:

        # Get default or fixed Key value
        if Key in ['ExtremelyCold', 'FreezingCold', 'VeryCold', 'Cold', 'Mild', 'Warm', 'Hot', 'VeryHot']:
            if 'c' in Config['Units']['Temp']:
                Value = keyDetails['Value']
            elif 'f' in Config['Units']['Temp']:
                Value = str(int(float(keyDetails['Value']) * 9 / 5 + 32))
        else:
            Value = keyDetails['Value']

        # Write default or fixed Key value pair to configuration file
        print('  Adding ' + keyDetails['Desc'] + ': ' + Value)
        Config.set(Section, Key, str(Value))

    # GET VALUE OF request KEY TYPE
    # --------------------------------------------------------------------------
    elif keyDetails['Type'] in ['request']:

        # Define local variables
        Value = ''

        # Get Observation metadata from WeatherFlow API
        RETRIES = 0
        if keyDetails['Source'] == 'observation' and OBSERVATION is None:
            while True:
                Template = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?api_key={}'
                URL = Template.format(Config['Station']['StationID'], Config['Keys']['WeatherFlow'])
                OBSERVATION = requests.get(URL).json()
                if 'status' in STATION:
                    if 'SUCCESS' in STATION['status']['status_message']:
                        break
                    else:
                        RETRIES += 1
                else:
                    RETRIES += 1
                if RETRIES >= MAXRETRIES:
                    sys.exit('\n    Error: unable to fetch observation metadata')

        # Validate TEMPEST device ID and get height above ground of TEMPEST
        if Section == 'Station':
            if Key == 'TempestHeight' and Config['Station']['TempestID']:
                while True:
                    for Device in STATION['stations'][0]['devices']:
                        if 'device_type' in Device:
                            if str(Device['device_id']) == Config['Station']['TempestID']:
                                if Device['device_type'] == 'ST':
                                    Value = Device['device_meta']['agl']
                    if not Value and Value != 0:
                        inputStr = '    TEMPEST not found. Please re-enter your TEMPEST device ID*: '
                        while True:
                            ID = input(inputStr)
                            if not ID:
                                print('    TEMPEST device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                inputStr = '    TEMPEST device ID not valid. Please re-enter your TEMPEST device ID*: '
                        Config.set('Station', 'TempestID', str(ID))
                    else:
                        break

        # Validate AIR device ID and get height above ground of AIR
        if Section == 'Station':
            if Key == 'OutAirHeight' and Config['Station']['OutAirID']:
                while True:
                    for Device in STATION['stations'][0]['devices']:
                        if 'device_type' in Device:
                            if str(Device['device_id']) == Config['Station']['OutAirID']:
                                if Device['device_type'] == 'AR':
                                    Value = Device['device_meta']['agl']
                    if not Value and Value != 0:
                        inputStr = '    Outdoor AIR not found. Please re-enter your Outdoor AIR device ID*: '
                        while True:
                            ID = input(inputStr)
                            if not ID:
                                print('    Outdoor AIR device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                inputStr = '    Outdoor AIR device ID not valid. Please re-enter your Outdoor AIR device ID*: '
                        Config.set('Station', 'OutAirID', str(ID))
                    else:
                        break

        # Validate SKY device ID and get height above ground of SKY
        if Section == 'Station':
            if Key == 'SkyHeight' and Config['Station']['SkyID']:
                while True:
                    for Device in STATION['stations'][0]['devices']:
                        if 'device_type' in Device:
                            if str(Device['device_id']) == Config['Station']['SkyID']:
                                if Device['device_type'] == 'SK':
                                    Value = Device['device_meta']['agl']
                    if not Value and Value != 0:
                        inputStr = '    SKY not found. Please re-enter your SKY device ID*: '
                        while True:
                            ID = input(inputStr)
                            if not ID:
                                print('    SKY device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                inputStr = '    SKY device ID not valid. Please re-enter your SKY device ID*: '
                        Config.set('Station', 'SkyID', str(ID))
                    else:
                        break

        # Get station latitude/longitude, timezone, or name
        if Section == 'Station':
            if Key in ['Latitude', 'Longitude', 'Timezone', 'Name']:
                Value = STATION['stations'][0][Key.lower()]

        # Get station elevation
        if Section == 'Station':
            if Key == 'Elevation':
                Value = STATION['stations'][0]['station_meta']['elevation']

        # Get station units
        if Section in ['Units']:
            Value = OBSERVATION['station_units']['units_' + Key.lower()]

        # Write request Key value pair to configuration file
        print('  Adding ' + keyDetails['Desc'] + ': ' + str(Value))
        Config.set(Section, Key, str(Value))

    # Validate API keys
    validateAPIKeys(Config)


def validateAPIKeys(Config):

    """ Validates API keys entered in the config file

    INPUTS
        Config              Station configuration

    """

    # Define global variables
    global STATION
    global CHECKWX

    # Validate CheckWX API key
    RETRIES = 0
    if 'Keys' in Config:
        if 'CheckWX' in Config['Keys'] and CHECKWX is None:
            while True:
                header = {'X-API-Key': Config['Keys']['CheckWX']}
                URL = 'https://api.checkwx.com/station/EGLL'
                CHECKWX = requests.get(URL, headers=header).json()
                if 'error' in CHECKWX:
                    if 'Unauthorized' in CHECKWX['error']:
                        inputStr = '    Access not authorized. Please re-enter your CheckWX API key*: '
                        while True:
                            APIKey = input(inputStr)
                            if not APIKey:
                                print('    CheckWX API key cannot be empty. Please try again')
                            else:
                                break
                        Config.set('Keys', 'CheckWX', str(APIKey))
                        RETRIES += 1
                    else:
                        RETRIES += 1
                elif 'results' in CHECKWX:
                    break
                else:
                    RETRIES += 1
                if RETRIES >= MAXRETRIES:
                    sys.exit('\n    Error: unable to complete CheckWX API call')

    # Validate WeatherFlow Personal Access Token
    RETRIES = 0
    if 'Keys' in Config and 'Station' in Config:
        if 'WeatherFlow' in Config['Keys'] and 'StationID' in Config['Station'] and STATION is None:
            while True:
                Template = 'https://swd.weatherflow.com/swd/rest/stations/{}?api_key={}'
                URL = Template.format(Config['Station']['StationID'], Config['Keys']['WeatherFlow'])
                STATION = requests.get(URL).json()
                if 'status' in STATION:
                    if 'NOT FOUND' in STATION['status']['status_message']:
                        inputStr = '    Station not found. Please re-enter your Station ID*: '
                        while True:
                            ID = input(inputStr)
                            if not ID:
                                print('    Station ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                inputStr = '    Station ID not valid. Please re-enter your Station ID*: '
                        Config.set('Station', 'StationID', str(ID))
                        RETRIES += 1
                    elif 'UNAUTHORIZED' in STATION['status']['status_message']:
                        inputStr = '    Access not authorized. Please re-enter your WeatherFlow Personal Access Token*: '
                        while True:
                            Token = input(inputStr)
                            if not Token:
                                print('    Personal Access Token cannot be empty. Please try again')
                            else:
                                break
                        Config.set('Keys', 'WeatherFlow', str(Token))
                        RETRIES += 1
                    elif 'SUCCESS' in STATION['status']['status_message']:
                        break
                    else:
                        RETRIES += 1
                else:
                    RETRIES += 1
                if RETRIES >= MAXRETRIES:
                    sys.exit('\n    Error: unable to fetch station metadata')


def queryUser(Question, Default=None):

    """ Ask a yes/no question via raw_input() and return their answer.

    INPUTS
        Question                Query string presented to user
        Default                 Presumed answer if the user just hits <Enter>.
                                It must be "yes", "no" or None

    OUTPUT
        Valid                   True for "yes" or False for "no"
    """

    # Define valid reponses and prompt based on specified default answer
    valid = {'yes': True, 'y': True, 'ye': True, 'no': False, 'n': False}
    if Default is None:
        prompt = ' [y/n] '
    elif Default == 'yes':
        prompt = ' [Y/n] '
    elif Default == 'no':
        prompt = ' [y/N] '
    else:
        raise ValueError('invalid default answer: "%s"' % Default)

    # Display question to user
    while True:
        sys.stdout.write('  ' + Question + prompt)
        choice = input().lower()
        if Default is not None and choice == '':
            return valid[Default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write('    Please respond with "yes"/"no" or "y"/"n"\n')


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
                                                          ('WeatherFlow',    {'Type': 'userInput', 'State': 'required', 'Format': str, 'Desc': 'WeatherFlow Personal Access Token'}),
                                                          ('CheckWX',        {'Type': 'userInput', 'State': 'required', 'Format': str, 'Desc': 'CheckWX API Key'})])
    Default['Station'] =         collections.OrderedDict([('Description',    '  Station and device IDs'),
                                                          ('StationID',      {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'Station ID'}),
                                                          ('TempestID',      {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'TEMPEST device ID'}),
                                                          ('SkyID',          {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'SKY device ID'}),
                                                          ('OutAirID',       {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'outdoor AIR device ID'}),
                                                          ('InAirID',        {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'indoor AIR device ID'}),
                                                          ('TempestHeight',  {'Type': 'request', 'Source': 'station', 'Desc': 'height of TEMPEST'}),
                                                          ('SkyHeight',      {'Type': 'request', 'Source': 'station', 'Desc': 'height of SKY'}),
                                                          ('OutAirHeight',   {'Type': 'request', 'Source': 'station', 'Desc': 'height of outdoor AIR'}),
                                                          ('Latitude',       {'Type': 'request', 'Source': 'station', 'Desc': 'station latitude'}),
                                                          ('Longitude',      {'Type': 'request', 'Source': 'station', 'Desc': 'station longitude'}),
                                                          ('Elevation',      {'Type': 'request', 'Source': 'station', 'Desc': 'station elevation'}),
                                                          ('Timezone',       {'Type': 'request', 'Source': 'station', 'Desc': 'station timezone'}),
                                                          ('Name',           {'Type': 'request', 'Source': 'station', 'Desc': 'station name'})])
    Default['Units'] =           collections.OrderedDict([('Description',    '  Observation units'),
                                                          ('Temp',           {'Type': 'request', 'Source': 'observation', 'Desc': 'station temperature units'}),
                                                          ('Pressure',       {'Type': 'request', 'Source': 'observation', 'Desc': 'station pressure units'}),
                                                          ('Wind',           {'Type': 'request', 'Source': 'observation', 'Desc': 'station wind units'}),
                                                          ('Direction',      {'Type': 'request', 'Source': 'observation', 'Desc': 'station direction units'}),
                                                          ('Precip',         {'Type': 'request', 'Source': 'observation', 'Desc': 'station precipitation units'}),
                                                          ('Distance',       {'Type': 'request', 'Source': 'observation', 'Desc': 'station distance units'}),
                                                          ('Other',          {'Type': 'request', 'Source': 'observation', 'Desc': 'station other units'})])
    Default['Display'] =         collections.OrderedDict([('Description',    '  Display settings'),
                                                          ('TimeFormat',     {'Type': 'default',   'Value': '24 hr', 'Desc': 'time format'}),
                                                          ('DateFormat',     {'Type': 'default',   'Value': 'Mon, 01 Jan 0000', 'Desc': 'date format'}),
                                                          ('LightningPanel', {'Type': 'default',   'Value': '1',    'Desc': 'lightning panel toggle'}),
                                                          ('IndoorTemp',     {'Type': 'dependent', 'Desc': 'indoor temperature toggle'}),
                                                          ('Cursor',         {'Type': 'default',   'Value': '1',    'Desc': 'cursor toggle'}),
                                                          ('Border',         {'Type': 'default',   'Value': '1',    'Desc': 'border toggle'}),
                                                          ('Fullscreen',     {'Type': 'default',   'Value': '1',    'Desc': 'fullscreen toggle'}),
                                                          ('Width',          {'Type': 'default',   'Value': '800',  'Desc': 'console width (pixels)'}),
                                                          ('Height',         {'Type': 'default',   'Value': '480',  'Desc': 'console height (pixels)'})])
    Default['FeelsLike'] =       collections.OrderedDict([('Description',    '  "Feels Like" temperature cut-offs'),
                                                          ('ExtremelyCold',  {'Type': 'default', 'Value': '-5', 'Desc': '"Feels extremely cold" cut-off temperature'}),
                                                          ('FreezingCold',   {'Type': 'default', 'Value': '0',  'Desc': '"Feels freezing cold" cut-off temperature'}),
                                                          ('VeryCold',       {'Type': 'default', 'Value': '5',  'Desc': '"Feels very cold" cut-off temperature'}),
                                                          ('Cold',           {'Type': 'default', 'Value': '10', 'Desc': '"Feels cold" cut-off temperature'}),
                                                          ('Mild',           {'Type': 'default', 'Value': '15', 'Desc': '"Feels mild" cut-off temperature'}),
                                                          ('Warm',           {'Type': 'default', 'Value': '20', 'Desc': '"Feels warm" cut-off temperature'}),
                                                          ('Hot',            {'Type': 'default', 'Value': '25', 'Desc': '"Feels hot" cut-off temperature'}),
                                                          ('VeryHot',        {'Type': 'default', 'Value': '30', 'Desc': '"Feels very hot" cut-off temperature'})])
    Default['PrimaryPanels'] =   collections.OrderedDict([('Description',    '  Primary panel layout'),
                                                          ('PanelOne',       {'Type': 'default', 'Value': 'Forecast',      'Desc': 'Primary display for Panel One'}),
                                                          ('PanelTwo',       {'Type': 'default', 'Value': 'Temperature',   'Desc': 'Primary display for Panel Two'}),
                                                          ('PanelThree',     {'Type': 'default', 'Value': 'WindSpeed',     'Desc': 'Primary display for Panel Three'}),
                                                          ('PanelFour',      {'Type': 'default', 'Value': 'SunriseSunset', 'Desc': 'Primary display for Panel Four'}),
                                                          ('PanelFive',      {'Type': 'default', 'Value': 'Rainfall',      'Desc': 'Primary display for Panel Five'}),
                                                          ('PanelSix',       {'Type': 'default', 'Value': 'Barometer',     'Desc': 'Primary display for Panel Six'})])
    Default['SecondaryPanels'] = collections.OrderedDict([('Description',    '  Secondary panel layout'),
                                                          ('PanelOne',       {'Type': 'default', 'Value': 'Sager',         'Desc': 'Secondary display for Panel One'}),
                                                          ('PanelTwo',       {'Type': 'default', 'Value': '',              'Desc': 'Secondary display for Panel Two'}),
                                                          ('PanelThree',     {'Type': 'default', 'Value': '',              'Desc': 'Secondary display for Panel Three'}),
                                                          ('PanelFour',      {'Type': 'default', 'Value': 'MoonPhase',     'Desc': 'Secondary display for Panel Four'}),
                                                          ('PanelFive',      {'Type': 'default', 'Value': '',              'Desc': 'Secondary display for Panel Five'}),
                                                          ('PanelSix',       {'Type': 'default', 'Value': 'Lightning',     'Desc': 'Secondary display for Panel Six'})])
    Default['System'] =          collections.OrderedDict([('Description',    '  System settings'),
                                                          ('BarometerMax',   {'Type': 'dependent', 'Desc': 'maximum barometer pressure'}),
                                                          ('BarometerMin',   {'Type': 'dependent', 'Desc': 'minimum barometer pressure'}),
                                                          ('SagerInterval',  {'Type': 'default',   'Value': '6',     'Desc': 'Interval in hours between Sager Forecasts'}),
                                                          ('Timeout',        {'Type': 'default',   'Value': '20',    'Desc': 'Timeout in seconds for API requests'}),
                                                          ('Hardware',       {'Type': 'default',   'Value': Hardware, 'Desc': 'Hardware type'}),
                                                          ('Version',        {'Type': 'default',   'Value': Version, 'Desc': 'Version number'})])

    # Return default configuration
    return Default


def updateRequired(Key, currentVersion):

    """ List configuration keys that require updating along with the version
    number when the update must be triggered

    OUTPUT:
        True/False         Boolean indicating whether configuration key needs
                           updating
    """

    # Dictionary holding configuration keys and version numbers
    updatesRequired = {
        'WeatherFlow': '3.7',
        'Hardware': '4',
    }

    # Determine if current configuration key passed to function requires
    # updating
    if Key in updatesRequired:
        if version.parse(currentVersion) < version.parse(updatesRequired[Key]):
            return 1
        else:
            return 0
    else:
        return 0
