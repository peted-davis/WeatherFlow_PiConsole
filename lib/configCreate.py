""" Defines the configuration .ini files required by the Raspberry Pi Python 
console for Weather Flow Smart Home Weather Stations. 
Copyright (C) 2018  Peter Davis
"""

import json
import configparser
from packaging import version
from pathlib import Path

def default_ini():

	""" Generates the default configuration required by the Raspberry Pi Python 
	console for Weather Flow Smart Home Weather Stations.
	"""

	# DEFINE DEFAULT CONFIGURATION
	# --------------------------------------------------------------------------
	Default = {}
	Default['Keys'] = {'GeoNames': ['required','GeoNames API key',str],
					   'MetOffice': ['optional','UK MetOffice API key',str],
					   'DarkSky': ['optional','DarkSky API key',str],
					   'CheckWX': ['required','CheckWX API key',str]}
	Default['Station'] = {'StationID': ['required','Station ID',int],
						  'OutdoorID': ['required','Outdoor module ID',int],
						  'IndoorID': ['optional','Indoor module ID',int],
						  'SkyID': ['required','Sky module ID',int]}
	Default['Settings'] = {'TimeFormat':['24hr','Time format']}					  
	Default['System'] = {'WFKey': ['146e4f2c-adec-4244-b711-1aeca8f46a48','WeatherFlow API key'],
						 'Version': ['1.8','Version number']}
	return Default

def create_ini():

	""" Generates the user configuration .ini file required by the Raspberry Pi 
	Python console for Weather Flow Smart Home Weather Stations. Default options 
	customised based on requested user input. Saves the user configuration .ini
	file to wfpiconsole.ini
	"""

	# LOAD DEFAULT CONFIGURATION DICTIONARY
	# --------------------------------------------------------------------------
	Default = default_ini()

	# CONVERT DEFAULT CONFIGURATION DICTIONARY INTO .ini FILE REQUESTING USER 
	# INPUT WHERE REQUIRED
	# --------------------------------------------------------------------------
	print('Generating user configuration file..... ')
	Config = configparser.ConfigParser(allow_no_value=True)
	Config.optionxform = str
	for section in Default:
		Config.add_section(section)
		for key in Default[section]:
			write_key(Config,section,key,Default[section][key])

	# WRITES USER .INI FILE TO DISK
	# --------------------------------------------------------------------------
	with open('wfpiconsole.ini','w') as configfile:
		Config.write(configfile)

def update_ini():

	""" Updates the existing user configuration .ini file required by the 
	Raspberry Pi Python console for Weather Flow Smart Home Weather Stations. 
	Compares the existing user configuration .ini file against the default 
	configuration dictionary, adding keys where required. User input requested
	where needed. The updated user configuration .ini file is saved to 
	wfpiconsole.ini
	"""	

	# LOAD DEFAULT CONFIGURATION DICTIONARY
	# --------------------------------------------------------------------------
	Default = default_ini()
	Default_version = Default['System']['Version'][0]
		
	# LOAD EXISTING USER CONFIGURATION FILE
	# --------------------------------------------------------------------------
	User = configparser.ConfigParser(allow_no_value=True)
	User.optionxform = str
	User.read('wfpiconsole.ini')
	User_version = User['System']['Version']
		
	# COMPARE DEFAULT CONFIGURATION WITH EXISTING USER CONFIGURATION
	# --------------------------------------------------------------------------
	if version.parse(User_version) < version.parse(Default_version):
		print('Updating user configuration file..... ')
		Changes = False
		for section in Default:
			if not User.has_section(section):
				User.add_section(section)
				Changes = True
			for key in Default[section]:
				if not User.has_option(section,key):
					write_key(User,section,key,Default[section][key])
					Changes = True
				elif key == 'Version':
					User.set(section,key,Default_version)
					print('    Updating version number')		
		if not Changes:
			print('    No further changes required')
				
		# WRITE UPDATED USER .INI FILE TO DISK
		# ----------------------------------------------------------------------
		with open('wfpiconsole.ini','w') as configfile:
			User.write(configfile)	

def write_key(config,section,key,details):

	""" Writes key value to specified section of the configuration file. Uses 
	the key details to determine key type and whether user input is required to 
	define the key value.
	"""

	# WRITES KEY TO CONFIGURATION FILE
	# --------------------------------------------------------------------------
	if details[0] in ['required','optional']:
		while True:
			Value = input('    Please enter your ' + details[1] + ' (' + details[0] + '): ')
			if not Value and details[0] == 'required':
				print('      ' + details[1] + ' cannot be empty. Please try again..... ')
				continue
			elif not Value and details[0] == 'optional':
				break
			try: 
				Value = details[2](Value)
				break
			except ValueError:
				print('      ' + details[1] + ' not valid. Please try again..... ')
	else:
		print('    Adding ' + details[1])
		Value = details[0]
	config.set(section,key,str(Value))	
		
def settings_json():

	data = [{'type':'title','title':'Time and date'},
			{'type':'scrolloptions','options':['24h','12h'],'title':'Time format','desc':'Set time format to 12 hr or 24 hr',"section": "Settings","key": "TimeFormat"}]
	parsed = json.dumps(data)
	return parsed
		
		
		
		
		
		