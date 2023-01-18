

class VirtualDeviceTemplate:
    def __init__(self, queue_in, queue_out):
        self._queue_in = queue_in
        self._queue_out = queue_out
        
    def measure_voltage(self):
        query_dict = {'type': 'measure_voltage', 'data': None}
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
        
    def measure_current(self):
        query_dict = {'type': 'measure_current', 'data': None}
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
        
    def measure_power(self):
        query_dict = {'type': 'measure_power', 'data': None}
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
    
    def measure_temperature(self):
        query_dict = {'type': 'measure_temperature', 'data': None}
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
    
    def set_current(self, current_setpoint_A):
        write_dict = {'type': 'set_current', 'data': current_setpoint_A}
        self._queue_in.put_nowait(write_dict)
    
    def set_voltage(self, voltage_setpoint_V):
        write_dict = {'type': 'set_voltage', 'data': voltage_setpoint_V}
        self._queue_in.put_nowait(write_dict)
        
    def toggle_output(self, state):
        write_dict = {'type': 'toggle_output', 'data': state}
        self._queue_in.put_nowait(write_dict)
        
    def remote_sense(self, state):
        write_dict = {'type': 'remote_sense', 'data': state}
        self._queue_in.put_nowait(write_dict)
    
    def lock_front_panel(self, state):
        write_dict = {'type': 'lock_front_panel', 'data': state}
        self._queue_in.put_nowait(write_dict)
        
    def lock_commands(self, state):
        write_dict = {'type': 'lock_commands', 'data': state}
        self._queue_in.put_nowait(write_dict)
        
    def set_mode_current(self):
        write_dict = {'type': 'set_mode_current', 'data': None}
        self._queue_in.put_nowait(write_dict)
        
    def set_mode_voltage(self):
        write_dict = {'type': 'set_mode_voltage', 'data': None}
        self._queue_in.put_nowait(write_dict)
        
    def set_cv_voltage(self, voltage_setpoint_V):
        write_dict = {'type': 'set_cv_voltage', 'data': voltage_setpoint_V}
        self._queue_in.put_nowait(write_dict)
        
    def select_channel(self, channel):
        write_dict = {'type': 'select_channel', 'data': channel}
        self._queue_in.put_nowait(write_dict)
        
    def reset(self):
        write_dict = {'type': 'reset', 'data': None}
        self._queue_in.put_nowait(write_dict)
        
    def connect_psu(self, state):
        write_dict = {'type': 'connect_psu', 'data': state}
        self._queue_in.put_nowait(write_dict)
    
    def connect_eload(self, state):
        write_dict = {'type': 'connect_eload', 'data': state}
        self._queue_in.put_nowait(write_dict)
        
    def psu_connected(self):
        write_dict = {'type': 'psu_connected', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return bool(self._queue_out.get(timeout = 10))
        
    def eload_connected(self):
        write_dict = {'type': 'eload_connected', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return bool(self._queue_out.get(timeout = 10))
        
    def set_led(self, value):
        write_dict = {'type': 'set_led', 'data': value}
        self._queue_in.put_nowait(write_dict)
        
    def get_num_channels(self):
        write_dict = {'type': 'get_num_channels', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return int(self._queue_out.get(timeout = 10))
