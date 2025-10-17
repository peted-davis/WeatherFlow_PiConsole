""" Formats and sets the required units of observations displayed on the
Raspberry Pi Python console for Weather Flow Smart Home Weather Stations.
Copyright (C) 2018-2025 Peter Davis

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
from lib      import derived_variables as derive
from datetime import datetime
import pytz
import copy


def units(observations, unit):

    """ Sets the required observation units

    INPUTS:
        observations                Observations with current units
        unit                        Required output unit

    OUTPUT:
        converted_observations      Observation converted into required unit
    """

    # Covert observations to list of lists if required
    not_list_of_lists = False
    if not isinstance(observations[0], list):
        not_list_of_lists = True
        observations = [observations]
    converted_observation = copy.deepcopy(observations)  

    # Convert temperature observations
    if unit in ['f', 'c']:
        for ii, observation in enumerate(observations):
            for jj, field in enumerate(observation):
                if field == 'c':
                    if unit == 'f':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * (9 / 5) + 32
                        converted_observation[ii][jj] = 'f'
                    else:
                        converted_observation[ii][jj - 1] = observation[jj - 1]
                        converted_observation[ii][jj] = 'c'
                if field in ['dc', 'c/hr']:
                    if unit == 'f':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * (9 / 5)
                        if field == 'dc':
                            converted_observation[ii][jj] = 'f'
                        elif field == 'c/hr':
                            converted_observation[ii][jj] = 'f/hr'
                    else:
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1]
                        if field == 'dc':
                            converted_observation[ii][jj] = 'c'

    # Convert pressure and pressure trend observations
    elif unit in ['inhg', 'mmhg', 'hpa', 'mb']:
        for ii, observation in enumerate(observations):
            for jj, field in enumerate(observation):
                if field in ['mb', 'mb/hr']:
                    if unit == 'inhg':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * 0.0295301
                        if field == 'mb':
                            converted_observation[ii][jj] = ' inHg'
                        else:
                            converted_observation[ii][jj] = ' inHg/hr'
                    elif unit == 'mmhg':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * 0.750063
                        if field == 'mb':
                            converted_observation[ii][jj] = ' mmHg'
                        else:
                            converted_observation[ii][jj] = ' mmHg/hr'
                    elif unit == 'hpa':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1]
                        if field == 'mb':
                            converted_observation[ii][jj] = ' hPa'
                        else:
                            converted_observation[ii][jj] = ' hPa/hr'
                    else:
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1]
                        if field == 'mb':
                            converted_observation[ii][jj] = ' mb'
                        else:
                            converted_observation[ii][jj] = ' mb/hr'

    # Convert windspeed observations
    elif unit in ['mph', 'lfm', 'kts', 'kph', 'bft', 'mps']:
        for ii, observation in enumerate(observations):
            for jj, field in enumerate(observation):
                if field == 'mps':
                    if unit == 'mph' or unit == 'lfm':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * 2.2369362920544
                        converted_observation[ii][jj] = 'mph'
                    elif unit == 'kts':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * 1.9438
                        converted_observation[ii][jj] = 'kts'
                    elif unit == 'kph':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * 3.6
                        converted_observation[ii][jj] = 'km/h'
                    elif unit == 'bft':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = derive.beaufort_scale(observations[ii - 1:ii + 1])[2]
                        converted_observation[ii][jj] = 'bft'
                    else:
                        converted_observation[ii][jj - 1] = observation[jj - 1]
                        converted_observation[ii][jj] = 'm/s'

    # Convert wind direction observations
    elif unit in ['degrees', 'cardinal']:
        for ii, observation in enumerate(observations):
            for jj, field in enumerate(observation):
                if field == 'degrees':
                    if converted_observation[ii][jj - 1] is None:
                        converted_observation[ii][jj - 1] = '-'
                        converted_observation[ii][jj] = ''
                    elif converted_observation[ii][jj - 1] == 'calm':
                        converted_observation[ii][jj - 1] = 'Calm'
                        converted_observation[ii][jj] = ''
                    elif unit == 'cardinal':
                        converted_observation[ii][jj - 1] = derive.cardinal_wind_dir(observation[jj - 1:jj + 1])[2]
                        converted_observation[ii][jj] = ''
                    else:
                        converted_observation[ii][jj - 1] = observation[jj - 1]
                        converted_observation[ii][jj] = 'degrees'

    # Convert rain accumulation and rain rate observations
    elif unit in ['in', 'cm', 'mm']:
        for ii, observation in enumerate(observations):
            for jj, field in enumerate(observation):
                if field in ['mm', 'mm/hr']:
                    if unit == 'in':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * 0.0393701
                        if field == 'mm':
                            converted_observation[ii][jj] = ' in'
                        else:
                            converted_observation[ii][jj] = ' in/hr'
                    elif unit == 'cm':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * 0.1
                        if field == 'mm':
                            converted_observation[ii][jj] = ' cm'
                        else:
                            converted_observation[ii][jj] = ' cm/hr'
                    else:
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1]
                        if field == 'mm':
                            converted_observation[ii][jj] = ' mm'
                        else:
                            converted_observation[ii][jj] = ' mm/hr'

    # Convert distance observations
    elif unit in ['km', 'mi']:
        for ii, observation in enumerate(observations):
            for jj, field in enumerate(observation):
                if field == 'km':
                    if unit == 'mi':
                        if observation[jj - 1] is not None:
                            converted_observation[ii][jj - 1] = observation[jj - 1] * 0.62137
                        converted_observation[ii][jj] = 'miles'

    # Convert other observations
    elif unit in ['metric', 'imperial']:
        for jj, field in enumerate(observations):
            if field == 'Wm2':
                pass
            elif field == 'index':
                pass
            elif field == 'hrs':
                pass
            elif field == '/min':
                pass
            elif field == 'count':
                pass
            elif field == 's':
                pass
            elif field == '%':
                pass

    # Covert converted observations back to simple list if required
    if not_list_of_lists:
        converted_observation = converted_observation[0]

    # Return converted observations
    return converted_observation


def format(observations, observation_type, config=[]):

    """ Formats the observation for display on the console

    INPUTS:
        observation             Observations with units
        observation_type        Observation type

    OUTPUT:
        formatted_observation   Formatted observation based on specified obType
    """

    # Convert observation_type to list if required
    if not isinstance(observation_type, list):
        observation_type = [observation_type]

    # Covert observations to list of lists if required
    not_list_of_lists = False
    
    if not isinstance(observations[0], list):
        not_list_of_lists = True
        observations = [observations]
    formatted_observation = copy.deepcopy(observations)  

    # Format temperature observations
    for type in observation_type:
        if type == 'Temp':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() in ['c', 'f']:
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        elif round(formatted_observation[jj][ii - 1], 1) == 0.0:
                            formatted_observation[jj][ii - 1] = '{:.1f}'.format(abs(formatted_observation[jj][ii - 1]))
                        else:
                            formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])
                        if field.strip() == 'c':
                            formatted_observation[jj][ii] = u'\N{DEGREE CELSIUS}'
                        elif field.strip() == 'f':
                            formatted_observation[jj][ii] = u'\N{DEGREE FAHRENHEIT}'
                    elif isinstance(field, str) and field.strip() in ['c/hr', 'f/hr']:
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        elif round(formatted_observation[jj][ii - 1], 1) == 0.0:
                            formatted_observation[jj][ii - 1] = '{:.1f}'.format(abs(formatted_observation[jj][ii - 1]))
                        else:
                            formatted_observation[jj][ii - 1] = '{:+.1f}'.format(formatted_observation[jj][ii - 1])
                        if field.strip() == 'c/hr':
                            formatted_observation[jj][ii] = u'\N{DEGREE CELSIUS}/hr'
                        elif field.strip() == 'f/hr':
                            formatted_observation[jj][ii] = u'\N{DEGREE FAHRENHEIT}/hr'
        elif type == 'forecast_temp':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() in ['c', 'f']:
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        elif round(formatted_observation[jj][ii - 1], 1) == 0.0:
                            formatted_observation[jj][ii - 1] = '{:.0f}'.format(abs(formatted_observation[jj][ii - 1]))
                        else:
                            formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                        if field.strip() == 'c':
                            formatted_observation[jj][ii] = u'\N{DEGREE CELSIUS}'
                        elif field.strip() == 'f':
                            formatted_observation[jj][ii] = u'\N{DEGREE FAHRENHEIT}'

        # Format pressure observations
        elif type == 'Pressure':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() in ['inHg/hr', 'inHg', 'mmHg/hr', 'mmHg', 'hPa/hr', 'mb/hr', 'hPa', 'mb']:
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        else:
                            if field.strip() in ['inHg/hr', 'inHg']:
                                if round(formatted_observation[jj][ii - 1], 3) == 0.0:
                                    formatted_observation[jj][ii - 1] = '{:.3f}'.format(abs(formatted_observation[jj][ii - 1]))
                                else:
                                    formatted_observation[jj][ii - 1] = '{:.3f}'.format(formatted_observation[jj][ii - 1])
                            elif field.strip() in ['mmHg/hr', 'mmHg']:
                                if round(formatted_observation[jj][ii - 1], 2) == 0.0:
                                    formatted_observation[jj][ii - 1] = '{:.2f}'.format(abs(formatted_observation[jj][ii - 1]))
                                else:
                                    formatted_observation[jj][ii - 1] = '{:.2f}'.format(formatted_observation[jj][ii - 1])
                            elif field.strip() in ['hPa/hr', 'mb/hr', 'hPa', 'mb']:
                                if round(formatted_observation[jj][ii - 1], 1) == 0.0:
                                    formatted_observation[jj][ii - 1] = '{:.1f}'.format(abs(formatted_observation[jj][ii - 1]))
                                else:
                                    formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])

        # Format windspeed observations
        elif type == 'Wind':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() in ['mph', 'kts', 'km/h', 'bft', 'm/s']:
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        else:
                            if round(formatted_observation[jj][ii - 1], 1) < 10:
                                formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])
                            else:
                                formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
        elif type == 'forecast_wind':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() in ['mph', 'kts', 'km/h', 'bft', 'm/s']:
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        else:
                            formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])

        # Format wind direction observations
        elif type == 'Direction':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() in ['degrees']:
                        formatted_observation[jj][ii] = u'\u00B0'
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        else:
                            formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])

        # Format rain accumulation and rain rate observations
        elif type == 'Precip':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str):
                        if field.strip() == 'mm':
                            if formatted_observation[jj][ii - 1] is None:
                                formatted_observation[jj][ii - 1] = '-'
                            else:
                                if formatted_observation[jj][ii - 1] == 0:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                                elif formatted_observation[jj][ii - 1] < 0.127:
                                    formatted_observation[jj][ii - 1] = 'Trace'
                                    formatted_observation[jj][ii] = ''
                                elif round(formatted_observation[jj][ii - 1], 1) < 10:
                                    formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])
                                else:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                        elif field.strip() == 'cm':
                            if formatted_observation[jj][ii - 1] is None:
                                formatted_observation[jj][ii - 1] = '-'
                            else:
                                if formatted_observation[jj][ii - 1] == 0:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                                elif formatted_observation[jj][ii - 1] < 0.0127:
                                    formatted_observation[jj][ii - 1] = 'Trace'
                                    formatted_observation[jj][ii] = ''
                                elif round(formatted_observation[jj][ii - 1], 2) < 10:
                                    formatted_observation[jj][ii - 1] = '{:.2f}'.format(formatted_observation[jj][ii - 1])
                                elif round(formatted_observation[jj][ii - 1], 1) < 100:
                                    formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])
                                else:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                        elif field.strip() == 'in':
                            formatted_observation[jj][ii] = u'\u0022'
                            if formatted_observation[jj][ii - 1] is None:
                                formatted_observation[jj][ii - 1] = '-'
                            else:
                                if formatted_observation[jj][ii - 1] == 0:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                                elif formatted_observation[jj][ii - 1] < 0.005:
                                    formatted_observation[jj][ii - 1] = 'Trace'
                                    formatted_observation[jj][ii] = ''
                                elif round(formatted_observation[jj][ii - 1], 2) < 10:
                                    formatted_observation[jj][ii - 1] = '{:.2f}'.format(formatted_observation[jj][ii - 1])
                                elif round(formatted_observation[jj][ii - 1], 1) < 100:
                                    formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])
                                else:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                        elif field.strip() == 'mm/hr':
                            if formatted_observation[jj][ii - 1] is None:
                                formatted_observation[jj][ii - 1] = '-'
                            else:
                                if formatted_observation[jj][ii - 1] == 0:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                                elif formatted_observation[jj][ii - 1] < 0.1:
                                    formatted_observation[jj][ii - 1] = '<0.1'
                                elif round(formatted_observation[jj][ii - 1], 1) < 10:
                                    formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])
                                else:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                        elif field.strip() in ['in/hr', 'cm/hr']:
                            if formatted_observation[jj][ii - 1] is None:
                                formatted_observation[jj][ii - 1] = '-'
                            else:
                                if formatted_observation[jj][ii - 1] == 0:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                                elif formatted_observation[jj][ii - 1] < 0.01:
                                    formatted_observation[jj][ii - 1] = '<0.01'
                                elif round(formatted_observation[jj][ii - 1], 2) < 10:
                                    formatted_observation[jj][ii - 1] = '{:.2f}'.format(formatted_observation[jj][ii - 1])
                                elif round(formatted_observation[jj][ii - 1], 1) < 100:
                                    formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])
                                else:
                                    formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])

        # Format humidity observations
        elif type == 'Humidity':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() == '%':
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        else:
                            formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])

        # Format solar radiation observations
        elif type == 'Radiation':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() == 'Wm2':
                        formatted_observation[jj][ii]   = ' W/m' + u'\u00B2'
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        else:
                            formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])

        # Format UV observations
        elif type == 'UV':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() == 'index':
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                            formatted_observation[jj].extend(['-', '#646464'])
                        else:
                            formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])

        # Format Peak Sun Hours observations
        elif type == 'peakSun':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() == 'hrs':
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        else:
                            formatted_observation[jj][ii - 1] = '{:.2f}'.format(formatted_observation[jj][ii - 1])

        # Format battery voltage observations
        elif type == 'Battery':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() == 'v':
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        else:
                            formatted_observation[jj][ii - 1] = '{:.2f}'.format(formatted_observation[jj][ii - 1])

        # Format lightning strike count observations
        elif type == 'StrikeCount':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() == 'count':
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        elif formatted_observation[jj][ii - 1] < 1000:
                            formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                        else:
                            formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1] / 1000) + ' k'

        # Format lightning strike distance observations
        elif type == 'StrikeDistance':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str):
                        if field.strip() in ['km']:
                            if formatted_observation[jj][ii - 1] is None:
                                formatted_observation[jj][ii - 1] = '-'
                            else:
                                formatted_observation[jj][ii - 1] = '{:.0f}'.format(max(formatted_observation[jj][ii - 1] - 3, 0)) + '-' +  '{:.0f}'.format(formatted_observation[jj][ii - 1] + 3)
                        elif field.strip() in ['miles']:
                            if formatted_observation[jj][ii - 1] is None:
                                formatted_observation[jj][ii - 1] = '-'
                            else:
                                formatted_observation[jj][ii - 1] = '{:.0f}'.format(max(formatted_observation[jj][ii - 1] - 3 * 0.62137, 0)) + '-' + '{:.0f}'.format(formatted_observation[jj][ii - 1] + 3 * 0.62137)

        # Format lightning strike frequency observations
        elif type == 'StrikeFrequency':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str):
                        if field.strip() in ['/min']:
                            if formatted_observation[jj][ii - 1] is None:
                                formatted_observation[jj][ii - 1] = '-'
                                formatted_observation[jj][ii] = ' /min'
                            elif formatted_observation[jj][ii - 1].is_integer():
                                formatted_observation[jj][ii - 1] = '{:.0f}'.format(formatted_observation[jj][ii - 1])
                                formatted_observation[jj][ii] = ' /min'
                            else:
                                formatted_observation[jj][ii - 1] = '{:.1f}'.format(formatted_observation[jj][ii - 1])
                                formatted_observation[jj][ii] = ' /min'

        # Format time difference observations
        elif type == 'Time':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() in ['s']:
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj][ii - 1] = '-'
                        else:
                            Tz = pytz.timezone(config['Station']['Timezone'])
                            if config['Display']['TimeFormat'] == '12 hr':
                                if config['System']['Hardware'] == 'Other':
                                    format = '%#I:%M %p'
                                else:
                                    format = '%-I:%M %p'
                            else:
                                format = '%H:%M'
                            formatted_observation[jj][ii - 1] = datetime.fromtimestamp(formatted_observation[jj][ii - 1], Tz).strftime(format)

        # Format time difference observations
        elif type == 'TimeDelta':
            for jj, observation in enumerate(observations):
                for ii, field in enumerate(observation):
                    if isinstance(field, str) and field.strip() in ['s']:
                        if formatted_observation[jj][ii - 1] is None:
                            formatted_observation[jj] = ['-', '-', '-', '-', formatted_observation[2]]
                        else:
                            days, remainder  = divmod(formatted_observation[jj][ii - 1], 86400)
                            hours, remainder = divmod(remainder, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            if days >= 1:
                                if days == 1:
                                    if hours == 1:
                                        formatted_observation[jj] = ['{:.0f}'.format(days), 'day', '{:.0f}'.format(hours), 'hour', formatted_observation[jj][2]]
                                    else:
                                        formatted_observation[jj] = ['{:.0f}'.format(days), 'day', '{:.0f}'.format(hours), 'hours', formatted_observation[jj][2]]
                                elif days <= 99:
                                    if hours == 1:
                                        formatted_observation[jj] = ['{:.0f}'.format(days), 'days', '{:.0f}'.format(hours), 'hour', formatted_observation[jj][2]]
                                    else:
                                        formatted_observation[jj] = ['{:.0f}'.format(days), 'days', '{:.0f}'.format(hours), 'hours', formatted_observation[jj][2]]
                                elif days >= 100:
                                    formatted_observation[jj] = ['{:.0f}'.format(days), 'days', '-', '-', formatted_observation[jj][2]]
                            elif hours >= 1:
                                if hours == 1:
                                    if minutes == 1:
                                        formatted_observation[jj] = ['{:.0f}'.format(hours), 'hour', '{:.0f}'.format(minutes), 'min', formatted_observation[jj][2]]
                                    else:
                                        formatted_observation[jj] = ['{:.0f}'.format(hours), 'hour', '{:.0f}'.format(minutes), 'mins', formatted_observation[jj][2]]
                                elif hours > 1:
                                    if minutes == 1:
                                        formatted_observation[jj] = ['{:.0f}'.format(hours), 'hours', '{:.0f}'.format(minutes), 'min', formatted_observation[jj][2]]
                                    else:
                                        formatted_observation[jj] = ['{:.0f}'.format(hours), 'hours', '{:.0f}'.format(minutes), 'mins', formatted_observation[jj][2]]
                            else:
                                if minutes == 0:
                                    formatted_observation[jj] = ['< 1', 'minute', '-', '-', formatted_observation[jj][2]]
                                elif minutes == 1:
                                    formatted_observation[jj] = ['{:.0f}'.format(minutes), 'minute', '-', '-', formatted_observation[jj][2]]
                                else:
                                    formatted_observation[jj] = ['{:.0f}'.format(minutes), 'minutes', '-', '-', formatted_observation[jj][2]]

    # Covert formatted observations back to simple list if required
    if not_list_of_lists:
        formatted_observation = formatted_observation[0]

    # Return formatted observations
    return formatted_observation
