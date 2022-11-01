#Eload CV Sweep graphing results - geared for solar panel testing

import pandas as pd
import matplotlib.pyplot as plt
import FileIO
import os

def calc_power(df):
	df['current_pos'] = -1 * df['current']
	df['power'] = df['voltage'] * df['current_pos']

def plot_power(df, test_name, save_filepath = ''):
	if df.size == 0:
		return
	
	fig, ax = plt.subplots()
	fig.set_size_inches(12,10)
	ax2 = ax.twinx()

	ax.plot('i_out_pos', 'voltage', data = df, label = "Voltage (V)")
	ax.plot('i_out_pos', 'power', data = df, label = "Power (W)")
	
	title = "{} Power".format(test_name)
	
	fig.suptitle(title)
	ax.set_ylabel('Voltage (V)')
	ax2.set_ylabel('Power (W)')
	ax.set_xlabel('Current (A)')
	
	ax.grid(b=True, axis='both')
	
	#Add a point at the MPP
	mpp_p = max(df['power'])
	mpp_i = 
	mpp_v = 
	
	
	#save the file if specified
	if(save_filepath != ''):
		plt.savefig(os.path.splitext(save_filepath)[0])
	
	plt.show()
	

def create_graphs(filepaths = None, save_dir = None):
	if filepaths == None:
		#get all the files to graph
		filepaths = FileIO.get_multiple_filepaths()
	
	if save_dir == None:
		save_dir = FileIO.get_directory(title = "Choose a location to save the graphs")
		
	for filepath in filepaths:
		dir_name, filename = os.path.split(filepath)
		
		split_path = filename.split(" ")
		test_name = split_path[0]
		graph_filename = os.path.join(save_dir, "{}_Graph".format(test_name))
		
		#get the input voltage for this test
		df = pd.read_csv(filepath)
		
		calc_power(df)
		plot_power(df, test_name, graph_filename)

################ PROGRAM ###################

if __name__ == '__main__':
	create_graphs()
	