# WeatherFlow PiConsole: Raspberry Pi Python console for WeatherFlow Tempest and
# Smart Home Weather stations.
# Copyright (C) 2018-2025 Peter Davis

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
from lib.observation_parser import obs_parser
from lib.system             import system

# Import required Kivy modules
from kivy.logger            import Logger
from kivy.app               import App

# Import required Python modules
import threading
import asyncio
import socket
import json


# ==============================================================================
# DEFINE 'EchoClientProtocol' CLASS
# ==============================================================================
class EchoClientProtocol(asyncio.Protocol):
    def __init__(self, _loop, _udp_connection, udp_client):
        self._udp_connection = _udp_connection
        self._asyncio_loop   = _loop
        self.udp_client      = udp_client
        self.transport       = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.udp_client.message = json.loads(data.decode())
        self._asyncio_loop.create_task(self.udp_client._udp_client__async__decode_message())

    def error_received(self, exception):
        Logger.error(f'UDP: {self.system.log_time()} - Error received: {exception}')

    def connection_lost(self, exc):
        pass


# ==============================================================================
# DEFINE 'udp_client' CLASS
# ==============================================================================
class udp_client():

    @classmethod
    async def create(cls):

        # Initialise udp_client
        self = App.get_running_app().connection_client = udp_client()
        self.app = App.get_running_app()

        # Load configuration file
        self.config = self.app.config

        # Load system class
        self.system = system()

        # Initialise udp_client class variables
        self._asyncio_loop    = asyncio.get_running_loop()
        self._udp_connection  = self._asyncio_loop.create_future()
        self._keep_running    = True
        self.watchdog_timeout = 300
        self.reply_timeout    = 60
        self.ping_timeout     = 60
        self.sleep_time       = 10
        self.thread_list      = {}
        self.task_list        = {}
        self.connected        = False
        self.socket           = None
        self.udp_port         = 50222
        self.udp_ip           = '0.0.0.0'

        # Initialise Observation Parser
        self.app.obsParser = obs_parser()

        # Open UDP socket and return udp_client
        await self.__async__open_socket()
        return self

    async def __async__open_socket(self):
        while not self.connected:
            try:
                Logger.info(f'UDP: {self.system.log_time()} - Opening socket')
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket.bind((self.udp_ip, self.udp_port))
                self.transport, self.protocol = await self._asyncio_loop.create_datagram_endpoint(
                    lambda: EchoClientProtocol(self._asyncio_loop, self._udp_connection, self),
                    sock=self.socket)
                self.connected = True
                Logger.info(f'UDP: {self.system.log_time()} - Socket open')
                await self.__async__get_devices()
                self.app.obsParser.flagAPI = [1, 1, 1, 1]
            except Exception as error:
                Logger.error(f'UDP: {self.system.log_time()} - Connection error: {error}')
                await asyncio.sleep(self.sleep_time)

    async def __async__get_devices(self):
        self.device_list = {'tempest': None, 'sky': None, 'out_air': None, 'in_air': None}
        if self.config['Station']['TempestSN']:
            self.device_list['tempest'] = self.config['Station']['TempestSN']
        else:
            if self.config['Station']['SkySN']:
                self.device_list['sky'] = self.config['Station']['SkySN']
            if self.config['Station']['OutAirSN']:
                self.device_list['out_air'] = self.config['Station']['OutAirSN']
        if self.config['Station']['InAirSN']:
            self.device_list['in_air'] = self.config['Station']['InAirSN']
        if all(device is None for device in self.device_list.values()):
            Logger.warning(f'UDP: {system().log_time()} - Data unavailable; no device IDs specified')

    async def __async__close_socket(self):
        Logger.info(f'UDP: {self.system.log_time()} - Closing socket')
        try:
            self.transport.close()
            Logger.info(f'UDP: {self.system.log_time()} - Socket closed')
            self.connected = False
        except Exception:
            Logger.info(f'Websocket: {self.system.log_time()} - Unable to close socket')

    async def __async__decode_message(self):
        try:
            if self.message:
                if 'type' in self.message:
                    if self.message['type'] in ['hub_status', 'device_status', 'evt_precip']:
                        pass
                    else:
                        if 'serial_number' in self.message:
                            if self.message['type'] == 'obs_st':
                                if self.message['serial_number'] == self.config['Station']['TempestSN']:
                                    if 'obs_st' in self.thread_list:
                                        while self.thread_list['obs_st'].is_alive():
                                            await asyncio.sleep(0.1)
                                    self.thread_list['obs_st'] = threading.Thread(target=self.app.obsParser.parse_obs_st,
                                                                                  args=(self.message, self.config, ),
                                                                                  name="obs_st")
                                    self.thread_list['obs_st'].start()
                            elif self.message['type'] == 'obs_sky':
                                if self.message['serial_number'] == self.config['Station']['SkySN']:
                                    if 'obs_sky' in self.thread_list:
                                        while self.thread_list['obs_sky'].is_alive():
                                            await asyncio.sleep(0.1)
                                    self.thread_list['obs_sky'] = threading.Thread(target=self.app.obsParser.parse_obs_sky,
                                                                                   args=(self.message, self.config, ),
                                                                                   name='obs_sky')
                                    self.thread_list['obs_sky'].start()
                            elif self.message['type'] == 'obs_air':
                                if self.message['serial_number'] == self.config['Station']['OutAirSN']:
                                    if 'obs_out_air' in self.thread_list:
                                        while self.thread_list['obs_out_air'].is_alive():
                                            await asyncio.sleep(0.1)
                                    self.thread_list['obs_out_air'] = threading.Thread(target=self.app.obsParser.parse_obs_out_air,
                                                                                       args=(self.message, self.config, ),
                                                                                       name='obs_out_air')
                                    self.thread_list['obs_out_air'].start()
                                elif self.message['serial_number'] == self.config['Station']['InAirSN']:
                                    if 'obs_in_air' in self.thread_list:
                                        while self.thread_list['obs_in_air'].is_alive():
                                            await asyncio.sleep(0.1)
                                    self.thread_list['obs_in_air'] = threading.Thread(target=self.app.obsParser.parse_obs_in_air,
                                                                                      args=(self.message, self.config, ),
                                                                                      name='obs_in_air')
                                    self.thread_list['obs_in_air'].start()
                            elif self.message['type'] == 'rapid_wind':
                                if self.message['serial_number'] in [self.config['Station']['TempestSN'], self.config['Station']['SkySN']]:
                                    self.app.obsParser.parse_rapid_wind(self.message, self.config)
                            elif self.message['type'] == 'evt_strike':
                                if self.message['serial_number'] in [self.config['Station']['TempestSN'], self.config['Station']['OutAirSN']]:
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
            await self._udp_connection
        except asyncio.CancelledError:
            raise

    async def __async__cancel(self):
        while self._keep_running:
            await asyncio.sleep(0.1)
        self.task_list['listen'].cancel()

    def activeThreads(self):
        for thread in self.thread_list:
            if self.thread_list[thread].is_alive():
                return True
        return False


async def main():
    try:
        udp = await udp_client.create()
        udp.task_list['listen'] = asyncio.create_task(udp._udp_client__async__listen())
        udp.task_list['cancel'] = asyncio.create_task(udp._udp_client__async__cancel())
        await asyncio.gather(*list(udp.task_list.values()))
    except asyncio.CancelledError:
        if not udp._keep_running:
            await udp._udp_client__async__close_socket()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
