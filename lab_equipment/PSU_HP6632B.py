"""Driver for the HP/Agilent/Keysight 6632B DC source."""

import pyvisa

from .PyVisaDeviceTemplate import PowerSupplyDevice


class HP6632B(PowerSupplyDevice):
    """Positive-voltage, bidirectional-current source/load with metering."""

    has_remote_sense = False
    can_measure_v_while_off = True
    has_output_relay = True  # Option 760 is required by this driver.
    max_voltage_V = 20.0
    max_current_A = 5.0
    capabilities = frozenset({
        "can_source_voltage",
        "can_source_current",
        "can_sink_current",
        "can_measure_voltage",
        "can_measure_current",
    })

    connection_settings = {
        "pyvisa_backend": "@ivi",
        "time_wait_after_open": 0,
        "idn_available": True,
    }

    def initialize(self):
        idn_split = self.inst_idn.strip().split(",")
        self.manufacturer = idn_split[0]
        self.model = idn_split[1] if len(idn_split) > 1 else "6632B"
        self.zero_number = idn_split[2] if len(idn_split) > 2 else ""
        self.version_number = idn_split[3] if len(idn_split) > 3 else ""

        self.inst.write("*RST")
        # Option 760 has an independent relay. Force normal polarity before
        # any connection to a cell is enabled.
        self._force_normal_relay_polarity()
        self.set_voltage(0)
        self.set_current(0)
        self.toggle_output(False)

    def set_voltage(self, voltage_setpoint_V):
        voltage = float(voltage_setpoint_V)
        if voltage < 0:
            raise ValueError("HP6632B voltage must not be negative")
        if voltage > self.max_voltage_V:
            raise ValueError("HP6632B voltage exceeds 20 V")
        self.inst.write("VOLT {}".format(voltage))

    def set_current(self, current_setpoint_A):
        """Set positive source/sink current magnitude."""
        current = float(current_setpoint_A)
        if current < 0:
            raise ValueError("HP6632B current setpoint must not be negative")
        if current > self.max_current_A:
            raise ValueError("HP6632B current exceeds 5 A")
        self.inst.write("CURR {}".format(current))

    def set_mode_current(self):
        """Compatibility method: the 6632B sinks current while in CV mode."""

    def set_mode_voltage(self):
        """Compatibility method for the e-load interface."""

    def set_cv_voltage(self, voltage_setpoint_V):
        self.set_voltage(voltage_setpoint_V)

    def toggle_output(self, state):
        """Enable/disable the output and Option-760 relay together."""
        self._force_normal_relay_polarity()
        self.inst.write("OUTP {}".format("ON" if bool(state) else "OFF"))

    def output_relay(self, state):
        """Safely control the relay without permitting polarity reversal."""
        self._force_normal_relay_polarity()
        if state and not self.get_output():
            raise RuntimeError("Cannot close HP6632B relay while output is off")
        self.inst.write("OUTP:REL {}".format("ON" if bool(state) else "OFF"))

    def _force_normal_relay_polarity(self):
        self.inst.write("OUTP:REL:POL NORM")

    def get_output(self):
        return bool(int(float(self.inst.query("OUTP?"))))

    def lock_front_panel(self, state):
        self.inst.write("SYST:REM" if state else "SYST:LOC")

    def measure_voltage(self):
        return float(self.inst.query("MEAS:VOLT?"))

    def measure_current(self):
        # Negative current is expected while sinking current from a cell.
        return float(self.inst.query("MEAS:CURR?"))

    def measure_power(self):
        return self.measure_voltage() * self.measure_current()

    def __del__(self):
        try:
            self.toggle_output(False)
            self.lock_front_panel(False)
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
