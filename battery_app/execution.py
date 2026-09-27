"""Stable execution-service boundary for channel controllers."""

from typing import Any

from charge_discharge.process_entrypoints import (
    run_charge_discharge_control,
    run_idle_control,
)

from .state import ChannelState


class TestExecutionService:
    """Translate channel state into execution-process targets and arguments."""

    def start_test(self, state: ChannelState) -> tuple[Any, tuple[Any, ...]]:
        return run_charge_discharge_control, (
            state.equipment_assignment,
            state.data_queue,
            state.control_queue,
            state.test_configuration,
            state.number,
        )

    def start_idle(self, state: ChannelState) -> tuple[Any, tuple[Any, ...]]:
        return run_idle_control, (
            state.equipment_assignment,
            state.data_queue,
            state.idle_control_queue,
        )
