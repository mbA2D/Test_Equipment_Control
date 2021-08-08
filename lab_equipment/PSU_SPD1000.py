#python pyvisa commands for controlling Siglent SPD1000 series power supplies

import pyvisa
import time
import easygui as eg

# Power Supply
class SPD1000:
	# Initialize the SPD1000 Power Supply
	def __init__(self, resource_id = ""):
		rm = pyvisa.ResourceManager('@ivi')
		
		if(resource_id == ""):
			resources = rm.list_resources('@ivi')
			
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
		self.inst.read_termination = '\n'
		self.inst.write_termination = '\n'
		self.inst.query_delay = 0.1
		
		print("Connected to %s\n" % self.inst.query("*IDN?"))
		self.inst.write("*RST")
		time.sleep(0.1)
		
		#Choose channel 1
		self.inst.write("INST CH1")
		time.sleep(0.1)
		self.lock_commands(False)
		time.sleep(0.1)
		self.set_current(0)
		time.sleep(0.1)
		self.set_voltage(0)
		time.sleep(0.1)
		
	# To Set power supply current limit in Amps 
	def set_current(self, current_setpoint_A):		
		self.inst.write("CURR {}".format(current_setpoint_A))

	def set_voltage(self, voltage_setpoint_V):
		self.inst.write("VOLT {}".format(voltage_setpoint_V))

	def toggle_output(self, state, ch = 1):
		if state:
			self.inst.write("OUTP CH{},ON".format(ch))
		else:
			self.inst.write("OUTP CH{},OFF".format(ch))
	
	def remote_sense(self, state):
		if state:
			self.inst.write("MODE:SET 4W")
		else:
			self.inst.write("MODE:SET 2W")
	
	def lock_commands(self, state):
		if state:
			self.inst.write("*LOCK")
		else:
			self.inst.write("*UNLOCK")
	
	def measure_voltage(self):
		return float(self.inst.query("MEAS:VOLT?"))

	def measure_current(self):
		return float(self.inst.query("MEAS:CURR?"))
		
	def measure_power(self):
		return float(self.inst.query("MEAS:POWE?"))
		
	def __del__(self):
		self.toggle_output(False)
		self.lock_commands(False)
		try:
			self.inst.close()
		except AttributeError:
			pass
