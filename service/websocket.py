# WeatherFlow PiConsole: Raspberry Pi Python console for WeatherFlow Tempest and
# Smart Home Weather stations.
# Copyright (C) 2018-2022 Peter Davis

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

# Import required library modules
from lib.observationParser  import obsParser
from lib.system             import system

# Import required Kivy modules
from kivy.logger            import Logger
from kivy.app               import App

# Import required Python modules
import websockets
import threading
import asyncio
import socket
import json
import ssl


# ==============================================================================
# DEFINE 'websocketClient' CLASS
# ==============================================================================
class websocketClient():

    @classmethod
    async def create(cls):

        # Initialise websocketClient
        self = App.get_running_app().websocket_client = websocketClient()
        self.app = App.get_running_app()

        # Load configuration file
        self.config = self.app.config

        # Load system class
        self.system = system()

        # Initialise websocketClient class variables
        self._keep_running  = True
        self._switch_device = False
        self.reply_timeout  = 60
        self.ping_timeout   = 60
        self.sleep_time     = 10
        self.thread_list    = {}
        self.task_list      = {}
        self.connected      = False
        self.connection     = None
        self.station        = int(self.config['Station']['StationID'])
        self.url            = 'wss://ws.weatherflow.com/swd/data?token=' + self.config['Keys']['WeatherFlow']

        # Initialise Observation Parser
        self.app.obsParser = obsParser()

        # Connect to specified Websocket URL and return websocketClient
        await self.__async__connect()
        return self

    async def __async__connect(self):
        while not self.connected:
            try:
                Logger.info(f'Websocket: {self.system.log_time()} - Opening connection')
                self.connection = await websockets.connect(self.url, ssl=ssl.SSLContext())
                self.message    = await asyncio.wait_for(self.connection.recv(), timeout=self.reply_timeout)
                self.message    = json.loads(self.message)
                try:
                    if 'type' in self.message and self.message['type'] == 'connection_opened':
                        await self.__async__get_devices()
                        await self.__async__listen_devices('listen_start')
                        self.app.obsParser.flagAPI = [1, 1, 1, 1]
                        self.connected = True
                        Logger.info(f'Websocket: {self.system.log_time()} - Connection open')
                    else:
                        Logger.error(f'Websocket: {self.system.log_time()} - Connection message error')
                        await self.connection.close()
                        await asyncio.sleep(self.sleep_time)
                except Exception as error:
                    Logger.error(f'Websocket: {self.system.log_time()} - Connection error: {error}')
                    await self.connection.close()
                    await asyncio.sleep(self.sleep_time)
            except (socket.gaierror, ConnectionRefusedError, websockets.exceptions.InvalidStatusCode) as error:
                Logger.error(f'Websocket: {self.system.log_time()} - Connection error: {error}')
                await asyncio.sleep(self.sleep_time)
            except Exception as error:
                Logger.error(f'Websocket: {self.system.log_time()} - General error: {error}')
                await asyncio.sleep(self.sleep_time)

    async def __async__disconnect(self):
        Logger.info(f'Websocket: {self.system.log_time()} - Closing connection')
        try:
            await asyncio.wait_for(self.connection.close(), timeout=5)
            self.connected = False
            Logger.info(f'Websocket: {self.system.log_time()} - Connection closed')
        except Exception:
            Logger.info(f'Websocket: {self.system.log_time()} - Unable to close connection')

    async def __async__verify(self):
        try:
            pong = await self.connection.ping()
            await asyncio.wait_for(pong, timeout=self.ping_timeout)
        except Exception:
            Logger.warning(f'Websocket: {self.system.log_time()} - Ping failed')
            await self.__async__disconnect()
            await asyncio.sleep(self.sleep_time)
            await self.__async__connect()

    async def __async__get_devices(self):
        self.device_list = {'tempest': None, 'sky': None, 'out_air': None, 'in_air': None}
        if self.config['Station']['TempestID']:
            self.device_list['tempest'] = self.config['Station']['TempestID']
        else:
            if self.config['Station']['SkyID']:
                self.device_list['sky'] = self.config['Station']['SkyID']
            if self.config['Station']['OutAirID']:
                self.device_list['out_air'] = self.config['Station']['OutAirID']
        if self.config['Station']['InAirID']:
            self.device_list['in_air'] = self.config['Station']['InAirID']

    async def __async__listen_devices(self, action):
        devices = []
        if self.device_list['tempest'] or self.device_list['sky']:
            devices.append('{"type":"' + action + '",'
                           + ' "device_id":' + (self.device_list['tempest'] or self.device_list['sky']) + ','
                           + ' "id":"tempest_sky"}')
            devices.append('{"type":"' + action.split('_')[0] + '_rapid_' + action.split('_')[1] + '",'
                           + ' "device_id":' + (self.device_list['tempest'] or self.device_list['sky']) + ','
                           + ' "id":"rapid_wind"}')
        if self.device_list['out_air']:
            devices.append('{"type":"' + action + '",'
                           + ' "device_id":' + self.device_list['out_air'] + ','
                           + ' "id":"outdoor_air"}')
        if self.device_list['in_air']:
            devices.append('{"type":"' + action + '",'
                           + ' "device_id":' + self.device_list['in_air'] + ','
                           + ' "id":"indoor_air"}')
        for device in devices:
            await self.connection.send(device)

    async def __async__getMessage(self):
        try:
            message = await asyncio.wait_for(self.connection.recv(), timeout=self.reply_timeout)
            try:
                return json.loads(message)
            except Exception:
                Logger.error(f'Websocket: {self.system.log_time()} - Parsing error: {message}')
                return {}
        except asyncio.CancelledError:
            raise
        except Exception:
            self.task_list['verify'] = asyncio.create_task(self.__async__verify())
            await self.task_list['verify']
            return {}

    async def __async__decodeMessage(self):
        try:
            if self.message:
                if 'type' in self.message:
                    if self.message['type'] in ['ack', 'evt_precip']:
                        pass
                    else:
                        if 'device_id' in self.message:
                            if self.message['type'] == 'obs_st':
                                if 'obs_st' in self.thread_list:
                                    while self.thread_list['obs_st'].is_alive():
                                        await asyncio.sleep(0.1)
                                self.thread_list['obs_st'] = threading.Thread(target=self.app.obsParser.parse_obs_st,
                                                                              args=(self.message, self.config, ),
                                                                              name="obs_st")
                                self.thread_list['obs_st'].start()
                            elif self.message['type'] == 'obs_sky':
                                if 'obs_sky' in self.thread_list:
                                    while self.thread_list['obs_sky'].is_alive():
                                        await asyncio.sleep(0.1)
                                self.thread_list['obs_sky'] = threading.Thread(target=self.app.obsParser.parse_obs_sky,
                                                                               args=(self.message, self.config, ),
                                                                               name='obs_sky')
                                self.thread_list['obs_sky'].start()
                            elif self.message['type'] == 'obs_air':
                                if str(self.message['device_id']) == self.config['Station']['OutAirID']:
                                    if 'obs_out_air' in self.thread_list:
                                        while self.thread_list['obs_out_air'].is_alive():
                                            await asyncio.sleep(0.1)
                                    self.thread_list['obs_out_air'] = threading.Thread(target=self.app.obsParser.parse_obs_out_air,
                                                                                       args=(self.message, self.config, ),
                                                                                       name='obs_out_air')
                                    self.thread_list['obs_out_air'].start()
                                elif str(self.message['device_id']) == self.config['Station']['InAirID']:
                                    if 'obs_in_air' in self.thread_list:
                                        while self.thread_list['obs_in_air'].is_alive():
                                            await asyncio.sleep(0.1)
                                    self.thread_list['obs_in_air'] = threading.Thread(target=self.app.obsParser.parse_obs_in_air,
                                                                                      args=(self.message, self.config, ),
                                                                                      name='obs_in_air')
                                    self.thread_list['obs_in_air'].start()
                            elif self.message['type'] == 'rapid_wind':
                                self.app.obsParser.parse_rapid_wind(self.message, self.config)
                            elif self.message['type'] == 'evt_strike':
                                self.app.obsParser.parse_evt_strike(self.message, self.config)
                            else:
                                Logger.warning(f'Websocket: {self.system.log_time()} - Unknown message type: {json.dumps(self.message)}')
                        else:
                            Logger.warning(f'Websocket: {self.system.log_time()} - Missing device ID: {json.dumps(self.message)}')
                else:
                    Logger.warning(f'Websocket: {self.system.log_time()} - Missing message type: {json.dumps(self.message)}')
        except asyncio.CancelledError:
            raise

    async def __async__listen(self):
        try:
            while self._keep_running:
                self.message = await self.__async__getMessage()
                await self.__async__decodeMessage()
        except asyncio.CancelledError:
            raise

    async def __async__switch(self):
        while not self._switch_device:
            await asyncio.sleep(0.1)
        if 'verify' in self.task_list:
            while not self.task_list['verify'].done():
                await asyncio.sleep(0.1)
        self.task_list['listen'].cancel()

    def activeThreads(self):
        for thread in self.thread_list:
            if self.thread_list[thread].is_alive():
                return True
        return False


async def main():
    websocket = await websocketClient.create()
    while websocket._keep_running:
        try:
            websocket.task_list['listen'] = asyncio.create_task(websocket._websocketClient__async__listen())
            websocket.task_list['switch'] = asyncio.create_task(websocket._websocketClient__async__switch())
            await asyncio.gather(*list(websocket.task_list.values()))
        except asyncio.CancelledError:
            if websocket._switch_device:
                await websocket._websocketClient__async__listen_devices('listen_stop')
                await websocket._websocketClient__async__get_devices()
                await websocket._websocketClient__async__listen_devices('listen_start')
                Logger.info(f'Websocket: {system().log_time()} - Switching devices and/or station')
                websocket._switch_device = False


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
