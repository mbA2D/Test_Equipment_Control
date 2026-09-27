"""Lifecycle adapter for one battery test channel."""

import queue
from multiprocessing.queues import Queue

from .execution import TestExecutionService
from .process_manager import ProcessManager
from .state import ChannelState, ChannelStatus


class ChannelController:
    """Own process lifecycle for a single channel.

    The execution target is supplied by the charge/discharge process-entry
    module, keeping process lifecycle separate from test execution.
    """

    def __init__(
        self,
        state: ChannelState,
        process_manager: ProcessManager | None = None,
        execution_service: TestExecutionService | None = None,
    ):
        self.state = state
        self.process_manager = process_manager or ProcessManager()
        self.execution_service = execution_service or TestExecutionService()

    def start_test(self) -> bool:
        if self.state.equipment_assignment is None:
            return False
        if self.state.test_configuration is None:
            return False
        if self.state.is_running:
            return False

        self.stop_idle()
        self._clear_queue(self.state.data_queue)
        self._clear_queue(self.state.control_queue)
        target, args = self.execution_service.start_test(self.state)
        self.state.test_process = self.process_manager.start(target, args)
        self.state.status = ChannelStatus.RUNNING
        return True

    def start_idle(self) -> bool:
        assignment = self.state.equipment_assignment
        if assignment is None:
            return False
        if not any(assignment.get(name) is not None for name in ("psu", "eload", "dmm_v")):
            return False
        if self.state.is_running or self.state.is_idle_process_running:
            return False

        self._clear_queue(self.state.data_queue)
        self._clear_queue(self.state.idle_control_queue)
        target, args = self.execution_service.start_idle(self.state)
        self.state.idle_process = self.process_manager.start(target, args)
        self.state.status = ChannelStatus.IDLE
        return True

    def stop_test(self) -> None:
        self.state.status = ChannelStatus.STOPPING
        self.process_manager.stop(self.state.test_process, self.state.control_queue)
        self.state.test_process = None
        if not self.state.safety_fault:
            self.state.status = ChannelStatus.IDLE

    def stop_idle(self) -> None:
        self.process_manager.stop(self.state.idle_process, self.state.idle_control_queue)
        self.state.idle_process = None

    def stop_all(self) -> None:
        self.stop_test()
        self.stop_idle()

    @staticmethod
    def _clear_queue(channel_queue: Queue | None) -> None:
        if channel_queue is None:
            return
        while True:
            try:
                channel_queue.get_nowait()
            except queue.Empty:
                return
