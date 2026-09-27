"""Equipment lifecycle and safe source/load transitions."""

import time
from typing import Any, Mapping


class EquipmentController:
    """Own safe state transitions for the equipment assigned to one channel."""

    def __init__(self, equipment: Mapping[str, Any]):
        self.equipment = equipment

    def initialize(self) -> None:
        eload = self.equipment.get("eload")
        psu = self.equipment.get("psu")
        if eload is not None:
            eload.toggle_output(False)
            eload.set_current(0)
        if psu is not None:
            psu.toggle_output(False)
            psu.set_voltage(0)
            psu.set_current(0)

        for name, method_name in (
            ("dmm_v", "measure_voltage"),
            ("dmm_i", "measure_current"),
            ("dmm_t", "measure_temperature"),
        ):
            device = self.equipment.get(name)
            if device is not None:
                getattr(device, method_name)()

        relay = self.equipment.get("relay_board")
        if relay is not None:
            relay.connect_eload(False)
            relay.connect_psu(False)

        for prefix, method_name in (
            ("v", "measure_voltage"),
            ("i", "measure_current"),
            ("t", "measure_temperature"),
        ):
            for index in range(100):
                device = self.equipment.get(f"dmm_{prefix}{index}")
                if device is None:
                    break
                getattr(device, method_name)()

    @staticmethod
    def disable_single(device: Any) -> None:
        if device is None:
            return
        errors = []
        time.sleep(0.02)
        try:
            device.set_current(0)
        except Exception as error:
            errors.append(error)
        time.sleep(0.02)
        try:
            device.toggle_output(False)
        except Exception as error:
            errors.append(error)
        time.sleep(0.02)
        if errors:
            raise RuntimeError(
                "Could not fully disable equipment: "
                + "; ".join(str(error) for error in errors)
            ) from errors[0]

    def disable_all(self) -> None:
        errors = []
        for name in ("psu", "eload"):
            try:
                self.disable_single(self.equipment.get(name))
            except Exception as error:
                errors.append((name, error))
        relay = self.equipment.get("relay_board")
        if relay is not None:
            for method_name in ("connect_eload", "connect_psu"):
                try:
                    getattr(relay, method_name)(False)
                except Exception as error:
                    errors.append(("relay board", error))
        if errors:
            summary = "; ".join(f"{name}: {error}" for name, error in errors)
            raise RuntimeError("Safe equipment shutdown was incomplete: " + summary) from errors[0][1]
