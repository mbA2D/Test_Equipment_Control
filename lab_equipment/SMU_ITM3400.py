#File for the Itech M3400 series biridectional power supplies

import pyvisa
from .PyVisaDeviceTemplate import SourceMeasureDevice

# DMM
class IT_M3400(SourceMeasureDevice):
    
    has_remote_sense = True
    connection_settings = {
        'pyvisa_backend':           '@ivi',
        'time_wait_after_open':     0,
        'idn_available':            True
    }
        
    def initialize(self):
        idn_split = self.inst_idn.split(',')
        model_number = idn_split[1]

        self.inst.write("*RST")
        self.set_mode_current()
        
        if '3434' in model_number:
            self.max_power = 800
            self.max_current = 6
            self.max_voltage = 300
        elif '3424' in model_number:
            self.max_power = 400
            self.max_current = 6
            self.max_voltage = 300
        elif '3414' in model_number:
            self.max_power = 200
            self.max_current = 6
            self.max_voltage = 300
        elif '3433' in model_number:
            self.max_power = 800
            self.max_current = 12
            self.max_voltage = 150
        elif '3423' in model_number:
            self.max_power = 400
            self.max_current = 12
            self.max_voltage = 150
        elif '3413' in model_number:
            self.max_power = 200
            self.max_current = 12
            self.max_voltage = 150
        elif '3432' in model_number:
            self.max_power = 800
            self.max_current = 30
            self.max_voltage = 60
        elif '3422' in model_number:
            self.max_power = 400
            self.max_current = 30
            self.max_voltage = 60
        elif '3412' in model_number:
            self.max_power = 200
            self.max_current = 30
            self.max_voltage = 60
        elif '3435' in model_number:
            self.max_power = 800
            self.max_current = 3
            self.max_voltage = 600
        elif '3425' in model_number:
            self.max_power = 400
            self.max_current = 3
            self.max_voltage = 600
        elif '3415' in model_number:
            self.max_power = 200
            self.max_current = 3
            self.max_voltage = 600

        #TODO - use the voltage/current/power limits in the setpoint functions
    
    def measure_voltage(self):
        return float(self.inst.query("MEAS:VOLT:DC?"))

    def measure_current(self):
        return float(self.inst.query("MEAS:CURR:DC?"))

    def toggle_output(self, state):
        if state:
            self.inst.write("OUTP ON")
        else:
            self.inst.write("OUTP OFF")

    ##COMMANDS FOR CC MODE (BATTERY DISCHARGING)
    def set_mode_current(self):
        self.toggle_output(False)
        self.inst.write("FUNC CURR")
        self.mode = "CURR"
        
    def set_current(self, current_setpoint_A):
        if self.mode != "CURR":
            print("ERROR - SMU not in correct mode")
            return
        self.inst.write("CURR {}".format(abs(current_setpoint_A)))

    def set_voltage(self, voltage_setpoint_V):
        #for compatibility with power supplies with a 'set_voltage' command
        if self.mode != "CURR":
            print("ERROR - SMU not in correct mode")
            return
        self.set_voltage_lim_low(0)
        self.set_voltage_lim_high(voltage_setpoint_V)
    
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
    ##END OF COMMANDS FOR CC MODE

    ##COMMANDS FOR CV MODE (BATTERY CHARGING)
    def set_mode_voltage(self):
        self.toggle_output(False)
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
