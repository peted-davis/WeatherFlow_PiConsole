""" Defines the configuration .ini files required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2020 Peter Davis

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
import collections


def create(metaData, deviceList, config, context=None):

    """ Generates a new user configuration file from the default configuration
        dictionary. Saves the new user configuration file to wfpiconsole.ini
    """

    # Get version number
    if context:
        packageManager = context.getPackageManager()
        Version = packageManager.getPackageInfo(context.getPackageName(), 0).versionName
    else:
        Version = None

    # Load default configuration dictionary
    default = defaultConfig(Version)

    # Loop through all sections in default configuration dictionary
    for Section in default:

        # Add section to user configuration file
        if Section not in config:
            config.add_section(Section)

        # Write keys to user configuration file
        for Key in default[Section]:
            writeConfigKey(metaData, deviceList, config, Section, Key, default[Section][Key])


def update(config, context=None):

    """ Updates an existing user configuration file by comparing it against the
        default configuration dictionary. Saves the updated user configuration
        file to wfpiconsole.ini
    """

    # Get latest version number
    if context:
        packageManager = context.getPackageManager()
        latestVersion = packageManager.getPackageInfo(context.getPackageName(), 0).versionName
    else:
        return

    # Get current version number
    currentVersion = config['System']['Version']

    # CONVERT DEFAULT CONFIGURATION DICTIONARY INTO .ini FILE
    # --------------------------------------------------------------------------
    # Check if version numbers are different
    if currentVersion != latestVersion:

        print('Update required')

        # Load default configuration dictionary
        default = defaultConfig(latestVersion)

        # Loop through default configuration dictionary and update or add
        # configuration keys to the current user configuration file as required
        for Section in default:
            for Key in default[Section]:
                if config.has_option(Section, Key):
                    if updateRequired(Key, currentVersion) or default[Section][Key]['Type'] == 'fixed':
                        writeConfigKey(None, None, config, Section, Key, default[Section][Key])
                if not config.has_option(Section, Key):
                    print(Section, Key, default[Section][Key])
                    writeConfigKey(None, None, config, Section, Key, default[Section][Key])

        # Loop through current user configuration file and remove all obselete
        # configuration sections and keys as required
        sectionList = []
        for Section in config:
            for Key in config[Section]:
                if Key not in default[Section]:
                    config.remove_option(Section, Key)
        for Section in config:
            if Section not in default:
                sectionList.append(Section)
        for Section in sectionList:
            config.remove_section(Section)


def writeConfigKey(metaData, deviceList, config, Section, Key, keyDetails):

    """ Gets and writes the key value pair to the specified section of the
        station configuration file

    INPUTS
        Config              Station configuration
        Section             Section of station configuration containing key
                            value pair
        Key                 Name of key value pair
        keyDetails          Details (type/description) of key value pair

    """

    # GET VALUE OF Station KEY TYPE
    # -------------------------------------------------------------------------
    if keyDetails['Type'] == 'station':
        if Section == 'Station':
            if Key == 'StationID':
                Value = metaData['station_id']
            if Key in ['Latitude', 'Longitude', 'Timezone', 'Elevation']:
                Value = metaData[Key.lower()]
            if Key == 'Name':
                Value = metaData['station_name']
        if Section in ['Units']:
            Value = metaData['station_units']['units_' + Key.lower()]
        config.set(Section, Key, str(Value))

    # GET VALUE OF Device KEY TYPE
    # -------------------------------------------------------------------------
    if keyDetails['Type'] == 'device':
        Value = ''
        if Section == 'Station':
            if Key == 'TempestID' and 'ST' in deviceList:
                Value = deviceList['ST']['device_id']
            elif Key == 'SkyID' and 'SK' in deviceList:
                Value = deviceList['SK']['device_id']
            elif Key == 'AirID' and 'AR' in deviceList:
                Value = deviceList['AR']['device_id']
            elif Key == 'TempestHeight' and 'ST' in deviceList:
                Value = deviceList['ST']['device_meta']['agl']
            elif Key == 'SkyHeight' and 'SK' in deviceList:
                Value = deviceList['SK']['device_meta']['agl']
            elif Key == 'AirHeight' and 'AR' in deviceList:
                Value = deviceList['AR']['device_meta']['agl']
        config.set(Section, Key, str(Value))

    # GET VALUE OF default OR fixed KEY TYPE
    # -------------------------------------------------------------------------
    elif keyDetails['Type'] in ['default', 'fixed']:
        if Key in ['ExtremelyCold', 'FreezingCold', 'VeryCold', 'Cold', 'Mild', 'Warm', 'Hot', 'VeryHot']:
            if 'c' in config['Units']['Temp']:
                Value = keyDetails['Value']
            elif 'f' in config['Units']['Temp']:
                Value = str(int(float(keyDetails['Value']) * (9 / 5) + 32))
        elif Key == 'BarometerMax':
            Units = ['mb', 'hpa', 'inhg', 'mmhg']
            Max = ['1050', '1050', '31.0', '788']
            Value = Max[Units.index(config['Units']['Pressure'])]
        elif Key == 'BarometerMin':
            Units = ['mb', 'hpa', 'inhg', 'mmhg']
            Min = ['950', '950', '28.0', '713']
            Value = Min[Units.index(config['Units']['Pressure'])]
        else:
            Value = keyDetails['Value']
        config.set(Section, Key, str(Value))


def updateRequired(Key, currentVersion):

    """ List configuration keys that require updating along with the version
    number at which the update must be triggered

    OUTPUT:
        True/False         Boolean indicating whether configuration key needs
                           updating
    """

    # Dictionary holding configuration keys and version numbers
    updatesRequired = {

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


def defaultConfig(Version):

    """ Generates the default configuration required by the Raspberry Pi Python
        console for Weather Flow Smart Home Weather Stations.

    OUTPUT:
        Default         Default configuration required by PiConsole

    """

    # DEFINE DEFAULT CONFIGURATION SECTIONS, KEY NAMES, AND KEY DETAILS AS
    # ORDERED DICTS
    # --------------------------------------------------------------------------
    Default =                    collections.OrderedDict()
    Default['Keys'] =            collections.OrderedDict([('WeatherFlow',    {'Type': 'OAuth2'})])
    Default['Station'] =         collections.OrderedDict([('StationID',      {'Type': 'station'}),
                                                          ('TempestID',      {'Type': 'device'}),
                                                          ('SkyID',          {'Type': 'device'}),
                                                          ('AirID',          {'Type': 'device'}),
                                                          ('TempestHeight',  {'Type': 'device'}),
                                                          ('SkyHeight',      {'Type': 'device'}),
                                                          ('AirHeight',      {'Type': 'device'}),
                                                          ('Latitude',       {'Type': 'station'}),
                                                          ('Longitude',      {'Type': 'station'}),
                                                          ('Elevation',      {'Type': 'station'}),
                                                          ('Timezone',       {'Type': 'station'}),
                                                          ('Name',           {'Type': 'station'})])
    Default['Units'] =           collections.OrderedDict([('Temp',           {'Type': 'station'}),
                                                          ('Pressure',       {'Type': 'station'}),
                                                          ('Wind',           {'Type': 'station'}),
                                                          ('Direction',      {'Type': 'station'}),
                                                          ('Precip',         {'Type': 'station'}),
                                                          ('Distance',       {'Type': 'station'}),
                                                          ('Other',          {'Type': 'station'})])
    Default['Display'] =         collections.OrderedDict([('AlwaysOn',       {'Type': 'default', 'Value': '0'}),
                                                          ('TimeFormat',     {'Type': 'default', 'Value': '24 hr'}),
                                                          ('DateFormat',     {'Type': 'default', 'Value': 'Mon, 01 Jan 0000'}),
                                                          ('LightningPanel', {'Type': 'default', 'Value': '1'}),
                                                          ('TextScale',      {'Type': 'default', 'Value': '1'})])
    Default['FeelsLike'] =       collections.OrderedDict([('ExtremelyCold',  {'Type': 'default', 'Value': '-5'}),
                                                          ('FreezingCold',   {'Type': 'default', 'Value': '0'}),
                                                          ('VeryCold',       {'Type': 'default', 'Value': '5'}),
                                                          ('Cold',           {'Type': 'default', 'Value': '10'}),
                                                          ('Mild',           {'Type': 'default', 'Value': '15'}),
                                                          ('Warm',           {'Type': 'default', 'Value': '20'}),
                                                          ('Hot',            {'Type': 'default', 'Value': '25'}),
                                                          ('VeryHot',        {'Type': 'default', 'Value': '30'})])
    Default['PrimaryPanels'] =   collections.OrderedDict([('PanelOne',       {'Type': 'default', 'Value': 'Forecast'}),
                                                          ('PanelTwo',       {'Type': 'default', 'Value': 'Temperature'}),
                                                          ('PanelThree',     {'Type': 'default', 'Value': 'WindSpeed'}),
                                                          ('PanelFour',      {'Type': 'default', 'Value': 'SunriseSunset'}),
                                                          ('PanelFive',      {'Type': 'default', 'Value': 'Rainfall'}),
                                                          ('PanelSix',       {'Type': 'default', 'Value': 'Barometer'})])
    Default['SecondaryPanels'] = collections.OrderedDict([('PanelOne',       {'Type': 'default', 'Value': ''}),
                                                          ('PanelTwo',       {'Type': 'default', 'Value': ''}),
                                                          ('PanelThree',     {'Type': 'default', 'Value': ''}),
                                                          ('PanelFour',      {'Type': 'default', 'Value': 'MoonPhase'}),
                                                          ('PanelFive',      {'Type': 'default', 'Value': ''}),
                                                          ('PanelSix',       {'Type': 'default', 'Value': 'Lightning'})])
    Default['System'] =          collections.OrderedDict([('BarometerMax',   {'Type': 'fixed'}),
                                                          ('BarometerMin',   {'Type': 'fixed'}),
                                                          ('Timeout',        {'Type': 'fixed', 'Value': '20'}),
                                                          ('Version',        {'Type': 'fixed', 'Value': Version})])

    # Return default configuration
    return Default
