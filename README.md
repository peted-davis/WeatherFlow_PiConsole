# WeatherFlow PiConsole
Python console for the WeatherFlow Tempest and Smart Home Weather
stations. The console uses the WeatherFlow REST API and websocket to stream data
from your Weather Flow Tempest or Smart Home Weather station in real time via
the internet. As soon as data from your station reaches the WeatherFlow servers, 
it is pushed immediately to the console, including the 3-second rapid wind 
updates.

For a list of supported features and screenshots of the console in action, please
checkout its page on the WeatherFlow community forums: https://community.weatherflow.com/t/weatherflow-piconsole/1933

The WeatherFlow PiConsole can be run on a Raspberry Pi 3 or 4 running Raspberry 
Pi OS , or on a PC running Ubuntu 18.04 LTS or Raspberry Pi OS. It is  currently 
*not* compatible with Ubuntu 20.04 without downgrading Python to version 3.7 

https://weatherflow.com/tempest-weather-system/<br/>
https://community.weatherflow.com/

## Contents

**[Installation Instructions](#installation-instructions)**<br>
**[Update Instructions](#update-instructions)**<br>
**[Auto-Start Instructions](#auto-start-instructions)**<br>
**[Advanced Installation: Windows](#advanced-installation-windows)**<br>
**[Credits](#credits)**<br>

## Installation Instructions

The installation of the WeatherFlow PiConsole is fully automated, and can
be started from the terminal with a single command. The automated installation
should take ~1 hour.

The automated installer assumes you have already sucesfully setup your Raspberry
Pi and have installed Raspberry Pi OS with Desktop, or you ar running on a PC
with Ubuntu 18.04 or Raspberry Pi OS installed. For a Raspberry Pi you should 
have also attached the touch screen, and have either a keyboard and mouse attached
directly to the Pi, or have accessesd the Pi remotely through SSH/VNC. If you
are starting from scratch with a Raspberry Pi, the documentation should help 
get you started:

* https://www.raspberrypi.org/documentation/

### Install WeatherFlow PiConsole

The WeatherFlow PiConsole can be installed quickly and conveniently with the
following command:
```
curl -sSL https://peted-davis.github.io/wfpiconsole | bash
```
Piping a command directly to ```bash``` is controversial, as it prevents the
user from reading code that is about to run on their system. If you are worried
about the contents of the installer, please examine the [first](https://raw.githubusercontent.com/peted-davis/peted-davis.github.io/master/wfpiconsole)
and [second](https://raw.githubusercontent.com/peted-davis/WeatherFlow_PiConsole/master/wfpiconsole.sh)
install files in the Git repository before running the install command. The
PiConsole requires a number of Python dependencies. Please check the second 
install file if you think there may be any conflicts with existing software on 
your on system.

### Raspberry Pi 4

For those of you running a Raspberry Pi 4 an extra step is needed to get the
console running perfectly. The “Task Bar” panel on the Raspberry Pi desktop
needs to be hidden or else it will displace the console on the screen. There are
two options to achieve this. First right click on the “Task Bar” panel on the
Raspberry Pi desktop and select Panel settings. Select the Advanced tab. Then
either:

1. Un-tick ```"Reserve space, and not covered by maximised windows"```, or
2. Tick ```"Minimise panel when not in use"``` and set ```"Size when minimised"``` to 0 pixels.

Please note that you also cannot use SSH to start the console on a Raspberry Pi
4. Instead for remote access it is recommended to setup VNC (https://www.raspberrypi.org/documentation/remote-access/vnc/)

### Configure and Run WeatherFlow PiConsole

When the console is run for the first time, you'll be asked to enter a
WeatherFlow Personal Access Token and a CheckWX Aviation Weather API key. The
Personal Access Token is required for the PiConsole to access the data from your
station, and the CheckWX API key is required to download the closest METAR 
information to your station location. 

A Personal Access Token can be generated, viewed, and deleted here: https://tempestwx.com/settings/tokens,
and a CheckWX API key can be obtained by registering for a free account here: 
https://www.checkwxapi.com/auth/signup

Once you have a Personal Access Token and registered with CheckWX, go ahead 
and run the console for the first time using:
```
wfpiconsole start
```
You'll be asked to enter the API keys you have just generated above, as well
as information about your station. This includes your station ID and device IDs
for your AIR, SKY, or TEMPEST modules. To find this information either open the
WeatherFlow app or view your station page in a web browser. Click on the gear 
(settings) icon -> Stations -> [Station name] -> Status.

If all goes smoothly the console should automatically add the extra information
it needs to your configuration file and then start running. You should not need
to enter this configuration information again.

Congratulations, you have installed the PiConsole for the Weather Flow Tempest 
and Smart Home Weather Stations.

### Screen size

By default the PiConsole will run in full screen mode. If you are running on a 
Raspberry Pi 4 or a PC with Raspberry Pi OS or Ubuntu 18.04 LTS, fullscreen mode 
can be disabled in Menu -> Settings -> Display. In this case the console will 
use the dimensions specified in the configuration file (```wfpiconsole.ini```), 
which can be changed manually. Please note that extreme changes to the aspect 
ratio will result in text fields running into one another. Under Settings -> 
Display there are also settings to show/hide the cursor and show/hide the window
border.  

## Update Instructions

The WeatherFlow PiConsole can be updated quickly and easily with the following
command:
```
wfpiconsole update
```
The update process will retain your existing user settings, but may prompt for
input from time to time in order to add new functionality. Once the update has
finished, restart the console using:
```
wfpiconsole start
```

## Auto-Start Instructions

The WeatherFlow PiConsole can be configured to run automatically when the
Raspberry Pi powers up. To enable the console to start automatically, run
```
wfpiconsole autostart-enable
```
To stop the WeatherFlow PiConsole from starting automatically, run
```
wfpiconsole autostart-disable
```
If you are going to use the auto-start method, it is highly recommended that you
can SSH into your Raspberry Pi, as the console can only be stopped using the
stop command or a hard shutdown:
```
wfpiconsole stop
```

## Advanced Installation: Windows

Although not officially supported, use the following step-by-step instructions
to install and run the WeatherFlow PiConsole on Windows.

1. Download and install the Python 3.7 version of Miniconda for Windows (a
lightweight Python interpreter): https://conda.io/miniconda.html

2. Once Miniconda is installed open the ‘Anaconda Prompt’ program.

3. In the Anaconda prompt, run:
```
python -m pip install --upgrade pip
```

4. Once that process has finished, run:
```
python -m pip install autobahn[twisted] pytz pyasn1-modules service_identity geopy ephem Cython numpy packaging
```

5. Once that has finished, follow steps 2 and 3 under “Installing the kivy
stable release” to install Kivy: https://kivy.org/doc/stable/installation/installation-windows.html
This is the GUI library that drives the console.

6. Once Kivy is installed, run the following commands in order in the Anaconda
Prompt. This will install the WeatherFlow PiConsole.
```
cd && mkdir wfpiconsole && cd wfpiconsole
curl -sL https://api.github.com/repos/peted-davis/WeatherFlow_PiConsole/tarball -o PiConsole.tar.gz
tar -xvf PiConsole.tar.gz --strip 1
del /f PiConsole.tar.gz
```

7. You’re almost there now! You can start the console using ```python main.py```.
As this is the first time you have run the console, you’ll be asked for some API
keys. Details of what you need can be found under "Configure and Run WeatherFlow
PiConsole" in the **[Installation Instructions](#installation-instructions)**.

## Credits

Many of the graphical elements in the console are based on the Weather34 Home
Weather Station Template (https://www.weather34.com/homeweatherstation/)
copyright 2015-2021 Brian Underdown. The Weather34 Home Weather Station Template
is licensed under a Creative Commons Attribution-NonCommercial-NoDerivatives 4.0
International License.
