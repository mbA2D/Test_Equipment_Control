#python pyvisa commands for controlling BK Precision BK9100 series power supplies

import pyvisa
from .PyVisaDeviceTemplate import PowerSupplyDevice

# Power Supply
class BK9100(PowerSupplyDevice):
	
	has_remote_sense = False
	can_measure_v_while_off = True #Have not checked this.
	
	# Initialize the BK9100 Power Supply
	connection_settings = {
        'baud_rate':            9600,
        'write_termination':    '\r',
        'read_termination':     '\r',
        'idn_available':        False,
        'pyvisa_backend':       '@py'
	}
		
	def initialize(self):
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
		try:
			self.toggle_output(False)
			self.lock_front_panel(False)
			self.inst.close()
		except (AttributeError, pyvisa.errors.InvalidSession):
			pass
