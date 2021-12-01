#class to hold the templates for input/outputs settings

import easygui as eg
import json
import os


######################  Statistics to gather for each cycle  ###############
class CycleStats:
	
	def __init__(self):
		self.stats = {
			"cell_name":				0,
			"charge_capacity_ah": 		0,
			"charge_capacity_wh": 		0,
			"charge_time_h": 			0,
			"charge_current_a":			0,
			"charge_max_temp_c":		0,
			"charge_start_time":		0,
			"charge_end_time":			0,
			"charge_end_v":				0,
			"discharge_capacity_ah": 	0,
			"discharge_capacity_wh": 	0,
			"discharge_time_h": 		0,
			"discharge_current_a":		0,
			"discharge_max_temp_c":		0,
			"discharge_start_time":		0,
			"discharge_end_time":		0,
			"discharge_end_v":			0
		}

#####################  AVAILABLE CYCLE TYPES  ####################
class CycleTypes:
	
	cycle_types = {
		"Single Cycle": 							{'func_call': '', 'str_chg_opt': True, 'load_req': True, 'supply_req': True},
		"One Setting Continuous Cycles With Rest": 	{'func_call': '', 'str_chg_opt': True,'load_req': True, 'supply_req': True},
		"Two Setting Continuous Cycles With Rest": 	{'func_call': '', 'str_chg_opt': True,'load_req': True, 'supply_req': True},
		"Charge Only": 								{'func_call': '', 'str_chg_opt': False,'load_req': False, 'supply_req': True},
		"Discharge Only": 							{'func_call': '', 'str_chg_opt': False,'load_req': True, 'supply_req': False},
		"Single Step":								{'func_call': '', 'str_chg_opt': False,'load_req': True, 'supply_req': True}
	}
	
	#TODO - Step should not have its load and supply requirements given here - it should only be after the step values are chosen


###############  CYCLE  #######################
class CycleSettings:

	def __init__(self):
		self.settings = { 
			"charge_end_v": 			4.2,
			"charge_a": 				7.5,
			"charge_end_a": 			0.3,
			"rest_after_charge_min": 	20, 
			"discharge_end_v": 			2.5,
			"discharge_a": 				52.5,
			"rest_after_discharge_min": 20,
			"meas_log_int_s": 			1
		}
	
	def get_cycle_settings(self, cycle_name = ""):
		
		if(cycle_name != ""):
			cycle_name += " "
		
		response = eg.buttonbox(msg = "Would you like to import settings for {}cycle or create new settings?".format(cycle_name),
										title = "Settings for {}cycle".format(cycle_name), choices = ("New Settings", "Import Settings"))
		if(response == "New Settings"):
			valid_entries = False
			while valid_entries == False:
				response_list = eg.multenterbox(msg = "Enter Info for {}cycle".format(cycle_name), title = response,
												fields = list(self.settings.keys()), values = list(self.settings.values()))
				valid_entries = self.check_user_entry(response_list)
			
			#update dict entries with the response
			self.update_settings(response_list)
			
			if (eg.ynbox(msg = "Would you like to save these settings for future use?", title = "Save Settings")):
				self.export_cycle_settings(cycle_name)
		elif (response == "Import Settings"):
			self.import_cycle_settings(cycle_name)
		
		self.convert_to_float()
	
	def check_user_entry(keys, entries):
		if(entries == None):
			return False
		
		entry_dict = dict(zip(keys, entries))
		
		for key in entry_dict:
			if not is_entry_valid(key, entry_dict[key]):
				return False
		
		return True

	def is_entry_valid(key, value):
		try:
			float(value)
			return True
		except ValueError:
			try:
				if value in self.valid_strings[key]:
					return True
			except AttributeError:
				return False
			return False
		return False
	
	def convert_to_float(self):
		#if possible, convert items to floats
		for key in self.settings.keys():
			try:
				self.settings[key] = float(self.settings[key])
			except ValueError:
				pass
	
	def update_settings(self, new_value_list):
		#assuming an ordered response list
		#a bit hacky but it should work
		index = 0
		for key in self.settings.keys():
			self.settings.update({key: new_value_list[index]})
			index += 1
	
	def export_cycle_settings(self, cycle_name = ""):
		#add extra space to get formatting correct
		if (cycle_name != ""):
			cycle_name += " "
		
		#get the file to export to
		file_name = eg.filesavebox(msg = "Choose a File to export {}cycle settings to".format(cycle_name),
									title = "Cycle Settings", filetypes = ['*.json', 'JSON files'])
		
		#force file name extension
		file_name = self.force_extension(file_name, '.json')
		
		#export the file
		if(file_name != None):
			with open(file_name, "w") as write_file:
				json.dump(self.settings, write_file, indent = 4)
	
	def import_cycle_settings(self, cycle_name = ""):
		#add extra space to get formatting correct
		if (cycle_name != ""):
			cycle_name += " "
		
		#get the file to import from
		file_name = eg.fileopenbox(msg = "Choose a File to import {}cycle settings from".format(cycle_name),
									title = "Cycle Settings", filetypes = ['*.json', 'JSON files'])
		
		#import the file
		if(file_name != None):
			with open(file_name, "r") as read_file:
				self.settings = json.load(read_file)
				
	def force_extension(self, filename, extension):
		#Checking the file type
		file_root, file_extension = os.path.splitext(filename)
		if(file_extension != extension):
			file_extension = extension
		file_name = file_root + file_extension
		return file_name

###############  CHARGE  #####################

class ChargeSettings(CycleSettings):

	def __init__(self):
		self.settings = { 
			"charge_end_v": 			4.2,
			"charge_a": 				7.5,
			"charge_end_a": 			0.3,
			"meas_log_int_s": 			1
		}
		
###############  DISCHARGE  #####################

class DischargeSettings(CycleSettings):

	def __init__(self):
		self.settings = { 
			"discharge_end_v": 			2.5,
			"discharge_a": 				52.5,
			"meas_log_int_s": 			1
		}

#################  STEPS FOR CONTROLLING BATTERY TEST  ############

class StepSettings(CycleSettings):
	def __init__(self):
		self.settings = {
			"drive_style":				'current_a', #'current_a', 'voltage_v', 'none'
			"drive_value":				1,
			"drive_value_other":		4.0,
			"end_style":				'time_s', #'time_s', 'current_a', 'voltage_v'
			"end_condition":			'greater', #'greater', 'lesser'
			"end_value":				10
		}
		self.valid_strings = {
			"drive_style":				{'current_a', 'voltage_v', 'none'},
			"end_style":				{'time_s', 'current_a', 'voltage_v'},
			"end_condition":			{'greater', 'lesser'}
		}

####################  DC DC TESTING  ############

class DcdcTestSettings():

	def __init__(self):
		self.settings = {
			"psu_voltage_min":				4,
			"psu_voltage_max":				7,
			"num_voltage_steps":			4,
			"psu_current_limit_a":			2,
			"load_current_min":				0.1,
			"load_current_max": 			1,
			"num_current_steps":			10,
			"step_delay_s":					2,
			"measurement_samples_for_avg":	10
		}

class DcdcSweepSettings():
	
	def __init__(self):
		self.settings = {
			"psu_voltage":					4,
			"psu_current_limit_a":			2,
			"load_current_min":				0.1,
			"load_current_max": 			1,
			"num_current_steps":			10,
			"step_delay_s":					2,
			"measurement_samples_for_avg":	10
		}
