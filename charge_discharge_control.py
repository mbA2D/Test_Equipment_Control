#Python Script for controlling the charge and discharge
#tests of a battery with Eload and Power supply

import Eload_BK8600
import PSU_SPD1000
from datetime import datetime
import time
import pandas as pd
import easygui as eg
import tkinter as tk
import os

eload = Eload_BK8600.BK8600()
psu = PSU_SPD1000.SPD1000()

def init_instruments():
	eload.remote_sense(True)
	psu.remote_sense(True)

####################### TEST CONTROL #####################

def start_charge(end_voltage, constant_current):
	eload.toggle_output(False)
	psu.set_voltage(end_voltage)
	time.sleep(0.1)
	psu.set_current(constant_current)
	time.sleep(0.1)
	psu.toggle_output(True)
	
def start_discharge(constant_current):
	psu.toggle_output(False)
	eload.set_current(constant_current)
	time.sleep(0.1)
	eload.toggle_output(True)

def start_rest():
	psu.toggle_output(False)
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

def get_directory():
	root = tk.Tk()
	root.withdraw()
	dir = tk.filedialog.askdirectory(
		title='Select location to save Discharge data files')
	root.destroy()
	return dir

def write_line(filepath, list_line):
	#read into pandas dataframe - works, in quick to code
	#and is likely easy to extend - but one line doesn't really need it
	df = pd.DataFrame(list_line).T
	
	#save to csv - append, no index, no header
	df.to_csv(filepath, header=False, mode='a', index=False)

def start_file(directory, name, cycle):
	dt = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
	filename = '{cell_name} {cell_cycle} {date}.csv'.format(\
				cell_name = name, cell_cycle = cycle, date = dt)
	
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
def cycle_cell(dir, cell_name, cycle_num,
				end_V_charge, cc_charge, end_A_charge,
				rest_after_charge_mins, 
				end_V_discharge, cc_discharge,
				rest_after_discharge_mins,
				log_interval_s = 1):
	
	#start a new file for the cycle
	filepath = start_file(dir, cell_name, cycle_num)
	
	rest_after_charge_s = rest_after_charge_mins * 60
	rest_after_discharge_s = rest_after_discharge_mins * 60
	
	print('Starting a cycle: {}\n'.format(time.ctime()) + 
			'Settings:\n' +
			'Cell Name: {}\n'.format(cell_name) + 
			'Cycle Number: {}\n'.format(cycle_num) + 
			'Charge End Voltage: {}\n'.format(end_V_charge) +
			'Charge Current: {}\n'.format(cc_charge) + 
			'Charge End Current: {}\n'.format(end_A_charge) + 
			'Rest After Charge (Minutes): {}\n'.format(rest_after_charge_mins) + 
			'Discharge End Voltage: {}\n'.format(end_V_discharge) + 
			'Discharge Current: {}\n'.format(cc_discharge) + 
			'Rest After Discharge (Minutes): {}\n'.format(rest_after_discharge_mins) + 
			'Log Interval (Seconds): {}\n'.format(log_interval_s) + 
			'\n\n')
	
	#start the charging
	start_charge(end_V_charge, cc_charge)
	data = (end_V_charge, cc_charge)
	charge_start_time = time.time()
	print('Starting Charge: {}\n'.format(time.ctime()))
	while (data[1] > end_A_charge):
		time.sleep(log_interval_s - ((time.time() - charge_start_time) % log_interval_s))
		data = measure_charge()
		gather_and_write_data(filepath, data)
	
	#rest
	start_rest()
	rest_start_time = time.time()
	print('Starting Rest After Charge: {}\n'.format(time.ctime()))
	while (time.time() - rest_start_time) < rest_after_charge_s:
		time.sleep(log_interval_s - ((time.time() - rest_start_time) % log_interval_s))
		data = measure_rest()
		gather_and_write_data(filepath, data)
	
	#start discharge
	start_discharge(cc_discharge)
	discharge_start_time = time.time()
	print('Starting Discharge: {}\n'.format(time.ctime()))
	while (data[0] > end_V_discharge):
		time.sleep(log_interval_s - ((time.time() - discharge_start_time) % log_interval_s))
		data = measure_discharge()
		gather_and_write_data(filepath, data)
	
	
	
	#rest
	start_rest()
	rest_start_time = time.time()
	print('Starting Rest After Discharge: {}\n'.format(time.ctime()))
	while (time.time() - rest_start_time) < rest_after_discharge_s:
		time.sleep(log_interval_s - ((time.time() - rest_start_time) % log_interval_s))
		data = measure_rest()
		gather_and_write_data(filepath, data)
	
	print('Cycle Completed: {}\n'.format(time.ctime()))
	
	return


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


####################### Program #########################

#get all the info for the test in a multenterbox
msg = "Enter test info"
title = "Battery Test Setup"
field_names = ["Unique Cell Name", 
				"Charge end voltage",
				"Charge Current",
				"Charge End Current",
				"Rest After Charge (Minutes)", 
				"Discharge End Voltage",
				"Discharge Current",
				"Rest After Discharge (Minutes)",
				"Number of cycles",
				"Measurement Logging Interval (Seconds)"]
default_text = ["CELL_NAME",
				"4.2",
				"7.5",
				"0.3",
				"20",
				"2.5",
				"30",
				"20",
				"1",
				"1"]

valid_entries = False

while valid_entries == False:
	entries = eg.multenterbox(msg, title, field_names, default_text)
	valid_entries = check_user_entry(entries)

#Ask user to double check the entries
valid_entries = False
msg = "Confirm these values are correct"

while valid_entries == False:
	entries = eg.multenterbox(msg, title, field_names, entries)
	valid_entries = check_user_entry(entries)

#Get a directory to save the file
directory = get_directory()
init_instruments()

for cycle in range(int(entries[8])):
	try:
		cycle_cell(directory, entries[0], cycle,
				float(entries[1]), float(entries[2]), float(entries[3]),
				float(entries[4]), float(entries[5]), float(entries[6]),
				float(entries[7]), log_interval_s = float(entries[9]))
	except KeyboardInterrupt:
		eload.toggle_output(False)
		psu.toggle_output(False)
		exit()
		