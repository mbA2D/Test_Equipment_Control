#python pyvisa commands for controlling Korad KAXXXXP series power supplies
#Korad 3010P
#Korad 3005P
#etc.

import pyvisa
import time
from .PyVisaDeviceTemplate import PowerSupplyDevice

# Power Supply
class KAXXXXP(PowerSupplyDevice):
    # Initialize the Korad KAXXXXP Power Supply
    has_remote_sense = False
    can_measure_v_while_off = True #Have not checked this.
    
    connection_settings = {
        'baud_rate':            9600,
        'query_delay':          0.01,
        'time_wait_after_open': 0,
        'pyvisa_backend':       '@py',
        'idn_available':        True
    }
    
    def initialize(self):
        #no *RST on this model
        time.sleep(0.01)
        self.lock_commands(False)
        time.sleep(0.01)
        self.toggle_output(0)
        time.sleep(0.01)
        self.set_current(0)
        time.sleep(0.01)
        self.set_voltage(0)
        time.sleep(0.01)
    
    # To set power supply limit in Amps 
    def set_current(self, current_setpoint_A):		
        self.inst.write("ISET1:{}".format(current_setpoint_A))

    def set_voltage(self, voltage_setpoint_V):
        self.inst.write("VSET1:{}".format(voltage_setpoint_V))

    def toggle_output(self, state, ch = 1):
        if state:
            self.inst.write("OUT1")
        else:
            self.inst.write("OUT0")
    
    def remote_sense(self, state):
        #these units do not have remote sense
        pass
    
    def lock_commands(self, state):
        #these units auto-lock front panel when USB connected
        pass
    
    def measure_voltage(self):
        return float(self.inst.query("VOUT1?"))

    def measure_current(self):
        return float(self.inst.query("IOUT1?"))
        
    def measure_power(self):
        current = self.measure_current()
        voltage = self.measure_voltage()
        return float(current*voltage)
        
    def __del__(self):
        try:
            self.toggle_output(False)
            self.lock_commands(False)
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
