import pytest

from battery_app.identity import new_profile_id, profile_version
from battery_app.profile_validation import (
    ProfileValidationError,
    validate_profile_configuration,
)


def _configuration():
    configuration = {
        "profile_schema_version": 1,
        "profile_id": new_profile_id(),
        "profile_name": "Rest profile",
        "eq_req_dict": {"psu": False, "eload": False},
        "settings_cycle_list_step_list": [[{
            "cycle_type": "step",
            "cycle_display": "Rest",
            "drive_style": "none",
            "drive_value": 0,
            "drive_value_other": 0,
            "end_style": "time_s",
            "end_condition": "greater",
            "end_value": 10,
            "meas_log_int_s": 1,
            "safety_min_voltage_v": 2.45,
            "safety_max_voltage_v": 4.25,
            "safety_min_current_a": -10,
            "safety_max_current_a": 10,
            "safety_max_time_s": 100,
        }]],
    }
    configuration["profile_version"] = profile_version(configuration)
    return configuration


def test_validator_requires_identity_and_recalculates_requirements():
    configuration = _configuration()
    configuration["settings_cycle_list_step_list"][0][0].update({
        "cycle_display": "Charge",
        "drive_style": "voltage_v",
        "drive_value": 4.2,
        "drive_value_other": 1.0,
        "end_style": "current_a",
        "end_value": 0.1,
    })
    configuration["eq_req_dict"] = {"psu": False, "eload": True}
    configuration["profile_version"] = profile_version(configuration)

    validated = validate_profile_configuration(configuration)

    assert validated["profile_id"].startswith("profile-")
    assert validated["profile_version"] == profile_version(validated)
    assert validated["eq_req_dict"] == {"psu": True, "eload": False}


def test_profile_revision_requires_a_new_version():
    first = validate_profile_configuration(_configuration())
    changed_configuration = {
        **first,
        "settings_cycle_list_step_list": [[{
            **first["settings_cycle_list_step_list"][0][0],
            "end_value": 20,
        }]],
    }

    with pytest.raises(ProfileValidationError, match="does not match"):
        validate_profile_configuration(changed_configuration)

    changed_configuration["profile_version"] = profile_version(changed_configuration)
    changed = validate_profile_configuration(changed_configuration)

    assert changed["profile_id"] == first["profile_id"]
    assert changed["profile_version"] != first["profile_version"]


def test_validator_rejects_profiles_without_identity():
    configuration = _configuration()
    del configuration["profile_id"]

    with pytest.raises(ProfileValidationError, match="profile_id"):
        validate_profile_configuration(configuration)


def test_validator_requires_profile_schema_and_name():
    configuration = _configuration()
    del configuration["profile_schema_version"]

    with pytest.raises(ProfileValidationError, match="profile_schema_version is required"):
        validate_profile_configuration(configuration)

    configuration = _configuration()
    del configuration["profile_name"]

    with pytest.raises(ProfileValidationError, match="profile_name"):
        validate_profile_configuration(configuration)


def test_validator_rejects_unknown_profile_and_step_fields():
    configuration = _configuration()
    configuration["profile_notes"] = "not in the contract"

    with pytest.raises(ProfileValidationError, match="unsupported fields"):
        validate_profile_configuration(configuration)

    configuration = _configuration()
    configuration["settings_cycle_list_step_list"][0][0]["typo"] = 1
    configuration["profile_version"] = profile_version(configuration)

    with pytest.raises(ProfileValidationError, match="unsupported fields"):
        validate_profile_configuration(configuration)


def test_validator_rejects_gui_owned_run_context():
    configuration = _configuration()
    configuration["directory"] = "D:/shared-test-data"

    with pytest.raises(ProfileValidationError, match="GUI-owned run context"):
        validate_profile_configuration(configuration)


def test_validator_rejects_incomplete_steps():
    configuration = _configuration()
    del configuration["settings_cycle_list_step_list"][0][0]["safety_max_time_s"]

    with pytest.raises(ProfileValidationError, match="safety_max_time_s"):
        validate_profile_configuration(configuration)
