import pytest

from charge_discharge.equipment_control import EquipmentController


class Device:
    def __init__(self, fail_zero=False, fail_off=False):
        self.fail_zero = fail_zero
        self.fail_off = fail_off
        self.calls = []

    def set_current(self, value):
        self.calls.append(("current", value))
        if self.fail_zero:
            raise RuntimeError("set-current failed")

    def toggle_output(self, enabled):
        self.calls.append(("output", enabled))
        if self.fail_off:
            raise RuntimeError("output-off failed")


class Relay:
    def __init__(self):
        self.calls = []

    def connect_eload(self, enabled):
        self.calls.append(("eload", enabled))

    def connect_psu(self, enabled):
        self.calls.append(("psu", enabled))


def test_disable_single_attempts_output_off_when_zero_setpoint_fails():
    device = Device(fail_zero=True)

    with pytest.raises(RuntimeError, match="set-current failed"):
        EquipmentController.disable_single(device)

    assert device.calls == [("current", 0), ("output", False)]


def test_disable_all_attempts_each_device_and_relay_after_failures():
    psu = Device(fail_off=True)
    eload = Device()
    relay = Relay()
    controller = EquipmentController({"psu": psu, "eload": eload, "relay_board": relay})

    with pytest.raises(RuntimeError, match="Safe equipment shutdown was incomplete"):
        controller.disable_all()

    assert ("output", False) in psu.calls
    assert ("output", False) in eload.calls
    assert relay.calls == [("eload", False), ("psu", False)]
