#contains a list of all the equipment that there are libraries for
#organized into which ones have common function calls

import easygui as eg

#multi channel device management functions
from BATT_HIL import fet_board_management as fbm
from lab_equipment import A2D_DAQ_management as adm

from easygui.boxes.derived_boxes import msgbox
import time

#Eloads
from lab_equipment import Eload_BK8600
from lab_equipment import Eload_DL3000
from lab_equipment import Eload_KEL10X
from lab_equipment import Eload_IT8500
from lab_equipment import Eload_PARALLEL
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

#Digital Multimeters
from lab_equipment import DMM_DM3000
from lab_equipment import DMM_SDM3065X
from lab_equipment import DMM_FET_BOARD_EQ
from lab_equipment import A2D_DAQ_control #Just for num_channels at the moment
from lab_equipment import DMM_A2D_DAQ_CH
from lab_equipment import DMM_Fake

#Other Equipment
from lab_equipment import OTHER_A2D_Relay_Board


def setup_instrument(instrument, setup_dict):
	#This should turn into a general 'setup equipment function'
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
	
	#A2D Relay Board Channel Allocation
	if isinstance(instrument, OTHER_A2D_Relay_Board.A2D_Relay_Board):
		#special setup for this instrument
		#Need to determine if channel has an eload or a psu.
		#Assume only 2 channels for now.
		#Cannot have multiple of the same device yet.
		if 'num_channels' not in setup_dict.keys():
			title = "Relay Board Setup"
			num_channels = eg.integerbox(msg = "How Many Channels?",
										title = title, default = 2,
										lowerbound = 1, upperbound = 999)
			setup_dict['num_channels'] = num_channels
			
		instrument.num_channels = setup_dict['num_channels']
		
		if 'equipment_type_connected' not in setup_dict.keys():
			title = "Relay Board Setup"
			choices = ['eload', 'psu']
			equipment_type_connected = list()
			for i in range(num_channels):
				msg = "What is connected to channel {}?".format(i)
				response = eg.choicebox(msg, title, choices)
				equipment_type_connected.append(response)
			
			setup_dict['equipment_type_connected'] = equipment_type_connected
		
		instrument.equipment_type_connected = setup_dict['equipment_type_connected']
		
	return setup_dict

def get_equipment_dict(res_ids_dict, multi_channel_event_and_queue_dict = None):
	eq_dict = {}
	for key in res_ids_dict:
		if res_ids_dict[key] != None and res_ids_dict[key]['res_id'] != None:
			eq_dict[key] = connect_to_eq(key, res_ids_dict[key]['class_name'], res_ids_dict[key]['res_id'], res_ids_dict[key]['setup_dict'], multi_channel_event_and_queue_dict)
		else:
			eq_dict[key] = None
	return eq_dict

def connect_to_eq(key, class_name, res_id, setup_dict = None, multi_channel_event_and_queue_dict = None):
	#Key should be 'eload', 'psu', 'dmm', 'relay_board'
	#'dmm' with any following characters will be considered a dmm
	instrument = None
	
	if class_name == 'E3631A': time.sleep(1) #testing E3631A and delay for passing equipment between threads
	
	#return the actual equipment object instead of the equipment dictionary
	if key == 'eload':
		instrument = eLoads.choose_eload(class_name, res_id, setup_dict)[1]
	elif key == 'psu':
		instrument = powerSupplies.choose_psu(class_name, res_id, setup_dict)[1]
	elif key == 'dmm' or ('dmm' in key): #for dmm_i and dmm_v keys and dmm_t
		instrument = dmms.choose_dmm(class_name, resource_id = res_id, multi_ch_event_and_queue_dict = multi_channel_event_and_queue_dict, setup_dict = setup_dict)[1]
	elif key == 'relay_board':
		instrument = otherEquipment.choose_equipment(class_name, res_id, setup_dict)[1]
	time.sleep(0.1)
	return instrument

def get_res_id_dict_and_disconnect(eq_list):
	#get resource id
	class_name = eq_list[0]
	eq_res_id_dict = {'class_name': class_name, 'res_id': None, 'setup_dict': {}}
	if class_name == 'MATICIAN_FET_BOARD_CH' or class_name == 'A2D_DAQ_CH':
		eq_res_id_dict['res_id'] = {'board_name': eq_list[1].board_name, 'ch_num': eq_list[1].ch_num}
		#eq_res_id_dict['setup_dict']['remote_sense'] = False
	elif class_name == 'Parallel Eloads':
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
		eq_res_id_dict['setup_dict']['remote_sense_1'] = eq_list[1].use_remote_sense_1
		eq_res_id_dict['setup_dict']['remote_sense_2'] = eq_list[1].use_remote_sense_2
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


class otherEquipment:
	part_numbers = {
		'A2D Relay Board': 		'OTHER_A2D_Relay_Board',
		'Fake item':			'Fake_Item' #Need 2 items for a choicebox
	}
		
	@classmethod
	def choose_equipment(self, class_name = None, resource_id = None, setup_dict = None):
		if class_name == None:
			msg = "What type of equipment?"
			title = "Equipment Series Selection"
			class_name = eg.choicebox(msg, title, otherEquipment.part_numbers.keys())

		if class_name == None:
			msgbox("Failed to select the equipment.")
			return			
		
		if class_name == 'A2D Relay Board':
			instrument = OTHER_A2D_Relay_Board.A2D_Relay_Board(resource_id = resource_id)
			
		setup_dict = setup_instrument(instrument, setup_dict)
		return class_name, instrument, setup_dict


class eLoads:
	part_numbers = {
		'BK8600': 			'Eload_BK8600',
		'DL3000': 			'Eload_DL3000',
		'KEL10X': 			'Eload_KEL10X',
		'IT8500': 			'Eload_IT8500',
		'Parallel Eloads':	'Eload_PARALLEL',
		'Fake Test Eload': 	'Eload_Fake'
	}
		
	@classmethod
	def choose_eload(self, class_name = None, resource_id = None, setup_dict = None):
		if class_name == None:
			msg = "In which series is the E-Load?"
			title = "E-Load Series Selection"
			class_name = eg.choicebox(msg, title, eLoads.part_numbers.keys())

		if class_name == None:
			msgbox("Failed to select the equipment.")
			return			
		
		if class_name == 'BK8600':
			eload = Eload_BK8600.BK8600(resource_id = resource_id)
		elif class_name == 'DL3000':
			eload = Eload_DL3000.DL3000(resource_id = resource_id)
		elif class_name == 'KEL10X':
			eload = Eload_KEL10X.KEL10X(resource_id = resource_id)
		elif class_name == 'IT8500':
			eload = Eload_IT8500.IT8500(resource_id = resource_id)
		elif class_name == 'Parallel Eloads':
			eload = Eload_PARALLEL.PARALLEL(resource_id = resource_id)
		elif class_name == 'Fake Test Eload':
			eload = Eload_Fake.Fake_Eload(resource_id = resource_id)
			
		setup_dict = setup_instrument(eload, setup_dict)
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
	def choose_psu(self, class_name = None, resource_id = None, setup_dict = None):
		if class_name == None:
			msg = "In which series is the PSU?"
			title = "PSU Series Selection"
			class_name = eg.choicebox(msg, title, powerSupplies.part_numbers.keys())

		if class_name == None:
			msgbox("Failed to select the equipment.")
			return
		
		if class_name == 'SPD1000':
			psu = PSU_SPD1000.SPD1000(resource_id = resource_id)
		elif class_name == 'DP800':
			psu = PSU_DP800.DP800(resource_id = resource_id)
		elif class_name == 'KWR10X or MP71025X':
			psu = PSU_MP71025X.MP71025X(resource_id = resource_id)
		elif class_name == 'BK9100':
			psu = PSU_BK9100.BK9100(resource_id = resource_id)
		elif class_name == 'N8700':
			psu = PSU_N8700.N8700(resource_id = resource_id)
		elif class_name == 'KAXXXXP':
			psu = PSU_KAXXXXP.KAXXXXP(resource_id = resource_id)
		elif class_name == 'E3631A':
			psu = PSU_E3631A.E3631A(resource_id = resource_id)
		elif class_name == 'Fake Test PSU':
			psu = PSU_Fake.Fake_PSU(resource_id = resource_id)
			
		setup_dict = setup_instrument(psu, setup_dict)
		return class_name, psu, setup_dict


class dmms:
	part_numbers = {
		'DM3000': 					'DMM_DM3000',
		'SDM3065X': 				'DMM_SDM3065X',
		'MATICIAN_FET_BOARD_CH':	'DMM_FET_BOARD',
		'A2D_DAQ_CH':				'A2D_DAQ',
		'Fake Test DMM': 			'DMM_Fake'
	}
	
	@classmethod
	def choose_dmm(self, class_name = None, resource_id = None, multi_ch_event_and_queue_dict = None, setup_dict = None):
		if class_name == None:
			msg = "In which series is the DMM?"
			title = "DMM Series Selection"
			class_name = eg.choicebox(msg, title, dmms.part_numbers.keys())

		if class_name == None:
			msgbox("Failed to select the equipment.")
			return			
		
		if(class_name == 'DM3000'):
			dmm = DMM_DM3000.DM3000(resource_id = resource_id)
		if class_name == 'SDM3065X':
			dmm = DMM_SDM3065X.SDM3065X(resource_id = resource_id)
		elif class_name == 'Fake Test DMM':
			dmm = DMM_Fake.Fake_DMM(resource_id = resource_id)
		elif class_name == 'A2D_DAQ_CH':
			#if running from this process then create the extra process from here.
			if multi_ch_event_and_queue_dict == None:
				multi_ch_event_and_queue_dict = adm.create_event_and_queue_dicts(1, A2D_DAQ_control.A2D_DAQ.num_channels)
			
			if resource_id == None:
				#get the event and queue dict from the proper channel of the proper device
				#Figure out which devices are connected
				#dict keyed by device name should be passed in
				#Choose the device
				msg = "Which Multi Channel Device to Use?"
				title = "Multi Channel Device Selection"
				num_available = len(multi_ch_event_and_queue_dict.keys())
				if num_available == 0:
					print("No Equipment Available. Connection attempt will exit with errors")
				elif num_available == 1:
					msg = "There is only 1 A2D DAQ board available.\nWould you like to use it?\n{}".format(list(multi_ch_event_and_queue_dict.keys())[0])
					if(eg.ynbox(msg, title)):
						board_name = int(list(multi_ch_event_and_queue_dict.keys())[0])
				else:
					board_name = int(eg.choicebox(msg, title, multi_ch_event_and_queue_dict.keys()))
				
				#Choose the channel
				msg = "Choose Which Channel of This Device to Use:"
				title = "Multi Channel Device Channel Selection"
				ch_num = int(eg.choicebox(msg, title, multi_ch_event_and_queue_dict[board_name].keys()))
				
				resource_id = {'board_name': board_name, 'ch_num': ch_num}
			
			event_and_queue_dict = multi_ch_event_and_queue_dict[resource_id['board_name']][resource_id['ch_num']]
			
			dmm = DMM_A2D_DAQ_CH.A2D_DAQ_CH(resource_id, event_and_queue_dict)
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
		return class_name, dmm, False #False since we will do no remote sense for dmms for now
