#Testing multiple MCP devices on the same computer
#Reference: https://github.com/adafruit/Adafruit_Blinka/pull/349
#We need to use the HID.open_path method instead of the HID.open that the library uses

import hid
#need busio to override the I2C initialization so it doesn't use detector to look for the board
import busio
import time

#The adafruit library creates an instance of the controller. We need to import that one
from adafruit_blinka.microcontroller.mcp2221.mcp2221 import mcp2221 as ada_mcp2221
from adafruit_blinka.microcontroller.mcp2221.mcp2221 import MCP2221_RESET_DELAY
#We need to override the __init__ in adafruit's MCP2221 class so we need that as well
from adafruit_blinka.microcontroller.mcp2221.mcp2221 import MCP2221 as _MCP2221
#We also need to override the custom I2C class since they also use the mcp2221 that the library created
from adafruit_blinka.microcontroller.mcp2221.i2c import I2C as _MCP2221_I2C

class I2C(busio.I2C):
	def __init__(self, mcp2221_i2c):
		self._i2c = mcp2221_i2c

class MCP2221_I2C(_MCP2221_I2C):
	def __init__(self, mcp2221, *, frequency=100000):
		self._mcp2221 = mcp2221
		self._mcp2221._i2c_configure(frequency)

class MCP2221(_MCP2221):
	def __init__(self, address):
		self._hid = hid.device()
		self._hid.open_path(address)
		if MCP2221_RESET_DELAY >= 0:
			self._reset()
		self._gp_config = [0x07] * 4  # "don't care" initial value
		for pin in range(4):
			self.gp_set_mode(pin, self.GP_GPIO)  # set to GPIO mode
			self.gpio_set_direction(pin, 1)  # set to INPUT


def connect_to_all_mcps():
    #find all the hid addresses associated with devices that match the VID and PID of mcp2221
	addresses = [mcp["path"] for mcp in hid.enumerate(ada_mcp2221.VID, ada_mcp2221.PID)]
	
	print("Num Addresses Found: {}".format(len(addresses)))
	
    #create array to hold all devices that we find
	devices = []
	addrs_used = []
	
    #add the device that is auto-created from adafruit libraries
	#devices.append(_mcp2221)
	#ada_mcp2221._hid.close()
	#time.sleep(0.1)
	#del ada_mcp2221
	
	
	#TODO - this does not seem to be catching the extra address.
	index = 0
	for addr in addresses:
		print(addr)
		#skip the first address? - does not seem to work
		if(index == 0):
			#index += 1
			#continue
			pass
		try:
			device = MCP2221(addr)
			devices.append(device)
		except OSError:
			print("Device path: {} is already used".format(addr))

	return devices
