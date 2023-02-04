#python pyvisa commands to emulate a combination of eloads as a single eload

import pyvisa
import time
import easygui as eg
import equipment as eq

# E-Load
class PARALLEL:
    # Initialize the Parallel E-Load
    
    has_remote_sense = False
    
    def __init__(self, resource_id = None, resources_list = None):
        
        #combine 2 or more eloads in parallel and split the current between them
        #need to create a 'virtual eload' here that emulates the other eload classes.
        
        self.class_name_1 = None
        self.class_name_2 = None
        self.res_id_1 = None
        self.res_id_2 = None
        self.setup_dict_1 = {'remote_sense': None}
        self.setup_dict_2 = {'remote_sense': None}
        
        print(resource_id)
        if resource_id != None:
            self.class_name_1 = resource_id['class_name_1']
            self.class_name_2 = resource_id['class_name_2']
            self.res_id_1 = resource_id['res_id_1']
            self.res_id_2 = resource_id['res_id_2']
            self.setup_dict_1 = {'remote_sense': resource_id['remote_sense_1']}
            self.setup_dict_2 = {'remote_sense': resource_id['remote_sense_2']}
            #self.use_remote_sense_1 = resource_id['use_remote_sense_1']
            #self.use_remote_sense_2 = resource_id['use_remote_sense_2']
        
        
        #choose_eload(self, class_name = None, resource_id = None, setup_dict = None, resources_list = None)
        eload_1_list = eq.eLoads.choose_eload(self.class_name_1, self.res_id_1, self.setup_dict_1)
        eload_2_list = eq.eLoads.choose_eload(self.class_name_2, self.res_id_2, self.setup_dict_2)
        
        self.class_name_1 = eload_1_list[0]
        self.class_name_2 = eload_2_list[0]
        self.eload1 = eload_1_list[1]
        self.eload2 = eload_2_list[1]
        self.use_remote_sense_1 = eload_1_list[2]
        self.use_remote_sense_2 = eload_2_list[2]
        
        #We want to load each eload proportionally to its max load.
        #We will start by sharing power proportionally, but should account in the future for uneven current ranges.
        #e.g. a high power load with 20A 500V 1000W and a lower power load wit 60A 120V 250W
        self.max_current = self.eload1.max_current + self.eload2.max_current
        self.max_power = self.eload1.max_power + self.eload2.max_power
        
        self.eload1_current_share = self.eload1.max_power / self.max_power
        self.eload2_current_share = self.eload2.max_power / self.max_power
        
        self.mode = "CURR"
        self.set_mode_current()
        
    def set_mode_current(self):
        self.eload1.set_mode_current()
        self.eload2.set_mode_current()
        self.mode = "CURR"
        
    def set_mode_voltage(self):
        print("ERROR - CV mode with parallel eloads is not allowed")
    
    # To Set E-Load in Amps 
    def set_current(self, current_setpoint_A):	
        if self.mode != "CURR":
            print("ERROR - E-load not in correct mode")
            return
        self.eload1.set_current(current_setpoint_A * self.eload1_current_share)
        self.eload2.set_current(current_setpoint_A * self.eload2_current_share)

    def toggle_output(self, state):
        self.eload1.toggle_output(state)
        self.eload2.toggle_output(state)
    
    def remote_sense(self, state):
        #only do remote sense on a single eload, we only need a single measurement and it doesn't compensate for anything.
        self.eload1.remote_sense(state)
    
    def lock_front_panel(self, state):
        self.eload1.lock_front_panel(state)
        self.eload2.lock_front_panel(state)
    
    def measure_voltage(self):
        #use only the voltage measurement from the first eload
        return self.eload1.measure_voltage()

    def measure_current(self):
        return (self.eload1.measure_current() + self.eload2.measure_current())
        
    #def __del__(self):
    #	pass