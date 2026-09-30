from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battery_app.application import BatteryApplication
from battery_app.profile_identity import ProfileIdentityService
from battery_app.state import ChannelStatus

RESOURCE = 'USB0::0xF4EC::0x1410::SPD1XEAX4R0095::0::INSTR'
IDN = 'Siglent Technologies,SPD1168X,SPD1XEAX4R0095,2.1.1.9R1,V1.0'
EQUIPMENT_ID = 'spd1168x-hardware-test-20260926'
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
RUN_ROOT = ROOT / 'hardware_tests' / 'results' / f'CELL_32AH_{RUN_ID}'
REPORT = ROOT / 'hardware_tests' / 'results' / f'CELL_32AH_{RUN_ID}_run_summary.json'

profile_definition = {
    'profile_schema_version': 2,
    'profile_name': 'CELL 32Ah low-current 30-second CC charge',
    'settings_cycle_list_step_list': [[{
        'cycle_type': 'step',
        'bdf_step_type': 'CC_CHG',
        'cycle_display': 'CC charge 1 A for 30 s',
        'drive_style': 'current_a',
        'drive_value': 1.0,
        'drive_value_other': 4.2,
        'end_style': 'time_s',
        'end_condition': 'greater',
        'end_value': 30.0,
        'meas_log_int_s': 1.0,
        'safety_min_voltage_v': 2.8,
        'safety_max_voltage_v': 4.2,
        'safety_min_current_a': -10.0,
        'safety_max_current_a': 8.0,
        'safety_max_time_s': 40.0,
    }]],
}
profile = ProfileIdentityService().create(profile_definition)
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--initialize-only', action='store_true')
    parser.add_argument(
        '--cell-voltage',
        type=float,
        help='Current externally verified open-circuit cell voltage in volts (required for charge runs).',
    )
    parser.add_argument(
        '--remote-sense',
        action='store_true',
        help='Enable four-wire remote sensing for the charge run.',
    )
    parser.add_argument(
        '--sense-leads-confirmed',
        action='store_true',
        help='Confirm remote-sense leads are secured at the cell terminals with polarity checked.',
    )
    parser.add_argument(
        '--pause-after-initialize',
        action='store_true',
        help='Pause after output-off initialization so its sound can be distinguished from shutdown.',
    )
    args = parser.parse_args()
    initialization_only = args.initialize_only
    pause_after_initialize = args.pause_after_initialize
    if not initialization_only and args.cell_voltage is None:
        parser.error('--cell-voltage is required for a charge run')
    if args.cell_voltage is not None and not 2.8 <= args.cell_voltage <= 4.2:
        parser.error('--cell-voltage must be within the agreed 2.8–4.2 V limits')
    if args.remote_sense and not args.sense_leads_confirmed:
        parser.error('--sense-leads-confirmed is required with --remote-sense')

    app = BatteryApplication()
    app.restart_idle_processes = False
    state = None
    all_events = []
    measurements = []
    started = False
    initialization_complete = False
    normal_completion = False
    run_error = None
    final_supply = None
    try:
        state = app.add_channel(0)
        descriptor = {
            'eq_type': 'psu',
            'class_name': 'SPD1000',
            'eq_idn': IDN,
            'res_id': RESOURCE,
            'setup_dict': {'remote_sense': args.remote_sense},
            'instrument_channels': [0],
            'capabilities': [],
            'equipment_id': EQUIPMENT_ID,
        }
        if pause_after_initialize:
            print('PHASE 1: Starting PSU connection and driver initialization; output remains off.', flush=True)
        if not app.connect_equipment(descriptor):
            raise RuntimeError(f'PSU connection failed: {app.equipment_manager.last_connection_error}')
        initialization_complete = True
        if pause_after_initialize:
            input('PHASE 1 COMPLETE: No test was started. Press Enter after listening to begin safe shutdown: ')
        if not initialization_only:
            equipment = app.connected_equipment[0]
            assignment = {
                'psu': {
                    'class_name': equipment['class_name'],
                    'eq_idn': equipment['eq_idn'],
                    'res_id': {'equipment_id': equipment['equipment_id'], 'eq_ch': 0},
                },
            }
            result = app.apply_equipment_assignment(0, assignment)
            if not result.ok:
                raise RuntimeError(f'Equipment assignment failed: {result.message}')
            app.apply_profile(0, profile)
            RUN_ROOT.mkdir(parents=True, exist_ok=True)
            result = app.start_test(0, {
                'cell_name': 'CELL_32AH_20260926',
                'directory': str(RUN_ROOT),
                'institution_code': 'LOCAL',
            })
            if not result.ok:
                raise RuntimeError(f'Test start refused: {result.message}')
            started = True
            deadline = time.monotonic() + 75.0
            while time.monotonic() < deadline:
                events = app.poll()
                for event in events:
                    item = {'kind': event.kind, 'message': event.message}
                    if event.kind == 'measurement' and isinstance(event.payload, dict):
                        item['measurement'] = event.payload
                        measurements.append(event.payload)
                        print(json.dumps({'event': 'measurement', 'voltage_v': event.payload.get('Voltage'), 'current_a': event.payload.get('Current'), 'step_time_s': event.payload.get('Data_Timestamp_From_Step_Start')}), flush=True)
                    elif event.payload is not None and event.kind != 'measurement':
                        item['payload'] = str(event.payload)
                    all_events.append(item)
                    if event.kind in ('safety_fault', 'error'):
                        raise RuntimeError(f'{event.kind}: {event.message}')
                    if event.kind == 'event' and event.message == 'All cycles completed':
                        normal_completion = True
                if normal_completion:
                    break
                if state.status in (ChannelStatus.SAFETY_FAULT, ChannelStatus.ERROR):
                    raise RuntimeError(f'Channel ended in {state.status.value}')
                time.sleep(0.05)
            if not normal_completion:
                raise TimeoutError('Runner did not report normal completion within 75 seconds')
    except Exception as error:
        run_error = f'{type(error).__name__}: {error}'
    finally:
        if pause_after_initialize:
            print('PHASE 2: Starting application/driver shutdown; output remains off.', flush=True)
        app.shutdown()
        if pause_after_initialize:
            input('PHASE 2 COMPLETE: Press Enter to run final read-only safety verification: ')
    
    # Query the supply only after the application has closed the owner process.
    try:
        if pause_after_initialize:
            print('PHASE 3: Starting final supply safety verification.', flush=True)
        import pyvisa
        rm = pyvisa.ResourceManager('@ivi')
        inst = rm.open_resource(RESOURCE)
        inst.read_termination = '\n'
        inst.write_termination = '\n'
        inst.query_delay = 0.15
        try:
            status = int(inst.query('SYST:STAT?'), 16)
            if status & (1 << 4):
                inst.write('OUTP CH1,OFF')
                status = int(inst.query('SYST:STAT?'), 16)
                if status & (1 << 4):
                    raise RuntimeError(
                        'PSU output did not turn off; refusing to reset setpoints'
                    )
            # The driver shutdown disables output and clears current, but keeps
            # the voltage compliance value. Return both controls to zero only
            # after confirming the output is off.
            inst.write('CURR 0')
            inst.write('VOLT 0')
            status = int(inst.query('SYST:STAT?'), 16)
            final_supply = {
                'idn': inst.query('*IDN?').strip(),
                'output': bool(status & (1 << 4)),
                'remote_sense': bool(status & (1 << 5)),
                'voltage_setpoint_v': float(inst.query('VOLT?')),
                'current_setpoint_a': float(inst.query('CURR?')),
                'error': inst.query('SYST:ERR?').strip(),
            }
        finally:
            inst.close()
            rm.close()
    except Exception as error:
        final_supply = {'query_error': f'{type(error).__name__}: {error}'}
    
    csv_files = sorted(RUN_ROOT.rglob('*.bdf.csv'))
    csv_rows = []
    for path in csv_files:
        with path.open(newline='', encoding='utf-8') as stream:
            csv_rows.extend(list(csv.DictReader(stream)))
    supply_is_safe = bool(
        final_supply
        and final_supply.get('output') is False
        and final_supply.get('voltage_setpoint_v') == 0.0
        and final_supply.get('current_setpoint_a') == 0.0
    )
    if initialization_only and initialization_complete and not run_error and supply_is_safe:
        outcome = 'initialization_only'
    elif normal_completion and not run_error and supply_is_safe:
        outcome = 'completed'
    else:
        outcome = 'incomplete_or_faulted'
    report = {
        'mode': 'initialize_only' if initialization_only else 'charge_test',
        'run_date': datetime.now(timezone.utc).date().isoformat(),
        'cell_name': 'CELL_32AH_20260926',
        'reported_open_circuit_voltage_v': args.cell_voltage,
        'profile': profile_definition['settings_cycle_list_step_list'][0][0],
        'profile_id': profile['profile_id'],
        'profile_version': profile['profile_version'],
        'remote_sense': args.remote_sense,
        'started': started,
        'events': all_events,
        'measurements': measurements,
        'sample_count': len(csv_rows),
        'first_sample': csv_rows[0] if csv_rows else None,
        'last_sample': csv_rows[-1] if csv_rows else None,
        'data_files': [str(path) for path in csv_files],
        'final_status': state.status.value if state is not None else None,
        'safety_fault': bool(state.safety_fault) if state is not None else None,
        'final_supply': final_supply,
        'post_run_setpoints_reset': bool(
            final_supply
            and final_supply.get('output') is False
            and final_supply.get('voltage_setpoint_v') == 0.0
            and final_supply.get('current_setpoint_a') == 0.0
        ),
        'run_error': run_error,
        'outcome': outcome,
    }
    REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'outcome': report['outcome'], 'run_error': run_error, 'event_count': len(all_events), 'measurement_events': len(measurements), 'csv_sample_count': len(csv_rows), 'data_files': report['data_files'], 'final_supply': final_supply, 'report': str(REPORT)}, indent=2), flush=True)
    if report['outcome'] == 'incomplete_or_faulted':
        raise SystemExit(1)
    
if __name__ == '__main__':
    main()

