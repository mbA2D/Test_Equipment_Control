#python library for controlling the A2D DAQ

import pyvisa
import easygui as eg
import voltage_to_temp as V2T
from . import A2D_DAQ_config
from .PyVisaDeviceTemplate import PyVisaDevice

#Data Acquisition Unit
class A2D_DAQ(PyVisaDevice):
    num_channels = 64
    connection_settings = {
        'read_termination':         '\r\n',
        'write_termination':        '\n',
        'baud_rate':                57600,
        'query_delay':              0.02,
        'chunk_size':               102400,
        'pyvisa_backend':           '@py',
        'time_wait_after_open':     2,
        'idn_available':            True
    }
    
    #initialization specific to this instrument
    def initialize(self):
        self.pull_up_r = 3300
        self.pullup_voltage = 3.3
        self.pull_up_cal_ch = 63
        self.config_dict = {}
        
    def __del__(self):
        try:
            self.inst.close()
        except AttributeError:
            pass
    
    def configure_from_dict(self):
        #Go through each channel and set it up according to the dict
        for ch in list(self.config_dict.keys()):
            if self.config_dict[ch]['Input_Type'] == 'voltage':
                self.conf_io(ch, 0) #input
            elif self.config_dict[ch]['Input_Type'] == 'temperature':
                self.conf_io(ch, 1) #output
                self.set_dig(ch, 1) #pull high
            elif self.config_dict[ch]['Input_Type'] == 'dig_in':
                self.conf_io(ch, 0) #input
            elif self.config_dict[ch]['Input_Type'] == 'dig_out':
                self.conf_io(ch, 1) #output
                self.set_dig(ch, 0) #pull low
                
                
    def reset(self):
        self.inst.write('*RST')
        
    def conf_io(self, channel = 0, dir = 1):
        #1 means output - pin is being driven
        if dir:
            self.inst.write('CONF:DAQ:OUTP (@{ch})'.format(ch = channel))
        #0 means input - pin high impedance
        elif not dir:
            self.inst.write('CONF:DAQ:INP (@{ch})'.format(ch = channel))
    
    def get_pullup_v(self):
        return self.pullup_voltage
    
    def calibrate_pullup_v(self, cal_ch = None):
        if cal_ch == None:
            cal_ch = self.pull_up_cal_ch
    
        #choose a channel to read from - this channel should have nothing on it
        if cal_ch < self.num_channels:
            #ensure channel is set to output and pullued high
            self.conf_io(channel = cal_ch, dir = 1)
            self.set_dig(channel = cal_ch, value = 1)
            
            self.pullup_voltage = float(self.measure_voltage(channel = cal_ch))
    
    def get_analog_mv(self, channel = 0):
        scaling = 1
        
        #print(f"Measuring channel {channel}")
        
        if self.config_dict[channel]['Input_Type'] == 'voltage':
            scaling = self.config_dict[channel]['Voltage_Scaling']
        
        raw_value = self.inst.query('INSTR:READ:ANA? (@{ch})'.format(ch = channel))
        #print(f"Query raw value: {raw_value}")
        return_value = float(raw_value)*scaling
        #print(f"Query return value: {return_value}")
        return return_value
    
    def get_analog_v(self, channel = 0):
        return float(self.get_analog_mv(channel))/1000.0
    
    def measure_voltage(self, channel = 0):
        return float(self.get_analog_v(channel))
    
    def measure_temperature(self, channel = 0):
        sh_consts = {'SH_A': self.config_dict[channel]['Temp_A'],
                     'SH_B': self.config_dict[channel]['Temp_B'],
                     'SH_C': self.config_dict[channel]['Temp_C']}
        return V2T.voltage_to_C(self.measure_voltage(channel), self.pull_up_r, self.pullup_voltage, sh_constants = sh_consts)
    
    def get_dig_in(self, channel = 0):
        return self.inst.query('INSTR:READ:DIG? (@{ch})'.format(ch = channel))
        
    def set_dig(self, channel = 0, value = 0):
        if(value > 1):
            value = 1
        self.inst.write('INSTR:DAQ:SET:OUTP (@{ch}),{val}'.format(ch = channel, val = value))
        
    def set_led(self, value = 0):
        if(value > 1):
            value = 1
        #x is a character that we parse but do nothing with (channel must be first)
        self.inst.write('INSTR:DAQ:SET:LED x {val}'.format(val = value))
        
    def set_read_delay_ms(self, delay_ms):
        #x is a character that we parse but do nothing with (channel must be first)
        self.inst.write('CONF:DAQ:READDEL x {val}'.format(val = delay_ms))
    
    def __del__(self):
        try:
            self.inst.close()
        except (AttributeError, pyvisa.errors.InvalidSession):
            pass
