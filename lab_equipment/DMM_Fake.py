"""Simulated DMM backed exclusively by ``FakeBatteryLink``."""

from battery_app.simulation import require_simulation_link

class Fake_DMM:
    
    def __init__(self, resource_id = None, resources_list = None):
        self.inst_idn = "TestEquipmentControl,SIMULATED_DMM,SIM-DMM-0001,0.1"
        self.battery_link = None
        
    def measure_voltage(self, nplc = None, volt_range = None):
        return require_simulation_link(self.battery_link, "Fake DMM").measure_voltage()

    def measure_current(self):
        return require_simulation_link(self.battery_link, "Fake DMM").measure_current()

    def measure_temperature(self):
        return require_simulation_link(self.battery_link, "Fake DMM").measure_temperature()
    
    def set_mode(self, mode = "DCV"):
        pass
    
    def set_auto_zero_dcv(self, state):
        pass
    
    def set_range_dcv(self, volt_range = None):
        pass
    
    def set_nplc(self, nplc = None):
        pass

    def attach_battery_link(self, battery_link):
        self.battery_link = battery_link
