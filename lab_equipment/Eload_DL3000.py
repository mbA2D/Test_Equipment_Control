#python pyvisa commands for controlling Rigol DL3000 series eloads

import pyvisa
import time
from .PyVisaDeviceTemplate import EloadDevice

# E-Load
class DL3000(EloadDevice):
	
	has_remote_sense = True
	pyvisa_backend = '@ivi'
	
	# Initialize the DL3000 E-Load
	def initialize(self):
		idn_split = self.inst_idn.split(',')
		model_number = idn_split[1]
		self.inst.write("*RST")
		
		if 'DL3021' in model_number:
			#values specific to the DL3021 & DL3021A
			self.ranges = {"low":4,"high":40}
			self.max_current = 40
			self.max_power = 200
		elif 'DL3031' in model_number:
			self.ranges = {"low":6,"high":60}
			self.max_current = 60
			self.max_power = 350
			
		self.range = "low"
		self.mode = "CURR"
		self.set_mode_current()
		self.set_current(0)
		self.set_range("high")
				
		#set to remote mode (disable front panel)
		#self.lock_front_panel(True)
		
	# To Set E-Load in Amps 
	def set_current(self, current_setpoint_A):		
		if self.mode != "CURR":
			print("ERROR - E-load not in correct mode")
			return
			
		if current_setpoint_A < 0:
			current_setpoint_A = -current_setpoint_A
		
		#4A range
		#if(current_setpoint_A <= self.ranges["low"]):
		#	if(self.range != "low"):
		#		self.set_range("low")
		
		#40A range
		#elif(current_setpoint_A <= self.ranges["high"]):
		#	if(self.range != "high"):
		#		self.set_range("high")
		
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
		self.mode = "CURR"
	
	
	##COMMANDS FOR CV MODE
	def set_mode_voltage(self):
		self.inst.write(":FUNC VOLT")
		time.sleep(0.05)
		self.inst.write(":VOLT:RANG MAX")
		self.mode = "VOLT"
	
	def set_cv_voltage(self, voltage_setpoint_V):
		if self.mode != "VOLT":
			print("ERROR - E-load not in correct mode")
			return
		self.inst.write(":VOLT {}".format(voltage_setpoint_V))
		
	#also have :VOLT:RANG :VOLT:VLIM :VOLT:ILIM
	
	##END OF COMMANDS FOR CV MODE
	
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
