#python library for controlling the A2D DAQ

import pyvisa
from time import sleep
import easygui as eg
import voltage_to_temp as V2T
from . import A2D_DAQ_config

#Data Acquisition Unit
class A2D_DAQ:
	num_channels = 64
	read_termination = '\r\n'
	write_termination = '\n'
	baud_rate = 57600
	query_delay = 0.02
	chunk_size = 102400
	
	#initialize
	def __init__(self, resource_id = None):
		rm = pyvisa.ResourceManager('@py')
		
		self.pull_up_r = 3300
		self.pullup_voltage = 3.3
		self.pull_up_cal_ch = 63
		
		self.config_dict = {}
		
		if(resource_id == None):
			resources = rm.list_resources()

			################# IDN VERSION #################
			#Attempt to connect to each Visa Resource and get the IDN response
			title = "DMM Selection"
			if(len(resources) == 0):
				resource_id = 0
				print("No PyVisa Resources Available. Connection attempt will exit with errors")
			idns_dict = {}
			for resource in resources:
				try:
					instrument = rm.open_resource(resource)
					instrument.read_termination = A2D_DAQ.read_termination
					instrument.write_termination = A2D_DAQ.write_termination
					instrument.baud_rate = A2D_DAQ.baud_rate
					instrument.query_delay = A2D_DAQ.query_delay
					instrument.chunk_size = A2D_DAQ.chunk_size
					sleep(2) #wait for arduino reset - this could make it take a while. Maybe there's a better way?
					instrument_idn = instrument.query("*IDN?")
					idns_dict[resource] = instrument_idn
					instrument.close()
				except (pyvisa.errors.VisaIOError, PermissionError, serial.serialutil.SerialException):
					pass
					
			#Now we have all the available resources that we can connect to, with their IDNs.
			resource_id = 0
			if(len(idns_dict.values()) == 0):
				print("No Equipment Available. Connection attempt will exit with errors")
			elif(len(idns_dict.values()) == 1):
				msg = "There is only 1 Visa Equipment available.\nWould you like to use it?\n{}".format(list(idns_dict.values())[0])
				if(eg.ynbox(msg, title)):
					idn = list(idns_dict.values())[0]
			else:
				msg = "Select the DMM Supply Model:"
				idn = eg.choicebox(msg, title, idns_dict.values())
			#Now we know which IDN we want to connect to
			#swap keys and values and then connect
			resources_dict = dict((v,k) for k,v in idns_dict.items())
			resource_id = resources_dict[idn]
		
		self.inst = rm.open_resource(resource_id)
		
		sleep(2) #wait for arduino reset
		
		#pyvisa configuration
		self.inst.baud_rate = self.baud_rate
		self.inst.read_termination = self.read_termination
		self.inst.write_termination = self.write_termination
		self.inst.query_delay = self.query_delay
		self.inst.chunk_size = self.chunk_size
		
		print('Connected to:\n{name}'.format(name = self.inst.query('*IDN?')))
		
		self.config_dict = A2D_DAQ_config.get_config_dict(default = True)
		
		msg = "Do you want to use a non-default config dict"
		title = "A2D DAQ Configuration"
		if eg.ynbox(msg, title):
			self.config_dict.update(A2D_DAQ_config.get_config_dict())
		self.configure_from_dict()
		
	def __del__(self):
		try:
			self.inst.close()
		except AttributeError:
			pass
	
	def configure_from_dict(self):
		#Go through each channel and set it up according to the dict
		for ch in list(self.config_dict.keys()):
			if self.config_dict[ch]['Input_Type'] == 'voltage':
				self.conf_io(ch, 0) #input
			elif self.config_dict[ch]['Input_Type'] == 'temperature':
				self.conf_io(ch, 1) #output
				self.set_dig(ch, 1) #pull high
	
	def reset(self):
		self.inst.write('*RST')
		
	def conf_io(self, channel = 0, dir = 1):
		#1 means output - pin is being driven
		if dir:
			self.inst.write('CONF:DAQ:OUTP (@{ch})'.format(ch = channel))
		#0 means input - pin high impedance
		elif not dir:
			self.inst.write('CONF:DAQ:INP (@{ch})'.format(ch = channel))
	
	def get_pullup_v(self):
		return self.pullup_voltage
	
	def calibrate_pullup_v(self, cal_ch = None):
		if cal_ch == None:
			cal_ch = self.pull_up_cal_ch
	
		#choose a channel to read from - this channel should have nothing on it
		if cal_ch < self.num_channels:
			#ensure channel is set to output and pullued high
			self.conf_io(channel = cal_ch, dir = 1)
			self.set_dig(channel = cal_ch, value = 1)
			
			self.pullup_voltage = float(self.measure_voltage(channel = cal_ch))
	
	def get_analog_mv(self, channel = 0):
		scaling = 1
		if self.config_dict[channel]['Input_Type'] == 'voltage':
			scaling = self.config_dict[channel]['Voltage_Scaling']
		return float(self.inst.query('INSTR:READ:ANA? (@{ch})'.format(ch = channel)))*scaling
	
	def get_analog_v(self, channel = 0):
		return float(self.get_analog_mv(channel))/1000.0
	
	def measure_voltage(self, channel = 0):
		return float(self.get_analog_v(channel))
	
	def measure_temperature(self, channel = 0):
		sh_consts = {'SH_A': self.config_dict[channel]['Temp_A'],
					 'SH_B': self.config_dict[channel]['Temp_B'],
					 'SH_C': self.config_dict[channel]['Temp_C']}
		return V2T.voltage_to_C(self.measure_voltage(channel), self.pull_up_r, self.pullup_voltage, sh_constants = sh_consts)
	
	def get_dig_in(self, channel = 0):
		return self.inst.query('INSTR:READ:DIG? (@{ch})'.format(ch = channel))
		
	def set_dig(self, channel = 0, value = 0):
		if(value > 1):
			value = 1
		self.inst.write('INSTR:DAQ:SET:OUTP (@{ch}),{val}'.format(ch = channel, val = value))
		
	def set_led(self, value = 0):
		if(value > 1):
			value = 1
		#x is a character that we parse but do nothing with (channel must be first)
		self.inst.write('INSTR:DAQ:SET:LED x {val}'.format(val = value))
		
	def set_read_delay_ms(self, delay_ms):
		#x is a character that we parse but do nothing with (channel must be first)
		self.inst.write('CONF:DAQ:READDEL x {val}'.format(val = delay_ms))
	
if __name__ == "__main__":
	#connect to the daq
	daq = A2D_DAQ()
