""" Handles Websocket messages received by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2021 Peter Davis

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
from kivy.clock     import mainthread
from lib            import derivedVariables   as derive
from lib            import observationFormat  as observation
from lib            import requestAPI
import time

# Define global variables
NaN = float('NaN')

def updateDisplay(derivedObs,wfpiconsole,Type):

    """ Updates wfpiconsole display using mainthread functions with new
    variables derived from latest websocket message

    INPUTS:
        derivedObs          Derived variables from latest Websocket message
        wfpiconsole         wfpiconsole object
        Type                Derived variable module type
    """

    # Update display with new derived observations
    for Key,Value in derivedObs.items():
        wfpiconsole.Obs[Key] = Value

    # Set "Feels Like" icon if TemperaturePanel is active
    if Type in ['Tempest','outdoorAir']  and hasattr(wfpiconsole,'TemperaturePanel'):
        for panel in getattr(wfpiconsole,'TemperaturePanel'):
            panel.setFeelsLikeIcon()

    # Set wind speed and direction icons if WindSpeedPanel panel is active
    if Type in ['Tempest','Sky'] and hasattr(wfpiconsole,'WindSpeedPanel'):
        for panel in getattr(wfpiconsole,'WindSpeedPanel'):
            panel.setWindIcons()

    # Set current UV index background color if SunriseSunsetPanel is active
    if Type in ['Tempest','Sky'] and hasattr(wfpiconsole,'SunriseSunsetPanel'):
        for panel in getattr(wfpiconsole,'SunriseSunsetPanel'):
            panel.setUVBackground()

    # Animate rain rate level if RainfallPanel is active
    if Type in ['Tempest','Sky'] and hasattr(wfpiconsole,'RainfallPanel'):
        for panel in getattr(wfpiconsole,'RainfallPanel'):
            panel.animateRainRate()

    # Set lightning bolt icon if LightningPanel is active
    if Type in ['Tempest','outdoorAir']  and hasattr(wfpiconsole,'LightningPanel'):
        for panel in getattr(wfpiconsole,'LightningPanel'):
            panel.setLightningBoltIcon()

    # Set barometer arrow to current sea level pressure if BarometerPanel is
    # active
    if Type in ['Tempest','outdoorAir'] and hasattr(wfpiconsole,'BarometerPanel'):
        for panel in getattr(wfpiconsole,'BarometerPanel'):
            panel.setBarometerArrow()

    # Return wfpiconsole object
    return wfpiconsole

def Tempest(Msg,wfpiconsole):

    """ Handles Websocket messages received from TEMPEST module

    INPUTS:
        Msg                 Websocket messages received from TEMPEST module
        wfpiconsole         wfpiconsole object
    """

    # Replace missing observations from latest TEMPEST Websocket JSON with NaN
    Ob = [x if x != None else NaN for x in Msg['obs'][0]]

    # Discard duplicate TEMPEST Websocket messages
    if 'TempestMsg' in wfpiconsole.Obs:
        if wfpiconsole.Obs['TempestMsg']['obs'][0] == Ob[0]:
            print('Discarding duplicate TEMPEST Websocket message')
            return

    # Extract TEMPEST device ID, API flag, and station configuration object
    Device  = wfpiconsole.config['Station']['TempestID']
    flagAPI = wfpiconsole.flagAPI[0]
    Config  = wfpiconsole.config

    # Extract required observations from latest TEMPEST Websocket JSON
    Time      = [Ob[0],'s']
    WindSpd   = [Ob[2],'mps']
    WindGust  = [Ob[3],'mps']
    WindDir   = [Ob[4],'degrees']
    Pres      = [Ob[6],'mb']
    Temp      = [Ob[7],'c']
    Humidity  = [Ob[8],'%']
    UV        = [Ob[10],'index']
    Radiation = [Ob[11],'Wm2']
    minutRain = [Ob[12],'mm']
    Strikes   = [Ob[15],'count']
    dailyRain = [Ob[18],'mm']

    # Extract lightning strike data from the latest AIR Websocket JSON "Summary"
    # object
    StrikeTime = [Msg['summary']['strike_last_epoch'] if 'strike_last_epoch' in Msg['summary'] else NaN,'s']
    StrikeDist = [Msg['summary']['strike_last_dist']  if 'strike_last_dist'  in Msg['summary'] else NaN,'km']
    Strikes3hr = [Msg['summary']['strike_count_3h']   if 'strike_count_3h'   in Msg['summary'] else NaN,'count']

    # Store latest TEMPEST Websocket message
    wfpiconsole.Obs['TempestMsg'] = Msg

    # Extract required derived observations
    minPres     = wfpiconsole.Obs['MinPres']
    maxPres     = wfpiconsole.Obs['MaxPres']
    minTemp     = wfpiconsole.Obs['outTempMin']
    maxTemp     = wfpiconsole.Obs['outTempMax']
    StrikeCount = {'Today': wfpiconsole.Obs['StrikesToday'],
                   'Month': wfpiconsole.Obs['StrikesMonth'],
                   'Year':  wfpiconsole.Obs['StrikesYear']}
    rainAccum   = {'Today':     wfpiconsole.Obs['TodayRain'],
                   'Yesterday': wfpiconsole.Obs['YesterdayRain'],
                   'Month':     wfpiconsole.Obs['MonthRain'],
                   'Year':      wfpiconsole.Obs['YearRain']}
    peakSun     = wfpiconsole.Obs['peakSun']
    avgWind     = wfpiconsole.Obs['AvgWind']
    maxGust     = wfpiconsole.Obs['MaxGust']

    # Request TEMPEST data from the previous three hours
    Data3h = requestAPI.weatherflow.Last3h(Device,Time[0],Config)

    # Calculate derived variables from TEMPEST observations
    DewPoint         = derive.DewPoint(Temp,Humidity)
    SLP              = derive.SLP(Pres,Config)
    PresTrend        = derive.SLPTrend(Pres,Time,Data3h,Config)
    FeelsLike        = derive.FeelsLike(Temp,Humidity,WindSpd,Config)
    MaxTemp, MinTemp = derive.TempMaxMin(Time,Temp,maxTemp,minTemp,Device,Config,flagAPI)
    MaxPres, MinPres = derive.SLPMaxMin(Time,Pres,maxPres,minPres,Device,Config,flagAPI)
    StrikeCount      = derive.StrikeCount(Strikes,StrikeCount,Device,Config,flagAPI)
    StrikeFreq       = derive.StrikeFrequency(Time,Data3h,Config)
    StrikeDeltaT     = derive.StrikeDeltaT(StrikeTime)
    FeelsLike        = derive.FeelsLike(Temp,Humidity,WindSpd,Config)
    RainRate         = derive.RainRate(minutRain)
    rainAccum        = derive.RainAccumulation(dailyRain,rainAccum,Device,Config,flagAPI)
    AvgWind          = derive.MeanWindSpeed(WindSpd,avgWind,Device,Config,flagAPI)
    MaxGust          = derive.MaxWindGust(WindGust,maxGust,Device,Config,flagAPI)
    WindSpd          = derive.BeaufortScale(WindSpd)
    WindDir          = derive.CardinalWindDirection(WindDir,WindSpd)
    peakSun          = derive.peakSunHours(Radiation,peakSun,wfpiconsole.Astro,Device,Config,flagAPI)
    UVIndex          = derive.UVIndex(UV)

    # Convert observation units as required
    Temp          = observation.Units(Temp,Config['Units']['Temp'])
    MaxTemp       = observation.Units(MaxTemp,Config['Units']['Temp'])
    MinTemp       = observation.Units(MinTemp,Config['Units']['Temp'])
    DewPoint      = observation.Units(DewPoint,Config['Units']['Temp'])
    FeelsLike     = observation.Units(FeelsLike,Config['Units']['Temp'])
    SLP           = observation.Units(SLP,Config['Units']['Pressure'])
    MaxPres       = observation.Units(MaxPres,Config['Units']['Pressure'])
    MinPres       = observation.Units(MinPres,Config['Units']['Pressure'])
    PresTrend     = observation.Units(PresTrend,Config['Units']['Pressure'])
    StrikeDist    = observation.Units(StrikeDist,Config['Units']['Distance'])
    RainRate      = observation.Units(RainRate,Config['Units']['Precip'])
    TodayRain     = observation.Units(rainAccum['Today'],Config['Units']['Precip'])
    YesterdayRain = observation.Units(rainAccum['Yesterday'],Config['Units']['Precip'])
    MonthRain     = observation.Units(rainAccum['Month'],Config['Units']['Precip'])
    YearRain      = observation.Units(rainAccum['Year'],Config['Units']['Precip'])
    WindSpd       = observation.Units(WindSpd,Config['Units']['Wind'])
    WindDir       = observation.Units(WindDir,Config['Units']['Direction'])
    WindGust      = observation.Units(WindGust,Config['Units']['Wind'])
    AvgWind       = observation.Units(AvgWind,Config['Units']['Wind'])
    MaxGust       = observation.Units(MaxGust,Config['Units']['Wind'])
    FeelsLike     = observation.Units(FeelsLike,Config['Units']['Temp'])

    # Store derived TEMPEST observations in dictionary
    derivedObs                  = {}
    derivedObs['outTemp']       = observation.Format(Temp,'Temp')
    derivedObs['outTempMax']    = observation.Format(MaxTemp,'Temp')
    derivedObs['outTempMin']    = observation.Format(MinTemp,'Temp')
    derivedObs['DewPoint']      = observation.Format(DewPoint,'Temp')
    derivedObs['FeelsLike']     = observation.Format(FeelsLike,'Temp')
    derivedObs['Pres']          = observation.Format(SLP,'Pressure')
    derivedObs['MaxPres']       = observation.Format(MaxPres,'Pressure')
    derivedObs['MinPres']       = observation.Format(MinPres,'Pressure')
    derivedObs['PresTrend']     = observation.Format(PresTrend,'Pressure')
    derivedObs['StrikeDeltaT']  = observation.Format(StrikeDeltaT,'TimeDelta')
    derivedObs['StrikeDist']    = observation.Format(StrikeDist,'StrikeDistance')
    derivedObs['StrikeFreq']    = observation.Format(StrikeFreq,'StrikeFrequency')
    derivedObs['Strikes3hr']    = observation.Format(Strikes3hr,'StrikeCount')
    derivedObs['StrikesToday']  = observation.Format(StrikeCount['Today'],'StrikeCount')
    derivedObs['StrikesMonth']  = observation.Format(StrikeCount['Month'],'StrikeCount')
    derivedObs['StrikesYear']   = observation.Format(StrikeCount['Year'], 'StrikeCount')
    derivedObs['Humidity']      = observation.Format(Humidity,'Humidity')
    derivedObs['FeelsLike']     = observation.Format(FeelsLike,'Temp')
    derivedObs['RainRate']      = observation.Format(RainRate,'Precip')
    derivedObs['TodayRain']     = observation.Format(TodayRain,'Precip')
    derivedObs['YesterdayRain'] = observation.Format(YesterdayRain,'Precip')
    derivedObs['MonthRain']     = observation.Format(MonthRain,'Precip')
    derivedObs['YearRain']      = observation.Format(YearRain,'Precip')
    derivedObs['WindSpd']       = observation.Format(WindSpd,'Wind')
    derivedObs['WindGust']      = observation.Format(WindGust,'Wind')
    derivedObs['AvgWind']       = observation.Format(AvgWind,'Wind')
    derivedObs['MaxGust']       = observation.Format(MaxGust,'Wind')
    derivedObs['WindDir']       = observation.Format(WindDir,'Direction')
    derivedObs['Radiation']     = observation.Format(Radiation,'Radiation')
    derivedObs['peakSun']       = observation.Format(peakSun,'peakSun')
    derivedObs['UVIndex']       = observation.Format(UVIndex,'UV')

    # Update wfpiconsole display with derived TEMPEST observations
    updateDisplay(derivedObs,wfpiconsole,'Tempest')

    # Set flags for required API calls
    wfpiconsole.flagAPI[0] = 0

    # Return wfpiconsole object
    return wfpiconsole

def Sky(Msg,wfpiconsole):

    """ Handles Websocket messages received from SKY module

    INPUTS:
        Msg                 Websocket messages received from SKY module
        wfpiconsole         wfpiconsole object
    """

    # Replace missing observations from latest SKY Websocket JSON with NaN
    Ob = [x if x != None else NaN for x in Msg['obs'][0]]

    # Discard duplicate SKY Websocket messages
    if 'SkyMsg' in wfpiconsole.Obs:
        if wfpiconsole.Obs['SkyMsg']['obs'][0] == Ob[0]:
            print('Discarding duplicate SKY Websocket message')
            return

    # Store latest SKY Websocket message
    wfpiconsole.Obs['SkyMsg'] = Msg

    # Extract SKY device ID and API flag, and station configuration object
    Device  = wfpiconsole.config['Station']['SkyID']
    flagAPI = wfpiconsole.flagAPI[1]
    Config  = wfpiconsole.config

    # Extract required observations from latest SKY Websocket JSON
    Time      = [Ob[0],'s']
    UV        = [Ob[2],'index']
    minutRain = [Ob[3],'mm']
    WindSpd   = [Ob[5],'mps']
    WindGust  = [Ob[6],'mps']
    WindDir   = [Ob[7],'degrees']
    Radiation = [Ob[10],'Wm2']
    dailyRain = [Ob[11],'mm']

    # Extract required observations from latest AIR Websocket observations
    Retries = 0
    while Retries <= 10:
        if 'outAirMsg' in wfpiconsole.Obs:
            Ob       = [x if x != None else NaN for x in wfpiconsole.Obs['outAirMsg']['obs'][0]]
            Temp     = [Ob[2],'c']
            Humidity = [Ob[3],'%']
            break
        else:
            Temp     = [NaN,'c']
            Humidity = [NaN,'%']
            Retries += 1
            time.sleep(0.1)

    # Set wind direction to None if wind speed is zero
    if WindSpd[0] == 0:
        WindDir = [None,'degrees']

    # Extract required derived observations
    rainAccum = {'Today':     wfpiconsole.Obs['TodayRain'],
                 'Yesterday': wfpiconsole.Obs['YesterdayRain'],
                 'Month':     wfpiconsole.Obs['MonthRain'],
                 'Year':      wfpiconsole.Obs['YearRain']}
    peakSun   = wfpiconsole.Obs['peakSun']
    avgWind   = wfpiconsole.Obs['AvgWind']
    maxGust   = wfpiconsole.Obs['MaxGust']

    # Calculate derived variables from SKY observations
    FeelsLike = derive.FeelsLike(Temp,Humidity,WindSpd,Config)
    RainRate  = derive.RainRate(minutRain)
    rainAccum = derive.RainAccumulation(dailyRain,rainAccum,Device,Config,flagAPI)
    AvgWind   = derive.MeanWindSpeed(WindSpd,avgWind,Device,Config,flagAPI)
    MaxGust   = derive.MaxWindGust(WindGust,maxGust,Device,Config,flagAPI)
    WindSpd   = derive.BeaufortScale(WindSpd)
    WindDir   = derive.CardinalWindDirection(WindDir,WindSpd)
    peakSun   = derive.peakSunHours(Radiation,peakSun,wfpiconsole.Astro,Device,Config,flagAPI)
    UVIndex   = derive.UVIndex(UV)

    # Convert observation units as required
    RainRate      = observation.Units(RainRate,Config['Units']['Precip'])
    TodayRain     = observation.Units(rainAccum['Today'],Config['Units']['Precip'])
    YesterdayRain = observation.Units(rainAccum['Yesterday'],Config['Units']['Precip'])
    MonthRain     = observation.Units(rainAccum['Month'],Config['Units']['Precip'])
    YearRain      = observation.Units(rainAccum['Year'],Config['Units']['Precip'])
    WindSpd       = observation.Units(WindSpd,Config['Units']['Wind'])
    WindDir       = observation.Units(WindDir,Config['Units']['Direction'])
    WindGust      = observation.Units(WindGust,Config['Units']['Wind'])
    AvgWind       = observation.Units(AvgWind,Config['Units']['Wind'])
    MaxGust       = observation.Units(MaxGust,Config['Units']['Wind'])
    FeelsLike     = observation.Units(FeelsLike,Config['Units']['Temp'])

    # Store derived SKY observations in dictionary
    derivedObs                  = {}
    derivedObs['FeelsLike']     = observation.Format(FeelsLike,'Temp')
    derivedObs['RainRate']      = observation.Format(RainRate,'Precip')
    derivedObs['TodayRain']     = observation.Format(TodayRain,'Precip')
    derivedObs['YesterdayRain'] = observation.Format(YesterdayRain,'Precip')
    derivedObs['MonthRain']     = observation.Format(MonthRain,'Precip')
    derivedObs['YearRain']      = observation.Format(YearRain,'Precip')
    derivedObs['WindSpd']       = observation.Format(WindSpd,'Wind')
    derivedObs['WindGust']      = observation.Format(WindGust,'Wind')
    derivedObs['AvgWind']       = observation.Format(AvgWind,'Wind')
    derivedObs['MaxGust']       = observation.Format(MaxGust,'Wind')
    derivedObs['WindDir']       = observation.Format(WindDir,'Direction')
    derivedObs['Radiation']     = observation.Format(Radiation,'Radiation')
    derivedObs['peakSun']       = observation.Format(peakSun,'peakSun')
    derivedObs['UVIndex']       = observation.Format(UVIndex,'UV')

    # Update wfpiconsole display with derived SKY observations
    updateDisplay(derivedObs,wfpiconsole,'Sky')

    # Set flags for required API calls
    wfpiconsole.flagAPI[1] = 0

    # Return wfpiconsole object
    return wfpiconsole

def outdoorAir(Msg,wfpiconsole):

    """ Handles Websocket messages received from outdoor AIR module

    INPUTS:
        Msg                 Websocket messages received from outdoor AIR module
        wfpiconsole         wfpiconsole object
    """

    # Replace missing observations in latest outdoor AIR Websocket JSON with NaN
    Ob = [x if x != None else NaN for x in Msg['obs'][0]]

    # Discard duplicate outdoor AIR Websocket messages
    if 'outAirMsg' in wfpiconsole.Obs:
        if wfpiconsole.Obs['outAirMsg']['obs'][0] == Ob[0]:
            print('Discarding duplicate outdoor AIR Websocket message')
            return

    # Store latest outdoor AIR Websocket message
    wfpiconsole.Obs['outAirMsg'] = Msg

    # Extract outdoor AIR device ID and API flag, and station configuration
    # object
    Device  = wfpiconsole.config['Station']['OutAirID']
    flagAPI = wfpiconsole.flagAPI[2]
    Config  = wfpiconsole.config

    # Extract required observations from latest outdoor AIR Websocket JSON
    Time     = [Ob[0],'s']
    Pres     = [Ob[1],'mb']
    Temp     = [Ob[2],'c']
    Humidity = [Ob[3],'%']
    Strikes  = [Ob[4],'count']

    # Extract lightning strike data from the latest outdoor AIR Websocket JSON
    # "Summary" object
    StrikeTime = [Msg['summary']['strike_last_epoch'] if 'strike_last_epoch' in Msg['summary'] else NaN,'s']
    StrikeDist = [Msg['summary']['strike_last_dist']  if 'strike_last_dist'  in Msg['summary'] else NaN,'km']
    Strikes3hr = [Msg['summary']['strike_count_3h']   if 'strike_count_3h'   in Msg['summary'] else NaN,'count']

    # Extract required derived observations
    minPres      = wfpiconsole.Obs['MinPres']
    maxPres      = wfpiconsole.Obs['MaxPres']
    minTemp      = wfpiconsole.Obs['outTempMin']
    maxTemp      = wfpiconsole.Obs['outTempMax']
    StrikeCount  = {'Today': wfpiconsole.Obs['StrikesToday'],
                    'Month': wfpiconsole.Obs['StrikesMonth'],
                    'Year':  wfpiconsole.Obs['StrikesYear']}

    # Request outdoor AIR data from the previous three hours
    Data3h = requestAPI.weatherflow.Last3h(Device,Time[0],Config)

    # Extract required observations from latest SKY Websocket JSON
    Retries = 0
    while Retries <= 10:
        if 'SkyMsg' in wfpiconsole.Obs:
            Ob = [x if x != None else NaN for x in wfpiconsole.Obs['SkyMsg']['obs'][0]]
            WindSpd = [Ob[5],'mps']
            break
        else:
            WindSpd = [NaN,'mps']
            Retries += 1
            time.sleep(0.1)

    # Calculate derived variables from AIR observations
    DewPoint         = derive.DewPoint(Temp,Humidity)
    SLP              = derive.SLP(Pres,Config)
    PresTrend        = derive.SLPTrend(Pres,Time,Data3h,Config)
    FeelsLike        = derive.FeelsLike(Temp,Humidity,WindSpd,Config)
    MaxTemp, MinTemp = derive.TempMaxMin(Time,Temp,maxTemp,minTemp,Device,Config,flagAPI)
    MaxPres, MinPres = derive.SLPMaxMin(Time,Pres,maxPres,minPres,Device,Config,flagAPI)
    StrikeCount      = derive.StrikeCount(Strikes,StrikeCount,Device,Config,flagAPI)
    StrikeFreq       = derive.StrikeFrequency(Time,Data3h,Config)
    StrikeDeltaT     = derive.StrikeDeltaT(StrikeTime)

    # Convert observation units as required
    Temp        = observation.Units(Temp,Config['Units']['Temp'])
    MaxTemp     = observation.Units(MaxTemp,Config['Units']['Temp'])
    MinTemp     = observation.Units(MinTemp,Config['Units']['Temp'])
    DewPoint    = observation.Units(DewPoint,Config['Units']['Temp'])
    FeelsLike   = observation.Units(FeelsLike,Config['Units']['Temp'])
    SLP         = observation.Units(SLP,Config['Units']['Pressure'])
    MaxPres     = observation.Units(MaxPres,Config['Units']['Pressure'])
    MinPres     = observation.Units(MinPres,Config['Units']['Pressure'])
    PresTrend   = observation.Units(PresTrend,Config['Units']['Pressure'])
    StrikeDist  = observation.Units(StrikeDist,Config['Units']['Distance'])

    # Store derived outdoor AIR observations in dictionary
    derivedObs                 = {}
    derivedObs['outTemp']      = observation.Format(Temp,'Temp')
    derivedObs['outTempMax']   = observation.Format(MaxTemp,'Temp')
    derivedObs['outTempMin']   = observation.Format(MinTemp,'Temp')
    derivedObs['DewPoint']     = observation.Format(DewPoint,'Temp')
    derivedObs['FeelsLike']    = observation.Format(FeelsLike,'Temp')
    derivedObs['Pres']         = observation.Format(SLP,'Pressure')
    derivedObs['MaxPres']      = observation.Format(MaxPres,'Pressure')
    derivedObs['MinPres']      = observation.Format(MinPres,'Pressure')
    derivedObs['PresTrend']    = observation.Format(PresTrend,'Pressure')
    derivedObs['StrikeDeltaT'] = observation.Format(StrikeDeltaT,'TimeDelta')
    derivedObs['StrikeDist']   = observation.Format(StrikeDist,'StrikeDistance')
    derivedObs['StrikeFreq']   = observation.Format(StrikeFreq,'StrikeFrequency')
    derivedObs['Strikes3hr']   = observation.Format(Strikes3hr,'StrikeCount')
    derivedObs['StrikesToday'] = observation.Format(StrikeCount['Today'],'StrikeCount')
    derivedObs['StrikesMonth'] = observation.Format(StrikeCount['Month'],'StrikeCount')
    derivedObs['StrikesYear']  = observation.Format(StrikeCount['Year'],'StrikeCount')
    derivedObs['Humidity']     = observation.Format(Humidity,'Humidity')

    # Update wfpiconsole display with derived outdoor AIR observations
    updateDisplay(derivedObs,wfpiconsole,'outdoorAir')

    # Set flags for required API calls
    wfpiconsole.flagAPI[2] = 0

    # Return wfpiconsole object
    return wfpiconsole

def indoorAir(Msg,wfpiconsole):

    """ Handles Websocket messages received from indoor AIR module

    INPUTS:
        Msg                 Websocket messages received from indoor AIR module
        wfpiconsole         wfpiconsole object
    """

    # Replace missing observations in latest indoor AIR Websocket JSON with NaN
    Ob = [x if x != None else NaN for x in Msg['obs'][0]]

    # Discard duplicate indoor AIR Websocket messages
    if 'inAirMsg' in wfpiconsole.Obs:
        if wfpiconsole.Obs['inAirMsg']['obs'][0] == Ob[0]:
            print('Discarding duplicate indoor AIR Websocket message')
            return

    # Extract indoor AIR device ID and API flag, and station configuration
    # object
    Device  = wfpiconsole.config['Station']['InAirID']
    flagAPI = wfpiconsole.flagAPI[3]
    Config  = wfpiconsole.config

    # Extract required observations from latest indoor AIR Websocket JSON
    Time     = [Ob[0],'s']
    Temp     = [Ob[2],'c']

    # Store latest indoor AIR Websocket message
    wfpiconsole.Obs['inAirMsg'] = Msg

    # Extract required derived observations
    minTemp = wfpiconsole.Obs['inTempMin']
    maxTemp = wfpiconsole.Obs['inTempMax']

    # Calculate derived variables from indoor AIR observations
    MaxTemp, MinTemp = derive.TempMaxMin(Time,Temp,maxTemp,minTemp,Device,Config,flagAPI)

    # Convert observation units as required
    Temp    = observation.Units(Temp,   Config['Units']['Temp'])
    MaxTemp = observation.Units(MaxTemp,Config['Units']['Temp'])
    MinTemp = observation.Units(MinTemp,Config['Units']['Temp'])

    # Store derived indoor AIR observations in Data dictionary
    derivedObs              = {}
    derivedObs['inTemp']    = observation.Format(Temp,   'Temp')
    derivedObs['inTempMax'] = observation.Format(MaxTemp,'Temp')
    derivedObs['inTempMin'] = observation.Format(MinTemp,'Temp')

    # Update wfpiconsole display with derived indoor AIR observations
    updateDisplay(derivedObs,wfpiconsole,'indoorAir')

    # Set flags for required API calls
    wfpiconsole.flagAPI[3] = 0

    # Return wfpiconsole object
    return wfpiconsole

def rapidWind(Msg,wfpiconsole):

    """ Handles RapidWind Websocket messages received from either SKY or TEMPEST
        module

    INPUTS:
        Msg                 Websocket messages received from SKY or TEMPEST
        wfpiconsole         wfpiconsole object
    """

    # Replace missing observations from Rapid Wind Websocket JSON
    # with NaN
    Ob = [x if x != None else NaN for x in Msg['ob']]

    # Discard duplicate Rapid Wind Websocket messages
    if 'RapidMsg' in wfpiconsole.Obs:
        if wfpiconsole.Obs['RapidMsg']['ob'][0] == Ob[0]:
            print('Discarding duplicate Rapid Wind Websocket message')
            return

    # Extract observations from latest Rapid Wind Websocket JSON
    Time    = [Ob[0],'s']
    WindSpd = [Ob[1],'mps']
    WindDir = [Ob[2],'degrees']

    # Extract wind direction from previous SKY Rapid-Wind Websocket JSON
    if 'RapidMsg' in wfpiconsole.Obs:
        Ob = [x if x != None else NaN for x in wfpiconsole.Obs['RapidMsg']['ob']]
        WindDirOld = [Ob[2],'degrees']
    else:
        WindDirOld = [0,'degrees']

    # If windspeed is zero, freeze direction at last direction of non-zero wind
    # speed and edit latest Rapid Wind Websocket JSON. Calculate wind shift
    if WindSpd[0] == 0:
        WindDir = WindDirOld
        Msg['ob'][2] = WindDirOld[0]

    # Store latest Rapid Wind wfpiconsole.Observation JSON message
    wfpiconsole.Obs['RapidMsg'] = Msg

    # Calculate derived variables from Rapid Wind observations
    WindDir = derive.CardinalWindDirection(WindDir,WindSpd)

    # Convert observation units as required
    WindSpd = observation.Units(WindSpd,wfpiconsole.config['Units']['Wind'])
    WindDir = observation.Units(WindDir,'degrees')

    # Update wfpiconsole display with derived Rapid Wind observations
    wfpiconsole.Obs['rapidShift'] = WindDir[0] - WindDirOld[0]
    wfpiconsole.Obs['rapidSpd']   = observation.Format(WindSpd,'Wind')
    wfpiconsole.Obs['rapidDir']   = observation.Format(WindDir,'Direction')

    # Animate wind rose arrow if WindSpeedPanel panel is active
    if hasattr(wfpiconsole,'WindSpeedPanel'):
        for panel in getattr(wfpiconsole,'WindSpeedPanel'):
            panel.animateWindRose()

    # Return wfpiconsole object
    return wfpiconsole

def evtStrike(Msg,wfpiconsole):

    """ Handles lightning strike event Websocket messages received from either
        AIR or TEMPEST module

    INPUTS:
        Msg                 Websocket messages received from AIR or TEMPEST
        wfpiconsole         wfpiconsole object
    """

    # Discard duplicate evt_strike Websocket messages
    if 'evtStrikeMsg' in wfpiconsole.Obs:
        if wfpiconsole.Obs['evtStrikeMsg']['evt'][0] == Msg['evt'][0]:
            print('Discarding duplicate evt_strike Websocket message')
            return

    # Extract required observations from latest evt_strike Websocket JSON
    StrikeTime = [Msg['evt'][0],'s']
    StrikeDist = [Msg['evt'][1],'km']

    # Store latest Rapid Wind wfpiconsole.Observation JSON message
    wfpiconsole.Obs['evtStrikeMsg'] = Msg

    # Calculate derived variables from evt_strike observations
    StrikeDeltaT = derive.StrikeDeltaT(StrikeTime)

    # Convert observation units as required
    StrikeDist = observation.Units(StrikeDist,wfpiconsole.config['Units']['Distance'])

    # Update wfpiconsole display with derived Rapid Wind observations
    wfpiconsole.Obs['StrikeDeltaT'] = observation.Format(StrikeDeltaT,'TimeDelta')
    wfpiconsole.Obs['StrikeDist']   = observation.Format(StrikeDist,'StrikeDistance')

    # If required, open secondary lightning panel to show strike has been
    # detected
    if wfpiconsole.config['Display']['LightningPanel'] == '1':
        for ii,Button in enumerate(wfpiconsole.CurrentConditions.buttonList):
            if "Lightning" in Button[2]:
                wfpiconsole.CurrentConditions.SwitchPanel([],Button)

    # Set and animate lightning bolt icon if LightningPanel panel is active
    if hasattr(wfpiconsole,'LightningPanel'):
        for panel in getattr(wfpiconsole,'LightningPanel'):
            panel.setLightningBoltIcon()
            panel.animateLightningBoltIcon()

    # Return wfpiconsole object
    return wfpiconsole
