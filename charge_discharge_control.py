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

 
def init_eload(eload):
	eload.toggle_output(False)
	eload.remote_sense(True)
	eload.set_current(0)
	
def init_psu(psu):
	psu.toggle_output(False)
	psu.remote_sense(True)
	psu.set_voltage(0)
	psu.set_current(0)

####################### TEST CONTROL #####################

def start_charge(end_voltage, constant_current, psu):
	psu.set_voltage(end_voltage)
	time.sleep(0.01)
	psu.set_current(constant_current)
	time.sleep(0.01)
	psu.toggle_output(True)

def end_charge(psu):
	psu.toggle_output(False)
	psu.set_current(0)

def start_discharge(constant_current, eload):
	eload.set_current(constant_current)
	time.sleep(0.01)
	eload.toggle_output(True)

def end_discharge(eload):
	eload.toggle_output(False)
	eload.set_current(0)

######################### MEASURING ######################

def measure_rest(v_meas_eq):
	#return current as 0
	return (v_meas_eq.measure_voltage(), 0)

def measure_charge(v_meas_eq, psu):
	#return current from power supply
	return (v_meas_eq.measure_voltage(), psu.measure_current())

def measure_discharge(v_meas_eq, eload):
	#return current from eload (as negative)
	return (v_meas_eq.measure_voltage(), eload.measure_current()*-1)


########################## CHARGE, DISCHARGE, REST #############################

def charge_cell(log_filepath, cycle_settings, psu, v_meas_eq):
	#start the charging
	#Start the data so we don't immediately trigger end conditions
	data = (cycle_settings["charge_end_v"], cycle_settings["charge_a"])
	
	start_charge(cycle_settings["charge_end_v"], cycle_settings["charge_a"], psu)
	charge_start_time = time.time()
	print('Starting Charge: {}\n'.format(time.ctime()), flush=True)
	while (data[1] > cycle_settings["charge_end_a"]):
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - charge_start_time) % cycle_settings["meas_log_int_s"]))
		data = measure_charge(v_meas_eq, psu)
		FileIO.write_data(log_filepath, data)
		
	end_charge(psu)

def rest_cell(log_filepath, cycle_settings, v_meas_eq, after_charge = True):
	#rest - do nothing for X time but continue monitoring voltage
	rest_start_time = time.time()
	
	rest_time_s = 0
	if(after_charge):
		rest_time_s = cycle_settings["rest_after_charge_min"] * 60
	else:
		rest_time_s = cycle_settings["rest_after_discharge_min"] * 60

	print('Starting Rest: {}\n'.format(time.ctime()), flush=True)
  
	while (time.time() - rest_start_time) < rest_time_s:
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - rest_start_time) % cycle_settings["meas_log_int_s"]))
		data = measure_rest(v_meas_eq)
		FileIO.write_data(log_filepath, data)

def discharge_cell(log_filepath, cycle_settings, eload, v_meas_eq):
	#start discharge
	start_discharge(cycle_settings["discharge_a"], eload)
	discharge_start_time = time.time()

	data = measure_rest(v_meas_eq)
	
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
		data = measure_discharge(v_meas_eq, eload)
		FileIO.write_data(log_filepath, data, timestamp = new_data_time)
	
	end_discharge(eload)



################################## SETTING CYCLE, CHARGE, DISCHARGE ############################

#run a single cycle on a cell while logging data
def cycle_cell(directory, cell_name, cycle_settings, eload, psu, v_meas_eq = None):
	#v_meas_eq is the measurement equipment to use for measuring the voltage.
	#the device MUST have a measure_voltage() method that returns a float with units of Volts.
	
	if v_meas_eq == None:
		#use eload by default since they typically have better accuracy
		v_meas_eq = eload
	
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
	
	charge_cell(filepath, cycle_settings, psu, v_meas_eq)
	
	rest_cell(filepath, cycle_settings, v_meas_eq, after_charge = True)
	
	discharge_cell(filepath, cycle_settings, eload, v_meas_eq)
	
	rest_cell(filepath, cycle_settings, v_meas_eq, after_charge = False)
	
	print('Cycle Completed: {}\n'.format(time.ctime()), flush=True)
	
	return

def charge_cycle(directory, cell_name, charge_settings, psu, v_meas_eq = None):

	if v_meas_eq == None:
		v_meas_eq = psu
		
	#start a new file for the cycle
	headers_list = ['Timestamp', 'Voltage', 'Current']
	filepath = FileIO.start_file(directory, cell_name, headers_list)
	
	charge_cell(filepath, charge_settings, psu, v_meas_eq)
	
def discharge_cycle(directory, cell_name, charge_settings, eload, v_meas_eq = None):

	if v_meas_eq == None:
		v_meas_eq = eload
		
	#start a new file for the cycle
	headers_list = ['Timestamp', 'Voltage', 'Current']
	filepath = FileIO.start_file(directory, cell_name, headers_list)
	
	discharge_cell(filepath, charge_settings, eload, v_meas_eq)
	
	
################################## CHOOSING CYCLE SETTINGS TYPES ################################

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

def charge_only_cycle_info():
	cycle_settings_list = list()
	
	charge_only_settings = Templates.ChargeSettings()
	charge_only_settings.get_cycle_settings("Charge Only")
	
	cycle_settings_list.append(charge_only_settings)
	
	return cycle_settings_list
	
def discharge_only_cycle_info():
	cycle_settings_list = list()
	
	discharge_only_settings = Templates.DischargeSettings()
	discharge_only_settings.get_cycle_settings("Discharge Only")
	
	cycle_settings_list.append(discharge_only_settings)
	
	return cycle_settings_list

def ask_storage_charge():
	return eg.ynbox(title = "Storage Charge",
					msg = "Do you want to do a storage charge?\n\
							Recommended to do one. Leaving a cell discharged increases\n\
							risk of latent failures due to dendrite growth.")

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
	cycle_types = Templates.CycleTypes.cycle_types
	
	#choose the cycle type
	msg = "Which cycle type do you want to do?"
	title = "Choose Cycle Type"
	cycle_type = eg.choicebox(msg, title, list(cycle_types.keys()))
	
	do_a_storage_charge = False
	
	#gather the list settings based on the cycle type
	cycle_settings_list = list()
	if(cycle_type == list(cycle_types.keys())[0]):
		cycle_settings_list = single_cycle()
		do_a_storage_charge = ask_storage_charge()
	
	elif(cycle_type == list(cycle_types.keys())[1]):
		cycle_settings_list = one_level_continuous_cycles_with_rest()
		do_a_storage_charge = ask_storage_charge()
	
	elif(cycle_type == list(cycle_types.keys())[2]):
		cycle_settings_list = two_level_continuous_cycles_with_rest()
		do_a_storage_charge = ask_storage_charge()
	
	elif(cycle_type == list(cycle_types.keys())[3]):
		cycle_settings_list = charge_only_cycle_info()
	
	elif(cycle_type == list(cycle_types.keys())[4]):
		cycle_settings_list = discharge_only_cycle_info()
	
	load_required = cycle_types[cycle_type]['load_req']
	supply_required = cycle_types[cycle_type]['supply_req']
	
	#extend adds two lists, append adds a single element to a list. We want extend here since charge_only_cycle() returns a list.
	if do_a_storage_charge:
		cycle_settings_list.extend(charge_only_cycle_info())
	
	#Separate voltage measurement device
	msg = "Do you want to use a separate device to measure voltage?"
	title = "Voltage Measurement Device"
	separate_v_meas = eg.ynbox(msg, title)
	dmm = None
	
	#Now we choose the PSU, Eload, and dmm to use
	if load_required:	
		eload = eloads.choose_eload()
		init_eload(eload)
	if supply_required:
		psu = psus.choose_psu()
		init_psu(psu)
	if separate_v_meas:
		dmms = eq.dmms()
		dmm = dmms.choose_dmm()
		#test voltage measurement to ensure everything is set up correctly
		#often the first measurement takes longer as it needs to setup range, NPLC
		#This also gets it setup to the correct range.
		#TODO - careful of batteries that will require a range switch during the charge
		#	  - this could lead to a measurement delay. 6S happens to cross the 20V range.
		test_volt = dmm.measure_voltage()
	
	#cycle x times
	cycle_num = 0
	for cycle_settings in cycle_settings_list:
		print("Cycle {} Starting".format(cycle_num), flush=True)
		try:
			#Charge only - only using the power supply
			if isinstance(cycle_settings, Templates.ChargeSettings):
				charge_cycle(directory, cell_name, cycle_settings.settings, psu, v_meas_eq = dmm)
				
			#Discharge only - only using the eload
			elif isinstance(cycle_settings, Templates.DischargeSettings):
				discharge_cycle(directory, cell_name, cycle_settings.settings, eload, v_meas_eq = dmm)
			
			#Cycle the cell - using both psu and eload
			else:
				cycle_cell(directory, cell_name, cycle_settings.settings, eload, psu, v_meas_eq = dmm)
			
		except KeyboardInterrupt:
			eload.toggle_output(False)
			psu.toggle_output(False)
			exit()
		cycle_num += 1
	
	print("All Cycles Completed")
	