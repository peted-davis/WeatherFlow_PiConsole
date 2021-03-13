from kivy.clock import Clock
from functools  import partial
#import smbus
import time

def read(Obs,dt):

    # SI7021 address, 0x40(64)
    # Read data, 2 bytes, Humidity MSB first
    #bus = smbus.SMBus(1)
    #rh = bus.read_i2c_block_data(0x40, 0xE5, 2) 
    #time.sleep(0.1)
    
    # Convert the data
    #humid = ((rh[0] * 256 + rh[1]) * 125 / 65536.0) - 6

    # SI7021 address, 0x40(64)
    # Read data , 2 bytes, Temperature MSB first
    #temp = bus.read_i2c_block_data(0x40, 0xE3,2)
    #time.sleep(0.1)

    # Convert the data
    #cTemp = ((temp[0] * 256 + temp[1]) * 175.72 / 65536.0) - 46.85
    #fTemp = cTemp * 1.8 + 32
    cTemp = 10.3432432
    # Format the temperature for display and assign to indoor temperature 
    # variable
    Temp = ['{:.1f}'.format(cTemp), u'\N{DEGREE CELSIUS}']
    Obs['inTemp'] = Temp
    
    # Get new temperature in 60 seconds
    Clock.schedule_once(partial(read,Obs), 60)
    
    # Output data to screen *** this is what I need sent to the Display***
    #print ("Humidity %%RH: %.2f%%" %humid)
    #print "Temperature : %.2f C" %cTemp