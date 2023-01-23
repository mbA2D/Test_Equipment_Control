#python pyvisa commands for controlling an A2D SENSE BOARD with I2C

import pyvisa
from .PyVisaDeviceTemplate import DMMDevice

# DMM
class A2D_SENSE_BOARD(DMMDevice):
	connection_settings = {
        'read_termination':         '\r\n',
        'write_termination':        '\n',
        'baud_rate':                57600,
        'query_delay':              0.02,
        'chunk_size':               102400,
        'pyvisa_backend':           '@py',
        'time_wait_after_open':     2,
        'idn_available':            True
    }
		
	def initialize(self):
		self.i2c_adc_addr = None
		
	def measure_voltage(self):
		return float(self.inst.query(":MEAS:VOLT:DC?"))

	def measure_current(self):
		return float(self.inst.query(":MEAS:CURR:DC?"))
        
    def measure_temperature(self):
		return float(self.inst.query(":MEAS:TEMP?"))
	
    def set_i2c_adc_addr(self, addr):
        self.i2c_adc_addr = addr
        self.inst.write('INSTR:SET:ADDR x {address}'.format(address = self.i2c_expander_addr))
    
	def __del__(self):
		try:
			self.inst.close()
		except (AttributeError, pyvisa.errors.InvalidSession):
			pass
