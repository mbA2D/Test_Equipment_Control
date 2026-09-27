"""Measurement collection independent of step control and file logging."""

import time
from typing import Any, Mapping


class CycleMeasurementAccumulator:
    """Integrate directional capacity and energy for the active cycle."""

    CHARGING_CAPACITY = "Cycle Charging Capacity / Ah"
    DISCHARGING_CAPACITY = "Cycle Discharging Capacity / Ah"
    CHARGING_ENERGY = "Cycle Charging Energy / Wh"
    DISCHARGING_ENERGY = "Cycle Discharging Energy / Wh"

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        """Reset counters and the timestamp reference for a new cycle."""
        self._previous_timestamp = None
        self._values = {
            self.CHARGING_CAPACITY: 0.0,
            self.DISCHARGING_CAPACITY: 0.0,
            self.CHARGING_ENERGY: 0.0,
            self.DISCHARGING_ENERGY: 0.0,
        }

    def update(self, measurement: Mapping[str, Any]) -> dict[str, float]:
        """Integrate the interval ending at ``measurement`` and return totals."""
        timestamp = _as_float(measurement.get("Data_Timestamp"))
        if self._previous_timestamp is not None and timestamp is not None:
            elapsed_s = max(timestamp - self._previous_timestamp, 0.0)
            current_a = _as_float(measurement.get("Current")) or 0.0
            voltage_v = _as_float(measurement.get("Voltage")) or 0.0

            if current_a > 0:
                self._values[self.CHARGING_CAPACITY] += current_a * elapsed_s / 3600
                self._values[self.CHARGING_ENERGY] += (
                    voltage_v * current_a * elapsed_s / 3600
                )
            elif current_a < 0:
                discharge_a = -current_a
                self._values[self.DISCHARGING_CAPACITY] += discharge_a * elapsed_s / 3600
                self._values[self.DISCHARGING_ENERGY] += (
                    voltage_v * discharge_a * elapsed_s / 3600
                )

        if timestamp is not None:
            self._previous_timestamp = timestamp
        return dict(self._values)


def _as_float(value: Any) -> float | None:
    """Convert a measurement value to float while tolerating missing data."""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


class MeasurementService:
    """Read the primary and optional DMM channels for one test sample."""

    def __init__(self, equipment: Mapping[str, Any]):
        self.equipment = equipment

    def read(self, step_index: int = 0, current_time: float | None = None) -> dict[str, Any]:
        timestamp = time.perf_counter() if current_time is None else current_time
        data: dict[str, Any] = {
            "Voltage": 0,
            "Current": 0,
            # The internal executor remains zero-based; BDF Step ID is
            # cycle-local and is presented to the data file as one-based.
            "Step ID": step_index + 1,
            "Data_Timestamp": timestamp,
            "Unix_Timestamp": time.time(),
        }

        voltage_device = self.equipment.get("dmm_v")
        current_device = self.equipment.get("dmm_i")
        if voltage_device is not None:
            data["Voltage"] = voltage_device.measure_voltage()
        if current_device is not None:
            data["Current"] = current_device.measure_current()

        temperature_device = self.equipment.get("dmm_t")
        if temperature_device is not None:
            data["Temperature"] = temperature_device.measure_temperature()

        for prefix, method_name in (
            ("v", "measure_voltage"),
            ("i", "measure_current"),
            ("t", "measure_temperature"),
        ):
            for index in range(100):
                device_name = f"dmm_{prefix}{index}"
                device = self.equipment.get(device_name)
                if device is None:
                    break
                data[device_name] = getattr(device, method_name)()
        return data
