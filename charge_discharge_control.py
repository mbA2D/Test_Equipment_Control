#Python Script for controlling the charge and discharge
#tests of a battery with Eload and Power supply

import equipment as eq
from datetime import datetime
import time
import pandas as pd
import easygui as eg
import os
import Templates
import FileIO

 
def init_instruments(eload, psu):
	eload.remote_sense(True)
	psu.remote_sense(True)

####################### TEST CONTROL #####################

def start_charge(end_voltage, constant_current, eload, psu):
	eload.toggle_output(False)
	psu.set_voltage(end_voltage)
	time.sleep(0.01)
	psu.set_current(constant_current)
	time.sleep(0.01)
	psu.toggle_output(True)
	
def start_discharge(constant_current, eload, psu):
	psu.toggle_output(False)
	eload.set_current(constant_current)
	time.sleep(0.01)
	eload.toggle_output(True)

def start_rest(eload, psu):
	psu.toggle_output(False)
	eload.toggle_output(False)

######################### MEASURING ######################

def measure_rest(eload):
	#return current as 0, measure from eload (more accurate)
	return (eload.measure_voltage(), 0)

def measure_charge(eload, psu):
	#return current from power supply, voltage from eload (more accurate)
	return (eload.measure_voltage(), psu.measure_current())

def measure_discharge(eload):
	#return current from eload (as negative), voltage from eload
	return (eload.measure_voltage(), eload.measure_current()*-1)


########################## CYCLE #############################

def charge_cell(log_filepath, cycle_settings, eload, psu):
	#start the charging
	#Start the data so we don't immediately trigger end conditions
	data = (cycle_settings["charge_end_v"], cycle_settings["charge_a"])
	
	start_charge(cycle_settings["charge_end_v"], cycle_settings["charge_a"], eload, psu)
	charge_start_time = time.time()
	print('Starting Charge: {}\n'.format(time.ctime()), flush=True)
	while (data[1] > cycle_settings["charge_end_a"]):
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - charge_start_time) % cycle_settings["meas_log_int_s"]))
		data = measure_charge(eload, psu)
		FileIO.write_data(log_filepath, data)

def rest_cell(log_filepath, cycle_settings, eload, psu, after_charge = True):
	#rest
	start_rest(eload, psu)
	rest_start_time = time.time()
	
	rest_time_s = 0
	if(after_charge):
		rest_time_s = cycle_settings["rest_after_charge_min"] * 60
	else:
		rest_time_s = cycle_settings["rest_after_discharge_min"] * 60

	print('Starting Rest: {}\n'.format(time.ctime()), flush=True)
  
	while (time.time() - rest_start_time) < rest_time_s:
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - rest_start_time) % cycle_settings["meas_log_int_s"]))
		data = measure_rest(eload)
		FileIO.write_data(log_filepath, data)

def discharge_cell(log_filepath, cycle_settings, eload, psu):
	#start discharge
	start_discharge(cycle_settings["discharge_a"], eload, psu)
	discharge_start_time = time.time()

	data = measure_rest(eload)
	
	#need to add a previous voltage, previous voltage time so that we can compare to better extimate the end time.
	#if we underestimate the end time, that's fine since we'll just get a measurement that is closer next, though there will be delay by the time to gather and write data
	prev_v = data[0]
	prev_v_time = discharge_start_time
	new_data_time = discharge_start_time
	
	print('Starting Discharge: {}\n'.format(time.ctime()), flush=True)

	while (data[0] > cycle_settings["discharge_end_v"]):
		rise = data[0] - prev_v
		run = new_data_time - prev_v_time
		slope = 0
		if(run > 0): #to avoid div by 0 errors
			slope = rise/run
		
		#if slope is 0 or positive (upwards) then we will never hit the intercept.
		#set interpolated wait time to same as meas_log_interval
		interpolated_wait_time = cycle_settings["meas_log_int_s"]
		
		if slope < 0:
			#now do the calculation
			interpolated_wait_time = (cycle_settings["discharge_end_v"] - data[0]) / slope
		
		max_wait_time = cycle_settings["meas_log_int_s"] - ((time.time() - discharge_start_time) % cycle_settings["meas_log_int_s"])
		wait_time = min(max_wait_time, interpolated_wait_time)
		time.sleep(wait_time)
		
		prev_v = data[0]
		prev_v_time = new_data_time
		
		new_data_time = time.time()
		data = measure_discharge(eload)
		FileIO.write_data(log_filepath, data, timestamp = new_data_time)

#run a single cycle on a cell while logging data
def cycle_cell(directory, cell_name, cycle_settings, eload, psu):
	
	#start a new file for the cycle
	headers_list = ['Timestamp', 'Voltage', 'Current']
	filepath = FileIO.start_file(directory, cell_name, headers_list)
	
	print('Starting a cycle: {}\n'.format(time.ctime()) + 
			'Settings:\n' +
			'Cell Name: {}\n'.format(cell_name) + 
			'Charge End Voltage: {}\n'.format(cycle_settings["charge_end_v"]) +
			'Charge Current: {}\n'.format(cycle_settings["charge_a"]) + 
			'Charge End Current: {}\n'.format(cycle_settings["charge_end_a"]) + 
			'Rest After Charge (Minutes): {}\n'.format(cycle_settings["rest_after_charge_min"]) + 
			'Discharge End Voltage: {}\n'.format(cycle_settings["discharge_end_v"]) + 
			'Discharge Current: {}\n'.format(cycle_settings["discharge_a"]) + 
			'Rest After Discharge (Minutes): {}\n'.format(cycle_settings["rest_after_discharge_min"]) + 
			'Log Interval (Seconds): {}\n'.format(cycle_settings["meas_log_int_s"]) + 
			'\n\n', flush=True)
	
	charge_cell(filepath, cycle_settings, eload, psu)
	
	rest_cell(filepath, cycle_settings, eload, psu, after_charge = True)
	
	discharge_cell(filepath, cycle_settings, eload, psu)
	
	rest_cell(filepath, cycle_settings, eload, psu, after_charge = False)
	
	print('Cycle Completed: {}\n'.format(time.ctime()), flush=True)
	
	return

def storage_charge(directory, cell_name, charge_settings, eload, psu):
	
	#start a new file for the cycle
	headers_list = ['Timestamp', 'Voltage', 'Current']
	filepath = FileIO.start_file(directory, cell_name, headers_list)
	
	charge_cell(filepath, charge_settings, eload, psu)
	
	#shut off power supply
	start_rest(eload, psu)
	
	
################################## CYCLE SETTINGS TYPES ################################

def single_cycle():
	#charge then discharge
	cycle_settings = Templates.CycleSettings()
	cycle_settings.get_cycle_settings()
	
	cycle_settings_list = list()
	cycle_settings_list.append(cycle_settings)
	
	return cycle_settings_list

def one_level_continuous_cycles_with_rest():
	#cycles - e.g. charge at 1A, rest, discharge at 5A, rest, repeat X times.
	#get user to enter number of cycles
	cycle_settings = Templates.CycleSettings()
	cycle_settings.get_cycle_settings()
	num_cycles = eg.integerbox(msg = "How Many Cycles?",
								title = "Degradation Cycle", default = 1,
								lowerbound = 0, upperbound = 999)

	cycle_settings_list = list()

	for i in range(num_cycles):
		cycle_settings_list.append(cycle_settings)
	
	return cycle_settings_list

def two_level_continuous_cycles_with_rest():
	#A battery degradation test where the degradation is done at one current
	#and the capacity measurement is done at another current.
	#e.g. 9 degradation cycles at current X, then 1 capacity measurement cycle at current Y.
	
	#Cycle type 1
	cycle_1_settings = Templates.CycleSettings()
	cycle_1_settings.get_cycle_settings("Cycle 1")
	num_cycles_type_1 = eg.integerbox(msg = "How Many Cycles of Type 1?",
											title = "Cycle 1", default = 9,
											lowerbound = 0, upperbound = 99)

	#Cycle type 2
	cycle_2_settings = Templates.CycleSettings()
	cycle_2_settings.get_cycle_settings("Cycle 2")
	num_cycles_type_2 = eg.integerbox(msg = "How Many Cycles of Type 2?",
											title = "Cycle 2", default = 1,
											lowerbound = 0, upperbound = 99)

	#test cycles - charge and discharge how many times?
	num_test_cycles = eg.integerbox(msg = "How Many Test Cycles?",
											title = "Test Cycles", default = 1,
											lowerbound = 0, upperbound = 99)

	cycle_settings_list = list()

	for j in range(num_test_cycles):
		for i in range(num_cycles_type_1):
			cycle_settings_list.append(cycle_1_settings)
		for i in range(num_cycles_type_2):
			cycle_settings_list.append(cycle_2_settings)
	
	return cycle_settings_list


####################################### PROGRAM ######################################
if __name__ == '__main__':
	
	eloads = eq.eLoads()
	psus = eq.powerSupplies()
	
	#get the cell name
	cell_name = eg.enterbox(title = "Test Setup", msg = "Enter the Cell Name\n(Spaces will be replaced with underscores)",
							default = "CELL_NAME", strip = True)
	#replace the spaces to keep file names consistent
	cell_name = cell_name.replace(" ", "_")
	
	#Get a directory to save the file
	directory = FileIO.get_directory("Choose directory to save the cycle logs")
	
	#different cycle types that are available
	available_cycle_types = ("Single Cycle",
							"One Setting Continuous Cycles With Rest",
							"Two Setting Continuous Cycles With Rest")
	
	#choose the cycle type
	msg = "Which cycle type do you want to do?"
	title = "Choose Cycle Type"
	cycle_type = eg.choicebox(msg, title, available_cycle_types)
	
	#gather the list settings based on the cycle type
	cycle_settings_list = list()
	if(cycle_type == available_cycle_types[0]):
		cycle_settings_list = single_cycle()
	elif(cycle_type == available_cycle_types[1]):
		cycle_settings_list = one_level_continuous_cycles_with_rest()
	elif(cycle_type == available_cycle_types[2]):
		cycle_settings_list = two_level_continuous_cycles_with_rest()
	
	#Ask to do a storage charge
	do_a_storage_charge = eg.ynbox(title = "Storage Charge",
									msg = "Do you want to do a storage charge?\n\
											Recommended to do one. Leaving a cell discharged increases\n\
											risk of latent failures due to dendrite growth.")
	
	if(do_a_storage_charge):
		#storage charge settings
		#always do a storage charge for cell safety!
		storage_charge_settings = Templates.ChargeSettings()
		storage_charge_settings.get_cycle_settings("Storage Charge")
	
	#Now we choose PSU and Eload to use
	eload = eloads.choose_eload()
	psu = psus.choose_psu()
	
	init_instruments(eload, psu)
	
	#cycle x times
	cycle_num = 0
	for cycle_settings in cycle_settings_list:
		print("Cycle {} Starting".format(cycle_num), flush=True)
		try:
			cycle_cell(directory, cell_name, cycle_settings.settings, eload, psu)
		except KeyboardInterrupt:
			eload.toggle_output(False)
			psu.toggle_output(False)
			exit()
		cycle_num += 1
	
	if(do_a_storage_charge):
		#storage charge
		#always do a storage charge for cell safety!
		try:
			storage_charge(directory, cell_name, storage_charge_settings.settings, eload, psu)
		except KeyboardInterrupt:
			eload.toggle_output(False)
			psu.toggle_output(False)
			exit()
