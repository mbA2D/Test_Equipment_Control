"""Read-only back-to-back VISA query-delay check for a Siglent SPD1168X.

Run from the repository root with ``.venv\\Scripts\\python.exe
hardware_tests\\benchmark_spd1168x_query_delay.py``. This script aborts unless
the output is off and both setpoints are zero. It only sends SCPI queries.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pyvisa


RESOURCE = "USB0::0xF4EC::0x1410::SPD1XEAX4R0095::0::INSTR"
EXPECTED_IDN = "Siglent Technologies,SPD1168X,SPD1XEAX4R0095,2.1.1.9R1,V1.0"
QUERY_DELAYS_S = (0.15, 0.10, 0.05, 0.025, 0.01, 0.0)
QUERIES = ("*IDN?", "SYST:STAT?", "VOLT?", "CURR?")
COMMANDS_PER_DELAY = 100
REPORT_PATH = Path(__file__).resolve().parent / "results" / "SPD1168X_query_delay_20260926.json"


def open_instrument(resource_manager, query_delay_s: float):
    instrument = resource_manager.open_resource(RESOURCE)
    instrument.read_termination = "\n"
    instrument.write_termination = "\n"
    instrument.timeout = 1500
    instrument.query_delay = query_delay_s
    return instrument


def validate_response(command: str, response: str) -> None:
    if command == "*IDN?":
        if response.strip() != EXPECTED_IDN:
            raise RuntimeError(f"Unexpected IDN response: {response!r}")
    elif command == "SYST:STAT?":
        status = int(response.strip(), 16)
        if status & (1 << 4):
            raise RuntimeError("PSU output became enabled during query-only test")
        if status & (1 << 5):
            raise RuntimeError("PSU remote sense changed during query-only test")
    elif command in {"VOLT?", "CURR?"}:
        if float(response.strip()) != 0.0:
            raise RuntimeError(f"Unexpected nonzero {command} readback: {response!r}")


def snapshot(instrument) -> dict:
    idn = instrument.query("*IDN?").strip()
    status = int(instrument.query("SYST:STAT?"), 16)
    voltage_v = float(instrument.query("VOLT?"))
    current_a = float(instrument.query("CURR?"))
    return {
        "idn": idn,
        "output": bool(status & (1 << 4)),
        "remote_sense": bool(status & (1 << 5)),
        "voltage_setpoint_v": voltage_v,
        "current_setpoint_a": current_a,
    }


def main() -> int:
    resource_manager = pyvisa.ResourceManager("@ivi")
    results = []
    initial_state = None
    final_state = None
    error_queue = None
    try:
        instrument = open_instrument(resource_manager, 0.15)
        try:
            initial_state = snapshot(instrument)
            if (
                initial_state["idn"] != EXPECTED_IDN
                or initial_state["output"]
                or initial_state["voltage_setpoint_v"] != 0.0
                or initial_state["current_setpoint_a"] != 0.0
            ):
                raise RuntimeError(f"Unsafe or unexpected pre-test PSU state: {initial_state}")
            initial_error = instrument.query("SYST:ERR?").strip()
            if not initial_error.startswith("+0,"):
                raise RuntimeError(f"PSU error queue is not clear: {initial_error}")
        finally:
            instrument.close()

        for delay_s in QUERY_DELAYS_S:
            instrument = open_instrument(resource_manager, delay_s)
            latencies_ms = []
            commands_passed = 0
            failure = None
            try:
                for index in range(COMMANDS_PER_DELAY):
                    command = QUERIES[index % len(QUERIES)]
                    started_at = time.perf_counter()
                    response = instrument.query(command)
                    latencies_ms.append((time.perf_counter() - started_at) * 1000)
                    validate_response(command, response)
                    commands_passed += 1
            except Exception as error:  # Record the first failure at this delay.
                failure = f"{type(error).__name__}: {error}"
            finally:
                instrument.close()

            results.append({
                "query_delay_s": delay_s,
                "commands_attempted": len(latencies_ms) + (1 if failure else 0),
                "commands_passed": commands_passed,
                "failure": failure,
                "elapsed_s": round(sum(latencies_ms) / 1000, 4),
                "mean_response_ms": round(sum(latencies_ms) / len(latencies_ms), 3) if latencies_ms else None,
                "max_response_ms": round(max(latencies_ms), 3) if latencies_ms else None,
            })
            print(json.dumps(results[-1]), flush=True)

        instrument = open_instrument(resource_manager, 0.15)
        try:
            final_state = snapshot(instrument)
            error_queue = instrument.query("SYST:ERR?").strip()
        finally:
            instrument.close()
    finally:
        resource_manager.close()

    report = {
        "instrument": EXPECTED_IDN,
        "test_type": "read-only consecutive SCPI queries over USBTMC",
        "commands_per_delay": COMMANDS_PER_DELAY,
        "queries": list(QUERIES),
        "initial_state": initial_state,
        "results": results,
        "final_state": final_state,
        "final_error_queue": error_queue,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT_PATH), "final_state": final_state, "final_error_queue": error_queue}, indent=2))

    state_is_safe = (
        final_state is not None
        and final_state["idn"] == EXPECTED_IDN
        and final_state["output"] is False
        and final_state["remote_sense"] is False
        and final_state["voltage_setpoint_v"] == 0.0
        and final_state["current_setpoint_a"] == 0.0
        and error_queue is not None
        and error_queue.startswith("+0,")
    )
    return 0 if state_is_safe else 1


if __name__ == "__main__":
    raise SystemExit(main())
