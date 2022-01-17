#python pyvisa commands for controlling Rigol DL3000 series eloads
#Written by: Micah Black
#
#Updated by: Micah Black Oct 4, 2021
#Added Battery Test Mode
#Changed local variable 'range' to '_range' to avoid confusion with python's range() function

import pyvisa
import time
import easygui as eg

# E-Load
class DL3000:
	# Initialize the DL3000 E-Load
	def __init__(self, resource_id = ""):
		rm = pyvisa.ResourceManager('@ivi')
		
		if(resource_id == ""):
			resources = rm.list_resources('@ivi')
			
			################# IDN VERSION #################
			#Attempt to connect to each Visa Resource and get the IDN response
			title = "Eload Selection"
			if(len(resources) == 0):
				resource_id = 0
				print("No PyVisa Resources Available. Connection attempt will exit with errors")
			idns_dict = {}
			for resource in resources:
				try:
					instrument = rm.open_resource(resource)
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
				msg = "Select the Eload Supply Model:"
				idn = eg.choicebox(msg, title, idns_dict.values())
			#Now we know which IDN we want to connect to
			#swap keys and values and then connect
			resources_dict = dict((v,k) for k,v in idns_dict.items())
			resource_id = resources_dict[idn]
		

		
		self.inst = rm.open_resource(resource_id)
        
        self.inst_idn = self.inst.query("*IDN?")
		print("Connected to {}\n".format(self.inst_idn))
        
        split_string = self.inst_idn.split(",")
        self.manufacturer = split_string[0]
        self.model_number = split_string[1]
        self.serial_number = split_string[2]
        self.version_number = split_string[3]
        
		self._range = "low"
		
        if self.model_number == "DL3021" or self.model_number == "DL3021A":
            #values specific to the DL3000 - will break out to another file later
            self.ranges = {"low":4,"high":40}
        elif self.model_number == "DL3031" or self.model_number == "DL3031A":
            #values specific to the DL3000 - will break out to another file later
            self.ranges = {"low":6,"high":60}
        
		self.inst.write("*RST")
		self.set_mode_current()
		self.set_current(0)
				
		#set to remote mode (disable front panel)
		self.lock_front_panel(True)
		
	# To Set E-Load in Amps 
	def set_current(self, current_setpoint_A):		
		#4 or 6A range
		if(current_setpoint_A <= self.ranges["low"]):
			if(self._range != "low"):
				self.set_range("low")
		
		#40 or 60A range
		elif(current_setpoint_A <= self.ranges["high"]):
			if(self._range != "high"):
				self.set_range("high")
		
		self.inst.write(":CURR:LEV %s" % current_setpoint_A)

	def set_range(self, set_range):
		#set_range is either "high" or "low"
		write_range = "MIN"
		if(set_range == "high"):
			write_range = "MAX"
		self.inst.write(":CURR:RANG {}".format(write_range))
		self._range = set_range
		
	def set_mode_current(self):
		self.inst.write(":FUNC CURR")

	def toggle_output(self, state):
		if state:
			self.inst.write(":INP ON")
		else:
			self.inst.write(":INP OFF")
	
	def remote_sense(self, state):
		if state:
			self.inst.write(":SENS ON")
		else:
			self.inst.write(":SENS OFF")
	
	def lock_front_panel(self, state):
		pass
	#	if state:
	#		self.inst.write("SYST:REM")
	#	else:
	#		self.inst.write("SYST:LOC")
	
	def measure_voltage(self):
		return float(self.inst.query(":MEAS:VOLT:DC?"))

	def measure_current(self):
		return float(self.inst.query(":MEAS:CURR:DC?"))
    
    def battery_test(self, current_a, end_condition = "v", end_value = 2.5, start_v = 2.5)
        #end_condition is "c", "v", or "t" for voltage, current, or time.
        #end_v is end voltage in V
        #end_c is end capacity in Ah
        #end_t is end time in seconds
        
        if(end_condition not in ("c", "v", "t"):
            print("Incompatible end condition for battery test")
            return
        
        #ensure output is off before switching modes
        self.toggle_output(False)
        #Go into battery mode
        self.inst.write(":FUNC:MODE:BATT")
        
        #Set current range for the battery
        self.inst.write(":BATT:RANG {}".format(current_a))
        #Set battery discharge current
        self.inst.write(":BATT {}".format(current_a))
        
        vstop = "MIN"
        cstop = "MIN"
        tstop = "MIN"
        
        if end_condition == "c":
            vstop = "MAX"
            tstop = "MAX"
            cstop = end_value * 1000
        elif end_condition == "v":
            vstop = end_value
            tstop = "MAX"
            cstop = "MAX"
        elif end_condition == "t":
            vstop = "MAX"
            tstop = end_value
            cstop = "MAX"
        
        self.inst.write(":BATT:VST {}".format(vstop))
        self.inst.write(":BATT:CST {}".format(cstop))
        self.inst.write(":BATT:TIM {}".format(tstop))
        self.inst.write("BATT:VON {}".format(start_v))
        
        #TODO - do VST, CST, TIM turn off the output when they trigger?
        
        #TODO - what are CEN, VEN, and TEN?
        
        #TODO - can we measure voltage and current when in battery mode?
        
        #TODO - how do we know when the discharge is complete?
    
    def get_battery_capacity_ah(self):
        #I believe the load measures capacity in mAh, so divide by 1000 for Ah.
        return self.inst.query(":FETCH:CAP?")/1000.0
    
    def get_battery_energy_wh(self):
        return self.inst.query(":FETCH:WATT?")
    
    def get_battery_time_s(self):
        #returns the time it took to discharge the battery_test
        return self.inst.query(":FETCH:DISCT?")
        
	def __del__(self):
		self.toggle_output(False)
		#self.lock_front_panel(False)
		try:
			self.inst.close()
		except AttributeError:
			pass