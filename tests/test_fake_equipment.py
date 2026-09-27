import pytest

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
    link = FakeBatteryLink()
    psu = Fake_PSU()
    dmm = Fake_DMM()
    psu.attach_battery_link(link)
    dmm.attach_battery_link(link)

    psu.set_voltage(3.7)
    psu.set_current(1.5)
    psu.toggle_output(True)

    assert psu.measure_voltage() == pytest.approx(dmm.measure_voltage())
    assert psu.measure_current() == 1.5
    assert psu.measure_power() == pytest.approx(psu.measure_voltage() * 1.5)
