#class to hold the templates for input/outputs settings
#TODO - write and read from saved JSON settings files

import easygui as eg
import json
import os

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
	
	for val in entry:
		if not is_number_float(val):
			return False
	
	return True

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
			"charge_end_v": 			4.2,
			"charge_a": 				7.5,
			"charge_end_a": 			0.3,
			"rest_after_charge_min": 	20, 
			"discharge_end_v": 			2.5,
			"discharge_a": 				52.5,
			"rest_after_discharge_min": 20,
			"meas_log_int_s": 			1
		}
	
	def get_cycle_settings(self, cycle_name = "TEST"):
		
		response = eg.buttonbox(msg = "Would you like to import settings for {} cycle or create new settings?".format(cycle_name),
										title = "Settings for {} cycle".format(cycle_name), choices = ("New Settings", "Import Settings"))
		if(response == "New Settings"):
			valid_entries = False
			while valid_entries == False:
				response_list = eg.multenterbox(msg = "Enter Cycle Info for {}".format(cycle_name), title = response,
												fields = list(self.settings.keys()), values = list(self.settings.values()))
				valid_entries = check_user_entry(response_list)
			
			#update dict entries with the response
			self.update_settings(response_list)
			
			if (eg.ynbox(msg = "Would you like to save these settings for future use?", title = "Save Settings")):
				self.export_cycle_settings()
		elif (response == "Import Settings"):
			self.import_cycle_settings()
		
		self.convert_to_float()
			
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
		if (cycle_name != "")
			cycle_name += " "
		
		#get the file to export to
		file_name = eg.filesavebox(msg = "Choose a File to export {}cycle settings to".format(cycle_name),
									title = "Cycle Settings", filetypes = ['*.json', 'JSON files'])
		
		#force file name extension
		file_name = self.force_extension(file_name, '.json')
		
		#export the file
		if(file_name != None):
			with open(file_name, "w") as write_file:
				json.dump(self.settings, write_file)
	
	def import_cycle_settings(self, cycle_name = ""):
		#add extra space to get formatting correct
		if (cycle_name != "")
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
