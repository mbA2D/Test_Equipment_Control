#python pyvisa commands for controlling Siglent SPD1000 series power supplies

import pyvisa
import time
from .PyVisaDeviceTemplate import PowerSupplyDevice

# Power Supply
class SPD1000(PowerSupplyDevice):
    # Initialize the SPD1000 Power Supply
    has_remote_sense = True
    can_measure_v_while_off = False
    
    connection_settings = {
        'read_termination':     '\n',
        'write_termination':    '\n',
        'query_delay':          0.15,
        'pyvisa_backend':       '@ivi',
        'time_wait_after_open': 0,
        'idn_available':        True
    }
    
    def initialize(self):
        self.inst.write("*RST")
        time.sleep(0.1)
        
        #Choose channel 1
        self.inst.write("INST CH1")
        time.sleep(0.1)
        self.lock_commands(False)
        time.sleep(0.1)
        self.toggle_output(False) #Apparently RST does not turn off the output?
        time.sleep(0.1)
        self.set_current(0)
        time.sleep(0.1)
        self.set_voltage(0)
        time.sleep(0.1)
        
    # To Set power supply current limit in Amps 
    def set_current(self, current_setpoint_A):		
        self.inst.write("CURR {}".format(current_setpoint_A))

    def set_voltage(self, voltage_setpoint_V):
        self.inst.write("VOLT {}".format(voltage_setpoint_V))

    def toggle_output(self, state, ch = 1):
        if state:
            self.inst.write("OUTP CH{},ON".format(ch))
        else:
            self.inst.write("OUTP CH{},OFF".format(ch))
    
    def remote_sense(self, state):
        if state:
            self.inst.write("MODE:SET 4W")
        else:
            self.inst.write("MODE:SET 2W")
    
    def lock_commands(self, state):
        if state:
            self.inst.write("*LOCK")
        else:
            self.inst.write("*UNLOCK")
    
    def measure_voltage(self):
        return float(self.inst.query("MEAS:VOLT?"))

    def measure_current(self):
        return float(self.inst.query("MEAS:CURR?"))
        
    def measure_power(self):
        return float(self.inst.query("MEAS:POWE?"))
        
    def __del__(self):
        try:
            self.toggle_output(False)
            self.lock_commands(False)
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
