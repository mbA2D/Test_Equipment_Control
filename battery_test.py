#Program to run the charge discharge control in different processes for each channel.

#Actions and menus from this tutorial: https://realpython.com/python-menus-toolbars/

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QGridLayout, QMenuBar
from PyQt6.QtGui import QAction
from PyQt6 import QtCore
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
from multiprocessing import Process, Queue, Event
from functools import partial
import queue #queue module required for exception handling of multiprocessing.Queue
import traceback

#from BATT_HIL import fet_board_management as fbm
from lab_equipment import A2D_DAQ_control
from lab_equipment import DMM_A2D_4CH_Isolated_ADC
from lab_equipment import Eload_A2D_Eload
import charge_discharge_control as cdc
import equipment as eq
import easygui as eg
import jsonIO
import time
import json

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
        self.restart_idle_processes = True
        
        self.resources_list = None
        self.connect_equipment_process = None
        self.disconnect_equipment_process = None
        self.connected_equipment_list = list()
        self.connected_equipment_process_list = list()
    
        self.eq_assignment_queue = Queue()
        self.resources_list_queue = Queue()
        self.new_equipment_queue = Queue()
        self.test_configuration_queue = Queue()
        self.edit_cell_name_queue = Queue()
        
        self.setWindowTitle("Battery Tester App")
        self.central_layout = QVBoxLayout()
        
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
        self.update_resources_process = None
        self.import_eq_assignment_process = None
        self.export_eq_assignment_process = None
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
        self.status_label_list = {}
        self.safety_label_list = {}
        self.button_clear_safety_list = {}
        
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
        
        self.create_actions()
        self.connect_actions()
        self.create_menu_bar()
        
        self.setup_channels()
        
    def create_actions(self):
        #self.connect_multi_ch_eq_action = QAction("Connect Multi-Channel Equipment", self)
        self.import_equipment_assignment_action = QAction("Import Equipment Assignment", self)
        self.export_equipment_assignment_action = QAction("Export Equipment Assignment", self)
        self.scan_equipment_resources_action = QAction("Scan Resources", self)
        self.connect_new_equipment_action = QAction("Connect New Equipment", self)
        self.add_channel_action = QAction("Add Channel", self)
    
    def connect_actions(self):
        #self.connect_multi_ch_eq_action.triggered.connect(self.multi_ch_devices_process)
        self.import_equipment_assignment_action.triggered.connect(self.import_equipment_assignment)
        self.export_equipment_assignment_action.triggered.connect(self.export_equipment_assignment)
        self.scan_equipment_resources_action.triggered.connect(self.scan_resources)
        self.connect_new_equipment_action.triggered.connect(self.connect_new_equipment)
        self.add_channel_action.triggered.connect(self.add_channel)
    
    def create_menu_bar(self):
        menu_bar = QMenuBar(self)
        
        file_menu = menu_bar.addMenu("File")
        #file_menu.addAction(self.connect_multi_ch_eq_action)
        file_menu.addAction(self.import_equipment_assignment_action)
        file_menu.addAction(self.export_equipment_assignment_action)
        file_menu.addAction(self.scan_equipment_resources_action)
        file_menu.addAction(self.connect_new_equipment_action)
        file_menu.addAction(self.add_channel_action)
        
        self.setMenuBar(menu_bar)
        
    
    #Scan new equipment in a process so that we don't block the main window
    def scan_resources(self):
        try:
            if self.update_resources_process is not None and self.update_resources_process.is_alive():
                print("There is a process already running to update resources list")
                return
            self.update_resources_process = Process(target=self.update_resources_list_process, args = (self.resources_list_queue,))
            self.update_resources_process.start()
        except:
            traceback.print_exc()
    
    @staticmethod
    def update_resources_list_process(resources_list_queue = None, return_list = False):
        resources_list = eq.get_resources_list()
        if resources_list_queue != None:
            resources_list_queue.put_nowait(resources_list)
        if return_list:
            return resources_list
    
    def connect_new_equipment(self):
        try:
            if self.connect_equipment_process is not None and self.connect_equipment_process.is_alive():
                print("There is a process already running to connect new equipment")
                return
            if self.resources_list == None or len(self.resources_list) == 0:
                print("There are no resources to connect to. Only Fake Test equipment will be available.")
            self.connect_equipment_process = Process(target=self.connect_new_equipment_process, args = (self.resources_list, self.new_equipment_queue))
            self.connect_equipment_process.start()
        except:
            traceback.print_exc()
    
    @staticmethod
    def connect_new_equipment_process(resources_list, new_equipment_queue):
        #We do have at least 1 resource to connect to. 
        #For multi-channel devices, we want to connect to the EQUIPMENT, not the CHANNEL.
        
        #What type of equipment are you connecting to?
        equipment_selection_functions = { 
            'psu':      eq.powerSupplies.choose_psu, 
            'eload':    eq.eLoads.choose_eload,
            'smu':      eq.smus.choose_smu,
            'dmm':      eq.dmms.choose_dmm,
            'other':    eq.otherEquipment.choose_equipment
        }
        
        msg = "Select Equipment Type"
        title = "Equipment Selection"
        equipment_selected = eg.choicebox(msg = msg, title = title, choices = equipment_selection_functions.keys())
        if equipment_selected == None:
            return
        
        #TODO - Make sure we don't try to connect to the same equipment twice!
        
        #What model of equipment?
        equipment_list = equipment_selection_functions[equipment_selected](resources_list = resources_list)
        
        #Then get res id and disconnect
        eq_res_id_dict = eq.get_res_id_dict_and_disconnect(equipment_list)
        
        #And put the res id to a queue
        #In update_loop, the queue is read and we create the equipment communication queues for virtual instrument
        new_equipment_queue.put_nowait(eq_res_id_dict)
        
    
    def clear_layout(self, layout):
        #https://stackoverflow.com/questions/4528347/clear-all-widgets-in-a-layout-in-pyqt
        if layout is not None:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget() is not None:
                    child.widget().deleteLater()
                elif child.layout() is not None:
                    self.clear_layout(child.layout())
    
    def remove_all_channels(self):
        self.clear_layout(self.channels_layout)
        
        for ch_num in range(self.num_battery_channels):
            self.stop_process(self.assign_eq_process_list[ch_num])
            self.stop_process(self.mp_process_list[ch_num])
            self.stop_process(self.mp_idle_process_list[ch_num])
    
    
    def setup_channels(self, num_ch = None):
        self.remove_all_channels()
        
        if num_ch == None:
            num_ch = eg.enterbox(msg = "How many battery channels?", title = "Battery Channels", default = "1")
            if num_ch == None:
                num_ch = 0
            num_ch = int(num_ch)
        self.num_battery_channels = num_ch
        
        for ch_num in range(self.num_battery_channels):
            self.setup_single_channel(ch_num)
    
    
    def setup_single_channel(self, ch_num):
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
        self.status_label_list[ch_num] = QLabel("Current Status: Idle\nNext Status: N/A")
        self.safety_label_list[ch_num] = QLabel("Safety: OK")
        self.button_clear_safety_list[ch_num] = QPushButton("Clear Safety Error")
        
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
        self.ch_graph_widget[ch_num].setMouseEnabled(False, False)
        
        #setting up buttons
        self.button_edit_cell_name_list[ch_num].setCheckable(False)
        self.button_edit_cell_name_list[ch_num].clicked.connect(partial(self.edit_cell_name, ch_num))
        
        self.button_clear_safety_list[ch_num].setCheckable(False)
        self.button_clear_safety_list[ch_num].clicked.connect(partial(self.clear_safety_error, ch_num))
        
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
        left_col_layout.addWidget(self.status_label_list[ch_num])
        left_col_layout.addWidget(self.safety_label_list[ch_num])
        left_col_layout.addWidget(self.button_clear_safety_list[ch_num])
        
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
    
    
    def add_channel(self):
        self.setup_single_channel(self.num_battery_channels)
        self.num_battery_channels = self.num_battery_channels + 1
        
        
    def update_loop(self):
        update_interval_s = 0.25
        
        #Check the equipment assignment queue
        try:
            #if we have a multi channel device, we want to connect to the CHANNEL
            new_eq_assignment = self.eq_assignment_queue.get_nowait()
            
            for key in new_eq_assignment['res_ids_dict']:
                if new_eq_assignment['res_ids_dict'][key] != None:
                    local_id = new_eq_assignment['res_ids_dict'][key]['res_id'].get('local_id')
                    if local_id != None:
                        queue_in, queue_out = self.get_connected_equipment_queues_matching_local_id(local_id)
                        new_eq_assignment['res_ids_dict'][key]['res_id'].update({'queue_in': queue_in, 'queue_out': queue_out})
            
            self.res_ids_dict_list[int(new_eq_assignment['ch_num'])] = new_eq_assignment['res_ids_dict']
            
            #stop the idle test to re-start with new equipment
            self.stop_idle_process(int(new_eq_assignment['ch_num']))
            print("CH{} - Assigned New Equipment".format(new_eq_assignment['ch_num']))
        except queue.Empty:
            pass #No new data was available
        
        #Check the resources list queue
        try:
            self.resources_list = self.resources_list_queue.get_nowait()
            print("Equipment Resources Updated: {}".format(self.resources_list))
        except queue.Empty:
            pass #No new data was available
        
        #Check the new equipment queue
        try:
            #for multi-channel devices, connects to the EQUIPMENT, not to the CHANNEL
            new_eq_res_id_dict = self.new_equipment_queue.get_nowait()
            
            self.create_new_equipment(new_eq_res_id_dict)
            
            print("New Equipment Connected")
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
            status_label_text = self.status_label_list[ch_num].text()
            split_status_label_text = status_label_text.split(' ')
            split_status_label_text[-1] = new_test_configuration['cdc_input_dict']['settings_cycle_list_step_list'][0][0]['cycle_display']
            status_label_text = ' '.join(split_status_label_text)
            self.status_label_list[ch_num].setText(status_label_text)
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
                if self.restart_idle_processes:    
                    if self.res_ids_dict_list[ch_num] != None:
                        if  (self.mp_process_list[ch_num] == None or 
                            (self.mp_process_list[ch_num] != None and not self.mp_process_list[ch_num].is_alive())) and \
                            (self.mp_idle_process_list[ch_num] == None or
                            (self.mp_idle_process_list[ch_num] != None and not self.mp_idle_process_list[ch_num].is_alive())):
                                #Set the current status to idle and next status to 'N/A' or the next cycle
                                current_status = "Idle"
                                try:
                                    next_status = self.cdc_input_dict_list[ch_num]['settings_cycle_list_step_list'][0][0]['cycle_display']
                                except (KeyError, TypeError):
                                    next_status = "N/A"
                                self.status_label_list[ch_num].setText('Current Status: {}\nNext Status: {}'.format(current_status, next_status))
                                
                                #start an idle process since nothing else is running
                                #print("CH{} - Starting Idle Process".format(ch_num))
                                self.start_idle_process(ch_num)
                
                #Read from all queues if available
                data_from_ch = self.data_from_ch_queue_list[ch_num].get_nowait()
                if data_from_ch['type'] == 'status':
                    self.status_label_list[ch_num].setText("Current Status: {}\nNext Status: {}".format(data_from_ch['data'][0], data_from_ch['data'][1]))
                elif data_from_ch['type'] == 'measurement':
                    self.data_dict_list[ch_num] = data_from_ch['data']
                elif data_from_ch['type'] == 'end_condition':
                    if data_from_ch['data'] == 'safety_condition':
                        self.safety_label_list[ch_num].setText('Safety: ERROR')
                        
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
    
    def create_new_equipment(self, eq_res_id_dict):
        #print(eq_res_id_dict)
    
        if eq_res_id_dict.get('local_id') is not None:
            eq_local_id = eq_res_id_dict.get('local_id')
        else:
            eq_local_id = len(self.connected_equipment_list)
        eq_idn = eq_res_id_dict['eq_idn']
        eq_type = eq_res_id_dict['eq_type']
        eq_res_id = eq_res_id_dict['res_id']
        
        #Create a queue to put data in and get data out
        queue_in = Queue()
        queue_out = Queue()
        #Create a process for this new piece of equipment and connect to it in that process
        eq_process = Process(target = eq.virtual_device_management_process, args = (eq_type, eq_res_id_dict, queue_in, queue_out))
        eq_process.start()
        
        #virtual_device_management does the following:
            # - connect to the equipment using the equipment type and the res_id_dict
            # - Then loop:
                # - listen for any messages in queue_in
                    # - take action on messages in queue_in
                # - put responses to messages in queue_out
        
        #TODO: When we assign a piece of equipment to a channel, then:
            # - Choose the equipment out of the list of connected devices
                # - Go through the usual process of selecting equipment of each type
                # - But only show the equipment of the appropriate type that we already connected to
            # - For the instrument selected:
                # - Get res id dict for a new virtual instrument with queue_in and queue_out of the correct type (dmm, psu, etc)
                # - pass that instrument res id (indexed by local_id primarily) to the channel that we are looking to connect to
                # - Change already assigned to True (assuming equipment can only be used by 1 channel for now)
        
        
        #Create a dict with a new process, 2 queues, and maybe some identifying info about the equipment
        equipment_dict = {
            'local_id':             eq_local_id,
            'res_id':               eq_res_id,
            'eq_type':              eq_type,
            'eq_idn':               eq_idn,
            'class_name':           eq_res_id_dict['class_name'],
            'setup_dict':           eq_res_id_dict['setup_dict'],
            'queue_in':             queue_in,
            'queue_out':            queue_out,
            'already_assigned':     False
        }
        equipment_process_dict = {
            'local_id':             eq_local_id,
            'process':              eq_process
        }
        
        
        #Then add that dict to connected_equipment_list
        self.connected_equipment_list.append(equipment_dict)
        self.connected_equipment_process_list.append(equipment_process_dict)
        
    
    def get_connected_equipment_queues_matching_local_id(self, local_id):
        for connected_equipment_dict in self.connected_equipment_list:
            if connected_equipment_dict['local_id'] == local_id:
                return connected_equipment_dict['queue_in'], connected_equipment_dict['queue_out']
        return None, None
    
    #Assigning equipment in a queue so that we don't block the main window
    def assign_equipment_process(self, ch_num):
        try:
            if self.assign_eq_process_list[ch_num] is not None and self.assign_eq_process_list[ch_num].is_alive():
                print("CH{} - There is a process already running to assign equipment".format(ch_num))
                return
                
            self.assign_eq_process_list[ch_num] = Process(target=self.assign_equipment, args = (ch_num, self.eq_assignment_queue, None, self.connected_equipment_list))
            self.assign_eq_process_list[ch_num].start()
        except:
            traceback.print_exc()
    
    @staticmethod
    def select_idn_matching_type(connected_equipment_list, eq_type):
        #connected_equipment_list contains the equipment dict with 'res_id', 'local_id', 'class_name', etc. created in create_new_equipment
        
        eq_type_match = list()
        if 'dmm' in eq_type or eq_type == 'eload' or eq_type == 'psu':
            eq_type_match.append('smu')
        eq_type_match.append(eq_type)
        
        eq_idn_list = [connected_equipment['eq_idn'] for connected_equipment in connected_equipment_list if connected_equipment['eq_type'] in eq_type_match]
        
        eq_idn = None
        if len(eq_idn_list) == 0:
            print("No equipment connected matching type: {}".format(eq_type))
            return None
        elif len(eq_idn_list) == 1:
            msg = "There is only 1 {} available.\nWould you like to use it?\n{}".format(eq_type, eq_idn_list[0])
            if(eg.ynbox(msg, title="Equipment Selection: {}".format(eq_type))):
                eq_idn = eq_idn_list[0]
        else:
            eq_idn = eg.choicebox(msg = f'Select equipment idn for {eq_type}', title = f'{eq_type} Selection', choices = eq_idn_list)
            
        return eq_idn
    
    @staticmethod
    def get_connected_equipment_local_id_matching_idn(connected_equipment_list, eq_idn):
        for connected_equipment_dict in connected_equipment_list:
            if connected_equipment_dict['eq_idn'] == eq_idn:
                return connected_equipment_dict['local_id']
        return None
    
    
    @staticmethod
    def get_connected_equipment_index_matching_idn(connected_equipment_list, eq_idn):
        #returns the index in the connected_equipment_list
        for index, connected_equipment_dict in enumerate(connected_equipment_list):
            if connected_equipment_dict['eq_idn'] == eq_idn:
                return index
        return None
    
    @staticmethod
    def assign_equipment(ch_num, assignment_queue, res_ids_dict = None, connected_equipment_list = None):
        try:
            if res_ids_dict == None:
                res_ids_dict = {'psu': None, 'eload': None, 'dmm_v': None, 'dmm_i': None}
                idns_dict = {'psu': None, 'eload': None, 'dmm_v': None, 'dmm_i': None}
            
                #choose a psu and eload for each channel
                msg = "Do you want to connect a power supply for channel {}?".format(ch_num)
                title = "CH {} Power Supply Connection".format(ch_num)
                if eg.ynbox(msg, title):
                    psu_idn = MainTestWindow.select_idn_matching_type(connected_equipment_list, 'psu')
                    idns_dict['psu'] = psu_idn
                
                msg = "Do you want to connect an eload for channel {}?".format(ch_num)
                title = "CH {} Eload Connection".format(ch_num)
                if eg.ynbox(msg, title):
                    eload_idn = MainTestWindow.select_idn_matching_type(connected_equipment_list, 'eload')
                    idns_dict['eload'] = eload_idn
                    
                #Separate measurement devices - total voltage and current
                msg = "Do you want to use a separate device to measure voltage on channel {}?".format(ch_num)
                title = "CH {} Voltage Measurement Device".format(ch_num)
                if eg.ynbox(msg, title):
                    dmm_v_idn = MainTestWindow.select_idn_matching_type(connected_equipment_list, 'dmm')
                    
                    #if this device has multiple channels, we need to choose which channel to use
                    connected_equipment_list_index = MainTestWindow.get_connected_equipment_index_matching_idn(connected_equipment_list, dmm_v_idn)
                    ch = None
                    if connected_equipment_list[connected_equipment_list_index]['class_name'] == 'A2D_DAQ_CH':
                        ch = eq.choose_channel(num_channels = A2D_DAQ_control.A2D_DAQ.num_channels, start_val = 0)
                    elif connected_equipment_list[connected_equipment_list_index]['class_name'] == 'A2D_4CH_Isolated_ADC_Channel':
                        ch = eq.choose_channel(num_channels = DMM_A2D_4CH_Isolated_ADC.A2D_4CH_Isolated_ADC.num_channels, start_val = 1)
                    elif connected_equipment_list[connected_equipment_list_index]['class_name'] == 'A2D_Eload':
                        ch = eq.choose_channel(num_channels = Eload_A2D_Eload.A2D_Eload.max_channels, start_val = 1)
                    idns_dict['dmm_v'] = {'idn': dmm_v_idn, 'ch': ch}

                    
                msg = "Do you want to use a separate device to measure current on channel {}?".format(ch_num)
                title = "CH {} Current Measurement Device".format(ch_num)
                if eg.ynbox(msg, title):
                    dmm_i_idn = MainTestWindow.select_idn_matching_type(connected_equipment_list, 'dmm')
                    idns_dict['dmm_i'] = dmm_i_idn
                
                #Add other devices? - temperaure sensors or mid-level voltage monitors?
                msg = "Do you want to add any other dmms for measurement on channel {}?".format(ch_num)
                title = "CH {} Measurement Device".format(ch_num)
                add_other_device = True
                device_v_counter = 0
                device_i_counter = 0
                device_t_counter = 0
                custom_measurement_names = list()
                while add_other_device:
                    add_other_device = eg.ynbox(msg, title)
                    if add_other_device:
                        choice = eg.choicebox("What will this device measure?","Adding Measurement Device",['Voltage', 'Current', 'Temperature', 'Other'])
                        dev_name = 'dmm'
                        valid_dev = False
                        if choice == 'Voltage':
                            dev_name = 'dmm_v_{}'.format(device_v_counter)
                            device_v_counter = device_v_counter + 1
                            valid_dev = True
                        elif choice == 'Current':
                            dev_name = 'dmm_i_{}'.format(device_i_counter)
                            device_i_counter = device_i_counter + 1
                            valid_dev = True
                        elif choice == 'Temperature':
                            dev_name = 'dmm_t_{}'.format(device_t_counter)
                            device_t_counter = device_t_counter + 1
                            valid_dev = True
                        elif choice == 'Other':
                            #This category used for measuring various other things (e.g. SoC from bq fuel gauge)
                            #The measurement function of this device must be named the same as this should return a float
                            #
                            #e.g. if 'soc_0' is entered here, then we will try to use a measurement function called 'measure_soc()' and we will call the device 'dmm_soc_0' 
                            #        'soc_test_0'                                                                   'measure_soc_test()'                        'dmm_soc_test_0'
                            #        'soc'                                                                          'measure_soc()'                             'dmm_soc'
                            #
                            custom_measurement_name = eg.enterbox(msg = "Enter the measurement name.\n\n" + 
                                                                        "1. Must be unique within each channel.\n"
                                                                        "2. Use '_identifier' at the end of name if 2 measurements of the same type are required on the same channel\n" + 
                                                                        "3. Device must have measurement function called 'measure_measurement-name-without-identifier()' that returns a float.\n" + 
                                                                        "4. Spaces will be replaced with underscores.",
                                                                  title = "Custom Measurement Setup",
                                                                  default = "soc")
                            if (custom_measurement_name is not None) and (str(custom_measurement_name) not in custom_measurement_names):
                                valid_dev = True
                                custom_measurement_name = custom_measurement_name.replace(' ','_')
                                custom_measurement_names.append(custom_measurement_name)
                                dev_name = 'dmm_{}'.format(str(custom_measurement_name))
                            
                        
                        if valid_dev:
                            #dmm_extra = eq.dmms.choose_dmm(multi_ch_event_and_queue_dict = dict_for_event_and_queue, resources_list = resources_list)
                            #res_ids_dict[dev_name] = eq.get_res_id_dict_and_disconnect(dmm_extra)
                            dmm_extra_idn = MainTestWindow.select_idn_matching_type(connected_equipment_list, 'dmm')
                            
                            #if this is a A2D_64_CH_DAQ, we need to choose which channel to use
                            connected_equipment_list_index = MainTestWindow.get_connected_equipment_index_matching_idn(connected_equipment_list, dmm_extra_idn)
                            ch = None
                            if connected_equipment_list[connected_equipment_list_index]['class_name'] == 'A2D_DAQ_CH':
                                ch = eq.choose_channel(num_channels = A2D_DAQ_control.A2D_DAQ.num_channels)
                            elif connected_equipment_list[connected_equipment_list_index]['class_name'] == 'A2D_4CH_Isolated_ADC_Channel':
                                ch = eq.choose_channel(num_channels = DMM_A2D_4CH_Isolated_ADC.A2D_4CH_Isolated_ADC.num_channels, start_val = 1)
                            
                            idns_dict[dev_name] = {'idn': dmm_extra_idn, 'ch': ch}
                        
                #Add power flow control? - such as relay board to disconnect equipment.
                msg = "Do you want to add a relay board for channel {}?".format(ch_num)
                title = "CH {} Power Control Device".format(ch_num)
                if eg.ynbox(msg, title):
                    #relay_board = eq.otherEquipment.choose_equipment(resources_list = resources_list)
                    #res_ids_dict['relay_board'] = eq.get_res_id_dict_and_disconnect(relay_board)
                    relay_board_idn = MainTestWindow.select_idn_matching_type(connected_equipment_list, 'other')
                    idns_dict['relay_board'] = relay_board_idn
                    
                for key in idns_dict.keys():
                    if idns_dict[key] is not None:
                        res_ids_dict[key] = {}
                        
                        eq_ch = None
                        if type(idns_dict[key]) is dict:
                            eq_idn = idns_dict[key]['idn']
                            eq_ch = idns_dict[key]['ch']
                        else:
                            eq_idn = idns_dict[key]
                        local_id = MainTestWindow.get_connected_equipment_local_id_matching_idn(connected_equipment_list, eq_idn)
                            
                        res_ids_dict[key]['res_id'] = {'queue_in': None, 'queue_out': None, 'local_id': local_id, 'eq_ch': eq_ch}
                        
                
                #if all values are None, print No equipment assigned and return.
                if not any(idns_dict.values()):
                    print("CH{} - No Equipment Assigned".format(ch_num))
                    return
            
            dict_for_queue = {'ch_num': ch_num, 'res_ids_dict': res_ids_dict}
            assignment_queue.put_nowait(dict_for_queue)
            #print("Put on Assignment Queue: {}".format(dict_for_queue))
            
        except:
            print("Something went wrong with assigning equipment. Please try again.")
            traceback.print_exc()
            return
    
    def export_equipment_assignment(self):
        if self.export_eq_assignment_process is not None and self.export_eq_assignment_process.is_alive():
            print("There is an export equipment process already running")
            return
        try:
            self.export_eq_assignment_process = Process(target=self.export_equipment_assignment_process, args = (self.connected_equipment_list, self.res_ids_dict_list))
            self.export_eq_assignment_process.start()
        except:
            traceback.print_exc()
    
    @staticmethod
    def export_equipment_assignment_process(connected_equipment_list, res_ids_dict_list):
        #Remove the queue_in and _out values from the dicts since they can't exist in json format
        connected_equipment_dict_for_export = {}
        for equipment_dict in connected_equipment_list:
            equipment_dict_for_export = {key: val for key, val in equipment_dict.items() if 'queue' not in key}
            connected_equipment_dict_for_export[equipment_dict_for_export['local_id']] = equipment_dict_for_export
        
        #for each channel, get the res_ids_dict, and remove the values from the queue entries
        res_ids_dict_for_export = {}
        for ch_num in res_ids_dict_list:
            res_ids_dict_for_export[ch_num] = {}
            for eq_type in res_ids_dict_list[ch_num]:
                res_ids_dict_for_export[ch_num][eq_type] = None
                if res_ids_dict_list[ch_num][eq_type] is not None:
                    res_ids_dict_for_export[ch_num][eq_type] = {}
                    res_ids_dict_for_export[ch_num][eq_type]['res_id'] = {key: val for key, val in res_ids_dict_list[ch_num][eq_type]['res_id'].items() if 'queue' not in key}
        
        #Then export these 2 lists to the same file - append
        dict_for_export = {'connected_equipment_dict': connected_equipment_dict_for_export, 'res_ids_dict': res_ids_dict_for_export}
        jsonIO.export_cycle_settings(dict_for_export)
        
    
    #Doesn't have to be a separate process since we shouldn't be running tests while importing equipment anyways
    #So we don't care if MainTestWindow hangs during this process.
    def import_equipment_assignment(self):		
        
        #Don't let the user import equipment assignment while a test is running.
        for ch_num in range(self.num_battery_channels):
            status_label_text = self.status_label_list[ch_num].text()
            current_status = status_label_text.split()[2] #not a great way to do this - should have variables storing current and next status.
            if current_status != "Idle":
                print("Stop tests on all channels before importing equipment assignment.")
                return
        
        self.restart_idle_processes = False
        for ch_num in range(self.num_battery_channels):
            self.stop_idle_process(ch_num)
        
        ########## NEW #############
        #read the dicts from the single file
        import_json = jsonIO.import_cycle_settings()
        equipment_to_connect_dict = jsonIO.convert_keys_to_int(import_json['connected_equipment_dict'])
        res_ids_dict_list = jsonIO.convert_keys_to_int(import_json['res_ids_dict'])
        
        #scan equipment to build the list of possible connections
        self.resources_list = self.update_resources_list_process(return_list = True)

        #remove and disconnect from all currently connected equipment
        self.disconnect_all_equipment()
        
        #create the equipment (rebuilding the queues) - in the correct order for local ids
        for local_id in equipment_to_connect_dict:
            self.create_new_equipment(equipment_to_connect_dict[local_id])
 
        #set the same number of channels as there are in the file.
        self.setup_channels(len(list(res_ids_dict_list.keys())))
        
        for ch_num in range(self.num_battery_channels):
            if res_ids_dict_list[ch_num] != None:
                MainTestWindow.assign_equipment(ch_num, self.eq_assignment_queue, res_ids_dict = res_ids_dict_list[ch_num], connected_equipment_list = self.connected_equipment_list)
        
        self.restart_idle_processes = True
        
        #What if the required equipment could not be found?? - connect everything else? (TODO)
            
    def disconnect_all_equipment(self):
        
        #Stop the processes used to communicate with equipment
        for index in range(len(self.connected_equipment_process_list)):
            #get the queue in from connected_equipment_list
            queue_in = self.connected_equipment_list[index]['queue_in']
            #get the process from the connected_equipment_process_list
            process_id = self.connected_equipment_process_list[index]['process']
            
            self.stop_process(process_id, queue_in)
            
        #These are the 2 lists that we need to empty and reset to default
        self.connected_equipment_list =list()
        self.connected_equipment_process_list = list()
        
    
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
        
    def clear_safety_error(self, ch_num):
        self.safety_label_list[ch_num].setText('Safety: OK')
    
    def edit_cell_name_process(self, ch_num):
        if self.edit_cell_name_process_list[ch_num] is not None and self.edit_cell_name_process_list[ch_num].is_alive():
            print("CH{} - There is a cell name edit already running".format(ch_num))
            return
        try:
            self.edit_cell_name_process_list[ch_num] = Process(target=cdc.run_get_cell_name, args = (ch_num, self.edit_cell_name_queue, self.cell_name_label_list[ch_num].text()))
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
            self.configure_test_process_list[ch_num] = Process(target=cdc.run_get_input_dict, args = (ch_num, self.test_configuration_queue, self.cell_name_label_list[ch_num].text()))
            self.configure_test_process_list[ch_num].start()
        except:
            traceback.print_exc()
    
    
    def start_test(self, ch_num):
        if self.safety_label_list[ch_num].text() != 'Safety: OK':
            print("CH{} - Please Check and Clear the Safety Error before starting a test!".format(ch_num))
            return
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
            
            self._clear_queue(data_out_queue)
            self._clear_queue(data_in_queue)
            #print("Done Clearing Queues")
            self.mp_process_list[ch_num] = Process(target=cdc.run_charge_discharge_control, 
                                                    args = (res_ids_dict, data_out_queue, data_in_queue, cdc_input_dict, ch_num))
            self.mp_process_list[ch_num].start()
        except:
            traceback.print_exc()
    
    def start_idle_process(self, ch_num):
        self.idle_process(self.res_ids_dict_list[ch_num], data_out_queue = self.data_from_ch_queue_list[ch_num],
                                data_in_queue = self.data_to_idle_ch_queue_list[ch_num], ch_num = ch_num)
    
    def idle_process(self, res_ids_dict, data_out_queue = None, data_in_queue = None, ch_num = None):
        if res_ids_dict == None or (res_ids_dict['psu'] == None and res_ids_dict['eload'] == None and res_ids_dict['dmm_v'] == None):
            #no equipment assigned or no voltage measurement equipment, don't start the idle measurements
            return
        try:
            self._clear_queue(data_out_queue)
            self._clear_queue(data_in_queue)
            #print("CH{} - Idle Process res_ids_dict: {}".format(ch_num, res_ids_dict))
            self.mp_idle_process_list[ch_num] = Process(target=cdc.run_idle_control, args = (res_ids_dict, data_out_queue, data_in_queue))
            self.mp_idle_process_list[ch_num].start()
        except:
            traceback.print_exc()
    
    def stop_idle_process(self, ch_num):
        #print("CH{} - Stopping Idle Process".format(ch_num))
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
                    process_id.join() #join should only be called by the process that created the process object.
                    process_id.close()
            except ValueError:
                pass
    
    @staticmethod
    def _clear_queue(queue_id):
        try:
            while True:
                queue_id.get_nowait()
        except queue.Empty:
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
        for equipment_process_dict in self.connected_equipment_process_list:
            queue_in, queue_out = self.get_connected_equipment_queues_matching_local_id(equipment_process_dict['local_id'])
            self.stop_process(equipment_process_dict['process'], queue_in)
            
    

def main():
    app = QApplication([])
    test_window = MainTestWindow()
    test_window.show()
    app.aboutToQuit.connect(test_window.clean_up)
    app.exec()
    
if __name__ == '__main__':
    main()
