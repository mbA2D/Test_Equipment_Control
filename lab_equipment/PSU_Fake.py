#python implementation for a fake power supply to test programs - has all functions and returns some values

# Power Supply
class Fake_PSU:
	has_remote_sense = False
	
	def __init__(self, resource_id = None):
		pass
		
	# To set power supply limit in Amps 
	def set_current(self, current_setpoint_A):		
		pass

	def set_voltage(self, voltage_setpoint_V):
		pass

	def toggle_output(self, state, ch = 1):
		pass
	
	def remote_sense(self, state):
		pass
	
	def lock_commands(self, state):
		pass
	
	def measure_voltage(self):
		return 4.1

	def measure_current(self):
		return 1.0
		
	def measure_power(self):
		current = self.measure_current()
		voltage = self.measure_voltage()
		return float(current*voltage)
