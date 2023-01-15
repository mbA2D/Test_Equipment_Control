#python pyvisa commands for controlling KORAD KWR10X or Multicomp Pro MP71025X series power supplies
#KWR102 - MP710256 - 30V 30A 300W
#KWR103 - MP710257 - 60V 15A 300W

import pyvisa
import time
from .PyVisaDeviceTemplate import PowerSupplyDevice

# Power Supply
class MP71025X(PowerSupplyDevice):
    # Initialize the KWR102/3 MP710256/7 Power Supply
    has_remote_sense = True
    can_measure_v_while_off = True #Have not checked this.
    
    connection_settings = {
        'baud_rate':            115200,
        'read_termination':     '\n',
        'query_delay':          0.04,
        'pyvisa_backend':       '@py',
        'time_wait_after_open': 0,
        'idn_available':        True
    }	
    
    def initialize(self):
        split_string = self.inst_idn.split(" ")
        self.model_number = split_string[0]
        self.version_number = split_string[1]
        self.serial_number = split_string[2]
        
        #this unit does not have a reset command
        #self.inst.write("*RST")
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
        self.inst.write("ISET:{}".format(current_setpoint_A))

    def set_voltage(self, voltage_setpoint_V):
        self.inst.write("VSET:{}".format(voltage_setpoint_V))

    def toggle_output(self, state, ch = 1):
        if state:
            self.inst.write("OUT:1")
        else:
            self.inst.write("OUT:0")
    
    def remote_sense(self, state):
        if state:
            self.inst.write("COMP:1")
        else:
            self.inst.write("COMP:0")
    
    def lock_commands(self, state):
        if state:
            self.inst.write("LOCK:1")
        else:
            self.inst.write("LOCK:0")
    
    def measure_voltage(self):
        return float(self.inst.query("VOUT?"))

    def measure_current(self):
        return float(self.inst.query("IOUT?"))
        
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
