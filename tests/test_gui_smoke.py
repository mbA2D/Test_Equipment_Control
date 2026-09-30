

import equipment
from battery_app import ApplicationEvent, ChannelStatus
from battery_app.persistence import ConfigurationStore
from battery_app.profile_identity import main as profile_cli_main


def _fake_descriptor(local_id, eq_type, class_name):
    return {
        "local_id": local_id,
        "eq_type": eq_type,
        "eq_idn": class_name,
        "class_name": class_name,
        "res_id": "Fake",
        "setup_dict": {},
        "capabilities": list(equipment.EQUIPMENT_CAPABILITIES[class_name]),
    }


def _select_equipment(widget, role, connected_equipment, class_name):
    selector = widget.equipment_assignment._selectors[role]
    equipment_id = next(
        item["equipment_id"]
        for item in connected_equipment
        if item["class_name"] == class_name
    )
    for index in range(selector.count()):
        selected = selector.itemData(index)
        if isinstance(selected, dict) and selected.get("equipment_id") == equipment_id:
            selector.setCurrentIndex(index)
            return
    raise AssertionError(f"No {class_name} option for {role}")


def test_gui_start_button_runs_fake_assignment_to_bdf(qtbot, tmp_path):
    """Run the ordinary GUI Start test action through fake owners to BDF."""

    from battery_test import MainTestWindow

    window = MainTestWindow()
    qtbot.addWidget(window)
    try:
        window.data_directory_edit.setText(str(tmp_path))
        for local_id, eq_type, class_name in (
            (0, "psu", "Fake Test PSU"),
            (1, "eload", "Fake Test Eload"),
            (2, "dmm", "Fake Test DMM"),
            (3, "dmm", "Fake Test DMM"),
            (4, "dmm", "Fake Test DMM"),
        ):
            assert window.create_new_equipment(
                _fake_descriptor(local_id, eq_type, class_name)
            )

        widget = window.channel_widgets[0]
        widget.cell_name_edit.setText("SIMULATED_LG_MJ1")
        _select_equipment(widget, "psu", window.connected_equipment_list, "Fake Test PSU")
        _select_equipment(widget, "eload", window.connected_equipment_list, "Fake Test Eload")
        for role in ("dmm_v", "dmm_i", "dmm_t"):
            _select_equipment(widget, role, window.connected_equipment_list, "Fake Test DMM")
        widget.equipment_assignment.apply_button.click()

        qtbot.waitUntil(
            lambda: window.channel_states[0].equipment_assignment is not None,
            timeout=3000,
        )
        qtbot.wait(100)
        assert not window.channel_states[0].is_idle_process_running
        assignment = window.channel_states[0].equipment_assignment
        assert assignment["psu"]["res_id"]["queue_in"] is not None
        assert assignment["psu"]["class_name"] == "Fake Test PSU"

        editor = widget.profile_editor
        editor.profile_type.setCurrentText("Discharge")
        editor.primary_value.setValue(1.0)
        editor.duration_or_cutoff.setValue(4.19)
        editor.safety_max_time.setValue(2.0)
        editor.apply_button.click()
        assert window.channel_states[0].test_configuration is not None

        widget.start_test_button.click()
        assert assignment["psu"]["res_id"]["response_queue"] is not None
        state = window.channel_states[0]
        qtbot.waitUntil(lambda: state.test_process is not None, timeout=3000)
        qtbot.waitUntil(
            lambda: state.test_process is None,
            timeout=10000,
        )
        assert list(tmp_path.rglob("*.bdf.csv"))

        widget.cell_name_edit.setText("REAL_LG_MJ1")
        widget.start_test_button.click()
        assert not state.is_running
    finally:
        window.timer.stop()
        window.clean_up()


def test_main_window_smoke(qtbot):
    from battery_test import MainTestWindow

    window = MainTestWindow()
    qtbot.addWidget(window)
    assert window.num_battery_channels == 1
    window.close()


def test_main_window_renders_worker_failure_state(qtbot):
    from battery_test import MainTestWindow

    window = MainTestWindow()
    qtbot.addWidget(window)
    try:
        window.channel_states[0].status = ChannelStatus.ERROR
        window._render_application_event(ApplicationEvent(
            "error",
            0,
            {"worker": "Charge/discharge worker", "exit_code": 7},
            "Charge/discharge worker stopped unexpectedly (exit code 7)",
            "#b42318",
        ))

        assert "Worker error" in window.channel_list.item(0).text()
        assert "Worker error" in window.channel_widgets[0].status_label.text()
        assert "stopped unexpectedly" in window.status_log.item(
            window.status_log.count() - 1
        ).text()
    finally:
        window.close()


def test_institution_code_is_shared_runtime_setting(qtbot):
    from battery_test import MainTestWindow

    window = MainTestWindow()
    qtbot.addWidget(window)
    window.institution_code_edit.setText("CBO")
    window.data_directory_edit.setText("D:/shared-test-data")

    profile = {
        "settings_cycle_list_step_list": [[{"cycle_display": "Charge", "bdf_step_type": "CC_CHG"}]],
    }
    assert "institution_code" not in profile
    assert "directory" not in profile
    runtime = window._configuration_for_start(profile, {"cell_name": "cell_1"})
    assert runtime["institution_code"] == "CBO"
    assert runtime["directory"] == "D:/shared-test-data"
    window.close()


def test_gui_loads_cli_created_advanced_profile_read_only(qtbot, tmp_path):
    """Load a hand-authored multi-cycle profile without a Profile Designer."""
    from battery_test import MainTestWindow

    draft = {
        "profile_schema_version": 2,
        "profile_name": "Advanced charge-rest-discharge",
        "settings_cycle_list_step_list": [
            [{
                "cycle_type": "step",
                "cycle_display": "Charge",
                "bdf_step_type": "CC_CHG",
                "drive_style": "voltage_v",
                "drive_value": 4.2,
                "drive_value_other": 1.0,
                "end_style": "current_a",
                "end_condition": "lesser",
                "end_value": 0.1,
                "meas_log_int_s": 1,
                "safety_min_voltage_v": 2.45,
                "safety_max_voltage_v": 4.25,
                "safety_min_current_a": -10,
                "safety_max_current_a": 10,
                "safety_max_time_s": 3600,
            }, {
                "cycle_type": "step",
                "cycle_display": "Rest",
                "bdf_step_type": "REST",
                "drive_style": "none",
                "drive_value": 0,
                "drive_value_other": 0,
                "end_style": "time_s",
                "end_condition": "greater",
                "end_value": 30,
                "meas_log_int_s": 1,
                "safety_min_voltage_v": 2.45,
                "safety_max_voltage_v": 4.25,
                "safety_min_current_a": -10,
                "safety_max_current_a": 10,
                "safety_max_time_s": 60,
            }],
            [{
                "cycle_type": "step",
                "cycle_display": "Discharge",
                "bdf_step_type": "CC_DCH",
                "drive_style": "current_a",
                "drive_value": -1.5,
                "drive_value_other": 0,
                "end_style": "voltage_v",
                "end_condition": "lesser",
                "end_value": 2.5,
                "meas_log_int_s": 1,
                "safety_min_voltage_v": 2.45,
                "safety_max_voltage_v": 4.25,
                "safety_min_current_a": -10,
                "safety_max_current_a": 10,
                "safety_max_time_s": 3600,
            }],
        ],
    }
    draft_path = tmp_path / "advanced-draft.json"
    profile_path = tmp_path / "advanced-profile.json"
    ConfigurationStore().save_test_configuration(draft, draft_path)
    assert profile_cli_main(["create", str(draft_path), "--output", str(profile_path)]) == 0

    window = MainTestWindow()
    qtbot.addWidget(window)
    try:
        configuration = ConfigurationStore().load_test_configuration(profile_path)
        window.apply_test_configuration(0, configuration, source="imported")

        widget = window.channel_widgets[0]
        assert not widget.profile_editor.isEnabled()
        assert "Cycles: 2; steps: 3" in widget.profile_summary.text()
        assert window.channel_states[0].test_configuration["profile_name"] == draft["profile_name"]
    finally:
        window.close()
