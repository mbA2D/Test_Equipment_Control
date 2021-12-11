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

#Power Supplies
from lab_equipment import PSU_DP800
from lab_equipment import PSU_SPD1000
from lab_equipment import PSU_MP71025X
from lab_equipment import PSU_BK9100
from lab_equipment import PSU_N8700
from lab_equipment import PSU_KAXXXXP

#Digital Multimeters
#from lab_equipment import DM3068
from lab_equipment import DMM_SDM3065X
from lab_equipment import DMM_FET_BOARD_EQ

def connect_to_eq(key, class_name, res_id):
	#Key should be 'eload', 'psu', or 'dmm'
	#'dmm' with any following characters will be considered a dmm
	
	if key == 'eload':
		return eLoads.choose_eload(class_name, res_id)[1]
	if key == 'psu':
		return powerSupplies.choose_psu(class_name, res_id)[1]
	if key == 'dmm' or ('dmm' in key): #for dmm_i and dmm_v keys
		if class_name == 'MATICIAN_FET_BOARD_CH':
			dmm = dmms.choose_dmm(class_name = class_name, event_and_queue_dict = res_id)[1]
		else:
			dmm = dmms.choose_dmm(class_name, res_id)[1]
		return dmm
	return None


class eLoads:
	part_numbers = {
		'BK8600': 'Eload_BK8600',
		'DL3000': 'Eload_DL3000',
		'KEL10X': 'Eload_KEL10X',
		'IT8500': 'Eload_IT8500'
	}
		
	@classmethod
	def choose_eload(self, class_name = None, resource_id = None):
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
		return class_name, eload


class powerSupplies:
	part_numbers = {
		'SPD1000': 				'PSU_SPD1000',
		'DP800': 				'PSU_DP800',
		'KWR10X or MP71025X': 	'PSU_MP71025X',
		'BK9100': 				'PSU_BK9100',
		'N8700': 				'PSU_N8700',
		'KAXXXXP': 				'PSU_KAXXXXP'
	}
	
	@classmethod
	def choose_psu(self, class_name = None, resource_id = None):
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
		return class_name, psu


class dmms:
	part_numbers = {
		'DM3068': 					'DMM_DM3068',
		'SDM3065X': 				'DMM_SDM3065X',
		'MATICIAN_FET_BOARD_CH':	'DMM_FET_BOARD'
	}
	
	@classmethod
	def choose_dmm(self, class_name = None, resource_id = None, event_and_queue_dict = None, multi_ch_event_and_queue_dict = None):
		if class_name == None:
			msg = "In which series is the DMM?"
			title = "DMM Series Selection"
			class_name = eg.choicebox(msg, title, dmms.part_numbers.keys())

		if class_name == None:
			msgbox("Failed to select the equipment.")
			return			
		
		#if(class_name == 'DM3068'):
		#	dmm = DMM_DM3068.DM3068(resource_id = resource_id)
		if class_name == 'SDM3065X':
			dmm = DMM_SDM3065X.SDM3065X(resource_id = resource_id)
		elif class_name == 'MATICIAN_FET_BOARD_CH':
			if event_and_queue_dict == None:
				if multi_ch_event_and_queue_dict == None:
					multi_ch_event_and_queue_dict = fbm.create_event_and_queue_dicts(4,4)
					
				#get the event and queue dict from the proper channel of the proper mcp device
				#Figure out which devices are connected
					#dict keyed by device name should be passed in
				#Choose the device
				msg = "Which Multi Channel Device to Use?"
				title = "Multi Channel Device Selection"
				multi_ch_device_name = int(eg.choicebox(msg, title, multi_ch_event_and_queue_dict.keys()))
				
				#Choose the channel
				msg = "Choose Which Channel of This Device to Use:"
				title = "Multi Channel Device Channel Selection"
				ch_num = int(eg.choicebox(msg, title, multi_ch_event_and_queue_dict[multi_ch_device_name].keys()))
				
				event_and_queue_dict = multi_ch_event_and_queue_dict[multi_ch_device_name][ch_num]
			
			dmm = DMM_FET_BOARD_EQ.FET_BOARD_EQ(event_and_queue_dict)
		return class_name, dmm
