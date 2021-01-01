""" Contains station functions required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2021 Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

# Import required library modules
from lib import requestAPI

# Import required Python modules
from datetime import datetime
import time
import pytz

# Define global variables
NaN = float('NaN')

def getHubStatus(Status,wfpiconsole):

    """ Gets the current status of the hub attached to the station

    INPUTS:
        Status                 Dictionary holding hub status information
        wfpiconsole            wfpiconsole object

    OUTPUT:
        Status                 Dictionary holding hub status information
    """

    # Set hub status based on device status
    deviceStatus = []
    for Key in Status:
        if 'Status' in Key:
            if Status[Key] == '-':
                continue
            else:
                if 'OK' in Status[Key]:
                    deviceStatus.append('OK')
                elif 'Error' in Status[Key]:
                    deviceStatus.append('Error')
    if all(Status == 'Error' for Status in deviceStatus):
        Status['stationStatus'] = '[color=d73027ff]Offline[/color]'
    else:
        Status['stationStatus'] = '[color=9aba2fff]Online[/color]'

    # Get hub firmware version
    Station = wfpiconsole.config['Station']['StationID']
    Data = requestAPI.weatherflow.stationMetaData(Station,wfpiconsole.config)
    if requestAPI.weatherflow.verifyResponse(Data,'stations'):
        Devices = Data.json()['stations'][0]['devices']
        for Device in Devices:
            if Device['device_type'] == 'HB':
                Status['hubFirmware'] = Device['firmware_revision']

def getDeviceStatus(Status,wfpiconsole):

    """ Gets the current status of the devices attached to the station

    INPUTS:
        Status                 Dictionary holding device status information
        wfpiconsole            wfpiconsole object

    OUTPUT:
        Status                 Dictionary holding device status information
    """

    # Define current time in station timezone
    Tz = pytz.timezone(wfpiconsole.config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Get TEMPEST device status
    if wfpiconsole.config['Station']['TempestID']:
        if 'TempestMsg' in wfpiconsole.Obs:
            lastOb         = [x if x != None else NaN for x in wfpiconsole.Obs['TempestMsg']['obs'][0]]
            lastSampleTime = datetime.fromtimestamp(lastOb[0],Tz)
            lastSampleDiff = (Now - lastSampleTime).total_seconds()
            if lastOb[16] != None:
                deviceVoltage = float(lastOb[16])
            else:
                deviceVoltage = NaN
            if lastSampleDiff < 300 and deviceVoltage > 1.9:
                deviceStatus = '[color=9aba2fff]OK[/color]'
            else:
                deviceStatus = '[color=d73027ff]Error[/color]'

            # Store outdoor AIR device status variables
            Status['tempestSampleTime'] = lastSampleTime.strftime('%H:%M:%S')
            Status['tempestVoltage']    = '{:.2f}'.format(deviceVoltage)
            Status['tempestStatus']     = deviceStatus

    # Get SKY device status
    if wfpiconsole.config['Station']['SkyID']:
        if 'SkyMsg' in wfpiconsole.Obs:
            lastOb         = [x if x != None else NaN for x in wfpiconsole.Obs['SkyMsg']['obs'][0]]
            lastSampleTime = datetime.fromtimestamp(lastOb[0],Tz)
            lastSampleDiff = (Now - lastSampleTime).total_seconds()
            if lastOb[8] != None:
                deviceVoltage = float(lastOb[8])
            else:
                deviceVoltage = NaN
            if lastSampleDiff < 300 and deviceVoltage > 2.0:
                deviceStatus = '[color=9aba2fff]OK[/color]'
            else:
                deviceStatus = '[color=d73027ff]Error[/color]'

            # Store outdoor AIR device status variables
            Status['skySampleTime'] = lastSampleTime.strftime('%H:%M:%S')
            Status['skyVoltage']    = '{:.2f}'.format(deviceVoltage)
            Status['skyStatus']     = deviceStatus

    # Get outdoor AIR device status
    if wfpiconsole.config['Station']['OutAirID']:
        if 'outAirMsg' in wfpiconsole.Obs:
            lastOb         = [x if x != None else NaN for x in wfpiconsole.Obs['outAirMsg']['obs'][0]]
            lastSampleTime = datetime.fromtimestamp(lastOb[0],Tz)
            lastSampleDiff = (Now - lastSampleTime).total_seconds()
            if lastOb[6] != None:
                deviceVoltage = float(lastOb[6])
            else:
                deviceVoltage = NaN
            if lastSampleDiff < 300 and deviceVoltage > 1.9:
                deviceStatus = '[color=9aba2fff]OK[/color]'
            else:
                deviceStatus = '[color=d73027ff]Error[/color]'

            # Store outdoor AIR device status variables
            Status['outAirSampleTime'] = lastSampleTime.strftime('%H:%M:%S')
            Status['outAirVoltage']    = '{:.2f}'.format(deviceVoltage)
            Status['outAirStatus']     = deviceStatus

    # Get outdoor AIR device status
    if wfpiconsole.config['Station']['InAirID']:
        if 'inAirMsg' in wfpiconsole.Obs:
            lastOb         = [x if x != None else NaN for x in wfpiconsole.Obs['inAirMsg']['obs'][0]]
            lastSampleTime = datetime.fromtimestamp(lastOb[0],Tz)
            lastSampleDiff = (Now - lastSampleTime).total_seconds()
            if lastOb[6] != None:
                deviceVoltage = float(lastOb[6])
            else:
                deviceVoltage = NaN
            if lastSampleDiff < 300 and deviceVoltage > 1.9:
                deviceStatus = '[color=9aba2fff]OK[/color]'
            else:
                deviceStatus = '[color=d73027ff]Error[/color]'

            # Store outdoor AIR device status variables
            Status['inAirSampleTime'] = lastSampleTime.strftime('%H:%M:%S')
            Status['inAirVoltage']    = '{:.2f}'.format(deviceVoltage)
            Status['inAirStatus']     = deviceStatus

    # Return device status
    return Status

def getObservationCount(Status,wfpiconsole):

    """ Gets number of observations in the last 24 hours for each device
    attached to the station

    INPUTS:
        Status                 Dictionary holding device status information
        wfpiconsole            wfpiconsole object

    OUTPUT:
        Status                 Dictionary holding device status information
    """

    # Define current time in station timezone
    Tz = pytz.timezone(wfpiconsole.config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Get TEMPEST observation count
    if wfpiconsole.config['Station']['TempestID']:
        Device  = wfpiconsole.config['Station']['TempestID']
        while not 'TempestMsg' in wfpiconsole.Obs:
            time.sleep(0.01)
        lastOb  = [x if x != None else NaN for x in wfpiconsole.Obs['TempestMsg']['obs'][0]]
        Data24h = requestAPI.weatherflow.Last24h(Device,lastOb[0],wfpiconsole.config)
        if requestAPI.weatherflow.verifyResponse(Data24h,'obs'):
            Data24h = Data24h.json()['obs']
            Status['tempestObCount'] = str(len(Data24h))

    # Get SKY observation count
    if wfpiconsole.config['Station']['SkyID']:
        Device  = wfpiconsole.config['Station']['SkyID']
        while not 'SkyMsg' in wfpiconsole.Obs:
            time.sleep(0.01)
        lastOb  = [x if x != None else NaN for x in wfpiconsole.Obs['SkyMsg']['obs'][0]]
        Data24h = requestAPI.weatherflow.Last24h(Device,lastOb[0],wfpiconsole.config)
        if requestAPI.weatherflow.verifyResponse(Data24h,'obs'):
            Data24h = Data24h.json()['obs']
            Status['skyObCount'] = str(len(Data24h))

    # Get outdoor AIR observation count
    if wfpiconsole.config['Station']['OutAirID']:
        Device  = wfpiconsole.config['Station']['OutAirID']
        while not 'outAirMsg' in wfpiconsole.Obs:
            time.sleep(0.01)
        lastOb  = [x if x != None else NaN for x in wfpiconsole.Obs['outAirMsg']['obs'][0]]
        Data24h = requestAPI.weatherflow.Last24h(Device,lastOb[0],wfpiconsole.config)
        if requestAPI.weatherflow.verifyResponse(Data24h,'obs'):
            Data24h = Data24h.json()['obs']
            Status['outAirObCount'] = str(len(Data24h))

    # Get indoor AIR observation count
    if wfpiconsole.config['Station']['InAirID']:
        Device  = wfpiconsole.config['Station']['InAirID']
        while not 'inAirMsg' in wfpiconsole.Obs:
            time.sleep(0.01)
        lastOb  = [x if x != None else NaN for x in wfpiconsole.Obs['inAirMsg']['obs'][0]]
        Data24h = requestAPI.weatherflow.Last24h(Device,lastOb[0],wfpiconsole.config)
        if requestAPI.weatherflow.verifyResponse(Data24h,'obs'):
            Data24h = Data24h.json()['obs']
            Status['inAirObCount'] = str(len(Data24h))

    # Return device observation count
    return Status


