import pytest

from lab_equipment.Eload_BK8600 import BK8600
from lab_equipment.PSU_SPD1000 import SPD1000, SetpointException


class StubInstrument:
    def __init__(self, responses):
        self.responses = responses
        self.writes = []

    def query(self, command):
        return self.responses[command]

    def write(self, command):
        self.writes.append(command)


def test_bk8601_current_setpoint_is_read_back():
    device = object.__new__(BK8600)
    device.mode = "CURR"
    device.setpoint_readback_tolerances = {"current": 0.001, "voltage": 0.01}
    device.inst = StubInstrument({"CURR?": "1.25"})

    device.set_current(1.25)

    assert device.inst.writes == ["CURR:LEV 1.25"]
    device.inst = None


def test_bk8601_rejects_mismatched_current_readback():
    device = object.__new__(BK8600)
    device.mode = "CURR"
    device.setpoint_readback_tolerances = {"current": 0.001, "voltage": 0.01}
    device.inst = StubInstrument({"CURR?": "1.1"})

    with pytest.raises(RuntimeError, match="does not match"):
        device.set_current(1.25)
    device.inst = None


def test_bk8601_accepts_one_resolution_count_and_rejects_more():
    device = object.__new__(BK8600)
    device.setpoint_readback_tolerances = {"current": 0.001, "voltage": 0.01}

    device._verify_setpoint(1.251, 1.25, "current")
    with pytest.raises(RuntimeError, match="0.001 resolution allowance"):
        device._verify_setpoint(1.252, 1.25, "current")
    with pytest.raises(RuntimeError, match="0.01 resolution allowance"):
        device._verify_setpoint(4.02, 4.0, "voltage")


def test_bk8601_status_checks_output_mode_and_protection():
    device = object.__new__(BK8600)
    device.inst = StubInstrument({
        "INP?": "1",
        "STAT:QUES:COND?": "0",
        "FUNC?": "CURR",
    })

    assert device.check_status(expected_output=True, expected_mode="CURR") is None

    device.inst.responses["STAT:QUES:COND?"] = str(1 << 1)
    with pytest.raises(RuntimeError, match="overcurrent"):
        device.check_status(expected_output=True, expected_mode="CURR")
    device.inst = None


def test_spd1168x_status_reports_regulation_and_checks_output_and_errors():
    device = object.__new__(SPD1000)
    device.inst = StubInstrument({
        "SYST:STAT?": "0x0011",
        "SYST:ERR?": '+0,"No error"',
    })

    assert device.check_status(expected_output=True) is None

    device.inst.responses["SYST:ERR?"] = '-100,"Command error"'
    with pytest.raises(RuntimeError, match="Command error"):
        device.check_status(expected_output=True)

    device.inst.responses["SYST:ERR?"] = '+0,"No error"'
    with pytest.raises(RuntimeError, match="output is on"):
        device.check_status(expected_output=False)
    device.inst = None


def test_spd1168x_accepts_one_resolution_count_and_rejects_more():
    device = object.__new__(SPD1000)
    device.setpoint_readback_tolerances = {"voltage": 0.001, "current": 0.001}

    device._verify_setpoint(4.001, 4.0, "voltage")
    device._verify_setpoint(1.001, 1.0, "current")
    with pytest.raises(SetpointException, match="0.001 resolution allowance"):
        device._verify_setpoint(4.002, 4.0, "voltage")
    with pytest.raises(SetpointException, match="0.001 resolution allowance"):
        device._verify_setpoint(1.002, 1.0, "current")
