from charge_discharge.conditions import StopReason, evaluate_end_condition
from charge_discharge.requirements import (
    equipment_requirements_for_cycle,
    equipment_requirements_for_plan,
)
from charge_discharge.profiles import CyclingSettings
from charge_discharge.measurement import CycleMeasurementAccumulator, MeasurementService
from charge_discharge.runner import CyclingControl
import queue
import pytest
import Templates


def _step(**overrides):
    step = {
        "cycle_type": "step",
        "drive_style": "current_a",
        "drive_value": 1.0,
        "drive_value_other": 4.2,
        "end_style": "time_s",
        "end_condition": "greater",
        "end_value": 10,
        "safety_min_voltage_v": 2.5,
        "safety_max_voltage_v": 4.3,
        "safety_min_current_a": -3.0,
        "safety_max_current_a": 3.0,
        "safety_max_time_s": 100,
    }
    step.update(overrides)
    return step


def test_end_condition_service_is_pure_and_returns_reason():
    data = {
        "Voltage": 3.7,
        "Current": 1.0,
        "Data_Timestamp_From_Step_Start": 11,
    }

    assert evaluate_end_condition(_step(), data) is StopReason.END_CONDITION
    assert evaluate_end_condition(_step(), data, stop_requested=True) is StopReason.END_REQUEST
    assert evaluate_end_condition(_step(), {**data, "Voltage": 2.0}) is StopReason.SAFETY


@pytest.mark.parametrize(
    ("end_style", "field", "below", "at", "above"),
    [
        ("time_s", "Data_Timestamp_From_Step_Start", 9.9, 10.0, 10.1),
        ("voltage_v", "Voltage", 3.9, 4.0, 4.1),
        ("current_a", "Current", 0.9, 1.0, 1.1),
    ],
)
def test_greater_end_condition_uses_configured_measurement_and_strict_boundary(
    end_style, field, below, at, above
):
    threshold = {
        "Current": 1.0,
        "Voltage": 4.0,
        "Data_Timestamp_From_Step_Start": 10.0,
    }[field]
    step = _step(end_style=end_style, end_value=threshold)
    data = {
        "Voltage": 3.7,
        "Current": 0.5,
        "Data_Timestamp_From_Step_Start": 5.0,
    }
    assert evaluate_end_condition(step, {**data, field: below}) is StopReason.NONE
    assert evaluate_end_condition(step, {**data, field: threshold}) is StopReason.NONE
    assert evaluate_end_condition(step, {**data, field: above}) is StopReason.END_CONDITION


@pytest.mark.parametrize(
    ("end_style", "field", "at", "below", "above"),
    [
        ("time_s", "Data_Timestamp_From_Step_Start", 10.0, 9.9, 10.1),
        ("voltage_v", "Voltage", 3.0, 2.9, 3.1),
        ("current_a", "Current", 0.5, 0.4, 0.6),
    ],
)
def test_lesser_end_condition_uses_configured_measurement_and_strict_boundary(
    end_style, field, at, below, above
):
    step = _step(end_style=end_style, end_condition="lesser", end_value=at)
    data = {
        "Voltage": 3.7,
        "Current": 0.8,
        "Data_Timestamp_From_Step_Start": 5.0,
    }

    assert evaluate_end_condition(step, {**data, field: above}) is StopReason.NONE
    assert evaluate_end_condition(step, {**data, field: at}) is StopReason.NONE
    assert evaluate_end_condition(step, {**data, field: below}) is StopReason.END_CONDITION


def test_cycle_end_time_waits_until_threshold_and_includes_equality():
    step = _step(cycle_end_time_s=20.0, end_value=30.0)
    data = {
        "Voltage": 3.7,
        "Current": 1.0,
        "Data_Timestamp_From_Step_Start": 0.0,
    }

    assert evaluate_end_condition(step, data) is StopReason.NONE
    assert evaluate_end_condition(
        step, {**data, "Data_Timestamp_From_Step_Start": 19.9}
    ) is StopReason.NONE
    assert evaluate_end_condition(
        step, {**data, "Data_Timestamp_From_Step_Start": 20.0}
    ) is StopReason.CYCLE_END


def test_cycle_end_voltage_includes_cutoff_equality():
    step = _step(cycle_end_voltage_v=3.0)
    data = {
        "Voltage": 3.1,
        "Current": 1.0,
        "Data_Timestamp_From_Step_Start": 0.0,
    }

    assert evaluate_end_condition(step, data) is StopReason.NONE
    assert evaluate_end_condition(step, {**data, "Voltage": 3.0}) is StopReason.CYCLE_END


def test_equipment_requirements_are_calculated_for_nested_plan():
    charge = _step(drive_value=1.0)
    discharge = _step(drive_value=-1.0)
    plan = [[charge], [discharge]]

    assert equipment_requirements_for_cycle([charge]) == {"psu": True, "eload": False}
    assert equipment_requirements_for_plan(plan) == {"psu": True, "eload": True}


def test_profile_conversion_is_available_from_profiles_module():
    settings = Templates.ChargeSettings().settings
    settings["charge_a"] = 2.0
    settings["charge_end_v"] = 4.1

    steps = CyclingSettings().convert_charge_settings_to_steps(settings)

    assert len(steps) == 1
    assert steps[0]["drive_style"] == "voltage_v"
    assert steps[0]["drive_value"] == 4.1
    assert steps[0]["drive_value_other"] == 2.0


def test_measurement_maps_internal_step_index_to_cycle_local_bdf_step_id():
    measurement = MeasurementService({}).read(step_index=0, current_time=1.0)
    assert measurement["Step ID"] == 1
    assert "Step_Index" not in measurement

    measurement = MeasurementService({}).read(step_index=2, current_time=1.0)
    assert measurement["Step ID"] == 3


def test_cycle_measurement_accumulator_preserves_directional_capacity_and_energy():
    accumulator = CycleMeasurementAccumulator()

    first = accumulator.update({"Data_Timestamp": 10.0, "Voltage": 4.0, "Current": 2.0})
    charging = accumulator.update({"Data_Timestamp": 11.0, "Voltage": 4.0, "Current": 2.0})
    discharging = accumulator.update({"Data_Timestamp": 13.0, "Voltage": 3.8, "Current": -1.0})

    assert first["Cycle Charging Capacity / Ah"] == 0.0
    assert charging["Cycle Charging Capacity / Ah"] == 2 / 3600
    assert charging["Cycle Discharging Capacity / Ah"] == 0.0
    assert discharging["Cycle Discharging Capacity / Ah"] == 2 / 3600
    assert discharging["Cycle Charging Energy / Wh"] == 8 / 3600
    assert discharging["Cycle Discharging Energy / Wh"] == 3.8 * 2 / 3600

    accumulator.reset()
    reset_values = accumulator.update({"Data_Timestamp": 20.0, "Voltage": 4.0, "Current": 1.0})
    assert reset_values["Cycle Charging Capacity / Ah"] == 0.0


def test_charge_discharge_worker_reports_setup_failure_to_application(monkeypatch):
    """A caught worker exception must reach the application as an error event."""

    def fail_to_connect(_assignment):
        raise RuntimeError("instrument owner is unavailable")

    monkeypatch.setattr(
        "charge_discharge.runner.eq.get_equipment_dict",
        fail_to_connect,
    )
    messages = queue.Queue()

    with pytest.raises(RuntimeError, match="instrument owner is unavailable"):
        CyclingControl().charge_discharge_control({}, data_out_queue=messages, input_dict={})

    message = messages.get(timeout=1)
    assert message["type"] == "error"
    assert message["data"]["worker"] == "Charge/discharge worker"
    assert message["data"]["exception_type"] == "RuntimeError"
    assert "instrument owner is unavailable" in message["data"]["message"]
