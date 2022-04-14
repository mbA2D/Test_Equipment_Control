#python script for reading analog values from A2D DAQ

from lab_equipment import A2D_DAQ_control as AD_control
import pandas as pd
import time
import easygui as eg
import FileIO

pull_up_v = 3.3
pull_up_r = 3300
pull_up_cal_ch = 63

def gather_and_write_data(filepath, time, print_all=False, print_max = True):
	daq.set_led(1)
	#recalibrate pullup voltage
	daq.calibrate_pullup_v(pull_up_cal_ch)
	pull_up_v = daq.pullup_voltage
	
	data = {}
	
	#add timestamp
	data["Timestamp"] = time
	
	max_temp_c = -273.15
	max_temp_c_groups = [-273.15, -273.15, -273.15, -273.15]
	
	#read all analog values
	for ch in range(daq.num_channels):
		volts = daq.measure_voltage(ch)
		
		data["Channel_{}".format(ch)] = volts*1000.0
		
		if(volts > pull_up_v):
			volts = pull_up_v
		
		temp_c = daq.measure_temperature(ch)
		
		if(ch/16 < 1):
			if(temp_c > max_temp_c_groups[0]):
				max_temp_c_groups[0] = temp_c
		elif(ch/32 < 1):
			if(temp_c > max_temp_c_groups[1]):
				max_temp_c_groups[1] = temp_c
		elif(ch/48 < 1):
			if(temp_c > max_temp_c_groups[2]):
				max_temp_c_groups[2] = temp_c
		else:
			if(temp_c > max_temp_c_groups[3]):
				max_temp_c_groups[3] = temp_c
		
		data["Channel_C_{}".format(ch)] = temp_c
	
	if(print_all):
		print(data)
	
	if(print_max):
		print('Max Temps (C)\tCH0-15: {:.1f}'.format(max_temp_c_groups[0]) + 
				'\tCH16-31: {:.1f}'.format(max_temp_c_groups[1]) + 
				'\tCH32-47: {:.1f}'.format(max_temp_c_groups[2]) +
				'\tCH48-63: {:.1f}'.format(max_temp_c_groups[3]))
	
	FileIO.write_line(filepath, data)
	
	daq.set_led(0)


######################### Program ########################
if __name__ == '__main__':
	#declare and initialize the daq
	daq = AD_control.A2D_DAQ()
	
	#Gather the test settings
	lb = 1
	ub = 60
	msg = 'Enter logging interval in seconds (from {} to {}):'.format(lb, ub)
	title = 'Logging Interval'
	interval_temp = eg.integerbox(msg, title, default = 5, lowerbound = lb, upperbound = ub)

	dir = FileIO.get_directory()
	path = FileIO.start_file(dir, 'A2D-DAQ-Results')

	#read all analog channels once every X seconds
	starttime = time.time()
	while True:
		try:
			gather_and_write_data(path, time=time.time())
			time.sleep(interval_temp - ((time.time() - starttime) % interval_temp))
		except KeyboardInterrupt:
			#make sure all outputs are off before quiting
			daq.reset()
			exit()
