"""Single-channel workspace for the battery-test GUI."""

from PyQt6 import QtCore
from PyQt6.QtWidgets import QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .equipment_assignment import EquipmentAssignmentWidget
from .profile_editor import ProfileEditorWidget


class ChannelWidget(QWidget):
    """Display one channel's measurements, state, and actions.

    The widget emits intent signals. It does not know about multiprocessing,
    equipment descriptors, or the test engine.
    """

    edit_cell_name_requested = QtCore.pyqtSignal()
    clear_safety_requested = QtCore.pyqtSignal()
    assign_equipment_requested = QtCore.pyqtSignal()
    configure_test_requested = QtCore.pyqtSignal()
    import_test_requested = QtCore.pyqtSignal()
    export_test_requested = QtCore.pyqtSignal()
    start_test_requested = QtCore.pyqtSignal()
    stop_test_requested = QtCore.pyqtSignal()
    equipment_assignment_applied = QtCore.pyqtSignal(dict)
    test_configuration_applied = QtCore.pyqtSignal(dict)
    cell_name_changed = QtCore.pyqtSignal(str)

    def __init__(self, channel: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.channel = channel

        self.cell_name_label = QLabel("N/A")
        self.edit_cell_name_button = QPushButton("Edit cell name")
        self.measurement_label = QLabel(f"CH: {channel}\nVoltage: --\nCurrent: --\nTemperature: --")
        self.status_label = QLabel("Status: Idle\nNext: N/A")
        self.safety_label = QLabel("Safety: OK")
        self.clear_safety_button = QPushButton("Clear safety fault")

        self.assign_equipment_button = QPushButton("Assign equipment")
        self.configure_test_button = QPushButton("Configure test")
        self.import_test_button = QPushButton("Import test")
        self.export_test_button = QPushButton("Export test")
        self.start_test_button = QPushButton("Start test")
        self.stop_test_button = QPushButton("Stop test")
        self.equipment_assignment = EquipmentAssignmentWidget()
        self.profile_editor = ProfileEditorWidget()
        self.cell_name_edit = QLineEdit("CELL_NAME")
        self.cell_name_edit.setPlaceholderText("SIMULATED_LG_MJ1 for built-in fake equipment")
        self.cell_name_edit.setToolTip(
            "Use SIMULATED_LG_MJ1 with Fake Test PSU, Eload, and DMM equipment."
        )
        self.profile_summary = QLabel(
            "No profile loaded. Use the simple editor or import a JSON profile."
        )
        self.profile_summary.setWordWrap(True)
        self._profile_source = None

        self._build_layout()
        self._connect_signals()

    def _build_layout(self) -> None:
        summary = QGroupBox("Channel status")
        summary_layout = QVBoxLayout(summary)
        summary_layout.addWidget(self.cell_name_label)
        summary_layout.addWidget(self.edit_cell_name_button)
        summary_layout.addWidget(self.measurement_label)
        summary_layout.addWidget(self.status_label)
        summary_layout.addWidget(self.safety_label)
        summary_layout.addWidget(self.clear_safety_button)

        actions = QGroupBox("Actions")
        actions_layout = QGridLayout(actions)
        buttons = (
            (self.assign_equipment_button, 0, 0),
            (self.configure_test_button, 0, 1),
            (self.import_test_button, 1, 0),
            (self.export_test_button, 1, 1),
            (self.start_test_button, 2, 0),
            (self.stop_test_button, 2, 1),
        )
        for button, row, column in buttons:
            actions_layout.addWidget(button, row, column)

        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addWidget(summary)
        assignment_group = QGroupBox("Equipment assignment")
        assignment_layout = QVBoxLayout(assignment_group)
        assignment_layout.addWidget(self.equipment_assignment)
        left.addWidget(assignment_group)
        run_context_group = QGroupBox("Run context")
        run_context_layout = QFormLayout(run_context_group)
        run_context_layout.addRow("Cell name", self.cell_name_edit)
        left.addWidget(run_context_group)
        profile_group = QGroupBox("Test profile")
        profile_layout = QVBoxLayout(profile_group)
        profile_layout.addWidget(self.profile_summary)
        profile_layout.addWidget(self.profile_editor)
        left.addWidget(profile_group)
        layout.addLayout(left, 1)
        layout.addWidget(actions, 1)

    def _connect_signals(self) -> None:
        self.edit_cell_name_button.clicked.connect(self.edit_cell_name_requested)
        self.clear_safety_button.clicked.connect(self.clear_safety_requested)
        self.assign_equipment_button.clicked.connect(self.assign_equipment_requested)
        self.configure_test_button.clicked.connect(self.configure_test_requested)
        self.import_test_button.clicked.connect(self.import_test_requested)
        self.export_test_button.clicked.connect(self.export_test_requested)
        self.start_test_button.clicked.connect(self.start_test_requested)
        self.stop_test_button.clicked.connect(self.stop_test_requested)
        self.equipment_assignment.assignment_applied.connect(self.equipment_assignment_applied)
        self.profile_editor.configuration_applied.connect(self.test_configuration_applied)
        self.cell_name_edit.textChanged.connect(self._cell_name_edited)

    def _cell_name_edited(self, value: str) -> None:
        """Keep the visible label in sync and report the edit to the application."""
        self.cell_name_label.setText(value)
        self.cell_name_changed.emit(value)

    def focus_cell_name(self) -> None:
        self.cell_name_edit.setFocus()
        self.cell_name_edit.selectAll()

    def run_configuration(self) -> dict[str, str]:
        """Return GUI-owned context for the next execution."""
        return {
            "cell_name": self.cell_name_edit.text().strip().replace(" ", "_") or "CELL_NAME",
        }

    def set_run_configuration(self, configuration: dict) -> None:
        """Display run context without changing the loaded profile."""
        self.cell_name_edit.setText(configuration.get("cell_name", "CELL_NAME"))

    def focus_profile_editor(self) -> None:
        """Focus the simple editor, explicitly replacing read-only import mode."""
        if self._profile_source == "imported":
            self.profile_editor.begin_new_profile()
            self._profile_source = "simple-draft"
            self.profile_summary.setText(
                "New simple profile draft. The imported profile remains active "
                "until this draft is applied."
            )
            self.configure_test_button.setText("Configure test")
        self.profile_editor.setEnabled(True)
        self.profile_editor.setFocus()

    def show_profile_configuration(self, configuration: dict, source: str) -> None:
        """Display the active profile and prevent accidental replacement."""
        cycles = configuration["settings_cycle_list_step_list"]
        step_count = sum(len(cycle) for cycle in cycles)
        displays = [
            step.get("cycle_display", "Step")
            for cycle in cycles
            for step in cycle
        ]
        requirements = configuration["eq_req_dict"]
        source_label = "Imported read-only profile" if source == "imported" else "Simple profile"
        self.profile_summary.setText(
            f"{source_label}\n"
            f"ID: {configuration['profile_id']}\n"
            f"Version: {configuration['profile_version']}\n"
            f"Cycles: {len(cycles)}; steps: {step_count}\n"
            f"Sequence: {' → '.join(displays)}\n"
            f"Required equipment: PSU={requirements['psu']}, e-load={requirements['eload']}"
        )
        self._profile_source = source
        imported = source == "imported"
        self.profile_editor.setEnabled(not imported)
        self.configure_test_button.setText(
            "Create simple profile" if imported else "Configure test"
        )

    def set_equipment_options(self, equipment: list[dict]) -> None:
        self.equipment_assignment.set_equipment_options(equipment)

    def update_measurement(self, measurement: dict) -> None:
        voltage = measurement.get("Voltage", "--")
        current = measurement.get("Current", "--")
        temperature = measurement.get("Temperature", measurement.get("dmm_t0", "--"))
        self.measurement_label.setText(
            f"CH: {self.channel}\nVoltage: {voltage}\nCurrent: {current}\nTemperature: {temperature}"
        )

    def update_status(self, current: str, next_status: str = "N/A") -> None:
        self.status_label.setText(f"Status: {current}\nNext: {next_status}")

    def set_safety_fault(self, fault: bool) -> None:
        self.safety_label.setText("Safety: ERROR" if fault else "Safety: OK")

    def set_channel_state(self, running: bool, safety_fault: bool, error: bool = False) -> None:
        """Update the detail panel's status accent without changing its data."""
        color = "#b42318" if safety_fault or error else "#18794e" if running else "#20252b"
        self.cell_name_label.setStyleSheet(f"font-weight: 600; color: {color};")
