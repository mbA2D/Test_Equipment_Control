#contains a list of all the equipment that there are libraries for
#organized into which ones have common function calls
import easygui as eg
from BATT_HIL import fet_board_management as fbm
from easygui.boxes.derived_boxes import msgbox

#Eloads
from lab_equipment import Eload_BK8600
from lab_equipment import Eload_DL3000
from lab_equipment import Eload_KEL10X
from lab_equipment import Eload_IT8500
from lab_equipment import Eload_Fake

#Power Supplies
from lab_equipment import PSU_DP800
from lab_equipment import PSU_SPD1000
from lab_equipment import PSU_MP71025X
from lab_equipment import PSU_BK9100
from lab_equipment import PSU_N8700
from lab_equipment import PSU_KAXXXXP
from lab_equipment import PSU_Fake

#Digital Multimeters
from lab_equipment import DMM_DM3000
from lab_equipment import DMM_SDM3065X
from lab_equipment import DMM_FET_BOARD_EQ
from lab_equipment import DMM_Fake

def setup_remote_sense(instrument, use_remote_sense):
	try:
		if instrument.has_remote_sense:
			if use_remote_sense == None:
				#ask to use remote sense
				msg = "Do you want to use remote sense on this instrument?"
				title = "Remote Sense"
				use_remote_sense = eg.ynbox(msg, title)
			instrument.remote_sense(use_remote_sense)
			return use_remote_sense
	except AttributeError:
		pass
	return None

def get_equipment_dict(res_ids_dict, multi_channel_event_and_queue_dict = None):
	eq_dict = {}
	for key in res_ids_dict:
		if res_ids_dict[key] != None and res_ids_dict[key]['res_id'] != None:
			eq_dict[key] = connect_to_eq(key, res_ids_dict[key]['class_name'], res_ids_dict[key]['res_id'], res_ids_dict[key]['use_remote_sense'], multi_channel_event_and_queue_dict)
		else:
			eq_dict[key] = None
	return eq_dict

def connect_to_eq(key, class_name, res_id, use_remote_sense = None, multi_channel_event_and_queue_dict = None):
	#Key should be 'eload', 'psu', or 'dmm'
	#'dmm' with any following characters will be considered a dmm
	instrument = None
	
	#return the actual equipment object instead of the equipment dictionary
	if key == 'eload':
		instrument = eLoads.choose_eload(class_name, res_id, use_remote_sense)[1]
	if key == 'psu':
		instrument = powerSupplies.choose_psu(class_name, res_id, use_remote_sense)[1]
	if key == 'dmm' or ('dmm' in key): #for dmm_i and dmm_v keys
		instrument = dmms.choose_dmm(class_name, resource_id = res_id, multi_ch_event_and_queue_dict = multi_channel_event_and_queue_dict, use_remote_sense = use_remote_sense)[1]

	return instrument

def get_res_id_dict_and_disconnect(eq_list):
	#get resource id
	class_name = eq_list[0]
	eq_res_id_dict = {'class_name': class_name, 'res_id': None, 'use_remote_sense': None}
	if class_name == 'MATICIAN_FET_BOARD_CH':
		eq_res_id_dict['res_id'] = {'board_name': eq_list[1].board_name, 'ch_num': eq_list[1].ch_num}
		eq_res_id_dict['use_remote_sense'] = False
	elif 'Fake' in class_name:
		eq_res_id_dict['res_id'] = 'Fake'
		eq_res_id_dict['use_remote_sense'] = eq_list[2]
	else:
		try:
			eq_res_id_dict['res_id'] = eq_list[1].inst.resource_name
			eq_res_id_dict['use_remote_sense'] = eq_list[2]
		except AttributeError:
			print("No res_id for instrument")
		
	#disconnect from equipment
	try:
		eq_list[1].inst.close()
	except AttributeError:
		pass #temporary fix for 'virtual and fake instruments' - TODO - figure out a way to do this more properly
	
	return eq_res_id_dict

class eLoads:
	part_numbers = {
		'BK8600': 			'Eload_BK8600',
		'DL3000': 			'Eload_DL3000',
		'KEL10X': 			'Eload_KEL10X',
		'IT8500': 			'Eload_IT8500',
		'Fake Test Eload': 	'Eload_Fake'
	}
		
	@classmethod
	def choose_eload(self, class_name = None, resource_id = None, use_remote_sense = None):
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
		elif class_name == 'Fake Test Eload':
			eload = Eload_Fake.Fake_Eload(resource_id = resource_id)
			
		use_remote_sense = setup_remote_sense(eload, use_remote_sense)
		return class_name, eload, use_remote_sense


class powerSupplies:
	part_numbers = {
		'SPD1000': 				'PSU_SPD1000',
		'DP800': 				'PSU_DP800',
		'KWR10X or MP71025X': 	'PSU_MP71025X',
		'BK9100': 				'PSU_BK9100',
		'N8700': 				'PSU_N8700',
		'KAXXXXP': 				'PSU_KAXXXXP',
		'Fake Test PSU':        'PSU_Fake'
	}
	
	@classmethod
	def choose_psu(self, class_name = None, resource_id = None, use_remote_sense = None):
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
		elif class_name == 'Fake Test PSU':
			psu = PSU_Fake.Fake_PSU(resource_id = resource_id)
			
		use_remote_sense = setup_remote_sense(psu, use_remote_sense)
		return class_name, psu, use_remote_sense


class dmms:
	part_numbers = {
		'DM3000': 					'DMM_DM3000',
		'SDM3065X': 				'DMM_SDM3065X',
		'MATICIAN_FET_BOARD_CH':	'DMM_FET_BOARD',
		'Fake Test DMM': 			'DMM_Fake'
	}
	
	@classmethod
	def choose_dmm(self, class_name = None, resource_id = None, multi_ch_event_and_queue_dict = None, use_remote_sense = None):
		#use_remote_sense is here to have similar interface to other functions, but does nothing in this case
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
