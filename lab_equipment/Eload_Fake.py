#python implementation for a fake power supply to test programs - has all functions and returns some values

# E-Load
class Fake_Eload:
	
	has_remote_sense = False

	def __init__(self, resource_id = None):
		pass
		
	# To Set E-Load in Amps 
	def set_current(self, current_setpoint_A):
		pass

	def toggle_output(self, state):
		pass
	
	def remote_sense(self, state):
		pass
	
	def lock_front_panel(self, state):
		pass
	
	def measure_voltage(self):
		return 4.05

	def measure_current(self):
		return -1.0
