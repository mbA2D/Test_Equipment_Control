#python pyvisa commands for controlling Multicomp Pro MP71025X series power supplies
#MP710256 - 30V 30A 300W
#MP710257 - 60V 15A 300W

import pyvisa
import time
import easygui as eg

# Power Supply
class MP71025X:
	# Initialize the MP71025X Power Supply (X is 6 or 7)
	def __init__(self, resource_id = ""):
		rm = pyvisa.ResourceManager('@py')
		
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
		#this unit does not have a reset command
		#self.inst.write("*RST")
		time.sleep(0.1)
		
		self.inst.baud_rate = 115200
		self.inst.read_termination = '\n'
		self.inst.query_delay = 0.1
		
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
		self.inst.write("ISET:{}".format(current_setpoint_A))

	def set_voltage(self, voltage_setpoint_V):
		self.inst.write("VSET:{}".format(voltage_setpoint_V))

	def toggle_output(self, state, ch = 1):
		if state:
			self.inst.write("OUT:1")
		else:
			self.inst.write("OUT:0")
	
	def remote_sense(self, state):
		if state:
			self.inst.write("COMP:1")
		else:
			self.inst.write("COMP:0")
	
	def lock_commands(self, state):
		if state:
			self.inst.write("LOCK:1")
		else:
			self.inst.write("LOCK:0")
	
	def measure_voltage(self):
		return float(self.inst.query("VOUT?"))

	def measure_current(self):
		return float(self.inst.query("IOUT?"))
		
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
