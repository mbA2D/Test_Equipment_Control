#python pyvisa commands for controlling Korad KEL10X series eloads
#Links helpful for finding commands: https://lygte-info.dk/project/TestControllerIntro

import pyvisa
import time
import easygui as eg

# E-Load
class KEL10X:
	# Initialize the KEL10X E-Load
	def __init__(self, resource_id = ""):
		rm = pyvisa.ResourceManager()
		
		if(resource_id == ""):
			resources = rm.list_resources()
			
			########### EASYGUI VERSION #############
			#choicebox needs 2 resources, so if we only have 1 device then add another.
			title = "Eload Selection"
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
				msg = "Select a visa resource for the Eload:"
				resource_id = eg.choicebox(msg, title, resources)
		
		self.inst = rm.open_resource(resource_id)
        
        self.inst.baud_rate = 115200
		self.inst.read_termination = '\n'
		self.inst.query_delay = 0.1
        
		print("Connected to %s\n" % self.inst.query("*IDN?"))
		#unit does not have reset command
        #self.inst.write("*RST")
		self.set_mode_current()
		self.set_current(0)
				
		#set to remote mode (disable front panel)
		self.lock_front_panel(True)
		
	# To Set E-Load in Amps 
	def set_current(self, current_setpoint_A):		
		self.inst.write(":CURR {}A" % current_setpoint_A)
		
	def set_mode_current(self):
		self.inst.write(":FUNC CC")

	def toggle_output(self, state):
		if state:
			self.inst.write(":INP 1")
		else:
			self.inst.write(":INP 0")
	
	def remote_sense(self, state):
		if state:
			self.inst.write(":SYST:COMP 1")
		else:
			self.inst.write(":SYST:COMP 0")
	
	def lock_front_panel(self, state):
		pass
		if state:
			self.inst.write("SYST:LOCK 1")
		else:
			self.inst.write("SYST:LOCK 0")
	
	def measure_voltage(self):
		return float(self.inst.query(":MEAS:VOLT?").strip('V\n'))

	def measure_current(self):
		return float(self.inst.query(":MEAS:CURR?").strip('A\n'))
    
    def measure_power(self):
        return float(self.inst.query(":MEAS:POW?").strip('W\n'))
    
	def __del__(self):
		self.toggle_output(False)
		self.lock_front_panel(False)
		try:
			self.inst.close()
		except AttributeError:
			pass
