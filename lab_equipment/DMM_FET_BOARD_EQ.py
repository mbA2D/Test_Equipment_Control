#Class for a single instrument with a single communication interface that could be connected to multiple channels
#Since a single communication interface cannot be recreated in each process then we need to keep the
#equipment object at a higher level and communicate with it via thread-safe events and queues.

class VirtualDMM:
	def __init__(self, event_and_queue_dict = None):
		#need to know which queues and events to connect to request measurements and receive data
		self.event_and_queue_dict = event_and_queue_dict
	
	def measure_voltage(self):
		self.event_and_queue_dict['v_event'].set()
		#2 second timeout for the voltage measurements
		return float(self.event_and_queue_dict['v_queue'].get(timeout = 10))
	
	def measure_current(self):
		self.event_and_queue_dict['i_event'].set()
		#2 second timeout for the current measurements
		return float(self.event_and_queue_dict['i_queue'].get(timeout = 10))
	
	def measure_temperature(self):
		self.event_and_queue_dict['t_event'].set()
		#2 second timeout for the temp measurements
		return float(self.event_and_queue_dict['t_queue'].get(timeout = 10))


class FET_BOARD_EQ(VirtualDMM):
	def __init__(self, resource_id, event_and_queue_dict = None):
		super().__init__(event_and_queue_dict)
		self.board_name = resource_id['board_name']
		self.ch_num = resource_id['ch_num']
		
	
