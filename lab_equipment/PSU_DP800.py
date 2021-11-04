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
					instrument_idn = instrument.query("*IDN?")
					idns_dict[resource] = instrument_idn
					instrument.close()
				except pyvisa.errors.VisaIOError:
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
			resources_dict = dict((v,k) for k,v in idns_dict.items())
			resource_id = resources_dict[idn]
		
		self.inst = rm.open_resource(resource_id)
		
		print("Connected to {}\n".format(self.inst.query("*IDN?")))
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
