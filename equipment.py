#contains a list of all the equipment that there are libraries for
#organized into which ones have common function calls
import easygui as eg

#Eloads
from lab_equipment import Eload_BK8600
from lab_equipment import Eload_DL3000
from lab_equipment import Eload_KEL10X

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

def connect_to_eq(key, class_name, res_id):
	#Key should be 'eload', 'psu', or 'dmm'
	#'dmm' with any following characters will be considered a dmm
	
	if key == 'eload':
		return eLoads.choose_eload(class_name, res_id)[1]
	if key == 'psu':
		return powerSupplies.choose_psu(class_name, res_id)[1]
	if key == 'dmm' or ('dmm' in key):
		return dmms.choose_dmm(class_name, res_id)[1]
	return None


class eLoads:
	def __init__(self):
		self.part_numbers = {
			'BK8600': 'Eload_BK8600',
			'DL3000': 'Eload_DL3000',
			'KEL10X': 'Eload_KEL10X'
		}
	@classmethod
	def choose_eload(self, class_name = None, resource_id = None):
		if class_name == None:
			msg = "In which series is the E-Load?"
			title = "E-Load Series Selection"
			class_name = eg.choicebox(msg, title, self.part_numbers.keys())
		
		if(class_name == 'BK8600'):
			eload = Eload_BK8600.BK8600(resource_id = resource_id)
		elif(class_name == 'DL3000'):
			eload = Eload_DL3000.DL3000(resource_id = resource_id)
		elif(class_name == 'KEL10X'):
			eload = Eload_KEL10X.KEL10X(resource_id = resource_id)
		return class_name, eload


class powerSupplies:
	def __init__(self):
		self.part_numbers = {
			'SPD1000': 'PSU_SPD1000',
			'DP800': 'PSU_DP800',
			'MP71025X': 'PSU_MP71025X',
			'BK9100': 'PSU_BK9100',
			'N8700': 'PSU_N8700',
            'KAXXXXP': 'PSU_KAXXXXP'
		}
	@classmethod
	def choose_psu(self, class_name = None, resource_id = None):
		if class_name == None:
			msg = "In which series is the PSU?"
			title = "PSU Series Selection"
			class_name = eg.choicebox(msg, title, self.part_numbers.keys())
		
		if(class_name == 'SPD1000'):
			psu = PSU_SPD1000.SPD1000(resource_id = resource_id)
		elif(class_name == 'DP800'):
			psu = PSU_DP800.DP800(resource_id = resource_id)
		elif(class_name == 'MP71025X'):
			psu = PSU_MP71025X.MP71025X(resource_id = resource_id)
		elif(class_name == 'BK9100'):
			psu = PSU_BK9100.BK9100(resource_id = resource_id)
		elif(class_name == 'N8700'):
			psu = PSU_N8700.N8700(resource_id = resource_id)
		elif(class_name == 'KAXXXXP'):
			psu = PSU_KAXXXXP.KAXXXXP(resource_id = resource_id)
		return class_name, psu


class dmms:
	def __init__(self):
		self.part_numbers = {
			'DM3068': 'DMM_DM3068',
			'SDM3065X': 'DMM_SDM3065X'
		}
	@classmethod
	def choose_dmm(self, class_name = None, resource_id = None):
		if class_name == None:
			msg = "In which series is the DMM?"
			title = "DMM Series Selection"
			class_name = eg.choicebox(msg, title, self.part_numbers.keys())
		
		#if(class_name == 'DM3068'):
		#	dmm = DMM_DM3068.DM3068(resource_id = resource_id)
		if(class_name == 'SDM3065X'):
			dmm = DMM_SDM3065X.SDM3065X(resource_id = resource_id)
		return class_name, dmm
