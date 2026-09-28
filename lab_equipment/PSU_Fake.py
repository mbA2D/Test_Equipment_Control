"""Simulated power supply backed exclusively by ``FakeBatteryLink``."""

from battery_app.simulation import require_simulation_link

class Fake_PSU:
    has_remote_sense = False
    can_measure_v_while_off = True
    
    def __init__(self, resource_id = None, resources_list = None):
        self.battery_link = None
        
        self.inst_idn = "TestEquipmentControl,SIMULATED_PSU,SIM-PSU-0001,0.1"
        
    def set_current(self, current_setpoint_A):		
        require_simulation_link(self.battery_link, "Fake PSU").set_psu_current(
            current_setpoint_A
        )

    def set_voltage(self, voltage_setpoint_V):
        require_simulation_link(self.battery_link, "Fake PSU").set_psu_voltage(
            voltage_setpoint_V
        )

    def toggle_output(self, state, ch = 1):
        require_simulation_link(self.battery_link, "Fake PSU").set_psu_output(state)
    
    def remote_sense(self, state):
        pass
    
    def lock_commands(self, state):
        pass
    
    def measure_voltage(self):
        return require_simulation_link(self.battery_link, "Fake PSU").measure_voltage()

    def measure_current(self):
        return require_simulation_link(self.battery_link, "Fake PSU").measure_current()
        
    def measure_power(self):
        current = self.measure_current()
        voltage = self.measure_voltage()
        return float(current*voltage)

    def attach_battery_link(self, battery_link):
        self.battery_link = battery_link
