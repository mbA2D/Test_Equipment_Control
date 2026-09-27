"""Typed state owned by the battery GUI application."""

from dataclasses import dataclass, field
from enum import Enum
from multiprocessing.queues import Queue
from typing import Any


class ChannelStatus(str, Enum):
    IDLE = "idle"
    CONFIGURING = "configuring"
    RUNNING = "running"
    STOPPING = "stopping"
    SAFETY_FAULT = "safety_fault"
    ERROR = "error"


@dataclass
class ChannelState:
    """Runtime state for one battery channel.

    Queue and process handles are intentionally runtime-only. They must never
    be serialized with test or equipment configuration.
    """

    number: int
    equipment_assignment: dict[str, Any] | None = None
    test_configuration: dict[str, Any] | None = None
    cell_name: str = "CELL_NAME"
    data_queue: Queue | None = None
    control_queue: Queue | None = None
    idle_control_queue: Queue | None = None
    test_process: Any = None
    idle_process: Any = None
    latest_measurement: dict[str, Any] = field(default_factory=dict)
    status: ChannelStatus = ChannelStatus.IDLE
    safety_fault: bool = False

    @property
    def is_running(self) -> bool:
        return self.test_process is not None and self.test_process.is_alive()

    @property
    def is_idle_process_running(self) -> bool:
        return self.idle_process is not None and self.idle_process.is_alive()
