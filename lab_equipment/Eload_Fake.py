"""Simulated electronic load backed exclusively by ``FakeBatteryLink``."""

from battery_app.simulation import require_simulation_link

class Fake_Eload:
    
    has_remote_sense = False
    capabilities = frozenset({
        'can_sink_current', 'can_measure_voltage', 'can_measure_current',
        'can_set_undervoltage_cutoff',
    })

    def __init__(self, resource_id = None, resources_list = None):
        self.max_power = 10000
        self.max_current = 1000
        self.mode = "CURR"
        self.battery_link = None
        
        self.inst_idn = "TestEquipmentControl,SIMULATED_ELOAD,SIM-ELOAD-0001,0.1"
        
    def set_current(self, current_setpoint_A):
        require_simulation_link(self.battery_link, "Fake Eload").set_eload_current(
            current_setpoint_A
        )
        if self.mode != "CURR":
            print("ERROR - E-load not in correct mode")

    def set_undervoltage_cutoff(self, voltage_v):
        require_simulation_link(self.battery_link, "Fake Eload").set_eload_undervoltage_cutoff(
            voltage_v
        )

    def set_mode_current(self):
        require_simulation_link(self.battery_link, "Fake Eload")
        self.mode = "CURR"
    
    def set_mode_voltage(self):
        require_simulation_link(self.battery_link, "Fake Eload")
        self.mode = "VOLT"
        
    def set_cv_voltage(self, voltage_setpoint_V):
        require_simulation_link(self.battery_link, "Fake Eload")
        if self.mode != "VOLT":
            print("ERROR - E-load not in correct mode")
    
    def toggle_output(self, state):
        require_simulation_link(self.battery_link, "Fake Eload").set_eload_output(state)
    
    def remote_sense(self, state):
        pass
    
    def lock_front_panel(self, state):
        pass
    
    def measure_voltage(self):
        return require_simulation_link(self.battery_link, "Fake Eload").measure_voltage()

    def measure_current(self):
        return require_simulation_link(self.battery_link, "Fake Eload").measure_current()

    def attach_battery_link(self, battery_link):
        self.battery_link = battery_link
