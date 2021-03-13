# WeatherFlow PiConsole: Raspberry Pi Python console for WeatherFlow Tempest and
# Smart Home Weather stations.
# Copyright (C) 2018-2020 Peter Davis

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

# =============================================================================
# IMPORT REQUIRED MODULES
# =============================================================================
from lib.observationParser      import obsParser
from oscpy.server               import OSCThreadServer
from oscpy.client               import OSCClient
import configparser
import websockets
import threading
import asyncio
import socket
import json
import ssl
import os

# =============================================================================
# IMPORT REQUIRED ANDROID MODULES
# =============================================================================
if 'ANDROID_ARGUMENT' in os.environ:
    from android.storage import app_storage_path

# =============================================================================
# INITIALISE REQUIRED VARIABLES
# =============================================================================
# Initialise OSC client (send messages)
oscCLIENT = OSCClient('localhost', 3002)

# Initialise OSC server (recieve messages)
oscSERVER = OSCThreadServer()
oscSERVER.listen(address=b'localhost', port=3001, default=True)

# Set config file path
if 'ANDROID_ARGUMENT' in os.environ:
    configFile = app_storage_path() + '/.wfpiconsole.ini'
else:
    configFile = 'wfpiconsole.ini'


# =============================================================================
# DEFINE 'websocketClient' CLASS
# =============================================================================
class websocketClient():

    def __init__(self):

        # Load configuration file
        self.config = configparser.ConfigParser(allow_no_value=True)
        self.config.optionxform = str
        self.config.read(configFile)

        # Initial websocketClient class variables
        self.thread_list   = {}
        self.reply_timeout = 60
        self.ping_timeout  = 120
        self.sleep_time    = 5
        self.websocket     = None
        self.url           = 'wss://ws.weatherflow.com/swd/data?token=' + self.config['Keys']['WeatherFlow']

        # Listen for configuration file changes
        oscSERVER.bind(b'/config', self.reloadConfig)

        # Initialise Observation Parser
        self.obsParser = obsParser(oscCLIENT, oscSERVER, [1, 1, 1])

        # Initialise asyn loop and connect to specified Websocket URL
        self.async_loop    = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_until_complete(self.__async__connect())

    async def __async__connect(self):
        Connected = False
        while not Connected:
            try:
                self.websocket = await websockets.connect(self.url, ssl=ssl.SSLContext())
                message        = await self.__async__getMessage()
                try:
                    if 'type' in message and message['type'] == 'connection_opened':
                        print('Connection open')
                        self.obsParser.flagAPI = [1, 1, 1, 1]
                        await self.__async__requestDevices()
                        Connected = True
                    else:
                        print('Websocket: Message error: {}'.format(message))
                        await self.websocket.close()
                        await asyncio.sleep(self.sleep_time)
                except Exception as error:
                    print('Connection error: {}'.format(error))
                    await self.websocket.close()
                    await asyncio.sleep(self.sleep_time)
            except (socket.gaierror, ConnectionRefusedError, websockets.exceptions.InvalidStatusCode) as error:
                print('Connection error: {}'.format(error))
                await asyncio.sleep(self.sleep_time)
            except Exception:
                print('General error')
                await asyncio.sleep(self.sleep_time)

    async def __async__requestDevices(self):
        deviceList = list()
        if self.config['Station']['TempestID']:
            deviceList.append('{"type":"listen_start",'
                              + ' "device_id":' + self.config['Station']['TempestID'] + ','
                              + ' "id":"Sky"}')
            deviceList.append('{"type":"listen_rapid_start",' + ' "device_id":'
                              + self.config['Station']['TempestID'] + ','
                              + ' "id":"rapidWind"}')
        elif self.config['Station']['SkyID']:
            deviceList.append('{"type":"listen_start",'
                              + ' "device_id":'
                              + self.config['Station']['SkyID'] + ',' + ' "id":"Sky"}')
            deviceList.append('{"type":"listen_rapid_start",'
                              + ' "device_id":' + self.config['Station']['SkyID'] + ','
                              + ' "id":"rapidWind"}')
        if self.config['Station']['OutAirID']:
            deviceList.append('{"type":"listen_start",'
                              + ' "device_id":' + self.config['Station']['OutAirID'] + ','
                              + ' "id":"OutdoorAir"}')
        for device in deviceList:
            await self.websocket.send(device)

    async def __async__getMessage(self):
        while True:
            try:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=self.reply_timeout)
                try:
                    return json.loads(message)
                except Exception:
                    print('Parsing error %s', message)
                    return {}
            except Exception:
                try:
                    pong = await self.websocket.ping()
                    await asyncio.wait_for(pong, timeout=self.ping_timeout)
                    print('Ping OK, keeping connection alive')
                except Exception:
                    print('Ping error, closing connection')
                    await self.websocket.close()
                    await asyncio.sleep(self.sleep_time)
                    await self.__async__connect()

    def getMessage(self):
        return self.async_loop.run_until_complete(self.__async__getMessage())

    def decodeMessage(self, message):
        if 'type' in message:
            if message['type'] == 'obs_st':
                if not hasattr(self.thread_list, 'obs_st'):
                    self.thread_list['obs_st'] = threading.Thread(target=self.obsParser.parse_obs_st, args=(message, self.config, ), name="obs_st")
                self.thread_list['obs_st'].start()
            elif message['type'] == 'obs_sky':
                if not hasattr(self.thread_list, 'obs_sky'):
                    self.thread_list['obs_sky'] = threading.Thread(target=self.obsParser.parse_obs_sky, args=(message, self.config, ), name='obs_sky')
                self.thread_list['obs_sky'].start()
            elif message['type'] == 'obs_air':
                if not hasattr(self.thread_list, 'obs_air'):
                    self.thread_list['obs_air'] = threading.Thread(target=self.obsParser.parse_obs_air, args=(message, self.config, ), name='obs_air')
                self.thread_list['obs_air'].start()
            elif message['type'] == 'rapid_wind':
                self.obsParser.parse_rapid_wind(message, self.config)
            elif message['type'] == 'evt_strike':
                self.obsParser.parse_evt_strike(message, self.config)
            elif message['type'] in ['ack', 'evt_precip']:
                pass
            else:
                print('Unknown message type: %s' % json.dumps(message))
        else:
            print('Unknown message type: %s' % json.dumps(message))

    def reloadConfig(self, payload):
        if json.loads(payload.decode('utf8')) == 1:
            self.config = configparser.ConfigParser(allow_no_value=True)
            self.config.optionxform = str
            self.config.read(configFile)
            self.updateDerivedVariables()

    def updateDerivedVariables(self):
        while True:
            active_threads = []
            for thread in self.thread_list:
                if self.thread_list[thread].is_alive():
                    active_threads.append(True)
            if not active_threads:
                break
        self.obsParser.calcDerivedVariables(self.config, 'obs_all')


if __name__ == '__main__':
    websocket = websocketClient()
    while True:
        message = websocket.getMessage()
        websocket.decodeMessage(message)
