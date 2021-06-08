#Python Script for controlling the charge and discharge
#tests of a battery with Eload and Power supply

import equipment as eq
from datetime import datetime
import time
import pandas as pd
import easygui as eg
import tkinter as tk
import os
import Templates


#eload = Eload_BK8600.BK8600()
eloads = eq.eLoads()
eload = eloads.choose_eload()
#psu = PSU_SPD1000.SPD1000()
psus = eq.powerSupplies()
psu = psus.choose_psu()
 
def init_instruments():
	eload.remote_sense(True)
	psu.remote_sense(True)

####################### TEST CONTROL #####################

def start_charge(end_voltage, constant_current):
	eload.toggle_output(False)
	time.sleep(0.1)
	psu.set_voltage(end_voltage)
	time.sleep(0.1)
	psu.set_current(constant_current)
	time.sleep(0.1)
	psu.toggle_output(True)
	
def start_discharge(constant_current):
	psu.toggle_output(False)
	time.sleep(0.1)
	eload.set_current(constant_current)
	time.sleep(0.1)
	eload.toggle_output(True)

def start_rest():
	psu.toggle_output(False)
	time.sleep(0.1)
	eload.toggle_output(False)

######################### MEASURING ######################

def measure_rest():
	#return current as 0, measure from eload (more accurate)
	return (eload.measure_voltage(), 0)

def measure_charge():
	#return current from power supply, voltage from eload`
	return (eload.measure_voltage(), psu.measure_current())

def measure_discharge():
	#return current from eload (as negative), voltage from eload
	return (eload.measure_voltage(), eload.measure_current()*-1)

####################### FILE IO ###########################

def get_directory(type):
	root = tk.Tk()
	root.withdraw()
	dir = tk.filedialog.askdirectory(
		title='Select location to save {} data files'.format(type))
	root.destroy()
	return dir

def write_line(filepath, list_line):
	#read into pandas dataframe - works, in quick to code
	#and is likely easy to extend - but one line doesn't really need it
	df = pd.DataFrame(list_line).T
	
	#save to csv - append, no index, no header
	df.to_csv(filepath, header=False, mode='a', index=False)

def start_file(directory, name):
	dt = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
	filename = '{cell_name} {date}.csv'.format(\
				cell_name = name, date = dt)
	
	filepath = os.path.join(directory, filename)
	
	#Headers
	#create a list
	headers = list()
	headers.append('Timestamp')
	headers.append('Voltage')
	headers.append('Current')
	
	write_line(filepath, headers)
	
	return filepath

def gather_and_write_data(filepath, iv_data, printout=False):
	data = list()
	
	#add timestamp
	data.append(time.time())
	data.append(iv_data[0])
	data.append(iv_data[1])
	
	if(printout):
		print(data)
	
	write_line(filepath, data)

########################## CYCLE #############################

#run a single cycle on a cell while logging data
def cycle_cell(dir, cell_name, cycle_settings):
	
	#start a new file for the cycle
	filepath = start_file(dir, cell_name)
	
	rest_after_charge_s = cycle_settings["rest_after_charge_min"] * 60
	rest_after_discharge_s = cycle_settings["rest_after_discharge_min"] * 60
	
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
			'\n\n')
	
	data = (cycle_settings["charge_end_v"], cycle_settings["charge_a"])
	
	#start the charging
	start_charge(cycle_settings["charge_end_v"], cycle_settings["charge_a"])
	charge_start_time = time.time()
	print('Starting Charge: {}\n'.format(time.ctime()))
	while (data[1] > cycle_settings["charge_end_a"]):
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - charge_start_time) % cycle_settings["meas_log_int_s"]))
		data = measure_charge()
		gather_and_write_data(filepath, data)
	
	#rest
	start_rest()
	rest_start_time = time.time()
	print('Starting Rest After Charge: {}\n'.format(time.ctime()))
	while (time.time() - rest_start_time) < rest_after_charge_s:
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - rest_start_time) % cycle_settings["meas_log_int_s"]))
		data = measure_rest()
		gather_and_write_data(filepath, data)
	
	#start discharge
	start_discharge(cycle_settings["discharge_a"])
	discharge_start_time = time.time()
	print('Starting Discharge: {}\n'.format(time.ctime()))
	while (data[0] > cycle_settings["discharge_end_v"]):
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - discharge_start_time) % cycle_settings["meas_log_int_s"]))
		data = measure_discharge()
		gather_and_write_data(filepath, data)
	
	#rest
	start_rest()
	rest_start_time = time.time()
	print('Starting Rest After Discharge: {}\n'.format(time.ctime()))
	while (time.time() - rest_start_time) < rest_after_discharge_s:
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - rest_start_time) % cycle_settings["meas_log_int_s"]))
		data = measure_rest()
		gather_and_write_data(filepath, data)
	
	print('Cycle Completed: {}\n'.format(time.ctime()))
	
	return

def storage_charge(dir, cell_name, charge_settings):
	
	#start a new file for the cycle
	filepath = start_file(dir, cell_name)
	
	#set data to not immediately close the program
	data = (charge_settings["charge_end_v"], charge_settings["charge_a"])
	
	#start the storage charging
	start_charge(charge_settings["charge_end_v"], charge_settings["charge_a"])
	charge_start_time = time.time()
	print('Starting Storage Charge: {}\n'.format(time.ctime()))
	while (data[1] > charge_settings["charge_end_a"]):
		time.sleep(charge_settings["meas_log_int_s"] - ((time.time() - charge_start_time) % charge_settings["meas_log_int_s"]))
		data = measure_charge()
		gather_and_write_data(filepath, data)
	
	#shut off power supply
	start_rest()
	
	
################################## CYCLE SETTINGS TYPES ################################

def single_cycle():
	#charge then discharge
	cycle_settings = Templates.CycleSettings()
	cycle_settings.get_cycle_settings("Cycle")
	
	cycle_settings_list = list()
	cycle_settings_list.append(cycle_settings)
	
	return cycle_settings_list

def one_level_continuous_cycles_with_rest():
	#cycles - e.g. charge at 1A, rest, discharge at 5A, rest, repeat X times.
	#get user to enter number of cycles
	cycle_settings = Templates.CycleSettings()
	cycle_settings.get_cycle_settings("Cycle")
	num_cycles = eg.integerbox(msg = "How Many Cycles?",
								title = "Degradation Cycle", default = 1,
								lowerbound = 0, upperbound = 999)

	cycle_settings_list = list()

	for i in range(num_cycles):
		cycle_settings_list.append(capacity_cycle_settings)
	
	return cycle_settings_list

def two_level_continuous_cycles_with_rest():
	#A battery degradation test where the degradation is done at one current
	#and the capacity measurement is done at another current.
	#e.g. 9 degradation cycles, then 1 capacity measurement cycle.
	
	#degradation cycles
	#get user to enter number of cycles
	degradation_cycle_settings = Templates.CycleSettings()
	degradation_cycle_settings.get_cycle_settings("Degradation")
	num_degradation_cycles = eg.integerbox(msg = "How Many Degradation Cycles?",
											title = "Degradation Cycle", default = 9,
											lowerbound = 0, upperbound = 99)

	#capacity measurement cycles
	capacity_cycle_settings = Templates.CycleSettings()
	capacity_cycle_settings.get_cycle_settings("Capacity")
	num_capacity_cycles = eg.integerbox(msg = "How Many Capacity Cycles?",
											title = "Capacity Cycle", default = 1,
											lowerbound = 0, upperbound = 99)

	#test cycles - X discharge, Y charge, how many times?
	num_test_cycles = eg.integerbox(msg = "How Many Test Cycles?",
											title = "Test Cycles", default = 1,
											lowerbound = 0, upperbound = 99)

	cycle_types = ("Degradation", "Capacity")
	first_cycle = eg.buttonbox(msg = "Which cycle type should be completed first?", title = "First Cycle",
								choices = cycle_types, default_choice = cycle_types[0])

	cycle_settings_list = list()

	for j in range(num_test_cycles):
		if(first_cycle == "Degradation"):
			for i in range(num_degradation_cycles):
				cycle_settings_list.append(degradation_cycle_settings)
			for i in range(num_capacity_cycles):
				cycle_settings_list.append(capacity_cycle_settings)
		elif(first_cycle == "Capacity"):
			for i in range(num_degradation_cycles):
				cycle_settings_list.append(capacity_cycle_settings)
			for i in range(num_capacity_cycles):
				cycle_settings_list.append(degradation_cycle_settings)
	
	return cycle_settings_list



####################################### PROGRAM ######################################
if __name__ == '__main__':
	#get the cell name
	cell_name = eg.enterbox(title = "Test Setup", msg = "Enter the Cell Name\n(Spaces will be replaced with underscores)",
							default = "CELL_NAME", strip = True)
	#replace the spaces to keep file names consistent
	cell_name = cell_name.replace(" ", "_")
	
	#Get a directory to save the file
	directory = get_directory("Cycle")
	init_instruments()
	
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

	#cycle x times
	cycle_num = 0
	for cycle_settings in cycle_settings_list:
		print("Cycle {} Starting".format(cycle_num))
		try:
			cycle_cell(directory, cell_name, cycle_settings.settings)
		except KeyboardInterrupt:
			eload.toggle_output(False)
			psu.toggle_output(False)
			exit()
		cycle_num += 1
	
	if(do_a_storage_charge):
		#storage charge
		#always do a storage charge for cell safety!
		try:
			storage_charge(directory, cell_name, storage_charge_settings.settings)
		except KeyboardInterrupt:
			eload.toggle_output(False)
			psu.toggle_output(False)
			exit()
	