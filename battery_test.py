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
from lab_equipment import A2D_DAQ_management as adm
import charge_discharge_control as cdc
import equipment as eq
import easygui as eg
import jsonIO
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
        
        self.num_battery_channels = 0
        
        self.dict_for_event_and_queue = {}
        self.multi_ch_device_process = None
        self.multi_ch_management_queue = None
    
        self.eq_assignment_queue = Queue()
        self.test_configuration_queue = Queue()
        self.edit_cell_name_queue = Queue()
        
        self.setWindowTitle("Battery Tester App")
        self.central_layout = QVBoxLayout()
        
        #Create a button at the top to connect multi-channel equipment
        self.connect_multi_ch_button = QPushButton("Connect Multi Channel Equipment")
        self.connect_multi_ch_button.clicked.connect(self.multi_ch_devices_process)
        self.central_layout.addWidget(self.connect_multi_ch_button)
        #Button for Export Equipment setup
        self.export_equipment_assignment_btn = QPushButton("Export Equipment Assignment")
        self.export_equipment_assignment_btn.clicked.connect(self.export_equipment_assignment)
        self.central_layout.addWidget(self.export_equipment_assignment_btn)
        #Button for Import Equipment setup
        self.import_equipment_assignment_btn = QPushButton("Import Equipment Assignment")
        self.import_equipment_assignment_btn.clicked.connect(self.import_equipment_assignment)
        self.central_layout.addWidget(self.import_equipment_assignment_btn)
        
        self.channels_layout = QGridLayout()
        channels_widget = QWidget()
        channels_widget.setLayout(self.channels_layout)
        self.central_layout.addWidget(channels_widget)
        
        central_widget = QWidget()
        central_widget.setLayout(self.central_layout)
        self.setCentralWidget(central_widget)
        
        self.timer = QtCore.QTimer()
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.update_loop)
        self.timer.start()
        self.last_update_time = time.time()
        
        #Connected Equipment
        self.assign_eq_process_list = {}
        self.res_ids_dict_list = {}
        self.configure_test_process_list = {}
        self.edit_cell_name_process_list = {}
        self.import_test_process_list = {}
        self.export_test_process_list = {}
        self.cdc_input_dict_list = {}
        self.mp_process_list = {}
        self.mp_idle_process_list = {}
        self.plot_list = {}
        
        #Create a widget and some labels - voltage and current for each channel
        #Update the widgets from the queues in each channel
        self.cell_name_label_list = {}
        self.button_edit_cell_name_list = {}
        self.data_label_list = {}
        self.current_status_label_list = {}
        self.next_status_label_list = {}
        self.button_assign_eq_list = {}
        self.button_configure_test_list = {}
        self.button_import_test_list = {}
        self.button_export_test_list = {}
        self.button_start_test_list = {}
        self.button_stop_test_list = {}
        self.data_from_ch_queue_list = {}
        self.data_to_ch_queue_list = {}
        self.data_to_idle_ch_queue_list = {}
        self.data_dict_list = {}
        self.ch_graph_widget = {}
        
        self.setup_channels()
    
    def clear_layout(self, layout):
        #https://stackoverflow.com/questions/4528347/clear-all-widgets-in-a-layout-in-pyqt
        if layout is not None:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget() is not None:
                    child.widget().deleteLater()
                elif child.layout() is not None:
                    clear_layout(child.layout())
    
    def remove_all_channels(self):
        self.clear_layout(self.channels_layout)
        
        for ch_num in range(self.num_battery_channels):
            self.stop_process(self.assign_eq_process_list[ch_num])
            self.stop_process(self.mp_process_list[ch_num])
            self.stop_process(self.mp_idle_process_list[ch_num])
    
    def setup_channels(self, num_ch = None):
        self.remove_all_channels()
        
        if num_ch == None:
            num_ch = int(eg.enterbox(msg = "How many battery channels?", title = "Battery Channels", default = "1"))
        self.num_battery_channels = num_ch
        
        for ch_num in range(self.num_battery_channels):
            
            #Connected Equipment
            self.assign_eq_process_list[ch_num] = None
            self.res_ids_dict_list[ch_num] = None
            self.configure_test_process_list[ch_num] = None
            self.edit_cell_name_process_list[ch_num] = None
            self.import_test_process_list[ch_num] = None
            self.export_test_process_list[ch_num] = None
            self.cdc_input_dict_list[ch_num] = None
            self.mp_process_list[ch_num] = None
            self.mp_idle_process_list[ch_num] = None
            self.plot_list[ch_num] = None
            
            #Create a widget and some labels - voltage and current for each channel
            #Update the widgets from the queues in each channel
            self.cell_name_label_list[ch_num] = QLabel("N/A")
            self.button_edit_cell_name_list[ch_num] = QPushButton("Edit Cell Name")
            self.data_label_list[ch_num] = QLabel("CH: {}\nV: \nI:".format(ch_num))
            self.current_status_label_list[ch_num] = QLabel("Current Status: Idle")
            self.next_status_label_list[ch_num] = QLabel("Next Status: N/A")
            self.button_assign_eq_list[ch_num] = QPushButton("Assign Equipment")
            self.button_configure_test_list[ch_num] = QPushButton("Configure Test")
            self.button_import_test_list[ch_num] = QPushButton("Import Test")
            self.button_export_test_list[ch_num] = QPushButton("Export Test")
            self.button_start_test_list[ch_num] = QPushButton("Start Test")
            self.button_stop_test_list[ch_num] = QPushButton("Stop Test")
            self.data_from_ch_queue_list[ch_num] = Queue()
            self.data_to_ch_queue_list[ch_num] = Queue()
            self.data_to_idle_ch_queue_list[ch_num] = Queue()
            self.data_dict_list[ch_num] = {}
            self.ch_graph_widget[ch_num] = pg.PlotWidget(background='w')
            
            #setting up buttons
            self.button_edit_cell_name_list[ch_num].setCheckable(False)
            self.button_edit_cell_name_list[ch_num].clicked.connect(partial(self.edit_cell_name, ch_num))
            
            self.button_assign_eq_list[ch_num].setCheckable(False)
            self.button_assign_eq_list[ch_num].clicked.connect(partial(self.assign_equipment_process, ch_num))
            self.button_configure_test_list[ch_num].setCheckable(False)
            self.button_configure_test_list[ch_num].clicked.connect(partial(self.configure_test, ch_num))
            
            self.button_import_test_list[ch_num].setCheckable(False)
            self.button_import_test_list[ch_num].clicked.connect(partial(self.import_test_configuration_process, ch_num))
            self.button_export_test_list[ch_num].setCheckable(False)
            self.button_export_test_list[ch_num].clicked.connect(partial(self.export_test_configuration_process, ch_num))
            
            self.button_stop_test_list[ch_num].setCheckable(False)
            self.button_stop_test_list[ch_num].clicked.connect(partial(self.stop_test, ch_num))
            self.button_start_test_list[ch_num].setCheckable(False)
            self.button_start_test_list[ch_num].clicked.connect(partial(self.start_test, ch_num))
            
            #setting up a widget and layout for each channel
            ch_layout = QHBoxLayout() #Each channel has horizontal layout
            
            #Data label on the left
            left_col_layout = QVBoxLayout()
            left_col_layout.addWidget(self.cell_name_label_list[ch_num])
            left_col_layout.addWidget(self.button_edit_cell_name_list[ch_num])
            left_col_layout.addWidget(self.data_label_list[ch_num])
            left_col_layout.addWidget(self.current_status_label_list[ch_num])
            left_col_layout.addWidget(self.next_status_label_list[ch_num])
            
            left_col_widget = QWidget()
            left_col_widget.setLayout(left_col_layout)
            
            ch_layout.addWidget(left_col_widget)
            
            
            #Graph in the middle
            ch_layout.addWidget(self.ch_graph_widget[ch_num])
            self.plot_list[ch_num] = LivePlot(self.ch_graph_widget[ch_num])
            
            #Buttons on the right
            btn_grid_layout = QGridLayout()
            btn_grid_layout.addWidget(self.button_assign_eq_list[ch_num], 0, 0)
            btn_grid_layout.addWidget(self.button_configure_test_list[ch_num], 0, 1)
            
            btn_grid_layout.addWidget(self.button_import_test_list[ch_num], 1, 0)
            btn_grid_layout.addWidget(self.button_export_test_list[ch_num], 1, 1)
            
            btn_grid_layout.addWidget(self.button_start_test_list[ch_num], 2, 0)
            btn_grid_layout.addWidget(self.button_stop_test_list[ch_num], 2, 1)
            
            btn_grid_widget = QWidget()
            btn_grid_widget.setLayout(btn_grid_layout)
            
            ch_layout.addWidget(btn_grid_widget)
            
            ch_widget = QWidget()
            ch_widget.setLayout(ch_layout)
            
            self.channels_layout.addWidget(ch_widget, (ch_num % 8 + 1), (int(ch_num/8)))
        
        
    def update_loop(self):
        update_interval_s = 0.5
        
        #Check the equipment assignment queue
        try:
            new_eq_assignment = self.eq_assignment_queue.get_nowait()
            self.res_ids_dict_list[int(new_eq_assignment['ch_num'])] = new_eq_assignment['res_ids_dict']
            #stop the idle test to re-start with new equipment
            self.stop_idle_process(int(new_eq_assignment['ch_num']))
            print("CH{} - Assigned New Equipment".format(new_eq_assignment['ch_num']))
        except queue.Empty:
            pass #No new data was available
        
        #Check test configuration queue
        try:
            new_test_configuration = self.test_configuration_queue.get_nowait()
            ch_num = int(new_test_configuration['ch_num'])
            self.cdc_input_dict_list[ch_num] = new_test_configuration['cdc_input_dict']
            #Update cell name
            self.cell_name_label_list[ch_num].setText(new_test_configuration['cdc_input_dict']['cell_name'])
            #Set the next status label
            self.next_status_label_list[ch_num].setText(f"Next Status: {new_test_configuration['cdc_input_dict']['cycle_settings_list_of_lists'][0][0]['cycle_type']}")
            print("CH{} - Configured Test".format(new_test_configuration['ch_num']))
        except queue.Empty:
            pass #No new data was available		
        
        #Check edit cell name queue
        try:
            new_cell_name_dict = self.edit_cell_name_queue.get_nowait()
            ch_num = int(new_cell_name_dict['ch_num'])
            self.cell_name_label_list[ch_num].setText(new_cell_name_dict['cell_name'])
            if self.cdc_input_dict_list[ch_num] != None:
                self.cdc_input_dict_list[ch_num]['cell_name'] = new_cell_name_dict['cell_name']
            print("CH{} - Updated Cell Name".format(new_cell_name_dict['ch_num']))
        except queue.Empty:
            pass #No new data was available
        
        #Read from all the data queues
        for ch_num in range(self.num_battery_channels):
            try:
                #if main process does not exist, or exists and is dead
                #and if idle process does not exist or exists and is dead
                if  (self.mp_process_list[ch_num] == None or 
                    (self.mp_process_list[ch_num] != None and not self.mp_process_list[ch_num].is_alive())) and \
                    (self.mp_idle_process_list[ch_num] == None or
                    (self.mp_idle_process_list[ch_num] != None and not self.mp_idle_process_list[ch_num].is_alive())):
                        #Set the current status to idle and next status to 'N/A' or the next cycle
                        self.current_status_label_list[ch_num].setText('Current Status: Idle')
                        try:
                            self.next_status_label_list[ch_num].setText(f"Next Status: {self.cdc_input_dict_list[ch_num]['cycle_settings_list_of_lists'][0][0]['cycle_type']}")
                        except (KeyError, TypeError):
                            self.next_status_label_list[ch_num].setText('Next Status: N/A')
                            
                        #start an idle process since nothing else is running
                        self.start_idle_process(ch_num)
                
                #Read from all queues if available
                data_from_ch = self.data_from_ch_queue_list[ch_num].get_nowait()
                if data_from_ch['type'] == 'status':
                    self.current_status_label_list[ch_num].setText(f"Current Status: {data_from_ch['data'][0]}")
                    self.next_status_label_list[ch_num].setText(f"Next Status: {data_from_ch['data'][1]}")
                elif data_from_ch['type'] == 'measurement':
                    self.data_dict_list[ch_num] = data_from_ch['data']
                
            except queue.Empty:
                pass #No new data was available
        
        #Update plots and displayed values
        if time.time() - self.last_update_time > update_interval_s:
            for ch_num in range(self.num_battery_channels):
                voltage = 0
                current = 0
                if "Voltage" and "Current" in self.data_dict_list[ch_num].keys():
                    voltage = self.data_dict_list[ch_num]["Voltage"]
                    current = self.data_dict_list[ch_num]["Current"]
                
                #update data label
                self.data_label_list[ch_num].setText("CH: {}\nV: {}\nI: {}".format(ch_num, voltage, current))
                
                #update plot
                self.plot_list[ch_num].x = self.plot_list[ch_num].x[1:]
                self.plot_list[ch_num].x.append(self.plot_list[ch_num].x[-1] + 1)
                
                self.plot_list[ch_num].y = self.plot_list[ch_num].y[1:]
                self.plot_list[ch_num].y2 = self.plot_list[ch_num].y2[1:]
                
                self.plot_list[ch_num].y.append(voltage)
                self.plot_list[ch_num].y2.append(current)

                self.plot_list[ch_num].data_line.setData(self.plot_list[ch_num].x, self.plot_list[ch_num].y)
                self.plot_list[ch_num].data_line2.setData(self.plot_list[ch_num].x, self.plot_list[ch_num].y2)
            self.last_update_time = time.time()
    
    def multi_ch_devices_process(self):
        #TODO - ask which board to connect to - for now, we will just connect to an A2D DAQ
        self.dict_for_event_and_queue, self.multi_ch_management_queue, self.multi_ch_device_process = adm.create_event_and_queue_dicts()
        #self.dict_for_event_and_queue = fbm.create_event_and_queue_dicts(4,4)
        
        
    #Assigning equipment in a queue so that we don't block the main window
    def assign_equipment_process(self, ch_num):
        try:
            if self.assign_eq_process_list[ch_num] is not None and self.assign_eq_process_list[ch_num].is_alive():
                print("CH{} - There is a process already running to assign equipment".format(ch_num))
                return
            self.assign_eq_process_list[ch_num] = Process(target=self.assign_equipment, args = (ch_num, self.eq_assignment_queue, None, self.dict_for_event_and_queue))
            self.assign_eq_process_list[ch_num].start()
        except:
            traceback.print_exc()
            
    @staticmethod
    def assign_equipment(ch_num, assignment_queue, res_ids_dict = None, dict_for_event_and_queue = None):
        try:
            if res_ids_dict == None:
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
                
                #Separate measurement devices - total voltage and current
                msg = "Do you want to use a separate device to measure voltage on channel {}?".format(ch_num)
                title = "CH {} Voltage Measurement Device".format(ch_num)
                if eg.ynbox(msg, title):
                    dmm_v = eq.dmms.choose_dmm(multi_ch_event_and_queue_dict = dict_for_event_and_queue)
                    res_ids_dict['dmm_v'] = eq.get_res_id_dict_and_disconnect(dmm_v)
                msg = "Do you want to use a separate device to measure current on channel {}?".format(ch_num)
                title = "CH {} Current Measurement Device".format(ch_num)
                if eg.ynbox(msg, title):
                    dmm_i = eq.dmms.choose_dmm(multi_ch_event_and_queue_dict = dict_for_event_and_queue)
                    res_ids_dict['dmm_i'] = eq.get_res_id_dict_and_disconnect(dmm_i)
                
                #Add other devices? - temperaure sensors or mid-level voltage monitors?
                msg = "Do you want to add any other dmms for measurement on channel {}?".format(ch_num)
                title = "CH {} Measurement Device".format(ch_num)
                add_other_device = True
                device_v_counter = 0
                device_i_counter = 0
                device_t_counter = 0
                while add_other_device:
                    add_other_device = eg.ynbox(msg, title)
                    if add_other_device:
                        choice = eg.choicebox("What will this device measure?","Adding Measurement Device",['Voltage', 'Current', 'Temperature'])
                        dev_name = 'dmm'
                        if choice == 'Voltage':
                            dev_name = 'dmm_v{}'.format(device_v_counter)
                            device_v_counter = device_v_counter + 1
                        elif choice == 'Current':
                            dev_name = 'dmm_i{}'.format(device_i_counter)
                            device_i_counter = device_i_counter + 1
                        elif choice == 'Temperature':
                            dev_name = 'dmm_t{}'.format(device_t_counter)
                            device_t_counter = device_t_counter + 1
                        
                        dmm_extra = eq.dmms.choose_dmm(multi_ch_event_and_queue_dict = dict_for_event_and_queue)
                        res_ids_dict[dev_name] = eq.get_res_id_dict_and_disconnect(dmm_extra)
                
                #Add power flow control? - such as relay board to disconnect equipment.
                msg = "Do you want to add a relay board for channel {}?".format(ch_num)
                title = "CH {} Power Control Device".format(ch_num)
                if eg.ynbox(msg, title):
                    relay_board = eq.otherEquipment.choose_equipment()
                    res_ids_dict['relay_board'] = eq.get_res_id_dict_and_disconnect(relay_board)
                
                
            dict_for_queue = {'ch_num': ch_num, 'res_ids_dict': res_ids_dict}
            assignment_queue.put_nowait(dict_for_queue)
            
        except:
            print("Something went wrong with assigning equipment. Please try again.")
            traceback.print_exc()
            return
    
    def export_equipment_assignment(self):
        jsonIO.export_cycle_settings(self.res_ids_dict_list)
        
    def import_equipment_assignment(self):		
        temp_dict_list = jsonIO.import_cycle_settings()
        temp_dict_list = jsonIO.convert_keys_to_int(temp_dict_list)
        
        self.setup_channels(len(list(temp_dict_list.keys())))
        
        for ch_num in range(self.num_battery_channels):
            if temp_dict_list[ch_num] != None:
                self.assign_equipment(ch_num, self.eq_assignment_queue, res_ids_dict = temp_dict_list[ch_num], dict_for_event_and_queue = self.dict_for_event_and_queue)
        
    def export_test_configuration_process(self, ch_num):	
        if self.export_test_process_list[ch_num] is not None and self.export_test_process_list[ch_num].is_alive():
            print("CH{} - There is an export already running".format(ch_num))
            return
        try:
            self.export_test_process_list[ch_num] = Process(target=jsonIO.export_cycle_settings, args = (self.cdc_input_dict_list[ch_num],))
            self.export_test_process_list[ch_num].start()
        except:
            traceback.print_exc()
        
    def import_test_configuration_process(self, ch_num):
        if self.import_test_process_list[ch_num] is not None and self.import_test_process_list[ch_num].is_alive():
                print("CH{} - There is an import already running".format(ch_num))
                return
        try:
            self.import_test_process_list[ch_num] = Process(target=jsonIO.import_cycle_settings, args = ("", self.test_configuration_queue, ch_num))
            self.import_test_process_list[ch_num].start()
        except:
            traceback.print_exc()
            
    
    def edit_cell_name(self, ch_num):
        self.edit_cell_name_process(ch_num = ch_num)
    
    def edit_cell_name_process(self, ch_num):
        if self.edit_cell_name_process_list[ch_num] is not None and self.edit_cell_name_process_list[ch_num].is_alive():
                print("CH{} - There is a cell name edit already running".format(ch_num))
                return
        try:
            self.edit_cell_name_process_list[ch_num] = Process(target=cdc.get_cell_name, args = (ch_num, self.edit_cell_name_queue, self.cell_name_label_list[ch_num].text()))
            self.edit_cell_name_process_list[ch_num].start()
        except:
            traceback.print_exc()
    
    def configure_test(self, ch_num):
        self.configure_test_process(ch_num = ch_num)
    
    def configure_test_process(self, ch_num):
        if self.configure_test_process_list[ch_num] is not None and self.configure_test_process_list[ch_num].is_alive():
                print("CH{} - There is a configuration already running".format(ch_num))
                return
        try:
            self.configure_test_process_list[ch_num] = Process(target=cdc.get_input_dict, args = (ch_num, self.test_configuration_queue, self.cell_name_label_list[ch_num].text()))
            self.configure_test_process_list[ch_num].start()
        except:
            traceback.print_exc()
    
    
    def start_test(self, ch_num):
        if self.res_ids_dict_list[ch_num] == None:
            print("CH{} - Please Assign Equipment before starting a test!".format(ch_num))
            return
        if self.cdc_input_dict_list[ch_num] == None:
            print("CH{} - Please Configure Test before starting a test!".format(ch_num))
            return
        self.batt_test_process(self.res_ids_dict_list[ch_num], data_out_queue = self.data_from_ch_queue_list[ch_num],
                                data_in_queue = self.data_to_ch_queue_list[ch_num], cdc_input_dict = self.cdc_input_dict_list[ch_num], ch_num = ch_num)
    
    def batt_test_process(self, res_ids_dict, data_out_queue = None, data_in_queue = None, cdc_input_dict = None, ch_num = None):
        try:
            if self.mp_process_list[ch_num] is not None and self.mp_process_list[ch_num].is_alive():
                print("CH{} - There is a battery test process already running".format(ch_num))
                return
            if self.mp_idle_process_list[ch_num] is not None and self.mp_idle_process_list[ch_num].is_alive():
                self.stop_idle_process(ch_num)
                
            self.mp_process_list[ch_num] = Process(target=cdc.charge_discharge_control, 
                                                    args = (res_ids_dict, data_out_queue, data_in_queue, cdc_input_dict, 
                                                    self.dict_for_event_and_queue, ch_num))
            self.mp_process_list[ch_num].start()
        except:
            traceback.print_exc()
    
    def start_idle_process(self, ch_num):
        self.idle_process(self.res_ids_dict_list[ch_num], data_out_queue = self.data_from_ch_queue_list[ch_num],
                                data_in_queue = self.data_to_idle_ch_queue_list[ch_num], ch_num = ch_num)
    
    def idle_process(self, res_ids_dict, data_out_queue = None, data_in_queue = None, ch_num = None):
        if res_ids_dict == None:
            #no equipment assigned, don't start the test
            return
        try:
            self.mp_idle_process_list[ch_num] = Process(target=cdc.idle_control, args = (res_ids_dict, data_out_queue, data_in_queue, self.dict_for_event_and_queue))
            self.mp_idle_process_list[ch_num].start()
        except:
            traceback.print_exc()
    
    def stop_idle_process(self, ch_num):
        self.stop_process(self.mp_idle_process_list[ch_num], self.data_to_idle_ch_queue_list[ch_num])
        self.mp_idle_process_list[ch_num] = None
        
    def stop_test(self, ch_num):
        self.stop_process(self.mp_process_list[ch_num], self.data_to_ch_queue_list[ch_num])
        self.mp_process_list[ch_num] = None
    
    def stop_process(self, process_id, queue_id = None):
        if process_id != None:
            try:
                #only put stop command if the process exists and is running
                if process_id.is_alive():
                    if queue_id != None:
                        queue_id.put_nowait('stop')
                    process_id.join()
                    process_id.close()
            except ValueError:
                pass
    
    def clean_up(self):
        #close all threads - run this function just before the app closes
        print("Exiting - Cleaning Up Processes")
        for ch_num in range(self.num_battery_channels):
            self.stop_process(self.assign_eq_process_list[ch_num])
            self.stop_process(self.configure_test_process_list[ch_num])
            self.stop_process(self.edit_cell_name_process_list[ch_num])
            self.stop_test(ch_num)
            self.stop_idle_process(ch_num)
        if self.multi_ch_device_process is not None and self.multi_ch_management_queue is not None:
            self.stop_process(self.multi_ch_device_process, self.multi_ch_management_queue)
            
    

def main():
    app = QApplication([])
    test_window = MainTestWindow()
    test_window.show()
    app.aboutToQuit.connect(test_window.clean_up)
    app.exec()
    
if __name__ == '__main__':
    main()
