""" Defines the configuration .ini files required by the Raspberry Pi Python
console for Weather Flow Smart Home Weather Stations. 
Copyright (C) 2018-2019  Peter Davis

This program is free software: you can redistribute it and/or modify it under 
the terms of the GNU General Public License as published by the Free Software 
Foundation, either version 3 of the License, or (at your option) any later 
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY 
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A 
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with 
this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# Import required modules
import json
import math
import configparser
import requests
import collections
from packaging import version
from pathlib import Path
from geopy import distance as geopy

# Define wfpiconsole version number
Version = 'v2.6'

# Define required variables
stationWF = None
observationWF = None
GeoNames = None
MetOffice = None
NaN = float('NaN')

def create_ini():

	""" Generates a new user configuration file from the default configuration
	dictionary. Saves the new user configuration file to wfpiconsole.ini.
	"""

	# LOAD DEFAULT CONFIGURATION DICTIONARY
	# --------------------------------------------------------------------------
	Default = default_ini()

	# CONVERT DEFAULT CONFIGURATION DICTIONARY INTO .ini FILE
	# --------------------------------------------------------------------------
	print('Generating user configuration file..... ')
	Config = configparser.ConfigParser(allow_no_value=True)
	Config.optionxform = str
	for section in Default:
		Config.add_section(section)
		for key in Default[section]:
			write_keyValue(Config,section,key,Default[section][key])

	# WRITES USER CONFIGURATION FILE TO wfpiconsole.ini
	# --------------------------------------------------------------------------
	with open('wfpiconsole.ini','w') as configfile:
		Config.write(configfile)

def update_ini():

	""" Updates an existing user configuration file by comparing it against the
	default configuration dictionary. Saves the updated user configuration file
	to wfpiconsole.ini.
	"""

	# LOAD DEFAULT CONFIGURATION DICTIONARY
	# --------------------------------------------------------------------------
	Default = default_ini()
	Default_version = Default['System']['Version']['Value']

	# LOAD EXISTING USER CONFIGURATION FILE
	# --------------------------------------------------------------------------
	Exist = configparser.ConfigParser(allow_no_value=True)
	Exist.optionxform = str
	Exist.read('wfpiconsole.ini')
	Exist_version = Exist['System']['Version']
	
	# CREATE NEW CONFIG PARSER OBJECT TO HOLD UPDATED USER CONFIGURATION FILE
	# --------------------------------------------------------------------------
	New = configparser.ConfigParser(allow_no_value=True)
	New.optionxform = str

	# COMPARE EXISTING USER CONFIGURATION AGAINST DEFAULT CONFIGURATION. ADD NEW
	# KEYS WHERE REQUIRED
	# --------------------------------------------------------------------------
	if version.parse(Exist_version) < version.parse(Default_version):
		print('New version detected. Updating user configuration file..... ')
		for section in Default:
			New.add_section(section)
			for key in Default[section]:
				if Default[section][key]['Type'] in ['fixed']:
					New.set(section,key,Default[section][key]['Value'])
				if Exist.has_option(section,key):
					New.set(section,key,Exist[section][key])
				if not Exist.has_option(section,key,):
					write_keyValue(New,section,key,Default[section][key])
				elif key == 'Version':
					New.set(section,key,Default_version)
					print('    Updating version number to: ' + Default_version)

		# WRITE UPDATED USER .INI FILE TO DISK
		# ----------------------------------------------------------------------
		with open('wfpiconsole.ini','w') as configfile:
			New.write(configfile)


def write_keyValue(config,section,key,keyDetails):

	""" Gets and writes the key value pair to the specified section of the user
	configuration file, using the keyDetails to determine the key type
	"""

	# GET VALUE OF userInput KEY TYPE
	# --------------------------------------------------------------------------
	if keyDetails['Type'] in ['userInput']:
	
		# Get userInput key value
		while True:
			Value = input('    Please enter your ' + keyDetails['Desc'] + ' (' + keyDetails['State'] + '): ')
			if not Value and keyDetails['State'] == 'required':
				print('      ' + keyDetails['Desc'] + ' cannot be empty. Please try again..... ')
				continue
			elif not Value and keyDetails['State'] == 'optional':
				break
			try:
				Value = keyDetails['Format'](Value)
				break
			except ValueError:
				print('      ' + keyDetails['Desc'] + ' not valid. Please try again..... ')

		# Write userInput key value pair to configuration file
		config.set(section,key,str(Value))

	# GET VALUE OF dependent KEY TYPE
	# --------------------------------------------------------------------------
	elif keyDetails['Type'] in ['dependent']:
	
		# Get dependent key value
		if key in ['BarometerMax']:
			Units = ['mb','hpa','inhg','mmhg']
			Max = ['1050','1050','31.0','788']
			Value = Max[Units.index(config['Units']['Pressure'])]
		elif key in ['BarometerMin']:
			Units = ['mb','hpa','inhg','mmhg']
			Min = ['950','950','28.0','713']
			Value = Min[Units.index(config['Units']['Pressure'])]
		print('    Adding ' + keyDetails['Desc'] + ' (' + keyDetails['Type'] + '): ' + Value)

		# Write dependent key value pair to configuration file
		config.set(section,key,str(Value))

	# GET VALUE OF default OR fixed KEY TYPE
	# --------------------------------------------------------------------------	
	elif keyDetails['Type'] in ['default','fixed']:
	
		# Get default or fixed key value
		if key in ['ExtremelyCold','FreezingCold','VeryCold','Cold','Mild','Warm','Hot','VeryHot']:
			if 'c' in config['Units']['Temp']:
				Value = keyDetails['Value']
			elif 'f' in config['Units']['Temp']:
				Value = str(int(float(keyDetails['Value'])*9/5 + 32))
		else:
			Value = keyDetails['Value']
		
		# Write default or fixed key value pair to configuration file
		print('    Adding ' + keyDetails['Desc'] + ' (' + keyDetails['Type'] + '): ' + Value)
		config.set(section,key,str(Value))

	# GET VALUE OF request KEY TYPE
	# --------------------------------------------------------------------------
	elif keyDetails['Type'] in ['request']:

		# Define global variables
		global stationWF
		global observationWF
		global GeoNames
		global MetOffice

		# Ensure all necessary API keys have been provided
		if 'Country' in config['Station']:
			if not config['Keys']['MetOffice'] and not config['Keys']['DarkSky']:
				print('      MetOffice and DarkSky API keys cannot both be empty')
				if config['Station']['Country'] in ['GB']:
					while True:
						Value = input('      Station located in UK. Please enter your MetOffice API key (required): ')
						if not Value:
							print('      MetOffice API key cannot be empty. Please try again..... ')
							continue
						break
					config.set('Keys','MetOffice',str(Value))
				else:
					while True:
						Value = input('      Station located outside UK. Please enter your DarkSky API key (required): ')
						if not Value:
							print('      DarkSky API key cannot be empty. Please try again..... ')
							continue
						break
					config.set('Keys','DarkSky',str(Value))

		# Make Required API Requests
		if keyDetails['Source'] == 'stationWF' and stationWF is None:
			while True:
				Template = 'https://swd.weatherflow.com/swd/rest/stations/{}?api_key={}'
				URL = Template.format(config['Station']['StationID'],config['Keys']['WeatherFlow'])
				stationWF = requests.get(URL).json()
				if 'NOT FOUND' in stationWF['status']['status_message']:
					Value = input('      Station ID not recognised. Please re-enter your Station ID (required): ')
					config.set('Station','StationID',str(Value))
					continue
				elif 'SUCCESS' in stationWF['status']['status_message']:
					break
		elif keyDetails['Source'] == 'observationWF' and observationWF is None:
			Template = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?api_key={}'
			URL = Template.format(config['Station']['StationID'],config['Keys']['WeatherFlow'])
			observationWF = requests.get(URL).json()
		elif keyDetails['Source'] == 'GeoNames' and GeoNames is None:
			Template = 'http://api.geonames.org/findNearbyPlaceName?lat={}&lng={}&username={}&radius=10&featureClass=P&maxRows=20&type=json'
			URL = Template.format(config['Station']['Latitude'],config['Station']['Longitude'],config['Keys']['GeoNames'])
			GeoNames = requests.get(URL).json()
		elif keyDetails['Source'] == 'MetOffice' and MetOffice is None and config['Station']['Country'] in ['GB']:
			Template = 'http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/json/sitelist?&key={}'
			URL = Template.format(config['Keys']['MetOffice'])
			MetOffice = requests.get(URL).json()

		# Get request key value from relevant API request
		if section in ['Station']:
			if key in ['OutdoorHeight']:
				Value = None
				while True:
					for Dev in stationWF['stations'][0]['devices']:
						if 'device_type' in Dev:
							if str(Dev['device_id']) == config['Station']['OutdoorID']:
								Value = Dev['device_meta']['agl']
					if Value is None:
						while True:
							ID = input('      Outdoor module ID not found. Please re-enter your Outdoor module ID: ')
							if not ID:
								print('      Outdoor module ID cannot be empty. Please try again..... ')
								continue
							try:
								ID = int(ID)
								break
							except ValueError:
								print('      Outdoor module ID not valid. Please try again..... ')
						config.set('Station','OutdoorID',str(ID))
					else:
						break
			elif key in ['SkyHeight']:
				Value = None
				while True:
					for Dev in stationWF['stations'][0]['devices']:
						if 'device_type' in Dev:
							if str(Dev['device_id']) == config['Station']['SkyID']:
								Value = Dev['device_meta']['agl']
					if Value is None:
						while True:
							ID = input('      Sky module ID not found. Please re-enter your Sky module ID: ')
							if not ID:
								print('      Sky module ID cannot be empty. Please try again..... ')
								continue
							try:
								ID = int(ID)
								break
							except ValueError:
								print('      Sky module ID not valid. Please try again..... ')
						config.set('Station','SkyID',str(ID))
					else:
						break
			elif key in ['ForecastLocn','MetOfficeID']:
				if config['Station']['Country'] in ['GB']:
					MinDist = math.inf
					for Locn in MetOffice['Locations']['Location']:
						ForecastLocn = (float(Locn['latitude']),float(Locn['longitude']))
						StationLocn = (float(config['Station']['Latitude']),float(config['Station']['Longitude']))
						LatDiff = abs(StationLocn[0] - ForecastLocn[0])
						LonDiff = abs(StationLocn[1] - ForecastLocn[1])
						if (LatDiff and LonDiff) < 0.5:
							Dist = geopy.distance(StationLocn,ForecastLocn).km
							if Dist < MinDist:
								MinDist = Dist
								if key in ['ForecastLocn']:
									Value = Locn['name']
								elif key in ['MetOfficeID']:
									Value = Locn['id']
				else:
					if key in ['ForecastLocn']:
						Locns = [Item['name'] for Item in GeoNames['geonames']]
						Len = [len(Item) for Item in Locns]
						Ind = next((Item for Item in Len if Item<=20),NaN)
						if Ind != NaN:
							Value = Locns[Len.index(Ind)]
						else:
							Value = ''
					elif key in ['MetOfficeID']:
						Value = ''
			elif key in ['Latitude','Longitude']:
				Value = stationWF['stations'][0][key.lower()]
			elif key in ['Timezone']:
				Value = stationWF['stations'][0]['timezone']
			elif key in ['Elevation']:
				Value = stationWF['stations'][0]['station_meta']['elevation']
			elif key in ['Country']:
				Value = GeoNames['geonames'][0]['countryCode']
		elif section in ['Units']:
			Value = observationWF['station_units']['units_' + key.lower()]

		# Write request key value pair to configuration file
		print('    Adding ' + keyDetails['Desc'] + ' (API request): ' + str(Value))
		config.set(section,key,str(Value))

def default_ini():

	""" Generates the default configuration required by the Raspberry Pi Python
	console for Weather Flow Smart Home Weather Stations.
	"""

	# DEFINE DEFAULT CONFIGURATION SECTIONS, KEY NAMES, AND KEY DETAILS AS 
	# ORDERED DICTS
	# --------------------------------------------------------------------------
	Default = 				collections.OrderedDict()
	Default['Keys'] =  		collections.OrderedDict([('GeoNames',		{'Type': 'userInput', 'State': 'required', 'Format': str, 'Desc': 'GeoNames API key'}),
													 ('MetOffice', 		{'Type': 'userInput', 'State': 'optional', 'Format': str, 'Desc': 'UK MetOffice API key'}),
													 ('DarkSky', 		{'Type': 'userInput', 'State': 'optional', 'Format': str, 'Desc': 'DarkSky API key',}),
													 ('CheckWX', 		{'Type': 'userInput', 'State': 'required', 'Format': str, 'Desc': 'CheckWX API key',}),
													 ('WeatherFlow',	{'Type': 'fixed', 'Value': '146e4f2c-adec-4244-b711-1aeca8f46a48', 'Desc': 'WeatherFlow API key'})])
	Default['Station'] =   	collections.OrderedDict([('StationID',		{'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'Station ID'}),
													 ('OutdoorID', 		{'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'outdoor Air module ID'}),
													 ('SkyID', 			{'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'outdoor Sky module ID'}),
													 ('OutdoorHeight',	{'Type': 'request', 'Source': 'stationWF', 'Desc': 'height of outdoor Air module'}),
													 ('SkyHeight', 		{'Type': 'request', 'Source': 'stationWF', 'Desc': 'height of outdoor Sky module'}),
													 ('Latitude',		{'Type': 'request', 'Source': 'stationWF', 'Desc': 'station latitude'}),
													 ('Longitude', 		{'Type': 'request', 'Source': 'stationWF', 'Desc': 'station longitude'}),
													 ('Elevation', 		{'Type': 'request', 'Source': 'stationWF', 'Desc': 'station elevation'}),
													 ('Timezone', 		{'Type': 'request', 'Source': 'stationWF', 'Desc': 'station timezone'}),
													 ('Country', 		{'Type': 'request', 'Source': 'GeoNames',  'Desc': 'station country'}),
													 ('ForecastLocn', 	{'Type': 'request', 'Source': 'MetOffice', 'Desc': 'station forecast location'}),
													 ('MetOfficeID', 	{'Type': 'request', 'Source': 'MetOffice', 'Desc': 'station forecast ID'})])
	Default['Units'] = 		collections.OrderedDict([('Temp',			{'Type':'request',  'Source': 'observationWF', 'Desc': 'station temperature units'}),
													 ('Pressure',		{'Type': 'request', 'Source': 'observationWF', 'Desc': 'station pressure units'}),
													 ('Wind',			{'Type': 'request', 'Source': 'observationWF', 'Desc': 'station wind units'}),
													 ('Direction',		{'Type': 'request', 'Source': 'observationWF', 'Desc': 'station direction units'}),
													 ('Precip',			{'Type': 'request', 'Source': 'observationWF', 'Desc': 'station precipitation units'}),
													 ('Distance',		{'Type': 'request', 'Source': 'observationWF', 'Desc': 'station distance units'}),
													 ('Other',			{'Type': 'request', 'Source': 'observationWF', 'Desc': 'station other units'})])
	Default['Display'] =  	collections.OrderedDict([('TimeFormat',		{'Type': 'default', 'Value': '24 hr', 'Desc': 'time format'}),
													 ('DateFormat',		{'Type': 'default', 'Value': 'Mon, 01 Jan 0000', 'Desc': 'date format'}),
													 ('LightningPanel',	{'Type': 'default', 'Value': '1', 'Desc': 'lightning panel'})])
	Default['FeelsLike'] = 	collections.OrderedDict([('ExtremelyCold',	{'Type': 'default', 'Value': '-4', 'Desc': '"Feels extremely" cold cut-off temperature'}),
													 ('FreezingCold',	{'Type': 'default', 'Value': '0',  'Desc': '"Feels freezing" cold cut-off temperature'}),
													 ('VeryCold',		{'Type': 'default', 'Value': '4',  'Desc': '"Feels very cold" cut-off temperature'}),
													 ('Cold',			{'Type': 'default', 'Value': '9',  'Desc': '"Feels cold" cut-off temperature'}),
													 ('Mild',			{'Type': 'default', 'Value': '14', 'Desc': '"Feels mild" cut-off temperature'}),
													 ('Warm',			{'Type': 'default', 'Value': '18', 'Desc': '"Feels warm" cut-off temperature'}),
													 ('Hot',			{'Type': 'default', 'Value': '23', 'Desc': '"Feels hot" cut-off temperature'}),
													 ('VeryHot',		{'Type': 'default', 'Value': '28', 'Desc': '"Feels very hot" cut-off temperature'})])
	Default['System'] =    	collections.OrderedDict([('BarometerMax',	{'Type': 'dependent', 'Desc': 'maximum barometer pressure'}),
													 ('BarometerMin',	{'Type': 'dependent', 'Desc': 'minimum barometer pressure'}),
													 ('Version',		{'Type': 'default',   'Value': Version, 'Desc': 'Version number'})])								 
	return Default

def settings_json(Section):

	if 'Display' in Section:
		Data = 	[
				 {'type':'FixedOptions', 'options':['24 hr','12 hr'],
				  'title':'Time format', 'desc':'Set time to display in 12 hr or 24 hr format', 'section':'Display', 'key':'TimeFormat'},
				 {'type':'FixedOptions', 'options':['Mon, 01 Jan 0000','Mon, Jan 01 0000','Monday, 01 Jan 0000','Monday, Jan 01 0000'],
				  'title':'Date format', 'desc':'Set date format', 'section':'Display', 'key':'DateFormat'},
				 {'type': 'bool', 'desc': 'Open the lightning panel automatically when a strike is detected', 
				  'title': 'Lightning panel','section': 'Display', 'key': 'LightningPanel'}]
	elif 'Units' in Section:
		Data = 	[
				 {'type':'FixedOptions', 'options':['c','f'],'title':'Temperature', 
				  'desc':'Set console temperature units', 'section':'Units', 'key':'Temp'},
				 {'type':'FixedOptions', 'options':['inhg','mmhg','hpa','mb'],'title':'Pressure', 
				  'desc':'Set console pressure units', 'section':'Units', 'key':'Pressure'}, 
				 {'type':'ScrollOptions', 'options':['mph','kph','kts','bft','mps','lfm'],'title':'Wind speed', 
				  'desc':'Set console wind speed units', 'section':'Units', 'key':'Wind'},
				 {'type':'FixedOptions', 'options':['degrees','cardinal'],'title':'Wind direction', 
				  'desc':'Set console wind direction units', 'section':'Units', 'key':'Direction'},	
				 {'type':'FixedOptions', 'options':['in','cm','mm'],'title':'Rainfall', 
				  'desc':'Set console rainfall units', 'section':'Units', 'key':'Precip'},
				 {'type':'FixedOptions', 'options':['km','mi'],'title':'Distance', 
				  'desc':'Set console distance units', 'section':'Units', 'key':'Distance'},
				 {'type':'FixedOptions', 'options':['metric','imperial'],'title':'Other', 
				  'desc':'Set console other units', 'section':'Units', 'key':'Other'}
				]

	elif 'FeelsLike' in Section:
		Data = 	[
				 {'type':'ToggleTemperature', 'title':'Extremely Cold',
				  'desc':'Set the maximum cut-off temperature for "Feeling extremely cold"', 'section':'FeelsLike', 'key':'ExtremelyCold'},
				 {'type':'ToggleTemperature', 'title':'Freezing Cold',
				  'desc':'Set the maximum cut-off temperature for "Feeling freezing cold"', 'section':'FeelsLike', 'key':'FreezingCold'},
				 {'type':'ToggleTemperature', 'title':'Very Cold',
				  'desc':'Set the maximum cut-off temperature for "Feeling very cold"', 'section':'FeelsLike', 'key':'VeryCold'},
				 {'type':'ToggleTemperature', 'title':'Cold',
				  'desc':'Set the maximum cut-off temperature for "Feeling cold"', 'section':'FeelsLike', 'key':'Cold'},
				 {'type':'ToggleTemperature', 'title':'Mild',
				  'desc':'Set the maximum cut-off temperature for "Feeling mild"', 'section':'FeelsLike', 'key':'Mild'},
				 {'type':'ToggleTemperature', 'title':'Warm',
				  'desc':'Set the maximum cut-off temperature for "Feeling warm"', 'section':'FeelsLike', 'key':'Warm'},
				 {'type':'ToggleTemperature', 'title':'Hot',
				  'desc':'Set the maximum cut-off temperature for "Feeling hot"', 'section':'FeelsLike', 'key':'Hot'},
				 {'type':'ToggleTemperature', 'title':'Very Hot',
				  'desc':'Set the maximum cut-off temperature for "Feeling very hot"', 'section':'FeelsLike', 'key':'VeryHot'}
				]

	return json.dumps(Data)