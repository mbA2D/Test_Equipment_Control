import json
from queue import Queue

import pytest

import FileIO
from battery_app.bdf_output import build_cycle_metadata, read_metadata, write_metadata
from battery_app.identity import new_profile_id, profile_version
from battery_app.manifest import load_manifest, manifest_path, save_manifest
from battery_app.persistence import ConfigurationStore
from battery_app.profile_identity import (
    ProfileIdentityService,
    main,
    revise_profile_file,
)
from charge_discharge.cycle_executor import CycleExecutor


def test_profile_identity_keeps_id_and_changes_version_when_settings_change():
    configuration = {
        "profile_schema_version": 1,
        "profile_id": new_profile_id(),
        "profile_name": "Current profile",
        "settings_cycle_list_step_list": [[{"cycle_type": "step", "current_a": 1.0}]],
    }

    first = {**configuration, "profile_version": profile_version(configuration)}
    unchanged = dict(first)
    changed = {**first, "settings_cycle_list_step_list": [[{
        "cycle_type": "step",
        "current_a": 2.0,
    }]]}
    changed["profile_version"] = profile_version(changed)

    assert first["profile_id"] == unchanged["profile_id"]
    assert first["profile_version"] == unchanged["profile_version"]
    assert changed["profile_id"] == first["profile_id"]
    assert changed["profile_version"] != first["profile_version"]
    assert first["profile_version"] == profile_version(first)


def test_profile_identity_service_revises_only_authored_profile_content():
    identity_service = ProfileIdentityService()
    definition = {
        "profile_schema_version": 1,
        "profile_name": "Current profile",
        "settings_cycle_list_step_list": [[{"cycle_type": "step", "current_a": 1.5}]],
    }

    created = identity_service.create(definition)
    unchanged = identity_service.revise(created["profile_id"], created)
    changed = identity_service.revise(
        created["profile_id"],
        {
            **created,
            "settings_cycle_list_step_list": [[{"cycle_type": "step", "current_a": 1.1}]],
        },
    )

    assert unchanged["profile_id"] == created["profile_id"]
    assert unchanged["profile_version"] == created["profile_version"]
    assert changed["profile_id"] == created["profile_id"]
    assert changed["profile_version"] != created["profile_version"]


def test_profile_version_includes_repeated_cycles():
    cycle = [{"cycle_type": "step", "current_a": 1.5}]
    one_cycle = {"settings_cycle_list_step_list": [cycle]}
    repeated_cycle = {"settings_cycle_list_step_list": [cycle, cycle]}

    assert profile_version(one_cycle) != profile_version(repeated_cycle)


def test_profile_revision_cli_revises_manual_edit_to_a_new_file(tmp_path, capsys):
    identity_service = ProfileIdentityService()
    profile = identity_service.create({
        "profile_schema_version": 1,
        "profile_name": "Discharge profile",
        "settings_cycle_list_step_list": [[{
            "cycle_type": "step",
            "cycle_display": "Discharge",
            "drive_style": "current_a",
            "drive_value": -1.5,
            "drive_value_other": 0,
            "end_style": "voltage_v",
            "end_condition": "lesser",
            "end_value": 2.5,
            "meas_log_int_s": 1,
            "safety_min_voltage_v": 2.0,
            "safety_max_voltage_v": 4.3,
            "safety_min_current_a": -10,
            "safety_max_current_a": 10,
            "safety_max_time_s": 3600,
        }]],
    })
    source = tmp_path / "profile.json"
    ConfigurationStore().save_test_configuration(profile, source)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["test_configuration"]["settings_cycle_list_step_list"][0][0]["drive_value"] = -1.1
    source.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["revise", str(source)]) == 0

    revised_path = tmp_path / "profile.revised.json"
    revised = ConfigurationStore().load_test_configuration(revised_path)
    assert revised["profile_id"] == profile["profile_id"]
    assert revised["profile_version"] != profile["profile_version"]
    assert revised["settings_cycle_list_step_list"][0][0]["drive_value"] == -1.1
    assert "Revised profile written" in capsys.readouterr().out


def test_profile_revision_cli_refuses_to_overwrite_new_output(tmp_path):
    source = tmp_path / "source.json"
    destination = tmp_path / "destination.json"
    source.write_text("{}", encoding="utf-8")
    destination.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        revise_profile_file(source, destination)


def test_profile_identity_cli_creates_an_advanced_profile(tmp_path, capsys):
    draft = {
        "profile_schema_version": 1,
        "profile_name": "Charge-rest-discharge",
        "settings_cycle_list_step_list": [
            [{
                "cycle_type": "step",
                "cycle_display": "Charge",
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
    created_path = tmp_path / "advanced-profile.json"
    ConfigurationStore().save_test_configuration(draft, draft_path)

    assert main(["create", str(draft_path), "--output", str(created_path)]) == 0

    created = ConfigurationStore().load_test_configuration(created_path)
    assert created["profile_id"].startswith("profile-")
    assert created["profile_name"] == "Charge-rest-discharge"
    assert len(created["settings_cycle_list_step_list"]) == 2
    assert sum(map(len, created["settings_cycle_list_step_list"])) == 3
    assert "eq_req_dict" not in created
    assert "Created profile written" in capsys.readouterr().out


def test_manifest_is_json_and_replaces_previous_state_atomically(tmp_path):
    manifest = {"test_id": "test-1", "last_cycle_number": 4}

    output_path = save_manifest(tmp_path, manifest)

    assert output_path == manifest_path(tmp_path)
    assert json.loads(output_path.read_text(encoding="utf-8")) == manifest
    assert load_manifest(tmp_path) == manifest


def test_stale_running_cycle_is_recorded_as_interrupted(tmp_path):
    data_path = tmp_path / "LOCAL__cell_1__20260925_001.bdf.csv"
    FileIO.write_bdf_data(data_path, {})
    write_metadata(
        data_path,
        build_cycle_metadata(
            data_path=data_path,
            institution_code="LOCAL",
            cell_name="cell_1",
            cycle_count=1,
            cycle_settings=[{"cycle_display": "Discharge"}],
            equipment={},
            temperature_sources={},
            start_time_utc="2026-09-25T00:00:00+00:00",
            test_id="test-1",
            session_id="session-1",
        ),
    )
    manifest = {
        "test_id": "test-1",
        "current_cycle": {
            "cycle_number": 1,
            "file": data_path.name,
            "status": "running",
        },
    }

    executor = CycleExecutor(object(), {}, Queue(), Queue(), 0)
    executor._recover_stale_cycle(tmp_path, manifest)

    metadata = read_metadata(data_path)
    assert metadata["test"]["status"] == "interrupted"
    assert manifest["current_cycle"]["status"] == "interrupted"
