#which channels are connected to what cells

class TempChannels:
	def __init__(self):
		self.channels = {
			'EMS_SC_1' : {
				'pos' : [0,1,2,3],
				'neg' : [0,1,2,3],
				'side' : [0,1,2,3]
			},
			'EMS_NI_1' : {
				'pos' : [0,1,2,3],
				'neg' : [0,1,2,3],
				'side' : [0,1,2,3]
			},
			'EMS_SC_EPOXY' : {
				'pos' : [0,1,2,3],
				'neg' : [0,1,2,3],
				'side' : [0,1,2,3]
			},
			'EMS_NI_EPOXY' : {
				'pos' : [0,1,2,3],
				'neg' : [0,1,2,3],
				'side' : [0,1,2,3]
			}
		}
