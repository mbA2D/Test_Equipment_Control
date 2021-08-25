#contains a list of all the equipment that there are libraries for
#organized into which ones have common function calls
import easygui as eg

#Eloads
from lab_equipment import Eload_BK8600
from lab_equipment import Eload_DL3000

#Power Supplies
from lab_equipment import PSU_DP800
from lab_equipment import PSU_SPD1000
from lab_equipment import PSU_MP71025X
from lab_equipment import PSU_BK9100
from lab_equipment import PSU_N8700

#Digital Multimeters
#import DM3068

class eLoads:
	def __init__(self):
		#organized into Cell_Name and Location
		self.part_numbers = {
			'BK8600': 'Eload_BK8600',
			'DL3000': 'Eload_DL3000'
		}
	def choose_eload(self):
		msg = "In which series is the E-Load?"
		title = "E-Load Series Selection"
		class_name = eg.choicebox(msg, title, self.part_numbers.keys())
		module_name = self.part_numbers[class_name]
		if(class_name == 'BK8600'):
			eload = Eload_BK8600.BK8600()
		elif(class_name == 'DL3000'):
			eload = Eload_DL3000.DL3000()
		return eload

class powerSupplies:
	def __init__(self):
		#organized into Cell_Name and Location
		self.part_numbers = {
			'SPD1000': 'PSU_SPD1000',
			'DP800': 'PSU_DP800',
			'MP71025X': 'PSU_MP71025X',
			'BK9100': 'PSU_BK9100',
			'N8700': 'PSU_N8700'
		}
	def choose_psu(self):
		msg = "In which series is the PSU?"
		title = "PSU Series Selection"
		class_name = eg.choicebox(msg, title, self.part_numbers.keys())
		module_name = self.part_numbers[class_name]
		if(class_name == 'SPD1000'):
			psu = PSU_SPD1000.SPD1000()
		elif(class_name == 'DP800'):
			psu = PSU_DP800.DP800()
		elif(class_name == 'MP71025X'):
			psu = PSU_MP71025X.MP71025X()
		elif(class_name == 'BK9100'):
			psu = PSU_BK9100.BK9100()
		elif(class_name == 'N8700'):
			psu = PSU_N8700.N8700()
		return psu

'''
class dmms:
	def __init__(self):
		#organized into Cell_Name and Location
		self.part_numbers = {
			'DM3068': 'DMM_DM3068'
		}
	def choose_dmm(self):
		msg = "In which series is the DMM?"
		title = "DMM Series Selection"
		class_name = eg.choicebox(msg, title, self.part_numbers.keys())
		module_name = self.part_numbers[class_name]
		return module_name, class_name
'''
