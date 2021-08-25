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
			#choicebox needs 2 resources, so if we only have 1 device then add another.
			title = "Power Supply Selection"
			if(len(resources) == 0):
				resource_id = 0
				print("No Resources Available. Connection attempt will exit with errors")
			elif(len(resources) == 1):
				msg = "There is only 1 visa resource available.\nWould you like to use it?\n{}".format(resources[0])
				if(eg.ynbox(msg, title)):
					resource_id = resources[0]
				else:
					resource_id = 0
			else:
				msg = "Select a visa resource for the Power Supply:"
				resource_id = eg.choicebox(msg, title, resources)
		
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
		pass
		#only for DP811A
		#if state:
		#	self.inst.write(":OUTP:SENS ON")
		#else:
		#	self.inst.write(":OUTP:SENS OFF")
	
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
