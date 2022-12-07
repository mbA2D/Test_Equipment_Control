#python implementation for a fake power supply to test programs - has all functions and returns some values

# Power Supply
class Fake_PSU:
	has_remote_sense = False
	can_measure_v_while_off = True
    
	def __init__(self, resource_id = None):
        self.current_a = 0
        self.voltage_v = 4.1
		pass
		
	# To set power supply limit in Amps 
	def set_current(self, current_setpoint_A):		
        pass

	def set_voltage(self, voltage_setpoint_V):
		self.voltage_v = voltage_setpoint_V

	def toggle_output(self, state, ch = 1):
		pass
	
	def remote_sense(self, state):
		pass
	
	def lock_commands(self, state):
		pass
	
	def measure_voltage(self):
		return self.voltage_v

	def measure_current(self):
		return self.current_a
		
	def measure_power(self):
		current = self.measure_current()
		voltage = self.measure_voltage()
		return float(current*voltage)
