# Test_Equipment_Control
Controlling Various Lab Test Equipment
 - Battery Testing (Capacity, Internal Resistance, SoC-OCV, SoC-IR) 
 - DC-DC Converter Testing (Efficiency across input voltage and output loads)
 
For an overview of what this program can do, check out this post: https://a2delectronics.ca/2023/05/04/battery-test-with-standard-lab-equipment/

## Setup
### Prerequisites:
 - Tested with Python 3.14.7. Download it from https://www.python.org/downloads/release/python-3147/
   - The project pins Python with `.python-version`; Python 3.14 is the only supported runtime.
   - On this workstation, the Python launcher may not find 3.14.7. If `py -3.14 --version` fails, use:
     ```powershell
     & "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" --version
     ```
 - Keysight Instrument Control Bundle (https://www.keysight.com/ca/en/lib/software-detail/computer-software/keysight-instrument-control-bundle-download-1184883.html). IO Libraries Suite and Command Expert are required (.NET 3.5 may be required for Command Expert).
 - NI VISA (https://www.ni.com/en-ca/support/downloads/drivers/download.ni-visa.html)
 - libusb, if USB instruments use the PyVISA-py backend.

### Python environment:
From `Test_Equipment_Control`:
```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[hardware,analysis,dev]"
python -m pip freeze > requirements.lock.txt
```

If the launcher cannot find Python 3.14, use the installed executable directly:
```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -m venv .venv
.venv\Scripts\Activate.ps1
```

### VISA backends:
Verify the available VISA backends with:
```powershell
python -m visa info
```
The application probes `@py` and `@ivi` independently. `@ivi` is optional:
an unavailable backend is logged and skipped, while resources from the other
backend remain available. With this migration, expect PyVISA 1.16.2 and
PyVISA-py 0.8.1.

## Running Tests
### Testing Batteries:
Run `\.venv\Scripts\python.exe battery_test.py` from the project root.
1. File->Scan resources
    - This checks the available `@py` and `@ivi` VISA backends. A missing backend does not prevent the other backend from being scanned.
2. File->Connect to equipment
    - Use the embedded equipment panel to choose the type, model, and resource. Fake equipment supports full owner-process and proxy-path simulation in both headless tests and the GUI workflow.
    - If you connect equipment with multiple channels (e.g. A2D 64CH DAQ), then here you connect only to the board.
3. Assign Equipment to channel
    - Equipment that you have previously connected to will be available to assign to the channel.
    - For equipment with multiple channels (e.g. A2D 64CH DAQ), then here you must select the channel of the equipment to assign to the test channel as well.
    - An 'idle_test' will be started that will measure voltage and current using the connected equipment.
    - Ensure voltage shown matches the battery voltage expected (if one is connected).
4. Configure Test
    - Choose and configure the type of Test you want to do.
    - A Test is made up of 1 or more Cycles.
    - A Cycle is made up of 1 or more Steps.
    - A Step contains: 
       1. Configuration Info. For sources and sinks (power supplies and electronic loads).
       2. Step End Conditions. If the step end condition is met, then the next step starts.
       3. Cycle End Limits. If these settings are exceeded, the Cycle ends immediately and the next Cycle starts. 
       4. Safety Limits. If these settings are exceeded, the Test ends immediately.
    - All Cycle types chosen in the GUI are converted to Steps before they are run.
5. Start Test  
    - The 'idle_test' that was running will be stopped and the configured test will start.
    - The test can be manually stopped at any time with the 'Stop Test' button.
    - If any of the safety settings are exceeded, then the test will stop automatically.
   - Application events and failures are written to the shared rotating
     `logs/application.log`; measurement data remains in CSV files.

The setups and tests can be exported and imported (.json format) for easy reconfiguration when restarting the software.  

### Running a battery test without the GUI

The headless CLI supports test execution, equipment setup, channel management,
and idle monitoring. See the [Headless CLI guide](HEADLESS_CLI.md) for
requirements, commands, safety confirmations, and examples.

See the results with ```GraphIV.py```. Graphs and stats (capacity_ah, capacity_wh, max temperature, etc.) for each cycle can be generated.  

### Battery data format and future storage

Battery cycling output uses the open-source [Battery Data Format (BDF)](https://github.com/battery-data-alliance/battery-data-format)
with one `.bdf.csv` file per cycle and a paired `.bdf.meta.jsonld` metadata
sidecar. CSV headers are fixed for every cycle. The required BDF measurements
are `Test Time / s`, `Voltage / V`, and `Current / A`; the output also records
Unix time, cycle count, global step count, cycle-local `Step ID`, step time,
step type, directional cycle capacity and energy, and fixed surface-temperature
slots.

The filename sequence (`XXX`) is also the persistent cycle number and is used
for `Cycle Count / 1`. It continues across dates and separate GUI starts for
the same institution/cell. `Step Count / 1` continues from the highest value
already recorded for that cell, while `Step ID` is the cycle-local program
step identifier and may restart at 1 in each cycle file.
Capacity and energy counters reset at each cycle boundary and charging and
discharging values are stored as separate non-negative quantities.

Metadata is written as JSON-LD using `batterydf`'s metadata helpers, with a
versioned `testEquipmentControl` project section containing the institution,
cell, test type, steps, equipment roles, and temperature-source placement.
The official `batterydf` validator is used where applicable, supplemented by
project validation for the fixed headers and sequencing rules. Metadata fields
should follow the finalized BDF metadata guidance when that specification is
published; the project section is deliberately versioned so it can be migrated
without changing measurement CSVs.

#### BDF identity and continuation

The complete identifier and continuation model is documented in the
[architecture plan](ARCHITECTURE.md#28-bdf-identity-and-continuation-model).
Operationally, the filename sequence provides the persistent cycle number;
profile, test, and session identity belong in metadata and the per-cell
manifest.

GraphIV reads the BDF column names directly and uses the metadata sidecar for
cell name and test type. Incremental-capacity analysis is temporarily disabled
and is tracked as a future reimplementation without `DiffCapAnalyzer`.

Parquet support is planned for later (`.bdf.parquet`) to reduce storage and
speed up analysis for long-running tests. It will require paired metadata,
schema validation, and GraphIV read support while retaining BDF CSV as the
simple, portable capture and debugging format.

### Testing DC-DC Converters:  
Run ```dc_dc_test.py``` from command line  
- Allows setting up a test with psu on input, eload on output.  
- Sweeps a range of output currents and a range of input voltages.  

An efficiency graph can be generated from the data with ```DC_DC_Graph.py```   

### Testing solar panels by sweeping an e-load in CV mode:  
Run ```Eload_cv_sweep.py``` from command line  
See results (solar panel IV curve with MPP marked) with `Eload_cv_sweep_graph.py`.

### Measuring a bunch of thermistors with A2D 64CH DAQ:
Using ```battery_test.py``` connect to the A2D 64CH DAQ, and a Fake DMM.
The config file for the A2D 64CH DAQ should be set up following the 'A2D_DAQ_Config_All_Thermistor_NXRT15XV.csv' format, using Steinhart-Hart coefficienct specific to your thermistor.
Assign the Fake DMM as a separate voltage measurement equipment, and the A2D 64CH DAQ channels you want to measure as additional DMMs to measure temperature for the channel.
Configure a test for the channel, using a single rest step for the amount of time you want to log the thermistors for. Make sure to change the safety_time_s as well. Setting safety_time_s to 0 will disable the time safety check.
Start the test, and a log will be created with a fake voltage measurement as well as all the temperature channels.

### Quick measurements with a DMM:
Run ```Measurement_Script.py``` from command line.  
Choose to measure voltage, current, or temperature, the number of measurements to take, and the delay before starting the measurements.  
Measurements will be printed out in the console.  


## TODO List
This backlog is grouped by area. Owner-startup acknowledgement is now
implemented; rediscovery when a saved resource address changes remains deferred.

### Equipment connection and control

- **HIGH PRIORITY:** Define capability-specific driver protocols for setting and verifying setpoints, operating mode, and output state. Initial hardware-test models (B&K 8601 and Siglent SPD1168X) have rated-limit checks, setpoint readback, output-state checks, and owner-side status/error checks. Still standardize these driver operations as advertised capabilities, extend coverage to the remaining hardware models, and verify assignment/profile requirements against those capabilities.
- Investigate slow `*IDN?` queries during equipment connection.
- Confirm output commands and verify the instrument entered the requested voltage/current mode.
- Query equipment output state so redundant disable commands and waits can be reduced safely.
- Remove the temporary virtual/fake instrument setup workaround in `equipment.py`.
- Show connected equipment and allow per-instrument settings such as remote sense to be changed without reconnecting everything.
- Allow one capable device to fill multiple roles where its driver and assignment model support it.
- Add explicit measurement synchronization for instruments that support it (low priority).

### Battery test workflow and profiles

- Add a remove-channel control.
- Show which safety limit was reached in the channel UI.
- Add an operator action to advance to the next cycle or step.
- Add electronic-load range switching between cycles.
- Add constant-voltage mode to battery-test e-load profiles.
- Allow current profiles to repeat until a safety limit is reached.
- Load current-step profiles from CSV.
- Build an HPPC profile authoring workflow. (The advanced visual profile editor is separately deferred.)
- Allow different measurement rates for different equipment, such as slower temperature sampling.

### Simulation and automated testing

- Add an accelerated full-cycle mode for `SIMULATED_LG_MJ1`. Make the BDF sampling interval and simulation clock scale independently configurable so full charge/discharge cycles can finish quickly without producing excessive rows. Verify that accelerated runs reach the expected SoC limits, preserve directional capacity totals and valid BDF timestamps, and do not change hardware-run timing.

### Safety and environmental control

- Add safety limits for auxiliary measurements, including cell monitors and temperature sensors.
- Add ambient-temperature setpoint control through an externally controlled heater.

### Shared equipment and relay scheduling

- Define relay-board routing so supplies and loads can be shared across cells.
- Schedule channel cycles that need shared equipment.
- After relay switching, verify that each channel remains connected to its intended equipment.

### GraphIV and data analysis

- Improve single-IR statistics when a step has enough samples, including outlier handling and capacity effects.
- Batch-process multiple cell folders and distinguish measurement logs from unrelated CSV files.
- Distinguish CC and CV phases when reporting representative current.
- Extrapolate settled voltage back to the start of a step.
- Reimplement incremental-capacity analysis without `DiffCapAnalyzer`.

### Hardware tests and utilities

- Add coverage for additional A2D e-load channels and reset handling.
- Complete the outstanding measurement in `voltage_to_temp.py`.

### Optional data integration

- Explore `battfeed` as an optional BDF CSV/metadata output sink while retaining the existing measurement and equipment-control loop.

## TODO List Graveyard
 - DONE - Consolidated the battery GUI's lifecycle and worker polling behind the Qt-independent BatteryApplication facade; removed the window's assignment/profile/cell-name queues and parallel per-channel control dictionaries.
 - DONE - Organized charge/discharge execution into focused `charge_discharge` package modules.
 - DONE - Added embedded equipment selectors with capability-filtered dropdowns. Advanced multi-step profile authoring remains deferred; use portable JSON for now.
 - DONE - Added the `SIMULATED_LG_MJ1` battery-equivalent simulation through fake equipment owner processes and the normal GUI workflow.
 - SUPERSEDED - Replacing cycle lists with cycle dictionaries. Portable profiles now use ordered cycles containing normalized step records; keep ordering and identity explicit in the profile contract.
 - DONE - Allow adding another cycle types to test configuration GUI - e.g. Rest then Single IR Test
 - DONE - Make sure to take a '0 current' reading at the start of every test to determine a rough starting SoC from SoC-OCV map. Useful for post-processing data.
 - DONE - Do not allow starting a test when a safety error exists.
 - DONE - Create an 'add channel' button
 - DONE - Repeated IR Discharge Test: Fix charge safety time, add rest after discharge
 - DONE - Flush queues after and before idle control cycle
	- Will cause issues with multiple channels accessing the same queues?
 - DONE - Show fake equipment even when no resources are available
 - DONE - Common equipment selection template - instead of a for loop and if statements in each device file
 - DONE - Make all instruments 'virtual' - e.g. controlled globally and not by the individual battery test channel processes. This opens the door to scheduled use of equipment, sharing between channels, and using all channels of multi channel devices.
 - DONE - cell logs go in a folder with the cell name
 - DONE - Separate safety conditions for each channel from end cycle conditions
 - DONE - Add safety conditions to all types of cycles (just make them all use step at the core)
 - DONE - Add a way to show a 'charge' or 'discharge' or 'ir test' instead of just showing 'step'
 - DONE - Change log file name to show which cycle_display name instead of just date, time, and cell name, overall cycle type
 - DONE - Add WARNING on the GUI if a safety setting was hit
 - DONE - Add internal resistance test through the step profiles
 - DONE - Add capability to test SoC vs Internal Resistance
 - DONE - Add parallel eloads ability to draw more power
 - DONE - Add ability to control and interact with the A2D DAQ
 - DONE - create auto-recognizing equipment profiles
      - DONE - choose instruments based on IDN? response instead of visa resource name.
      - DONE - Save equipment connections to a json file
 - DONE - change charge and discharge to have the psu or eload passed in to the function
 - DONE - add multiple end conditions (time, current, voltage) to each step
 - DONE - charge/discharge profiles from a file
 - DONE - Add ability to choose different voltage measurement equipment (e.g. DMM instead of eload or PSU for voltage).
 - DONE - Add ability to choose different current measurement equipment
 - DONE - use multiple processes to have multiple tests running at the same time
 - DONE - Add support for a current profile - or a number of steps
 - DONE - Add 'safety limits' for voltage, time, current
 - DONE - Ensure Step functions use minimal equipment - e.g. only power supply when charging or only eload when discharging.
