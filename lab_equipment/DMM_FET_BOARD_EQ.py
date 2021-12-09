#Class for a single instrument with a single communication interface that could be connected to multiple channels
#Since a single communication interface cannot be recreated in each process then we need to keep the
#equipment object at a higher level and communicate with it via thread-safe events and queues.

class FET_BOARD_EQ:

	def __init__(event_and_queue_dict = None):
		#need to know which queues and events to connect to request measurements and receive data
		self.ch_num = ch_num
		self.v_meas_event = None
		self.v_meas_queue = None
		self.i_meas_event = None
		self.i_meas_queue = None
		self.t_meas_event = None
		self.t_meas_queue = None
		if event_and_queue_dict != None:
			self.setup_queues(event_and_queue_dict)
		
	def setup_queues(event_and_queue_dict)
	
		self.v_meas_event = event_and_queue_dict['v_event']
		self.v_meas_queue = event_and_queue_dict['v_queue']
		self.i_meas_event = event_and_queue_dict['i_event']
		self.i_meas_queue = event_and_queue_dict['i_queue']
		self.t_meas_event = event_and_queue_dict['t_event']
		self.t_meas_queue = event_and_queue_dict['t_queue']
	
	def measure_voltage():
		v_meas_event.set()
		#2 second timeout for the voltage measurements
		return float(v_meas_queue.get(timeout = 2))
	
	def measure_current():
		i_meas_event.set()
		#2 second timeout for the current measurements
		return float(i_meas_queue.get(timeout = 2))
	
	def measure_temperature():
		t_meas_event.set()
		#2 second timeout for the temperature measurements
		return float(t_meas_queue.get(timeout = 2))
