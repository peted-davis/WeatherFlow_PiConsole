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
from kivy.logger                import Logger
from lib                        import system
from lib                        import config
import configparser
import websockets
import threading
import asyncio
import socket
import json
import time
import ssl
import sys
import os

# =============================================================================
# INITIALISE REQUIRED VARIABLES
# =============================================================================
# Initialise OSC client (send messages)
oscCLIENT = OSCClient('localhost', 3002)

# Initialise OSC server (recieve messages)
oscSERVER = OSCThreadServer()
oscSERVER.listen(address=b'localhost', port=3001, default=True)

# Set config file path
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
        self.reply_timeout  = 0.1
        self.reply_watchdog = time.time() + 60
        self.ping_timeout   = 120
        self.sleep_time     = 5
        self._keep_running  = True
        self._switch_device = False
        self.thread_list    = {}
        self.connection     = None
        self.url            = 'wss://ws.weatherflow.com/swd/data?token=' + self.config['Keys']['WeatherFlow']

        # Listen for configuration file changes or commands to modify websocket
        # connection
        oscSERVER.bind(b'/websocket', self.modifyConnection)

        # Initialise Observation Parser
        self.obsParser = obsParser(oscCLIENT, oscSERVER, [1, 1, 1, 1])

        # Initialise asyn loop and connect to specified Websocket URL
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_until_complete(self.__async__connect())


    async def __async__connect(self):
        Connected = False
        while not Connected:
            try:
                Logger.info(f'Websocket: {system.logTime()} - Opening connection')
                self.websocket = await websockets.connect(self.url, ssl=ssl.SSLContext())
                message        = await self.__async__getMessage()
                try:
                    if 'type' in message and message['type'] == 'connection_opened':
                        Logger.info(f'Websocket: {system.logTime()} - Connection open')
                        self.obsParser.flagAPI = [1, 1, 1, 1]
                        self.reply_watchdog = time.time() + 60
                        await self.__async__manageDevices('listen_start')
                        Connected = True
                    else:
                        Logger.error(f'Websocket: {system.logTime()} - Connection message error')
                        await self.websocket.close()
                        await asyncio.sleep(self.sleep_time)
                except Exception as error:
                    Logger.error(f'Websocket: {system.logTime()} - Connection error: {error}')
                    await self.websocket.close()
                    await asyncio.sleep(self.sleep_time)
            except (socket.gaierror, ConnectionRefusedError, websockets.exceptions.InvalidStatusCode) as error:
                Logger.error(f'Websocket: {system.logTime()} - Connection error: {error}')
                await asyncio.sleep(self.sleep_time)
            except Exception as error:
                Logger.error(f'Websocket: {system.logTime()} - General error: {error}')
                await asyncio.sleep(self.sleep_time)


    async def __async__disconnect(self):
        Logger.info(f'Websocket: {system.logTime()} - Closing connection')
        try:
            await asyncio.wait_for(self.websocket.close(), timeout=5)
            Logger.info(f'Websocket: {system.logTime()} - Connection closed')
        except Exception:
            Logger.info(f'Websocket: {system.logTime()} - Unable to close connection cleanly')


    async def __async__manageDevices(self, action):
        deviceList = list()
        if self.config['Station']['TempestID'] or self.config['Station']['SkyID']:
            device = self.config['Station']['TempestID'] or self.config['Station']['SkyID']
            deviceList.append('{"type":"' + action + '",'
                              + ' "device_id":' + device + ','
                              + ' "id":"Sky/Tempest"}')
            deviceList.append('{"type":"' + action.split('_')[0] + '_rapid_' + action.split('_')[1] + '",'
                              + ' "device_id":' + device + ','
                              + ' "id":"rapidWind"}')
        if self.config['Station']['OutAirID']:
            deviceList.append('{"type":"' + action + '",'
                              + ' "device_id":' + self.config['Station']['OutAirID'] + ','
                              + ' "id":"OutdoorAir"}')
        if self.config['Station']['InAirID']:
            deviceList.append('{"type":"' + action + '",'
                              + ' "device_id":' + self.config['Station']['InAirID'] + ','
                              + ' "id":"IndoorAir"}')
        for device in deviceList:
            print(device)
            await self.websocket.send(device)


    async def __async__getMessage(self):
        try:
            message = await asyncio.wait_for(self.websocket.recv(), timeout=self.reply_timeout)
            self.reply_watchdog = time.time() + 60
            try:
                return json.loads(message)
            except Exception:
                Logger.error(f'Websocket: {system.logTime()} - Parsing error: {message}')
                return None
        except Exception:
            if time.time() >= self.reply_watchdog:
                try:
                    pong = await self.websocket.ping()
                    await asyncio.wait_for(pong, timeout=self.ping_timeout)
                    Logger.info(f'Websocket: {system.logTime()} - Ping OK, keeping connection alive')
                    self.reply_watchdog = time.time() + 60
                except Exception:
                    Logger.error(f'Websocket: {system.logTime()} - Ping error, closing connection')
                    await self.websocket.close()
                    await asyncio.sleep(self.sleep_time)
                    await self.__async__connect()
            else:
                return None


    async def __async__decodeMessage(self, message):
        if message is not None:
            if 'type' in message:
                if message['type'] in ['ack', 'evt_precip']:
                    pass
                else:
                    if 'device_id' in message:
                        if message['type'] == 'obs_st':
                            self.thread_list['obs_st'] = threading.Thread(target=self.obsParser.parse_obs_st, args=(message, self.config, ), name="obs_st")
                            self.thread_list['obs_st'].start()
                        elif message['type'] == 'obs_sky':
                            self.thread_list['obs_sky'] = threading.Thread(target=self.obsParser.parse_obs_sky,     args=(message, self.config, ), name='obs_sky')
                            self.thread_list['obs_sky'].start()
                        elif message['type'] == 'obs_air':
                            if str(message['device_id']) == self.config['Station']['OutAirID']:
                                self.thread_list['obs_out_air'] = threading.Thread(target=self.obsParser.parse_obs_out_air, args=(message, self.config, ), name='obs_out_air')
                                self.thread_list['obs_out_air'].start()
                            elif str(message['device_id']) == self.config['Station']['InAirID']:
                                self.thread_list['obs_in_air'] = threading.Thread(target=self.obsParser.parse_obs_in_air,  args=(message, self.config, ), name='obs_in_air')
                                self.thread_list['obs_in_air'].start()
                        elif message['type'] == 'rapid_wind':
                            self.obsParser.parse_rapid_wind(message, self.config)
                        elif message['type'] == 'evt_strike':
                            self.obsParser.parse_evt_strike(message, self.config)
                        else:
                            Logger.error(f'Websocket: {system.logTime()} - Unknown message type: {json.dumps(message)}')
                    else:
                        Logger.info(f'Websocket: {system.logTime()} - Missing device ID: {json.dumps(message)}')
            else:
                Logger.info(f'Websocket: {system.logTime()} - Missing message type: {json.dumps(message)}')


    def modifyConnection(self, *payload):
        if payload[0].decode('utf8') == 'reload_config':
            self.config = configparser.ConfigParser(allow_no_value=True)
            self.config.optionxform = str
            self.config.read(configFile)
            self.updateDerivedVariables()
        elif payload[0].decode('utf8') == 'switch_device':
            self.stationMetaData = json.loads(payload[1].decode('utf8'))
            self.deviceList      = json.loads(payload[2].decode('utf8'))
            self._switch_device  = True


    def updateDerivedVariables(self):
        while True:
            active_threads = []
            for thread in self.thread_list:
                if self.thread_list[thread].is_alive():
                    active_threads.append(True)
            if not active_threads:
                break
        self.obsParser.formatDerivedVariables(self.config, 'obs_all')


if __name__ == '__main__':
    websocket = websocketClient()
    while websocket._keep_running:
        message = websocket.async_loop.run_until_complete(websocket._websocketClient__async__getMessage())
        websocket.async_loop.run_until_complete(websocket._websocketClient__async__decodeMessage(message))
        #message = websocket.getMessage()
        #websocket.decodeMessage(message)
