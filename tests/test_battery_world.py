import pytest

from battery_app.battery_model_simple import BatteryCellWorldModel


def test_default_model_represents_full_lg_mj1_cell():
    cell = BatteryCellWorldModel()

    assert cell.parameters.capacity_ah == 3.5
    assert cell.state.soc == 1.0
    assert cell.open_circuit_voltage_v == pytest.approx(4.2)
    assert cell.state.temperature_c == 25.0
    assert cell.state.safety_state == "normal"


def test_discharge_reduces_soc_and_terminal_voltage():
    cell = BatteryCellWorldModel(initial_soc=0.5)

    state = cell.step(current_a=-3.5, dt_s=3600.0)

    assert state.soc == pytest.approx(0.0)
    assert state.terminal_voltage_v < cell.open_circuit_voltage_v
    assert state.charge_throughput_ah == pytest.approx(3.5)


def test_charge_increases_soc_and_resistive_voltage_rise():
    cell = BatteryCellWorldModel(initial_soc=0.5)

    state = cell.step(current_a=1.0, dt_s=60.0)

    assert state.soc > 0.5
    assert state.terminal_voltage_v > cell.open_circuit_voltage_v
    assert state.temperature_c > 25.0


def test_thermal_model_cools_at_rest():
    cell = BatteryCellWorldModel(initial_temperature_c=40.0)

    state = cell.step(current_a=0.0, dt_s=10.0)

    assert 25.0 < state.temperature_c < 40.0


def test_overcurrent_is_reported_without_hiding_the_requested_current():
    cell = BatteryCellWorldModel()

    state = cell.step(current_a=-11.0, dt_s=1.0)

    assert state.current_a == -11.0
    assert state.safety_state == "overdischarge_current"


def test_invalid_time_step_is_rejected():
    cell = BatteryCellWorldModel()

    with pytest.raises(ValueError, match="dt_s"):
        cell.step(current_a=0.0, dt_s=0.0)

