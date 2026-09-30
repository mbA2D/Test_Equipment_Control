import pytest
import pandas as pd
import json
import time
from multiprocessing import Queue as ProcessQueue
from queue import Empty, Queue

import equipment
from battery_app.equipment_manager import EquipmentManager
from battery_app.identity import new_profile_id, profile_version
from battery_app.process_manager import ProcessManager
from battery_app.battery_model_simple import BatteryCellWorldModel
from battery_app.bdf_output import build_cycle_metadata
from battery_app.simulation import (
    FakeBatteryLink,
    is_simulated_cell_name,
)
from charge_discharge.process_entrypoints import run_charge_discharge_control
from charge_discharge.runner import CyclingControl
from lab_equipment.DMM_Fake import Fake_DMM
from lab_equipment.Eload_Fake import Fake_Eload
from lab_equipment.PSU_Fake import Fake_PSU
from lab_equipment.correlated_device import InstrumentRequestError


def test_simulated_cell_name_is_explicit():
    assert is_simulated_cell_name("simulated_lg_mj1")
    assert not is_simulated_cell_name("LG MJ1")


def test_fake_equipment_share_one_model_and_advance_it():
    link = FakeBatteryLink(BatteryCellWorldModel(initial_soc=0.5))
    psu = Fake_PSU()
    eload = Fake_Eload()
    dmm = Fake_DMM()
    for device in (psu, eload, dmm):
        device.attach_battery_link(link)

    psu.set_current(1.0)
    psu.set_voltage(4.2)
    psu.toggle_output(True)
    link.advance(dt_s=60.0)

    assert dmm.measure_voltage() == pytest.approx(psu.measure_voltage())
    assert dmm.measure_current() == pytest.approx(1.0)
    assert dmm.measure_temperature() > 25.0

    psu.toggle_output(False)
    eload.set_current(-1.0)
    eload.toggle_output(True)
    link.advance(dt_s=60.0)
    assert dmm.measure_current() == pytest.approx(-1.0)


def _proxy_backed_fake_assignment():
    """Build the same owner-process assignment that the GUI creates."""

    manager = EquipmentManager()
    role_and_type = (
        ("psu", "psu", "Fake Test PSU"),
        ("eload", "eload", "Fake Test Eload"),
        ("dmm_v", "dmm", "Fake Test DMM"),
        ("dmm_i", "dmm", "Fake Test DMM"),
        ("dmm_t", "dmm", "Fake Test DMM"),
    )
    assignment = {}
    fake_idn = {
        "Fake Test PSU": Fake_PSU().inst_idn,
        "Fake Test Eload": Fake_Eload().inst_idn,
        "Fake Test DMM": Fake_DMM().inst_idn,
    }
    for local_id, (role, eq_type, class_name) in enumerate(role_and_type):
        descriptor = {
            "local_id": local_id,
            "eq_type": eq_type,
            "eq_idn": fake_idn[class_name],
            "class_name": class_name,
            "res_id": "Fake",
            "setup_dict": {},
        }
        assert manager.connect(descriptor)
        connected = manager.connected_equipment[-1]
        client_id = f"channel-0-{role}"
        response_queue = manager.response_queue_for(local_id, client_id, 0, 0)
        assignment[role] = {
            "class_name": class_name,
            "setup_dict": {},
            "res_id": {
                "equipment_id": connected["equipment_id"],
                "eq_idn": connected["eq_idn"],
                "class_name": connected["class_name"],
                "resource_id": connected["res_id"],
                "local_id": local_id,
                "queue_in": connected["queue_in"],
                "client_id": client_id,
                "response_queue": response_queue,
                "eq_ch": 0,
            },
        }
    return manager, assignment


def test_simulated_instruments_keep_the_owner_process_and_proxy_path():
    manager, assignment = _proxy_backed_fake_assignment()
    control = CyclingControl()
    try:
        control._validate_simulated_equipment_assignment(assignment)
        control.eq_dict = equipment.get_equipment_dict(assignment)
        metadata = build_cycle_metadata(
            data_path="simulated.bdf.csv",
            institution_code="TEST",
            cell_name="SIMULATED_LG_MJ1",
            cycle_count=1,
            cycle_settings=[],
            equipment=control.eq_dict,
            temperature_sources={},
            start_time_utc="2026-09-27T00:00:00+00:00",
        )["equipment"]
        assert metadata["psu"]["manufacturer"] == "TestEquipmentControl"
        assert metadata["psu"]["instrument_model"] == "SIMULATED_PSU"
        assert metadata["psu"]["serial_number"] == "SIM-PSU-0001"
        assert metadata["eload"]["instrument_model"] == "SIMULATED_ELOAD"
        assert metadata["eload"]["serial_number"] == "SIM-ELOAD-0001"
        assert metadata["dmm_v"]["instrument_model"] == "SIMULATED_DMM"
        assert metadata["dmm_v"]["serial_number"] == "SIM-DMM-0001"
        control._connect_simulated_battery()

        control.eq_dict["psu"].set_current(1.0)
        control.eq_dict["psu"].set_voltage(4.2)
        control.eq_dict["psu"].toggle_output(True)

        assert control.eq_dict["dmm_i"].measure_current() == pytest.approx(1.0)
        assert control.battery_link.snapshot()["soc"] > 0.5
        control._disconnect_simulated_battery()
        with pytest.raises(
            InstrumentRequestError,
            match="FakeInstrumentNotAttachedError",
        ):
            control.eq_dict["dmm_i"].measure_current()
    finally:
        if control.simulation_service is not None:
            control.simulation_service.close()
        manager.close()


def test_simulation_rejects_a_non_fake_or_non_proxy_assignment():
    assignment = {
        "psu": {"class_name": "SPD1000", "res_id": {"queue_in": object()}},
    }

    with pytest.raises(ValueError, match="requires assigned Fake Test"):
        CyclingControl._validate_simulated_equipment_assignment(assignment)


def test_gui_style_runner_drives_simulated_battery_and_logs_measurements(
    tmp_path, record_property
):
    stage_timings = []

    def record_stage(name, started_at):
        duration = time.perf_counter() - started_at
        stage_timings.append((name, duration))
        print(f"[timing] {name}: {duration:.3f}s", flush=True)

    stage_started = time.perf_counter()
    manager, assignment = _proxy_backed_fake_assignment()
    record_stage("initial_fake_owner_setup", stage_started)
    step = {
        "cycle_type": "step",
        "cycle_display": "Discharge",
        "bdf_step_type": "CC_DCH",
        "drive_style": "current_a",
        "drive_value": -10.0,
        "drive_value_other": 0.0,
        "end_style": "time_s",
        "end_condition": "greater",
        "end_value": 0.05,
        "meas_log_int_s": 0.01,
        "safety_min_voltage_v": 2.0,
        "safety_max_voltage_v": 4.3,
        "safety_min_current_a": -10.0,
        "safety_max_current_a": 10.0,
        "safety_max_time_s": 2.0,
    }
    configuration = {
        "profile_schema_version": 2,
        "profile_id": new_profile_id(),
        "cell_name": "SIMULATED_LG_MJ1",
        "directory": str(tmp_path),
        "cycle_type": "Discharge",
        "eq_req_dict": {"psu": False, "eload": True},
        "settings_cycle_list_step_list": [[step], [step]],
    }
    configuration["profile_version"] = profile_version(configuration)
    measurements = ProcessQueue()
    process_manager = ProcessManager(join_timeout_s=2)
    process = None
    try:
        stage_started = time.perf_counter()
        process = process_manager.start(
            run_charge_discharge_control,
            (assignment, measurements, ProcessQueue(), configuration, 0),
        )
        record_stage("first_worker_start", stage_started)
        stage_started = time.perf_counter()
        process.join(10)
        record_stage("first_worker_execution", stage_started)
        assert process.exitcode == 0, (
            "First battery runner did not exit successfully within 10 seconds "
            f"(exitcode={process.exitcode}, pid={process.pid})."
        )
    finally:
        if process is not None:
            stage_started = time.perf_counter()
            process_manager.stop(process)
            record_stage("first_worker_cleanup", stage_started)
        stage_started = time.perf_counter()
        manager.close()
        record_stage("initial_owner_cleanup", stage_started)

    messages = []
    while True:
        try:
            messages.append(measurements.get(timeout=0.2))
        except Empty:
            break
    measurement_data = [message["data"] for message in messages if message["type"] == "measurement"]

    assert len(measurement_data) >= 2
    assert "Temperature" in measurement_data[-1]
    csv_files = sorted(tmp_path.rglob("*.csv"))
    assert len(csv_files) == 2
    dataframes = [pd.read_csv(filepath) for filepath in csv_files]
    for dataframe in dataframes:
        assert "Test Time / s" in dataframe.columns
        assert "Unix Time / s" in dataframe.columns
        assert "Cycle Count / 1" in dataframe.columns
        assert "Step Count / 1" in dataframe.columns
        assert "Step ID" in dataframe.columns
        assert "Step Time / s" in dataframe.columns
        assert "Surface Temperature T1 / degC" in dataframe.columns
        assert "Cycle Discharging Capacity / Ah" in dataframe.columns
        assert dataframe["Step Type"].eq("CC_DCH").all()
        assert dataframe["Step ID"].eq(1).all()

    assert dataframes[0]["Cycle Count / 1"].eq(1).all()
    assert dataframes[1]["Cycle Count / 1"].eq(2).all()
    assert dataframes[0]["Step Count / 1"].eq(1).all()
    assert dataframes[1]["Step Count / 1"].eq(2).all()
    assert dataframes[0]["Cycle Discharging Capacity / Ah"].iloc[0] == 0.0
    assert dataframes[1]["Cycle Discharging Capacity / Ah"].iloc[0] == 0.0
    assert all(filepath.with_suffix(".meta.jsonld").exists() for filepath in csv_files)
    manifest_path = tmp_path / "SIMULATED_LG_MJ1" / "cell_manifest.json"
    first_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert first_manifest["last_cycle_number"] == 2
    assert first_manifest["last_step_count"] == 2
    first_test_id = first_manifest["test_id"]
    first_session_id = first_manifest["last_session_id"]

    continuation_configuration = {
        **configuration,
        "settings_cycle_list_step_list": [[step]],
    }
    stage_started = time.perf_counter()
    continuation_manager, continuation_assignment = _proxy_backed_fake_assignment()
    record_stage("continuation_fake_owner_setup", stage_started)
    continuation_process = None
    try:
        stage_started = time.perf_counter()
        continuation_process = process_manager.start(
            run_charge_discharge_control,
            (continuation_assignment, ProcessQueue(), ProcessQueue(), continuation_configuration, 0),
        )
        record_stage("continuation_worker_start", stage_started)
        stage_started = time.perf_counter()
        continuation_process.join(10)
        record_stage("continuation_worker_execution", stage_started)
        assert continuation_process.exitcode == 0, (
            "Continuation battery runner did not exit successfully within 10 seconds "
            f"(exitcode={continuation_process.exitcode}, pid={continuation_process.pid})."
        )
    finally:
        if continuation_process is not None:
            stage_started = time.perf_counter()
            process_manager.stop(continuation_process)
            record_stage("continuation_worker_cleanup", stage_started)
        stage_started = time.perf_counter()
        continuation_manager.close()
        record_stage("continuation_owner_cleanup", stage_started)

    timing_summary = ", ".join(
        f"{name}={duration:.3f}s" for name, duration in stage_timings
    )
    record_property("stage_timings", timing_summary)
    print(f"Fake battery end-to-end stage timings: {timing_summary}", flush=True)

    continued_files = sorted(tmp_path.rglob("*.csv"))
    continued_dataframe = pd.read_csv(continued_files[-1])
    assert len(continued_files) == 3
    assert continued_files[-1].name.endswith("_003.bdf.csv")
    assert continued_dataframe["Cycle Count / 1"].eq(3).all()
    assert continued_dataframe["Step Count / 1"].eq(3).all()
    continued_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert continued_manifest["test_id"] == first_test_id
    assert continued_manifest["last_session_id"] != first_session_id
    assert continued_manifest["last_cycle_number"] == 3
    assert continued_manifest["last_step_count"] == 3


def test_gui_style_runner_writes_charge_and_rest_bdf_step_types(tmp_path):
    manager, assignment = _proxy_backed_fake_assignment()
    step_base = {
        "cycle_type": "step",
        "drive_value_other": 0.0,
        "end_style": "time_s",
        "end_condition": "greater",
        "end_value": 0.03,
        "meas_log_int_s": 0.01,
        "safety_min_voltage_v": 2.0,
        "safety_max_voltage_v": 4.3,
        "safety_min_current_a": -10.0,
        "safety_max_current_a": 10.0,
        "safety_max_time_s": 2.0,
    }
    charge_step = {
        **step_base,
        "cycle_display": "Charge",
        "bdf_step_type": "CC_CHG",
        "drive_style": "current_a",
        "drive_value": 1.0,
        "drive_value_other": 4.2,
        "end_value": 0.8,
    }
    rest_step = {
        **step_base,
        "cycle_display": "Rest",
        "bdf_step_type": "REST",
        "drive_style": "none",
        "drive_value": 0.0,
    }
    configuration = {
        "profile_schema_version": 2,
        "profile_id": new_profile_id(),
        "cell_name": "SIMULATED_LG_MJ1",
        "directory": str(tmp_path),
        "cycle_type": "Charge and rest",
        "eq_req_dict": {"psu": True, "eload": False},
        "settings_cycle_list_step_list": [[charge_step, rest_step]],
    }
    configuration["profile_version"] = profile_version(configuration)
    process_manager = ProcessManager(join_timeout_s=2)
    process = None
    try:
        process = process_manager.start(
            run_charge_discharge_control,
            (assignment, ProcessQueue(), ProcessQueue(), configuration, 0),
        )
        process.join(10)
        assert process.exitcode == 0, (
            "Charge/rest battery runner did not exit successfully within 10 seconds "
            f"(exitcode={process.exitcode}, pid={process.pid})."
        )
    finally:
        if process is not None:
            process_manager.stop(process)
        manager.close()

    csv_files = sorted(tmp_path.rglob("*.bdf.csv"))
    assert len(csv_files) == 1
    dataframe = pd.read_csv(csv_files[0])
    assert set(dataframe["Step Type"]) == {"CC_CHG", "REST"}
    charge_rows = dataframe[dataframe["Step Type"] == "CC_CHG"]
    rest_rows = dataframe[dataframe["Step Type"] == "REST"]
    assert not charge_rows.empty
    assert not rest_rows.empty
    assert charge_rows["Current / A"].gt(0).all()
    assert charge_rows["Cycle Charging Capacity / Ah"].iloc[-1] > 0
    assert rest_rows["Current / A"].eq(0).all()


def test_headless_simulated_charge_rest_discharge_rest_writes_bdf_and_identity(tmp_path):
    manager, assignment = _proxy_backed_fake_assignment()
    step_base = {
        "cycle_type": "step",
        "drive_value_other": 0.0,
        "end_style": "time_s",
        "end_condition": "greater",
        "end_value": 0.2,
        "meas_log_int_s": 0.01,
        "safety_min_voltage_v": 2.0,
        "safety_max_voltage_v": 4.3,
        "safety_min_current_a": -10.0,
        "safety_max_current_a": 10.0,
        "safety_max_time_s": 1.0,
    }
    steps = [
        {
            **step_base,
            "cycle_display": "Charge",
            "bdf_step_type": "CC_CHG",
            "drive_style": "current_a",
            "drive_value": 1.0,
            "drive_value_other": 4.2,
            "end_value": 0.8,
        },
        {
            **step_base,
            "cycle_display": "Rest after charge",
            "bdf_step_type": "REST",
            "drive_style": "none",
            "drive_value": 0.0,
        },
        {
            **step_base,
            "cycle_display": "Discharge",
            "bdf_step_type": "CC_DCH",
            "drive_style": "current_a",
            "drive_value": -1.0,
            "end_value": 0.8,
        },
        {
            **step_base,
            "cycle_display": "Rest after discharge",
            "bdf_step_type": "REST",
            "drive_style": "none",
            "drive_value": 0.0,
        },
    ]
    configuration = {
        "profile_schema_version": 2,
        "profile_id": new_profile_id(),
        "cell_name": "SIMULATED_LG_MJ1",
        "directory": str(tmp_path),
        "institution_code": "TEST",
        "cycle_type": "Charge, rest, discharge, rest",
        "eq_req_dict": {"psu": True, "eload": True},
        "settings_cycle_list_step_list": [steps],
    }
    configuration["profile_version"] = profile_version(configuration)
    process_manager = ProcessManager(join_timeout_s=2)
    process = None
    try:
        process = process_manager.start(
            run_charge_discharge_control,
            (assignment, ProcessQueue(), ProcessQueue(), configuration, 0),
        )
        process.join(10)
        assert process.exitcode == 0, (
            "Headless simulated cycle did not exit successfully within 10 seconds "
            f"(exitcode={process.exitcode}, pid={process.pid})."
        )
    finally:
        if process is not None:
            process_manager.stop(process)
        manager.close()

    csv_files = sorted(tmp_path.rglob("*.bdf.csv"))
    assert len(csv_files) == 1
    dataframe = pd.read_csv(csv_files[0])
    assert set(dataframe["Step Type"]) == {"CC_CHG", "REST", "CC_DCH"}
    charge_rows = dataframe[dataframe["Step Type"] == "CC_CHG"]
    discharge_rows = dataframe[dataframe["Step Type"] == "CC_DCH"]
    rest_rows = dataframe[dataframe["Step Type"] == "REST"]
    assert not charge_rows.empty and not discharge_rows.empty and len(rest_rows) >= 2
    assert charge_rows["Current / A"].gt(0).all()
    assert discharge_rows["Current / A"].lt(0).all()
    assert rest_rows["Current / A"].eq(0).all()
    assert charge_rows["Cycle Charging Capacity / Ah"].iloc[-1] > 0
    assert discharge_rows["Cycle Discharging Capacity / Ah"].iloc[-1] > 0

    metadata_path = csv_files[0].with_suffix(".meta.jsonld")
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))["testEquipmentControl"]
    assert metadata["test"]["status"] == "completed"
    assert [step["display_name"] for step in metadata["test"]["steps"]] == [
        "Charge",
        "Rest",
        "Discharge",
        "Rest",
    ]
    assert metadata["equipment"]["psu"]["serial_number"] == "SIM-PSU-0001"
    assert metadata["equipment"]["eload"]["serial_number"] == "SIM-ELOAD-0001"
    assert metadata["equipment"]["dmm_v"]["serial_number"] == "SIM-DMM-0001"

