import pytest

from battery_app.equipment_limits import (
    EquipmentLimitError,
    validate_profile_equipment_limits,
)


def _step(**overrides):
    step = {
        "cycle_type": "step",
        "cycle_display": "Charge",
        "bdf_step_type": "CC_CHG",
        "drive_style": "current_a",
        "drive_value": 2.0,
        "drive_value_other": 4.2,
        "end_style": "time_s",
        "end_condition": "greater",
        "end_value": 10.0,
        "meas_log_int_s": 1.0,
        "safety_min_voltage_v": 2.5,
        "safety_max_voltage_v": 4.3,
        "safety_min_current_a": -5.0,
        "safety_max_current_a": 3.0,
        "safety_max_time_s": 60.0,
    }
    step.update(overrides)
    return step


def _profile(step):
    return {"settings_cycle_list_step_list": [[step]]}


def _equipment(role, limits, model="Test instrument"):
    return {
        role: {
            "class_name": "Test driver",
            "eq_idn": model,
            "rated_limits": limits,
            "is_fake": False,
        }
    }


def test_pre_run_limits_accept_profile_within_siglent_ratings():
    validate_profile_equipment_limits(
        _profile(_step()),
        _equipment(
            "psu",
            {"max_voltage_v": 16.0, "max_current_a": 8.0, "max_power_w": 128.0},
            "Siglent SPD1168X",
        ),
    )


def test_pre_run_limits_reject_safety_current_above_psu_rating():
    with pytest.raises(EquipmentLimitError, match="rated maximum is 8 A"):
        validate_profile_equipment_limits(
            _profile(_step(safety_max_current_a=9.0)),
            _equipment(
                "psu",
                {"max_voltage_v": 16.0, "max_current_a": 8.0, "max_power_w": 128.0},
                "Siglent SPD1168X",
            ),
        )


def test_pre_run_limits_reject_electronic_load_power_envelope():
    discharge = _step(
        cycle_display="Discharge",
        bdf_step_type="CC_DCH",
        drive_value=-10.0,
        drive_value_other=0.0,
        safety_max_voltage_v=30.0,
        safety_min_current_a=-10.0,
        safety_max_current_a=5.0,
    )
    with pytest.raises(EquipmentLimitError, match="power limit.*300 W.*250 W"):
        validate_profile_equipment_limits(
            _profile(discharge),
            _equipment(
                "eload",
                {"max_voltage_v": 120.0, "max_current_a": 60.0, "max_power_w": 250.0},
                "B&K 8601",
            ),
        )


def test_pre_run_limits_fail_closed_for_unrated_physical_equipment():
    with pytest.raises(EquipmentLimitError, match="does not report rated limits"):
        validate_profile_equipment_limits(
            _profile(_step()),
            _equipment("psu", None, "Unknown physical PSU"),
        )


def test_pre_run_limits_skip_fake_equipment_ratings():
    validate_profile_equipment_limits(
        _profile(_step()),
        {
            "psu": {
                "class_name": "Fake Test PSU",
                "eq_idn": "Fake Test PSU",
                "rated_limits": None,
                "is_fake": True,
            }
        },
    )
