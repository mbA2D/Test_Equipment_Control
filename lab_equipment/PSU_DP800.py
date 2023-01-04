#python pyvisa commands for controlling Rigol DP800 series power supplies

import pyvisa
from .PyVisaDeviceTemplate import PowerSupplyDevice

# Power Supply
class DP800(PowerSupplyDevice):
    
    has_remote_sense = False
    can_measure_v_while_off = True #Have not checked this.
    connection_settings = {
        'pyvisa_backend':   '@ivi',
        'idn_available':    True
    }
        
    def initialize(self):
        self.inst.write("*RST")
        
        split_string = self.inst_idn.split(",")
        self.manufacturer = split_string[0]
        self.model = split_string[1]
        self.serial_number = split_string[2]
        self.version_number = split_string[3]
        
        if 'DP811' in self.model:
            self.has_remote_sense = True
        
        #Choose channel 1 by default
        self.select_channel(1)
        
        self.lock_front_panel(True)
        self.set_current(0)
        self.set_voltage(0)
        
    def select_channel(self, channel):
        #channel is a number - 1,2,3
        if(channel <= 3) and (channel > 0):
            self.inst.write(":INST:NSEL {}".format(channel))
    
    def set_current(self, current_setpoint_A):
        self.inst.write(":CURR {}".format(current_setpoint_A))
    
    def set_voltage(self, voltage_setpoint_V):
        self.inst.write(":VOLT {}".format(voltage_setpoint_V))

    def toggle_output(self, state):
        if state:
            self.inst.write(":OUTP ON")
        else:
            self.inst.write(":OUTP OFF")
    
    def remote_sense(self, state):
        if self.has_remote_sense:
            #only for DP811
            if state:
                self.inst.write(":OUTP:SENS ON")
            else:
                self.inst.write(":OUTP:SENS OFF")
    
    def lock_front_panel(self, state):
        if state:
            self.inst.write(":SYST:REM")
        else:
            self.inst.write(":SYST:LOC")
    
    def measure_voltage(self):
        return float(self.inst.query(":MEAS:VOLT?"))

    def measure_current(self):
        return float(self.inst.query(":MEAS:CURR?"))
        
    def measure_power(self):
        return float(self.inst.query(":MEAS:POWE?"))
        
    def __del__(self):
        try:
            for ch in range(3):
                self.select_channel(ch+1)
                self.toggle_output(False)
                self.lock_front_panel(False)
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
