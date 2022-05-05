#Python Script for controlling the charge and discharge
#tests of a battery with Eload and Power supply

import equipment as eq
from datetime import datetime
import time
import pandas as pd
import easygui as eg
import os
import queue
import traceback

import Templates
import FileIO
import jsonIO


##################### EQUIPMENT SETUP ####################

def init_eload(eload):
	eload.toggle_output(False)
	eload.set_current(0)
	
def init_psu(psu):
	psu.toggle_output(False)
	psu.set_voltage(0)
	psu.set_current(0)

def init_dmm_v(dmm):
	test_v = dmm.measure_voltage()
	#test voltage measurement to ensure everything is set up correctly
	#often the first measurement takes longer as it needs to setup range, NPLC
	#This also gets it setup to the correct range.
	#TODO - careful of batteries that will require a range switch during the charge
	#	  - this could lead to a measurement delay. 6S happens to cross the 20V range.

def init_dmm_i(dmm):
	test_i = dmm.measure_current()
	#test measurement to ensure everything is set up correctly
	#and the fisrt measurement which often takes longer is out of the way

def initialize_connected_equipment(eq_dict):
	if eq_dict['eload'] != None:	
		init_eload(eq_dict['eload'])
	if eq_dict['psu'] != None:
		init_psu(eq_dict['psu'])
	if eq_dict['dmm_v'] != None:
		init_dmm_v(eq_dict['dmm_v'])
	if eq_dict['dmm_i'] != None:
		init_dmm_i(eq_dict['dmm_i'])

def disable_equipment(eq_dict):
	if eq_dict['psu'] != None:
		eq_dict['psu'].set_current(0) #Turn current to 0 first to try and eliminate arcing in a relay inside an eload that disconnects the output
		eq_dict['psu'].toggle_output(False)
	if eq_dict['eload'] != None:
		eq_dict['eload'].set_current(0) #Turn current to 0 first to try and eliminate arcing in a relay inside a power supply that disconnects the output
		eq_dict['eload'].toggle_output(False)

####################### TEST CONTROL #####################

def start_charge(end_voltage, constant_current, eq_dict):
	eq_dict['psu'].set_voltage(end_voltage)
	time.sleep(0.01)
	eq_dict['psu'].set_current(constant_current)
	time.sleep(0.01)
	eq_dict['psu'].toggle_output(True)

def start_discharge(constant_current, eq_dict):
	eq_dict['eload'].set_current(constant_current)
	time.sleep(0.01)
	eq_dict['eload'].toggle_output(True)
	
def start_step(step_settings, eq_dict):
	#This function will set all the supplies to the settings given in the step
	
	#CURRENT DRIVEN
	if step_settings["drive_style"] == 'current_a':
		if step_settings["drive_value"] > 0:
			#charge - turn off eload first if connected
			disable_equipment(eq_dict)
			if eq_dict['psu'] != None:
				eq_dict['psu'].set_current(step_settings["drive_value"])
				eq_dict['psu'].set_voltage(step_settings["drive_value_other"])
				eq_dict['psu'].toggle_output(True)
			else:
				print("No PSU Connected. Can't Charge! Exiting.")
				return False
		elif step_settings["drive_value"] < 0:
			#discharge
			disable_equipment(eq_dict)
			if eq_dict['eload'] != None:
				eq_dict['eload'].set_current(step_settings["drive_value"])
				eq_dict['eload'].toggle_output(True)
				#we're in constant current mode - can't set a voltage.
			else:
				print("No Eload Connected. Can't Discharge! Exiting.")
				return False
		elif step_settings["drive_value"] == 0:
			#rest
			disable_equipment(eq_dict)
	
	#VOLTAGE DRIVEN
	elif step_settings["drive_style"] == 'voltage_v':
		#positive current
		if step_settings["drive_value_other"] >= 0:
			disable_equipment(eq_dict) #turn off eload
			if eq_dict['psu'] != None:
				eq_dict['psu'].set_current(step_settings["drive_value_other"])
				eq_dict['psu'].set_voltage(step_settings["drive_value"])
				eq_dict['psu'].toggle_output(True)
		#TODO - needs CV mode on eloads
		else:
			print("Voltage Driven Step Not Yet Implemented for negative current. Exiting.")
			#Ensure everything is off since not yet implemented.
			disable_equipment(eq_dict)
			return False
	
	#NOT DRIVEN
	elif step_settings["drive_style"] == 'none':
		#Ensure all sources and loads are off.
		disable_equipment(eq_dict)
	
	
	#return True for a successful step start.
	return True

def evaluate_end_condition(step_settings, data, data_in_queue):
	#evaluates different end conditions (voltage, current, time)
	#returns true if the end condition has been met (e.g. voltage hits lower bound, current hits lower bound, etc.)
	#also returns true if any of the safety settings have been exceeded
	
	#REQUEST TO END
	if end_signal(data_in_queue):
		return 'end_request'
	
	#SAFETY SETTINGS
	#Voltage and current limits are always active
	if (data["Voltage"] < step_settings["safety_min_voltage_v"] or 
	    data["Voltage"] > step_settings["safety_max_voltage_v"] or 
	    data["Current"] < step_settings["safety_min_current_a"] or
	    data["Current"] > step_settings["safety_max_current_a"]):
	
		return 'safety_condition'
		
	if (step_settings["safety_max_time_s"] > 0 and 
        data["Data_Timestamp_From_Step_Start"] > step_settings["safety_max_time_s"]):
		
		return 'safety_condition'
			
	
	#END CONDITIONS
	if step_settings["end_style"] == 'current_a':
		left_comparator = data["Current"]
	elif step_settings["end_style"] == 'voltage_v':
		left_comparator = data["Voltage"]
	elif step_settings["end_style"] == 'time_s':
		left_comparator = data["Data_Timestamp_From_Step_Start"]
	
	if step_settings["end_condition"] == 'greater':
		if left_comparator > step_settings["end_value"]:
			return 'end_condition'
		else:
			return 'none'
	elif step_settings["end_condition"] == 'lesser':
		#For positive current less than value endpoint, also check the voltage to be close to the end voltage
		if step_settings["end_style"] == 'current_a' and step_settings["drive_style"] == 'voltage_v' and step_settings["end_value"] > 0:
			if data["Voltage"] > 0.99*step_settings["end_value_other"] and left_comparator < step_settings["end_value"]:
				return 'end_condition'
		elif left_comparator < step_settings["end_value"]:
			return 'end_condition'
		else:
			return 'none'
	
	#return True so that we end the step if the settings were incorrectly configured.
	return 'settings'


######################### MEASURING ######################

def measure_battery(eq_dict, data_out_queue = None):
	data_dict = {'type': 'measurement', 'data': {}}
	data_dict['data']["Voltage"] = 0
	if eq_dict['dmm_v'] != None:
		data_dict['data']["Voltage"] = eq_dict['dmm_v'].measure_voltage()
	data_dict['data']["Current"] = 0
	if eq_dict['dmm_i'] != None:
		data_dict['data']["Current"] = eq_dict['dmm_i'].measure_current()
	data_dict['data']["Data_Timestamp"] = time.time()
	
	#Send voltage and current to be displayed in the main test window
	if data_out_queue != None:
		#add the new data to the output queue
		data_out_queue.put_nowait(data_dict)
	
	#Now, measure all the extra devices that were added to the channel - these being less time-critical.
	prefix_list = ['v', 'i', 't']
	#start at index 0 and keep increasing until we get a KeyError.
	for prefix in prefix_list:
		index = 0
		try:
			while index < 100:
				dev_name = 'dmm_{}{}'.format(prefix, index)
				measurement = 0
				if prefix == 'v':
					measurement = eq_dict[dev_name].measure_voltage()
				elif prefix == 'i':
					measurement = eq_dict[dev_name].measure_current()
				elif prefix == 't':
					measurement = eq_dict[dev_name].measure_temperature()
				data_dict['data'][dev_name] = measurement
				index = index + 1
		except KeyError:
			continue
	
	return data_dict['data']


########################## CHARGE, DISCHARGE, REST #############################

def end_signal(data_in_queue):
	end_signal = False
	try:
		signal = data_in_queue.get_nowait()
		if signal == 'stop':
			end_signal = True
	except queue.Empty:
		pass
	return end_signal

def charge_cell(log_filepath, cycle_settings, eq_dict, data_out_queue = None, data_in_queue = None, ch_num = None):
	#start the charging
	#Start the data so we don't immediately trigger end conditions
	data = {}
	data["Voltage"] = cycle_settings["charge_end_v"]
	data["Current"] = cycle_settings["charge_a"]
	data["Data_Timestamp"] = time.time()
	
	start_charge(cycle_settings["charge_end_v"], cycle_settings["charge_a"], eq_dict)
	charge_start_time = time.time()
	print('CH{} - Starting Charge: {}\n'.format(ch_num, time.ctime()), flush=True)
	
	end_reason = 'end_condition'
	if end_signal(data_in_queue):
		end_reason = 'end_requested'
	while ((data["Current"] > cycle_settings["charge_end_a"] or data["Voltage"] < 0.99*cycle_settings["charge_end_v"]) and end_reason != 'end_requested'):
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - charge_start_time) % cycle_settings["meas_log_int_s"]))
		data.update(measure_battery(eq_dict, data_out_queue = data_out_queue))
		if end_signal(data_in_queue):
			end_reason = 'end_requested'
		FileIO.write_data(log_filepath, data)
		
	disable_equipment(eq_dict)
	return end_reason

def idle_cell(eq_dict, data_out_queue = None, data_in_queue = None):
	#Measures voltage (and current if available) when no other process is running to have live voltage updates
	while not end_signal(data_in_queue):
		measure_battery(eq_dict, data_out_queue = data_out_queue)
		time.sleep(1)

def rest_cell(log_filepath, cycle_settings, eq_dict, after_charge = True, data_out_queue = None, data_in_queue = None, ch_num = None):
	#rest - do nothing for X time but continue monitoring voltage
	rest_start_time = time.time()
	
	rest_time_s = 0
	if(after_charge):
		rest_time_s = cycle_settings["rest_after_charge_min"] * 60
	else:
		rest_time_s = cycle_settings["rest_after_discharge_min"] * 60

	print('CH{} - Starting Rest: {}\n'.format(ch_num, time.ctime()), flush=True)
	data = {}
	
	end_reason = 'end_condition'
	if end_signal(data_in_queue):
		end_reason = 'end_requested'
	while ((time.time() - rest_start_time) < rest_time_s) and end_reason != 'end_requested':
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - rest_start_time) % cycle_settings["meas_log_int_s"]))
		data.update(measure_battery(eq_dict, data_out_queue = data_out_queue))
		if end_signal(data_in_queue):
			end_reason = 'end_requested'
		FileIO.write_data(log_filepath, data)
	return end_reason

def discharge_cell(log_filepath, cycle_settings, eq_dict, data_out_queue = None, data_in_queue = None, ch_num = None):
	#start discharge
	start_discharge(cycle_settings["discharge_a"], eq_dict)
	discharge_start_time = time.time()

	data = dict()
	data.update(measure_battery(eq_dict))
	
	#need to add a previous voltage, previous voltage time so that we can compare to better extimate the end time.
	#if we underestimate the end time, that's fine since we'll just get a measurement that is closer next, though there will be delay by the time to gather and write data
	prev_v = data["Voltage"]
	prev_v_time = discharge_start_time
	data["Data_Timestamp"] = discharge_start_time
	
	print('CH{} - Starting Discharge: {}\n'.format(ch_num, time.ctime()), flush=True)
	
	end_reason = 'end_condition'
	if end_signal(data_in_queue):
		end_reason = 'end_requested'
	while (data["Voltage"] > cycle_settings["discharge_end_v"]) and end_reason != 'end_requested':
		rise = data["Voltage"] - prev_v
		run = data["Data_Timestamp"] - prev_v_time
		slope = 0
		if(run > 0): #to avoid div by 0 errors
			slope = rise/run
		
		#if slope is 0 or positive (upwards) then we will never hit the intercept.
		#set interpolated wait time to same as meas_log_interval
		interpolated_wait_time = cycle_settings["meas_log_int_s"]
		
		if slope < 0:
			#now do the calculation
			interpolated_wait_time = (cycle_settings["discharge_end_v"] - data["Voltage"]) / slope
		
		max_wait_time = cycle_settings["meas_log_int_s"] - ((time.time() - discharge_start_time) % cycle_settings["meas_log_int_s"])
		wait_time = min(max_wait_time, interpolated_wait_time)
		time.sleep(wait_time)
		
		prev_v = data["Voltage"]
		prev_v_time = data["Data_Timestamp"]
		
		data.update(measure_battery(eq_dict, data_out_queue = data_out_queue))
		if end_signal(data_in_queue):
			end_reason = 'end_requested'
		FileIO.write_data(log_filepath, data)
	
	disable_equipment(eq_dict)
	return end_reason

def step_cell(log_filepath, step_settings, eq_dict, data_out_queue = None, data_in_queue = None):
	
	if start_step(step_settings, eq_dict):
		
		step_start_time = time.time()
		
		data = dict()
		data.update(measure_battery(eq_dict))
		data["Data_Timestamp_From_Step_Start"] = 0
		
		#If we are charging to the end of a CC cycle, then we need to not exit immediately.
		if (step_settings["drive_style"] == 'voltage_v' and
		    step_settings["end_style"] == 'current_a' and
		    step_settings["end_condition"] == 'lesser'):
		
			data["Current"] = step_settings["drive_value_other"]
		
		end_condition = evaluate_end_condition(step_settings, data, data_in_queue)
		
		#Do the measurements and check the end conditions at every logging interval
		while end_condition == 'none':
			time.sleep(step_settings["meas_log_int_s"] - ((time.time() - step_start_time) % step_settings["meas_log_int_s"]))
			data.update(measure_battery(eq_dict, data_out_queue = data_out_queue))
			data["Data_Timestamp_From_Step_Start"] = (data["Data_Timestamp"] - step_start_time)
			end_condition = evaluate_end_condition(step_settings, data, data_in_queue)
			FileIO.write_data(log_filepath, data)
		
		#if the end condition is due to safety settings, then we want to end all future steps as well so return the exit reason
		return end_condition
	
	else:
		print("Step Setup Failed")
		return 'settings'

################################## SETTING CYCLE, CHARGE, DISCHARGE ############################

#run a single cycle on a cell while logging data
def cycle_cell(filepath, cycle_settings, eq_dict, data_out_queue = None, data_in_queue = None, ch_num = None):
	#v_meas_eq is the measurement equipment to use for measuring the voltage.
	#the device MUST have a measure_voltage() method that returns a float with units of Volts.
	
	#i_meas_eq is the measurement equipment to use for measuring the current.
	#the device MUST have a measure_current() method that returns a float with units of Amps.
	#When charging the battery this function should be positive current and discharging should be negative current.
	
	#use eload by default since they typically have better accuracy
	no_dmm_v = False
	no_dmm_i = False
	if eq_dict['dmm_v'] == None:
		eq_dict['dmm_v'] = eq_dict['eload']
		no_dmm_v = True
	if eq_dict['dmm_i'] == None:
		eq_dict['dmm_i'] = eq_dict['eload']
		no_dmm_i = True
	
	#need to override i_meas_eq since eload does not provide current during this step.
	end_reason = 'none'
	#Charge
	if no_dmm_i:
		eq_dict['dmm_i'] = eq_dict['psu']
	end_reason = charge_cell(filepath, cycle_settings, eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num) 
	#Rest
	if end_reason != 'end_requested':
		end_reason = rest_cell(filepath, cycle_settings, eq_dict, after_charge = True, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num)
	#Discharge
	if no_dmm_i:
		eq_dict['dmm_i'] = eq_dict['eload']
	if end_reason != 'end_requested':	
		end_reason = discharge_cell(filepath, cycle_settings, eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num)
	#Rest
	if end_reason != 'end_requested':
		end_reason = rest_cell(filepath, cycle_settings, eq_dict, after_charge = False, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num)
	
	if end_reason == 'end_requested':
		print('CH{} - Cycle Stopped: {}\n'.format(ch_num, time.ctime()), flush=True)
	elif end_reason == 'end_condition':
		print('CH{} - Cycle Completed: {}\n'.format(ch_num, time.ctime()), flush=True)
	
	if no_dmm_i:
		eq_dict['dmm_i'] = None
	if no_dmm_v:
		eq_dict['dmm_v'] = None
	return end_reason

def charge_cycle(filepath, charge_settings, eq_dict, data_out_queue = None, data_in_queue = None, ch_num = None):

	no_dmm_v = False
	no_dmm_i = False
	if eq_dict['dmm_v'] == None:
		eq_dict['dmm_v'] = eq_dict['psu']
		no_dmm_v = True
	if eq_dict['dmm_i'] == None:
		eq_dict['dmm_i'] = eq_dict['psu']
		no_dmm_i = True
	
	end_reason = 'none'
	end_reason = charge_cell(filepath, charge_settings, eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num)
	
	if no_dmm_i:
		eq_dict['dmm_i'] = None
	if no_dmm_v:
		eq_dict['dmm_v'] = None
	
	return end_reason
	
def discharge_cycle(filepath, charge_settings, eq_dict, data_out_queue = None, data_in_queue = None, ch_num = None):
	
	no_dmm_v = False
	no_dmm_i = False
	if eq_dict['dmm_v'] == None:
		eq_dict['dmm_v'] = eq_dict['eload']
		no_dmm_v = True
	if eq_dict['dmm_i'] == None:
		eq_dict['dmm_i'] = eq_dict['eload']
		no_dmm_i = True
	
	end_reason = 'none'
	end_reason = discharge_cell(filepath, charge_settings, eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num)
	
	if no_dmm_i:
		eq_dict['dmm_i'] = None
	if no_dmm_v:
		eq_dict['dmm_v'] = None
	
	return end_reason

def idle_cell_cycle(eq_dict, data_out_queue = None, data_in_queue = None):
	
	no_dmm_v = False
	no_dmm_i = False
	if eq_dict['dmm_v'] == None:
		no_dmm_v = True
		if eq_dict['eload'] != None:
			eq_dict['dmm_v'] = eq_dict['eload']
		elif eq_dict['psu'] != None:
			eq_dict['dmm_v'] = eq_dict['psu']
		else:
			print("No Voltage Measurement Equipment Connected! Exiting")
			return 'settings'
	
	if eq_dict['dmm_i'] == None:
		no_dmm_i = True
		if eq_dict['eload'] != None:
			eq_dict['dmm_i'] = eq_dict['eload']
		elif eq_dict['psu'] != None:
			eq_dict['dmm_i'] = eq_dict['psu']
			
	idle_cell(eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue)
	
	if no_dmm_i:
		eq_dict['dmm_i'] = None
	if no_dmm_v:
		eq_dict['dmm_v'] = None

def single_step_cycle(filepath, step_settings, eq_dict, data_out_queue = None, data_in_queue = None, ch_num = None):
	
	no_dmm_v = False
	no_dmm_i = False
	#if we don't have separate voltage measurement equipment, then choose what to use:
	if eq_dict['dmm_v'] == None:
		no_dmm_v = True
		if eq_dict['eload'] != None:
			eq_dict['dmm_v'] = eq_dict['eload']
		elif eq_dict['psu'] != None:
			eq_dict['dmm_v'] = eq_dict['psu']
		else:
			print("No Voltage Measurement Equipment Connected! Exiting")
			return 'settings'
	
	#if we don't have separate current measurement equipment, then choose what to use:
	if eq_dict['dmm_i'] == None:
		no_dmm_i = True
		resting = False
		left_comparator = 0
		if step_settings["drive_style"] == 'current_a':
			left_comparator = step_settings["drive_value"]
		elif step_settings["drive_style"] == 'voltage_v':
			left_comparator = step_settings["drive_value_other"]
		elif step_settings["drive_style"] == ['none'] or left_comparator == 0:
			resting = True
		
		if left_comparator > 0 and eq_dict['psu'] != None:
			eq_dict['dmm_i'] = eq_dict['psu'] #current measurement during charge
		elif left_comparator < 0 and eq_dict['eload'] != None:
			eq_dict['dmm_i'] = eq_dict['eload'] #current measurement during discharge
		elif not resting:
			print("No Current Measurement Equipment Connected and not Resting! Exiting")
			return 'settings'
		
	end_condition = step_cell(filepath, step_settings, eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue)

	if no_dmm_i:
		eq_dict['dmm_i'] = None
	if no_dmm_v:
		eq_dict['dmm_v'] = None

	return end_condition

def find_eq_req_steps(step_settings):
	eq_req_dict = {'psu': False, 'eload': False}
	
	#Go through all the steps to see which equipment we need connected
	if step_settings["drive_style"] == 'current_a':
		if step_settings["drive_value"] > 0:
			eq_req_dict['psu'] = True
		elif step_settings["drive_value"] < 0:
			eq_req_dict['eload'] = True
	elif step_settings["drive_style"] == 'voltage_v':
		if step_settings["drive_value_other"] > 0:
			eq_req_dict['psu'] = True
		elif step_settings["drive_value_other"] < 0:
			eq_req_dict['eload'] = True
	
	return eq_req_dict


################################## CHOOSING CYCLE SETTINGS TYPES ################################

def single_cc_cycle_info():
	#charge then discharge
	cycle_settings = Templates.CycleSettings()
	cycle_settings.get_cycle_settings()
	
	cycle_settings_list = list()
	cycle_settings_list.append((cycle_settings.settings,))
	
	return cycle_settings_list

def one_level_continuous_cc_cycles_with_rest_info():
	#cycles - e.g. charge at 1A, rest, discharge at 5A, rest, repeat X times.
	#get user to enter number of cycles
	cycle_settings = Templates.CycleSettings()
	cycle_settings.get_cycle_settings()
	num_cycles = eg.integerbox(msg = "How Many Cycles?",
								title = "Degradation Cycle", default = 1,
								lowerbound = 0, upperbound = 999)

	cycle_settings_list = list()

	for i in range(num_cycles):
		cycle_settings_list.append((cycle_settings.settings,))
	
	return cycle_settings_list

def two_level_continuous_cc_cycles_with_rest_info():
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
			cycle_settings_list.append((cycle_1_settings.settings,))
		for i in range(num_cycles_type_2):
			cycle_settings_list.append((cycle_2_settings.settings,))
	
	return cycle_settings_list

def charge_only_cycle_info():
	cycle_settings_list = list()
	
	charge_only_settings = Templates.ChargeSettings()
	charge_only_settings.get_cycle_settings("Charge Only")
	
	cycle_settings_list.append((charge_only_settings.settings,))
	
	return cycle_settings_list
	
def discharge_only_cycle_info():
	cycle_settings_list = list()
	
	discharge_only_settings = Templates.DischargeSettings()
	discharge_only_settings.get_cycle_settings("Discharge Only")
	
	cycle_settings_list.append((discharge_only_settings.settings,))
	
	return cycle_settings_list

def single_step_cell_info():
	step_settings_list = list()
	
	step_settings = Templates.StepSettings()
	step_settings.get_cycle_settings("Step")
	
	step_settings_list.append((step_settings.settings,))
	
	return step_settings_list

def multi_step_cell_info():
	
	
	#import multi step from csv?:
	msg = "Import the multiple step cycle from a csv?"
	title = "CSV Import"
	from_csv = eg.ynbox(msg, title)
	
	if from_csv:
		step_settings_list = jsonIO.import_multi_step_from_csv()
	
	else:
		step_settings_list = list()
		msg = "Add a step to the cycle?"
		title = "Add Step"
		while eg.ynbox(msg = msg, title = title):
			step_settings_list.append(single_step_cell_info()[0][0])
			msg = "Add another step to the cycle?"
	
	step_settings_list = (step_settings_list,)
	
	return step_settings_list

def continuous_step_cycles_info():
	cycle_settings_list = list()
	
	msg = "Add another cycle?"
	title = "Add Cycle"
	while eg.ynbox(msg = msg, title = title):
		cycle_settings_list.extend(multi_step_cell_info())
	
	return cycle_settings_list

def ask_storage_charge():
	return eg.ynbox(title = "Storage Charge",
					msg = "Do you want to do a storage charge?\n\
							Recommended to do one. Leaving a cell discharged increases\n\
							risk of latent failures due to dendrite growth.")

def get_cell_name(ch_num = None, queue = None):
	#get the cell name
	cell_name = eg.enterbox(title = "Test Setup", msg = "Enter the Cell Name\n(Spaces will be replaced with underscores)",
							default = "CELL_NAME", strip = True)
	#replace the spaces to keep file names consistent
	cell_name = cell_name.replace(" ", "_")
	
	if queue != None:
		dict_to_put = {'ch_num': ch_num, 'cell_name': cell_name}
		queue.put_nowait(dict_to_put)
	else:
		return cell_name
	
def get_cycle_type():
	cycle_types = Templates.CycleTypes.cycle_types
	
	#choose the cycle type
	msg = "Which cycle type do you want to do?"
	title = "Choose Cycle Type"
	cycle_type = eg.choicebox(msg, title, list(cycle_types.keys()))
	return cycle_type

def get_cycle_settings_list_of_lists(cycle_type):
	cycle_types = Templates.CycleTypes.cycle_types
	
	#different cycle types that are available
	cycle_types["Single CC Cycle"]['func_call'] = single_cc_cycle_info
	cycle_types["One Setting Continuous CC Cycles With Rest"]['func_call'] = one_level_continuous_cc_cycles_with_rest_info
	cycle_types["Two Setting Continuous CC Cycles With Rest"]['func_call'] = two_level_continuous_cc_cycles_with_rest_info
	cycle_types["CC Charge Only"]['func_call'] = charge_only_cycle_info
	cycle_types["CC Discharge Only"]['func_call'] = discharge_only_cycle_info
	cycle_types["Step Cycle"]['func_call'] = multi_step_cell_info
	cycle_types["Continuous Step Cycles"]['func_call'] = continuous_step_cycles_info
	
	#gather the list settings based on the cycle type
	cycle_settings_list_of_lists = list()
	cycle_settings_list_of_lists = cycle_types[cycle_type]['func_call']()
	
	#STORAGE CHARGE
	do_a_storage_charge = False
	if(cycle_types[cycle_type]['str_chg_opt']):
		do_a_storage_charge = ask_storage_charge()
	
	#extend adds two lists, append adds a single element to a list. We want extend here since charge_only_cycle_info() returns a list.
	if do_a_storage_charge:
		cycle_settings_list_of_lists.extend(charge_only_cycle_info())
		
	return cycle_settings_list_of_lists

def get_eq_req_dict(cycle_type, cycle_settings_list_of_lists):
	#REQUIRED EQUIPMENT
	eq_req_dict = {'psu': False, 'eload': False}
	
	for settings_list in cycle_settings_list_of_lists:
		for settings in settings_list:
			if settings["cycle_type"] == 'step':
				eq_req_from_settings = find_eq_req_steps(settings)
				eq_req_dict['psu'] = eq_req_dict['psu'] or eq_req_from_settings['psu']
				eq_req_dict['eload'] = eq_req_dict['eload'] or eq_req_from_settings['eload']
			else:
				cycle_types = Templates.CycleTypes.cycle_types
				eq_req_dict['psu'] = eq_req_dict['psu'] or cycle_types[cycle_type]['supply_req']
				eq_req_dict['eload'] = eq_req_dict['eload'] or cycle_types[cycle_type]['load_req']
	
	return eq_req_dict

def get_input_dict(ch_num = None, queue = None):
	input_dict = {}
	input_dict['cell_name'] = get_cell_name()
	input_dict['directory'] = FileIO.get_directory("Choose directory to save the cycle logs")
	input_dict['cycle_type'] = get_cycle_type()
	input_dict['cycle_settings_list_of_lists'] = get_cycle_settings_list_of_lists(input_dict['cycle_type'])
	input_dict['eq_req_dict'] = get_eq_req_dict(input_dict['cycle_type'], input_dict['cycle_settings_list_of_lists'])
	
	if queue != None:
		dict_to_put = {'ch_num': ch_num, 'cdc_input_dict': input_dict}
		print(dict_to_put)
		queue.put_nowait(dict_to_put)
	else:
		return input_dict

def get_equipment_dict(res_ids_dict, multi_channel_event_and_queue_dict):
	eq_dict = {}
	for key in res_ids_dict:
		if res_ids_dict[key] != None and res_ids_dict[key]['res_id'] != None:
			eq_dict[key] = eq.connect_to_eq(key, res_ids_dict[key]['class_name'], res_ids_dict[key]['res_id'], res_ids_dict[key]['use_remote_sense'], multi_channel_event_and_queue_dict)
		else:
			eq_dict[key] = None
	return eq_dict

################################## BATTERY CYCLING SETUP FUNCTION ######################################
def idle_control(res_ids_dict, data_out_queue = None, data_in_queue = None, multi_channel_event_and_queue_dict = None):
	try:
		eq_dict = get_equipment_dict(res_ids_dict, multi_channel_event_and_queue_dict)
		idle_cell_cycle(eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue)
		disable_equipment(eq_dict)
	except Exception:
		traceback.print_exc()
	
def charge_discharge_control(res_ids_dict, data_out_queue = None, data_in_queue = None, input_dict = None, multi_channel_event_and_queue_dict = None, ch_num = None):
	try:
		eq_dict = get_equipment_dict(res_ids_dict, multi_channel_event_and_queue_dict)
		
		if input_dict == None:
			input_dict = get_input_dict()
		
		#CHECKING CONNECTION OF REQUIRED EQUIPMENT
		if input_dict['eq_req_dict']['eload'] and eq_dict['eload'] == None:
			print("Eload required for cycle but none connected! Exiting")
			return
	
		if input_dict['eq_req_dict']['psu'] and eq_dict['psu'] == None:
			print("Power Supply required for cycle type but none connected! Exiting")
			return
		#TODO - check cycles with multiple types
		
		initialize_connected_equipment(eq_dict)
		#Now initialize all the equipment that is connected
		
		
		#TODO - looping a current profile until safety limits are hit
		#TODO - current step profiles to/from csv
		
		#cycle x times
		cycle_num = 0
		end_list_of_lists = False
		
		for count_1, cycle_settings_list in enumerate(input_dict['cycle_settings_list_of_lists']):
			print("CH{} - Cycle {} Starting".format(ch_num, cycle_num), flush=True)
			filepath = FileIO.start_file(input_dict['directory'], input_dict['cell_name'])
			
			try:
				for count_2, cycle_settings in enumerate(cycle_settings_list):
					end_condition = 'none'
					
					#Set label text for current and next status
					current_status = cycle_settings["cycle_type"]
					try:
						next_status = cycle_settings_list[count_2 + 1]["cycle_type"]
					except IndexError:
						try:
							next_status = input_dict['cycle_settings_list_of_lists'][count_1 + 1][0]["cycle_type"]
						except (IndexError, TypeError):
							next_status = "Idle"
					
					data_out_queue.put_nowait({'type': 'status', 'data': (current_status, next_status)})
					
					
					#Charge only - only using the power supply
					if current_status == 'charge':
						end_condition = charge_cycle(filepath, cycle_settings, eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num)
						
					#Discharge only - only using the eload
					elif current_status == 'discharge':
						end_condition = discharge_cycle(filepath, cycle_settings, eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num)
					
					#Step Functions
					elif current_status == 'step':
						end_condition = single_step_cycle(filepath, cycle_settings, eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num)
						if end_condition == 'safety_condition':
							break
							
					#Cycle the cell - using both psu and eload
					elif current_status == 'cycle':
						end_condition = cycle_cell(filepath, cycle_settings, eq_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num)
					
					if end_condition == 'end_request':
						end_list_of_lists = True
						break
				if end_list_of_lists:
					break
				
			except KeyboardInterrupt:
				disable_equipment(eq_dict)
				exit()
			cycle_num += 1
		
		disable_equipment(eq_dict)

		print("CH{} - All Cycles Completed: {}".format(ch_num, time.ctime()), flush=True)
	except Exception:
		traceback.print_exc()

####################################### MAIN PROGRAM ######################################

if __name__ == '__main__':
	print("Use the battery_test.py script")
	#charge_discharge_control()
