# Test Equipment Control Architecture and Modernization Plan

> Status date: 2026-09-25
> Migration status: Python 3.14.7 is the supported runtime. The automated suite covers the deterministic simulated-cell model and GUI- and headless-driven end-to-end runs; physical-hardware validation remains deferred.
> Scope: Current repository state, active runtime architecture, instrument ownership, stale/unused code, known bugs, and a staged plan for Python/dependency modernization and end-to-end simulated testing.

## 1. Executive summary

`Test_Equipment_Control` is a lab automation suite built around a core lab-control application:

1. **Core lab-control application**
   - Main GUI entry point: `battery_test.py`
   - Application services: `battery_app/`
   - Reusable Qt controls: `battery_gui/`
   - Equipment registry/factory: `equipment.py`
   - Instrument drivers: `lab_equipment/`
   - Test execution engine: `charge_discharge/runner.py`
   - Configuration and logging: `Templates.py`, `jsonIO.py`, `FileIO.py`
   - Post-processing: `GraphIV.py`, `PlotTemps.py`, `voltage_to_temp.py`

The migrated core application targets **Python 3.14.7** and uses the dependency versions in `pyproject.toml`. It uses a process-isolated instrument ownership model: the GUI does not directly own most instruments during a test. Instead, each physical instrument is owned by a dedicated child process, and test-channel processes communicate with it through queues and proxy objects.

Completed cleanup includes removal of obsolete modules, the legacy uncorrelated
transport, dynamic `eval()` dispatch, and the old Python/dependency metadata.
The remaining work is physical-hardware validation. Section 10 documents the
implemented GUI and headless simulation path.

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
- Live status and measurement updates. Live plotting is a future optional feature, not part of the GUI rewrite.
- CSV logging.
- Test configuration import/export.
- Equipment assignment import/export.

Supported cycle types are defined in:

- `Templates.CycleTypes`
- `charge_discharge.profiles.CyclingSettings`

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
- Incremental capacity analysis is currently deferred; GraphIV has a TODO to
  re-implement it without DiffCapAnalyzer.
- BDF CSV capture with a JSON-LD metadata sidecar and project-level schema checks.
- Separate temperature logs.

### 2.8 BDF identity and continuation model

Battery test identity is deliberately separate from profile identity:

```text
institution_code + cell_name
    -> profile_id + profile_version
        -> test_id
            -> session_id
                -> cycle files
```

- `institution_code` and `cell_name` identify the output namespace and cell.
- `profile_id` identifies a reusable test program.
- `profile_version` identifies the exact profile settings, preferably by a
  normalized-content hash.
- `test_id` identifies one test campaign on one cell and persists across
  intentional continuation after a stop or restart.
- `session_id` identifies one execution attempt. A test may contain multiple
  sessions.
- The filename sequence is the persistent cycle number and is copied to
  `Cycle Count / 1`.
- `Step Count / 1` is global across the continued test; `Step ID` remains the
  cycle-local program step identifier.

The per-cell manifest is a cache and allocation record for the latest cycle
and step values. It is not the measurement authority: raw BDF files and
their metadata remain the recovery and audit source. If a profile changes,
the application starts a new `test_id`, records the prior test as a
continuation reference, and uses the new `profile_version`.

---

## 3. Main runtime architecture

### 3.1 High-level flow

```text
battery_test.py
    MainTestWindow
        |
        | Qt presentation and user actions
        v
battery_app/application.py
    BatteryApplication facade
        | lifecycle, assignments, scans, probes, polling
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
charge_discharge/process_entrypoints.py
    CyclingControl process target
        |
        v
equipment.get_equipment_dict()
    creates proxy devices for channel process
        |
        v
lab_equipment/correlated_device.py
    sends correlated protocol-v2 requests through queues
        |
        v
equipment.virtual_device_management_process()
    instrument-owning child process
        |
        v
concrete instrument driver
```

### 3.2 GUI and application facade

`battery_test.py` defines `MainTestWindow` and the embedded widgets.
`battery_app/application.py` defines the Qt-independent `BatteryApplication`
facade used by the window to coordinate equipment and channel services.

The GUI layer is responsible for:

- Owning the PyQt event loop.
- Compose channel, equipment, assignment, and profile widgets.
- Render facade events as status, measurement, and error UI.
- Forward user actions to `BatteryApplication`.

The application facade and its services are responsible for:

- Channel lifecycle and state, including assignment and configuration.
- Equipment discovery, owner-process startup, capability descriptors, and
  exclusive instrument/channel claims made when an assignment is applied.
- Starting and stopping test and idle processes, polling their messages,
  handling worker failures, and safe process cleanup at shutdown.
- Emitting frontend-neutral events; it contains no Qt widget state.

The window may retain widget-facing compatibility mappings, but the lifecycle
and coordination policy belong to `BatteryApplication` and its services.

### 3.3 Equipment scan and selection

#### Resource scan

1. The GUI forwards the scan action to `BatteryApplication.scan_resources()`.
2. The application/equipment service starts `update_resources_list_process()`.
3. That process calls `equipment.get_resources_list()`.
4. `get_resources_list()` queries PyVISA backends:
   - `@py`
   - `@ivi`
5. The resource list is returned to the GUI through `resources_list_queue`.

The backend list remains deliberately fixed to `@py` and `@ivi`, but each backend
is probed independently. An unavailable backend is logged and skipped, so it does
not prevent resources from the other backend from being returned. Each returned
resource also retains its backend identifier.

#### Connect new equipment

1. GUI exposes the embedded equipment connection panel and forwards the
   selection to the application/equipment service.
2. The user selects:
   - PSU
   - E-load
   - DMM
   - Other equipment
3. The application starts a managed, non-mutating equipment probe with the explicit type, model, resource, and setup choices.
4. The selected equipment class calls the matching `equipment.py` chooser:
   - `powerSupplies.choose_psu()`
   - `eLoads.choose_eload()`
   - `dmms.choose_dmm()`
   - `otherEquipment.choose_equipment()`
5. The chooser opens the selected resource and queries its identity without calling driver `initialize()` or applying setup commands. Setup defaults and explicit choices are retained in the returned descriptor.
6. `equipment.get_res_id_dict_and_disconnect()`:
   - Extracts the PyVISA resource ID.
   - Extracts setup state.
   - Closes the physical resource.
   - Returns a serializable equipment descriptor.

7. A dedicated owner process reopens the resource, calls driver `initialize()`, applies the saved setup choices once, and only then reports readiness.

This read-only-probe, close, and owner-reconnect pattern lets the GUI store only descriptors while avoiding instrument resets or setup changes during identification. Composite Parallel E-load probes are rejected until they have a non-mutating probe implementation.

#### Owner startup and deferred rediscovery

Equipment assignment import reconnects the exact saved `res_id`. The connected
equipment descriptor is published for assignment only after the owner process
reports successful resource opening and driver initialization. A failed or
timed-out startup stops the owner and leaves no connected descriptor or
assignment claim.

If a device moves from one COM or USB/VISA address to another, the application
does not automatically search for it yet. Import-time rediscovery remains
deferred. Its planned flow is deliberately fail-closed:

1. Attempt the saved `res_id` first.
2. On connection failure, scan only resources compatible with the saved driver.
3. Query `*IDN?` where the driver supports it and compare a normalized,
   serial-bearing hardware identity.
4. Rebind and persist the new `res_id` only when exactly one candidate matches.
5. If there are zero matches, duplicate/non-serial IDNs, or a driver without a
   reliable IDN, require manual verification and selection; never silently
   substitute another instrument.

### 3.4 Physical instrument ownership

The most important architectural distinction is:

> A test-channel process does not normally own a PyVISA instrument directly. It owns a correlated capability proxy. A separate equipment process owns the real PyVISA resource.

#### Ownership sequence

1. The equipment service receives the selected equipment type, model, and
   resource from the application.
2. The equipment service creates:
   - `queue_in`
   - Per-channel response queues registered by `client_id`.
   - a dedicated `multiprocessing.Process`
3. The process runs `equipment.virtual_device_management_process()`.
4. That process calls `equipment.connect_to_eq()` and creates a concrete driver.
5. The concrete driver inherits from `lab_equipment.PyVisaDeviceTemplate`.
6. `PyVisaDeviceTemplate.__init__()` creates a `pyvisa.ResourceManager`.
7. It opens the PyVISA resource, configures termination and timing, queries
   `*IDN?`, and calls `initialize()`.
8. Only after initialization succeeds does the owner acknowledge readiness.
   The equipment manager then publishes the descriptor, response routes, and
   ownership slots.
9. The instrument-owning process handles queued method calls. The manager
   retains:
   - Process ID.
   - Request and response routing metadata.
   - Class name.
   - Resource ID.
   - Setup dictionary.
   - Local ID.
   - Instrument IDN.

#### Instrument process loop

`equipment.virtual_device_management_process()`:

- Reads `queue_in`.
- Expects a protocol-v2 request:
  ```python
  {
      "protocol": 2,
      "request_id": "...",
      "client_id": "...",
      "operation": "method_name",
      "args": [...],
      "instrument_channel": 0,
  }
  ```
- Dispatches the operation through the explicit allowlist.
- Returns a structured response to the requesting client's private queue.
- Periodically calls `device.kick()` if present.
- Stops on a `stop` message.

Unsupported or non-callable operations are rejected with a structured error.

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

- `queue_in` and a private response queue registered by `client_id`
- `equipment_id`, a persisted identity for the connected instrument
- `local_id`
- required `eq_ch`: `0` for a singleton or canonical `1..N` for a
  multi-channel instrument

Connected equipment descriptors also expose `capabilities` and canonical
`instrument_channels`: `[0]` for a singleton or `[1, ..., N]` for a
multi-channel instrument. The embedded assignment widget only offers a role when
the required capability is explicitly present, and emits the selected
`equipment_id`, `local_id`, and `eq_ch` together. `local_id` remains a runtime
index; it is not used to rebind imported assignments. Equipment-assignment
schema version 3 requires a stable `equipment_id` and a valid canonical
`eq_ch` for every connected instrument and assigned role.

`eq_ch` is both the ownership slot and the canonical driver-selection value.
The owner process treats `0` as a singleton slot and does not pass it to a
driver. Before every operation for a positive `eq_ch`, it calls the driver's
`select_channel(eq_ch)`. Each multi-channel driver owns the conversion from
the canonical `1..N` selection to its native numbering; for example, the A2D
DAQ converts `1..64` to physical channels `0..63`.

`BatteryApplication` applies the assignment through the equipment assignment
service. Applying it claims the requested instrument slot, adds queue-routing
metadata, and stores the assignment in channel state. A running test uses that
claim; start does not perform a second claim. `res_ids_dict_list` is not part of
the current implementation.

### 3.6 Test-channel process

When the user starts a test:

1. The GUI forwards the action to `BatteryApplication.start_test(ch_num)`.
2. The application facade validates:
   - Safety error is clear.
   - Equipment is assigned.
   - Test configuration exists.
3. Application services stop the idle process and clear stale queues.
4. The process service starts a process targeting `charge_discharge.process_entrypoints.run_charge_discharge_control()`.
5. The channel process receives:
   - Equipment descriptor dictionary.
   - Data output queue.
   - Data input/control queue.
   - Test configuration.
   - Channel number.

#### Worker failure behaviour

`CyclingControl` catches operational exceptions at each worker entry point. It
logs the full traceback, attempts a best-effort output shutdown when equipment
has connected, and publishes this serializable message on the channel data
queue:

```python
{
    "type": "error",
    "data": {
        "message": "Charge/discharge worker failed: RuntimeError: ...",
        "worker": "Charge/discharge worker",
        "exception_type": "RuntimeError",
    },
}
```

`BatteryApplication.poll()` consumes that message before considering an idle
restart. It changes the channel to `ChannelStatus.ERROR`, emits a renderable
error event, and does not automatically restart idle measurement for that
channel. Starting a later test remains the explicit recovery action after the
operator corrects the cause. A safety fault retains priority over a concurrent
worker error and still requires the normal safety-clear acknowledgement.

After publishing the message, the worker re-raises the original exception so
the process has a non-zero exit code. This prevents an idle restart if the
multiprocessing queue delivers the final error message after process exit.

The application also reaps finished test and idle process handles. If a worker
terminates with a non-zero exit code before it can publish an error message,
the application creates the same visible error state from that exit code. This
is a fallback for abrupt process failures or delayed queue delivery, not the
normal error-reporting path.
Configuration and equipment setup failures that formerly returned the internal
`"settings"` sentinel are promoted to worker failures as well, so they follow
this same visible path instead of being mistaken for a completed test.

### 3.7 Reconnecting equipment inside the channel process

`charge_discharge.process_entrypoints.run_charge_discharge_control()` creates `CyclingControl`.

`CyclingControl.charge_discharge_control()` calls:

- `equipment.get_equipment_dict(res_ids_dict)`

The current effective implementation checks each descriptor. If it contains queue routing metadata, it calls:

- `equipment.connect_to_virtual_eq()`

This returns a correlated capability proxy from `lab_equipment.correlated_device`.

Therefore:

- The channel process owns proxy objects.
- The instrument-owning process owns PyVISA resources.
- PyVISA calls are isolated to the equipment process.

### 3.8 Queue protocol

The correlated capability proxy wraps method calls. For example, `measure_voltage()`:

1. Builds:
   ```python
   {
       "protocol": 2,
       "request_id": "...",
       "client_id": "...",
       "operation": "measure_voltage",
       "args": [],
       "instrument_channel": canonical_channel,
   }
   ```
2. Puts it on `queue_in`.
3. Waits for the matching `request_id` on its private response queue.
4. Converts the result to the expected type.

The owner process uses `instrument_channel` to select a positive channel
before dispatching the operation. It retains `0` as metadata for singleton
ownership and dispatches the operation without a channel argument.

All operations use the same acknowledged request/response protocol. Each
client receives responses through a private response queue registered with the
owner process, so separate channel processes cannot consume one another's
responses.

### 3.9 Test execution engine

The extracted execution services now live under `charge_discharge/`:

- `conditions.py` contains pure safety and end-condition evaluation.
- `requirements.py` calculates PSU/e-load requirements for steps and plans.
- `measurement.py` collects primary and auxiliary measurements.
- `equipment_control.py` owns equipment initialization and safe shutdown.

The multiprocessing entry points are in `process_entrypoints.py`. The embedded
`ProfileEditorWidget` delegates one-step charge, discharge, and rest authoring
to the shared `ProfileIdentityService`; imported JSON can supply richer normalized
plans. The pure profile validator validates imported and widget-created
profiles before they reach the runner. Profile compilation and the step runner
remain in their focused modules. The portable file contract is maintained separately in
[`PROFILE_JSON_CONTRACT.md`](PROFILE_JSON_CONTRACT.md).

#### `CyclingControl`

Runtime execution:

- Initializes equipment.
- Disables outputs.
- Connects relay-board paths.
- Starts each step.
- Measures voltage/current/temperature.
- Evaluates end conditions.
- Evaluates safety conditions.
- Writes measurement CSV files and application-wide diagnostic log events.
- Reports caught worker failures to the application queue and attempts a
  best-effort equipment shutdown before returning.
- Sends status and measurements to the GUI.
- Stops on user request or safety fault.

#### Profile validation and `CyclingSettings`

`battery_app.profile_validation.validate_profile_configuration()` owns the
profile validation boundary. It validates the normalized cycle/step structure,
requires the declared schema and `profile_name`, rejects unknown fields,
verifies `profile_id` and `profile_version`, and calculates `eq_req_dict`.
`battery_app.profile_identity.ProfileIdentityService` creates profile IDs and revisions.
The embedded simple editor calls that service, while the battery-test GUI never
revises an imported profile; neither component calculates equipment
requirements. The Profile Revision CLI exposes `create` and `revise` for
trained users authoring JSON without a Profile Designer.

`CyclingSettings` remains the compatibility conversion helper for older
settings dictionaries. New advanced profile files should contain normalized
`cycle_type: "step"` objects directly and must not contain executable code or
GUI widget state.

### 3.10 Data flow

```text
CyclingControl
    -> data_out_queue
        -> BatteryApplication.poll()
            -> frontend-neutral application events
                -> MainTestWindow renders status, live measurements,
                   and safety warning state
```

Control flow:

```text
MainTestWindow action
    -> BatteryApplication
        -> data_in_queue
        -> CyclingControl.end_signal()
            -> stop request
```

Log flow:

```text
CyclingControl
    -> FileIO.write_bdf_data() and FileIO.write_bdf_metadata()
        -> BDF CSV log and JSON-LD metadata sidecar
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

`lab_equipment/correlated_device.py` provides the transport and named
capability proxies for source, load, DMM, and relay operations:

- Measurement
- Output control
- Calibration
- Relay control
- Fan and LED control
- RS-485 address management
- I2C address setup

The removed `VirtualDeviceTemplate.py` legacy proxy is no longer part of the
application transport.

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
| `charge_discharge/runner.py` | Equipment-facing step execution | Equipment primitives remain here; cycle navigation is delegated to `cycle_executor.py` |
| `charge_discharge/cycle_executor.py` | Cycle and step navigation | Coordinates cycle logs, status events, and stop conditions |
| `battery_test.py` | GUI composition and Qt event routing | Uses `ChannelState` and application services; hardware lifecycle is delegated |
| `GraphIV.py` | BDF-aware post-processing and plotting | Its loading boundary validates BDF data before the existing analysis pipeline enriches DataFrames in place |
| `equipment.py` | Equipment registry and virtual-device dispatch | Broad imports and tightly coupled registry |
| `lab_equipment/correlated_device.py` | Correlated protocol-v2 transport and capability proxies | Requires a registered private response queue for cross-process use |
| `Templates.py` | Settings defaults and schemas | Plain dicts without validation |

---

## 7. Dead, stale, or unused code

The following is based on static import and reference analysis. Some driver methods may still be useful even when no current caller exists because they form a public hardware interface.

### 7.1 Completed removals

`live_graph_temp.py`, `lab_equipment/DMM_FET_BOARD_EQ.py`,
`add_temp_to_logs.py`, and `MSXIV_Battery_Module_Wiring_Test.py` are absent
from the repository. They are completed removals, not remaining cleanup
targets.

### 7.2 Dead code inside active files

`equipment.py` contains one `get_equipment_dict()` definition, and
`lab_equipment/A2D_DAQ_control.py` contains one `A2D_DAQ.__del__()` definition.
The former duplicate-definition findings are resolved.

#### `GraphIV.py`

- Incremental-capacity analysis was removed from the active path. Re-implement it
  later against the BDF columns without restoring DiffCapAnalyzer.
- Remove the obsolete block.
- `add_cycle_numbers()` has no current in-repository caller.
- `get_filename_pref`, `glob`, `itertools`, `peakutils`, `scipy`, and `sqlite3` are imported but not currently used.

#### `FileIO.py`

`FileIO.py` no longer imports pandas. `ensure_subdir_exists_file()` remains a
small compatibility helper with no current in-repository caller.

#### `battery_test.py`

- Imports `Event` and `json` without current use.

### 7.3 Manual hardware tests

`hardware_tests/` contains hardware smoke scripts rather than automated tests. The name is
ambiguous because it can be mistaken for a pytest test package.

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

### 8.1 Removed syntax-broken files

There are no known syntax-broken Python files in the current source tree. The
former `live_graph_temp.py` placeholder was removed.

### 8.2 Unsafe dynamic method dispatch

`equipment.virtual_device_management_process()` previously used:

```python
device.<method_name>(*args)
```

Problems:

- The old implementation allowed arbitrary method-name evaluation.
- The current implementation validates the method against the proxy registry.

Current implementation:

```python
method = _dispatch_virtual_device_method(device, method_name, data)
```

The transport uses an explicit operation registry and named capability
proxies. Unsupported operations fail in the owner process with a structured
error response.

### 8.3 Response timeout policy

The correlated proxy centralizes response waiting and raises a timeout when a
matching response is not received. Per-device or per-method timeout tuning can
be added later without reintroducing an uncorrelated response channel.

### 8.5 Resource scan failure handling

`equipment.get_resources_list()` now probes `@py` and `@ivi` independently,
logs backend-specific failures, closes each successfully created resource
manager, and returns resources from the available backends. The remaining
constraint is the intentionally fixed two-backend list.

### 8.6 Incomplete construction state

`PyVisaDevice.__init__()` can return early if no device is selected, without fully initializing the object. Callers may then receive an object without `inst`, causing later failures.

Recommendation:

- Raise a typed exception instead of returning early.
- Or return `None` explicitly.
- Validate all required attributes after construction.

### 8.7 Connect-close-reconnect pattern

Equipment selection opens a resource for an identity query, closes it, and another process later reopens it for initialization and ownership.

This is central to the current process-ownership model, but it can fail if:

- The backend does not release the resource immediately.
- Another process claims the resource.
- The instrument requires a recovery delay.

Direct PyVISA drivers now skip driver initialization and setup commands during
the probe. The owner process remains responsible for initialization and applies
the saved setup dictionary once. Composite Parallel E-loads still need a
read-only probe implementation and are rejected by the probe path.

### 8.8 Outdated pandas operation

`GraphIV.py` uses `pandas.concat()` for summary-row updates and does not use
the removed `DataFrame.append()` API.

### 8.9 Missing main guards

Most files under `hardware_tests/` execute hardware actions immediately when run and are not pytest tests.

Recommendation:

- Add `if __name__ == "__main__":` guards.
- Convert test scripts to pytest-compatible functions.

### 8.10 Packaging baseline

`pyproject.toml` defines the project metadata and explicitly packages
`battery_app`, `battery_gui`, `charge_discharge`, and `lab_equipment`. The
battery entry point remains a root-level script, so invoking it from the
repository root is still the supported development workflow.

### 8.11 Duplicate and broad driver imports

`equipment.py` imports every driver at module import time.

Issues:

- Heavy import graph.
- A single optional dependency can break the entire application.
- Hardware-specific modules are tightly coupled.

Recommendation:

- Use a registry of lazy imports or entry points.
- Separate required drivers from optional drivers.

### 8.12 Application-wide logging

The battery application uses Python's `logging` module through
`battery_app.logging_config`. The GUI and its worker processes write to a
shared rotating `logs/application.log` file. Each entry includes the timestamp,
severity, process name and ID, logger name, and message so failures in a child
process can be correlated with GUI activity.

The application log covers user-facing status, equipment connection and
instrument-operation failures, test lifecycle events, safety events, and
exceptions. The measurement CSV files remain the durable record of sampled
data; the old per-cycle text logs are no longer created.
  - Errors.

### 8.13 No formal device protocols

The application relies on duck typing and `hasattr()`.

See the prioritized implementation plan in [Section 13.2](#132-define-explicit-driver-capability-protocols).

---

## 9. Dependency and Python modernization

### 9.1 Current baseline

The supported runtime is Python 3.14.7, pinned in `.python-version` and `pyproject.toml`.

The Python 3.14 runtime dependencies are pinned in `pyproject.toml`, including:

- `numpy==2.5.3`
- `pandas==3.0.6`
- `matplotlib==3.11.2`
- `scipy==1.18.1`
- `PyQt6==6.11.0`
- `PyVISA==1.16.2`
- `PyVISA-py==0.8.1`
- `batterydf==0.1.0` (optional analysis/validation)
- `keyboard==0.13.5`
- `retry==0.9.2`

The battery application uses Qt dialogs through `battery_gui.dialogs`. The
legacy `easygui` dependency is optional and reserved for one-off hardware
scripts; it is not imported by the battery application or its packaged path.

### 9.2 Recommended target

Use Python 3.14.7 as the supported baseline.

Rationale:

- This project uses native and binary-dependent packages such as PyQt6, PyVISA backends, `hidapi`, and scientific libraries. Those wheels and platform drivers require validation on the lab workstation.
### 9.3 Dependency groups

Dependency groups are defined in `pyproject.toml`:

- `pyproject.toml`
- Runtime dependencies
- Development/test dependencies
- Optional hardware dependencies

Recommended groups:

```text
runtime:
    PyQt6
    pyvisa
    pyvisa-py
    pandas
    numpy
    scipy
    matplotlib
    batterydf (optional analysis/validation)

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
  - Removed from the active analysis path; re-evaluate only when ICA is reimplemented.

### 9.5 Staged update sequence

Do not update all dependencies at once. Use staged compatibility passes:

1. **Make the package importable**
   - Completed with `pyproject.toml`.
   - Completed with explicit package files.
   - Completed with dependency groups.

2. **Remove dead code**
   - Delete or archive obsolete files.
   - Remove duplicate definitions.
   - Remove unused imports.
   - Add main guards.

3. **Move to the Python 3.14 baseline**
   - Completed for the core dependency set.
   - Runtime and hardware validation remain.

4. **Update analysis stack — completed**
   - NumPy, pandas, SciPy, and matplotlib are pinned at the current Python
     3.14 baseline.
   - The removed `DataFrame.append()` call was replaced with `pandas.concat()`.

5. **Update GUI stack — completed package update; hardware validation remains**
   - PyQt6 is pinned at the current baseline.
   - Validate the Qt event loop and multiprocessing behavior on the lab workstation.

6. **Update instrument stack — completed package update; hardware validation remains**
   - PyVISA, PyVISA-py, pyserial, pyusb, and hidapi are pinned in their
     applicable dependency groups.

7. **Reassess optional dependencies**
   - EasyGUI
   - batterydf (optional analysis/validation package)

---

## 10. End-to-end simulation and self-testing status

The deterministic `BatteryCellWorldModel`, `FakeBatteryLink`, and end-to-end
test path are implemented. Both headless and GUI simulation run through the
normal owner-process and correlated-proxy transport before fake drivers apply
their commands to one shared model and the profile engine writes BDF output.

### 10.1 Implemented full-path test architecture

```text
pytest or GUI
    -> EquipmentManager
        -> Fake PSU owner process
        -> Fake E-load owner process
        -> Fake DMM owner process
    -> channel test worker
        -> correlated equipment proxies
            -> fake owner method call
                -> shared FakeBatteryLink service
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

The deterministic cell model has inputs including:

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

### 10.3 Fake instruments and the GUI-simulation boundary

The first integration path uses the profile cell name `SIMULATED_LG_MJ1`.
`SIMULATED_LG_MJ1` requires assigned `Fake Test PSU`, `Fake Test Eload`, and
`Fake Test DMM` owner-process proxies. At test start, the channel worker starts
one process-safe `FakeBatteryLink` service and sends its link proxy through the
normal correlated transport to each fake instrument owner. The fake driver's
normal `set_current()`, `toggle_output()`, and measurement methods then apply
to or read from that shared model. The profile and step engine, proxy request
correlation, instrument ownership checks, and BDF output therefore use the
same path as a physical-instrument test. Non-fake assignments are rejected.
Fake instruments do not provide fixed measurements: an operation without an
attached simulation link fails explicitly.

The implemented path is current-controlled: the PSU and e-load apply their
configured current through the shared model, and the DMM reads that model.

#### Deferred simulation-fidelity work

The following extensions are deliberately deferred rather than silently
emulated with fixed values:

1. Model PSU voltage/current regulation and e-load constant-voltage mode, so
   voltage setpoints participate in the operating point rather than only being
   recorded by the fake driver.
2. Enforce simulated voltage/current limits and instrument faults, including a
   fake relay board when relay isolation is part of the assigned equipment.

Until that work is complete, simulated profiles should use the implemented
current-controlled operating modes.

#### `FakePowerSupply`

Methods:

- `set_voltage()`
- `set_current()`
- `toggle_output()`
- `measure_voltage()`
- `measure_current()`

Behavior:

- In the implemented current-controlled path, it applies its configured current
  to the cell model and measurements reflect that model.
- Voltage-regulation and current-limit faults are deferred simulation-fidelity
  work.

#### `FakeElectronicLoad`

Methods:

- `set_current()`
- `set_mode_current()`
- `set_mode_voltage()`
- `toggle_output()`
- `measure_voltage()`
- `measure_current()`

Behavior:

- Draws its requested current through the cell model.
- Constant-voltage operation and limit/fault behavior are deferred
  simulation-fidelity work.

#### `FakeDMM`

Methods:

- `measure_voltage()`
- `measure_current()`
- `measure_temperature()`

Behavior:

- Reads from the world model.
- Measurement noise, latency, and injected failures are not currently modeled.

#### `FakeRelayBoard`

Methods:

- `connect_psu()`
- `connect_eload()`
- `psu_connected()`
- `eload_connected()`

Behavior:

- Not implemented in the current simulated equipment set; relay behavior is
  deferred simulation-fidelity work.

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

Start a fake instrument process and a correlated capability proxy.

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

Completed through `pyproject.toml`, explicit `lab_equipment` package metadata, separated dependency
groups, and Ruff configuration.

### Phase 3: Make the architecture testable

1. Introduce device protocol interfaces.
2. Inject a resource factory into `PyVisaDevice`.
3. Replace `eval()` dispatch with an allowlist. Completed.
4. Add standardized request/response messages.
5. Extend structured logging to instrument request/response traffic where the
   diagnostic value justifies the additional volume.
6. Factor GUI-independent test logic out of `battery_test.py`.

### Phase 4: Add simulation

The deterministic cell model, fake-battery link service, equipment-owner
process tests, and headless and GUI-style end-to-end BDF tests are complete.
Simulation preserves the complete correlated instrument transport described in
section 10.3.

### Phase 5: Modernize dependencies

1. Validate the Python 3.14 environment and dependency lock file.
2. Update analysis packages.
3. Replace removed pandas APIs.
4. Update Qt/PyVISA packages.
5. Re-run all simulated tests after each dependency group.

---

## 12. Recommended cleanup decisions

| Decision | Recommended action |
|---|---|
| `live_graph_temp.py` | Removed; live plotting remains a future optional feature |
| `add_temp_to_logs.py` | Removed as legacy code |
| `MSXIV_Battery_Module_Wiring_Test.py` | Removed as legacy code |
| `hardware_tests/` | Keep as manually invoked hardware scripts; do not collect as pytest tests |
| EasyGUI prompts | Keep initially, then progressively replace with PyQt dialogs |
| `eval()` dispatch | Replaced with an allowlisted proxy-method registry |
| Duplicate `get_equipment_dict()` | Resolved; retain the sole virtual-queue-aware implementation |
| Duplicate `A2D_DAQ.__del__()` | Resolved; retain the sole implementation |
| Old ICA block in `GraphIV.py` | Remove |
| `requirements.txt` | Removed; use `pyproject.toml` and `requirements.lock.txt` |
| Python 3.9 support | Removed; Python 3.14.7 is the only supported runtime |

---

## 13. Future improvements

These are remaining follow-up items, not gaps in the current exclusive
ownership or worker-failure design. They should be implemented as separate
changes with their own simulated and hardware validation. Section 13.1 records
the completed owner-startup acknowledgement and the still-deferred address
rediscovery work.

### 13.1 Confirm instrument-owner readiness and reconnect safely

**Owner-startup acknowledgement: implemented.** A descriptor is added to the
connected-equipment list only after the owner process reports that the selected
resource opened and the driver initialized. Failed startup and timeout leave no
connected descriptor or ownership slot. Rediscovery after a saved resource
address changes remains deferred.

#### Current limitation

An imported assignment uses its saved VISA resource address directly. If that
address has changed, the connection fails and the user must reconnect equipment
manually.

#### Intended design

1. For future rediscovery, try the saved address first. If it fails, scan only
   resources compatible with the saved driver and accept a replacement only
   when exactly one normalized, serial-bearing identity matches. Require manual
   selection for zero, ambiguous, or non-serial matches.
2. The owner startup handshake sends a serializable success result only after
   opening the resource, validating the driver, and completing initialization.
   The result includes the resource identity and IDN when available.
3. `EquipmentManager` publishes the connected-equipment record, response
   routes, and ownership slots only after that success result arrives.
4. On timeout or failure, stop the owner and return a visible connection error;
   do not expose a partially connected instrument to assignment controls.
This preserves the current rule that a battery channel never gains ownership of
an instrument slot until the physical owner is known to be usable. Tests should
cover successful acknowledgement, startup timeout, initialization failure,
stale-resource rediscovery, and ambiguous-match rejection.

### 13.2 Define explicit driver capability protocols

**Priority: high.** The selected models now have a first rated-limit, setpoint
readback, and status-check slice. Complete the capability-specific driver
contracts and the planned physical validation before treating the selected
hardware path as qualified. Extend support model by model; do not assume every
driver offers the same readbacks.

**Implemented slice:** the B&K 8601 and Siglent SPD1168X drivers advertise
their rated voltage, current, and power after owner initialization. Before a
test worker starts, `BatteryApplication` checks each driven profile step and
its safety envelope against the assigned physical instrument's ratings. Fake
equipment is exempt. A physical driver without complete ratings is rejected
for a driven step so the check cannot silently pass without data. That startup
rating check alone does not confirm live setpoints, operating mode, or output
state; those are handled by the separate driver readback and status checks
described below.

The B&K 8601 and SPD1168X now verify their model-specific setpoint writes by
reading them back in the instrument-owner process. The B&K also verifies its
selected function and input state; the Siglent verifies output state and checks
its SCPI error queue. The cycle runner requests a combined health check from
each audited instrument owner at step start and at most once per second while
the step runs. Successful checks return no payload; a mismatch or device fault
raises in the owner and arrives as a correlated operation failure. That fails
the worker and triggers its existing best-effort safe shutdown. Profile
voltage/current safety limits continue to be checked on every measurement
sample by the runner. Before the first sample of a driven step, the runner uses
a 0.1-second software settling interval, bounded by the step's time and safety
limits. Instrument readbacks and VISA query latency add time before the sample;
the interval does not promise a measurement exactly 0.1 seconds after output
enable. The Siglent CV/CC status describes live regulation, so it is not treated
as a fault or fixed mode requirement.

The readback acceptance bands are based on the selected models' published
programming resolution, not on output accuracy specifications:

| Model | Readback | Acceptance band | Published basis |
| --- | --- | ---: | --- |
| B&K 8601/B | Current setpoint | 0.001 A | 1 mA CC high-range resolution; `*RST` selects the high range |
| B&K 8601/B | Voltage setpoint | 0.01 V | 10 mV CV resolution |
| Siglent SPD1168X | Voltage setpoint | 0.001 V | 1 mV resolution |
| Siglent SPD1168X | Current setpoint | 0.001 A | 1 mA resolution |

The driver accepts a readback difference up to one listed resolution count.
The values come from the [B&K 8600 Series datasheet](https://bkpmedia.s3.us-west-1.amazonaws.com/downloads/datasheets/en-us/8600_Series_datasheet.pdf)
and [Siglent SPD1168X user manual](https://siglentna.com/wp-content/uploads/dlm_uploads/2018/05/SPD1168X_UserManual_UM0501X-E01A.pdf).
The [B&K programming manual](https://bkpmedia.s3.us-west-1.amazonaws.com/downloads/programming_manuals/en-us/8600_Series_programming_manual.pdf)
and Siglent manual describe the set/query commands used by the drivers; current
automated coverage uses simulated instrument responses. A physical instrument
has not yet been exercised, so hardware readback behavior remains to be
confirmed during the planned bench test. A setpoint register matching within
one LSB does not prove that the output terminals meet their accuracy
specification; output accuracy and measurement uncertainty are separate
specifications and checks.

#### Current limitation

The driver layer still relies partly on duck typing and `hasattr()`. That makes
adding a new instrument or capability less discoverable than it should be and
can defer an incompatible driver error until a test is already running.

#### Intended design

Define small operation-based `typing.Protocol` interfaces, such as
`PowerSupplyProtocol`, `ElectronicLoadProtocol`, `DMMProtocol`,
`RelayBoardProtocol`, and `SourceMeasureUnitProtocol`. Keep each protocol
limited to its actual capability operations; do not make every driver implement
an oversized common base class.

Setpoint, mode, and output-state verification should be represented as explicit
supported capabilities. Where a device exposes a reliable readback, verify the
reported value after the corresponding command. Do not treat cached driver
state as instrument confirmation or require unsupported queries from every
model.

At connection time, validate the capabilities advertised by the driver against
the protocol and its operation registry. At assignment and profile-validation
time, validate that the selected equipment can satisfy the required capability.
The correlated transport remains the one request/response mechanism; protocols
describe what may be requested, not a second transport or another resource
owner. Fake drivers should implement the same protocols as their physical
counterparts.

The selected B&K 8601/B and SPD1168X models have the initial rating and readback
slice. Remaining work is to complete the operation-based capability contracts
and expand capability-contract coverage to other supported models, including an
intentionally incomplete driver that is rejected before a worker starts.

### 13.3 Add deterministic simulation fault injection

#### Current limitation

The fake battery path validates normal command flow and worker-failure handling,
but it does not model measurement noise, latency, instrument command failures,
or owner-process failures.

#### Intended design

Add an opt-in, serializable fake-equipment fault scenario that can inject
deterministic events by operation count or simulated time. Initial scenarios
should include a rejected output command, a measurement exception, a delayed or
timed-out response, and an owner-process termination. Each scenario must remain
confined to fake drivers and the simulation test path; it must never alter
physical-equipment control or weaken output-off behavior.

Use these scenarios to exercise the complete failure contract: the worker sends
its structured error when possible, exits non-zero, `BatteryApplication` enters
`ERROR`, automatic idle restart remains suppressed, and safe shutdown is
attempted. The existing real child-process regression remains the baseline for
the abrupt-exit fallback.
