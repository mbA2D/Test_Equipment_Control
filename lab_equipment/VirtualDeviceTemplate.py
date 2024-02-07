#This class acts as an intermediary between the physical instrument and the channel configuration
#objects of this class are creates in equipment.py connect_to_virtual_eq, from charge_discharge_control.py get_equipment_dict
'''
When a test channel wants to query or control an instrument, it uses this class instead of the instrument directly
This allows the instruments to be controlled at a high level and the virtual devices passed to the channels for control
So multiple channels could interact with the same device (pending timing of messages)
'''

#Messages are sent to the instrument with _queue_in
#messages are a dictionary with the following fields:
'''
{
'type': string, the name of the function in the device file (DMM_DM3000.py) that you want to call
'data': serializeable argument list for the function
}
'''

#Responses come back from the instrument via _queue_out, if the function returns something
'''
The instrument puts the return value from the function onto the queue, and this class reads it.
This class converts the instrument's response to the correct format (float, bool, etc), and will send it to the channel
'''
    
class VirtualDeviceTemplate:
    def __init__(self, queue_in, queue_out, eq_ch = None):
        self._queue_in = queue_in
        self._queue_out = queue_out
        self._eq_ch = eq_ch
    
    ################ MEASURE FUNCTIONS #######################
    def measure_voltage(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        query_dict = {'type': 'measure_voltage', 'data': msg_data}
        #print(f"Sending query: {query_dict}")
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
    
    def measure_voltage_supply(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        query_dict = {'type': 'measure_voltage_supply', 'data': msg_data}
        #print(f"Sending query: {query_dict}")
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
        
    def measure_voltage_at_adc(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        query_dict = {'type': 'measure_voltage', 'data': msg_data}
        #print(f"Sending query: {query_dict}")
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
    
    def measure_voltage_at_adc_supply(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        query_dict = {'type': 'measure_voltage_at_adc_supply', 'data': msg_data}
        #print(f"Sending query: {query_dict}")
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
        
    def measure_current(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        query_dict = {'type': 'measure_current', 'data': msg_data}
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
    
    def measure_current_control(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        query_dict = {'type': 'measure_current_control', 'data': msg_data}
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
        
    def measure_power(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        query_dict = {'type': 'measure_power', 'data': msg_data}
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
    
    def measure_temperature(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        query_dict = {'type': 'measure_temperature', 'data': msg_data}
        self._queue_in.put_nowait(query_dict)
        return float(self._queue_out.get(timeout = 10))
    
    ################ SET FUNCTIONS ##############################
    def set_current(self, current_setpoint_A):
        write_dict = {'type': 'set_current', 'data': current_setpoint_A}
        self._queue_in.put_nowait(write_dict)
    
    def set_voltage(self, voltage_setpoint_V):
        write_dict = {'type': 'set_voltage', 'data': voltage_setpoint_V}
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
    
    def select_channel(self, channel):
        write_dict = {'type': 'select_channel', 'data': channel}
        self._queue_in.put_nowait(write_dict)
        
    def reset(self):
        write_dict = {'type': 'reset', 'data': None}
        self._queue_in.put_nowait(write_dict)
    
    #calibration
    def reset_calibration(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        write_dict = {'type': 'reset_calibration', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)

    #calibration
    def cal_v_reset(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        write_dict = {'type': 'cal_v_reset', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)

    #calibration
    def cal_i_reset(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        write_dict = {'type': 'cal_i_reset', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)
        
    #calibration
    def save_calibration(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        write_dict = {'type': 'save_calibration', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)

    #calibration
    def cal_v_save(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        write_dict = {'type': 'cal_v_save', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)

    #calibration
    def cal_i_save(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        write_dict = {'type': 'cal_i_save', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)
        
    #calibration
    def get_calibration(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        write_dict = {'type': 'get_calibration', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)
        return [float(val) for val in self._queue_out.get(timeout = 10)]
    
    #calibration
    def get_cal_v(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        write_dict = {'type': 'get_cal_v', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)
        return [float(val) for val in self._queue_out.get(timeout = 10)]
    
    #calibration
    def get_cal_i(self):
        msg_data = None
        if self._eq_ch is not None:
            msg_data = self._eq_ch
        write_dict = {'type': 'get_cal_i', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)
        return [float(val) for val in self._queue_out.get(timeout = 10)]
    
    #calibration
    def calibrate_voltage(self, v1a, v1m, v2a, v2m):
        msg_data = [v1a, v1m, v2a, v2m]
        if self._eq_ch is not None:
            msg_data.append(self._eq_ch)
        write_dict = {'type': 'calibrate_voltage', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)

    #calibration
    def calibrate_current(self, i1a, i1m, i2a, i2m):
        msg_data = [i1a, i1m, i2a, i2m]
        if self._eq_ch is not None:
            msg_data.append(self._eq_ch)
        write_dict = {'type': 'calibrate_current', 'data': msg_data}
        self._queue_in.put_nowait(write_dict)
    
    #relay board
    def connect_psu(self, state):
        write_dict = {'type': 'connect_psu', 'data': state}
        self._queue_in.put_nowait(write_dict)
        
    #relay board
    def connect_eload(self, state):
        write_dict = {'type': 'connect_eload', 'data': state}
        self._queue_in.put_nowait(write_dict)
    
    #relay board
    def psu_connected(self):
        write_dict = {'type': 'psu_connected', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return bool(self._queue_out.get(timeout = 10))
    
    #relay board
    def eload_connected(self):
        write_dict = {'type': 'eload_connected', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return bool(self._queue_out.get(timeout = 10))
    
    def get_output(self):
        write_dict = {'type': 'get_output', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return bool(self._queue_out.get(timeout = 10))

    def set_led(self, value):
        write_dict = {'type': 'set_led', 'data': value}
        self._queue_in.put_nowait(write_dict)

    def get_led(self):
        write_dict = {'type': 'get_led', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return bool(self._queue_out.get(timeout = 10))
    
    def set_fan(self, value):
        write_dict = {'type': 'set_fan', 'data': value}
        self._queue_in.put_nowait(write_dict)

    def get_fan(self):
        write_dict = {'type': 'get_fan', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return bool(self._queue_out.get(timeout = 10))
        
    def get_num_channels(self):
        write_dict = {'type': 'get_num_channels', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return int(self._queue_out.get(timeout = 10))
    
    ############## RS485
    def get_rs485_addr(self):
        write_dict = {'type': 'get_rs485_addr', 'data': None}
        self._queue_in.put_nowait(write_dict)
        return int(self._queue_out.get(timeout = 10))
    
    def set_rs485_addr(self, addr):
        write_dict = {'type': 'set_rs485_addr', 'data': addr}
        self._queue_in.put_nowait(write_dict)

    def save_rs485_addr(self):
        write_dict = {'type': 'save_rs485_addr', 'data': None}
        self._queue_in.put_nowait(write_dict)

    ############## FOR RELAY BOARD and SENSE BOARD
    def set_i2c_expander_addr(self, addr):
        write_dict = {'type': 'set_i2c_expander_addr', 'data': addr}
        self._queue_in.put_nowait(write_dict)
        
    def set_i2c_adc_addr(self, addr):
        write_dict = {'type': 'set_i2c_adc_addr', 'data': addr}
        self._queue_in.put_nowait(write_dict)
        
    def set_i2c_dac_addr(self, addr):
        write_dict = {'type': 'set_i2c_dac_addr', 'data': addr}
        self._queue_in.put_nowait(write_dict)
