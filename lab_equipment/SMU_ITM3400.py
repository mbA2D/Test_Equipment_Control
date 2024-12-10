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
        #TODO - instrument models and voltage/current/power limits
    
    def measure_voltage(self):
        return float(self.inst.query("MEAS:VOLT:DC?"))

    def measure_current(self):
        return float(self.inst.query("MEAS:CURR:DC?"))

    def toggle_output(self, state):
        if state:
            self.inst.write("OUTP ON")
        else:
            self.inst.write("OUTP OFF")

    ##COMMANDS FOR CC MODE (DISCHARGING)
    def set_current(self, current_setpoint_A):
        if self.mode != "CURR":
            print("ERROR - SMU not in correct mode")
            return
        self.inst.write("CURR {}".format(abs(current_setpoint_A)))

    def set_voltage_lim_bidir(self, voltage_limit_V):
        self.set_voltage_lim_low(voltage_limit_V)
        self.set_voltage_lim_high(voltage_limit_V)
    
    def set_voltage_lim_low(self, voltage_limit_V):
        if self.mode != "CURR":
            print("ERROR - SMU not in correct mode")
            return
        self.inst.write("VOLT:LIM:LOW {}".format(voltage_setpoint_V))
    
    def set_voltage_lim_high(self, voltage_limit_V):
        if self.mode != "CURR":
            print("ERROR - SMU not in correct mode")
            return
        self.inst.write("VOLT:LIM:LOW {}".format(voltage_setpoint_V))

    def set_mode_current(self):
        self.inst.write("FUNC CURR")
        self.mode = "CURR"
    ##END OF COMMANDS FOR CC MODE

    ##COMMANDS FOR CV MODE (CHARGING)
    def set_mode_voltage(self):
        self.inst.write("FUNC VOLT")
        self.mode = "VOLT"

    def set_cv_voltage(self, voltage_setpoint_V):
        if self.mode != "VOLT":
            print("ERROR - SMU not in correct mode")
            return
        self.inst.write("VOLT {}".format(voltage_setpoint_V))
        
    def set_curr_lim_bidir(self, current_limit_A):
        self.set_curr_lim_low(-1.0*current_limit_A)
        self.set_curr_lim_high(current_limit_A)
    
    def set_curr_lim_low(self, current_limit_A):
        if self.mode != "VOLT":
            print("ERROR - SMU not in correct mode")
            return
        self.inst.write("CURR:LIM:NEG {}".format(voltage_setpoint_V))
        
    def set_curr_lim_high(self, current_limit_A):
        if self.mode != "VOLT":
            print("ERROR - SMU not in correct mode")
            return
        self.inst.write("CURR:LIM:POS {}".format(voltage_setpoint_V))
    ##END OF COMMANDS FOR CV MODE
    
    def remote_sense(self, state):
        if state:
            self.inst.write("REM:SENS ON")
        else:
            self.inst.write("REM:SENS OFF")
    
    def lock_front_panel(self, state):
        if state:
            self.inst.write("SYST:REM")
        else:
            self.inst.write("SYST:LOC")
    
    def __del__(self):
        try:
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
