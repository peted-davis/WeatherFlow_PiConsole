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
		print("Client connection failed .. retrying ..")
		self.retry(connector)

	def clientConnectionLost(self,connector,reason):
		print("Client connection lost .. retrying ..")
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
import platform

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
# DEFINE "WeatherFlowPiConsole" APP CLASS
# ==============================================================================
class WeatherFlowPiConsole(App):
	
	# Define Kivy properties required for display in "WeatherFlowPiConsole.kv" 
	System = DictProperty([('ForecastLocn','--'),('Units',{}),('Barometer','--')])
	MetData = DictProperty([('Temp','--'),('Precip','--'),('WindSpd','--'),
							('WindDir','--'),('Weather','Building'),
	                        ('Valid','--'),('Issued','--')])
	Sager = DictProperty([('Lat','--'),('MetarKey','--'),('WindDir6','--'),
	                      ('WindDir','--'),('WindSpd6','--'),('WindSpd','--'),
						  ('Pres','--'),('Pres6','--'),('LastRain','--'),
						  ('Temp','--'),('Dial','--'),('Forecast','--'),
						  ('Issued','--')])									 
	SkyRapid = DictProperty([('Time','--'),('Speed','--'),('Direc','-'),
	                         ('DirecText','--'),('Icon','Building')])	
	SkyRapidAngle = NumericProperty(0)							 
	Sky = DictProperty([('UV','--'),('UVIcon','Building'),('Radiation','--'),
						('RainRate','--'),('RainRateText','--'),('WindAvg','--'),
						('WindGust','--'),('WindDirec','--'),('DirecIcon','--'),
						('MaxWind','--'),('MaxGust','--'),('BeaufortText','--'),
						('BeaufortIcon','Building'),('Time','--'),('Battery','--'),
						('DayRain',['--','--','--']),('MonthRain',['--','--','--']),
						('YearRain',['--','--','--']),
						('StatusIcon','Error'),('MetDay','--'),('Obs','--')])
	Breathe = DictProperty([('Temp','--'),('Min','--'),('Max','--'),('MetDay','--')])		
	Air = DictProperty([('Temp','--'),('MinTemp','---'),('MaxTemp','---'),
						('Humidity','--'),('DewPoint','--'),('Pres','---'),
						('MaxPres','--'),('MinPres','--'),('PresTrend','---'),
						('FeelsLike','--'),('Comfort','--'),('Time','-'),
						('Battery','-'),('StatusIcon','Error')])									 
	SunData = DictProperty([('Sunrise','--'),('Sunset','--'),
							('SunriseTxt','--'),('SunsetTxt','--'),('SunAngle','--'),
							('Event','--'),('EventHrs','--'),('EventMins','--'),
							('ValidDate','--')])
	MoonData = DictProperty([('Moonrise','--'),('Moonset','--'),
							('MoonriseTxt','--'),('MoonsetTxt','--'),('NewMoon','--'),
							('FullMoon','--'),('Illuminated','--'),('Phase','--'),
							('Icon','Building')])	
	MetDict = DictProperty()						
    
	# INITIALISE "WeatherFlowPiConsole" CLASS
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
		if self.System['Units']['Pressure'] == 'mb' or 'hpa':
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
			Template = ("http://api.geonames.org/findNearbyPlaceName?lat={}&lng={}" 
						"&username={}&radius=10&featureClass=P&maxRows=20&type=json")	
			URL = Template.format(self.System['Lat'],self.System['Lon'],self.System['GeoNamesKey'])
			Data = requests.get(URL).json()
			Locns = [Item['name'] for Item in Data['geonames']]
			Len = [len(Item) for Item in Locns]
			Ind = next((Item for Item in Len if Item<=11),NaN)
			if Ind != NaN:
				self.System['ForecastLocn'] = Locns[Len.index(Ind)]
			else:
				self.System['ForecastLocn'] = ""
									
		# Initialise Sunrise/sunset and Moonrise/moonset times
		self.SunriseSunset()
		self.MoonriseMoonset()

		# Define Kivy loop schedule
		Clock.schedule_once(lambda dt: self.DownloadForecast())
		Clock.schedule_once(lambda dt: self.WebsocketConnect())
		Clock.schedule_once(self.SagerForecast)
		Clock.schedule_interval(self.UpdateMethods,1.0)
		Clock.schedule_interval(self.SkyAirStatus,1.0)
		
	# POINT "WeatherFlowPiConsole" APP CLASS TO ASSOCIATED .kv FILE
	# --------------------------------------------------------------------------
	def build(self):
		return Builder.load_file('WeatherFlowPiConsole.kv')
	
	# CONNECT TO THE WEATHER FLOW WEBSOCKET SERVER
	# --------------------------------------------------------------------------
	def WebsocketConnect(self):
		Template = "ws://ws.weatherflow.com/swd/data?api_key={}"
		Server = Template.format(self.System['WFlowKey'])
		self._factory = WeatherFlowClientFactory(Server,self)
		reactor.connectTCP("ws.weatherflow.com",80,self._factory)		

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
			
		# Extract 1-minute observations from Sky Module
		elif Type == 'obs_sky':
		
			# Extract observations from Sky websocket message, and replace 
			# missing observations with NaN
			Obs = [x if x != None else NaN for x in Msg['obs'][0]]
			Time = Obs[0]
			UV = Obs[2]
			RainRate = Obs[3] 
			WindAvg = Obs[5]       
			WindGust = Obs[6]      
			WindDirec = Obs[7]
			Battery = Obs[8]
			Radiation = Obs[10]
			
			# Store latest Observation JSON message
			self.Sky['Obs'] = Msg['obs'][0]
			
			# Calculate derived variables from Sky observations
			FeelsLike = self.FeelsLike()
			
			# Convert observation units as required
			RainRate = RainRate * 60				  # Rain rate in mm/hour
			WindAvg = WindAvg * 2.23694         	  # Wind speed in miles/hour
			WindGust = WindGust * 2.23694       	  # Wind speed in miles/hour
			FeelsLike = self.ConvertObservationUnits(FeelsLike,'Temp')
						
			# Define and format Sky Kivy label binds		
			self.Sky['Time'] = datetime.fromtimestamp(Time,self.System['tz']).strftime('%H:%M:%S')
			self.Sky['UV'] = "{:2.1f}".format(UV)
			self.Sky['Radiation'] = "{:4.0f}".format(Radiation)
			self.Sky['WindAvg'] = "{:2.1f}".format(WindAvg)
			self.Sky['WindGust'] = "{:2.1f}".format(WindGust)
			self.Sky['Battery'] = "{:1.2f}".format(Battery)
			self.Sky['DirecIcon'] = self.WindBearingToCompassDirec(WindDirec,WindAvg)[0]
			self.Sky['WindDirec'] = str(WindDirec)
			if RainRate == 0:
				self.Sky['RainRate'] = "{:1.0f}".format(RainRate)	
			elif RainRate < 1:
				self.Sky['RainRate'] = "{:1.2f}".format(RainRate)
			else:
				self.Sky['RainRate'] = "{:2.1f}".format(RainRate)
				
			# Define and format AIR Kivy label binds
			self.Air['FeelsLike'] = ['--' if math.isnan(FeelsLike[0]) else "{:2.1f}".format(FeelsLike[0]),FeelsLike[1]]
						
			# Calculate "Feels Like" temperature, rain 
			# accumulation, and  max/min wind speed and gust  
			self.RainAccumulation()
			self.SkyObsMaxMin()
			
			# Set comfort level text/icon, wind direction text, 
			# Beaufort Scale text, and UV Index icon.
			#self.Set_ComfortLevelText()
			self.BeaufortScale()
			self.RainRate()
			self.UVIndex()
			
		# Extract Rapid-Wind observations from SKY Module	
		elif Type == 'rapid_wind':
			
			# Replace missing observations from SKY Rapid-Wind Websocket JSON 
			# with NaN
			Obs = [x if x != None else NaN for x in Msg['ob']]	

			# Extract observations from latest SKY Rapid-Wind Websocket JSON 
			Time = Obs[0]
			Speed = Obs[1] 
			Direc = Obs[2]
			
			# Extract wind direction from previous SKY Rapid-Wind Websocket JSON
			if 'Obs' in self.SkyRapid:
				DirecOld = self.SkyRapid['Obs'][2]
			else:
				DirecOld = 0
						
			# If windspeed is zero, freeze direction at last direction of 
			# non-zero wind speed, and edit latest SKY Rapid-Wind Websocket JSON 
			if Speed == 0:
				Direc = DirecOld
				Obs[2] = DirecOld
				
			# Store latest SKY Observation JSON message
			self.SkyRapid['Obs'] = Obs
			
			# Convert observation units as required
			Speed = Speed * 2.23694         		  # Wind speed in miles/hour
			
			# Animate wind rose arrow 
			self.WindRoseAnimation(Direc,DirecOld)
			
			# Define and format Kivy labels
			self.SkyRapid['Time'] = datetime.fromtimestamp(Time,self.System['tz']).strftime('%H:%M:%S')
			self.SkyRapid['Speed'] = "{:2.1f}".format(Speed)
			self.SkyRapid['DirecText'] = self.WindBearingToCompassDirec(Direc,Speed)[1]
			self.SkyRapid['Direc'] = str(Direc)	
					
		# Extract 1-minute observations from AIR Module
		elif Type == 'obs_air':
		
			# Replace missing observations from AIR Websocket JSON with NaN
			Obs = [x if x != None else NaN for x in Msg['obs'][0]]	
			
			# Extract observations from AIR Websocket JSON 	
			Time = [Obs[0],'s']
			Pres = [Obs[1],'mb']
			Temp = [Obs[2],'c']
			Humidity = [Obs[3],'%']
			Battery = [Obs[6],'v']
			
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
			Temp = self.ConvertObservationUnits(Temp,'Temp')
			DewPoint = self.ConvertObservationUnits(DewPoint,'Temp')
			FeelsLike = self.ConvertObservationUnits(FeelsLike,'Temp')
			TempMaxMin = self.ConvertObservationUnits(TempMaxMin,'Temp')
			SLP = self.ConvertObservationUnits(SLP,'Pressure')
			PresTrend = self.ConvertObservationUnits(PresTrend,'Pressure')
			PresMaxMin = self.ConvertObservationUnits(PresMaxMin,'Pressure')
			
			# Define Pressure format string based on observation unit
			if self.System['Units']['Pressure'] == 'inhg':
				PresFormat = "{:2.3f}"
			elif self.System['Units']['Pressure'] == 'mmhg':
				PresFormat = "{:3.2f}"
			else:
				PresFormat = "{:4.1f}"
			
			# Define and format Kivy labels
			self.Air['Time'] = datetime.fromtimestamp(Time[0],self.System['tz']).strftime('%H:%M:%S')
			self.Air['Temp'] = ["{:2.1f}".format(Temp[0]),Temp[1]]
			self.Air['MaxTemp'] = ["{:2.1f}".format(float(TempMaxMin[0])),TempMaxMin[1],TempMaxMin[2]]
			self.Air['MinTemp'] = ["{:2.1f}".format(float(TempMaxMin[3])),TempMaxMin[4],TempMaxMin[5]]
			self.Air['DewPoint'] = ["{:2.1f}".format(DewPoint[0]),DewPoint[1]]		
			self.Air['FeelsLike'] = ['-' if math.isnan(FeelsLike[0]) else "{:2.1f}".format(FeelsLike[0]),FeelsLike[1]]
			self.Air['Pres'] = ["{:4.1f}".format(Pres[0]),PresFormat.format(SLP[0]),SLP[1]]
			self.Air['MaxPres'] = [PresFormat.format(PresMaxMin[0]),PresMaxMin[1]]
			self.Air['MinPres'] = [PresFormat.format(PresMaxMin[2]),PresMaxMin[3]]
			self.Air['PresTrend'] = [PresFormat.format(PresTrend[0]/3),PresTrend[1] + '/hr',PresTrend[2]]		
			self.Air['Humidity'] = ["{:2.0f}".format(Humidity[0]),' ' + Humidity[1]]
			self.Air['Comfort'] = ComfortLevel
			self.Air['Battery'] = "{:1.2f}".format(Battery[0])
				
	# CONVERT STATION OBSERVATIONS INTO REQUIRED UNITS
    # --------------------------------------------------------------------------		
	def ConvertObservationUnits(self,Obs,Type):
		
		# Convert temperature observation
		cObs = Obs[:]
		if Type == 'Temp': 
			for ii,T in enumerate(Obs):
				if T == 'c':
					if self.System['Units'][Type] == 'f':
						cObs[ii-1] = Obs[ii-1] * 9/5 + 32
					else:
						cObs[ii-1] = Obs[ii-1]
					cObs[ii] = " [sup]o[/sup]" + self.System['Units'][Type].upper()	

		# Convert pressure observation
		elif Type == 'Pressure': 
			for ii,P in enumerate(Obs):
				if P == 'mb':
					if self.System['Units'][Type] == 'inhg':
						cObs[ii-1] = Obs[ii-1] * 0.029530
						cObs[ii] = 'inHg'
					elif self.System['Units'][Type] == 'mmhg':
						cObs[ii-1] = Obs[ii-1] * 0.750063
						cObs[ii] = 'mmHg'
					elif self.System['Units'][Type] == 'hpa':
						cObs[ii-1] = Obs[ii-1]
						cObs[ii] = 'hPa'
					else:
						cObs[ii-1] = Obs[ii-1]
						cObs[ii] = 'mb'

		# Return converted observation	
		return cObs
				
	# ANIMATE RAPID-WIND WIND ROSE DIRECTION ARROW
	# --------------------------------------------------------------------------
	def WindRoseAnimation(self,newDirec,oldDirec):
	
		# Calculate change in wind direction over last Rapid-Wind period
		WindShift = newDirec - oldDirec			
		
		# Animate Wind Rose at constant speed between old and new Rapid-Wind 
		# wind direction
		if WindShift >= -180 and WindShift <= 180:
			Animation(SkyRapidAngle=newDirec,duration=2*abs(WindShift)/360).start(self)
		elif WindShift > 180:
			Animation(SkyRapidAngle=0,duration=2*oldDirec/360).start(self)	
			self.SkyRapidAngle = 360
			Animation(SkyRapidAngle=newDirec,duration=2*(360-newDirec)/360).start(self)
		elif WindShift < -180:
			Animation(SkyRapidAngle=360,duration=2*(360-oldDirec)/360).start(self)	
			self.SkyRapidAngle = 0
			Animation(SkyRapidAngle=newDirec,duration=2*newDirec/360).start(self)
			
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
			DewPoint = [N/D,'c']
		else:
			DewPoint = [NaN,'c']
		return DewPoint
		
	# CALCULATE "FEELS LIKE" TEMPERATURE FROM HUMIDITY, TEMPERATURE, AND WIND 
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
			
		# Return "Feels Like" temperature
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

		# Return sea level pressure
		return [SLP,'mb']		
							
	# CALCULATE THE PRESSURE TREND AND SET THE PRESSURE TREND TEXT
    # --------------------------------------------------------------------------
	def PressureTrend(self):
	
		# Calculate timestamp three hours past
		TimeStart = self.Air['Obs'][0] - (3600*3+59)
		TimeEnd = self.Air['Obs'][0]

		# Download pressure data for last three hours
		Template = ("https://swd.weatherflow.com/swd/rest/observations/"
		            "device/{}?time_start={}&time_end={}&api_key={}")
		URL = Template.format(self.System['AirID'],TimeStart,TimeEnd,self.System['WFlowKey'])
		Data = requests.get(URL).json()['obs']
		Pres = [item[1] for item in Data]
		
		# Calculate pressure trend
		Trend = []
		Trend.append(Pres[-1]-Pres[0])
		Trend.append('mb')
			
		# Define Kivy label binds
		if Trend[0] >= 1:
			Trend.append("[color=ff8837ff]Rising[/color]")
		elif Trend[0] <= -1:
			Trend.append("[color=00a4b4ff]Falling[/color]")
		else:
			Trend.append("[color=9aba2fff]Steady[/color]")
		return Trend	

	# CALCULATE DAILY RAIN ACCUMULATION LEVELS
    # --------------------------------------------------------------------------
	def RainAccumulation(self):
		
		# Extract required meteorological fields
		Rain = self.Sky['Obs'][3]
		
		# Define current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		
		# Code initialising. Download all data for current day
		# using Weatherflow API. Calculate total daily rainfall
		if self.Sky['DayRain'][0] == '--':
		
			# Download data from current day
			Template = ("https://swd.weatherflow.com/swd/rest/observations/"
						"device/{}?day_offset=0&api_key={}")
			URL = Template.format(self.System['SkyID'],self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Rain = [item[3] if item[3] != None else NaN for item in Data]
			
			# Calculate daily rain accumulation
			self.Sky['DayRain'][0] = sum(Rain)
			self.Sky['DayRain'][1] = "{:2.1f}".format(self.Sky['DayRain'][0])
			self.Sky['DayRain'][2] = Now
			
		# Code initialising. Download all data for current month
		# using Weatherflow API. Calculate total monthly rainfall
		if self.Sky['MonthRain'][0] == '--':
		
			# Calculate timestamps for current month
			Time = datetime.utcfromtimestamp(self.Sky['Obs'][0])
			TimeStart = datetime(Time.year,Time.month,1)
			TimeStart = pytz.utc.localize(TimeStart)
			TimeStart = int(UNIX.mktime(TimeStart.timetuple()))
			TimeEnd = self.Sky['Obs'][0]

			# Download rainfall data for current month
			Template = ("https://swd.weatherflow.com/swd/rest/observations/"
		            "device/{}?time_start={}&time_end={}&api_key={}")
			URL = Template.format(self.System['SkyID'],TimeStart,TimeEnd,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Rain = [item[3] if item[3] != None else NaN for item in Data]

			# Calculate monthly rain accumulation
			self.Sky['MonthRain'][0] = sum(Rain)
			self.Sky['MonthRain'][1] = "{:3.0f}".format(self.Sky['MonthRain'][0])
			self.Sky['MonthRain'][2] = Now	
			
		# Code initialising. Download all data for current year
		# using Weatherflow API. Calculate total yearly rainfall
		if self.Sky['YearRain'][0] == '--':
		
			# Calculate timestamps for current year
			Time = datetime.utcfromtimestamp(self.Sky['Obs'][0])
			TimeStart = datetime(Time.year,1,1)
			TimeStart = pytz.utc.localize(TimeStart)
			TimeStart = int(UNIX.mktime(TimeStart.timetuple()))
			TimeEnd = self.Sky['Obs'][0]

			# Download rainfall data for current year
			Template = ("https://swd.weatherflow.com/swd/rest/observations/"
		            "device/{}?time_start={}&time_end={}&api_key={}")
			URL = Template.format(self.System['SkyID'],TimeStart,TimeEnd,self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Rain = [item[3] if item[3] != None else NaN for item in Data]

			# Calculate yearly rain accumulation
			self.Sky['YearRain'][0] = sum(Rain)
			self.Sky['YearRain'][1] = "{:3.0f}".format(self.Sky['YearRain'][0])
			self.Sky['YearRain'][2] = Now	
			return
			
		# At midnight, reset daily rainfall to zero, else add
		# current rainfall to current daily rainfall
		if Now.date() > self.Sky['DayRain'][2].date():
			self.Sky['DayRain'][0] = Rain
			self.Sky['DayRain'][1] = "{:2.1f}".format(self.Sky['DayRain'][0])
			self.Sky['DayRain'][2] = Now
		else:
			self.Sky['DayRain'][0] = self.Sky['DayRain'][0] + Rain
			self.Sky['DayRain'][1] = "{:2.1f}".format(self.Sky['DayRain'][0])
			self.Sky['DayRain'][2] = Now
		
		# At end of month, reset monthly rainfall to zero, else 
		# add current rainfall to current monthly rainfall
		if (Now.month > self.Sky['MonthRain'][2].month or 
			  Now.year  > self.Sky['MonthRain'][2].year):
			self.Sky['MonthRain'][0] = Rain
			self.Sky['MonthRain'][1] = "{:3.0f}".format(self.Sky['MonthRain'][0])
			self.Sky['MonthRain'][2] = Now
		else:
			self.Sky['MonthRain'][0] = self.Sky['MonthRain'][0] + Rain
			self.Sky['MonthRain'][1] = "{:3.0f}".format(self.Sky['MonthRain'][0])
			self.Sky['MonthRain'][2] = Now	
		
		# At end of year, reset yearly rainfall to zero, else 
		# add current rainfall to current yearly rainfall
		if Now.year > self.Sky['YearRain'][2].year:
			self.Sky['YearRain'][0] = Rain
			self.Sky['YearRain'][1] = "{:3.0f}".format(self.Sky['YearRain'][0])
			self.Sky['YearRain'][2] = Now
		else:
			self.Sky['YearRain'][0] = self.Sky['YearRain'][0] + Rain
			self.Sky['YearRain'][1] = "{:3.0f}".format(self.Sky['YearRain'][0])
			self.Sky['YearRain'][2] = Now	
		
	# CALCULATE MAXIMUM AND MINIMUM OBSERVED TEMPERATURE
	# --------------------------------------------------------------------------
	def AirObsMaxMin(self):

		# Extract required meteorological fields
		Time = self.Air['Obs'][0]
		Temp = [self.Air['Obs'][2],'c']
		Pres = [1050,'mb']

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

		# Code initialising. Download all data for current day using Weatherflow 
		# API. Extract maximum and minimum observed temperature and time
		if self.Air['MaxTemp'] == '---':
					
			# Download data from current day using Weatherflow  API and extract 
			# temperature, pressure and time data
			Template = 'https://swd.weatherflow.com/swd/rest/observations/device/{}?day_offset=0&api_key={}'
			URL = Template.format(self.System['AirID'],self.System['WFlowKey'])
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
			
		# At midnight, reset maximum and minimum temperature and pressure 
		# recorded by AIR module
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
			
	# CALCULATE MAXIMUM AND MINIMUM OBSERVED WEATHER PARAMETERS FROM SKY MODULE 
	# (WIND SPEED AND GUST STRENGTH)
	# --------------------------------------------------------------------------
	def SkyObsMaxMin(self):

		# Extract required meteorological fields
		Wind = self.Sky['Obs'][5] * 2.23694                   # Wind in mph
		Gust = self.Sky['Obs'][6] * 2.23694                   # Wind in mph
		
		# Define current time in station timezone
		Tz = self.System['tz']
		Now = datetime.now(pytz.utc).astimezone(Tz)	
		
		# Code initialising. Download all data for current day
		# using Weatherflow API. Extract maximum and minimum
		# observed temperature and time
		if self.Sky['MaxWind'] == '--':
		
			# Download data from current day using Weatherflow 
			# API and extract temperature and time data
			Template = ("https://swd.weatherflow.com/swd/rest/observations/"
			            "device/{}?day_offset=0&api_key={}")
			URL = Template.format(self.System['SkyID'],self.System['WFlowKey'])
			Data = requests.get(URL).json()['obs']
			Wind = [item[5]*2.23694 if item[5] != None else NaN for item in Data]
			Gust = [item[6]*2.23694 if item[6] != None else NaN for item in Data]
			
			# Define Kivy label binds
			self.Sky['MaxWind'] = "{:.1f}".format(max(Wind))
			self.Sky['MaxGust'] = "{:.1f}".format(max(Gust))
			self.Sky['MetDay'] = Now.date()
			return

		# At midnight, reset maximum recorded wind speed and gust
		if self.Sky['MetDay'] < Now.date():
			self.Sky['MaxWind'] = "{:.1f}".format(Wind)
			self.Sky['MaxGust'] = "{:.1f}".format(Gust)
			self.Sky['MetDay'] = Now.date()
			
		# Current wind speed is greater than maximum recorded
		# wind speed. Update maximum wind speed
		if Wind > float(self.Sky['MaxWind']):
			self.Sky['MaxWind'] = "{:.1f}".format(Wind)
			
		# Current gust is greater than maximum recorded gust. 
		# Update maximum gust	
		if Gust > float(self.Sky['MaxGust']):
			self.Sky['MaxGust'] = "{:.1f}".format(Gust)	
		
	# SET THE RAIN RATE TEXT
    # --------------------------------------------------------------------------
	def RainRate(self):
				
		# Extract required meteorological fields
		RainRate = self.Sky['Obs'][3] * 60
		
		# Define rain rate text
		if RainRate == 0:
			self.Sky['RainRateText'] = "Currently Dry"
		elif RainRate < 0.25:
			self.Sky['RainRateText'] = "Very Light Rain"
		elif RainRate < 1.0:
			self.Sky['RainRateText'] = "Light Rain"	
		elif RainRate < 4.0:
			self.Sky['RainRateText'] = "Moderate Rain"	
		elif RainRate < 16.0:
			self.Sky['RainRateText'] = "Heavy Rain"		
		elif RainRate < 50.0:
			self.Sky['RainRateText'] = "Very Heavy Rain"
		else:
			self.Sky['RainRateText'] = "Extreme Rain"
			
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
					
	# DEFINE COMPASS DIRECTION TEXT BASED ON SPECIFIED WIND DIRECTION BEARING
	# --------------------------------------------------------------------------
	def WindBearingToCompassDirec(self,Dir,Spd):
			
		# Define compass direction text with and without markup based on input
		# wind direction bearing
		if Spd == 0:
			CompassText_wMarkup = "[color=9aba2fff]Calm[/color]"
			CompassText = "N"
		elif float(Dir) <= 11.25:
			CompassText_wMarkup = "Due [color=9aba2fff]North[/color]"
			CompassText = "N"
		elif float(Dir) <= 33.75:
			CompassText_wMarkup = "North [color=9aba2fff]NE[/color]"
			CompassText = "NNE"
		elif float(Dir) <= 56.25:
			CompassText_wMarkup = "North [color=9aba2fff]East[/color]"
			CompassText = "NE"
		elif float(Dir) <= 78.75:
			CompassText_wMarkup = "East [color=9aba2fff]NE[/color]"
			CompassText = "ENE"
		elif float(Dir) <= 101.25:
			CompassText_wMarkup = "Due [color=9aba2fff]East[/color]"
			CompassText = "E"
		elif float(Dir) <= 123.75:
			CompassText_wMarkup = "East [color=9aba2fff]SE[/color]"
			CompassText = "ESE"
		elif float(Dir) <= 146.25:
			CompassText_wMarkup = "South [color=9aba2fff]East[/color]"
			CompassText = "SE"
		elif float(Dir) <= 168.75:
			CompassText_wMarkup = "South [color=9aba2fff]SE[/color]"
			CompassText = "SSE"
		elif float(Dir) <= 191.25:
			CompassText_wMarkup = "Due [color=9aba2fff]South[/color]"
			CompassText = "S"
		elif float(Dir) <= 213.75:
			CompassText_wMarkup = "South [color=9aba2fff]SW[/color]"
			CompassText = "SSW"
		elif float(Dir) <= 236.25:
			CompassText_wMarkup = "South [color=9aba2fff]West[/color]"
			CompassText = "SW"
		elif float(Dir) <= 258.75:
			CompassText_wMarkup = "West [color=9aba2fff]SW[/color]"
			CompassText = "WSW"
		elif float(Dir) <= 281.25:
			CompassText_wMarkup = "Due [color=9aba2fff]West[/color]"
			CompassText = "W"
		elif float(Dir) <= 303.75:
			CompassText_wMarkup = "West [color=9aba2fff]NW[/color]"
			CompassText = "WNW"
		elif float(Dir) <= 326.25:
			CompassText_wMarkup = "North [color=9aba2fff]West[/color]"
			CompassText = "NW"			
		elif float(Dir) <= 348.75:
			CompassText_wMarkup = "North [color=9aba2fff]NW[/color]"
			CompassText = "NNW"
		else:
			CompassText_wMarkup = "Due [color=9aba2fff]North[/color]"
			CompassText = "N"
			
		# Return compass direction text with and without markup
		return CompassText, CompassText_wMarkup
			
	# SET THE BEAUFORT SCALE WIND SPEED ICON AND TEXT
    # --------------------------------------------------------------------------
	def BeaufortScale(self):
	
		# Extract required meteorological fields
		Wind = self.Sky['Obs'][5] * 1.94384                      # Wind in knots
	
		# Define Beaufort Scale text and Icon
		if Wind <= 1:
			self.Sky['BeaufortIcon'] = "1kts"
			self.Sky['BeaufortText'] = "Calm Conditions"
		elif Wind <= 3:
			self.Sky['BeaufortIcon'] = "3kts"
			self.Sky['BeaufortText'] = "Light Air"
		elif Wind <= 6:
			self.Sky['BeaufortIcon'] = "6kts"
			self.Sky['BeaufortText'] = "Light Breeze"
		elif Wind <= 10:
			self.Sky['BeaufortIcon'] = "10kts"
			self.Sky['BeaufortText'] = "Gentle Breeze"
		elif Wind <= 16:
			self.Sky['BeaufortIcon'] = "16kts"
			self.Sky['BeaufortText'] = "Moderate Breeze"
		elif Wind <= 21:
			self.Sky['BeaufortIcon'] = "21kts"
			self.Sky['BeaufortText'] = "Fresh Breeze"
		elif Wind <= 27:
			self.Sky['BeaufortIcon'] = "27kts"
			self.Sky['BeaufortText'] = "Strong Breeze"
		elif Wind <= 33:
			self.Sky['BeaufortIcon'] = "33kts"
			self.Sky['BeaufortText'] = "Moderate Gale"
		elif Wind <= 40:
			self.Sky['BeaufortIcon'] = "40kts"
			self.Sky['BeaufortText'] = "Gale Force"
		elif Wind <= 47:
			self.Sky['BeaufortIcon'] = "47kts"
			self.Sky['BeaufortText'] = "Severe Gale"
		elif Wind <= 55:
			self.Sky['BeaufortIcon'] = "55kts"
			self.Sky['BeaufortText'] = "Storm Force"
		elif Wind <= 63:
			self.Sky['BeaufortIcon'] = "63kts"
			self.Sky['BeaufortText'] = "Violent Storm"
		else:
			self.Sky['BeaufortIcon'] = "71kts"
			self.Sky['BeaufortText'] = "Hurricane Force"
	
	# SET THE UV INDEX ICON
    # --------------------------------------------------------------------------
	def UVIndex(self):
	
		# Extract required meteorological fields
		UV = self.Sky['Obs'][2]  
	
		# Set the UV index icon
		if UV < 1:
			self.Sky['UVIcon'] = "0"
		elif 1 <= UV < 3:
			self.Sky['UVIcon'] = "1"
		elif 3 <= UV < 6:
			self.Sky['UVIcon'] = "2"
		elif 6 <= UV < 8:
			self.Sky['UVIcon'] = "3"
		elif 8 <= UV < 11:
			self.Sky['UVIcon'] = "4"
		else:
			self.Sky['UVIcon'] = "5"
			
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
		if self.SunData['Sunset'] == '--':
		
			# Convert midnight today in Station timezone to midnight 
			# today in UTC
			Date = date.today()
			Midnight = Tz.localize(datetime.combine(Date,time()))
			Midnight_UTC = Midnight.astimezone(pytz.utc)
			Ob.date = Midnight_UTC.strftime('%Y/%m/%d %H:%M:%S')
						
			# Sunrise time in station time zone
			Sunrise = Ob.next_rising(ephem.Sun())
			Sunrise = pytz.utc.localize(Sunrise.datetime())
			self.SunData['Sunrise'] = Sunrise.astimezone(Tz)

			# Sunset time in station time zone
			Sunset = Ob.next_setting(ephem.Sun())
			Sunset = pytz.utc.localize(Sunset.datetime())
			self.SunData['Sunset'] = Sunset.astimezone(Tz)
			
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
			self.SunData['Sunrise'] = Sunrise.astimezone(Tz)
			
			# Sunset time in station time zone
			Sunset = Ob.next_setting(ephem.Sun())
			Sunset = pytz.utc.localize(Sunset.datetime())
			self.SunData['Sunset'] = Sunset.astimezone(Tz)
			
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
		if self.MoonData['Moonrise'] == '--':
		
			# Convert midnight in Station timezone to midnight in UTC
			Date = date.today()
			Midnight = Tz.localize(datetime.combine(Date,time()))
			Midnight_UTC = Midnight.astimezone(pytz.utc)
			Ob.date = Midnight_UTC.strftime('%Y/%m/%d %H:%M:%S')
			
			# Calculate Moonrise time in Station time zone
			Moonrise = Ob.next_rising(ephem.Moon())
			Moonrise = pytz.utc.localize(Moonrise.datetime())
			self.MoonData['Moonrise'] = Moonrise.astimezone(Tz)
						
		# Moonset has passed. Calculate time of next moonrise in station 
		# timezone
		else:
		
			# Convert moonset time in Station timezone to moonset time in UTC
			Moonset = self.MoonData['Moonset'].astimezone(pytz.utc)
			Ob.date = Moonset.strftime('%Y/%m/%d %H:%M:%S')
			
			# Calculate Moonrise time in Station time zone
			Moonrise = Ob.next_rising(ephem.Moon())
			Moonrise = pytz.utc.localize(Moonrise.datetime())
			self.MoonData['Moonrise'] = Moonrise.astimezone(Tz)			
			
		# Convert Moonrise time in Station timezone to Moonrise time in UTC
		Moonrise = self.MoonData['Moonrise'].astimezone(pytz.utc)
		Ob.date = Moonrise.strftime('%Y/%m/%d %H:%M:%S')
		
		# Calculate time of next Moonset in station timezone based on current 
		# Moonrise time in UTC
		Moonset = Ob.next_setting(ephem.Moon())
		Moonset = pytz.utc.localize(Moonset.datetime())
		self.MoonData['Moonset'] = Moonset.astimezone(Tz)
			
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
		if datetime.now(self.System['tz']).date() == self.SunData['Sunrise'].date():
			self.SunData['SunriseTxt'] = self.SunData['Sunrise'].strftime("%H:%M")
			self.SunData['SunsetTxt'] = self.SunData['Sunset'].strftime("%H:%M")
		else:
			self.SunData['SunriseTxt'] = self.SunData['Sunrise'].strftime("%H:%M") + " (+1)"
			self.SunData['SunsetTxt'] = self.SunData['Sunset'].strftime("%H:%M") + " (+1)"
			
	# DEFINE SUNSET AND SUNRISE KIVY LABEL BINDS
	# --------------------------------------------------------------------------
	def MoonriseMoonsetText(self):
		
		# Define Moonrise kivy label bind based on date of next 
		# moonrise
		if datetime.now(self.System['tz']).date() == self.MoonData['Moonrise'].date():
			self.MoonData['MoonriseTxt'] = self.MoonData['Moonrise'].strftime("%H:%M")
		elif datetime.now(self.System['tz']).date() < self.MoonData['Moonrise'].date():
			self.MoonData['MoonriseTxt'] = self.MoonData['Moonrise'].strftime("%H:%M") + " (+1)"
		else:
			self.MoonData['MoonriseTxt'] = self.MoonData['Moonrise'].strftime("%H:%M") + " (-1)"
			
		# Define Moonset kivy label bind based on date of next
		# moonset
		if datetime.now(self.System['tz']).date() == self.MoonData['Moonset'].date():
			self.MoonData['MoonsetTxt'] = self.MoonData['Moonset'].strftime("%H:%M")
		elif datetime.now(self.System['tz']).date() < self.MoonData['Moonset'].date():
			self.MoonData['MoonsetTxt'] = self.MoonData['Moonset'].strftime("%H:%M") + " (+1)"
		else:
			self.MoonData['MoonsetTxt'] = self.MoonData['Moonset'].strftime("%H:%M") + " (-1)"	
			
	# CALCULATE THE SUN TRANSIT ANGLE AND THE TIME UNTIL SUNRISE OR SUNSET
	# --------------------------------------------------------------------------
	def SunTransit(self):
	
		# If time is between sunrise and sun set, calculate sun
		# transit angle
		if (datetime.now(self.System['tz']) >= self.SunData['Sunrise'] and 
		    datetime.now(self.System['tz']) <= self.SunData['Sunset']):
			
			# Determine total length of daylight, amount of daylight
			# that has passed, and amount of daylight left
			DaylightTotal = self.SunData['Sunset'] - self.SunData['Sunrise']
			DaylightLapsed = datetime.now(self.System['tz']) - self.SunData['Sunrise']
			DaylightLeft = self.SunData['Sunset'] - datetime.now(self.System['tz'])
			
			# Determine sun transit angle
			Angle = DaylightLapsed.total_seconds() / DaylightTotal.total_seconds() * 180
			Angle = int(Angle*10)/10.0
			
			# Determine hours and minutes left until sunset
			hours,remainder = divmod(DaylightLeft.total_seconds(), 3600)
			minutes,seconds = divmod(remainder,60)
			
			# Define Kivy Label binds
			self.SunData['SunAngle'] = "{:3.1f}".format(Angle)
			self.SunData['Event'] = "Till [color=f05e40ff]Sunset[/color]"
			self.SunData['EventHrs'] = "{:02.0f}".format(hours)
			self.SunData['EventMins'] = "{:02.0f}".format(minutes)

		# When not daylight, set sun transit angle to building
		# value. Define time until sunrise
		elif datetime.now(self.System['tz']) <= self.SunData['Sunrise']:
		
			# Determine hours and minutes left until sunrise
			NightLeft = self.SunData['Sunrise'] - datetime.now(self.System['tz'])
			hours,remainder = divmod(NightLeft.total_seconds(), 3600)
			minutes,seconds = divmod(remainder,60)
			
			# Define Kivy Label binds
			self.SunData['SunAngle'] = "--"
			self.SunData['Event'] = "Till [color=f0b240ff]Sunrise[/color]"
			self.SunData['EventHrs'] = "{:02.0f}".format(hours)
			self.SunData['EventMins'] = "{:02.0f}".format(minutes)		

	# CALCULATE THE PHASE OF THE MOON
	# --------------------------------------------------------------------------
	def MoonPhase(self):	
	
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
			self.MoonData['Icon'] = 'Waxing_' + "{:.0f}".format(Moon.phase)
		elif NewMoon < FullMoon:
			self.MoonData['Icon'] = 'Waning_' + "{:.0f}".format(Moon.phase)

		# Define Moon phase text
		if self.MoonData['NewMoon'] == '[color=ff8837ff]Today[/color]':
			self.MoonData['Phase'] = 'New Moon'
		elif self.MoonData['FullMoon'] == '[color=ff8837ff]Today[/color]':
			self.MoonData['Phase'] = 'Full Moon'	
		elif FullMoon < NewMoon and Moon.phase < 49:
			self.MoonData['Phase'] = 'Waxing crescent'
		elif FullMoon < NewMoon and 49 <= Moon.phase <= 51:
			self.MoonData['Phase'] = 'First Quarter'
		elif FullMoon < NewMoon and Moon.phase > 51:
			self.MoonData['Phase'] = 'Waxing gibbous'
		elif NewMoon < FullMoon and Moon.phase > 51:
			self.MoonData['Phase'] = 'Waning gibbous'
		elif NewMoon < FullMoon and 49 <= Moon.phase <= 51:
			self.MoonData['Phase'] = 'Last Quarter'
		elif NewMoon < FullMoon and Moon.phase < 49:
			self.MoonData['Phase'] = 'Waning crescent'	

		# Define Kivy labels
		self.MoonData['Illuminated'] = "{:.0f}".format(Moon.phase)	
			
	# DOWNLOAD THE LATEST FORECAST FOR STATION LOCATION
	# --------------------------------------------------------------------------
	def DownloadForecast(self):
	
		# If Station is located in Great Britain, download latest 
		# MetOffice three-hourly forecast
		if self.System['Country'] == 'GB':
			Template = ("http://datapoint.metoffice.gov.uk/public/data/"
						"val/wxfcs/all/json/{}?res=3hourly&key={}")
			URL = Template.format(self.System['MetOfficeID'],self.System['MetOfficeKey'])    
			self.MetDict = requests.get(URL).json()
			self.ExtractMetOfficeForecast()
			
		# If station is located outside of Great Britain, download the latest 
		# DarkSky hourly forecast
		else:
			Template = ("https://api.darksky.net/forecast/{}/{},{}?"
						"exclude=currently,minutely,alerts,flags&units=uk2")
			URL = Template.format(self.System['DarkSkyKey'],self.System['Lat'],self.System['Lon'])    
			self.MetDict = requests.get(URL).json()
			self.ExtractDarkSkyForecast()			
		
	# EXTRACT THE LATEST THREE-HOURLY METOFFICE FORECAST FOR THE STATION 
	# LOCATION
	# --------------------------------------------------------------------------
	def ExtractMetOfficeForecast(self):
	
		# Extract all forecast data from MetOffice JSON file. If 
		# forecast is unavailable, set forecast variables to blank 
		# and indicate to user that forecast is unavailable
		try:
			MetData = (self.MetDict['SiteRep']['DV']['Location']['Period'])
		except KeyError:
			self.MetData['Time'] = datetime.now(self.System['tz'])
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
		MetData = MetData[Dates.index(datetime.now(self.System['tz']).strftime("%Y-%m-%dZ"))]['Rep']
		
		# Extract "valid from" time of all available three-hourly forecasts, and 
		# retrieve forecast for the current three-hour period
		Times = list(int(item['$'])//60 for item in MetData)
		MetData = MetData[bisect.bisect(Times,datetime.now().hour)-1]
		
		# Extract "valid until" time for the retrieved forecast
		Valid = Times[bisect.bisect(Times,datetime.now(self.System['tz']).hour)-1] + 3
		if Valid == 24:
			Valid = 0
			
		# Extract weather variables from DarkSky forecast
		Temp = [float(MetData['T']),'c']
		WindDir = MetData['D']
		WindSpd = MetData['S']
		Weather = MetData['W']
		Precip = MetData['Pp']	
		
		# Convert forecast units as required
		Temp = self.ConvertObservationUnits(Temp,'Temp')
		
		# Define and format Kivy label binds
		self.MetData['Time'] = datetime.now(self.System['tz'])
		self.MetData['Issued'] = Issued
		self.MetData['Valid'] = "{:02.0f}".format(Valid) + ':00'	
		self.MetData['Temp'] = ["{:.1f}".format(Temp[0]),Temp[1]]
		self.MetData['WindDir'] = WindDir
		self.MetData['WindSpd'] = WindSpd
		self.MetData['Weather'] = Weather
		self.MetData['Precip'] = Precip

	# EXTRACT THE LATEST HOURLY DARK SKY FORECAST FOR THE STATION LOCATION
	# --------------------------------------------------------------------------
	def ExtractDarkSkyForecast(self):
		
		# Extract all forecast data from DarkSky JSON file. If 
		# forecast is unavailable, set forecast variables to blank 
		# and indicate to user that forecast is unavailable
		try:
			MetData = (self.MetDict['hourly']['data'])
		except KeyError:
			self.MetData['Time'] = datetime.now(self.System['tz'])
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
		
		# Extract "valid from" time of all available hourly forecasts, and 
		# retrieve forecast for the current hourly period
		Times = list(item['time'] for item in MetData)
		MetData = MetData[bisect.bisect(Times,int(UNIX.time()))-1]
		
		# Extract "Issued" and "Valid" times
		Issued = Times[0]
		Valid = Times[bisect.bisect(Times,int(UNIX.time()))]
		Issued = datetime.fromtimestamp(Issued,pytz.utc).astimezone(self.System['tz'])
		Valid = datetime.fromtimestamp(Valid,pytz.utc).astimezone(self.System['tz'])
		
		# Extract weather variables from DarkSky forecast
		Temp = [MetData['temperature'],'c']
		WindDir = MetData['windBearing']
		WindSpd = MetData['windSpeed']
		Weather = MetData['icon']
		Precip = MetData['precipProbability']*100	
		
		# Convert forecast units as required
		Temp = self.ConvertObservationUnits(Temp,'Temp')

		# Define and format Kivy label binds
		self.MetData['Time'] = datetime.now(self.System['tz'])
		self.MetData['Issued'] = datetime.strftime(Issued,'%H:%M')
		self.MetData['Valid'] = datetime.strftime(Valid,'%H:%M')
		self.MetData['Temp'] = ["{:.1f}".format(Temp[0]),Temp[1]]
		self.MetData['WindDir'] = self.WindBearingToCompassDirec(WindDir,1)[0]
		self.MetData['WindSpd'] = "{:.0f}".format(WindSpd)
		self.MetData['Precip'] = "{:.0f}".format(Precip)
		
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
		Hours_6 = (60*60*6)+60
			
		# Download Sky data from last 6 hours using Weatherflow API 
		# and extract observation times, wind speed, wind direction, 
		# and rainfall
		Template = ("https://swd.weatherflow.com/swd/rest/observations/"
		            "device/{}?time_start={}&time_end={}&api_key={}")
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
		Template = ("https://swd.weatherflow.com/swd/rest/observations/"
		            "device/{}?time_start={}&time_end={}&api_key={}")
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
		Template = "https://api.checkwx.com/metar/lat/{}/lon/{}/decoded"
		URL = Template.format(self.System['Lat'],self.System['Lon'])
		Data = requests.get(URL,headers=header).json()
		self.Sager['METAR'] = Data['data'][0]
	
		# Calculate Sager Weathercaster Forecast
		self.Sager['Dial'] = Sager.DialSetting(self.Sager)
		self.Sager['Forecast'] = Sager.Forecast(self.Sager['Dial'])
		self.Sager['Issued'] = datetime.now(self.System['tz']).strftime('%H:%M')
		
		# Determine time until generation of next Sager 
		# Weathercaster forecast
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
				self.Air['StatusIcon'] = "OK"
			
			# Latest AIR observation time is greater than 5 minutes old
			else:
				self.Air['StatusIcon'] = "Error"
			
		# Check latest Sky observation time is less than 5 minutes old
		if self.Sky['Obs'] != '--':
			SkyTime = datetime.fromtimestamp(self.Sky['Obs'][0],self.System['tz'])
			SkyDiff = (datetime.now(self.System['tz']) - SkyTime).total_seconds()
			if SkyDiff < 300:
				self.Sky['StatusIcon'] = "OK"
				
			# Latest Sky observation time is greater than 5 minutes old	
			else:
				self.Sky['StatusIcon'] = "Error"
	
	# UPDATE "WeatherFlowPiConsole" METHODS AT REQUIRED INTERVALS
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
		if Now > self.SunData['Sunset']:
			self.SunriseSunset()
			
		# If app is initialising or once moonset has passed, 
		# calculate new moonrise/moonset times
		if Now > self.MoonData['Moonset']:
			self.MoonriseMoonset()	

		# At midnight, update Sunset and Sunrise Label binds
		if Now.time() == time(0,0,0):
			self.SunriseSunsetText()
			self.MoonriseMoonsetText()
			
		# Update sun transit and moon phase icon
		self.SunTransit()
		self.MoonPhase()
		
# ==============================================================================
# DEFINE "WeatherFlowPiConsoleScreen" SCREEN MANAGER
# ==============================================================================			
class WeatherFlowPiConsoleScreen(ScreenManager):
    pass

# ==============================================================================
# DEFINE "CurrentConditions" SCREEN 
# ==============================================================================
class CurrentConditions(Screen):

	# Define Kivy properties required by "CurrentConditions" 
	Screen = DictProperty([('Clock','--'),('SunMoon','Sun'),
						   ('MetSager','Met'),
						   ('xRainAnim',476),('yRainAnim',3)])
					
	# INITIALISE "CurrentConditions" CLASS
	# --------------------------------------------------------------------------
	def __init__(self,**kwargs):
		super(CurrentConditions,self).__init__(**kwargs)
		Clock.schedule_interval(self.Clock,1.0)
		Clock.schedule_interval(self.RainRateAnimation,1/10)		
	
	# DEFINE DATE AND TIME FOR CLOCK IN STATION TIMEZONE
	# --------------------------------------------------------------------------
	def Clock(self,dt):
		Tz = App.get_running_app().System['tz']
		self.Screen['Clock'] = datetime.now(Tz).strftime("%a, %d %b %Y\n%H:%M:%S")
		
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
			self.ids.Forecast.source = "Buttons/Forecast_Pressed.png"
		elif ID == 'SunMoon':
			self.ids.SunMoon.source = "Buttons/SunMoon_Pressed.png"
		elif ID == 'Credits':
			self.ids.Credits.source = "Buttons/Credits_Pressed.png"
		
	# REMOVE BUTTON HIGHLIGHTING WHEN RELEASED
	# --------------------------------------------------------------------------
	def ButtonRelease(self,instance):
		if instance.text == 'Forecast':
			self.ids.Forecast.source = "Buttons/Forecast.png"
		elif instance.text == 'SunMoon':
			self.ids.SunMoon.source = "Buttons/SunMoon.png"
		elif instance.text == 'Credits':
			self.ids.Credits.source = "Buttons/Credits.png"
	
	# SHOW CREDITS POPUP 
	# --------------------------------------------------------------------------
	def ShowCredits(self,instance):
	
		# Highlight Credits button press
		self.ButtonPress(instance.text)
		
		# Open Credits popup
		Credits().open()	
		
# ==============================================================================
# DEFINE SCREENS
# ==============================================================================
class Forecast(Screen):
	pass
	
class Credits(Popup):
	pass	

# ==============================================================================
# RUN WeatherFlowPiConsole
# ==============================================================================
if __name__ == "__main__":
	log.startLogging(sys.stdout)
	WeatherFlowPiConsole().run()
