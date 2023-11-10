# WeatherFlow PiConsole

<a href="https://www.buymeacoffee.com/peted.davis" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

**PLEASE NOTE: no support is available until late January 2024 as the developer
is working in Antarctica with no access to the internet**

The WeatherFlow PiConsole is a Python console that displays the data collected
by a WeatherFlow Tempest or Smart Home Weather Station. The console uses either
the WeatherFlow REST API and websocket service or the local UDP connection to
stream data from your station in real time, including the 3-second rapid wind
updates. In UDP only mode, the console requires no connection to the internet
once installation is complete.

The console is currently compatible with Raspberry Pi 3 and 4 running 32 bit
Raspberry Pi OS with the Official 7 inch touchscreen or equivalent. It can also
be run on a PC with Ubuntu 20.04 LTS or later, or Raspberry Pi OS. For full
system compatibility details, see below. Support for Raspberry Pi 5 is coming
soon.

For a list of supported features and screenshots of the console in action,
please checkout the WeatherFlow community forums: https://community.weatherflow.com/t/weatherflow-piconsole/20083

https://weatherflow.com/tempest-weather-system/<br/>
https://community.weatherflow.com/

## Contents

**[Compatibility](#compatibility)**<br>
**[Installation Instructions](#installation-instructions)**<br>
**[Update Instructions](#update-instructions)**<br>
**[Auto-Start Instructions](#auto-start-instructions)**<br>
**[Advanced Installation: Windows](#advanced-installation-windows)**<br>
**[Credits](#credits)**<br>

## Compatibility

### Raspberry Pi

The console is fully supported for Raspberry Pi 3 Model B/B+ and Raspberry Pi 4
running the 32 bit version of Raspberry Pi OS. It can be run on earlier models,
a Raspberry Pi 5, or the 64 bit version of Raspberry Pi OS, but no direct
support is provided for these environments. It is not compatible with Raspberry
Pi Zero or Zero W. Raspberry Pi 5 will become fully supported in the future.
While the console is compatiable with Raspberry Pi 3, the graphics hardware on
this model is ageing and performance of the console can be sluggish. It is
recommended to use a Pi 4 or above

For all models of Raspberry Pi, the console is compatible with Raspberry Pi OS
(Bookworm) or the legacy Raspberry Pi OS (Bullseye). The console is no longer
comptaible with Raspberry Pi OS (Buster).

The console is compatible with the Raspberry Pi Official 7 inch Touchscreen or
other HDMI equivalents. Note, screens that attach solely to the GPIO pins (SPI)
are not compatible and the console will not start.

### PC / Laptop

The console is fully supported on laptops and PCs running Ubuntu 20.04 LTS or
later, or the desktop version of Raspberry Pi OS. It will run on other
debian-based operating systems with Python version 3.9 or above, but no direct
support is provided for these environments.

## Installation Instructions

The installation of the WeatherFlow PiConsole is fully automated, and can
be started from the terminal with a single command. The automated installation
should take no longer than 10 minutes.

The automated installer assumes you have already sucesfully setup your Raspberry
Pi and have installed Raspberry Pi OS with Desktop, or you ar running on a PC
with Ubuntu 20.04 or later or Raspberry Pi OS installed. For a Raspberry Pi you
should have also attached the touch screen, and have either a keyboard and mouse
attached directly to the Pi, or have accessesd the Pi remotely through SSH/VNC.
If you are starting from scratch with a Raspberry Pi, the documentation should
help get you started:

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
install files in the Git repository before running the install command.

### Configure and Run WeatherFlow PiConsole

When the console is run for the first time, you'll be asked whether you want to
install a blank configuration file for demonstration purposes or advanced setup.
You can use this option if you wish to try out the console before your
WeatherFlow hardware has arrived, or if you are a power user and wish to
configure the console manually rather than using the configuration wizard. For
most users, the advanced installation option is no appropriate and the default
option of 'no' should be selected at this prompt.

You will be prompted to specify your preferred connection type: Websocket and
REST API (default), UDP and REST API, or UDP only. For UDP only you will be
prompted to manually enter futher information about your station (location,
name, elevation etc.). For Websocket and REST API or UDP and REST API you will
be prompted to enter a WeatherFlow Personal Access Token and a CheckWX Aviation
Weather API key. The Personal Access Token is required for the PiConsole to
access the data from your station, and the CheckWX API key is required to
download the closest METAR information to your station location.

A Personal Access Token can be generated, viewed, and deleted here: https://tempestwx.com/settings/tokens,
and a CheckWX API key can be obtained by registering for a free account here:
https://www.checkwxapi.com/auth/signup

Once you have a Personal Access Token and registered with CheckWX (if required),
go ahead and run the console for the first time using:
```
wfpiconsole start
```
Depending on the connection type you select, you'll be asked to enter the API
keys you have just generated above, as well as information about your station.
This includes your station ID and device IDs for your AIR, SKY, or TEMPEST
modules. To find this information either open the WeatherFlow app or view your
station page in a web browser. Click on the gear (settings) icon -> Stations ->
[Station name] -> Status.

If all goes smoothly the console should automatically add the extra information
it needs to your configuration file and then start running. You should not need
to enter this configuration information again.

Congratulations, you have installed the PiConsole for the Weather Flow Tempest
and Smart Home Weather Stations.

### Screen size

By default the PiConsole will run in full screen mode. Fullscreen mode can be
disabled in Menu -> Settings -> Display. In this case the console will use the
dimensions specified in the configuration file (```wfpiconsole.ini```), which
can be changed manually. Please note that extreme changes to the aspect ratio
will result in text fields running into one another. Under Settings -> Display
there are also settings to show/hide the cursor and show/hide the window border.

### Remote access

Please note that you cannot use SSH to start the console remotely.  Instead for
remote access it is recommended to setup VNC (https://www.raspberrypi.org/documentation/remote-access/vnc/).
Note there are currently issues using Real VNC (the default VNC provider on
Raspberry Pis) with the latest version of Raspberry  Pi OS (Bookworm): https://help.realvnc.com/hc/en-us/articles/14110635000221-Raspberry-Pi-5-Bookworm-and-RealVNC-Connect

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

1. Download and install the Python 3.11.5 version of Miniconda for Windows (a
lightweight Python interpreter): https://conda.io/miniconda.html

2. Once Miniconda is installed open the ‘Anaconda Prompt’ program.

3. In the Anaconda prompt, run:
```
python -m pip install --upgrade pip
```

4. Once that process has finished, run:
```
python -m pip install websockets numpy pytz tzlocal ephem packaging pyOpenSSL certifi
```

5. Once that has finished, install Kivy using
```
python -m pip install kivy[base]
```
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
