#class to hold the templates for input/outputs settings
#TODO - write and read from saved JSON settings files

import easygui as eg

class CycleStats:
	
	def __init__(self):
		self.stats = {
			"charge_capacity_ah": 		0,
			"charge_capacity_wh": 		0,
			"charge_time_h": 			0,
			"discharge_capacity_ah": 	0,
			"discharge_capacity_wh": 	0,
			"discharge_time_h": 		0
		}


##################### Checking User Input ##############
def check_user_entry(entry):
	if(entry == None):
		return False
	
	valid = True
	
	for val in entry:
		if(val == entry[0]):
			if("." in val):
				return False
		else:	
			if not is_number_float(val):
				return False
	
	return valid

def is_number_float(string):
	try:
		float(string)
		return True
	except ValueError:
		return False

###############  CYCLE  #######################
class CycleSettings:

	def __init__(self):
		self.settings = {
			"cell_name": 				"CELL_NAME", 
			"charge_end_v": 			4.2,
			"charge_a": 				7.5,
			"charge_end_a": 			0.3,
			"rest_after_charge_min": 	20, 
			"discharge_end_v": 			2.5,
			"discharge_a": 				52.5,
			"rest_after_discharge_min": 20,
			"meas_log_int_s": 			1
		}
	
	def get_cycle_settings(self, title):
		valid_entries = False
		while valid_entries == False:
			self.settings = eg.multenterbox(msg = "Enter Cycle Info", title, self.settings.keys(), self.settings.values())
			valid_entries = check_user_entry(self.settings)
		self.convert_to_float()
			
	def convert_to_float():
		#if possible, convert items to floats
		for key in self.settings:
			try:
				self.settings[key] = float(self.settings[key])
			except ValueError:
				pass


###############  CHARGE  #####################
class ChargeSettings:

	def __init__(self):
		self.settings = {
			"cell_name": 				"CELL_NAME", 
			"charge_end_v": 			4.2,
			"charge_a": 				7.5,
			"charge_end_a": 			0.3,
			"meas_log_int_s": 			1
		}
	
	def get_cycle_settings(self, title):
		valid_entries = False
		while valid_entries == False:
			self.settings = eg.multenterbox(msg = "Enter Charge Info", title, self.settings.keys(), self.settings.values())
			valid_entries = check_user_entry(self.settings)
		self.convert_to_float()
			
	def convert_to_float():
		#if possible, convert items to floats
		for key in self.settings:
			try:
				self.settings[key] = float(self.settings[key])
			except ValueError:
				pass
