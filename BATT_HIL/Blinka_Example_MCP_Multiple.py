#Packages
import time
import hid
import busio

#Drivers for ICs
import adafruit_tca9548a
from adafruit_pca9685 import PCA9685
from .PCA9539.PCA9539 import PCA9539
import adafruit_ads1x15.ads1115 as ADS1115
from adafruit_ads1x15.analog_in import AnalogIn as ADS1115_AnalogIn
from .LTC2944 import LTC2944 as LTC2944
from .ADS1219.ads1219 import ADS1219, ADS1219_MUX, ADS1219_GAIN, ADS1219_DATA_RATE, ADS1219_CONV_MODE, ADS1219_VREF

#Multiple MCP Devices
#from adafruit_blinka.microcontroller.mcp2221.mcp2221 import mcp2221 as _mcp2221
from adafruit_blinka.microcontroller.mcp2221.mcp2221 import MCP2221 as _MCP2221
from adafruit_blinka.microcontroller.mcp2221.i2c import I2C as _MCP2221I2C


#I2C Addresses for control section
CTRL_IO_EXP_I2C_ADDR = 0x77
PWM_DRIVER_I2C_ADDR = 0x60
I2C_EXP_I2C_ADDR = 0x70
CTRL_ADC_I2C_ADDR = 0x48

#I2C Addresses for each channel
CH_CC_I2C_ADDR = 0x64
CH_ADC_I2C_ADDR = 0x40
CH_IO_EXP_I2C_ADDR = 0x74

############## CLASSES TO DEAL WITH MULTIPLE MCPS #################

class MCP2221(_MCP2221):  # pylint: disable=too-few-public-methods
	def __init__(self, address):
		self._hid = hid.device()
		self._hid.open_path(address)
		print("Connected to " + str(address))
		self._gp_config = [0x07] * 4  # "don't care" initial value
		for pin in range(4):
			self.gp_set_mode(pin, self.GP_GPIO)  # set to GPIO mode
			self.gpio_set_direction(pin, 1)  # set to INPUT

class MCP2221I2C(_MCP2221I2C):  # pylint: disable=too-few-public-methods
	def __init__(self, mcp2221, *, frequency=100000):
		self._mcp2221 = mcp2221
		self._mcp2221._i2c_configure(frequency)

class I2C(busio.I2C):  # pylint: disable=too-few-public-methods
	def __init__(self, mcp2221_i2c):
		self._i2c = mcp2221_i2c


################### CLASSES FOR EACH OF THE BOARDS ################
class SAFETY_Controller():
	def __init__(self, mcp):
		self._mcp = mcp
		self._i2c = I2C(MCP2221I2C(self._mcp))
		self._ctrl_exp = PCA9539(self._i2c, CTRL_IO_EXP_I2C_ADDR)
		
		
		#Setup IO expander pins
		self.latch_reset_pin = 5
		self.wdi_pin = 7
		self.interlock_loop_en_pin = 0
		self.nRESET_pin = 1
		self.nINTERLOCK_GOOD_pin = 8
		
		self._ctrl_exp.set_output_val(self.latch_reset_pin, 1)
		self._ctrl_exp.set_output_val(self.wdi_pin, 1)
		self._ctrl_exp.set_output_val(self.interlock_loop_en_pin, 0)
		self._ctrl_exp.set_output_val(self.nRESET_pin, 0)
		self._ctrl_exp.set_output_val(self.nINTERLOCK_GOOD_pin, 0)

		self._ctrl_exp.set_pol_inv(self.latch_reset_pin, PCA9539.POL_INV_FALSE)
		self._ctrl_exp.set_pol_inv(self.wdi_pin, PCA9539.POL_INV_FALSE)
		self._ctrl_exp.set_pol_inv(self.interlock_loop_en_pin, PCA9539.POL_INV_FALSE)
		self._ctrl_exp.set_pol_inv(self.nRESET_pin, PCA9539.POL_INV_FALSE)
		self._ctrl_exp.set_pol_inv(self.nINTERLOCK_GOOD_pin, PCA9539.POL_INV_FALSE)

		self._ctrl_exp.set_conf_dir(self.latch_reset_pin, PCA9539.CONF_OUTPUT)
		self._ctrl_exp.set_conf_dir(self.wdi_pin, PCA9539.CONF_OUTPUT)
		self._ctrl_exp.set_conf_dir(self.interlock_loop_en_pin, PCA9539.CONF_OUTPUT)
		self._ctrl_exp.set_conf_dir(self.nRESET_pin, PCA9539.CONF_INPUT)
		self._ctrl_exp.set_conf_dir(self.nINTERLOCK_GOOD_pin, PCA9539.CONF_INPUT)
		
		
	def get_interlock_status(self):
		#if true, interlock loop is complete, current is flowing
		return  not self._ctrl_exp.get_input_val(self.nINTERLOCK_GOOD_pin)
	
	def get_reset_status(self):
		#if true, the system is in reset
		return self._ctrl_exp.get_input_val(self.nRESET_pin)

	def set_interlock(self, val):
		self._ctrl_exp.set_output_val(self.interlock_loop_en_pin, val)

	def kick_watchdog(self):
		#watchdog just needs any edge, rising or falling.
		self._ctrl_exp.set_output_val(self.wdi_pin, not self._ctrl_exp.get_input_val(self.wdi_pin))
	
	def reset_latch(self):
		#pull low for a brief time
		self._ctrl_exp.set_output_val(self.latch_reset_pin, 0)
		time.sleep(0.01)
		self._ctrl_exp.set_output_val(self.latch_reset_pin, 1)


class FET_Board():
	def __init__(self, mcp):
		self._mcp = mcp
		self._i2c = I2C(MCP2221I2C(self._mcp))
		#self._ctrl_exp = PCA9539(self._i2c, CTRL_IO_EXP_I2C_ADDR) #CHANGED
		self._i2c_switch = adafruit_tca9548a.TCA9548A(self._i2c)
		self._pwm_drv = PCA9685(self._i2c, address = PWM_DRIVER_I2C_ADDR) #CHANGED
		#self._ntc_adc = ADS1115.ADS1115(self._i2c) #CHANGED
		
		self.eload_used = False
		self.psu_1_used = False
		self.psu_2_used = False
		
		self.eload_ch = None
		self.psu_1_ch = None
		self.psu_2_ch = None
		
		self.channel_min = 0
		self.channel_max = 3
		self.num_channels = 1 #CHANGED
		
		#setup CTRL IO Expander
		'''
		self.latch_reset_pin = 9
		self.wdi_pin = 8
		self.nRESET_pin = 2
		
		self._ctrl_exp.set_output_val(self.latch_reset_pin, 1)
		self._ctrl_exp.set_output_val(self.wdi_pin, 1)
		self._ctrl_exp.set_output_val(self.nRESET_pin, 0)

		self._ctrl_exp.set_pol_inv(self.latch_reset_pin, PCA9539.POL_INV_FALSE)
		self._ctrl_exp.set_pol_inv(self.wdi_pin, PCA9539.POL_INV_FALSE)
		self._ctrl_exp.set_pol_inv(self.nRESET_pin, PCA9539.POL_INV_FALSE)

		self._ctrl_exp.set_conf_dir(self.latch_reset_pin, PCA9539.CONF_OUTPUT)
		self._ctrl_exp.set_conf_dir(self.wdi_pin, PCA9539.CONF_OUTPUT)
		self._ctrl_exp.set_conf_dir(self.nRESET_pin, PCA9539.CONF_INPUT)
		'''
		
		#setup PWM Driver
		self._pwm_drv.frequency = 250
		
		self.fan_ch = 0
		self.bat_0_r_ch = 2
		self.bat_0_g_ch = 3
		self.bat_0_b_ch = 4
		self.bat_1_r_ch = 10
		self.bat_1_g_ch = 11
		self.bat_1_b_ch = 12
		self.bat_2_r_ch = 5
		self.bat_2_g_ch = 6
		self.bat_2_b_ch = 7
		self.bat_3_r_ch = 13
		self.bat_3_g_ch = 14
		self.bat_3_b_ch = 15
		
		self.set_fan_speed(1)#default fan speed - full on #CHANGED
		
		#setup NTC ADC
		#set gain and sampling
		#self.ntcs = []
		#for pin in range(4):
			#ntcs.append(ADS1115_AnalogIn(_ntc_adc, pin)) #CHANGED

		#Setup all 4 FET Channels
		self.channels = []
		for ch in range(self.num_channels):
			self.channels.append(FET_Channel(self._i2c_switch[ch]))


	def get_interlock_status(self):
		return  not self._mcp.gpio_get_pin(3)

	def set_fan_speed(self, speed):
		if 0 <= speed <= 1:
			#set speed
			#convert from 0-1 to 12-bit to 16-bit
			speed_12b = 0xFFF * speed
			speed_16b = (speed_12b << 4) | 0x000F
			self._pwm_drv.channels[self.fan_ch].duty_cycle = speed_16b
		else:
			print("Invalid Fan Speed")

	def measure_voltage(self, channel):
		return self.channels[channel].measure_voltage()
		
	def measure_current(self, channel):
		return self.channels[channel].measure_current()
		
	def measure_temp(self, channel):
		return self.channels[channel].measure_temp()
		
	def get_cc(self, channel):
		return self.channels[channel].get_cc()
	
	#These checks are over-the-top in thoroughness. (e.g. not very well coded but, but safe).
	#Should revisit later to see what is really required.
	def set_eload_ch(self, channel):
		#Force disconnect all channels
		if channel == None:
			#go through all channels. If a channel is connected then disable the channel
			for ch in self.channels:
				if(ch.connected_to == "eload"):
					ch.enable_ideal_diodes(False)
			self.eload_used = False
			self.eload_ch = None
		
		#Check channel numbering
		if  not check_valid_channel(channel):
			print("Invalid Channel")
			return
		
		#Check if already used
		elif self.eload_used:
			print("Eload Already Used")
			return
		
		#ensure no other equipment is connected to this channel
		elif self.channels[channel] != "none":
			print("Another Device Connected to this channel already")
			return
		
		else:
			#extra check - make sure eload is disconnected from all other channels
			if "eload" not in self.list_connected_to():
				self.eload_used = True
				self.eload_ch = channel
				self.channels[channel].set_eload()
			else:
				#We should never get here - should be caught above
				print("Eload Already Connected")
			
	def set_psu_1_ch(self, channel):
		#Force disconnect all channels
		if channel == None:
			#go through all channels. If a channel is connected then disable the channel
			for ch in self.channels:
				if(ch.connected_to == "psu1"):
					ch.enable_ideal_diodes(False)
			self.psu_1_used = False
			self.psu_1_ch = None
		
		#Check channel numbering
		if not check_valid_channel(channel):
			print("Invalid Channel")
			return
		
		#Check if already used
		elif self.psu_1_used:
			print("PSU1 Already Used")
			return
		
		#ensure no other equipment is connected to this channel
		elif self.channels[channel] != "none":
			print("Another Device Connected to this channel already")
			return
		
		else:
			#extra check - make sure eload is disconnected from all other channels
			if "psu1" not in self.list_connected_to():
				self.psu_1_used = True
				self.psu_1_ch = channel
				self.channels[channel].set_psu_1()
			else:
				#We should never get here - should be caught above
				print("PSU1 Already Connected")
		
	def set_psu_2_ch(self, channel):
		#Force disconnect all channels
		if channel == None:
			#go through all channels. If a channel is connected then disable the channel
			for ch in self.channels:
				if(ch.connected_to == "psu2"):
					ch.enable_ideal_diodes(False)
			self.psu_2_used = False
			self.psu_2_ch = None
		
		#Check channel numbering
		if not check_valid_channel(channel):
			print("Invalid Channel")
			return
		
		#Check if already used
		elif self.psu_2_used:
			print("PSU2 Already Used")
			return
		
		#ensure no other equipment is connected to this channel
		elif self.channels[channel] != "none":
			print("Another Device Connected to this channel already")
			return
		
		else:
			#extra check - make sure eload is disconnected from all other channels
			if "psu2" not in self.list_connected_to():
				self.psu_2_used = True
				self.psu_2_ch = channel
				self.channels[channel].set_psu_2()
			else:
				#We should never get here - should be caught above
				print("PSU2 Already Connected")
	
	def check_valid_channel(self, channel):
		return channel_min <= channel <= channel_max
		
	def list_connected_to(self):
		connected_list = []
		for ch in self.channels:
			connected_list.append(ch.connected_to)
		return connected_list

	def disable_all_loads(self):
		self.set_eload_ch(None)
		self.set_psu_1_ch(None)
		self.set_psu_2_ch(None)
		
		

class FET_Channel():
	adc_v_ch = ADS1219_MUX.AIN2
	adc_i_ch = ADS1219_MUX.P_AIN0_N_AIN1 #P = AIN0, N = AIN1
	adc_t_ch = ADS1219_MUX.AIN3
	adc_vref = 2.5 #accurate external 2.5V reference - find a way to calibrate and store this value later - read from calibration data file?
	shunt_value = 0.002 #Ohms - also for calibration file
	csa_gain = 200 #V/V - also for calibration file
	top_r = 18700
	bot_r = 2000
	vdiv_gain = (top_r + bot_r) / bot_r
	
	def __init__(self, i2c):
		
		self._i2c = i2c
		
		self.ch_queue_and_event_dict = None
		
		#initialize all devices
		#self._coulomb_counter = LTC2944.LTC2944(self._i2c) #CHANGED
		self._adc = ADS1219(self._i2c, CH_ADC_I2C_ADDR)
		#self._ch_exp = PCA9539(self._i2c, CH_IO_EXP_I2C_ADDR) #CHANGED
		
		#Setup IO Expander
		#CHANGED
		'''
		self.nALCC_pin = 6
		self.nFAULT_0_pin = 0
		self.nFAULT_1_pin = 2
		self.nFAULT_2_pin = 1
		self.EN_pin = 3
		self.A0_pin = 5
		self.A1_pin = 4
		self.NTC_SOURCE_EN_pin = 7
		self.NTC_SINK_EN_pin = 8
		
		self._ch_exp.set_output_val(self.nALCC_pin, 1)
		self._ch_exp.set_output_val(self.nFAULT_0_pin, 1)
		self._ch_exp.set_output_val(self.nFAULT_1_pin, 1)
		self._ch_exp.set_output_val(self.nFAULT_2_pin, 1)
		self._ch_exp.set_output_val(self.EN_pin, 0)
		self._ch_exp.set_output_val(self.A0_pin, 0)
		self._ch_exp.set_output_val(self.A1_pin, 0)
		self._ch_exp.set_output_val(self.NTC_SOURCE_EN_pin, 0)
		self._ch_exp.set_output_val(self.NTC_SINK_EN_pin, 0)

		self._ch_exp.set_pol_inv(self.nALCC_pin, PCA9539.POL_INV_FALSE)
		self._ch_exp.set_pol_inv(self.nFAULT_0_pin, PCA9539.POL_INV_FALSE)
		self._ch_exp.set_pol_inv(self.nFAULT_1_pin, PCA9539.POL_INV_FALSE)
		self._ch_exp.set_pol_inv(self.nFAULT_2_pin, PCA9539.POL_INV_FALSE)
		self._ch_exp.set_pol_inv(self.EN_pin, PCA9539.POL_INV_FALSE)
		self._ch_exp.set_pol_inv(self.A0_pin, PCA9539.POL_INV_FALSE)
		self._ch_exp.set_pol_inv(self.A1_pin, PCA9539.POL_INV_FALSE)
		self._ch_exp.set_pol_inv(self.NTC_SOURCE_EN_pin, PCA9539.POL_INV_FALSE)
		self._ch_exp.set_pol_inv(self.NTC_SINK_EN_pin, PCA9539.POL_INV_FALSE)
		
		self._ch_exp.set_conf_dir(self.nALCC_pin, PCA9539.CONF_INPUT)
		self._ch_exp.set_conf_dir(self.nFAULT_0_pin, PCA9539.CONF_INPUT)
		self._ch_exp.set_conf_dir(self.nFAULT_1_pin, PCA9539.CONF_INPUT)
		self._ch_exp.set_conf_dir(self.nFAULT_2_pin, PCA9539.CONF_INPUT)
		self._ch_exp.set_conf_dir(self.EN_pin, PCA9539.CONF_OUTPUT)
		self._ch_exp.set_conf_dir(self.A0_pin, PCA9539.CONF_OUTPUT)
		self._ch_exp.set_conf_dir(self.A1_pin, PCA9539.CONF_OUTPUT)
		self._ch_exp.set_conf_dir(self.NTC_SOURCE_EN_pin, PCA9539.CONF_OUTPUT)
		self._ch_exp.set_conf_dir(self.NTC_SINK_EN_pin, PCA9539.CONF_OUTPUT)
		'''
		
		#Setup ADC channels
		self._adc.set_channel(FET_Channel.adc_v_ch)
		self._adc.set_conversion_mode(ADS1219_CONV_MODE.CM_SINGLE)
		self._adc.set_gain(ADS1219_GAIN.GAIN_1)
		self._adc.set_data_rate(ADS1219_DATA_RATE.DR_20_SPS)  # 20 SPS is the most accurate
		self._adc.set_vref(ADS1219_VREF.VREF_EXTERNAL)
		
		#Setup coulomb counter
		#CHANGED
		#self._coulomb_counter.RSHUNT = shunt_value
		#self._coulomb_counter.adc_mode = LTC2944.LTC2944_ADCMode.AUTO #Continuous conversions.
		#self._coulomb_counter.prescaler = LTC2944.LTC2944_Prescaler.PRESCALER_1
		
		self.connected_to = "none" #"none", "eload", "psu1", "psu2"
		
	def _get_adc_voltage(self, channel):
		#print("CHANNEL: Reading ADC_MUX: {}".format(bin(channel)))
		self._adc.set_channel(channel)
		code = self._adc.read_data()
		adc_voltage = code * FET_Channel.adc_vref / ADS1219.POSITIVE_CODE_RANGE
		return adc_voltage
		
	def measure_voltage(self):
		#this is a good approximation - need to consider calibration later
		adc_voltage = self._get_adc_voltage(FET_Channel.adc_v_ch)
		voltage = FET_Channel.vdiv_gain * adc_voltage
		return voltage
	
	def measure_current(self):
		#this is a good approximation - need to consider calibration later
		adc_voltage = self._get_adc_voltage(FET_Channel.adc_i_ch)
		current = adc_voltage / FET_Channel.csa_gain / FET_Channel.shunt_value
		return current
		
	def measure_temp(self):
		#need to do some thermistor constants for the pack thermistors
		return 9999
	
	def measure_power(self):
		return self.measure_voltage() * self.measure_current()
	
	def measure_voltage_cc(self):
		return self._coulomb_counter.get_voltage_v()
	
	def measure_current_cc(self):
		return self._coulomb_counter.get_current_a()
		
	def measure_temp_cc(self):
		return self._coulomb_counter.get_temp_c()
	
	def measure_power_cc(self):
		return self.measure_voltage_cc() * self.measure_current_cc
	
	def get_cc(self):
		return self._coulomb_counter.charge

	def set_psu_1(self):
		self.enable_ideal_diodes(False)
		self._ch_exp.set_output_val(self.A0_pin, 0)
		self._ch_exp.set_output_val(self.A1_pin, 0)
		self.enable_ideal_diodes(True)
		self.connected_to = "psu1"
		
	def set_psu_2(self):
		self.enable_ideal_diodes(False)
		self._ch_exp.set_output_val(self.A0_pin, 0)
		self._ch_exp.set_output_val(self.A1_pin, 1)
		self.enable_ideal_diodes(True)
		self.connected_to = "psu2"
		
	def set_eload(self):
		self.enable_ideal_diodes(False)
		self._ch_exp.set_output_val(self.A0_pin, 1)
		self._ch_exp.set_output_val(self.A1_pin, 1)
		self.enable_ideal_diodes(True)
		self.connected_to = "eload"
		
	def enable_ideal_diodes(self, state):
		if(state):
			self._ch_exp.set_output_val(self.EN_pin, 1)
		else:
			self._ch_exp.set_output_val(self.EN_pin, 1)
			self.connected_to = "none"


######################### END OF BOARD CLASSES #########################


def get_gpio_id(mcp):
	value = 0
	for pin in range(3): #only 3 pins used for addressing
		pin_val = mcp.gpio_get_pin(pin)
		value += (2**pin)*pin_val
	return value

def get_mcp_dict():
	addresses = [mcp["path"] for mcp in hid.enumerate(0x04D8, 0x00DD)]
	mcp_devices = {}
	
	gpio_to_name = {0: "Safety Controller",
				1: "FET Board 0",
				2: "FET Board 1",
				3: "FET Board 2",
				4: "FET Board 3"}
	
	#setup mcp devices
	for addr in addresses:
		try:
			mcp_device = MCP2221(addr)
			IO_ID = get_gpio_id(mcp_device)
			ID_NAME = gpio_to_name[IO_ID]
			mcp_devices[ID_NAME] = FET_Board(mcp_device)
		except OSError:
			print("Device path: " + str(addr) + " is used")
	
	return mcp_devices


	
###################### PROGRAM #####################
if __name__ == '__main__':
	addresses = [mcp["path"] for mcp in hid.enumerate(0x04D8, 0x00DD)]
	print("Num Addresses: {}".format(len(addresses)))

	mcp_devices = []
	i2c_devices = []
	expanders = []

	#setup i2c devices
	for addr in addresses:
		try:
			mcp_device = MCP2221(addr)
			i2c_device = I2C(MCP2221I2C(mcp_device))
			
			mcp_devices.append(mcp_device)
			i2c_devices.append(i2c_device)
		except OSError:
			print("Device path: " + str(addr) + " is used")
		expanders.append(PCA9539(i2c_device, CTRL_IO_EXP_I2C_ADDR))

	print("MCP Devices: {}".format(len(mcp_devices)))
	print("I2C Devices: {}".format(len(i2c_devices)))
	print("Expanders: {}\n".format(len(expanders)))

	#Setup control expanders
	for exp in expanders:
		exp.output_ports = 0 #all low
		exp.configuration_ports = 0 #all outputs
		exp.configuration_port_0_pin_0 = 1 #input
	
	gpio_to_name = {0: "Safety Controller",
				1: "FET Board 0",
				2: "FET Board 1",
				3: "FET Board 2",
				4: "FET Board 3"}
	
	#Read MCP GPIO pins
	for mcp in mcp_devices:
		IO_0 = mcp.gpio_get_pin(0)
		IO_1 = mcp.gpio_get_pin(1)
		IO_2 = mcp.gpio_get_pin(2)
		IO_ID = get_gpio_id(mcp)
		ID_NAME = gpio_to_name[IO_ID]
		
		print("Device GPIO: {}{}{}  ID: {}  NAME: {}".format(IO_0, IO_1, IO_2, IO_ID, ID_NAME))

		
	#Lock the I2C bus to the extra IO address
	#this is on the 2nd I2C bus (for now - need to identify based on GPIOs
	tca = adafruit_tca9548a.TCA9548A(i2c_devices[1])
	tca[2].try_lock()
	print("Locked to TCA channel 2")

	#Scan the I2C Busses
	index = 1
	for i2c in i2c_devices:
		print("Scan I2C {}: {}".format(index, [hex(x) for x in i2c.scan()]))
		index += 1

	tca[2].unlock()
	print("Unlocked to TCA channel")

	#Scan the I2C Busses
	index = 1
	for i2c in i2c_devices:
		print("Scan I2C {}: {}".format(index, [hex(x) for x in i2c.scan()]))
		index += 1

	#continuously read devices
	while True:
		inp = []
		for exp in expanders:
			inp.append(exp.input_ports)
			
		print("Device 1: {} \t Device 2: {}".format(inp[0], inp[1]))
		time.sleep(1)
