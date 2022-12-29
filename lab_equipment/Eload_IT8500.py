#python pyvisa commands for controlling Itech IT8500 series eloads

import pyvisa
import time
from .PyVisaDeviceTemplate import EloadDevice

# E-Load
class IT8500(EloadDevice):
	# Initialize the IT8500 E-Load
	
	baud_rate = 115200
	write_termination = '\n'
	read_termination = '\n'
	has_remote_sense = True
	pyvisa_backend = '@py'
		
	def initialize(self):	
		idn_split = self.inst_idn.split(',')
		model_number = idn_split[1]
		
		if 'IT8511A' in model_number:
			self.max_current = 30
			self.max_power = 150
		elif 'IT8511B' in model_number:
			self.max_current = 10
			self.max_power = 150
		elif 'IT8512A' in model_number:
			self.max_current = 30
			self.max_power = 300
		elif 'IT8512B' in model_number:
			self.max_current = 15
			self.max_power = 300
		elif 'IT8512C' in model_number:
			self.max_current = 60
			self.max_power = 300
		elif 'IT8512H' in model_number:
			self.max_current = 5
			self.max_power = 300
		elif 'IT8513A' in model_number:
			self.max_current = 60
			self.max_power = 400
		elif 'IT8513B' in model_number:
			self.max_current = 30
			self.max_power = 600
		elif 'IT8513C' in model_number:
			self.max_current = 120
			self.max_power = 600
		elif 'IT8514B' in model_number:
			self.max_current = 60
			self.max_power = 1500
		elif 'IT8514C' in model_number:
			self.max_current = 240
			self.max_power = 1500
		elif 'IT8516C' in model_number:
			self.max_current = 240
			self.max_power = 3000
		
		#resets to Constant Current Mode
		self.mode = "CURR"
		self.inst.write("*RST")
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
		self.inst.write("CURR {}".format(current_setpoint_A))
	
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
			self.inst.write("SYST:SENS ON")
		else:
			self.inst.write("SYST:SENS OFF")
	
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