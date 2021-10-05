import tkinter as tk
import easygui as eg
import pandas as pd
import os
from datetime import datetime

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