#class to hold the cycle stats

class CycleStats:
	
	def __init__(self):
		self.stats = {
			"charge_capacity_ah": 0,
			"charge_capacity_wh": 0,
			"charge_time_h": 0,
			"discharge_capacity_ah": 0,
			"discharge_capacity_wh": 0,
			"discharge_time_h": 0
		}
