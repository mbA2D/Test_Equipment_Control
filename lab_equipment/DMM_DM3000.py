#python pyvisa commands for controlling Rigol DM3000 series dmm
#Manuals: https://www.rigolna.com/products/digital-multimeters/dm3000/

import pyvisa
import time
import easygui as eg
import serial

# DMM
class DM3000:
	# Initialize the DM3000 DMM
	
	read_termination = '\n'
	timeout = 5000 #5 second timeout
	
	def __init__(self, resource_id = None):
		rm = pyvisa.ResourceManager()
		
		if(resource_id == None):
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
					instrument.read_termination = DM3000.read_termination
					instrument.timeout = DM3000.timeout
					instrument_idn = instrument.query("*IDN?")
					idns_dict[resource] = instrument_idn
					instrument.close()
				except (pyvisa.errors.VisaIOError, PermissionError, serial.serialutil.SerialException):
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
		self.inst.read_termination = DM3000.read_termination
		
		self.volt_ranges = {0.2: 0,
							2: 1,
							20: 2,
							200: 3,
							1000: 4,
							'AUTO': 'AUTO'}
		self.res_ranges = [0, 1, 2]
		self.rate_ranges = {20: 'S',
							2: 'M',
							1: 'F'}
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
						  "RES": None,
						  "NPLC": None}
		
		print("Connected to %s\n" % self.inst.query("*IDN?"))
		self.inst.write("*RST")
		
	def measure_voltage(self, res = 2, volt_range = 'AUTO'):
		
		if self.mode != "DCV":
			self.set_mode(mode = "DCV")
			
		if self.setup_dcv["RES"] != res:
			self.set_res(res)
		
		if self.setup_dcv["RANGE"] != volt_range:
			self.set_range_dcv(volt_range = volt_range)
		
		return float(self.inst.query(":MEAS:VOLT:DC?"))
	
	def set_mode(self, mode = "DCV"):
		if mode == "DCV":
			self.inst.write(":FUNC:VOLT:DC")
			self.mode = mode
	
	def set_range_dcv(self, volt_range = 'AUTO'):
		if volt_range not in self.volt_ranges.keys():
			print("Invalid Voltage Range Selection")
			return
		self.inst.write("CONF:VOLT:DC {}".format(self.volt_ranges[volt_range]))
		self.setup_dcv["RANGE"] = volt_range
	
	def set_res(self, res = 1):
		#res=0 is 4.5 digit
		#res=1 is 5.5 digit
		#res=2 is 6.5 digit
		if res not in self.res_ranges:
			print("Invalid Resolution Selection")
			return
		self.inst.write(":MEAS:VOLT:DC {}".format(res))
		self.setup_dcv["RES"] = res
		
	def set_nplc(self, nplc = 1):
		#This is not quite NPLC, but we will keep it as NPLC for cross compatibility.
		#nplc=F is 123 readings/s, 50Hz refresh rate, almost 1 NPLC
		#nplc=M is 20 readings/s, 20Hz refresh rate, almost 2 NPLC
		#nplc=S is 2.5 readings/s, 2.5Hz refresh rate, almost 20 NPLC
		if nplc not in self.rate_ranges.keys():
			print("Invalid Rate Selection")
			return
		self.inst.write(":RATE:VOLT:DC {}".format(nplc))
		self.setup_dcv["NPLC"] = nplc
		
	#def measure_voltage_ac(self):
	#	return float(self.inst.query("MEAS:VOLT:AC?"))

	#def measure_diode(self):
	#	return float(self.inst.query("MEAS:DIODE?"))

	#def measure_current(self):
	#	return float(self.inst.query(":MEAS:CURR?"))
	
	def __del__(self):
		try:
			self.inst.close()
		except AttributeError:
			pass
