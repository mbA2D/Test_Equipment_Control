#python pyvisa commands for controlling A2D Eload

import pyvisa
import time
from .PyVisaDeviceTemplate import EloadDevice

# E-Load
class A2D_Eload(EloadDevice):
    max_channels = 32 #max 32 eloads connected on the RS485 bus
    has_remote_sense = False
    connection_settings = {
        'read_termination':         '\r\n',
        'write_termination':        '\n',
        'baud_rate':                115200,
        'query_delay':              0.005,
        'command_delay':            0.005, #wait between commands sent to instrument
        'time_wait_after_open':     0,
        'chunk_size':               102400,
        'pyvisa_backend':           '@py',
        'idn_available':            True
    }
    
    # Initialize the A2D ELoad
    def initialize(self):
        idn_split = self.inst_idn.split(',')
        self.manufacturer = idn_split[0]
        self.model_number = idn_split[1]
        self.serial_number = idn_split[2]
        self.firmware_version = idn_split[3]

        if 'Eload' in self.model_number:
            self.max_current = 10.0
        self.current_setpoint = 0.0

        self._last_command_time = time.perf_counter()

        self.reset()
        self.set_current(0)
    
    def reset(self):
        self._inst_write("*RST")
        self.current_setpoint = 0.0
        time.sleep(2.0)

    def kick(self, channel = 1):
        self._inst_write(f"INSTR:KICK {channel}")

    # To Set E-Load in Amps 
    def set_current(self, current_setpoint_A, channel = 1):		 
        if current_setpoint_A < 0:
            current_setpoint_A = abs(current_setpoint_A)
        self._inst_write(f"CURR {channel},{current_setpoint_A}")
        self.current_setpoint = current_setpoint_A

    def toggle_output(self, state, channel = 1):
        if state:
            self._inst_write(f"INSTR:RELAY {channel},1")
            #This device sets the current to 0 before turning the relay ON to avoid a current spike and maintain relay health
            #So we need to set the current again after turning the relay ON.
            self.set_current(self.current_setpoint) 
        else:
            self._inst_write(f"INSTR:RELAY {channel},0")
            self.current_setpoint = 0.0
    
    def get_output(self, channel = 1):
        return bool(int(self._inst_query(f"INSTR:RELAY {channel}?")))

    def measure_voltage_supply(self, channel = 1):
        return float(self._inst_query(f"MEAS:VOLT {channel}?"))
    
    def measure_voltage_adc_supply(self, channel = 1):
        return float(self._inst_query(f"MEAS:VOLT:ADC {channel}?"))

    def measure_current(self, channel = 1):
        return (float(self._inst_query(f"CURR {channel}?")) * (-1)) #just returns the target current

    def measure_current_control(self, channel = 1):
        return (float(self._inst_query(f"CURR:CTRL {channel}?")) * (-1)) #returns the applied control signal for the current (use for calibration)

    def measure_temperature(self, channel = 1):
        return (float(self._inst_query(f"MEAS:TEMP {channel}?")))

    def set_led(self, state, channel = 1):
        if state:
            self._inst_write(f"INSTR:LED {channel},1")
        else:
            self._inst_write(f"INSTR:LED {channel},0")

    def get_led(self, channel = 1):
        return bool(int(self._inst_query(f"INSTR:LED {channel},?")))

    def set_fan(self, state, channel = 1):
        if state:
            self._inst_write(f"INSTR:FAN {channel},1")
        else:
            self._inst_write(f"INSTR:FAN {channel},0")

    def get_fan(self, channel = 1):
        return bool(int(self._inst_query(f"INSTR:FAN {channel},?")))
    
    def cal_v_reset(self, channel = 1):
        self._inst_write(f"CAL:V:RST {channel}")

    def cal_v_save(self, channel = 1):
        self._inst_write(f"CAL:V:SAV {channel}")

    def cal_i_reset(self, channel = 1):
        self._inst_write(f"CAL:I:RST {channel}")

    def cal_i_save(self, channel = 1):
        self._inst_write(f"CAL:I:SAV {channel}")

    def get_cal_v(self, channel = 1): #returns [offset,gain]
        return [float(val) for val in self._inst_query_ascii(f'CAL:V {channel}?')]
    
    def get_cal_i(self, channel = 1): #returns [offset,gain]
        return [float(val) for val in self._inst_query_ascii(f'CAL:I {channel}?')]

    def calibrate_voltage(self, v1a, v1m, v2a, v2m, channel = 1): #2 points, actual (a - dmm) and measured (m - dut)
        self._inst_write(f'CAL:V {channel},{v1a},{v1m},{v2a},{v2m}')

    def calibrate_current(self, i1a, i1m, i2a, i2m, channel = 1): #2 points, actual (a - dmm) and measured (m - dut)
        self._inst_write(f'CAL:I {channel},{i1a},{i1m},{i2a},{i2m}')

    def get_rs485_addr(self):
        return int(self._inst_query("INSTR:RS485?"))
    
    def set_rs485_addr(self, address):
        self._inst_write(f"INSTR:RS485 {address}")

    def save_rs485_addr(self):
        self._inst_write("INSTR:RS485:SAV")

    def _inst_write(self, string_to_write):
        while (time.perf_counter() - self._last_command_time) < self.connection_settings['command_delay']:
            time.sleep(self.connection_settings['command_delay'] / 10.0)
        self.inst.write(string_to_write)
        self._last_command_time = time.perf_counter()

    def _inst_query(self, string_to_write):
        while (time.perf_counter() - self._last_command_time) < self.connection_settings['command_delay']:
            time.sleep(self.connection_settings['command_delay'] / 10.0)
        response = self.inst.query(string_to_write)
        self._last_command_time = time.perf_counter()
        return response
    
    def _inst_query_ascii(self, string_to_write):
        while (time.perf_counter() - self._last_command_time) < self.connection_settings['command_delay']:
            time.sleep(self.connection_settings['command_delay'] / 10.0)
        response = self.inst.query_ascii_values(string_to_write)
        self._last_command_time = time.perf_counter()
        return response

    def __del__(self):
        try:
            self.toggle_output(False)
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
