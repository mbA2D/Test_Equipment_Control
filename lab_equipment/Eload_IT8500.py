#python pyvisa commands for controlling Itech IT8500 series eloads

import pyvisa
import time
import easygui as eg
import serial

# E-Load
class IT8500:
	# Initialize the IT8500 E-Load
	
	baud_rate = 115200
	write_termination = '\n'
	read_termination = '\n'
	
	def __init__(self, resource_id = None):
		rm = pyvisa.ResourceManager('@py')
		
		if(resource_id == None):
			resources = rm.list_resources()
			
			################# IDN VERSION #################
			#Attempt to connect to each Visa Resource and get the IDN response
			title = "Eload Selection"
			if(len(resources) == 0):
				resource_id = None
				print("No PyVisa Resources Available. Connection attempt will exit with errors")
			idns_dict = {}
			for resource in resources:
				try:
					instrument = rm.open_resource(resource)
					instrument.baud_rate = IT8500.baud_rate
					instrument.read_termination = IT8500.read_termination
					instrument.write_termination = IT8500.write_termination
					instrument_idn = instrument.query("*IDN?")
					idns_dict[resource] = instrument_idn
					instrument.close()
				except (pyvisa.errors.VisaIOError, PermissionError, serial.serialutil.SerialException):
					pass
					
			#Now we have all the available resources that we can connect to, with their IDNs.
			resource_id = None
			idn = None
			if(len(idns_dict.values()) == 0):
				print("No Equipment Available. Connection attempt will exit with errors")
			elif(len(idns_dict.values()) == 1):
				msg = "There is only 1 Visa Equipment available.\nWould you like to use it?\n{}".format(list(idns_dict.values())[0])
				if(eg.ynbox(msg, title)):
					idn = list(idns_dict.values())[0]
			else:
				msg = "Select the Eload Model:"
				idn = eg.choicebox(msg, title, idns_dict.values())
			#Now we know which IDN we want to connect to
			#swap keys and values and then connect
			if idn != None:
				resources_dict = dict((v,k) for k,v in idns_dict.items())
				resource_id = resources_dict[idn]
		
		
		self.inst = rm.open_resource(resource_id)
		
		self.inst.baud_rate = IT8500.baud_rate
		self.inst.read_termination = IT8500.read_termination
		self.inst.write_termination = IT8500.write_termination
		
		print("Connected to {}\n".format(self.inst.query("*IDN?")))
		#resets to Constant Current Mode
		self.inst.write("*RST")
		self.set_current(0)
		#set to remote mode (disable front panel)
		self.lock_front_panel(True)
		
	# To Set E-Load in Amps 
	def set_current(self, current_setpoint_A):
		if current_setpoint_A < 0:
			current_setpoint_A = -current_setpoint_A
		self.inst.write("CURR {}".format(current_setpoint_A))

	def toggle_output(self, state):
		if state:
			self.inst.write("INP ON")
		else:
			self.inst.write("INP OFF")
	
	def remote_sense(self, state):
		if state:
			self.inst.write("SYST:SENS ON")
		else:
			self.inst.write("SYST:SENS OFF")
	
	def lock_front_panel(self, state):
		if state:
			self.inst.write("SYST:REM")
		else:
			self.inst.write("SYST:LOC")
	
	def measure_voltage(self):
		return float(self.inst.query("MEAS:VOLT:DC?"))

	def measure_current(self):
		return (float(self.inst.query("MEAS:CURR:DC?")) * (-1))
		
	def __del__(self):
		self.toggle_output(False)
		self.lock_front_panel(False)
		try:
			self.inst.close()
		except AttributeError:
			pass