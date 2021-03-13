""" Returns the derived weather variables required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
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

# Import required library modules
from lib import derivedVariables as derive
from lib import requestAPI

# Import required Python modules
from datetime import datetime, date, time, timedelta
import numpy  as np
import requests
import bisect
import math
import pytz
import time

# Define global variables
NaN = float('NaN')

# Define circular mean
def CircularMean(angles):
    angles = np.radians(angles)
    r = np.nanmean(np.exp(1j*angles))
    return np.angle(r, deg=True) % 360

# ==============================================================================
# DEFINE DERIVED VARIABLE FUNCTIONS
# ==============================================================================
def DewPoint(Temp,Humidity):

    """ Calculate the dew point from the temperature and relative humidity

    INPUTS:
        Temp                Temperature from AIR module         [C]
        Humidity            Relative humidity from AIR module   [%]

    OUTPUT:
        DewPoint            Dew point                           [C]
    """

    # Calculate dew point unless humidity equals zero
    if Humidity[0] != 0:
        A = 17.625
        B = 243.04
        N = B*(math.log(Humidity[0]/100.0) + (A*Temp[0])/(B+Temp[0]))
        D = A-math.log(Humidity[0]/100.0) - (A*Temp[0])/(B+Temp[0])
        DewPoint = N/D
    else:
        DewPoint = NaN

    # Return Dew Point
    return [DewPoint,'c']

def FeelsLike(Temp,Humidity,windSpd,Config):

    """ Calculate the Feels Like temperature from the temperature, relative
    humidity, and wind speed

    INPUTS:
        Temp                Temperature from AIR module         [C]
        Humidity            Relative humidity from AIR module   [%]
        windSpd             Wind speed from SKY module          [m/s]
        Config              Station configuration

    OUTPUT:
        FeelsLike           Feels Like temperature              [C]
    """

    # Convert observation units as required
    TempF   = [Temp[0]*9/5 + 32,'f']
    WindMPH = [windSpd[0]*2.2369362920544,'mph']
    WindKPH = [windSpd[0]*3.6,'kph']

    # If temperature or humidity is NaN, set Feels Like temperature to NaN
    if math.isnan(Temp[0]) or math.isnan(Humidity[0]) or math.isnan(windSpd[0]):
        FeelsLike = [NaN,'c']

    # If temperature is less than 10 degrees celcius and wind speed is higher
    # than 3 mph, calculate wind chill using the Joint Action Group for
    # Temperature Indices formula
    elif Temp[0] <= 10 and WindMPH[0] > 3:
        WindChill = 13.12 + 0.6215*Temp[0] - 11.37*(WindKPH[0])**0.16 + 0.3965*Temp[0]*(WindKPH[0])**0.16
        FeelsLike = [WindChill,'c']

    # If temperature is at or above 80 degress farenheit (26.67 C), and humidity
    # is at or above 40%, calculate the Heat Index
    elif TempF[0] >= 80 and Humidity[0] >= 40:
        HeatIndex = -42.379 + (2.04901523*TempF[0]) + (10.1433127*Humidity[0]) - (0.22475541*TempF[0]*Humidity[0]) - (6.83783e-3*TempF[0]**2) - (5.481717e-2*Humidity[0]**2) + (1.22874e-3*TempF[0]**2*Humidity[0]) + (8.5282e-4*TempF[0]*Humidity[0]**2) - (1.99e-6*TempF[0]**2*Humidity[0]**2)
        FeelsLike = [(HeatIndex-32)*5/9,'c']

    # Else set Feels Like temperature to observed temperature
    else:
        FeelsLike = Temp

    # Define 'FeelsLike' temperature cutoffs
    Cutoffs = [float(item) for item in list(Config['FeelsLike'].values())]

    # Define 'FeelsLike temperature text and icon
    Description = ['Feeling extremely cold', 'Feeling freezing cold', 'Feeling very cold',
                   'Feeling cold', 'Feeling mild', 'Feeling warm', 'Feeling hot',
                   'Feeling very hot', 'Feeling extremely hot', '-']
    Icon =        ['ExtremelyCold', 'FreezingCold', 'VeryCold', 'Cold', 'Mild', 'Warm',
                   'Hot', 'VeryHot', 'ExtremelyHot', '-']
    if not math.isnan(FeelsLike[0]):
        if Config['Units']['Temp'] == 'f':
            Ind = bisect.bisect(Cutoffs,FeelsLike[0]* 9/5 + 32)
        else:
            Ind = bisect.bisect(Cutoffs,FeelsLike[0])
    else:
        Ind = 9

    # Return 'Feels Like' temperature
    return [FeelsLike[0],FeelsLike[1],Description[Ind],Icon[Ind]]

def SLP(Pres,Config):

    """ Calculate the sea level pressure from the station pressure

    INPUTS:
        Pres                Station pressure from AIR module    [mb]
        Config              Station configuration

    OUTPUT:
        SLP                 Sea level pressure                  [mb]
    """

    # Extract required configuration variables
    Elevation = Config['Station']['Elevation']
    if Config['Station']['OutAirHeight']:
        Height = Config['Station']['OutAirHeight']
    elif Config['Station']['TempestHeight']:
        Height = Config['Station']['TempestHeight']

    # Define required constants
    P0 = 1013.25
    Rd = 287.05
    GammaS = 0.0065
    g = 9.80665
    T0 = 288.15
    Elev = float(Elevation) + float(Height)

    # Calculate and return sea level pressure
    SLP = Pres[0] * (1 + ((P0/Pres[0])**((Rd*GammaS)/g)) * ((GammaS*Elev)/T0))**(g/(Rd*GammaS))
    return [SLP,'mb','-' if math.isnan(SLP) else '{:.1f}'.format(SLP)]

def SLPTrend(Pres,Time,Data3h,Config):

    """ Calculate the pressure trend from the sea level pressure over the last
        three hours

    INPUTS:
        Pres                Current station pressure from AIR module    [mb]
        Data3h              Data from previous 3 hours from AIR module
        Config              Station configuration

    OUTPUT:
        SLP                 Sea level pressure                          [mb]
    """

    # Extract pressure observation from three hours ago based on device type.
    # Return NaN for pressure trend if API call has failed
    if requestAPI.weatherflow.verifyResponse(Data3h,'obs'):
        Data3h = Data3h.json()['obs']
        if Config['Station']['OutAirID']:
            Pres3h = [Data3h[0][1] if Data3h[0][1] != None else NaN,'mb']
        elif Config['Station']['TempestID']:
            Pres3h = [Data3h[0][6] if Data3h[0][6] != None else NaN,'mb']
    else:
        Pres3h = [NaN,'mb']

    # Convert station pressure into sea level pressure
    Pres   = SLP(Pres,  Config)
    Pres3h = SLP(Pres3h,Config)

    # Calculate pressure trend
    Trend = (Pres[0] - Pres3h[0])/3

    # Remove sign from pressure trend if it rounds to 0.0
    if abs(Trend) < 0.05:
        Trend = abs(Trend)

    # Define pressure trend text
    if math.isnan(Trend):
        TrendTxt = '-'
    elif Trend > 2/3:
        TrendTxt = '[color=ff8837ff]Rising rapidly[/color]'
    elif Trend >= 1/3:
        TrendTxt = '[color=ff8837ff]Rising[/color]'
    elif Trend <= -2/3:
        TrendTxt = '[color=00a4b4ff]Falling rapidly[/color]'
    elif Trend <= -1/3:
        TrendTxt = '[color=00a4b4ff]Falling[/color]'
    else:
        TrendTxt = '[color=9aba2fff]Steady[/color]'

    # Define weather tendency based on pressure and trend
    if Pres[0] >= 1023:
        if 'Falling rapidly' in TrendTxt:
            Tendency = 'Becoming cloudy and warmer'
        else:
            Tendency = 'Fair conditions likely'
    elif 1009 < Pres[0] < 1023:
        if 'Falling rapidly' in TrendTxt:
            Tendency = 'Rainy conditions likely'
        else:
            Tendency = 'Conditions unchanged'
    elif Pres[0] <= 1009:
        if 'Falling rapidly' in TrendTxt:
            Tendency = 'Stormy conditions likely'
        elif 'Falling' in TrendTxt:
            Tendency = 'Rainy conditions likely'
        else:
            Tendency = 'Becoming clearer and cooler'
    else:
        Tendency = '-'

    # Return pressure trend
    return [Trend,'mb/hr',TrendTxt,Tendency]

def SLPMaxMin(Time,Pres,maxPres,minPres,Device,Config,flagAPI):

    """ Calculate maximum and minimum pressure since midnight station time

    INPUTS:
        Time                Current observation time        [s]
        Temp                Current pressure                [mb]
        maxPres             Current maximum pressure        [mb]
        minPres             Current minimum pressure        [mb]
        Device              Device ID
        Config              Station configuration
        flagAPI             Flag for required API calls

    OUTPUT:
        MaxTemp             Maximum pressure                [mb]
        MinTemp             Minumum pressure                [mb]
    """

    # Calculate sea level pressure
    SLP = derive.SLP(Pres,Config)

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Set time format based on user configuration
    if Config['Display']['TimeFormat'] == '12 hr':
        if Config['System']['Hardware'] != 'Other':
            Format = '%-I:%M %P'
        else:
            Format = '%I:%M %p'
    else:
        Format = '%H:%M'

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily maximum and minimum pressure
    if maxPres[0] == '-' or flagAPI:

        # Download pressure data from the current day
        Data = requestAPI.weatherflow.Today(Device,Config)

        # Calculate maximum and minimum pressure. Return NaN if API call fails
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):

            # Extract data from API call based on device type
            Data = Data.json()['obs']
            Time = [item[0] for item in Data if item[0] != None]
            if Config['Station']['OutAirID']:
                Pres = [[item[1],'mb'] for item in Data if item[1] != None]
            elif Config['Station']['TempestID']:
                Pres = [[item[6],'mb'] for item in Data if item[6] != None]

            # Calculate sea level pressure
            SLP = [derive.SLP(P,Config) for P in Pres]

            # Define maximum and minimum pressure
            if len(SLP) > 0:
                MaxPres = [max(SLP)[0],'mb',datetime.fromtimestamp(Time[SLP.index(max(SLP))],Tz).strftime(Format),max(SLP)[0],Now]
                MinPres = [min(SLP)[0],'mb',datetime.fromtimestamp(Time[SLP.index(min(SLP))],Tz).strftime(Format),min(SLP)[0],Now]
            else:
                MaxPres = [NaN,'mb','-',NaN,Now]
                MinPres = [NaN,'mb','-',NaN,Now]
        else:
            MaxPres = [NaN,'mb','-',NaN,Now]
            MinPres = [NaN,'mb','-',NaN,Now]

    # Else if midnight has passed, reset maximum and minimum pressure
    elif Now.date() > maxPres[4].date():
        MaxPres = [SLP[0],'mb',datetime.fromtimestamp(Time[0],Tz).strftime(Format),SLP[0],Now]
        MinPres = [SLP[0],'mb',datetime.fromtimestamp(Time[0],Tz).strftime(Format),SLP[0],Now]

    # Else if current pressure is greater than maximum recorded pressure, update
    # maximum pressure
    elif SLP[0] > maxPres[3]:
        MaxPres = [SLP[0],'mb',datetime.fromtimestamp(Time[0],Tz).strftime(Format),SLP[0],Now]
        MinPres = [minPres[3],'mb',minPres[2],minPres[3],Now]

    # Else if current pressure is less than minimum recorded pressure, update
    # minimum pressure and time
    elif SLP[0] < minPres[3]:
        MaxPres = [maxPres[3],'mb',maxPres[2],maxPres[3],Now]
        MinPres = [SLP[0],'mb',datetime.fromtimestamp(Time[0],Tz).strftime(Format),SLP[0],Now]

    # Else maximum and minimum pressure unchanged, return existing values
    else:
        MaxPres = [maxPres[3],'mb',maxPres[2],maxPres[3],Now]
        MinPres = [minPres[3],'mb',minPres[2],minPres[3],Now]

    # Return required variables
    return MaxPres,MinPres

def TempMaxMin(Time,Temp,maxTemp,minTemp,Device,Config,flagAPI):

    """ Calculate maximum and minimum temperature for specified device since
        midnight station time

    INPUTS:
        Time                Current observation time                    [s]
        Temp                Current outdoor temperature                 [deg C]
        maxTemp             Current maximum outdoor temperature         [deg C]
        minTemp             Current minimum outdoor temperature         [deg C]
        Device              Device ID
        Config              Station configuration
        flagAPI             Flag for required API calls

    OUTPUT:
        MaxTemp             Maximum outdoor temperature                 [deg C]
        MinTemp             Minumum outdoot temperature                 [deg C]
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Set time format based on user configuration
    if Config['Display']['TimeFormat'] == '12 hr':
        if Config['System']['Hardware'] != 'Other':
            Format = '%-I:%M %P'
        else:
            Format = '%I:%M %p'
    else:
        Format = '%H:%M'

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily maximum and minimum temperature
    if maxTemp[0] == '-' or flagAPI:

        # Download temperature data from the current day
        Data = requestAPI.weatherflow.Today(Device,Config)

        # Calculate maximum and minimum temperature. Return NaN if API call
        # fails
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):

            # Extract data from API call based on specified device ID
            Data = Data.json()['obs']
            Time = [[item[0],'s'] for item in Data if item[0] != None]
            if Device == Config['Station']['TempestID']:
                Temp = [[item[7],'c'] for item in Data if item[7] != None]
            elif Device in {Config['Station']['OutAirID'], Config['Station']['InAirID']}:
                Temp = [[item[2],'c'] for item in Data if item[2] != None]

            # Define maximum and minimum temperature and time
            MaxTemp = [max(Temp)[0],'c',datetime.fromtimestamp(Time[Temp.index(max(Temp))][0],Tz).strftime(Format),max(Temp)[0],Now]
            MinTemp = [min(Temp)[0],'c',datetime.fromtimestamp(Time[Temp.index(min(Temp))][0],Tz).strftime(Format),min(Temp)[0],Now]
        else:
            MaxTemp = [NaN,'c','-',NaN,Now]
            MinTemp = [NaN,'c','-',NaN,Now]

    # Else if midnight has passed, reset maximum and minimum temperature
    elif Now.date() > maxTemp[4].date():
        MaxTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],Tz).strftime(Format),Temp[0],Now]
        MinTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],Tz).strftime(Format),Temp[0],Now]

    # Else if current temperature is greater than maximum recorded temperature,
    # update maximum temperature
    elif Temp[0] > maxTemp[3]:
        MaxTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],Tz).strftime(Format),Temp[0],Now]
        MinTemp = [minTemp[3],'c',minTemp[2],minTemp[3],Now]

    # Else if current temperature is less than minimum recorded temperature,
    # update minimum temperature
    elif Temp[0] < minTemp[3]:
        MaxTemp = [maxTemp[3],'c',maxTemp[2],maxTemp[3],Now]
        MinTemp = [Temp[0],'c',datetime.fromtimestamp(Time[0],Tz).strftime(Format),Temp[0],Now]

    # Else maximum and minimum temperature unchanged, return existing values
    else:
        MaxTemp = [maxTemp[3],'c',maxTemp[2],maxTemp[3],Now]
        MinTemp = [minTemp[3],'c',minTemp[2],minTemp[3],Now]

    # Return required variables
    return MaxTemp,MinTemp

def StrikeDeltaT(StrikeTime):

    """ Calculate time since last lightning strike

    INPUTS:
        StrikeTime          Time of last lightning strike               [s]

    OUTPUT:
        StrikeDeltaT        Time since last lightning strike            [s]
    """

    # Calculate time since last lightning strike
    Now = int(time.time())
    deltaT = Now - StrikeTime[0]
    deltaT = [deltaT,'s',deltaT]

    # Return time since and distance to last lightning strike
    return deltaT

def StrikeFrequency(obTime,Data3h,Config):

    """ Calculate lightning strike frequency over the previous 10 minutes and
        three hours

    INPUTS:
        obTime              Time of latest observation
        Data3h              Data from previous 3 hours from AIR module
        Config              Station configuration

    OUTPUT:
        strikeFrequency     Strike frequency over the previous 10       [Count]
                            minutes and three hours
    """

    # Extract lightning strike count over the last three hours. Return NaN for
    # strikeFrequency if API call has failed
    if requestAPI.weatherflow.verifyResponse(Data3h,'obs'):
        Data3h  = Data3h.json()['obs']
        Time    = [item[0] for item in Data3h if item[0] != None]
        if Config['Station']['OutAirID']:
            Count3h = [item[4] for item in Data3h if item[4] != None]
        elif Config['Station']['TempestID']:
            Count3h = [item[15] for item in Data3h if item[15] != None]
    else:
        return [NaN,'/min',NaN,'/min']

    # Convert lists to Numpy arrays
    Count3h = np.array(Count3h,dtype=np.float32)
    Time    = np.array(Time,   dtype=np.float64)

    # Calculate average strike frequency over the last three hours
    activeStrikes = Count3h[Count3h>0]
    if len(activeStrikes) > 0:
        strikeFrequency3h = [np.nanmean(activeStrikes),'/min']
    else:
        strikeFrequency3h = [np.nanmean([0]),'/min']

    # Calculate average strike frequency over the last 10 minutes
    Count10m = Count3h[np.where(Time >= obTime[0]-600)]
    activeStrikes = Count10m[Count10m>0]
    if len(activeStrikes) > 0:
        strikeFrequency10m = [np.nanmean(activeStrikes),'/min']
    else:
        strikeFrequency10m = [np.nanmean([0]),'/min']

    # Return strikeFrequency for last 10 minutes and last three hours
    return strikeFrequency10m + strikeFrequency3h

def StrikeCount(Count,strikeCount,Device,Config,flagAPI):

    """ Calculate the number of lightning strikes for the last day/month/year

    INPUTS:
        Count               Number of lightning strikes in the past minute  [Count]
        strikeCount         Dictionary containing fields:
            Today               Number of lightning strikes today           [Count]
            Yesterday           Number of lightning strikes in last month   [Count]
            Year                Number of lightning strikes in last year    [Count]
        Device              Device ID
        Config              Station configuration
        flagAPI             Flag for required API calls

    OUTPUT:
        strikeCount         Dictionary containing fields:
            Today               Number of lightning strikes today           [Count]
            Yesterday           Number of lightning strikes in last month   [Count]
            Year                Number of lightning strikes in last year    [Count]
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate total daily lightning strikes
    if strikeCount['Today'][0] == '-' or flagAPI:

        # Download lightning strike data from the current day
        Data = requestAPI.weatherflow.Today(Device,Config)

        # Calculate daily lightning strike total. Return NaN if API call has
        # failed
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):
            Data = Data.json()['obs']
            if Config['Station']['OutAirID']:
                Strikes = [item[4] for item in Data if item[4] != None]
            elif Config['Station']['TempestID']:
                Strikes = [item[15] for item in Data if item[15] != None]
            todayStrikes = [sum(x for x in Strikes),'count',sum(x for x in Strikes),Now]
        else:
            todayStrikes = [NaN,'count',NaN,Now]

    # Else if midnight has passed, reset daily lightning strike count to zero
    elif Now.date() > strikeCount['Today'][3].date():
        todayStrikes = [Count[0],'count',Count[0],Now]

    # Else, calculate current daily lightning strike count
    else:
        currentCount = strikeCount['Today'][2]
        updatedCount = currentCount + Count[0] if not math.isnan(Count[0]) else currentCount
        todayStrikes = [updatedCount,'count',updatedCount,Now]

    # If console is initialising, download all data for current month using
    # Weatherflow API and calculate total monthly lightning strikes
    if strikeCount['Month'][0] == '-' or flagAPI:

        # Download lightning strike data from the current month
        Data = requestAPI.weatherflow.Month(Device,Config)

        # Calculate monthly lightning strike total. Return NaN if API call
        # has failed
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):
            Data = Data.json()['obs']
            if Config['Station']['OutAirID']:
                Strikes = [item[4] for item in Data if item[4] != None]
            elif Config['Station']['TempestID']:
                Strikes = [item[15] for item in Data if item[15] != None]
            monthStrikes = [sum(x for x in Strikes),'count',sum(x for x in Strikes),Now]
        else:
            monthStrikes = [NaN,'count',NaN,Now]

        # Adjust monthly lightning strike total for strikes that have been
        # recorded today
        if not math.isnan(todayStrikes[0]):
            monthStrikes[0] += todayStrikes[0]
            monthStrikes[2] += todayStrikes[2]

    # Else if the end of the month has passed, reset monthly lightning strike
    # count to zero
    elif Now.month > strikeCount['Month'][3].month:
        monthStrikes = [Count[0],'count',Count[0],Now]

    # Else, calculate current monthly lightning strike count
    else:
        currentCount = strikeCount['Month'][2]
        updatedCount = currentCount + Count[0] if not math.isnan(Count[0]) else currentCount
        monthStrikes = [updatedCount,'count',updatedCount,Now]

    # If console is initialising, download all data for current year using
    # Weatherflow API and calculate total yearly lightning strikes
    if strikeCount['Year'][0] == '-' or flagAPI:

        # Download lightning strike data from the current year
        Data = requestAPI.weatherflow.Year(Device,Config)

        # Calculate yearly lightning strikes total. Return NaN if API call
        # has failed
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):
            bucketStep = Data.json()['bucket_step_minutes']
            Data = Data.json()['obs']
            if Config['Station']['OutAirID']:
                Strikes = [item[4] for item in Data if item[4] != None]
            elif Config['Station']['TempestID']:
                if bucketStep == 1440:
                    Strikes = [item[24] for item in Data if item[24] != None]
                else:
                    Strikes = [item[15] for item in Data if item[15] != None]
            yearStrikes = [sum(x for x in Strikes),'count',sum(x for x in Strikes),Now]
        else:
            yearStrikes = [NaN,'count',NaN,Now]

        # Adjust yearly lightning strike total for strikes that have been
        # recorded today
        if not math.isnan(todayStrikes[0]):
            yearStrikes[0] += todayStrikes[0]
            yearStrikes[2] += todayStrikes[2]

    # Else if the end of the year has passed, reset monthly and yearly lightning
    # strike count to zero
    elif Now.year > strikeCount['Year'][3].year:
        monthStrikes = [Count[0],'count',Count[0],Now]
        yearStrikes  = [Count[0],'count',Count[0],Now]

    # Else, calculate current yearly lightning strike count
    else:
        currentCount = strikeCount['Year'][2]
        updatedCount = currentCount + Count[0] if not math.isnan(Count[0]) else currentCount
        yearStrikes = [updatedCount,'count',updatedCount,Now]

    # Return Daily, Monthly, and Yearly lightning strike counts
    return {'Today':todayStrikes, 'Month':monthStrikes, 'Year':yearStrikes}

def RainRate(rainAccum):

    """ Calculate the average windspeed since midnight station time

    INPUTS:
        windSpd             Current 1 minute rain accumulation             [mm]

    OUTPUT:
        rainRate            Current instantaneous rain rate                [mm/hr]
    """

    # Calculate instantaneous rain rate from instantaneous rain accumulation
    Rate = rainAccum[0]*60

    # Define rain rate text based on calculated
    if math.isnan(Rate):
        RateText = '-'
    elif Rate == 0:
        RateText = 'Currently Dry'
    elif Rate < 0.25:
        RateText = 'Very Light Rain'
    elif Rate < 1.0:
        RateText = 'Light Rain'
    elif Rate < 4.0:
        RateText = 'Moderate Rain'
    elif Rate < 16.0:
        RateText = 'Heavy Rain'
    elif Rate < 50.0:
        RateText = 'Very Heavy Rain'
    else:
        RateText = 'Extreme Rain'

    # Return instantaneous rain rate and text
    return [Rate,'mm/hr',RateText,Rate]

def RainAccumulation(dailyRain,rainAccum,Device,Config,flagAPI):

    """ Calculate the rain accumulation for today/yesterday/month/year

    INPUTS:
        dailyRain           Daily rain accumulation                         [mm]
        rainAccum           Dictionary containing fields:
            Today               Rain accumulation for the current day       [mm]
            Yesterday           Rain accumulation yesterday                 [mm]
            Month               Rain accumulation for the current month     [mm]
            Year                Rain accumulation for the current year      [mm]
        Device              Device ID
        Config              Station configuration
        flagAPI             Flag for required API calls

    OUTPUT:
        rainAccum           Dictionary containing fields:
            Today               Rain accumulation for the current day       [mm]
            Yesterday           Rain accumulation yesterday                 [mm]
            Month               Rain accumulation for the current month     [mm]
            Year                Rain accumulation for the current year      [mm]
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Set current daily rainfall accumulation
    TodayRain = [dailyRain[0],'mm',dailyRain[0],Now]

    # If console is initialising, download all data for yesterday using
    # Weatherflow API and calculate total daily rainfall
    if rainAccum['Yesterday'][0] == '-' or flagAPI:

        # Download rainfall data for yesterday
        Data = requestAPI.weatherflow.Yesterday(Device,Config)

        # Calculate yesterday rainfall total. Return NaN if API call has
        # failed
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):
            Data = Data.json()['obs']
            if Config['Station']['SkyID']:
                Rain = [item[3] for item in Data if item[3] != None]
            elif Config['Station']['TempestID']:
                Rain = [item[12] for item in Data if item[12] != None]
            YesterdayRain = [sum(x for x in Rain),'mm',sum(x for x in Rain),Now]
        else:
            YesterdayRain = [NaN,'mm',NaN,Now]

    # Else if midnight has passed, set yesterday rainfall accumulation equal to
    # rainAccum['Today'] (which still contains yesterday's accumulation)
    elif Now.date() > rainAccum['Today'][3].date():
        YesterdayRain = [rainAccum['Today'][2],'mm',rainAccum['Today'][2],Now]

    # Else, set yesterday rainfall accumulation as unchanged
    else:
        YesterdayRain = [rainAccum['Yesterday'][2],'mm',rainAccum['Yesterday'][2],Now]

    # If console is initialising and today is the first day on the month, set
    # monthly rainfall to current daily rainfall
    if rainAccum['Month'][0] == '-' and Now.day == 1:
        MonthRain = [dailyRain[0],'mm',0,Now]

    # If console is initialising, download all data for current month using
    # Weatherflow API and calculate total monthly rainfall
    elif rainAccum['Month'][0] == '-' or flagAPI:

        # Download rainfall data for last Month
        Data = requestAPI.weatherflow.Month(Device,Config)

        # Calculate monthly rainfall total. Return NaN if API call has
        # failed
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):
            Data = Data.json()['obs']
            if Config['Station']['SkyID']:
                Rain = [item[3] for item in Data if item[3] != None]
            elif Config['Station']['TempestID']:
                Rain = [item[28] for item in Data if item[28] != None]
            MonthRain = [sum(x for x in Rain),'mm',sum(x for x in Rain),Now]
        else:
            MonthRain = [NaN,'mm',NaN,Now]

        # Adjust monthly rainfall total for rain that has fallen today
        if not math.isnan(TodayRain[0]):
            MonthRain[0] += dailyRain[0]

    # Else if the end of the month has passed, reset monthly rain accumulation
    # to current daily rain accumulation
    elif Now.month > rainAccum['Month'][3].month:
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        MonthRain  = [dailyAccum,'mm',0,Now]

    # Else if midnight has passed, permanently add rainAccum['Today'] (which
    # still contains yesterday's accumulation) and current daily rainfall to
    # monthly rain accumulation
    elif Now.date() > rainAccum['Month'][3].date():
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        MonthRain  = [rainAccum['Month'][2] + rainAccum['Today'][2] + dailyAccum,'mm',rainAccum['Month'][2] + rainAccum['Today'][2],Now]

    # Else, update current monthly rainfall accumulation
    else:
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        MonthRain  = [rainAccum['Month'][2] + dailyAccum,'mm',rainAccum['Month'][2],Now]

    # If console is initialising and today is the first day on the year, set
    # yearly rainfall to current daily rainfall
    if rainAccum['Year'][0] == '-' and Now.timetuple().tm_yday == 1:
        YearRain = [dailyRain[0],'mm',0,Now]

    # If console is initialising and today is during the first month of the
    # year, set yearly rainfall to current monthly rainfall
    elif rainAccum['Year'][0] == '-' and Now.timetuple().tm_mon == 1:
        YearRain = MonthRain

    # If console is initialising, download all data for current year using
    # Weatherflow API and calculate total yearly rainfall
    elif rainAccum['Year'][0] == '-' or flagAPI:

        # Download rainfall data for last Month
        Data = requestAPI.weatherflow.Year(Device,Config)

        # Calculate yearly rainfall total. Return NaN if API call has failed
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):
            Data = Data.json()['obs']
            if Config['Station']['SkyID']:
                Rain = [item[3] for item in Data if item[3] != None]
            elif Config['Station']['TempestID']:
                Rain = [item[28] for item in Data if item[28] != None]
            YearRain = [sum(x for x in Rain),'mm',sum(x for x in Rain),Now]
        else:
            YearRain = [NaN,'mm',NaN,Now]

        # Adjust yearly rainfall total for rain that has fallen today
        if not math.isnan(dailyRain[0]):
            YearRain[0] += dailyRain[0]

    # Else if the end of the year has passed, reset monthly and yearly rain
    # accumulation to current daily rain accumulation
    elif Now.year > rainAccum['Year'][3].year:
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        YearRain   = [dailyAccum,'mm',0,Now]
        MonthRain  = [dailyAccum,'mm',0,Now]

    # Else if midnight has passed, permanently add rainAccum['Today'] (which
    # still contains yesterday's accumulation) and current daily rainfall to
    # yearly rain accumulation
    elif Now.date() > rainAccum['Year'][3].date():
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        YearRain  = [rainAccum['Year'][2] + rainAccum['Today'][2] + dailyAccum,'mm',rainAccum['Year'][2] + rainAccum['Today'][2],Now]

    # Else, calculate current yearly rain accumulation
    else:
        dailyAccum = dailyRain[0] if not math.isnan(dailyRain[0]) else 0
        YearRain   = [rainAccum['Year'][2] + dailyAccum,'mm',rainAccum['Year'][2],Now]

    # Return Daily, Monthly, and Yearly rainfall accumulation totals
    return {'Today':TodayRain, 'Yesterday':YesterdayRain, 'Month':MonthRain, 'Year':YearRain}

def MeanWindSpeed(windSpd,avgWind,Device,Config,flagAPI):

    """ Calculate the average windspeed since midnight station time

    INPUTS:
        windSpd             Current wind speed                             [m/s]
        avgWind             Current average wind speed since midnight      [m/s]
        Device              Device ID
        Config              Station configuration
        flagAPI             Flag for required API calls

    OUTPUT:
        AvgWind             Average wind speed since midnight              [m/s]
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily averaged windspeed
    if avgWind[0] == '-' or flagAPI:

        # Download windspeed data for current day
        Data = requestAPI.weatherflow.Today(Device,Config)

        # Calculate daily averaged wind speed. Return NaN if API call has failed
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):
            Data = Data.json()['obs']
            if Config['Station']['SkyID']:
                windSpd = [item[5] for item in Data if item[5] != None]
            elif Config['Station']['TempestID']:
                windSpd = [item[2] for item in Data if item[2] != None]
            Sum = sum(x for x in windSpd)
            Length = len(windSpd)
            AvgWind = [Sum/Length,'mps',Sum/Length,Length,Now]
        else:
            AvgWind = [NaN,'mps',NaN,NaN,Now]

    # Else if midnight has passed, reset daily averaged wind speed
    elif Now.date() > avgWind[4].date():
        AvgWind = [windSpd[0],'mps',windSpd[0],1,Now]

    # Else, calculate current daily averaged wind speed
    else:
        Length = avgWind[3] + 1
        currentAvg = avgWind[2]
        if not math.isnan(windSpd[0]):
            updatedAvg = (Length-1)/Length * currentAvg + 1/Length * windSpd[0]
            AvgWind = [updatedAvg,'mps',updatedAvg,Length,Now]
        else:
            AvgWind = [currentAvg,'mps',currentAvg,Length-1,Now]

    # Return daily averaged wind speed
    return AvgWind

def MaxWindGust(windGust,maxGust,Device,Config,flagAPI):

    """ Calculate the maximum wind gust since midnight station time

    INPUTS:
        windGust            Current wind gust                              [m/s]
        maxGust             Current maximum wind gust since midnight       [m/s]
        Device              Device ID
        Config              Station configuration
        flagAPI             Flag for required API calls

    OUTPUT:
        maxGust             Maximum wind gust since midnight               [m/s]
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate daily maximum wind gust
    if maxGust == '--' or flagAPI:

        # Download windspeed data for current day
        Data = requestAPI.weatherflow.Today(Device,Config)

        # Calculate daily maximum wind gust. Return NaN if API call has failed
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):
            Data = Data.json()['obs']
            if Config['Station']['SkyID']:
                windGust = [item[6] for item in Data if item[6] != None]
            elif Config['Station']['TempestID']:
                windGust = [item[3] for item in Data if item[3] != None]
            maxGust  = [max(x for x in windGust),'mps',max(x for x in windGust),Now]
        else:
            maxGust = [NaN,'mps',NaN,Now]

    # Else if midnight has passed, reset maximum recorded wind gust
    elif Now.date() > maxGust[3].date():
        maxGust = [windGust[0],'mps',windGust[0],Now]

    # Else if current gust speed is greater than maximum recorded gust speed,
    # update maximum gust speed
    elif windGust[0] > maxGust[2]:
        maxGust = [windGust[0],'mps',windGust[0],Now]

    # Else maximum gust speed is unchanged, return existing value
    else:
        maxGust = [maxGust[2],'mps',maxGust[2],Now]

    # Return maximum wind gust
    return maxGust

def CardinalWindDirection(windDir,windSpd=[1,'mps']):

    """ Defines the cardinal wind direction from the current wind direction in
        degrees. Sets the wind direction as "Calm" if current wind speed is zero

    INPUTS:
        windDir             Current wind direction                     [degrees]
        windSpd             Current wind speed                             [m/s]

    OUTPUT:
        cardinalWind        Cardinal wind direction
    """

    # Define all possible cardinal wind directions and descriptions
    Direction = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW','N']
    Description = ['Due North','North NE','North East','East NE','Due East','East SE','South East','South SE',
                   'Due South','South SW','South West','West SW','Due West','West NW','North West','North NW',
                   'Due North']

    # Define actual cardinal wind direction and description based on current
    # wind direction in degrees
    if windSpd[0] == 0:
        Direction = 'Calm'
        Description = '[color=9aba2fff]Calm[/color]'
        cardinalWind = [windDir[0],windDir[1],Direction,Description]
    elif math.isnan(windDir[0]):
        cardinalWind = [windDir[0],windDir[1],'-','-']
    else:
        Ind = int(round(windDir[0]/22.5))
        Direction = Direction[Ind]
        Description = Description[Ind].split()[0] + ' [color=9aba2fff]' + Description[Ind].split()[1] + '[/color]'
        cardinalWind = [windDir[0],windDir[1],Direction,Description]

    # Return cardinal wind direction and description
    return cardinalWind

def BeaufortScale(windSpd):

    """ Defines the Beaufort scale value from the current wind speed

    INPUTS:
        windSpd             Current wind speed                             [m/s]

    OUTPUT:
        beaufortScale       Beaufort Scale speed, description, and icon
    """

    # Define Beaufort scale cutoffs and Force numbers
    Cutoffs = [0.5,1.5,3.3,5.5,7.9,10.7,13.8,17.1,20.7,24.4,28.4,32.6]
    Force = [0,1,2,3,4,5,6,7,8,9,10,11,12]
    Description = ['Calm Conditions', 'Light Air' ,        'Light Breeze',  'Gentle Breeze',
                   'Moderate Breeze', 'Fresh Breeze',      'Strong Breeze', 'Near Gale Force',
                   'Gale Force',      'Severe Gale Force', 'Storm Force',   'Violent Storm',
                   'Hurricane Force']

    # Define Beaufort Scale wind speed, description, and icon
    if math.isnan(windSpd[0]):
        Beaufort = ['-','-','-']
    else:
        Ind = bisect.bisect(Cutoffs,windSpd[0])
        Beaufort = [float(Force[Ind]),str(Force[Ind]),Description[Ind]]

    # Return Beaufort Scale speed, description, and icon
    beaufortScale = windSpd + Beaufort
    return beaufortScale

def UVIndex(uvLevel):

    """ Defines the UV index from the current UV level

    INPUTS:
        uvLevel             Current UV level                               [m/s]

    OUTPUT:
        uvIndex             UV index
    """

    # Define UV Index cutoffs and level descriptions
    Cutoffs = [0,3,6,8,11]
    Level   = ['None','Low','Moderate','High','Very High','Extreme']

    # Define UV index colours
    Grey   = '#646464'
    Green  = '#558B2F'
    Yellow = '#F9A825'
    Orange = '#EF6C00'
    Red    = '#B71C1C'
    Violet = '#6A1B9A'
    Color  = [Grey,Green,Yellow,Orange,Red,Violet]

    # Set the UV index
    if math.isnan(uvLevel[0]):
        uvIndex = [uvLevel[0],'index','-',Grey]
    else:
        if uvLevel[0] > 0:
            Ind = bisect.bisect(Cutoffs,round(uvLevel[0],1))
        else:
            Ind = 0
        uvIndex = [round(uvLevel[0],1),'index',Level[Ind],Color[Ind]]

    # Return UV Index icon
    return uvIndex

def peakSunHours(Radiation,peakSun,Astro,Device,Config,flagAPI):

    """ Calculate peak sun hours since midnight and daily solar potential

    INPUTS:
        Radiation           Current solar radiation                        [W/m^2]
        maxGust             Current peak sun hours since midnight          [hours]
        Astro               Dictionary containing sunrise/sunset info
        Device              Device ID
        Config              Station configuration
        flagAPI             Flag for required API calls

    OUTPUT:
        peakSun             Peak sun hours since midnight and solar potential
    """

    # Define current time in station timezone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # If console is initialising, download all data for current day using
    # Weatherflow API and calculate Peak Sun Hours
    if peakSun[0] == '-' or flagAPI:

        # Download solar radiation data for current day
        Data = requestAPI.weatherflow.Today(Device,Config)

        # Calculate Peak Sun Hours. Return NaN if API call has failed
        if requestAPI.weatherflow.verifyResponse(Data,'obs'):
            Data = Data.json()['obs']
            if Config['Station']['SkyID']:
                Radiation = [item[10] for item in Data if item[10] != None]
            elif Config['Station']['TempestID']:
                Radiation = [item[11] for item in Data if item[11] != None]
            watthrs = sum([item*1/60 for item in Radiation])
            peakSun = [watthrs/1000,'hrs',watthrs,Now]
        else:
            peakSun = [NaN,'hrs',NaN,Now]

    # Else if midnight has passed, reset Peak Sun Hours
    elif Now.date() > peakSun[3].date():
        watthrs = Radiation[0] * 1/60
        peakSun = [watthrs/1000,'hrs',watthrs,Now]

    # Else calculate current Peak Sun Hours
    else:
        watthrs = peakSun[2] + Radiation[0]*1/60 if not math.isnan(Radiation[0]) else peakSun[2]
        peakSun = [watthrs/1000,'hrs',watthrs,Now]

    # Calculate proportion of daylight hours that have passed
    daylightTotal  = (Astro['Sunset'][0] - Astro['Sunrise'][0]).total_seconds()
    if Astro['Sunrise'][0] <= Now <= Astro['Sunset'][0]:
        daylightElapsed = (Now - Astro['Sunrise'][0]).total_seconds()
    else:
        daylightElapsed = daylightTotal
    daylightFactor = daylightElapsed/daylightTotal

    # Define daily solar potential
    if math.isnan(peakSun[0]):
        peakSun.append('-')
    if peakSun[0]/daylightFactor == 0:
        peakSun.append('[color=#646464ff]None[/color]')
    elif peakSun[0]/daylightFactor < 2:
        peakSun.append('[color=#4575b4ff]Limited[/color]')
    elif peakSun[0]/daylightFactor < 4:
        peakSun.append('[color=#fee090ff]Moderate[/color]')
    elif peakSun[0]/daylightFactor < 6:
        peakSun.append('[color=#f46d43ff]Good[/color]')
    else:
        peakSun.append('[color=#d73027ff]Excellent[/color]')

    # Return Peak Sun Hours
    return peakSun
