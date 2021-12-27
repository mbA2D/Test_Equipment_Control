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
import traceback


##################### EQUIPMENT SETUP ####################

def init_eload(eload):
	eload.toggle_output(False)
	eload.remote_sense(False)
	eload.set_current(0)
	
def init_psu(psu):
	psu.toggle_output(False)
	psu.remote_sense(False)
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

def disable_equipment(psu = None, eload = None):
	if psu != None:
		psu.set_current(0) #Turn current to 0 first to try and eliminate arcing in a relay inside an eload that disconnects the output
		psu.toggle_output(False)
	if eload != None:
		eload.set_current(0) #Turn current to 0 first to try and eliminate arcing in a relay inside a power supply that disconnects the output
		eload.toggle_output(False)

####################### TEST CONTROL #####################

def start_charge(end_voltage, constant_current, psu):
	psu.set_voltage(end_voltage)
	time.sleep(0.01)
	psu.set_current(constant_current)
	time.sleep(0.01)
	psu.toggle_output(True)

def start_discharge(constant_current, eload):
	eload.set_current(constant_current)
	time.sleep(0.01)
	eload.toggle_output(True)
	
def start_step(step_settings, psu, eload, v_meas_eq, i_meas_eq):
	#This function will set all the supplies to the settings given in the step
	
	#CURRENT DRIVEN
	if step_settings["drive_style"] == 'current_a':
		if step_settings["drive_value"] > 0:
			#charge - turn off eload first if connected
			disable_equipment(eload = eload)
			if psu != None:
				psu.set_current(step_settings["drive_value"])
				psu.set_voltage(step_settings["drive_value_other"])
				psu.toggle_output(True)
			else:
				print("No PSU Connected. Can't Charge! Exiting.")
				return False
		elif step_settings["drive_value"] < 0:
			#discharge
			disable_equipment(psu = psu)
			if eload != None:
				eload.set_current(step_settings["drive_value"])
				eload.toggle_output(True)
				#we're in constant current mode - can't set a voltage.
			else:
				print("No Eload Connected. Can't Discharge! Exiting.")
				return False
		elif step_settings["drive_value"] == 0:
			#rest
			disable_equipment(psu, eload)
	
	#VOLTAGE DRIVEN
	elif step_settings["drive_style"] == 'voltage_v':
		#positive current
		if step_settings["drive_value_other"] >= 0:
			disable_equipment(eload = eload) #turn off eload
			if psu != None:
				psu.set_current(step_settings["drive_value_other"])
				psu.set_voltage(step_settings["drive_value"])
				psu.toggle_output(True)
		#TODO - needs CV mode on eloads
		else:
			print("Voltage Driven Step Not Yet Implemented for negative current. Exiting.")
			#Ensure everything is off since not yet implemented.
			disable_equipment(psu, eload)
			return False
	
	#NOT DRIVEN
	elif step_settings["drive_style"] == 'none':
		#Ensure all sources and loads are off.
		disable_equipment(psu, eload)
	
	
	#return True for a successful step start.
	return True

def end_steps(psu, eload):
	disable_equipment(psu, eload)

def evaluate_end_condition(step_settings, data):
	#evaluates different end conditions (voltage, current, time)
	#returns true if the end condition has been met (e.g. voltage hits lower bound, current hits lower bound, etc.)
	#also returns true if any of the safety settings have been exceeded
	
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
		if left_comparator < step_settings["end_value"]:
			return 'end_condition'
		else:
			return 'none'
	
	#return True so that we end the step if the settings were incorrectly configured.
	return 'settings'


######################### MEASURING ######################

def measure_battery(v_meas_eq, i_meas_eq = None, data_out_queue = None):
	data_dict = dict()
	data_dict["Voltage"] = v_meas_eq.measure_voltage()
	data_dict["Current"] = 0
	if i_meas_eq != None:
		data_dict['Current'] = i_meas_eq.measure_current()
	data_dict["Data_Timestamp"] = time.time()
	
	if data_out_queue != None:
		#add the new data to the output queue
		data_out_queue.put_nowait(data_dict)
		
	return data_dict


########################## CHARGE, DISCHARGE, REST #############################

def charge_cell(log_filepath, cycle_settings, psu, v_meas_eq, i_meas_eq, data_out_queue = None):
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
		data.update(measure_battery(v_meas_eq, i_meas_eq, data_out_queue = data_out_queue))
		FileIO.write_data(log_filepath, data)
		
	disable_equipment(psu = psu)

def rest_cell(log_filepath, cycle_settings, v_meas_eq, after_charge = True, data_out_queue = None):
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
		data.update(measure_battery(v_meas_eq, data_out_queue = data_out_queue))
		FileIO.write_data(log_filepath, data)

def discharge_cell(log_filepath, cycle_settings, eload, v_meas_eq, i_meas_eq, data_out_queue = None):
	#start discharge
	start_discharge(cycle_settings["discharge_a"], eload)
	discharge_start_time = time.time()

	data = dict()
	data.update(measure_battery(v_meas_eq))
	
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
		
		data.update(measure_battery(v_meas_eq, i_meas_eq, data_out_queue = data_out_queue))
		FileIO.write_data(log_filepath, data)
	
	disable_equipment(eload = eload)

def step_cell(log_filepath, step_settings, psu = None, eload = None, v_meas_eq = None, i_meas_eq = None, data_out_queue = None):
	
	if start_step(step_settings, psu, eload, v_meas_eq, i_meas_eq):
		
		step_start_time = time.time()
		
		data = dict()
		data.update(measure_battery(v_meas_eq, i_meas_eq))
		data["Data_Timestamp_From_Step_Start"] = 0
		
		#If we are charging to the end of a CC cycle, then we need to not exit immediately.
		if (step_settings["drive_style"] == 'voltage_v' and
		    step_settings["end_style"] == 'current_a' and
		    step_settings["end_condition"] == 'lesser'):
		
			data["Current"] = step_settings["drive_value_other"]
		
		end_condition = evaluate_end_condition(step_settings, data)
		
		#Do the measurements and check the end conditions at every logging interval
		while end_condition == 'none':
			time.sleep(step_settings["meas_log_int_s"] - ((time.time() - step_start_time) % step_settings["meas_log_int_s"]))
			data.update(measure_battery(v_meas_eq, i_meas_eq, data_out_queue = data_out_queue))
			data["Data_Timestamp_From_Step_Start"] = (data["Data_Timestamp"] - step_start_time)
			end_condition = evaluate_end_condition(step_settings, data)
			FileIO.write_data(log_filepath, data)
		
		#if the end condition is due to safety settings, then we want to end all future steps as well so return the exit reason
		return end_condition
	
	else:
		print("Step Setup Failed")
		return 'settings'

################################## SETTING CYCLE, CHARGE, DISCHARGE ############################

#run a single cycle on a cell while logging data
def cycle_cell(filepath, cycle_settings, eload, psu, v_meas_eq = None, i_meas_eq = None, data_out_queue = None):
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
	
	#need to override i_meas_eq since eload does not provide current during this step.
	charge_cell(filepath, cycle_settings, psu, v_meas_eq, i_meas_eq = psu, data_out_queue = data_out_queue) 
	rest_cell(filepath, cycle_settings, v_meas_eq, after_charge = True, data_out_queue = data_out_queue)
	discharge_cell(filepath, cycle_settings, eload, v_meas_eq, i_meas_eq = eload, data_out_queue = data_out_queue)
	rest_cell(filepath, cycle_settings, v_meas_eq, after_charge = False, data_out_queue = data_out_queue)
	
	print('Cycle Completed: {}\n'.format(time.ctime()), flush=True)
	
	return

def charge_cycle(filepath, charge_settings, psu, v_meas_eq = None, i_meas_eq = None, data_out_queue = None):

	if v_meas_eq == None:
		v_meas_eq = psu
	if i_meas_eq == None:
		i_meas_eq = psu
	
	charge_cell(filepath, charge_settings, psu, v_meas_eq, i_meas_eq, data_out_queue = data_out_queue)
	
def discharge_cycle(filepath, charge_settings, eload, v_meas_eq = None, i_meas_eq = None, data_out_queue = None):

	if v_meas_eq == None:
		v_meas_eq = eload
	if i_meas_eq == None:
		i_meas_eq = eload
	
	discharge_cell(filepath, charge_settings, eload, v_meas_eq, i_meas_eq, data_out_queue = data_out_queue)

def single_step_cycle(filepath, step_settings, eload = None, psu = None, v_meas_eq = None, i_meas_eq = None, data_out_queue = None):
	
	#if we don't have separate voltage measurement equipment, then choose what to use:
	if v_meas_eq == None:
		if eload != None:
			v_meas_eq = eload
		elif psu != None:
			v_meas_eq = psu
		else:
			print("No Voltage Measurement Equipment Connected! Exiting")
			return 'settings'
	
	#if we don't have separate current measurement equipment, then choose what to use:
	if i_meas_eq == None:
		resting = False
		left_comparator = 0
		if step_settings["drive_style"] == 'current_a':
			left_comparator = step_settings["drive_value"]
		elif step_settings["drive_style"] == 'voltage_v':
			left_comparator = step_settings["drive_value_other"]
		elif step_settings["drive_style"] == ['none'] or left_comparator == 0:
			resting = True
		
		if left_comparator > 0 and psu != None:
			i_meas_eq = psu #current measurement during charge
		elif left_comparator < 0 and eload != None:
			i_meas_eq = eload #current measurement during discharge
		elif not resting:
			print("No Current Measurement Equipment Connected and not Resting! Exiting")
			return 'settings'
		
	return step_cell(filepath, step_settings, psu, eload, v_meas_eq, i_meas_eq, data_out_queue = data_out_queue)

def find_eq_req_steps(step_settings_list_of_lists):
	eq_req_dict = {'psu': False, 'eload': False}
	
	#Go through all the steps to see which equipment we need connected
	for step_settings_list in step_settings_list_of_lists:
		for step_settings in step_settings_list:
			if step_settings.settings["drive_style"] == 'current_a':
				if step_settings.settings["drive_value"] > 0:
					eq_req_dict['psu'] = True
				elif step_settings.settings["drive_value"] < 0:
					eq_req_dict['eload'] = True
			elif step_settings.settings["drive_style"] == 'voltage_v':
				if step_settings.settings["drive_value_other"] > 0:
					eq_req_dict['psu'] = True
				elif step_settings.settings["drive_value_other"] < 0:
					eq_req_dict['eload'] = True
	
	return eq_req_dict


################################## CHOOSING CYCLE SETTINGS TYPES ################################

def single_cc_cycle_info():
	#charge then discharge
	cycle_settings = Templates.CycleSettings()
	cycle_settings.get_cycle_settings()
	
	cycle_settings_list = list()
	cycle_settings_list.append((cycle_settings,))
	
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
		cycle_settings_list.append((cycle_settings,))
	
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
			cycle_settings_list.append((cycle_1_settings,))
		for i in range(num_cycles_type_2):
			cycle_settings_list.append((cycle_2_settings,))
	
	return cycle_settings_list

def charge_only_cycle_info():
	cycle_settings_list = list()
	
	charge_only_settings = Templates.ChargeSettings()
	charge_only_settings.get_cycle_settings("Charge Only")
	
	cycle_settings_list.append((charge_only_settings,))
	
	return cycle_settings_list
	
def discharge_only_cycle_info():
	cycle_settings_list = list()
	
	discharge_only_settings = Templates.DischargeSettings()
	discharge_only_settings.get_cycle_settings("Discharge Only")
	
	cycle_settings_list.append((discharge_only_settings,))
	
	return cycle_settings_list

def single_step_cell_info():
	step_settings_list = list()
	
	step_settings = Templates.StepSettings()
	step_settings.get_cycle_settings("Step")
	
	step_settings_list.append(step_settings)
	
	return step_settings_list

def multi_step_cell_info():
	step_settings_list = list()
	
	msg = "Add a step to the cycle?"
	title = "Add Step"
	while eg.ynbox(msg = msg, title = title):
		step_settings_list.append(single_step_cell_info())
		msg = "Add another step to the cycle?"
	
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

def get_cell_name():
	#get the cell name
	cell_name = eg.enterbox(title = "Test Setup", msg = "Enter the Cell Name\n(Spaces will be replaced with underscores)",
							default = "CELL_NAME", strip = True)
	#replace the spaces to keep file names consistent
	cell_name = cell_name.replace(" ", "_")
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

def get_eq_rect_dict(cycle_type):
	#REQUIRED EQUIPMENT
	eq_req_dict = {'psu': False, 'eload': False}
	
	if cycle_type in ("Step Cycle", "Continuous Step Cycles"):
		eq_req_dict = find_eq_req_steps(cycle_settings_list_of_lists)
	else:
		cycle_types = Templates.CycleTypes.cycle_types
		eq_req_dict['psu'] = cycle_types[cycle_type]['supply_req']
		eq_req_dict['eload'] = cycle_types[cycle_type]['load_req']
	
	return eq_rect_dict


################################## BATTERY CYCLING SETUP FUNCTION ######################################

def charge_discharge_control(res_ids_dict, data_out_queue = None, cell_name = None, directory = None, cycle_type = None, 
								cycle_settings_list_of_lists = None, eq_req_dict = None):
	eq_dict = dict()
	try:
		for key in res_ids_dict:
			if res_ids_dict[key]['res_id'] != None:
				eq_dict[key] = eq.connect_to_eq(key, res_ids_dict[key]['class_name'], res_ids_dict[key]['res_id'])
			else:
				eq_dict[key] = None
		
		if cell_name == None:
			cell_name = get_cell_name()
			
		#Get a directory to save the file
		if directory == None:
			directory = FileIO.get_directory("Choose directory to save the cycle logs")
		
		if cycle_type == None:
			cycle_type = get_cycle_type()
		
		if cycle_settings_list_of_lists == None:
			cycle_settings_list_of_lists = get_cycle_settings_list_of_lists()
		
		if eq_rect_dict == None:
			eq_rect_dict = get_eq_rect_dict(cycle_type)
		
		#CHECKING CONNECTION OF REQUIRED EQUIPMENT
		if eq_req_dict['eload'] and eq_dict['eload'] == None:
			print("Eload required for cycle but none connected! Exiting")
			return
	
		if eq_req_dict['psu'] and eq_dict['psu'] == None:
			print("Power Supply required for cycle type but none connected! Exiting")
			return
		#TODO - check cycles with multiple types
		
		initialize_connected_equipment(eq_dict)
		#Now initialize all the equipment that is connected
		
		#TODO - looping a current profile until safety limits are hit
		#TODO - current step profiles to/from csv and/or JSON files
		
		#cycle x times
		cycle_num = 0
		for cycle_settings_list in cycle_settings_list_of_lists:
			print("Cycle {} Starting".format(cycle_num), flush=True)
			filepath = FileIO.start_file(directory, cell_name)
			
			try:
				
				for cycle_settings in cycle_settings_list:
					#Charge only - only using the power supply
					if isinstance(cycle_settings, Templates.ChargeSettings):
						charge_cycle(filepath, cycle_settings.settings, eq_dict['psu'], v_meas_eq = eq_dict['dmm_v'], i_meas_eq = eq_dict['dmm_i'], data_out_queue = data_out_queue)
						
					#Discharge only - only using the eload
					elif isinstance(cycle_settings, Templates.DischargeSettings):
						discharge_cycle(filepath, cycle_settings.settings, eq_dict['eload'], v_meas_eq = eq_dict['dmm_v'], i_meas_eq = eq_dict['dmm_i'], data_out_queue = data_out_queue)
					
					#Step Functions
					elif isinstance(cycle_settings, Templates.StepSettings):
						end_condition = single_step_cycle(filepath, cycle_settings.settings, eload = eq_dict['eload'], psu = eq_dict['psu'], v_meas_eq = eq_dict['dmm_v'], i_meas_eq = eq_dict['dmm_i'], data_out_queue = data_out_queue)
						if end_condition == 'safety_condition':
							break
							
					#Cycle the cell - using both psu and eload
					else:
						cycle_cell(filepath, cycle_settings.settings, eq_dict['eload'], eq_dict['psu'], v_meas_eq = eq_dict['dmm_v'], i_meas_eq = eq_dict['dmm_i'], data_out_queue = data_out_queue)
				
			except KeyboardInterrupt:
				disable_equipment(psu = eq_dict['psu'], eload = eq_dict['eload'])
				exit()
			cycle_num += 1
		
		disable_equipment(psu = eq_dict['psu'], eload = eq_dict['eload'])

		print("All Cycles Completed")
	except Exception:
		traceback.print_exc()

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
				class_name = self.eq_dict[key][0]
				if class_name == 'MATICIAN_FET_BOARD_CH':
					eq_res_ids_dict[key] = {'class_name': class_name, 'res_id': self.eq_dict[key][1].event_and_queue_dict}
				else:
					eq_res_ids_dict[key] = {'class_name': class_name, 'res_id': self.eq_dict[key][1].inst.resource_name}
		
		return eq_res_ids_dict
		
	def disconnect_all_assigned_eq(self):
		#disconnect from equipment so that we can pass the resource ids to the
		#charge_discharge_control function and reconnect to the devices there
		for key in self.eq_dict:
			if self.eq_dict[key] != None:
				try:
					self.eq_dict[key][1].inst.close()
				except AttributeError:
					pass #temporary fix for 'virtual instrument' - TODO - figure out a way to do this more properly

if __name__ == '__main__':
	print("Use the battery_test.py script")
	#charge_discharge_control()
