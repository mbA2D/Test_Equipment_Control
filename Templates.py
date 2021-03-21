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
	
	def get_cycle_settings(self):
		
		response = easygui.buttonbox(msg = "Would you like to import settings for this cycle or create new settings?",
										title = "Get Settings", choices = ("New Settings", "Import Settings"))
		if(response == "New Settings"):
			valid_entries = False
			while valid_entries == False:
				self.settings = eg.multenterbox(msg = "Enter Cycle Info", title, self.settings.keys(), self.settings.values())
				valid_entries = self.check_user_entry(self.settings)
			if (eg.ynbox(msg = "Would you like to save these settings for future use?", title = "Save Settings")):
				self.export_cycle_settings()
		elif (response == "Import Settings"):
			self.import_cycle_settings()
		
		self.convert_to_float()
			
	def convert_to_float(self):
		#if possible, convert items to floats
		for key in self.settings:
			try:
				self.settings[key] = float(self.settings[key])
			except ValueError:
				pass
	
	def export_cycle_settings(self):
		#get the file to export to
		file_name = eg.filesavebox(msg = "Choose a File to export the settings",
									title = "Cycle Settings", filetypes = ['*.json', 'JSON files'])
		
		#Checking the file type
		file_name = self.force_extension(file_name, '.json')
		
		#export the file
		if(file_name != None):
			with open(file_name, "w") as write_file:
				json.dump(self.settings, write_file)
	
	def import_cycle_settings(self):
		#get the file to import from
		file_name = eg.fileopenbox(msg = "Choose a File to import settings from",
									title = "Cycle Settings", filetypes = ['*.json', 'JSON files'])
		
		#import the file
		if(file_name != None):
			with open(file_name, "r") as read_file:
				json.load(self.settings, read_file)
				
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
			"cell_name": 				"CELL_NAME", 
			"charge_end_v": 			4.2,
			"charge_a": 				7.5,
			"charge_end_a": 			0.3,
			"meas_log_int_s": 			1
		}
