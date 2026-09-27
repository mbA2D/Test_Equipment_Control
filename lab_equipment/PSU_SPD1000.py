#python pyvisa commands for controlling Siglent SPD1000 series power supplies

import pyvisa
import time
import logging
from decimal import Decimal
from .PyVisaDeviceTemplate import PowerSupplyDevice
from retry import retry

logger = logging.getLogger(__name__)

class SetpointException(Exception):
    #Raised when a command is not passed to the instrument correctly.
    pass

# Power Supply
class SPD1000(PowerSupplyDevice):
    # Initialize the SPD1000 Power Supply
    has_remote_sense = True
    can_measure_v_while_off = False
    
    connection_settings = {
        'read_termination':     '\n',
        'write_termination':    '\n',
        # Siglent suggests 10-100 ms between SPD writes and reads; 25 ms passed
        # the 100-query-per-setting USB check recorded in hardware_tests/results.
        'query_delay':          0.025,
        'pyvisa_backend':       '@ivi',
        'time_wait_after_open': 0,
        'idn_available':        True
    }
    
    def initialize(self):
        self.rated_limits = None
        self.setpoint_readback_tolerances = None
        if "SPD1168X" in self.inst_idn.upper():
            # SPD1168X manual gives 1 mV voltage and 1 mA current resolution.
            self.setpoint_readback_tolerances = {
                "voltage": 0.001,
                "current": 0.001,
            }
            self.rated_limits = {
                "max_voltage_v": 16.0,
                "max_current_a": 8.0,
                "max_power_w": 128.0,
            }
        #Choose channel 1
        self.inst.write("INST CH1")
        self._check_error_queue("initialize: select CH1")
        time.sleep(0.1)
        selected_channel = self.inst.query("INST?").strip().upper()
        self._check_error_queue("initialize: query selected channel")
        if selected_channel != "CH1":
            raise RuntimeError(f"SPD1000 selected channel {selected_channel!r}; expected 'CH1'")
        self.lock_commands(False)
        time.sleep(0.1)
        self.toggle_output(False)
        time.sleep(0.1)
        self.inst.write("TIMER CH1,OFF")
        self._check_error_queue("initialize: disable timer")
        time.sleep(0.1)
        self.set_current(0)
        time.sleep(0.1)
        self.set_voltage(0)
        time.sleep(0.1)
        # Use the safe local-sense mode unless equipment setup explicitly selects 4-wire.
        self.remote_sense(False)
        time.sleep(0.1)
        self.check_status(
            expected_output=False,
            expected_remote_sense=False,
            expected_timer=False,
        )

    def _check_error_queue(self, context):
        """Check the instrument error queue and fail at the command that caused it."""
        response = self.inst.query("SYST:ERR?").strip()
        try:
            error_code = int(response.split(",", 1)[0])
        except ValueError as error:
            logger.error(
                "SPD1168X returned an invalid error response after %s: %s",
                context,
                response,
            )
            raise RuntimeError(
                f"SPD1168X returned an invalid error response after {context}: {response}"
            ) from error
        if error_code:
            logger.error("SPD1168X error after %s: %s", context, response)
            raise RuntimeError(
                f"SPD1168X reports instrument error after {context}: {response}"
            )
        logger.debug("SPD1168X error queue after %s: %s", context, response)
        
    # To Set power supply current limit in Amps 
    @retry(SetpointException, delay=0.1, tries=10)
    def set_current(self, current_setpoint_A):		
        self.inst.write("CURR {}".format(current_setpoint_A))
        self._check_error_queue(f"set current to {current_setpoint_A}")
        self._verify_setpoint(self.get_current(), current_setpoint_A, "current")
    
    def get_current(self):
        value = float(self.inst.query("CURR?"))
        self._check_error_queue("query current setpoint")
        return value
    
    @retry(SetpointException, delay=0.1, tries=10)
    def set_voltage(self, voltage_setpoint_V):
        self.inst.write("VOLT {}".format(voltage_setpoint_V))
        self._check_error_queue(f"set voltage to {voltage_setpoint_V}")
        self._verify_setpoint(self.get_voltage(), voltage_setpoint_V, "voltage")

    def _verify_setpoint(self, actual, expected, quantity):
        tolerances = self.setpoint_readback_tolerances
        if tolerances is None:
            return
        tolerance = tolerances[quantity]
        if abs(Decimal(str(actual)) - Decimal(str(expected))) > Decimal(str(tolerance)):
            raise SetpointException(
                f"SPD1168X {quantity} setpoint readback {actual:g} does not match "
                f"requested {expected:g} within the {tolerance:g} resolution allowance"
            )
    
    def get_voltage(self):
        value = float(self.inst.query("VOLT?"))
        self._check_error_queue("query voltage setpoint")
        return value

    def check_status(
        self,
        expected_output=None,
        expected_remote_sense=None,
        expected_timer=None,
        expected_waveform=None,
    ):
        """Verify the output and report the live CV/CC regulation mode."""
        status = int(self.inst.query("SYST:STAT?"), 16)
        self._check_error_queue("check instrument status")
        expected_states = (
            (expected_output, 4, "output"),
            (expected_remote_sense, 5, "remote sense"),
            (expected_timer, 6, "timer"),
            (expected_waveform, 8, "waveform display"),
        )
        for expected, bit, state_name in expected_states:
            if expected is None:
                continue
            actual = bool(status & (1 << bit))
            if actual != bool(expected):
                expected_text = "on" if expected else "off"
                actual_text = "on" if actual else "off"
                raise RuntimeError(
                    f"SPD1168X {state_name} is {actual_text}, but {expected_text} was expected"
                )

        # CV/CC is the observed regulation state, not a requested output mode.
    
    @retry(SetpointException, delay=0.1, tries=10)
    def toggle_output(self, state, ch = 1):
        if state:
            self.inst.write("OUTP CH{},ON".format(ch))
        else:
            self.inst.write("OUTP CH{},OFF".format(ch))
        actual = self.get_output()
        self._check_error_queue(f"set output {'on' if state else 'off'}")
        if actual != state:
            raise SetpointException
    
    def get_output(self):
        val = int(self.inst.query("SYST:STAT?"),16)
        return bool(val & (1<<4)) #Bit number 4 is Output
    
    @retry(SetpointException, delay=0.1, tries=10)
    def remote_sense(self, state):
        if state:
            self.inst.write("MODE:SET 4W")
        else:
            self.inst.write("MODE:SET 2W")
        actual = self.get_remote_sense()
        self._check_error_queue(f"set remote sense {'on' if state else 'off'}")
        if actual != state:
            raise SetpointException
            
    def get_remote_sense(self):
        val = int(self.inst.query("SYST:STAT?"),16)
        return bool(val & (1<<5)) #Bit number 5 is remote sense
    
    def lock_commands(self, state):
        if state:
            self.inst.write("*LOCK")
        else:
            self.inst.write("*UNLOCK")
        self._check_error_queue(f"set command lock {'on' if state else 'off'}")
    
    def measure_voltage(self):
        value = float(self.inst.query("MEAS:VOLT?"))
        self._check_error_queue("measure voltage")
        return value

    def measure_current(self):
        value = float(self.inst.query("MEAS:CURR?"))
        self._check_error_queue("measure current")
        return value
        
    def measure_power(self):
        return float(self.inst.query("MEAS:POWE?"))
        
    def __del__(self):
        try:
            self.toggle_output(False)
            self.lock_commands(False)
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
