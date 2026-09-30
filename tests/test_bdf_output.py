import json

import pandas as pd
import pytest

import FileIO
from battery_app.bdf_output import (
    BDF_COLUMNS,
    build_bdf_row,
    build_cycle_metadata,
    metadata_path,
    validate_bdf_dataframe,
    write_metadata,
)


@pytest.mark.parametrize(
    ("cycle_display", "bdf_step_type"),
    [
        ("Charge", "CC_CHG"),
        ("Discharge", "CC_DCH"),
        ("Rest", "REST"),
        ("Rest after charge", "REST"),
        ("Rest after discharge", "REST"),
    ],
)
def test_cycle_metadata_uses_explicit_bdf_step_type(
    tmp_path, cycle_display, bdf_step_type
):
    filepath = tmp_path / "LOCAL__cell__20260924_001.bdf.csv"
    metadata = build_cycle_metadata(
        data_path=filepath,
        institution_code="LOCAL",
        cell_name="cell",
        cycle_count=1,
        cycle_settings=[{
            "cycle_type": "step",
            "cycle_display": cycle_display,
            "bdf_step_type": bdf_step_type,
        }],
        equipment={},
        temperature_sources={},
        start_time_utc="2026-09-24T00:00:00+00:00",
    )

    step = metadata["testEquipmentControl"]["test"]["steps"][0]
    assert step["step_type"] == bdf_step_type
    assert step["display_name"] == cycle_display


def _row():
    return build_bdf_row(
        {
            "Voltage": 3.7,
            "Current": 1.0,
            "Unix_Timestamp": 1_700_000_000.0,
            "Cycle Charging Capacity / Ah": 0.1,
            "Cycle Discharging Capacity / Ah": 0.0,
            "Cycle Charging Energy / Wh": 0.37,
            "Cycle Discharging Energy / Wh": 0.0,
            "Temperature": 25.0,
        },
        test_time_s=1.0,
        cycle_count=1,
        step_count=1,
        step_id=1,
        step_time_s=1.0,
        step_type="CC_CHG",
        temperature_sources={"Surface Temperature T1 / degC": "Temperature"},
    )


def test_bdf_writer_keeps_fixed_headers_and_uses_bdf_labels(tmp_path):
    filepath = tmp_path / "LOCAL__cell__20260924_001.bdf.csv"
    FileIO.write_bdf_data(filepath, _row())
    FileIO.write_bdf_data(filepath, _row())

    dataframe = pd.read_csv(filepath)
    assert tuple(dataframe.columns) == BDF_COLUMNS
    assert len(dataframe) == 2
    assert "Log_Timestamp" not in dataframe.columns
    assert dataframe["Surface Temperature T1 / degC"].iloc[0] == 25.0


def test_official_bdf_validator_accepts_required_schema(tmp_path):
    bdf = __import__("bdf")
    filepath = tmp_path / "LOCAL__cell__20260924_001.bdf.csv"
    FileIO.write_bdf_data(filepath, _row())

    report = bdf.validate(pd.read_csv(filepath), report=False, raise_on_error=False)
    assert report["ok"] is True


def test_project_validator_enforces_fixed_headers_and_monotonic_counters(tmp_path):
    filepath = tmp_path / "LOCAL__cell__20260924_001.bdf.csv"
    FileIO.write_bdf_data(filepath, _row())
    FileIO.write_bdf_data(filepath, _row())
    dataframe = pd.read_csv(filepath)

    assert validate_bdf_dataframe(dataframe)["ok"] is True

    dataframe.loc[1, "Step Count / 1"] = 0
    report = validate_bdf_dataframe(dataframe)
    assert report["ok"] is False
    assert any("Step Count / 1" in error for error in report["errors"])


def test_metadata_sidecar_uses_jsonld_and_records_temperature_placement(tmp_path):
    filepath = tmp_path / "LOCAL__cell__20260924_001.bdf.csv"
    metadata = build_cycle_metadata(
        data_path=filepath,
        institution_code="LOCAL",
        cell_name="cell",
        cycle_count=1,
        cycle_settings=[{
            "cycle_display": "Charge",
            "bdf_step_type": "CC_CHG",
            "cycle_type": "step",
        }],
        equipment={"dmm_t": object()},
        temperature_sources={"Surface Temperature T1 / degC": "Temperature"},
        start_time_utc="2026-09-24T00:00:00+00:00",
        profile_id="profile-1",
        profile_version="sha256:profile",
        test_id="test-1",
        session_id="session-1",
    )

    output_path = write_metadata(filepath, metadata)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path == metadata_path(filepath)
    assert payload["@type"] == "schema:Dataset"
    project_metadata = payload["testEquipmentControl"]
    assert project_metadata["test"]["type"] == "Charge"
    assert project_metadata["identity"]["profile_id"] == "profile-1"
    assert project_metadata["identity"]["test_id"] == "test-1"
    assert project_metadata["identity"]["session_id"] == "session-1"
    assert project_metadata["temperature_sensors"]["Surface Temperature T1 / degC"]["placement"] == "T1"
    assert project_metadata["temperature_sensors"]["Surface Temperature T1 / degC"]["physical_location"] == "unspecified"
