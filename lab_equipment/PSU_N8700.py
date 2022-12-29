#python pyvisa commands for controlling Keysight N8700 series power supplies

import pyvisa
from .PyVisaDeviceTemplate import PowerSupplyDevice

# Power Supply
class N8700(PowerSupplyDevice):
	# Initialize the N8700 Power Supply
	
	has_remote_sense = False
	can_measure_v_while_off = True #Have not checked this.
	pyvisa_backend = '@py'
	
	def initialize(self):
		self.inst.write("*RST")
		self.lock_front_panel(True)
		self.set_current(0)
		self.set_voltage(0)
		
	def select_channel(self, channel):
		pass
	
	def set_current(self, current_setpoint_A):
		self.inst.write("CURR {}".format(current_setpoint_A))
	
	def set_voltage(self, voltage_setpoint_V):
		self.inst.write("VOLT {}".format(voltage_setpoint_V))

	def toggle_output(self, state):
		if state:
			self.inst.write("OUTP ON")
		else:
			self.inst.write("OUTP OFF")
	
	def remote_sense(self, state):
		#remote sense is done by the wire connection, no software setting
		pass
	
	def lock_front_panel(self, state):
		if state:
			self.inst.write("SYST:COMM:RLST RWL")
		else:
			self.inst.write("SYST:COMM:RLST REM")
	
	def measure_voltage(self):
		return float(self.inst.query("MEAS:VOLT?"))

	def measure_current(self):
		return float(self.inst.query("MEAS:CURR?"))
		
	def measure_power(self):
		return self.measure_voltage()*self.measure_current()
		
	def __del__(self):
		try:
			self.toggle_output(False)
			self.lock_front_panel(False)
			self.inst.close()
		except (AttributeError, pyvisa.errors.InvalidSession):
			pass
