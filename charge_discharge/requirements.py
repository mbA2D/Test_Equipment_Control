"""Determine which source/load equipment a test plan requires."""

from typing import Any, Iterable, Mapping

import Templates


def equipment_requirements_for_step(step: Mapping[str, Any]) -> dict[str, bool]:
    requirements = {"psu": False, "eload": False}
    if step["drive_style"] == "current_a":
        value = step["drive_value"]
    elif step["drive_style"] == "voltage_v":
        value = step["drive_value_other"]
    else:
        value = 0

    requirements["psu"] = value > 0
    requirements["eload"] = value < 0
    return requirements


def equipment_requirements_for_cycle(settings: Iterable[Mapping[str, Any]]) -> dict[str, bool]:
    requirements = {"psu": False, "eload": False}
    cycle_requirements = Templates.CycleTypes.cycle_requirements
    for step in settings:
        if step["cycle_type"] == "step":
            current = equipment_requirements_for_step(step)
        else:
            current = cycle_requirements[step["cycle_type"]]
            current = {
                "psu": current["supply_req"],
                "eload": current["load_req"],
            }
        requirements["psu"] |= current["psu"]
        requirements["eload"] |= current["eload"]
    return requirements


def equipment_requirements_for_plan(
    cycles: Iterable[Iterable[Mapping[str, Any]]],
) -> dict[str, bool]:
    requirements = {"psu": False, "eload": False}
    for cycle in cycles:
        current = equipment_requirements_for_cycle(cycle)
        requirements["psu"] |= current["psu"]
        requirements["eload"] |= current["eload"]
    return requirements
