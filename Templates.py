#class to hold the templates for input/outputs settings

import easygui as eg
import jsonIO
import json
import os


######################  Statistics to gather for each cycle  ###############
class CycleStats:
    
    def __init__(self):
        self.stats = {
            "cell_name":				0,
            "charge_capacity_ah": 		0,
            "charge_capacity_wh": 		0,
            "charge_time_h": 			0,
            "charge_current_a":			0,
            "charge_max_temp_c":		0,
            "charge_start_time":		0,
            "charge_end_time":			0,
            "charge_end_v":				0,
            "discharge_capacity_ah": 	0,
            "discharge_capacity_wh": 	0,
            "discharge_time_h": 		0,
            "discharge_current_a":		0,
            "discharge_max_temp_c":		0,
            "discharge_start_time":		0,
            "discharge_end_time":		0,
            "discharge_end_v":			0
        }

#####################  AVAILABLE CYCLE TYPES  ####################
class CycleTypes:
    
    cycle_types = {
        "Single_CC_Cycle": 								{'func_call': '', 'str_chg_opt': True},
        "One_Setting_Continuous_CC_Cycles_With_Rest": 	{'func_call': '', 'str_chg_opt': True},
        "Two_Setting_Continuous_CC_Cycles_With_Rest": 	{'func_call': '', 'str_chg_opt': True},
        "CC_Charge_Only": 								{'func_call': '', 'str_chg_opt': False},
        "CC_Discharge_Only": 							{'func_call': '', 'str_chg_opt': False},
        "Step_Cycle":									{'func_call': '', 'str_chg_opt': False},
        "Continuous_Step_Cycles":						{'func_call': '', 'str_chg_opt': True},
        "Single_IR_Test":	        					{'func_call': '', 'str_chg_opt': False},
        "Repeated_IR_Discharge_Test":      	            {'func_call': '', 'str_chg_opt': True}
    }
    
    cycle_requirements = {
        "charge": 		{'load_req': False, 'supply_req': True},
        "discharge": 	{'load_req': True,  'supply_req': False},
        "step": 		{'load_req': False, 'supply_req': False},
        "rest": 		{'load_req': False, 'supply_req': False},
        "cycle": 		{'load_req': True,  'supply_req': True}
    }

###############  CYCLE  #######################
class CycleSettings:

    def __init__(self):
        self.settings = { 
            "cycle_type":				'cycle',
            "charge_end_v": 			4.2,
            "charge_a": 				1,
            "charge_end_a": 			0.3,
            "rest_after_charge_min": 	20, 
            "discharge_end_v": 			2.5,
            "discharge_a": 				-1,
            "rest_after_discharge_min": 20,
            "meas_log_int_s": 			1
        }
        self.valid_strings = {
            "cycle_type":				('cycle',)
        }
    
    def get_cycle_settings(self, cycle_name = ""):
        self.settings = jsonIO.get_cycle_settings(self.settings, self.valid_strings, cycle_name)
    
    def export_cycle_settings(self, cycle_name = ""):
        jsonIO.export_cycle_settings(self.settings, cycle_name)
    
    def import_cycle_settings(self, cycle_name = ""):
        self.settings = jsonIO.import_cycle_settings(cycle_name)

###############  CHARGE  #####################

class ChargeSettings(CycleSettings):

    def __init__(self):
        self.settings = {
            "cycle_type":				'charge',
            "charge_end_v": 			4.2,
            "charge_a": 				1,
            "charge_end_a": 			0.1,
            "meas_log_int_s": 			1,
            "safety_min_voltage_v":		2.45,
            "safety_max_voltage_v":		4.25,
            "safety_min_current_a":		-10,
            "safety_max_current_a":		10,
            "safety_max_time_s":		100 #positive values give a value in seconds, negative values and 0 will disable the time safety check
        }
        self.valid_strings = {
            "cycle_type":				('charge',)
        }
        
###############  DISCHARGE  #####################

class DischargeSettings(CycleSettings):

    def __init__(self):
        self.settings = { 
            "cycle_type":				'discharge',
            "discharge_end_v": 			2.5,
            "discharge_a": 				-1,
            "meas_log_int_s": 			1,
            "safety_min_voltage_v":		2.45,
            "safety_max_voltage_v":		4.25,
            "safety_min_current_a":		-10,
            "safety_max_current_a":		10,
            "safety_max_time_s":		100 #positive values give a value in seconds, negative values and 0 will disable the time safety check
        }
        self.valid_strings = {
            "cycle_type":				('discharge',)
        }

###############  REST  #####################

class RestSettings(CycleSettings):

    def __init__(self):
        self.settings = { 
            "cycle_type":				'rest',
            "rest_time_min":			5,
            "meas_log_int_s": 			1
        }
        self.valid_strings = {
            "cycle_type":				('rest',)
        }

#################  STEPS  ############

class StepSettings(CycleSettings):
    def __init__(self):
        self.settings = {
            "cycle_type":				'step',
            "drive_style":				'none', #'current_a', 'voltage_v', 'none'
            "drive_value":				0,
            "drive_value_other":		0,
            "end_style":				'time_s', #'time_s', 'current_a', 'voltage_v'
            "end_condition":			'greater', #'greater', 'lesser'
            "end_value":				10,
            "meas_log_int_s":			1,
            "safety_min_voltage_v":		2.45,
            "safety_max_voltage_v":		4.25,
            "safety_min_current_a":		-10,
            "safety_max_current_a":		10,
            "safety_max_time_s":		100 #positive values give a value in seconds, negative values and 0 will disable the time safety check
        }
        self.valid_strings = {
            "cycle_type":				('step',),
            "drive_style":				('current_a', 'voltage_v', 'none'),
            "end_style":				('time_s', 'current_a', 'voltage_v'),
            "end_condition":			('greater', 'lesser')
        }

################ INTERNAL RESISTANCE BATTERY TEST ##############

class SingleIRSettings(CycleSettings):
    def __init__(self):
        self.settings = {
            "cycle_type":               'single_ir_test',
            "current_1_a":              -1,
            "time_1_s":                 5,
            "current_2_a":              -5,
            "time_2_s":                 5,
            "psu_voltage_if_pos_i":		0,
            "meas_log_int_s":			1,
            "safety_min_voltage_v":		2.45,
            "safety_max_voltage_v":		4.25,
            "safety_min_current_a":		-10,
            "safety_max_current_a":		10,
            "safety_max_time_s":		100 #positive values give a value in seconds, negative values and 0 will disable the time safety check
        }
        self.valid_strings = {
            "cycle_type":				('single_ir_test',)
        }

class RepeatedIRSettings(CycleSettings):
    def __init__(self):
        self.settings = {
            "cycle_type":               'repeated_ir_test',
            "charge_end_v": 			4.2,
            "charge_a": 				1,
            "charge_end_a": 			0.1,
            "rest_after_charge_min":	20,
            "current_1_a":              -1,
            "time_1_s":                 5,
            "current_2_a":              -5,
            "time_2_s":                 5,
            "psu_voltage_if_pos_i":		0,
            "meas_log_int_s":			1,
            "safety_min_voltage_v":		2.45,
            "safety_max_voltage_v":		4.25,
            "safety_min_current_a":		-10,
            "safety_max_current_a":		10,
            "estimated_capacity_ah":    2.5
        }
        self.valid_strings = {
            "cycle_type":				('repeated_ir_test',)
        }

####################  DC DC TESTING  ############

class DcdcTestSettings():

    def __init__(self):
        self.settings = {
            "psu_voltage_min":				4,
            "psu_voltage_max":				7,
            "num_voltage_steps":			4,
            "psu_current_limit_a":			2,
            "load_current_min":				0.1,
            "load_current_max": 			1,
            "num_current_steps":			10,
            "step_delay_s":					2,
            "measurement_samples_for_avg":	10
        }
        self.valid_strings = {}

class DcdcSweepSettings():
    
    def __init__(self):
        self.settings = {
            "psu_voltage":					4,
            "psu_current_limit_a":			2,
            "load_current_min":				0.1,
            "load_current_max": 			1,
            "num_current_steps":			10,
            "step_delay_s":					2,
            "measurement_samples_for_avg":	10
        }
        self.valid_strings = {}

######################### MPPT TESTING ################

class EloadCVSweepSettings():
    
    def __init__(self):
        self.settings = {
            "min_cv_voltage":				0,
            "max_cv_voltage":				30,
            "num_voltage_steps":			10,
            "step_delay_s":					1,
            "measurement_samples_for_avg":	10
        }
        self.valid_strings = {}
    