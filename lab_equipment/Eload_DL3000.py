#python pyvisa commands for controlling Rigol DL3000 series eloads

import pyvisa
import time
import easygui as eg

# E-Load
class DL3000:
	# Initialize the DL3000 E-Load
	def __init__(self, resource_id = ""):
		rm = pyvisa.ResourceManager('@ivi')
		
		if(resource_id == ""):
			resources = rm.list_resources()
			
			########### EASYGUI VERSION #############
			msg = "Select a visa resource for the E-Load:"
			title = "E-Load Selection"
			resource_id = eg.choicebox(msg, title, resources)
			
			########### COMMAND LINE VERSION ########
			#print('{}\n'.format(resources))
			#id_index = int(input('Select resource list index\n'))
			#resource_id = resources[id_index]
		
		#values specific to the DL3000 - will break out to another file later
		self.ranges = {"low":4,"high":40}
		self.range = "low"
		
		self.inst = rm.open_resource(resource_id)
		print("Connected to %s\n" % self.inst.query("*IDN?"))
		self.inst.write("*RST")
		self.set_mode_current()
		self.set_current(0)
				
		#set to remote mode (disable front panel)
		#self.lock_front_panel(True)
		
	# To Set E-Load in Amps 
	def set_current(self, current_setpoint_A):		
		#4A range
		if(current_setpoint_A <= self.ranges["low"]):
			if(self.range != "low"):
				self.set_range("low")
		
		#40A range
		elif(current_setpoint_A <= self.ranges["high"]):
			if(self.range != "high"):
				self.set_range("high")
		
		self.inst.write(":CURR:LEV %s" % current_setpoint_A)

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
		return float(self.inst.query(":MEAS:CURR:DC?"))

	def __del__(self):
		self.toggle_output(False)
		#self.lock_front_panel(False)
		try:
			self.inst.close()
		except AttributeError:
			pass
