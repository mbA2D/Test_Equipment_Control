import pytest

from lab_equipment.PSU_HP6632B import HP6632B


class FakeInstrument:
    def __init__(self):
        self.writes = []
        self.queries = {
            "OUTP?": "1",
            "MEAS:VOLT?": "12.5",
            "MEAS:CURR?": "-2.0",
        }

    def write(self, command):
        self.writes.append(command)

    def query(self, command):
        return self.queries[command]


def make_device():
    device = HP6632B.__new__(HP6632B)
    device.inst = FakeInstrument()
    return device


def test_rejects_negative_or_out_of_range_voltage():
    device = make_device()

    with pytest.raises(ValueError):
        device.set_voltage(-0.001)
    with pytest.raises(ValueError):
        device.set_voltage(20.001)
    assert device.inst.writes == []


def test_output_forces_normal_relay_polarity():
    device = make_device()

    device.toggle_output(True)

    assert device.inst.writes == ["OUTP:REL:POL NORM", "OUTP ON"]


def test_metering_preserves_sink_current_sign():
    device = make_device()

    assert device.measure_voltage() == 12.5
    assert device.measure_current() == -2.0
    assert device.measure_power() == -25.0


def test_equipment_registry_exposes_source_and_load_roles():
    import equipment

    assert "HP6632B" in equipment.powerSupplies.part_numbers
    assert "HP6632B" not in equipment.eLoads.part_numbers
    assert "A2D_POWER_BOARD" in equipment.powerSupplies.part_numbers
    assert "A2D_POWER_BOARD" not in equipment.smus.part_numbers
    assert "HP6632B" in equipment.get_capable_equipment("can_sink_current")
    assert "HP6632B" in equipment.get_capable_equipment("can_measure_voltage")
    assert equipment.get_capable_equipment(
        "can_source_voltage", "can_sink_current"
    ) == ["HP6632B", "A2D_POWER_BOARD"]
