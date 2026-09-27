"""In-window editor for the common battery test profiles."""

from PyQt6 import QtCore
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QPushButton, QVBoxLayout, QWidget

import Templates
from battery_app.profile_identity import ProfileIdentityService


class ProfileEditorWidget(QWidget):
    """Build a small, validated one-step charge/discharge/rest plan."""

    configuration_applied = QtCore.pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        # The identity belongs to the profile, not to the widget lifetime.
        # It is created on the first Apply and retained while this simple
        # profile is edited.
        self.profile_id: str | None = None
        self.profile_version: str | None = None
        self.profile_identity_service = ProfileIdentityService()
        self.profile_type = QComboBox()
        self.profile_type.addItems(["Charge", "Discharge", "Rest"])
        self.primary_value = QDoubleSpinBox()
        self.primary_value.setRange(-10000, 10000)
        self.primary_value.setValue(1.0)
        self.secondary_value = QDoubleSpinBox()
        self.secondary_value.setRange(-10000, 10000)
        self.secondary_value.setValue(4.2)
        self.duration_or_cutoff = QDoubleSpinBox()
        self.duration_or_cutoff.setRange(0.001, 100000)
        self.duration_or_cutoff.setValue(3600)
        self.safety_max_time = QDoubleSpinBox()
        self.safety_max_time.setRange(0, 1000000)
        self.safety_max_time.setValue(3600)
        self.apply_button = QPushButton("Apply test profile")
        self.apply_button.clicked.connect(self._apply)
        self.profile_type.currentTextChanged.connect(self._update_labels)

        form = QFormLayout()
        form.addRow("Profile", self.profile_type)
        form.addRow("Current / rest time (s)", self.primary_value)
        form.addRow("Voltage / unused", self.secondary_value)
        form.addRow("Cutoff / duration (s)", self.duration_or_cutoff)
        form.addRow("Safety max time (s)", self.safety_max_time)

        group = QGroupBox("Test profile")
        group.setLayout(form)
        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.addWidget(self.apply_button)
        self._update_labels(self.profile_type.currentText())

    def _update_labels(self, profile: str) -> None:
        form = self.findChild(QFormLayout)
        if form is None:
            return
        if profile == "Charge":
            form.labelForField(self.primary_value).setText("Charge current (A)")
            form.labelForField(self.secondary_value).setText("Charge voltage (V)")
            form.labelForField(self.duration_or_cutoff).setText("End current (A)")
            self.duration_or_cutoff.setValue(0.1)
        elif profile == "Discharge":
            form.labelForField(self.primary_value).setText("Discharge current (A)")
            form.labelForField(self.secondary_value).setText("Unused")
            form.labelForField(self.duration_or_cutoff).setText("End voltage (V)")
            self.duration_or_cutoff.setValue(2.5)
        else:
            form.labelForField(self.primary_value).setText("Rest time (unused)")
            form.labelForField(self.secondary_value).setText("Unused")
            form.labelForField(self.duration_or_cutoff).setText("Duration (s)")
            self.duration_or_cutoff.setValue(60)

    def begin_new_profile(self) -> None:
        """Start a new simple profile without applying it yet."""
        self.profile_id = None
        self.profile_version = None
        self.setEnabled(True)

    def set_profile_identity(self, profile_id: str, profile_version_value: str) -> None:
        """Keep the editor identity synchronized after a validated Apply."""
        self.profile_id = profile_id
        self.profile_version = profile_version_value

    def _apply(self) -> None:
        profile = self.profile_type.currentText()
        step = Templates.StepSettings().settings.copy()
        step["cycle_type"] = "step"
        step["cycle_display"] = profile
        step["safety_max_time_s"] = self.safety_max_time.value()

        if profile == "Charge":
            step.update({
                "drive_style": "voltage_v",
                "drive_value": self.secondary_value.value(),
                "drive_value_other": self.primary_value.value(),
                "end_style": "current_a",
                "end_condition": "lesser",
                "end_value": self.duration_or_cutoff.value(),
            })
        elif profile == "Discharge":
            step.update({
                "drive_style": "current_a",
                "drive_value": -abs(self.primary_value.value()),
                "end_style": "voltage_v",
                "end_condition": "lesser",
                "end_value": self.duration_or_cutoff.value(),
            })
        else:
            step.update({
                "drive_style": "none",
                "drive_value": 0,
                "end_style": "time_s",
                "end_condition": "greater",
                "end_value": self.duration_or_cutoff.value(),
            })

        definition = {
            "profile_schema_version": 1,
            "profile_name": profile,
            "settings_cycle_list_step_list": [[step]],
        }
        if self.profile_id is None:
            configuration = self.profile_identity_service.create(definition)
        else:
            configuration = self.profile_identity_service.revise(self.profile_id, definition)
        self.profile_id = configuration["profile_id"]
        self.profile_version = configuration["profile_version"]
        self.configuration_applied.emit(configuration)
