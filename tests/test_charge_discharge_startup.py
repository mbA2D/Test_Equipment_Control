"""Startup sampling behavior for charge/discharge steps."""

import charge_discharge.runner as runner
from charge_discharge.runner import CyclingControl


def test_driven_step_uses_a_short_bounded_startup_wait(monkeypatch):
    clock = [10.0]
    measurements = []
    written_rows = []

    def perf_counter():
        return clock[0]

    def sleep(duration):
        clock[0] += duration

    monkeypatch.setattr(runner.time, "perf_counter", perf_counter)
    monkeypatch.setattr(runner.time, "sleep", sleep)

    control = CyclingControl()
    control.start_step = lambda _settings: True
    control._check_instrument_health = lambda *_args, **_kwargs: None

    def measure_battery(*, step_index, current_time, **_kwargs):
        measurements.append(current_time)
        return {
            "Step ID": step_index + 1,
            "Data_Timestamp": current_time,
            "Unix_Timestamp": current_time,
            "Voltage": 3.7,
            "Current": 1.0,
        }

    control.measure_battery = measure_battery
    control.write_bdf_measurement = lambda data, **_kwargs: written_rows.append(data.copy())
    control.evaluate_end_condition = lambda *_args, **_kwargs: "end_condition"

    result = control.step_cell(
        {
            "cycle_display": "CC charge",
            "bdf_step_type": "CC_CHG",
            "drive_style": "current_a",
            "drive_value": 1.0,
            "drive_value_other": 4.2,
            "end_style": "time_s",
            "end_condition": "greater",
            "end_value": 30.0,
            "meas_log_int_s": 1.0,
            "safety_max_time_s": 40.0,
        }
    )

    assert result == "end_condition"
    assert len(measurements) == 1
    assert 10.5 <= measurements[0] < 10.51
    elapsed_s = written_rows[0]["Data_Timestamp_From_Step_Start"]
    assert 0.5 <= elapsed_s < 0.51
