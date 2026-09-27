"""Equipment-owner process management for the battery application."""

from multiprocessing import Manager, Queue
import queue
import time
from typing import Any
from uuid import uuid4

import equipment as eq

from .process_manager import ProcessManager


class EquipmentManager:
    """Own connected equipment descriptors and their owner processes."""

    OWNER_STARTUP_TIMEOUT_S = 15.0

    def __init__(self, process_manager: ProcessManager | None = None):
        self.process_manager = process_manager or ProcessManager()
        self.connected_equipment: list[dict[str, Any]] = []
        self.owner_processes: list[dict[str, Any]] = []
        self._response_manager = Manager()
        self._closed = False
        self.last_connection_error: str | None = None

    @staticmethod
    def physical_resource_ids(resource: Any) -> set[Any]:
        if isinstance(resource, dict):
            return {
                value for key, value in resource.items()
                if key.startswith("res_id") and value not in (None, "Fake")
            }
        return set() if resource in (None, "Fake") else {resource}

    def is_duplicate(self, descriptor: dict[str, Any]) -> bool:
        new_ids = self.physical_resource_ids(descriptor.get("res_id"))
        if not new_ids:
            return False
        return any(
            new_ids & self.physical_resource_ids(existing.get("res_id"))
            for existing in self.connected_equipment
        )

    def next_local_id(self, descriptor: dict[str, Any]) -> Any:
        local_id = descriptor.get("local_id")
        if local_id is not None:
            return local_id
        used_ids = {
            equipment.get("local_id")
            for equipment in self.connected_equipment
            if equipment.get("local_id") is not None
        }
        candidate = len(self.connected_equipment)
        while candidate in used_ids:
            candidate += 1
        return candidate

    @staticmethod
    def has_canonical_channels(channels: Any) -> bool:
        """Accept singleton ``[0]`` or contiguous multi-channel ``[1, ..., N]``."""
        if not isinstance(channels, list) or not channels:
            return False
        if any(
            not isinstance(channel, int) or isinstance(channel, bool) or channel < 0
            for channel in channels
        ):
            return False
        return channels == [0] or channels == list(range(1, len(channels) + 1))

    def connect(self, descriptor: dict[str, Any]) -> bool:
        self.last_connection_error = None
        startup_result_queue = None
        queue_in = None
        process = None
        if self.is_duplicate(descriptor):
            self.last_connection_error = "This physical resource is already connected"
            return False

        local_id = self.next_local_id(descriptor)
        if any(item.get("local_id") == local_id for item in self.connected_equipment):
            self.last_connection_error = f"Equipment local ID {local_id} is already in use"
            return False

        equipment_id = descriptor.get("equipment_id") or uuid4().hex
        if any(item.get("equipment_id") == equipment_id for item in self.connected_equipment):
            self.last_connection_error = "Equipment identity is already connected"
            return False

        instrument_channels = descriptor.get("instrument_channels")
        if not instrument_channels:
            instrument_channels = eq.get_instrument_channels(
                descriptor.get("class_name"),
                None,
                descriptor.get("setup_dict"),
            )
        if not self.has_canonical_channels(instrument_channels):
            self.last_connection_error = "Equipment reported an invalid channel layout"
            return False

        try:
            startup_result_queue = Queue()
            queue_in = Queue()
            response_routes = self._response_manager.dict()
            process = self.process_manager.start(
                eq.virtual_device_management_process,
                (descriptor["eq_type"], descriptor, queue_in, response_routes, startup_result_queue),
            )
            deadline = time.monotonic() + self.OWNER_STARTUP_TIMEOUT_S
            startup_ok = False
            startup_payload: dict[str, Any] = {}
            while time.monotonic() < deadline:
                try:
                    startup_ok, startup_payload = startup_result_queue.get(timeout=0.1)
                    break
                except queue.Empty:
                    if not process.is_alive():
                        raise RuntimeError(
                            f"Equipment owner exited before initialization (exit code {process.exitcode})"
                        )
            else:
                raise TimeoutError(
                    f"Equipment owner did not initialize within {self.OWNER_STARTUP_TIMEOUT_S:g} seconds"
                )

            if not startup_ok:
                error_type = startup_payload.get("error_type", "ConnectionError")
                message = startup_payload.get("message", "Equipment initialization failed")
                raise RuntimeError(f"{error_type}: {message}")
            if startup_payload.get("resource_id") != descriptor["res_id"]:
                raise RuntimeError("Equipment owner acknowledged a different resource")
            observed_idn = startup_payload.get("eq_idn")
            if (
                descriptor.get("class_name") not in eq.SIMULATED_FAKE_CLASSES
                and descriptor.get("eq_idn")
                and observed_idn
                and descriptor["eq_idn"] != observed_idn
            ):
                raise RuntimeError(
                    f"Instrument identity changed at the selected resource: {observed_idn}"
                )
        except Exception as error:
            self.last_connection_error = str(error)
            if process is not None:
                self.process_manager.stop(process, queue_in)
            if queue_in is not None:
                queue_in.close()
                queue_in.join_thread()
            if startup_result_queue is not None:
                startup_result_queue.close()
                startup_result_queue.join_thread()
            return False

        startup_result_queue.close()
        startup_result_queue.join_thread()
        equipment = {
            "equipment_id": equipment_id,
            "local_id": local_id,
            "res_id": descriptor["res_id"],
            "eq_type": descriptor["eq_type"],
            "eq_idn": descriptor["eq_idn"],
            "class_name": descriptor["class_name"],
            "rated_limits": startup_payload.get("rated_limits"),
            "capabilities": list(descriptor.get("capabilities") or []),
            "instrument_channels": list(instrument_channels),
            "setup_dict": descriptor["setup_dict"],
            "queue_in": queue_in,
            "response_routes": response_routes,
            "owners": {},
            "already_assigned": False,
            "owner_ready": True,
        }
        self.connected_equipment.append(equipment)
        self.owner_processes.append({"local_id": local_id, "process": process})
        return True

    def queue_for_local_id(self, local_id: Any):
        for equipment in self.connected_equipment:
            if equipment["local_id"] == local_id:
                return equipment["queue_in"]
        return None

    def disconnect_all(self) -> None:
        for owner in self.owner_processes:
            queue_in = self.queue_for_local_id(owner["local_id"])
            self.process_manager.stop(owner["process"], queue_in)
        for equipment in self.connected_equipment:
            equipment["response_routes"].clear()
            equipment["owners"].clear()
        self.connected_equipment.clear()
        self.owner_processes.clear()

    def response_queue_for(
        self,
        local_id: Any,
        client_id: str,
        battery_channel: int,
        instrument_channel: int,
    ):
        """Claim an instrument slot and register its private response queue."""
        for equipment in self.connected_equipment:
            if equipment["local_id"] == local_id:
                if (
                    not isinstance(instrument_channel, int)
                    or isinstance(instrument_channel, bool)
                    or instrument_channel not in equipment.get("instrument_channels", [0])
                ):
                    return None
                slot = str(instrument_channel)
                owner = equipment["owners"].get(slot)
                if owner not in (None, battery_channel):
                    return None
                equipment["owners"][slot] = battery_channel
                response_queue = self._response_manager.Queue()
                equipment["response_routes"][client_id] = response_queue
                return response_queue
        return None

    def release_channel_ownership(self, battery_channel: int) -> None:
        """Release all instrument slots held by one battery channel."""
        for equipment in self.connected_equipment:
            for slot, owner in list(equipment["owners"].items()):
                if owner == battery_channel:
                    del equipment["owners"][slot]
            for client_id in list(equipment["response_routes"].keys()):
                if client_id.startswith(f"channel-{battery_channel}-"):
                    del equipment["response_routes"][client_id]

    def close(self) -> None:
        """Stop equipment owners and shut down the response-queue manager."""
        if self._closed:
            return
        self.disconnect_all()
        self._response_manager.shutdown()
        self._closed = True
