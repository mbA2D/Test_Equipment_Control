# The MIT License (MIT)
# Copyright (c) 2019 Mike Teachman
# https://opensource.org/licenses/MIT

# MicroPython driver for the Texas Instruments ADS1219 ADC

from micropython import const
import adafruit_bus_device.i2c_device as i2cdevice
from adafruit_register.i2c_struct import ROUnaryStruct, UnaryStruct
from adafruit_register.i2c_bits import ROBits, RWBits
from adafruit_register.i2c_bit import ROBit, RWBit

try:
    import struct
except ImportError:
    import ustruct as struct

import time

_CHANNEL_MASK = const(0b11100000)
_GAIN_MASK = const(0b00010000)
_DR_MASK = const(0b00001100)
_CM_MASK = const(0b00000010)
_VREF_MASK = const(0b00000001)

_COMMAND_RESET = const(0b00000110)
_COMMAND_START_SYNC = const(0b00001000)
_COMMAND_POWERDOWN = const(0b00000010)
_COMMAND_RDATA = const(0b00010000)

_COMMAND_RREG_CONFIG = const(0b00100000)
_COMMAND_RREG_STATUS = const(0b00100100)
_COMMAND_WREG_CONFIG = const(0b01000000)

_DRDY_MASK = const(0b10000000)  
_DRDY_NO_NEW_RESULT = const(0b00000000)    # No new conversion result available
_DRDY_NEW_RESULT_READY = const(0b10000000) # New conversion result ready

class ADS1219_MUX:
	P_AIN0_N_AIN1 = 0
	P_AIN2_N_AIN3 = 1
	P_AIN1_N_AIN2 = 2
	AIN0 = 3
	AIN1 = 4
	AIN2 = 5
	AIN3 = 6
	P_N_AVDD_2 = 7
	
class ADS1219_GAIN:
	GAIN_1 = 0
	GAIN_4 = 1
	
class ADS1219_DATA_RATE:
	DR_20_SPS = 0
	DR_90_SPS = 1
	DR_330_SPS = 2
	DR_1000_SPS = 3

class ADS1219_CONV_MODE:
	CM_SINGLE = 0
	CM_CONTINUOUS = 1
	
class ADS1219_VREF:
	VREF_INTERNAL = 0
	VREF_EXTERNAL = 1



class ADS1219:
	
	VREF_INTERNAL_MV = 2048 # Internal reference voltage = 2048 mV
	POSITIVE_CODE_RANGE = 0x7FFFFF # 23 bits of positive range    

	def __init__(self, i2c, address=0x40):
		self.i2c_device = i2cdevice.I2CDevice(i2c, address)
		
		self.MUX = ADS1219_MUX.P_AIN0_N_AIN1
		self.GAIN = ADS1219_GAIN.GAIN_1
		self.DR = ADS1219_DATA_RATE.DR_20_SPS
		self.CM = ADS1219_CONV_MODE.CM_SINGLE
		self.VREF = ADS1219_VREF.VREF_INTERNAL
		self.config_byte = self._calc_config_byte()
		
		self.reset()
	
	def _calc_config_byte(self):
		#cfg_byte = bytearray(1)
		return ((self.MUX << 5) | (self.GAIN << 4) | (self.DR << 2) | (self.CM << 1) | (self.VREF))
		
		#print("cfg_byte: {}\tMUX: {}\tGAIN: {}\tDR: {}\tCM: {}\tVREF: {}".format(bin(cfg_byte), bin(self.MUX), bin(self.GAIN), bin(self.DR), bin(self.CM), bin(self.VREF)))
	
	def _update_config(self):
		new_config_byte = self._calc_config_byte()
		
		if new_config_byte != self.config_byte:
			self.config_byte = new_config_byte
			data = bytearray([_COMMAND_WREG_CONFIG, self.config_byte])
			with self.i2c_device:	
				self.i2c_device.write(data)
	
	def read_config(self):
		rreg = struct.pack('B', _COMMAND_RREG_CONFIG) 
		#self._i2c.writeto(self._address, rreg)
		with self.i2c_device:		
			self.i2c_device.write(rreg)
			config = bytearray(1)
			#self._i2c.readfrom_into(self._address, config)
			self.i2c_device.readinto(config)
		return config[0]
	
	def read_status(self):
		rreg = struct.pack('B', _COMMAND_RREG_STATUS) 
		#self._i2c.writeto(self._address, rreg)
		with self.i2c_device:
			self.i2c_device.write(rreg)
			status = bytearray(1)
			#self._i2c.readfrom_into(self._address, status)
			self.i2c_device.readinto(status)
		return status[0]

	def set_channel(self, channel):
		self.MUX = channel
		self._update_config()
		
	def set_gain(self, gain):
		self.GAIN = gain
		self._update_config()
		
	def set_data_rate(self, dr):
		self.DR = dr
		self._update_config()
		
	def set_conversion_mode(self, cm):
		self.CM = cm
		self._update_config()
		
	def set_vref(self, vref):
		self.VREF = vref
		self._update_config()
		
	def read_data(self):
		if self.CM == ADS1219_CONV_MODE.CM_SINGLE:
			self.start_sync()
			# loop until conversion is completed
			while((self.read_status() & _DRDY_MASK) == _DRDY_NO_NEW_RESULT):
				time.sleep(100.0/1000/1000)
			
		rreg = struct.pack('B', _COMMAND_RDATA) 
		#self._i2c.writeto(self._address, rreg)
		with self.i2c_device:		
			self.i2c_device.write(rreg)
			data = bytearray(3)
			#self._i2c.readfrom_into(self._address, data)
			self.i2c_device.readinto(data)
		return struct.unpack('>I', b'\x00' + data)[0]
	
	def read_data_irq(self):
		rreg = struct.pack('B', _COMMAND_RDATA) 
		#self._i2c.writeto(self._address, rreg)
		with self.i2c_device:	
			self.i2c_device.write(rreg)
			data = bytearray(3)
			#self._i2c.readfrom_into(self._address, data)
			self.i2c_device.readinto(data)
		return struct.unpack('>I', b'\x00' + data)[0]
		
	def reset(self):
		data = struct.pack('B', _COMMAND_RESET)
		#self._i2c.writeto(self._address, data) 
		with self.i2c_device:	
			self.i2c_device.write(data)
		self.reset_local_conf_copies()
		
	def start_sync(self):
		data = struct.pack('B', _COMMAND_START_SYNC)
		#self._i2c.writeto(self._address, data)
		with self.i2c_device:	
			self.i2c_device.write(data)

	def powerdown(self):
		data = struct.pack('B', _COMMAND_POWERDOWN)
		#self._i2c.writeto(self._address, data)
		with self.i2c_device:
			self._i2c.writeto(self._address, data)
	
	def reset_local_conf_copies(self):
		self.MUX = ADS1219_MUX.P_AIN0_N_AIN1
		self.GAIN = ADS1219_GAIN.GAIN_1
		self.DR = ADS1219_DATA_RATE.DR_20_SPS
		self.CM = ADS1219_CONV_MODE.CM_SINGLE
		self.VREF = ADS1219_VREF.VREF_INTERNAL
		self.config_byte = self._calc_config_byte()