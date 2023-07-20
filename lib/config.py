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
import shutil
import sys
import os

# Define wfpiconsole version number
ver = 'v23.5.beta'

# Define required variables
TEMPEST       = False
INDOORAIR     = False
STATION       = None
OBSERVATION   = None
CHECKWX       = None
MAXRETRIES    = 3
TYPE          = None
UNITS         = None
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

    # Define global variables
    global TYPE, UNITS

    # Load default configuration dictionary
    default = default_config()

    # Load UDP input fields
    udp_input = udp_input_fields()

    # CONVERT DEFAULT CONFIGURATION DICTIONARY INTO .ini FILE
    # --------------------------------------------------------------------------
    # Print progress dialogue to screen
    print('')
    print('  ===================================================')
    print('  Starting wfpiconsole configuration wizard          ')
    print('  ===================================================')
    print('')
    print('  Welcome to the WeatherFlow PiConsole. You will now ')
    print('  be guided through the initial configuration        ')
    print('')
    print('  Required fields are marked with an asterix (*)     ')
    print('')

    # Give the user the opportunity to install a minimal .ini file for 
    # demonstration purposes or advanced configuration
    if query_user('Would you like to install a minimal configuration file \n' +
                  '  for demonstration purposes or advanced setup?*', 'no'):

        # Generate minimal configuration file
        try:
            # Open new configuration object
            config = configparser.ConfigParser(allow_no_value=True)
            config.optionxform = str

            # Loop over all sections and keys in default configuration
            for section in default:
                config.add_section(section)
                for key in default[section]:
                    if key != 'Description':
                        if 'Value' in default[section][key]:
                            config.set(section, key, str(default[section][key]['Value']))
                        else:
                            config.set(section, key, '')

            # Write the minimal configuration to disk
            with open('wfpiconsole.ini', 'w') as config_file:
                config.write(config_file)
            print('\n  Sucesfully installed a minimal configuration file. Please edit')
            print('  this file manually to configure an advanced installation\n')

        # Unable to install minimal configuration
        except Exception as error:
            if os.path.exists("wfpiconsole.ini"):
                os.remove("wfpiconsole.ini")
            sys.exit(f'\n Error: unable to install minimal configuration \n  {error}')
        return
    else:
        print('')

    # Determine preferred connection type
    print('  Please select your preferred connection type')
    print('    1) Websocket and REST API [default]')
    print('    2) UDP and REST API')
    print('    3) UDP only')
    TYPE = input('    > ') or '1'
    print('')
    while True:
        if TYPE == '1' or TYPE == '2' or TYPE == '3':
            if TYPE == '1':
                print('  Websocket and REST API selected')
            elif TYPE == '2':
                print('  UDP and REST API selected')
            elif TYPE == '3':
                print('  UDP only selected')        
            TYPE = int(TYPE)    
            print('')
            break
        else:
            print('  Connection type not recognised')
            TYPE = input('  Please select your preferred connection type: ') or 1
            print('')

    # Determine preferred unit convention if connection type is UDP only
    if TYPE == 3:
        print('  Please select your preferred unit convention')
        print('  Individual units can be adjusted in the console')
        print('    1) Metric WX (\u00b0C, mb,   m/s, mm, km) [default]')
        print('    2) Metric    (\u00b0C, mb,   kph, cm, km)')
        print('    3) Imperial  (\u00b0F, inHg, mph, in, miles)')
        UNITS = input('    > ') or '1'
        print('')
        while True:
            if UNITS == '1' or UNITS == '2' or UNITS == '3':
                if UNITS == '1':
                    print('  Metric WX units selected')
                elif UNITS == '2':
                    print('  Metric units selected')
                elif UNITS == '3':
                    print('  Imperial units selected')        
                UNITS = int(UNITS)    
                print('')
                break
            else:
                print('  Unit convention not recognised')
                UNITS = input('  Please select your preferred unit convention: ') or '1'
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
                if section in udp_input and key in udp_input[section]:
                    write_config_key(config, section, key, udp_input[section][key])
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

    #  VERSION UNCHANGED. VERIFY STATION AND DEVICE DETAILS FOR EXISTING 
    # CONFIGURATION
    # --------------------------------------------------------------------------
    elif version.parse(current_version) == version.parse(latest_version):
        if int(current_config['System']['rest_api']):
            current_config = verify_station(current_config)
        with open('wfpiconsole.ini', 'w') as config_file:
            current_config.write(config_file)

def verify_station(config):

    # Skip verification if running example config
    if not  config['Keys']['WeatherFlow'] or not config['Station']['StationID']:
        return config

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

    # Verify station details
    config_key = ['Latitude', 'Longitude', 'Elevation', 'Timezone', 'Name']
    api_key    = ['latitude', 'longitude', 'elevation', 'timezone', 'station_name']
    for idx, key in enumerate(config_key):
        if config['Station'][key] != str(STATION[api_key[idx]]):
            config.set('Station', key, str(STATION[api_key[idx]]))
            Logger.info('Config: Updating station ' + key.lower())

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

    # Set TEMPEST flag if required
    if key == 'TempestID' and value:
        TEMPEST = True

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
    global TYPE
    global UNITS

    # Define required variables
    key_required = True

    # GET VALUE OF userInput KEY TYPE
    # --------------------------------------------------------------------------
    if details['Type'] in ['userInput']:

        # Determine whether userInput keys are required based on specified 
        # connection type
        if key in ['WeatherFlow', 'CheckWX', 'StationID'] and TYPE == 3:
            print('  ' + key + ' key not required for UDP only connections')
            value = ''
            key_required = False

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

        # Skip device IDs when connection type = 3
        if section == 'Station' and 'ID' in key and TYPE == 3:
            value = ''
            key_required = False

        # Skip device ID keys for devices that are not present
        if 'Tempest' in key and not TEMPEST:
            value = ''
            key_required = False
        elif 'Sky' in key and TEMPEST:
            value = ''
            key_required = False
        elif 'OutAir' in key and TEMPEST:
            value = ''
            key_required = False
        elif 'InAir' in key and not INDOORAIR:
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
                except KeyError:
                    break

        # Write userInput Key value pair to configuration file
        config.set(section, key, str(value))

    # GET VALUE OF dependent KEY TYPE
    # --------------------------------------------------------------------------
    elif details['Type'] in ['dependent']:

        # Get dependent Key value
        if key == 'IndoorTemp':
            if config['Station']['InAirID'] or config['Station']['InAirSN']:
                value = '1'
            else:
                value = '0'
        elif section == 'Units':
            value = details['Value'][UNITS]
        elif section == 'System':
            if key == 'Connection':
                if TYPE == 1:
                    value = 'Websocket'
                elif TYPE in [2, 3]:
                    value = 'UDP'
            elif key == 'rest_api':
                if TYPE in [1, 2]:
                    value = '1'
                elif TYPE == 3:
                    value = '0'
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
                print(TEMPEST)
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
    global TYPE

    # Validate CheckWX API key
    RETRIES = 0
    if 'Keys' in Config:
        if 'CheckWX' in Config['Keys'] and CHECKWX is None and TYPE != 3:
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
        if 'WeatherFlow' in Config['Keys'] and 'StationID' in Config['Station'] and STATION is None and TYPE != 3:
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
        prompt = ' [y/n] (y) '
    elif Default == 'no':
        prompt = ' [y/n] (n) '
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
    default =                    collections.OrderedDict()
    default['Keys'] =            collections.OrderedDict([('Description',    '  API keys'),
                                                          ('WeatherFlow',    {'Type': 'userInput', 'State': 'required',         'Desc': 'WeatherFlow Access Token',     'Format': str}),
                                                          ('CheckWX',        {'Type': 'userInput', 'State': 'required',         'Desc': 'CheckWX API Key',              'Format': str, })])
    default['Station'] =         collections.OrderedDict([('Description',    '  Station and device IDs'),
                                                          ('StationID',      {'Type': 'userInput', 'State': 'required',         'Desc': 'Station ID',                   'Format': int}),
                                                          ('TempestID',      {'Type': 'userInput', 'State': 'required',         'Desc': 'TEMPEST device ID',            'Format': int,}),
                                                          ('TempestSN',      {'Type': 'request',   'Source': 'station',         'Desc': 'TEMPEST serial number'}),
                                                          ('SkyID',          {'Type': 'userInput', 'State': 'required',         'Desc': 'SKY device ID',                'Format': int,}),
                                                          ('SkySN',          {'Type': 'request',   'Source': 'station',         'Desc': 'SKY serial number'}),
                                                          ('OutAirID',       {'Type': 'userInput', 'State': 'required',         'Desc': 'outdoor AIR device ID',        'Format': int, }),
                                                          ('OutAirSN',       {'Type': 'request',   'Source': 'station',         'Desc': 'outdoor AIR serial number'}),
                                                          ('InAirID',        {'Type': 'userInput', 'State': 'required',         'Desc': 'indoor AIR device ID',         'Format': int, }),
                                                          ('InAirSN',        {'Type': 'request',   'Source': 'station',         'Desc': 'indoor AIR serial number'}),
                                                          ('TempestHeight',  {'Type': 'request',   'Source': 'station',         'Desc': 'height of TEMPEST'}),
                                                          ('SkyHeight',      {'Type': 'request',   'Source': 'station',         'Desc': 'height of SKY'}),
                                                          ('OutAirHeight',   {'Type': 'request',   'Source': 'station',         'Desc': 'height of outdoor AIR'}),
                                                          ('Latitude',       {'Type': 'request',   'Source': 'station',         'Desc': 'station latitude',             'Value': '51.5072'}),
                                                          ('Longitude',      {'Type': 'request',   'Source': 'station',         'Desc': 'station longitude',            'Value': '0.1276'}),
                                                          ('Elevation',      {'Type': 'request',   'Source': 'station',         'Desc': 'station elevation',            'Value': '11'}),
                                                          ('Timezone',       {'Type': 'request',   'Source': 'station',         'Desc': 'station timezone',             'Value': 'Europe/London'}),
                                                          ('Name',           {'Type': 'request',   'Source': 'station',         'Desc': 'station name',                 'Value': 'London, UK'})])
    default['Units'] =           collections.OrderedDict([('Description',    '  Observation units'),
                                                          ('Temp',           {'Type': 'request',   'Source': 'observation',     'Desc': 'station temperature units',    'Value': 'c'}),
                                                          ('Pressure',       {'Type': 'request',   'Source': 'observation',     'Desc': 'station pressure units',       'Value': 'mb'}),
                                                          ('Wind',           {'Type': 'request',   'Source': 'observation',     'Desc': 'station wind units',           'Value': 'mph'}),
                                                          ('Direction',      {'Type': 'request',   'Source': 'observation',     'Desc': 'station direction units',      'Value': 'cardinal'}),
                                                          ('Precip',         {'Type': 'request',   'Source': 'observation',     'Desc': 'station precipitation units',  'Value': 'mm'}),
                                                          ('Distance',       {'Type': 'request',   'Source': 'observation',     'Desc': 'station distance units',       'Value': 'km'}),
                                                          ('Other',          {'Type': 'request',   'Source': 'observation',     'Desc': 'station other units',          'Value': 'metric'})])
    default['Display'] =         collections.OrderedDict([('Description',    '  Display settings'),
                                                          ('TimeFormat',     {'Type': 'default',   'Value': '24 hr',            'Desc': 'time format'}),
                                                          ('DateFormat',     {'Type': 'default',   'Value': 'Mon, 01 Jan 0000', 'Desc': 'date format'}),
                                                          ('LightningPanel', {'Type': 'default',   'Value': '1',                'Desc': 'lightning panel toggle'}),
                                                          ('IndoorTemp',     {'Type': 'dependent',                              'Desc': 'indoor temperature toggle'}),
                                                          ('Cursor',         {'Type': 'default',   'Value': '1',                'Desc': 'cursor toggle'}),
                                                          ('Border',         {'Type': 'default',   'Value': '1',                'Desc': 'border toggle'}),
                                                          ('Fullscreen',     {'Type': 'default',   'Value': '1',                'Desc': 'fullscreen toggle'}),
                                                          ('Width',          {'Type': 'default',   'Value': '800',              'Desc': 'console width (pixels)'}),
                                                          ('Height',         {'Type': 'default',   'Value': '480',              'Desc': 'console height (pixels)'})])
    default['FeelsLike'] =       collections.OrderedDict([('Description',    '  "Feels Like" temperature cut-offs'),
                                                          ('ExtremelyCold',  {'Type': 'default',   'Value': '-5',               'Desc': '"Feels extremely cold" cut-off temperature'}),
                                                          ('FreezingCold',   {'Type': 'default',   'Value': '0',                'Desc': '"Feels freezing cold" cut-off temperature'}),
                                                          ('VeryCold',       {'Type': 'default',   'Value': '5',                'Desc': '"Feels very cold" cut-off temperature'}),
                                                          ('Cold',           {'Type': 'default',   'Value': '10',               'Desc': '"Feels cold" cut-off temperature'}),
                                                          ('Mild',           {'Type': 'default',   'Value': '15',               'Desc': '"Feels mild" cut-off temperature'}),
                                                          ('Warm',           {'Type': 'default',   'Value': '20',               'Desc': '"Feels warm" cut-off temperature'}),
                                                          ('Hot',            {'Type': 'default',   'Value': '25',               'Desc': '"Feels hot" cut-off temperature'}),
                                                          ('VeryHot',        {'Type': 'default',   'Value': '30',               'Desc': '"Feels very hot" cut-off temperature'})])
    default['PrimaryPanels'] =   collections.OrderedDict([('Description',    '  Primary panel layout'),
                                                          ('PanelOne',       {'Type': 'default',   'Value': 'Forecast',         'Desc': 'Primary display for Panel One'}),
                                                          ('PanelTwo',       {'Type': 'default',   'Value': 'Temperature',      'Desc': 'Primary display for Panel Two'}),
                                                          ('PanelThree',     {'Type': 'default',   'Value': 'WindSpeed',        'Desc': 'Primary display for Panel Three'}),
                                                          ('PanelFour',      {'Type': 'default',   'Value': 'SunriseSunset',    'Desc': 'Primary display for Panel Four'}),
                                                          ('PanelFive',      {'Type': 'default',   'Value': 'Rainfall',         'Desc': 'Primary display for Panel Five'}),
                                                          ('PanelSix',       {'Type': 'default',   'Value': 'Barometer',        'Desc': 'Primary display for Panel Six'})])
    default['SecondaryPanels'] = collections.OrderedDict([('Description',    '  Secondary panel layout'),
                                                          ('PanelOne',       {'Type': 'default',   'Value': 'Sager',            'Desc': 'Secondary display for Panel One'}),
                                                          ('PanelTwo',       {'Type': 'default',   'Value': '',                 'Desc': 'Secondary display for Panel Two'}),
                                                          ('PanelThree',     {'Type': 'default',   'Value': '',                 'Desc': 'Secondary display for Panel Three'}),
                                                          ('PanelFour',      {'Type': 'default',   'Value': 'MoonPhase',        'Desc': 'Secondary display for Panel Four'}),
                                                          ('PanelFive',      {'Type': 'default',   'Value': '',                 'Desc': 'Secondary display for Panel Five'}),
                                                          ('PanelSix',       {'Type': 'default',   'Value': 'Lightning',        'Desc': 'Secondary display for Panel Six'})])
    default['System'] =          collections.OrderedDict([('Description',    '  System settings'),
                                                          ('Connection',     {'Type': 'dependent',                              'Desc': 'Connection type'}),
                                                          ('rest_api',       {'Type': 'dependent',                              'Desc': 'REST API services'}),
                                                          ('SagerInterval',  {'Type': 'default',   'Value': '6',                'Desc': 'Interval in hours between Sager Forecasts'}),
                                                          ('Timeout',        {'Type': 'default',   'Value': '20',               'Desc': 'Timeout in seconds for API requests'}),
                                                          ('Hardware',       {'Type': 'default',   'Value': hardware,           'Desc': 'Hardware type'}),
                                                          ('Version',        {'Type': 'default',   'Value': ver,                'Desc': 'Version number'})])

    # Return default configuration
    return default


def udp_input_fields():

    """ Generates the default configuration required by the Raspberry Pi Python
        console running in UDP mode for WeatherFlow Tempest and Smart Home 
        Weather Stations.

    OUTPUT:
        Default         Default configuration required by PiConsole

    """

    # DEFINE DEFAULT CONFIGURATION SECTIONS, KEY NAMES, AND KEY DETAILS AS
    # ORDERED DICTS
    # --------------------------------------------------------------------------
    udp_input =                    collections.OrderedDict()
    udp_input['Station'] =         collections.OrderedDict([('TempestSN',      {'Type': 'userInput',   'State': 'required',   'Desc': 'TEMPEST serial number',      'Format': str}),
                                                            ('SkySN',          {'Type': 'userInput',   'State': 'required',   'Desc': 'SKY serial number',          'Format': str}),
                                                            ('OutAirSN',       {'Type': 'userInput',   'State': 'required',   'Desc': 'outdoor AIR serial number',  'Format': str}),
                                                            ('InAirSN',        {'Type': 'userInput',   'State': 'required',   'Desc': 'indoor AIR serial number',   'Format': str}),
                                                            ('TempestHeight',  {'Type': 'userInput',   'State': 'required',   'Desc': 'TEMPEST height',             'Format': float}),
                                                            ('SkyHeight',      {'Type': 'userInput',   'State': 'required',   'Desc': 'SKY height',                 'Format': float}),
                                                            ('OutAirHeight',   {'Type': 'userInput',   'State': 'required',   'Desc': 'outdoor AIR height',         'Format': float}),
                                                            ('Latitude',       {'Type': 'userInput',   'State': 'required',   'Desc': 'station latitude',           'Format': float}),
                                                            ('Longitude',      {'Type': 'userInput',   'State': 'required',   'Desc': 'station longitude',          'Format': float}),
                                                            ('Elevation',      {'Type': 'userInput',   'State': 'required',   'Desc': 'station elevation',          'Format': float}),
                                                            ('Timezone',       {'Type': 'userInput',   'State': 'required',   'Desc': 'station timezone',           'Format': str}),
                                                            ('Name',           {'Type': 'userInput',   'State': 'required',   'Desc': 'station name',               'Format': str})])
    udp_input['Units'] =           collections.OrderedDict([('Description',    '  Observation units'),
                                                            ('Temp',           {'Type': 'dependent',   'Desc': 'station temperature units',    'Value': {1: 'c',        2: 'c',        3: 'f'}}),
                                                            ('Pressure',       {'Type': 'dependent',   'Desc': 'station pressure units',       'Value': {1: 'mb',       2: 'mb',       3: 'inhg'}}),
                                                            ('Wind',           {'Type': 'dependent',   'Desc': 'station wind units',           'Value': {1: 'mps',      2: 'kph',      3: 'mph'}}),
                                                            ('Direction',      {'Type': 'dependent',   'Desc': 'station direction units',      'Value': {1: 'cardinal', 2: 'cardinal', 3: 'cardinal'}}),
                                                            ('Precip',         {'Type': 'dependent',   'Desc': 'station precipitation units',  'Value': {1: 'mm',       2: 'cm',       3: 'in'}}),
                                                            ('Distance',       {'Type': 'dependent',   'Desc': 'station distance units',       'Value': {1: 'km',       2: 'km',       3: 'mi'}}),
                                                            ('Other',          {'Type': 'dependent',   'Desc': 'station other units',          'Value': {1: 'metric',   2: 'metric',   3: 'imperial'}})])

    # Return default configuration
    return udp_input

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
