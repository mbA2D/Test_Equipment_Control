#Program to run the charge discharge control in different processes for each channel.

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton
import charge_discharge_control as cdc
from multiprocessing import Process

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
		
		equipment_dict = dict()
		
		for ch_num in range(self.num_battery_channels):
			#choose a psu and eload for each channel
			eload = eloads.choose_eload()
			psu = eloade.choose_psu()
			
			#Separate measurement devices
			msg = "Do you want to use a separate device to measure voltage?"
			title = "Voltage Measurement Device"
			separate_v_meas = eg.ynbox(msg, title)
			dmm_v = None
			msg = "Do you want to use a separate device to measure current?"
			title = "Current Measurement Device"
			separate_i_meas = eg.ynbox(msg, title)
			dmm_i = None
		
		
	
	def batt_test_processes(self):		
		process1 = Process(target=cdc.charge_discharge_control)
		process1.start()

def main():
	app = QApplication([])
	test_window = MainTestWindow()
	test_window.show()
	app.exec()
	
if __name__ == '__main__':
	main()
