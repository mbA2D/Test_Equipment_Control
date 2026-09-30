"""Application services for the battery-test GUI."""

from importlib import import_module

__all__ = [
    "SIMULATED_LG_MJ1",
    "ApplicationEvent",
    "BatteryApplication",
    "BatteryCellParameters",
    "BatteryCellState",
    "BatteryCellWorldModel",
    "ChannelController",
    "ChannelState",
    "ChannelStatus",
    "ConfigurationStore",
    "EquipmentManager",
    "FakeBatteryLink",
    "HeadlessRunner",
    "MessageRouter",
    "ProcessManager",
    "ProfileIdentityService",
    "TestExecutionService",
    "is_simulated_cell_name",
]

_EXPORTS = {
    "ApplicationEvent": (".application", "ApplicationEvent"),
    "BatteryApplication": (".application", "BatteryApplication"),
    "ChannelController": (".channel_controller", "ChannelController"),
    "BatteryCellParameters": (".battery_model_simple", "BatteryCellParameters"),
    "BatteryCellState": (".battery_model_simple", "BatteryCellState"),
    "BatteryCellWorldModel": (".battery_model_simple", "BatteryCellWorldModel"),
    "FakeBatteryLink": (".simulation", "FakeBatteryLink"),
    "HeadlessRunner": (".headless_runner", "HeadlessRunner"),
    "SIMULATED_LG_MJ1": (".simulation", "SIMULATED_LG_MJ1"),
    "is_simulated_cell_name": (".simulation", "is_simulated_cell_name"),
    "EquipmentManager": (".equipment_manager", "EquipmentManager"),
    "TestExecutionService": (".execution", "TestExecutionService"),
    "ChannelState": (".state", "ChannelState"),
    "ChannelStatus": (".state", "ChannelStatus"),
    "MessageRouter": (".messages", "MessageRouter"),
    "ConfigurationStore": (".persistence", "ConfigurationStore"),
    "ProcessManager": (".process_manager", "ProcessManager"),
    "ProfileIdentityService": (".profile_identity", "ProfileIdentityService"),
}


def __getattr__(name):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value
