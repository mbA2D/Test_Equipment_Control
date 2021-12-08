#Purpose: Automated Testing of DC-DC Converter Efficiency curves
#		  at different load currents and input voltages 
#Written By: Micah Black
#Date

import equipment as eq
import time
import easygui as eg
import numpy as np
import tkinter as tk
import FileIO
import Templates
import jsonIO



#sweep the load current of an E-load from X to Y A in increments and log to CSV

eload = eq.eLoads.choose_eload()[1]
psu = eq.powerSupplies.choose_psu()[1]

def init_instruments():
	eload.remote_sense(False)
	psu.remote_sense(False)

def remove_extreme_values(list_to_remove, num_to_remove):
	for i in range(int(num_to_remove)):
		list_to_remove.remove(max(list_to_remove))
		list_to_remove.remove(min(list_to_remove))
	return list_to_remove

def gather_data(samples_to_avg):
	data = dict()
	
	input_voltage = list()
	input_current = list()
	output_voltage = list()
	output_current = list()
	
	for i in range(int(samples_to_avg)):
		#The current and voltage measurements are not simultaneous
		#so we technically are not measuring true power
		#we will average each term individually as the load conditions are not
		#changing and any switching noise, mains noise, etc. will be averaged out (hopefully)
		time.sleep(0.01)
		input_voltage.append(psu.measure_voltage())
		input_current.append(psu.measure_current())
		output_voltage.append(eload.measure_voltage())
		output_current.append(eload.measure_current())
		
	#discard top and bottom measurements
	#average and save the rest of the measurements
	#need to be careful of number of samples taken
	
	#top and bottom amount to remove:
	remove_num = int(np.log(samples_to_avg))
	
	input_voltage = remove_extreme_values(input_voltage, remove_num)
	input_current = remove_extreme_values(input_current, remove_num)
	output_voltage = remove_extreme_values(output_voltage, remove_num)
	output_current = remove_extreme_values(output_current, remove_num)
	
	#compute average of what's left (non-outliers)
	iv = sum(input_voltage) / len(input_voltage)
	ic = sum(input_current) / len(input_current)
	ov = sum(output_voltage) / len(output_voltage)
	oc = sum(output_current) / len(output_current)	
	
	data['v_in']=(iv)
	data['i_in']=(ic)
	data['v_out']=(ov)
	data['i_out']=(oc)
	
	return data

def sweep_load_current(filepath, test_name, settings):

	psu.set_voltage(settings["psu_voltage"])
	psu.set_current(settings["psu_current_limit_a"])
	
	for current in np.linspace(settings["load_current_min"],
								settings["load_current_max"],
								int(settings["num_current_steps"])):
		eload.set_current(current)
		time.sleep(settings["step_delay_s"])
		data = gather_data(settings["measurement_samples_for_avg"])
		data["v_in_set"] = settings["psu_voltage"]
		FileIO.write_data(filepath, data, printout = True)


################# MAIN PROGRAM ##################
if __name__ == '__main__':
	directory = FileIO.get_directory("DC-DC-Test")
	test_name = eg.enterbox(title = "Test Setup", msg = "Enter the Test Name\n(Spaces will be replaced with underscores)",
							default = "TEST_NAME", strip = True)
	test_name = test_name.replace(" ", "_")
	
	test_settings = Templates.DcdcTestSettings()
	test_settings = test_settings.settings
	test_settings = jsonIO.get_cycle_settings(test_settings, test_name)
	
	#generate a list of sweep settings - changing voltage for each sweep
	voltage_list = np.linspace(test_settings["psu_voltage_min"],
							   test_settings["psu_voltage_max"],
							   int(test_settings["num_voltage_steps"]))
	
	sweep_settings_list = list()
	for voltage in voltage_list:
		sweep_settings = Templates.DcdcSweepSettings()
		sweep_settings = sweep_settings.settings
		sweep_settings["psu_voltage"] = voltage
		sweep_settings["psu_current_limit_a"] = test_settings["psu_current_limit_a"]
		sweep_settings["load_current_min"] = test_settings["load_current_min"]
		sweep_settings["load_current_max"] = test_settings["load_current_max"]
		sweep_settings["num_current_steps"] = test_settings["num_current_steps"]
		sweep_settings["step_delay_s"] = test_settings["step_delay_s"]
		sweep_settings["measurement_samples_for_avg"] = test_settings["measurement_samples_for_avg"]
		sweep_settings_list.append(sweep_settings)
	
	filepath = FileIO.start_file(directory, test_name)
	
	#Turn on power supply and eload to get the converter started up
	init_instruments()
	psu.set_voltage(test_settings["psu_voltage_min"])
	psu.set_current(test_settings["psu_current_limit_a"])
	eload.set_current(0)
	psu.toggle_output(True)
	eload.toggle_output(True)
	
	#run through each of the generated settings
	for sweep_settings in sweep_settings_list:
		sweep_load_current(filepath, test_name, sweep_settings)
	
	#Turn off power supply and eload
	eload.set_current(0)
	eload.toggle_output(False)
	psu.toggle_output(False)
