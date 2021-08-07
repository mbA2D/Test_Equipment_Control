#python pyvisa commands for controlling BK Precision BK9100 series power supplies

import pyvisa
import time
import easygui as eg

# Power Supply
class BK9100:
	# Initialize the BK9100 Power Supply
	def __init__(self, resource_id = ""):
		rm = pyvisa.ResourceManager('@py')
		
		if(resource_id == ""):
			resources = rm.list_resources()
			
			########### EASYGUI VERSION #############
			#choicebox needs 2 resources, so if we only have 1 device then add another.
			title = "Power Supply Selection"
			if(len(resources) == 0):
				resource_id = 0
				print("No Resources Available. Connection attempt will exit with errors")
			elif(len(resources) == 1):
				msg = "There is only 1 visa resource available.\nWould you like to use it?\n{}".format(resources[0])
				if(eg.ynbox(msg, title)):
					resource_id = resources[0]
				else:
					resource_id = 0
			else:
				msg = "Select a visa resource for the Power Supply:"
				resource_id = eg.choicebox(msg, title, resources)
		
		self.inst = rm.open_resource(resource_id)
		
		self.inst.baud_rate = 9600
		self.inst.write_termination = '\r'
		self.inst.read_termination = '\r'
		
		#IDN and RST not implemented in this PSU
		#print("Connected to %s\n" % self.inst.query("*IDN?"))
		#self.inst.write("*RST")
		
		self.toggle_output(0)
		self.lock_front_panel(True)
		self.set_current(0)
		self.set_voltage(0)
		
	def select_channel(self, channel):
		pass
	
	def float_to_4_dig(self, val):
		val = int(val*100)
		#pad leading 0's if required
		val = str(val)
		while len(val) < 4:
			val = '0' + val
		return val
	
	#preset 3 is the output
	def set_current(self, current_setpoint_A):
		self.inst.query("CURR3{}".format(self.float_to_4_dig(current_setpoint_A)))
	
	def set_voltage(self, voltage_setpoint_V):
		self.inst.query("VOLT3{}".format(self.float_to_4_dig(voltage_setpoint_V)))

	def toggle_output(self, state):
		if state:
			self.inst.query("SOUT1")
		else:
			self.inst.query("SOUT0")
	
	def remote_sense(self, state):
		pass
	
	def lock_front_panel(self, state):
		pass
	
	#extra queries to clear the buffer
	def measure_voltage(self):
		v = self.inst.query("GETD")
		v = float(v[0:4])/100.0
		self.inst.query("")
		return v

	def measure_current(self):
		i = self.inst.query("GETD")
		i = float(i[4:8])/100.0
		self.inst.query("")
		return i
		
	def measure_power(self):
		p = self.inst.query("GETD")
		v = float(p[0:4])/100.0
		i = float(p[4:8])/100.0
		self.inst.query("")
		return v*i
		
	def __del__(self):
		self.toggle_output(False)
		self.lock_front_panel(False)
		try:
			self.inst.close()
		except AttributeError:
			pass
