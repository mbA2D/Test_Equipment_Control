#python script for reading analog values from A2D DAQ

import A2D_DAQ_control as AD_control
import pandas as pd
from datetime import datetime
import os
import time
import easygui as eg
import voltage_to_temp as V2T


pull_up_v = 3.3
pull_up_r = 3300
pull_up_cal_ch = 63

def get_directory():
	dir = eg.diropenbox(
		title='Select location to save DAQ data file')
	return dir

def write_line(filepath, list_line):
	#read into pandas dataframe - works, in quick to code
	#and is likely easy to extend - but one line doesn't really need it
	df = pd.DataFrame(list_line).T
	
	#save to csv - append, no index, no header
	df.to_csv(filepath, header=False, mode='a', index=False)

def start_file(directory):
	dt = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
	filename = 'A2D-DAQ-Results {date}.csv'.format(date = dt)
	
	filepath = os.path.join(directory, filename)
	
	#Headers
	#create a list
	headers = list()
	headers.append('Timestamp')
	for ch in range(daq.num_channels):
		headers.append('Channel_{}'.format(ch))
		#adding a spot to store temps
		headers.append('Channel_C_{}'.format(ch))
	
	write_line(filepath, headers)
	
	return filepath

def init_all_channels():
	dir = 1
	value = 1
	for ch in range(daq.num_channels):
		daq.conf_io(ch, dir)
		daq.set_dig(ch, value)
	daq.calibrate_pullup_v(pull_up_cal_ch)
	pull_up_v = daq.pullup_voltage

def gather_and_write_data(filepath, time, print_all=False, print_max = True):
	daq.set_led(1)
	#recalibrate pullup voltage
	daq.calibrate_pullup_v(pull_up_cal_ch)
	pull_up_v = daq.pullup_voltage
	
	data = list()
	
	#add timestamp
	data.append(time)
	
	max_temp_c = -273.15
	max_temp_c_groups = [-273.15, -273.15, -273.15, -273.15]
	
	#read all analog values
	for ch in range(daq.num_channels):
		mv = float(daq.get_analog_mv(ch))
		data.append(mv)
		
		if(mv/1000 > pull_up_v):
			mv = pull_up_v*1000
		
		temp_c = V2T.voltage_to_C(mv/1000, pull_up_r, pull_up_v)
		
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
		
		data.append(temp_c)
	
	if(print_all):
		print(data)
	
	if(print_max):
		print('Max Temps (C)\tCH0-15: {:.1f}'.format(max_temp_c_groups[0]) + 
				'\tCH16-31: {:.1f}'.format(max_temp_c_groups[1]) + 
				'\tCH32-47: {:.1f}'.format(max_temp_c_groups[2]) +
				'\tCH48-63: {:.1f}'.format(max_temp_c_groups[3]))
	
	write_line(filepath, data)
	
	daq.set_led(0)


######################### Program ########################
if __name__ == '__main__':
	#declare and initialize the daq
	daq = AD_control.A2D_DAQ()
	init_all_channels()

	#Gather the test settings
	lb = 1
	ub = 60
	msg = 'Enter logging interval in seconds (from {} to {}):'.format(lb, ub)
	title = 'Logging Interval'
	interval_temp = eg.integerbox(msg, title, default = 5, lowerbound = lb, upperbound = ub)

	dir = get_directory()
	path = start_file(dir)

	#read all analog channels once every 5 seconds
	starttime = time.time()
	while True:
		try:
			gather_and_write_data(path, time=time.time())
			time.sleep(interval_temp - ((time.time() - starttime) % interval_temp))
		except KeyboardInterrupt:
			#make sure all outputs are off before quiting
			daq.reset()
			exit()
