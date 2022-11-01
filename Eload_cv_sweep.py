# Script to sweep CV with eload for MPPT Testing

import equipment as eq
import time
import easygui as eg
import numpy as np
import FileIO
import Templates
import jsonIO

eload = eq.eLoads.choose_eload()[1]

def init_instruments():
	eload.set_mode_voltage()
	v_test_1 = eload.measure_voltage()

def remove_extreme_values(list_to_remove, num_to_remove):
	for i in range(int(num_to_remove)):
		list_to_remove.remove(max(list_to_remove))
		list_to_remove.remove(min(list_to_remove))
	return list_to_remove

def gather_data(samples_to_avg):
	data = dict()
	
	voltage = list()
	current = list()
	
	for i in range(int(samples_to_avg)):
		#The current and voltage measurements are not simultaneous
		#so we technically are not measuring true power
		#we will average each term individually as the load conditions are not
		#changing and any switching noise, mains noise, etc. will be averaged out (hopefully)
		time.sleep(0.01)
		voltage.append(eload.measure_voltage())
		current.append(eload.measure_current())
		
	#discard top and bottom measurements
	#average and save the rest of the measurements
	#need to be careful of number of samples taken
	
	#top and bottom amount to remove:
	remove_num = int(np.log(samples_to_avg))
	
	voltage = remove_extreme_values(voltage, remove_num)
	current = remove_extreme_values(current, remove_num)
	
	#compute average of what's left (non-outliers)
	v = sum(voltage) / len(voltage)
	i = sum(current) / len(current)	
	
	data['voltage']=(v)
	data['current']=(i)
	
	return data

def sweep_load_voltage(filepath, test_name, voltage_list):
	
	for voltage in voltage_list:
		eload.set_cv_voltage(voltage)
		time.sleep(settings["step_delay_s"])
		data = gather_data(settings["measurement_samples_for_avg"])
		FileIO.write_data(filepath, data, printout = True)


if __name__ == '__main__':
	directory = FileIO.get_directory("Eload-CV-Sweep-Test")
	test_name = eg.enterbox(title = "Test Setup", msg = "Enter the Test Name\n(Spaces will be replaced with underscores)",
							default = "TEST_NAME", strip = True)
	test_name = test_name.replace(" ", "_")
	
	test_settings = Templates.EloadCVSweepSettings()
	test_settings = test_settings.settings
	test_settings = jsonIO.get_cycle_settings(test_settings, cycle_name = test_name)
	
	#generate a list of sweep settings - changing voltage for each sweep
	voltage_list = np.linspace(test_settings["min_cv_voltage"],
							   test_settings["max_cv_voltage"],
							   int(test_settings["num_voltage_steps"]))
	
	filepath = FileIO.start_file(directory, test_name)
	
	#Turn on power supply and eload to get the converter started up
	init_instruments()
	eload.set_cv_voltage(0)
	time.sleep(0.05)
	eload.toggle_output(True)
	
	sweep_load_voltage(filepath, test_name, voltage_list)
	
	#Turn off power supply and eload
	eload.toggle_output(False)
	eload.set_cv_voltage(0)
	