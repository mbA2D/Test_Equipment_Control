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



class CyclingControl():
    
    def __init__(self):
        self.eq_dict = None
        self.input_dict = None
        pass
    
    ################################################## EQUIPMENT SETUP #############################################

    def init_eload(self):
        self.eq_dict['eload'].toggle_output(False)
        self.eq_dict['eload'].set_current(0)
        
    def init_psu(self):
        self.eq_dict['psu'].toggle_output(False)
        self.eq_dict['psu'].set_voltage(0)
        self.eq_dict['psu'].set_current(0)

    def init_dmm_v(self, device = None):
        #test voltage measurement to ensure everything is set up correctly
        #often the first measurement takes longer as it needs to setup range, NPLC
        #This also gets it setup to the correct range.
        #TODO - careful of batteries that will require a range switch during the charge
        #	  - this could lead to a measurement delay. 6S happens to cross the 20V range.
        if device is not None:
            device.measure_voltage()
        else:
            self.eq_dict['dmm_v'].measure_voltage()

    def init_dmm_i(self, device = None):
        #test measurement to ensure everything is set up correctly
        #and the fisrt measurement which often takes longer is out of the way
        if device is not None:
            device.measure_current()
        else:
            self.eq_dict['dmm_i'].measure_current()
        
    def init_dmm_t(self, device = None):
        #test measurement to ensure everything is set up correctly
        #and the fisrt measurement which often takes longer is out of the way
        if device is not None:
            device.measure_temperature()
        else:
            self.eq_dict['dmm_t'].measure_temperature()

    def init_relay_board(self):
        #turn off all channels
        self.eq_dict['relay_board'].connect_eload(False)
        self.eq_dict['relay_board'].connect_psu(False)
        
    def initialize_connected_equipment(self):
        #print("initialize_connected_equipment")
        
        if self.eq_dict['eload'] != None:	
            self.init_eload()
        if self.eq_dict['psu'] != None:
            self.init_psu()
        if self.eq_dict['dmm_v'] != None:
            self.init_dmm_v()
        if self.eq_dict['dmm_i'] != None:
            self.init_dmm_i()
        if self.eq_dict.get('relay_board') != None:
            self.init_relay_board()
        
        #all the extra dmms:
        dmm_postfixes = ['v', 'i', 't']
        for postfix in dmm_postfixes:
            valid_device = True
            count = 0
            while valid_device:
                dev_name = 'dmm_{}{}'.format(postfix, count)
                dev = self.eq_dict.get(dev_name)
                if dev != None:
                    if postfix == 'v':
                        self.init_dmm_v(dev)
                    elif postfix == 'i':
                        self.init_dmm_i(dev)
                    elif postfix == 't':
                        self.init_dmm_t(dev)
                else:
                    valid_device = False
                count += 1

    def disable_equipment_single(self, equipment):
        if equipment != None:
            time.sleep(0.02)
            equipment.set_current(0) #Turn current to 0 first to try and eliminate arcing in a relay inside an eload that disconnects the output
            time.sleep(0.02)
            equipment.toggle_output(False)
            time.sleep(0.02)

    def disable_equipment(self):
        if self.eq_dict['psu'] != None:
            self.disable_equipment_single(self.eq_dict['psu'])
            #print("Disabled PSU")
        if self.eq_dict['eload'] != None:
            self.disable_equipment_single(self.eq_dict['eload'])
            #print("Disabled Eload")
        if self.eq_dict.get('relay_board') != None: #TODO - figure out voltage measurement during idle. This might disconnect all our equipment.
            self.eq_dict['relay_board'].connect_eload(False)
            self.eq_dict['relay_board'].connect_psu(False)

    def connect_proper_equipment(self, eq_req_for_cycle_dict):
        #If a relay board is connected (that can connect or disconnect equipment) then we want to have only the necessary equipment connected on each cycle
        #For now, we will assume that all 'relay boards' can only be connected to PSUs or eLoads - which channels these are connected to happens on setup of the relay board.
        #But only 2 channels and only 1 of each equipment.
        
        #TODO - add a voltage check to see if equipment switched properly.
        
        #Disconnect first (break before make)
        #if not required but it is connected, then break connection
        if not eq_req_for_cycle_dict['psu'] and self.eq_dict['relay_board'].psu_connected():
            self.disable_equipment_single(self.eq_dict['psu'])
            self.eq_dict['relay_board'].connect_psu(False)
        if not eq_req_for_cycle_dict['eload'] and self.eq_dict['relay_board'].eload_connected():
            self.disable_equipment_single(self.eq_dict['eload'])
            self.eq_dict['relay_board'].connect_eload(False)
        
        #Connect second (break before make)
        #if required but is not connected, then make connection
        if eq_req_for_cycle_dict['psu'] and not self.eq_dict['relay_board'].psu_connected(): #if changing states
            #ensure psu output is disabled before connecting
            self.disable_equipment_single(self.eq_dict['psu'])
            self.eq_dict['relay_board'].connect_psu(True)
        if eq_req_for_cycle_dict['eload'] and not self.eq_dict['relay_board'].eload_connected():
            #ensure eload output is disabled before connecting
            self.disable_equipment_single(self.eq_dict['eload'])
            self.eq_dict['relay_board'].connect_eload(True)

        time.sleep(0.1) #Delay to make sure all the relays click.


    ###################################################### TEST CONTROL ###################################################
       
    def start_step(self, step_settings):
        #This function will set all the supplies to the settings given in the step
        
        #CURRENT DRIVEN
        if step_settings["drive_style"] == 'current_a':
            FileIO.write_line_txt(self.log_filepath, "Current-Driven Step Setup")
            if step_settings["drive_value"] > 0:
                #charge - turn off eload first if connected, leave psu on.
                self.disable_equipment_single(self.eq_dict['eload'])
                if self.eq_dict['psu'] != None:
                    time.sleep(0.01)
                    self.eq_dict['psu'].set_current(step_settings["drive_value"])
                    time.sleep(0.01)
                    self.eq_dict['psu'].set_voltage(step_settings["drive_value_other"])
                    time.sleep(0.01)
                    self.eq_dict['psu'].toggle_output(True)
                    time.sleep(0.01)
                else:
                    print("No PSU Connected. Can't Charge! Exiting.")
                    FileIO.write_line_txt(self.log_filepath, "ERROR - No PSU Connected. Can't Charge! Exiting.")
                    return False
            elif step_settings["drive_value"] < 0:
                #discharge - turn off power supply if connected, leave eload on.
                self.disable_equipment_single(self.eq_dict['psu'])
                if self.eq_dict['eload'] != None:
                    time.sleep(0.01)
                    self.eq_dict['eload'].set_current(step_settings["drive_value"])
                    time.sleep(0.01)
                    self.eq_dict['eload'].toggle_output(True)
                    time.sleep(0.01)
                    #we're in constant current mode - can't set a voltage.
                else:
                    print("No Eload Connected. Can't Discharge! Exiting.")
                    FileIO.write_line_txt(self.log_filepath, "ERROR - No Eload Connected. Can't Discharge! Exiting.")
                    return False
            elif step_settings["drive_value"] == 0:
                #rest
                self.disable_equipment(self.eq_dict)
        
        #VOLTAGE DRIVEN
        elif step_settings["drive_style"] == 'voltage_v':
            FileIO.write_line_txt(self.log_filepath, "Voltage-Driven Step Setup")
            #positive current
            if step_settings["drive_value_other"] >= 0:
                self.disable_equipment_single(self.eq_dict['eload']) #turn off eload
                if self.eq_dict['psu'] != None:
                    time.sleep(0.01)
                    self.eq_dict['psu'].set_current(step_settings["drive_value_other"])
                    time.sleep(0.01)
                    self.eq_dict['psu'].set_voltage(step_settings["drive_value"])
                    time.sleep(0.01)
                    self.eq_dict['psu'].toggle_output(True)
                    time.sleep(0.01)
                else:
                    print("No PSU Connected. Can't Charge! Exiting.")
                    FileIO.write_line_txt(self.log_filepath, "ERROR - No PSU Connected. Can't Charge! Exiting.")
                    return False
            #TODO - needs CV mode on eloads
            else:
                print("Voltage Driven Step Not Yet Implemented for negative current. Exiting.")
                FileIO.write_line_txt(self.log_filepath, "ERROR - Voltage Driven Step Not Yet Implemented for negative current. Exiting.")
                #Ensure everything is off since not yet implemented.
                self.disable_equipment(self.eq_dict)
                return False
        
        #NOT DRIVEN
        elif step_settings["drive_style"] == 'none':
            FileIO.write_line_txt(self.log_filepath, "Non-Driven (Rest) Step Setup")
            #Ensure all sources and loads are off.
            self.disable_equipment(self.eq_dict)
        
        #return True for a successful step start.
        #print("start_step returning True")
        return True

    def evaluate_end_condition(self, step_settings, data, data_in_queue):
        #evaluates different end conditions (voltage, current, time)
        #returns true if the end condition has been met (e.g. voltage hits lower bound, current hits lower bound, etc.)
        #also returns true if any of the safety settings have been exceeded
        
        #print(data)
        
        #REQUEST TO END
        if self.end_signal(data_in_queue):
            return 'end_request'
        
        
        #SAFETY SETTINGS
        #Voltage and current limits are always active
        if data["Voltage"] < step_settings["safety_min_voltage_v"]:
            FileIO.write_line_txt(self.log_filepath, f'WARNING - Min Voltage Limit Hit! Data: {data["Voltage"]}V Limit: {step_settings["safety_min_voltage_v"]}V')
            return 'safety_condition'
        if data["Voltage"] > step_settings["safety_max_voltage_v"]:
            FileIO.write_line_txt(self.log_filepath, f'WARNING - Max Voltage Limit Hit! Data: {data["Voltage"]}V Limit: {step_settings["safety_max_voltage_v"]}V')
            return 'safety_condition'
        if data["Current"] < step_settings["safety_min_current_a"]:
            FileIO.write_line_txt(self.log_filepath, f'WARNING - Min Current Limit Hit! Data: {data["Current"]}A Limit: {step_settings["safety_min_current_a"]}A')
            return 'safety_condition'
        if data["Current"] > step_settings["safety_max_current_a"]:
            FileIO.write_line_txt(self.log_filepath, f'WARNING - Max Current Limit Hit! Data: {data["Current"]}A Limit: {step_settings["safety_max_current_a"]}A')
            return 'safety_condition'
            
        if (step_settings["safety_max_time_s"] > 0 and 
            data["Data_Timestamp_From_Step_Start"] > step_settings["safety_max_time_s"]):
            FileIO.write_line_txt(self.log_filepath, f'WARNING - Max Time Limit Hit! Data: {data["Data_Timestamp_From_Step_Start"]}s Limit: {step_settings["safety_max_time_s"]}s')
            return 'safety_condition'
        
        
        #CYCLE END SETTINGS
        #Ending the cycle:
        cycle_end_voltage = step_settings.get("cycle_end_voltage_v")
        if cycle_end_voltage is not None:
            if data["Voltage"] <= cycle_end_voltage:
                return 'cycle_end_condition'
                
        cycle_end_time = step_settings.get("cycle_end_time_s")
        if cycle_end_time is not None:
            if data["Data_Timestamp_From_Step_Start"] <= cycle_end_time:
                return 'cycle_end_condition'
        
        
        #STEP END CONDITIONS
        end_reason = None
        
        #Ending the Step
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
                end_reason = 'none'
        elif step_settings["end_condition"] == 'lesser':
            #For positive current less than value endpoint, also check the voltage to be close to the end voltage
            if step_settings["end_style"] == 'current_a' and step_settings["drive_style"] == 'voltage_v' and step_settings["end_value"] > 0:
                if data["Voltage"] > 0.98*step_settings["drive_value"] and left_comparator < step_settings["end_value"]:
                    return 'end_condition'
                else:
                    end_reason = 'none'
            elif left_comparator < step_settings["end_value"]:
                return 'end_condition'
            else:
                end_reason = 'none'
        
        if end_reason == 'none':
            return end_reason
        
        #return settings so that we end the step if the settings were incorrectly configured.
        return 'settings'


    ######################### MEASURING ######################

    def measure_battery(self, data_out_queue = None, step_index = 0, current_time = None):
        data_dict = {'type': 'measurement', 'data': {}}
        data_dict['data']["Voltage"] = 0
        data_dict['data']["Current"] = 0
        data_dict['data']["Step_Index"] = step_index
        
        if current_time is not None:
            data_dict['data']["Data_Timestamp"] = time.perf_counter()
        else:
            data_dict['data']["Data_Timestamp"] = current_time
        
        if self.eq_dict['dmm_v'] is not None:
            data_dict['data']["Voltage"] = self.eq_dict['dmm_v'].measure_voltage()
        if self.eq_dict['dmm_i'] is not None:
            data_dict['data']["Current"] = self.eq_dict['dmm_i'].measure_current()
        
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
                        measurement = self.eq_dict[dev_name].measure_voltage()
                    elif prefix == 'i':
                        measurement = self.eq_dict[dev_name].measure_current()
                    elif prefix == 't':
                        measurement = self.eq_dict[dev_name].measure_temperature()
                    data_dict['data'][dev_name] = measurement
                    index = index + 1
            except KeyError:
                continue
        
        #Send voltage and current to be displayed in the main test window
        if data_out_queue != None:
            #add the new data to the output queue
            data_out_queue.put_nowait(data_dict)
        
        #print("Measurement: {}".format(data_dict['data']))
        return data_dict['data']


    ########################## CHARGE, DISCHARGE, REST #############################

    def end_signal(self, data_in_queue):
        end_signal = False
        try:
            signal = data_in_queue.get_nowait()
            if signal == 'stop':
                end_signal = True
        except queue.Empty:
            pass
        return end_signal
        
    def idle_cell(self, data_out_queue = None, data_in_queue = None):
        #Measures voltage (and current if available) when no other process is running to have live voltage updates
        while not self.end_signal(data_in_queue):
            self.measure_battery(data_out_queue = data_out_queue)
            time.sleep(1)

    def step_cell(self, step_settings, data_out_queue = None, data_in_queue = None, step_index = 0):
        
        if self.start_step(step_settings):
            FileIO.write_line_txt(self.log_filepath, "Start Step Successful")
            
            perf_counter_start = time.perf_counter()
            step_start_time_perf = perf_counter_start
            
            data = dict()
            data.update(self.measure_battery(current_time = step_start_time_perf))
            data["Data_Timestamp_From_Step_Start"] = 0
            FileIO.write_data(self.csv_filepath, data) #Log the measurements from the start of the step - e.g. OCV point for starting SoC.
            
            #If we are charging to the end of a CC cycle, then we need to not exit immediately.
            if (step_settings["drive_style"] == "voltage_v" and
                step_settings["end_style"] == "current_a" and
                step_settings["end_condition"] == "lesser"):
            
                data["Current"] = step_settings["drive_value_other"]
            
            end_condition = self.evaluate_end_condition(step_settings, data, data_in_queue)
            FileIO.write_line_txt(self.log_filepath, "End Condition Before Loop: {}".format(end_condition))
            
            #Do the measurements and check the end conditions at every logging interval
            while end_condition == 'none':
                perf_counter_end = perf_counter_start + step_settings["meas_log_int_s"]
                perf_counter_start = time.perf_counter()
                
                perf_counter_delay = perf_counter_start
                while perf_counter_delay < perf_counter_end:
                    time.sleep(0.001) #1ms
                    perf_counter_delay = time.perf_counter()
                
                data.update(self.measure_battery(data_out_queue = data_out_queue, step_index = step_index, current_time = perf_counter_delay))
                data["Data_Timestamp_From_Step_Start"] = (data["Data_Timestamp"] - step_start_time_perf)
                end_condition = self.evaluate_end_condition(step_settings, data, data_in_queue)
                FileIO.write_data(self.csv_filepath, data)
            
            #if the end condition is due to safety settings, then we want to end all future steps as well so return the exit reason
            return end_condition
        
        else:
            print("Step Setup Failed")
            FileIO.write_line_txt(self.log_filepath, "ERROR - Step Setup Failed!")
            return 'settings'

    ################################## SETTING CYCLE, CHARGE, DISCHARGE ############################

    def idle_cell_cycle(self, data_out_queue = None, data_in_queue = None):
        if self.eq_dict['dmm_v'] == None or self.eq_dict['dmm_v'] == self.eq_dict['eload'] or self.eq_dict['dmm_v'] == self.eq_dict['psu']:
            if self.eq_dict['eload'] != None:
                self.eq_dict['dmm_v'] = self.eq_dict['eload']
            elif self.eq_dict['psu'] != None:
                self.eq_dict['dmm_v'] = self.eq_dict['psu']
            else:
                print("No Voltage Measurement Equipment Connected! Exiting")
                return 'settings'
        
        if self.eq_dict['dmm_i'] == None or self.eq_dict['dmm_i'] == self.eq_dict['eload'] or self.eq_dict['dmm_i'] == self.eq_dict['psu']:
            if self.eq_dict['eload'] != None:
                self.eq_dict['dmm_i'] = self.eq_dict['eload']
            elif self.eq_dict['psu'] != None:
                self.eq_dict['dmm_i'] = self.eq_dict['psu']
                
        self.idle_cell(data_out_queue = data_out_queue, data_in_queue = data_in_queue)

    def single_step_cycle(self, step_settings, data_out_queue = None, data_in_queue = None, ch_num = None, step_index = 0):

        #if we don't have separate voltage measurement equipment, then choose what to use:
        if self.eq_dict['dmm_v'] == None or self.eq_dict['dmm_v'] == self.eq_dict['eload'] or self.eq_dict['dmm_v'] == self.eq_dict['psu']:
            if self.eq_dict['eload'] != None:
                self.eq_dict['dmm_v'] = self.eq_dict['eload']
            elif self.eq_dict['psu'] != None:
                self.eq_dict['dmm_v'] = self.eq_dict['psu']
            else:
                print("No Voltage Measurement Equipment Connected! Exiting")
                return 'settings'
        
        FileIO.write_line_txt(self.log_filepath, "Voltage Measurement Equipment Chosen")
        
        #if we don't have separate current measurement equipment, then choose what to use:
        if self.eq_dict['dmm_i'] == None or self.eq_dict['dmm_i'] == self.eq_dict['eload'] or self.eq_dict['dmm_i'] == self.eq_dict['psu']:
            resting = False
            left_comparator = 0
            if step_settings["drive_style"] == 'current_a':
                left_comparator = step_settings["drive_value"]
            elif step_settings["drive_style"] == 'voltage_v':
                left_comparator = step_settings["drive_value_other"]
            if step_settings["drive_style"] == ['none'] or left_comparator == 0:
                resting = True
            
            if left_comparator > 0 and self.eq_dict['psu'] != None:
                self.eq_dict['dmm_i'] = self.eq_dict['psu'] #current measurement during charge
            elif left_comparator < 0 and self.eq_dict['eload'] != None:
                self.eq_dict['dmm_i'] = self.eq_dict['eload'] #current measurement during discharge
            elif not resting:
                print("No Current Measurement Equipment Connected and not Resting! Exiting")
                return 'settings'
        
        FileIO.write_line_txt(self.log_filepath, "Current Measurement Equipment Chosen")
        
        end_reason = 'none'
        end_reason = self.step_cell(step_settings, data_out_queue = data_out_queue, data_in_queue = data_in_queue, step_index = step_index)

        return end_reason
        
    ################################## BATTERY CYCLING SETUP FUNCTION ######################################
    def idle_control(self, res_ids_dict, data_out_queue = None, data_in_queue = None):
        try:
            self.eq_dict = eq.get_equipment_dict(res_ids_dict)
            self.idle_cell_cycle(data_out_queue = data_out_queue, data_in_queue = data_in_queue)
            self.disable_equipment()
        except Exception:
            traceback.print_exc()
        
    def charge_discharge_control(self, res_ids_dict, data_out_queue = None, data_in_queue = None, input_dict = None, ch_num = None):
        try:
            c_i = CyclingInfo()
            
            self.eq_dict = eq.get_equipment_dict(res_ids_dict)
            #print("Got Equipment Dict")
            
            self.input_dict = input_dict
            if self.input_dict == None:
                self.input_dict = c_i.get_input_dict()
            
            #CHECKING CONNECTION OF REQUIRED EQUIPMENT
            if self.input_dict['eq_req_dict']['eload'] and self.eq_dict['eload'] == None:
                print("Eload required for cycle but none connected! Exiting")
                return
        
            if self.input_dict['eq_req_dict']['psu'] and self.eq_dict['psu'] == None:
                print("Power Supply required for cycle type but none connected! Exiting")
                return
            
            #Ensure that the proper directories exist for logging
            csv_dir = FileIO.ensure_subdir_exists_dir(self.input_dict['directory'], self.input_dict['cell_name'])
            log_dir = FileIO.ensure_subdir_exists_dir(csv_dir, 'logs')
            
            #Now initialize all the equipment that is connected
            self.initialize_connected_equipment()
            
            #TODO - looping a current profile until safety limits are hit
            #TODO - current step profiles to/from csv
            
            #cycle x times
            end_list_of_lists = False
            end_condition = 'none'
            
            for cycle_num, settings_cycle_list in enumerate(self.input_dict['settings_cycle_list_step_list']):
                
                self.csv_filepath = FileIO.start_file(csv_dir, "{} {} {}".format(self.input_dict['cell_name'], self.input_dict['cycle_type'], settings_cycle_list[0]["cycle_display"]), extension = '.csv')
                self.log_filepath = FileIO.start_file(log_dir, "{} {} {}".format(self.input_dict['cell_name'], self.input_dict['cycle_type'], settings_cycle_list[0]["cycle_display"]), extension = '.txt')
                
                print("CH{} - Cycle {} Starting {}".format(ch_num, cycle_num, time.ctime()), flush=True)
                FileIO.write_line_txt(log_filepath, "Cycle {} Starting".format(cycle_num))
                FileIO.write_line_txt(log_filepath, "Cycle Settings List: {}".format(settings_cycle_list))
                
                try:
                
                    #TODO - If we have a relay board to disconnect equipment, ensure we are still connected to the correct equipment
                    if self.eq_dict.get('relay_board') != None:
                        #determine the equipment that we need for this cycle
                        eq_req_for_cycle_dict = c_i.get_eq_req_for_cycle(settings_cycle_list)
                        self.connect_proper_equipment(eq_req_for_cycle_dict)
                
                    for step_num, step_settings in enumerate(settings_cycle_list):
                        FileIO.write_line_txt(self.log_filepath, "Cycle {} Step {} Starting".format(cycle_num, step_num))
                        FileIO.write_line_txt(self.log_filepath, "Step Settings: {}".format(step_settings))
                        
                        #print("Cycle Settings: {}".format(step_settings))
                        end_condition = 'none'
                        
                        #Set label text for current and next status
                        current_cycle_type = step_settings["cycle_type"]
                        current_display_status = step_settings["cycle_display"]
                        try:
                            next_display_status = settings_cycle_list[step_num + 1]["cycle_display"]
                        except (IndexError, TypeError):
                            try:
                                next_display_status = self.input_dict['settings_cycle_list_step_list'][cycle_num + 1][0]["cycle_display"]
                            except (IndexError, TypeError):
                                next_display_status = "Idle"
                        
                        data_out_queue.put_nowait({'type': 'status', 'data': (current_display_status, next_display_status)})
                        
                        #Step Functions
                        if current_cycle_type == 'step':
                            end_condition = self.single_step_cycle(step_settings, data_out_queue = data_out_queue, data_in_queue = data_in_queue, ch_num = ch_num, step_index = step_num)
                        
                        FileIO.write_line_txt(self.log_filepath, "Cycle {} Step {} Ending. Reason: {}".format(cycle_num, step_num, end_condition))
                        
                        #End Conditions
                        if end_condition == 'cycle_end_condition':
                            self.disable_equipment()
                            #print("Cycle End Condition. Break.")
                            break
                        
                        if end_condition == 'safety_condition':
                            #send something back to the main queue to say a safety condition was hit.
                            data_out_queue.put_nowait({'type': 'end_condition', 'data': 'safety_condition'})
                        
                        if end_condition == 'end_request' or end_condition == 'safety_condition':
                            end_list_of_lists = True
                            #print("End Request or Safety. Break.")
                            break
                    
                    if end_list_of_lists:
                        FileIO.write_line_txt(self.log_filepath, "Ending all cycles")
                        break
                    
                    FileIO.write_line_txt(self.log_filepath, "Cycle {} Ending".format(cycle_num))    
                
                except KeyboardInterrupt:
                    self.disable_equipment()
                    FileIO.write_line_txt(self.log_filepath, "Keyboard Interrupt")
                    exit()
                    
            self.disable_equipment()
            
            
            if end_condition == 'safety_condition':
                print("CH{} - SAFETY LIMIT HIT: {}".format(ch_num, time.ctime()), flush=True)
                FileIO.write_line_txt(self.log_filepath, "SAFETY LIMIT HIT!") 
            else:
                print("CH{} - All Cycles Completed: {}".format(ch_num, time.ctime()), flush=True)
                FileIO.write_line_txt(self.log_filepath, "All Cycles Completed!")
        except Exception:
            exception = traceback.format_exc()
            print(exception)
            FileIO.write_line_txt(self.log_filepath, exception)


class CyclingSettings():
    ###################################################### GATHERING REQUIRED INPUTS FOR EACH CYCLE TYPE ########################################################
    
    def __init__(self):
        pass
    
    def single_cc_cycle_info(self):
        #charge then discharge
        cycle_test_settings = Templates.CycleSettings()
        cycle_test_settings.get_cycle_settings("Cycle Test")
        
        if cycle_test_settings.settings == None:
            return None
        
        #Charge
        charge_settings = Templates.ChargeSettings()
        
        charge_settings.settings["charge_end_v"] = cycle_test_settings.settings["charge_end_v"]
        charge_settings.settings["charge_a"] = cycle_test_settings.settings["charge_a"]
        charge_settings.settings["charge_end_a"] = cycle_test_settings.settings["charge_end_a"]
        charge_settings.settings["meas_log_int_s"] = cycle_test_settings.settings["meas_log_int_s"]
        charge_settings.settings["safety_max_current_a"] = cycle_test_settings.settings["safety_max_current_a"]
        charge_settings.settings["safety_min_current_a"] = cycle_test_settings.settings["safety_min_current_a"]
        charge_settings.settings["safety_max_voltage_v"] = cycle_test_settings.settings["safety_max_voltage_v"]
        charge_settings.settings["safety_min_voltage_v"] = cycle_test_settings.settings["safety_min_voltage_v"]
        charge_settings.settings["safety_max_time_s"] = cycle_test_settings.settings["safety_max_time_s"]
        
        #Rest
        rest_1_settings = Templates.RestSettings()
        
        rest_1_settings.settings["meas_log_int_s"] = cycle_test_settings.settings["meas_log_int_s"]
        rest_1_settings.settings["rest_time_min"] = cycle_test_settings.settings["rest_after_charge_min"]
        rest_1_settings.settings["safety_max_current_a"] = cycle_test_settings.settings["safety_max_current_a"]
        rest_1_settings.settings["safety_min_current_a"] = cycle_test_settings.settings["safety_min_current_a"]
        rest_1_settings.settings["safety_max_voltage_v"] = cycle_test_settings.settings["safety_max_voltage_v"]
        rest_1_settings.settings["safety_min_voltage_v"] = cycle_test_settings.settings["safety_min_voltage_v"]
        rest_1_settings.settings["safety_max_time_s"] = cycle_test_settings.settings["safety_max_time_s"]
        
        #Discharge
        discharge_settings = Templates.DischargeSettings()
        
        discharge_settings.settings["discharge_end_v"] = cycle_test_settings.settings["discharge_end_v"]
        discharge_settings.settings["discharge_a"] = cycle_test_settings.settings["discharge_a"]
        discharge_settings.settings["meas_log_int_s"] = cycle_test_settings.settings["meas_log_int_s"]
        discharge_settings.settings["safety_max_current_a"] = cycle_test_settings.settings["safety_max_current_a"]
        discharge_settings.settings["safety_min_current_a"] = cycle_test_settings.settings["safety_min_current_a"]
        discharge_settings.settings["safety_max_voltage_v"] = cycle_test_settings.settings["safety_max_voltage_v"]
        discharge_settings.settings["safety_min_voltage_v"] = cycle_test_settings.settings["safety_min_voltage_v"]
        discharge_settings.settings["safety_max_time_s"] = cycle_test_settings.settings["safety_max_time_s"]
        
        #Rest
        rest_2_settings = Templates.RestSettings()
        
        rest_2_settings.settings["meas_log_int_s"] = cycle_test_settings.settings["meas_log_int_s"]
        rest_2_settings.settings["rest_time_min"] = cycle_test_settings.settings["rest_after_charge_min"]
        rest_2_settings.settings["safety_max_current_a"] = cycle_test_settings.settings["safety_max_current_a"]
        rest_2_settings.settings["safety_min_current_a"] = cycle_test_settings.settings["safety_min_current_a"]
        rest_2_settings.settings["safety_max_voltage_v"] = cycle_test_settings.settings["safety_max_voltage_v"]
        rest_2_settings.settings["safety_min_voltage_v"] = cycle_test_settings.settings["safety_min_voltage_v"]
        rest_2_settings.settings["safety_max_time_s"] = cycle_test_settings.settings["safety_max_time_s"]
        
        #Convert everything to steps
        charge_step_settings = self.convert_charge_settings_to_steps(charge_settings.settings)
        rest_1_step_settings = self.convert_rest_settings_to_steps(rest_1_settings.settings)
        discharge_step_settings = self.convert_discharge_settings_to_steps(discharge_settings.settings)
        rest_2_step_settings = self.convert_rest_settings_to_steps(rest_2_settings.settings)
        
        settings_list = list()
        settings_list.append(charge_step_settings)
        settings_list.append(rest_1_step_settings)
        settings_list.append(discharge_step_settings)
        settings_list.append(rest_2_step_settings)
        
        return settings_list

    def one_level_continuous_cc_cycles_with_rest_info(self):
        #cycles - e.g. charge at 1A, rest, discharge at 5A, rest, repeat X times.
        #get user to enter number of cycles
        single_cycle_step_settings_list = self.single_cc_cycle_info()
        if single_cycle_step_settings_list == None:
            return None
        num_cycles = eg.integerbox(msg = "How Many Cycles?",
                                    title = "Cycle Type 1", default = 1,
                                    lowerbound = 0, upperbound = 999)
        if num_cycles == None:
            return None
        
        multi_cycle_step_settings_list = list()
        
        for i in range(num_cycles):
            multi_cycle_step_settings_list.extend(single_cycle_step_settings_list)
        
        return multi_cycle_step_settings_list

    def two_level_continuous_cc_cycles_with_rest_info(self):
        #A battery degradation test where the degradation is done at one current
        #and the capacity measurement is done at another current.
        #e.g. 9 degradation cycles at current X, then 1 capacity measurement cycle at current Y.
        
        #Cycle type 1
        cycle_1_step_settings_list = self.single_cc_cycle_info()
        if cycle_1_step_settings_list == None:
            return None
        num_cycles_type_1 = eg.integerbox(msg = "How Many Cycles of Type 1 in a row?",
                                                title = "Cycle Type 1", default = 9,
                                                lowerbound = 0, upperbound = 999)
        if num_cycles_type_1 == None:
            return None

        #Cycle type 2
        cycle_2_step_settings_list = self.single_cc_cycle_info()
        if cycle_2_step_settings_list == None:
            return None
        num_cycles_type_2 = eg.integerbox(msg = "How Many Cycles of Type 2 in a row?",
                                                title = "Cycle Type 2", default = 1,
                                                lowerbound = 0, upperbound = 999)
        if num_cycles_type_2 == None:
            return None

        #test cycles - charge and discharge how many times?
        num_test_cycles = eg.integerbox(msg = "How Many Test Cycles of X Cycle 1 then Y Cycle 2?",
                                                title = "Test Cycles", default = 1,
                                                lowerbound = 0, upperbound = 999)
        if num_test_cycles == None:
            return None

        multi_cycle_settings_list = list()

        for j in range(num_test_cycles):
            for i in range(num_cycles_type_1):
                multi_cycle_settings_list.extend(cycle_1_step_settings_list)
            for i in range(num_cycles_type_2):
                multi_cycle_settings_list.extend(cycle_2_step_settings_list)
        
        return multi_cycle_settings_list

    def convert_rest_settings_to_steps(self, rest_settings, model_step_settings = None):
        if model_step_settings is None:
            step_1 = Templates.StepSettings()
        else:
            step_1 = model_step_settings
        
        step_1.settings["cycle_display"] = rest_settings["cycle_display"]
        step_1.settings["drive_style"] = 'none'
        step_1.settings["end_style"] = 'time_s'
        step_1.settings["end_condition"] = 'greater'
        step_1.settings["end_value"] = rest_settings["rest_time_min"]*60
        step_1.settings["safety_min_voltage_v"] = rest_settings["safety_min_voltage_v"]
        step_1.settings["safety_max_voltage_v"] = rest_settings["safety_max_voltage_v"]
        step_1.settings["safety_min_current_a"] = rest_settings["safety_min_current_a"]
        step_1.settings["safety_max_current_a"] = rest_settings["safety_max_current_a"]
        step_1.settings["safety_max_time_s"] = rest_settings["safety_max_time_s"]
        
        return_list = list()
        return_list.append(step_1.settings)
        return return_list

    def charge_only_cycle_info(self):
        charge_test_settings = Templates.ChargeSettings()
        charge_test_settings.get_cycle_settings("Charge Only")
        
        if charge_test_settings.settings == None:
            return None
        
        #Transform charge settings to step settings.
        charge_settings = charge_test_settings.settings
        step_settings_list = list()
        step_settings_list.append(self.convert_charge_settings_to_steps(charge_settings))

        return step_settings_list
   
    def convert_charge_settings_to_steps(self, charge_settings, model_step_settings = None):
        if model_step_settings is None:
            step_1 = Templates.StepSettings()
        else:
            step_1 = model_step_settings
        
        step_1.settings["cycle_display"] = charge_settings["cycle_display"]
        step_1.settings["drive_style"] = 'voltage_v'
        step_1.settings["drive_value"] = charge_settings["charge_end_v"]
        step_1.settings["drive_value_other"] = charge_settings["charge_a"]
        step_1.settings["end_style"] = 'current_a'
        step_1.settings["end_condition"] = 'lesser'
        step_1.settings["end_value"] = charge_settings["charge_end_a"]
        step_1.settings["safety_min_voltage_v"] = charge_settings["safety_min_voltage_v"]
        step_1.settings["safety_max_voltage_v"] = charge_settings["safety_max_voltage_v"]
        step_1.settings["safety_min_current_a"] = charge_settings["safety_min_current_a"]
        step_1.settings["safety_max_current_a"] = charge_settings["safety_max_current_a"]
        step_1.settings["safety_max_time_s"] = charge_settings["safety_max_time_s"]
        
        return_list = list()
        return_list.append(step_1.settings)
        return return_list

    def discharge_only_cycle_info(self):
        discharge_test_settings = Templates.DischargeSettings()
        discharge_test_settings.get_cycle_settings("Discharge Only")
        
        if discharge_test_settings.settings == None:
            return None
        
        #Transform discharge settings to step settings.
        discharge_settings = discharge_test_settings.settings
        step_settings_list = list()
        step_settings_list.append(self.convert_discharge_settings_to_steps(discharge_settings))

        return step_settings_list

    def convert_discharge_settings_to_steps(self, discharge_settings, model_step_settings = None):
        if model_step_settings is None:
            step_1 = Templates.StepSettings()
        else:
            step_1 = model_step_settings
        
        step_1.settings["cycle_display"] = discharge_settings["cycle_display"]
        step_1.settings["drive_style"] = 'current_a'
        step_1.settings["drive_value"] = discharge_settings["discharge_a"]
        step_1.settings["end_style"] = 'voltage_v'
        step_1.settings["end_condition"] = 'lesser'
        step_1.settings["end_value"] = discharge_settings["discharge_end_v"]
        step_1.settings["safety_min_voltage_v"] = discharge_settings["safety_min_voltage_v"]
        step_1.settings["safety_max_voltage_v"] = discharge_settings["safety_max_voltage_v"]
        step_1.settings["safety_min_current_a"] = discharge_settings["safety_min_current_a"]
        step_1.settings["safety_max_current_a"] = discharge_settings["safety_max_current_a"]
        step_1.settings["safety_max_time_s"] = discharge_settings["safety_max_time_s"]
        
        return_list = list()
        return_list.append(step_1.settings)
        return return_list

    def single_step_cell_info(self):
        step_settings_list = list()
        
        step_settings = Templates.StepSettings()
        step_settings.get_cycle_settings("Step")
        
        if step_settings.settings == None:
            return None
        
        step_settings_list.append((step_settings.settings,))
        
        return step_settings_list

    def multi_step_cell_info(self):
        
        #import multi step from csv?:
        msg = "Import the multiple step cycle from a csv?"
        title = "CSV Import"
        from_csv = eg.ynbox(msg, title)
        
        if from_csv:
            step_settings_list = jsonIO.import_multi_step_from_csv()
            if step_settings_list == None:
                return None
        
        else:
            step_settings_list = list()
            msg = "Add a step to the cycle?"
            title = "Add Step"
            while eg.ynbox(msg = msg, title = title):
                single_step_info = self.single_step_cell_info()
                if single_step_info != None:
                    step_settings_list.append(single_step_info[0][0])
                msg = "Add another step to the cycle?"
            
            if len(step_settings_list) == 0:
                return None
        
        step_settings_list = (step_settings_list,)
        
        return step_settings_list

    def continuous_step_cycles_info(self):
        cycle_settings_list = list()
        
        msg = "Add another cycle?"
        title = "Add Cycle"
        while eg.ynbox(msg = msg, title = title):
            multi_step_list = self.multi_step_cell_info()
            if multi_step_list != None:
                cycle_settings_list.extend(multi_step_list)
        
        if len(cycle_settings_list) == 0:
            return None
        
        return cycle_settings_list

    def rest_info(self):
        rest_settings = Templates.RestSettings()
        rest_settings.get_cycle_settings("Rest")
        
        if rest_settings == None:
            return None
            
        rest_settings = rest_settings.settings
        rest_settings_list = list()
        rest_settings_list.append(self.convert_rest_settings_to_steps(rest_settings))
        
        return rest_settings_list

    def single_ir_test_info(self):
        #Create a cycle with 2 steps.
        ir_test_settings = Templates.SingleIRSettings()
        ir_test_settings.get_cycle_settings("Single IR Test")
        
        if ir_test_settings.settings == None:
            return None
        
        ir_settings = ir_test_settings.settings
        step_settings_list = list()
        step_settings_list.append(self.convert_single_ir_settings_to_steps(ir_settings))

        return step_settings_list
    
    def convert_single_ir_settings_to_steps(self, ir_settings, model_step_settings = None):
        if model_step_settings is None:
            model_step_settings = Templates.StepSettings()
            
            model_step_settings.settings["cycle_display"] = ir_settings["cycle_display"]
            model_step_settings.settings["drive_style"] = 'current_a'
            model_step_settings.settings["drive_value_other"] = ir_settings["psu_voltage_if_pos_i"]
            model_step_settings.settings["end_style"] = 'time_s'
            model_step_settings.settings["end_condition"] = 'greater'
            model_step_settings.settings["safety_min_current_a"] = ir_settings["safety_min_current_a"]
            model_step_settings.settings["safety_max_current_a"] = ir_settings["safety_max_current_a"]
            model_step_settings.settings["safety_min_voltage_v"] = ir_settings["safety_min_voltage_v"]
            model_step_settings.settings["safety_max_voltage_v"] = ir_settings["safety_max_voltage_v"]
            model_step_settings.settings["safety_max_time_s"] = ir_settings["safety_max_time_s"]
        
        step_1_settings = model_step_settings.settings.copy()
        step_2_settings = model_step_settings.settings.copy()
        
        step_1_settings["drive_value"] = ir_settings["current_1_a"]
        step_2_settings["drive_value"] = ir_settings["current_2_a"]
        step_1_settings["end_value"] = ir_settings["time_1_s"]
        step_2_settings["end_value"] = ir_settings["time_2_s"]
        
        return_list = list()
        return_list.append(step_1_settings)
        return_list.append(step_2_settings)
        return return_list
    
    
    def repeated_ir_discharge_test_info(self):
        ir_test_settings = Templates.RepeatedIRDischargeSettings()
        ir_test_settings.get_cycle_settings("Repeated IR Discharge Test")
        
        if ir_test_settings.settings == None:
            return None
        
        #CC Charge
        charge_settings = Templates.ChargeSettings()
        charge_settings.settings["charge_end_v"] = ir_test_settings.settings["charge_end_v"]
        charge_settings.settings["charge_a"] = ir_test_settings.settings["charge_a"]
        charge_settings.settings["charge_end_a"] = ir_test_settings.settings["charge_end_a"]
        charge_settings.settings["meas_log_int_s"] = ir_test_settings.settings["meas_log_int_s"]
        charge_settings.settings["safety_min_current_a"] = ir_test_settings.settings["safety_min_current_a"]
        charge_settings.settings["safety_max_current_a"] = ir_test_settings.settings["safety_max_current_a"]
        charge_settings.settings["safety_min_voltage_v"] = ir_test_settings.settings["safety_min_voltage_v"]
        charge_settings.settings["safety_max_voltage_v"] = ir_test_settings.settings["safety_max_voltage_v"]
        charge_settings.settings["safety_max_time_s"] = (ir_test_settings.settings["estimated_capacity_ah"] / ir_test_settings.settings["charge_a"])*3600*5
        charge_step_settings = self.convert_charge_settings_to_steps(charge_settings.settings)
        
        #Rest
        rest1_settings = Templates.RestSettings()
        rest1_settings.settings["meas_log_int_s"] = ir_test_settings.settings["meas_log_int_s"]
        rest1_settings.settings["rest_time_min"] = ir_test_settings.settings["rest_after_charge_min"]
        rest1_settings.settings["safety_min_current_a"] = ir_test_settings.settings["safety_min_current_a"]
        rest1_settings.settings["safety_max_current_a"] = ir_test_settings.settings["safety_max_current_a"]
        rest1_settings.settings["safety_min_voltage_v"] = ir_test_settings.settings["safety_min_voltage_v"]
        rest1_settings.settings["safety_max_voltage_v"] = ir_test_settings.settings["safety_max_voltage_v"]
        rest1_settings.settings["safety_max_time_s"] = int(rest1_settings.settings["rest_time_min"]*60*1.25)
        rest1_step_settings = self.convert_rest_settings_to_steps(rest1_settings.settings)
        
        #Discharge with IR pulses
        step_settings_list = self.convert_repeated_ir_settings_to_steps(ir_test_settings.settings)
        
        #Rest
        rest2_settings = Templates.RestSettings()
        rest2_settings.settings["meas_log_int_s"] = ir_test_settings.settings["meas_log_int_s"]
        rest2_settings.settings["rest_time_min"] = ir_test_settings.settings["rest_after_discharge_min"]
        rest2_settings.settings["safety_min_current_a"] = ir_test_settings.settings["safety_min_current_a"]
        rest2_settings.settings["safety_max_current_a"] = ir_test_settings.settings["safety_max_current_a"]
        rest2_settings.settings["safety_min_voltage_v"] = ir_test_settings.settings["safety_min_voltage_v"]
        rest2_settings.settings["safety_max_voltage_v"] = ir_test_settings.settings["safety_max_voltage_v"]
        rest2_settings.settings["safety_max_time_s"] = int(rest2_settings.settings["rest_time_min"]*60*1.25)
        rest2_step_settings = self.convert_rest_settings_to_steps(rest2_settings.settings)
        
        #Combine all steps
        settings_list = list()
        settings_list.append(charge_step_settings)
        settings_list.append(rest1_step_settings)
        settings_list.append(step_settings_list)
        settings_list.append(rest2_step_settings)
        
        return settings_list
    
    def convert_repeated_ir_settings_to_steps(self, test_settings):
        model_step_settings = Templates.StepSettings()
        max_time = max(test_settings["time_1_s"], test_settings["time_2_s"])
        
        model_step_settings.settings["cycle_display"] = test_settings["cycle_display"]
        model_step_settings.settings["drive_style"] = 'current_a'
        model_step_settings.settings["drive_value_other"] = test_settings["psu_voltage_if_pos_i"]
        model_step_settings.settings["end_style"] = 'time_s'
        model_step_settings.settings["end_condition"] = 'greater'
        model_step_settings.settings["cycle_end_voltage_v"] = test_settings["cycle_end_voltage_v"]
        model_step_settings.settings["safety_min_voltage_v"] = test_settings["safety_min_voltage_v"]
        model_step_settings.settings["safety_max_voltage_v"] = test_settings["safety_max_voltage_v"]
        model_step_settings.settings["safety_min_current_a"] = test_settings["safety_min_current_a"]
        model_step_settings.settings["safety_max_current_a"] = test_settings["safety_max_current_a"]
        model_step_settings.settings["safety_max_time_s"] = max_time*1.75
        
        step_1_settings = model_step_settings.settings.copy()
        step_2_settings = model_step_settings.settings.copy()
        
        step_1_settings["drive_value"] = test_settings["current_1_a"]
        step_2_settings["drive_value"] = test_settings["current_2_a"]
        step_1_settings["end_value"] = test_settings["time_1_s"]
        step_2_settings["end_value"] = test_settings["time_2_s"]
        
        capacity_per_test_a_s = test_settings["current_1_a"]*test_settings["time_1_s"] + test_settings["current_2_a"]*test_settings["time_2_s"]
        total_capacity_a_s = test_settings["estimated_capacity_ah"] * 3600
        num_tests_required = int(abs(total_capacity_a_s / capacity_per_test_a_s))
        
        settings_list = list()
        
        for i in range(num_tests_required*2):
            settings_list.append(step_1_settings)
            settings_list.append(step_2_settings)
            
        return settings_list


class CyclingInfo():
    ################################################### SETUP TO GET INPUT DICT #########################################
    def __init__(self):
        pass

    def ask_storage_charge(self):
        message = "Do you want to do a storage charge?\n" + \
                    "Recommended to do one. Leaving a cell discharged increases\n" + \
                    "risk of latent failures due to dendrite growth."
        return eg.ynbox(title = "Storage Charge",
                        msg = message)

    def get_cell_name(self, ch_num = None, queue = None, current_text = None):
        default_name = "CELL_NAME"
        if current_text != None:
            default_name = current_text

        #get the cell name
        cell_name = eg.enterbox(title = "Test Setup", msg = "Enter the Cell Name\n(Spaces will be replaced with underscores)",
                                default = default_name, strip = True)
        
        #if we don't hit Cancel
        if cell_name != None:
            #replace the spaces to keep file names consistent
            cell_name = cell_name.replace(" ", "_")
            
            if queue != None:
                dict_to_put = {'ch_num': ch_num, 'cell_name': cell_name}
                queue.put_nowait(dict_to_put)
            else:
                return cell_name
        else:
            return None
    
    def get_cycle_type(self):
        cycle_types = Templates.CycleTypes.cycle_types
        
        #choose the cycle type
        msg = "Which cycle type do you want to do?"
        title = "Choose Cycle Type"
        cycle_type = eg.choicebox(msg, title, list(cycle_types.keys()))
        return cycle_type

    def get_settings_cycle_list_step_list(self, cycle_type):
        cycle_types = Templates.CycleTypes.cycle_types
        
        c_s = CyclingSettings()
        
        #different cycle types that are available
        cycle_types["Single_CC_Cycle"]['func_call'] = c_s.single_cc_cycle_info
        cycle_types["One_Setting_Continuous_CC_Cycles_With_Rest"]['func_call'] = c_s.one_level_continuous_cc_cycles_with_rest_info
        cycle_types["Two_Setting_Continuous_CC_Cycles_With_Rest"]['func_call'] = c_s.two_level_continuous_cc_cycles_with_rest_info
        cycle_types["CC_Charge_Only"]['func_call'] = c_s.charge_only_cycle_info
        cycle_types["CC_Discharge_Only"]['func_call'] = c_s.discharge_only_cycle_info
        cycle_types["Step_Cycle"]['func_call'] = c_s.multi_step_cell_info
        cycle_types["Continuous_Step_Cycles"]['func_call'] = c_s.continuous_step_cycles_info
        cycle_types["Single_IR_Test"]['func_call'] = c_s.single_ir_test_info
        cycle_types["Repeated_IR_Discharge_Test"]['func_call'] = c_s.repeated_ir_discharge_test_info
        cycle_types["Rest"]['func_call'] = c_s.rest_info
        
        #gather the list settings based on the cycle type
        settings_cycle_list_step_list = list()
        settings_cycle_list_step_list = cycle_types[cycle_type]['func_call']()
        
        if settings_cycle_list_step_list == None:
            return None
        
        #STORAGE CHARGE
        do_a_storage_charge = False
        if(cycle_types[cycle_type]['str_chg_opt']):
            do_a_storage_charge = self.ask_storage_charge()
        
        #extend adds two lists, append adds a single element to a list. We want extend here since charge_only_cycle_info() returns a list.
        if do_a_storage_charge:
            settings_cycle_list_step_list.extend(c_s.charge_only_cycle_info())
            
        return settings_cycle_list_step_list

    def find_eq_req_steps(self, step_settings):
        eq_req_dict = {'psu': False, 'eload': False}
        
        #Go through all the steps to see which equipment we need connected (power supply and/or eload)
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

    def get_eq_req_for_cycle(self, settings_list):
        eq_req_dict = {'psu': False, 'eload': False}
        cycle_requirements = Templates.CycleTypes.cycle_requirements
        
        for settings in settings_list:
            if settings["cycle_type"] == 'step':
                eq_req_from_settings = self.find_eq_req_steps(settings)
                eq_req_dict['psu'] = eq_req_dict['psu'] or eq_req_from_settings['psu']
                eq_req_dict['eload'] = eq_req_dict['eload'] or eq_req_from_settings['eload']
            else:
                eq_req_dict['psu'] = eq_req_dict['psu'] or cycle_requirements[settings["cycle_type"]]['supply_req']
                eq_req_dict['eload'] = eq_req_dict['eload'] or cycle_requirements[settings["cycle_type"]]['load_req']
                
        return eq_req_dict

    def get_eq_req_dict(self, settings_cycle_list_step_list):
        #REQUIRED EQUIPMENT
        eq_req_dict = {'psu': False, 'eload': False}
        cycle_requirements = Templates.CycleTypes.cycle_requirements
        
        for settings_list in settings_cycle_list_step_list:
            eq_req_for_cycle_dict = self.get_eq_req_for_cycle(settings_list)
            eq_req_dict['psu'] = eq_req_dict['psu'] or eq_req_for_cycle_dict['psu']
            eq_req_dict['eload'] = eq_req_dict['eload'] or eq_req_for_cycle_dict['eload']
        
        return eq_req_dict

    def ask_another_cycle(self):
        message = "Do you want to add another cycle?"
        return eg.ynbox(title = "Add Cycle", msg = message)

    def get_input_dict(self, ch_num = None, queue = None, current_cell_name = None):
        input_dict = {}
        
        cell_name = self.get_cell_name(current_text = current_cell_name)
        if cell_name == None:
            return None
        input_dict['cell_name'] = cell_name
        
        directory = FileIO.get_directory("Choose directory to save the cycle logs")
        if directory == None:
            return None
        input_dict['directory'] = directory
        
        add_more_cycles = True
        cycle_counter = 0
        settings_cycle_list_step_list = list()
        
        while add_more_cycles:
            #Cycle Type
            cycle_type = self.get_cycle_type()
            if cycle_type == None:
                return None
            
            if cycle_counter == 0:
                input_dict['cycle_type'] = cycle_type
            
            #Cycle Settings
            new_settings_cycle_list_step_list = self.get_settings_cycle_list_step_list(cycle_type)
            if new_settings_cycle_list_step_list == None:
                return None
            else:
                settings_cycle_list_step_list.extend(new_settings_cycle_list_step_list)
            
            cycle_counter += 1
            
            #Add another cycle?
            ask_cycle = self.ask_another_cycle()
            if ask_cycle == None or ask_cycle == False:
                add_more_cycles = False
                
        input_dict['settings_cycle_list_step_list'] = settings_cycle_list_step_list
        
        #Equipment Required
        input_dict['eq_req_dict'] = self.get_eq_req_dict(input_dict['settings_cycle_list_step_list']) #This does not have a GUI associated.
        
        if queue != None:
            dict_to_put = {'ch_num': ch_num, 'cdc_input_dict': input_dict}
            #print(dict_to_put)
            queue.put_nowait(dict_to_put)
        else:
            return input_dict


################################# Functions to run in thread from another program #############
def run_get_cell_name(ch_num = None, queue = None, current_text = None):
    c_i = CyclingInfo()
    c_i.get_cell_name(ch_num = ch_num, queue = queue, current_text = current_text)

def run_get_input_dict(ch_num = None, queue = None, current_cell_name = None):
    c_i = CyclingInfo()
    c_i.get_input_dict(ch_num = ch_num, queue = queue, current_cell_name = current_cell_name)

def run_charge_discharge_control(res_ids_dict, data_out_queue = None, data_in_queue = None, input_dict = None, ch_num = None):
    c_c = CyclingControl()
    c_c.charge_discharge_control(res_ids_dict = res_ids_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue, input_dict = input_dict, ch_num = ch_num)

def run_idle_control(res_ids_dict, data_out_queue = None, data_in_queue = None):
    c_c = CyclingControl()
    c_c.idle_control(res_ids_dict = res_ids_dict, data_out_queue = data_out_queue, data_in_queue = data_in_queue)


####################################### MAIN PROGRAM ######################################

if __name__ == '__main__':
    print("Use the battery_test.py script")
    #charge_discharge_control()
