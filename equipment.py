#contains a list of all the equipment that there are libraries for
#organized into which ones have common function calls

import easygui as eg
import pyvisa

#multi channel device management functions
#from BATT_HIL import fet_board_management as fbm

import queue #For handling queue.Empty error

from easygui.boxes.derived_boxes import msgbox
import time

#Eloads
from lab_equipment import Eload_BK8600
from lab_equipment import Eload_DL3000
from lab_equipment import Eload_KEL10X
from lab_equipment import Eload_IT8500
from lab_equipment import Eload_PARALLEL
from lab_equipment import Eload_A2D_Eload
from lab_equipment import Eload_Fake

#Power Supplies
from lab_equipment import PSU_DP800
from lab_equipment import PSU_SPD1000
from lab_equipment import PSU_MP71025X
from lab_equipment import PSU_BK9100
from lab_equipment import PSU_N8700
from lab_equipment import PSU_KAXXXXP
from lab_equipment import PSU_E3631A
from lab_equipment import PSU_Fake

#SMUs
from lab_equipment import SMU_A2D_POWER_BOARD
from lab_equipment import SMU_ITM3400

#Digital Multimeters
from lab_equipment import DMM_DM3000
from lab_equipment import DMM_SDM3065X
#from lab_equipment import DMM_FET_BOARD_EQ
from lab_equipment import A2D_DAQ_control
from lab_equipment import A2D_DAQ_config #to load config file from csv
from lab_equipment import DMM_A2D_SENSE_BOARD
from lab_equipment import DMM_A2D_4CH_Isolated_ADC
from lab_equipment import DMM_Fake

#Other Equipment
from lab_equipment import OTHER_A2D_Relay_Board
from lab_equipment import OTHER_Arduino_IO_Module

#Virtual Equipment Management
from lab_equipment import VirtualDeviceTemplate

def choose_channel(num_channels = 64, start_val = 0):
    max_number = num_channels + start_val - 1
    ch_num = eg.integerbox(msg = "Which channel on this device would you like to use?",
                           title = "Channel Selection",
                           default = start_val,
                           lowerbound = start_val,
                           upperbound = max_number)
    return int(ch_num)

#used in create_new_equipment in battery_test.py
def virtual_device_management_process(eq_type, new_eq_res_id_dict, queue_in, queue_out):
    # - connect to the equipment using the equipment type and the res_id_dict
            # - Then loop:
                # - listen for any messages in queue_in
                    # - take action on messages in queue_in
                # - put responses to messages in queue_out
    
    device = connect_to_eq(eq_type, new_eq_res_id_dict['class_name'], new_eq_res_id_dict['res_id'], new_eq_res_id_dict['setup_dict'])
    print(f"Virtual Device Connected: {new_eq_res_id_dict['class_name']}")
    last_kick_time = time.time()

    queue_in_message_type = None
    #All queue in message must be a dict with 'type' and 'data' keys.
    #'type' should be a function name that the device has
    #'data' should be an argument list for that function
    while queue_in_message_type != 'disconnect':
        try:
            queue_in_message = queue_in.get_nowait()
            if queue_in_message == 'stop':
                return
            queue_in_message_type = queue_in_message['type']
            queue_in_message_data = queue_in_message['data']
            
            if queue_in_message_data is None:
                return_data = eval('device.'+queue_in_message_type+'()')
            else:
                if type(queue_in_message_data) is not list:
                    queue_in_message_data = [queue_in_message_data,]
                args = queue_in_message_data
                return_data = eval('device.'+queue_in_message_type+'(*args)', {}, {"args": args, "device": device})
            
            if return_data != None:
                queue_out.put_nowait(return_data)
        except queue.Empty:
            pass
        #TODO - kick device watchdog if it needs one - this should be done from the thread controlling the instrument instead?
        #If 10s has passed, send a kick message
        if (time.time() - last_kick_time) > 5:
            try:
                device.kick()
            except AttributeError:
                pass
            last_kick_time = time.time()

        time.sleep(0.001000) #1000us = 1ms

def get_resources_list():
    #looks through all pyvisa backends to see which resources we can connect to.
    resources_list = list()
    backends = ['@py', '@ivi']
    for backend in backends:
        rm = pyvisa.ResourceManager(backend)
        resource_list = rm.list_resources()
        for resource in resource_list:
            resources_list.append({'resource': resource, 'backend': backend})
    return resources_list
    #How do we know which device settings to use to communicate with it? Try all the settings until we get a legible response from IDN that we can use?

def setup_instrument(instrument, setup_dict):
    if setup_dict == None:
        setup_dict = {}
    
    #REMOTE SENSE
    if hasattr(instrument, 'has_remote_sense') and instrument.has_remote_sense:
        if 'remote_sense' not in setup_dict.keys():
            setup_dict['remote_sense'] = None
        
        if setup_dict['remote_sense'] == None:
            #ask to use remote sense
            msg = "Do you want to use remote sense on this instrument?"
            title = "Remote Sense"
            use_remote_sense = eg.ynbox(msg, title)
            setup_dict['remote_sense'] = use_remote_sense
            
        time.sleep(0.5) #delay to allow the instrument to process commands after re-booting.
                        #Ran into an issue with the DL3000 where it would display 'sense' on the screen, but
                        #the sensing relay would not be on. Adding a delay here seems to have fixed it.
                        #The sense line relay did not have time to toggle between a quick on-off-on sequence
        
        instrument.remote_sense(setup_dict['remote_sense'])
    
    #A2D Relay Board Special Setup
    if isinstance(instrument, OTHER_A2D_Relay_Board.A2D_Relay_Board):
        #special setup for this instrument
        #Need to determine if channel has an eload or a psu.
        #Cannot have multiple of the same device yet.

        if 'num_channels' not in setup_dict.keys():
            setup_dict['num_channels'] = instrument.get_num_channels()

        if 'equipment_type_connected' not in setup_dict.keys():
            title = "A2D Relay Board Setup - Connected Equipment"
            choices = ['eload', 'psu', 'none']
            equipment_type_connected = list()
            
            for i in range(setup_dict['num_channels']):
                msg = "What is connected to channel {}?".format(i)
                response = eg.choicebox(msg, title, choices)
                if response == None:
                    return None
                equipment_type_connected.append(response)
            
            setup_dict['equipment_type_connected'] = equipment_type_connected
        
        if 'i2c_expander_addr' not in setup_dict.keys():
            title = "A2D Relay Board Setup - I2C Expander"
            msg = "Enter I2C Expander Address\n Use 7-bit right-justified hexadecimal\n(e.g. '0x77')"
            response = eg.enterbox(msg, title, default = '0x74')
            if response == None:
                return None
            setup_dict['i2c_expander_addr'] = int(response, 16)
            
        instrument.equipment_type_connected = setup_dict['equipment_type_connected']
        instrument.set_i2c_expander_addr(setup_dict['i2c_expander_addr'])
    
    #A2D Sense Board Special Setup
    if isinstance(instrument, DMM_A2D_SENSE_BOARD.A2D_SENSE_BOARD):

        if 'i2c_adc_addr' not in setup_dict.keys():
            title = "A2D Sense Board Setup - I2C ADC"
            msg = "Enter ADC I2C Address\n Use 7-bit right-justified hexadecimal\n(e.g. '0x77')"
            response = eg.enterbox(msg, title, default = '0x74')
            if response == None:
                return None
            setup_dict['i2c_adc_addr'] = int(response, 16)
            
        instrument.set_i2c_adc_addr(setup_dict['i2c_adc_addr'])
    
    #A2D Power Board Special Setup
    if isinstance(instrument, SMU_A2D_POWER_BOARD.A2D_POWER_BOARD):

        if 'i2c_adc_addr' not in setup_dict.keys():
            title = "A2D Power Board Setup - I2C ADC"
            msg = "Enter ADC I2C Address\n Use 7-bit right-justified hexadecimal\n(e.g. '0x77')"
            response = eg.enterbox(msg, title, default = '0x32')
            if response == None:
                return None
            setup_dict['i2c_adc_addr'] = int(response, 16)
            
        instrument.set_i2c_adc_addr(setup_dict['i2c_adc_addr'])
            
        if 'i2c_dac_addr' not in setup_dict.keys():
            title = "A2D Power Board Setup - I2C DAC"
            msg = "Enter DAC I2C Address\n Use 7-bit right-justified hexadecimal\n(e.g. '0x77')"
            response = eg.enterbox(msg, title, default = '0x4A')
            if response == None:
                return None
            setup_dict['i2c_dac_addr'] = int(response, 16)
            
        instrument.set_i2c_dac_addr(setup_dict['i2c_dac_addr'])
    
    #A2D 64 CH DAQ special setup
    if isinstance(instrument, A2D_DAQ_control.A2D_DAQ):
        if 'config_dict' not in setup_dict.keys():
            #Get the config dict and save it in the setup_dict
            setup_dict['config_dict'] = A2D_DAQ_config.get_config_dict()
        setup_dict['config_dict'] = {int(key):value for key, value in setup_dict['config_dict'].items()}
        instrument.config_dict = setup_dict['config_dict']
        instrument.configure_from_dict()
    
    return setup_dict

def get_equipment_dict(res_ids_dict):
    eq_dict = {}
    for key in res_ids_dict:
        if res_ids_dict[key] != None and res_ids_dict[key]['res_id'] != None:
            eq_dict[key] = connect_to_eq(key, res_ids_dict[key]['class_name'], res_ids_dict[key]['res_id'], res_ids_dict[key]['setup_dict'])
        else:
            eq_dict[key] = None
    return eq_dict

def connect_to_eq(key, class_name, res_id, setup_dict = None):
    #Key should be 'eload', 'psu', 'dmm', 'relay_board', 'smu'
    #'dmm' with any following characters will be considered a dmm
    instrument = None
    
    if class_name == 'E3631A': time.sleep(1) #testing E3631A and delay for passing equipment between threads
    
    #return the actual equipment object instead of the equipment dictionary
    if key == 'eload':
        instrument = eLoads.choose_eload(class_name, res_id, setup_dict)[1]
    elif key == 'psu':
        instrument = powerSupplies.choose_psu(class_name, res_id, setup_dict)[1]
    elif 'dmm' in key: #for dmm_i and dmm_v and dmm_t keys
        instrument = dmms.choose_dmm(class_name, resource_id = res_id, setup_dict = setup_dict)[1]
    elif key == 'relay_board' or key == 'other':
        instrument = otherEquipment.choose_equipment(class_name, res_id, setup_dict)[1]
    elif key == 'smu':
        instrument = smus.choose_smu(class_name, res_id, setup_dict)[1]
    time.sleep(0.1)
    return instrument

#Used in get_equipment_dict
def connect_to_virtual_eq(virtual_res_id_dict):
    if virtual_res_id_dict.get('eq_ch') != None:
        instrument = VirtualDeviceTemplate.VirtualDeviceTemplate(virtual_res_id_dict['queue_in'], virtual_res_id_dict['queue_out'], virtual_res_id_dict['eq_ch'])
    else:
        instrument = VirtualDeviceTemplate.VirtualDeviceTemplate(virtual_res_id_dict['queue_in'], virtual_res_id_dict['queue_out'])
    return instrument

#used in battery_test.py when connecting to a new piece of equipment
#equipment_list comes from the choose_eload, choose_dmm, etc. functions in equipment.py
'''
eq_list has 3 items: 
    class_name - the instrument class e.g. 'DM3000'
    instrument - the instrument object that communicates with the instrument
    setup_dict - gets passed to the setup_equipment function for special setup
'''
def get_res_id_dict_and_disconnect(eq_list):
    class_name = eq_list[0]
    
    #print(eq_list)
    
    eq_type = None
    if class_name in smus.part_numbers.keys():
        eq_type = 'smu'
    if class_name in otherEquipment.part_numbers.keys():
        if class_name == otherEquipment.part_numbers['A2D Relay Board']:
            eq_type = 'relay_board'
        else:
            eq_type = 'other'
    elif class_name in eLoads.part_numbers.keys():
        eq_type = 'eload'
    elif class_name in powerSupplies.part_numbers.keys():
        eq_type = 'psu'
    elif class_name in dmms.part_numbers.keys():
        eq_type = 'dmm'
    
    eq_idn = None
    try:
        eq_idn = eq_list[1].inst_idn
    except AttributeError:
        pass
    
    eq_res_id_dict = {
        'eq_idn':       eq_idn,
        'eq_type':      eq_type,
        'class_name':   class_name,
        'res_id':       None,
        'setup_dict':   {}
    }
    
    #if class_name == 'MATICIAN_FET_BOARD_CH':# or class_name == 'A2D_DAQ_CH':
    #    eq_res_id_dict['res_id'] = {'board_name': eq_list[1].board_name, 'ch_num': eq_list[1].ch_num}
    if class_name == 'Parallel Eloads':
        eq_res_id_dict['res_id'] = {}
        eq_res_id_dict['res_id']['class_name_1'] = eq_list[1].class_name_1
        eq_res_id_dict['res_id']['class_name_2'] = eq_list[1].class_name_2
        try:
            eq_res_id_dict['res_id']['res_id_1'] = eq_list[1].eload1.inst.resource_name
        except AttributeError:
            eq_res_id_dict['res_id']['res_id_1'] = None #For fake instruments
        try:
            eq_res_id_dict['res_id']['res_id_2'] = eq_list[1].eload2.inst.resource_name
        except AttributeError:
            eq_res_id_dict['res_id']['res_id_2'] = None #For fake instruments
        #print('Adding setup_dict to res_id_dict')
        eq_res_id_dict['res_id']['remote_sense_1'] = eq_list[1].use_remote_sense_1
        eq_res_id_dict['res_id']['remote_sense_2'] = eq_list[1].use_remote_sense_2
    elif 'Fake' in class_name:
        eq_res_id_dict['res_id'] = 'Fake'
        eq_res_id_dict['setup_dict'] = eq_list[2]
    else:
        try:
            eq_res_id_dict['res_id'] = eq_list[1].inst.resource_name
            eq_res_id_dict['setup_dict'] = eq_list[2]
        except AttributeError:
            print("No res_id for instrument")
        
    #disconnect from equipment
    try:
        if class_name == 'Parallel Eloads':
            eq_list[1].eload1.inst.close()
            eq_list[1].eload2.inst.close()
        else:
            eq_list[1].inst.close()
    except AttributeError:
        pass #temporary fix for 'virtual and fake instruments' - TODO - figure out a way to do this more properly
    
    return eq_res_id_dict


#Connect to the equipment and return the handle for the virtual equipment
def get_equipment_dict(res_ids_dict):
    eq_dict = {}
    for key in res_ids_dict:
        if res_ids_dict[key] != None and res_ids_dict[key]['res_id'] != None:
            if res_ids_dict[key]['res_id'].get('queue_in') != None:
                #This is a virtual equipment that is communicated with through queues.
                eq_dict[key] = connect_to_virtual_eq(res_ids_dict[key]['res_id'])
            else:
                eq_dict[key] = connect_to_eq(key, res_ids_dict[key]['class_name'], res_ids_dict[key]['res_id'], res_ids_dict[key]['setup_dict'])
        else:
            eq_dict[key] = None
    return eq_dict    
    

class otherEquipment:
    part_numbers = {
        'A2D Relay Board': 		'OTHER_A2D_Relay_Board',
        'Arduino IO Module':	'OTHER_Arduino_IO_Module'
    }
        
    @classmethod
    def choose_equipment(self, class_name = None, resource_id = None, setup_dict = None, resources_list = None):
        if class_name == None:
            msg = "What type of equipment?"
            title = "Equipment Series Selection"
            class_name = eg.choicebox(msg, title, otherEquipment.part_numbers.keys())

        if class_name == None:
            print("Failed to select the equipment.")
            return			
        
        if class_name == 'A2D Relay Board':
            instrument = OTHER_A2D_Relay_Board.A2D_Relay_Board(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'Arduino IO Module':
            instrument = OTHER_Arduino_IO_Module.Arduino_IO(resource_id = resource_id, resources_list = resources_list)
            
        setup_dict = setup_instrument(instrument, setup_dict)
        if setup_dict == None:
            print("Equipment Setup Failed")
            return
        return class_name, instrument, setup_dict


class eLoads:
    part_numbers = {
        'BK8600': 			'Eload_BK8600',
        'DL3000': 			'Eload_DL3000',
        'KEL10X': 			'Eload_KEL10X',
        'IT8500': 			'Eload_IT8500',
        'A2D_Eload':        'Eload_A2D_Eload',
        'Parallel Eloads':	'Eload_PARALLEL',
        'Fake Test Eload': 	'Eload_Fake'
    }
        
    @classmethod
    def choose_eload(self, class_name = None, resource_id = None, setup_dict = None, resources_list = None):
        if class_name == None:
            msg = "In which series is the E-Load?"
            title = "E-Load Series Selection"
            class_name = eg.choicebox(msg, title, list(eLoads.part_numbers.keys())+list(smus.part_numbers.keys()))

        if class_name == None:
            print("Failed to select the equipment.")
            return			
        
        if class_name == 'BK8600':
            eload = Eload_BK8600.BK8600(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'DL3000':
            eload = Eload_DL3000.DL3000(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'KEL10X':
            eload = Eload_KEL10X.KEL10X(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'IT8500':
            eload = Eload_IT8500.IT8500(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'A2D_POWER_BOARD':
            eload = SMU_A2D_POWER_BOARD.A2D_POWER_BOARD(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'A2D_Eload':
            eload = Eload_A2D_Eload.A2D_Eload(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'IT_M3400':
            eload = SMU_ITM3400.IT_M3400(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'Parallel Eloads':
            eload = Eload_PARALLEL.PARALLEL(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'Fake Test Eload':
            eload = Eload_Fake.Fake_Eload(resource_id = resource_id, resources_list = resources_list)
            
        setup_dict = setup_instrument(eload, setup_dict)
        if setup_dict == None:
            print("Equipment Setup Failed")
            return
        return class_name, eload, setup_dict


class powerSupplies:
    part_numbers = {
        'SPD1000': 				'PSU_SPD1000',
        'DP800': 				'PSU_DP800',
        'KWR10X or MP71025X': 	'PSU_MP71025X',
        'BK9100': 				'PSU_BK9100',
        'N8700': 				'PSU_N8700',
        'KAXXXXP': 				'PSU_KAXXXXP',
        'E3631A':				'PSU_E3631A',
        'Fake Test PSU':        'PSU_Fake'
    }
    
    @classmethod
    def choose_psu(self, class_name = None, resource_id = None, setup_dict = None, resources_list = None):
        if class_name == None:
            msg = "In which series is the PSU?"
            title = "PSU Series Selection"
            class_name = eg.choicebox(msg, title, list(powerSupplies.part_numbers.keys())+list(smus.part_numbers.keys()))

        if class_name == None:
            print("Failed to select the equipment.")
            return
        
        if class_name == 'SPD1000':
            psu = PSU_SPD1000.SPD1000(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'DP800':
            psu = PSU_DP800.DP800(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'KWR10X or MP71025X':
            psu = PSU_MP71025X.MP71025X(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'BK9100':
            psu = PSU_BK9100.BK9100(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'N8700':
            psu = PSU_N8700.N8700(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'KAXXXXP':
            psu = PSU_KAXXXXP.KAXXXXP(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'E3631A':
            psu = PSU_E3631A.E3631A(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'A2D_POWER_BOARD':
            psu = SMU_A2D_POWER_BOARD.A2D_POWER_BOARD(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'IT_M3400':
            psu = SMU_ITM3400.IT_M3400(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'Fake Test PSU':
            psu = PSU_Fake.Fake_PSU(resource_id = resource_id, resources_list = resources_list)
            
        setup_dict = setup_instrument(psu, setup_dict)
        if setup_dict == None:
            print("Equipment Setup Failed")
            return
        return class_name, psu, setup_dict


class smus:
    part_numbers = part_numbers = {
        'A2D_POWER_BOARD':          'SMU_A2D_POWER_BOARD',
        'IT_M3400':                 'SMU_ITM3400',
    }
    
    @classmethod
    def choose_smu(self, class_name = None, resource_id = None, setup_dict = None, resources_list = None):
        if class_name == None:
            msg = "In which series is the PSU?"
            title = "PSU Series Selection"
            class_name = eg.choicebox(msg, title, smus.part_numbers.keys)

        if class_name == None:
            print("Failed to select the equipment.")
            return
        
        if class_name == 'A2D_POWER_BOARD':
            smu = SMU_A2D_POWER_BOARD.A2D_POWER_BOARD(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'IT_M3400':
            smu = SMU_ITM3400.IT_M3400(resource_id = resource_id, resources_list = resources_list)
            
        setup_dict = setup_instrument(smu, setup_dict)
        if setup_dict == None:
            print("Equipment Setup Failed")
            return
        return class_name, smu, setup_dict
        

class dmms:
    part_numbers = {
        'DM3000': 					        'DMM_DM3000',
        'SDM3065X': 				        'DMM_SDM3065X',
        #'MATICIAN_FET_BOARD_CH':	        'DMM_FET_BOARD',
        'A2D_DAQ_CH':				        'A2D_DAQ',
        'A2D_SENSE_BOARD':                  'A2D_SENSE_BOARD',
        'A2D_4CH_Isolated_ADC_Channel':     'A2D_4CH_Isolated_ADC',
        'Fake Test DMM': 			        'DMM_Fake'
    }
    
    @classmethod
    def choose_dmm(self, class_name = None, resource_id = None, multi_ch_event_and_queue_dict = None, setup_dict = None, resources_list = None):
        if class_name == None:
            msg = "In which series is the DMM?"
            title = "DMM Series Selection"
            class_name = eg.choicebox(msg, title, list(dmms.part_numbers.keys())+list(smus.part_numbers.keys()))

        if class_name == None:
            print("Failed to select the equipment.")
            return			
        
        if class_name == 'DM3000':
            dmm = DMM_DM3000.DM3000(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'SDM3065X':
            dmm = DMM_SDM3065X.SDM3065X(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'Fake Test DMM':
            dmm = DMM_Fake.Fake_DMM(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'A2D_SENSE_BOARD':
            dmm = DMM_A2D_SENSE_BOARD.A2D_SENSE_BOARD(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'A2D_POWER_BOARD':
            dmm = SMU_A2D_POWER_BOARD.A2D_POWER_BOARD(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'IT_M3400':
            dmm = SMU_ITM3400.IT_M3400(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'A2D_DAQ_CH':
            dmm = A2D_DAQ_control.A2D_DAQ(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'A2D_4CH_Isolated_ADC_Channel':
            dmm = DMM_A2D_4CH_Isolated_ADC.A2D_4CH_Isolated_ADC(resource_id = resource_id, resources_list = resources_list)
        '''
        elif class_name == 'MATICIAN_FET_BOARD_CH':
            #if running from this process then create the extra process from here.
            if multi_ch_event_and_queue_dict == None:
                multi_ch_event_and_queue_dict = fbm.create_event_and_queue_dicts(4,4)
            
            if resource_id == None:
                #get the event and queue dict from the proper channel of the proper mcp device
                #Figure out which devices are connected
                #dict keyed by device name should be passed in
                #Choose the device
                msg = "Which Multi Channel Device to Use?"
                title = "Multi Channel Device Selection"
                board_name = int(eg.choicebox(msg, title, multi_ch_event_and_queue_dict.keys()))
                
                #Choose the channel
                msg = "Choose Which Channel of This Device to Use:"
                title = "Multi Channel Device Channel Selection"
                ch_num = int(eg.choicebox(msg, title, multi_ch_event_and_queue_dict[board_name].keys()))
                
                resource_id = {'board_name': board_name, 'ch_num': ch_num}
            
            event_and_queue_dict = multi_ch_event_and_queue_dict[resource_id['board_name']][resource_id['ch_num']]
            
            dmm = DMM_FET_BOARD_EQ.FET_BOARD_EQ(resource_id, event_and_queue_dict)
        '''
        setup_dict = setup_instrument(dmm, setup_dict)
        if setup_dict == None:
            print("Equipment Setup Failed")
            return
        
        return class_name, dmm, setup_dict
