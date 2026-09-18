# Test Equipment Control Architecture and Modernization Plan

> Status date: 2026-09-16  
> Scope: Current repository state, active runtime architecture, instrument ownership, stale/unused code, known bugs, and a staged plan for Python/dependency modernization and end-to-end simulated testing.

## 1. Executive summary

`Test_Equipment_Control` is a lab automation suite built around a core lab-control application:

1. **Core lab-control application**
   - Main GUI: `battery_test.py`
   - Equipment registry/factory: `equipment.py`
   - Instrument drivers: `lab_equipment/`
   - Test execution engine: `charge_discharge_control.py`
   - Configuration and logging: `Templates.py`, `jsonIO.py`, `FileIO.py`
   - Post-processing: `GraphIV.py`, `PlotTemps.py`, `voltage_to_temp.py`

The main application currently targets **Python 3.9.10** and uses dependency versions from roughly 2021–2022. It uses a process-isolated instrument ownership model: the GUI does not directly own most instruments during a test. Instead, each physical instrument is owned by a dedicated child process, and test-channel processes communicate with it through queues and proxy objects.

The most important cleanup targets are:

- Remove or isolate syntax-broken and prototype files.
- Remove duplicate definitions and obsolete blocks.
- Replace `eval()`-based dynamic dispatch with a controlled method registry.
- Add package metadata and a supported Python baseline.
- Update pinned dependencies in staged steps.
- Add a headless end-to-end simulation layer using fake instruments and a battery-cell world model.
- Convert hardware smoke scripts into selectable pytest tests rather than scripts that execute on import.

No dependency updates or code refactoring have been performed yet; this document records the current state and proposed roadmap.

---

## 2. What the repository can do

### 2.1 Battery-cell testing

The primary application, `battery_test.py`, supports:

- Multi-channel battery testing.
- Equipment scanning and selection.
- Per-channel equipment assignment.
- Charge, discharge, and rest steps.
- Single and repeated internal-resistance tests.
- Step-based custom profiles.
- Safety limits for voltage, current, and time.
- Live status and plot updates.
- CSV logging.
- Test configuration import/export.
- Equipment assignment import/export.

Supported cycle types are defined in:

- `Templates.CycleTypes`
- `charge_discharge_control.CyclingSettings`
- `charge_discharge_control.CyclingInfo`

### 2.2 DC-DC converter testing

- `dc_dc_test.py`
  - Sweeps input voltage and output load current.
  - Measures input/output voltage and current.
  - Logs efficiency-test data.

- `DC_DC_Graph.py`
  - Calculates efficiency and generates plots.

### 2.3 Solar-panel / CV-load sweeps

- `Eload_cv_sweep.py`
  - Sweeps an electronic load in constant-voltage mode.

- `Eload_cv_sweep_graph.py`
  - Calculates power and generates IV/power graphs.

### 2.4 General measurements

- `Measurement_Script.py`
  - Prompts the user to select a DMM.
  - Takes repeated voltage, current, or temperature readings.

### 2.5 Calibration

- `Calibration_Gui.py`
  - PyQt GUI wrapper around calibration logic.

- `Calibration_Script.py`
  - Connects a device under test, calibrated DMM, and power supply.
  - Performs voltage calibration and validation.

### 2.6 64-channel DAQ temperature logging

- `A2D_DAQ_read_all_analog_pullup.py`
- `lab_equipment/A2D_DAQ_control.py`
- `lab_equipment/A2D_DAQ_config.py`
- `lab_equipment/A2D_DAQ_Config_*.csv`
- `voltage_to_temp.py`
- `PlotTemps.py`

### 2.7 Post-processing

`GraphIV.py` processes log files for:

- Charge/discharge curves.
- Capacity in Ah and Wh.
- Internal resistance.
- SoC-OCV relationships.
- Repeated IR discharge tests.
- Incremental capacity analysis through DiffCapAnalyzer.
- Separate temperature logs.

---

## 3. Main runtime architecture

### 3.1 High-level flow

```text
battery_test.py
    MainTestWindow
        |
        | process spawning and queue ownership
        v
equipment.py
    equipment registry / factory / virtual-device process
        |
        v
lab_equipment/<driver>.py
    concrete instrument driver
        |
        v
lab_equipment/PyVisaDeviceTemplate.py
    PyVISA resource ownership
        |
        v
pyvisa.ResourceManager
    physical instrument
```

Channel execution is separate:

```text
battery_test.py
    start_test(channel)
        |
        | multiprocessing.Process
        v
charge_discharge_control.py
    CyclingControl
        |
        v
equipment.get_equipment_dict()
    creates proxy devices for channel process
        |
        v
lab_equipment/VirtualDeviceTemplate.py
    sends method-call messages through queues
        |
        v
equipment.virtual_device_management_process()
    instrument-owning child process
        |
        v
concrete instrument driver
```

### 3.2 GUI process

`battery_test.py` defines `MainTestWindow`.

Responsibilities:

- Own the PyQt event loop.
- Create channel widgets, buttons, status labels, and plots.
- Spawn resource-scanning child processes.
- Spawn equipment-connection child processes.
- Maintain `connected_equipment_list`.
- Maintain `connected_equipment_process_list`.
- Maintain per-channel:
  - Equipment assignment dictionaries.
  - Input/output queues.
  - Idle processes.
  - Test processes.
  - Configuration dictionaries.
- Drain queues in `update_loop()`.
- Start and stop test processes.
- Restart idle measurement processes when equipment changes.
- Clean up all processes on application exit.

Important GUI-owned state:

- `resources_list`
- `connected_equipment_list`
- `connected_equipment_process_list`
- `res_ids_dict_list`
- `cdc_input_dict_list`
- `data_from_ch_queue_list`
- `data_to_ch_queue_list`
- `data_to_idle_ch_queue_list`
- `mp_process_list`
- `mp_idle_process_list`

### 3.3 Equipment scan and selection

#### Resource scan

1. GUI calls `scan_resources()`.
2. GUI spawns `update_resources_list_process()`.
3. That process calls `equipment.get_resources_list()`.
4. `get_resources_list()` queries PyVISA backends:
   - `@py`
   - `@ivi`
5. The resource list is returned to the GUI through `resources_list_queue`.

Current limitation:

- Backend list is hard-coded.
- Failures are not handled per backend.
- A missing backend can abort the entire scan.

#### Connect new equipment

1. GUI calls `connect_new_equipment()`.
2. GUI spawns `connect_new_equipment_process()`.
3. The user selects:
   - PSU
   - E-load
   - DMM
   - Other equipment
4. The selected equipment class calls the matching `equipment.py` chooser:
   - `powerSupplies.choose_psu()`
   - `eLoads.choose_eload()`
   - `dmms.choose_dmm()`
   - `otherEquipment.choose_equipment()`
5. The chooser instantiates a driver from `lab_equipment/`.
6. The driver opens and identifies the instrument through PyVISA.
7. `equipment.get_res_id_dict_and_disconnect()`:
   - Extracts the PyVISA resource ID.
   - Extracts setup state.
   - Closes the physical resource.
   - Returns a serializable equipment descriptor.

This create-close-reconnect pattern lets the GUI store only descriptors while a dedicated process later owns the actual resource.

### 3.4 Physical instrument ownership

The most important architectural distinction is:

> A test-channel process does not normally own a PyVISA instrument directly. It owns a `VirtualDeviceTemplate` proxy. A separate equipment process owns the real PyVISA resource.

#### Ownership sequence

1. `battery_test.MainTestWindow.create_new_equipment()` receives an equipment descriptor.
2. GUI creates:
   - `queue_in`
   - `queue_out`
   - a dedicated `multiprocessing.Process`
3. The process runs `equipment.virtual_device_management_process()`.
4. That process calls `equipment.connect_to_eq()` and creates a concrete driver.
5. The concrete driver inherits from `lab_equipment.PyVisaDeviceTemplate`.
6. `PyVisaDeviceTemplate.__init__()` creates a `pyvisa.ResourceManager`.
7. It opens the PyVISA resource, configures termination and timing, queries `*IDN?`, and calls `initialize()`.
8. The instrument-owning process enters a loop and handles queued method calls.
9. The GUI stores:
   - Process ID.
   - Queues.
   - Class name.
   - Resource ID.
   - Setup dictionary.
   - Local ID.
   - Instrument IDN.

#### Instrument process loop

`equipment.virtual_device_management_process()`:

- Reads `queue_in`.
- Expects a dict:
  ```python
  {
      "type": "method_name",
      "data": argument_or_list,
  }
  ```
- Calls the method on the real driver using dynamic `eval()`.
- Writes return values to `queue_out`.
- Periodically calls `device.kick()` if present.
- Stops on a `disconnect` message.

Current concern:

- `eval()` is unsafe and hard to analyze statically.
- It should be replaced with a method registry or `getattr()` plus an allowlist.

### 3.5 Channel equipment assignment

For each battery channel, the GUI creates a dictionary with entries such as:

- `psu`
- `eload`
- `dmm_v`
- `dmm_i`
- `dmm_t`
- extra `dmm_v0`, `dmm_i0`, `dmm_t0`, etc.
- `relay_board`

For virtualized equipment, the descriptor's `res_id` contains:

- `queue_in`
- `queue_out`
- `local_id`
- `eq_ch`, for multi-channel instruments

The GUI writes this assignment to `eq_assignment_queue`, and `update_loop()` stores it in `res_ids_dict_list[ch_num]`.

### 3.6 Test-channel process

When the user starts a test:

1. GUI calls `start_test(ch_num)`.
2. GUI validates:
   - Safety error is clear.
   - Equipment is assigned.
   - Test configuration exists.
3. GUI stops the idle process.
4. GUI clears queues.
5. GUI spawns a new process targeting `cdc.run_charge_discharge_control()`.
6. The channel process receives:
   - Equipment descriptor dictionary.
   - Data output queue.
   - Data input/control queue.
   - Test configuration.
   - Channel number.

### 3.7 Reconnecting equipment inside the channel process

`charge_discharge_control.run_charge_discharge_control()` creates `CyclingControl`.

`CyclingControl.charge_discharge_control()` calls:

- `equipment.get_equipment_dict(res_ids_dict)`

The current effective implementation checks each descriptor. If it contains queue handles, it calls:

- `equipment.connect_to_virtual_eq()`

This returns a `VirtualDeviceTemplate` proxy.

Therefore:

- The channel process owns proxy objects.
- The instrument-owning process owns PyVISA resources.
- PyVISA calls are isolated to the equipment process.

### 3.8 Queue protocol

`VirtualDeviceTemplate` wraps method calls. For example, `measure_voltage()`:

1. Builds:
   ```python
   {
       "type": "measure_voltage",
       "data": channel_or_none,
   }
   ```
2. Puts it on `queue_in`.
3. Waits up to 10 seconds for a return value on `queue_out`.
4. Converts the result to the expected type.

Write-only methods such as `set_current()` put a message on `queue_in` but do not wait for an acknowledgment.

Current limitations:

- No standardized acknowledgment for writes.
- Errors in the instrument process are not reliably surfaced to the channel process.
- Timeouts are hard-coded.
- Different methods duplicate the same queue logic.
- Multiple channels can share one instrument process, but multi-step operations are not transactional.

### 3.9 Test execution engine

`charge_discharge_control.py` contains three major classes.

#### `CyclingControl`

Runtime execution:

- Initializes equipment.
- Disables outputs.
- Connects relay-board paths.
- Starts each step.
- Measures voltage/current/temperature.
- Evaluates end conditions.
- Evaluates safety conditions.
- Writes CSV and text logs.
- Sends status and measurements to the GUI.
- Stops on user request or safety fault.

#### `CyclingSettings`

Builds user-facing cycle settings and converts them to generic step dictionaries.

#### `CyclingInfo`

Handles prompts, cycle selection, cell name, storage charge, output directory, and assembly of the complete test dictionary.

### 3.10 Data flow

```text
CyclingControl
    -> data_out_queue
        -> MainTestWindow.update_loop()
            -> status labels
            -> live plot
            -> safety warning state
```

Control flow:

```text
MainTestWindow
    -> data_in_queue
        -> CyclingControl.end_signal()
            -> stop request
```

Log flow:

```text
CyclingControl
    -> FileIO.write_data()
        -> CSV log
```

Post-processing:

```text
CSV log
    -> GraphIV.py
        -> graphs and statistics
```

---

## 4. Driver architecture

### 4.1 Base classes

`lab_equipment/PyVisaDeviceTemplate.py` defines:

- `PyVisaDevice`
- `PowerSupplyDevice`
- `EloadDevice`
- `SourceMeasureDevice`
- `DMMDevice`

`PyVisaDevice` is responsible for:

- Creating a `ResourceManager`.
- Listing resources if no resource ID is given.
- Opening a resource.
- Applying connection settings:
  - Baud rate
  - Read/write termination
  - Query delay
  - Chunk size
  - Timeout
- Querying `*IDN?` when supported.
- Calling the driver-specific `initialize()` method.

### 4.2 Concrete drivers

Each concrete driver implements the SCPI or serial protocol for one instrument family.

Examples:

- `lab_equipment/Eload_DL3000.py`
- `lab_equipment/Eload_BK8600.py`
- `lab_equipment/PSU_SPD1000.py`
- `lab_equipment/DMM_SDM3065X.py`
- `lab_equipment/A2D_DAQ_control.py`
- `lab_equipment/OTHER_A2D_Relay_Board.py`

### 4.3 Interface shape

Drivers are duck-typed rather than formal interfaces.

Common PSU methods:

- `set_current()`
- `set_voltage()`
- `toggle_output()`
- `remote_sense()`
- `measure_voltage()`
- `measure_current()`

Common e-load methods:

- `set_current()`
- `set_mode_current()`
- `set_mode_voltage()`
- `set_cv_voltage()`
- `toggle_output()`
- `measure_voltage()`
- `measure_current()`

Common DMM methods:

- `measure_voltage()`
- `measure_current()`
- `measure_temperature()`

Modernization target:

- Define Python `Protocol` classes for each device category.
- Make fake devices satisfy the same protocols.
- Keep optional methods explicit rather than relying on `hasattr()`.

### 4.4 Virtual-device proxy

`lab_equipment/VirtualDeviceTemplate.py` exposes a broad proxy interface. It is intentionally large because it mirrors many possible driver methods:

- Measurement
- Output control
- Calibration
- Relay control
- Fan and LED control
- RS-485 address management
- I2C address setup

This file is active and should not be removed, but it should be refactored from repetitive queue logic into a helper method.

---

## 5. Other execution modes

### 5.1 Direct-driver scripts

Some scripts do not use the GUI's instrument-process architecture:

- `Measurement_Script.py`
- `dc_dc_test.py`
- `Eload_cv_sweep.py`
- `Calibration_Script.py`
- `Calibration_Gui.py`

These directly instantiate driver objects in the script process and therefore directly own PyVISA resources.

This is acceptable for standalone utilities, but it means there are two ownership models in the repository. A future version should provide a reusable connection layer that supports both modes.

## 6. Large files and current design issues

| File | Current role | Main issue |
|---|---|---|
| `charge_discharge_control.py` | Runtime engine, cycle prompts, settings conversion, logging | Combines multiple responsibilities; should be split |
| `battery_test.py` | Main GUI and process orchestration | GUI, multiprocessing, and queue wiring are tightly coupled |
| `GraphIV.py` | Post-processing and plotting | Contains obsolete code, duplicate imports, and old pandas patterns |
| `equipment.py` | Equipment registry and virtual-device dispatch | Duplicate definitions, broad imports, dynamic `eval()` |
| `lab_equipment/VirtualDeviceTemplate.py` | Queue proxy for instrument methods | Highly repetitive; no write acknowledgments |
| `Templates.py` | Settings defaults and schemas | Plain dicts without validation |

---

## 7. Dead, stale, or unused code

The following is based on static import and reference analysis. Some driver methods may still be useful even when no current caller exists because they form a public hardware interface.

### 7.1 High-confidence cleanup targets

| Path | Finding | Recommendation |
|---|---|---|
| `live_graph_temp.py` | Syntax error at line 22; only a placeholder | Remove, or implement and add a main guard |
| `lab_equipment/DMM_FET_BOARD_EQ.py` | Equipment registration is commented out | Remove or restore deliberately |
| `add_temp_to_logs.py` | One-off migration utility; no main guard | Add `if __name__ == "__main__":` or remove |
| `MSXIV_Battery_Module_Wiring_Test.py` | Standalone hardware test; no main guard | Add a main guard or move under a hardware-tests package |

### 7.2 Dead code inside active files

#### `equipment.py`

- `get_equipment_dict()` is defined twice.
- The second definition replaces the first.
- The earlier implementation is unreachable at runtime.
- Remove the shadowed definition and retain the virtual-queue-aware implementation.

#### `lab_equipment/A2D_DAQ_control.py`

- `A2D_DAQ.__del__()` is defined twice.
- The second definition replaces the first.
- Keep one implementation only.

#### `GraphIV.py`

- Lines 138–209 contain an obsolete triple-quoted incremental-capacity implementation.
- The active path uses the DiffCapAnalyzer integration instead.
- Remove the obsolete block.
- `add_cycle_numbers()` has no current in-repository caller.
- `get_filename_pref`, `glob`, `itertools`, `peakutils`, `scipy`, and `sqlite3` are imported but not currently used.

#### `FileIO.py`

- `ensure_subdir_exists_file()` has no current in-repository caller.
- `pandas` is imported but not used.

#### `battery_test.py`

- Imports `Event`, `PlotWidget`, `plot`, and `json` without current use.

#### `charge_discharge_control.py`

- Imports `datetime`, `os`, and `pandas` without current use.

#### `Templates.py`

- Imports `easygui`, `json`, and `os` without current use.

### 7.3 Manual hardware tests

`test_scripts/` currently contains hardware smoke scripts rather than automated tests.

Issues:

- Most scripts execute immediately when imported.
- They require real hardware and user interaction.
- They are not pytest-compatible.
- They are not suitable for CI.
- `test_A2D_Eload_functions.py` is large and runs on import.

Recommendation:

- Split tests into:
  - Pure unit tests.
  - Simulated integration tests.
  - Optional hardware smoke tests.
- Add `pytest.mark.hardware` and skip them by default in CI.

---

## 8. Bugs and robustness concerns

### 8.1 Syntax-broken files

- `live_graph_temp.py`

These currently fail parsing.

### 8.2 Unsafe dynamic method dispatch

`equipment.virtual_device_management_process()` uses:

```python
eval('device.' + method_name + '(*args)')
```

Problems:

- Security risk if a queue message is ever populated from untrusted input.
- Hard to statically analyze.
- Method-name typos fail at runtime.
- No interface validation.
- No explicit return-type handling.

Recommended replacement:

```python
allowed_methods = {
    "measure_voltage",
    "measure_current",
    "set_current",
    "set_voltage",
    "toggle_output",
}

if method_name not in allowed_methods:
    raise ValueError(f"Unsupported method: {method_name}")

method = getattr(device, method_name)
result = method(*args)
```

A stronger design would store bound methods in a registry when the device is connected.

### 8.3 No write acknowledgments

`VirtualDeviceTemplate` sends write commands without waiting for confirmation.

Potential failure mode:

- The channel process believes a command succeeded, but the instrument process failed or delayed.
- Later measurements may be attributed to the wrong output state.

Recommendation:

- Add a standardized response object:
  ```python
  {
      "type": "result",
      "ok": True,
      "value": None,
      "error": None,
  }
  ```
- Make write commands optionally synchronous.

### 8.4 Hard-coded response timeouts

`VirtualDeviceTemplate` uses a 10-second timeout for many queries.

Issues:

- Some instruments may take longer.
- Some operations should fail sooner.
- Timeout errors are not standardized.

Recommendation:

- Centralize timeout policy.
- Propagate a typed timeout exception.
- Allow per-device or per-method timeout overrides.

### 8.5 Resource scan failure handling

`equipment.get_resources_list()` assumes both `@py` and `@ivi` backends are usable.

Recommendation:

- Probe each backend independently.
- Return available and failed backends.
- Continue scanning if one backend fails.

### 8.6 Incomplete construction state

`PyVisaDevice.__init__()` can return early if no device is selected, without fully initializing the object. Callers may then receive an object without `inst`, causing later failures.

Recommendation:

- Raise a typed exception instead of returning early.
- Or return `None` explicitly.
- Validate all required attributes after construction.

### 8.7 Connect-close-reconnect pattern

Equipment selection opens a resource, closes it, and another process later reopens it.

This is central to the current process-ownership model, but it can fail if:

- The backend does not release the resource immediately.
- Another process claims the resource.
- The instrument requires a recovery delay.

Recommendation:

- Keep the process-ownership model, but make the reconnect logic explicit and testable.
- Consider keeping a lightweight probe object separate from the full driver.

### 8.8 Outdated pandas operation

`GraphIV.py` uses `DataFrame.append()`.

This method was deprecated and removed in newer pandas versions. Any dependency update to pandas 2.x will require replacing it with `pandas.concat()`.

### 8.9 Missing main guards

The following execute immediately on import:

- `add_temp_to_logs.py`
- `MSXIV_Battery_Module_Wiring_Test.py`
- Most files under `test_scripts/`

Recommendation:

- Add `if __name__ == "__main__":` guards.
- Convert test scripts to pytest-compatible functions.

### 8.10 Weak packaging

- The root contains an empty `__init__.py`.
- `lab_equipment/` has no explicit `__init__.py`.
- Imports rely on the current working directory and namespace-package behavior.
- There is no `pyproject.toml`.

Recommendation:

- Create a proper package layout.
- Add `pyproject.toml`.
- Use stable package names for imports.
- Avoid depending on the user launching from the repository root.

### 8.11 Duplicate and broad driver imports

`equipment.py` imports every driver at module import time.

Issues:

- Heavy import graph.
- A single optional dependency can break the entire application.
- Hardware-specific modules are tightly coupled.

Recommendation:

- Use a registry of lazy imports or entry points.
- Separate required drivers from optional drivers.

### 8.12 No structured logging

The code uses `print()` and text files.

Recommendation:

- Use Python's `logging` module.
- Separate:
  - User-facing status.
  - Instrument traffic.
  - Test lifecycle events.
  - Safety events.
  - Errors.

### 8.13 No formal device protocols

The application relies on duck typing and `hasattr()`.

Recommendation:

- Add `typing.Protocol` classes:
  - `PowerSupplyProtocol`
  - `ElectronicLoadProtocol`
  - `DMMProtocol`
  - `RelayBoardProtocol`
  - `SourceMeasureUnitProtocol`
- Use runtime checks where hardware compatibility matters.

---

## 9. Dependency and Python modernization

### 9.1 Current baseline

The README specifies Python 3.9.10.

`requirements.txt` pins old versions, including:

- `numpy==1.21.2`
- `pandas==1.3.4`
- `matplotlib==3.4.3`
- `scipy==1.7.2`
- `PyQt6==6.2.1`
- `pyqtgraph==0.12.3`
- `PyVISA==1.14.1`
- `DiffCapAnalyzer==0.1.1`
- `easygui==0.98.2`
- `keyboard==0.13.5`
- `retry==0.9.2`

### 9.2 Recommended target

Use a current, actively maintained Python baseline rather than merely moving from Python 3.9 to Python 3.12:

- **Python 3.13** as the primary supported baseline.
- **Python 3.14** as the forward-compatibility target once the full instrument, GUI, and scientific stack is verified.

Rationale:

- As of September 2026, Python 3.14 is the newest stable release and Python 3.13 remains in normal maintenance.
- Python 3.12 is still supported but has entered the security-fix-only phase; it is not the best baseline for a new modernization effort.
- This project uses native and binary-dependent packages such as PyQt6, PyVISA backends, `hidapi`, and scientific libraries. Those wheels and platform drivers must be checked before committing to Python 3.14.
- Starting at Python 3.13 gives a longer support lifetime while still being current enough for modern packaging and type-checking tools.
### 9.3 Dependency groups

Replace one monolithic `requirements.txt` with:

- `pyproject.toml`
- Runtime dependencies
- Development/test dependencies
- Optional hardware dependencies

Recommended groups:

```text
runtime:
    PyQt6
    pyqtgraph
    pyvisa
    pyvisa-py
    pandas
    numpy
    scipy
    matplotlib
    diffcapanalyzer

gui-legacy:
    easygui

testing:
    pytest
    pytest-qt
    ruff
    mypy or pyright

hardware-optional:
    pyserial
    pyusb
    hidapi

```

### 9.4 Dependency cleanup

Remove or reconsider:

- `tk==0.1.0`
  - This does not appear to be the Python `tkinter` package and may be an unrelated PyPI package.
- Exact pins for transitive dependencies such as `pyparsing`.
- `keyboard`
  - Only needed for the Arduino I/O hardware script and can be optional.
- `DiffCapAnalyzer`
  - Keep only if ICA processing remains supported.

### 9.5 Staged update sequence

Do not update all dependencies at once. Use staged compatibility passes:

1. **Make the package importable**
   - Add `pyproject.toml`.
   - Add explicit package files.
   - Add dependency groups.

2. **Remove dead code**
   - Delete or archive obsolete files.
   - Remove duplicate definitions.
   - Remove unused imports.
   - Add main guards.

3. **Move to a modern Python baseline**
   - Run tests on Python 3.13 and 3.14 compatibility.
   - Fix syntax and standard-library changes.

4. **Update analysis stack**
   - NumPy
   - pandas
   - SciPy
   - matplotlib
   - Replace `DataFrame.append()`.

5. **Update GUI stack**
   - PyQt6
   - pyqtgraph
   - Test Qt event loop and multiprocessing behavior.

6. **Update instrument stack**
   - PyVISA
   - PyVISA-py
   - pyserial
   - pyusb
   - hidapi

7. **Reassess optional dependencies**
   - EasyGUI
   - DiffCapAnalyzer

---

## 10. End-to-end simulation and self-testing plan

The current fake devices are too simple for full end-to-end testing. They mostly return fixed values. A true end-to-end test needs a **world model** that connects all simulated devices to the same simulated battery.

### 10.1 Desired test architecture

```text
pytest
    -> simulated GUI or headless test engine
        -> fake equipment processes
            -> Fake PSU
            -> Fake E-load
            -> Fake DMM
            -> Fake relay board
        -> BatteryCellWorldModel
            -> state of charge
            -> open-circuit voltage
            -> internal resistance
            -> terminal voltage
            -> current
            -> temperature
            -> safety limits
        -> logs and assertions
```

### 10.2 `BatteryCellWorldModel`

Create a deterministic cell model with inputs:

- Capacity, Ah.
- Initial SoC.
- OCV-SoC curve.
- Series resistance.
- Parallel resistance, optional.
- Thermal resistance and thermal capacitance.
- Ambient temperature.
- Minimum and maximum voltage.
- Current and temperature safety limits.
- Time step.

Outputs:

- Terminal voltage.
- Current.
- Temperature.
- SoC.
- Energy and capacity used.
- Safety state.

Recommended implementation:

```python
@dataclass
class BatteryCellState:
    soc: float
    temperature_c: float
    current_a: float
    terminal_voltage_v: float
```

The world model should evolve time explicitly so tests are deterministic.

### 10.3 Fake instruments

Fakes should not simply return constants. They should interact with the world model.

#### `FakePowerSupply`

Methods:

- `set_voltage()`
- `set_current()`
- `toggle_output()`
- `measure_voltage()`
- `measure_current()`

Behavior:

- When output is on, it requests a voltage/current operating point from the cell model.
- Measurements reflect the world model.
- Supports faults such as current-limit reached.

#### `FakeElectronicLoad`

Methods:

- `set_current()`
- `set_mode_current()`
- `set_mode_voltage()`
- `toggle_output()`
- `measure_voltage()`
- `measure_current()`

Behavior:

- Draws requested current if the simulated cell can supply it.
- Falls back to a safe current or raises a simulated fault if not.

#### `FakeDMM`

Methods:

- `measure_voltage()`
- `measure_current()`
- `measure_temperature()`

Behavior:

- Reads from the world model.
- Optionally injects measurement noise, latency, and failures.

#### `FakeRelayBoard`

Methods:

- `connect_psu()`
- `connect_eload()`
- `psu_connected()`
- `eload_connected()`

Behavior:

- Enforces break-before-make.
- Rejects invalid relay states.

### 10.4 Test layers

#### Layer 1: Pure unit tests

- Cycle-setting conversion.
- End-condition evaluation.
- Safety-condition evaluation.
- Filename parsing.
- Thermistor conversion.
- JSON import/export.
- CSV writing.

#### Layer 2: Driver command tests

Use a fake PyVISA resource that records SCPI commands:

- Assert correct command strings.
- Assert response parsing.
- Assert initialization settings.
- Assert error handling.

#### Layer 3: Equipment-process tests

Start a fake instrument process and a `VirtualDeviceTemplate` proxy.

Verify:

- Method calls are delivered.
- Results are returned.
- Unknown methods are rejected.
- Timeouts are handled.
- Disconnect works.
- Watchdog kicks are sent only for supporting devices.

#### Layer 4: Headless end-to-end test

Run a short charge/discharge/rest sequence using simulated equipment.

Assertions:

- Correct equipment outputs are enabled and disabled.
- Current and voltage setpoints are correct.
- CSV logs are created.
- Columns are correct.
- End conditions are reached.
- Safety cutoff stops the test.
- GUI status queue receives expected transitions.

#### Layer 5: GUI tests

Use `pytest-qt` and an offscreen Qt platform.

Verify:

- Channel creation.
- Equipment assignment.
- Start/stop behavior.
- Safety warning display.
- Process cleanup.

#### Layer 6: Optional hardware tests

Separate from CI:

```bash
pytest -m hardware
```

These should require an explicit environment variable or command-line option so they never run accidentally on machines without lab hardware.

---

## 11. Suggested refactor sequence

### Phase 1: Stabilize current behavior

1. Add a syntax/import check script or CI job.
2. Remove or fix syntax-broken files.
3. Add main guards to standalone scripts.
4. Remove duplicate definitions.
5. Remove high-confidence dead code.
6. Add a minimal test harness.

### Phase 2: Package and isolate

1. Add `pyproject.toml`.
2. Create an explicit package layout.
3. Separate core dependencies from optional hardware dependencies.
5. Add linting and formatting.

### Phase 3: Make the architecture testable

1. Introduce device protocol interfaces.
2. Inject a resource factory into `PyVisaDevice`.
3. Replace `eval()` dispatch with an allowlist.
4. Add standardized request/response messages.
5. Add structured logging.
6. Factor GUI-independent test logic out of `battery_test.py`.

### Phase 4: Add simulation

1. Implement the battery-cell world model.
2. Upgrade fake instruments to use the world model.
3. Add driver command tests.
4. Add equipment-process tests.
5. Add a headless end-to-end test.

### Phase 5: Modernize dependencies

1. Move to Python 3.13, then verify Python 3.14 compatibility.
2. Update analysis packages.
3. Replace removed pandas APIs.
4. Update Qt/PyVISA packages.
5. Re-run all simulated tests after each dependency group.

---

## 12. Recommended cleanup decisions

| Decision | Recommended action |
|---|---|
| `live_graph_temp.py` | Remove unless live plotting is still desired |
| `add_temp_to_logs.py` | Keep only as a documented migration utility with a main guard |
| `test_scripts/` | Convert to pytest-compatible, hardware-marked tests |
| EasyGUI prompts | Keep initially, then progressively replace with PyQt dialogs |
| `eval()` dispatch | Replace immediately |
| Duplicate `get_equipment_dict()` | Remove the shadowed definition |
| Duplicate `A2D_DAQ.__del__()` | Remove one definition |
| Old ICA block in `GraphIV.py` | Remove |
| `requirements.txt` | Replace with `pyproject.toml` dependency groups |
| Python 3.9 support | Replace with a Python 3.13 baseline; verify Python 3.14 compatibility |
