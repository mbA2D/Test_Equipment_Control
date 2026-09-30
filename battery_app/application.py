"""Qt-independent application orchestration for battery test channels."""

from __future__ import annotations

import queue
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from multiprocessing import Queue
from typing import Any

from .channel_controller import ChannelController
from .equipment_manager import EquipmentManager
from .messages import MessageRouter
from .persistence import ConfigurationStore
from .process_manager import ProcessManager
from .profile_validation import execution_configuration, validate_profile_configuration
from .equipment_limits import EquipmentLimitError, validate_profile_equipment_limits
from .simulation import (
    SIMULATED_FAKE_CLASSES,
    assignment_uses_fake_equipment,
    is_simulated_cell_name,
)
from .state import ChannelState, ChannelStatus


@dataclass(frozen=True)
class ApplicationEvent:
    """A state change for a presentation adapter to render.

    Events contain no Qt objects and do not require a particular frontend.  The
    desktop GUI currently renders them, while a future CLI or service can emit
    the same information as structured output.
    """

    kind: str
    channel: int | None
    payload: Any = None
    message: str | None = None
    color: str | None = None


@dataclass(frozen=True)
class OperationResult:
    """Success or a user-facing reason that an application operation was refused."""

    ok: bool
    message: str | None = None


ControllerFactory = Callable[[ChannelState, ProcessManager], ChannelController]


def _scan_resources_worker(result_queue) -> None:
    """Scan host VISA resources outside the presentation process."""
    import equipment as eq

    try:
        result_queue.put(("resources", True, eq.get_resources_list()))
    except Exception as error:  # noqa: BLE001 - return worker failures to the application event stream
        result_queue.put(("resources", False, str(error)))


def _probe_equipment_worker(eq_type, class_name, resource_id, setup_dict, resources_list, result_queue) -> None:
    """Identify one selected instrument and return a portable descriptor."""
    import equipment as eq

    try:
        chooser = {
            "psu": eq.powerSupplies.choose_psu,
            "eload": eq.eLoads.choose_eload,
            "dmm": eq.dmms.choose_dmm,
            "relay_board": eq.otherEquipment.choose_equipment,
            "other": eq.otherEquipment.choose_equipment,
        }[eq_type]
        selected = chooser(
            class_name=class_name,
            resource_id=resource_id,
            setup_dict=setup_dict,
            resources_list=resources_list,
            interactive=False,
            probe_only=True,
        )
        if selected is None:
            result_queue.put(("equipment_probe", False, "No equipment was selected"))
            return
        result_queue.put(("equipment_probe", True, eq.get_res_id_dict_and_disconnect(selected)))
    except Exception as error:  # noqa: BLE001 - return worker failures to the application event stream
        result_queue.put(("equipment_probe", False, str(error)))


class BatteryApplication:
    """Own battery-channel state and non-Qt lifecycle services.

    The application owns runtime channels, equipment-owner processes, worker
    polling, and test start/stop behaviour.  A frontend owns only user input
    and rendering of :class:`ApplicationEvent` values.
    """

    def __init__(
        self,
        process_manager: ProcessManager | None = None,
        equipment_manager: EquipmentManager | None = None,
        configuration_store: ConfigurationStore | None = None,
        message_router: MessageRouter | None = None,
        controller_factory: ControllerFactory | None = None,
    ):
        self.process_manager = process_manager or getattr(
            equipment_manager, "process_manager", None
        ) or ProcessManager()
        self.equipment_manager = equipment_manager or EquipmentManager(self.process_manager)
        self.configuration_store = configuration_store or ConfigurationStore()
        self.message_router = message_router or MessageRouter()
        self._controller_factory = controller_factory or self._create_controller
        self.channel_states: dict[int, ChannelState] = {}
        self.channel_controllers: dict[int, ChannelController] = {}
        self.restart_idle_processes = True
        self._background_results = Queue()
        self._background_processes: dict[str, Any] = {}
        self._closed = False

    def scan_resources(self) -> OperationResult:
        """Start a managed VISA scan and report its result through ``poll``."""
        return self._start_background_job("resources", _scan_resources_worker)

    def probe_equipment(
        self,
        eq_type: str,
        class_name: str,
        resource_id: Any,
        setup_dict: Mapping[str, Any] | None = None,
        resources_list: list[dict[str, Any]] | None = None,
    ) -> OperationResult:
        """Identify a selected instrument in a managed worker process."""
        if eq_type not in {"psu", "eload", "dmm", "relay_board", "other"}:
            return OperationResult(False, f"Unsupported equipment category: {eq_type}")
        if resource_id is None and "Fake" not in class_name:
            return OperationResult(False, "Select a physical VISA resource for non-fake equipment.")
        return self._start_background_job(
            "equipment_probe",
            _probe_equipment_worker,
            (eq_type, class_name, resource_id, dict(setup_dict or {}), resources_list),
        )

    def _start_background_job(self, kind: str, target, args=()) -> OperationResult:
        if self._closed:
            return OperationResult(False, "BatteryApplication is closed")
        process = self._background_processes.get(kind)
        if process is not None:
            try:
                if process.is_alive():
                    return OperationResult(False, f"A {kind.replace('_', ' ')} job is already running")
                process.join()
                process.close()
            except ValueError:
                pass
        try:
            process = self.process_manager.start(target, (*args, self._background_results))
        except Exception as error:  # noqa: BLE001 - process startup can fail for platform-specific reasons
            return OperationResult(False, f"Could not start {kind.replace('_', ' ')} job: {error}")
        self._background_processes[kind] = process
        return OperationResult(True)

    @property
    def connected_equipment(self) -> list[dict[str, Any]]:
        """Return the manager-owned connected-equipment collection."""

        return self.equipment_manager.connected_equipment

    @property
    def owner_processes(self) -> list[dict[str, Any]]:
        """Return the manager-owned equipment-owner process collection."""

        return self.equipment_manager.owner_processes

    @staticmethod
    def _create_controller(
        state: ChannelState,
        process_manager: ProcessManager,
    ) -> ChannelController:
        return ChannelController(state, process_manager)

    def add_channel(self, channel: int | None = None) -> ChannelState:
        """Create one channel and its runtime-only queues and controller."""

        if self._closed:
            raise RuntimeError("BatteryApplication is closed")
        if channel is None:
            channel = self.next_channel_number()
        if not isinstance(channel, int) or isinstance(channel, bool) or channel < 0:
            raise ValueError("channel must be a non-negative integer")
        if channel in self.channel_states:
            raise ValueError(f"Channel {channel} already exists")

        state = ChannelState(
            number=channel,
            data_queue=Queue(),
            control_queue=Queue(),
            idle_control_queue=Queue(),
        )
        self.channel_states[channel] = state
        self.channel_controllers[channel] = self._controller_factory(state, self.process_manager)
        return state

    def next_channel_number(self) -> int:
        """Return the lowest unused non-negative channel number."""

        channel = 0
        while channel in self.channel_states:
            channel += 1
        return channel

    def reset_channels(self, count: int) -> list[ChannelState]:
        """Stop and replace the complete channel set with ``count`` channels."""

        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("count must be a non-negative integer")
        self.remove_channels()
        return [self.add_channel(channel) for channel in range(count)]

    def remove_channels(self) -> None:
        """Stop channels and release every instrument slot they own."""

        for channel, controller in list(self.channel_controllers.items()):
            controller.stop_all()
            self.equipment_manager.release_channel_ownership(channel)
        self.channel_controllers.clear()
        self.channel_states.clear()

    def remove_channel(self, channel: int) -> bool:
        """Stop one channel and release its equipment ownership."""

        controller = self.channel_controllers.pop(channel, None)
        if controller is None:
            return False
        controller.stop_all()
        self.equipment_manager.release_channel_ownership(channel)
        self.channel_states.pop(channel, None)
        return True

    def connect_equipment(self, descriptor: dict[str, Any]) -> bool:
        """Register one descriptor and start its equipment-owner process."""

        if self._closed:
            return False
        return self.equipment_manager.connect(descriptor)

    def disconnect_all_equipment(self) -> None:
        """Disconnect every equipment owner after stopping channel workers."""

        for controller in self.channel_controllers.values():
            controller.stop_all()
        self.equipment_manager.disconnect_all()

    @staticmethod
    def resolve_connected_equipment(
        assignment: Mapping[str, Any] | Any,
        connected_equipment: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Resolve a role descriptor by its persisted equipment identity."""

        if not isinstance(assignment, Mapping):
            return None
        equipment_id = assignment.get("equipment_id")
        if not isinstance(equipment_id, str) or not equipment_id:
            return None
        candidates = [
            item
            for item in connected_equipment
            if item.get("equipment_id") == equipment_id
        ]
        if len(candidates) != 1:
            return None
        resolved = candidates[0]
        expected_class = assignment.get("class_name")
        if expected_class is not None and expected_class != resolved.get("class_name"):
            return None
        return resolved

    def apply_equipment_assignment(
        self,
        channel: int,
        assignment: Mapping[str, Any],
    ) -> OperationResult:
        """Bind an assignment to equipment owners and claim its slots.

        The input remains serializable.  This method adds runtime proxy queues
        only to the copy retained in :class:`ChannelState`.
        """

        state = self.channel_states.get(channel)
        if state is None:
            return OperationResult(False, f"Unknown channel {channel}")
        if not isinstance(assignment, Mapping):
            return OperationResult(False, "Equipment assignment must be a mapping")
        if not any(value is not None for value in assignment.values()):
            return OperationResult(False, "No equipment assigned")

        controller = self.channel_controllers[channel]
        controller.stop_idle()
        self.equipment_manager.release_channel_ownership(channel)
        prepared_assignment = deepcopy(dict(assignment))

        for role, descriptor in prepared_assignment.items():
            if descriptor is None:
                continue
            if not isinstance(descriptor, dict):
                return self._assignment_error(channel, f"Equipment role {role} is invalid")

            resource = descriptor.get("res_id")
            if not isinstance(resource, dict):
                return self._assignment_error(channel, f"Equipment role {role} has no resource identity")

            connected = self.resolve_connected_equipment(resource, self.connected_equipment)
            if connected is None:
                return self._assignment_error(
                    channel,
                    f"Equipment role {role} does not match exactly one connected instrument",
                )

            local_id = connected["local_id"]
            instrument_channel = resource.get("eq_ch")
            valid_channels = connected.get("instrument_channels", [0])
            if (
                not isinstance(instrument_channel, int)
                or isinstance(instrument_channel, bool)
                or instrument_channel not in valid_channels
            ):
                return self._assignment_error(
                    channel,
                    f"Equipment role {role} has invalid equipment channel {instrument_channel!r}",
                )

            queue_in = self.equipment_manager.queue_for_local_id(local_id)
            client_id = f"channel-{channel}-{role}"
            response_queue = self.equipment_manager.response_queue_for(
                local_id,
                client_id,
                channel,
                instrument_channel,
            )
            if response_queue is None:
                return self._assignment_error(
                    channel,
                    f"Equipment for role {role} is already owned by another battery channel",
                )

            resource.update({
                "equipment_id": connected["equipment_id"],
                "eq_idn": connected.get("eq_idn"),
                "class_name": connected.get("class_name"),
                "resource_id": connected.get("res_id"),
                "local_id": local_id,
                "queue_in": queue_in,
                "client_id": client_id,
                "response_queue": response_queue,
            })
            descriptor.update({
                "class_name": connected["class_name"],
                "setup_dict": dict(connected["setup_dict"]),
            })

        state.equipment_assignment = prepared_assignment
        return OperationResult(True)

    def _assignment_error(self, channel: int, message: str) -> OperationResult:
        """Release partial claims and leave a rejected reassignment unusable."""

        self.equipment_manager.release_channel_ownership(channel)
        self.channel_states[channel].equipment_assignment = None
        return OperationResult(False, message)

    def apply_profile(
        self,
        channel: int,
        configuration: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate and store a portable profile for one channel."""

        state = self._channel_state(channel)
        profile = validate_profile_configuration(configuration)
        state.test_configuration = profile
        return profile

    def set_cell_name(self, channel: int, cell_name: str) -> OperationResult:
        """Store the channel's GUI-owned cell context outside its profile."""

        state = self.channel_states.get(channel)
        if state is None:
            return OperationResult(False, f"Unknown channel {channel}")
        normalized = cell_name.strip().replace(" ", "_") if isinstance(cell_name, str) else ""
        state.cell_name = normalized or "CELL_NAME"
        return OperationResult(True)

    def build_execution_configuration(
        self,
        configuration: Mapping[str, Any],
        run_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Combine a validated profile with frontend-supplied run context."""

        cell_name = run_context.get("cell_name")
        directory = run_context.get("directory")
        institution_code = run_context.get("institution_code")
        runtime = execution_configuration(
            configuration,
            cell_name=cell_name,
            directory=directory,
        )
        runtime["institution_code"] = (
            institution_code.strip()
            if isinstance(institution_code, str) and institution_code.strip()
            else "LOCAL"
        )
        return runtime

    def start_test(self, channel: int, run_context: Mapping[str, Any]) -> OperationResult:
        """Start a channel worker using a temporary runtime configuration."""

        state = self.channel_states.get(channel)
        if state is None:
            return OperationResult(False, f"Unknown channel {channel}")
        if state.safety_fault:
            return OperationResult(False, "Check and clear the safety error before starting a test")
        if state.equipment_assignment is None:
            return OperationResult(False, "Please assign equipment before starting a test")
        if state.test_configuration is None:
            return OperationResult(False, "Please configure a test before starting a test")

        execution = self.build_execution_configuration(state.test_configuration, run_context)
        if (
            assignment_uses_fake_equipment(state.equipment_assignment)
            and not is_simulated_cell_name(execution["cell_name"])
        ):
            return OperationResult(False, "Fake Test equipment requires SIMULATED_LG_MJ1")

        profile = state.test_configuration
        try:
            validate_profile_equipment_limits(
                profile,
                self._assigned_equipment_limits(state.equipment_assignment),
            )
        except EquipmentLimitError as error:
            return OperationResult(False, str(error))

        try:
            state.test_configuration = execution
            self.channel_controllers[channel].stop_idle()
            started = self.channel_controllers[channel].start_test()
        finally:
            state.test_configuration = profile
        if not started:
            return OperationResult(False, "Test could not be started")
        return OperationResult(True)

    def _assigned_equipment_limits(
        self,
        assignment: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Resolve model ratings from owner-ready equipment, not profile data."""

        limits_by_role = {}
        for role, descriptor in assignment.items():
            if not isinstance(descriptor, Mapping):
                continue
            class_name = descriptor.get("class_name")
            resolved = self.resolve_connected_equipment(
                descriptor.get("res_id"),
                self.connected_equipment,
            )
            equipment = resolved or descriptor
            resolved_class = equipment.get("class_name", class_name)
            limits_by_role[role] = {
                "class_name": resolved_class,
                "eq_idn": equipment.get("eq_idn", descriptor.get("eq_idn")),
                "rated_limits": equipment.get("rated_limits"),
                "is_fake": (
                    resolved_class in SIMULATED_FAKE_CLASSES
                    or equipment.get("res_id") == "Fake"
                ),
            }
        return limits_by_role

    def start_idle(self, channel: int) -> OperationResult:
        """Start idle measurement for one configured non-running channel."""

        state = self.channel_states.get(channel)
        if state is None:
            return OperationResult(False, f"Unknown channel {channel}")
        if state.safety_fault or state.status is ChannelStatus.SAFETY_FAULT:
            return OperationResult(False, "Clear the safety fault before starting idle measurement")
        if self.channel_controllers[channel].start_idle():
            return OperationResult(True)
        return OperationResult(False, "Idle measurement could not be started")

    def stop_idle(self, channel: int) -> None:
        """Stop one channel's idle worker if it is running."""

        controller = self.channel_controllers.get(channel)
        if controller is not None:
            controller.stop_idle()

    def stop_test(self, channel: int) -> OperationResult:
        """Stop one channel's test worker cooperatively, then forcibly if needed."""

        controller = self.channel_controllers.get(channel)
        if controller is None:
            return OperationResult(False, f"Unknown channel {channel}")
        controller.stop_test()
        return OperationResult(True)

    def clear_safety_fault(self, channel: int) -> OperationResult:
        """Clear an acknowledged safety fault in channel state."""

        state = self.channel_states.get(channel)
        if state is None:
            return OperationResult(False, f"Unknown channel {channel}")
        state.safety_fault = False
        if state.status is ChannelStatus.SAFETY_FAULT:
            state.status = ChannelStatus.IDLE
        return OperationResult(True)

    def poll(self) -> list[ApplicationEvent]:
        """Update state from channel workers and return renderable events."""

        events: list[ApplicationEvent] = []
        while True:
            try:
                kind, ok, payload = self._background_results.get_nowait()
            except queue.Empty:
                break
            if kind == "resources":
                events.append(ApplicationEvent("resources", None, payload) if ok else ApplicationEvent(
                    "error", None, {"job": kind}, f"Resource scan failed: {payload}", "#b42318"
                ))
            elif kind == "equipment_probe":
                events.append(ApplicationEvent("equipment_probe", None, payload) if ok else ApplicationEvent(
                    "error", None, {"job": kind}, f"Equipment connection failed: {payload}", "#b42318"
                ))
        for kind, process in list(self._background_processes.items()):
            try:
                if process.is_alive():
                    continue
                exit_code = process.exitcode
                process.join()
                process.close()
            except ValueError:
                exit_code = 0
            del self._background_processes[kind]
            if exit_code not in (None, 0):
                events.append(ApplicationEvent(
                    "error", None, {"job": kind, "exit_code": exit_code},
                    f"{kind.replace('_', ' ').capitalize()} worker stopped unexpectedly (exit code {exit_code})",
                    "#b42318",
                ))

        for channel, state in self.channel_states.items():
            if state.data_queue is not None:
                self.message_router.drain(
                    channel,
                    state.data_queue,
                    lambda number, message: events.extend(self._handle_channel_message(number, message)),
                )
            events.extend(self._collect_worker_exit_events(channel, state))
            self._start_idle_if_needed(channel, state, events)
        return events

    @staticmethod
    def _collect_worker_exit_events(
        channel: int,
        state: ChannelState,
    ) -> list[ApplicationEvent]:
        """Release completed workers and report failures that could not use the queue."""

        events: list[ApplicationEvent] = []
        for attribute, worker_name in (
            ("test_process", "Charge/discharge worker"),
            ("idle_process", "Idle worker"),
        ):
            process = getattr(state, attribute)
            if process is None:
                continue
            try:
                if process.is_alive():
                    continue
                exit_code = process.exitcode
            except ValueError:
                # The process handle was already closed elsewhere.
                setattr(state, attribute, None)
                continue

            setattr(state, attribute, None)
            try:
                process.close()
            except ValueError:
                pass

            if exit_code not in (None, 0) and not state.safety_fault:
                state.status = ChannelStatus.ERROR
                events.append(ApplicationEvent(
                    "error",
                    channel,
                    {"worker": worker_name, "exit_code": exit_code},
                    f"{worker_name} stopped unexpectedly (exit code {exit_code})",
                    "#b42318",
                ))
        return events

    def _start_idle_if_needed(
        self,
        channel: int,
        state: ChannelState,
        events: list[ApplicationEvent],
    ) -> None:
        if (
            not self.restart_idle_processes
            or state.equipment_assignment is None
            or assignment_uses_fake_equipment(state.equipment_assignment)
            or state.is_running
            or state.is_idle_process_running
            or state.status in (ChannelStatus.ERROR, ChannelStatus.SAFETY_FAULT, ChannelStatus.STOPPING)
        ):
            return

        next_status = "N/A"
        try:
            next_status = state.test_configuration["settings_cycle_list_step_list"][0][0]["cycle_display"]
        except (KeyError, TypeError, IndexError):
            pass
        if self.start_idle(channel).ok:
            events.append(ApplicationEvent("status", channel, ("Idle", next_status)))

    def _handle_channel_message(
        self,
        channel: int,
        message: dict[str, Any],
    ) -> list[ApplicationEvent]:
        """Apply one worker message and return the resulting presentation events."""

        state = self.channel_states[channel]
        message_type = message.get("type")
        if message_type == "status":
            try:
                current, next_status = message["data"]
            except (KeyError, TypeError, ValueError):
                return [ApplicationEvent("warning", channel, message, "Invalid status message")]
            state.status = ChannelStatus.RUNNING
            return [
                ApplicationEvent(
                    "status",
                    channel,
                    (current, next_status),
                    f"Entered {current}; next: {next_status}",
                )
            ]
        if message_type == "measurement":
            measurement = message.get("data")
            if not isinstance(measurement, dict):
                return [ApplicationEvent("warning", channel, message, "Invalid measurement message")]
            state.latest_measurement = measurement
            return [ApplicationEvent("measurement", channel, measurement)]
        if message_type == "error":
            error = message.get("data")
            if isinstance(error, dict):
                error_message = error.get("message")
            else:
                error_message = error
            if not isinstance(error_message, str) or not error_message.strip():
                error_message = "Worker reported an invalid failure message"
            if state.status is ChannelStatus.ERROR:
                return []
            if not state.safety_fault:
                state.status = ChannelStatus.ERROR
            return [
                ApplicationEvent(
                    "error",
                    channel,
                    error,
                    error_message,
                    "#b42318",
                )
            ]
        if message_type == "end_condition" and message.get("data") == "safety_condition":
            state.safety_fault = True
            state.status = ChannelStatus.SAFETY_FAULT
            return [
                ApplicationEvent(
                    "safety_fault",
                    channel,
                    message,
                    "Safety error - test stopped",
                    "#b42318",
                )
            ]
        if message_type == "event":
            event = message.get("data", {})
            if not isinstance(event, dict):
                event = {"message": str(event)}
            event_message = event.get("message", "Status update")
            if event_message in ("All cycles completed", "Safety limit reached; all cycles stopped"):
                state.status = ChannelStatus.SAFETY_FAULT if state.safety_fault else ChannelStatus.IDLE
            return [
                ApplicationEvent(
                    "event",
                    channel,
                    event,
                    str(event_message),
                    event.get("color"),
                )
            ]
        return []

    def shutdown(self) -> None:
        """Stop channels, equipment owners, and the response-queue manager."""

        if self._closed:
            return
        for process in self._background_processes.values():
            self.process_manager.stop(process)
        self._background_processes.clear()
        self.remove_channels()
        self.equipment_manager.close()
        self._background_results.close()
        self._background_results.join_thread()
        self._closed = True

    def _channel_state(self, channel: int) -> ChannelState:
        try:
            return self.channel_states[channel]
        except KeyError as error:
            raise ValueError(f"Unknown channel {channel}") from error
