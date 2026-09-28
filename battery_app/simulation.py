"""Connections between the simple battery model and fake instruments."""

from multiprocessing.managers import BaseManager
from time import monotonic

from .battery_model_simple import BatteryCellWorldModel


SIMULATED_LG_MJ1 = "SIMULATED_LG_MJ1"
SIMULATED_FAKE_CLASSES = frozenset({
    "Fake Test PSU",
    "Fake Test Eload",
    "Fake Test DMM",
})


class FakeInstrumentNotAttachedError(RuntimeError):
    """A fake instrument was used outside a shared simulated-cell run."""


def require_simulation_link(battery_link, instrument_name: str):
    """Return a shared link or reject obsolete fixed-value fake behavior."""

    if battery_link is None:
        raise FakeInstrumentNotAttachedError(
            f"{instrument_name} requires an attached SIMULATED_LG_MJ1 battery link"
        )
    return battery_link


def assignment_uses_fake_equipment(assignment) -> bool:
    """Return whether an assignment contains a built-in fake descriptor."""

    if not isinstance(assignment, dict):
        return False
    for descriptor in assignment.values():
        if not isinstance(descriptor, dict):
            continue
        if descriptor.get("class_name") in SIMULATED_FAKE_CLASSES:
            return True
        if descriptor.get("res_id") == "Fake":
            return True
    return False


def is_simulated_cell_name(cell_name: str | None) -> bool:
    """Return whether a profile requests the built-in LG MJ1 simulation."""

    return (cell_name or "").strip().upper() == SIMULATED_LG_MJ1


class FakeBatteryLink:
    """Share one battery model between a channel's fake instruments.

    The link advances on measurement calls using wall-clock time during normal
    execution. Tests can advance it deterministically with ``advance(dt_s)``.
    The simulated cell starts at 50% SoC by default. Positive PSU current is
    limited by both its current setting and voltage headroom above cell OCV; a
    fake electronic load always contributes negative current.
    """

    def __init__(
        self,
        model: BatteryCellWorldModel | None = None,
        *,
        initial_soc: float = 0.5,
    ) -> None:
        self.model = model or BatteryCellWorldModel(initial_soc=initial_soc)
        self.psu_output_enabled = False
        self.psu_current_limit_a = 0.0
        self.psu_voltage_setpoint_v = 0.0
        self.eload_output_enabled = False
        self.eload_current_a = 0.0
        self._last_update = monotonic()

    @property
    def current_a(self) -> float:
        if self.psu_output_enabled:
            current_limit_a = max(0.0, self.psu_current_limit_a)
            voltage_headroom_v = (
                self.psu_voltage_setpoint_v - self.model.open_circuit_voltage_v
            )
            if voltage_headroom_v <= 0.0:
                return 0.0
            resistance_ohm = self.model.internal_resistance_ohm
            if resistance_ohm <= 0.0:
                return current_limit_a
            return min(current_limit_a, voltage_headroom_v / resistance_ohm)
        if self.eload_output_enabled:
            return -abs(self.eload_current_a)
        return 0.0

    def set_psu_current(self, current_a: float) -> None:
        self.advance()
        self.psu_current_limit_a = current_a

    def set_psu_voltage(self, voltage_v: float) -> None:
        self.advance()
        self.psu_voltage_setpoint_v = voltage_v

    def set_psu_output(self, enabled: bool) -> None:
        self.advance()
        self.psu_output_enabled = enabled

    def set_eload_current(self, current_a: float) -> None:
        self.advance()
        self.eload_current_a = abs(current_a)

    def set_eload_output(self, enabled: bool) -> None:
        self.advance()
        self.eload_output_enabled = enabled

    def advance(self, dt_s: float | None = None) -> None:
        """Advance the model by explicit seconds or elapsed wall-clock time."""

        if dt_s is None:
            now = monotonic()
            dt_s = max(0.0, now - self._last_update)
            self._last_update = now
        else:
            if dt_s < 0.0:
                raise ValueError("dt_s must not be negative")
            self._last_update = monotonic()
        if dt_s > 0.0:
            self.model.step(self.current_a, dt_s)

    def measure_voltage(self) -> float:
        self.advance()
        return self.model.state.terminal_voltage_v

    def measure_current(self) -> float:
        self.advance()
        return self.current_a

    def measure_temperature(self) -> float:
        self.advance()
        return self.model.state.temperature_c

    def snapshot(self) -> dict[str, float]:
        """Return the model state for process-boundary integration tests."""

        self.advance()
        return {
            "soc": self.model.state.soc,
            "temperature_c": self.model.state.temperature_c,
            "current_a": self.model.state.current_a,
            "terminal_voltage_v": self.model.state.terminal_voltage_v,
        }


class _BatterySimulationManager(BaseManager):
    """Host one shared battery link for instrument-owner processes."""


_BatterySimulationManager.register("FakeBatteryLink", FakeBatteryLink)


class SimulationLinkService:
    """Own a process-safe simulated-cell link for one test channel.

    The service returns a manager proxy that can be passed to already-running
    fake-instrument owners.  Fake drivers therefore retain the same owner
    process and method-call path as physical instruments while sharing one
    authoritative cell model.
    """

    def __init__(self) -> None:
        self._manager: _BatterySimulationManager | None = None
        self.link = None

    def start(self):
        if self.link is not None:
            return self.link
        self._manager = _BatterySimulationManager()
        self._manager.start()
        self.link = self._manager.FakeBatteryLink()
        return self.link

    def close(self) -> None:
        if self._manager is not None:
            self._manager.shutdown()
            self._manager = None
        self.link = None

