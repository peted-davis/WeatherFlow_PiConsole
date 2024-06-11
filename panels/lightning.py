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
from kivy.clock              import Clock

# Load required panel modules
from panels.template         import panelTemplate

# Load required Python modules
from functools               import partial

# ==============================================================================
# LightningPanel AND LightningButton CLASS
# ==============================================================================
class LightningPanel(panelTemplate):

    # Define LightningPanel class properties
    lightningBoltPosX = NumericProperty(0)
    lightningBoltIcon = StringProperty('lightningBolt')

    # Initialise LightningPanel
    def __init__(self, mode=None, **kwargs):
        super().__init__(mode, **kwargs)
        self.setLightningBoltIcon()
        if mode == 'auto':
            self.auto_close_lightning_panel()

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

    # Automatically close lightning panel after specified period if required
    def auto_close_lightning_panel(self):
        panel_timeout = int(self.app.config['Display']['lightning_timeout']) * 60
        try:
            self.app.Sched.lightning_timeout.cancel()
        except AttributeError:
            pass
        if panel_timeout > 0:
            for ii, button in enumerate(self.app.CurrentConditions.button_list):
                if button[3] == "Lightning" and button[4] == 'primary':
                    self.app.Sched.lightning_timeout = Clock.schedule_once(
                        partial(self.app.CurrentConditions.switchPanel, 
                                None, 
                                button), 
                                panel_timeout
                                )

class LightningButton(RelativeLayout):
    pass
