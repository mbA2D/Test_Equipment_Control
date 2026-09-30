#Program to run the charge discharge control in different processes for each channel.

#Actions and menus from this tutorial: https://realpython.com/python-menus-toolbars/

from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QSplitter,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QAction, QColor
from PyQt6 import QtCore
from functools import partial
from pathlib import Path

from lab_equipment import A2D_DAQ_control
from lab_equipment import DMM_A2D_4CH_Isolated_ADC
from lab_equipment import Eload_A2D_Eload
import equipment as eq
import time
from battery_app import ApplicationEvent, BatteryApplication, ChannelStatus, HeadlessRunner
from battery_app.logging_config import configure_application_logging, get_logger
from battery_gui import ChannelWidget, ConnectedEquipmentWidget, EquipmentConnectionWidget


logger = get_logger(__name__)

class MainTestWindow(QMainWindow):
    def __init__(
        self,
        application: BatteryApplication | None = None,
        runner: HeadlessRunner | None = None,
    ):
        super().__init__()

        if application is not None and runner is not None:
            raise ValueError("Provide either application or runner, not both")

        self.num_battery_channels = 0
        self.resources_list = None
        self.runner = runner or HeadlessRunner(application=application)
        # Compatibility alias for callers that inspect the shared application facade.
        self.application = self.runner.application
        # Public read-through for callers that inspect application channel state.
        self.channel_states = self.application.channel_states
        self.connected_equipment_list = self.application.connected_equipment
        
        self.setWindowTitle("Battery Tester App")
        self.central_layout = QVBoxLayout()

        global_settings_panel = QGroupBox("Global settings")
        global_settings_layout = QFormLayout(global_settings_panel)
        self.institution_code_edit = QLineEdit("LOCAL")
        self.institution_code_edit.setPlaceholderText("Your lab or organization code")
        self.institution_code_edit.setToolTip(
            "Short, stable code used in BDF filenames; shared by all channels and profiles."
        )
        global_settings_layout.addRow("Institution code", self.institution_code_edit)
        self.data_directory_edit = QLineEdit(str(Path.cwd()))
        self.data_directory_edit.setPlaceholderText("Shared root folder for all test data")
        self.data_directory_edit.setToolTip(
            "All channels store test data beneath this directory in cell-specific folders."
        )
        global_settings_layout.addRow("Test data directory", self.data_directory_edit)
        self.central_layout.addWidget(global_settings_panel)

        connection_panel = QGroupBox("Equipment connections")
        connection_layout = QVBoxLayout(connection_panel)
        self.connection_widget = EquipmentConnectionWidget()
        relay_models = [
            class_name
            for class_name in eq.otherEquipment.part_numbers
            if "can_isolate_output" in eq.EQUIPMENT_CAPABILITIES.get(class_name, ())
        ]
        self.connection_widget.set_models({
            "psu": list(eq.powerSupplies.part_numbers.keys()),
            "eload": list(eq.eLoads.part_numbers.keys()) + list(eq.get_capable_equipment("can_sink_current")),
            "dmm": list(eq.dmms.part_numbers.keys()) + list(eq.get_capable_equipment("can_measure_voltage")),
            "relay_board": relay_models,
            "other": [
                class_name
                for class_name in eq.otherEquipment.part_numbers
                if class_name not in relay_models
            ],
        })
        self.connection_widget.connect_requested.connect(self.connect_selected_equipment)
        connection_layout.addWidget(self.connection_widget)
        self.connected_equipment_widget = ConnectedEquipmentWidget()
        connection_layout.addWidget(self.connected_equipment_widget)
        self.central_layout.addWidget(connection_panel)

        middle_splitter = QSplitter(QtCore.Qt.Orientation.Horizontal)
        channel_panel = QGroupBox("Battery channels")
        channel_panel.setMinimumWidth(150)
        channel_panel.setMaximumWidth(260)
        channel_layout = QVBoxLayout(channel_panel)
        self.channel_list = QListWidget()
        self.channel_list.currentRowChanged.connect(self._select_channel)
        channel_layout.addWidget(self.channel_list)
        middle_splitter.addWidget(channel_panel)

        details_panel = QGroupBox("Active channel details")
        details_layout = QVBoxLayout(details_panel)
        self.channel_stack = QStackedWidget()
        details_layout.addWidget(self.channel_stack)
        middle_splitter.addWidget(details_panel)
        middle_splitter.setStretchFactor(0, 0)
        middle_splitter.setStretchFactor(1, 1)
        self.central_layout.addWidget(middle_splitter, 1)

        log_panel = QGroupBox("Important status log")
        log_layout = QVBoxLayout(log_panel)
        self.status_log = QListWidget()
        self.status_log.setMaximumHeight(150)
        log_layout.addWidget(self.status_log)
        self.central_layout.addWidget(log_panel)
        
        central_widget = QWidget()
        central_widget.setLayout(self.central_layout)
        self.setCentralWidget(central_widget)
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f4f6f8; color: #20252b; }
            QLabel { font-size: 13px; }
            QComboBox, QPushButton {
                min-height: 28px;
                padding: 3px 9px;
                border: 1px solid #c7cdd4;
                border-radius: 4px;
                background: #ffffff;
            }
            QPushButton:hover, QComboBox:hover { border-color: #3978b8; }
            QPushButton:disabled { color: #8b949e; background: #e9edf1; }
            """
        )
        
        self.timer = QtCore.QTimer()
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.update_loop)
        self.timer.start()
        self.channel_widgets: dict[int, ChannelWidget] = {}
        
        self.create_actions()
        self.connect_actions()
        self.create_menu_bar()
        
        self.setup_channels()
        
    def create_actions(self):
        #self.connect_multi_ch_eq_action = QAction("Connect Multi-Channel Equipment", self)
        self.import_equipment_assignment_action = QAction("Import Equipment Assignment", self)
        self.export_equipment_assignment_action = QAction("Export Equipment Assignment", self)
        self.scan_equipment_resources_action = QAction("Scan Resources", self)
        self.connect_new_equipment_action = QAction("Connect New Equipment", self)
        self.add_channel_action = QAction("Add Channel", self)
    
    def connect_actions(self):
        #self.connect_multi_ch_eq_action.triggered.connect(self.multi_ch_devices_process)
        self.import_equipment_assignment_action.triggered.connect(self.import_equipment_assignment)
        self.export_equipment_assignment_action.triggered.connect(self.export_equipment_assignment)
        self.scan_equipment_resources_action.triggered.connect(self.scan_resources)
        self.connect_new_equipment_action.triggered.connect(self.connect_new_equipment)
        self.add_channel_action.triggered.connect(self.add_channel)
    
    def create_menu_bar(self):
        menu_bar = QMenuBar(self)
        
        file_menu = menu_bar.addMenu("File")
        #file_menu.addAction(self.connect_multi_ch_eq_action)
        file_menu.addAction(self.import_equipment_assignment_action)
        file_menu.addAction(self.export_equipment_assignment_action)
        file_menu.addAction(self.scan_equipment_resources_action)
        file_menu.addAction(self.connect_new_equipment_action)
        file_menu.addAction(self.add_channel_action)
        
        self.setMenuBar(menu_bar)
        
    
    #Scan new equipment in a process so that we don't block the main window
    def scan_resources(self):
        result = self.runner.scan_resources()
        if not result.ok:
            logger.warning(result.message)
            self.connection_widget.status.setText(result.message or "Resource scan could not be started")
    
    def connect_new_equipment(self):
        self.connection_widget.setFocus()

    def connect_selected_equipment(self, eq_type, class_name, resource_id, setup_dict=None):
        result = self.runner.probe_equipment(
            eq_type,
            class_name,
            resource_id,
            setup_dict,
            self.resources_list,
        )
        if not result.ok:
            logger.warning(result.message)
            self.connection_widget.status.setText(result.message or "Equipment connection could not be started")
    
    def clear_layout(self, layout):
        #https://stackoverflow.com/questions/4528347/clear-all-widgets-in-a-layout-in-pyqt
        if layout is not None:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget() is not None:
                    child.widget().deleteLater()
                elif child.layout() is not None:
                    self.clear_layout(child.layout())
    
    def remove_all_channels(self, *, remove_application_channels=True):
        if remove_application_channels:
            self.runner.remove_channels()
        self.channel_widgets.clear()
        while self.channel_stack.count():
            widget = self.channel_stack.widget(0)
            self.channel_stack.removeWidget(widget)
            widget.deleteLater()
        self.channel_list.clear()
    
    
    def setup_channels(self, num_ch=None, *, application_channels_ready=False):
        self.remove_all_channels(remove_application_channels=not application_channels_ready)
        
        if num_ch == None:
            # Start with one workspace. Additional channels are added from
            # the menu without interrupting the main interface.
            num_ch = 1
        self.num_battery_channels = num_ch
        
        for ch_num in range(self.num_battery_channels):
            self.setup_single_channel(ch_num, create_application_channel=not application_channels_ready)
    
    
    def setup_single_channel(self, ch_num, *, create_application_channel=True):
        """Create the single-window workspace for one channel."""
        widget = ChannelWidget(ch_num)
        self.channel_widgets[ch_num] = widget
        if create_application_channel:
            self.runner.add_channel(ch_num)
        widget.set_run_configuration({"cell_name": self.runner.channel_states[ch_num].cell_name})

        widget.edit_cell_name_requested.connect(widget.focus_cell_name)
        widget.cell_name_changed.connect(partial(self._set_cell_name, ch_num))
        widget.clear_safety_requested.connect(partial(self.clear_safety_error, ch_num))
        widget.assign_equipment_requested.connect(widget.equipment_assignment.setFocus)
        widget.configure_test_requested.connect(widget.focus_profile_editor)
        widget.import_test_requested.connect(partial(self.import_test_configuration_process, ch_num))
        widget.export_test_requested.connect(partial(self.export_test_configuration_process, ch_num))
        widget.stop_test_requested.connect(partial(self.stop_test, ch_num))
        widget.start_test_requested.connect(partial(self.start_test, ch_num))
        widget.equipment_assignment_applied.connect(partial(self.apply_equipment_assignment, ch_num))
        widget.test_configuration_applied.connect(partial(self.apply_test_configuration, ch_num))
        widget.set_equipment_options(self.runner.connected_equipment)

        self.channel_stack.addWidget(widget)
        self.channel_list.addItem(f"CH {ch_num}  |  Idle")
        if self.channel_list.currentRow() < 0:
            self.channel_list.setCurrentRow(0)

    def add_channel(self):
        self.setup_single_channel(self.num_battery_channels)
        self.num_battery_channels = self.num_battery_channels + 1

    def _set_cell_name(self, channel: int, cell_name: str) -> None:
        """Send edited run context directly to the application facade."""
        result = self.runner.set_cell_name(channel, cell_name)
        if not result.ok:
            logger.warning("CH%s: %s", channel, result.message)

    def _select_channel(self, index):
        if index >= 0:
            self.channel_stack.setCurrentIndex(index)

    def _refresh_channel_indicator(self, ch_num):
        """Reflect safety > worker error > running > idle in navigation."""
        state = self.runner.channel_states[ch_num]
        item = self.channel_list.item(ch_num)
        if item is None:
            return
        if state.safety_fault:
            label, color = "Safety error", "#b42318"
        elif state.status == ChannelStatus.ERROR:
            label, color = "Worker error", "#b42318"
        elif state.is_running or state.status == ChannelStatus.RUNNING:
            label, color = "Running", "#18794e"
        else:
            label, color = "Idle", "#20252b"
        item.setText(f"CH {ch_num}  |  {label}")
        item.setForeground(QColor(color))
        self.channel_widgets[ch_num].set_channel_state(
            label == "Running",
            state.safety_fault,
            error=state.status == ChannelStatus.ERROR,
        )

    def _log_important(self, message, ch_num=None, color=None):
        prefix = f"CH {ch_num}: " if ch_num is not None else ""
        logger.info("%s%s", prefix, message)
        item = QListWidgetItem(f"{time.strftime('%H:%M:%S')}  {prefix}{message}")
        if color:
            item.setForeground(QColor(color))
        self.status_log.addItem(item)
        while self.status_log.count() > 200:
            self.status_log.takeItem(0)
        self.status_log.scrollToBottom()

    def apply_equipment_assignment(self, ch_num, assignment):
        """Apply an embedded equipment assignment through the application."""
        if not any(value is not None for value in assignment.values()):
            logger.warning("CH%s - No equipment assigned", ch_num)
            return
        result = self.runner.apply_equipment_assignment(ch_num, assignment)
        if result.ok:
            self._log_important("Equipment assignment updated", ch_num)
            self._refresh_channel_indicator(ch_num)
            self.connected_equipment_widget.set_equipment(self.runner.connected_equipment)
        else:
            logger.warning("CH%s: %s", ch_num, result.message)

    @staticmethod
    def _resolve_connected_equipment(assignment, connected_equipment):
        """Resolve a role descriptor by required stable equipment identity."""
        return HeadlessRunner.resolve_connected_equipment(assignment, connected_equipment)

    @staticmethod
    def _physical_resource_ids(res_id):
        """Return physical resource identifiers represented by a descriptor."""
        return HeadlessRunner.physical_resource_ids(res_id)

    @staticmethod
    def is_equipment_already_connected(eq_res_id_dict, connected_equipment_list):
        """Check for a duplicate physical resource across equipment roles."""
        return HeadlessRunner.is_equipment_already_connected(eq_res_id_dict, connected_equipment_list)

    def apply_test_configuration(self, ch_num, configuration, source="simple"):
        """Validate and store an executable profile without spawning a dialog."""
        profile_configuration = self.runner.apply_profile(ch_num, configuration)
        widget = self.channel_widgets[ch_num]
        run_context = widget.run_configuration()
        self._set_cell_name(ch_num, run_context["cell_name"])
        first_step = profile_configuration["settings_cycle_list_step_list"][0][0]
        self.channel_widgets[ch_num].update_status("Idle", first_step["cycle_display"])
        widget.set_run_configuration(run_context)
        widget.profile_editor.set_profile_identity(
            profile_configuration["profile_id"],
            profile_configuration["profile_version"],
        )
        self.channel_widgets[ch_num].show_profile_configuration(
            profile_configuration,
            source,
        )
        self._log_important(
            "Imported profile loaded" if source == "imported" else "Test configuration updated",
            ch_num,
        )

    def _data_directory(self) -> str:
        """Return the one application-wide root directory for test data."""
        return self.data_directory_edit.text().strip() or str(Path.cwd())

    def _configuration_for_start(self, configuration, run_context=None):
        """Build an execution configuration from profile and GUI run context."""
        if run_context is None:
            run_context = {"cell_name": configuration.get("cell_name", "CELL_NAME")}
        runtime_context = dict(run_context)
        runtime_context["directory"] = self._data_directory()
        runtime_context["institution_code"] = self.institution_code_edit.text()
        return self.runner.build_execution_configuration(configuration, runtime_context)

    def _render_application_event(self, event: ApplicationEvent):
        """Render one non-Qt application event in the active channel workspace."""
        if event.kind == "resources":
            self.resources_list = event.payload
            self.connection_widget.set_resources(self.resources_list)
            logger.info("Equipment resources updated: %s", self.resources_list)
            return
        if event.kind == "equipment_probe":
            if self.create_new_equipment(event.payload):
                self.connection_widget.status.setText("Equipment connected")
                logger.info("New equipment connected")
            else:
                message = self.runner.last_equipment_error
                self.connection_widget.status.setText(
                    f"Equipment could not be connected: {message}"
                    if message else "Equipment could not be connected"
                )
            return
        if event.channel is None:
            if event.message:
                logger.warning(event.message)
                self.connection_widget.status.setText(event.message)
            return
        widget = self.channel_widgets.get(event.channel)
        if widget is None:
            return
        if event.kind == "status":
            current, next_status = event.payload
            widget.update_status(current, next_status)
        elif event.kind == "measurement":
            widget.update_measurement(event.payload)
        elif event.kind == "safety_fault":
            widget.set_safety_fault(True)
        elif event.kind == "error":
            widget.update_status("Worker error", "Correct the issue and start a new test")
        if event.message:
            self._log_important(event.message, event.channel, event.color)
        self._refresh_channel_indicator(event.channel)
        
        
    def update_loop(self):
        for event in self.runner.poll():
            self._render_application_event(event)
    
    def create_new_equipment(self, eq_res_id_dict):
        """Register a connected instrument through the equipment manager."""
        if not self.runner.connect_equipment(eq_res_id_dict):
            message = self.runner.last_equipment_error
            logger.warning("Equipment could not be connected: %s", message or "connection was rejected")
            return False
        for widget in self.channel_widgets.values():
            widget.set_equipment_options(self.runner.connected_equipment)
        self.connected_equipment_widget.set_equipment(self.runner.connected_equipment)
        return True

    def export_equipment_assignment(self):
        filename, _filter = QFileDialog.getSaveFileName(
            self,
            "Export equipment assignment",
            "",
            "JSON files (*.json)",
        )
        if filename:
            self.runner.save_equipment_configuration(filename)

    def import_equipment_assignment(self):
        if any(state.is_running for state in self.runner.channel_states.values()):
            logger.warning("Stop tests on all channels before importing equipment assignment")
            return
        filename, _filter = QFileDialog.getOpenFileName(
            self,
            "Import equipment assignment",
            "",
            "JSON files (*.json)",
        )
        if not filename:
            return
        try:
            restored = self.runner.restore_equipment_configuration(filename)
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            logger.exception("Could not import equipment assignment: %s", error)
            self._log_important(f"Equipment import failed: {error}", color="#b42318")
            if not self.runner.channel_states:
                channel_count = max(1, self.num_battery_channels)
                self.runner.reset_channels(range(channel_count))
                self.setup_channels(channel_count, application_channels_ready=True)
                self.connected_equipment_widget.set_equipment(self.runner.connected_equipment)
                for widget in self.channel_widgets.values():
                    widget.set_equipment_options(self.runner.connected_equipment)
            return

        self.setup_channels(len(restored), application_channels_ready=True)
        self.connected_equipment_widget.set_equipment(self.runner.connected_equipment)
        for widget in self.channel_widgets.values():
            widget.set_equipment_options(self.runner.connected_equipment)

    def disconnect_all_equipment(self):
        self.runner.disconnect_all_equipment()
        
    
    def export_test_configuration_process(self, ch_num):
        configuration = self.runner.channel_states[ch_num].test_configuration
        if configuration is None:
            logger.warning("CH%s - No test configuration to export", ch_num)
            return
        filename, _filter = QFileDialog.getSaveFileName(
            self,
            "Export test configuration",
            "",
            "JSON files (*.json)",
        )
        if filename:
            self.runner.save_profile(ch_num, filename)

    def import_test_configuration_process(self, ch_num):
        filename, _filter = QFileDialog.getOpenFileName(
            self,
            "Import test configuration",
            "",
            "JSON files (*.json)",
        )
        if not filename:
            return
        try:
            configuration = self.runner.load_profile(filename)
            self.apply_test_configuration(ch_num, configuration, source="imported")
        except (OSError, ValueError, KeyError) as error:
            logger.exception("CH%s - Could not import test configuration: %s", ch_num, error)
            self._log_important(f"Profile import failed: {error}", ch_num, "#b42318")

    def clear_safety_error(self, ch_num):
        self.runner.clear_safety_fault(ch_num)
        self.channel_widgets[ch_num].set_safety_fault(False)
        self._log_important("Safety cleared", ch_num)
        self._refresh_channel_indicator(ch_num)


    def start_test(self, ch_num):
        try:
            run_context = self.channel_widgets[ch_num].run_configuration()
            run_context["directory"] = self._data_directory()
            run_context["institution_code"] = self.institution_code_edit.text()
            result = self.runner.start_test(ch_num, run_context)
            if result.ok:
                self._log_important("Test started", ch_num, "#18794e")
                self._refresh_channel_indicator(ch_num)
                return
            logger.warning("CH%s - %s", ch_num, result.message)
            self._log_important(f"Test not started: {result.message}", ch_num, "#b42318")
        except Exception:
            logger.exception("Test start failed for channel %s", ch_num)
    
    def start_idle_process(self, ch_num):
        try:
            if self.runner.start_idle(ch_num).ok:
                return
        except Exception:
            logger.exception("Idle process start failed for channel %s", ch_num)
    
    def stop_idle_process(self, ch_num):
        #print("CH{} - Stopping Idle Process".format(ch_num))
        self.runner.stop_idle(ch_num)
        
    def stop_test(self, ch_num):
        if self.runner.stop_test(ch_num).ok:
            self._log_important("Test stopped", ch_num)
            self._refresh_channel_indicator(ch_num)
    
    def clean_up(self):
        #Close all worker processes before the application exits.
        logger.info("Exiting; cleaning up processes")
        self.runner.shutdown()
            
    

def main():
    configure_application_logging()
    app = QApplication([])
    test_window = MainTestWindow()
    test_window.show()
    app.aboutToQuit.connect(test_window.clean_up)
    app.exec()
    
if __name__ == '__main__':
    main()
