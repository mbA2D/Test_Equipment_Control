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
		
		self.num_battery_channels = int(eg.enterbox(msg = "How many battery channels?", title = "Battery Channels", default = "1"))
		self.dict_for_event_and_queue = {}

		#Connected Equipment
		self.assign_eq_process_list = [None for i in range(self.num_battery_channels)]
		self.res_ids_dict_list = [None for i in range(self.num_battery_channels)]
		self.configure_test_process_list = [None for i in range(self.num_battery_channels)]
		self.cdc_input_dict_list = [None for i in range(self.num_battery_channels)]
		self.mp_process_list = [None for i in range(self.num_battery_channels)]
		self.plot_list = [None for i in range(self.num_battery_channels)]
		
		self.eq_assignment_queue = Queue()
		self.test_configuration_queue = Queue()
		
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
		self.button_configure_test_list = [QPushButton("Configure Test") for i in range(self.num_battery_channels)]
		self.button_start_test_list = [QPushButton("Start Test") for i in range(self.num_battery_channels)]
		self.button_stop_test_list = [QPushButton("Stop Test") for i in range(self.num_battery_channels)]
		self.data_from_ch_queue_list = [Queue() for i in range(self.num_battery_channels)]
		self.data_to_ch_queue_list = [Queue() for i in range(self.num_battery_channels)]
		self.data_dict_list = [dict() for i in range(self.num_battery_channels)]
		self.ch_graph_widget = [pg.PlotWidget(background='w') for i in range(self.num_battery_channels)]
		
		for ch_num in range(self.num_battery_channels):
			
			#setting up buttons
			self.button_assign_eq_list[ch_num].setCheckable(False)
			self.button_assign_eq_list[ch_num].clicked.connect(partial(self.assign_equipment_process, ch_num))
			self.button_configure_test_list[ch_num].setCheckable(False)
			self.button_configure_test_list[ch_num].clicked.connect(partial(self.configure_test, ch_num))
			self.button_stop_test_list[ch_num].setCheckable(False)
			self.button_stop_test_list[ch_num].clicked.connect(partial(self.stop_test, ch_num))
			self.button_start_test_list[ch_num].setCheckable(False)
			self.button_start_test_list[ch_num].clicked.connect(partial(self.start_test, ch_num))
			
			#setting up a widget and layout for each channel
			ch_layout = QHBoxLayout()
			ch_layout.addWidget(self.data_label_list[ch_num])
			ch_layout.addWidget(self.ch_graph_widget[ch_num])
			self.plot_list[ch_num] = LivePlot(self.ch_graph_widget[ch_num])

			btn_grid_layout = QGridLayout()
			btn_grid_layout.addWidget(self.button_assign_eq_list[ch_num], 0, 0)
			btn_grid_layout.addWidget(self.button_configure_test_list[ch_num], 0, 1)
			btn_grid_layout.addWidget(self.button_start_test_list[ch_num], 1, 0)
			btn_grid_layout.addWidget(self.button_stop_test_list[ch_num], 1, 1)
			
			btn_grid_widget = QWidget()
			btn_grid_widget.setLayout(btn_grid_layout)
			
			ch_layout.addWidget(btn_grid_widget)
			
			ch_widget = QWidget()
			ch_widget.setLayout(ch_layout)
			
			central_layout.addWidget(ch_widget, (ch_num % 8 + 1), (0 if ch_num < 8 else 1))
		
		central_widget = QWidget()
		central_widget.setLayout(central_layout)
		self.setCentralWidget(central_widget)

		self.timer = QtCore.QTimer()
		self.timer.setInterval(0)
		self.timer.timeout.connect(self.update_loop)
		self.timer.start()
		self.last_update_time = time.time()

	def update_loop(self):
		update_interval_s = 0.5
		
		
		#Check the equipment assignment queue
		try:
			new_eq_assignment = self.eq_assignment_queue.get_nowait()
			self.res_ids_dict_list[int(new_eq_assignment['ch_num'])] = new_eq_assignment['res_ids_dict']
			print("Assigned New Equipment to Channel {}".format(new_eq_assignment['ch_num']))
		except queue.Empty:
			pass #No new data was available
		
		#Check test configuration queue
		try:
			new_test_configuration = self.test_configuration_queue.get_nowait()
			self.cdc_input_dict_list[int(new_test_configuration['ch_num'])] = new_test_configuration['cdc_input_dict']
			print("Configured Test for Channel {}".format(new_test_configuration['ch_num']))
		except queue.Empty:
			pass #No new data was available
		
		
		#Read from all the data queues
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
		
		
	#Assigning equipment in a queue so that we don't block the main window
	def assign_equipment_process(self, ch_num):
		try:
			if self.assign_eq_process_list[ch_num] is not None and self.assign_eq_process_list[ch_num].is_alive():
				print("There is a process already running to assign equipment on Channel {}".format(ch_num))
				return
			self.assign_eq_process_list[ch_num] = Process(target=self.assign_equipment, args = (ch_num, self.eq_assignment_queue))
			self.assign_eq_process_list[ch_num].start()
		except:
			traceback.print_exc()
	
	@staticmethod
	def assign_equipment(ch_num, assignment_queue):
		try:
			res_ids_dict = {'psu': None, 'eload': None, 'dmm_v': None, 'dmm_i': None}
			
			#choose a psu and eload for each channel
			msg = "Do you want to connect a power supply for channel {}?".format(ch_num)
			title = "CH {} Power Supply Connection".format(ch_num)
			if eg.ynbox(msg, title):
				psu = eq.powerSupplies.choose_psu()
				res_ids_dict['psu'] = eq.get_res_id_dict_and_disconnect(psu)
			msg = "Do you want to connect an eload for channel {}?".format(ch_num)
			title = "CH {} Eload Connection".format(ch_num)
			if eg.ynbox(msg, title):
				eload = eq.eLoads.choose_eload()
				res_ids_dict['eload'] = eq.get_res_id_dict_and_disconnect(eload)
			
			#Separate measurement devices
			msg = "Do you want to use a separate device to measure voltage on channel {}?".format(ch_num)
			title = "CH {} Voltage Measurement Device".format(ch_num)
			if eg.ynbox(msg, title):
				dmm_v = eq.dmms.choose_dmm(multi_ch_event_and_queue_dict = self.dict_for_event_and_queue)
				res_ids_dict['dmm_v'] = eq.get_res_id_dict_and_disconnect(dmm_v)
			msg = "Do you want to use a separate device to measure current on channel {}?".format(ch_num)
			title = "CH {} Current Measurement Device".format(ch_num)
			if eg.ynbox(msg, title):
				dmm_i = eq.dmms.choose_dmm(multi_ch_event_and_queue_dict = self.dict_for_event_and_queue)
				res_ids_dict['dmm_i'] = eq.get_res_id_dict_and_disconnect(dmm_i)
			
			dict_for_queue = {'ch_num': ch_num, 'res_ids_dict': res_ids_dict}
			assignment_queue.put_nowait(dict_for_queue)
			
		except:
			print("Something went wrong with assigning equipment. Please try again.")
			return


	def configure_test(self, ch_num):
		self.configure_test_process(ch_num = ch_num)
	
	def configure_test_process(self, ch_num):
		if self.configure_test_process_list[ch_num] is not None and self.configure_test_process_list[ch_num].is_alive():
				print("There is a configuration already running in Channel {}".format(ch_num))
				return
		try:
			self.configure_test_process_list[ch_num] = Process(target=cdc.get_input_dict, args = (ch_num, self.test_configuration_queue))
			self.configure_test_process_list[ch_num].start()
		except:
			traceback.print_exc()
	
	
	def start_test(self, ch_num):
		if self.res_ids_dict_list[ch_num] == None:
			print("Please Assign Equipment to Channel {} before starting a test!".format(ch_num))
			return
		if self.cdc_input_dict_list[ch_num] == None:
			print("Please Configure Test for Channel {} before starting a test!".format(ch_num))
			return
		self.batt_test_process(self.res_ids_dict_list[ch_num], data_out_queue = self.data_from_ch_queue_list[ch_num],
								data_in_queue = self.data_to_ch_queue_list[ch_num], cdc_input_dict = self.cdc_input_dict_list[ch_num], ch_num = ch_num)
	
	def batt_test_process(self, res_ids_dict, data_out_queue = None, data_in_queue = None, cdc_input_dict = None, ch_num = None):
		try:
			if self.mp_process_list[ch_num] is not None and self.mp_process_list[ch_num].is_alive():
				print("There is a process already running in Channel {}".format(ch_num))
				return
			self.mp_process_list[ch_num] = Process(target=cdc.charge_discharge_control, args = (res_ids_dict, data_out_queue, data_in_queue, cdc_input_dict))
			self.mp_process_list[ch_num].start()
		except:
			traceback.print_exc()
	
	
	def stop_test(self, ch_num):
		self.data_to_ch_queue_list[ch_num].put_nowait('stop')
		#Need to properly close the process somehow


def main():
	app = QApplication([])
	test_window = MainTestWindow()
	test_window.show()
	app.exec()
	
if __name__ == '__main__':
	main()
