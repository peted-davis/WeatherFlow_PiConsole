# WeatherFlow PiConsole
Raspberry Pi Python console for the Weather Flow Smart Home Weather Station. The 
console uses the WeatherFlow REST API and websocket to stream data from your 
Weather Flow Smart Home Weather Station in real time via the internet. As soon 
as the data from your station reaches the WeatherFlow servers, it is pushed 
immediately to the console, including the 3-second rapid fire wind updates.   

Many of the graphical elements in the console are based on the Weather34 Home
Weather Station Template (https://www.weather34.com/homeweatherstation/) 
copyright 2015-2019 Brian Underdown. The Weather34 Home Weather Station Template 
is licensed under a Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 
International License.

http://weatherflow.com/smart-home-weather-stations/  
https://community.weatherflow.com/

## Installation Instructions

The installation of the WeatherFlow PiConsole is fully automated, and can
be started from the terminal with a single command. The initial installation 
should take ~1 hour.

The automated installer assumes you have already sucesfully setup your Raspberry 
Pi and have installed Raspbian Stretch with Desktop. You should have also attached 
the touch screen, and have either a keyboard and mouse attached directly to the Pi, 
or have accessesd the Pi remotely through SSH/VNC. If you are starting from 
scratch, some of these links may help get you started:

* https://www.raspberrypi.org/downloads/raspbian/
* https://www.raspberrypi.org/documentation/configuration/security.md
* https://www.raspberrypi.org/documentation/remote-access/ssh/
* https://www.raspberrypi.org/documentation/remote-access/vnc/

### One-Step Automated Install

The WeatherFlow PiConsole can be installed quickly and conveniently with the following 
command:
```
curl -sSL https://peted-davis.github.io/wfpiconsole | bash
```
Piping a command directly to ```bash``` is controversial, as it prevents you from 
reading code that is about to run on your system. If you are worried about the contents
of the installer, please examine the install file in the Git repository before running 
the install command.

### Configure and Run WeatherFlow PiConsole

As this will be the first time you have run the console, you'll be asked to enter 
a number of API keys required by the console to run. One API key is needed 
determine the the station location (country) from its latitude/longitude, 
one needed to download an apppropriate weather forecast for your location, 
and one needed to download the closest METAR information for your location.  

First, go to http://www.geonames.org/login and register for a new account. Once
you have registered, go to your account (http://www.geonames.org/manageaccount)
and activate "Free Web Services". Once this is done, your username will be your
'GeoNames' API key.

Next, if you live in the UK go to the UK MetOffice DataPoint homepage
(https://www.metoffice.gov.uk/datapoint), and register for a new account. You'll
be given an API key that will be you 'MetOffice' API key.

If you live outside the UK, register instead for a DarkSky API account 
(https://darksky.net/dev/register). This will be your 'DarkSky' API key. The 
console requires you to enter either a MetOffice API key or a DarkSky API key.

Finally go to CheckWX Aviation Weather and register to enable access to the 
closest METAR information to you station location. 
(https://www.checkwx.com/signup). This will be your 'CheckWX' key.

Once you have registered for the required API keys, go ahead and run the console
for the first time using:

```
wfpiconsole start
```

You'll be asked to enter the API keys you have just signed-up for above, as well 
as information about your station. This includes your station ID and device ID 
for your outdoor Air and Sky modules. To find this information either open the 
WeatherFlow app or view your station page in a web browser. Click on the gear icon 
-> Stations -> [Station name] -> Status.

If all goes smoothly the console should automatically add the extra information 
it needs to your configuration file and then start running. You should not need 
to enter this information again.

Congratulations, you have installed the Raspberry Pi Python console for the 
Weather Flow Smart Home Weather Station.

## Update Instructions

The WeatherFlow PiConsole can be updated quickly and easily with the following 
command:
```
wfpiconsole update
```
The update process will retain your existing user settings, but may prompt for
input from time to time in order to add new functionality. Once the update has 
finished, restart the console using
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
stop command
```
wfpiconsole stop
```
or by a hard power down
