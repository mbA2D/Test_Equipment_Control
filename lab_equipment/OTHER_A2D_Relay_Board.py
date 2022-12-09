#python library for controlling the A2D DAQ

import pyvisa
from time import sleep
import easygui as eg
import serial

#Data Acquisition Unit
class A2D_Relay_Board:
	read_termination = '\r\n'
	write_termination = '\n'
	baud_rate = 57600
	query_delay = 0.02
	chunk_size = 102400
	
	#initialize
	def __init__(self, resource_id = None):
		rm = pyvisa.ResourceManager('@py')
		
		self.num_channels = None
		self.equipment_type_connected = None
			
		self.eload_connected = False
		self.psu_connected = False
		
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
		
		if resource_id != None:
			self.inst = rm.open_resource(resource_id)
			
			sleep(2) #wait for arduino reset
			
			#pyvisa configuration
			self.inst.baud_rate = self.baud_rate
			self.inst.read_termination = self.read_termination
			self.inst.write_termination = self.write_termination
			self.inst.query_delay = self.query_delay
			self.inst.chunk_size = self.chunk_size
			
			print('Connected to: {name}'.format(name = self.inst.query('*IDN?')))
			
		
	def __del__(self):
		try:
			self.inst.close()
		except AttributeError:
			pass
	
	def connect_psu(self, state):
		value = 0
		if state:
			value = 1
		
		if self.equipment_type_connected[0] == 'psu':
			psu_channel = 0
		elif self.equipment_type_connected[1] == 'psu':
			psu_channel = 1
		
		self.inst.write('INSTR:DAQ:SET:OUTP (@{ch}),{val}'.format(ch = psu_channel, val = value))
		
		self.psu_connected = state
	
	def psu_connected(self):
		return self.psu_connected
		
	def connect_eload(self, state):
		value = 0
		if state:
			value = 1
		
		if self.equipment_type_connected[0] == 'eload':
			eload_channel = 0
		elif self.equipment_type_connected[1] == 'eload':
			eload_channel = 1
		
		self.inst.write('INSTR:DAQ:SET:OUTP (@{ch}),{val}'.format(ch = eload_channel, val = value))
	
		self.eload_connected = state
	
	def eload_connected(self):
		return self.eload_connected
	
	def reset(self):
		self.inst.write('*RST')

	def set_led(self, value = 0):
		if(value > 1):
			value = 1
		#x is a character that we parse but do nothing with (channel must be first)
		self.inst.write('INSTR:DAQ:SET:LED x {val}'.format(val = value))
	
if __name__ == "__main__":
	#connect to the daq
	daq = A2D_DAQ()
