#python pyvisa commands to emulate a combination of eloads as a single eload

import pyvisa
import time
import easygui as eg
import equipment as eq

# E-Load
class PARALLEL:
	# Initialize the Parallel E-Load
	def __init__(self, resource_id = ""):
		
		#combine 2 or more eloads in parallel and split the current between them
		#need to create a 'virtual eload' here that emulates the other eload classes.
		
		eloads = eq.eLoads(include_parallel = False) #class to select the eloads
		
		eload1 = eloads.choose_eload()
		eload2 = eloads.choose_eload()
		
		eload1_current_share = 0.5
		eload2_current_share = 0.5
		
		
	# To Set E-Load in Amps 
	def set_current(self, current_setpoint_A):		
		eload1.set_current(current_setpoint_A * eload1_current_share)
		eload2.set_current(current_setpoint_A * eload2_current_share)

	def toggle_output(self, state):
		eload1.toggle_output(state)
		eload2.toggle_output(state)
	
	def remote_sense(self, state):
		eload1.remote_sense(state)
		eload2.remote_sense(state)
	
	def lock_front_panel(self, state):
		eload1.lock_front_panel(state)
		eload2.lock_front_panel(state)
	
	def measure_voltage(self):
		#use only the voltage measurement from the first eload
		return eload1.measure_voltage()

	def measure_current(self):
		return (eload1.measure_current() + eload2.measure_current())
		
	#def __del__(self):
	#	pass
