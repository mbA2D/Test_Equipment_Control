"""Pre-run checks against rated operating limits of assigned instruments."""

from collections.abc import Mapping
from math import isfinite
from typing import Any


class EquipmentLimitError(ValueError):
    """Raised when a profile cannot be validated against assigned hardware."""


def validate_profile_equipment_limits(
    profile: Mapping[str, Any],
    equipment_by_role: Mapping[str, Mapping[str, Any] | None],
) -> None:
    """Reject driven steps that exceed the rated limits of their assigned device.

    ``equipment_by_role`` contains connected-device metadata, including the
    driver-reported ``rated_limits`` mapping. Built-in fake equipment is
    excluded because it has no physical instrument rating.
    """

    cycles = profile.get("settings_cycle_list_step_list", [])
    for cycle_index, steps in enumerate(cycles, start=1):
        for step_index, step in enumerate(steps, start=1):
            role, voltage_v, current_a = _driven_equipment(step)
            if role is None:
                continue

            device = equipment_by_role.get(role)
            if device is None:
                raise EquipmentLimitError(
                    f"Cycle {cycle_index}, step {step_index} ({step['cycle_display']}) "
                    f"requires an assigned {role} with rated limits"
                )
            if device.get("is_fake"):
                continue

            limits = device.get("rated_limits")
            model = device.get("eq_idn") or device.get("class_name") or role
            if not isinstance(limits, Mapping):
                raise EquipmentLimitError(
                    f"Cannot start cycle {cycle_index}, step {step_index} "
                    f"({step['cycle_display']}): {model} does not report rated limits"
                )

            max_voltage = _rated_limit(limits, "max_voltage_v", model, cycle_index, step_index)
            max_current = _rated_limit(limits, "max_current_a", model, cycle_index, step_index)
            max_power = _rated_limit(limits, "max_power_w", model, cycle_index, step_index)

            _check_limit(
                voltage_v,
                max_voltage,
                "voltage",
                "V",
                model,
                cycle_index,
                step_index,
                step["cycle_display"],
            )
            _check_limit(
                current_a,
                max_current,
                "current",
                "A",
                model,
                cycle_index,
                step_index,
                step["cycle_display"],
            )

            if role == "psu":
                safety_current = max(float(step["safety_max_current_a"]), current_a)
            else:
                safety_current = max(abs(float(step["safety_min_current_a"])), current_a)
            safety_voltage = max(float(step["safety_max_voltage_v"]), voltage_v)
            envelope_power = safety_voltage * safety_current
            _check_limit(
                envelope_power,
                max_power,
                "voltage-current safety envelope power",
                "W",
                model,
                cycle_index,
                step_index,
                step["cycle_display"],
            )

            if role == "eload":
                safety_current_bound = abs(float(step["safety_min_current_a"]))
            else:
                safety_current_bound = max(float(step["safety_max_current_a"]), 0.0)
            _check_limit(
                safety_voltage,
                max_voltage,
                "safety maximum voltage",
                "V",
                model,
                cycle_index,
                step_index,
                step["cycle_display"],
            )
            _check_limit(
                safety_current_bound,
                max_current,
                "directional safety current limit",
                "A",
                model,
                cycle_index,
                step_index,
                step["cycle_display"],
            )


def _driven_equipment(step: Mapping[str, Any]) -> tuple[str | None, float, float]:
    """Return active device role and non-negative voltage/current requirements."""

    drive_style = step["drive_style"]
    drive_value = float(step["drive_value"])
    drive_value_other = float(step["drive_value_other"])
    if drive_style == "none":
        return None, 0.0, 0.0
    if drive_style == "current_a":
        if drive_value > 0:
            return "psu", drive_value_other, drive_value
        if drive_value < 0:
            return "eload", float(step["safety_max_voltage_v"]), abs(drive_value)
        return None, 0.0, 0.0
    if drive_style == "voltage_v":
        if drive_value_other >= 0:
            return "psu", drive_value, drive_value_other
        return "eload", float(step["safety_max_voltage_v"]), abs(drive_value_other)
    return None, 0.0, 0.0


def _rated_limit(
    limits: Mapping[str, Any],
    name: str,
    model: str,
    cycle_index: int,
    step_index: int,
) -> float:
    value = limits.get(name)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value <= 0
    ):
        raise EquipmentLimitError(
            f"Cannot start cycle {cycle_index}, step {step_index}: {model} "
            f"has no valid {name} rating"
        )
    return float(value)


def _check_limit(
    requested: float,
    rated: float,
    quantity: str,
    unit: str,
    model: str,
    cycle_index: int,
    step_index: int,
    display: str,
) -> None:
    if requested > rated:
        raise EquipmentLimitError(
            f"Cycle {cycle_index}, step {step_index} ({display}) exceeds {model} "
            f"{quantity} limit: profile requires {requested:g} {unit}; "
            f"rated maximum is {rated:g} {unit}"
        )
