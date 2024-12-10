#File for the Itech M3400 series biridectional power supplies

import pyvisa
from .PyVisaDeviceTemplate import SourceMeasureDevice

# DMM
class IT_M3400(SourceMeasureDevice):
    
    has_remote_sense = True
    connection_settings = {
        'read_termination':         '\r\n',
        'write_termination':        '\n',
        'query_delay':              0.02,
        'pyvisa_backend':           '@py',
        'idn_available':            True
    }
        
    def initialize(self):
        self.inst.write("*RST")
    
    def measure_voltage(self):
        return float(self.inst.query("MEAS:VOLT:DC?"))

    def measure_current(self):
        return float(self.inst.query("MEAS:CURR:DC?"))
    
    def set_current(self, current_setpoint_A):
            self.inst.write("CURR {}".format(abs(current_setpoint_A)))
    
    def set_voltage(self, voltage_setpoint_V):
        self.inst.write("VOLT {}".format(voltage_setpoint_V))
    
    def toggle_output(self, state):
        if state:
            self.inst.write("OUTP ON")
        else:
            self.inst.write("OUTP OFF")
    
    def __del__(self):
        try:
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
