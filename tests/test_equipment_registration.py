from battery_test import MainTestWindow
import equipment
from lab_equipment.A2D_DAQ_control import A2D_DAQ


def test_physical_resource_ids_support_composite_equipment():
    assert MainTestWindow._physical_resource_ids("GPIB0::1::INSTR") == {
        "GPIB0::1::INSTR"
    }
    assert MainTestWindow._physical_resource_ids({
        "res_id_1": "GPIB0::1::INSTR",
        "res_id_2": "GPIB0::2::INSTR",
        "class_name_1": "A",
    }) == {"GPIB0::1::INSTR", "GPIB0::2::INSTR"}


def test_duplicate_resource_is_rejected_even_when_role_differs():
    connected = [{"res_id": "GPIB0::1::INSTR", "eq_type": "psu"}]
    new_equipment = {
        "res_id": "GPIB0::1::INSTR",
        "eq_type": "dmm",
    }

    assert MainTestWindow.is_equipment_already_connected(
        new_equipment,
        connected,
    )


def test_different_resource_is_allowed():
    connected = [{"res_id": "GPIB0::1::INSTR", "eq_type": "psu"}]
    new_equipment = {
        "res_id": "GPIB0::2::INSTR",
        "eq_type": "dmm",
    }

    assert not MainTestWindow.is_equipment_already_connected(
        new_equipment,
        connected,
    )


def test_assignment_resolution_prefers_stable_equipment_id_over_local_id():
    connected = [
        {"equipment_id": "equipment-a", "local_id": 0, "class_name": "DP800"},
        {"equipment_id": "equipment-b", "local_id": 1, "class_name": "DP800"},
    ]

    resolved = MainTestWindow._resolve_connected_equipment(
        {"equipment_id": "equipment-b", "local_id": 0, "class_name": "DP800"},
        connected,
    )

    assert resolved["local_id"] == 1


def test_assignment_resolution_rejects_class_mismatch():
    connected = [{"equipment_id": "equipment-a", "local_id": 0, "class_name": "DP800"}]

    assert MainTestWindow._resolve_connected_equipment(
        {"equipment_id": "equipment-a", "local_id": 0, "class_name": "DM3000"},
        connected,
    ) is None


def test_assignment_resolution_rejects_missing_stable_equipment_id():
    connected = [{"equipment_id": "equipment-a", "local_id": 0, "class_name": "DP800"}]

    assert MainTestWindow._resolve_connected_equipment(
        {"local_id": 0, "class_name": "DP800"},
        connected,
    ) is None


def test_instrument_channel_metadata_is_canonical_and_one_based_for_multi_channel_devices():
    class Device:
        num_channels = 2
        start_channel = 0

    assert equipment.get_instrument_channels("custom", Device()) == [1, 2]


def test_instrument_channel_metadata_uses_zero_for_singleton_devices():
    assert equipment.get_instrument_channels("custom", object()) == [0]


def test_a2d_daq_driver_translates_canonical_channel_to_zero_based_hardware_channel():
    class Instrument:
        def __init__(self):
            self.queries = []

        def query(self, command):
            self.queries.append(command)
            return "1200"

    daq = A2D_DAQ.__new__(A2D_DAQ)
    daq.inst = Instrument()
    daq.config_dict = {0: {"Input_Type": "voltage", "Voltage_Scaling": 1}}
    daq.select_channel(1)

    assert daq.measure_voltage() == 1.2
    assert daq.inst.queries == ["INSTR:READ:ANA? (@0)"]
