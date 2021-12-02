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
	
def start_step(step_settings, psu, eload, v_meas_eq, i_meas_eq):
	#This function will set all the supplies to the settings given in the step
	if step_settings["drive_style"] == 'current_a':
		if step_settings["drive_value"] > 0:
			#charge
			psu.set_current(step_settings["drive_value"])
			psu.set_voltage(step_settings["drive_value_other"])
			psu.toggle_output(True)
		elif step_settings["drive_value"] < 0:
			#discharge
			eload.set_current(step_settings["drive_value"])
			eload.toggle_output(True)
			#we're in constant current mode - can't set a voltage.
		elif step_settings["drive_value"] == 0:
			#rest
			#TODO - for now just ensure to shut off both. Later we will need to ensure transition between steps is 'smooth'
			psu.set_current(0)
			eload.set_current(0)
	elif step_settings["drive_style"] == 'voltage_v':
		print("Voltage Step Not Yet Implemented")
		pass
	elif step_settings["drive_style"] == 'none':
		psu.set_current(0)
		psu.toggle_output(False)
		eload.set_current(0)
		eload.toggle_output(False)	

def evaluate_end_condition(step_settings, data):
	#evaluates different end conditions (voltage, current, time)
	#returns true if the end condition has been met (e.g. voltage hits lower bound, current hits lower bound, etc.)
	
	if step_settings["end_style"] == 'current_a':
		left_comparator = data["Current"]
	elif step_settings["end_style"] == 'voltage_v':
		left_comparator = data["Voltage"]
	elif step_settings["end_style"] == 'time_s':
		left_comparator = data["Data_Timestamp_From_Step_Start"]
	
	if step_settings["end_condition"] == 'greater':
		return left_comparator > step_settings["end_value"]
	elif step_settings["end_condition"] == 'lesser':
		return left_comparator < step_settings["end_value"]
	
	#return True so that we end the step if the settings were incorrectly configured.
	return True


######################### MEASURING ######################

def measure_battery(v_meas_eq, i_meas_eq = None):
	voltage = v_meas_eq.measure_voltage()
	current = 0
	if i_meas_eq != None:
		current = i_meas_eq.measure_current()
	return (voltage, current, time.time())


########################## CHARGE, DISCHARGE, REST #############################

def charge_cell(log_filepath, cycle_settings, psu, v_meas_eq, i_meas_eq):
	#start the charging
	#Start the data so we don't immediately trigger end conditions
	data = dict()
	data["Current"] = cycle_settings["charge_a"]
	data["Voltage"] = cycle_settings["charge_end_v"]
	data["Data_Timestamp"] = time.time()
	
	start_charge(cycle_settings["charge_end_v"], cycle_settings["charge_a"], psu)
	charge_start_time = time.time()
	print('Starting Charge: {}\n'.format(time.ctime()), flush=True)
	while (data["Current"] > cycle_settings["charge_end_a"]):
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - charge_start_time) % cycle_settings["meas_log_int_s"]))
		data["Voltage"], data["Current"], data["Data_Timestamp"] = measure_battery(v_meas_eq, i_meas_eq)
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
	data = dict()
  
	while (time.time() - rest_start_time) < rest_time_s:
		time.sleep(cycle_settings["meas_log_int_s"] - ((time.time() - rest_start_time) % cycle_settings["meas_log_int_s"]))
		data["Voltage"], data["Current"], data["Data_Timestamp"] = measure_battery(v_meas_eq)
		FileIO.write_data(log_filepath, data)

def discharge_cell(log_filepath, cycle_settings, eload, v_meas_eq, i_meas_eq):
	#start discharge
	start_discharge(cycle_settings["discharge_a"], eload)
	discharge_start_time = time.time()

	data = dict()
	data["Voltage"], data["Current"], data["Data_Timestamp"] = measure_battery(v_meas_eq)
	
	#need to add a previous voltage, previous voltage time so that we can compare to better extimate the end time.
	#if we underestimate the end time, that's fine since we'll just get a measurement that is closer next, though there will be delay by the time to gather and write data
	prev_v = data["Voltage"]
	prev_v_time = discharge_start_time
	data["Data_Timestamp"] = discharge_start_time
	
	print('Starting Discharge: {}\n'.format(time.ctime()), flush=True)

	while (data["Voltage"] > cycle_settings["discharge_end_v"]):
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
		
		data["Voltage"], data["Current"], data["Data_Timestamp"] = measure_battery(v_meas_eq, i_meas_eq)
		FileIO.write_data(log_filepath, data)
	
	end_discharge(eload)

def step_cell(log_filepath, step_settings, psu = None, eload = None, v_meas_eq = None, i_meas_eq = None):
	
	start_step(step_settings, psu, eload, v_meas_eq, i_meas_eq)
	step_start_time = time.time()
	
	data = dict()
	data["Voltage"], data["Current"], data["Data_Timestamp"] = measure_battery(v_meas_eq)
	data["Data_Timestamp_From_Step_Start"] = 0
	
	#TODO - this will exit immediately if we end on charge current less than value
	while not evaluate_end_condition(step_settings, data):
		time.sleep(step_settings["meas_log_int_s"] - ((time.time() - step_start_time) % step_settings["meas_log_int_s"]))
		data["Voltage"], data["Current"], data["Data_Timestamp"] = measure_battery(v_meas_eq, i_meas_eq)
		data["Data_Timestamp_From_Step_Start"] = (data["Data_Timestamp"] - step_start_time)
		FileIO.write_data(log_filepath, data)
	
	psu.toggle_output(False)
	eload.toggle_output(False)

################################## SETTING CYCLE, CHARGE, DISCHARGE ############################

#run a single cycle on a cell while logging data
def cycle_cell(directory, cell_name, cycle_settings, eload, psu, v_meas_eq = None, i_meas_eq = None):
	#v_meas_eq is the measurement equipment to use for measuring the voltage.
	#the device MUST have a measure_voltage() method that returns a float with units of Volts.
	
	#i_meas_eq is the measurement equipment to use for measuring the current.
	#the device MUST have a measure_current() method that returns a float with units of Amps.
	#When charging the battery this function should be positive current and discharging should be negative current.
	
	#use eload by default since they typically have better accuracy
	if v_meas_eq == None:
		v_meas_eq = eload
	if i_meas_eq == None:
		i_meas_eq = eload
	
	#start a new file for the cycle
	filepath = FileIO.start_file(directory, cell_name)
	
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
	
	#need to override i_meas_eq since eload does not provide current during this step.
	charge_cell(filepath, cycle_settings, psu, v_meas_eq, i_meas_eq = psu) 
	
	rest_cell(filepath, cycle_settings, v_meas_eq, after_charge = True)
	
	discharge_cell(filepath, cycle_settings, eload, v_meas_eq, i_meas_eq = eload)
	
	rest_cell(filepath, cycle_settings, v_meas_eq, after_charge = False)
	
	print('Cycle Completed: {}\n'.format(time.ctime()), flush=True)
	
	return

def charge_cycle(directory, cell_name, charge_settings, psu, v_meas_eq = None, i_meas_eq = None):

	if v_meas_eq == None:
		v_meas_eq = psu
	if i_meas_eq == None:
		i_meas_eq = psu
		
	#start a new file for the cycle
	filepath = FileIO.start_file(directory, cell_name)
	
	charge_cell(filepath, charge_settings, psu, v_meas_eq, i_meas_eq)
	
def discharge_cycle(directory, cell_name, charge_settings, eload, v_meas_eq = None, i_meas_eq = None):

	if v_meas_eq == None:
		v_meas_eq = eload
	if i_meas_eq == None:
		i_meas_eq = eload
		
	#start a new file for the cycle
	filepath = FileIO.start_file(directory, cell_name)
	
	discharge_cell(filepath, charge_settings, eload, v_meas_eq, i_meas_eq)

def step_cycle(directory, cell_name, step_settings, eload, psu, v_meas_eq = None, i_meas_eq = None):
	
	#TODO - what if these defaults are not available??
	if v_meas_eq == None:
		v_meas_eq = eload
	if i_meas_eq == None:
		i_meas_eq = psu
	
	#start a new file for the cycle
	filepath = FileIO.start_file(directory, cell_name)
	
	step_cell(filepath, step_settings, psu, eload, v_meas_eq, i_meas_eq)
	
	
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

def single_step_cell_info():
	step_settings_list = list()
	
	step_settings = Templates.StepSettings()
	step_settings.get_cycle_settings("Step")
	
	step_settings_list.append(step_settings)
	
	return step_settings_list

def ask_storage_charge():
	return eg.ynbox(title = "Storage Charge",
					msg = "Do you want to do a storage charge?\n\
							Recommended to do one. Leaving a cell discharged increases\n\
							risk of latent failures due to dendrite growth.")

def charge_discharge_control(res_ids_dict):
	
	eq_dict = dict()
	for key in res_ids_dict:
		if res_ids_dict[key]['res_id'] != None:
			eq_dict[key] = eq.connect_to_eq(key, res_ids_dict[key]['class_name'], res_ids_dict[key]['res_id'])
		else:
			eq_dict[key] = None
	
	#get the cell name
	cell_name = eg.enterbox(title = "Test Setup", msg = "Enter the Cell Name\n(Spaces will be replaced with underscores)",
							default = "CELL_NAME", strip = True)
	#replace the spaces to keep file names consistent
	cell_name = cell_name.replace(" ", "_")
	
	#Get a directory to save the file
	directory = FileIO.get_directory("Choose directory to save the cycle logs")
	
	#different cycle types that are available
	cycle_types = Templates.CycleTypes.cycle_types
	cycle_types["Single Cycle"]['func_call'] = single_cycle
	cycle_types["One Setting Continuous Cycles With Rest"]['func_call'] = one_level_continuous_cycles_with_rest
	cycle_types["Two Setting Continuous Cycles With Rest"]['func_call'] = two_level_continuous_cycles_with_rest
	cycle_types["Charge Only"]['func_call'] = charge_only_cycle_info
	cycle_types["Discharge Only"]['func_call'] = discharge_only_cycle_info
	cycle_types["Single Step"]['func_call'] = single_step_cell_info
	
	#choose the cycle type
	msg = "Which cycle type do you want to do?"
	title = "Choose Cycle Type"
	cycle_type = eg.choicebox(msg, title, list(cycle_types.keys()))
	
	#gather the list settings based on the cycle type
	cycle_settings_list = list()
	cycle_settings_list = cycle_types[cycle_type]['func_call']()
	
	do_a_storage_charge = False
	if(cycle_types[cycle_type]['str_chg_opt']):
		do_a_storage_charge = ask_storage_charge()
	load_required = cycle_types[cycle_type]['load_req']
	supply_required = cycle_types[cycle_type]['supply_req']
	
	#extend adds two lists, append adds a single element to a list. We want extend here since charge_only_cycle() returns a list.
	if do_a_storage_charge:
		cycle_settings_list.extend(charge_only_cycle_info())
	
	#Now we choose the PSU, Eload, dmms to use
	if eq_dict['eload'] != None:	
		init_eload(eq_dict['eload'])
	if eq_dict['psu'] != None:
		init_psu(eq_dict['psu'])
	if eq_dict['dmm_v'] != None:
		init_dmm_v(eq_dict['dmm_v'])
	if eq_dict['dmm_i'] != None:
		init_dmm_i(eq_dict['dmm_i'])
		
	#cycle x times
	cycle_num = 0
	for cycle_settings in cycle_settings_list:
		print("Cycle {} Starting".format(cycle_num), flush=True)
		try:
			#Charge only - only using the power supply
			if isinstance(cycle_settings, Templates.ChargeSettings):
				charge_cycle(directory, cell_name, cycle_settings.settings, eq_dict['psu'], v_meas_eq = eq_dict['dmm_v'], i_meas_eq = eq_dict['dmm_i'])
				
			#Discharge only - only using the eload
			elif isinstance(cycle_settings, Templates.DischargeSettings):
				discharge_cycle(directory, cell_name, cycle_settings.settings, eq_dict['eload'], v_meas_eq = eq_dict['dmm_v'], i_meas_eq = eq_dict['dmm_i'])
			
			#Use Step Functions
			elif isinstance(cycle_settings, Templates.StepSettings):
				step_cycle(directory, cell_name, cycle_settings.settings, eq_dict['eload'], eq_dict['psu'], v_meas_eq = eq_dict['dmm_v'], i_meas_eq = eq_dict['dmm_i'])
			
			#Cycle the cell - using both psu and eload
			else:
				cycle_cell(directory, cell_name, cycle_settings.settings, eq_dict['eload'], eq_dict['psu'], v_meas_eq = eq_dict['dmm_v'], i_meas_eq = eq_dict['dmm_i'])
			
		except KeyboardInterrupt:
			self.eload.toggle_output(False)
			self.psu.toggle_output(False)
			exit()
		cycle_num += 1
	
	print("All Cycles Completed")

####################################### MAIN PROGRAM ######################################

class BatteryChannel:
	
	def __init__(self, psu = None, eload = None, dmm_v = None, dmm_i = None):
		self.eq_dict = dict()
		self.eq_dict['eload'] = None
		self.eq_dict['psu'] = None
		self.eq_dict['dmm_v'] = None
		self.eq_dict['dmm_i'] = None
		self.assign_equipment(psu_to_assign = psu, eload_to_assign = eload, dmm_v_to_assign = dmm_v, dmm_i_to_assign = dmm_i)
	
	def assign_equipment(self, psu_to_assign = None, eload_to_assign = None, dmm_v_to_assign = None, dmm_i_to_assign = None):
		self.eq_dict['eload'] = eload_to_assign
		self.eq_dict['psu'] = psu_to_assign
		self.eq_dict['dmm_v'] = dmm_v_to_assign
		self.eq_dict['dmm_i'] = dmm_i_to_assign
	
	def get_assigned_eq_res_ids(self):
		eq_res_ids_dict = dict()
		
		for key in self.eq_dict:
			eq_res_ids_dict[key] = {'class_name': None, 'res_id': None}
			if self.eq_dict[key] != None:
				eq_res_ids_dict[key] = {'class_name': self.eq_dict[key][0], 'res_id': self.eq_dict[key][1].inst.resource_name}
		
		return eq_res_ids_dict 
		
	def disconnect_all_assigned_eq(self):
		#disconnect from equipment so that we can pass the resource ids to the
		#charge_discharge_control function and reconnect to the devices there
		for key in self.eq_dict:
			if self.eq_dict[key] != None:
				self.eq_dict[key][1].inst.close()


if __name__ == '__main__':
	print("Use the battery_test.py script")
	#charge_discharge_control()
