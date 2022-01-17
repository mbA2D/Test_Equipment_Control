# Repurposed for PCA9539 IO Expander.
# Address Ranges updated by Micah Black Oct 1 2021 



# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2021 James Carr
#
# SPDX-License-Identifier: MIT

"""
`community_tca9555`
================================================================================

CircuitPython library for connecting a TCA9555 16-Bit I2C GPIO expander
Library for TCA9555 Low-Voltage 16-Bit I2C and SMBus I/O Expander with Interrupt Output
and Configuration Registers


* Author(s): James Carr

Implementation Notes
--------------------

**Hardware:**

* `Pimoroni Pico RGB Keybad Base <https://shop.pimoroni.com/products/pico-rgb-keypad-base>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
    https://github.com/adafruit/circuitpython/releases

* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
* Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/lesamouraipourpre/Community_CircuitPython_TCA9555.git"


import busio
from micropython import const
from adafruit_bus_device.i2c_device import I2CDevice
from adafruit_register.i2c_bit import ROBit, RWBit
from adafruit_register.i2c_bits import ROBits, RWBits


ADDRESS_MINIMUM = const(0x74)
"""The minimum I2C address the TCA9555 supports"""
ADDRESS_MAXIMUM = const(0x77)
"""The maximum I2C address the TCA9555 supports"""

INPUT_PORT_0 = const(0x00)
INPUT_PORT_1 = const(0x01)
OUTPUT_PORT_0 = const(0x02)
OUTPUT_PORT_1 = const(0x03)
POLARITY_INVERSION_PORT_0 = const(0x04)
POLARITY_INVERSION_PORT_1 = const(0x05)
CONFIGURATION_PORT_0 = const(0x06)
CONFIGURATION_PORT_1 = const(0x07)


class PCA9539:
	# pylint: disable=too-few-public-methods
	"""CircuitPython driver for the Texas Instruments TCA9555 expander."""
	
	CONF_INPUT = 1
	CONF_OUTPUT = 0
	
	POL_INV_FALSE = 0
	POL_INV_TRUE = 1
	
	def __init__(self, i2c: busio.I2C, address: int = ADDRESS_MINIMUM):
		"""
        :param busio.I2C i2c: the I2C bus object to use. *Note:* This will
            be converted to an `adafruit_bus_device.i2c_device.I2CDevice`
            internally.
        :param int address: The I2C address of the TCA9555. This must be in
            the range `ADDRESS_MINIMUM` to `ADDRESS_MAXIMUM`. (Defaults to
            `ADDRESS_MINIMUM`)
        """
		if not ADDRESS_MINIMUM <= address <= ADDRESS_MAXIMUM:
			raise ValueError(
				"Address '{}' is not in the allowed range: {}-{}".format(
					address, ADDRESS_MINIMUM, ADDRESS_MAXIMUM
				)
			)

		# This MUST be named i2c_device for register to work
		self.i2c_device = I2CDevice(i2c, address)
	
	def set_output_val(self, pin, val):
		if pin == 0:
			self.output_port_0_pin_0 = val
		elif pin == 1:
			self.output_port_0_pin_1 = val
		elif pin == 2:
			self.output_port_0_pin_2 = val
		elif pin == 3:
			self.output_port_0_pin_3 = val
		elif pin == 4:
			self.output_port_0_pin_4 = val
		elif pin == 5:
			self.output_port_0_pin_5 = val
		elif pin == 6:
			self.output_port_0_pin_6 = val
		elif pin == 7:
			self.output_port_0_pin_7 = val
		elif pin == 8:
			self.output_port_1_pin_0 = val
		elif pin == 9:
			self.output_port_1_pin_1 = val
		elif pin == 10:
			self.output_port_1_pin_2 = val
		elif pin == 11:
			self.output_port_1_pin_3 = val
		elif pin == 12:
			self.output_port_1_pin_4 = val
		elif pin == 13:
			self.output_port_1_pin_5 = val
		elif pin == 14:
			self.output_port_1_pin_6 = val
		elif pin == 15:
			self.output_port_1_pin_7 = val
	
	def get_input_val(self, pin):
		if pin == 0:
			return self.input_port_0_pin_0
		elif pin == 1:
			return self.input_port_0_pin_1
		elif pin == 2:
			return self.input_port_0_pin_2
		elif pin == 3:
			return self.input_port_0_pin_3
		elif pin == 4:
			return self.input_port_0_pin_4
		elif pin == 5:
			return self.input_port_0_pin_5
		elif pin == 6:
			return self.input_port_0_pin_6
		elif pin == 7:
			return self.input_port_0_pin_7
		elif pin == 8:
			return self.input_port_1_pin_0
		elif pin == 9:
			return self.input_port_1_pin_1
		elif pin == 10:
			return self.input_port_1_pin_2
		elif pin == 11:
			return self.input_port_1_pin_3
		elif pin == 12:
			return self.input_port_1_pin_4
		elif pin == 13:
			return self.input_port_1_pin_5
		elif pin == 14:
			return self.input_port_1_pin_6
		elif pin == 15:
			return self.input_port_1_pin_7
	
	def set_conf_dir(self, pin, val):
		if pin == 0:
			self.configuration_port_0_pin_0 = val
		elif pin == 1:
			self.configuration_port_0_pin_1 = val
		elif pin == 2:
			self.configuration_port_0_pin_2 = val
		elif pin == 3:
			self.configuration_port_0_pin_3 = val
		elif pin == 4:
			self.configuration_port_0_pin_4 = val
		elif pin == 5:
			self.configuration_port_0_pin_5 = val
		elif pin == 6:
			self.configuration_port_0_pin_6 = val
		elif pin == 7:
			self.configuration_port_0_pin_7 = val
		elif pin == 8:
			self.configuration_port_1_pin_0 = val
		elif pin == 9:
			self.configuration_port_1_pin_1 = val
		elif pin == 10:
			self.configuration_port_1_pin_2 = val
		elif pin == 11:
			self.configuration_port_1_pin_3 = val
		elif pin == 12:
			self.configuration_port_1_pin_4 = val
		elif pin == 13:
			self.configuration_port_1_pin_5 = val
		elif pin == 14:
			self.configuration_port_1_pin_6 = val
		elif pin == 15:
			self.configuration_port_1_pin_7 = val

	def set_pol_inv(self, pin, val):
		if pin == 0:
			self.polarity_inversion_port_0_pin_0 = val
		elif pin == 1:
			self.polarity_inversion_port_0_pin_1 = val
		elif pin == 2:
			self.polarity_inversion_port_0_pin_2 = val
		elif pin == 3:
			self.polarity_inversion_port_0_pin_3 = val
		elif pin == 4:
			self.polarity_inversion_port_0_pin_4 = val
		elif pin == 5:
			self.polarity_inversion_port_0_pin_5 = val
		elif pin == 6:
			self.polarity_inversion_port_0_pin_6 = val
		elif pin == 7:
			self.polarity_inversion_port_0_pin_7 = val
		elif pin == 8:
			self.polarity_inversion_port_1_pin_0 = val
		elif pin == 9:
			self.polarity_inversion_port_1_pin_1 = val
		elif pin == 10:
			self.polarity_inversion_port_1_pin_2 = val
		elif pin == 11:
			self.polarity_inversion_port_1_pin_3 = val
		elif pin == 12:
			self.polarity_inversion_port_1_pin_4 = val
		elif pin == 13:
			self.polarity_inversion_port_1_pin_5 = val
		elif pin == 14:
			self.polarity_inversion_port_1_pin_6 = val
		elif pin == 15:
			self.polarity_inversion_port_1_pin_7 = val
	
	
	input_ports = ROBits(16, INPUT_PORT_0, 0, register_width=2)

	input_port_0 = ROBits(8, INPUT_PORT_0, 0)
	
	input_port_0_pin_0 = ROBit(INPUT_PORT_0, 0)
	input_port_0_pin_1 = ROBit(INPUT_PORT_0, 1)
	input_port_0_pin_2 = ROBit(INPUT_PORT_0, 2)
	input_port_0_pin_3 = ROBit(INPUT_PORT_0, 3)
	input_port_0_pin_4 = ROBit(INPUT_PORT_0, 4)
	input_port_0_pin_5 = ROBit(INPUT_PORT_0, 5)
	input_port_0_pin_6 = ROBit(INPUT_PORT_0, 6)
	input_port_0_pin_7 = ROBit(INPUT_PORT_0, 7)

	input_port_1 = ROBits(8, INPUT_PORT_1, 0)

	input_port_1_pin_0 = ROBit(INPUT_PORT_1, 0)
	input_port_1_pin_1 = ROBit(INPUT_PORT_1, 1)
	input_port_1_pin_2 = ROBit(INPUT_PORT_1, 2)
	input_port_1_pin_3 = ROBit(INPUT_PORT_1, 3)
	input_port_1_pin_4 = ROBit(INPUT_PORT_1, 4)
	input_port_1_pin_5 = ROBit(INPUT_PORT_1, 5)
	input_port_1_pin_6 = ROBit(INPUT_PORT_1, 6)
	input_port_1_pin_7 = ROBit(INPUT_PORT_1, 7)

	output_ports = RWBits(16, OUTPUT_PORT_0, 0, register_width=2)

	output_port_0 = RWBits(8, OUTPUT_PORT_0, 0)

	output_port_0_pin_0 = RWBit(OUTPUT_PORT_0, 0)
	output_port_0_pin_1 = RWBit(OUTPUT_PORT_0, 1)
	output_port_0_pin_2 = RWBit(OUTPUT_PORT_0, 2)
	output_port_0_pin_3 = RWBit(OUTPUT_PORT_0, 3)
	output_port_0_pin_4 = RWBit(OUTPUT_PORT_0, 4)
	output_port_0_pin_5 = RWBit(OUTPUT_PORT_0, 5)
	output_port_0_pin_6 = RWBit(OUTPUT_PORT_0, 6)
	output_port_0_pin_7 = RWBit(OUTPUT_PORT_0, 7)

	output_port_1 = RWBits(8, OUTPUT_PORT_1, 0)

	output_port_1_pin_0 = RWBit(OUTPUT_PORT_1, 0)
	output_port_1_pin_1 = RWBit(OUTPUT_PORT_1, 1)
	output_port_1_pin_2 = RWBit(OUTPUT_PORT_1, 2)
	output_port_1_pin_3 = RWBit(OUTPUT_PORT_1, 3)
	output_port_1_pin_4 = RWBit(OUTPUT_PORT_1, 4)
	output_port_1_pin_5 = RWBit(OUTPUT_PORT_1, 5)
	output_port_1_pin_6 = RWBit(OUTPUT_PORT_1, 6)
	output_port_1_pin_7 = RWBit(OUTPUT_PORT_1, 7)
	
	polarity_inversions = RWBits(16, POLARITY_INVERSION_PORT_0, 0, register_width=2)

	polarity_inversion_port_0 = RWBits(8, POLARITY_INVERSION_PORT_0, 0)

	polarity_inversion_port_0_pin_0 = RWBit(POLARITY_INVERSION_PORT_0, 0)
	polarity_inversion_port_0_pin_1 = RWBit(POLARITY_INVERSION_PORT_0, 1)
	polarity_inversion_port_0_pin_2 = RWBit(POLARITY_INVERSION_PORT_0, 2)
	polarity_inversion_port_0_pin_3 = RWBit(POLARITY_INVERSION_PORT_0, 3)
	polarity_inversion_port_0_pin_4 = RWBit(POLARITY_INVERSION_PORT_0, 4)
	polarity_inversion_port_0_pin_5 = RWBit(POLARITY_INVERSION_PORT_0, 5)
	polarity_inversion_port_0_pin_6 = RWBit(POLARITY_INVERSION_PORT_0, 6)
	polarity_inversion_port_0_pin_7 = RWBit(POLARITY_INVERSION_PORT_0, 7)
	
	polarity_inversion_port_1 = RWBits(8, POLARITY_INVERSION_PORT_1, 0)

	polarity_inversion_port_1_pin_0 = RWBit(POLARITY_INVERSION_PORT_1, 0)
	polarity_inversion_port_1_pin_1 = RWBit(POLARITY_INVERSION_PORT_1, 1)
	polarity_inversion_port_1_pin_2 = RWBit(POLARITY_INVERSION_PORT_1, 2)
	polarity_inversion_port_1_pin_3 = RWBit(POLARITY_INVERSION_PORT_1, 3)
	polarity_inversion_port_1_pin_4 = RWBit(POLARITY_INVERSION_PORT_1, 4)
	polarity_inversion_port_1_pin_5 = RWBit(POLARITY_INVERSION_PORT_1, 5)
	polarity_inversion_port_1_pin_6 = RWBit(POLARITY_INVERSION_PORT_1, 6)
	polarity_inversion_port_1_pin_7 = RWBit(POLARITY_INVERSION_PORT_1, 7)

	configuration_ports = RWBits(16, CONFIGURATION_PORT_0, 0, register_width=2)

	configuration_port_0 = RWBits(8, CONFIGURATION_PORT_0, 0)

	configuration_port_0_pin_0 = RWBit(CONFIGURATION_PORT_0, 0)
	configuration_port_0_pin_1 = RWBit(CONFIGURATION_PORT_0, 1)
	configuration_port_0_pin_2 = RWBit(CONFIGURATION_PORT_0, 2)
	configuration_port_0_pin_3 = RWBit(CONFIGURATION_PORT_0, 3)
	configuration_port_0_pin_4 = RWBit(CONFIGURATION_PORT_0, 4)
	configuration_port_0_pin_5 = RWBit(CONFIGURATION_PORT_0, 5)
	configuration_port_0_pin_6 = RWBit(CONFIGURATION_PORT_0, 6)
	configuration_port_0_pin_7 = RWBit(CONFIGURATION_PORT_0, 7)

	configuration_port_1 = RWBits(8, CONFIGURATION_PORT_1, 0)
	
	configuration_port_1_pin_0 = RWBit(CONFIGURATION_PORT_1, 0)
	configuration_port_1_pin_1 = RWBit(CONFIGURATION_PORT_1, 1)
	configuration_port_1_pin_2 = RWBit(CONFIGURATION_PORT_1, 2)
	configuration_port_1_pin_3 = RWBit(CONFIGURATION_PORT_1, 3)
	configuration_port_1_pin_4 = RWBit(CONFIGURATION_PORT_1, 4)
	configuration_port_1_pin_5 = RWBit(CONFIGURATION_PORT_1, 5)
	configuration_port_1_pin_6 = RWBit(CONFIGURATION_PORT_1, 6)
	configuration_port_1_pin_7 = RWBit(CONFIGURATION_PORT_1, 7)
	