#python library for controlling an Arduino's analog and digital pins

import pyvisa
from time import sleep
import easygui as eg
import keyboard
from functools import partial

#Data Acquisition Unit
class Arduino_IO:
	#initialize
	def __init__(self, resource_id = ""):
		self.num_channels = 13
		
		rm = pyvisa.ResourceManager('@py')
		
		if(resource_id == ""):
			resources = list(rm.list_resources()) #RM returns a tuple so cast to a list to append
		
			########### EASYGUI VERSION #############
			#choicebox needs 2 resources, so if we only have 1 device then add another.
			title = "DAQ Selection"
			if(len(resources) == 0):
				resource_id = 0
			elif(len(resources) == 1):
				msg = "There is only 1 visa resource available.\nWould you like to use it?\n{}".format(resources[0])
				if(eg.ynbox(msg, title)):
					resource_id = resources[0]
				else:
					resource_id = 0
			else:
				msg = "Select a visa resource for the DAQ:"
				resource_id = eg.choicebox(msg, title, resources)
		
		self.inst = rm.open_resource(resource_id)
		
		sleep(2) #wait for arduino reset
		
		self.inst.baud_rate = 57600
		self.inst.read_termination = '\r\n'
		self.inst.write_termination = '\n'
		self.inst.query_delay = 0.02
		self.inst.chunk_size = 102400
		
		print('Connected to:\n{name}'.format(name = self.inst.query('*IDN?')))
	
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
			sleep(s_per_step) #not fully accurate, but works for now
	
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
	
	#Controlling some PWM pins
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
	
	#Controlling some servos with arrow keys
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
		sleep(0.5)
			