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
    
    def reset_calibration(self):
        self.inst.write('INSTR:CAL:RESET')
    
    def calibrate_voltage(self, v1a, v1m, v2a, v2m): #2 points, actual (a) (dmm) and measured (m) (sense board)
        self.inst.write('INSTR:CAL:VOLT {},{},{},{}'.format(v1a, v1m, v2a, v2m))
        
    def calibrate_current(self, i1a, i1m, i2a, i2m): #2 points, actual (a) (dmm) and measured (m) (sense board)
        self.inst.write('INSTR:CAL:CURR {},{},{},{}'.format(v1a, v1m, v2a, v2m))
    
    def measure_voltage(self):
        return float(self.inst.query("MEAS:VOLT:DC?"))

    def measure_current(self):
        return float(self.inst.query("MEAS:CURR:DC?"))
        
    def measure_temperature(self):
        return float(self.inst.query("MEAS:TEMP_C?"))
    
    def set_i2c_adc_addr(self, addr):
        self.i2c_adc_addr = addr
        self.inst.write('INSTR:SET:ADDR x {address}'.format(address = self.i2c_adc_addr))
    
    def set_led(self, state): #state is a bool
        if state:
            self.inst.write('INSTR:SET:LED x {}'.format(True))
        else:
            self.inst.write('INSTR:SET:LED x {}'.format(False))
    
    def __del__(self):
        try:
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
