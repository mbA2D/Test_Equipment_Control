"""Deterministic single-cell battery model for simulation and testing.

The model is intentionally small.  It is an electrical equivalent circuit with
one state of charge and one lumped thermal state; it is not intended to predict
real-cell behaviour or replace a battery safety model.

Current uses the battery convention: positive current charges the cell and
negative current discharges it.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BatteryCellParameters:
    """Parameters for the default LG INR18650 MJ1 simulation cell.

    The electrical ratings are based on LG Chem's 2016 MJ1 product
    specification.  The OCV curve and thermal values are deliberately simple
    simulation approximations and are exposed so tests can replace them.
    """

    capacity_ah: float = 3.5
    nominal_voltage_v: float = 3.635
    internal_resistance_ohm: float = 0.040
    resistance_temperature_coefficient: float = 0.003
    min_voltage_v: float = 2.5
    max_voltage_v: float = 4.2
    max_charge_current_a: float = 3.35
    max_discharge_current_a: float = 10.0
    min_temperature_c: float = -20.0
    max_temperature_c: float = 60.0
    charge_min_temperature_c: float = 0.0
    charge_max_temperature_c: float = 45.0
    ambient_temperature_c: float = 25.0
    thermal_resistance_k_per_w: float = 12.0
    thermal_capacitance_j_per_k: float = 100.0
    ocv_curve: tuple[tuple[float, float], ...] = field(
        default_factory=lambda: (
            (0.00, 3.00),
            (0.05, 3.25),
            (0.10, 3.35),
            (0.20, 3.48),
            (0.40, 3.62),
            (0.60, 3.72),
            (0.80, 3.86),
            (0.90, 4.02),
            (1.00, 4.20),
        )
    )


@dataclass
class BatteryCellState:
    """Observable state of the simulated cell."""

    soc: float
    temperature_c: float
    current_a: float = 0.0
    terminal_voltage_v: float = 0.0
    elapsed_time_s: float = 0.0
    charge_throughput_ah: float = 0.0
    energy_throughput_wh: float = 0.0
    safety_state: str = "normal"


class BatteryCellWorldModel:
    """A deterministic, time-stepped equivalent-circuit cell model."""

    def __init__(
        self,
        *,
        parameters: BatteryCellParameters | None = None,
        initial_soc: float = 1.0,
        initial_temperature_c: float | None = None,
    ) -> None:
        self.parameters = parameters or BatteryCellParameters()
        self._validate_parameters()
        if not 0.0 <= initial_soc <= 1.0:
            raise ValueError("initial_soc must be between 0 and 1")
        temperature = (
            self.parameters.ambient_temperature_c
            if initial_temperature_c is None
            else initial_temperature_c
        )
        self.state = BatteryCellState(soc=initial_soc, temperature_c=temperature)
        self.state.terminal_voltage_v = self.open_circuit_voltage_v
        self.state.safety_state = self._safety_state()

    @property
    def open_circuit_voltage_v(self) -> float:
        """Return OCV from the configured piecewise-linear SoC curve."""

        soc = self.state.soc
        curve = self.parameters.ocv_curve
        for (soc_a, voltage_a), (soc_b, voltage_b) in zip(curve, curve[1:]):
            if soc <= soc_b:
                fraction = (soc - soc_a) / (soc_b - soc_a)
                return voltage_a + fraction * (voltage_b - voltage_a)
        return curve[-1][1]

    @property
    def internal_resistance_ohm(self) -> float:
        """Return resistance adjusted linearly around 25 degrees Celsius."""

        delta_c = self.state.temperature_c - 25.0
        return max(
            0.0,
            self.parameters.internal_resistance_ohm
            * (1.0 + self.parameters.resistance_temperature_coefficient * delta_c),
        )

    def step(self, current_a: float, dt_s: float) -> BatteryCellState:
        """Advance the model by ``dt_s`` seconds at ``current_a``.

        Positive current charges the cell.  The terminal voltage is calculated
        after the state update as ``OCV + current * resistance``.
        """

        if dt_s <= 0.0:
            raise ValueError("dt_s must be greater than zero")

        previous_voltage = self.state.terminal_voltage_v
        capacity_as = self.parameters.capacity_ah * 3600.0
        self.state.soc = min(1.0, max(0.0, self.state.soc + current_a * dt_s / capacity_as))
        self.state.current_a = current_a
        self.state.elapsed_time_s += dt_s
        self.state.charge_throughput_ah += abs(current_a) * dt_s / 3600.0

        heat_w = current_a * current_a * self.internal_resistance_ohm
        cooling_w = (
            self.state.temperature_c - self.parameters.ambient_temperature_c
        ) / self.parameters.thermal_resistance_k_per_w
        self.state.temperature_c += (
            (heat_w - cooling_w) / self.parameters.thermal_capacitance_j_per_k * dt_s
        )

        self.state.terminal_voltage_v = self.open_circuit_voltage_v + (
            current_a * self.internal_resistance_ohm
        )
        self.state.energy_throughput_wh += abs(
            (previous_voltage + self.state.terminal_voltage_v) / 2.0
            * current_a
            * dt_s
            / 3600.0
        )
        self.state.safety_state = self._safety_state()
        return self.state

    def reset(self, *, soc: float = 1.0, temperature_c: float | None = None) -> BatteryCellState:
        """Reset the cell state and accumulated throughput counters."""

        if not 0.0 <= soc <= 1.0:
            raise ValueError("soc must be between 0 and 1")
        self.state = BatteryCellState(
            soc=soc,
            temperature_c=(
                self.parameters.ambient_temperature_c
                if temperature_c is None
                else temperature_c
            ),
        )
        self.state.terminal_voltage_v = self.open_circuit_voltage_v
        self.state.safety_state = self._safety_state()
        return self.state

    def _safety_state(self) -> str:
        if self.state.current_a > self.parameters.max_charge_current_a:
            return "overcharge_current"
        if self.state.current_a < -self.parameters.max_discharge_current_a:
            return "overdischarge_current"
        if self.state.terminal_voltage_v < self.parameters.min_voltage_v:
            return "undervoltage"
        if self.state.terminal_voltage_v > self.parameters.max_voltage_v:
            return "overvoltage"
        if self.state.temperature_c < self.parameters.min_temperature_c:
            return "undertemperature"
        if self.state.temperature_c > self.parameters.max_temperature_c:
            return "overtemperature"
        if (
            self.state.current_a > 0.0
            and not self.parameters.charge_min_temperature_c
            <= self.state.temperature_c
            <= self.parameters.charge_max_temperature_c
        ):
            return "charge_temperature"
        return "normal"

    def _validate_parameters(self) -> None:
        if self.parameters.capacity_ah <= 0.0:
            raise ValueError("capacity_ah must be greater than zero")
        if self.parameters.thermal_resistance_k_per_w <= 0.0:
            raise ValueError("thermal_resistance_k_per_w must be greater than zero")
        if self.parameters.thermal_capacitance_j_per_k <= 0.0:
            raise ValueError("thermal_capacitance_j_per_k must be greater than zero")
        if len(self.parameters.ocv_curve) < 2:
            raise ValueError("ocv_curve must contain at least two points")
        if any(
            soc_a < 0.0 or soc_a > 1.0 or soc_b <= soc_a
            for (soc_a, _), (soc_b, _) in zip(
                self.parameters.ocv_curve, self.parameters.ocv_curve[1:]
            )
        ):
            raise ValueError("ocv_curve SoC values must be strictly increasing in [0, 1]")

