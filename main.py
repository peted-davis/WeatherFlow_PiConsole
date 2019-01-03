# WeatherFlow PiConsole: Raspberry Pi Python console for Weather Flow 
# Smart Home Weather Station. Copyright (C) 2018  Peter Davis

# This program is free software: you can redistribute it and/or modify it under 
# the terms of the GNU General Public License as published by the Free Software 
# Foundation, either version 3 of the License, or (at your option) any later 
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT 
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more 
# details.

# You should have received a copy of the GNU General Public License along with 
# this program.  If not, see <http://www.gnu.org/licenses/>.

# ==============================================================================
# INITIALISE KIVY BACKEND BASED ON CURRENT HARDWARE TYPE
# ==============================================================================
import platform
import os
if platform.system() == 'Linux' and 'arm' in platform.machine():
	os.environ['KIVY_GL_BACKEND'] = 'gl'
elif platform.system() == 'Windows':
	os.environ['KIVY_GL_BACKEND'] = 'glew'
	
# ==============================================================================
# CREATE OR UPDATE wfpiconsole.ini FILE
# ==============================================================================
from lib import configCreate
from pathlib import Path
if not Path('wfpiconsole.ini').is_file():
	configCreate.create_ini()
else:
	configCreate.update_ini()
	
# ==============================================================================
# INITIALISE KIVY TWISTED WEBSOCKET CLIENT
# ==============================================================================
from kivy.support import install_twisted_reactor
install_twisted_reactor()

from twisted.python import log
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.policies import TimeoutMixin
from autobahn.twisted.websocket import WebSocketClientProtocol,WebSocketClientFactory

# Specifies behaviour of Websocket Client									   
class WeatherFlowClientProtocol(WebSocketClientProtocol,TimeoutMixin):

	def onConnect(self, response):
		self.factory.resetDelay()
		self.setTimeout(300)
	
	def onOpen(self):
		self.factory._proto = self
		
	def onMessage(self,payload,isBinary):
		Message = json.loads(payload.decode('utf8'))
		self.factory._app.WebsocketDecodeMessage(Message)
		self.resetTimeout()
		
	def timeoutConnection(self):
		self.transport.loseConnection()
		
	def onClose(self,wasClean,code,reason):
		self.factory._proto = None

# Specifies Websocket Factory		
class WeatherFlowClientFactory(WebSocketClientFactory,ReconnectingClientFactory):

	# Define protocol and reconnection properties
	protocol = WeatherFlowClientProtocol
	initialDelay = 60
	maxDelay = 60
	jitter = 0
	
	def clientConnectionFailed(self,connector,reason):
		print('Client connection failed .. retrying ..')
		self.retry(connector)

	def clientConnectionLost(self,connector,reason):
		print('Client connection lost .. retrying ..')
		self.retry(connector)
	
	def __init__(self, url, app):
		WebSocketClientFactory.__init__(self,url)
		self._app = app
		self._proto = None

# ==============================================================================
# IMPORT REQUIRED MODULES
# ==============================================================================
from kivy.app import App
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.uix.screenmanager import ScreenManager,Screen
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.properties import StringProperty,DictProperty,NumericProperty
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.config import ConfigParser
from kivy.uix.settings import SettingsWithSidebar
from twisted.internet import reactor,ssl
from datetime import datetime,date,time,timedelta
from geopy import distance as geopy
from packaging import version
from lib import sager
import time as UNIX
import numpy as np
import pytz
import math
import bisect
import json
import requests
import ephem
import sys

from kivy.uix.settings import SettingOptions 
from kivy.uix.gridlayout import GridLayout 
from kivy.uix.scrollview import ScrollView 
from kivy.uix.widget import Widget 
from kivy.uix.togglebutton import ToggleButton 
from kivy.uix.settings import SettingSpacer 
from kivy.uix.button import Button 
from kivy.metrics import dp 
from kivy.uix.popup import Popup

# ==============================================================================
# DEFINE GLOBAL FUNCTIONS AND VARIABLES
# ==============================================================================
# Define global variables
NaN = float('NaN')

# CIRCULAR MEAN
# ------------------------------------------------------------------------------
def CircularMean(angles):
	angles = np.radians(angles)
	r = np.nanmean(np.exp(1j*angles))
	return np.angle(r, deg=True) % 360

# VERIFY IF DATA IS VALID JSON STRING
# ------------------------------------------------------------------------------
def VerifyJSON(Data):
	if not Data.ok:
		return False
	try:
		Data.json()
	except ValueError:
		return False
	else:
		return True

# ==============================================================================
# DEFINE 'WeatherFlowPiConsole' APP CLASS
# ==============================================================================
class wfpiconsole(App):

	# Define Kivy properties required for display in 'WeatherFlowPiConsole.kv' 
	System = DictProperty([('ForecastLocn','--'),('Units',{}),('BaromLim','--')])
	MetData = DictProperty([('Temp','--'),('Precip','--'),('WindSpd','--'),
							('WindDir','--'),('Weather','Building'),
	                        ('Valid','--'),('Issued','--')])
	Sager = DictProperty([('Lat','--'),('MetarKey','--'),('WindDir6','--'),
	                      ('WindDir','--'),('WindSpd6','--'),('WindSpd','--'),
						  ('Pres','--'),('Pres6','--'),('LastRain','--'),
						  ('Temp','--'),('Dial','--'),('Forecast','--'),
						  ('Issued','--')])									 
	SkyRapid = DictProperty([('Time','-'),('Speed','--'),('Direc','----')])	
	SkyRapidIcon = NumericProperty(0)							 
	Sky = DictProperty([('WindSpd','----'),('WindGust','--'),('WindDir','---'),
						('AvgWind','--'),('MaxGust','--'),('RainRate','---'),
						('TodayRain','--'),('YesterdayRain','--'),('MonthRain','--'),
						('YearRain','--'),('Radiation','----'),('UV','---'),
						('Time','-'),('Battery','--'),('StatusIcon','Error')])
	Breathe = DictProperty([('Temp','--'),('MinTemp','---'),('MaxTemp','---')])		
	Air = DictProperty([('Temp','--'),('MinTemp','---'),('MaxTemp','---'),
						('Humidity','--'),('DewPoint','--'),('Pres','---'),
						('MaxPres','--'),('MinPres','--'),('PresTrend','---'),
						('FeelsLike','--'),('Comfort','--'),('Time','-'),
						('Battery','--'),('StatusIcon','Error')])									 
	SunData = DictProperty([('Sunrise',['-','-']),('Sunset',['-','-']),('SunAngle','-'),
							('Event',['-','-','-']),('ValidDate','--')])
	MoonData = DictProperty([('Moonrise',['-','-']),('Moonset',['-','-']),('NewMoon','--'),
							 ('FullMoon','--'),('Phase','---')])	
	MetDict = DictProperty()						
    
	# INITIALISE 'WeatherFlowPiConsole' CLASS
	# --------------------------------------------------------------------------
	def __init__(self,**kwargs):
	
		# Initiate class
		super(wfpiconsole,self).__init__(**kwargs)
		
		# Force window size if required
		if 'arm' not in platform.machine():
			Window.size = (800,480)
	
		# Parse variables from wfpiconsole.ini configuration file
		config = ConfigParser()
		config.read('wfpiconsole.ini')		
		
		# Assign configuration variables to Kivy properties
		self.System['WFlowKey'] = config['System']['WFKey']
		self.System['Version'] = config['System']['Version']
		self.System['GeoNamesKey'] = config['Keys']['GeoNames']
		self.System['MetOfficeKey'] = config['Keys']['MetOffice']
		self.System['DarkSkyKey'] = config['Keys']['DarkSky']
		self.System['CheckWXKey'] = config['Keys']['CheckWX']
		self.System['StationID'] = config['Station']['StationID']
		self.System['OutdoorID'] = config['Station']['OutdoorID']
		self.System['IndoorID'] = config['Station']['IndoorID']
		self.System['SkyID'] = config['Station']['SkyID']

		# Determine height above ground of the outdoor, indoor, and Sky modules
		Template = 'https://swd.weatherflow.com/swd/rest/stations/{}?api_key={}'
		URL = Template.format(self.System['StationID'],self.System['WFlowKey'])
		Station = requests.get(URL).json()
		Devices = Station['stations'][0]['devices']
		for Dev in Devices:
			if 'device_type' in Dev:
				if str(Dev['device_id']) == self.System['OutdoorID']:
					self.System['OutdoorHeight'] = Dev['device_meta']['agl']
				elif str(Dev['device_id']) == self.System['SkyID']:
					self.System['SkyHeight'] = Dev['device_meta']['agl']
					
		# Determine Station latitude/longitude, elevation, and timezone
		self.System['Lat'] = Station['stations'][0]['latitude']
		self.System['Lon'] = Station['stations'][0]['longitude']
		self.System['tz'] = pytz.timezone(Station['stations'][0]['timezone'])
		self.System['StnElev'] = Station['stations'][0]['station_meta']['elevation']
		
		# Determine Station units
		Template = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?api_key={}'
		URL = Template.format(self.System['StationID'],self.System['WFlowKey'])
		Data = requests.get(URL).json()
		self.System['Units']['Temp'] = Data['station_units']['units_temp']
		self.System['Units']['Wind'] = Data['station_units']['units_wind']
		self.System['Units']['Precip'] = Data['station_units']['units_precip']
		self.System['Units']['Pressure'] = Data['station_units']['units_pressure']
		self.System['Units']['Distance'] = Data['station_units']['units_distance']
		self.System['Units']['Direction'] = Data['station_units']['units_direction']
		self.System['Units']['Other'] = Data['station_units']['units_other']
		
		# Define maximum and minimum pressure limits for barometer
		if self.System['Units']['Pressure'] == 'mb':
			self.System['BaromLim'] = ['950','1050']
		elif self.System['Units']['Pressure'] == 'hpa':
			self.System['BaromLim'] = ['950','1050']
		elif self.System['Units']['Pressure'] == 'inhg':
			self.System['BaromLim'] = ['28.0','31.0']
		elif self.System['Units']['Pressure'] == 'mmhg':
			self.System['BaromLim'] = ['713','788']
		
		# Determine country of Station
		Template = 'http://api.geonames.org/countryCode?lat={}&lng={}&username={}&type=json'
		URL = Template.format(self.System['Lat'],self.System['Lon'],self.System['GeoNamesKey'])
		Data = requests.get(URL)
		if Data.ok:
			if 'countryCode' in Data.json():
				self.System['Country'] = Data.json()['countryCode']
			else:
				self.System['Country'] = None
		else:
			self.System['Country'] = None		
		
		# If Station is located in Great Britain: determine closest MetOffice 
		# forecast location
		if self.System['Country'] == 'GB':
			Template = 'http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/json/sitelist?&key={}'
			URL = Template.format(self.System['MetOfficeKey'])
			Data = requests.get(URL).json()
			MinDist = math.inf
			for Locn in Data['Locations']['Location']:
				ForecastLocn = (float(Locn['latitude']),float(Locn['longitude']))
				StationLocn = (self.System['Lat'],self.System['Lon'])
				LatDiff = abs(StationLocn[0] - ForecastLocn[0])
				LonDiff = abs(StationLocn[1] - ForecastLocn[1])
				if (LatDiff and LonDiff) < 0.5:
					Dist = geopy.distance(StationLocn,ForecastLocn).km
					if Dist < MinDist:
						MinDist = Dist
						self.System['MetOfficeID'] = Locn['id']
						self.System['ForecastLocn'] = Locn['name']
						
		# Else determine location from Geonames API that most closely matches 
		# the Station latitude/longitude
		else:
			Template = 'http://api.geonames.org/findNearbyPlaceName?lat={}&lng={}&username={}&radius=10&featureClass=P&maxRows=20&type=json'	
			URL = Template.format(self.System['Lat'],self.System['Lon'],self.System['GeoNamesKey'])
			Data = requests.get(URL)
			if Data.ok:
				Locns = [Item['name'] for Item in Data.json()['geonames']]
				Len = [len(Item) for Item in Locns]
				Ind = next((Item for Item in Len if Item<=11),NaN)
				if Ind != NaN:
					self.System['ForecastLocn'] = Locns[Len.index(Ind)]
			else:
				self.System['ForecastLocn'] = ''
									
		# Initialise Sunrise and Sunset time, Moonrise andMoonset time, and 
		# MetOffice or DarkSky weather forecast data
		self.SunriseSunset()
		self.MoonriseMoonset()
		self.DownloadForecast()

		# Initialise Sager Weathercaster forecast, and check for latest version
		Clock.schedule_once(self.SagerForecast)
		Clock.schedule_once(self.CheckVersion)

		# Initialise websocket connection
		self.WebsocketConnect()

		# Define Kivy loop schedule
		Clock.schedule_interval(self.SkyAirStatus,1.0)
		Clock.schedule_interval(self.UpdateMethods,1.0)
		Clock.schedule_interval(self.SunTransit,1.0)
		Clock.schedule_interval(self.MoonPhase,1.0)
		
		self.Config = ConfigParser()
		self.Config.optionxform = str
		self.Config.read('wfpiconsole.ini')
		self.settings_cls = SettingsWithSidebar
		
	# BUILD SETTINGS SCREEN
	# --------------------------------------------------------------------------
	def build_settings(self,settings):
		settings.register_type('scrolloptions', SettingScrollOptions)
		self.use_kivy_settings  =  False
		jsondata = configCreate.settings_json()
		settings.add_json_panel('Display',self.Config,data=jsondata)	
		
	# CONNECT TO THE WEATHER FLOW WEBSOCKET SERVER
	# --------------------------------------------------------------------------
	def WebsocketConnect(self):
		Template = 'ws://ws.weatherflow.com/swd/data?api_key={}'
		Server = Template.format(self.System['WFlowKey'])
		self._factory = WeatherFlowClientFactory(Server,self)
		reactor.connectTCP('ws.weatherflow.com',80,self._factory)		

	# SEND MESSAGE TO THE WEATHER FLOW WEBSOCKET SERVER
	# --------------------------------------------------------------------------
	def WebsocketSendMessage(self,Message):
		Message = Message.encode('utf8')
		proto = self._factory._proto
		if Message and proto:
			proto.sendMessage(Message)
			
	# DECODE THE WEATHER FLOW WEBSOCKET MESSAGE
	# --------------------------------------------------------------------------
	def WebsocketDecodeMessage(self,Msg):

		# Extract type of received message
		Type = Msg['type']
		
		# Initialise data streaming upon connection of websocket
		if Type == 'connection_opened':	
			pass
#			self.WebsocketSendMessage('{"type":"listen_start",' +
#			                           ' "device_id":' + self.System['SkyID'] + ',' + 
#									   ' "id":"Sky"}')
#			self.WebsocketSendMessage('{"type":"listen_rapid_start",' +
#			                           ' "device_id":' + self.System['SkyID'] + ',' +
#									   ' "id":"RapidSky"}')
#			self.WebsocketSendMessage('{"type":"listen_start",' +
#			                           ' "device_id":' + self.System['OutdoorID'] + ',' +
#									   ' "id":"Outdoor"}')
			
		# Extract observations from obs_Sky websocket message
		elif Type == 'obs_sky':
			self.WebsocketObsSky(Msg)
									
		# Extract observations from obs_Air websocket message
		elif Type == 'obs_air':
			self.WebsocketObsAir(Msg)
				
		# Extract observations from Rapid_Wind websocket message	
		elif Type == 'rapid_wind':
			self.WebsocketRapidWind(Msg)

	# EXTRACT OBSERVATIONS FROM OBS_SKY WEBSOCKET JSON MESSAGE
	# --------------------------------------------------------------------------
	def WebsocketObsSky(self,Msg):
	
		# Replace missing observations from latest SKY Websocket JSON with NaN
		Obs = [x if x != None else NaN for x in Msg['obs'][0]]	
		
		# Extract required observations from latest SKY Websocket JSON 
		Time = [Obs[0],'s']
		UV = [Obs[2],'index']
		Rain = [Obs[3],'mm'] 
		WindSpd = [Obs[5],'mps']       
		WindGust = [Obs[6],'mps']      
		WindDir = [Obs[7],'degrees']
		Battery = [Obs[8],'v']
		Radiation = [Obs[10],' W m[sup]-2[/sup]']

		# Store latest SKY Websocket JSON
		self.Sky['Obs'] = Obs
		
		# Extract required observations from latest AIR Websocket JSON
		if 'Obs' in self.Air:
			Temp = [self.Air['Obs'][2],'c']
			Humidity = [self.Air['Obs'][3],'%']
		else:
			Temp = None
			Humidity = None
			
		# Set wind direction to None if wind speed is zero
		if WindSpd[0] == 0:
			WindDir = [None,'degrees']	
				
		# Calculate derived variables from SKY observations
		FeelsLike = self.FeelsLike(Temp,Humidity,WindSpd)
		RainRate = self.RainRate(Rain)
		TodayRain,YesterdayRain,MonthRain,YearRain = self.RainAccumulation(Rain) 
		AvgWind = self.MeanWindSpeed(WindSpd)
		MaxGust = self.SkyObsMaxMin(WindSpd,WindGust)
		Beaufort = self.BeaufortScale(WindSpd)
		WindDir = self.CardinalWindDirection(WindDir,WindSpd)
		UV = self.UVIndex(UV)
		
		# Convert observation units as required
		RainRate = self.ObservationUnits(RainRate,self.System['Units']['Precip'])
		TodayRain = self.ObservationUnits(TodayRain,self.System['Units']['Precip'])
		YesterdayRain = self.ObservationUnits(YesterdayRain,self.System['Units']['Precip'])
		MonthRain = self.ObservationUnits(MonthRain,self.System['Units']['Precip'])
		YearRain = self.ObservationUnits(YearRain,self.System['Units']['Precip'])
		WindSpd = self.ObservationUnits(WindSpd,self.System['Units']['Wind'])
		WindDir = self.ObservationUnits(WindDir,self.System['Units']['Direction'])
		WindGust = self.ObservationUnits(WindGust,self.System['Units']['Wind'])
		AvgWind = self.ObservationUnits(AvgWind,self.System['Units']['Wind'])
		MaxGust = self.ObservationUnits(MaxGust,self.System['Units']['Wind'])
		FeelsLike = self.ObservationUnits(FeelsLike,self.System['Units']['Temp'])

		# Define SKY Kivy label binds	
		self.Sky['Time'] =  datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M:%S')
		self.Sky['RainRate'] = self.ObservationFormat(RainRate,'Precip')
		self.Sky['TodayRain'] = self.ObservationFormat(TodayRain,'Precip')
		self.Sky['YesterdayRain'] = self.ObservationFormat(YesterdayRain,'Precip')
		self.Sky['MonthRain'] = self.ObservationFormat(MonthRain,'Precip')
		self.Sky['YearRain'] = self.ObservationFormat(YearRain,'Precip')
		self.Sky['WindSpd'] = self.ObservationFormat(WindSpd,'Wind') + Beaufort
		self.Sky['WindGust'] = self.ObservationFormat(WindGust,'Wind')
		self.Sky['AvgWind'] = self.ObservationFormat(AvgWind,'Wind')
		self.Sky['MaxGust'] = self.ObservationFormat(MaxGust,'Wind')
		self.Sky['Radiation'] = self.ObservationFormat(Radiation,'Radiation')
		self.Sky['UV'] = self.ObservationFormat(UV,'UV')
		self.Sky['Battery'] = self.ObservationFormat(Battery,'Battery')
		self.Sky['WindDir'] = self.ObservationFormat(WindDir,'Direction')

		# Define AIR Kivy label binds
		self.Air['FeelsLike'] = self.ObservationFormat(FeelsLike,'Temp')
	
	# EXTRACT OBSERVATIONS FROM OBS_AIR WEBSOCKET JSON MESSAGE
	# --------------------------------------------------------------------------
	def WebsocketObsAir(self,Msg):
	
		# Replace missing observations in latest AIR Websocket JSON with NaN
		Obs = [x if x != None else NaN for x in Msg['obs'][0]]	
		
		# Extract required observations from latest AIR Websocket JSON 	
		Time = [Obs[0],'s']
		Pres = [Obs[1],'mb']
		Temp = [Obs[2],'c']
		Humidity = [Obs[3],' %']
		Battery = [Obs[6],' v']
		
		# Store latest AIR Websocket JSON
		self.Air['Obs'] = Obs
		
		# Extract required observations from latest SKY Websocket JSON
		if 'Obs' in self.Sky:
			WindSpd = [self.Sky['Obs'][5],'mps']
		else:
			WindSpd = None

		# Calculate derived variables from AIR observations
		DewPoint = self.DewPoint(Temp,Humidity)
		FeelsLike = self.FeelsLike(Temp,Humidity,WindSpd)
		ComfortLevel = self.ComfortLevel(FeelsLike)
		SLP = self.SeaLevelPressure(Pres)
		PresTrend = self.PressureTrend(Pres)
		MaxTemp,MinTemp,MaxPres,MinPres = self.AirObsMaxMin(Time,Temp,Pres)

		# Convert observation units as required
		Temp = self.ObservationUnits(Temp,self.System['Units']['Temp'])
		MaxTemp = self.ObservationUnits(MaxTemp,self.System['Units']['Temp'])
		MinTemp = self.ObservationUnits(MinTemp,self.System['Units']['Temp'])
		DewPoint = self.ObservationUnits(DewPoint,self.System['Units']['Temp'])
		FeelsLike = self.ObservationUnits(FeelsLike,self.System['Units']['Temp'])
		SLP = self.ObservationUnits(SLP,self.System['Units']['Pressure'])
		MaxPres = self.ObservationUnits(MaxPres,self.System['Units']['Pressure'])
		MinPres = self.ObservationUnits(MinPres,self.System['Units']['Pressure'])
		PresTrend = self.ObservationUnits(PresTrend,self.System['Units']['Pressure'])
								
		# Define AIR Kivy label binds
		self.Air['Time'] = datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M:%S')
		self.Air['Temp'] = self.ObservationFormat(Temp,'Temp')
		self.Air['MaxTemp'] = self.ObservationFormat(MaxTemp,'Temp')
		self.Air['MinTemp'] = self.ObservationFormat(MinTemp,'Temp')
		self.Air['DewPoint'] = self.ObservationFormat(DewPoint,'Temp')	
		self.Air['FeelsLike'] = self.ObservationFormat(FeelsLike,'Temp')
		self.Air['Pres'] = self.ObservationFormat(SLP,'Pressure')
		self.Air['MaxPres'] = self.ObservationFormat(MaxPres,'Pressure')
		self.Air['MinPres'] = self.ObservationFormat(MinPres,'Pressure')
		self.Air['PresTrend'] = self.ObservationFormat(PresTrend,'Pressure')	
		self.Air['Humidity'] = self.ObservationFormat(Humidity,'Humidity')
		self.Air['Battery'] = self.ObservationFormat(Battery,'Battery')
		self.Air['Comfort'] = ComfortLevel
		
	# EXTRACT OBSERVATIONS FROM RAPID_WIND WEBSOCKET JSON MESSAGE
	# --------------------------------------------------------------------------
	def WebsocketRapidWind(self,Msg):
	
		# Replace missing observations from SKY Rapid-Wind Websocket JSON 
		# with NaN
		Obs = [x if x != None else NaN for x in Msg['ob']]	

		# Extract observations from latest SKY Rapid-Wind Websocket JSON 
		Time = [Obs[0],'s']
		WindSpd = [Obs[1],'mps'] 
		WindDir = [Obs[2],'degrees']
		
		# Extract wind direction from previous SKY Rapid-Wind Websocket JSON
		if 'Obs' in self.SkyRapid:
			WindDirOld = [self.SkyRapid['Obs'][2],'degrees']
		else:
			WindDirOld = [0,'degrees']
					
		# If windspeed is zero, freeze direction at last direction of 
		# non-zero wind speed, and edit latest SKY Rapid-Wind Websocket JSON 
		if WindSpd[0] == 0:
			WindDir = WindDirOld
			Obs[2] = WindDirOld[0]
			
		# Store latest SKY Observation JSON message
		self.SkyRapid['Obs'] = Obs
		
		# Calculate derived variables from Rapid SKY observations
		WindDir = self.CardinalWindDirection(WindDir,WindSpd)
		
		# Convert observation units as required
		WindSpd = self.ObservationUnits(WindSpd,self.System['Units']['Wind'])
		WindDir = self.ObservationUnits(WindDir,'degrees')
		
		# Define Rapid-SKY Kivy label binds
		self.SkyRapid['Time'] = datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M:%S')
		self.SkyRapid['Speed'] = self.ObservationFormat(WindSpd,'Wind')
		self.SkyRapid['Direc'] = self.ObservationFormat(WindDir,'Direction')
		
		# Animate wind rose arrow 
		self.WindRoseAnimation(WindDir[0],WindDirOld[0])
	
	# CONVERT STATION OBSERVATIONS INTO REQUIRED UNITS
    # --------------------------------------------------------------------------		
	def ObservationUnits(self,Obs,Unit):
		
		# Convert temperature observations
		cObs = Obs[:]
		if Unit in ['f','c']: 
			for ii,T in enumerate(Obs):
				if T == 'c':
					if Unit == 'f':
						cObs[ii-1] = Obs[ii-1] * 9/5 + 32
						cObs[ii] = ' [sup]o[/sup]F'
					else:
						cObs[ii-1] = Obs[ii-1]
						cObs[ii] = ' [sup]o[/sup]C'	

		# Convert pressure and pressure trend observations 
		elif Unit in ['inhg','mmhg','hpa','mb']: 
			for ii,P in enumerate(Obs):
				if P in ['mb','mb/hr']:
					if Unit == 'inhg':
						cObs[ii-1] = Obs[ii-1] * 0.0295301
						if P == 'mb':
							cObs[ii] = ' inHg'
						else:
							cObs[ii] = ' inHg/hr'
						
					elif Unit == 'mmhg':
						cObs[ii-1] = Obs[ii-1] * 0.750063
						if P == 'mb':
							cObs[ii] = ' mmHg'
						else:
							cObs[ii] = ' mmHg/hr'
					elif Unit == 'hpa':
						cObs[ii-1] = Obs[ii-1]
						if P == 'mb':
							cObs[ii] = ' hpa'
						else:
							cObs[ii] = ' hpa/hr'
					else:
						cObs[ii-1] = Obs[ii-1]
						if P == 'mb':
							cObs[ii] = ' mb'
						else:
							cObs[ii] = ' mb/hr'
						
		# Convert windspeed observations
		elif Unit in ['mph','lfm','kts','kph','bft','mps']:
			for ii,W in enumerate(Obs):
				if W == 'mps':
					if Unit == 'mph' or Unit == 'lfm':
						cObs[ii-1] = Obs[ii-1] * 2.2369362920544
						cObs[ii] = 'mph'
					elif Unit == 'kts':
						cObs[ii-1] = Obs[ii-1] * 1.9438
						cObs[ii] = 'kts'
					elif Unit == 'kph':
						cObs[ii-1] = Obs[ii-1] * 3.6
						cObs[ii] = 'km/h'							
					elif Unit == 'bft':
						cObs[ii-1] = self.BeaufortScale(Obs[ii-1:ii+1])[2] 
						cObs[ii] = 'bft'
					else:
						cObs[ii-1] = Obs[ii-1]
						cObs[ii] = 'm/s'	

		# Convert wind direction observations
		elif Unit in ['degrees','cardinal']:
			for ii,W in enumerate(Obs):
				if W == 'degrees':
					if cObs[ii-1] is None:
						cObs[ii-1] = 'Calm'
						cObs[ii] = ''
					elif Unit == 'cardinal':
						cObs[ii-1] = self.CardinalWindDirection(Obs[ii-1:ii+1])[2]   
						cObs[ii] = ''
					else:
						cObs[ii-1] = Obs[ii-1]   
						cObs[ii] = '[sup]o[/sup]'
						
		# Convert rain accumulation and rain rate observations
		elif Unit in ['in','cm','mm']:
			for ii,Prcp in enumerate(Obs):
				if Prcp in ['mm','mm/hr']:
					if Unit == 'in':
						cObs[ii-1] = Obs[ii-1] * 0.0393701
						if Prcp == 'mm':
							cObs[ii] = '"'
						else:
							cObs[ii] = ' in/hr'
					elif Unit == 'cm':
						cObs[ii-1] = Obs[ii-1] * 0.1
						if Prcp == 'mm':
							cObs[ii] = ' cm'
						else:
							cObs[ii] = ' cm/hr'	
					else:
						cObs[ii-1] = Obs[ii-1]
						if Prcp == 'mm':
							cObs[ii] = ' mm'	
						else:
							cObs[ii] = ' mm/hr'				
						
		# Return converted observations	
		return cObs
				
	# FORMAT STATION OBSERVATIONS AND DERIVED VARIABLES FOR DISPLAY
	# --------------------------------------------------------------------------
	def ObservationFormat(self,Obs,Type):

		# Format temperature observations
		cObs = Obs[:]
		if Type == 'Temp':
			for ii,T in enumerate(Obs):
				if isinstance(T,str) and T.strip() in ['[sup]o[/sup]F','[sup]o[/sup]C']:
					if math.isnan(cObs[ii-1]):
						cObs[ii-1] = '-'
					else:	
						cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])
						
		# Format pressure observations
		elif Type == 'Pressure':
			for ii,P in enumerate(Obs):
				if isinstance(P,str): 
					if P.strip() in ['inHg/hr','inHg']:
						cObs[ii-1] = '{:2.3f}'.format(cObs[ii-1])	
					elif P.strip() in ['mmHg/hr','mmHg']:
						cObs[ii-1] = '{:3.2f}'.format(cObs[ii-1])
					elif P.strip() in ['hpa/hr','mb/hr','hpa','mb']:
						cObs[ii-1] = '{:4.1f}'.format(cObs[ii-1])
	
		# Format windspeed observations
		elif Type == 'Wind':
			for ii,W in enumerate(Obs):
				if isinstance(W,str) and W.strip() in ['mph','kts','km/h','bft','m/s']:
					if cObs[ii-1] < 10:
						cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])	
					else:
						cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])
						
		# Format wind direction observations
		elif Type == 'Direction':
			for ii,D in enumerate(Obs):
				if isinstance(D,str) and D.strip() in ['[sup]o[/sup]']:
						cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])				
						
		# Format rain accumulation and rain rate observations
		elif Type == 'Precip':
			for ii,Prcp in enumerate(Obs):
				if isinstance(Prcp,str):
					if Prcp.strip() in ['mm','mm/hr']:	
						if cObs[ii-1] == 0:
							cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])
						elif cObs[ii-1] < 0.1:
							cObs[ii-1] = 'Trace'
							cObs[ii] = ''
						elif cObs[ii-1] < 10:
							cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])	
						else:
							cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])				
					elif Prcp.strip() in ['"','in/hr','cm/hr','cm']:							
						if cObs[ii-1] == 0:
							cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])
						elif cObs[ii-1] < 0.01:
							cObs[ii-1] = 'Trace'
							cObs[ii] = ''
						elif cObs[ii-1] < 10:
							cObs[ii-1] = '{:.2f}'.format(cObs[ii-1])
						elif cObs[ii-1] < 100:
							cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])
						else:
							cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])
							
		# Format humidity observations
		elif Type == 'Humidity':	
			for ii,H in enumerate(Obs):
				if isinstance(H,str) and H.strip() == '%':
						cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])
					
		# Format solar radiation observations
		elif Type == 'Radiation':	
			for ii,Rad in enumerate(Obs):
				if isinstance(Rad,str) and Rad.strip() == 'W m[sup]-2[/sup]':
						cObs[ii-1] = '{:.0f}'.format(cObs[ii-1])	

		# Format UV observations
		elif Type == 'UV':	
			for ii,UV in enumerate(Obs):
				if isinstance(UV,str) and UV.strip() == 'index':
						cObs[ii-1] = '{:.1f}'.format(cObs[ii-1])				
					
		# Format battery voltage observations
		elif Type == 'Battery':	
			for ii,V in enumerate(Obs):
				if isinstance(V,str) and V.strip() == 'v':
						cObs[ii-1] = '{:.2f}'.format(cObs[ii-1])			
		
		# Return formatted observations
		return cObs
				
	# ANIMATE RAPID-WIND WIND ROSE DIRECTION ARROW
	# --------------------------------------------------------------------------
	def WindRoseAnimation(self,newDirec,oldDirec):

		# Calculate change in wind direction over last Rapid-Wind period
		WindShift = newDirec - oldDirec	
					
		# Animate Wind Rose at constant speed between old and new Rapid-Wind 
		# wind direction
		if WindShift >= -180 and WindShift <= 180:
			Anim = Animation(SkyRapidIcon=newDirec,duration=2*abs(WindShift)/360)
			Anim.start(self)
		elif WindShift > 180:
			Anim = Animation(SkyRapidIcon=0.1,duration=2*oldDirec/360) + Animation(SkyRapidIcon=newDirec,duration=2*(360-newDirec)/360)		
			Anim.start(self)
		elif WindShift < -180:
			Anim = Animation(SkyRapidIcon=359.9,duration=2*(360-oldDirec)/360) + Animation(SkyRapidIcon=newDirec,duration=2*newDirec/360)
			Anim.start(self)
	
	# Fix Wind Rose angle at 0/360 degree discontinuity 		
	def on_SkyRapidIcon(self,item,SkyRapidIcon):
		if SkyRapidIcon == 0.1:
			item.SkyRapidIcon = 360	
		if SkyRapidIcon == 359.9:
			item.SkyRapidIcon = 0		
			
	# CALCULATE DEW POINT FROM HUMIDITY AND TEMPERATURE
    # --------------------------------------------------------------------------
	def DewPoint(self,Temp,Humidity):
		
		# Calculate dew point unless humidity equals zero
		if Humidity != 0:
			A = 17.625
			B = 243.04
			N = B*(math.log(Humidity[0]/100.0) + (A*Temp[0])/(B+Temp[0]))
			D = A-math.log(Humidity[0]/100.0) - (A*Temp[0])/(B+Temp[0])
			DewPoint = N/D
		else:
			DewPoint = NaN
		
		# Return Dew Point
		return [DewPoint,'c']
		
	# CALCULATE 'FEELS LIKE' TEMPERATURE FROM TEMPERATURE, RELATIVE HUMIDITY, 
	# AND WIND SPEED
    # --------------------------------------------------------------------------
	def FeelsLike(self,TempC,RH,WindSpd):
	
		# Skip calculation during initialisation
		if None in [TempC,RH,WindSpd]:
			return [NaN,'c']
						
		# Convert observation units as required
		TempF = self.ObservationUnits(TempC,'f')
		WindMPH = self.ObservationUnits(WindSpd,'mph')         
		WindKPH = self.ObservationUnits(WindSpd,'kph')				
						
		# If temperature is less than 10 degrees celcius and wind speed is 
		# higher than 5 mph, calculate wind chill using the Joint Action Group 
		# for Temperature Indices formula
		if TempC[0] <= 10 and WindMPH[0] > 5:
		
			# Calculate wind chill
			WindChill = 13.12 + 0.6215*TempC[0] - 11.37*(WindKPH[0])**0.16 + 0.3965*TempC[0]*(WindKPH[0])**0.16
			FeelsLike = [WindChill,'c']
			
		# If temperature is at or above 80 degress farenheit (26.67 C), and 
		# humidity is at or above 40%, calculate the Heat Index
		elif TempF[0] >= 80 and RH[0] >= 40:
		
			# Calculate Heat Index
			HeatIndex = -42.379 + (2.04901523*TempF[0]) + (10.1433127*RH[0]) - (0.22475541*TempF[0]*RH[0]) - (6.83783e-3*TempF[0]**2) - (5.481717e-2*RH[0]**2) + (1.22874e-3*TempF[0]**2*RH[0]) + (8.5282e-4*TempF[0]*RH[0]**2) - (1.99e-6*TempF[0]**2*RH[0]**2)
			FeelsLike = [(HeatIndex-32)*5/9,'c']

		# Else set 'Feels Like' temperature to observed temperature
		else: 
			FeelsLike = TempC
			
		# Return 'Feels Like' temperature
		return FeelsLike
						
	# CALCULATE SEA LEVEL PRESSURE FROM AMBIENT PRESSURE AND STATION ELEVATION
	# --------------------------------------------------------------------------
	def SeaLevelPressure(self,Pres):
	
		# Extract required meteorological fields
		Psta = Pres[0]
		
		# Define required constants
		P0 = 1013.25
		Rd = 287.05
		GammaS = 0.0065
		g = 9.80665
		Elev = self.System['StnElev'] + self.System['OutdoorHeight']
		T0 = 288.15
		
		# Calculate sea level pressure
		SLP = Psta * (1 + ((P0/Psta)**((Rd*GammaS)/g)) * ((GammaS*Elev)/T0))**(g/(Rd*GammaS))

		# Return Sea Level Pressure
		return [SLP,'mb','{:.1f}'.format(SLP)]		
							
	# CALCULATE THE PRESSURE TREND AND SET THE PRESSURE TREND TEXT
    # --------------------------------------------------------------------------
	def PressureTrend(self,Pres0h):
	
		# Calculate timestamp three hours past
		TimeStart = self.Air['Obs'][0] - int((3600*3+59))
		TimeEnd = self.Air['Obs'][0] - int((3600*2.9))

		# Download pressure data for last three hours
		Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
		URL = Template.format(self.System['OutdoorID'],TimeStart,TimeEnd,self.System['WFlowKey'])
		Data = requests.get(URL).json()['obs']

		# Extract pressure from three hours ago
		Pres3h = [Data[0][1],'mb']
		
		# Calculate pressure trend
		Trend = (Pres0h[0] - Pres3h[0])/3
		
		# Remove sign from pressure trend if it rounds to 0.0
		if abs(Trend) < 0.05:
			Trend = abs(Trend)
		
		# Define pressure trend text
		if Trend >= 1/3:
			TrendTxt = '[color=ff8837ff]Rising[/color]'
		elif Trend <= -1/3:
			TrendTxt = '[color=00a4b4ff]Falling[/color]'
		else:
			TrendTxt = '[color=9aba2fff]Steady[/color]'
		
		# Return pressure trend
		return [Trend,'mb/hr',TrendTxt]
		
	# CALCULATE DAILY RAIN ACCUMULATION LEVELS
    # --------------------------------------------------------------------------
	def RainAccumulation(self,Rain):
		
		# Define current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		
		# Code initialising. Download all data for current day using Weatherflow 
		# API. Calculate total daily rainfall
		if self.Sky['TodayRain'][0] == '-':
		
			# Convert midnight today in Station timezone to midnight today in  
			# UTC. Convert UTC time into UNIX timestamp
			Date = date.today()																
			Midnight = Tz.localize(datetime.combine(Date,time()))
			Midnight_UTC = int(Midnight.timestamp())
			
			# Convert current time in Station timezone to current time in  UTC. 
			# Convert current time time into UNIX timestamp
			Now = Tz.localize(datetime.now())
			Now_UTC = int(Now.timestamp())													

			# Download rainfall data for current month
			Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
			URL = Template.format(self.System['SkyID'],Midnight_UTC,Now_UTC,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Rain = [[item[3],'mm'] if item[3] != None else NaN for item in Data]

			# Calculate daily rain accumulation
			TodayRain = [sum([x for x,y in Rain]),'mm',sum([x for x,y in Rain]),Now]
			
		# Code initialising. Download all data for yesterday using Weatherflow 
		# API. Calculate total daily rainfall
		if self.Sky['YesterdayRain'][0] == '-':
		
			# Convert midnight yesterday in Station timezone to midnight 
			# yesterday in UTC. Convert UTC time into UNIX timestamp
			Date = date.today()	- timedelta(days=1)		
			Midnight = Tz.localize(datetime.combine(Date,time()))		
			Midnight_UTC = int(Midnight.timestamp())
			
			# Convert current time in Station timezone to current time in  UTC. 
			# Convert current time time into UNIX timestamp
			End_UTC = Midnight_UTC + (60*60*24)-1												

			# Download rainfall data for current month
			Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
			URL = Template.format(self.System['SkyID'],Midnight_UTC,End_UTC,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Rain = [[item[3],'mm'] if item[3] != None else NaN for item in Data]
			
			# Calculate daily rain accumulation
			YesterdayRain = [sum([x for x,y in Rain]),'mm',sum([x for x,y in Rain]),Now]

		# Code initialising. Download all data for current month using 
		# Weatherflow API. Calculate total monthly rainfall
		if self.Sky['MonthRain'][0] == '-':
		
			# Calculate timestamps for current month
			Time = datetime.utcfromtimestamp(self.Sky['Obs'][0])
			TimeStart = datetime(Time.year,Time.month,1)
			TimeStart = pytz.utc.localize(TimeStart)
			TimeStart = int(UNIX.mktime(TimeStart.timetuple()))
			TimeEnd = self.Sky['Obs'][0]

			# Download rainfall data for current month
			Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
			URL = Template.format(self.System['SkyID'],TimeStart,TimeEnd,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Rain = [[item[3],'mm'] if item[3] != None else NaN for item in Data]
			
			# Calculate monthly rain accumulation
			MonthRain = [sum([x for x,y in Rain]),'mm',sum([x for x,y in Rain]),Now]
			
		# Code initialising. Download all data for current year using 
		# Weatherflow API. Calculate total yearly rainfall
		if self.Sky['YearRain'][0] == '-':
		
			# Calculate timestamps for current year
			Time = datetime.utcfromtimestamp(self.Sky['Obs'][0])
			TimeStart = datetime(Time.year,1,1)
			TimeStart = pytz.utc.localize(TimeStart)
			TimeStart = int(UNIX.mktime(TimeStart.timetuple()))
			TimeEnd = self.Sky['Obs'][0]

			# Download rainfall data for current year
			Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
			URL = Template.format(self.System['SkyID'],TimeStart,TimeEnd,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Rain = [[item[3],'mm'] if item[3] != None else NaN for item in Data]
			
			# Calculate yearly rain accumulation
			YearRain = [sum([x for x,y in Rain]),'mm',sum([x for x,y in Rain]),Now]
			
			# Return Daily, Monthly, and Yearly rainfall accumulation totals
			return TodayRain,YesterdayRain,MonthRain,YearRain
			
		# At midnight, reset daily rainfall accumulation to zero, else add 
		# current rainfall to current daily rainfall accumulation
		if Now.date() > self.Sky['TodayRain'][3].date():
			TodayRain = [Rain[0],'mm',Rain[0],Now]
			YesterdayRain = [self.Sky['TodayRain'][2],'mm',self.Sky['TodayRain'][2],Now]
		else:
			RainAccum = self.Sky['TodayRain'][2]+Rain[0]
			TodayRain = [RainAccum,'mm',RainAccum,Now]
			YesterdayRain = [self.Sky['YesterdayRain'][2],'mm',self.Sky['YesterdayRain'][2],Now]
		
		# At end of month, reset monthly rainfall accumulation to zero, else add 
		# current rainfall to current monthly rainfall accumulation
		if Now.month > self.Sky['MonthRain'][3].month:
			MonthRain = [Rain[0],'mm',Rain[0],Now]
		else:
			RainAccum = self.Sky['MonthRain'][2]+Rain[0]
			MonthRain = [RainAccum,'mm',RainAccum,Now]	
		
		# At end of year, reset monthly and yearly rainfall accumulation to zero, 
		# else add current rainfall to current yearly rainfall accumulation
		if Now.year > self.Sky['YearRain'][3].year:
			YearRain = [Rain[0],'mm',Rain[0],Now]
			MonthRain = [Rain[0],'mm',Rain[0],Now]
		else:
			RainAccum = self.Sky['YearRain'][2]+Rain[0]
			YearRain = [RainAccum,'mm',RainAccum,Now]	
			
		# Return Daily, Monthly, and Yearly rainfall accumulation totals
		return TodayRain,YesterdayRain,MonthRain,YearRain
		
	# CALCULATE THE RAIN RATE FROM THE PREVIOUS 1 MINUTE RAIN ACCUMULATION
    # --------------------------------------------------------------------------
	def RainRate(self,RainAccum):
				
		# Calculate instantaneous rain rate from instantaneous rain accumulation
		RainRate = RainAccum[0]*60
		
		# Define rain rate text based on calculated 
		if RainRate == 0:
			RainRateTxt = 'Currently Dry'
		elif RainRate < 0.25:
			RainRateTxt = 'Very Light Rain'
		elif RainRate < 1.0:
			RainRateTxt = 'Light Rain'
		elif RainRate < 4.0:
			RainRateTxt = 'Moderate Rain'
		elif RainRate < 16.0:
			RainRateTxt = 'Heavy Rain'	
		elif RainRate < 50.0:
			RainRateTxt = 'Very Heavy Rain'
		else:
			RainRateTxt = 'Extreme Rain'
			
		# Return instantaneous rain rate and text
		return [RainRate,'mm/hr',RainRateTxt]	
		
	# CALCULATE DAILY AVERAGED WIND SPEED
	# --------------------------------------------------------------------------
	def MeanWindSpeed(self,WindSpd):
	
		# Define current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		
		# CODE INITIALISING. DOWNLOAD DATA FOR CURRENT DAY USING WEATHERFLOW API
		if self.Sky['AvgWind'] == '--':
		
			# Convert midnight today in Station timezone to midnight today in 
			# UTC. Convert UTC time into UNIX timestamp
			Date = date.today()																
			Midnight = Tz.localize(datetime.combine(Date,time()))
			Midnight_UTC = int(Midnight.timestamp())
			
			# Convert current time in Station timezone to current time in UTC. 
			# Convert current time time into UNIX timestamp
			Now = Tz.localize(datetime.now())
			Now_UTC = int(Now.timestamp())													

			# Download data from current day using Weatherflow API and extract 
			# wind speed and wind gust data
			Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
			URL = Template.format(self.System['SkyID'],Midnight_UTC,Now_UTC,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			WindSpd = [[item[5],'mps'] if item[5] != None else [NaN,'mps'] for item in Data]

			# Calculate daily averaged wind speed
			Sum = sum([x for x,y in WindSpd])
			Length = len(WindSpd)
			AvgWind = [Sum/Length,'mps',Sum/Length,Length,Now]
			
			# Return daily averaged wind speed
			return AvgWind
		
		# At midnight, reset daily averaged wind speed to zero	
		if Now.date() > self.Sky['AvgWind'][4].date():
			AvgWind = [WindSpd[0],'mps',WindSpd[0],1,Now]
		
		# Update current daily averaged wind speed with new wind speed 
		# observation
		else:
			Len = self.Sky['AvgWind'][3] + 1
			CurrentAvg = self.Sky['AvgWind'][2]
			NewAvg = (Len-1)/Len * CurrentAvg + 1/Len * WindSpd[0]
			AvgWind = [NewAvg,'mps',NewAvg,Len,Now]
		
		# Return daily averaged wind speed
		return AvgWind
		
	# CALCULATE MAXIMUM AND MINIMUM OBSERVED TEMPERATURE AND PRESSURE
	# --------------------------------------------------------------------------
	def AirObsMaxMin(self,Time,Temp,Pres):

		# Calculate sea level pressure
		SLP = self.SeaLevelPressure(Pres)
		
		# Define current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	

		# CODE INITIALISING. DOWNLOAD DATA FOR CURRENT DAY USING WEATHERFLOW API
		if self.Air['MaxTemp'] == '---':
		
			# Convert midnight today in Station timezone to midnight today in 
			# UTC. Convert UTC time into UNIX timestamp
			Date = date.today()																
			Midnight = Tz.localize(datetime.combine(Date,time()))
			Midnight_UTC = int(Midnight.timestamp())
			
			# Convert current time in Station timezone to current time in 
			# UTC. Convert current time time into UNIX timestamp
			Now = Tz.localize(datetime.now())
			Now_UTC = int(Now.timestamp())													

			# Download data from current day using Weatherflow API and extract 
			# temperature, pressure and time data
			Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
			URL = Template.format(self.System['OutdoorID'],Midnight_UTC,Now_UTC,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Time = [[item[0],'s'] if item[0] != None else NaN for item in Data]
			Temp = [[item[2],'c'] if item[2] != None else [NaN,'c'] for item in Data]
			Pres = [[item[1],'mb'] if item[1] != None else [NaN,'mb'] for item in Data]

			# Calculate sea level pressure
			SLP = [self.SeaLevelPressure(P) for P in Pres]

			# Define maximum and minimum temperature and time
			MaxTemp = [max(Temp)[0],max(Temp)[1],datetime.fromtimestamp(Time[Temp.index(max(Temp))][0],Tz).strftime('%H:%M'),max(Temp)[0],Now]
			MinTemp = [min(Temp)[0],min(Temp)[1],datetime.fromtimestamp(Time[Temp.index(min(Temp))][0],Tz).strftime('%H:%M'),min(Temp)[0],Now]

			# Define maximum and minimum pressure
			MaxPres = [max(SLP)[0],max(SLP)[1],max(SLP)[0],Now]
			MinPres = [min(SLP)[0],min(SLP)[1],min(SLP)[0],Now]
			
			# Return required variables
			return MaxTemp,MinTemp,MaxPres,MinPres
			
		# AT MIDNIGHT RESET MAXIMUM AND MINIMUM TEMPERATURE AND PRESSURE 
		if Now.date() > self.Air['MaxTemp'][4].date():
		
			# Reset maximum and minimum temperature
			MaxTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M'),Temp[0],Now]
			MinTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M'),Temp[0],Now]
			
			# Reset maximum and minimum pressure
			MaxPres = [SLP[0],'mb',SLP[0],Now]
			MinPres = [SLP[0],'mb',SLP[0],Now]
			
			# Return required variables
			return MaxTemp,MinTemp,MaxPres,MinPres
	
		# Current temperature is greater than maximum recorded temperature. 
		# Update maximum temperature and time
		if Temp[0] > self.Air['MaxTemp'][3]:
			MaxTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M'),Temp[0],Now]
			MinTemp = [self.Air['MinTemp'][3],'c',self.Air['MinTemp'][2],self.Air['MinTemp'][3],Now]

		# Current temperature is less than minimum recorded temperature. Update 
		# minimum temperature and time	
		elif Temp[0] < self.Air['MinTemp'][3]:
			MaxTemp = [self.Air['MaxTemp'][3],'c',self.Air['MaxTemp'][2],self.Air['MaxTemp'][3],Now]
			MinTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M'),Temp[0],Now]

		# Maximum and minimum temperature unchanged. Return existing values	
		else:
			MaxTemp = [self.Air['MaxTemp'][3],'c',self.Air['MaxTemp'][2],self.Air['MaxTemp'][3],Now]
			MinTemp = [self.Air['MinTemp'][3],'c',self.Air['MinTemp'][2],self.Air['MinTemp'][3],Now]
			
		# Current pressure is greater than maximum recorded pressure. Update 
		# maximum pressure
		if SLP[0] > self.Air['MaxPres'][2]:
			MaxPres = [SLP[0],'mb',SLP[0],Now]
			MinPres = [self.Air['MinPres'][2],'mb',self.Air['MinPres'][2],Now]
			
		# Current pressure is less than minimum recorded pressure. Update 
		# minimum pressure and time	
		elif SLP[0] < self.Air['MinPres'][2]:		
			MaxPres = [self.Air['MaxPres'][2],'mb',self.Air['MaxPres'][2],Now]
			MinPres = [SLP[0],'mb',SLP[0],Now]
			
		# Maximum and minimum pressure unchanged. Return existing values
		else:
			MaxPres = [self.Air['MaxPres'][2],'mb',self.Air['MaxPres'][2],Now]
			MinPres = [self.Air['MinPres'][2],'mb',self.Air['MinPres'][2],Now]
			
		# Return required variables
		return MaxTemp,MinTemp,MaxPres,MinPres	
			
	# CALCULATE MAXIMUM OBSERVED WIND SPEED AND GUST STRENGTH
	# --------------------------------------------------------------------------
	def SkyObsMaxMin(self,WindSpd,WindGust):
		
		# Define current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		
		# CODE INITIALISING. DOWNLOAD DATA FOR CURRENT DAY USING WEATHERFLOW API
		if self.Sky['MaxGust'] == '--':
		
			# Convert midnight today in Station timezone to midnight today in 
			# UTC. Convert UTC time into UNIX timestamp
			Date = date.today()																
			Midnight = Tz.localize(datetime.combine(Date,time()))
			Midnight_UTC = int(Midnight.timestamp())
			
			# Convert current time in Station timezone to current time in UTC. 
			# Convert current time time into UNIX timestamp
			Now = Tz.localize(datetime.now())
			Now_UTC = int(Now.timestamp())													

			# Download data from current day using Weatherflow API and extract 
			# wind speed and wind gust data
			Template = ('https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}')
			URL = Template.format(self.System['SkyID'],Midnight_UTC,Now_UTC,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			WindGust = [[item[6],'mps'] if item[6] != None else [NaN,'mps'] for item in Data]

			# Define maximum wind gust
			MaxGust = [max([x for x,y in WindGust]),'mps',max([x for x,y in WindGust]),Now]
			
			# Return maximum wind gust
			return MaxGust

		# AT MIDNIGHT RESET MAXIMUM RECORDED WIND GUST	
		if Now.date() > self.Sky['MaxGust'][3].date():
			MaxGust = [WindGust[0],'mps',WindGust[0],Now]
			
			# Return maximum wind gust
			return MaxGust	
			
		# Current gust speed is greater than maximum recorded gust speed. Update 
		# maximum gust speed 
		if WindGust[0] > self.Sky['MaxGust'][2]:
			MaxGust = [WindGust[0],'mps',WindGust[0],Now]	
				
		# Maximum gust speed is unchanged. Return existing value
		else:
			MaxGust = [self.Sky['MaxGust'][2],'mps',self.Sky['MaxGust'][2],Now]	
			
		# Return maximum wind speed and gust
		return MaxGust
			
	# SET THE COMFORT LEVEL TEXT STRING AND ICON
	# --------------------------------------------------------------------------
	def ComfortLevel(self,FeelsLike):		
	
		# Skip during initialisation
		if math.isnan(FeelsLike[0]):
			return ['-','-']
		
		# Define comfort level text and icon
		if FeelsLike[0] < -4:
			Description = 'Feeling extremely cold'
			Icon = 'ExtremelyCold'
		elif FeelsLike[0] < 0:
			Description = 'Feeling freezing cold'
			Icon = 'FreezingCold'
		elif FeelsLike[0] < 4:
			Description = 'Feeling very cold'
			Icon = 'VeryCold'
		elif FeelsLike[0] < 9:
			Description = 'Feeling cold'
			Icon = 'Cold'
		elif FeelsLike[0] < 14:
			Description = 'Feeling mild'
			Icon = 'Mild'
		elif FeelsLike[0] < 18:
			Description = 'Feeling warm'
			Icon = 'Warm'
		elif FeelsLike[0] < 23:
			Description = 'Feeling hot'
			Icon = 'Hot'
		elif FeelsLike[0] < 28:
			Description = 'Feeling very hot'
			Icon = 'VeryHot'
		elif FeelsLike[0] >= 28:
			Description = 'Feeling extremely hot'
			Icon = 'ExtremelyHot'
		
		# Return comfort level text string and icon
		return [Description,Icon]	

	# CALCULATE CARDINAL WIND DIRECTION FROM WIND DIRECTION IN DEGREES
	# --------------------------------------------------------------------------
	def CardinalWindDirection(self,Dir,Spd=[1,'mps']):
	
		# Define all possible cardinal wind directions and descriptions
		Direction = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW','N']
		Description = ['Due North','North NE','North East','East NE','Due East','East SE','South East','South SE',
					   'Due South','South SW','South West','West SW','Due West','West NW','North West','North NW',
					   'Due North']
	
		# Define actual cardinal wind direction and description based on current
		# wind direction in degrees
		if Spd[0] == 0:
			Direction = 'Calm'
			Description = '[color=9aba2fff]Calm[/color]'
		else:
			Ind = int(round(Dir[0]/22.5))
			Direction = Direction[Ind]
			Description = Description[Ind].split()[0] + ' [color=9aba2fff]' + Description[Ind].split()[1] + '[/color]'
					
		# Return cardinal wind direction and description
		return [Dir[0],Dir[1],Direction,Description]		
	
	# SET THE BEAUFORT SCALE WIND SPEED, DESCRIPTION, AND ICON
    # --------------------------------------------------------------------------
	def BeaufortScale(self,Wind):
	
		# Define Beaufort Scale wind speed, description, and icon
		if Wind[0] <= 0.3:
			Speed = 0.0
			Icon = '0'
			Description = 'Calm Conditions'
		elif Wind[0] <= 1.6:
			Speed = 1.0
			Icon = '1'
			Description = 'Light Air'
		elif Wind[0] <= 3.5:
			Speed = 2.0
			Icon = '2'
			Description = 'Light Breeze'
		elif Wind[0] <= 5.5:
			Speed = 3.0
			Icon = '3'
			Description = 'Gentle Breeze'
		elif Wind[0] <= 8.0:
			Speed = 4.0
			Icon = '4'
			Description = 'Moderate Breeze'
		elif Wind[0] <= 10.8:
			Speed = 5.0
			Icon = '5'
			Description = 'Fresh Breeze'
		elif Wind[0] <= 13.9:
			Speed = 6.0
			Icon = '6'
			Description = 'Strong Breeze'
		elif Wind[0] <= 17.2:
			Speed = 7.0
			Icon = '7'
			Description = 'Near Gale Force'
		elif Wind[0] <= 20.8:
			Speed = 8.0
			Icon = '8'
			Description = 'Gale Force'
		elif Wind[0] <= 24.5:
			Speed = 9.0
			Icon = '9'
			Description = 'Severe Gale Force'
		elif Wind[0] <= 28.5:
			Speed = 10.0
			Icon = '10'
			Description = 'Storm Force'
		elif Wind[0] <= 32.7:
			Speed = 11.0
			Icon = '11'
			Description = 'Violent Storm'
		else:
			Speed = 12.0
			Icon = '12'
			Description = 'Hurricane Force'
			
		# Return Beaufort Scale speed, description, and icon
		return [Icon,Description,Speed]
	
	# SET THE UV INDEX ICON
    # --------------------------------------------------------------------------
	def UVIndex(self,UV):
		
		# Set the UV index icon
		if UV[0] < 1:
			UVIcon = '0'
		elif 1 <= UV[0] < 3:
			UVIcon = '1'
		elif 3 <= UV[0] < 6:
			UVIcon = '2'
		elif 6 <= UV[0] < 8:
			UVIcon = '3'
		elif 8 <= UV[0] < 11:
			UVIcon = '4'
		else:
			UVIcon = '5'
			
		# Return UV Index icon
		return [round(UV[0],1),'index',UVIcon]
			
	# CALCULATE SUNRISE/SUNSET TIMES
	# --------------------------------------------------------------------------
	def SunriseSunset(self):
	
		# Define Sunrise/Sunset location properties
		Tz = self.System['tz']
		Ob = ephem.Observer()
		Ob.lat = str(self.System['Lat'])
		Ob.lon = str(self.System['Lon'])
		
		# The code is initialising. Calculate sunset/sunrise times for current 
		# day starting at midnight in Station timezone
		if self.SunData['Sunset'][0] == '-':
		
			# Convert midnight today in Station timezone to midnight 
			# today in UTC
			Date = date.today()
			Midnight = Tz.localize(datetime.combine(Date,time()))
			Midnight_UTC = Midnight.astimezone(pytz.utc)
			Ob.date = Midnight_UTC.strftime('%Y/%m/%d %H:%M:%S')
						
			# Sunrise time in station time zone
			Sunrise = Ob.next_rising(ephem.Sun())
			Sunrise = pytz.utc.localize(Sunrise.datetime())

			# Sunset time in station time zone
			Sunset = Ob.next_setting(ephem.Sun())
			Sunset = pytz.utc.localize(Sunset.datetime())
			
			# Define Kivy label binds
			self.SunData['Sunrise'][0] = Sunrise.astimezone(Tz)
			self.SunData['Sunset'][0] = Sunset.astimezone(Tz)
			
		# Sunset has passed. Calculate sunset/sunrise times for tomorrow 
		# starting at midnight in Station timezone
		else:
		
			# Convert midnight tomorrow in Station timezone to midnight 
			# tomorrow in UTC
			Date = date.today() + timedelta(days=1)
			Midnight = Tz.localize(datetime.combine(Date,time()))
			Midnight_UTC = Midnight.astimezone(pytz.utc)
			Ob.date = Midnight_UTC.strftime('%Y/%m/%d %H:%M:%S')
			
			# Sunrise time in station time zone
			Sunrise = Ob.next_rising(ephem.Sun())
			Sunrise = pytz.utc.localize(Sunrise.datetime())
			
			# Sunset time in station time zone
			Sunset = Ob.next_setting(ephem.Sun())
			Sunset = pytz.utc.localize(Sunset.datetime())
			
			# Define Kivy label binds
			self.SunData['Sunrise'][0] = Sunrise.astimezone(Tz)
			self.SunData['Sunset'][0] = Sunset.astimezone(Tz)
			
		# Update Kivy label binds based on date of next sunrise
		self.UpdateSunriseSunset()
		
	# CALCULATE MOONRISE/MOONSET TIMES
	# --------------------------------------------------------------------------
	def MoonriseMoonset(self):
	
		# Define Moonrise/Moonset location properties
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		Ob = ephem.Observer()
		Ob.lat = str(self.System['Lat'])
		Ob.lon = str(self.System['Lon'])
		
		# The code is initialising. Calculate moonrise time for current day 
		# starting at midnight in station time zone
		if self.MoonData['Moonrise'][0] == '-':
		
			# Convert midnight in Station timezone to midnight in UTC
			Date = date.today()
			Midnight = Tz.localize(datetime.combine(Date,time()))
			Midnight_UTC = Midnight.astimezone(pytz.utc)
			Ob.date = Midnight_UTC.strftime('%Y/%m/%d %H:%M:%S')
			
			# Calculate Moonrise time in Station time zone
			Moonrise = Ob.next_rising(ephem.Moon())
			Moonrise = pytz.utc.localize(Moonrise.datetime())
			self.MoonData['Moonrise'][0] = Moonrise.astimezone(Tz)
						
		# Moonset has passed. Calculate time of next moonrise in station 
		# timezone
		else:
		
			# Convert moonset time in Station timezone to moonset time in UTC
			Moonset = self.MoonData['Moonset'][0].astimezone(pytz.utc)
			Ob.date = Moonset.strftime('%Y/%m/%d %H:%M:%S')
			
			# Calculate Moonrise time in Station time zone
			Moonrise = Ob.next_rising(ephem.Moon())
			Moonrise = pytz.utc.localize(Moonrise.datetime())
			self.MoonData['Moonrise'][0] = Moonrise.astimezone(Tz)			
			
		# Convert Moonrise time in Station timezone to Moonrise time in UTC
		Moonrise = self.MoonData['Moonrise'][0].astimezone(pytz.utc)
		Ob.date = Moonrise.strftime('%Y/%m/%d %H:%M:%S')
		
		# Calculate time of next Moonset in station timezone based on current 
		# Moonrise time in UTC
		Moonset = Ob.next_setting(ephem.Moon())
		Moonset = pytz.utc.localize(Moonset.datetime())
		self.MoonData['Moonset'][0] = Moonset.astimezone(Tz)
			
		# Calculate date of next full moon in UTC
		Ob.date = Now.strftime('%Y/%m/%d')
		FullMoon = ephem.next_full_moon(Ob.date)
		FullMoon = pytz.utc.localize(FullMoon.datetime())
		
		# Calculate date of next new moon in UTC
		NewMoon = ephem.next_new_moon(Ob.date)
		NewMoon = pytz.utc.localize(NewMoon.datetime())
		
		# Define Kivy label binds for next new/full moon in station time zone
		self.MoonData['FullMoon'] = [FullMoon.astimezone(Tz).strftime('%b %d'),FullMoon] 
		self.MoonData['NewMoon'] = [NewMoon.astimezone(Tz).strftime('%b %d'),NewMoon] 
		
		# Update Kivy label binds based on date of next moonrise
		self.UpdateMoonriseMoonset()	
		
	# UPDATE SUNSET AND SUNRISE KIVY LABEL BINDS BASED ON DATE OF NEXT SUNRISE
	# --------------------------------------------------------------------------
	def UpdateSunriseSunset(self):
		if datetime.now(self.System['tz']).date() == self.SunData['Sunrise'][0].date():
			self.SunData['Sunrise'][1] = self.SunData['Sunrise'][0].strftime('%H:%M')
			self.SunData['Sunset'][1] = self.SunData['Sunset'][0].strftime('%H:%M')
		else:
			self.SunData['Sunrise'][1] = self.SunData['Sunrise'][0].strftime('%H:%M') + ' (+1)'
			self.SunData['Sunset'][1] = self.SunData['Sunset'][0].strftime('%H:%M') + ' (+1)'
			
	# UPDATE MOONRISE AND MOONSET KIVY LABEL BINDS BASED ON DATE OF NEXT 
	# MOONRISE
	# --------------------------------------------------------------------------
	def UpdateMoonriseMoonset(self):
	
		# Get current time in station time zone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		
		# Update Moonrise Kivy Label bind based on date of next moonrise
		if datetime.now(self.System['tz']).date() == self.MoonData['Moonrise'][0].date():
			self.MoonData['Moonrise'][1] = self.MoonData['Moonrise'][0].strftime('%H:%M')
		elif datetime.now(self.System['tz']).date() < self.MoonData['Moonrise'][0].date():
			self.MoonData['Moonrise'][1] = self.MoonData['Moonrise'][0].strftime('%H:%M') + ' (+1)'
		else:
			self.MoonData['Moonrise'][1] = self.MoonData['Moonrise'][0].strftime('%H:%M') + ' (-1)'
			
		# Update Moonset Kivy Label bind based on date of next moonset
		if datetime.now(self.System['tz']).date() == self.MoonData['Moonset'][0].date():
			self.MoonData['Moonset'][1] = self.MoonData['Moonset'][0].strftime('%H:%M')
		elif datetime.now(self.System['tz']).date() < self.MoonData['Moonset'][0].date():
			self.MoonData['Moonset'][1] = self.MoonData['Moonset'][0].strftime('%H:%M') + ' (+1)'
		else:
			self.MoonData['Moonset'][1] = self.MoonData['Moonset'][0].strftime('%H:%M') + ' (-1)'	
			
		# Update New Moon Kivy Label bind based on date of next new moon
		if self.MoonData['FullMoon'][1].date() == Now.date():
			self.MoonData['FullMoon'] = ['[color=ff8837ff]Today[/color]',self.MoonData['FullMoon'][1]]  
		
		# Update Full Moon Kivy Label bind based on date of next full moon
		elif self.MoonData['NewMoon'][1].date() == Now.date():
			self.MoonData['NewMoon'] = ['[color=ff8837ff]Today[/color]',self.MoonData['NewMoon'][1]] 		
			
	# CALCULATE THE SUN TRANSIT ANGLE AND THE TIME UNTIL SUNRISE OR SUNSET
	# --------------------------------------------------------------------------
	def SunTransit(self,dt):
	
		# If time is between sunrise and sun set, calculate sun
		# transit angle
		if (datetime.now(self.System['tz']) >= self.SunData['Sunrise'][0] and 
		    datetime.now(self.System['tz']) <= self.SunData['Sunset'][0]):
			
			# Determine total length of daylight, amount of daylight
			# that has passed, and amount of daylight left
			DaylightTotal = self.SunData['Sunset'][0] - self.SunData['Sunrise'][0]
			DaylightLapsed = datetime.now(self.System['tz']) - self.SunData['Sunrise'][0]
			DaylightLeft = self.SunData['Sunset'][0] - datetime.now(self.System['tz'])
			
			# Determine sun transit angle
			Angle = DaylightLapsed.total_seconds() / DaylightTotal.total_seconds() * 180
			Angle = int(Angle*10)/10.0
			
			# Determine hours and minutes left until sunset
			hours,remainder = divmod(DaylightLeft.total_seconds(), 3600)
			minutes,seconds = divmod(remainder,60)
			
			# Define Kivy Label binds
			self.SunData['SunAngle'] = '{:.1f}'.format(Angle)
			self.SunData['Event'] = ['Till [color=f05e40ff]Sunset[/color]','{:02.0f}'.format(hours),'{:02.0f}'.format(minutes)]

		# When not daylight, set sun transit angle to building
		# value. Define time until sunrise
		elif datetime.now(self.System['tz']) <= self.SunData['Sunrise'][0]:
		
			# Determine hours and minutes left until sunrise
			NightLeft = self.SunData['Sunrise'][0] - datetime.now(self.System['tz'])
			hours,remainder = divmod(NightLeft.total_seconds(), 3600)
			minutes,seconds = divmod(remainder,60)
			
			# Define Kivy Label binds
			self.SunData['SunAngle'] = '-'
			self.SunData['Event'] = ['Till [color=f0b240ff]Sunrise[/color]','{:02.0f}'.format(hours),'{:02.0f}'.format(minutes)]	

	# CALCULATE THE PHASE OF THE MOON
	# --------------------------------------------------------------------------
	def MoonPhase(self,dt):	
	
		# Define current time and date in UTC and station timezone
		Tz = self.System['tz']
		UTC = datetime.now(pytz.utc)
		Now = UTC.astimezone(Tz)	
		
		# Define moon phase location properties
		Ob = ephem.Observer()
		Ob.lat = str(self.System['Lat'])
		Ob.lon = str(self.System['Lon'])
		
		# Calculate date of next full moon in station time zone
		Ob.date = Now.strftime('%Y/%m/%d')
		FullMoon = ephem.next_full_moon(Ob.date)
		FullMoon = pytz.utc.localize(FullMoon.datetime())
		FullMoon = FullMoon.astimezone(self.System['tz'])
		
		# Calculate date of next new moon in station time zone
		NewMoon = ephem.next_new_moon(Ob.date)
		NewMoon = pytz.utc.localize(NewMoon.datetime())
		NewMoon = NewMoon.astimezone(self.System['tz'])
		
		# Calculate phase of moon
		Moon = ephem.Moon()
		Moon.compute(UTC.strftime('%Y/%m/%d %H:%M:%S'))
		
		# Define Moon phase icon
		if FullMoon < NewMoon:
			PhaseIcon = 'Waxing_' + '{:.0f}'.format(Moon.phase)
		elif NewMoon < FullMoon:
			PhaseIcon = 'Waning_' + '{:.0f}'.format(Moon.phase)
			
		# Define Moon phase text
		if self.MoonData['NewMoon'] == '[color=ff8837ff]Today[/color]':
			PhaseTxt = 'New Moon'
		elif self.MoonData['FullMoon'] == '[color=ff8837ff]Today[/color]':
			PhaseTxt = 'Full Moon'	
		elif FullMoon < NewMoon and Moon.phase < 49:
			PhaseTxt = 'Waxing crescent'
		elif FullMoon < NewMoon and 49 <= Moon.phase <= 51:
			PhaseTxt = 'First Quarter'
		elif FullMoon < NewMoon and Moon.phase > 51:
			PhaseTxt = 'Waxing gibbous'
		elif NewMoon < FullMoon and Moon.phase > 51:
			PhaseTxt = 'Waning gibbous'
		elif NewMoon < FullMoon and 49 <= Moon.phase <= 51:
			PhaseTxt = 'Last Quarter'
		elif NewMoon < FullMoon and Moon.phase < 49:
			PhaseTxt = 'Waning crescent'	
		
		# Define Moon phase illumination
		Illumination = '{:.0f}'.format(Moon.phase)	

		# Define Kivy Label binds
		self.MoonData['Phase'] = [PhaseIcon,PhaseTxt,Illumination]	
			
	# DOWNLOAD THE LATEST FORECAST FOR STATION LOCATION
	# --------------------------------------------------------------------------
	def DownloadForecast(self):
	
		# If Station is located in Great Britain, download latest 
		# MetOffice three-hourly forecast
		if self.System['Country'] == 'GB':
			Template = 'http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/json/{}?res=3hourly&key={}'
			URL = Template.format(self.System['MetOfficeID'],self.System['MetOfficeKey'])    
			self.MetDict = requests.get(URL).json()
			self.ExtractMetOfficeForecast()
			
		# If station is located outside of Great Britain, download the latest 
		# DarkSky hourly forecast
		else:
			Template = 'https://api.darksky.net/forecast/{}/{},{}?exclude=currently,minutely,alerts,flags&units=uk2'
			URL = Template.format(self.System['DarkSkyKey'],self.System['Lat'],self.System['Lon'])    
			self.MetDict = requests.get(URL).json()
			self.ExtractDarkSkyForecast()			
		
	# EXTRACT THE LATEST THREE-HOURLY METOFFICE FORECAST FOR THE STATION 
	# LOCATION
	# --------------------------------------------------------------------------
	def ExtractMetOfficeForecast(self):
	
		# Extract all forecast data from DarkSky JSON file. If  forecast is 
		# unavailable, set forecast variables to blank and indicate to user that 
		# forecast is unavailable
		Tz = self.System['tz']
		try:
			MetData = (self.MetDict['SiteRep']['DV']['Location']['Period'])
		except KeyError:
			self.MetData['Time'] = datetime.now(pytz.utc).astimezone(Tz)	
			self.MetData['Temp'] = '--'
			self.MetData['WindDir'] = '--'
			self.MetData['WindSpd'] = '--'
			self.MetData['Weather'] = 'ForecastUnavailable'
			self.MetData['Precip'] = '--'
			self.MetData['Issued'] = '--'
			self.MetData['Valid'] = '--'
			
			# Attempt to download forecast again in 1 minute
			Clock.schedule_once(lambda dt: self.DownloadForecast(),600)
			return
		
		# Extract issue time of forecast data
		Issued = str(self.MetDict['SiteRep']['DV']['dataDate'][11:-4])
		
		# Extract date of all available forecasts, and retrieve forecast for 
		# today
		Dates = list(item['value'] for item in MetData)
		MetData = MetData[Dates.index(datetime.now(self.System['tz']).strftime('%Y-%m-%dZ'))]['Rep']
		
		# Extract 'valid from' time of all available three-hourly forecasts, and 
		# retrieve forecast for the current three-hour period
		Times = list(int(item['$'])//60 for item in MetData)
		MetData = MetData[bisect.bisect(Times,datetime.now().hour)-1]
		
		# Extract 'valid until' time for the retrieved forecast
		Valid = Times[bisect.bisect(Times,datetime.now(self.System['tz']).hour)-1] + 3
		if Valid == 24:
			Valid = 0
			
		# Extract weather variables from MetOffice forecast
		Temp = [float(MetData['T']),'c']
		WindSpd = [float(MetData['S'])/2.2369362920544,'mps']
		WindDir = [MetData['D'],'cardinal']
		Precip = [MetData['Pp'],'%']	
		Weather = MetData['W']	
		
		# Convert forecast units as required
		Temp = self.ObservationUnits(Temp,self.System['Units']['Temp'])
		WindSpd = self.ObservationUnits(WindSpd,self.System['Units']['Wind'])
		
		# Define and format Kivy label binds
		self.MetData['Time'] = datetime.now(pytz.utc).astimezone(Tz)	
		self.MetData['Issued'] = Issued
		self.MetData['Valid'] = '{:02.0f}'.format(Valid) + ':00'	
		self.MetData['Temp'] = ['{:.1f}'.format(Temp[0]),Temp[1]]
		self.MetData['WindDir'] = WindDir[0]
		self.MetData['WindSpd'] = ['{:.0f}'.format(WindSpd[0]),WindSpd[1]]
		self.MetData['Weather'] = Weather
		self.MetData['Precip'] = Precip[0]

	# EXTRACT THE LATEST HOURLY DARK SKY FORECAST FOR THE STATION LOCATION
	# --------------------------------------------------------------------------
	def ExtractDarkSkyForecast(self):
		
		# Extract all forecast data from DarkSky JSON file. If  forecast is 
		# unavailable, set forecast variables to blank and indicate to user that 
		# forecast is unavailable
		Tz = self.System['tz']
		try:
			MetData = (self.MetDict['hourly']['data'])
		except KeyError:
			self.MetData['Time'] = datetime.now(pytz.utc).astimezone(Tz)	
			self.MetData['Temp'] = '--'
			self.MetData['WindDir'] = '--'
			self.MetData['WindSpd'] = '--'
			self.MetData['Weather'] = 'ForecastUnavailable'
			self.MetData['Precip'] = '--'
			self.MetData['Issued'] = '--'
			self.MetData['Valid'] = '--'
			
			# Attempt to download forecast again in 1 minute
			Clock.schedule_once(lambda dt: self.DownloadForecast(),600)
			return
		
		# Extract 'valid from' time of all available hourly forecasts, and 
		# retrieve forecast for the current hourly period
		Times = list(item['time'] for item in MetData)
		MetData = MetData[bisect.bisect(Times,int(UNIX.time()))-1]
		
		# Extract 'Issued' and 'Valid' times
		Issued = Times[0]
		Valid = Times[bisect.bisect(Times,int(UNIX.time()))]
		Issued = datetime.fromtimestamp(Issued,pytz.utc).astimezone(self.System['tz'])
		Valid = datetime.fromtimestamp(Valid,pytz.utc).astimezone(self.System['tz'])
		
		# Extract weather variables from DarkSky forecast
		Temp = [MetData['temperature'],'c']
		WindSpd = [MetData['windSpeed']/2.2369362920544,'mps']
		WindDir = [MetData['windBearing'],'degrees']
		Precip = [MetData['precipProbability']*100,'%']
		Weather = MetData['icon']	
		
		# Convert forecast units as required
		Temp = self.ObservationUnits(Temp,self.System['Units']['Temp'])
		WindSpd = self.ObservationUnits(WindSpd,self.System['Units']['Wind'])

		# Define and format Kivy label binds
		self.MetData['Time'] = datetime.now(pytz.utc).astimezone(Tz)
		self.MetData['Issued'] = datetime.strftime(Issued,'%H:%M')
		self.MetData['Valid'] = datetime.strftime(Valid,'%H:%M')
		self.MetData['Temp'] = ['{:.1f}'.format(Temp[0]),Temp[1]]
		self.MetData['WindDir'] = self.CardinalWindDirection(WindDir)[2]
		self.MetData['WindSpd'] = ['{:.0f}'.format(WindSpd[0]),WindSpd[1]]
		self.MetData['Precip'] = '{:.0f}'.format(Precip[0])
		
		# Define weather icon
		if Weather == 'clear-day':
			self.MetData['Weather'] = '1'
		elif Weather == 'clear-night':
			self.MetData['Weather'] = '0'
		elif Weather == 'rain':
			self.MetData['Weather'] = '12'
		elif Weather == 'snow':
			self.MetData['Weather'] = '27'
		elif Weather == 'sleet':
			self.MetData['Weather'] = '18'
		elif Weather == 'wind':
			self.MetData['Weather'] = 'wind'
		elif Weather == 'fog':
			self.MetData['Weather'] = '6'
		elif Weather == 'cloudy':
			self.MetData['Weather'] = '7'
		elif Weather == 'partly-cloudy-day':
			self.MetData['Weather'] = '3'
		elif Weather == 'partly-cloudy-night': 
			self.MetData['Weather'] = '2'
		else:
			self.MetData['Weather'] = 'ForecastUnavailable'

	# CALCULATE SAGER WEATHERCASTER FORECAST USING OBSERVED WEATHER TREND OVER 
	# THE PREVIOUS SIX HOURS
	# --------------------------------------------------------------------------
	def SagerForecast(self,dt):
		
		# Get current UNIX timestamp in UTC
		Now = int(UNIX.time())
		Hours_6 = (6*60*60)+60
			
		# Download Sky data from last 6 hours using Weatherflow API 
		# and extract observation times, wind speed, wind direction, 
		# and rainfall
		Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
		URL = Template.format(self.System['SkyID'],Now-Hours_6,Now,self.System['WFlowKey'])
		Sky = {}
		Sky['obs'] = requests.get(URL).json()['obs']
		Sky['Time'] = [item[0] if item[0] != None else NaN for item in Sky['obs']]
		Sky['WindSpd'] = [item[5]*2.23694 if item[5] != None else NaN for item in Sky['obs']]
		Sky['WindDir'] = [item[7] if item[7] != None else NaN for item in Sky['obs']]
		Sky['Rain'] = [item[3] if item[3] != None else NaN for item in Sky['obs']]
		
		# Convert data lists to Numpy arrays
		Sky['Time'] = np.array(Sky['Time'],dtype=np.int64)
		Sky['WindSpd'] = np.array(Sky['WindSpd'],dtype=np.float64)
		Sky['WindDir'] = np.array(Sky['WindDir'],dtype=np.float64)
		Sky['Rain'] = np.array(Sky['Rain'],dtype=np.float64)
		
		# Download AIR data from current day using Weatherflow API 
		# and extract observation times, pressure and temperature
		Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
		URL = Template.format(self.System['OutdoorID'],Now-Hours_6,Now,self.System['WFlowKey'])
		Air = {}
		Air['obs'] = requests.get(URL).json()['obs']
		Air['Time'] = [item[0] if item[0] != None else NaN for item in Air['obs']]
		Air['Pres'] = [item[1] if item[1] != None else NaN for item in Air['obs']]
		Air['Temp'] = [item[2] if item[2] != None else NaN for item in Air['obs']]
		
		# Convert data lists to Numpy arrays
		Air['Time'] = np.array(Air['Time'],dtype=np.int64)
		Air['Pres'] = np.array(Air['Pres'],dtype=np.float64)
		Air['Temp'] = np.array(Air['Temp'],dtype=np.float64)
				
		# Define required station variables for the Sager 
		# Weathercaster Forecast
		self.Sager['Lat'] = self.System['Lat']
		
		# Define required wind direction variables for the Sager 
		# Weathercaster Forecast
		self.Sager['WindDir6'] = CircularMean(Sky['WindDir'][:15])
		self.Sager['WindDir'] = CircularMean(Sky['WindDir'][-15:])

		# Define required wind speed variables for the Sager 
		# Weathercaster Forecast
		self.Sager['WindSpd6'] = np.nanmean(Sky['WindSpd'][:15])
		self.Sager['WindSpd'] = np.nanmean(Sky['WindSpd'][-15:])

		# Define required pressure variables for the Sager 
		# Weathercaster Forecast
		self.Sager['Pres'] = np.nanmean(Air['Pres'][-15:])
		self.Sager['Pres6'] = np.nanmean(Air['Pres'][:15])
		
		# Define required present weather variables for the Sager 
		# Weathercaster Forecast
		LastRain = np.where(Sky['Rain'] > 0)[0]
		if LastRain.size == 0:
			self.Sager['LastRain'] = math.inf
		else:
			LastRain = Sky['Time'][LastRain.max()]
			LastRain = datetime.fromtimestamp(LastRain,self.System['tz'])
			LastRain = datetime.now(self.System['tz']) - LastRain
			self.Sager['LastRain'] = LastRain.total_seconds()/60

		# Define required temperature variables for the Sager 
		# Weathercaster Forecast
		self.Sager['Temp'] = np.nanmean(Air['Temp'][-15:])
		
		# Download closet METAR information to station location
		header = {'X-API-Key':self.System['CheckWXKey']}
		Template = 'https://api.checkwx.com/metar/lat/{}/lon/{}/decoded'
		URL = Template.format(self.System['Lat'],self.System['Lon'])
		Data = requests.get(URL,headers=header)
		if VerifyJSON(Data) and 'data' in Data.json():
			self.Sager['METAR'] = Data.json()['data'][0]
		else:
			return

		# Calculate Sager Weathercaster Forecast
		self.Sager['Dial'] = sager.DialSetting(self.Sager)
		self.Sager['Forecast'] = sager.Forecast(self.Sager['Dial'])
		self.Sager['Issued'] = datetime.now(self.System['tz']).strftime('%H:%M')
		
		# Determine time until generation of next Sager Weathercaster forecast
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		if Now.hour < 6:
			Date = Now.date()
			Time = time(6,0,0) 
			Forecast = Tz.localize(datetime.combine(Date,Time))
		elif Now.hour < 18:
			Date = Now.date()
			Time = time(18,0,0) 
			Forecast = Tz.localize(datetime.combine(Date,Time))
		else:
			Date = Now.date() + timedelta(days=1)
			Time = time(6,0,0)
			Forecast = Tz.localize(datetime.combine(Date,Time))
			
		# Schedule generation of next Sager Weathercaster forecast
		Seconds = (Forecast - Now).total_seconds()
		Clock.schedule_once(self.SagerForecast,Seconds)
			
	# CHECK STATUS OF SKY AND AIR MODULES
	# --------------------------------------------------------------------------	
	def SkyAirStatus(self,dt):
	
		# Check latest AIR observation time is less than 5 minutes old
		if 'Obs' in self.Air:
			AirTime = datetime.fromtimestamp(self.Air['Obs'][0],self.System['tz'])
			AirDiff = (datetime.now(self.System['tz']) - AirTime).total_seconds()
			if AirDiff < 300:
				self.Air['StatusIcon'] = 'OK'
			
			# Latest AIR observation time is greater than 5 minutes old
			else:
				self.Air['StatusIcon'] = 'Error'
			
		# Check latest Sky observation time is less than 5 minutes old
		if 'Obs' in self.Sky:
			SkyTime = datetime.fromtimestamp(self.Sky['Obs'][0],self.System['tz'])
			SkyDiff = (datetime.now(self.System['tz']) - SkyTime).total_seconds()
			if SkyDiff < 300:
				self.Sky['StatusIcon'] = 'OK'
				
			# Latest Sky observation time is greater than 5 minutes old	
			else:
				self.Sky['StatusIcon'] = 'Error'
	
	# UPDATE 'WeatherFlowPiConsole' METHODS AT REQUIRED INTERVALS
	# --------------------------------------------------------------------------
	def UpdateMethods(self,dt):
	
		# Get current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		Now = Now.replace(microsecond=0)
			
		# At 5 minutes past each hour, download a new forecast for the Station 
		# location
		if (Now.minute,Now.second) == (5,0):
			self.DownloadForecast()
			
		# At the top of each hour update the on-screen forecast for the Station 
		# location
		if Now.hour > self.MetData['Time'].hour or Now.date() > self.MetData['Time'].date():
			if self.System['Country'] == 'GB':
				self.ExtractMetOfficeForecast()
			else:
				self.ExtractDarkSkyForecast()
			self.MetData['Time'] = Now

		# Once sunset has passed, calculate new sunrise/sunset times
		if Now > self.SunData['Sunset'][0]:
			self.SunriseSunset()
			
		# Once moonset has passed, calculate new moonrise/moonset times
		if Now > self.MoonData['Moonset'][0]:
			self.MoonriseMoonset()	

		# At midnight, update Sunset, Sunrise, Moonrise and Moonset Kivy Labels
		if Now.time() == time(0,0,0):
			self.UpdateSunriseSunset()
			self.UpdateMoonriseMoonset()
	
	# CHECK CURRENT VERSION OF CODE AGAINST LATEST AVAILABLE VERSION
	# --------------------------------------------------------------------------
	def CheckVersion(self,dt):

		# Get latest verion tag from Github API
		header = {'Accept': 'application/vnd.github.v3+json'}
		Template = 'https://api.github.com/repos/{}/{}/releases/latest'
		URL = Template.format('peted-davis','WeatherFlow_PiConsole')
		Data = requests.get(URL,headers=header).json()
		self.System['LatestVer'] = Data['tag_name']

		# If current version and latest version do not match, open update 
		# notification
		if version.parse(self.System['Version']) < version.parse(self.System['LatestVer']):
			
			# Check if update notification is already open. Close if required
			if 'UpdateNotif' in self.System:
				self.System['UpdateNotif'].dismiss()
		
			# Open update notification
			self.System['UpdateNotif'] = Version()
			self.System['UpdateNotif'].open()

		# Schedule next Version Check
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)
		Next = Tz.localize(datetime.combine(date.today()+timedelta(days=1),time(0,0,0)))
		Clock.schedule_once(self.CheckVersion,(Next - Now).total_seconds())
		
# ==============================================================================
# DEFINE 'CurrentConditions' SCREEN 
# ==============================================================================
class CurrentConditions(Screen):

	# Define Kivy properties required by 'CurrentConditions' 
	Screen = DictProperty([('Clock','--'),('SunMoon','Sun'),
						   ('MetSager','Met'),
						   ('xRainAnim',471),('yRainAnim',11)])
					
	# INITIALISE 'CurrentConditions' CLASS
	# --------------------------------------------------------------------------
	def __init__(self,**kwargs):
		super(CurrentConditions,self).__init__(**kwargs)
		Clock.schedule_interval(self.Clock,1.0)
		Clock.schedule_interval(self.RainRateAnimation,1/10)		
	
	# DEFINE DATE AND TIME FOR CLOCK IN STATION TIMEZONE
	# --------------------------------------------------------------------------
	def Clock(self,dt):
		Tz = App.get_running_app().System['tz']
		self.Screen['Clock'] = datetime.now(pytz.utc).astimezone(Tz).strftime('%a, %d %b %Y\n%H:%M:%S')
		
	# ANIMATE RAIN RATE ICON
	# --------------------------------------------------------------------------
	def RainRateAnimation(self,dt):
	
		# Calculate current rain rate
		if 'Obs' in App.get_running_app().Sky:
			RainRate = App.get_running_app().Sky['Obs'][3] * 60
		else:
			return	
			
		# Define required animation variables
		x0 = 11
		xt = 124
		t = 50
			
		# Calculate rain rate animation y position	
		if RainRate == 0:
			self.Screen['yRainAnim'] = x0				
		elif RainRate < 50.0:
			A = (xt-x0)/t**0.5 * RainRate**0.5 + x0
			B = (xt-x0)/t**0.3 * RainRate**0.3 + x0
			C = (1 + np.tanh(RainRate-3))/2
			self.Screen['yRainAnim'] = np.asscalar(A + C * (B-A))
		else:
			self.Screen['yRainAnim'] = xt				

		# Rain rate animation x position
		if self.Screen['xRainAnim']-1 == 240:
			self.Screen['xRainAnim'] = 471
		else:
			self.Screen['xRainAnim'] -= 1	

	# SWITCH BETWEEN PANELS BASED ON USER INPUT
	# --------------------------------------------------------------------------
	def SwitchPanel(self,Instance,Panel):

		# Switch between Sunrise/Sunset and Moonrise/Moonset panels
		if Panel == 'SunMoon':
			if self.Screen['SunMoon'] == 'Sun':
				self.ids.Sunrise.opacity = 0
				self.ids.Moon.opacity = 1
				self.Screen['SunMoon'] = 'Moon'
			else:
				self.ids.Sunrise.opacity = 1
				self.ids.Moon.opacity = 0
				self.Screen['SunMoon'] = 'Sun'
	
		# Switch between MetOffice and Sager Forecast panels
		elif Panel == 'MetSager':
			if self.Screen['MetSager'] == 'Met':
				self.ids.MetOffice.opacity = 0
				self.ids.Sager.opacity = 1
				self.Screen['MetSager'] = 'Sager'
			else:
				self.ids.MetOffice.opacity = 1
				self.ids.Sager.opacity = 0
				self.Screen['MetSager'] = 'Met'

# ==============================================================================
# DEFINE CREDITS POPUP
# ==============================================================================	
class Credits(Popup):
	pass

# ==============================================================================
# DEFINE VERSION POPUP
# ==============================================================================
class Version(Popup):
	pass	


class SettingScrollOptions(SettingOptions):

	def _create_popup(self, instance):
		
		#global oORCA
		# create the popup

		content         = GridLayout(cols=1, spacing='5dp')
		scrollview      = ScrollView(do_scroll_x=False)
		scrollcontent   = GridLayout(cols=1,  spacing='5dp', size_hint=(1, None))
		#scrollcontent.bind(minimum_height=scrollcontent.setter('height'))
		self.modalview  = ModalView(size_hint=(0.5, 0.5), auto_dismiss=False, padding=[0,0])
		self.modalview.add_widget(content)
		
		
		#we need to open the popup first to get the metrics 
		self.modalview.open()
		#Add some space on top
		#content.add_widget(Widget(size_hint_y=None, height=dp(2)))
		# add all the options
		#uid = str(self.uid)
		#for option in self.options:
		#	state = 'down' if option == self.value else 'normal'
		#	btn = ToggleButton(text=option, state=state, group=uid, size_hint=(None,None), width=self.modalview.width,  height=dp(50))
		#	btn.bind(on_release=self._set_option)
		#	scrollcontent.add_widget(btn)

		# finally, add a cancel button to return on the previous panel
		scrollview.add_widget(scrollcontent)
		content.add_widget(scrollview)
		content.add_widget(SettingSpacer())
		btn = Button(text='Cancel', size=(self.modalview.width, dp(50)),size_hint=(0.9, None))
		btn.bind(on_release=self.modalview.dismiss)
		content.add_widget(btn)		
		#print(scrollcontent.height)
		
# ==============================================================================
# RUN APP
# ==============================================================================
if __name__ == '__main__':
	log.startLogging(sys.stdout)
	wfpiconsole().run()
