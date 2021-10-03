""" Defines the mainMenu Panel required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2021 Peter Davis

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

# Load required Kivy modules
from kivy.network.urlrequest import UrlRequest
from kivy.uix.modalview      import ModalView
from kivy.uix.boxlayout      import BoxLayout
from kivy.properties         import ListProperty, DictProperty, StringProperty
from kivy.properties         import ObjectProperty
from kivy.app                import App

# Load required system modules
import certifi

# ==============================================================================
# mainMenu CLASS
# ==============================================================================
class mainMenu(ModalView):

   stationMetaData = DictProperty([])
   stationList     = ListProperty([])
   tempestList     = ListProperty([])
   deviceList      = DictProperty([])
   skyList         = ListProperty([])
   airList         = ListProperty([])

   # Initialise 'mainMenu' ModalView class
   def __init__(self, **kwargs):
       super().__init__(**kwargs)
       self.app = App.get_running_app()
       self.initialiseStatusPanels()
       self.get_stationList()

   def on_open(self):
       self.app.mainMenu = self

   # Initialise device status panels based on devices connected to station
   def initialiseStatusPanels(self):

       # Add device status panels based on devices connected to station
       if self.app.config['Station']['TempestID']:
           self.ids.devicePanel.add_widget(self.app.Station.tempestStatusPanel)
       if self.app.config['Station']['SkyID']:
           self.ids.devicePanel.add_widget(self.app.Station.skyStatusPanel)
       if self.app.config['Station']['OutAirID']:
           self.ids.devicePanel.add_widget(self.app.Station.outAirStatusPanel)
       if self.app.config['Station']['InAirID']:
           self.ids.devicePanel.add_widget(self.app.Station.inAirStatusPanel)

       # Populate status fields
       self.app.Station.get_observationCount()
       self.app.Station.get_hubFirmware()

   # Fetch list of stations associated with WeatherFlow key
   def get_stationList(self):
       URL = 'https://swd.weatherflow.com/swd/rest/stations?token={}'
       URL = URL.format(self.app.config['Keys']['WeatherFlow'])
       UrlRequest(URL,
                  on_success=self.parse_stationList,
                  on_failure=self.fail_stationList,
                  on_error=self.fail_stationList,
                  ca_file=certifi.where())

   # Parse list of stations associated with WeatherFlow key
   def parse_stationList(self, Request, Response):
       if 'status' in Response:
           if 'SUCCESS' in Response['status']['status_message']:
               self.stationDetails = {}
               for Station in Response['stations']:
                   self.stationDetails[Station['name']] = Station
               self.stationList = list(self.stationDetails.keys())
               self.ids.stationList.text = self.app.config['Station']['Name']

   # FALIED TO FETCH LIST OF STATIONS
   # -------------------------------------------------------------------------
   def fail_stationList(self, Request, Response):
       if isinstance(Response, socket.gaierror):
           self.ids.loginButton.text = 'Host name error. Please try again'
       else:
           self.ids.loginButton.text = f'Error {Request.resp_status}. Please try again'

   # GET DEVICES ASSOCIATED WITH SELECTED STATION
   # -------------------------------------------------------------------------
   def get_stationDevices(self):

       # Define required variables
       #self.ids.continueButton.text = 'Fetching Station information'
       self.stationMetaData = {}
       self.deviceMetaData = {}
       self.deviceList = {}
       self.tempestList = []
       self.skyList = []
       self.airList = []
       self.retries = 0

       # Fetch all devices associated with Station
       if self.stationDetails:
           self.get_stationMetaData()
           for Device in self.stationDetails[self.ids.stationList.text]['devices']:
               if 'device_type' in Device:
                   if Device['device_type'] == 'ST':
                       self.tempestList.append(Device['device_meta']['name'] + ': ' + str(Device['device_id']))
                       self.deviceMetaData[str(Device['device_id'])] = Device
                   if Device['device_type'] == 'SK':
                       self.skyList.append(Device['device_meta']['name'] + ': ' + str(Device['device_id']))
                       self.deviceMetaData[str(Device['device_id'])] = Device
                   if Device['device_type'] == 'AR':
                       self.airList.append(Device['device_meta']['name'] + ': ' + str(Device['device_id']))
                       self.deviceMetaData[str(Device['device_id'])] = Device

       # Initialise device selection lists based on the number and type of
       # devices associated with the station.
       # [1] Tempest AND (Sky OR Air)
       if self.tempestList and (self.skyList or self.airList):
           self.ids.tempestDropdown.disabled = 0
           self.tempestList.insert(len(self.tempestList), 'Clear')
           if (self.app.config['Station']['TempestID'] and
               self.ids.stationList.text == self.app.config['Station']['Name']):
               for tempest in self.tempestList:
                   if self.app.config['Station']['TempestID'] in tempest:
                       self.ids.tempestDropdown.text = tempest
               self.ids.skyDropdown.text     = self.ids.airDropdown.text     = 'Tempest selected'
               self.ids.skyDropdown.disabled = self.ids.airDropdown.disabled = 1
           else:
               self.ids.tempestDropdown.text = 'Please select'

               if self.skyList:
                   if (self.app.config['Station']['SkyID'] and
                       self.ids.stationList.text == self.app.config['Station']['Name']):
                       self.ids.skyDropdown.disabled = 0
                       for sky in self.skyList:
                           if self.app.config['Station']['SkyID'] in sky:
                               self.ids.skyDropdown.text = sky
                       self.ids.tempestDropdown.text = 'Sky selected'
                       self.ids.tempestDropdown.disabled = 0
                   else:
                       self.ids.skyDropdown.text = 'Please select'
                       self.ids.skyDropdown.disabled = 0
                   self.skyList.insert(len(self.skyList), 'Clear')
               else:
                   self.ids.skyDropdown.text = 'No device available'
                   self.ids.skyDropdown.disabled = 1

               if self.airList:
                   if (self.app.config['Station']['OutAirID'] and
                       self.ids.stationList.text == self.app.config['Station']['Name']):
                       self.ids.airDropdown.disabled = 0
                       for air in self.airList:
                           if self.app.config['Station']['OutAirID'] in air:
                               self.ids.airDropdown.text = air
                       self.ids.tempestDropdown.text = 'Air selected'
                       self.ids.tempestDropdown.disabled = 0
                   else:
                       self.ids.airDropdown.text = 'Please select'
                       self.ids.airDropdown.disabled = 0
                   self.airList.insert(len(self.airList), 'Clear')
               else:
                   self.ids.airDropdown.text = 'No device available'
                   self.ids.airDropdown.disabled = 1

       # [2] Tempest ONLY
       elif self.tempestList:
           self.ids.tempestDropdown.disabled = 0
           self.ids.airDropdown.disabled = self.ids.skyDropdown.disabled = 1
           self.ids.airDropdown.text     = self.ids.skyDropdown.text     = 'No device available'
           if self.ids.stationList.text == self.app.config['Station']['Name']:
               for tempest in self.tempestList:
                   if self.app.config['Station']['TempestID'] in tempest:
                       self.ids.tempestDropdown.text = tempest
           else:
               self.ids.tempestDropdown.text = 'Please select'
           self.tempestList.insert(len(self.tempestList), 'Clear')

       # [3] Sky OR Air ONLY
       elif self.skyList or self.airList:
           self.ids.tempestDropdown.disabled = 1
           self.ids.tempestDropdown.text = 'No device available'

           if self.airList:
               self.ids.airDropdown.disabled = 0
               if (self.app.config['Station']['OutAirID'] and
                   self.ids.stationList.text == self.app.config['Station']['Name']):
                   for air in self.airList:
                       if self.app.config['Station']['OutAirID'] in air:
                           self.ids.airDropdown.text = air
               else:
                   self.ids.airDropdown.text = 'Please select'
               self.tempestList.insert(len(self.airList), 'Clear')
           else:
               self.ids.airDropdown.text = 'No device available'
               self.ids.airDropdown.disabled = 1

           if self.skyList:
               self.ids.skyDropdown.disabled = 0
               if (self.app.config['Station']['SkyID'] and
                   self.ids.stationList.text == self.app.config['Station']['Name']):
                   for sky in self.skyList:
                       if self.app.config['Station']['SkyID'] in sky:
                           self.ids.skyDropdown.text = sky
               else:
                   self.ids.skyDropdown.text = 'Please select'
               self.tempestList.insert(len(self.skyList), 'Clear')
           else:
               self.ids.skyDropdown.text = 'No device available'
               self.ids.skyDropdown.disabled = 1

   # SET BEHAVIOUR OF DEVICE SELECTION LISTS AS USER SELECTS THEIR DEVICES
   # --------------------------------------------------------------------------
   def on_deviceSelection(self, instance):
       instance_id = list(self.ids.keys())[list(self.ids.values()).index(instance)]
       if instance.text == 'Clear':
           for device in ['tempest', 'sky', 'air']:
               if getattr(self, device + 'List'):
                   getattr(self.ids, device + 'Dropdown').text = 'Please select'
                   getattr(self.ids, device + 'Dropdown').disabled = 0
           self.ids.switchButton.disabled = 1
           self.ids.switchButton.text = 'Please select devices'
           self.deviceList = {}
       else:
           Device = self.deviceMetaData[instance.text.split(':')[1].strip()]
           self.deviceList[Device['device_type']] = Device
           if instance_id == 'tempestDropdown':
               self.ids.skyDropdown.disabled = self.ids.airDropdown.disabled = 1
               if self.airList:
                   self.ids.airDropdown.text = 'Tempest selected'
               if self.skyList:
                   self.ids.skyDropdown.text = 'Tempest selected'
           elif instance_id in ['skyDropdown', 'airDropdown']:
               self.ids.tempestDropdown.disabled = 1
               if self.tempestList:
                   self.ids.tempestDropdown.text = 'Air or Sky selected'
       if self.ids.switchButton.text != 'Fetching Station information':
           self.set_switchButton()

   # GET METADATA ASSOCIATED WITH SELECTED STATION
   # -------------------------------------------------------------------------
   def get_stationMetaData(self):
       self.ids.switchButton.text = 'Fetching Station information'
       self.ids.switchButton.disabled = 1
       if hasattr(self, 'pendingRequest'):
           self.pendingRequest.cancel()
       if hasattr(self, 'activeRequest'):
           self.activeRequest.cancel()
       if self.stationDetails:
           station = self.ids.stationList.text
           URL = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?token={}'
           URL = URL.format(self.stationDetails[station]['station_id'], App.get_running_app().config['Keys']['WeatherFlow'])
           self.activeRequest = UrlRequest(URL,
                                           on_success=self.parse_stationMetaData,
                                           on_failure=self.fail_stationMetaData,
                                           on_error=self.fail_stationMetaData,
                                           ca_file=certifi.where())

   # PARSE METADATA ASSOCIATED WITH SELECTED STATION
   # -------------------------------------------------------------------------
   def parse_stationMetaData(self, Request, Response):

       # Parse Station metadata received from API request
       self.retries += 1
       if 'status' in Response:
           if 'SUCCESS' in Response['status']['status_message']:
               self.stationMetaData = Response
           elif self.retries <= 3:
               self.ids.switchButton.text = 'Bad response. Retrying...'
               self.pendingRequest = Clock.schedule_once(lambda dt: self.get_stationMetaData(), 2)
               return
           else:
               self.ids.switchButton.text = 'Failed to fetch Station information'
               self.ids.switchButton.disabled = 1
               return
       self.set_switchButton()

   # FAILED TO GET METADATA ASSOCIATED WITH SELECTED STATION
   # -------------------------------------------------------------------------
   def fail_stationMetaData(self, Request, Response):
       self.retries += 1
       if self.retries <= 3:
           self.ids.switchButton.text = 'Bad response. Retrying...'
           Clock.schedule_once(lambda dt: self.get_stationMetaData(), 2)
       else:
           self.ids.switchButton.text = 'Failed to fetch Station information'

   # SET TEXT OF continueButton BASED ON STATUS OF DEVICE SELECTION LISTS
   # -------------------------------------------------------------------------
   def set_switchButton(self):
       newStation = self.ids.stationList.text != self.app.config['Station']['Name']
       newDevice  = (self.app.config['Station']['TempestID'] not in self.ids.tempestDropdown.text or
                     self.app.config['Station']['SkyID']     not in self.ids.skyDropdown.text     or
                     self.app.config['Station']['OutAirID']  not in self.ids.airDropdown.text)
       deviceSelected = (self.ids.tempestDropdown.selected or
                         self.ids.skyDropdown.selected     or
                         self.ids.airDropdown.selected)
       if newStation:
           if deviceSelected:
               self.ids.switchButton.disabled = 0
               self.ids.switchButton.text = 'Switch station'
           else:
               self.ids.switchButton.text = 'Please select devices'
       else:
           if deviceSelected and newDevice:
               self.ids.switchButton.disabled = 0
               self.ids.switchButton.text = 'Switch devices'
           else:
               if deviceSelected:
                   self.ids.switchButton.disabled = 1
                   self.ids.switchButton.text = 'Station & Devices unchanged'
               else:
                   self.ids.switchButton.disabled = 1
                   self.ids.switchButton.text = 'Please select devices'


   def switchStations(self):
       self.dismiss(animation=False)
       # Retries = 0
       # while Retries < 3:
       #     try:
       #         self.app.oscCLIENT.send_message(b'/websocket', [('listen_stop').encode('utf8')])
       #         break
       #     except Exception:
       #         Retries += 1
       #
       #
       #
       # config.switch(self.stationMetaData, self.deviceList, self.app.config)
       #
       # Retries = 0
       # while Retries < 3:
       #     try:
       #         self.app.oscCLIENT.send_message(b'/websocket', [('reload_config').encode('utf8')])
       #         break
       #     except Exception:
       #         Retries += 1



       Retries = 0
       while Retries < 3:
           try:
               self.app.oscCLIENT.send_message(b'/websocket', [('switch_device').encode('utf8'),
                                                               json.dumps(self.stationMetaData).encode('utf8'),
                                                               json.dumps(self.deviceList).encode('utf8')])
               break
           except Exception:
               Retries += 1



       #self.app.stopWebsocketService()
       #self.app.Sched.deviceStatus.cancel()
       #del(self.app.Station)


       config.switch(self.stationMetaData, self.deviceList, self.app.config)
       #self.app.CurrentConditions.Obs = properties.Obs()

       #print(dict(properties.Obs()))
       #print()
       #print(self.app.CurrentConditions.Obs)
       system.updateDisplay('obs_all', dict(properties.Obs()), self.app)

       #self.app.startWebsocketService()
       #self.app.Station = station.Station(self.app)
       #self.app.Sched.deviceStatus = Clock.schedule_interval(self.app.Station.get_deviceStatus, 1.0)

   # Exit console and shutdown system
   def shutdownSystem(self):
       global SHUTDOWN
       SHUTDOWN = 1
       App.get_running_app().stop()

   # Exit console and reboot system
   def rebootSystem(self):
       global REBOOT
       REBOOT = 1
       App.get_running_app().stop()

   # Delete device status panel widgets when closing main menu
   def on_dismiss(self):
       self.ids.devicePanel.clear_widgets()



# =============================================================================
# DEFINE 'deviceStatusPanel' CLASS
# =============================================================================
class deviceStatusPanel(BoxLayout):

    stationStatus = DictProperty([])
    SampleTime    = StringProperty('-')
    Station       = ObjectProperty()
    Voltage       = StringProperty('-')
    ObCount       = StringProperty('-')
    Device        = StringProperty('-')
    Status        = StringProperty('-')

    def __init__(self, station, device_type, **kwargs):
        super().__init__(**kwargs)
        self.device_type = device_type
        self.station = station
        self.station.bind(Status=self.setter('stationStatus'))
        self.bind(stationStatus=self.statusChange)

        # Define device display name for status panel
        if 'out' in self.device_type:
            self.Device = 'AIR (outdoor)'
        elif 'in' in self.device_type:
            self.Device = 'AIR (indoor)'
        else:
            self.Device = self.device_type.upper()

    def statusChange(self, _instance, newStatus):
        for field, value in newStatus.items():
            if self.device_type in field:
                setattr(self, field.replace(self.device_type,''), value)
