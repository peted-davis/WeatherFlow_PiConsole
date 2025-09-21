""" Defines the configuration .ini files required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2025 Peter Davis

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
from tzlocal        import get_localzone
import configparser
import collections
import subprocess
import requests
import platform
import sys
import os

# Define wfpiconsole version number
ver = 'v25.9.2'

# Define required variables
TEMPEST       = False
INDOORAIR     = False
STATION       = None
OBSERVATION   = None
CHECKWX       = None
CONNECTION    = None
UNITS         = None
idx           = None
MAXRETRIES    = 3

# Determine current system
if os.path.exists('/proc/device-tree/model'):
    proc = subprocess.Popen(['cat', '/proc/device-tree/model'], stdout=subprocess.PIPE)
    hardware = proc.stdout.read().decode('utf-8')
    proc.kill()
    if 'Raspberry Pi 5' in hardware:
        hardware = 'Pi5'
    elif 'Raspberry Pi 4' in hardware:
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
    global CONNECTION, UNITS

    # Load default configuration dictionary
    default_config = default_config_file()

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
    if query_user('Would you like to install a minimal configuration file \n'
                  + '  for demonstration purposes or advanced setup?*', 'no'):

        # Generate minimal configuration file
        try:
            # Open new configuration object
            config = configparser.ConfigParser(allow_no_value=True)
            config.optionxform = str

            # Loop over all sections and keys in default configuration
            for section in default_config:
                config.add_section(section)
                for key in default_config[section]:
                    if key != 'description':
                        if 'value' in default_config[section][key]:
                            config.set(section, key, str(default_config[section][key]['value']))
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
    CONNECTION = input('    > ') or '1'
    print('')
    while True:
        if CONNECTION == '1' or CONNECTION == '2' or CONNECTION == '3':
            if CONNECTION == '1':
                print('  Websocket and REST API selected')
            elif CONNECTION == '2':
                print('  UDP and REST API selected')
            elif CONNECTION == '3':
                print('  UDP only selected')
            CONNECTION = int(CONNECTION)
            print('')
            break
        else:
            print('  Connection type not recognised')
            CONNECTION = input('  Please select your preferred connection type: ') or '1'
            print('')

    # Determine preferred unit convention if connection type is UDP only
    if CONNECTION == 3:
        print('  Please select your preferred unit convention')
        print('  Individual units can be adjusted in the console')
        print('    1) Metric WX (C, mb,   m/s, mm, km) [default]')
        print('    2) Metric    (C, mb,   kph, cm, km)')
        print('    3) Imperial  (F, inHg, mph, in, miles)')
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
    for section in default_config:

        # Add section to user configuration file
        config.add_section(section)

        # Add remaining sections to user configuration file
        for key in default_config[section]:
            if key == 'description':
                print(default_config[section][key])
                print('  ---------------------------------')
            else:
                if CONNECTION == 3 and section in udp_input and key in udp_input[section]:
                    write_config_key(config, section, key, udp_input[section][key])
                else:
                    write_config_key(config, section, key, default_config[section][key])
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
    latest_version = default_config_file()['System']['Version']['value']

    # Load current user configuration file
    current_config = configparser.ConfigParser(allow_no_value=True)
    current_config.optionxform = str
    current_config.read('wfpiconsole.ini')
    current_version = current_config['System']['Version']

    # NEW VERSION DETECTED. GENERATE UPDATED CONFIGURATION FILE
    # --------------------------------------------------------------------------
    if version.parse(current_version) < version.parse(latest_version):

        # Print progress dialogue to screen
        print(''                                                     , flush=True)
        print('  ===================================================', flush=True)
        print('  New version detected                               ', flush=True)
        print('  Starting wfpiconsole configuration wizard          ', flush=True)
        print('  ===================================================', flush=True)
        print(''                                                     , flush=True)
        print('  Required fields are marked with an asterix (*)     ', flush=True)
        print(''                                                     , flush=True)

        # Create new config parser object to hold updated user configuration file
        new_config = configparser.ConfigParser(allow_no_value=True)
        new_config.optionxform = str

        # Loop through all sections in default configuration dictionary. Take
        # existing key values from current configuration file
        for section in default_config_file():
            changes = False
            new_config.add_section(section)
            for key in default_config_file()[section]:
                if key == 'description':
                    print(default_config_file()[section][key]  , flush=True)
                    print('  ---------------------------------', flush=True)
                else:
                    if current_config.has_option(section, key):
                        if update_required(key, current_version):
                            changes = True
                            write_config_key(new_config, section, key, default_config_file()[section][key])
                        else:
                            copy_config_key(new_config, current_config, section, key, default_config_file()[section][key])
                    if not current_config.has_option(section, key):
                        changes = True
                        write_config_key(new_config, section, key, default_config_file()[section][key])
                    elif key == 'Version':
                        changes = True
                        new_config.set(section, key, latest_version)
                        print('  Updating version number to: ' + latest_version, flush=True)
            if not changes:
                print('  No changes required', flush=True)
            print('', flush=True)

        # Verify station details for updated configuration
        new_config = verify_station(new_config)

        # Write updated configuration file to disk
        with open('wfpiconsole.ini', 'w') as config_file:
            new_config.write(config_file)

    #  VERSION UNCHANGED. VERIFY STATION AND DEVICE DETAILS FOR EXISTING
    # CONFIGURATION
    # --------------------------------------------------------------------------
    elif version.parse(current_version) == version.parse(latest_version):
        if current_config['System']['rest_api'] and int(current_config['System']['rest_api']):
            current_config = verify_station(current_config)
        with open('wfpiconsole.ini', 'w') as config_file:
            current_config.write(config_file)


def verify_station(config):

    # Skip verification if running example config
    if not config['Keys']['WeatherFlow'] or not config['Station']['StationID']:
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
    if details['type'] == 'fixed':
        value = details['value']

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
    global CONNECTION
    global UNITS

    # Define required variables
    key_required = True

    # GET value OF user_input KEY type
    # --------------------------------------------------------------------------
    if details['type'] in ['user_input']:

        # Determine whether user_input keys are required based on specified
        # connection type
        if key in ['WeatherFlow', 'CheckWX', 'StationID'] and CONNECTION == 3:
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
        if section == 'Station' and 'ID' in key and CONNECTION == 3:
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

        # user_input key required. Get value from user
        if key_required:
            while True:
                if details['state'] == 'required':
                    string = '  Please enter your ' + details['desc'] + '*: '
                else:
                    string = '  Please enter your ' + details['desc'] + ': '
                value = input(string)

                # user_input key value is empty. Check if user_input key is
                # required
                if not value and details['state'] == 'required':
                    print('    ' + details['desc'] + ' cannot be empty. Please try again')
                    continue
                elif not value and details['state'] == 'optional':
                    break

                # Check if user_input key value matches required format
                try:
                    value = details['format'](value)
                    break
                except ValueError:
                    print('    ' + details['desc'] + ' format is not valid. Please try again')
                except KeyError:
                    break

        # Write user_input Key value pair to configuration file
        config.set(section, key, str(value))

    # GET value OF dependent KEY type
    # --------------------------------------------------------------------------
    elif details['type'] in ['dependent']:

        # Get dependent Key value
        if key == 'IndoorTemp':
            if config['Station']['InAirID'] or config['Station']['InAirSN']:
                value = '1'
            else:
                value = '0'
        elif section == 'Units':
            value = details['value'][UNITS]
        elif section == 'System':
            if key == 'Connection':
                if CONNECTION == 1 or CONNECTION is None:
                    value = 'Websocket'
                elif CONNECTION in [2, 3]:
                    value = 'UDP'
            elif key == 'rest_api':
                if CONNECTION in [1, 2] or CONNECTION is None:
                    value = '1'
                elif CONNECTION == 3:
                    value = '0'
            print('  Adding ' + details['desc'] + ': ' + value)

        # Write dependent Key value pair to configuration file
        config.set(section, key, str(value))

    # GET value OF default OR fixed KEY type
    # --------------------------------------------------------------------------
    elif details['type'] in ['default', 'fixed']:

        # Get default or fixed Key value
        if key in ['ExtremelyCold', 'FreezingCold', 'VeryCold', 'Cold', 'Mild', 'Warm', 'Hot', 'VeryHot']:
            if 'c' in config['Units']['Temp']:
                value = details['value']
            elif 'f' in config['Units']['Temp']:
                value = str(int(float(details['value']) * 9 / 5 + 32))
        else:
            value = details['value']

        # Write default or fixed Key value pair to configuration file
        print('  Adding ' + details['desc'] + ': ' + value)
        config.set(section, key, str(value))

    # GET value OF request KEY type
    # --------------------------------------------------------------------------
    elif details['type'] in ['request']:

        # Define local variables
        value = ''

        # Get Observation metadata from WeatherFlow API
        RETRIES = 0
        if details['source'] == 'observation' and OBSERVATION is None:
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
                        if 'devices' in station:
                            for device in station['devices']:
                                if 'device_type' in device:
                                    if str(device['device_id']) == config['Station']['TempestID']:
                                        if device['device_type'] == 'ST':
                                            if key == 'TempestHeight':
                                                value = device['device_meta']['agl']
                                            elif key == 'TempestSN':
                                                value = device['serial_number']
                    if not value and value != 0:
                        input_str = '    TEMPEST not found. Please re-enter your TEMPEST device ID*: '
                        while True:
                            ID = input(input_str)
                            if not ID:
                                print('    TEMPEST device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                input_str = '    TEMPEST device ID not valid. Please re-enter your TEMPEST device ID*: '
                        config.set('Station', 'TempestID', str(ID))
                    else:
                        break

        # Validate outdoor AIR device ID and get height above ground of serial
        # number of outdoor AIR
        if section == 'Station':
            if key in ['OutAirHeight', 'OutAirSN'] and not TEMPEST:
                while True:
                    for station in STATION['stations']:
                        if 'devices' in station:
                            for device in station['devices']:
                                if 'device_type' in device:
                                    if str(device['device_id']) == config['Station']['OutAirID']:
                                        if device['device_type'] == 'AR':
                                            value = device['device_meta']['agl']
                    if not value and value != 0:
                        input_str = '    Outdoor AIR not found. Please re-enter your Outdoor AIR device ID*: '
                        while True:
                            ID = input(input_str)
                            if not ID:
                                print('    Outdoor AIR device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                input_str = '    Outdoor AIR device ID not valid. Please re-enter your Outdoor AIR device ID*: '
                        config.set('Station', 'OutAirID', str(ID))
                    else:
                        break

        # Validate SKY device ID and get height above ground or serial number of
        # SKY
        if section == 'Station':
            if key in ['SkyHeight',  'SkySN'] and not TEMPEST:
                while True:
                    for station in STATION['stations']:
                        if 'devices' in station:
                            for device in station['devices']:
                                if 'device_type' in device:
                                    if str(device['device_id']) == config['Station']['SkyID']:
                                        if device['device_type'] == 'SK':
                                            if key == 'SkyHeight':
                                                value = device['device_meta']['agl']
                                            elif key == 'SkySN':
                                                value = device['serial_number']
                    if not value and value != 0:
                        input_str = '    SKY not found. Please re-enter your SKY device ID*: '
                        while True:
                            ID = input(input_str)
                            if not ID:
                                print('    SKY device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                input_str = '    SKY device ID not valid. Please re-enter your SKY device ID*: '
                        config.set('Station', 'SkyID', str(ID))
                    else:
                        break

        # Validate outdoor AIR device ID and get height above ground of serial
        # number of outdoor AIR
        if section == 'Station':
            if key in 'InAirSN' and config['Station']['InAirID']:
                while True:
                    for station in STATION['stations']:
                        if 'devices' in station:
                            for device in station['devices']:
                                if 'device_type' in device:
                                    if str(device['device_id']) == config['Station']['InAirID']:
                                        if device['device_type'] == 'AR':
                                            value = device['serial_number']
                    if not value and value != 0:
                        input_str = '    Indoor AIR not found. Please re-enter your Indoor AIR device ID*: '
                        while True:
                            ID = input(input_str)
                            if not ID:
                                print('    Indoor AIR device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                input_str = '    Indoor AIR device ID not valid. Please re-enter your Indoor AIR device ID*: '
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
            print('  Adding ' + details['desc'] + ': ' + str(value))
        config.set(section, key, str(value))

    # Validate API keys
    validate_API_keys(config)


def validate_API_keys(config):

    """ Validates API keys entered in the config file

    INPUTS
        config              Station configuration

    """

    # Define global variables
    global STATION
    global CHECKWX
    global idx
    global CONNECTION

    # Validate CheckWX API key
    RETRIES = 0
    if 'Keys' in config:
        if 'CheckWX' in config['Keys'] and CHECKWX is None and CONNECTION != 3:
            while True:
                header = {'X-API-Key': config['Keys']['CheckWX']}
                URL = 'https://api.checkwx.com/station/EGLL'
                CHECKWX = requests.get(URL, headers=header).json()
                if 'error' in CHECKWX:
                    if 'Unauthorized' in CHECKWX['error']:
                        input_string = '    Access not authorized. Please re-enter your CheckWX API key*: '
                        while True:
                            api_key = input(input_string)
                            if not api_key:
                                print('    CheckWX API key cannot be empty. Please try again')
                            else:
                                break
                        config.set('Keys', 'CheckWX', str(api_key))
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
    if 'Keys' in config and 'Station' in config:
        if 'WeatherFlow' in config['Keys'] and 'StationID' in config['Station'] and STATION is None and CONNECTION != 3:
            while True:
                url_template = 'https://swd.weatherflow.com/swd/rest/stations/?token={}'
                URL = url_template.format(config['Keys']['WeatherFlow'])
                STATION = requests.get(URL).json()
                if 'status' in STATION:
                    if 'UNAUTHORIZED' in STATION['status']['status_message']:
                        input_string = '    Access not authorized. Please re-enter your WeatherFlow Personal Access Token*: '
                        while True:
                            token = input(input_string)
                            if not token:
                                print('    Personal Access Token cannot be empty. Please try again')
                            else:
                                break
                        config.set('Keys', 'WeatherFlow', str(token))
                        RETRIES += 1
                    elif 'SUCCESS' in STATION['status']['status_message']:
                        if 'stations' in STATION:
                            for ii, station in enumerate(STATION['stations']):
                                if station['station_id'] == int(config['Station']['StationID']):
                                    idx = ii
                            if idx is not None:
                                break
                            else:
                                input_string = '    Station not found. Please re-enter your Station ID*: '
                                while True:
                                    ID = input(input_string)
                                    if not ID:
                                        print('    Station ID cannot be empty. Please try again')
                                        continue
                                    try:
                                        ID = int(ID)
                                        break
                                    except ValueError:
                                        input_string = '    Station ID not valid. Please re-enter your Station ID*: '
                                config.set('Station', 'StationID', str(ID))
                                RETRIES += 1
                        else:
                            RETRIES += 1
                    else:
                        RETRIES += 1
                else:
                    RETRIES += 1
                if RETRIES >= MAXRETRIES:
                    sys.exit('\n    Error: unable to fetch station metadata')


def query_user(question, default=None):

    """ Ask a yes/no question via raw_input() and return their answer.

    INPUTS
        question                Query string presented to user
        default                 Presumed answer if the user just hits <Enter>.
                                It must be "yes", "no" or None

    OUTPUT
        valid                   True for "yes" or False for "no"
    """

    # Define valid reponses and prompt based on specified default answer
    valid = {'yes': True, 'y': True, 'ye': True, 'no': False, 'n': False}
    if default is None:
        prompt = ' [y/n] '
    elif default == 'yes':
        prompt = ' [y/n] (y) '
    elif default == 'no':
        prompt = ' [y/n] (n) '
    else:
        raise ValueError('invalid default answer: "%s"' % default)

    # Display question to user
    while True:
        sys.stdout.write('  ' + question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write('    Please respond with "yes"/"no" or "y"/"n"\n')


def default_config_file():

    """ Generates the default configuration required by the Raspberry Pi Python
        console for Weather Flow Smart Home Weather Stations.

    OUTPUT:
        Default         Default configuration required by PiConsole

    """

    # DEFINE DEFAULT CONFIGURATION SECTIONS, KEY NAMES, AND KEY DETAILS AS
    # ORDERED DICTS
    # --------------------------------------------------------------------------
    config =                    collections.OrderedDict()
    config['Keys'] =            collections.OrderedDict([('description',           '  API keys'),
                                                         ('WeatherFlow',           {'type': 'user_input', 'state': 'required',         'desc': 'WeatherFlow Access Token',     'format': str}),
                                                         ('CheckWX',               {'type': 'user_input', 'state': 'required',         'desc': 'CheckWX API Key',              'format': str})])
    config['Station'] =         collections.OrderedDict([('description',           '  Station and device IDs'),
                                                         ('StationID',             {'type': 'user_input', 'state': 'required',         'desc': 'Station ID',                   'format': int}),
                                                         ('TempestID',             {'type': 'user_input', 'state': 'required',         'desc': 'TEMPEST device ID',            'format': int}),
                                                         ('TempestSN',             {'type': 'request',    'source': 'station',         'desc': 'TEMPEST serial number'}),
                                                         ('SkyID',                 {'type': 'user_input', 'state': 'required',         'desc': 'SKY device ID',                'format': int}),
                                                         ('SkySN',                 {'type': 'request',    'source': 'station',         'desc': 'SKY serial number'}),
                                                         ('OutAirID',              {'type': 'user_input', 'state': 'required',         'desc': 'outdoor AIR device ID',        'format': int}),
                                                         ('OutAirSN',              {'type': 'request',    'source': 'station',         'desc': 'outdoor AIR serial number'}),
                                                         ('InAirID',               {'type': 'user_input', 'state': 'required',         'desc': 'indoor AIR device ID',         'format': int}),
                                                         ('InAirSN',               {'type': 'request',    'source': 'station',         'desc': 'indoor AIR serial number'}),
                                                         ('TempestHeight',         {'type': 'request',    'source': 'station',         'desc': 'height of TEMPEST'}),
                                                         ('SkyHeight',             {'type': 'request',    'source': 'station',         'desc': 'height of SKY'}),
                                                         ('OutAirHeight',          {'type': 'request',    'source': 'station',         'desc': 'height of outdoor AIR'}),
                                                         ('Latitude',              {'type': 'request',    'source': 'station',         'desc': 'station latitude',             'value': '51.5072'}),
                                                         ('Longitude',             {'type': 'request',    'source': 'station',         'desc': 'station longitude',            'value': '0.1276'}),
                                                         ('Elevation',             {'type': 'request',    'source': 'station',         'desc': 'station elevation',            'value': '11'}),
                                                         ('Timezone',              {'type': 'request',    'source': 'station',         'desc': 'station timezone',             'value': 'Europe/London'}),
                                                         ('Name',                  {'type': 'request',    'source': 'station',         'desc': 'station name',                 'value': 'London, UK'})])
    config['Units'] =           collections.OrderedDict([('description',           '  Observation units'),
                                                         ('Temp',                  {'type': 'request',   'source': 'observation',     'desc': 'station temperature units',    'value': 'c'}),
                                                         ('Pressure',              {'type': 'request',   'source': 'observation',     'desc': 'station pressure units',       'value': 'mb'}),
                                                         ('Wind',                  {'type': 'request',   'source': 'observation',     'desc': 'station wind units',           'value': 'mph'}),
                                                         ('Direction',             {'type': 'request',   'source': 'observation',     'desc': 'station direction units',      'value': 'cardinal'}),
                                                         ('Precip',                {'type': 'request',   'source': 'observation',     'desc': 'station precipitation units',  'value': 'mm'}),
                                                         ('Distance',              {'type': 'request',   'source': 'observation',     'desc': 'station distance units',       'value': 'km'}),
                                                         ('Other',                 {'type': 'request',   'source': 'observation',     'desc': 'station other units',          'value': 'metric'})])
    config['Display'] =         collections.OrderedDict([('description',           '  Display settings'),
                                                         ('TimeFormat',            {'type': 'default',   'value': '24 hr',            'desc': 'time format'}),
                                                         ('DateFormat',            {'type': 'default',   'value': 'Mon, 01 Jan 0000', 'desc': 'date format'}),
                                                         ('UpdateNotification',    {'type': 'default',   'value': '1',                'desc': 'update notification toggle'}),
                                                         ('PanelCount',            {'type': 'default',   'value': '6',                'desc': 'number of display panels'}),
                                                         ('LightningPanel',        {'type': 'default',   'value': '1',                'desc': 'lightning panel toggle'}),
                                                         ('lightning_timeout',     {'type': 'default',   'value': '0',                'desc': 'lightning panel timeout'}),
                                                         ('IndoorTemp',            {'type': 'dependent',                              'desc': 'indoor temperature toggle'}),
                                                         ('Cursor',                {'type': 'default',   'value': '1',                'desc': 'cursor toggle'}),
                                                         ('Border',                {'type': 'default',   'value': '1',                'desc': 'border toggle'}),
                                                         ('Fullscreen',            {'type': 'default',   'value': '1',                'desc': 'fullscreen toggle'}),
                                                         ('Width',                 {'type': 'default',   'value': '800',              'desc': 'console width (pixels)'}),
                                                         ('Height',                {'type': 'default',   'value': '480',              'desc': 'console height (pixels)'})])
    config['FeelsLike'] =       collections.OrderedDict([('description',           '  "Feels Like" temperature cut-offs'),
                                                         ('ExtremelyCold',         {'type': 'default',   'value': '-5',               'desc': '"Feels extremely cold" cut-off temperature'}),
                                                         ('FreezingCold',          {'type': 'default',   'value': '0',                'desc': '"Feels freezing cold" cut-off temperature'}),
                                                         ('VeryCold',              {'type': 'default',   'value': '5',                'desc': '"Feels very cold" cut-off temperature'}),
                                                         ('Cold',                  {'type': 'default',   'value': '10',               'desc': '"Feels cold" cut-off temperature'}),
                                                         ('Mild',                  {'type': 'default',   'value': '15',               'desc': '"Feels mild" cut-off temperature'}),
                                                         ('Warm',                  {'type': 'default',   'value': '20',               'desc': '"Feels warm" cut-off temperature'}),
                                                         ('Hot',                   {'type': 'default',   'value': '25',               'desc': '"Feels hot" cut-off temperature'}),
                                                         ('VeryHot',               {'type': 'default',   'value': '30',               'desc': '"Feels very hot" cut-off temperature'})])
    config['PrimaryPanels'] =   collections.OrderedDict([('description',           '  Primary panel layout'),
                                                         ('PanelOne',              {'type': 'default',   'value': 'Forecast',         'desc': 'Primary display for Panel One'}),
                                                         ('PanelTwo',              {'type': 'default',   'value': 'Temperature',      'desc': 'Primary display for Panel Two'}),
                                                         ('PanelThree',            {'type': 'default',   'value': 'WindSpeed',        'desc': 'Primary display for Panel Three'}),
                                                         ('PanelFour',             {'type': 'default',   'value': 'SunriseSunset',    'desc': 'Primary display for Panel Four'}),
                                                         ('PanelFive',             {'type': 'default',   'value': 'Rainfall',         'desc': 'Primary display for Panel Five'}),
                                                         ('PanelSix',              {'type': 'default',   'value': 'Barometer',        'desc': 'Primary display for Panel Six'})])
    config['SecondaryPanels'] = collections.OrderedDict([('description',           '  Secondary panel layout'),
                                                         ('PanelOne',              {'type': 'default',   'value': 'Sager',            'desc': 'Secondary display for Panel One'}),
                                                         ('PanelTwo',              {'type': 'default',   'value': '',                 'desc': 'Secondary display for Panel Two'}),
                                                         ('PanelThree',            {'type': 'default',   'value': '',                 'desc': 'Secondary display for Panel Three'}),
                                                         ('PanelFour',             {'type': 'default',   'value': 'MoonPhase',        'desc': 'Secondary display for Panel Four'}),
                                                         ('PanelFive',             {'type': 'default',   'value': '',                 'desc': 'Secondary display for Panel Five'}),
                                                         ('PanelSix',              {'type': 'default',   'value': 'Lightning',        'desc': 'Secondary display for Panel Six'})])
    config['System'] =          collections.OrderedDict([('description',           '  System settings'),
                                                         ('Connection',            {'type': 'dependent',                              'desc': 'Connection type',     'value': 'Websocket'}),
                                                         ('rest_api',              {'type': 'dependent',                              'desc': 'REST API services',   'value': 1}),
                                                         ('stats_endpoint',        {'type': 'default',   'value': '0',                'desc': 'Statistics API endpoint toggle'}),
                                                         ('SagerInterval',         {'type': 'default',   'value': '6',                'desc': 'Interval in hours between Sager Forecasts'}),
                                                         ('Timeout',               {'type': 'default',   'value': '20',               'desc': 'Timeout in seconds for API requests'}),
                                                         ('Hardware',              {'type': 'default',   'value': hardware,           'desc': 'Hardware type'}),
                                                         ('Version',               {'type': 'default',   'value': ver,                'desc': 'Version number'})])

    # Return default configuration
    return config


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
    udp_input['Station'] =         collections.OrderedDict([('TempestSN',      {'type': 'user_input',   'state': 'required',             'desc': 'TEMPEST serial number',                  'format': str}),
                                                            ('SkySN',          {'type': 'user_input',   'state': 'required',             'desc': 'SKY serial number',                      'format': str}),
                                                            ('OutAirSN',       {'type': 'user_input',   'state': 'required',             'desc': 'outdoor AIR serial number',              'format': str}),
                                                            ('InAirSN',        {'type': 'user_input',   'state': 'required',             'desc': 'indoor AIR serial number',               'format': str}),
                                                            ('TempestHeight',  {'type': 'user_input',   'state': 'required',             'desc': 'TEMPEST height (meters)',                'format': float}),
                                                            ('SkyHeight',      {'type': 'user_input',   'state': 'required',             'desc': 'SKY height (meters)',                    'format': float}),
                                                            ('OutAirHeight',   {'type': 'user_input',   'state': 'required',             'desc': 'outdoor AIR height (meters)',            'format': float}),
                                                            ('Latitude',       {'type': 'user_input',   'state': 'required',             'desc': 'station latitude (negative for south)',  'format': float}),
                                                            ('Longitude',      {'type': 'user_input',   'state': 'required',             'desc': 'station longitude (negative for west)',  'format': float}),
                                                            ('Elevation',      {'type': 'user_input',   'state': 'required',             'desc': 'station elevation (meters)',             'format': float}),
                                                            ('Name',           {'type': 'user_input',   'state': 'required',             'desc': 'station name',                           'format': str}),
                                                            ('Timezone',       {'type': 'default',     'value': str(get_localzone()),   'desc': 'station timezone'})])
    udp_input['Units'] =           collections.OrderedDict([('description',    '  Observation units'),
                                                            ('Temp',           {'type': 'dependent',   'desc': 'station temperature units',    'value': {1: 'c',        2: 'c',        3: 'f'}}),
                                                            ('Pressure',       {'type': 'dependent',   'desc': 'station pressure units',       'value': {1: 'mb',       2: 'mb',       3: 'inhg'}}),
                                                            ('Wind',           {'type': 'dependent',   'desc': 'station wind units',           'value': {1: 'mps',      2: 'kph',      3: 'mph'}}),
                                                            ('Direction',      {'type': 'dependent',   'desc': 'station direction units',      'value': {1: 'cardinal', 2: 'cardinal', 3: 'cardinal'}}),
                                                            ('Precip',         {'type': 'dependent',   'desc': 'station precipitation units',  'value': {1: 'mm',       2: 'cm',       3: 'in'}}),
                                                            ('Distance',       {'type': 'dependent',   'desc': 'station distance units',       'value': {1: 'km',       2: 'km',       3: 'mi'}}),
                                                            ('Other',          {'type': 'dependent',   'desc': 'station other units',          'value': {1: 'metric',   2: 'metric',   3: 'imperial'}})])

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
