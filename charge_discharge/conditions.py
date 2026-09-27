"""Pure stop-condition evaluation for battery test steps."""

from enum import Enum
from typing import Any, Mapping


class StopReason(str, Enum):
    NONE = "none"
    END_CONDITION = "end_condition"
    CYCLE_END = "cycle_end_condition"
    SAFETY = "safety_condition"
    END_REQUEST = "end_request"
    INVALID_SETTINGS = "settings"


def evaluate_end_condition(
    step: Mapping[str, Any],
    data: Mapping[str, Any],
    stop_requested: bool = False,
) -> StopReason:
    """Return the reason a step should stop.

    This function deliberately has no queue, hardware, or file-system
    dependencies. The runner owns side effects such as logging a safety event.
    """
    if stop_requested:
        return StopReason.END_REQUEST

    voltage = data["Voltage"]
    current = data["Current"]
    elapsed = data["Data_Timestamp_From_Step_Start"]

    if voltage < step["safety_min_voltage_v"]:
        return StopReason.SAFETY
    if voltage > step["safety_max_voltage_v"]:
        return StopReason.SAFETY
    if current < step["safety_min_current_a"]:
        return StopReason.SAFETY
    if current > step["safety_max_current_a"]:
        return StopReason.SAFETY
    if step["safety_max_time_s"] > 0 and elapsed > step["safety_max_time_s"]:
        return StopReason.SAFETY

    cycle_end_voltage = step.get("cycle_end_voltage_v")
    if cycle_end_voltage is not None and voltage <= cycle_end_voltage:
        return StopReason.CYCLE_END

    cycle_end_time = step.get("cycle_end_time_s")
    if cycle_end_time is not None and elapsed <= cycle_end_time:
        return StopReason.CYCLE_END

    comparator_name = {
        "current_a": "Current",
        "voltage_v": "Voltage",
        "time_s": "Data_Timestamp_From_Step_Start",
    }.get(step["end_style"])
    if comparator_name is None:
        return StopReason.INVALID_SETTINGS

    comparator = data[comparator_name]
    end_value = step["end_value"]
    if step["end_condition"] == "greater" and comparator > end_value:
        return StopReason.END_CONDITION

    if step["end_condition"] == "lesser":
        # During CV charging, the current endpoint is valid only after the
        # cell has reached the requested voltage.
        if (
            step["end_style"] == "current_a"
            and step["drive_style"] == "voltage_v"
            and end_value > 0
        ):
            if voltage > 0.98 * step["drive_value"] and comparator < end_value:
                return StopReason.END_CONDITION
        elif comparator < end_value:
            return StopReason.END_CONDITION

    if step["end_condition"] not in {"greater", "lesser"}:
        return StopReason.INVALID_SETTINGS
    return StopReason.NONE
