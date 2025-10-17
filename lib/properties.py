""" Defines the Kivy property values required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright C) 2018-2025 Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""


def Obs():

    """ Define the Obs property values """

    return {'outTemp': '--',       'FeelsLike': '----',     'DewPoint': '--',
            'outTempDiff': '---',  'outTempTrend': '---',   'outTempMax': '---',
            'outTempMin': '---',   'Humidity': '--',        'SLP': '---',
            'SLPTrend': '----',    'SLPMax': '---',         'SLPMin': '---',
            'StrikeDist': '--',    'StrikeDeltaT': '-----', 'StrikeFreq': '----',
            'Strikes3hr': '-',     'StrikesToday': '-',     'StrikesMonth': '-',
            'StrikesYear': '-',    'Radiation': '----',     'UVIndex': '----',
            'peakSun': '------',   'RainRate': '---',       'TodayRain': '--',
            'YesterdayRain': '--', 'MonthRain': '--',       'YearRain': '--',
            'WindSpd': '-----',    'WindGust': '--',        'AvgWind': '--',
            'MaxGust': '--',       'WindDir': '---',        'inTemp': '--',
            'inTempMax': '---',    'inTempMin': '---',      'rapidSpd': '--',
            'rapidDir': '----',
            }


def Astro():

    """ Define the Astro property values """

    return {'Sunrise': ['-', '-', 0], 'Sunset': ['-', '-', 0], 'Dawn': ['-', '-', 0],
            'Dusk': ['-', '-', 0],    'sunEvent': '----',      'sunIcon': ['-', 0, 0],
            'Moonrise': ['-', '-'],   'Moonset': ['-', '-'],   'NewMoon': '--',
            'FullMoon': '--',         'Phase': ['-', '-', '-', 0]
            }


def Met():

    """ Define the Met property values """

    return {'current_hour': 
                {'valid_time': '--',        'temperature': '--',        'wind_speed': '--',      
                 'wind_gust': '--',         'wind_dir': '--',           'precip_percnt': '--', 
                 'precip_amount': '--',     'precip_type': '--',        'conditions': '-',      
                 'forecast_icon': '-',      'status': '--'},
            'current_day':
                {'high_temperature': '--',  'low_temperature': '--',    'precip_percnt': '--', },
            '12_hour':
                {'valid_time':    '-'*12, 'temperature':   [['-', '-', '#FFFFFF']]*12, 'feels_like':    [['-', '-', '#FFFFFF']]*12, 
                 'forecast_icon': '-'*12, 'wind_speed':    [['-', '-']]*12,              'wind_gust':     [['-', '-']]*12, 
                 'wind_dir':      '-'*12, 'precip_percnt': [['-', '-']]*12,              'precip_amount': [['-', '-']]*12,
                 'precip_type':   '-'*12,},
            '5_day':
                {'valid_time':    '-'*12, 'temperature':   [['-', '-', '#FFFFFF']]*12, 'feels_like':    [['-', '-', '#FFFFFF']]*12, 
                 'forecast_icon': '-'*12, 'wind_speed':    [['-', '-']]*12,              'wind_gust':     [['-', '-']]*12, 
                 'wind_dir':   '-'*12,    'precip_percnt': [['-', '-']]*12,              'precip_amount': [['-', '-']]*12}
            }

def metar_taf():

    """ Define the taf_metar property values """

    return {'taf_location_string': '-',     'taf_timing_string': '-',       'taf_forecast_string': '-',     
            'metar_location_string': '-',   'metar_timing_string': '-',     'metar_observation_string': '-',     }

def Sager():

    """ Define the Sager property values """

    return {'Forecast': '-', 'Issued': '-'}


def Status():

    """ Define the Status property values """

    return {'tempest_sample_time': '-', 'tempest_last_sample': ' ',  'tempest_voltage': '-',
            'tempest_status': '-',      'tempest_ob_count': '-',
            'sky_sample_time': '-',     'sky_last_sample': ' ',      'sky_voltage': '-',
            'sky_status': '-',          'sky_ob_count': '-',
            'out_air_sample_time': '-', 'out_air_last_sample': ' ',  'out_air_voltage': '-',
            'out_air_status': '-',      'out_air_ob_count': '-',
            'in_air_sample_time': '-',  'in_air_last_sample': ' ',   'in_air_voltage': '-',
            'in_air_status': '-',       'in_air_ob_count': '-',
            'station_status': '-',
            'hub_firmware': '-'
            }


def System():

    """ Define the System property values """

    return {'Time': '-', 'Date': '-'}
