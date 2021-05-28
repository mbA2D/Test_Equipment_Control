#python pyvisa commands for controlling Siglent SPD1000 series power supplies

import pyvisa
import time
import easygui as eg

# Power Supply
class DP800:
	# Initialize the DP800 Power Supply
	def __init__(self, resource_id = ""):
		rm = pyvisa.ResourceManager('@ivi')
		
		if(resource_id == ""):
			resources = rm.list_resources()
			
			########### EASYGUI VERSION #############
			msg = "Select a visa resource for the Power Supply:"
			title = "Power Supply Selection"
			resource_id = eg.choicebox(msg, title, resources)
			
			########### COMMAND LINE VERSION ########
			#print('{}\n'.format(resources))
			#id_index = int(input('Select resource list index\n'))
			#resource_id = resources[id_index]
		
		self.inst = rm.open_resource(resource_id)
		
		print("Connected to %s\n" % self.inst.query("*IDN?"))
		self.inst.write("*RST")
		
		#Choose channel 1 by default
		self.select_channel(1)
		
		self.lock_front_panel(True)
		self.set_current(0)
		self.set_voltage(0)
		
	def select_channel(self, channel):
		#channel is a number - 1,2,3
		if(channel <= 3) and (channel >= 0):
			self.inst.write(":INST:NSEL {}".format(channel))
	
	def set_current(self, current_setpoint_A):		
		self.inst.write(":CURR {}".format(current_setpoint_A))

	def set_voltage(self, voltage_setpoint_V):
		self.inst.write(":VOLT {}".format(voltage_setpoint_V))

	def toggle_output(self, state):
		if state:
			self.inst.write(":OUTP ON")
		else:
			self.inst.write(":OUTP OFF")
	
	def remote_sense(self, state):
		if state:
			self.inst.write(":OUTP:SENS ON")
		else:
			self.inst.write(":OUTP:SENS OFF")
	
	def lock_front_panel(self, state):
		if state:
			self.inst.write(":SYST:REM")
		else:
			self.inst.write(":SYST:LOC")
	
	def measure_voltage(self):
		return float(self.inst.query(":MEAS:VOLT?"))

	def measure_current(self):
		return float(self.inst.query(":MEAS:CURR?"))
		
	def measure_power(self):
		return float(self.inst.query(":MEAS:POWE?"))
		
	def __del__(self):
		for ch in range(3):
			self.select_channel(ch+1)
			self.toggle_output(False)
			self.lock_front_panel(False)
		try:
			self.inst.close()
		except AttributeError:
			pass
