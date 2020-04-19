""" Handles Websocket messages received by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2020 Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

# Import required library modules
from lib import derivedVariables   as derive
from lib import observationFormat  as observation
from lib import requestAPI
import time

# Define global variables
NaN = float('NaN')

def Tempest(Msg,Console):

    """ Handles Websocket messages received from TEMPEST module

	INPUTS:
		Msg				    Websocket messages received from TEMPEST module
		Console             Console object
	"""

    # Replace missing observations from latest SKY Websocket JSON with NaN
    Ob = [x if x != None else NaN for x in Msg['obs'][0]]

    # Extract TEMPEST device ID
    Device = Console.config['Station']['TempestID']

    # Extract required observations from latest TEMPEST Websocket JSON
    Time      = [Ob[0],'s']
    WindSpd   = [Ob[2],'mps']
    WindGust  = [Ob[3],'mps']
    WindDir   = [Ob[4],'degrees']
    Pres      = [Ob[6],'mb']
    Temp      = [Ob[7],'c']
    Humidity  = [Ob[8],' %']
    UV        = [Ob[10],'index']
    Radiation = [Ob[11],' W m[sup]-2[/sup]']
    Rain      = [Ob[12],'mm']
    Strikes   = [Ob[15],'count']
    Battery   = [Ob[16],' v']

    # Extract lightning strike data from the latest AIR Websocket JSON "Summary"
    # object
    StrikeTime = [Msg['summary']['strike_last_epoch'] if 'strike_last_epoch' in Msg['summary'] else NaN,'s']
    StrikeDist = [Msg['summary']['strike_last_dist']  if 'strike_last_dist'  in Msg['summary'] else NaN,'km']
    Strikes3hr = [Msg['summary']['strike_count_3h']   if 'strike_count_3h'   in Msg['summary'] else NaN,'count']

    # Store latest TEMPEST Websocket message
    Console.Obs['TempestMsg'] = Msg

    # Extract required derived observations
    minPres     = Console.Obs['MinPres']
    maxPres     = Console.Obs['MaxPres']
    minTemp     = Console.Obs['outTempMin']
    maxTemp     = Console.Obs['outTempMax']
    StrikeCount = {'Today': Console.Obs['StrikesToday'],
                   'Month': Console.Obs['StrikesMonth'],
                   'Year':  Console.Obs['StrikesYear']}
    rainAccum   = {'Today':     Console.Obs['TodayRain'],
                   'Yesterday': Console.Obs['YesterdayRain'],
                   'Month':     Console.Obs['MonthRain'],
                   'Year':      Console.Obs['YearRain']}
    avgWind     = Console.Obs['AvgWind']
    maxGust     = Console.Obs['MaxGust']

    # Request TEMPEST data from the previous three hours
    Data3h = requestAPI.weatherflow.Last3h(Device,Time[0],Console.config)

    # Calculate derived variables from TEMPEST observations
    DewPoint         = derive.DewPoint(Temp,Humidity)
    SLP              = derive.SLP(Pres,Console.config)
    PresTrend        = derive.SLPTrend(Pres,Time,Data3h,Console.config)
    FeelsLike        = derive.FeelsLike(Temp,Humidity,WindSpd,Console.config)
    MaxTemp, MinTemp = derive.TempMaxMin(Time,Temp,maxTemp,minTemp,Device,Console.config)
    MaxPres, MinPres = derive.SLPMaxMin(Time,Pres,maxPres,minPres,Device,Console.config)
    StrikeCount      = derive.StrikeCount(Strikes,StrikeCount,Device,Console.config)
    StrikeFreq       = derive.StrikeFrequency(Time,Data3h,Console.config)
    StrikeDeltaT     = derive.StrikeDeltaT(StrikeTime)
    FeelsLike        = derive.FeelsLike(Temp,Humidity,WindSpd,Console.config)
    RainRate         = derive.RainRate(Rain)
    rainAccum        = derive.RainAccumulation(Rain,rainAccum,Device,Console.config)
    AvgWind          = derive.MeanWindSpeed(WindSpd,avgWind,Device,Console.config)
    MaxGust          = derive.MaxWindGust(WindGust,maxGust,Device,Console.config)
    WindSpd          = derive.BeaufortScale(WindSpd)
    WindDir          = derive.CardinalWindDirection(WindDir,WindSpd)
    UVIndex          = derive.UVIndex(UV)

    # Convert observation units as required
    Temp          = observation.Units(Temp,Console.config['Units']['Temp'])
    MaxTemp       = observation.Units(MaxTemp,Console.config['Units']['Temp'])
    MinTemp       = observation.Units(MinTemp,Console.config['Units']['Temp'])
    DewPoint      = observation.Units(DewPoint,Console.config['Units']['Temp'])
    FeelsLike     = observation.Units(FeelsLike,Console.config['Units']['Temp'])
    SLP           = observation.Units(SLP,Console.config['Units']['Pressure'])
    MaxPres       = observation.Units(MaxPres,Console.config['Units']['Pressure'])
    MinPres       = observation.Units(MinPres,Console.config['Units']['Pressure'])
    PresTrend     = observation.Units(PresTrend,Console.config['Units']['Pressure'])
    StrikeDist    = observation.Units(StrikeDist,Console.config['Units']['Distance'])
    RainRate      = observation.Units(RainRate,Console.config['Units']['Precip'])
    TodayRain     = observation.Units(rainAccum['Today'],Console.config['Units']['Precip'])
    YesterdayRain = observation.Units(rainAccum['Yesterday'],Console.config['Units']['Precip'])
    MonthRain     = observation.Units(rainAccum['Month'],Console.config['Units']['Precip'])
    YearRain      = observation.Units(rainAccum['Year'],Console.config['Units']['Precip'])
    WindSpd       = observation.Units(WindSpd,Console.config['Units']['Wind'])
    WindDir       = observation.Units(WindDir,Console.config['Units']['Direction'])
    WindGust      = observation.Units(WindGust,Console.config['Units']['Wind'])
    AvgWind       = observation.Units(AvgWind,Console.config['Units']['Wind'])
    MaxGust       = observation.Units(MaxGust,Console.config['Units']['Wind'])
    FeelsLike     = observation.Units(FeelsLike,Console.config['Units']['Temp'])

    # Define Kivy label binds
    Console.Obs['outTemp']       = observation.Format(Temp,'Temp')
    Console.Obs['outTempMax']    = observation.Format(MaxTemp,'Temp')
    Console.Obs['outTempMin']    = observation.Format(MinTemp,'Temp')
    Console.Obs['DewPoint']      = observation.Format(DewPoint,'Temp')
    Console.Obs['FeelsLike']     = observation.Format(FeelsLike,'Temp')
    Console.Obs['Pres']          = observation.Format(SLP,'Pressure')
    Console.Obs['MaxPres']       = observation.Format(MaxPres,'Pressure')
    Console.Obs['MinPres']       = observation.Format(MinPres,'Pressure')
    Console.Obs['PresTrend']     = observation.Format(PresTrend,'Pressure')
    Console.Obs['StrikeDeltaT']  = observation.Format(StrikeDeltaT,'TimeDelta')
    Console.Obs['StrikeDist']    = observation.Format(StrikeDist,'StrikeDistance')
    Console.Obs['StrikeFreq']    = observation.Format(StrikeFreq,'StrikeFrequency')
    Console.Obs['Strikes3hr']    = observation.Format(Strikes3hr,'StrikeCount')
    Console.Obs['StrikesToday']  = observation.Format(StrikeCount['Today'],'StrikeCount')
    Console.Obs['StrikesMonth']  = observation.Format(StrikeCount['Month'],'StrikeCount')
    Console.Obs['StrikesYear']   = observation.Format(StrikeCount['Year'],'StrikeCount')
    Console.Obs['Humidity']      = observation.Format(Humidity,'Humidity')
    Console.Obs['Battery']       = observation.Format(Battery,'Battery')
    Console.Obs['FeelsLike']     = observation.Format(FeelsLike,'Temp')
    Console.Obs['RainRate']      = observation.Format(RainRate,'Precip')
    Console.Obs['TodayRain']     = observation.Format(TodayRain,'Precip')
    Console.Obs['YesterdayRain'] = observation.Format(YesterdayRain,'Precip')
    Console.Obs['MonthRain']     = observation.Format(MonthRain,'Precip')
    Console.Obs['YearRain']      = observation.Format(YearRain,'Precip')
    Console.Obs['WindSpd']       = observation.Format(WindSpd,'Wind')
    Console.Obs['WindGust']      = observation.Format(WindGust,'Wind')
    Console.Obs['AvgWind']       = observation.Format(AvgWind,'Wind')
    Console.Obs['MaxGust']       = observation.Format(MaxGust,'Wind')
    Console.Obs['WindDir']       = observation.Format(WindDir,'Direction')
    Console.Obs['Radiation']     = observation.Format(Radiation,'Radiation')
    Console.Obs['Battery']       = observation.Format(Battery,'Battery')
    Console.Obs['UVIndex']       = observation.Format(UVIndex,'UV')

    # Animate RainRate if RainfallPanel is active
    if hasattr(Console,'RainfallPanel'):
        Console.RainfallPanel.RainRateAnimation()

    # Set mean wind speed and direction icons if WindSpeedPanel is active
    if hasattr(Console,'WindSpeedPanel'):
        Console.WindSpeedPanel.meanWindIcons()

    # Set UV Index icon if Sunrise/Sunset panel is active
    if hasattr(Console,'SunriseSunsetPanel'):
        Console.SunriseSunsetPanel.setUVIcon()

    # Set current pressure arrow if BarometerPanel is active
    if hasattr(Console,'BarometerPanel'):
        Console.BarometerPanel.setArrow()

    # Set "Feels Like" icon if TemperaturePanel is active
    if hasattr(Console,'TemperaturePanel'):
        Console.TemperaturePanel.feelsLikeIcon()

    # Return Console object
    return Console

def Sky(Msg,Console):

    """ Handles Websocket messages received from SKY module

	INPUTS:
		Msg				    Websocket messages received from SKY module
		Console             Console object
	"""

    # Replace missing observations from latest SKY Websocket JSON with NaN
    Ob = [x if x != None else NaN for x in Msg['obs'][0]]

    # Extract SKY device ID
    Device = Console.config['Station']['SkyID']

    # Extract required observations from latest SKY Websocket JSON
    Time      = [Ob[0],'s']
    UV        = [Ob[2],'index']
    Rain      = [Ob[3],'mm']
    WindSpd   = [Ob[5],'mps']
    WindGust  = [Ob[6],'mps']
    WindDir   = [Ob[7],'degrees']
    Battery   = [Ob[8],'v']
    Radiation = [Ob[10],' W m[sup]-2[/sup]']

    # Store latest SKY Websocket message
    Console.Obs['SkyMsg'] = Msg

    # Extract required observations from latest AIR Websocket observations
    while not 'outAirMsg' in Console.Obs:
        time.sleep(0.01)
    Ob = [x if x != None else NaN for x in Console.Obs['outAirMsg']['obs'][0]]
    Temp = [Ob[2],'c']
    Humidity = [Ob[3],'%']

    # Set wind direction to None if wind speed is zero
    if WindSpd[0] == 0:
        WindDir = [None,'degrees']

    # Extract required derived observations
    rainAccum = {'Today':     Console.Obs['TodayRain'],
                 'Yesterday': Console.Obs['YesterdayRain'],
                 'Month':     Console.Obs['MonthRain'],
                 'Year':      Console.Obs['YearRain']}
    avgWind   = Console.Obs['AvgWind']
    maxGust   = Console.Obs['MaxGust']

    # Calculate derived variables from SKY observations
    FeelsLike = derive.FeelsLike(Temp,Humidity,WindSpd,Console.config)
    RainRate  = derive.RainRate(Rain)
    rainAccum = derive.RainAccumulation(Rain,rainAccum,Device,Console.config)
    AvgWind   = derive.MeanWindSpeed(WindSpd,avgWind,Device,Console.config)
    MaxGust   = derive.MaxWindGust(WindGust,maxGust,Device,Console.config)
    WindSpd   = derive.BeaufortScale(WindSpd)
    WindDir   = derive.CardinalWindDirection(WindDir,WindSpd)
    UVIndex   = derive.UVIndex(UV)

    # Convert observation units as required
    RainRate      = observation.Units(RainRate,Console.config['Units']['Precip'])
    TodayRain     = observation.Units(rainAccum['Today'],Console.config['Units']['Precip'])
    YesterdayRain = observation.Units(rainAccum['Yesterday'],Console.config['Units']['Precip'])
    MonthRain     = observation.Units(rainAccum['Month'],Console.config['Units']['Precip'])
    YearRain      = observation.Units(rainAccum['Year'],Console.config['Units']['Precip'])
    WindSpd       = observation.Units(WindSpd,Console.config['Units']['Wind'])
    WindDir       = observation.Units(WindDir,Console.config['Units']['Direction'])
    WindGust      = observation.Units(WindGust,Console.config['Units']['Wind'])
    AvgWind       = observation.Units(AvgWind,Console.config['Units']['Wind'])
    MaxGust       = observation.Units(MaxGust,Console.config['Units']['Wind'])
    FeelsLike     = observation.Units(FeelsLike,Console.config['Units']['Temp'])

    # Define Kivy label binds
    Console.Obs['FeelsLike']     = observation.Format(FeelsLike,'Temp')
    Console.Obs['RainRate']      = observation.Format(RainRate,'Precip')
    Console.Obs['TodayRain']     = observation.Format(TodayRain,'Precip')
    Console.Obs['YesterdayRain'] = observation.Format(YesterdayRain,'Precip')
    Console.Obs['MonthRain']     = observation.Format(MonthRain,'Precip')
    Console.Obs['YearRain']      = observation.Format(YearRain,'Precip')
    Console.Obs['WindSpd']       = observation.Format(WindSpd,'Wind')
    Console.Obs['WindGust']      = observation.Format(WindGust,'Wind')
    Console.Obs['AvgWind']       = observation.Format(AvgWind,'Wind')
    Console.Obs['MaxGust']       = observation.Format(MaxGust,'Wind')
    Console.Obs['WindDir']       = observation.Format(WindDir,'Direction')
    Console.Obs['Radiation']     = observation.Format(Radiation,'Radiation')
    Console.Obs['Battery']       = observation.Format(Battery,'Battery')
    Console.Obs['UVIndex']       = observation.Format(UVIndex,'UV')

    # Animate RainRate if RainfallPanel is active
    if hasattr(Console,'RainfallPanel'):
        Console.RainfallPanel.RainRateAnimation()

    # Set mean wind speed and direction icons if WindSpeedPanel is active
    if hasattr(Console,'WindSpeedPanel'):
        Console.WindSpeedPanel.meanWindIcons()

    # Set UV Index icon if Sunrise/Sunset panel is active
    if hasattr(Console,'SunriseSunsetPanel'):
        Console.SunriseSunsetPanel.setUVIcon()

    # Set "Feels Like" icon if TemperaturePanel is active
    if hasattr(Console,'TemperaturePanel'):
        Console.TemperaturePanel.feelsLikeIcon()

    # Return Console object
    return Console

def outdoorAir(Msg,Console):

    """ Handles Websocket messages received from outdoor AIR module

	INPUTS:
		Msg				    Websocket messages received from outdoor AIR module
		Console             Console object
	"""

    # Replace missing observations in latest outdoor AIR Websocket JSON with NaN
    Ob = [x if x != None else NaN for x in Msg['obs'][0]]

    # Extract outdoor AIR device ID
    Device = Console.config['Station']['OutAirID']

    # Extract required observations from latest outdoor AIR Websocket JSON
    Time     = [Ob[0],'s']
    Pres     = [Ob[1],'mb']
    Temp     = [Ob[2],'c']
    Humidity = [Ob[3],' %']
    Battery  = [Ob[6],' v']
    Strikes  = [Ob[4],'count']

    # Extract lightning strike data from the latest outdoor AIR Websocket JSON
    # "Summary" object
    StrikeTime = [Msg['summary']['strike_last_epoch'] if 'strike_last_epoch' in Msg['summary'] else NaN,'s']
    StrikeDist = [Msg['summary']['strike_last_dist']  if 'strike_last_dist'  in Msg['summary'] else NaN,'km']
    Strikes3hr = [Msg['summary']['strike_count_3h']   if 'strike_count_3h'   in Msg['summary'] else NaN,'count']

    # Extract required derived observations
    minPres      = Console.Obs['MinPres']
    maxPres      = Console.Obs['MaxPres']
    minTemp      = Console.Obs['outTempMin']
    maxTemp      = Console.Obs['outTempMax']
    StrikeCount  = {'Today': Console.Obs['StrikesToday'],
                    'Month': Console.Obs['StrikesMonth'],
                    'Year':  Console.Obs['StrikesYear']}

    # Request Outdoor AIR data from the previous three hours
    Data3h = requestAPI.weatherflow.Last3h(Device,Time[0],Console.config)

    # Store latest Outdoor AIR Websocket message
    Console.Obs['outAirMsg'] = Msg

    # Extract required observations from latest SKY Websocket JSON
    while not 'SkyMsg' in Console.Obs:
        time.sleep(0.01)
    Ob = [x if x != None else NaN for x in Console.Obs['SkyMsg']['obs'][0]]
    WindSpd = [Ob[5],'mps']

    # Calculate derived variables from AIR observations
    DewPoint         = derive.DewPoint(Temp,Humidity)
    SLP              = derive.SLP(Pres,Console.config)
    PresTrend        = derive.SLPTrend(Pres,Time,Data3h,Console.config)
    FeelsLike        = derive.FeelsLike(Temp,Humidity,WindSpd,Console.config)
    MaxTemp, MinTemp = derive.TempMaxMin(Time,Temp,maxTemp,minTemp,Device,Console.config)
    MaxPres, MinPres = derive.SLPMaxMin(Time,Pres,maxPres,minPres,Device,Console.config)
    StrikeCount      = derive.StrikeCount(Strikes,StrikeCount,Device,Console.config)
    StrikeFreq       = derive.StrikeFrequency(Time,Data3h,Console.config)
    StrikeDeltaT     = derive.StrikeDeltaT(StrikeTime)

    # Convert observation units as required
    Temp        = observation.Units(Temp,Console.config['Units']['Temp'])
    MaxTemp     = observation.Units(MaxTemp,Console.config['Units']['Temp'])
    MinTemp     = observation.Units(MinTemp,Console.config['Units']['Temp'])
    DewPoint    = observation.Units(DewPoint,Console.config['Units']['Temp'])
    FeelsLike   = observation.Units(FeelsLike,Console.config['Units']['Temp'])
    SLP         = observation.Units(SLP,Console.config['Units']['Pressure'])
    MaxPres     = observation.Units(MaxPres,Console.config['Units']['Pressure'])
    MinPres     = observation.Units(MinPres,Console.config['Units']['Pressure'])
    PresTrend   = observation.Units(PresTrend,Console.config['Units']['Pressure'])
    StrikeDist  = observation.Units(StrikeDist,Console.config['Units']['Distance'])

    # Define Kivy label binds
    Console.Obs['outTemp']      = observation.Format(Temp,'Temp')
    Console.Obs['outTempMax']   = observation.Format(MaxTemp,'Temp')
    Console.Obs['outTempMin']   = observation.Format(MinTemp,'Temp')
    Console.Obs['DewPoint']     = observation.Format(DewPoint,'Temp')
    Console.Obs['FeelsLike']    = observation.Format(FeelsLike,'Temp')
    Console.Obs['Pres']         = observation.Format(SLP,'Pressure')
    Console.Obs['MaxPres']      = observation.Format(MaxPres,'Pressure')
    Console.Obs['MinPres']      = observation.Format(MinPres,'Pressure')
    Console.Obs['PresTrend']    = observation.Format(PresTrend,'Pressure')
    Console.Obs['StrikeDeltaT'] = observation.Format(StrikeDeltaT,'TimeDelta')
    Console.Obs['StrikeDist']   = observation.Format(StrikeDist,'StrikeDistance')
    Console.Obs['StrikeFreq']   = observation.Format(StrikeFreq,'StrikeFrequency')
    Console.Obs['Strikes3hr']   = observation.Format(Strikes3hr,'StrikeCount')
    Console.Obs['StrikesToday'] = observation.Format(StrikeCount['Today'],'StrikeCount')
    Console.Obs['StrikesMonth'] = observation.Format(StrikeCount['Month'],'StrikeCount')
    Console.Obs['StrikesYear']  = observation.Format(StrikeCount['Year'],'StrikeCount')
    Console.Obs['Humidity']     = observation.Format(Humidity,'Humidity')
    Console.Obs['Battery']      = observation.Format(Battery,'Battery')

    # Set current pressure arrow if BarometerPanel is active
    if hasattr(Console,'BarometerPanel'):
        Console.BarometerPanel.setArrow()

    # Set "Feels Like" icon if TemperaturePanel is active
    if hasattr(Console,'TemperaturePanel'):
        Console.TemperaturePanel.feelsLikeIcon()

    # Return Console object
    return Console

def indoorAir(Msg,Console):

    """ Handles Websocket messages received from indoor AIR module

	INPUTS:
		Msg				    Websocket messages received from indoor AIR module
		Console             Console object
	"""

    # Replace missing observations in latest AIR Websocket JSON with NaN
    Ob = [x if x != None else NaN for x in Msg['obs'][0]]

    # Extract indoor AIR device ID
    Device = Console.config['Station']['InAirID']

    # Extract required observations from latest indoor AIR Websocket JSON
    Time     = [Ob[0],'s']
    Temp     = [Ob[2],'c']

    # Store latest indoor AIR Websocket message
    Console.Obs['inAirMsg'] = Msg

    # Extract required derived observations
    minTemp = Console.Obs['inTempMin']
    maxTemp = Console.Obs['inTempMax']

    # Calculate derived variables from indoor AIR observations
    MaxTemp, MinTemp = derive.TempMaxMin(Time,Temp,maxTemp,minTemp,Device,Console.config)

    # Convert observation units as required
    Temp    = observation.Units(Temp,Console.config['Units']['Temp'])
    MaxTemp = observation.Units(MaxTemp,Console.config['Units']['Temp'])
    MinTemp = observation.Units(MinTemp,Console.config['Units']['Temp'])

    # Define Kivy label binds
    Console.Obs['inTemp']    = observation.Format(Temp,'Temp')
    Console.Obs['inTempMax'] = observation.Format(MaxTemp,'Temp')
    Console.Obs['inTempMin'] = observation.Format(MinTemp,'Temp')

    # Return Console object
    return Console

def rapidWind(Msg,Console):

    """ Handles RapidWind Websocket messages received from either SKY or TEMPEST
        module

	INPUTS:
		Msg				    Websocket messages received from SKY or TEMPEST
		Console             Console object
	"""

    # Replace missing observations from Rapid Wind Websocket JSON
    # with NaN
    Ob = [x if x != None else NaN for x in Msg['ob']]

    # Extract observations from latest Rapid Wind Websocket JSON
    Time    = [Ob[0],'s']
    WindSpd = [Ob[1],'mps']
    WindDir = [Ob[2],'degrees']

    # Extract wind direction from previous SKY Rapid-Wind Websocket JSON
    if 'RapidMsg' in Console.Obs:
        Ob = [x if x != None else NaN for x in Console.Obs['RapidMsg']['ob']]
        WindDirOld = [Ob[2],'degrees']
    else:
        WindDirOld = [0,'degrees']

    # If windspeed is zero, freeze direction at last direction of non-zero wind
    # speed and edit latest Rapid Wind Websocket JSON. Calculate wind shift
    if WindSpd[0] == 0:
        WindDir = WindDirOld
        Msg['ob'][2] = WindDirOld[0]

    # Store latest Rapid Wind Console.Observation JSON message
    Console.Obs['RapidMsg'] = Msg

    # Calculate derived variables from Rapid Wind observations
    WindDir = derive.CardinalWindDirection(WindDir,WindSpd)

    # Convert observation units as required
    WindSpd = observation.Units(WindSpd,Console.config['Units']['Wind'])
    WindDir = observation.Units(WindDir,'degrees')

    # Define Kivy label binds
    Console.Obs['rapidShift'] = WindDir[0] - WindDirOld[0]
    Console.Obs['rapidSpd']   = observation.Format(WindSpd,'Wind')
    Console.Obs['rapidDir']   = observation.Format(WindDir,'Direction')

    # If WindSpeedPanel panel is open, animate wind rose arrow
    if hasattr(Console,'WindSpeedPanel'):
        Console.WindSpeedPanel.WindRoseAnimation()

    # Return Console object
    return Console

def evtStrike(Msg,Console):

    """ Handles lightning strike event Websocket messages received from either
        AIR or TEMPEST module

	INPUTS:
		Msg				    Websocket messages received from AIR or TEMPEST
		Console             Console object
	"""

    # Extract required observations from latest evt_strike Websocket JSON
    StrikeTime = [Msg['evt'][0],'s']
    StrikeDist = [Msg['evt'][1],'km']

    # Store latest Rapid Wind Console.Observation JSON message
    Console.Obs['evtStrikeMsg'] = Msg

    # Calculate derived variables from evt_strike observations
    StrikeDeltaT = derive.StrikeDeltaT(StrikeTime)

    # Convert observation units as required
    StrikeDist = observation.Units(StrikeDist,Console.config['Units']['Distance'])

    # Define Kivy label binds
    Console.Obs['StrikeDeltaT'] = observation.Format(StrikeDeltaT,'TimeDelta')
    Console.Obs['StrikeDist']   = observation.Format(StrikeDist,'StrikeDistance')

    # Return Console object
    return Console