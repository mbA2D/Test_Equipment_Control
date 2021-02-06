#python library for controlling the A2D DAQ

import pyvisa
import time
import easygui

#Data Acquisition Unit
class A2D_DAQ:
	#initialize
	def __init__(self, resource_id = ""):
		self.num_channels = 64
		
		rm = pyvisa.ResourceManager()
		
		if(resource_id == ""):
			resources = rm.list_resources()
			
			########### EASYGUI VERSION #############
			msg = "Select a visa resource for the DAQ:"
			title = "DAQ Selection"
			resource_id = choicebox(msg, title, resources)
			
			########### COMMAND LINE VERSION ########
			#print('{}\n'.format(resources))
			#id_index = input('Select resource list index\n')
			#resource_id = resources[id_index]
		
		self.inst = rm.open_resource(resource_id)
		
		time.sleep(2) #wait for arduino reset
		
		self.inst.baud_rate = 57600
		self.inst.read_termination = '\n'
		self.inst.write_termination = '\n'
		
		print('Connected to:\n{name}'.format(name = self.inst.query('*IDN?')))
	
	def __del__(self):
		self.inst.close()
	
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
		self.inst.write('INSTR:DAQ:SET:OUTP (@{ch}),{val}'.format(ch = channel, val = value))
		
if __name__ == "__main__":
	#connect to the daq
	daq = A2D_DAQ()