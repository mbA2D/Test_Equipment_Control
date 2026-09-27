#python pyvisa commands for controlling BK8600 series eloads

import pyvisa
import time
from decimal import Decimal
from .PyVisaDeviceTemplate import EloadDevice

# E-Load
class BK8600(EloadDevice):
    
    has_remote_sense = True
    connection_settings = {
        'pyvisa_backend':       '@ivi',
        'time_wait_after_open': 0,
        'idn_available':        True
    }

    def initialize(self):
        self.split_standard_idn()
        model_number = self.model_number or ""
        self.rated_limits = None
        self.setpoint_readback_tolerances = None
        
        #resets to Constant Current Mode
        self.inst.write("*RST")
        self.toggle_output(False)
        
        if '8600' in model_number:
            self.max_current = 30
            self.max_power = 150
        elif '8601' in model_number:
            self.max_current = 60
            self.max_power = 250
            self.max_voltage = 120
            # B&K 8601/B datasheet: CC high-range resolution is 1 mA;
            # CV high-range resolution is 10 mV. *RST selects high CC range.
            self.setpoint_readback_tolerances = {
                "current": 0.001,
                "voltage": 0.01,
            }
            self.rated_limits = {
                'max_voltage_v': 120.0,
                'max_current_a': 60.0,
                'max_power_w': 250.0,
            }
        elif '8602' in model_number:
            self.max_current = 15
            self.max_power = 200
        elif '8610' in model_number:
            self.max_current = 120
            self.max_power = 750
        elif '8612' in model_number:
            self.max_current = 30
            self.max_power = 750
        elif '8614' in model_number:
            self.max_current = 240
            self.max_power = 1500
        elif '8616' in model_number:
            self.max_current = 60
            self.max_power = 1200
        elif '8620' in model_number:
            self.max_current = 480
            self.max_power = 3000
        elif '8622' in model_number:
            self.max_current = 100
            self.max_power = 2500
        elif '8624' in model_number:
            self.max_current = 600
            self.max_power = 4500
        elif '8610' in model_number:
            self.max_current = 720
            self.max_power = 6000
        
        self.mode = "CURR"
        self.set_mode_current()
        self.set_current(0)
        #set to remote mode (disable front panel)
        self.lock_front_panel(True)
        
    # To Set E-Load in Amps 
    def set_current(self, current_setpoint_A):
        if self.mode != "CURR":
            print("ERROR - E-load not in correct mode")
            return
        if current_setpoint_A < 0:
            current_setpoint_A = -current_setpoint_A
        self.inst.write("CURR:LEV {}".format(current_setpoint_A))
        self._verify_setpoint(self.get_current(), current_setpoint_A, "current")

    def get_current(self):
        return float(self.inst.query("CURR?"))
    
    def set_mode_current(self):
        self.inst.write("FUNC CURR")
        if self.get_mode() != "CURR":
            raise RuntimeError("B&K 8600 failed to enter constant-current mode")
        self.mode = "CURR"

    def get_mode(self):
        mode = self.inst.query("FUNC?").strip().upper()
        # The 8601 reports long-form SCPI mode names (CURRENT/VOLTAGE), while
        # other BK 8600 firmware revisions report the abbreviated names.
        return {
            "CURRENT": "CURR",
            "VOLTAGE": "VOLT",
            "RESISTANCE": "RES",
            "POWER": "POW",
        }.get(mode, mode)
    
    ##COMMANDS FOR CV MODE
    def set_mode_voltage(self):
        self.inst.write("FUNC VOLT")
        if self.get_mode() != "VOLT":
            raise RuntimeError("B&K 8600 failed to enter constant-voltage mode")
        self.mode = "VOLT"
        #Only 1 voltage range on this eload
    
    def set_cv_voltage(self, voltage_setpoint_V):
        if self.mode != "VOLT":
            print("ERROR - E-load not in correct mode")
            return
        self.inst.write("VOLT {}".format(voltage_setpoint_V))
        self._verify_setpoint(self.get_voltage(), voltage_setpoint_V, "voltage")

    def get_voltage(self):
        return float(self.inst.query("VOLT?"))
    
    ##END OF COMMANDS FOR CV MODE
    
    def toggle_output(self, state):
        if state:
            self.inst.write("INP ON")
        else:
            self.inst.write("INP OFF")
        # Input-state commands are overlapped on the 8600 series.  Wait for
        # the operation to finish before checking its readback.
        self.inst.write("*WAI")
        if self.get_output() is not bool(state):
            raise RuntimeError(f"B&K 8600 input did not turn {'on' if state else 'off'}")

    def get_output(self):
        return bool(int(self.inst.query("INP?")))

    def get_fault_status(self):
        """Return active protection flags from the Questionable Condition register."""
        status = int(self.inst.query("STAT:QUES:COND?"))
        fault_bits = {
            0: "voltage fault or reverse voltage",
            1: "overcurrent",
            3: "overpower",
            4: "overtemperature",
            9: "remote reverse voltage",
            11: "local reverse voltage",
            12: "overvoltage",
            13: "protection shutdown",
        }
        return [description for bit, description in fault_bits.items() if status & (1 << bit)]

    def check_status(self, expected_output=None, expected_mode=None):
        """Verify input state and raise when a protection flag is active."""
        output_enabled = self.get_output()
        if expected_output is not None and output_enabled != bool(expected_output):
            raise RuntimeError(
                f"B&K 8601 input is {'on' if output_enabled else 'off'}, but "
                f"{'on' if expected_output else 'off'} was expected"
            )
        faults = self.get_fault_status()
        if faults:
            raise RuntimeError("B&K 8601 protection status: " + ", ".join(faults))
        mode = self.get_mode()
        if mode not in {"CURR", "CURRENT", "VOLT", "VOLTAGE", "RES", "RESISTANCE", "POW", "POWER"}:
            raise RuntimeError(f"B&K 8601 reported an unknown operating mode: {mode!r}")
        if expected_mode is not None and mode not in {expected_mode, f"{expected_mode}ENT"}:
            raise RuntimeError(
                f"B&K 8601 is in {mode} mode, but {expected_mode} mode was expected"
            )
        return None

    def _verify_setpoint(self, actual, expected, quantity):
        tolerances = self.setpoint_readback_tolerances
        if tolerances is None:
            return
        tolerance = tolerances[quantity]
        if abs(Decimal(str(actual)) - Decimal(str(expected))) > Decimal(str(tolerance)):
            raise RuntimeError(
                f"B&K 8600 {quantity} setpoint readback {actual:g} does not match "
                f"requested {expected:g} within the {tolerance:g} resolution allowance"
            )
    
    def remote_sense(self, state):
        if state:
            self.inst.write("REM:SENS ON")
        else:
            self.inst.write("REM:SENS OFF")
    
    def lock_front_panel(self, state):
        if state:
            self.inst.write("SYST:REM")
        else:
            self.inst.write("SYST:LOC")
    
    def measure_voltage(self):
        return float(self.inst.query("MEAS:VOLT:DC?"))

    def measure_current(self):
        return (float(self.inst.query("MEAS:CURR:DC?")) * (-1))
        
    def __del__(self):
        try:
            self.toggle_output(False)
            self.lock_front_panel(False)
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
