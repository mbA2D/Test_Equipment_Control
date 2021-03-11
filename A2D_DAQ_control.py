#python library for controlling the A2D DAQ

import pyvisa
from time import sleep
import easygui as eg

#Data Acquisition Unit
class A2D_DAQ:
	#initialize
	def __init__(self, resource_id = ""):
		self.num_channels = 64
		
		rm = pyvisa.ResourceManager('@py')
		
		if(resource_id == ""):
			resources = list(rm.list_resources()) #RM returns a tuple so cast to a list to append
		
			########### EASYGUI VERSION #############
			#choicebox needs 2 resources, so if we only have 1 device then add another.
			title = "DAQ Selection"
			if(len(resources) == 0):
				resource_id = 0
			elif(len(resources) == 1):
				msg = "There is only 1 visa resource available.\nWould you like to use it?\n{}".format(resources[0])
				if(eg.ynbox(msg, title)):
					resource_id = resources[0]
				else:
					resource_id = 0
			else:
				msg = "Select a visa resource for the DAQ:"
				resource_id = eg.choicebox(msg, title, resources)
		
		self.inst = rm.open_resource(resource_id)
		
		sleep(2) #wait for arduino reset
		
		self.inst.baud_rate = 57600
		self.inst.read_termination = '\r\n'
		self.inst.write_termination = '\n'
		self.inst.query_delay = 0.02
		self.inst.chunk_size = 102400
		
		print('Connected to:\n{name}'.format(name = self.inst.query('*IDN?')))
	
	def __del__(self):
		try:
			self.inst.close()
		except AttributeError:
			pass
	
	def reset(self):
		self.inst.write('*RST')
		
	def conf_io(self, channel = 0, dir = 1):
		#1 means output - pin is being driven
		if dir:
			self.inst.write('CONF:DAQ:OUTP (@{ch})'.format(ch = channel))
		#0 means input - pin high impedance
		elif not dir:
			self.inst.write('CONF:DAQ:INP (@{ch})'.format(ch = channel))
	
	def get_analog_mv(self, channel = 0):
		return self.inst.query('INSTR:READ:ANA? (@{ch})'.format(ch = channel))
	
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
		
if __name__ == "__main__":
	#connect to the daq
	daq = A2D_DAQ()