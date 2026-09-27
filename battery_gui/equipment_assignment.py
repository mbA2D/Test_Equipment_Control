"""Embedded equipment assignment controls for one battery channel."""

from typing import Any

from PyQt6 import QtCore
from PyQt6.QtWidgets import QComboBox, QFormLayout, QPushButton, QVBoxLayout, QWidget


class EquipmentAssignmentWidget(QWidget):
    """Assign capability-backed equipment roles without dialogs."""

    assignment_applied = QtCore.pyqtSignal(dict)

    ROLE_DEFINITIONS = (
        ("psu", "Power supply", "can_source_voltage"),
        ("eload", "Electronic load", "can_sink_current"),
        ("dmm_v", "Voltage measurement", "can_measure_voltage"),
        ("dmm_i", "Current measurement", "can_measure_current"),
        ("dmm_t", "Temperature measurement", "can_measure_temperature"),
        ("dmm_v0", "Auxiliary voltage measurement", "can_measure_voltage"),
        ("dmm_i0", "Auxiliary current measurement", "can_measure_current"),
        ("dmm_t0", "Auxiliary temperature measurement", "can_measure_temperature"),
        ("relay_board", "Relay board", "can_isolate_output"),
    )
    ROLES = tuple((role, label) for role, label, _capability in ROLE_DEFINITIONS)
    _CAPABILITY_BY_ROLE = {
        role: capability for role, _label, capability in ROLE_DEFINITIONS
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._options: list[dict[str, Any]] = []
        self._selectors: dict[str, QComboBox] = {}
        self._channel_selectors: dict[str, QComboBox] = {}
        form = QFormLayout()
        for role, label, _capability in self.ROLE_DEFINITIONS:
            selector = QComboBox()
            selector.addItem("Not assigned", None)
            self._selectors[role] = selector
            channel_selector = QComboBox()
            channel_selector.addItem("Not assigned", None)
            channel_selector.setEnabled(False)
            channel_selector.setToolTip("Select channel 0 for a singleton or a numbered multi-channel slot.")
            self._channel_selectors[role] = channel_selector
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(selector)
            row_layout.addWidget(channel_selector)
            selector.currentIndexChanged.connect(
                lambda _index, selected_role=role: self._update_channels(selected_role)
            )
            form.addRow(label, row)

        self.apply_button = QPushButton("Apply equipment assignment")
        self.apply_button.clicked.connect(self._apply)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.apply_button)

    def set_equipment_options(self, equipment: list[dict[str, Any]]) -> None:
        self._options = list(equipment)
        for role, _label, _capability in self.ROLE_DEFINITIONS:
            selector = self._selectors[role]
            selected = selector.currentData()
            selected_equipment_id = (
                selected.get("equipment_id") if isinstance(selected, dict) else selected
            )
            selected_channel = self._channel_selectors[role].currentData()
            selector.blockSignals(True)
            selector.clear()
            selector.addItem("Not assigned", None)
            for device in self._matching_devices(role):
                selector.addItem(
                    self._device_label(device),
                    {
                        "equipment_id": device.get("equipment_id"),
                        "local_id": device.get("local_id"),
                    },
                )
            if selected_equipment_id is not None:
                index = self._find_equipment_index(selector, selected_equipment_id)
                if index >= 0:
                    selector.setCurrentIndex(index)
            selector.blockSignals(False)
            self._update_channels(role, selected_channel)

    def _matching_devices(self, role: str) -> list[dict[str, Any]]:
        capability = self._CAPABILITY_BY_ROLE[role]
        return [
            device
            for device in self._options
            if device.get("equipment_id")
            and capability in set(device.get("capabilities") or ())
        ]

    @staticmethod
    def _device_label(device: dict[str, Any]) -> str:
        identity = device.get("eq_idn") or "Unknown IDN"
        model = device.get("class_name", device.get("eq_type", "device"))
        local_id = device.get("local_id", "?")
        return f"{identity} ({model}, local {local_id})"

    @staticmethod
    def _find_equipment_index(selector: QComboBox, equipment_id: Any) -> int:
        for index in range(selector.count()):
            data = selector.itemData(index)
            if isinstance(data, dict) and data.get("equipment_id") == equipment_id:
                return index
        return -1

    def _selected_device(self, role: str) -> dict[str, Any] | None:
        selected = self._selectors[role].currentData()
        if not isinstance(selected, dict):
            return None
        equipment_id = selected.get("equipment_id")
        local_id = selected.get("local_id")
        for device in self._options:
            if equipment_id is not None and device.get("equipment_id") == equipment_id:
                return device
            if equipment_id is None and device.get("local_id") == local_id:
                return device
        return None

    @staticmethod
    def _instrument_channels(device: dict[str, Any]) -> list[int]:
        channels = device.get("instrument_channels") or []
        try:
            return [int(channel) for channel in channels] or [0]
        except (TypeError, ValueError):
            return [0]

    def _update_channels(self, role: str, selected_channel: Any = None) -> None:
        channel_selector = self._channel_selectors[role]
        device = self._selected_device(role)
        channels = self._instrument_channels(device) if device else []
        channel_selector.blockSignals(True)
        channel_selector.clear()
        if not device:
            channel_selector.addItem("Not assigned", None)
            channel_selector.setEnabled(False)
        elif channels == [0]:
            channel_selector.addItem("Channel 0 (single)", 0)
            channel_selector.setEnabled(False)
        else:
            for channel in channels:
                channel_selector.addItem(f"Channel {channel}", channel)
            channel_selector.setEnabled(True)
            index = channel_selector.findData(selected_channel)
            channel_selector.setCurrentIndex(index if index >= 0 else 0)
        channel_selector.blockSignals(False)

    def _apply(self) -> None:
        assignment = {}
        for role, _label, _capability in self.ROLE_DEFINITIONS:
            selection = self._selectors[role].currentData()
            assignment[role] = None if not isinstance(selection, dict) else {
                "res_id": {
                    "queue_in": None,
                    "equipment_id": selection.get("equipment_id"),
                    "local_id": selection.get("local_id"),
                    "eq_ch": self._channel_selectors[role].currentData(),
                }
            }
        self.assignment_applied.emit(assignment)
