#Program to run the charge discharge control in different processes for each channel.

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton
from multiprocessing import Process

import charge_discharge_control as cdc
import equipment as eq

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
		
		batt_channel_list = list()
		
		equipment_dict = dict()
		
		for ch_num in range(self.num_battery_channels):
			
			batt_channel_list.append(cdc.BatteryChannel())
			
			#choose a psu and eload for each channel
			eload = eloads.choose_eload()
			psu = psus.choose_psu()
			
			#Separate measurement devices
			msg = "Do you want to use a separate device to measure voltage?"
			title = "Voltage Measurement Device"
			separate_v_meas = eg.ynbox(msg, title)
			dmm_v = None
			msg = "Do you want to use a separate device to measure current?"
			title = "Current Measurement Device"
			separate_i_meas = eg.ynbox(msg, title)
			dmm_i = None
		
		
	
	def batt_test_process(self, batt_channel, psu = None, eload = None, dmm_v = None, dmm_i = None):
		
		batt_channel.assign_equipment(psu_to_assign = psu, eload_to_assign = eload, dmm_v_to_assign = dmm_v, dmm_i_to_assign = dmm_i)
		
		process1 = Process(target=batt_channel.charge_discharge_control)
		process1.start()

def main():
	app = QApplication([])
	test_window = MainTestWindow()
	test_window.show()
	app.exec()
	
if __name__ == '__main__':
	main()
