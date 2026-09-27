# Battery GUI and Execution Migration Plan

> Status: Completion 1 (application facade) and Completion 2 (GUI compatibility
> handoff removal) are implemented. Readiness review and advanced visual profile
> authoring remain planned; regression and hardware sign-off are pending.
> Scope: Rewrite `battery_test.py`, modernize the battery-test GUI, and replace the current multi-dialog workflow with one guided application interface.
> Constraint: Keep the application runnable after every phase.

## Current implementation status

The implemented migration work includes:

- `battery_app` contains typed channel state, bounded process lifecycle management, channel controllers, and Qt-independent message routing.
- `battery_app.EquipmentManager` owns connected instrument descriptors and equipment-owner process shutdown.
- `battery_gui.ChannelWidget` owns the per-channel measurement/status/action layout and communicates through intent signals.
- The channel workspace includes embedded common equipment assignment controls; assignment and profile changes call the application facade directly.
- Equipment connection uses an embedded type/model/resource panel; resource scans and instrument probes run through `BatteryApplication` and its managed workers.
- `BatteryApplication` owns channel state/controllers, equipment and configuration services, assignment claims, lifecycle orchestration, worker polling, and asynchronous resource/probe results. Importing the facade does not import Qt.
- The channel workspace includes an in-window common profile editor for charge, discharge, and rest plans; imported and advanced profiles remain compatibility paths.
- `ConfigurationStore` handles queue-free JSON persistence, and all shared-instrument requests use correlated protocol-v2 messages.
- `charge_discharge.profiles` owns the legacy-compatible profile conversion class, and `TestExecutionService` isolates channel controllers from legacy process-entry functions.
- `CyclingControl` lives in `charge_discharge.runner`; process entry points live in `charge_discharge.process_entrypoints`.
- `battery_test.py` uses a single active-channel workspace rather than a grid of channel plots.
- Live plotting has been removed from the battery GUI and `pyqtgraph` is no longer a runtime dependency.
- Live measurements remain available to the GUI and test engine.
- Battery measurements are written as fixed-schema BDF CSV files, one file per cycle,
  with JSON-LD metadata sidecars. The filename sequence is the persistent cycle
  number and is reused as `Cycle Count / 1`; existing BDF files are scanned so
  both cycle and global `Step Count / 1` continue across GUI starts. The output
  includes cycle-local `Step ID`, three timestamps, directional cycle
  capacity/energy, and mapped surface-temperature slots.
- GraphIV reads the BDF columns and metadata sidecars directly. Incremental-capacity
  analysis is deferred until it can be reimplemented without `DiffCapAnalyzer`.
- The BDF identity and continuation design is documented in the
  [architecture plan](ARCHITECTURE.md#28-bdf-identity-and-continuation-model).
  Current output continues cycle and step numbers by scanning existing BDF
  files; the per-cell manifest caches the latest allocated cycle and step
  values.

The equipment/profile panels and correlated shared-instrument transport are
implemented. They do not yet meet every target-workflow criterion in this plan;
the verified differences are recorded in the next section.

## Verified implementation differences

- The embedded profile editor builds one-step Charge, Discharge, and Rest
  plans. Single/repeated IR and multi-step plans are supported by the execution
  engine when imported as JSON. Imported profiles are displayed as read-only in
  the channel workspace; the simple editor must be explicitly re-enabled before
  it can replace an imported profile.
- The embedded assignment widget exposes PSU, e-load, relay-board, primary
  voltage/current/temperature, and one auxiliary voltage/current/temperature
  measurement role. Every selection has a canonical channel: `0` for a
  singleton or `1..N` for a multi-channel instrument. Role choices are
  filtered by the device's explicit capability list.
- Connected equipment now receives a persisted stable `equipment_id` in
  addition to the session-local `local_id`. New assignments resolve by the
  stable identity only; schema version 3 imports require every connected
  instrument and assigned role to carry that ID and a valid canonical channel.
  Other assignment schema
  versions are rejected during import.
- Equipment-assignment import reconnects the exact persisted `res_id` and now
  waits for the equipment-owner process to open and initialize that resource
  before displaying it as connected. It does not rediscover an instrument when
  a USB or COM-port address changes. A future import flow must scan compatible
  resources, compare a reliable `*IDN?`-based hardware identity, update the
  resource only for one exact match, and require manual verification or selection
  when there are zero or multiple matches.
- `eq_ch` is the required canonical assignment and ownership channel: `0` for
  a singleton and `1..N` for a multi-channel instrument. The owner process
  selects a positive channel before each operation. Channel-aware drivers
  translate that canonical number to their native numbering (for example,
  `1..64` to an A2D DAQ's `0..63`); singleton drivers never receive `0` as a
  method argument.
- Assignment-widget TODOs:
  - Hydrate each selector and channel control from an imported or already
    applied assignment, so the widget is a view of `ChannelState` rather than
    only its initial editor.
  - Show inline readiness feedback for missing required roles and unavailable
    or already-owned equipment channels, rather than reporting failed claims
    only through the application log.
  - Replace the fixed auxiliary voltage/current/temperature roles with an
    add/remove measurement-role list if a test needs more than one auxiliary
    measurement of a given kind.
  - Complete the planned review panel so assignment completeness and ownership
    availability are visible before Start is enabled.
- `MainTestWindow` delegates channel and equipment lifecycle to
  `BatteryApplication`. Assignment, profile, and cell-name changes use direct
  facade calls; the window retains one `ChannelWidget` per visible channel and
  no longer stores parallel dictionaries of its controls.
- Start buttons are validated when clicked, rather than being disabled until
  the review/validation criteria succeed. A separate review panel is also not
  implemented.
- `SIMULATED_LG_MJ1` is supported by the normal GUI assignment-and-start
  workflow through the full owner-process and correlated-proxy path. One
  process-safe `FakeBatteryLink` service is shared by the assigned fake
  instrument owners, so their normal control and measurement methods drive the
  model.

## Profile JSON contract

The standalone [profile JSON contract](PROFILE_JSON_CONTRACT.md) defines the
portable advanced-profile format, identity/revision rules, normalized step
fields, and the boundary between profile data and GUI-owned run context. Trained
users can create or revise hand-authored profiles through the Profile Revision
CLI; the battery-test GUI only imports and executes the resulting authored
profile.

Imported profiles are intentionally not edited by the embedded editor. The GUI
shows their identity, version, sequence, cycle/step count, and required
equipment. Selecting the simple editor creates a new draft; the imported
profile remains active until the draft is explicitly applied.

## 1. Goals

The migration has four goals:

1. Separate Qt presentation from equipment, process, and test-execution logic.
2. Preserve the existing process-isolated instrument ownership model.
3. Make shared instruments safe for multiple battery channels.
4. Replace scattered legacy dialogs with a single-window Qt workflow that exposes context-sensitive panels.

The rewrite should preserve the current user-visible capabilities:

- Resource scanning and equipment connection.
- Per-channel equipment assignment.
- Test profile creation, import, and export.
- Charge, discharge, rest, and IR tests.
- Live measurements, status, safety faults, and stop controls.

## 2. Target user experience

The application should use one main window with four regions:

```text
+---------------------------------------------------------------+
| Toolbar: Scan | Equipment | Profiles | Start/Stop | Settings  |
+----------------------+----------------------------------------+
| Channel navigator     | Active channel workspace              |
|                       |                                        |
| CH 0  Idle            | 1. Equipment / 2. Profile / 3. Review |
| CH 1  Running         |                                        |
| CH 2  Safety fault    | Equipment assignment                  |
|                       | Test profile editor                   |
|                       | Live measurements and test status      |
+----------------------+----------------------------------------+
| Event log / warnings / process and equipment connection state |
+---------------------------------------------------------------+
```

Use panels, tabs, or a stacked workspace instead of modal dialogs. A user should be able to:

- Select a channel.
- See its current equipment and profile.
- Edit one section at a time.
- Review the complete configuration.
- Start the test from the same workspace.

Dialogs should be reserved for genuinely exceptional decisions, such as confirming a destructive disconnect or acknowledging a safety fault.

Live measurements remain a first-class feature. Each active channel should show its latest:

- Cell voltage.
- Test current.
- Temperature values when assigned.
- Measurement timestamp or age.
- Current step and elapsed time.
- Safety state.

Measurements should continue to feed the test engine, safety evaluation, CSV logging, and the GUI message router. They should not be retained solely for visualization.

## 3. Migration rules

- Do not rewrite the GUI and the instrument transport protocol in one change.
- Do not move PyVISA resources into the GUI or channel processes.
- Do not persist queue handles or process objects.
- Keep compatibility wrappers until the new GUI has passed simulated end-to-end tests.
- Every phase must leave the existing application importable and testable.
- New GUI code should depend on typed application services, not raw multiprocessing queues.

## 4. Target architecture

```text
MainTestWindow
    -> ChannelWidget(s)
    -> BatteryApplication
        -> ChannelController
        -> EquipmentManager
        -> ConfigurationStore
        -> ProcessManager
        -> MessageRouter
            -> TestExecutionService
                -> charge_discharge.runner
                    -> StepExecutor
                    -> MeasurementService
                    -> EquipmentController
                    -> condition evaluation
            -> equipment-owner processes
                -> concrete PyVISA drivers
```

Recommended packages:

```text
battery_gui/
    channel_widget.py
    equipment_panel.py
    profile_panel.py
    review_panel.py

battery_app/
    application.py
    channel_controller.py
    equipment_manager.py
    process_manager.py
    message_router.py
    persistence.py
    state.py

charge_discharge/
    runner.py
    steps.py
    profiles.py
    conditions.py
    measurement.py
    equipment_control.py
    requirements.py
```

## 5. Phased migration

### Phase 0: Baseline and safety net

Deliverables:

- Record current GUI behavior and supported workflows.
- Add tests for channel startup, test start/stop, safety reset, import/export, and cleanup.
- Add a deterministic fake-equipment scenario.
- Capture the current queue message types and process ownership rules.
- Define a test-plan schema independent of Qt widgets.

Exit criteria:

- The current GUI still starts.
- The test suite can run without physical instruments.
- A failed child process is reported instead of leaving the GUI indefinitely busy.
  Caught runner exceptions publish an `error` queue message; an unexpected
  non-zero process exit is detected while polling as a fallback. Both put the
  channel in `ChannelStatus.ERROR` and suppress automatic idle restart until a
  later explicit test start. The worker re-raises after publishing, so its exit
  code also protects against delayed queue delivery.

### Phase 1: Introduce typed state and process services

Create:

- `ChannelState`.
- `ProcessManager`.
- `ChannelController`.
- `MessageRouter`.

Move channel lifecycle behavior out of `MainTestWindow` while keeping the existing widgets. The old GUI can call the new controllers through adapters.

Exit criteria:

- No new code adds entries to parallel per-channel dictionaries.
- Start, stop, idle restart, and cleanup tests pass.

### Phase 2: Extract the single-window UI shell

Create `ChannelWidget` and move the current per-channel controls and live measurement display into it. Do not carry the legacy plot widget into the new interface.

Live plotting is explicitly out of scope for this rewrite. Keep the channel UI extensible so a future version can add an `Open Live Plot` button or separate plot window without changing the measurement or execution services.

Replace direct widget dictionaries with:

```python
channel_widget.update_measurement(measurement)
channel_widget.update_status(status)
channel_widget.set_safety_fault(fault)
```

Exit criteria:

- `MainTestWindow` no longer creates individual channel controls.
- GUI smoke tests still pass.

### Phase 3: Replace modal selection dialogs with panels

Build the new workflow in this order:

1. Equipment panel.
2. Profile panel.
3. Review panel.
4. Run/monitor panel with live measurements and status.

The equipment panel should show connected instruments as cards or rows with:

- Type.
- Model/IDN.
- Connection state.
- Assigned channels.
- Available channels for multi-channel devices.

Assignment should use explicit controls such as combo boxes or drag-and-drop rows, not repeated yes/no dialogs.

The profile panel should use a step table or form editor with:

- Step type.
- Drive mode and setpoint.
- End condition.
- Safety limits.
- Measurement interval.
- Reordering and duplication.

The review panel should show:

- Required equipment.
- Missing assignments.
- Safety-limit summary.
- Output directory.
- Estimated sequence.

The Start button should be disabled until validation succeeds.

Exit criteria:

- Normal equipment assignment and profile creation require no legacy modal dialogs.
- A user can complete configuration from one main window.
- Cancellation does not leave child processes running.

### Phase 4: Extract test execution behind a service interface

Create `TestExecutionService` with a stable API:

```python
start(channel_state, test_plan)
request_stop(channel)
start_idle(channel_state)
```

The execution service calls the process entry points in `charge_discharge.process_entrypoints`, which delegate to `charge_discharge.runner`.

Extract next:

- Profile compilation into `profiles.py`.
- One-step timing and execution into `steps.py`.
- Outer cycle orchestration into `runner.py`.
- Dialog-free validation into pure services.

Exit criteria:

- The embedded simple editor delegates profile creation to the shared `ProfileIdentityService`; legacy dialog setup has been removed.
- Headless tests can run a complete simulated plan without creating Qt widgets.

### Phase 5: Make equipment communication concurrency-safe

This phase is required before claiming reliable multi-channel support.

Replace raw messages such as:

```python
{"type": "measure_voltage", "data": None}
```

with correlated requests:

```python
{
    "protocol": 2,
    "request_id": "...",
    "client_id": "channel-0-psu",
    "operation": "measure_voltage",
    "args": [],
    "instrument_channel": 2,
}
```

Return structured responses:

```python
{
    "request_id": "...",
    "ok": True,
    "value": 4.12,
    "error": None,
}
```

Safety-critical writes must be acknowledgeable. Driver exceptions must become structured errors rather than leaving callers waiting for a timeout.

The equipment manager also claims one slot per physical instrument, or one
hardware channel for a multi-channel instrument. A slot can be reused by the
same battery channel, but another battery channel is rejected until ownership
is released. Responses are delivered through private client queues and are
correlated by `request_id`.

Implemented tests cover:

- Ownership rejection for two channels targeting one instrument.
- Response routing.
- Timeout behavior.
- Unsupported operations.
- Driver exceptions.
- Private response queues and concurrent request correlation.
- Owner-process shutdown and manager cleanup.

### Phase 6: Cut over and remove legacy GUI paths

Completed in the current migration pass:

- The new window is the default `battery_test.py` entry point.
- Direct legacy profile/setup dialogs and duplicate process wrappers were removed.
- `ChannelState` is now the single per-channel runtime state source; queue
  draining is delegated through `ChannelController` and `MessageRouter`.
- Cycle-loop orchestration is isolated in `charge_discharge.cycle_executor`.

The equipment-owner protocol migration is complete; legacy uncorrelated
transport has been removed.

### Completion plan: remaining migration

This is the implementation order for the outstanding work identified in
[Verified implementation differences](#verified-implementation-differences).
It deliberately does not reopen the completed protocol-v2, stable equipment
identity, capability-filtered assignment, or simulated owner-process work.
Every phase preserves the current single-window workflow and leaves the
application importable and runnable with simulated equipment.

#### Completion 1: Introduce a Qt-independent `BatteryApplication`

Create `battery_app/application.py` as the application-service facade. It owns
the `ChannelState` and `ChannelController` collections, `EquipmentManager`,
`ConfigurationStore`, `MessageRouter`, process lifecycle, and the polling of
worker results. It exposes typed operations such as:

```python
add_channel()
remove_channels()
apply_equipment_assignment(channel, assignment)
apply_profile(channel, profile, run_context)
start_test(channel, run_context)
stop_test(channel)
poll()
shutdown()
```

The exact return types should be small Qt-independent result/event dataclasses
(for example, a channel update, a user-visible warning, or an equipment-list
change), rather than Qt signals or raw queue payloads. `poll()` updates only
application state and returns those events; it must not mutate widgets.

`MainTestWindow` becomes a view/composition root: create and select widgets,
connect intent signals to `BatteryApplication`, render returned events, own the
Qt timer, and show file dialogs or exceptional confirmations. It must not
directly create or drain multiprocessing queues, claim equipment ownership,
start or stop workers, or use label text as application state.

Worker failures follow the same application-event boundary: the worker sends a
serializable `{"type": "error", "data": {...}}` message, the application
sets `ChannelStatus.ERROR`, and the window renders the error in the channel and
bounded status log. A non-zero worker exit without that message is surfaced by
the application as the same error event. `ERROR` is not a safety acknowledgement
state: it prevents automatic idle measurement but a corrected configuration can
be started explicitly; `SAFETY_FAULT` remains the state that must be cleared by
the operator.

Keep runtime channel queues and process handles in `ChannelState`, and keep
private correlated response queues inside `EquipmentManager`; these are real
execution resources, not the compatibility queues being removed. Move
resource-scan and equipment-probe worker functions to a Qt-independent service
at the same time, so their result queues are application-owned.

Deliverables:

- `BatteryApplication` with constructor injection seams for process/equipment
  services in unit tests.
- A small application-event/read-model contract consumed by the GUI.
- Headless tests for channel add/remove, assignment, profile application,
  worker-message routing, start/stop, idle restart, and shutdown.

Exit criteria:

- `battery_app` imports no Qt modules.
- A headless test can drive the ordinary simulated start/stop lifecycle through
  `BatteryApplication`.
- `MainTestWindow` delegates all non-Qt state changes to the facade.

#### Completion 2: Remove compatibility handoffs and parallel widget state

**Implementation status: complete.** The window now calls the application
directly for assignment and cell-name changes, applies imported assignments
synchronously after channel creation, renders measurement events through each
`ChannelWidget`, and no longer owns compatibility queues or parallel per-channel
control dictionaries. Full regression validation remains part of Completion 5
and is intentionally deferred.

The cutover replaced the window-owned
`eq_assignment_queue`, `test_configuration_queue`, and
`edit_cell_name_queue` handoffs with direct typed application calls. Resource
scan and equipment-probe workers remain owned by `BatteryApplication`.

The window keeps one `ChannelWidget` per visible channel and no longer keeps
parallel dictionaries of its labels and buttons. Measurement, status, and safety
events render through the widget methods. Channel safety and worker state are
read from `ChannelState`; preflight-based Start enablement belongs to Completion
3.

Deliverables:

- A thin `MainTestWindow.update_loop()` that calls `application.poll()` and
  renders returned events.
- No direct `multiprocessing.Process`, `Queue`, or `queue.Empty` use in
  `battery_test.py`.
- Tests that reset channel count, import assignments, and close the window
  without stale widget references or live workers.

Exit criteria:

- `MainTestWindow` contains only Qt composition, signal wiring, presentation,
  and file-dialog/confirmation handling.
- No parallel per-channel widget dictionaries or GUI compatibility queues
  remain.

#### Completion 3: Add a pure readiness service and embedded review panel

Create a pure `battery_app` readiness/preflight service. Given a channel state,
validated profile, run context, connected-equipment snapshot, and ownership
availability, it returns a structured `RunReadiness` result containing:

- blocking errors and non-blocking warnings;
- required and assigned equipment roles, including physical channel selection;
- profile identity/version, step and cycle summary, and safety limits;
- cell name, output directory, and institution code; and
- an estimated sequence summary when it can be calculated without guessing.

The readiness check must be side-effect free. The actual assignment/start path
must repeat the necessary validation and claim ownership atomically, because a
preview cannot reserve an instrument against another channel. A failed
revalidation must leave the channel idle and release any partial ownership
claims.

Add `battery_gui/review_panel.py` (or an equivalently focused embedded widget)
to render `RunReadiness`. Refresh it whenever the profile, run context,
equipment assignment, connection state, or safety state changes. Disable Start
while there are blocking errors, but retain the application-level revalidation
at click time as the safety boundary.

Deliverables:

- Pure readiness tests for missing roles, incompatible capabilities,
  disconnected/ambiguous equipment, invalid profile/run context, safety fault,
  and simulated-cell fake-equipment requirements.
- `pytest-qt` coverage that verifies the panel contents and Start enablement
  change when configuration becomes valid or invalid.
- A cancellation/failed-claim test proving that no child process or ownership
  claim is left behind.

Exit criteria:

- Normal configuration, review, and start happen in the active-channel
  workspace with no modal setup flow.
- The enabled Start button means the most recent preflight passed; execution
  still rechecks just before it starts.

#### Completion 4: Add advanced profile authoring on the portable contract

**Status: deferred for later.** The portable JSON and CLI workflow are available
for advanced profiles; the visual multi-step editor is not part of the current
cutover work.

Retain imported profiles as immutable records. Add an explicit **Duplicate as
editable draft** action for an imported profile; it creates a new
`profile_id`, leaving the imported record unchanged. Edits to a profile created
through the Profile Identity Service retain its `profile_id` and recalculate its deterministic
`profile_version` only after the draft validates. The battery-test GUI must not
revise imported profiles.

Build the advanced editor around the normalized
`settings_cycle_list_step_list` contract, not legacy cycle objects or execution
callbacks. It needs draft operations for adding, removing, duplicating, and
reordering cycles and steps, with forms for the existing drive, end-condition,
measurement-interval, and safety fields. Charge, discharge, rest, single IR,
and repeated IR procedures must compile to normal `"step"` records; do not add
new executable cycle types merely for the UI.

The simple editor may remain as a quick authoring mode if it feeds the same
draft model. Before Apply or Export, all drafts pass through
`validate_profile_configuration()`. Persist only `profile_payload()` data; run
context and equipment assignments remain outside the profile file.

Deliverables:

- An advanced-profile draft model with no Qt or process dependencies.
- A step-table/form widget with explicit draft/apply/cancel behaviour.
- Tests for ordering, duplication, IR compilation, profile identity/version
  rules, validation errors, imported-profile immutability, and JSON round trips.

Exit criteria:

- Every procedure already supported by the execution engine can be authored in
  the main window or imported as a portable JSON profile.
- The execution engine continues to receive only validated normalized profiles.

#### Completion 5: Regression, release, and hardware sign-off

Run the automated suite after each completion phase and keep the simulated
system as the required gate:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The regression matrix must include pure application/readiness tests,
`pytest-qt` interaction tests, correlated equipment-owner tests, and the
headless and GUI-driven `SIMULATED_LG_MJ1` path through BDF output. Add a
regression for every compatibility handoff or widget dictionary removed in
Completion 2.

Only after the simulated matrix passes, perform opt-in manual hardware
validation: one channel first, then the intended multi-channel/shared-resource
cases. Confirm safe output-off behaviour on start failure, stop, safety fault,
ownership rejection, assignment reassignment, disconnect, and application
shutdown. Keep hardware scripts manually invoked under `hardware_tests/`; they
must not become ordinary pytest collection.

Exit criteria:

- The automated suite passes from the local virtual environment without
  physical instruments.
- Hardware validation records the instrument models/resources used and the
  observed safe-state checks.
- A packaged build is made only after the automated and applicable hardware
  gates pass.

## 6. Future plotting extension

This migration does not implement live plots. A future plotting feature may subscribe to the existing measurement stream and open a channel-specific window or panel. It should be an observer of measurements, not a dependency of test execution, safety evaluation, or logging.

## 7. Visual modernization guidance

Use a restrained Qt stylesheet rather than adding a large UI framework dependency:

- Neutral background and high-contrast text.
- One accent color for active controls.
- Green/amber/red status colors used consistently.
- Cards or grouped panels for equipment and channels.
- Clear spacing and typography hierarchy.
- Persistent status bar and event log.
- Disable controls while an operation is unsafe or unavailable.

Prioritize clarity over decoration. The most important visual improvement is that the user can see channel state, equipment assignment, profile readiness, and safety state in one place.

## 8. Rollout and rollback

Use feature boundaries rather than a long-lived divergent branch:

- `legacy-ui`: current GUI behavior.
- `service-ui`: new controllers and panels behind the existing window.
- `new-ui`: single-interface workflow enabled by default.

Keep the old entry points callable until the new GUI has passed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Rollback should be a configuration/entry-point change, not a restoration of deleted process code.

## 9. Definition of done

The migration is complete when:

- The main window is the normal interface for equipment, profile, review, and monitoring.
- Normal workflows do not use chains of modal pop-ups.
- `MainTestWindow` contains Qt composition and application wiring only.
- Test execution is usable headlessly.
- Equipment-owner processes remain the sole owners of physical PyVISA resources.
- Shared instruments have correlated, acknowledged request/response handling.
- Import/export contains only versioned serializable configuration.
- GUI, headless simulation, and hardware smoke tests are separately runnable.
