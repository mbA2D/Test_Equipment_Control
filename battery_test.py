#Program to run the charge discharge control in different processes for each channel.

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QGridLayout
from PyQt6 import QtCore
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
from multiprocessing import Process, Queue, Event
from functools import partial
import queue #queue module required for exception handling of multiprocessing.Queue
import traceback
from random import randint

from BATT_HIL import fet_board_management as fbm
import charge_discharge_control as cdc
import equipment as eq
import easygui as eg
import time

class LivePlot:
	def __init__(self, plot_widget):
		self.x = list(range(100))  # 100 time points
		self.y = [0 for _ in range(100)]  # 100 data points
		self.y2 = [0 for _ in range(100)]
		self.data_line = plot_widget.plot(self.x, self.y, pen=pg.mkPen('r'))
		self.data_line2 = plot_widget.plot(self.x, self.y2, pen=pg.mkPen('b'))

class MainTestWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		
		self.num_battery_channels = 16
		self.dict_for_event_and_queue = {}

		#Connected Equipment
		self.batt_ch_list = [None for i in range(self.num_battery_channels)]
		self.psu_ch_list = [None for i in range(self.num_battery_channels)]
		self.eload_ch_list = [None for i in range(self.num_battery_channels)]
		self.dmm_v_ch_list = [None for i in range(self.num_battery_channels)]
		self.dmm_i_ch_list = [None for i in range(self.num_battery_channels)]
		self.res_ids_dict_list = [None for i in range(self.num_battery_channels)]
		self.mp_process_list = [None for i in range(self.num_battery_channels)]
		self.plot_list = [None for i in range(self.num_battery_channels)]
		
		
		self.setWindowTitle("Battery Tester App")
		central_layout = QGridLayout()
		
		
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
		self.ch_graph_widget = [pg.PlotWidget(background='w') for i in range(self.num_battery_channels)]
		
		for ch_num in range(self.num_battery_channels):
			
			#setting up buttons
			self.button_assign_eq_list[ch_num].setCheckable(False)
			self.button_assign_eq_list[ch_num].clicked.connect(partial(self.assign_equipment, ch_num))
			self.button_start_test_list[ch_num].setCheckable(False)
			self.button_start_test_list[ch_num].clicked.connect(partial(self.start_test, ch_num))
			
			#setting up a widget and layout for each channel
			ch_layout = QHBoxLayout()
			ch_layout.addWidget(self.data_label_list[ch_num])
			ch_layout.addWidget(self.ch_graph_widget[ch_num])
			self.plot_list[ch_num] = LivePlot(self.ch_graph_widget[ch_num])


			ch_layout.addWidget(self.button_assign_eq_list[ch_num])
			ch_layout.addWidget(self.button_start_test_list[ch_num])
			
			ch_widget = QWidget()
			ch_widget.setLayout(ch_layout)
			
			central_layout.addWidget(ch_widget, (ch_num % 8 + 1), (0 if ch_num < 8 else 1))
			self.batt_ch_list[ch_num] = cdc.BatteryChannel()
		
		central_widget = QWidget()
		central_widget.setLayout(central_layout)
		self.setCentralWidget(central_widget)

		self.timer = QtCore.QTimer()
		self.timer.setInterval(0)
		self.timer.timeout.connect(self.update_loop)
		self.timer.start()
		self.last_update_time = time.time()

	def update_loop(self):
		update_interval_s = 0.1

		for ch_num in range(self.num_battery_channels):
			try:
				#Read from all queues if available
				self.data_dict_list[ch_num] = self.data_from_ch_queue_list[ch_num].get_nowait()
			except queue.Empty:
				pass #No new data was available

		if time.time() - self.last_update_time > update_interval_s:
			for ch_num in range(self.num_battery_channels):
				self.plot_list[ch_num].x = self.plot_list[ch_num].x[1:]
				self.plot_list[ch_num].x.append(self.plot_list[ch_num].x[-1] + 1)
				
				self.plot_list[ch_num].y = self.plot_list[ch_num].y[1:]
				self.plot_list[ch_num].y2 = self.plot_list[ch_num].y2[1:]
				
				if "Voltage" and "Current" in self.data_dict_list[ch_num].keys():
					self.plot_list[ch_num].y.append(self.data_dict_list[ch_num]["Voltage"])
					self.plot_list[ch_num].y2.append(self.data_dict_list[ch_num]["Current"])
				else:
					self.plot_list[ch_num].y.append(0)
					self.plot_list[ch_num].y2.append(0)

				self.plot_list[ch_num].data_line.setData(self.plot_list[ch_num].x, self.plot_list[ch_num].y)
				self.plot_list[ch_num].data_line2.setData(self.plot_list[ch_num].x, self.plot_list[ch_num].y2)
			self.last_update_time = time.time()
	
	def multi_ch_devices_process(self):
		self.dict_for_event_and_queue = fbm.create_event_and_queue_dicts(4,4)
		
		
	
	#TODO - assign_equipment while another test is running - don't freeze the GUI. Make this a thread or process.
	#       easier once we only connect via pickle-able results.
	def assign_equipment(self, ch_num):
		try:
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

			self.batt_ch_list[ch_num].assign_equipment(psu_to_assign = self.psu_ch_list[ch_num], eload_to_assign = self.eload_ch_list[ch_num],
										dmm_v_to_assign = self.dmm_v_ch_list[ch_num], dmm_i_to_assign = self.dmm_i_ch_list[ch_num])
			
			self.res_ids_dict_list[ch_num] = self.batt_ch_list[ch_num].get_assigned_eq_res_ids()

			self.batt_ch_list[ch_num].disconnect_all_assigned_eq()
		except:
			print("Something went wrong with assigning equipment. Please try again.")
			return

	def start_test(self, ch_num):
		self.batt_test_process(self.res_ids_dict_list[ch_num], data_out_queue = self.data_from_ch_queue_list[ch_num], ch_num = ch_num)
		
	
	def batt_test_process(self, res_ids_dict, data_out_queue = None, ch_num = None):
		if res_ids_dict == None:
			print("Please Assign Equipment to this Channel before starting a test!")
			return

		try:
			if self.mp_process_list[ch_num] is not None and self.mp_process_list[ch_num].is_alive():
				print(f"There is a process already running in Channel {ch_num}")
				return
			self.mp_process_list[ch_num] = Process(target=cdc.charge_discharge_control, args = (res_ids_dict, data_out_queue))
			self.mp_process_list[ch_num].start()
		except:
			traceback.print_exc()


def main():
	app = QApplication([])
	test_window = MainTestWindow()
	test_window.show()
	app.exec()
	
if __name__ == '__main__':
	main()
