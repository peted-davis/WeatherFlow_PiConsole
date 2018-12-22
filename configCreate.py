""" Defines the configuration .ini files required by the Raspberry Pi Python 
console for Weather Flow Smart Home Weather Stations. 
Copyright (C) 2018  Peter Davis
"""

import configparser
from pathlib import Path

def default_ini():

	""" Generates the default configuration required by the Raspberry Pi Python 
	console for Weather Flow Smart Home Weather Stations.
	"""
	
	# DEFINE DEFAULT CONFIGURATION
	# --------------------------------------------------------------------------
	Default = {}
	Default['Keys'] = {'GeoNames': ['required',str,'GeoNames API key'],
					   'MetOffice': ['optional',str,'UK MetOffice API key'],
					   'DarkSky': ['optional',str,'DarkSky API key'],
					   'CheckWX': ['required',str,'CheckWX API key']}
	Default['Station'] = {'StationID': ['required',int,'Station ID'],
						  'OutdoorID': ['optional',int,'Outdoor module ID'],
						  'IndoorID': ['optional',int,'Indoor module ID'],
						  'SkyID': ['optional',int,'Sky module ID']}		
	Default['System'] = {'WFKey': '146e4f2c-adec-4244-b711-1aeca8f46a48',
						 'Version': '1.8'}
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
	Config = configparser.ConfigParser(allow_no_value=True)
	Config.optionxform = str
	for section in Default:
		Config.add_section(section)
		for key in Default[section]:
			if Default[section][key][0] in ['required','optional']:
				while True:
					Value = input('Please enter your ' + Default[section][key][2] + 
					              ' (' + Default[section][key][0] + '): ')
					if not Value and Default[section][key][0] == 'required':
						print(Default[section][key][2] + ' cannot be empty. Please try again..... ')
						continue
					elif not Value and Default[section][key][0] == 'optional':
						break
					try: 
						Value = Default[section][key][1](Value)
						break
					except ValueError:
						print(Default[section][key][2] + ' not valid. Please try again..... ')
			else:
				Value = Default[section][key]
			Config.set(section,key,str(Value))
				
		
		
		
		
		
		
		
		
			# # Generate configuration section for API keys
			# if section == 'Keys' and key in ['GeoNames','CheckWX']:
				# while True:
					# print('Please enter ' + key + ' API key (required):')
					# Value = input()
					# if not Value:
						# print(key + ' API key cannot be empty. Try again.... ')
					# else:
						# Config.set(section,key,Value)
						# print()
						# break
			# elif section == 'Keys' and key in ['MetOffice','DarkSky']:
				# print('Please enter ' + key + ' API key (optional):')
				# Value = input()
				# Config.set(section,key,Value)
				# print()
				
			# # Generate configuration section for station/module keys
			# elif section == 'Station' and key in ['StationID']:
				# while True:
					# try:
						# print('Please enter your station ID (required):')
						# Value = input()
						# if not Value:
							# print('Station ID cannot be empty. Try again.... ')
						# else:
							# Value = str(int(Value))
							# Config.set(section,key,Value)
							# print()
							# break							
					# except ValueError:
						# print('Station ID not valid. Try again.... ')
			# elif section == 'Station' and key in ['OutdoorID','IndoorID','SkyID']:
				# while True:
					# try:
						# print('Please enter your ' + key[:-2] + ' module ID (optional):')
						# Value = str(int(input()))
						# Config.set(section,key,Value)
						# print()	
						# break
					# except ValueError:
						# print(key[:-2] + ' module ID not valid. Try again.... ')
					
			# # Generate configuration section for system keys
			# elif section == 'System':
				# Config.set(section,key,defaultConfig[section][key])

	# WRITES USER .INI FILE TO DISK
	# --------------------------------------------------------------------------
	with open('config.ini','w') as configfile:
		Config.write(configfile)
		
	def update_iniUser():
		
		""" Updates the existing user configuration .ini file required by the 
		Raspberry Pi Python console for Weather Flow Smart Home Weather 
		Stations. Compares the existing user configuration .ini file against the 
		default configuration dictionary, adding keys where required. User input 
		requested where needed. The updated user configuration .ini file is 
		saved to wfpiconsole.ini
		"""	

		# LOAD DEFAULT CONFIGURATION DICTIONARY
		# ----------------------------------------------------------------------
		defaultConfig = defaultDict()
		
		# LOAD EXISTING USER CONFIGURATION FILE
		# ----------------------------------------------------------------------
	
		
		
		
		
		
		
		