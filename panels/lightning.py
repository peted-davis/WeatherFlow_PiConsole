""" Defines the Lightning panel required by the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2023 Peter Davis

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

# Load required Kivy modules
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties         import StringProperty, NumericProperty
from kivy.animation          import Animation
from kivy.metrics            import dp

# Load required panel modules
from panels.template         import panelTemplate


# ==============================================================================
# LightningPanel AND LightningButton CLASS
# ==============================================================================
class LightningPanel(panelTemplate):

    # Define LightningPanel class properties
    lightningBoltPosX = NumericProperty(0)
    lightningBoltIcon = StringProperty('lightningBolt')

    # Initialise LightningPanel
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setLightningBoltIcon()

    # Set lightning bolt icon
    def setLightningBoltIcon(self):
        if self.app.CurrentConditions.Obs['StrikeDeltaT'][0] != '-':
            if self.app.CurrentConditions.Obs['StrikeDeltaT'][4] < 360:
                self.lightningBoltIcon = 'lightningBoltStrike'
            else:
                self.lightningBoltIcon = 'lightningBolt'

    # Animate lightning bolt icon
    def animateLightningBoltIcon(self):
        Anim = Animation(lightningBoltPosX=dp(10), t='out_quad', d=0.02) + Animation(lightningBoltPosX=dp(0), t='out_elastic', d=0.5)
        Anim.start(self)


class LightningButton(RelativeLayout):
    pass
