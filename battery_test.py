#Program to run the charge discharge control in different processes for each channel.

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget
from multiprocessing import Process, Queue
from functools import partial
import queue #queue module required for exception handling of multiprocessing.Queue

import charge_discharge_control as cdc
import equipment as eq
import easygui as eg
import time

class MainTestWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		
		self.num_battery_channels = 3

		#Connected Equipment
		self.batt_ch_list = [None for i in range(self.num_battery_channels)]
		self.psu_ch_list = [None for i in range(self.num_battery_channels)]
		self.eload_ch_list = [None for i in range(self.num_battery_channels)]
		self.dmm_v_ch_list = [None for i in range(self.num_battery_channels)]
		self.dmm_i_ch_list = [None for i in range(self.num_battery_channels)]
		self.res_ids_dict_list = [None for i in range(self.num_battery_channels)]
		self.mp_process_list = [None for i in range(self.num_battery_channels)]
		
		
		self.setWindowTitle("Battery Tester App")
		central_layout = QVBoxLayout()
		
		#Create a widget and some labels - voltage and current for each channel
		#Update the widgets from the queues in each channel
		self.data_label_list = [QLabel("CH: {}\nV: \nI:".format(i)) for i in range(self.num_battery_channels)]
		self.button_assign_eq_list = [QPushButton("Assign Equipment") for i in range(self.num_battery_channels)]
		self.button_start_test_list = [QPushButton("Start Test") for i in range(self.num_battery_channels)]
		self.data_from_ch_queue_list = [Queue() for i in range(self.num_battery_channels)]
		self.data_dict_list = [dict() for i in range(self.num_battery_channels)]
		
		for ch_num in range(self.num_battery_channels):
			
			#setting up buttons
			self.button_assign_eq_list[ch_num].setCheckable(False)
			self.button_assign_eq_list[ch_num].clicked.connect(partial(self.assign_equipment, ch_num))
			self.button_start_test_list[ch_num].setCheckable(False)
			self.button_start_test_list[ch_num].clicked.connect(partial(self.start_test, ch_num))
			
			#setting up a widget and layout for each channel
			ch_layout = QHBoxLayout()
			ch_layout.addWidget(self.data_label_list[ch_num])
			ch_layout.addWidget(self.button_assign_eq_list[ch_num])
			ch_layout.addWidget(self.button_start_test_list[ch_num])
			
			ch_widget = QWidget()
			ch_widget.setLayout(ch_layout)
			
			central_layout.addWidget(ch_widget)
			self.batt_ch_list[ch_num] = cdc.BatteryChannel()
		
		central_widget = QWidget()
		central_widget.setLayout(central_layout)
		self.setCentralWidget(central_widget)
		
		
	def update_loop(self):
		#Loop the data updates forever - TODO: should use some Signals, Slots, Events for this maybe.
		update_interval_s = 0.1
		last_update_time = time.time()
		while True:
			#Always read new data
			for ch_num in range(self.num_battery_channels):
				try:
					#Read from all queues if available
					self.data_dict_list[ch_num] = self.data_from_ch_queue_list[ch_num].get_nowait()
				except queue.Empty:
					pass #No new data was available
			
			#Display New Data if time interval passed
			if time.time() - last_update_time > update_interval_s:
				for ch_num in range(self.num_battery_channels):
					#Update all the widgets with the new data
					try:
						self.data_label_list[ch_num].setText("CH: {}\nV: {} V\nI: {} A".format(ch_num, self.data_dict_list[ch_num]["Voltage"], self.data_dict_list[ch_num]["Current"]))
					except KeyError:
						pass #No data in the dictionary
				last_update_time = time.time()
			
			QApplication.processEvents()
			
	
	def assign_equipment(self, ch_num):
		#choose a psu and eload for each channel
		msg = "Do you want to connect a power supply for channel {}?".format(ch_num)
		title = "Power Supply Connection"
		if eg.ynbox(msg, title):
			self.psu_ch_list[ch_num] = eq.powerSupplies.choose_psu()
		msg = "Do you want to connect an eload for channel {}?".format(ch_num)
		title = "Eload Connection"
		if eg.ynbox(msg, title):
			self.eload_ch_list[ch_num] = eq.eLoads.choose_eload()
		
		#Separate measurement devices
		msg = "Do you want to use a separate device to measure voltage on channel {}?".format(ch_num)
		title = "Voltage Measurement Device"
		if eg.ynbox(msg, title):
			self.dmm_v_ch_list[ch_num] = eq.dmms.choose_dmm()
		msg = "Do you want to use a separate device to measure current on channel {}?".format(ch_num)
		title = "Current Measurement Device"
		if eg.ynbox(msg, title):
			self.dmm_i_ch_list[ch_num] = eq.dmms.choose_dmm()

		self.batt_ch_list[ch_num].assign_equipment(psu_to_assign = self.psu_ch_list[ch_num], eload_to_assign = self.eload_ch_list[ch_num],
									  dmm_v_to_assign = self.dmm_v_ch_list[ch_num], dmm_i_to_assign = self.dmm_i_ch_list[ch_num])
		
		self.res_ids_dict_list[ch_num] = self.batt_ch_list[ch_num].get_assigned_eq_res_ids()

		self.batt_ch_list[ch_num].disconnect_all_assigned_eq()

	def start_test(self, ch_num):
		self.batt_test_process(self.res_ids_dict_list[ch_num], data_out_queue = self.data_from_ch_queue_list[ch_num], ch_num = ch_num)
		
	
	def batt_test_process(self, res_ids_dict, data_out_queue = None, ch_num = None):
		# TODO: Handle res_ids_dict = None
		if self.mp_process_list[ch_num] is not None and self.mp_process_list[ch_num].is_alive():
			print(f"There is a process already running")
			return
		self.mp_process_list[ch_num] = Process(target=cdc.charge_discharge_control, args = (res_ids_dict, data_out_queue))
		self.mp_process_list[ch_num].start()
		self.mp_process_list[ch_num].join()


def main():
	app = QApplication([])
	test_window = MainTestWindow()
	test_window.show()
	test_window.update_loop()
	app.exec()
	
if __name__ == '__main__':
	main()
