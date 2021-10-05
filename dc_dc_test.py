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

eloads = eq.eLoads()
eload = eloads.choose_eload()

psus = eq.powerSupplies()
psu = psus.choose_psu()

def init_instruments():
	eload.remote_sense(True)
	psu.remote_sense(True)


def gather_data(samples_to_avg):
	data = list()
	
	input_voltage = list()
	input_current = list()
	output_voltage = list()
	output_current = list()
	
	for i in range(samples_to_avg):
		#The current and voltage measurements are not simultaneous
		#so we technically are not measuring true power
		#we will average each term individually as the load conditions are not
		#changing and any switching noise, mains noise, etc. will be averaged out (hopefully)
		
		input_voltage.append(psu.measure_voltage())
		input_current.append(psu.measure_current())
		output_voltage.append(eload.measure_voltage())
		output_current.append(eload.measure_current())
		
	#discard top and bottom measurements
	#average and save the rest of the measurements
	#need to be careful of number of samples taken
	
	#top and bottom amount to remove:
	remove_num = int(np.log(samples_to_avg))
	
	for i in range(remove_num):
		input_current.remove(max(input_current))
		input_current.remove(min(input_current))
		input_voltage.remove(max(input_voltage))
		input_voltage.remove(min(input_voltage))
		output_current.remove(max(output_current))
		output_current.remove(min(output_current))
		output_voltage.remove(max(output_voltage))
		output_voltage.remove(min(output_voltage))
	
	#compute average of what's left (non-outliers)
	iv = sum(input_voltage) / len(input_voltage)
	ic = sum(input_current) / len(input_current)
	ov = sum(output_voltage) / len(output_voltage)
	oc = sum(output_current) / len(output_current)	
	
	data.append(oc)
	data.append(ov)
	data.append(ic)
	data.append(iv)
	
	return data


#TODO - still need to incorporate averaging of measurements
def sweep_load_current(dir, test_name, settings):
	
	min_a = settings["load_current_min"]
	max_a = settings["load_current_max"]
	num_steps = settings["num_current_steps"]
	delay_s = settings["step_delay_s"]
	
	filepath = FileIO.start_file(dir, test_name)
	
	#TODO - adjust power supply voltage
	psu.set_voltage(settings["psu_voltage"])
	psu.set_current(settings["psu_current_limit_a"])
	
	for current in np.linspace(settings["load_current_min"],
								settings["load_current_max"],
								settings["num_current_steps"]):
		eload.set_current(current)
		time.sleep(delay_s)
		data = gather_data(settings["measurement_samples_for_avg"])
		FileIO.write_data(filepath, data)


################# MAIN PROGRAM ##################
if __name__ == '__main__':
	directory = FileIO.get_directory("DC-DC-Test")
	test_name = eg.enterbox(title = "Test Setup", msg = "Enter the Test Name\n(Spaces will be replaced with underscores)",
							default = "TEST_NAME", strip = True)
	test_name = test_name.replace(" ", "_")
	
	test_settings = Templates.DcdcTestSettings()
	test_settings = jsonIO.get_cycle_settings(test_settings, test_name)
	
	#generate a list of sweep settings - changing voltage for each sweep
	voltage_list = np.linspace(test_settings["psu_voltage_min"],
							   test_settings["psu_voltage_max"],
							   test_settings["num_voltage_steps"])
	
	sweep_settings_list = list()
	for voltage in voltage_list:
		sweep_settings = Templates.DcdcSweepSettings()
		sweep_settings["psu_voltage"] = voltage
		sweep_settings["psu_current_limit_a"] = test_settings["psu_current_limit_a"]
		sweep_settings["load_current_min"] = test_settings["load_current_min"]
		sweep_settings["load_current_max"] = test_settings["load_current_max"]
		sweep_settings["num_current_steps"] = test_settings["num_current_steps"]
		sweep_settings["step_delay_s"] = test_settings["step_delay_s"]
		sweep_settings["measurement_samples_for_avg"] = test_settings["measurement_samples_for_avg"]
		sweep_settings_list.append(sweep_settings)
	
	
	#Turn on power supply and eload to get the converter started up
	init_instruments()
	psu.set_voltage(test_settings["psu_voltage_min"])
	psu.set_current(test_settings["psu_current_limit_a"])
	eload.set_current(0)
	psu.toggle_output(True)
	eload.toggle_output(True)
	
	#run through each of the generated settings
	for sweep_settings in sweep_settings_list:
		sweep_load_current(directory, test_name, sweep_settings)
	
	#Turn off power supply and eload
	eload.toggle_output(False)
	psu.toggle_output(False)
