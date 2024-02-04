#python pyvisa commands for controlling Siglent SPD1000 series power supplies

import pyvisa
import time
from .PyVisaDeviceTemplate import PowerSupplyDevice
from retry import retry

class SetpointException(Exception):
    #Raised when a command is not passed to the instrument correctly.
    pass

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
    
    setpoint_compare_tolerance = 0.0001
    
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
    @retry(SetpointException, delay=0.1, tries=10)
    def set_current(self, current_setpoint_A):		
        self.inst.write("CURR {}".format(current_setpoint_A))
        if abs(self.get_current() - current_setpoint_A) > SPD1000.setpoint_compare_tolerance:
            raise SetpointException
    
    def get_current(self):
        return float(self.inst.query("CURR?"))
    
    @retry(SetpointException, delay=0.1, tries=10)
    def set_voltage(self, voltage_setpoint_V):
        self.inst.write("VOLT {}".format(voltage_setpoint_V))
        if abs(self.get_voltage() - voltage_setpoint_V) > SPD1000.setpoint_compare_tolerance:
            raise SetpointException
    
    def get_voltage(self):
        return float(self.inst.query("VOLT?"))
    
    @retry(SetpointException, delay=0.1, tries=10)
    def toggle_output(self, state, ch = 1):
        if state:
            self.inst.write("OUTP CH{},ON".format(ch))
        else:
            self.inst.write("OUTP CH{},OFF".format(ch))
        if self.get_output() != state:
            raise SetpointException
    
    def get_output(self):
        val = int(self.inst.query("SYST:STAT?"),16)
        return bool(val & (1<<4)) #Bit number 4 is Output
    
    @retry(SetpointException, delay=0.1, tries=10)
    def remote_sense(self, state):
        if state:
            self.inst.write("MODE:SET 4W")
        else:
            self.inst.write("MODE:SET 2W")
        if self.get_remote_sense() != state:
            raise SetpointException
            
    def get_remote_sense(self):
        val = int(self.inst.query("SYST:STAT?"),16)
        return bool(val & (1<<5)) #Bit number 5 is remote sense
    
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
