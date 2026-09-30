# Headless battery-test CLI

The headless CLI uses the same application and equipment-control services as
the desktop GUI, without starting Qt. It provides one-shot test execution and
an interactive control session for equipment setup, channels, idle
measurements, and tests.

## Requirements

- The project currently requires Python 3.14 (`>=3.14,<3.15`).
- Install the project and the hardware dependencies needed by the connected
  instruments on the control computer.
- Export profile and equipment-assignment JSON files from the GUI, or prepare
  files that meet the documented schemas.

The installed `battery-cycle` command and
`python -m battery_app.headless_runner` invoke the same CLI. Global options such as
`--log-directory` go before the subcommand. Logs default to
`logs/application.log`.

## Run a profile

`run` loads one profile and equipment configuration, then runs one channel to
completion:

```bash
battery-cycle run \
  --profile /path/to/profile.json \
  --equipment /path/to/equipment.json \
  --channel 0 \
  --cell-name CELL_001 \
  --data-directory /data/battery-tests \
  --institution-code LOCAL
```

For physical equipment, include `--confirm-physical-output` only after
checking the wiring, sense leads, fresh cell voltage, and that instrument
outputs are off. The flag is not required when every assigned instrument is
built-in fake equipment.

The command writes lifecycle events as JSON Lines. Live measurements are
omitted unless `--show-measurements` is set. SIGINT and SIGTERM request a
controlled stop and worker shutdown. Exit codes are `0` for normal completion,
`1` for a configuration or worker error, `2` for a safety fault, and `130` for
a requested stop.

## Scan and probe equipment

`scan` lists available VISA resources:

```bash
battery-cycle scan
```

`probe` checks an instrument identity and emits a portable descriptor. It does
not start an equipment-owner process or configure the instrument for a test:

```bash
battery-cycle probe \
  --type psu \
  --class-name "Fake Test PSU" \
  --resource Fake
```

Valid equipment types are `psu`, `eload`, `dmm`, `relay_board`, and `other`.
Optional driver settings can be passed as a JSON object with `--setup-json`.
Physical instrument probing is read-only; connecting a physical instrument in
the control session has a separate output-off confirmation.

## Interactive control session

Use `control` to keep equipment owners and channel state alive while issuing
multiple commands. It accepts an optional exported equipment configuration:

```bash
battery-cycle control --equipment /path/to/equipment.json
```

Add `--confirm-physical-equipment` after checking physical instruments are in
a safe output-off state. To print each idle measurement event, add
`--show-measurements`.

Enter `help` in the session for the command list:

```text
scan
probe <type> <class-name> <resource-id> [setup-json]
equipment load <exported-assignment.json>
equipment list
channel list
channel add [number]
channel remove <number>
assign <channel> <role-map.json>
idle start <channel>
idle stop <channel>
test start <channel> <profile.json> <cell-name> <data-directory> [options]
test stop <channel>
safety clear <channel> --cause-corrected
status
help
quit
```

`equipment load` reconnects the exported equipment and applies its channel
assignments. `assign` takes a JSON object mapping equipment roles to connected
equipment descriptors. `test start` accepts `--institution-code CODE` and
`--confirm-physical-output`; the latter requires checking the wiring, sense
leads, fresh cell voltage, and output-off state. `safety clear` requires
`--cause-corrected` after the fault has been resolved, and refuses to clear
while a test or idle worker is active. Exiting the session stops workers and
releases equipment owners.

## Deployment status

This is the initial headless execution path, not a qualification for
unattended, multi-month physical operation. Validate the deployment with fake
equipment before connecting a cell or enabling physical outputs. A successful
CLI run does not establish hardware, recovery, or long-duration reliability.
