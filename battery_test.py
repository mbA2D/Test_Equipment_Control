#Program to run the charge discharge control in different processes for each channel.

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton
from multiprocessing import Process

import charge_discharge_control as cdc
import equipment as eq
import easygui as eg

class MainTestWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		
		self.num_battery_channels = 1
		
		self.setWindowTitle("Battery Tester App")
		button = QPushButton("Start Test")
		button.setCheckable(False)
		button.clicked.connect(self.setup_battery_channels)
		self.setCentralWidget(button)
	
	def setup_battery_channels(self):
		eloads = eq.eLoads()
		psus = eq.powerSupplies()
		dmms = eq.dmms()
		
		batt_ch_list = [None for i in range(self.num_battery_channels)]
		psu_ch_list = [None for i in range(self.num_battery_channels)]
		eload_ch_list = [None for i in range(self.num_battery_channels)]
		dmm_v_ch_list = [None for i in range(self.num_battery_channels)]
		dmm_i_ch_list = [None for i in range(self.num_battery_channels)]
		
		#Assign all equipment
		for ch_num in range(self.num_battery_channels):
			
			batt_ch_list[ch_num] = cdc.BatteryChannel()
			
			#choose a psu and eload for each channel
			eload_ch_list[ch_num] = eloads.choose_eload()
			psu_ch_list[ch_num] = psus.choose_psu()
			
			#Separate measurement devices
			msg = "Do you want to use a separate device to measure voltage?"
			title = "Voltage Measurement Device"
			if eg.ynbox(msg, title):
				dmm_v_ch_list[ch_num] = dmms.choose_dmm()
			msg = "Do you want to use a separate device to measure current?"
			title = "Current Measurement Device"
			if eg.ynbox(msg, title):
				dmm_i_ch_list[ch_num] = dmms.choose_dmm()

		
		#Start tests on each channel
		for ch_num in range(self.num_battery_channels):
			self.batt_test_process(batt_ch_list[ch_num], psu = psu_ch_list[ch_num], eload = eload_ch_list[ch_num],
							  dmm_v = dmm_v_ch_list[ch_num], dmm_i = dmm_i_ch_list[ch_num])
		
	
	def batt_test_process(self, batt_channel, psu = None, eload = None, dmm_v = None, dmm_i = None):
		
		batt_channel.assign_equipment(psu_to_assign = psu, eload_to_assign = eload,
									  dmm_v_to_assign = dmm_v, dmm_i_to_assign = dmm_i)
		
		process1 = Process(target=batt_channel.charge_discharge_control)
		process1.start()

def main():
	app = QApplication([])
	test_window = MainTestWindow()
	test_window.show()
	app.exec()
	
if __name__ == '__main__':
	main()
