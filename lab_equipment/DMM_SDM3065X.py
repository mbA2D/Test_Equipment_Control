#python pyvisa commands for controlling Korad SDM3065X series eloads
#Links helpful for finding commands: https://lygte-info.dk/project/TestControllerIntro

import pyvisa
import time
import easygui as eg

# E-Load
class SDM3065X:
	# Initialize the SDM3065X E-Load
	
	read_termination = '\n'
	
	def __init__(self, resource_id = ""):
		rm = pyvisa.ResourceManager()
		
		if(resource_id == ""):
			resources = rm.list_resources()

			################# IDN VERSION #################
			#Attempt to connect to each Visa Resource and get the IDN response
			title = "DMM Selection"
			if(len(resources) == 0):
				resource_id = 0
				print("No PyVisa Resources Available. Connection attempt will exit with errors")
			idns_dict = {}
			for resource in resources:
				try:
					instrument = rm.open_resource(resource)
					instrument.read_termination = SDM3065X.read_termination
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
				msg = "Select the DMM Supply Model:"
				idn = eg.choicebox(msg, title, idns_dict.values())
			#Now we know which IDN we want to connect to
			#swap keys and values and then connect
			resources_dict = dict((v,k) for k,v in idns_dict.items())
			resource_id = resources_dict[idn]
		
		
		
		self.inst = rm.open_resource(resource_id)
		self.inst.read_termination = SDM3065X.read_termination
		
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
		self.setup_dcv = {"MODE": None,
						  "RANGE": None,
						  "NPLC": None}
		
		print("Connected to %s\n" % self.inst.query("*IDN?"))
		self.inst.write("*RST")
				
		#set to remote mode (disable front panel)
		#self.lock_front_panel(True)
		
	
	def measure_voltage(self, nplc = 1, volt_range = 'AUTO'):
		
		if self.mode != "DCV":
			self.inst.write("CONF:VOLT:DC")
			self.mode = "DCV"
		
		if self.setup_dcv["NPLC"] != nplc:
			if nplc not in self.nplc_ranges:
				print("Invalid NPLC Selection")
				return 0
			self.inst.write("SENS:VOLT:DC:NPLC {}".format(nplc))
			self.setup_dcv["NPLC"] = nplc
		
		if self.setup_dcv["RANGE"] != volt_range:
			if volt_range not in self.volt_ranges.keys():
				print("Invalid Voltage Range Selection")
				return 0
			if volt_range == 'AUTO':
				self.inst.write("VOLT:DC:RANG:AUTO ON")
			else:
				self.inst.write("VOLT:DC:RANG {}".format(self.volt_ranges[volt_range]))
			self.setup_dcv["RANGE"] = volt_range
		
		return float(self.inst.query("READ?"))
		
		#uses auto-range and 10 PLC
		#return float(self.inst.query("MEAS:VOLT:DC?"))
	
	#def measure_voltage_ac(self):
	#	return float(self.inst.query("MEAS:VOLT:AC?"))

	#def measure_diode(self):
	#	return float(self.inst.query("MEAS:DIODE?"))

	#def measure_current(self):
	#	return float(self.inst.query(":MEAS:CURR?"))
	
	def __del__(self):
		#self.conf_voltage_dc(False)
		#self.lock_front_panel(False)
		try:
			self.inst.close()
		except AttributeError:
			pass
