""" Defines the Kivy property values required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2020 Peter Davis

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


def Obs():

    """ Define the Obs Kivy properties values

    OUTPUTS
        Obs                Values for Obs Kivy property
    """

    return [('rapidSpd', '--'),       ('rapidDir', '----'),      ('rapidShift', '-'),
            ('WindSpd', '-----'),     ('WindGust', '--'),        ('WindDir', '---'),
            ('AvgWind', '--'),        ('MaxGust', '--'),         ('RainRate', '---'),
            ('TodayRain', '--'),      ('YesterdayRain', '--'),   ('MonthRain', '--'),
            ('YearRain', '--'),       ('Radiation', '----'),     ('UVIndex', '----'),
            ('peakSun', '------'),    ('outTemp', '--'),         ('outTempMin', '---'),
            ('outTempMax', '---'),    ('outTempTrend', '---'),   ('outTempDiff', '---'),
            ('inTemp', '--'),         ('inTempMin', '---'),      ('inTempMax', '---'),
            ('Humidity', '--'),       ('DewPoint', '--'),        ('SLP', '---'),
            ('SLPMax', '---'),        ('SLPMin', '---'),         ('SLPTrend', '----'),
            ('FeelsLike', '----'),    ('StrikeDeltaT', '-----'), ('StrikeDist', '--'),
            ('StrikeFreq', '----'),   ('Strikes3hr', '-'),       ('StrikesToday', '-'),
            ('StrikesMonth', '-'),    ('StrikesYear', '-')
            ]


def Astro():

    """ Define the Astro Kivy properties values

    OUTPUTS
        Astro                Values for Obs Kivy property
    """

    return [('Sunrise', ['-', '-', 0]), ('Sunset', ['-', '-', 0]), ('Dawn', ['-', '-', 0]),
            ('Dusk', ['-', '-', 0]),    ('sunEvent', '----'),      ('sunIcon', ['-', 0, 0]),
            ('Moonrise', ['-', '-']),   ('Moonset', ['-', '-']),   ('NewMoon', '--'),
            ('FullMoon', '--'),         ('Phase', '---'),          ('Reformat', '-'),
            ]


def Met():

    """ Define the Met Kivy properties values

    OUTPUTS
        Met                Values for Obs Kivy property
    """

    return [('Valid', '--'),        ('Temp', '--'),         ('highTemp', '--'),
            ('lowTemp', '--'),      ('WindSpd', '--'),      ('WindGust', '--'),
            ('WindDir', '--'),      ('PrecipPercnt', '--'), ('PrecipDay', '--'),
            ('PrecipAmount', '--'), ('PrecipType', '--'),   ('Conditions', '-'),
            ('Icon', '-'),          ('Status', '--')
            ]


def Sager():

    """ Define the Sager Kivy properties values

    OUTPUTS
        Met                Values for Obs Kivy property
    """

    return [('Forecast','--'),       ('Issued','--')
            ]


def Status():

    """ Define the Status Kivy properties values

    OUTPUTS
        Met                Values for Obs Kivy property
    """

    return [('tempestSampleTime', '-'), ('tempestLastSample', ' '), ('tempestVoltage', '-'),
            ('tempestStatus', '-'),     ('tempestObCount', '-'),    ('skySampleTime', '-'),
            ('skyLastSample', ' '),     ('skyVoltage', '-'),        ('skyStatus', '-'),
            ('skyObCount', '-'),        ('outAirSampleTime', '-'),  ('outAirLastSample', ' '),
            ('outAirVoltage', '-'),     ('outAirStatus', '-'),      ('outAirObCount', '-'),
            ('inAirSampleTime', '-'),   ('inAirLastSample', ' '),   ('inAirVoltage', '-'),
            ('inAirStatus', '-'),       ('inAirObCount', '-'),      ('stationStatus', '-'),
            ('hubFirmware', '-')
            ]
