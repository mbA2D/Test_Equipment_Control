"""Shared frontend-neutral runner and command-line battery test entry point.

The Qt GUI and the headless command use this module for profile, equipment,
channel, and test lifecycle operations. Presentation code is limited to
collecting inputs and rendering :class:`ApplicationEvent` values.
"""

from __future__ import annotations

import argparse
import json
import queue
import shlex
import signal
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .application import ApplicationEvent, BatteryApplication, OperationResult
from .logging_config import configure_application_logging, get_logger
from .profile_validation import profile_payload
from .simulation import SIMULATED_FAKE_CLASSES, is_simulated_cell_name
from .state import ChannelState, ChannelStatus


logger = get_logger(__name__)


class HeadlessRunner:
    """Frontend-neutral workflows shared by the GUI and command line."""

    def __init__(self, application: BatteryApplication | None = None):
        self.application = application or BatteryApplication()

    @property
    def channel_states(self) -> dict[int, ChannelState]:
        return self.application.channel_states

    @property
    def connected_equipment(self) -> list[dict[str, Any]]:
        return self.application.connected_equipment

    @property
    def configuration_store(self):
        return self.application.configuration_store

    @property
    def last_equipment_error(self) -> str | None:
        return self.application.equipment_manager.last_connection_error

    @staticmethod
    def resolve_connected_equipment(assignment, connected_equipment):
        return BatteryApplication.resolve_connected_equipment(assignment, connected_equipment)

    @staticmethod
    def physical_resource_ids(resource):
        from .equipment_manager import EquipmentManager

        return EquipmentManager.physical_resource_ids(resource)

    @staticmethod
    def is_equipment_already_connected(candidate, connected_equipment) -> bool:
        candidate_ids = HeadlessRunner.physical_resource_ids(candidate.get("res_id"))
        return bool(candidate_ids) and any(
            candidate_ids & HeadlessRunner.physical_resource_ids(item.get("res_id"))
            for item in connected_equipment
        )

    def reset_channels(self, channels: Sequence[int]) -> list[ChannelState]:
        """Replace runtime channels with the requested channel identifiers."""
        self.application.remove_channels()
        return [self.application.add_channel(channel) for channel in channels]

    def add_channel(self, channel: int | None = None) -> ChannelState:
        return self.application.add_channel(channel)

    def remove_channels(self) -> None:
        self.application.remove_channels()

    def remove_channel(self, channel: int) -> bool:
        return self.application.remove_channel(channel)

    def scan_resources(self) -> OperationResult:
        return self.application.scan_resources()

    def probe_equipment(self, *args, **kwargs) -> OperationResult:
        return self.application.probe_equipment(*args, **kwargs)

    def connect_equipment(self, descriptor: dict[str, Any]) -> bool:
        return self.application.connect_equipment(descriptor)

    def disconnect_all_equipment(self) -> None:
        self.application.disconnect_all_equipment()

    def apply_equipment_assignment(
        self,
        channel: int,
        assignment: Mapping[str, Any],
    ) -> OperationResult:
        return self.application.apply_equipment_assignment(channel, assignment)

    def apply_profile(
        self,
        channel: int,
        configuration: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self.application.apply_profile(channel, configuration)

    def load_profile(self, filename: str | Path) -> dict[str, Any]:
        return self.configuration_store.load_test_configuration(filename)

    def save_profile(self, channel: int, filename: str | Path) -> Path:
        state = self.channel_states.get(channel)
        if state is None or state.test_configuration is None:
            raise ValueError(f"Channel {channel} has no test profile to save")
        return self.configuration_store.save_test_configuration(
            profile_payload(state.test_configuration),
            filename,
        )

    def restore_equipment_configuration(
        self,
        filename: str | Path,
        *,
        channels: Sequence[int] | None = None,
        include_unassigned_equipment: bool = True,
    ) -> dict[int, dict[str, Any] | None]:
        """Reconnect serialized equipment and restore its assignments.

        ``channels=None`` restores the complete GUI configuration. A headless
        one-channel process can pass a single channel; only equipment assigned
        to that channel is connected.
        """
        imported = self.configuration_store.load_equipment_assignment(filename)
        assignments = imported["res_ids_dict"]
        connected = imported["connected_equipment_dict"]

        if channels is None:
            selected_channels = sorted(set(range(max(assignments, default=0) + 1)))
            include_unassigned_equipment = True
        else:
            selected_channels = sorted(set(channels))
            if not selected_channels:
                raise ValueError("At least one channel must be selected")
            missing = [channel for channel in selected_channels if channel not in assignments]
            if missing:
                raise ValueError(
                    "Equipment configuration has no assignment entry for channel(s): "
                    + ", ".join(map(str, missing))
                )

        if any(state.is_running for state in self.channel_states.values()):
            raise RuntimeError("Stop active tests before restoring equipment configuration")

        equipment_ids = set()
        for channel in selected_channels:
            for descriptor in (assignments.get(channel) or {}).values():
                resource = descriptor.get("res_id") if isinstance(descriptor, dict) else None
                equipment_id = resource.get("equipment_id") if isinstance(resource, dict) else None
                if equipment_id:
                    equipment_ids.add(equipment_id)

        descriptors = [
            descriptor
            for _local_id, descriptor in sorted(connected.items())
            if include_unassigned_equipment or descriptor.get("equipment_id") in equipment_ids
        ]

        previous_idle_restart = self.application.restart_idle_processes
        self.application.restart_idle_processes = False
        try:
            self.application.remove_channels()
            self.application.disconnect_all_equipment()
            for channel in selected_channels:
                self.application.add_channel(channel)

            for descriptor in descriptors:
                if not self.connect_equipment(descriptor):
                    message = self.last_equipment_error or "equipment connection was rejected"
                    raise RuntimeError(f"Could not connect {descriptor.get('class_name')}: {message}")

            restored: dict[int, dict[str, Any] | None] = {}
            for channel in selected_channels:
                assignment = assignments.get(channel)
                restored[channel] = assignment
                if assignment is None:
                    continue
                result = self.apply_equipment_assignment(channel, assignment)
                if not result.ok:
                    raise RuntimeError(f"Channel {channel} assignment failed: {result.message}")
            return restored
        except Exception:
            self.application.remove_channels()
            self.application.disconnect_all_equipment()
            raise
        finally:
            self.application.restart_idle_processes = previous_idle_restart

    def save_equipment_configuration(self, filename: str | Path) -> Path:
        return self.configuration_store.save_equipment_assignment(
            self.connected_equipment,
            {
                channel: state.equipment_assignment
                for channel, state in self.channel_states.items()
            },
            filename,
        )

    def set_cell_name(self, channel: int, cell_name: str) -> OperationResult:
        return self.application.set_cell_name(channel, cell_name)

    def build_execution_configuration(
        self,
        configuration: Mapping[str, Any],
        run_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self.application.build_execution_configuration(configuration, run_context)

    def start_test(self, channel: int, run_context: Mapping[str, Any]) -> OperationResult:
        return self.application.start_test(channel, run_context)

    def start_idle(self, channel: int) -> OperationResult:
        return self.application.start_idle(channel)

    def stop_idle(self, channel: int) -> None:
        self.application.stop_idle(channel)

    def stop_test(self, channel: int) -> OperationResult:
        return self.application.stop_test(channel)

    def clear_safety_fault(self, channel: int) -> OperationResult:
        return self.application.clear_safety_fault(channel)

    def poll(self) -> list[ApplicationEvent]:
        return self.application.poll()

    def shutdown(self) -> None:
        self.application.shutdown()


def _is_simulated_descriptor(descriptor: Mapping[str, Any]) -> bool:
    resource = descriptor.get("res_id")
    resource_id = resource.get("resource_id") if isinstance(resource, Mapping) else resource
    return (
        descriptor.get("class_name") in SIMULATED_FAKE_CLASSES
        and resource_id == "Fake"
    )


def _is_fully_simulated_assignment(assignment: Mapping[str, Any] | None) -> bool:
    devices = [descriptor for descriptor in (assignment or {}).values() if descriptor is not None]
    return bool(devices) and all(
        isinstance(descriptor, Mapping) and _is_simulated_descriptor(descriptor)
        for descriptor in devices
    )


def _write_event(event: ApplicationEvent, *, show_measurements: bool = False) -> None:
    if event.kind == "measurement" and not show_measurements:
        return
    record = {
        "event": event.kind,
        "channel": event.channel,
        "message": event.message,
    }
    if event.payload is not None:
        record["data"] = event.payload
    print(json.dumps(record, default=str, separators=(",", ":")), flush=True)


def run_headless(
    *,
    profile_file: str | Path,
    equipment_file: str | Path,
    channel: int = 0,
    cell_name: str,
    data_directory: str | Path,
    institution_code: str = "LOCAL",
    poll_interval_s: float = 0.1,
    confirm_physical_output: bool = False,
    show_measurements: bool = False,
    stop_event: threading.Event | None = None,
    event_handler: Callable[[ApplicationEvent], None] | None = None,
    runner: HeadlessRunner | None = None,
) -> int:
    """Run one configured channel to completion without importing Qt."""
    if poll_interval_s <= 0:
        raise ValueError("poll_interval_s must be greater than zero")

    runner = runner or HeadlessRunner()
    stop_event = stop_event or threading.Event()
    runner.application.restart_idle_processes = False
    try:
        profile = runner.load_profile(profile_file)
        equipment_payload = runner.configuration_store.load_equipment_assignment(equipment_file)
        assignment = equipment_payload["res_ids_dict"].get(channel)
        if not _is_fully_simulated_assignment(assignment) and not confirm_physical_output:
            raise ValueError(
                "Physical equipment requires --confirm-physical-output after verifying "
                "the wiring, sense leads, fresh cell voltage, and output-off state"
            )

        runner.restore_equipment_configuration(
            equipment_file,
            channels=[channel],
            include_unassigned_equipment=False,
        )
        runner.apply_profile(channel, profile)
        if stop_event.is_set():
            return 130

        context = {
            "cell_name": cell_name,
            "directory": str(data_directory),
            "institution_code": institution_code,
        }
        result = runner.start_test(channel, context)
        if not result.ok:
            raise RuntimeError(result.message or "Test could not be started")

        print(json.dumps({"event": "run_started", "channel": channel}), flush=True)
        while True:
            if stop_event.is_set():
                runner.stop_test(channel)
                for event in runner.poll():
                    if event_handler:
                        event_handler(event)
                    _write_event(event, show_measurements=show_measurements)
                return 130

            for event in runner.poll():
                if event_handler:
                    event_handler(event)
                _write_event(event, show_measurements=show_measurements)

            state = runner.channel_states[channel]
            if state.status is ChannelStatus.SAFETY_FAULT or state.safety_fault:
                return 2
            if state.status is ChannelStatus.ERROR:
                return 1
            if not state.is_running:
                if state.status is ChannelStatus.IDLE:
                    return 0
                raise RuntimeError(
                    f"Worker ended without a completed state (status={state.status.value})"
                )
            stop_event.wait(poll_interval_s)
    except Exception as error:  # noqa: BLE001 - provide a structured failure at the CLI boundary
        logger.exception("Headless battery run failed")
        print(json.dumps({"event": "run_failed", "error": str(error)}), file=sys.stderr, flush=True)
        return 1
    finally:
        runner.shutdown()


def _wait_for_job_event(
    runner: HeadlessRunner,
    expected_kind: str,
    *,
    timeout_s: float = 180.0,
) -> ApplicationEvent:
    """Poll managed scan/probe work until its result event arrives."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        for event in runner.poll():
            if event.kind == expected_kind:
                return event
            if event.kind == "error" and event.channel is None:
                raise RuntimeError(event.message or "Background equipment operation failed")
            _write_event(event)
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for {expected_kind.replace('_', ' ')}")


def run_resource_scan(runner: HeadlessRunner | None = None) -> int:
    """Scan available VISA resources and print the result as JSON."""
    runner = runner or HeadlessRunner()
    try:
        result = runner.scan_resources()
        if not result.ok:
            raise RuntimeError(result.message or "Resource scan could not be started")
        event = _wait_for_job_event(runner, "resources")
        print(json.dumps({"event": "resources", "data": event.payload}, default=str), flush=True)
        return 0
    except Exception as error:  # noqa: BLE001 - report failures at the CLI boundary
        logger.exception("Equipment resource scan failed")
        print(json.dumps({"event": "scan_failed", "error": str(error)}), file=sys.stderr, flush=True)
        return 1
    finally:
        runner.shutdown()


def run_equipment_probe(
    *,
    eq_type: str,
    class_name: str,
    resource_id: Any,
    setup: Mapping[str, Any] | None = None,
    runner: HeadlessRunner | None = None,
) -> int:
    """Probe one instrument and print its portable descriptor as JSON."""
    runner = runner or HeadlessRunner()
    try:
        if resource_id == "Fake":
            resources = []
        else:
            scan = runner.scan_resources()
            if not scan.ok:
                raise RuntimeError(scan.message or "Resource scan could not be started")
            resources = _wait_for_job_event(runner, "resources").payload
        result = runner.probe_equipment(eq_type, class_name, resource_id, setup, resources)
        if not result.ok:
            raise RuntimeError(result.message or "Equipment probe could not be started")
        event = _wait_for_job_event(runner, "equipment_probe")
        print(json.dumps({"event": "equipment_probe", "data": event.payload}, default=str), flush=True)
        return 0
    except Exception as error:  # noqa: BLE001 - report failures at the CLI boundary
        logger.exception("Equipment probe failed")
        print(json.dumps({"event": "probe_failed", "error": str(error)}), file=sys.stderr, flush=True)
        return 1
    finally:
        runner.shutdown()


class HeadlessControlConsole:
    """Small interactive frontend for persistent equipment and idle workers."""

    HELP = """Commands:
  scan
  probe <psu|eload|dmm|relay_board|other> <class-name> <resource-id> [setup-json]
  equipment load <exported-assignment.json> | equipment list
  channel list | channel add [number] | channel remove <number>
  assign <channel> <role-map.json>
  idle start <channel> | idle stop <channel>
  test start <channel> <profile.json> <cell-name> <data-directory>
       [--institution-code CODE] [--confirm-physical-output]
  test stop <channel>
  safety clear <channel> --cause-corrected
  status
  help
  quit"""

    def __init__(
        self,
        runner: HeadlessRunner,
        *,
        show_measurements: bool = False,
        confirm_physical_equipment: bool = False,
    ):
        self.runner = runner
        self.show_measurements = show_measurements
        self.confirm_physical_equipment = confirm_physical_equipment
        self._commands: queue.Queue[str] = queue.Queue()
        self._stop_requested = threading.Event()

    def run(self) -> int:
        input_thread = threading.Thread(target=self._read_commands, daemon=True)
        input_thread.start()
        try:
            while not self._stop_requested.is_set():
                for event in self.runner.poll():
                    _write_event(event, show_measurements=self.show_measurements)
                try:
                    command = self._commands.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    self._execute(command)
                except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as error:
                    self._write_record({"event": "command_failed", "error": str(error)})
        except KeyboardInterrupt:
            self._stop_requested.set()
        finally:
            self.runner.shutdown()
        return 0

    def request_stop(self) -> None:
        self._stop_requested.set()

    def _read_commands(self) -> None:
        while not self._stop_requested.is_set():
            try:
                command = input("battery> ")
            except (EOFError, OSError):
                self._commands.put("quit")
                return
            self._commands.put(command)

    @staticmethod
    def _write_record(record: Mapping[str, Any]) -> None:
        print(json.dumps(record, default=str, separators=(",", ":")), flush=True)

    def _execute(self, command: str) -> None:
        try:
            parts = shlex.split(command)
        except ValueError as error:
            raise ValueError(f"Could not parse command: {error}") from error
        if not parts:
            return
        action, *args = parts
        if action in {"quit", "exit"}:
            self._stop_requested.set()
        elif action in {"help", "?"}:
            print(self.HELP, flush=True)
        elif action == "scan" and not args:
            result = self.runner.scan_resources()
            self._require_ok(result)
            event = _wait_for_job_event(self.runner, "resources")
            self._write_record({"event": "resources", "data": event.payload})
        elif action == "probe":
            self._probe(args)
        elif action == "equipment":
            self._equipment(args)
        elif action == "channel":
            self._channel(args)
        elif action == "assign":
            self._assign(args)
        elif action == "idle":
            self._idle(args)
        elif action == "test":
            self._test(args)
        elif action == "safety" and len(args) == 3 and args[0] == "clear":
            if args[2] != "--cause-corrected":
                raise ValueError("Safety clearing requires --cause-corrected after the fault is resolved")
            channel = int(args[1])
            state = self.runner.channel_states.get(channel)
            if state is None:
                raise ValueError(f"Unknown channel {channel}")
            if state.is_running or state.is_idle_process_running:
                raise RuntimeError("Stop test and idle workers before clearing the safety fault")
            if not state.safety_fault and state.status is not ChannelStatus.SAFETY_FAULT:
                raise RuntimeError(f"Channel {channel} has no active safety fault")
            self._require_ok(self.runner.clear_safety_fault(channel))
            self._write_record({"event": "safety_cleared", "channel": channel})
        elif action == "status" and not args:
            self._status()
        else:
            raise ValueError("Unknown command or invalid arguments; enter 'help' for usage")

    def _probe(self, args: list[str]) -> None:
        if len(args) < 3 or len(args) > 4:
            raise ValueError("Usage: probe <type> <class-name> <resource-id> [setup-json]")
        setup = json.loads(args[3]) if len(args) == 4 else {}
        if not isinstance(setup, dict):
            raise ValueError("Probe setup JSON must be an object")
        if args[2] == "Fake":
            resources = []
        else:
            scan = self.runner.scan_resources()
            self._require_ok(scan)
            resources = _wait_for_job_event(self.runner, "resources").payload
        result = self.runner.probe_equipment(args[0], args[1], args[2], setup, resources)
        self._require_ok(result)
        event = _wait_for_job_event(self.runner, "equipment_probe")
        if (
            not _is_simulated_descriptor(event.payload)
            and not self.confirm_physical_equipment
        ):
            raise ValueError(
                "Connecting physical equipment requires --confirm-physical-equipment "
                "after verifying the instruments are in a safe output-off state"
            )
        if not self.runner.connect_equipment(event.payload):
            raise RuntimeError(self.runner.last_equipment_error or "Could not connect equipment")
        self._write_record({
            "event": "equipment_connected",
            "equipment_id": event.payload.get("equipment_id"),
            "class_name": event.payload.get("class_name"),
        })

    def _equipment(self, args: list[str]) -> None:
        if args == ["list"]:
            summary = [
                {
                    key: item.get(key)
                    for key in (
                        "equipment_id", "local_id", "class_name", "eq_idn", "res_id",
                        "instrument_channels", "owner_ready",
                    )
                }
                for item in self.runner.connected_equipment
            ]
            self._write_record({"event": "equipment", "data": summary})
            return
        if len(args) == 2 and args[0] == "load":
            payload = self.runner.configuration_store.load_equipment_assignment(args[1])
            descriptors = payload["connected_equipment_dict"].values()
            if (
                any(not _is_simulated_descriptor(item) for item in descriptors)
                and not self.confirm_physical_equipment
            ):
                raise ValueError(
                    "Loading physical equipment requires --confirm-physical-equipment "
                    "after verifying the instruments are in a safe output-off state"
                )
            restored = self.runner.restore_equipment_configuration(args[1])
            self._write_record({
                "event": "equipment_loaded",
                "channels": sorted(restored),
                "connected_count": len(self.runner.connected_equipment),
            })
            return
        raise ValueError("Usage: equipment list | equipment load <exported-assignment.json>")

    def _channel(self, args: list[str]) -> None:
        if args == ["list"]:
            self._status()
            return
        if args and args[0] == "add" and len(args) <= 2:
            channel = self.runner.add_channel(int(args[1]) if len(args) == 2 else None)
            self._write_record({"event": "channel_added", "channel": channel.number})
            return
        if len(args) == 2 and args[0] == "remove":
            channel = int(args[1])
            state = self.runner.channel_states.get(channel)
            if state is None:
                raise ValueError(f"Unknown channel {channel}")
            if state.is_running:
                raise RuntimeError("Stop the active test before removing its channel")
            if state.safety_fault or state.status is ChannelStatus.SAFETY_FAULT:
                raise RuntimeError("Clear the safety fault before removing its channel")
            self.runner.stop_idle(channel)
            if not self.runner.remove_channel(channel):
                raise ValueError(f"Unknown channel {channel}")
            self._write_record({"event": "channel_removed", "channel": channel})
            return
        raise ValueError("Usage: channel list | channel add [number] | channel remove <number>")

    def _assign(self, args: list[str]) -> None:
        if len(args) != 2:
            raise ValueError("Usage: assign <channel> <role-map.json>")
        channel = int(args[0])
        assignment = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        result = self.runner.apply_equipment_assignment(channel, assignment)
        self._require_ok(result)
        self._write_record({"event": "equipment_assigned", "channel": channel})

    def _idle(self, args: list[str]) -> None:
        if len(args) != 2 or args[0] not in {"start", "stop"}:
            raise ValueError("Usage: idle start <channel> | idle stop <channel>")
        action, channel_text = args
        channel = int(channel_text)
        if channel not in self.runner.channel_states:
            raise ValueError(f"Unknown channel {channel}")
        if action == "start":
            self._require_ok(self.runner.start_idle(channel))
            self._write_record({"event": "idle_started", "channel": channel})
        else:
            self.runner.stop_idle(channel)
            self._write_record({"event": "idle_stopped", "channel": channel})

    def _test(self, args: list[str]) -> None:
        if len(args) == 2 and args[0] == "stop":
            channel = int(args[1])
            self._require_ok(self.runner.stop_test(channel))
            self._write_record({"event": "test_stop_requested", "channel": channel})
            return
        if len(args) < 5 or args[0] != "start":
            raise ValueError(
                "Usage: test start <channel> <profile.json> <cell-name> <data-directory> "
                "[--institution-code CODE] [--confirm-physical-output] | test stop <channel>"
            )
        channel = int(args[1])
        state = self.runner.channel_states.get(channel)
        if state is None:
            raise ValueError(f"Unknown channel {channel}")
        institution_code = "LOCAL"
        confirm_physical_output = False
        remaining = iter(args[5:])
        for option in remaining:
            if option == "--confirm-physical-output":
                confirm_physical_output = True
            elif option == "--institution-code":
                try:
                    institution_code = next(remaining)
                except StopIteration as error:
                    raise ValueError("--institution-code requires a value") from error
            else:
                raise ValueError(f"Unknown test start option: {option}")
        if (
            not _is_fully_simulated_assignment(state.equipment_assignment)
            and not confirm_physical_output
        ):
            raise ValueError(
                "Physical test start requires --confirm-physical-output after verifying wiring, "
                "sense leads, fresh cell voltage, and output-off state"
            )
        profile = self.runner.load_profile(args[2])
        self.runner.apply_profile(channel, profile)
        result = self.runner.start_test(channel, {
            "cell_name": args[3],
            "directory": args[4],
            "institution_code": institution_code,
        })
        self._require_ok(result)
        self._write_record({"event": "test_started", "channel": channel})

    def _status(self) -> None:
        channels = []
        for channel, state in sorted(self.runner.channel_states.items()):
            channels.append({
                "channel": channel,
                "status": state.status.value,
                "test_running": state.is_running,
                "idle_running": state.is_idle_process_running,
                "safety_fault": state.safety_fault,
                "assigned_roles": sorted(
                    role for role, descriptor in (state.equipment_assignment or {}).items()
                    if descriptor is not None
                ),
                "latest_measurement": state.latest_measurement,
            })
        self._write_record({"event": "channel_status", "channels": channels})

    @staticmethod
    def _require_ok(result: OperationResult) -> None:
        if not result.ok:
            raise RuntimeError(result.message or "Operation failed")


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one battery test channel without the Qt GUI."
    )
    parser.add_argument("--log-directory", type=Path, help="Directory for rotating application logs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scan", help="Scan for available VISA resources")
    probe_parser = subparsers.add_parser("probe", help="Identify one instrument without connecting an owner")
    probe_parser.add_argument("--type", required=True, choices=("psu", "eload", "dmm", "relay_board", "other"))
    probe_parser.add_argument("--class-name", required=True, help="Equipment driver class name")
    probe_parser.add_argument("--resource", required=True, help="VISA resource name or Fake")
    probe_parser.add_argument("--setup-json", default="{}", help="JSON object containing driver setup")
    control_parser = subparsers.add_parser(
        "control",
        help="Open an interactive equipment and channel control session",
    )
    control_parser.add_argument("--equipment", type=Path, help="Load an exported equipment assignment")
    control_parser.add_argument(
        "--confirm-physical-equipment",
        action="store_true",
        help="Confirm physical instruments have been checked and are output off before connecting",
    )
    control_parser.add_argument(
        "--show-measurements",
        action="store_true",
        help="Print idle measurement events as JSON Lines",
    )
    run_parser = subparsers.add_parser("run", help="Run one channel to completion")
    run_parser.add_argument("--profile", required=True, type=Path, help="Schema-versioned profile JSON")
    run_parser.add_argument(
        "--equipment", required=True, type=Path, help="Exported equipment and assignment JSON"
    )
    run_parser.add_argument("--channel", type=int, default=0, help="Battery channel number (default: 0)")
    run_parser.add_argument("--cell-name", required=True, help="Cell identifier for output files")
    run_parser.add_argument("--data-directory", required=True, type=Path, help="Root directory for BDF output")
    run_parser.add_argument("--institution-code", default="LOCAL", help="BDF institution code")
    run_parser.add_argument("--poll-interval", type=float, default=0.1, help="Worker polling interval in seconds")
    run_parser.add_argument(
        "--confirm-physical-output",
        action="store_true",
        help="Confirm wiring, sense leads, fresh cell voltage, and outputs-off state were checked",
    )
    run_parser.add_argument(
        "--show-measurements",
        action="store_true",
        help="Write live measurement events to stdout as JSON lines",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    options = parser.parse_args(arguments)
    configure_application_logging(options.log_directory)
    if options.command == "scan":
        return run_resource_scan()
    if options.command == "probe":
        try:
            setup = json.loads(options.setup_json)
            if not isinstance(setup, dict):
                raise ValueError("--setup-json must contain a JSON object")
        except (json.JSONDecodeError, ValueError) as error:
            parser.error(str(error))
        return run_equipment_probe(
            eq_type=options.type,
            class_name=options.class_name,
            resource_id=options.resource,
            setup=setup,
        )
    if options.command == "control":
        runner = HeadlessRunner()
        stop_event = threading.Event()
        previous_handlers = {}

        def request_control_stop(_signum, _frame):
            stop_event.set()

        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, request_control_stop)
        try:
            if options.equipment:
                payload = runner.configuration_store.load_equipment_assignment(options.equipment)
                descriptors = payload["connected_equipment_dict"].values()
                if (
                    any(not _is_simulated_descriptor(item) for item in descriptors)
                    and not options.confirm_physical_equipment
                ):
                    raise ValueError(
                        "Physical equipment requires --confirm-physical-equipment "
                        "after verifying the instruments are output off"
                    )
                runner.restore_equipment_configuration(options.equipment)
            else:
                runner.add_channel(0)
            runner.application.restart_idle_processes = False
            console = HeadlessControlConsole(
                runner,
                show_measurements=options.show_measurements,
                confirm_physical_equipment=options.confirm_physical_equipment,
            )

            def watch_control_stop():
                stop_event.wait()
                console.request_stop()

            threading.Thread(target=watch_control_stop, daemon=True).start()
            try:
                return console.run()
            finally:
                stop_event.set()
        except Exception as error:  # noqa: BLE001 - report startup failures at the CLI boundary
            logger.exception("Headless control session failed")
            print(json.dumps({"event": "control_failed", "error": str(error)}), file=sys.stderr, flush=True)
            runner.shutdown()
            return 1
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)

    stop_event = threading.Event()
    previous_handlers = {}

    def request_stop(_signum, _frame):
        stop_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, request_stop)
    try:
        return run_headless(
            profile_file=options.profile,
            equipment_file=options.equipment,
            channel=options.channel,
            cell_name=options.cell_name,
            data_directory=options.data_directory,
            institution_code=options.institution_code,
            poll_interval_s=options.poll_interval,
            confirm_physical_output=options.confirm_physical_output,
            show_measurements=options.show_measurements,
            stop_event=stop_event,
        )
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    raise SystemExit(main())
