#Program to run the charge discharge control in different processes for each channel.

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget
from multiprocessing import Process, Queue, Event
from functools import partial
import queue #queue module required for exception handling of multiprocessing.Queue

from python_libraries import fet_board_management as fbm
import charge_discharge_control as cdc
import equipment as eq
import easygui as eg
import time

class MainTestWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		
		self.num_battery_channels = 3
		
		self.dict_for_event_and_queue = {}
		
		#Connected Equipment
		self.batt_ch_list = [None for i in range(self.num_battery_channels)]
		self.psu_ch_list = [None for i in range(self.num_battery_channels)]
		self.eload_ch_list = [None for i in range(self.num_battery_channels)]
		self.dmm_v_ch_list = [None for i in range(self.num_battery_channels)]
		self.dmm_i_ch_list = [None for i in range(self.num_battery_channels)]
		
		
		self.setWindowTitle("Battery Tester App")
		central_layout = QVBoxLayout()
		
		
		#Create a button at the top to connect multi-channel equipment
		self.connect_multi_ch_button = QPushButton("Connect Multi Channel Equipment")
		self.connect_multi_ch_button.clicked.connect(self.multi_ch_devices_process)
		central_layout.addWidget(self.connect_multi_ch_button)
		
		
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
			
	
	def multi_ch_devices_process(self):
		self.dict_for_event_and_queue = fbm.create_event_and_queue_dicts(4,4)
		
		
	
	#TODO - assign_equipment while another test is running - don't freeze the GUI. Make this a thread or process.
	#       easier once we only connect via pickle-able results.
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
			self.dmm_v_ch_list[ch_num] = eq.dmms.choose_dmm(multi_ch_event_and_queue_dict = self.dict_for_event_and_queue)
		msg = "Do you want to use a separate device to measure current on channel {}?".format(ch_num)
		title = "Current Measurement Device"
		if eg.ynbox(msg, title):
			self.dmm_i_ch_list[ch_num] = eq.dmms.choose_dmm(multi_ch_event_and_queue_dict = self.dict_for_event_and_queue)

	def start_test(self, ch_num):
		self.batt_test_process(self.batt_ch_list[ch_num], psu = self.psu_ch_list[ch_num], eload = self.eload_ch_list[ch_num],
							  dmm_v = self.dmm_v_ch_list[ch_num], dmm_i = self.dmm_i_ch_list[ch_num], data_out_queue = self.data_from_ch_queue_list[ch_num])
		
	
	def batt_test_process(self, batt_channel, psu = None, eload = None, dmm_v = None, dmm_i = None, data_out_queue = None):
		
		batt_channel.assign_equipment(psu_to_assign = psu, eload_to_assign = eload,
									  dmm_v_to_assign = dmm_v, dmm_i_to_assign = dmm_i)
		
		res_ids_dict = batt_channel.get_assigned_eq_res_ids()
		#disconnect form this process so we can pass to new process by pickle-able resource id.
		batt_channel.disconnect_all_assigned_eq()
		
		process1 = Process(target=cdc.charge_discharge_control, args = (res_ids_dict, data_out_queue))
		process1.start()

def main():
	app = QApplication([])
	test_window = MainTestWindow()
	test_window.show()
	test_window.update_loop()
	app.exec()
	
if __name__ == '__main__':
	main()
