"""Pure conversion helpers for persisted battery-test profiles."""

import Templates


class CyclingSettings:
    """Convert profile dictionaries into executable step dictionaries."""

    def convert_rest_settings_to_steps(self, rest_settings, model_step_settings=None):
        step = model_step_settings or Templates.StepSettings()
        step.settings["cycle_display"] = rest_settings["cycle_display"]
        step.settings["drive_style"] = "none"
        step.settings["end_style"] = "time_s"
        step.settings["end_condition"] = "greater"
        step.settings["end_value"] = rest_settings["rest_time_min"] * 60
        step.settings["safety_min_voltage_v"] = rest_settings["safety_min_voltage_v"]
        step.settings["safety_max_voltage_v"] = rest_settings["safety_max_voltage_v"]
        step.settings["safety_min_current_a"] = rest_settings["safety_min_current_a"]
        step.settings["safety_max_current_a"] = rest_settings["safety_max_current_a"]
        step.settings["safety_max_time_s"] = rest_settings["safety_max_time_s"]
        return [step.settings]

    def convert_charge_settings_to_steps(self, charge_settings, model_step_settings=None):
        step = model_step_settings or Templates.StepSettings()
        step.settings["cycle_display"] = charge_settings["cycle_display"]
        step.settings["drive_style"] = "voltage_v"
        step.settings["drive_value"] = charge_settings["charge_end_v"]
        step.settings["drive_value_other"] = charge_settings["charge_a"]
        step.settings["end_style"] = "current_a"
        step.settings["end_condition"] = "lesser"
        step.settings["end_value"] = charge_settings["charge_end_a"]
        step.settings["safety_min_voltage_v"] = charge_settings["safety_min_voltage_v"]
        step.settings["safety_max_voltage_v"] = charge_settings["safety_max_voltage_v"]
        step.settings["safety_min_current_a"] = charge_settings["safety_min_current_a"]
        step.settings["safety_max_current_a"] = charge_settings["safety_max_current_a"]
        step.settings["safety_max_time_s"] = charge_settings["safety_max_time_s"]
        return [step.settings]

    def convert_discharge_settings_to_steps(self, discharge_settings, model_step_settings=None):
        step = model_step_settings or Templates.StepSettings()
        step.settings["cycle_display"] = discharge_settings["cycle_display"]
        step.settings["drive_style"] = "current_a"
        step.settings["drive_value"] = discharge_settings["discharge_a"]
        step.settings["end_style"] = "voltage_v"
        step.settings["end_condition"] = "lesser"
        step.settings["end_value"] = discharge_settings["discharge_end_v"]
        step.settings["safety_min_voltage_v"] = discharge_settings["safety_min_voltage_v"]
        step.settings["safety_max_voltage_v"] = discharge_settings["safety_max_voltage_v"]
        step.settings["safety_min_current_a"] = discharge_settings["safety_min_current_a"]
        step.settings["safety_max_current_a"] = discharge_settings["safety_max_current_a"]
        step.settings["safety_max_time_s"] = discharge_settings["safety_max_time_s"]
        return [step.settings]

    def convert_single_ir_settings_to_steps(self, ir_settings, model_step_settings=None):
        step = model_step_settings or Templates.StepSettings()
        step.settings["cycle_display"] = ir_settings["cycle_display"]
        step.settings["drive_style"] = "current_a"
        step.settings["drive_value_other"] = ir_settings["psu_voltage_if_pos_i"]
        step.settings["end_style"] = "time_s"
        step.settings["end_condition"] = "greater"
        step.settings["safety_min_current_a"] = ir_settings["safety_min_current_a"]
        step.settings["safety_max_current_a"] = ir_settings["safety_max_current_a"]
        step.settings["safety_min_voltage_v"] = ir_settings["safety_min_voltage_v"]
        step.settings["safety_max_voltage_v"] = ir_settings["safety_max_voltage_v"]
        step.settings["safety_max_time_s"] = ir_settings["safety_max_time_s"]

        first = step.settings.copy()
        second = step.settings.copy()
        first["drive_value"] = ir_settings["current_1_a"]
        second["drive_value"] = ir_settings["current_2_a"]
        first["end_value"] = ir_settings["time_1_s"]
        second["end_value"] = ir_settings["time_2_s"]
        return [first, second]

    def convert_repeated_ir_settings_to_steps(self, test_settings):
        step = Templates.StepSettings()
        max_time = max(test_settings["time_1_s"], test_settings["time_2_s"])
        step.settings["cycle_display"] = test_settings["cycle_display"]
        step.settings["drive_style"] = "current_a"
        step.settings["drive_value_other"] = test_settings["psu_voltage_if_pos_i"]
        step.settings["end_style"] = "time_s"
        step.settings["end_condition"] = "greater"
        step.settings["cycle_end_voltage_v"] = test_settings["cycle_end_voltage_v"]
        step.settings["safety_min_voltage_v"] = test_settings["safety_min_voltage_v"]
        step.settings["safety_max_voltage_v"] = test_settings["safety_max_voltage_v"]
        step.settings["safety_min_current_a"] = test_settings["safety_min_current_a"]
        step.settings["safety_max_current_a"] = test_settings["safety_max_current_a"]
        step.settings["safety_max_time_s"] = max_time * 1.75

        first = step.settings.copy()
        second = step.settings.copy()
        first["drive_value"] = test_settings["current_1_a"]
        second["drive_value"] = test_settings["current_2_a"]
        first["end_value"] = test_settings["time_1_s"]
        second["end_value"] = test_settings["time_2_s"]

        capacity_per_test_a_s = (
            test_settings["current_1_a"] * test_settings["time_1_s"]
            + test_settings["current_2_a"] * test_settings["time_2_s"]
        )
        total_capacity_a_s = test_settings["estimated_capacity_ah"] * 3600
        num_tests_required = int(abs(total_capacity_a_s / capacity_per_test_a_s))
        return [step for _ in range(num_tests_required) for step in (first, second)]
