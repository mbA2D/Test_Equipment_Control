
import equipment as eq
import time
import easygui as eg
import os
import Templates
import numpy as np
import tkinter as tk
from datetime import datetime
import pandas as pd


#sweep the load current of an E-load from X to Y A in increments and log to CSV

eloads = eq.eLoads()
eload = eloads.choose_eload()

psus = eq.powerSupplies()
psu = psus.choose_psu()

def init_instruments(psu_output_voltage, psu_output_current):
	eload.remote_sense(False)
	psu.remote_sense(False)
	psu.set_voltage(psu_output_voltage)
	psu.set_current(psu_output_current)

####################### FILE IO ###########################


def get_directory(type):
	root = tk.Tk()
	root.withdraw()
	dir = tk.filedialog.askdirectory(
		title='Select location to save {} data files'.format(type))
	root.destroy()
	return dir

def write_line(filepath, list_line):
	#read into pandas dataframe - works, in quick to code
	#and is likely easy to extend - but one line doesn't really need it
	df = pd.DataFrame(list_line).T
	
	#save to csv - append, no index, no header
	df.to_csv(filepath, header=False, mode='a', index=False)

def start_file(directory, name):
	dt = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
	filename = '{test_name} {date}.csv'.format(\
				test_name = name, date = dt)
	
	filepath = os.path.join(directory, filename)
	
	#Headers
	#create a list
	headers = list()
	headers.append('Timestamp')
	headers.append('i_out')
	headers.append('v_out')
	headers.append('i_in')
	headers.append('v_in')
	
	write_line(filepath, headers)
	
	return filepath

def write_data(filepath, data_to_log, printout=False):
	data = list()
	
	#add timestamp
	data.append(time.time())
	data.extend(data_to_log)
	
	if(printout):
		print(data)
	
	write_line(filepath, data)

####################################################################

def gather_data():
	data = list()
	data.append(eload.measure_current())
	data.append(eload.measure_voltage())
	data.append(psu.measure_current())
	data.append(psu.measure_voltage())
	return data

def sweep_load_current(dir, test_name, min_a, max_a, step_size_a, delay_s):
	num_steps = int((max_a - min_a) / step_size_a) + 1
	
	filepath = start_file(dir, test_name)
	
	for current in np.linspace(min_a, max_a, num_steps):
		eload.set_current(current)
		time.sleep(delay_s)
		data = gather_data()
		write_data(filepath, data)
		
if __name__ == '__main__':
	directory = get_directory("DC-DC-Test")
	test_name = eg.enterbox(title = "Test Setup", msg = "Enter the Test Name\n(Spaces will be replaced with underscores)",
							default = "TEST_NAME", strip = True)
	test_name = test_name.replace(" ", "_")
	
	msg = "Enter PSU Voltage"
	title = "PSU Setup"
	default = "1.0"
	psu_voltage = float(eg.enterbox(msg,title,default))
	msg = "Enter PSU Current"
	psu_current = float(eg.enterbox(msg,title,default))
	
	msg = "Enter Min Load Current"
	title = "Load Setup"
	default = "1.0"
	eload_min_a = float(eg.enterbox(msg,title,default))
	msg = "Enter Max Load Current"
	eload_max_a = float(eg.enterbox(msg,title,default))
	msg = "Enter Load Current Step Size"
	eload_step = float(eg.enterbox(msg,title,default))
	msg = "Enter Delay between Load Steps"
	eload_step_delay = float(eg.enterbox(msg,title,default))

	init_instruments(psu_voltage, psu_current)
	
	psu.toggle_output(1)
	eload.toggle_output(1)
	
	sweep_load_current(directory, test_name, min_a = eload_min_a, max_a = eload_max_a, step_size_a = eload_step, delay_s = eload_step_delay)
