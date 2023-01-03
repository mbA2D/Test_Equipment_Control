#Class to manage all the connected A2D DAQ boards in a separate process or thread.

from multiprocessing import Process, Queue, Event
import queue #queue module required for exception handling of multiprocessing.Queue
from . import A2D_DAQ_control

def create_event_and_queue_dicts(num_devices = 1, num_ch_per_device = A2D_DAQ_control.A2D_DAQ.num_channels):
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
	
	#Create a new process to manage the A2D DAQ board
	management_queue = Queue()
	multi_ch_device_process = Process(target = a2d_daq_management, args = (dict_for_event_and_queue, management_queue))
	multi_ch_device_process.start()
	
	return dict_for_event_and_queue, management_queue, multi_ch_device_process
	
def a2d_daq_management(queue_and_event_dict, management_queue):
	boardManagement = A2DDAQManagement(queue_and_event_dict, management_queue)
	boardManagement.connect_to_multiple_devices()
	boardManagement.monitor_events()


class A2DDAQManagement:
	
	def __init__(self, dict_for_event_and_queue = None, management_queue = None):
		self.dict_for_event_and_queue = dict_for_event_and_queue
		self.device = None
		self.management_queue = management_queue
	
	def connect_to_multiple_devices(self):
		self.device = A2D_DAQ_control.A2D_DAQ() #Connect to the device with PyVisa - this is where we want the thing to be connected
		self.num_devices = 1
		
	def monitor_events(self):
		queue_message = None
		while queue_message != 'stop':
			for device_num in range(self.num_devices):
				for ch_num in range(A2D_DAQ_control.A2D_DAQ.num_channels):
					for dict_key in self.dict_for_event_and_queue[device_num][ch_num]:
						#check the event to see if it has been set
						if 'event' in dict_key and self.dict_for_event_and_queue[device_num][ch_num][dict_key].is_set():
							self.dict_for_event_and_queue[device_num][ch_num][dict_key].clear()
							#if set, measure voltage and put it in the appropriate queue
							if dict_key == 'v_event':
								self.dict_for_event_and_queue[device_num][ch_num]['v_queue'].put_nowait(self.device.measure_voltage(ch_num))
							#elif dict_key == 'i_event':
							#	self.dict_for_event_and_queue[device_num][ch_num]['i_queue'].put_nowait()
							elif dict_key == 't_event':
								self.dict_for_event_and_queue[device_num][ch_num]['t_queue'].put_nowait(self.device.measure_temperature(ch_num))
			try:
				queue_message = self.management_queue.get_nowait()
			except queue.Empty:
				pass