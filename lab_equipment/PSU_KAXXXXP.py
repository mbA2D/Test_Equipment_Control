#python pyvisa commands for controlling Korad KAXXXXP series power supplies
#Korad 3010P
#Korad 3005P
#etc.

import pyvisa
import time
import easygui as eg
import serial

# Power Supply
class KAXXXXP:
	# Initialize the Korad KAXXXXP Power Supply
	
	baud_rate = 9600
	query_delay = 0.01
	
	def __init__(self, resource_id = ""):
		rm = pyvisa.ResourceManager('@py')
		
		if(resource_id == ""):
			resources = rm.list_resources()
			
			################# IDN VERSION #################
			#Attempt to connect to each Visa Resource and get the IDN response
			title = "Power Supply Selection"
			if(len(resources) == 0):
				resource_id = 0
				print("No PyVisa Resources Available. Connection attempt will exit with errors")
			idns_dict = {}
			for resource in resources:
				try:
					instrument = rm.open_resource(resource)
					instrument.baud_rate = KAXXXXP.baud_rate
					instrument.query_delay = KAXXXXP.query_delay
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
				msg = "Select the Power Supply Model:"
				idn = eg.choicebox(msg, title, idns_dict.values())
			#Now we know which IDN we want to connect to
			#swap keys and values and then connect
			resources_dict = dict((v,k) for k,v in idns_dict.items())
			resource_id = resources_dict[idn]
		
		self.inst = rm.open_resource(resource_id)
		
		self.inst.baud_rate = KAXXXXP.baud_rate
		self.inst.query_delay = KAXXXXP.query_delay
        
		print("Connected to {}\n".format(self.inst.query("*IDN?")))
		#this unit does not have a reset command
		#self.inst.write("*RST")
		time.sleep(0.1)
		
		self.lock_commands(False)
		time.sleep(0.01)
		self.toggle_output(0)
		time.sleep(0.01)
		self.set_current(0)
		time.sleep(0.01)
		self.set_voltage(0)
		time.sleep(0.01)
    
	# To set power supply limit in Amps 
	def set_current(self, current_setpoint_A):		
		self.inst.write("ISET1:{}".format(current_setpoint_A))

	def set_voltage(self, voltage_setpoint_V):
		self.inst.write("VSET1:{}".format(voltage_setpoint_V))

	def toggle_output(self, state, ch = 1):
		if state:
			self.inst.write("OUT1")
		else:
			self.inst.write("OUT0")
	
	def remote_sense(self, state):
		#these units do not have remote sense
		pass
	
	def lock_commands(self, state):
		#these units auto-lock front panel when USB connected
		pass
	
	def measure_voltage(self):
		return float(self.inst.query("VOUT1?"))

	def measure_current(self):
		return float(self.inst.query("IOUT1?"))
		
	def measure_power(self):
		current = self.measure_current()
		voltage = self.measure_voltage()
		return float(current*voltage)
		
	def __del__(self):
		self.toggle_output(False)
		self.lock_commands(False)
		try:
			self.inst.close()
		except AttributeError:
			pass
