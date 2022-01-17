#python pyvisa commands for controlling Rigol DL3000 series eloads

import pyvisa
import time
import easygui as eg
import serial

# E-Load
class DL3000:
	
	has_remote_sense = True
	
	# Initialize the DL3000 E-Load
	def __init__(self, resource_id = None):
		rm = pyvisa.ResourceManager()
		
		if(resource_id == None):
			resources = rm.list_resources()
			
			################# IDN VERSION #################
			#Attempt to connect to each Visa Resource and get the IDN response
			title = "Eload Selection"
			if(len(resources) == 0):
				resource_id = 0
				print("No PyVisa Resources Available. Connection attempt will exit with errors")
			idns_dict = {}
			for resource in resources:
				try:
					instrument = rm.open_resource(resource)
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
				msg = "Select the Eload Model:"
				idn = eg.choicebox(msg, title, idns_dict.values())
			#Now we know which IDN we want to connect to
			#swap keys and values and then connect
			if idn != None:
				resources_dict = dict((v,k) for k,v in idns_dict.items())
				resource_id = resources_dict[idn]
		
		#values specific to the DL3000 - will break out to another file later
		self.ranges = {"low":4,"high":40}
		self.range = "low"
		
		self.inst = rm.open_resource(resource_id)
		print("Connected to {}\n".format(self.inst.query("*IDN?")))
		self.inst.write("*RST")
		self.set_mode_current()
		self.set_current(0)
				
		#set to remote mode (disable front panel)
		#self.lock_front_panel(True)
		
	# To Set E-Load in Amps 
	def set_current(self, current_setpoint_A):		
		if current_setpoint_A < 0:
			current_setpoint_A = -current_setpoint_A
		
		#4A range
		if(current_setpoint_A <= self.ranges["low"]):
			if(self.range != "low"):
				self.set_range("low")
		
		#40A range
		elif(current_setpoint_A <= self.ranges["high"]):
			if(self.range != "high"):
				self.set_range("high")
		
		self.inst.write(":CURR:LEV {}".format(current_setpoint_A))

	def set_range(self, set_range):
		#set_range is either "high" or "low"
		write_range = "MIN"
		if(set_range == "high"):
			write_range = "MAX"
		self.inst.write(":CURR:RANG {}".format(write_range))
		self.range = set_range
		
	def set_mode_current(self):
		self.inst.write(":FUNC CURR")

	def toggle_output(self, state):
		if state:
			self.inst.write(":INP ON")
		else:
			self.inst.write(":INP OFF")
	
	def remote_sense(self, state):
		if state:
			self.inst.write(":SENS ON")
		else:
			self.inst.write(":SENS OFF")
	
	def lock_front_panel(self, state):
		pass
	#	if state:
	#		self.inst.write("SYST:REM")
	#	else:
	#		self.inst.write("SYST:LOC")
	
	def measure_voltage(self):
		return float(self.inst.query(":MEAS:VOLT:DC?"))

	def measure_current(self):
		return (float(self.inst.query(":MEAS:CURR:DC?")) * (-1))

	def __del__(self):
		try:
			self.toggle_output(False)
			#self.lock_front_panel(False)
			self.inst.close()
		except (AttributeError, pyvisa.errors.InvalidSession):
			pass
