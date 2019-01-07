""" Defines the configuration .ini files required by the Raspberry Pi Python
console for Weather Flow Smart Home Weather Stations.
Copyright (C) 2018  Peter Davis
"""

# Import required modules
import json
import math
import configparser
import requests
from packaging import version
from pathlib import Path
from geopy import distance as geopy

# Define wfpiconsole version number
Version = 'v1.24'

# Define required variables
stationWF = None
observationWF = None
GeoNames = None
MetOffice = None

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
	User = configparser.ConfigParser(allow_no_value=True)
	User.optionxform = str
	User.read('wfpiconsole.ini')
	User_version = User['System']['Version']

	# COMPARE EXISTING USER CONFIGURATION AGAINST DEFAULT CONFIGURATION AND ADD 
	# ALL NEW KEYS
	# --------------------------------------------------------------------------
	if version.parse(User_version) < version.parse(Default_version):
		print('New version detected. Updating user configuration file..... ')
		Changes = False
		for section in Default:
			if not User.has_section(section):
				User.add_section(section)
				Changes = True
			for key in Default[section]:
				if not User.has_option(section,key):
					write_keyValue(User,section,key,Default[section][key])
					Changes = True
				elif Default[section][key]['Type'] in ['fixed']:
					User.set(section,key,Default[section][key]['Value'])
				elif key == 'Version':
					User.set(section,key,Default_version)
					print('    Updating version number to: ' + Default_version)
		
		# COMPARE DEFAULT CONFIGURATION AGAINST EXISTING USER CONFIGURATION AND 
		# REMOVE ALL UNNECESSARY KEYS
		# ----------------------------------------------------------------------
		del_sections = []
		for section in User:
			if not section in Default:
				del_sections.append(section)
		for section in del_sections:
			User.remove_section(section)
		for section in User:		
			for key in User[section]:
				if not key in Default[section]:
					User.remove_option(section,key)
		if not Changes:
			print('    No further changes required')

		# WRITE UPDATED USER .INI FILE TO DISK
		# ----------------------------------------------------------------------
		with open('wfpiconsole.ini','w') as configfile:
			User.write(configfile)


def write_keyValue(config,section,key,keyDetails):

	""" Gets and writes the key value pair to the specified section of the user
	configuration file, using the keyDetails to determine the key type
	"""

	# GET VALUE OF userInput KEY TYPE
	# --------------------------------------------------------------------------
	# Get userInput key value
	if keyDetails['Type'] in ['userInput']:
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
	# Get dependent key value
	elif keyDetails['Type'] in ['dependent']:
		if section in ['System']:
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
	# Get default or fixed key value
	elif keyDetails['Type'] in ['default','fixed']:
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

		# Make Required Api Requests
		if keyDetails['Source'] == 'stationWF' and stationWF is None:
			Template = 'https://swd.weatherflow.com/swd/rest/stations/{}?api_key={}'
			URL = Template.format(config['Station']['StationID'],config['Keys']['WeatherFlow'])
			stationWF = requests.get(URL).json()
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
							ID = input('      Outdoor module ID not found in station. Please re-enter: ')
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
							ID = input('      Sky module ID not found in station. Please re-enter: ')
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
						Ind = next((Item for Item in Len if Item<=11),NaN)
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

	# DEFINE DEFAULT CONFIGURATION SECTIONS, KEY NAMES, AND KEY DETAILS
	# --------------------------------------------------------------------------
	Default = {}
	Default['Keys'] =  	   {'GeoNames': 	{'Type': 'userInput', 'State': 'required', 'Format': str, 'Desc': 'GeoNames API key'},
							'MetOffice': 	{'Type': 'userInput', 'State': 'optional', 'Format': str, 'Desc': 'UK MetOffice API key'},
							'DarkSky': 		{'Type': 'userInput',
											 'State': 'optional',
											 'Desc': 'DarkSky API key',
											 'Format': str},
							'CheckWX': 		{'Type': 'userInput',
											 'State': 'required',
											 'Desc': 'CheckWX API key',
											 'Format': str},
							'WeatherFlow': 	{'Type': 'fixed',
											 'Value': '146e4f2c-adec-4244-b711-1aeca8f46a48',
											 'Desc': 'WeatherFlow API key'}}
	Default['Station'] =   {'StationID': 	{'Type': 'userInput',
											 'State': 'required',
											 'Desc': 'Station ID',
											 'Format': int},
							'OutdoorID': 	{'Type': 'userInput',
											 'State': 'required',
											 'Desc': 'Outdoor module ID',
											 'Format': int},
							'IndoorID': 	{'Type': 'userInput',
											 'State': 'optional',
											 'Desc': 'Indoor module ID',
											 'Format': int},
							'SkyID': 		{'Type': 'userInput',
											 'State': 'required',
											 'Desc': 'Sky module ID',
											 'Format': int},
							'OutdoorHeight':{'Type': 'request',
											 'Source': 'stationWF',
											 'Desc': 'height of Outdoor module'},
							'SkyHeight': 	{'Type': 'request',
											 'Source': 'stationWF',
											 'Desc': 'height of Sky module'},
							'Latitude': 	{'Type': 'request',
											 'Source': 'stationWF',
											 'Desc': 'station latitude'},
							'Longitude': 	{'Type': 'request',
											 'Source': 'stationWF',
											 'Desc': 'station longitude'},
							'Elevation': 	{'Type': 'request',
											 'Source': 'stationWF',
											 'Desc': 'station elevation'},
							'Timezone': 	{'Type': 'request',
										     'Source': 'stationWF',
											 'Desc': 'station timezone'},
							'Country': 		{'Type': 'request',
											 'Source': 'GeoNames',
											 'Desc': 'station country'},
							'ForecastLocn': {'Type': 'request',
											 'Source': 'MetOffice',
											 'Desc': 'station forecast location'},
							'MetOfficeID': 	{'Type': 'request',
											 'Source': 'MetOffice',
											 'Desc': 'station forecast ID'}}
	Default['Units'] = 	   {'Temp':			{'Type':'request',
											 'Source': 'observationWF',
											 'Desc': 'station temperature units'},
							'Wind':			{'Type': 'request',
											 'Source': 'observationWF',
											 'Desc': 'station wind units'},
							'Precip':		{'Type': 'request',
											 'Source': 'observationWF',
											 'Desc': 'station precipitation units'},
							'Pressure':		{'Type': 'request',
											 'Source': 'observationWF',
											 'Desc': 'station pressure units'},
							'Distance':		{'Type': 'request',
											 'Source': 'observationWF',
											 'Desc': 'station distance units'},
							'Direction':	{'Type': 'request',
											 'Source': 'observationWF',
											 'Desc': 'station direction units'},
							'Other':		{'Type': 'request',
											 'Source': 'observationWF',
											 'Desc': 'station other units'}}
	Default['Settings'] =  {'TimeFormat':	{'Type': 'default',
											 'Value': '24 hr',
											 'Desc': 'time format'},
							'DateFormat':	{'Type': 'default',
											 'Value': 'Mon, 01 Jan 0000',
											 'Desc': 'date format'}}
	Default['System'] =    {'BarometerMax':	{'Type': 'dependent',
											 'Desc': 'maximum barometer pressure'},
							'BarometerMin':	{'Type': 'dependent',
											 'Desc': 'minimum barometer pressure'},
							'Version': 		{'Type': 'default',
											 'Value': Version,
											 'Desc': 'Version number'}}
	return Default

def settings_json():

	data = 	[
			{'type':'title',
			 'title':'Time and date'},

			{'type':'fixedoptions',
			 'options':['24 hr','12 hr','test'],
			 'title':'Time format',
			 'desc':'Set time to display in 12 hr or 24 hr format',
			 'section':'Settings',
			 'key':'TimeFormat'},

			{'type':'scrolloptions',
			 'options':['Mon, 01 Jan 0000','Mon, Jan 01 0000','Monday, 01 Jan 0000','Monday, Jan 01 0000'],
			 'title':'Date format',
			 'desc':'Set date format',
			 'section':'Settings',
			 'key':'DateFormat'},

			 {'type':'title',
			  'title':'Feels Like temperature'},
			]
	return json.dumps(data)