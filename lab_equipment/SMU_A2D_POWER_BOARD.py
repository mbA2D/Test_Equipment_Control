#python pyvisa commands for controlling an A2D SENSE BOARD with I2C

import pyvisa
from .PyVisaDeviceTemplate import SourceMeasureDevice

# DMM
class A2D_POWER_BOARD(SourceMeasureDevice):
    
    has_remote_sense = False
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
        self.current_target_a = 0.0
        self.output_is_on = False
        self.inst.write("*RST")
        self.i2c_dac_addr = None
        self.i2c_adc_addr = None
    
    def reset_calibration(self):
        self.inst.write('POWER:CAL:RESET')
        self.inst.write('SENSE:CAL:RESET')
    
    def calibrate_voltage(self, v1a, v1m, v2a, v2m): #2 points, actual (a) (dmm) and measured (m) (sense board)
        self.inst.write('SENSE:CAL:VOLT {},{},{},{}'.format(v1a, v1m, v2a, v2m))
        
    def calibrate_current(self, i1a, i1m, i2a, i2m): #2 points, actual (a) (dmm) and measured (m) (sense board)
        self.inst.write('SENSE:CAL:CURR {},{},{},{}'.format(v1a, v1m, v2a, v2m))
    
    def measure_voltage(self):
        return float(self.inst.query("MEAS:VOLT:DC?"))

    def measure_current(self):
        return float(self.inst.query("MEAS:CURR:DC?"))
        
    def measure_temperature(self):
        return float(self.inst.query("MEAS:TEMP_C?"))
    
    def set_current(self, current_setpoint_A):
        #Turn output off and back on when switching current directions. Send new target before turning back on
        if self.output_is_on and (self.current_target_a <= 0.0 and current_setpoint_A > 0.0) or (self.current_target_a >= 0.0 and current_setpoint_A < 0.0):
            self.toggle_output(False)
            self.current_target_a = current_setpoint_A
            
            self.inst.write("CURR {}".format(abs(current_setpoint_A)))
            self.toggle_output(True)
        else:
            self.current_target_a = current_setpoint_A
            self.inst.write("CURR {}".format(abs(current_setpoint_A)))
    
    def set_voltage(self, voltage_setpoint_V):
        self.inst.write("VOLT {}".format(voltage_setpoint_V))
    
    def toggle_output(self, state):
        if state:
            if self.current_target_a >= 0.0:
                self.inst.write("ELOAD:OFF")
                self.inst.write("PSU:ON")
            elif self.current_target_a < 0.0:
                self.inst.write("PSU:OFF")
                self.inst.write("ELOAD:ON")
            self.output_is_on = True
        else:
            self.inst.write("PSU:OFF")
            self.inst.write("ELOAD:OFF")
            self.output_is_on = False
    
    def set_i2c_dac_addr(self, addr):
        self.i2c_dac_addr = addr
        self.inst.write('INSTR:DAC:ADDR x {address}'.format(address = self.i2c_dac_addr))
    
    def set_i2c_adc_addr(self, addr):
        self.i2c_adc_addr = addr
        self.inst.write('INSTR:ADC:ADDR x {address}'.format(address = self.i2c_adc_addr))
    
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
