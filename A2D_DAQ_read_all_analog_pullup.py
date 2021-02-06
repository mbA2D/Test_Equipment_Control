#python script for reading analog values from A2D DAQ

import A2D_DAQ_control as AD_control
import tkinter as tk
from tkinter import filedialog
import pandas as pd
from datetime import datetime
import os
import time
import easygui

def get_directory():
	root = tk.Tk()
	root.withdraw()
	dir = tk.filedialog.askdirectory(
		title='Select location to save DAQ data file')
	root.destroy()
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
	
	write_line(filepath, headers)
	
	return filepath

def init_all_channels():
	dir = 1
	value = 1
	for ch in range(daq.num_channels):
		daq.conf_io(ch, dir)
		daq.set_dig(ch, value)

def gather_and_write_data(filepath, time, printout=False):
	data = list()
	
	#add timestamp
	data.append(time)
	
	#read all analog values
	for ch in range(daq.num_channels):
		data.append(daq.get_analog_mv(ch))
	
	if(printout):
		print(data)
	
	write_line(filepath, data)


######################### Program ########################

#declare and initialize the daq
daq = AD_control.A2D_DAQ()
init_all_channels()

#Gather the test settings
lb = 1
ub = 60
msg = 'Enter logging interval in seconds (from {} to {}):'.format(lb, ub)
title = 'Logging Interval'
interval_temp = integerbox(msg, title, default = 0, lowerbound = lb, upperbound = ub)

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
