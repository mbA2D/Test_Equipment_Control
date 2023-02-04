#python pyvisa commands for controlling Korad KEL10X series eloads
#Links helpful for finding commands: https://lygte-info.dk/project/TestControllerIntro

import pyvisa
import time
from .PyVisaDeviceTemplate import EloadDevice

# E-Load
class KEL10X(EloadDevice):
    
    has_remote_sense = True
    connection_settings = {
        'baud_rate':            115200,
        'read_termination':     '\n',
        'query_delay':          0.05,
        'pyvisa_backend':       '@ivi',
        'time_wait_after_open': 0,
        'idn_available':        True
    }
    
    # Specific initialization for the KEL10X E-Load	
    def initialize(self):
        split_string = self.inst_idn.split(" ")
        self.model_number = split_string[0]
        self.version_number = split_string[1]
        self.serial_number = split_string[2]
        
        if 'KEL103' in self.model_number:
            self.max_current = 30
            self.max_power = 300
        elif 'KEL102' in self.model_number:
            self.max_current = 30
            self.max_power = 150
        
        self.mode = "CURR"
        
        #unit does not have reset command
        #self.inst.write("*RST")
        self.set_mode_current()
        self.set_current(0)
                
        #set to remote mode (disable front panel)
        self.lock_front_panel(True)
        
    # To Set E-Load in Amps 
    def set_current(self, current_setpoint_A):	
        if self.mode != "CURR":
            print("ERROR - E-load not in correct mode")
            return
        if current_setpoint_A < 0:
            current_setpoint_A = -current_setpoint_A
        self.inst.write(":CURR {}A".format(current_setpoint_A))
        
    def set_mode_current(self):
        self.inst.write(":FUNC CC")
        self.mode = "CURR"

    ##COMMANDS FOR CV MODE
    def set_mode_voltage(self):
        self.inst.write(":FUNC CV")
        self.mode = "VOLT"
    
    def set_cv_voltage(self, voltage_setpoint_V):
        if self.mode != "VOLT":
            print("ERROR - E-load not in correct mode")
            return
        self.inst.write(":VOLT {}".format(voltage_setpoint_V))
    
    ##END OF COMMANDS FOR CV MODE
    
    def toggle_output(self, state):
        if state:
            self.inst.write(":INP 1")
        else:
            self.inst.write(":INP 0")
    
    def remote_sense(self, state):
        if state:
            self.inst.write(":SYST:COMP 1")
        else:
            self.inst.write(":SYST:COMP 0")
    
    def lock_front_panel(self, state):
        pass
        if state:
            self.inst.write(":SYST:LOCK 1")
        else:
            self.inst.write(":SYST:LOCK 0")
    
    def measure_voltage(self):
        return float(self.inst.query(":MEAS:VOLT?").strip('V\n'))

    def measure_current(self):
        return (float(self.inst.query(":MEAS:CURR?").strip('A\n')) * (-1))
    
    def measure_power(self):
        return float(self.inst.query(":MEAS:POW?").strip('W\n'))
    
    def __del__(self):
        try:
            self.toggle_output(False)
            self.lock_front_panel(False)
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
