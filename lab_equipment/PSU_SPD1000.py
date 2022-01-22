#python pyvisa commands for controlling Siglent SPD1000 series power supplies

import pyvisa
import time
import easygui as eg
import serial

# Power Supply
class SPD1000:
	# Initialize the SPD1000 Power Supply
	
	read_termination = '\n'
	write_termination = '\n'
	query_delay = 0.05
	has_remote_sense = True
	
	def __init__(self, resource_id = None):
		rm = pyvisa.ResourceManager()
		
		if(resource_id == None):
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
					instrument.read_termination = self.read_termination
					instrument.write_termination = self.write_termination
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
				msg = "Select the Power Supply Model:"
				idn = eg.choicebox(msg, title, idns_dict.values())
			#Now we know which IDN we want to connect to
			#swap keys and values and then connect
			if idn != None:
				resources_dict = dict((v,k) for k,v in idns_dict.items())
				resource_id = resources_dict[idn]
		
		self.inst = rm.open_resource(resource_id)
		self.inst.read_termination = self.read_termination
		self.inst.write_termination = self.write_termination
		self.inst.query_delay = self.query_delay
		
		print("Connected to {}\n".format(self.inst.query("*IDN?")))
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
		try:
			self.toggle_output(False)
			self.lock_commands(False)
			self.inst.close()
		except (AttributeError, pyvisa.errors.InvalidSession):
			pass
