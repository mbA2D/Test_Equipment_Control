#This class interacts with the actual instrument with queues and events.
#The instrument object is stored in another process.

from .DMM_VIRTUAL import VirtualDMM

class A2D_DAQ_CH(VirtualDMM):
	def __init__(self, resource_id, event_and_queue_dict = None):
		super().__init__(event_and_queue_dict)
		self.board_name = resource_id['board_name']
		self.ch_num = resource_id['ch_num']
