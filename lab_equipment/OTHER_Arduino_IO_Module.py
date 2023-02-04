#python library for controlling an Arduino's analog and digital pins

import pyvisa
import time
from .PyVisaDeviceTemplate import PyVisaDevice
import keyboard
from functools import partial

#Data Acquisition Unit
class Arduino_IO(PyVisaDevice):
    connection_settings = {
        'baud_rate':                57600,
        'read_termination':         '\r\n',
        'write_termination':        '\n',
        'query_delay':              0.02,
        'chunk_size':               102400,
        'pyvisa_backend':           '@py',
        'time_wait_after_open':     2,
        'idn_available':            True
    }
    
    def initialize(self):
        self.num_channels = 13
    
    def __del__(self):
        try:
            self.inst.close()
        except AttributeError:
            pass
    
    def reset(self):
        self.inst.write('*RST')
        
    def conf_io(self, channel = 2, dir = 1):
        #1 means output - pin is being driven
        if dir:
            self.inst.write('CONF:IO:OUTP (@{ch})'.format(ch = channel))
        #0 means input - pin high impedance
        elif not dir:
            self.inst.write('CONF:IO:INP (@{ch})'.format(ch = channel))
    
    def conf_servo(self, channel):
        self.inst.write('CONF:SERVO (@{ch})'.format(ch = channel))
    
    def set_servo_us(self, channel, value):
        self.inst.write('IO:SERVO:MICRO (@{ch}),{val}'.format(ch = channel, val = value))
    
    def get_analog_mv(self, channel = 2):
        return self.inst.query('INSTR:IO:READ:ANA? (@{ch})'.format(ch = channel))
    
    def get_analog_v(self, channel = 2):
        return self.get_analog_mv/1000.0
    
    def get_dig_in(self, channel = 2):
        return self.inst.query('INSTR:IO:READ:DIG? (@{ch})'.format(ch = channel))
        
    def set_dig(self, channel = 2, value = 0):
        if(value > 1):
            value = 1
        self.inst.write('INSTR:IO:SET:DIG:OUTP (@{ch}),{val}'.format(ch = channel, val = value))
    
    def set_pwm(self, channel = 3, pwm = 0):
        if(pwm > 255): #max arduino 8-bit PWM
            pwm = 255
        self.inst.write('INSTR:IO:SET:PWM:OUTP (@{ch}),{val}'.format(ch = channel, val = pwm))
    
    def fade_pwm(self, channel = 3, pwm_start = 0, pwm_end = 255, time_s = 1):
        pwm_high = max(pwm_start, pwm_end)
        pwm_low = min(pwm_start, pwm_end)
        
        increment = 1
        if pwm_end < pwm_start:
            increment = -1
        
        num_steps = pwm_high - pwm_low + 1
        s_per_step = time_s / num_steps
        
        for pwm in range(pwm_start, pwm_end + 1*increment, increment):
            self.set_pwm(channel, pwm)
            time.sleep(s_per_step) #not fully accurate, but works for now
    
    #make a pin give a high or low pulse
    def pulse_pin(self, channel = 2, pulse_val = 1):
        self.inst.write('INSTR:IO:PULSE (@{ch}),{val}'.format(ch = channel, val = pulse_val))
    
    def set_led(self, value = 0):
        if(value > 1):
            value = 1
        #x is a character that we parse but do nothing with (channel must be first)
        self.inst.write('INSTR:IO:SET:LED x {val}'.format(val = value))
    
    
        
if __name__ == "__main__":
    #connect to the io module
    io = Arduino_IO()
    
    ###################### Controlling some PWM pins
    '''
    # setup testing for 6 pwm signals
    out_pins = [2,3,5,6,9,10,11]
    en_pin = 2
    pwm_pins = [3,5,6,9,10,10]
    
    for pin in out_pins:
        io.conf_io(pin, 1)
    
    #enable
    io.set_dig(en_pin, 1)
    
    #fade PWMs in and out
    for pin in pwm_pins:
        io.fade_pwm(pin, 0, 255, 0.5)
        io.fade_pwm(pin, 255, 0, 0.5)
    
    #disable
    io.set_dig(en_pin, 0)
    '''
    
    ##################### Controlling some servos with arrow keys
    # WASD control for moving a 2 wheel robot around with tank steering.
    io.conf_servo(9)
    io.conf_servo(10)
    
    up_pressed = False
    down_pressed = False
    left_pressed = False
    right_pressed = False
    
    def key_pr(test, key, pr):
        #print('KEY: {}, PR: {}'.format(key, pr))
        pressed = False
        if pr == 'p':
            pressed = True
        if key == 'w':
            #print('W {}'.format(pressed))
            global up_pressed
            up_pressed = pressed
        elif key == 'a':
            global left_pressed
            left_pressed = pressed
        elif key == 's':
            global down_pressed
            down_pressed = pressed
        elif key == 'd':
            global right_pressed
            right_pressed = pressed
    
    keyboard.on_press_key('w', partial(key_pr,key = 'w',pr = 'p'))
    keyboard.on_press_key('a', partial(key_pr,key = 'a',pr = 'p'))
    keyboard.on_press_key('s', partial(key_pr,key = 's',pr = 'p'))
    keyboard.on_press_key('d', partial(key_pr,key = 'd',pr = 'p'))
    
    keyboard.on_release_key('w', partial(key_pr,key = 'w',pr = 'r'))
    keyboard.on_release_key('a', partial(key_pr,key = 'a',pr = 'r'))
    keyboard.on_release_key('s', partial(key_pr,key = 's',pr = 'r'))
    keyboard.on_release_key('d', partial(key_pr,key = 'd',pr = 'r'))
    
    io.set_servo_us(9,1500)
    io.set_servo_us(10, 1500)
    
    while True:
        if up_pressed:
            #both forward
            print('Forward')
            io.set_servo_us(9, 1800)
            io.set_servo_us(10, 1800)
        elif down_pressed:
            #both backward
            print('Backward')
            io.set_servo_us(9, 1200)
            io.set_servo_us(10, 1200)
        elif left_pressed:
            #left only forward
            print('Left')
            io.set_servo_us(9, 1800)
            io.set_servo_us(10, 1500)	
        elif right_pressed:
            #right only forward
            print('Right')
            io.set_servo_us(9, 1500)
            io.set_servo_us(10, 1800)
        else:
            print('Stop')
            io.set_servo_us(9, 1500)
            io.set_servo_us(10, 1500)
        #print('Loop {} {} {} {}'.format(up_pressed, down_pressed, left_pressed, right_pressed))
        time.sleep(0.5)
            