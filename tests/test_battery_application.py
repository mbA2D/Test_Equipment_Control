from __future__ import annotations

import queue
import subprocess
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, field

from battery_app.application import BatteryApplication
from battery_app.process_manager import ProcessManager
from battery_app.profile_identity import ProfileIdentityService
from battery_app.profile_validation import validate_profile_configuration
from battery_app.state import ChannelStatus


def _raise_intentional_worker_failure():
    """Top-level target required for the Windows multiprocessing spawn method."""

    raise RuntimeError("intentional worker failure")


@dataclass
class FakeEquipmentManager:
    """In-memory equipment manager used to isolate application orchestration."""

    process_manager: ProcessManager = field(default_factory=ProcessManager)
    connected_equipment: list[dict] = field(default_factory=list)
    owner_processes: list[dict] = field(default_factory=list)
    released_channels: list[int] = field(default_factory=list)
    closed: bool = False

    def release_channel_ownership(self, channel: int) -> None:
        self.released_channels.append(channel)

    def close(self) -> None:
        self.closed = True


class RecordingController:
    """Controller double that records the temporary execution configuration."""

    def __init__(self, state, _process_manager):
        self.state = state
        self.started_configuration = None
        self.stop_idle_calls = 0
        self.stop_test_calls = 0
        self.stop_all_calls = 0

    def start_test(self) -> bool:
        self.started_configuration = deepcopy(self.state.test_configuration)
        self.state.status = ChannelStatus.RUNNING
        return True

    def start_idle(self) -> bool:
        return False

    def stop_idle(self) -> None:
        self.stop_idle_calls += 1

    def stop_test(self) -> None:
        self.stop_test_calls += 1

    def stop_all(self) -> None:
        self.stop_all_calls += 1


def _profile_definition() -> dict:
    return {
        "profile_schema_version": 1,
        "profile_name": "Short rest",
        "settings_cycle_list_step_list": [[{
            "cycle_type": "step",
            "cycle_display": "Rest",
            "drive_style": "none",
            "drive_value": 0,
            "drive_value_other": 0,
            "end_style": "time_s",
            "end_condition": "greater",
            "end_value": 10,
            "meas_log_int_s": 1,
            "safety_min_voltage_v": 2.45,
            "safety_max_voltage_v": 4.25,
            "safety_min_current_a": -10,
            "safety_max_current_a": 10,
            "safety_max_time_s": 60,
        }]],
    }


def _application_with_recording_controller():
    manager = FakeEquipmentManager()
    controllers = {}

    def create_controller(state, process_manager):
        controller = RecordingController(state, process_manager)
        controllers[state.number] = controller
        return controller

    return BatteryApplication(
        equipment_manager=manager,
        controller_factory=create_controller,
    ), manager, controllers


def test_application_owns_channel_lifecycle_and_releases_ownership():
    application, manager, controllers = _application_with_recording_controller()

    state = application.add_channel(2)

    assert state.number == 2
    assert state.data_queue is not None
    assert application.channel_states[2] is state
    assert application.channel_controllers[2] is controllers[2]

    application.remove_channels()

    assert manager.released_channels == [2]
    assert controllers[2].stop_all_calls == 1
    assert application.channel_states == {}

    application.shutdown()
    assert manager.closed


def test_application_keeps_profile_portable_while_starting_with_run_context(tmp_path):
    application, manager, controllers = _application_with_recording_controller()
    state = application.add_channel(0)
    state.equipment_assignment = {"psu": {"class_name": "Test PSU"}}
    profile = validate_profile_configuration(ProfileIdentityService().create(_profile_definition()))

    stored_profile = application.apply_profile(0, profile)
    result = application.start_test(0, {
        "cell_name": "cell one",
        "directory": str(tmp_path),
        "institution_code": "CBO",
    })

    assert result.ok
    assert controllers[0].started_configuration["cell_name"] == "cell_one"
    assert controllers[0].started_configuration["directory"] == str(tmp_path)
    assert controllers[0].started_configuration["institution_code"] == "CBO"
    assert state.test_configuration == stored_profile
    assert "cell_name" not in state.test_configuration

    application.shutdown()
    assert manager.closed


def test_application_blocks_start_when_profile_exceeds_assigned_equipment_limits(tmp_path):
    application, manager, controllers = _application_with_recording_controller()
    state = application.add_channel(0)
    manager.connected_equipment.append({
        "equipment_id": "psu-1",
        "class_name": "SPD1000",
        "eq_idn": "Siglent,SPD1168X,SN123,1.0",
        "rated_limits": {
            "max_voltage_v": 16.0,
            "max_current_a": 8.0,
            "max_power_w": 128.0,
        },
    })
    state.equipment_assignment = {
        "psu": {
            "class_name": "SPD1000",
            "eq_idn": "Siglent,SPD1168X,SN123,1.0",
            "res_id": {"equipment_id": "psu-1"},
        }
    }
    profile_definition = _profile_definition()
    charge_step = profile_definition["settings_cycle_list_step_list"][0][0]
    charge_step.update({
        "cycle_display": "Charge",
        "drive_style": "current_a",
        "drive_value": 2.0,
        "drive_value_other": 4.2,
        "safety_max_current_a": 9.0,
    })
    profile = ProfileIdentityService().create(profile_definition)
    application.apply_profile(0, profile)

    result = application.start_test(0, {
        "cell_name": "cell one",
        "directory": str(tmp_path),
    })

    assert not result.ok
    assert "Siglent,SPD1168X" in result.message
    assert "rated maximum is 8 A" in result.message
    assert controllers[0].started_configuration is None
    application.shutdown()
    assert manager.closed


def test_application_poll_updates_state_and_returns_render_events():
    application, manager, _controllers = _application_with_recording_controller()
    state = application.add_channel(0)
    state.data_queue = queue.Queue()
    state.data_queue.put({"type": "status", "data": ("Rest", "Complete")})
    state.data_queue.put({"type": "measurement", "data": {"Voltage": 3.8}})
    state.data_queue.put({"type": "end_condition", "data": "safety_condition"})

    events = application.poll()

    assert [event.kind for event in events] == ["status", "measurement", "safety_fault"]
    assert state.status is ChannelStatus.SAFETY_FAULT
    assert state.safety_fault
    assert state.latest_measurement == {"Voltage": 3.8}

    application.shutdown()
    assert manager.closed


def test_application_worker_error_message_sets_terminal_error_state():
    application, manager, _controllers = _application_with_recording_controller()
    state = application.add_channel(0)
    state.data_queue = queue.Queue()
    state.data_queue.put({
        "type": "error",
        "data": {
            "message": "Charge/discharge worker failed: RuntimeError: instrument owner is unavailable",
            "worker": "Charge/discharge worker",
            "exception_type": "RuntimeError",
        },
    })

    events = application.poll()

    assert [event.kind for event in events] == ["error"]
    assert events[0].message == (
        "Charge/discharge worker failed: RuntimeError: instrument owner is unavailable"
    )
    assert state.status is ChannelStatus.ERROR
    application.shutdown()
    assert manager.closed


def test_application_reports_nonzero_worker_exit_when_no_error_message_exists():
    class FailedProcess:
        exitcode = 7

        def __init__(self):
            self.closed = False

        @staticmethod
        def is_alive():
            return False

        def close(self):
            self.closed = True

    application, manager, _controllers = _application_with_recording_controller()
    state = application.add_channel(0)
    failed_process = FailedProcess()
    state.test_process = failed_process

    events = application.poll()

    assert [event.kind for event in events] == ["error"]
    assert events[0].message == "Charge/discharge worker stopped unexpectedly (exit code 7)"
    assert state.status is ChannelStatus.ERROR
    assert state.test_process is None
    assert failed_process.closed
    application.shutdown()
    assert manager.closed


def test_application_reports_a_real_failed_worker_process():
    application, manager, _controllers = _application_with_recording_controller()
    state = application.add_channel(0)
    state.test_process = application.process_manager.start(_raise_intentional_worker_failure)

    deadline = time.monotonic() + 5
    events = []
    while time.monotonic() < deadline and state.status is not ChannelStatus.ERROR:
        events.extend(application.poll())
        time.sleep(0.01)

    assert state.status is ChannelStatus.ERROR
    assert state.test_process is None
    assert any(event.kind == "error" and "exit code" in event.message for event in events)
    application.shutdown()
    assert manager.closed


def test_battery_application_import_does_not_require_qt():
    script = """
import importlib.abc
import sys
class BlockQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('PyQt6'):
            raise RuntimeError(f'Unexpected Qt import: {fullname}')
sys.meta_path.insert(0, BlockQt())
from battery_app import BatteryApplication
assert BatteryApplication is not None
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
