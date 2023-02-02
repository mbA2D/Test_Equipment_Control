#python pyvisa commands for controlling Keysight E3631A series power supplies
#Commands: https://www.keysight.com/ca/en/assets/9018-01308/user-manuals/9018-01308.pdf?success=true

import pyvisa
import time
from .PyVisaDeviceTemplate import PowerSupplyDevice

# Power Supply
class E3631A(PowerSupplyDevice):
    has_remote_sense = False
    can_measure_v_while_off = True #Have not checked this.
    
    connection_settings = {
        'query_delay':           0.75,
        'pyvisa_backend':       '@ivi',
        'time_wait_after_open': 0,
        'idn_available':         True
    }
    
    # Initialize the E3631A Power Supply
    def initialize(self):
        self.inst.write("*RST")
        
        split_string = self.inst_idn.split(",")
        self.manufacturer = split_string[0]
        self.model = split_string[1]
        self.zero_number = split_string[2]
        self.version_number = split_string[3]
        
        #Choose channel 2 by default
        self.select_channel(2)
        
        self.lock_front_panel(True)
        self.set_current(0)
        self.set_voltage(0)
        
    def select_channel(self, channel):
        #channel is a number - 1,2,3
        if(channel <= 3) and (channel > 0):
            self.inst.write("INST:NSEL {}".format(channel))
        else:
            print("Invalid Channel")
    
    def set_current(self, current_setpoint_A):
        self.inst.write("CURR {}".format(current_setpoint_A))
    
    def set_voltage(self, voltage_setpoint_V):
        self.inst.write("VOLT {}".format(voltage_setpoint_V))

    def toggle_output(self, state):
        if state:
            self.inst.write("OUTP ON")
        else:
            self.inst.write("OUTP OFF")
    
    def remote_sense(self, state):
        pass
    
    def lock_front_panel(self, state):
        if state:
            self.inst.write("SYST:REM")
        else:
            self.inst.write("SYST:LOC")
    
    def measure_voltage(self):
        return float(self.inst.query("MEAS:VOLT?"))

    def measure_current(self):
        return float(self.inst.query("MEAS:CURR?"))
        
    def measure_power(self):
        return self.measure_current()*self.measure_voltage()
        
    def __del__(self):
        try:
            for ch in range(3):
                self.lock_front_panel(False)
                self.select_channel(ch+1)
                self.toggle_output(False)
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
