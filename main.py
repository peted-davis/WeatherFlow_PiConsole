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
# INITIALISE KIVY BACKEND
# ==============================================================================
import platform
import os
if platform.system() == 'Linux':
	os.environ['KIVY_GL_BACKEND'] = 'gl'
elif platform.system() == 'Windows':
	os.environ['KIVY_GL_BACKEND'] = 'glew'

# ==============================================================================
# INITIALISE KIVY TWISTED WEBSOCKET CLIENT
# ==============================================================================
from kivy.support import install_twisted_reactor
install_twisted_reactor()

from twisted.python import log
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.policies import TimeoutMixin
from autobahn.twisted.websocket import WebSocketClientProtocol, \
                                       WebSocketClientFactory

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
# Import required modules
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
from twisted.internet import reactor,ssl
from datetime import datetime,date,time,timedelta
from geopy import distance as geopy
import time as UNIX
import numpy as np
import Sager
import pytz
import math
import bisect
import json
import requests
import ephem
import configparser
import sys

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

# ==============================================================================
# DEFINE 'WeatherFlowPiConsole' APP CLASS
# ==============================================================================
class WeatherFlowPiConsole(App):
	
	# Define Kivy properties required for display in 'WeatherFlowPiConsole.kv' 
	System = DictProperty([('ForecastLocn','--'),('Units',{}),('Barometer','--')])
	MetData = DictProperty([('Temp','--'),('Precip','--'),('WindSpd','--'),
							('WindDir','--'),('Weather','Building'),
	                        ('Valid','--'),('Issued','--')])
	Sager = DictProperty([('Lat','--'),('MetarKey','--'),('WindDir6','--'),
	                      ('WindDir','--'),('WindSpd6','--'),('WindSpd','--'),
						  ('Pres','--'),('Pres6','--'),('LastRain','--'),
						  ('Temp','--'),('Dial','--'),('Forecast','--'),
						  ('Issued','--')])									 
	SkyRapid = DictProperty([('Time','-'),('Speed','--'),('Direc','---')])	
	SkyRapidIcon = NumericProperty(0)							 
	Sky = DictProperty([('Radiation','----'),('RainRate','---'),('WindSpd','----'),
						('WindGust','--'),('WindDir','---'),('MaxWind','--'),
						('MaxGust','--'),('DayRain','--'),('MonthRain','--'),
						('YearRain','--'),('Time','-'),('Battery','--'),
						('StatusIcon','Error'),('Obs','--')])
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
	
		# Initiate class and force window size if required
		super(WeatherFlowPiConsole,self).__init__(**kwargs)
		
		# Force window size if required
		if 'arm' not in platform.machine():
			Window.size = (800,480)
	
		# Parse variables from WeatherPi configuration file
		config = configparser.ConfigParser()
		config.read('WeatherFlowPiConsole.ini')
		
		# Assign configuration variables to Kivy properties
		self.System['WFlowKey'] = config['System']['WFlowKey']
		self.System['Version'] = config['System']['Version']
		self.System['GeoNamesKey'] = config['User']['GeoNamesKey']
		self.System['MetOfficeKey'] = config['User']['MetOfficeKey']
		self.System['DarkSkyKey'] = config['User']['DarkSkyKey']
		self.System['CheckWXKey'] = config['User']['CheckWXKey']
		self.System['StationID'] = config['User']['StationID']
		self.System['AirName'] = config['User']['AirName']
		self.System['SkyName'] = config['User']['SkyName']

		# Determine Sky and AIR IDs and extract height above ground
		Template = 'https://swd.weatherflow.com/swd/rest/stations/{}?api_key={}'
		URL = Template.format(self.System['StationID'],self.System['WFlowKey'])
		Data = requests.get(URL).json()
		Devices = Data['stations'][0]['devices']
		for Dev in Devices:
			if 'device_type' in Dev:
				Type = Dev['device_type']
				if Type == 'AR' and not 'AirID' in self.System:
					Name = Dev['device_meta']['name']
					if Name == self.System['AirName'] or not self.System['AirName']:
						self.System['AirID'] = str(Dev['device_id'])
						self.System['AirHeight'] = Dev['device_meta']['agl']
				elif Type == 'SK' and not 'SkyID' in self.System:
					Name = Dev['device_meta']['name']
					if Name == self.System['SkyName'] or not self.System['SkyName']:
						self.System['SkyID'] = str(Dev['device_id'])
						self.System['SkyHeight'] = Dev['device_meta']['agl']
					
		# Determine Station latitude/longitude, elevation, and timezone
		self.System['Lat'] = Data['stations'][0]['latitude']
		self.System['Lon'] = Data['stations'][0]['longitude']
		self.System['tz'] = pytz.timezone(Data['stations'][0]['timezone'])
		self.System['StnElev'] = Data['stations'][0]['station_meta']['elevation']
		
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
		
		# Define maximum and minimum pressure for barometer
		if self.System['Units']['Pressure'] == 'mb':
			self.System['Barometer'] = ['950','1050']
		elif self.System['Units']['Pressure'] == 'hpa':
			self.System['Barometer'] = ['950','1050']
		elif self.System['Units']['Pressure'] == 'inhg':
			self.System['Barometer'] = ['28.0','31.0']
		elif self.System['Units']['Pressure'] == 'mmhg':
			self.System['Barometer'] = ['713','788']
		
		# Determine country of Station
		Template = 'http://api.geonames.org/countryCode?lat={}&lng={}&username={}&type=json'
		URL = Template.format(self.System['Lat'],self.System['Lon'],self.System['GeoNamesKey'])
		Data = requests.get(URL).json()
		self.System['Country'] = Data['countryCode']
		
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
			Data = requests.get(URL).json()
			Locns = [Item['name'] for Item in Data['geonames']]
			Len = [len(Item) for Item in Locns]
			Ind = next((Item for Item in Len if Item<=11),NaN)
			if Ind != NaN:
				self.System['ForecastLocn'] = Locns[Len.index(Ind)]
			else:
				self.System['ForecastLocn'] = ''
									
		# Initialise Sunrise/sunset and Moonrise/moonset times
		self.SunriseSunset()
		self.MoonriseMoonset()

		# Define Kivy loop schedule
		Clock.schedule_once(lambda dt: self.DownloadForecast())
		Clock.schedule_once(lambda dt: self.WebsocketConnect())
		Clock.schedule_once(self.SagerForecast)
		Clock.schedule_interval(self.UpdateMethods,1.0)
		Clock.schedule_interval(self.SkyAirStatus,1.0)
		Clock.schedule_interval(self.SunTransit,1.0)
		Clock.schedule_interval(self.MoonPhase,1.0)
		
	# POINT 'WeatherFlowPiConsole' APP CLASS TO ASSOCIATED .kv FILE
	# --------------------------------------------------------------------------
	def build(self):
		return Builder.load_file('WeatherFlowPiConsole.kv')
	
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
			self.WebsocketSendMessage('{"type":"listen_start",' +
			                           ' "device_id":' + self.System['SkyID'] + ',' + 
									   ' "id":"Sky"}')
			self.WebsocketSendMessage('{"type":"listen_rapid_start",' +
			                           ' "device_id":' + self.System['SkyID'] + ',' +
									   ' "id":"RapidSky"}')
			self.WebsocketSendMessage('{"type":"listen_start",' +
			                           ' "device_id":' + self.System['AirID'] + ',' +
									   ' "id":"Air"}')
			
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
	
		# Replace missing observations from SKY Websocket JSON with NaN
		Obs = [x if x != None else NaN for x in Msg['obs'][0]]	
		
		# Extract observations from SKY Websocket JSON 
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

		# Calculate derived variables from SKY observations
		FeelsLike = self.FeelsLike()
		RainRate = self.RainRate(Rain)
		DayRain,MonthRain,YearRain = self.RainAccumulation(Rain) 
		MaxWind,MaxGust = self.SkyObsMaxMin(WindSpd,WindGust)
		Beaufort = self.BeaufortScale(WindSpd)
		Cardinal = self.CardinalWindDirection(WindDir,WindSpd)
		UV = self.UVIndex(UV)
		
		# Convert observation units as required
		cRainRate = self.ConvertObservationUnits(RainRate,'Precip')
		cDayRain = self.ConvertObservationUnits(DayRain,'Precip')
		cMonthRain = self.ConvertObservationUnits(MonthRain,'Precip')
		cYearRain = self.ConvertObservationUnits(YearRain,'Precip')
		cWindSpd = self.ConvertObservationUnits(WindSpd,'Wind')
		cWindDir = self.ConvertObservationUnits(WindDir,'Direction')
		cWindGust = self.ConvertObservationUnits(WindGust,'Wind')
		cMaxWind = self.ConvertObservationUnits(MaxWind,'Wind')
		cMaxGust = self.ConvertObservationUnits(MaxGust,'Wind')
		cFeelsLike = self.ConvertObservationUnits(FeelsLike,'Temp')
		
		# Define Rain Rate format string based on current Rain Rate
		if cRainRate[0] == 0:
			RainRateFmt = '{:.0f}'
		elif cRainRate[0] < 1:
			RainRateFmt = '{:.2f}'
		else:
			RainRateFmt = '{:.1f}'
		
		# Define Rain Accumulation format string based on current Rain Accumulation
		if cDayRain[0] == 0:
			DayRainFmt = '{:.0f}'
		elif cDayRain[0] < 10:
			DayRainFmt = '{:.1f}'
		else:
			DayRainFmt = '{:.0f}'
		if cMonthRain[0] < 10:
			MonthRainFmt = '{:.1f}'
		else:
			MonthRainFmt = '{:.0f}'		
		if cYearRain[0] < 10:
			YearRainFmt = '{:.1f}'
		else:
			YearRainFmt = '{:.0f}'						
					
		# Define and format SKY Kivy label binds		
		self.Sky['Time'] =  datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M:%S')
		self.Sky['RainRate'] = [RainRateFmt.format(cRainRate[0]),cRainRate[1],cRainRate[2]]
		self.Sky['DayRain'] = [DayRainFmt.format(cDayRain[0]),cDayRain[1],cDayRain[0],cDayRain[2]]
		self.Sky['MonthRain'] = [MonthRainFmt.format(cMonthRain[0]),cMonthRain[1],cMonthRain[0],cMonthRain[2]]
		self.Sky['YearRain'] = [YearRainFmt.format(cYearRain[0]),cYearRain[1],cYearRain[0],cYearRain[2]]
		self.Sky['WindSpd'] = ['{:.1f}'.format(cWindSpd[0]),cWindSpd[1],Beaufort[0],Beaufort[1]]
		self.Sky['WindGust'] = ['{:.1f}'.format(cWindGust[0]),cWindGust[1]]
		self.Sky['MaxWind'] = ['{:.1f}'.format(cMaxWind[0]),cMaxWind[1],cMaxWind[2]]
		self.Sky['MaxGust'] = ['{:.1f}'.format(cMaxGust[0]),cMaxGust[1],cMaxGust[2]]
		self.Sky['WindDir'] = [cWindDir[0] if isinstance(cWindDir[0],str) else '{:.0f}'.format(cWindDir[0]),cWindDir[1],Cardinal[0]]
		self.Sky['Battery'] = ['{:.2f}'.format(Battery[0]),Battery[1]]
		self.Sky['Radiation'] = ['{:.0f}'.format(Radiation[0]),Radiation[1],'{:.1f}'.format(UV[0]),UV[2]]

		# Define and format AIR Kivy label binds
		self.Air['FeelsLike'] = ['-' if math.isnan(cFeelsLike[0]) else '{:2.1f}'.format(cFeelsLike[0]),cFeelsLike[1]]
	
	# EXTRACT OBSERVATIONS FROM OBS_AIR WEBSOCKET JSON MESSAGE
	# --------------------------------------------------------------------------
	def WebsocketObsAir(self,Msg):
	
		# Replace missing observations from AIR Websocket JSON with NaN
		Obs = [x if x != None else NaN for x in Msg['obs'][0]]	
		
		# Extract observations from AIR Websocket JSON 	
		Time = [Obs[0],'s']
		Pres = [Obs[1],'mb']
		Temp = [Obs[2],'c']
		Humidity = [Obs[3],'%']
		Battery = [Obs[6],' v']
		
		# Store latest AIR Websocket JSON
		self.Air['Obs'] = Obs

		# Calculate derived variables from AIR observations
		DewPoint = self.DewPoint()
		FeelsLike = self.FeelsLike()
		ComfortLevel = self.ComfortLevel(FeelsLike)
		SLP = self.SeaLevelPressure(Pres)
		PresTrend = self.PressureTrend()
		TempMaxMin,PresMaxMin = self.AirObsMaxMin()

		# Convert observation units as required
		cTemp = self.ConvertObservationUnits(Temp,'Temp')
		cDewPoint = self.ConvertObservationUnits(DewPoint,'Temp')
		cFeelsLike = self.ConvertObservationUnits(FeelsLike,'Temp')
		cTempMaxMin = self.ConvertObservationUnits(TempMaxMin,'Temp')
		cSLP = self.ConvertObservationUnits(SLP,'Pressure')
		cPresTrend = self.ConvertObservationUnits(PresTrend,'Pressure')
		cPresMaxMin = self.ConvertObservationUnits(PresMaxMin,'Pressure')
					
		# Define Pressure format string based on observation unit
		if self.System['Units']['Pressure'] == 'inhg':
			PresFormat = '{:2.3f}'
		elif self.System['Units']['Pressure'] == 'mmhg':
			PresFormat = '{:3.2f}'
		else:
			PresFormat = '{:4.1f}'
		
		# Define and format Kivy labels
		self.Air['Time'] = datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M:%S')
		self.Air['Temp'] = ['{:.1f}'.format(cTemp[0]),cTemp[1]]
		self.Air['MaxTemp'] = ['{:.1f}'.format(float(cTempMaxMin[0])),cTempMaxMin[1],cTempMaxMin[2]]
		self.Air['MinTemp'] = ['{:.1f}'.format(float(cTempMaxMin[3])),cTempMaxMin[4],cTempMaxMin[5]]
		self.Air['DewPoint'] = ['{:.1f}'.format(cDewPoint[0]),cDewPoint[1]]		
		self.Air['FeelsLike'] = ['-' if math.isnan(cFeelsLike[0]) else '{:2.1f}'.format(cFeelsLike[0]),cFeelsLike[1]]
		self.Air['Pres'] = ['{:.1f}'.format(SLP[0]),PresFormat.format(cSLP[0]),cSLP[1]]
		self.Air['MaxPres'] = [PresFormat.format(cPresMaxMin[0]),cPresMaxMin[1]]
		self.Air['MinPres'] = [PresFormat.format(cPresMaxMin[2]),cPresMaxMin[3]]
		self.Air['PresTrend'] = [PresFormat.format(cPresTrend[0]),cPresTrend[1],cPresTrend[2]]		
		self.Air['Humidity'] = ['{:.0f}'.format(Humidity[0]),' ' + Humidity[1]]
		self.Air['Battery'] = ['{:.2f}'.format(Battery[0]),Battery[1]]
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
		Cardinal = self.CardinalWindDirection(WindDir,WindSpd)
		
		# Convert observation units as required
		cWindSpd = self.ConvertObservationUnits(WindSpd,'Wind')

		# Animate wind rose arrow 
		self.WindRoseAnimation(WindDir[0],WindDirOld[0])
		
		# Define and format Kivy labels
		self.SkyRapid['Time'] = datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M:%S')
		self.SkyRapid['Speed'] = ['{:.1f}'.format(cWindSpd[0]),cWindSpd[1]]
		self.SkyRapid['Direc'] = ['{:.0f}'.format(WindDir[0]),'[sup]o[/sup]',Cardinal[1]]		
	
	# CONVERT STATION OBSERVATIONS INTO REQUIRED UNITS
    # --------------------------------------------------------------------------		
	def ConvertObservationUnits(self,Obs,Type):
		
		# Convert temperature observations
		cObs = Obs[:]
		if Type == 'Temp': 
			for ii,T in enumerate(Obs):
				if T == 'c':
					if self.System['Units'][Type] == 'f':
						cObs[ii-1] = Obs[ii-1] * 1.8 + 32
						cObs[ii] = ' [sup]o[/sup]F'
					else:
						cObs[ii-1] = Obs[ii-1]
						cObs[ii] = ' [sup]o[/sup]C'	

		# Convert pressure and pressure trend observations 
		elif Type == 'Pressure': 
			for ii,P in enumerate(Obs):
				if P in ['mb','mb/hr']:
					if self.System['Units'][Type] == 'inhg':
						cObs[ii-1] = Obs[ii-1] * 0.0295301
						if P == 'mb':
							cObs[ii] = ' inHg'
						else:
							cObs[ii] = ' inHg/hr'
						
					elif self.System['Units'][Type] == 'mmhg':
						cObs[ii-1] = Obs[ii-1] * 0.750063
						if P == 'mb':
							cObs[ii] = ' mmHg'
						else:
							cObs[ii] = ' mmHg/hr'
					elif self.System['Units'][Type] == 'hpa':
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
		elif Type == 'Wind':
			for ii,W in enumerate(Obs):
				if W == 'mps':
					if self.System['Units'][Type] == 'mph':
						cObs[ii-1] = Obs[ii-1] * 2.2369362920544
						cObs[ii] = 'mph'
					elif self.System['Units'][Type] == 'kts':
						cObs[ii-1] = Obs[ii-1] * 1.9438
						cObs[ii] = 'kts'
					elif self.System['Units'][Type] == 'kph':
						cObs[ii-1] = Obs[ii-1] * 3.6
						cObs[ii] = 'km/h'							
					elif self.System['Units'][Type] == 'lfm':
						cObs[ii-1] = Obs[ii-1] * 2.2369362920544 * 88
						cObs[ii] = 'lfm'	
					elif self.System['Units'][Type] == 'bft':
						cObs[ii-1] = self.BeaufortScale(Obs[ii-1:ii+1])[2] 
						cObs[ii] = 'bft'
					else:
						cObs[ii-1] = Obs[ii-1]
						cObs[ii] = 'm/s'	

		# Convert wind direction observations
		elif Type == 'Direction':
			for ii,W in enumerate(Obs):
				if W == 'degrees':
					if self.System['Units'][Type] == 'cardinal':
						cObs[ii-1] = self.CardinalWindDirection(Obs[ii-1:ii+1],[1,'mps'])[0]   
						cObs[ii] = ''
					else:
						cObs[ii-1] = Obs[ii-1]   
						cObs[ii] = '[sup]o[/sup]'
						
		# Convert rain accumulation and rain rate observations
		elif Type == 'Precip':
			for ii,Prcp in enumerate(Obs):
				if Prcp in ['mm','mm/hr']:
					if self.System['Units'][Type] == 'in':
						cObs[ii-1] = Obs[ii-1] * 0.0393701
						if Prcp == 'mm':
							cObs[ii] = ' in'
						else:
							cObs[ii] = ' in/hr'
					elif self.System['Units'][Type] == 'cm':
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
				
	# ANIMATE RAPID-WIND WIND ROSE DIRECTION ARROW
	# --------------------------------------------------------------------------
	def WindRoseAnimation(self,newDirec,oldDirec):
	
		# Calculate change in wind direction over last Rapid-Wind period
		WindShift = newDirec - oldDirec			
		
		# Animate Wind Rose at constant speed between old and new Rapid-Wind 
		# wind direction
		if WindShift >= -180 and WindShift <= 180:
			Animation(SkyRapidIcon=newDirec,duration=2*abs(WindShift)/360).start(self)
		elif WindShift > 180:
			Animation(SkyRapidIcon=0,duration=2*oldDirec/360).start(self)	
			self.SkyRapidIcon = 360
			Animation(SkyRapidIcon=newDirec,duration=2*(360-newDirec)/360).start(self)
		elif WindShift < -180:
			Animation(SkyRapidIcon=360,duration=2*(360-oldDirec)/360).start(self)	
			self.SkyRapidIcon = 0
			Animation(SkyRapidIcon=newDirec,duration=2*newDirec/360).start(self)
			
	# CALCULATE DEW POINT FROM HUMIDITY AND TEMPERATURE
    # --------------------------------------------------------------------------
	def DewPoint(self):
	
		# Extract required meteorological fields
		Temp = self.Air['Obs'][2]
		Humidity = self.Air['Obs'][3]
		
		# Calculate dew point unless humidity equals zero
		if Humidity != 0:
			A = 17.625
			B = 243.04
			N = B*(math.log(Humidity/100.0) + (A*Temp)/(B+Temp))
			D = A-math.log(Humidity/100.0) - A*Temp/(B+Temp)
			DewPoint = N/D
		else:
			DewPoint = NaN
		
		# Return Dew Point
		return [DewPoint,'c']
		
	# CALCULATE 'FEELS LIKE' TEMPERATURE FROM HUMIDITY, TEMPERATURE, AND WIND 
	# SPEED
    # --------------------------------------------------------------------------
	def FeelsLike(self):
	
		# Skip calculation during initialisation
		if 'Obs' not in self.Air or self.Sky['Obs'] == '--':
			return [NaN,'c']
				
		# Extract required meteorological fields
		TempC = self.Air['Obs'][2]						# Temperature in C
		TempF = self.Air['Obs'][2] * 9/5 + 32			# Temperature in F
		RH = self.Air['Obs'][3]							# Relative humidity in %
		WindMPH = self.Sky['Obs'][5] * 2.23694          # Wind speed in mph
		WindKPH = self.Sky['Obs'][5] * 3.6				# Wind speed in km/h 
						
		# If temperature is less than 10 degrees celcius and wind speed is 
		# higher than 5 mph, calculate wind chill using the Joint Action Group 
		# for Temperature Indices formula
		if TempC <= 10 and WindMPH > 5:
		
			# Calculate wind chill
			FeelsLike = 13.12 + 0.6215*TempC - 11.37*(WindKPH)**0.16 + 0.3965*TempC*(WindKPH)**0.16
			
		# If temperature is greater than 26.67 degress celcius (80 F), calculate
		# the Heat Index
		elif TempF >= 80:
		
			# Calculate Heat Index
			FeelsLike = -42.379 + (2.04901523*TempF) + (10.1433127*RH) - (0.22475541*TempF*RH) - (6.83783e-3*TempF**2) - (5.481717e-2*RH**2) + (1.22874e-3*TempF**2*RH) + (8.5282e-4*TempF*RH**2) - (1.99e-6*TempF**2*RH**2)
			FeelsLike = (FeelsLike-32) * 5/9

		# Else set 'Feels Like' temperature to observed temperature
		else: 
			FeelsLike = TempC
			
		# Return 'Feels Like' temperature
		return [FeelsLike,'c']
						
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
		Elev = self.System['StnElev'] + self.System['AirHeight']
		T0 = 288.15
		
		# Calculate sea level pressure
		SLP = Psta * (1 + ((P0/Psta)**((Rd*GammaS)/g)) * ((GammaS*Elev)/T0))**(g/(Rd*GammaS))

		# Return Sea Level Pressure
		return [SLP,'mb']		
							
	# CALCULATE THE PRESSURE TREND AND SET THE PRESSURE TREND TEXT
    # --------------------------------------------------------------------------
	def PressureTrend(self):
	
		# Calculate timestamp three hours past
		TimeStart = self.Air['Obs'][0] - (3600*3+59)
		TimeEnd = self.Air['Obs'][0]

		# Download pressure data for last three hours
		Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?time_start={}&time_end={}&api_key={}'
		URL = Template.format(self.System['AirID'],TimeStart,TimeEnd,self.System['WFlowKey'])
		Data = requests.get(URL).json()['obs']
		Pres = [item[1] for item in Data]
		
		# Calculate pressure trend
		Trend = []
		Trend = Pres[-1] - Pres[0]
		
		# Calculate pressure trend text
		if Trend >= 1:
			TrendText = '[color=ff8837ff]Rising[/color]'
		elif Trend <= -1:
			TrendText = '[color=00a4b4ff]Falling[/color]'
		else:
			TrendText = '[color=9aba2fff]Steady[/color]'
		
		# Return pressure trend
		return [Trend/3,'mb/hr',TrendText]
		
	# CALCULATE DAILY RAIN ACCUMULATION LEVELS
    # --------------------------------------------------------------------------
	def RainAccumulation(self,Rain):
		
		# Convert observation units as required
		cRain = self.ConvertObservationUnits(Rain,'Precip')
		
		# Define current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		
		# Code initialising. Download all data for current day using Weatherflow 
		# API. Calculate total daily rainfall
		if self.Sky['DayRain'][0] == '-':
		
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
			DayRain = [sum([x for x,y in Rain]),'mm',Now]

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
			MonthRain = [sum([x for x,y in Rain]),'mm',Now]
			
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
			YearRain = [sum([x for x,y in Rain]),'mm',Now]
			
			# Return Daily, Monthly, and Yearly rainfall accumulation totals
			return DayRain,MonthRain,YearRain
			
		# At midnight, reset daily rainfall accumulation to zero, else add 
		# current rainfall to current daily rainfall accumulation
		if Now.date() > self.Sky['DayRain'][3].date():
			DayRain = [cRain[0],cRain[1],Now]
		else:
			DayRain = [self.Sky['DayRain'][2] + cRain[0],cRain[1],Now]	
		
		# At end of month, reset monthly rainfall accumulation to zero, else add 
		# current rainfall to current monthly rainfall accumulation
		if Now.month > self.Sky['MonthRain'][3].month:
			MonthRain = [cRain[0],cRain[1],Now]
		else:
			MonthRain = [self.Sky['MonthRain'][2] + cRain[0],cRain[1],Now]
		
		# At end of year, reset monthly and yearly rainfall accumulation to zero, 
		# else add current rainfall to current yearly rainfall accumulation
		if Now.year > self.Sky['YearRain'][3].year:
			YearRain = [cRain[0],cRain[1],Now]
			MonthRain = [cRain[0],cRain[1],Now]
		else:
			YearRain = [self.Sky['YearRain'][2] + cRain[0],cRain[1],Now]
			
		# Return Daily, Monthly, and Yearly rainfall accumulation totals
		return DayRain,MonthRain,YearRain
		
	# SET THE RAIN RATE TEXT
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
		
	# CALCULATE MAXIMUM AND MINIMUM OBSERVED TEMPERATURE AND PRESSURE
	# --------------------------------------------------------------------------
	def AirObsMaxMin(self):

		# Extract required meteorological fields
		Time = self.Air['Obs'][0]
		Temp = [self.Air['Obs'][2],'c']
		Pres = [self.Air['Obs'][1],'mb']

		# Calculate sea level pressure
		SLP = self.SeaLevelPressure(Pres)
		
		# Convert observation units as required
		cTemp = self.ConvertObservationUnits(Temp,'Temp')
		cSLP = self.ConvertObservationUnits(SLP,'Pressure')
		
		# Define current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		
		# Define required variables
		TempMaxMin = []
		PresMaxMin = []

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
			URL = Template.format(self.System['AirID'],Midnight_UTC,Now_UTC,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Time = [item[0] if item[0] != None else NaN for item in Data]
			Temp = [[item[2],'c'] if item[2] != None else [NaN,'c'] for item in Data]
			Pres = [[item[1],'mb'] if item[1] != None else [NaN,'mb'] for item in Data]

			# Calculate sea level pressure
			SLP = [self.SeaLevelPressure(P) for P in Pres]

			# Define maximum and minimum temperature and time
			TempMaxMin.extend(Temp[Temp.index(max(Temp))])
			TempMaxMin.append(datetime.fromtimestamp(Time[Temp.index(max(Temp))],Tz).strftime('%H:%M'))
			TempMaxMin.extend(Temp[Temp.index(min(Temp))])
			TempMaxMin.append(datetime.fromtimestamp(Time[Temp.index(min(Temp))],Tz).strftime('%H:%M'))

			# Define maximum and minimum pressure
			PresMaxMin.extend(max(SLP))
			PresMaxMin.extend(min(SLP))

			# Define current meteorological day
			self.Air['MetDay'] = Now.date()
			
			# Return required variables
			return TempMaxMin,PresMaxMin
			
		# AT MIDNIGHT RESET MAXIMUM AND MINIMUM TEMPERATURE AND PRESSURE 
		if self.Air['MetDay'] < Now.date():
			TempMaxMin.extend(Temp)
			TempMaxMin.append(datetime.fromtimestamp(Time,self.System['tz']).strftime('%H:%M'))
			TempMaxMin.extend(Temp)
			TempMaxMin.append(datetime.fromtimestamp(Time,self.System['tz']).strftime('%H:%M'))
			PresMaxMin.extend(SLP)
			PresMaxMin.extend(SLP)
			self.Air['MetDay'] = Now.date()
			
			# Return required variables
			return TempMaxMin,PresMaxMin
	
		# Current temperature is greater than maximum recorded temperature. 
		# Update maximum temperature and time
		if cTemp[0] > float(self.Air['MaxTemp'][0]):
			TempMaxMin.extend(Temp)
			TempMaxMin.append(datetime.fromtimestamp(Time,self.System['tz']).strftime('%H:%M'))
			TempMaxMin.append(float(self.Air['MinTemp'][0]))
			TempMaxMin.extend(self.Air['MinTemp'][1:])

		# Current temperature is less than minimum recorded temperature. Update 
		# minimum temperature and time	
		elif cTemp[0] < float(self.Air['MinTemp'][0]):
			TempMaxMin.append(float(self.Air['MaxTemp'][0]))
			TempMaxMin.extend(self.Air['MaxTemp'][1:])
			TempMaxMin.extend(Temp)
			TempMaxMin.append(datetime.fromtimestamp(Time,self.System['tz']).strftime('%H:%M'))

		# Maximum and minimum temperature unchanged. Return existing values	
		else:
			TempMaxMin.append(float(self.Air['MaxTemp'][0]))
			TempMaxMin.extend(self.Air['MaxTemp'][1:])
			TempMaxMin.append(float(self.Air['MinTemp'][0]))
			TempMaxMin.extend(self.Air['MinTemp'][1:])

		# Current pressure is greater than maximum recorded pressure. Update 
		# maximum pressure
		if cSLP[0] > float(self.Air['MaxPres'][0]):
			PresMaxMin.extend(SLP)
			PresMaxMin.extend([float(self.Air['MinPres'][0]),self.Air['MinPres'][1]])
			
		# Current pressure is less than minimum recorded pressure. Update 
		# minimum pressure and time	
		elif cSLP[0] < float(self.Air['MinPres'][0]):
			PresMaxMin.extend([float(self.Air['MaxPres'][0]),self.Air['MaxPres'][1]])
			PresMaxMin.extend(SLP)
			
		# Maximum and minimum pressure unchanged. Return existing values
		else:
			PresMaxMin.extend([float(self.Air['MaxPres'][0]),self.Air['MaxPres'][1]])
			PresMaxMin.extend([float(self.Air['MinPres'][0]),self.Air['MinPres'][1]])
			
		# Return required variables
		return TempMaxMin,PresMaxMin	
			
	# CALCULATE MAXIMUM AND MINIMUM OBSERVED WIND SPEED AND GUST STRENGTH
	# --------------------------------------------------------------------------
	def SkyObsMaxMin(self,WindSpd,WindGust):
		
		# Convert observation units as required
		cWindSpd = self.ConvertObservationUnits(WindSpd,'Wind')
		cWindGust = self.ConvertObservationUnits(WindGust,'Wind')
		
		# Define current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		
		# CODE INITIALISING. DOWNLOAD DATA FOR CURRENT DAY USING WEATHERFLOW API
		if self.Sky['MaxWind'] == '--':
		
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
			WindGust = [[item[6],'mps'] if item[6] != None else [NaN,'mps'] for item in Data]

			# Define maximum wind speed and wind gust
			MaxWind = [max([x for x,y in WindSpd]),'mps',Now]
			MaxGust = [max([x for x,y in WindGust]),'mps',Now]
			
			# Return maximum wind speed and gust
			return MaxWind,MaxGust

		# AT MIDNIGHT RESET MAXIMUM RECORDED WIND SPEED AND GUST	
		if self.Sky['MaxWind'][2].date() < Now.date():
			MaxWind = [WindSpd[0],'mps',Now]
			MaxGust = [WindGust[0],'mps',Now]
			
			# Return maximum wind speed and gust
			return MaxWind,MaxGust	
			
		# Current wind speed is greater than maximum recorded wind speed. Update
		# maximum wind speed
		if cWindSpd[0] > float(self.Sky['MaxWind'][0]):
			MaxWind = [WindSpd[0],'mps',Now]
			
		# Maximum wind speed is unchanged. Return existing value
		else:
			MaxWind = [float(self.Sky['MaxWind'][0]),self.Sky['MaxWind'][1],self.Sky['MaxWind'][2]]
			
		# Current gust speed is greater than maximum recorded gust speed. Update 
		# maximum gust speed 
		if cWindGust[0] > float(self.Sky['MaxGust'][0]):
			MaxGust = [WindGust[0],'mps',Now]	
				
		# Maximum gust speed is unchanged. Return existing value
		else:
			MaxGust = [float(self.Sky['MaxGust'][0]),self.Sky['MaxGust'][1],self.Sky['MaxGust'][2]]	
			
		# Return maximum wind speed and gust
		return MaxWind,MaxGust	
			
	# SET THE COMFORT LEVEL TEXT STRING AND ICON
	# --------------------------------------------------------------------------
	def ComfortLevel(self,FeelsLike):		
	
		# Skip during initialisation
		if FeelsLike == '--':
			return
		
		# Define comfort level text and icon
		ComfortLevel = []
		if FeelsLike[0] < -4:
			ComfortLevel.append('Feeling extremely cold')
			ComfortLevel.append('ExtremelyCold')
		elif FeelsLike[0] < 0:
			ComfortLevel.append('Feeling freezing cold')
			ComfortLevel.append('FreezingCold')
		elif FeelsLike[0] < 4:
			ComfortLevel.append('Feeling very cold')
			ComfortLevel.append('VeryCold')
		elif FeelsLike[0] < 9:
			ComfortLevel.append('Feeling cold')
			ComfortLevel.append('Cold')
		elif FeelsLike[0] < 14:
			ComfortLevel.append('Feeling mild')
			ComfortLevel.append('Mild')
		elif FeelsLike[0] < 18:
			ComfortLevel.append('Feeling warm')
			ComfortLevel.append('Warm')
		elif FeelsLike[0] < 23:
			ComfortLevel.append('Feeling hot')
			ComfortLevel.append('Hot')
		elif FeelsLike[0] < 28:
			ComfortLevel.append('Feeling very hot')
			ComfortLevel.append('VeryHot')
		elif FeelsLike[0] >= 28:
			ComfortLevel.append('Feeling extremely hot')
			ComfortLevel.append('ExtremelyHot')
		
		# Return comfort level text string and icon
		return ComfortLevel	
					
	# SET CARDINAL WIND DIRECTION AND DESCRIPTION
	# --------------------------------------------------------------------------
	def CardinalWindDirection(self,Dir,Spd):
			
		# Define cardinal wind direction and description
		if Spd[0] == 0:
			Description = '[color=9aba2fff]Calm[/color]'
			Direction = 'N'
		elif Dir[0] <= 11.25:
			Description = 'Due [color=9aba2fff]North[/color]'
			Direction = 'N'
		elif Dir[0] <= 33.75:
			Description = 'North [color=9aba2fff]NE[/color]'
			Direction = 'NNE'
		elif Dir[0] <= 56.25:
			Description = 'North [color=9aba2fff]East[/color]'
			Direction = 'NE'
		elif Dir[0] <= 78.75:
			Description = 'East [color=9aba2fff]NE[/color]'
			Direction = 'ENE'
		elif Dir[0] <= 101.25:
			Description = 'Due [color=9aba2fff]East[/color]'
			Direction = 'E'
		elif Dir[0] <= 123.75:
			Description = 'East [color=9aba2fff]SE[/color]'
			Direction = 'ESE'
		elif Dir[0] <= 146.25:
			Description = 'South [color=9aba2fff]East[/color]'
			Direction = 'SE'
		elif Dir[0] <= 168.75:
			Description = 'South [color=9aba2fff]SE[/color]'
			Direction = 'SSE'
		elif Dir[0] <= 191.25:
			Description = 'Due [color=9aba2fff]South[/color]'
			Direction = 'S'
		elif Dir[0] <= 213.75:
			Description = 'South [color=9aba2fff]SW[/color]'
			Direction = 'SSW'
		elif Dir[0] <= 236.25:
			Description = 'South [color=9aba2fff]West[/color]'
			Direction = 'SW'
		elif Dir[0] <= 258.75:
			Description = 'West [color=9aba2fff]SW[/color]'
			Direction = 'WSW'
		elif Dir[0] <= 281.25:
			Description = 'Due [color=9aba2fff]West[/color]'
			Direction = 'W'
		elif Dir[0] <= 303.75:
			Description = 'West [color=9aba2fff]NW[/color]'
			Direction = 'WNW'
		elif Dir[0] <= 326.25:
			Description = 'North [color=9aba2fff]West[/color]'
			Direction = 'NW'			
		elif Dir[0] <= 348.75:
			Description = 'North [color=9aba2fff]NW[/color]'
			Direction = 'NNW'
		else:
			Description = 'Due [color=9aba2fff]North[/color]'
			Direction = 'N'
			
		# Cardinal wind direction and description
		return [Direction,Description]
			
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
		return [UV[0],'index',UVIcon]
			
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
			
		# Define Kivy label binds for sunset and sunrise times
		self.SunriseSunsetText()
		
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
		
		# Define Kivy label binds for next new/full moon in 
		# station time zone
		if FullMoon.date() == Now.date():
			self.MoonData['FullMoon'] = '[color=ff8837ff]Today[/color]'   
		else:
			self.MoonData['FullMoon'] = FullMoon.astimezone(Tz).strftime('%b %d') 
		if NewMoon.date() == Now.date():
			self.MoonData['NewMoon'] = '[color=ff8837ff]Today[/color]'
		else:
			self.MoonData['NewMoon'] = NewMoon.astimezone(Tz).strftime('%b %d') 
		
		# Define Kivy label binds for moonrise and moonset times
		self.MoonriseMoonsetText()	
		
	# DEFINE SUNSET AND SUNRISE KIVY LABEL BINDS
	# --------------------------------------------------------------------------
	def SunriseSunsetText(self):
		
		# Define sunrise/sunset kivy label binds based on date of
		# next sunrise/sunset
		if datetime.now(self.System['tz']).date() == self.SunData['Sunrise'][0].date():
			self.SunData['Sunrise'][1] = self.SunData['Sunrise'][0].strftime('%H:%M')
			self.SunData['Sunset'][1] = self.SunData['Sunset'][0].strftime('%H:%M')
		else:
			self.SunData['Sunrise'][1] = self.SunData['Sunrise'][0].strftime('%H:%M') + ' (+1)'
			self.SunData['Sunset'][1] = self.SunData['Sunset'][0].strftime('%H:%M') + ' (+1)'
			
	# DEFINE SUNSET AND SUNRISE KIVY LABEL BINDS
	# --------------------------------------------------------------------------
	def MoonriseMoonsetText(self):
		
		# Define Moonrise Kivy Label bind based on date of next 
		# moonrise
		if datetime.now(self.System['tz']).date() == self.MoonData['Moonrise'][0].date():
			self.MoonData['Moonrise'][1] = self.MoonData['Moonrise'][0].strftime('%H:%M')
		elif datetime.now(self.System['tz']).date() < self.MoonData['Moonrise'][0].date():
			self.MoonData['Moonrise'][1] = self.MoonData['Moonrise'][0].strftime('%H:%M') + ' (+1)'
		else:
			self.MoonData['Moonrise'][1] = self.MoonData['Moonrise'][0].strftime('%H:%M') + ' (-1)'
			
		# Define Moonset Kivy Label bind based on date of next
		# moonset
		if datetime.now(self.System['tz']).date() == self.MoonData['Moonset'][0].date():
			self.MoonData['Moonset'][1] = self.MoonData['Moonset'][0].strftime('%H:%M')
		elif datetime.now(self.System['tz']).date() < self.MoonData['Moonset'][0].date():
			self.MoonData['Moonset'][1] = self.MoonData['Moonset'][0].strftime('%H:%M') + ' (+1)'
		else:
			self.MoonData['Moonset'][1] = self.MoonData['Moonset'][0].strftime('%H:%M') + ' (-1)'	
			
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
		Temp = self.ConvertObservationUnits(Temp,'Temp')
		WindSpd = self.ConvertObservationUnits(WindSpd,'Wind')
		
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
		Temp = self.ConvertObservationUnits(Temp,'Temp')
		WindSpd = self.ConvertObservationUnits(WindSpd,'Wind')

		# Define and format Kivy label binds
		self.MetData['Time'] = datetime.now(pytz.utc).astimezone(Tz)
		self.MetData['Issued'] = datetime.strftime(Issued,'%H:%M')
		self.MetData['Valid'] = datetime.strftime(Valid,'%H:%M')
		self.MetData['Temp'] = ['{:.1f}'.format(Temp[0]),Temp[1]]
		self.MetData['WindDir'] = self.CardinalWindDirection(WindDir,[1,'mps'])[0]
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
		URL = Template.format(self.System['AirID'],Now-Hours_6,Now,self.System['WFlowKey'])
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
		Data = requests.get(URL,headers=header).json()
		self.Sager['METAR'] = Data['data'][0]
	
		# Calculate Sager Weathercaster Forecast
		self.Sager['Dial'] = Sager.DialSetting(self.Sager)
		self.Sager['Forecast'] = Sager.Forecast(self.Sager['Dial'])
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
		if self.Sky['Obs'] != '--':
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
			
		# At 5 minutes past each hour, download a new forecast
		# for the Station location
		if (Now.minute,Now.second) == (5,0):
			self.DownloadForecast()
			
		# At the top of each hour update the on-screen forecast
		# for the Station location
		if Now.hour > self.MetData['Time'].hour or Now.time() == time(0,0,0):
			if self.System['Country'] == 'GB':
				self.ExtractMetOfficeForecast()
			else:
				self.ExtractDarkSkyForecast()
			self.MetData['Time'] = Now

		# If app is initialising or once sunset has passed, 
		# calculate new sunrise/sunset times
		if Now > self.SunData['Sunset'][0]:
			self.SunriseSunset()
			
		# If app is initialising or once moonset has passed, 
		# calculate new moonrise/moonset times
		if Now > self.MoonData['Moonset'][0]:
			self.MoonriseMoonset()	

		# At midnight, update Sunset and Sunrise Label binds
		if Now.time() == time(0,0,0):
			self.SunriseSunsetText()
			self.MoonriseMoonsetText()
		
# ==============================================================================
# DEFINE 'WeatherFlowPiConsoleScreen' SCREEN MANAGER
# ==============================================================================			
class WeatherFlowPiConsoleScreen(ScreenManager):
    pass

# ==============================================================================
# DEFINE 'CurrentConditions' SCREEN 
# ==============================================================================
class CurrentConditions(Screen):

	# Define Kivy properties required by 'CurrentConditions' 
	Screen = DictProperty([('Clock','--'),('SunMoon','Sun'),
						   ('MetSager','Met'),
						   ('xRainAnim',476),('yRainAnim',3)])
					
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
		self.Screen['Clock'] = datetime.now(Tz).strftime('%a, %d %b %Y\n%H:%M:%S')
		
	# ANIMATE RAIN RATE ICON
	# --------------------------------------------------------------------------
	def RainRateAnimation(self,dt):
	
		# Calculate current rain rate
		if App.get_running_app().Sky['Obs'] == '--':
			return
		else:
			RainRate = App.get_running_app().Sky['Obs'][3] * 60
			
		# Define required animation variables
		x0 = 3
		xt = 116
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
		if self.Screen['xRainAnim']-1 == 245:
			self.Screen['xRainAnim'] = 476
		else:
			self.Screen['xRainAnim'] -= 1	
			
	# SWITCH BETWEEN SUNRISE/SUNSET AND MOON DATA
	# --------------------------------------------------------------------------		
	def SwitchSunMoon(self,instance):
	
		# Highlight Sun/Moon button press
		self.ButtonPress(instance.text)
	
		# Switch between Sun and Moon screens
		if self.Screen['SunMoon'] == 'Sun':
			self.ids.Sunrise.opacity = 0
			self.ids.Moon.opacity = 1
			self.Screen['SunMoon'] = 'Moon'
		else:
			self.ids.Sunrise.opacity = 1
			self.ids.Moon.opacity = 0		
			self.Screen['SunMoon'] = 'Sun'	
			
	# SWITCH BETWEEN SUNRISE/SUNSET AND MOOD DATA
	# --------------------------------------------------------------------------
	def SwitchMetOfficeSager(self,instance):
	
		# Highlight Sun/Moon button press
		self.ButtonPress(instance.text)
	
		# Switch between Sun and Moon screens
		if self.Screen['MetSager'] == 'Met':
			self.ids.MetOffice.opacity = 0
			self.ids.Sager.opacity = 1
			self.Screen['MetSager'] = 'Sager'
		else:
			self.ids.MetOffice.opacity = 1
			self.ids.Sager.opacity = 0		
			self.Screen['MetSager'] = 'Met'			
	
	# HIGHLIGHT BUTTON WHEN PRESSED
	# --------------------------------------------------------------------------
	def ButtonPress(self,ID):
		if ID == 'Forecast':
			self.ids.Forecast.source = 'Buttons/Forecast_Pressed.png'
		elif ID == 'SunMoon':
			self.ids.SunMoon.source = 'Buttons/SunMoon_Pressed.png'
		elif ID == 'Credits':
			self.ids.Credits.source = 'Buttons/Credits_Pressed.png'
		
	# REMOVE BUTTON HIGHLIGHTING WHEN RELEASED
	# --------------------------------------------------------------------------
	def ButtonRelease(self,instance):
		if instance.text == 'Forecast':
			self.ids.Forecast.source = 'Buttons/Forecast.png'
		elif instance.text == 'SunMoon':
			self.ids.SunMoon.source = 'Buttons/SunMoon.png'
		elif instance.text == 'Credits':
			self.ids.Credits.source = 'Buttons/Credits.png'
	
	# SHOW CREDITS POPUP 
	# --------------------------------------------------------------------------
	def ShowCredits(self,instance):
	
		# Highlight Credits button press
		self.ButtonPress(instance.text)
		
		# Open Credits popup
		Credits().open()
		
# ==============================================================================
# DEFINE POPUPS
# ==============================================================================	
class Credits(Popup):
	pass

class Version(ModalView):
	pass
	
# ==============================================================================
# RUN WeatherFlowPiConsole
# ==============================================================================
if __name__ == '__main__':
	log.startLogging(sys.stdout)
	WeatherFlowPiConsole().run()
