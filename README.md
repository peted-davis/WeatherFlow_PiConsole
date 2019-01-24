# WeatherFlow PiConsole
Raspberry Pi Python console for the Weather Flow Smart Home Weather Station. The 
console uses the WeatherFlow REST API and websocket to stream data from your 
Weather Flow Smart Home Weather Station in real time via the internet. As soon as 
the data from your station reaches the WeatherFlow servers, it is pushed immediately 
to the console, including the 3-second rapid fire wind updates.   

Many of the graphical elements in the console are based on the Weather34 Home
Weather Station Template (https://www.weather34.com/homeweatherstation/) copyright
2015-2019 Brian Underdown. The Weather34 Home Weather Station Template is licensed
under a Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International 
License.

http://weatherflow.com/smart-home-weather-stations/  
https://community.weatherflow.com/

## Update Instructions

Follow these instructions to update an existing installation of the WeatherFlow 
PiConsole. These instructions assume you have installed the PiConsole in the 
default directory (~/wfpiconsole/). If you have installed the PiConsole in a 
different location, I assume you know what you are doing!

```
cd ~/wfpiconsole/
wget https://api.github.com/repos/peted-davis/WeatherFlow_PiConsole/tarball -O PiConsole.tar.gz
tar -xvf PiConsole.tar.gz --strip 1
rm PiConsole.tar.gz
```

If you are have the console setup to auto run using the .service file, copy the
new .service file into /etc/systemd/system and renable:

```
sudo cp WeatherFlowPiConsole.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable WeatherFlowPiConsole.service
```

## Auto-Run Instructions

If you want to enable the console to auto-run when the Raspberry Pi powers up, copy the
WeatherFlowPiConsole.service file into /etc/systemd/system/. These .service files assumes 
you have installed the PiConsole in the default directory (~/wfpiconsole/) and are using
the default 'Pi' username. If you have installed the PiConsole in a different location, or
are using a different username, I assume you know what you are doing and can edit the
.service file appropriately. 

```
cd ~/wfpiconsole/
sudo cp WeatherFlowPiConsole.service /etc/systemd/system/
```

Start the service using

```
sudo systemctl start WeatherFlowPiConsole.service
```

If the console boots and everything is working, stop the console and set the service to 
start automatically at reboot

```
sudo systemctl stop WeatherFlowPiConsole.service
sudo systemctl enable WeatherFlowPiConsole.service
```

Reboot your Raspberry Pi and the console should come up automatically

```
sudo reboot now
```

If you are going to use the auto-start method, it is highly recommended that you can SSH
into your Raspberry Pi, as the console can only be stopped using the stop command above
and not ctrl-c on the keyboard.

## Installation Instructions

Follow these instructions to setup a new installation of the WeatherFlow PiConsole on your
Raspberry Pi Official 7 inch touch screen. This initial installation should take ~1 hour.

The instructions assume you have already sucesfully setup your Raspberry Pi and 
installed Raspbian Stretch with Desktop, have attached the touch screen, and have 
either a keyboard and mouse attached directly to the Pi, or you can access the Pi 
through SSH/VNC. If you are starting from scratch, some of these links may help get 
you started:

* https://www.raspberrypi.org/downloads/raspbian/
* https://www.raspberrypi.org/documentation/configuration/security.md
* https://www.raspberrypi.org/documentation/remote-access/ssh/
* https://www.raspberrypi.org/documentation/remote-access/vnc/

### Step 1: Make sure your Raspberry Pi is fully up to date

```
sudo apt-get update && sudo apt-get dist-upgrade
```

### Step 2: Upgrade the Python 3 version of Pip

```
python3 -m pip install --upgrade pip
```	

### Step 3: Confirm current user is in "input" and "video" groups

```
sudo usermod -a -G input,video $(whoami)
```

### Step 4: Install required dependencies

`sudo apt-get install libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev pkg-config libgl1-mesa-dev libgles2-mesa-dev python-setuptools libgstreamer1.0-dev git-core gstreamer1.0-plugins-{bad,base,good,ugly} gstreamer1.0-{omx,alsa} python-dev libmtdev-dev xclip xsel libatlas-base-dev`

```
y (confirms you want to install dependencies)
[press enter]
```

### Step 5: Install required Python modules

```
sudo python3 -m pip install autobahn[twisted] pytz pyasn1-modules service_identity geopy ephem Cython numpy packaging
```

### Step 6: Install Kivy Python library - this make take some time

```
sudo python3 -m pip install git+https://github.com/kivy/kivy.git@master
```

### Step 7: Configure Kivy for Raspberry Pi touchscreen

Run Kivy for the first time to generate configuration files:

```
python3 -c "import kivy"
```

Open file ".Kivy/config.ini" in Nano:

```
nano ~/.kivy/config.ini
```

Delete everything in the [input] section. Add this:

```
mouse = mouse
mtdev_%(name)s = probesysfs,provider=mtdev
hid_%(name)s = probesysfs,provider=hidinput
```	

Save changes in Nano:

```
ctrl-x
y (confirms you want to save changes)
[press enter]
```

Reboot the system:

```
sudo reboot now
```

### Step 8: Download WeatherFlow PiConsole source code

```
cd && mkdir wfpiconsole && cd wfpiconsole
wget https://api.github.com/repos/peted-davis/WeatherFlow_PiConsole/tarball -O PiConsole.tar.gz
tar -xvf PiConsole.tar.gz --strip 1
rm PiConsole.tar.gz
```

### Step 9: Configure and Run WeatherFlow PiConsole

To get the WeatherFlow PiConsole up and running, you need to register for a 
number of API keys. One API key is needed determine the the station location 
(country) from its latitude/longitude, one needed to download an apppropriate 
weather forecast, and one needed to download the closest METAR information to 
your station location.  

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
python3 main.py
```

As this is the first run, you'll be asked to enter the API keys you have just
signed-up for above, as well as information about your station. This includes 
your station ID and device ID for your outdoor Air and Sky modules. To find this 
information either open the WeatherFlow app or view your station page in a web
browser. Click on the gear icon -> Stations -> [Station name] -> Status.

If all goes smoothly the console should automatically add the extra information 
it needs to your configuration file and then start running.

Congratulations, you have installed the Raspberry Pi Python console for the 
Weather Flow Smart Home Weather Station.