""" Defines the configuration .ini files required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2023 Peter Davis

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
Version = 'v23.5.beta'

# Define required variables
TEMPEST       = False
INDOORAIR     = False
STATION       = None
OBSERVATION   = None
CHECKWX       = None
MAXRETRIES    = 3
idx           = None

# Determine current system
if os.path.exists('/proc/device-tree/model'):
    proc = subprocess.Popen(['cat', '/proc/device-tree/model'], stdout=subprocess.PIPE)
    hardware = proc.stdout.read().decode('utf-8')
    proc.kill()
    if 'Raspberry Pi 4' in hardware:
        hardware = 'Pi4'
    elif 'Raspberry Pi 3' in hardware:
        hardware = 'Pi3'
    elif 'Raspberry Pi Model B' in hardware:
        hardware = 'PiB'
    else:
        hardware = 'Other'
else:
    if platform.system() == 'Linux':
        hardware = 'Linux'
    else:
        hardware = 'Other'


def create():

    """ Generates a new user configuration file from the default configuration
        dictionary. Saves the new user configuration file to wfpiconsole.ini
    """

    # Load default configuration dictionary
    default = default_config()

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
    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str

    # Loop through all sections in default configuration dictionary
    for section in default:

        # Add section to user configuration file
        config.add_section(section)

        # Add remaining sections to user configuration file
        for key in default[section]:
            if key == 'Description':
                print(default[section][key])
                print('  ---------------------------------')
            else:
                write_config_key(config, section, key, default[section][key])
        print('')

    # WRITES USER CONFIGURATION FILE TO wfpiconsole.ini
    # --------------------------------------------------------------------------
    with open('wfpiconsole.ini', 'w') as config_file:
        config.write(config_file)


def update():

    """ Updates an existing user configuration file by comparing it against the
        default configuration dictionary. Saves the updated user configuration
        file to wfpiconsole.ini
    """

    # Fetch latest version number
    latest_version = default_config()['System']['Version']['Value']

    # Load current user configuration file
    current_config = configparser.ConfigParser(allow_no_value=True)
    current_config.optionxform = str
    current_config.read('wfpiconsole.ini')
    current_version = current_config['System']['Version']

    # NEW VERSION DETECTED. GENERATE UPDATED CONFIGURATION FILE
    # --------------------------------------------------------------------------
    if version.parse(current_version) < version.parse(latest_version):

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
        new_config = configparser.ConfigParser(allow_no_value=True)
        new_config.optionxform = str

        # Loop through all sections in default configuration dictionary. Take
        # existing key values from current configuration file
        for section in default_config():
            changes = False
            new_config.add_section(section)
            for key in default_config()[section]:
                if key == 'Description':
                    print(default_config()[section][key])
                    print('  ---------------------------------')
                else:
                    if current_config.has_option(section, key):
                        if update_required(key, current_version):
                            changes = True
                            write_config_key(new_config, section, key, default_config()[section][key])
                        else:
                            copy_config_key(new_config, current_config, section, key, default_config()[section][key])
                    if not current_config.has_option(section, key):
                        changes = True
                        write_config_key(new_config, section, key, default_config()[section][key])
                    elif key == 'Version':
                        changes = True
                        new_config.set(section, key, latest_version)
                        print('  Updating version number to: ' + latest_version)
            if not changes:
                print('  No changes required')
            print('')

        # Verify station details for updated configuration
        new_config = verify_station(new_config)

        # Write updated configuration file to disk
        with open('wfpiconsole.ini', 'w') as config_file:
            new_config.write(config_file)

    #  VERSION UNCHANGED. VERIFY STATION DETAILS FOR EXISTING CONFIGURATION
    # --------------------------------------------------------------------------
    elif version.parse(current_version) == version.parse(latest_version):
        if int(current_config['System']['rest_api']):
            current_config = verify_station(current_config)
        with open('wfpiconsole.ini', 'w') as config_file:
            current_config.write(config_file)


def verify_station(config):

    # Fetch latest station metadata
    Logger.info('Config: Verifying station details')
    RETRIES = 0
    while True:
        Template = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?token={}'
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
            if config['System']['Connection'] == 'UDP':
                Logger.warning('Config: Disable REST API services when using UDP without an internet connection')
            sys.exit()

    # Confirm existing station name
    config.set('Station', 'Name', STATION['station_name'])

    # Return verified configuration
    return config


def switch(station_meta_data, device_list, config):

    # Update Station section in configuration file to match new station details
    for key in config['Station']:
        value = ''
        if key == 'StationID':
            value = station_meta_data['station_id']
        elif key in ['Latitude', 'Longitude', 'Timezone']:
            value = station_meta_data[key.lower()]
        elif key == 'Elevation':
            value = station_meta_data['station_meta'][key.lower()]
        elif key == 'Name':
            value = station_meta_data['name']
        elif key == 'TempestID' and 'ST' in device_list:
            value = device_list['ST']['device_id']
        elif key == 'TempestSN' and 'ST' in device_list:
            value = device_list['ST']['serial_number']
        elif key == 'SkyID' and 'SK' in device_list:
            value = device_list['SK']['device_id']
        elif key == 'SkySN' and 'SK' in device_list:
            value = device_list['SK']['serial_number']
        elif key == 'OutAirID' and 'AR_out' in device_list:
            value = device_list['AR_out']['device_id']
        elif key == 'OutAirSN' and 'AR_out' in device_list:
            value = device_list['AR_out']['serial_number']
        elif key == 'InAirID' and 'AR_in' in device_list:
            value = device_list['AR_in']['device_id']
        elif key == 'InAirSN' and 'AR_in' in device_list:
            value = device_list['AR_in']['serial_number']
        elif key == 'TempestHeight' and 'ST' in device_list:
            value = device_list['ST']['device_meta']['agl']
        elif key == 'SkyHeight' and 'SK' in device_list:
            value = device_list['SK']['device_meta']['agl']
        elif key == 'OutAirHeight' and 'AR_out' in device_list:
            value = device_list['AR_out']['device_meta']['agl']
        config.set('Station', key, str(value))

    # Write updated configuration file to disk
    try:
        config.write()
    except TypeError:
        with open('wfpiconsole.ini', 'w') as configfile:
            config.write(configfile)


def copy_config_key(new_config, current_config, section, key, details):

    # Define global variables
    global TEMPEST, INDOORAIR

    # Copy fixed key from default configuration
    if details['Type'] == 'fixed':
        value = details['Value']

    # Copy key value from existing configuration. Ignore AIR/SKY device IDs if
    # switching to TEMPEST
    else:
        if (key == 'SkyID' or key == 'SkyHeight' or key == 'SkySN') and TEMPEST:
            value = ''
        elif (key == 'OutAirID' or key == 'OutAirHeight' or key == 'OutAirSN') and TEMPEST:
            value = ''
        else:
            value = current_config[section][key]

    # Write key value to new configuration
    new_config.set(section, key, str(value))

    # Validate API keys
    validate_API_keys(new_config)


def write_config_key(config, section, key, details):

    """ Gets and writes the key value pair to the specified section of the
        station configuration file

    INPUTS
        config              Station configuration
        section             Section of station configuration containing key
                            value pair
        key                 Name of key value pair
        details             Details (type/description) of key value pair

    """

    # Define global variables
    global TEMPEST
    global INDOORAIR
    global STATION
    global OBSERVATION
    global CHECKWX

    # Define required variables
    key_required = True

    # GET VALUE OF userInput KEY TYPE
    # --------------------------------------------------------------------------
    if details['Type'] in ['userInput']:

        # Request user input to determine which devices are present
        if key == 'TempestID':
            if query_user('Do you own a TEMPEST?*', None):
                TEMPEST = True
            else:
                value = ''
                key_required = False
        elif key == 'InAirID':
            if query_user('Do you own an Indoor AIR?*', None):
                INDOORAIR = True
            else:
                value = ''
                key_required = False

        # Skip device ID keys for devices that are not present
        if (key == 'SkyID' or key == 'SkySN') and TEMPEST:
            value = ''
            key_required = False
        elif (key == 'OutAirID' or key == 'OutAirSN') and TEMPEST:
            value = ''
            key_required = False

        # userInput key required. Get value from user
        if key_required:
            while True:
                if details['State'] == 'required':
                    string = '  Please enter your ' + details['Desc'] + '*: '
                else:
                    string = '  Please enter your ' + details['Desc'] + ': '
                value = input(string)

                # userInput key value is empty. Check if userInput key is
                # required
                if not value and details['State'] == 'required':
                    print('    ' + details['Desc'] + ' cannot be empty. Please try again')
                    continue
                elif not value and details['State'] == 'optional':
                    break

                # Check if userInput key value matches required format
                try:
                    value = details['Format'](value)
                    break
                except ValueError:
                    print('    ' + details['Desc'] + ' format is not valid. Please try again')

        # Write userInput Key value pair to configuration file
        config.set(section, key, str(value))

    # GET VALUE OF dependent KEY TYPE
    # --------------------------------------------------------------------------
    elif details['Type'] in ['dependent']:

        # Get dependent Key value
        if key == 'IndoorTemp':
            if config['Station']['InAirID']:
                value = '1'
            else:
                value = '0'
        elif key == 'BarometerMax':
            Units = ['mb', 'hpa', 'inhg', 'mmhg']
            Max = ['1050', '1050', '31.0', '788']
            value = Max[Units.index(config['Units']['Pressure'])]
        elif key == 'BarometerMin':
            Units = ['mb', 'hpa', 'inhg', 'mmhg']
            Min = ['950', '950', '28.0', '713']
            value = Min[Units.index(config['Units']['Pressure'])]
        print('  Adding ' + details['Desc'] + ': ' + value)

        # Write dependent Key value pair to configuration file
        config.set(section, key, str(value))

    # GET VALUE OF default OR fixed KEY TYPE
    # --------------------------------------------------------------------------
    elif details['Type'] in ['default', 'fixed']:

        # Get default or fixed Key value
        if key in ['ExtremelyCold', 'FreezingCold', 'VeryCold', 'Cold', 'Mild', 'Warm', 'Hot', 'VeryHot']:
            if 'c' in config['Units']['Temp']:
                value = details['Value']
            elif 'f' in config['Units']['Temp']:
                value = str(int(float(details['Value']) * 9 / 5 + 32))
        else:
            value = details['Value']

        # Write default or fixed Key value pair to configuration file
        print('  Adding ' + details['Desc'] + ': ' + value)
        config.set(section, key, str(value))

    # GET VALUE OF request KEY TYPE
    # --------------------------------------------------------------------------
    elif details['Type'] in ['request']:

        # Define local variables
        value = ''

        # Get Observation metadata from WeatherFlow API
        RETRIES = 0
        if details['Source'] == 'observation' and OBSERVATION is None:
            while True:
                Template = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?token={}'
                URL = Template.format(config['Station']['StationID'], config['Keys']['WeatherFlow'])
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

        # Validate TEMPEST device ID and get height above ground or serial
        # number of TEMPEST
        if section == 'Station':
            if key in ['TempestHeight', 'TempestSN'] and TEMPEST:
                while True:
                    for station in STATION['stations']:
                        for device in station['devices']:
                            if 'device_type' in device:
                                if str(device['device_id']) == config['Station']['TempestID']:
                                    if device['device_type'] == 'ST':
                                        if key == 'TempestHeight':
                                            value = device['device_meta']['agl']
                                        elif key == 'TempestSN':
                                            value = device['serial_number']
                    if not value and value != 0:
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
                        config.set('Station', 'TempestID', str(ID))
                    else:
                        break

        # Validate outdoor AIR device ID and get height above ground of serial
        # number of outdoor AIR
        if section == 'Station':
            if key in ['OutAirHeight', 'OutAirSN'] and not TEMPEST:
                while True:
                    for station in STATION['stations']:
                        for device in station['devices']:
                            if 'device_type' in device:
                                if str(device['device_id']) == config['Station']['OutAirID']:
                                    if device['device_type'] == 'AR':
                                        value = device['device_meta']['agl']
                    if not value and value != 0:
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
                        config.set('Station', 'OutAirID', str(ID))
                    else:
                        break

        # Validate SKY device ID and get height above ground or serial number of
        # SKY
        if section == 'Station':
            if key in ['SkyHeight',  'SkySN'] and not TEMPEST:
                while True:
                    for station in STATION['stations']:
                        for device in station['devices']:
                            if 'device_type' in device:
                                if str(device['device_id']) == config['Station']['SkyID']:
                                    if device['device_type'] == 'SK':
                                        if key == 'SkyHeight':
                                            value = device['device_meta']['agl']
                                        elif key == 'SkySN':
                                            value = device['serial_number']
                    if not value and value != 0:
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
                        config.set('Station', 'SkyID', str(ID))
                    else:
                        break

        # Validate outdoor AIR device ID and get height above ground of serial
        # number of outdoor AIR
        if section == 'Station':
            if key in 'InAirSN' and config['Station']['InAirID']:
                while True:
                    for station in STATION['stations']:
                        for device in station['devices']:
                            if 'device_type' in device:
                                if str(device['device_id']) == config['Station']['InAirID']:
                                    if device['device_type'] == 'AR':
                                        value = device['serial_number']
                    if not value and value != 0:
                        inputStr = '    Indoor AIR not found. Please re-enter your Indoor AIR device ID*: '
                        while True:
                            ID = input(inputStr)
                            if not ID:
                                print('    Indoor AIR device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                inputStr = '    Indoor AIR device ID not valid. Please re-enter your Indoor AIR device ID*: '
                        config.set('Station', 'InAirID', str(ID))
                    else:
                        break

        # Get station latitude/longitude, timezone, or name
        if section == 'Station':
            if key in ['Latitude', 'Longitude', 'Timezone', 'Name']:
                value = STATION['stations'][idx][key.lower()]

        # Get station elevation
        if section == 'Station':
            if key == 'Elevation':
                value = STATION['stations'][idx]['station_meta']['elevation']

        # Get station units
        if section in ['Units']:
            value = OBSERVATION['station_units']['units_' + key.lower()]

        # Write request Key value pair to configuration file
        if value:
            print('  Adding ' + details['Desc'] + ': ' + str(value))
        config.set(section, key, str(value))

    # Validate API keys
    validate_API_keys(config)


def validate_API_keys(Config):

    """ Validates API keys entered in the config file

    INPUTS
        Config              Station configuration

    """

    # Define global variables
    global STATION
    global CHECKWX
    global idx

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
                Template = 'https://swd.weatherflow.com/swd/rest/stations/?token={}'
                URL = Template.format(Config['Keys']['WeatherFlow'])
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
    if STATION is not None and idx is None:
        for ii, station in enumerate(STATION['stations']):
            if station['station_id'] == int(Config['Station']['StationID']):
                idx = ii


def query_user(Question, Default=None):

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


def default_config():

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
                                                          ('TempestSN',      {'Type': 'request',   'Source': 'station', 'Desc': 'TEMPEST serial number'}),
                                                          ('SkyID',          {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'SKY device ID'}),
                                                          ('SkySN',          {'Type': 'request',   'Source': 'station', 'Desc': 'SKY serial number'}),
                                                          ('OutAirID',       {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'outdoor AIR device ID'}),
                                                          ('OutAirSN',       {'Type': 'request',   'Source': 'station', 'Desc': 'outdoor AIR serial number'}),
                                                          ('InAirID',        {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'indoor AIR device ID'}),
                                                          ('InAirSN',        {'Type': 'request',   'Source': 'station', 'Desc': 'indoor AIR serial number'}),
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
                                                          ('Connection',     {'Type': 'default',   'Value': 'Websocket', 'Desc': 'Connection type'}),
                                                          ('rest_api',       {'Type': 'default',   'Value': '1',         'Desc': 'REST API services'}),
                                                          ('SagerInterval',  {'Type': 'default',   'Value': '6',         'Desc': 'Interval in hours between Sager Forecasts'}),
                                                          ('Timeout',        {'Type': 'default',   'Value': '20',        'Desc': 'Timeout in seconds for API requests'}),
                                                          ('Hardware',       {'Type': 'default',   'Value': hardware,    'Desc': 'Hardware type'}),
                                                          ('Version',        {'Type': 'default',   'Value': Version,     'Desc': 'Version number'})])

    # Return default configuration
    return Default


def update_required(Key, current_version):

    """ List configuration keys that require updating along with the version
    number when the update must be triggered

    OUTPUT:
        True/False         Boolean indicating whether configuration key needs
                           updating
    """

    # Dictionary holding configuration keys and version numbers
    updates_required = {
        'WeatherFlow': '3.7',
        'Hardware': '4',
    }

    # Determine if current configuration key passed to function requires
    # updating
    if Key in updates_required:
        if version.parse(current_version) < version.parse(updates_required[Key]):
            return 1
        else:
            return 0
    else:
        return 0
