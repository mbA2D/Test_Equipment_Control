#Class to manage all the connected FET boards in a separate process or thread.

from . import Blinka_Example_MCP_Multiple as bemm
from multiprocessing import Process, Queue, Event
import queue #queue module required for exception handling of multiprocessing.Queue


def create_event_and_queue_dicts(num_devices = 4, num_ch_per_device = 4):
	dict_for_event_and_queue = {}
	for device_num in range(num_devices):
			dict_for_event_and_queue[device_num] = {}
			for ch_num in range(num_ch_per_device):	
				dict_for_event_and_queue[device_num][ch_num] = {
					'v_event': Event(),
					'v_queue': Queue(),
					'i_event': Event(),
					'i_queue': Queue(),
					't_event': Event(),
					't_queue': Queue()
				} 
	
	#Create a new process to manage all the fet boards
	multi_ch_device_process = Process(target = fet_board_management, args = (dict_for_event_and_queue,))
	multi_ch_device_process.start()
	
	return dict_for_event_and_queue
	
def fet_board_management(queue_and_event_dict):
	boardManagement = FETBoardManagement(queue_and_event_dict)
	boardManagement.connect_to_multiple_devices()
	boardManagement.monitor_events()


class FETBoardManagement:
	
	def __init__(self, dict_for_event_and_queue = None):
		self.dict_for_event_and_queue = dict_for_event_and_queue
		self.multi_ch_eq_dict = {}
	
	def connect_to_multiple_devices(self):
		self.multi_ch_eq_dict = bemm.get_mcp_dict()
		print("Devices found:")
		print(self.multi_ch_eq_dict)
	
	def monitor_events(self):
		#TODO - split this up into a thread for each I2C bus so we can read faster - don't have to wait for other devices to finish reading first.		
		while True:
			for eq_key in self.multi_ch_eq_dict:
				if "FET Board" in eq_key:
					device_num = int(eq_key[-1])
					for ch_num in range(self.multi_ch_eq_dict[eq_key].num_channels):
						for dict_key in self.dict_for_event_and_queue[device_num][ch_num]:
							#check the event to see if it has been set
							if 'event' in dict_key and self.dict_for_event_and_queue[device_num][ch_num][dict_key].is_set():
								self.dict_for_event_and_queue[device_num][ch_num][dict_key].clear()
								#if set, measure voltage and put it in the appropriate queue
								if dict_key == 'v_event':
									self.dict_for_event_and_queue[device_num][ch_num]['v_queue'].put_nowait(self.multi_ch_eq_dict[eq_key].measure_voltage(ch_num))
								elif dict_key == 'i_event':
									self.dict_for_event_and_queue[device_num][ch_num]['i_queue'].put_nowait(self.multi_ch_eq_dict[eq_key].measure_current(ch_num))
								elif dict_key == 't_event':
									self.dict_for_event_and_queue[device_num][ch_num]['t_queue'].put_nowait(self.multi_ch_eq_dict[eq_key].measure_temp(ch_num))
								