# Battery Profile JSON Contract

Status: version 2

This file defines the portable profile format for advanced battery-test
programs. It is independent of Qt widgets, equipment assignments, and the
execution process.

## File envelope

The persisted file uses the existing configuration envelope:

```json
{
  "schema_version": 3,
  "test_configuration": {
    "profile_schema_version": 2,
    "profile_id": "profile-example-001",
    "profile_version": "sha256:...",
    "profile_name": "Charge-rest-discharge",
    "settings_cycle_list_step_list": [
      [
        {
          "cycle_type": "step",
          "bdf_step_type": "CC_CHG",
          "cycle_display": "Charge",
          "drive_style": "voltage_v",
          "drive_value": 4.2,
          "drive_value_other": 1.0,
          "end_style": "current_a",
          "end_condition": "lesser",
          "end_value": 0.1,
          "meas_log_int_s": 1,
          "safety_min_voltage_v": 2.45,
          "safety_max_voltage_v": 4.25,
          "safety_min_current_a": -10,
          "safety_max_current_a": 10,
          "safety_max_time_s": 3600
        }
      ]
    ]
  }
}
```

`schema_version` identifies the persistence envelope and must currently be
`3`. A profile file must contain only `schema_version` and
`test_configuration` at its top level. The nested required
`profile_schema_version` identifies this profile contract and must currently be
`2`.
Version 1 profiles are unsupported; the application does not migrate them.

## Identity and revision rules

- `profile_id` is required. It is generated once when a profile is created and
  remains unchanged for that profile.
- `profile_version` is required. It is generated when the profile is created or
  when the user changes its settings.
- Only the Profile Identity Service assigns `profile_id` and calculates
  `profile_version`. The battery-test GUI validates, displays, and executes an
  authored profile; it does not revise an imported profile.
- The version is a deterministic hash of the profile definition. The importer
  verifies the supplied version and rejects stale or fabricated values; it does
  not generate a replacement version.
- Changing cell selection, output location, institution code, equipment, or
  execution state does not create a new profile version.
- Profiles without explicit IDs or versions are rejected. There is no legacy
  profile identity fallback.
- Every cycle, including repeated identical cycles, is part of the profile
  definition. Adding, removing, duplicating, or reordering a cycle changes the
  profile version.

### Components

- **Profile Definition:** the portable authored JSON data: all cycles and
  steps, plus `profile_id` and `profile_version`.
- **Profile Identity Service:** creates a new `profile_id` and calculates a
  profile version, or preserves an existing ID while calculating a revision.
- **Profile Validator:** checks the definition without changing its identity
  and derives `eq_req_dict` for in-memory execution.
- **Profile Revision CLI:** the trained-user command-line interface to the
  Identity Service and Validator. It provides `create` and `revise` commands.
- **Simple Profile Editor:** the embedded one-step editor; it authors a basic
  definition through the Identity Service.
- **Profile Designer:** a future advanced visual editor for multi-cycle,
  multi-step, and IR plans. It will also use the Identity Service.
- **Battery Test GUI:** imports, displays, and executes an authored profile;
  it never revises profile identity.

### Profile workflows

**New creation:** The Simple Profile Editor creates a one-step definition and
passes it to the Profile Identity Service. The service assigns a new
`profile_id` and first `profile_version`; the Profile Validator validates it
and derives equipment requirements. A future Profile Designer will follow the
same sequence for advanced plans. A trained user can create a new advanced
profile from a hand-authored draft with the Profile Revision CLI.

**Manual revision:** A trained user edits the JSON definition, preserving its
`profile_id`, then uses the Profile Revision CLI. It calculates the new
`profile_version`, validates the revised definition, and writes a separate
profile file by default.

**Loading:** The Battery Test GUI loads the profile and calls the Profile
Validator. A mismatched version, unsupported structure, or GUI-owned run data
causes import to fail. A valid imported profile is displayed read-only and its
identity is left unchanged.

**Execution:** Immediately before starting a worker, the Battery Test GUI
combines the validated profile with run context: cell name, the application-wide
test-data directory, institution code, and derived equipment requirements. This
temporary Execution Configuration is never written back to the profile file.

### Manual JSON edits

The format is open for trained users to author or edit directly. After editing
an existing profile, preserve its `profile_id` and run the Profile Revision CLI
to calculate a matching version and validate the result:

```powershell
.\.venv\Scripts\python.exe -m battery_app.profile_identity create .\advanced-draft.json --output .\advanced-profile.json
.\.venv\Scripts\python.exe -m battery_app.profile_identity revise .\profile.json
```

`create` takes a complete draft without `profile_id` or `profile_version`;
`revise` preserves its existing `profile_id`. By default either command writes
`<input>.revised.json` beside the input file. Use `--output <path>` for another
destination, or the explicit `--in-place` option only after reviewing the edit.
The main battery-test GUI does not revise an imported profile.

## Profile definition

`profile_name` is a required non-empty name for people. It is part of the
profile definition and therefore changes `profile_version` when edited.

`settings_cycle_list_step_list` is an ordered list of cycles. Each cycle is an
ordered list of executable steps. A step must contain:

- `cycle_type`: exactly `"step"`.
- `bdf_step_type`: one of `"CC_CHG"`, `"CC_DCH"`, `"REST"`, or `"IR"`.
- `cycle_display`: non-empty display text.
- `drive_style`: `"current_a"`, `"voltage_v"`, or `"none"`.
- `drive_value` and `drive_value_other`: numeric drive setpoints.
- `end_style`: `"time_s"`, `"current_a"`, or `"voltage_v"`.
- `end_condition`: `"greater"` or `"lesser"`.
- `end_value`: numeric end threshold.
- `meas_log_int_s`: positive measurement interval in seconds.
- Voltage and current safety minimums and maximums.
- `safety_max_time_s`: finite numeric safety timeout; zero or a negative value
  disables that timeout according to the existing engine convention.

`bdf_step_type` is the authoritative BDF classification. It is stored in the
profile and copied to the BDF CSV and JSON-LD metadata; it is never inferred
from `cycle_display`. `cycle_display` is presentation text only.

The optional step fields are `cycle_end_voltage_v` and
`cycle_end_time_s`. Advanced profiles express multi-step, repeated, and IR
procedures by composing these normalized steps. They must not contain Python,
callbacks, Qt objects, queue handles, or equipment instances.

No additional top-level profile fields or step fields are allowed. This keeps
the JSON contract explicit; a future contract revision must introduce new
fields through a new `profile_schema_version`.

## Derived and run-owned data

`eq_req_dict` is not part of the authored file. The validator derives it from
the steps and attaches it to the in-memory execution configuration.

The following are GUI-owned run context and are deliberately excluded from the
profile file:

- `cell_name`.
- `directory`.
- `institution_code`.
- Equipment assignments and physical resource identifiers.
- Queues, process handles, measurements, and current execution state.

An imported profile containing `cell_name`, `directory`, or
`institution_code` is rejected rather than silently accepting run context as
profile data.

The GUI combines the validated profile with the selected cell and the one
application-wide test-data directory immediately before execution. Reusing one
profile for another cell therefore does not require editing or revising the
profile.

## Validation boundary

`battery_app.profile_validation.validate_profile_configuration()` is the single
profile validation boundary. It validates the structure and safety-related
fields, verifies identity, and derives equipment requirements. The execution
runner receives an already validated profile plus run context and does not
rewrite profile identity.
