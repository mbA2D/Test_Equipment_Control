#python pyvisa commands for controlling an A2D 4CH Isolated ADC

import pyvisa
from .PyVisaDeviceTemplate import DMMDevice

# DMM
class A2D_4CH_Isolated_ADC(DMMDevice):
    num_channels = 4
    start_channel = 1
    connection_settings = {
        'read_termination':         '\r\n',
        'write_termination':        '\n',
        'baud_rate':                115200,
        'query_delay':              0.001,
        'time_wait_after_open':     0,
        'chunk_size':               102400,
        'pyvisa_backend':           '@py',
        'idn_available':            True
    }
    
    def reset(self):
        self.inst.write('*RST')
    
    def reset_calibration(self, channel = 1):
        self.inst.write(f'CAL:RESET {channel}')
        
    def save_calibration(self, channel = 1):
        self.inst.write(f'CAL:SAVE {channel}')
        
    def get_calibration(self, channel = 1):
        #returns a list with offset,gain for each channel.
        return [float(val) for val in self.inst.query_ascii_values(f'CAL {channel}?')]
    
    def calibrate_voltage(self, v1a, v1m, v2a, v2m, channel = 1): #2 points, actual (a) (dmm) and measured (m) (sense board)
        self.inst.write(f'CAL:VOLT {channel},{v1a},{v1m},{v2a},{v2m}')
    
    def measure_voltage(self, channel = 1):
        if channel == 0:
            #return a list with all 4 values.
            return [float(val) for val in self.inst.query_ascii_values(f'MEAS:VOLT {channel}?')]
        else:
            return float(self.inst.query(f'MEAS:VOLT {channel}?'))
        
    def measure_voltage_at_adc(self, channel = 1):
        if channel == 0:
            #return a list with all 4 values.
            return [float(val) for val in self.inst.query_ascii_values(f'MEAS:VOLT:ADC {channel}?')]
        else:
            return float(self.inst.query(f'MEAS:VOLT:ADC {channel}?'))
        
    def set_led(self, state): #state is a bool
        if state:
            self.inst.write('INSTR:LED 1')
        else:
            self.inst.write('INSTR:LED 0')
    
    def get_num_channels(self):
        return A2D_4CH_Isolated_ADC.num_channels
    
    def __del__(self):
        try:
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
