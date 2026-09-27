"""Validation and normalization for persisted battery-test profiles.

The GUI creates only a small subset of the profile language.  Imported
profiles use the same normalized step contract so that the execution engine
does not need to know whether a profile came from a widget or a JSON file.
"""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from collections.abc import Mapping
from typing import Any

from battery_app.identity import profile_version


REQUIRED_STEP_FIELDS = frozenset({
    "cycle_type",
    "cycle_display",
    "drive_style",
    "drive_value",
    "drive_value_other",
    "end_style",
    "end_condition",
    "end_value",
    "meas_log_int_s",
    "safety_min_voltage_v",
    "safety_max_voltage_v",
    "safety_min_current_a",
    "safety_max_current_a",
    "safety_max_time_s",
})

OPTIONAL_STEP_FIELDS = frozenset({
    "cycle_end_voltage_v",
    "cycle_end_time_s",
})
PROFILE_FIELDS = frozenset({
    "profile_schema_version",
    "profile_id",
    "profile_version",
    "profile_name",
    "settings_cycle_list_step_list",
    # Derived in memory and tolerated only so validation can be repeated.
    "eq_req_dict",
})

_DRIVE_STYLES = frozenset({"current_a", "voltage_v", "none"})
_END_STYLES = frozenset({"time_s", "current_a", "voltage_v"})
_END_CONDITIONS = frozenset({"greater", "lesser"})
PROFILE_SCHEMA_VERSION = 1
RUN_CONTEXT_FIELDS = frozenset({"cell_name", "directory", "institution_code"})


class ProfileValidationError(ValueError):
    """Raised when a persisted profile cannot be safely executed."""


def validate_profile_configuration(
    configuration: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a validated profile without changing its identity.

    Profile creation and editing calculate identity before this function is
    called.  Imported profiles must contain both identity fields, and a stale
    version is rejected rather than silently revised. ``eq_req_dict`` is
    deliberately ignored if supplied by a file and recalculated from the
    validated steps.
    """

    if not isinstance(configuration, Mapping):
        raise ProfileValidationError("Profile must be a JSON object")

    result = deepcopy(dict(configuration))
    unexpected_run_context = sorted(RUN_CONTEXT_FIELDS & result.keys())
    if unexpected_run_context:
        raise ProfileValidationError(
            "Profile must not contain GUI-owned run context: "
            + ", ".join(unexpected_run_context)
        )
    unexpected_fields = sorted(set(result) - PROFILE_FIELDS)
    if unexpected_fields:
        raise ProfileValidationError(
            "Profile contains unsupported fields: " + ", ".join(unexpected_fields)
        )
    if "profile_schema_version" not in result:
        raise ProfileValidationError("profile_schema_version is required")
    schema_version = result["profile_schema_version"]
    if schema_version != PROFILE_SCHEMA_VERSION:
        raise ProfileValidationError(
            f"Unsupported profile_schema_version: {schema_version!r}"
        )
    result["profile_schema_version"] = PROFILE_SCHEMA_VERSION

    profile_id = result.get("profile_id")
    _require_non_empty_string(result, "profile_id")
    if not isinstance(profile_id, str):
        raise ProfileValidationError("profile_id must be a string")
    _require_non_empty_string(result, "profile_version")
    if not isinstance(result["profile_version"], str):
        raise ProfileValidationError("profile_version must be a string")
    _require_non_empty_string(result, "profile_name")

    cycles = result.get("settings_cycle_list_step_list")
    if not isinstance(cycles, list) or not cycles:
        raise ProfileValidationError(
            "settings_cycle_list_step_list must contain at least one cycle"
        )

    normalized_cycles: list[list[dict[str, Any]]] = []
    for cycle_index, cycle in enumerate(cycles, start=1):
        if not isinstance(cycle, list) or not cycle:
            raise ProfileValidationError(
                f"cycle {cycle_index} must contain at least one step"
            )
        normalized_cycles.append([
            _validate_step(step, cycle_index, step_index)
            for step_index, step in enumerate(cycle, start=1)
        ])

    result["settings_cycle_list_step_list"] = normalized_cycles
    expected_version = profile_version(result)
    if result["profile_version"] != expected_version:
        raise ProfileValidationError(
            "profile_version does not match the profile settings; revise the profile before importing"
        )
    # Import lazily because ``charge_discharge`` exposes the runner from its
    # package initializer and this module is also imported by the GUI boundary.
    from charge_discharge.requirements import equipment_requirements_for_plan

    result["eq_req_dict"] = equipment_requirements_for_plan(normalized_cycles)
    return result


def profile_payload(configuration: Mapping[str, Any]) -> dict[str, Any]:
    """Return only profile fields suitable for JSON persistence."""
    result = deepcopy(dict(configuration))
    for field in ("cell_name", "directory", "institution_code", "eq_req_dict"):
        result.pop(field, None)
    return result


def execution_configuration(
    profile: Mapping[str, Any],
    *,
    cell_name: str,
    directory: str,
) -> dict[str, Any]:
    """Combine a validated profile with GUI-owned per-run context."""
    if not isinstance(cell_name, str) or not cell_name.strip():
        raise ProfileValidationError("cell_name must be a non-empty string")
    if not isinstance(directory, str) or not directory.strip():
        raise ProfileValidationError("directory must be a non-empty string")
    result = deepcopy(dict(profile))
    result["cell_name"] = cell_name.strip().replace(" ", "_")
    result["directory"] = directory.strip()
    return result


def _validate_step(
    step: Any,
    cycle_index: int,
    step_index: int,
) -> dict[str, Any]:
    if not isinstance(step, Mapping):
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} must be a JSON object"
        )

    result = deepcopy(dict(step))
    unexpected_fields = sorted(
        set(result) - REQUIRED_STEP_FIELDS - OPTIONAL_STEP_FIELDS
    )
    if unexpected_fields:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} contains unsupported fields: "
            + ", ".join(unexpected_fields)
        )
    missing = sorted(REQUIRED_STEP_FIELDS - result.keys())
    if missing:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} is missing: {', '.join(missing)}"
        )

    if result["cycle_type"] != "step":
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} must use cycle_type 'step'"
        )
    _require_non_empty_string(result, "cycle_display", cycle_index, step_index)

    if result["drive_style"] not in _DRIVE_STYLES:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} has an invalid drive_style"
        )
    if result["end_style"] not in _END_STYLES:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} has an invalid end_style"
        )
    if result["end_condition"] not in _END_CONDITIONS:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} has an invalid end_condition"
        )

    numeric_fields = REQUIRED_STEP_FIELDS - {
        "cycle_type",
        "cycle_display",
        "drive_style",
        "end_style",
        "end_condition",
    }
    numeric_fields |= OPTIONAL_STEP_FIELDS & result.keys()
    for field in numeric_fields:
        _require_finite_number(result[field], field, cycle_index, step_index)

    if result["meas_log_int_s"] <= 0:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} requires meas_log_int_s > 0"
        )
    if result["safety_min_voltage_v"] >= result["safety_max_voltage_v"]:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} has invalid voltage safety limits"
        )
    if result["safety_min_current_a"] >= result["safety_max_current_a"]:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} has invalid current safety limits"
        )
    # TODO: Reject voltage and current drive setpoints outside their matching
    # safety envelopes. A voltage-driven step must also validate its current
    # limit (drive_value_other) against the current safety limits.
    # TODO: Reject voltage/current end thresholds outside their matching safety
    # envelopes, and a time end condition longer than an enabled safety timeout.
    # Such settings can otherwise terminate only through a safety condition.
    if result["end_style"] == "time_s" and result["end_value"] <= 0:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} requires a positive time end_value"
        )
    if result["drive_style"] == "none" and result["drive_value"] != 0:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} must use drive_value 0 when undriven"
        )
    if result["drive_style"] == "voltage_v" and result["drive_value"] < 0:
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} cannot use negative voltage"
        )

    return result


def _require_non_empty_string(
    mapping: Mapping[str, Any],
    field: str,
    cycle_index: int | None = None,
    step_index: int | None = None,
) -> None:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        location = (
            f"cycle {cycle_index}, step {step_index} "
            if cycle_index is not None else ""
        )
        raise ProfileValidationError(f"{location}{field} must be a non-empty string")


def _require_finite_number(
    value: Any,
    field: str,
    cycle_index: int,
    step_index: int,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ProfileValidationError(
            f"cycle {cycle_index}, step {step_index} field {field} must be finite numeric data"
        )
