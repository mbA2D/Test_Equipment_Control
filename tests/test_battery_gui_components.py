from battery_gui import (
    ChannelWidget,
    ConnectedEquipmentWidget,
    EquipmentAssignmentWidget,
    EquipmentConnectionWidget,
    ProfileEditorWidget,
)


def test_profile_editor_emits_charge_configuration(qtbot):
    editor = ProfileEditorWidget()
    qtbot.addWidget(editor)
    received = []
    editor.configuration_applied.connect(received.append)

    editor.apply_button.click()

    assert "cell_name" not in received[0]
    assert "directory" not in received[0]
    assert "institution_code" not in received[0]
    assert received[0]["profile_id"].startswith("profile-")
    assert received[0]["profile_version"].startswith("sha256:")
    assert received[0]["profile_name"] == "Charge"
    assert "eq_req_dict" not in received[0]
    step = received[0]["settings_cycle_list_step_list"][0][0]
    assert step["drive_style"] == "voltage_v"


def test_channel_widget_keeps_run_context_outside_the_profile(qtbot):
    widget = ChannelWidget(0)
    qtbot.addWidget(widget)

    widget.cell_name_edit.setText("SIMULATED_LG_MJ1")

    assert widget.run_configuration() == {
        "cell_name": "SIMULATED_LG_MJ1",
    }
    assert not hasattr(widget, "output_directory_edit")


def test_equipment_assignment_emits_serializable_assignment(qtbot):
    assignment_widget = EquipmentAssignmentWidget()
    qtbot.addWidget(assignment_widget)
    received = []
    assignment_widget.assignment_applied.connect(received.append)
    assignment_widget.set_equipment_options([
        {
            "equipment_id": "fake-psu-4",
            "local_id": 4,
            "eq_idn": "Fake PSU",
            "eq_type": "psu",
            "class_name": "Fake_PSU",
            "capabilities": ["can_source_voltage"],
        }
    ])
    assignment_widget._selectors["psu"].setCurrentIndex(1)
    assignment_widget.apply_button.click()

    assert received[0]["psu"]["res_id"]["local_id"] == 4
    assert received[0]["psu"]["res_id"]["equipment_id"] == "fake-psu-4"
    assert received[0]["psu"]["res_id"]["eq_ch"] == 0
    assert received[0]["eload"] is None


def test_equipment_assignment_requires_specific_capability_and_selects_channel(qtbot):
    assignment_widget = EquipmentAssignmentWidget()
    qtbot.addWidget(assignment_widget)
    received = []
    assignment_widget.assignment_applied.connect(received.append)
    assignment_widget.set_equipment_options([
        {
            "equipment_id": "psu-1",
            "local_id": 4,
            "eq_idn": "Three-channel PSU",
            "eq_type": "psu",
            "class_name": "DP800",
            "capabilities": ["can_source_voltage"],
            "instrument_channels": [1, 2, 3],
        },
        {
            "equipment_id": "dmm-1",
            "local_id": 5,
            "eq_idn": "Voltage-only DMM",
            "eq_type": "dmm",
            "class_name": "DM3000",
            "capabilities": ["can_measure_voltage"],
        },
        {
            "equipment_id": "dmm-2",
            "local_id": 6,
            "eq_idn": "Unadvertised DMM",
            "eq_type": "dmm",
            "class_name": "Unknown",
            "capabilities": [],
        },
    ])

    assert assignment_widget._selectors["dmm_i"].count() == 1
    assert assignment_widget._selectors["dmm_v"].count() == 2

    assignment_widget._selectors["psu"].setCurrentIndex(1)
    assignment_widget._channel_selectors["psu"].setCurrentText("Channel 2")
    assignment_widget.apply_button.click()

    assert received[0]["psu"]["res_id"] == {
        "queue_in": None,
        "equipment_id": "psu-1",
        "local_id": 4,
        "eq_ch": 2,
    }
    assert "relay_board" in received[0]
    assert "dmm_v0" in received[0]


def test_connected_equipment_widget_lists_instruments_and_channels(qtbot):
    widget = ConnectedEquipmentWidget()
    qtbot.addWidget(widget)

    widget.set_equipment([{
        "local_id": 2,
        "eq_type": "relay_board",
        "eq_idn": "A2D Relay Board",
        "class_name": "A2D Relay Board",
        "capabilities": ["can_isolate_output"],
        "instrument_channels": [1, 2],
    }])

    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 0).text() == "2"
    assert widget.table.item(0, 4).text() == "1, 2"


def test_channel_widget_updates_live_measurements(qtbot):
    widget = ChannelWidget(3)
    qtbot.addWidget(widget)

    widget.update_measurement({"Voltage": 3.7, "Current": -1.2, "dmm_t0": 25.0})

    assert "3.7" in widget.measurement_label.text()
    assert "-1.2" in widget.measurement_label.text()
    assert "25.0" in widget.measurement_label.text()


def test_imported_profile_is_read_only_until_explicit_simple_profile_action(qtbot):
    widget = ChannelWidget(0)
    qtbot.addWidget(widget)
    configuration = {
        "profile_id": "profile-imported",
        "profile_version": "sha256:imported",
        "cell_name": "cell_1",
        "directory": "results",
        "eq_req_dict": {"psu": True, "eload": False},
        "settings_cycle_list_step_list": [[{
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
        }]],
    }

    widget.show_profile_configuration(configuration, source="imported")

    assert not widget.profile_editor.isEnabled()
    assert "Imported read-only profile" in widget.profile_summary.text()
    widget.focus_profile_editor()
    assert widget.profile_editor.isEnabled()
    assert "draft" in widget.profile_summary.text()


def test_equipment_connection_widget_emits_explicit_selection(qtbot):
    widget = EquipmentConnectionWidget()
    qtbot.addWidget(widget)
    received = []
    widget.connect_requested.connect(lambda *args: received.append(args))
    widget.set_models({"psu": ["Fake Test PSU"], "eload": [], "dmm": [], "other": []})
    widget.set_resources(["USB::INSTR0"])
    widget.model.setCurrentText("Fake Test PSU")
    widget.resource.setCurrentIndex(1)
    widget.connect_button.click()

    assert received == [("psu", "Fake Test PSU", "USB::INSTR0", {})]
