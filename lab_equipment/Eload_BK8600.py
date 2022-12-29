#python pyvisa commands for controlling BK8600 series eloads

import pyvisa
import time
from .PyVisaDeviceTemplate import EloadDevice

# E-Load
class BK8600(EloadDevice):
	
	has_remote_sense = True
	pyvisa_backend = '@ivi'
	
	def initialize(self):
		idn_split = self.inst_idn.split(',')
		model_number = idn_split[1]
		
		#resets to Constant Current Mode
		self.inst.write("*RST")
		
		if '8600' in model_number:
			self.max_current = 30
			self.max_power = 150
		elif '8601' in model_number:
			self.max_current = 60
			self.max_power = 250
		elif '8602' in model_number:
			self.max_current = 15
			self.max_power = 200
		elif '8610' in model_number:
			self.max_current = 120
			self.max_power = 750
		elif '8612' in model_number:
			self.max_current = 30
			self.max_power = 750
		elif '8614' in model_number:
			self.max_current = 240
			self.max_power = 1500
		elif '8616' in model_number:
			self.max_current = 60
			self.max_power = 1200
		elif '8620' in model_number:
			self.max_current = 480
			self.max_power = 3000
		elif '8622' in model_number:
			self.max_current = 100
			self.max_power = 2500
		elif '8624' in model_number:
			self.max_current = 600
			self.max_power = 4500
		elif '8610' in model_number:
			self.max_current = 720
			self.max_power = 6000
		
		self.mode = "CURR"
		
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
		self.inst.write("CURR:LEV {}".format(current_setpoint_A))
	
	def set_mode_current(self):
		self.inst.write("FUNC CURR")
		self.mode = "CURR"
	
	##COMMANDS FOR CV MODE
	def set_mode_voltage(self):
		self.inst.write("FUNC VOLT")
		self.mode = "VOLT"
		#Only 1 voltage range on this eload
	
	def set_cv_voltage(self, voltage_setpoint_V):
		if self.mode != "VOLT":
			print("ERROR - E-load not in correct mode")
			return
		self.inst.write("VOLT {}".format(voltage_setpoint_V))
	
	##END OF COMMANDS FOR CV MODE
	
	def toggle_output(self, state):
		if state:
			self.inst.write("INP ON")
		else:
			self.inst.write("INP OFF")
	
	def remote_sense(self, state):
		if state:
			self.inst.write("REM:SENS ON")
		else:
			self.inst.write("REM:SENS OFF")
	
	def lock_front_panel(self, state):
		if state:
			self.inst.write("SYST:REM")
		else:
			self.inst.write("SYST:LOC")
	
	def measure_voltage(self):
		return float(self.inst.query("MEAS:VOLT:DC?"))

	def measure_current(self):
		return (float(self.inst.query("MEAS:CURR:DC?")) * (-1))
		
	def __del__(self):
		try:
			self.toggle_output(False)
			self.lock_front_panel(False)
			self.inst.close()
		except (AttributeError, pyvisa.errors.InvalidSession):
			pass
