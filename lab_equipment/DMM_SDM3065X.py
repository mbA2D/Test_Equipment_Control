#python pyvisa commands for controlling Korad SDM3065X series eloads
#Links helpful for finding commands: https://lygte-info.dk/project/TestControllerIntro

import pyvisa
from .PyVisaDeviceTemplate import DMMDevice

#DMM
class SDM3065X(DMMDevice):
	# Initialize the SDM3065X E-Load
	connection_settings = {
        'read_termination':     '\n',
        'timeout':              5000, #5 second timeout
        'time_wait_after_open': 0,
        'pyvisa_backend':       '@ivi',
        'idn_available':        True
	}
	defaults = {"NPLC": 1,
				"VOLT_DC_RANGE": 'AUTO'}
		
	def initialize(self):
		
		self.volt_ranges = {0.2: '200mv',
							2: '2V',
							20: '20V',
							200: '200V',
							1000: '1000V',
							'AUTO': 'AUTO'}
		self.nplc_ranges = [100, 10, 1, 0.5, 0.05, 0.005]
		self.curr_ranges = {0.0002: '200uA',
							0.002: '2mA',
							0.02: '20mA',
							0.2: '200mA',
							2: '2A',
							10: '10A',
							'AUTO': 'AUTO'}
		self.mode = "NONE"
		self.setup_dcv = {"RANGE": None,
						  "NPLC": None}
		
		self.inst.write("*RST")
				
		#set to remote mode (disable front panel)
		#self.lock_front_panel(True)
		
	
	def measure_voltage(self, nplc = defaults["NPLC"], volt_range = defaults["VOLT_DC_RANGE"]):
		
		if self.mode != "DCV":
			self.set_mode(mode = "DCV")
			
		if self.setup_dcv["NPLC"] != nplc:
			self.set_nplc(nplc = nplc)
		
		if self.setup_dcv["RANGE"] != volt_range:
			self.set_range_dcv(volt_range = volt_range)
		
		self.inst.write("INIT") #set to wait for trigger state
		return float(self.inst.query("READ?"))
		
		#uses auto-range and 10 PLC
		#return float(self.inst.query("MEAS:VOLT:DC?"))
	
	def set_mode(self, mode = "DCV"):
		if mode == "DCV":
			self.inst.write("CONF:VOLT:DC")
			self.set_auto_zero_dcv(False) #faster measurements
			self.mode = mode
	
	def set_auto_zero_dcv(self, state):
		self.inst.write("VOLT:DC:AZ {:d}".format(state))
	
	def set_range_dcv(self, volt_range = defaults["VOLT_DC_RANGE"]):
		if volt_range not in self.volt_ranges.keys():
			print("Invalid Voltage Range Selection")
			return
		if volt_range == 'AUTO':
			self.inst.write("VOLT:DC:RANG:AUTO ON")
		else:
			self.inst.write("VOLT:DC:RANG {}".format(self.volt_ranges[volt_range]))
		self.setup_dcv["RANGE"] = volt_range
	
	def set_nplc(self, nplc = defaults["NPLC"]):
		if nplc not in self.nplc_ranges:
			print("Invalid NPLC Selection")
			return
		self.inst.write("SENS:VOLT:DC:NPLC {}".format(nplc))
		self.setup_dcv["NPLC"] = nplc
	
	
	#def measure_voltage_ac(self):
	#	return float(self.inst.query("MEAS:VOLT:AC?"))

	#def measure_diode(self):
	#	return float(self.inst.query("MEAS:DIODE?"))

	#def measure_current(self):
	#	return float(self.inst.query("MEAS:CURR:DC?"))
	
	def __del__(self):
		#self.conf_voltage_dc(False)
		#self.lock_front_panel(False)
		try:
			self.inst.close()
		except (AttributeError, pyvisa.errors.InvalidSession):
			pass
