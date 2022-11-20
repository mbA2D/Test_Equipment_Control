#python pyvisa commands for controlling Korad KEL10X series eloads
#Links helpful for finding commands: https://lygte-info.dk/project/TestControllerIntro

import pyvisa
import time
import easygui as eg
import serial

# E-Load
class KEL10X:
	# Initialize the KEL10X E-Load
	
	baud_rate = 115200
	read_termination = '\n'
	query_delay = 0.05
	has_remote_sense = True
	
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
					instrument.baud_rate = self.baud_rate
					instrument.read_termination = self.read_termination
					instrument.query_delay = self.query_delay
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
		
		self.inst = rm.open_resource(resource_id)
        
		self.inst.baud_rate = self.baud_rate
		self.inst.read_termination = self.read_termination
		self.inst.query_delay = self.query_delay
        
		self.instrument_idn = self.inst.query("*IDN?")
		print("Connected to {}\n".format(self.instrument_idn))
		
		split_string = self.instrument_idn.split(" ")
		self.model_number = split_string[0]
		self.version_number = split_string[1]
		self.serial_number = split_string[2]
		
		if 'KEL103' in self.model_number:
			self.max_current = 30
			self.max_power = 300
		elif 'KEL102' in self.model_number:
			self.max_current = 30
			self.max_power = 150
		
		self.mode = "CURR"
		
		#unit does not have reset command
        #self.inst.write("*RST")
		self.set_mode_current()
		self.set_current(0)
				
		#set to remote mode (disable front panel)
		self.lock_front_panel(True)
		
	# To Set E-Load in Amps 
	def set_current(self, current_setpoint_A):	
		if self.mode != "CURR":
			print("ERROR - E-load not in correct mode")
			return
		if current_setpoint_A < 0:
			current_setpoint_A = -current_setpoint_A
		self.inst.write(":CURR {}A".format(current_setpoint_A))
		
	def set_mode_current(self):
		self.inst.write(":FUNC CC")
		self.mode = "CURR"

	##COMMANDS FOR CV MODE
	def set_mode_voltage(self):
		self.inst.write(":FUNC CV")
		self.mode = "VOLT"
	
	def set_cv_voltage(self, voltage_setpoint_V):
		if self.mode != "VOLT":
			print("ERROR - E-load not in correct mode")
			return
		self.inst.write(":VOLT {}".format(voltage_setpoint_V))
	
	##END OF COMMANDS FOR CV MODE
	
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
			self.inst.write(":SYST:LOCK 1")
		else:
			self.inst.write(":SYST:LOCK 0")
	
	def measure_voltage(self):
		return float(self.inst.query(":MEAS:VOLT?").strip('V\n'))

	def measure_current(self):
		return (float(self.inst.query(":MEAS:CURR?").strip('A\n')) * (-1))
	
	def measure_power(self):
		return float(self.inst.query(":MEAS:POW?").strip('W\n'))
	
	def __del__(self):
		try:
			self.toggle_output(False)
			self.lock_front_panel(False)
			self.inst.close()
		except (AttributeError, pyvisa.errors.InvalidSession):
			pass
