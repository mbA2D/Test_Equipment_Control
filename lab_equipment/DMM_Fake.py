#python implementation for a fake power supply to test programs - has all functions and returns some values

#DMM
class Fake_DMM:
	
	def __init__(self, resource_id = None):
		pass
		
	def measure_voltage(self, nplc = None, volt_range = None):
		return 4.15
	
	def set_mode(self, mode = "DCV"):
		pass
	
	def set_auto_zero_dcv(self, state):
		pass
	
	def set_range_dcv(self, volt_range = None):
		pass
	
	def set_nplc(self, nplc = None):
		pass
