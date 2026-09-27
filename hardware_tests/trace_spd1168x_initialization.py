"""Interactively trace the SPD1168X output-off initialization commands."""

from __future__ import annotations

import time

import pyvisa


RESOURCE = 'USB0::0xF4EC::0x1410::SPD1XEAX4R0095::0::INSTR'
EXPECTED_IDN = 'Siglent Technologies,SPD1168X,SPD1XEAX4R0095,2.1.1.9R1,V1.0'


def main() -> int:
    rm = pyvisa.ResourceManager('@ivi')
    inst = rm.open_resource(RESOURCE)
    inst.read_termination = '\n'
    inst.write_termination = '\n'
    inst.query_delay = 0.025
    inst.timeout = 3000

    steps = [
        ('select channel 1', [('write', 'INST CH1'), ('query', 'SYST:ERR?')]),
        ('query selected channel', [('query', 'INST?'), ('query', 'SYST:ERR?')]),
        ('unlock commands', [('write', '*UNLOCK'), ('query', 'SYST:ERR?')]),
        ('turn output off and read status', [
            ('write', 'OUTP CH1,OFF'), ('query', 'SYST:STAT?'), ('query', 'SYST:ERR?'),
        ]),
        ('disable timer', [('write', 'TIMER CH1,OFF'), ('query', 'SYST:ERR?')]),
        ('disable waveform', [('write', 'OUTP:WAVE OFF'), ('query', 'SYST:ERR?')]),
        ('set and read current setpoint zero', [
            ('write', 'CURR 0'), ('query', 'SYST:ERR?'),
            ('query', 'CURR?'), ('query', 'SYST:ERR?'),
        ]),
        ('set and read voltage setpoint zero', [
            ('write', 'VOLT 0'), ('query', 'SYST:ERR?'),
            ('query', 'VOLT?'), ('query', 'SYST:ERR?'),
        ]),
        ('set local sense and read status', [
            ('write', 'MODE:SET 2W'), ('query', 'SYST:STAT?'), ('query', 'SYST:ERR?'),
        ]),
        ('verify initialization state', [('query', 'SYST:STAT?'), ('query', 'SYST:ERR?')]),
        ('repeat local-sense setup applied by equipment manager', [
            ('write', 'MODE:SET 2W'), ('query', 'SYST:STAT?'), ('query', 'SYST:ERR?'),
        ]),
    ]

    try:
        idn = inst.query('*IDN?').strip()
        print(f'Connected instrument: {idn}', flush=True)
        if idn != EXPECTED_IDN:
            raise RuntimeError(f'Unexpected instrument identity: {idn}')
        status = int(inst.query('SYST:STAT?'), 16)
        if status & (1 << 4):
            inst.write('OUTP CH1,OFF')
            status = int(inst.query('SYST:STAT?'), 16)
            if status & (1 << 4):
                raise RuntimeError('PSU output is on and would not turn off; stopping trace')
        print('Preflight passed: output is off. No step in this trace enables it.', flush=True)

        for index, (label, commands) in enumerate(steps, start=1):
            print(f'PHASE {index}/{len(steps)}: {label}', flush=True)
            for operation, command in commands:
                response = inst.write(command) if operation == 'write' else inst.query(command).strip()
                if command != 'SYST:ERR?':
                    print(f'    {operation.upper()} {command} -> {response}', flush=True)
                else:
                    print(f'    QUERY {command} -> {response}', flush=True)
                    if int(response.split(',', 1)[0]):
                        raise RuntimeError(f'Instrument error during phase {index}: {response}')
            time.sleep(0.1)
            input('    Listen for a beep during this phase, then press Enter to continue: ')

        final_status = int(inst.query('SYST:STAT?'), 16)
        voltage = float(inst.query('VOLT?'))
        current = float(inst.query('CURR?'))
        error = inst.query('SYST:ERR?').strip()
        print({
            'output': bool(final_status & (1 << 4)),
            'remote_sense': bool(final_status & (1 << 5)),
            'voltage_setpoint_v': voltage,
            'current_setpoint_a': current,
            'error': error,
        }, flush=True)
        if final_status & (1 << 4) or voltage != 0.0 or current != 0.0 or not error.startswith('+0,'):
            raise RuntimeError('Final PSU safety state did not match output-off / zero-setpoint expectation')
        return 0
    finally:
        inst.close()
        rm.close()


if __name__ == '__main__':
    raise SystemExit(main())
