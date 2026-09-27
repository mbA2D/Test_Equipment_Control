"""Embedded equipment connection controls."""

import json

from typing import Any

from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class EquipmentConnectionWidget(QWidget):
    """Select an equipment category, driver family, and resource in-window."""

    connect_requested = QtCore.pyqtSignal(str, str, object, object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.category = QComboBox()
        self.model = QComboBox()
        self.resource = QComboBox()
        self.setup = QLineEdit("{}")
        self.setup.setPlaceholderText('{"remote_sense": false}')
        self.connect_button = QPushButton("Connect selected equipment")
        self.status = QLabel("Scan resources before connecting physical equipment.")

        self.category.addItems(["psu", "eload", "dmm", "relay_board", "other"])
        self.category.currentTextChanged.connect(self._category_changed)
        self.connect_button.clicked.connect(self._connect_requested)

        form = QHBoxLayout()
        form.addWidget(QLabel("Type"))
        form.addWidget(self.category)
        form.addWidget(QLabel("Model"))
        form.addWidget(self.model)
        form.addWidget(QLabel("Resource"))
        form.addWidget(self.resource)
        form.addWidget(QLabel("Setup JSON"))
        form.addWidget(self.setup)
        form.addWidget(self.connect_button)

        group = QGroupBox("Connect equipment")
        group.setLayout(form)
        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.addWidget(self.status)
        self._models: dict[str, list[str]] = {}
        self._category_changed(self.category.currentText())

    def set_models(self, models: dict[str, list[str]]) -> None:
        self._models = {key: list(value) for key, value in models.items()}
        self._category_changed(self.category.currentText())

    def set_resources(self, resources: list[Any] | None) -> None:
        self.resource.clear()
        self.resource.addItem("Automatic / fake", None)
        for resource in resources or []:
            self.resource.addItem(str(resource), resource)
        self.status.setText(f"{len(resources or [])} resource(s) available.")

    def _category_changed(self, category: str) -> None:
        self.model.clear()
        self.model.addItems(self._models.get(category, []))

    def _connect_requested(self) -> None:
        model = self.model.currentText()
        if not model:
            self.status.setText("Select an equipment model first.")
            return
        try:
            setup = json.loads(self.setup.text() or "{}")
        except json.JSONDecodeError as error:
            self.status.setText(f"Invalid setup JSON: {error.msg}")
            return
        if not isinstance(setup, dict):
            self.status.setText("Setup JSON must be an object.")
            return
        self.connect_requested.emit(self.category.currentText(), model, self.resource.currentData(), setup)


class ConnectedEquipmentWidget(QWidget):
    """Show the registered instruments and their selectable channels."""

    HEADERS = ("Local ID", "Type", "Instrument", "Capabilities", "Channels", "Owners")

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setMinimumHeight(90)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip("Registered equipment is identified by local ID and stable equipment identity.")

        group = QGroupBox("Connected instruments")
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(self.table)
        layout = QVBoxLayout(self)
        layout.addWidget(group)

    def set_equipment(self, equipment: list[dict[str, Any]]) -> None:
        self.table.setRowCount(0)
        for device in equipment:
            row = self.table.rowCount()
            self.table.insertRow(row)
            channels = device.get("instrument_channels") or []
            channel_text = ", ".join(str(channel) for channel in channels) if channels else "not reported"
            owners = device.get("owners") or {}
            owner_text = ", ".join(
                f"{slot}: CH {owner}" for slot, owner in sorted(owners.items(), key=lambda item: str(item[0]))
            ) or "unassigned"
            values = (
                str(device.get("local_id", "?")),
                str(device.get("eq_type", "unknown")),
                f"{device.get('eq_idn', 'Unknown IDN')} ({device.get('class_name', 'unknown')})",
                ", ".join(sorted(str(capability) for capability in (device.get("capabilities") or []))) or "none",
                channel_text,
                owner_text,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
