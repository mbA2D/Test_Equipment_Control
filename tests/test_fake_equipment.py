import pytest

from battery_app.battery_model_simple import BatteryCellWorldModel
from battery_app.simulation import FakeBatteryLink, FakeInstrumentNotAttachedError
from lab_equipment.DMM_Fake import Fake_DMM
from lab_equipment.Eload_Fake import Fake_Eload
from lab_equipment.PSU_Fake import Fake_PSU


def test_fake_instruments_reject_operations_without_a_battery_link():
    with pytest.raises(FakeInstrumentNotAttachedError):
        Fake_DMM().measure_voltage()
    with pytest.raises(FakeInstrumentNotAttachedError):
        Fake_Eload().set_current(2.5)
    with pytest.raises(FakeInstrumentNotAttachedError):
        Fake_PSU().set_voltage(3.7)


def test_fake_eload_sets_and_measures_current_through_the_battery_link():
    link = FakeBatteryLink()
    eload = Fake_Eload()
    dmm = Fake_DMM()
    eload.attach_battery_link(link)
    dmm.attach_battery_link(link)

    eload.set_current(2.5)
    eload.toggle_output(True)

    assert eload.measure_current() == -2.5
    assert dmm.measure_voltage() == pytest.approx(eload.measure_voltage())


def test_fake_psu_sets_and_measures_voltage_through_the_battery_link():
    link = FakeBatteryLink(BatteryCellWorldModel(initial_soc=0.5))
    psu = Fake_PSU()
    dmm = Fake_DMM()
    psu.attach_battery_link(link)
    dmm.attach_battery_link(link)

    psu.set_voltage(4.2)
    psu.set_current(1.5)
    psu.toggle_output(True)

    assert psu.measure_voltage() == pytest.approx(dmm.measure_voltage())
    assert psu.measure_current() == 1.5
    assert psu.measure_power() == pytest.approx(psu.measure_voltage() * 1.5)


@pytest.mark.parametrize("voltage_setpoint_v", [0.0, 3.6])
def test_fake_psu_does_not_charge_when_voltage_limit_is_below_cell_ocv(
    voltage_setpoint_v,
):
    model = BatteryCellWorldModel(initial_soc=0.5)
    link = FakeBatteryLink(model)
    psu = Fake_PSU()
    psu.attach_battery_link(link)

    psu.set_current(1.0)
    psu.set_voltage(voltage_setpoint_v)
    psu.toggle_output(True)
    link.advance(dt_s=60.0)

    if voltage_setpoint_v > 0.0:
        assert voltage_setpoint_v < model.open_circuit_voltage_v
    else:
        assert voltage_setpoint_v == 0.0
    assert psu.measure_current() == 0.0
    assert model.state.soc == pytest.approx(0.5)


def test_fake_psu_voltage_limit_reduces_current_below_current_setting():
    model = BatteryCellWorldModel(initial_soc=0.5)
    link = FakeBatteryLink(model)
    psu = Fake_PSU()
    psu.attach_battery_link(link)
    voltage_setpoint_v = model.open_circuit_voltage_v + 0.02

    psu.set_current(10.0)
    psu.set_voltage(voltage_setpoint_v)
    psu.toggle_output(True)

    assert psu.measure_current() == pytest.approx(0.5, abs=1e-3)
    assert psu.measure_voltage() == pytest.approx(voltage_setpoint_v, abs=1e-3)
