# WeatherFlow PiConsole: Raspberry Pi Python console for WeatherFlow Tempest and
# Smart Home Weather stations.
# Copyright (C) 2018-2023 Peter Davis

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
# import websockets
import threading
import asyncio
import socket
import json
import time
# import ssl


# ==============================================================================
# DEFINE 'udp_client' CLASS
# ==============================================================================
class udp_client():

    @classmethod
    async def create(cls):

        # Initialise udp_client
        self = App.get_running_app().udp_client = udp_client()
        self.app = App.get_running_app()

        # Load configuration file
        self.config = self.app.config

        # Load system class
        self.system = system()

        # Initialise udp_client class variables
        self._keep_running    = True
        self._switch_device   = False
        self.watchdog_timeout = 300
        self.reply_timeout    = 60
        self.ping_timeout     = 60
        self.sleep_time       = 10
        self.thread_list      = {}
        self.task_list        = {}
        self.watchdog_list    = {}
        self.connected        = False
        self.socket           = None
        self.station          = int(self.config['Station']['StationID'])
        self.udp_address      = '<broadcast>'
        self.udp_port         = 50222

        # Initialise Observation Parser
        self.app.obsParser = obsParser()

        # Open UDP socket and return udp_client
        await self.__async__open_socket()
        return self

    async def __async__open_socket(self):
        while not self.connected:
            #try:
            Logger.info(f'UDP: {self.system.log_time()} - Opening socket')
            self.socket     = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.socket.bind(('', self.udp_port))
            self.connected = True
            Logger.info(f'UDP: {self.system.log_time()} - Socket open')
            #     try:
            #         if 'type' in self.message and self.message['type'] == 'connection_opened':
            #             await self.__async__get_devices()
            #             await self.__async__listen_devices('listen_start')
            #             self.app.obsParser.flagAPI = [1, 1, 1, 1]
            #             self.connected = True
            #             Logger.info(f'Websocket: {self.system.log_time()} - Connection open')
            #         else:
            #             Logger.error(f'Websocket: {self.system.log_time()} - Connection message error')
            #             await self.connection.close()
            #             await asyncio.sleep(self.sleep_time)
            #     except Exception as error:
            #         Logger.error(f'Websocket: {self.system.log_time()} - Connection error: {error}')
            #         await self.connection.close()
            #         await asyncio.sleep(self.sleep_time)
            # except (socket.gaierror, ConnectionRefusedError, websockets.exceptions.InvalidStatusCode) as error:
            #     Logger.error(f'Websocket: {self.system.log_time()} - Connection error: {error}')
            #     await asyncio.sleep(self.sleep_time)
            # except Exception as error:
            #     Logger.error(f'Websocket: {self.system.log_time()} - General error: {error}')
            #     await asyncio.sleep(self.sleep_time)

    # async def __async__disconnect(self):
    #     Logger.info(f'Websocket: {self.system.log_time()} - Closing connection')
    #     try:
    #         await asyncio.wait_for(self.connection.close(), timeout=5)
    #         self.connected = False
    #         Logger.info(f'Websocket: {self.system.log_time()} - Connection closed')
    #     except Exception:
    #         Logger.info(f'Websocket: {self.system.log_time()} - Unable to close connection')

    # async def __async__verify(self):
    #     try:
    #         pong = await self.connection.ping()
    #         await asyncio.wait_for(pong, timeout=self.ping_timeout)
    #     except Exception:
    #         Logger.warning(f'Websocket: {self.system.log_time()} - Ping failed')
    #         await self.__async__disconnect()
    #         await asyncio.sleep(self.sleep_time)
    #         await self.__async__open_socket()

    # async def __async__get_devices(self):
    #     self.device_list = {'tempest': None, 'sky': None, 'out_air': None, 'in_air': None}
    #     if self.config['Station']['TempestID']:
    #         self.device_list['tempest'] = self.config['Station']['TempestID']
    #         self.watchdog_list['obs_st'], self.watchdog_list['rapid_wind']  = time.time(), time.time()
    #     else:
    #         if self.config['Station']['SkyID']:
    #             self.device_list['sky'] = self.config['Station']['SkyID']
    #             self.watchdog_list['obs_sky'], self.watchdog_list['rapid_wind']  = time.time(), time.time()
    #         if self.config['Station']['OutAirID']:
    #             self.device_list['out_air'] = self.config['Station']['OutAirID']
    #             self.watchdog_list['obs_out_air']  = time.time()
    #     if self.config['Station']['InAirID']:
    #         self.device_list['in_air'] = self.config['Station']['InAirID']
    #         self.watchdog_list['obs_in_air']  = time.time()

    # async def __async__listen_devices(self, action):
    #     devices = []
    #     if self.device_list['tempest'] or self.device_list['sky']:
    #         devices.append('{"type":"' + action + '",'
    #                        + ' "device_id":' + (self.device_list['tempest'] or self.device_list['sky']) + ','
    #                        + ' "id":"tempest_sky"}')
    #         devices.append('{"type":"' + action.split('_')[0] + '_rapid_' + action.split('_')[1] + '",'
    #                        + ' "device_id":' + (self.device_list['tempest'] or self.device_list['sky']) + ','
    #                        + ' "id":"rapid_wind"}')
    #     if self.device_list['out_air']:
    #         devices.append('{"type":"' + action + '",'
    #                        + ' "device_id":' + self.device_list['out_air'] + ','
    #                        + ' "id":"outdoor_air"}')
    #     if self.device_list['in_air']:
    #         devices.append('{"type":"' + action + '",'
    #                        + ' "device_id":' + self.device_list['in_air'] + ','
    #                        + ' "id":"indoor_air"}')
    #     for device in devices:
    #         await self.connection.send(device)

    async def __async_socket_recieve(self):
        message = self.socket.recv(1024)
        return message

    async def __async__get_message(self):
        try:
            message = await asyncio.wait_for(self.__async_socket_recieve(), timeout=self.reply_timeout)
            try:
                return json.loads(message)
            except Exception:
                Logger.error(f'Websocket: {self.system.log_time()} - Parsing error: {message}')
                return {}
        except asyncio.CancelledError:
            raise
        except Exception:
            return {}

    # async def __async__watchdog(self):
    #     now = time.time()
    #     watchdog_triggered = False
    #     for ob in self.watchdog_list:
    #         if self.watchdog_list[ob] < (now - self.watchdog_timeout):
    #             watchdog_triggered = True
    #             break
    #     if watchdog_triggered:
    #         Logger.warning(f'Websocket: {self.system.log_time()} - Watchdog triggered {ob}')
    #         await self.__async__disconnect()
    #         await self.__async__open_socket()

    async def __async__decode_message(self):
        try:
            if self.message:
                if 'type' in self.message:
                    if self.message['type'] in ['hub_status', 'device_status', 'evt_precip']:
                        pass
                    else:
                        if 'serial_number' in self.message:
                            print(self.message)
                            if self.message['type'] == 'obs_st':
                                if 'obs_st' in self.thread_list:
                                    while self.thread_list['obs_st'].is_alive():
                                        await asyncio.sleep(0.1)
                                self.watchdog_list['obs_st'] = time.time()
                                # self.thread_list['obs_st'] = threading.Thread(target=self.app.obsParser.parse_obs_st,
                                #                                               args=(self.message, self.config, ),
                                #                                               name="obs_st")
                                # self.thread_list['obs_st'].start()
                            elif self.message['type'] == 'obs_sky':
                                if 'obs_sky' in self.thread_list:
                                    while self.thread_list['obs_sky'].is_alive():
                                        await asyncio.sleep(0.1)
                                self.watchdog_list['obs_sky'] = time.time()
                                # self.thread_list['obs_sky'] = threading.Thread(target=self.app.obsParser.parse_obs_sky,
                                #                                                args=(self.message, self.config, ),
                                #                                                name='obs_sky')
                                # self.thread_list['obs_sky'].start()
                            elif self.message['type'] == 'obs_air':
                                if str(self.message['serial_number']) == self.config['Station']['OutAirID']:
                                    if 'obs_out_air' in self.thread_list:
                                        while self.thread_list['obs_out_air'].is_alive():
                                            await asyncio.sleep(0.1)
                                    self.watchdog_list['obs_out_air'] = time.time()
                                    # self.thread_list['obs_out_air'] = threading.Thread(target=self.app.obsParser.parse_obs_out_air,
                                    #                                                    args=(self.message, self.config, ),
                                    #                                                    name='obs_out_air')
                                    # self.thread_list['obs_out_air'].start()
                                elif str(self.message['serial_number']) == self.config['Station']['InAirID']:
                                    if 'obs_in_air' in self.thread_list:
                                        while self.thread_list['obs_in_air'].is_alive():
                                            await asyncio.sleep(0.1)
                                    # self.watchdog_list['obs_in_air'] = time.time()
                                    # self.thread_list['obs_in_air'] = threading.Thread(target=self.app.obsParser.parse_obs_in_air,
                                    #                                                   args=(self.message, self.config, ),
                                    #                                                   name='obs_in_air')
                                    # self.thread_list['obs_in_air'].start()
                            elif self.message['type'] == 'rapid_wind':
                                self.watchdog_list['rapid_wind'] = time.time()
                                # self.app.obsParser.parse_rapid_wind(self.message, self.config)
                            elif self.message['type'] == 'evt_strike':
                                pass
                                # self.app.obsParser.parse_evt_strike(self.message, self.config)
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
                self.message = await self.__async__get_message()
                # await self.__async__watchdog()
                await self.__async__decode_message()
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
    udp = await udp_client.create()
    while udp._keep_running:
        try:
            udp.task_list['listen'] = asyncio.create_task(udp._udp_client__async__listen())
            udp.task_list['switch'] = asyncio.create_task(udp._udp_client__async__switch())
            await asyncio.gather(*list(udp.task_list.values()))
        except asyncio.CancelledError:
            if udp._switch_device:
                await udp._websocketClient__async__listen_devices('listen_stop')
                await udp._websocketClient__async__get_devices()
                await udp._websocketClient__async__listen_devices('listen_start')
                Logger.info(f'Websocket: {system().log_time()} - Switching devices and/or station')
                udp._switch_device = False


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
