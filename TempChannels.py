#which channels are connected to what cells

class TempChannels:
	def __init__(self):
		self.channels = {
			'EMS_SC1' : {
				'pos' : [56,57,58,59,60,61,62],
				'neg' : [48,49,50,51,52,53,54],
				'side' : [55]
			},
			'EMS_NI1' : {
				'pos' : [0,1,2,3,4,5,6],
				'neg' : [7,8,9,11,13,14],
				'side' : [12]
			},
			'EMS_SC_EPOXY' : {
				'pos' : [40,41,42,43,44,45,46],
				'neg' : [32,33,34,35,36,37,38],
				'side' : [39]
			},
			'EMS_NI_EPOXY' : {
				'pos' : [16,17,18,19,20,21,22],
				'neg' : [24,25,26,27,28,29,30],
				'side' : [23]
			}
		}
