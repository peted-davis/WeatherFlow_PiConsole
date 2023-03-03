""" Formats and sets the required units of observations displayed on the
Raspberry Pi Python console for Weather Flow Smart Home Weather Stations.
Copyright (C) 2018-2023  Peter Davis

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

# Import required modules
from lib      import derivedVariables as derive
from datetime import datetime
import pytz


def Units(Obs, Unit):

    """ Sets the required observation units

    INPUTS:
        Obs             Observations with current units
        Unit            Required output unit

    OUTPUT:
        cObs            Observation converted into required unit
    """

    # Convert temperature observations
    cObs = Obs[:]
    if Unit in ['f', 'c']:
        for ii, T in enumerate(Obs):
            if T == 'c':
                if Unit == 'f':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * (9 / 5) + 32
                    cObs[ii] = 'f'
                else:
                    cObs[ii - 1] = Obs[ii - 1]
                    cObs[ii] = 'c'
            if T in ['dc', 'c/hr']:
                if Unit == 'f':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * (9 / 5)
                    if T == 'dc':
                        cObs[ii] = 'f'
                    elif T == 'c/hr':
                        cObs[ii] = 'f/hr'
                else:
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1]
                    if T == 'dc':
                        cObs[ii] = 'c'

    # Convert pressure and pressure trend observations
    elif Unit in ['inhg', 'mmhg', 'hpa', 'mb']:
        for ii, P in enumerate(Obs):
            if P in ['mb', 'mb/hr']:
                if Unit == 'inhg':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * 0.0295301
                    if P == 'mb':
                        cObs[ii] = ' inHg'
                    else:
                        cObs[ii] = ' inHg/hr'
                elif Unit == 'mmhg':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * 0.750063
                    if P == 'mb':
                        cObs[ii] = ' mmHg'
                    else:
                        cObs[ii] = ' mmHg/hr'
                elif Unit == 'hpa':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1]
                    if P == 'mb':
                        cObs[ii] = ' hPa'
                    else:
                        cObs[ii] = ' hPa/hr'
                else:
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1]
                    if P == 'mb':
                        cObs[ii] = ' mb'
                    else:
                        cObs[ii] = ' mb/hr'

    # Convert windspeed observations
    elif Unit in ['mph', 'lfm', 'kts', 'kph', 'bft', 'mps']:
        for ii, W in enumerate(Obs):
            if W == 'mps':
                if Unit == 'mph' or Unit == 'lfm':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * 2.2369362920544
                    cObs[ii] = 'mph'
                elif Unit == 'kts':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * 1.9438
                    cObs[ii] = 'kts'
                elif Unit == 'kph':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * 3.6
                    cObs[ii] = 'km/h'
                elif Unit == 'bft':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = derive.beaufortScale(Obs[ii - 1:ii + 1])[2]
                    cObs[ii] = 'bft'
                else:
                    cObs[ii - 1] = Obs[ii - 1]
                    cObs[ii] = 'm/s'

    # Convert wind direction observations
    elif Unit in ['degrees', 'cardinal']:
        for ii, W in enumerate(Obs):
            if W == 'degrees':
                if cObs[ii - 1] is None:
                    cObs[ii - 1] = '-'
                    cObs[ii] = ''
                elif cObs[ii - 1] == 'calm':
                    cObs[ii - 1] = 'Calm'
                    cObs[ii] = ''
                elif Unit == 'cardinal':
                    cObs[ii - 1] = derive.cardinalWindDir(Obs[ii - 1:ii + 1])[2]
                    cObs[ii] = ''
                else:
                    cObs[ii - 1] = Obs[ii - 1]
                    cObs[ii] = 'degrees'

    # Convert rain accumulation and rain rate observations
    elif Unit in ['in', 'cm', 'mm']:
        for ii, Prcp in enumerate(Obs):
            if Prcp in ['mm', 'mm/hr']:
                if Unit == 'in':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * 0.0393701
                    if Prcp == 'mm':
                        cObs[ii] = ' in'
                    else:
                        cObs[ii] = ' in/hr'
                elif Unit == 'cm':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * 0.1
                    if Prcp == 'mm':
                        cObs[ii] = ' cm'
                    else:
                        cObs[ii] = ' cm/hr'
                else:
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1]
                    if Prcp == 'mm':
                        cObs[ii] = ' mm'
                    else:
                        cObs[ii] = ' mm/hr'

    # Convert distance observations
    elif Unit in ['km', 'mi']:
        for ii, Dist in enumerate(Obs):
            if Dist == 'km':
                if Unit == 'mi':
                    if Obs[ii - 1] is not None:
                        cObs[ii - 1] = Obs[ii - 1] * 0.62137
                    cObs[ii] = 'miles'

    # Convert other observations
    elif Unit in ['metric', 'imperial']:
        for ii, other in enumerate(Obs):
            if other == 'Wm2':
                pass
            elif other == 'index':
                pass
            elif other == 'hrs':
                pass
            elif other == '/min':
                pass
            elif other == 'count':
                pass
            elif other == 's':
                pass
            elif other == '%':
                pass

    # Return converted observations
    return cObs


def Format(Obs, obType, config=[]):

    """ Formats the observation for display on the console

    INPUTS:
        Obs             Observations with units
        obType            Observation type

    OUTPUT:
        cObs            Formatted observation based on specified obType
    """

    # Convert obType to list if required
    if not isinstance(obType, list):
        obType = [obType]

    # Format temperature observations
    cObs = Obs[:]
    for Type in obType:
        if Type == 'Temp':
            for ii, T in enumerate(Obs):
                if isinstance(T, str) and T.strip() in ['c', 'f']:
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    elif round(cObs[ii - 1], 1) == 0.0:
                        cObs[ii - 1] = '{:.1f}'.format(abs(cObs[ii - 1]))
                    else:
                        cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])
                    if T.strip() == 'c':
                        cObs[ii] = u'\N{DEGREE CELSIUS}'
                    elif T.strip() == 'f':
                        cObs[ii] = u'\N{DEGREE FAHRENHEIT}'
                elif isinstance(T, str) and T.strip() in ['c/hr', 'f/hr']:
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    elif round(cObs[ii - 1], 1) == 0.0:
                        cObs[ii - 1] = '{:.1f}'.format(abs(cObs[ii - 1]))
                    else:
                        cObs[ii - 1] = '{:+.1f}'.format(cObs[ii - 1])
                    if T.strip() == 'c/hr':
                        cObs[ii] = u'\N{DEGREE CELSIUS}/hr'
                    elif T.strip() == 'f/hr':
                        cObs[ii] = u'\N{DEGREE FAHRENHEIT}/hr'
        elif Type == 'forecastTemp':
            for ii, T in enumerate(Obs):
                if isinstance(T, str) and T.strip() in ['c', 'f']:
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    elif round(cObs[ii - 1], 1) == 0.0:
                        cObs[ii - 1] = '{:.0f}'.format(abs(cObs[ii - 1]))
                    else:
                        cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                    if T.strip() == 'c':
                        cObs[ii] = u'\N{DEGREE CELSIUS}'
                    elif T.strip() == 'f':
                        cObs[ii] = u'\N{DEGREE FAHRENHEIT}'

        # Format pressure observations
        elif Type == 'Pressure':
            for ii, P in enumerate(Obs):
                if isinstance(P, str) and P.strip() in ['inHg/hr', 'inHg', 'mmHg/hr', 'mmHg', 'hPa/hr', 'mb/hr', 'hPa', 'mb']:
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    else:
                        if P.strip() in ['inHg/hr', 'inHg']:
                            if round(cObs[ii - 1], 1) == 0.0:
                                cObs[ii - 1] = '{:.3f}'.format(abs(cObs[ii - 1]))
                            else:
                                cObs[ii - 1] = '{:.3f}'.format(cObs[ii - 1])
                        elif P.strip() in ['mmHg/hr', 'mmHg']:
                            if round(cObs[ii - 1], 1) == 0.0:
                                cObs[ii - 1] = '{:.2f}'.format(abs(cObs[ii - 1]))
                            else:
                                cObs[ii - 1] = '{:.2f}'.format(cObs[ii - 1])
                        elif P.strip() in ['hPa/hr', 'mb/hr', 'hPa', 'mb']:
                            if round(cObs[ii - 1], 1) == 0.0:
                                cObs[ii - 1] = '{:.1f}'.format(abs(cObs[ii - 1]))
                            else:
                                cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])

        # Format windspeed observations
        elif Type == 'Wind':
            for ii, W in enumerate(Obs):
                if isinstance(W, str) and W.strip() in ['mph', 'kts', 'km/h', 'bft', 'm/s']:
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    else:
                        if round(cObs[ii - 1], 1) < 10:
                            cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])
                        else:
                            cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
        elif Type == 'forecastWind':
            for ii, W in enumerate(Obs):
                if isinstance(W, str) and W.strip() in ['mph', 'kts', 'km/h', 'bft', 'm/s']:
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    else:
                        cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])

        # Format wind direction observations
        elif Type == 'Direction':
            for ii, D in enumerate(Obs):
                if isinstance(D, str) and D.strip() in ['degrees']:
                    cObs[ii] = u'\u00B0'
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    else:
                        cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])

        # Format rain accumulation and rain rate observations
        elif Type == 'Precip':
            for ii, Prcp in enumerate(Obs):
                if isinstance(Prcp, str):
                    if Prcp.strip() == 'mm':
                        if cObs[ii - 1] is None:
                            cObs[ii - 1] = '-'
                        else:
                            if cObs[ii - 1] == 0:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                            elif cObs[ii - 1] < 0.127:
                                cObs[ii - 1] = 'Trace'
                                cObs[ii] = ''
                            elif round(cObs[ii - 1], 1) < 10:
                                cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])
                            else:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                    elif Prcp.strip() == 'cm':
                        if cObs[ii - 1] is None:
                            cObs[ii - 1] = '-'
                        else:
                            if cObs[ii - 1] == 0:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                            elif cObs[ii - 1] < 0.0127:
                                cObs[ii - 1] = 'Trace'
                                cObs[ii] = ''
                            elif round(cObs[ii - 1], 2) < 10:
                                cObs[ii - 1] = '{:.2f}'.format(cObs[ii - 1])
                            elif round(cObs[ii - 1], 1) < 100:
                                cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])
                            else:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                    elif Prcp.strip() == 'in':
                        cObs[ii] = u'\u0022'
                        if cObs[ii - 1] is None:
                            cObs[ii - 1] = '-'
                        else:
                            if cObs[ii - 1] == 0:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                            elif cObs[ii - 1] < 0.005:
                                cObs[ii - 1] = 'Trace'
                                cObs[ii] = ''
                            elif round(cObs[ii - 1], 2) < 10:
                                cObs[ii - 1] = '{:.2f}'.format(cObs[ii - 1])
                            elif round(cObs[ii - 1], 1) < 100:
                                cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])
                            else:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                    elif Prcp.strip() == 'mm/hr':
                        if cObs[ii - 1] is None:
                            cObs[ii - 1] = '-'
                        else:
                            if cObs[ii - 1] == 0:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                            elif cObs[ii - 1] < 0.1:
                                cObs[ii - 1] = '<0.1'
                            elif round(cObs[ii - 1], 1) < 10:
                                cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])
                            else:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                    elif Prcp.strip() in ['in/hr', 'cm/hr']:
                        if cObs[ii - 1] is None:
                            cObs[ii - 1] = '-'
                        else:
                            if cObs[ii - 1] == 0:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                            elif cObs[ii - 1] < 0.01:
                                cObs[ii - 1] = '<0.01'
                            elif round(cObs[ii - 1], 2) < 10:
                                cObs[ii - 1] = '{:.2f}'.format(cObs[ii - 1])
                            elif round(cObs[ii - 1], 1) < 100:
                                cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])
                            else:
                                cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])

        # Format humidity observations
        elif Type == 'Humidity':
            for ii, H in enumerate(Obs):
                if isinstance(H, str) and H.strip() == '%':
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    else:
                        cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])

        # Format solar radiation observations
        elif Type == 'Radiation':
            for ii, Rad in enumerate(Obs):
                if isinstance(Rad, str) and Rad.strip() == 'Wm2':
                    cObs[ii]   = ' W/m' + u'\u00B2'
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    else:
                        cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])

        # Format UV observations
        elif Type == 'UV':
            for ii, UV in enumerate(Obs):
                if isinstance(UV, str) and UV.strip() == 'index':
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                        cObs.extend(['-', '#646464'])
                    else:
                        cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])

        # Format Peak Sun Hours observations
        elif Type == 'peakSun':
            for ii, psh in enumerate(Obs):
                if isinstance(psh, str) and psh.strip() == 'hrs':
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    else:
                        cObs[ii - 1] = '{:.2f}'.format(cObs[ii - 1])

        # Format battery voltage observations
        elif Type == 'Battery':
            for ii, V in enumerate(Obs):
                if isinstance(V, str) and V.strip() == 'v':
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    else:
                        cObs[ii - 1] = '{:.2f}'.format(cObs[ii - 1])

        # Format lightning strike count observations
        elif Type == 'StrikeCount':
            for ii, L in enumerate(Obs):
                if isinstance(L, str) and L.strip() == 'count':
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    elif cObs[ii - 1] < 1000:
                        cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                    else:
                        cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1] / 1000) + ' k'

        # Format lightning strike distance observations
        elif Type == 'StrikeDistance':
            for ii, StrikeDist in enumerate(Obs):
                if isinstance(StrikeDist, str):
                    if StrikeDist.strip() in ['km']:
                        if cObs[ii - 1] is None:
                            cObs[ii - 1] = '-'
                        else:
                            cObs[ii - 1] = '{:.0f}'.format(max(cObs[ii - 1] - 3, 0)) + '-' +  '{:.0f}'.format(cObs[ii - 1] + 3)
                    elif StrikeDist.strip() in ['miles']:
                        if cObs[ii - 1] is None:
                            cObs[ii - 1] = '-'
                        else:
                            cObs[ii - 1] = '{:.0f}'.format(max(cObs[ii - 1] - 3 * 0.62137, 0)) + '-' +  '{:.0f}'.format(cObs[ii - 1] + 3 * 0.62137)

        # Format lightning strike frequency observations
        elif Type == 'StrikeFrequency':
            for ii, StrikeFreq in enumerate(Obs):
                if isinstance(StrikeFreq, str):
                    if StrikeFreq.strip() in ['/min']:
                        if cObs[ii - 1] is None:
                            cObs[ii - 1] = '-'
                            cObs[ii] = ' /min'
                        elif cObs[ii - 1].is_integer():
                            cObs[ii - 1] = '{:.0f}'.format(cObs[ii - 1])
                            cObs[ii] = ' /min'
                        else:
                            cObs[ii - 1] = '{:.1f}'.format(cObs[ii - 1])
                            cObs[ii] = ' /min'

        # Format time difference observations
        elif Type == 'Time':
            for ii, Time in enumerate(Obs):
                if isinstance(Time, str) and Time.strip() in ['s']:
                    if cObs[ii - 1] is None:
                        cObs[ii - 1] = '-'
                    else:
                        Tz = pytz.timezone(config['Station']['Timezone'])
                        if config['Display']['TimeFormat'] == '12 hr':
                            if config['System']['Hardware'] == 'Other':
                                Format = '%#I:%M %p'
                            else:
                                Format = '%-I:%M %p'
                        else:
                            Format = '%H:%M'
                        cObs[ii - 1] = datetime.fromtimestamp(cObs[ii - 1], Tz).strftime(Format)

        # Format time difference observations
        elif Type == 'TimeDelta':
            for ii, Delta in enumerate(Obs):
                if isinstance(Delta, str) and Delta.strip() in ['s']:
                    if cObs[ii - 1] is None:
                        cObs = ['-', '-', '-', '-', cObs[2]]
                    else:
                        days, remainder  = divmod(cObs[ii - 1], 86400)
                        hours, remainder = divmod(remainder, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        if days >= 1:
                            if days == 1:
                                if hours == 1:
                                    cObs = ['{:.0f}'.format(days), 'day', '{:.0f}'.format(hours), 'hour', cObs[2]]
                                else:
                                    cObs = ['{:.0f}'.format(days), 'day', '{:.0f}'.format(hours), 'hours', cObs[2]]
                            elif days <= 99:
                                if hours == 1:
                                    cObs = ['{:.0f}'.format(days), 'days', '{:.0f}'.format(hours), 'hour', cObs[2]]
                                else:
                                    cObs = ['{:.0f}'.format(days), 'days', '{:.0f}'.format(hours), 'hours', cObs[2]]
                            elif days >= 100:
                                cObs = ['{:.0f}'.format(days), 'days', '-', '-', cObs[2]]
                        elif hours >= 1:
                            if hours == 1:
                                if minutes == 1:
                                    cObs = ['{:.0f}'.format(hours), 'hour', '{:.0f}'.format(minutes), 'min', cObs[2]]
                                else:
                                    cObs = ['{:.0f}'.format(hours), 'hour', '{:.0f}'.format(minutes), 'mins', cObs[2]]
                            elif hours > 1:
                                if minutes == 1:
                                    cObs = ['{:.0f}'.format(hours), 'hours', '{:.0f}'.format(minutes), 'min', cObs[2]]
                                else:
                                    cObs = ['{:.0f}'.format(hours), 'hours', '{:.0f}'.format(minutes), 'mins', cObs[2]]
                        else:
                            if minutes == 0:
                                cObs = ['< 1', 'minute', '-', '-', cObs[2]]
                            elif minutes == 1:
                                cObs = ['{:.0f}'.format(minutes), 'minute', '-', '-', cObs[2]]
                            else:
                                cObs = ['{:.0f}'.format(minutes), 'minutes', '-', '-', cObs[2]]

    # Return formatted observations
    return cObs
