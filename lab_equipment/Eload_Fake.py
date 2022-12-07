#python implementation for a fake power supply to test programs - has all functions and returns some values

# E-Load
class Fake_Eload:
    
    has_remote_sense = False

    def __init__(self, resource_id = None):
        self.max_power = 10000
        self.max_current = 1000
        self.mode = "CURR"
        self.current_a = 0
        self.voltage_v = 4
        
        pass
        
    # To Set E-Load in Amps 
    def set_current(self, current_setpoint_A):
        self.current_a = current_setpoint_A
        if self.mode != "CURR":
            print("ERROR - E-load not in correct mode")
        pass
    
    def set_mode_current(self):
        self.current_a = 0
        self.mode = "CURR"
    
    def set_mode_voltage(self):
        self.voltage_v = 0
        self.mode = "VOLT"
        pass
        
    def set_cv_voltage(self, voltage_setpoint_V):
        self.voltage_v = voltage_setpoint_V
        if self.mode != "VOLT":
            print("ERROR - E-load not in correct mode")
        pass
    
    def toggle_output(self, state):
        pass
    
    def remote_sense(self, state):
        pass
    
    def lock_front_panel(self, state):
        pass
    
    def measure_voltage(self):
        return self.voltage_v

    def measure_current(self):
        return self.current_a
