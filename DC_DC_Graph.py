#DC-DC Test Graphing Results

import pandas as pd
import matplotlib.pyplot as plt
import FileIO
import os

def calc_eff(df):
	df['p_in'] = df['v_in'] * df['i_in']
	df['p_out'] = df['v_out'] * df['i_out'] #i_out is negative from the eloads - system (DC-DC Converter) is providing current
	df['p_loss'] = df['p_in'] + df['p_out'] #p_out is negative - system (DC-DC Converter) is losing power
	df['eff'] = abs(df['p_out'] / df['p_in'])

def plot_eff(df, test_name, save_filepath = ''):
	if df.size == 0:
		return
	
	fig, ax = plt.subplots()
	fig.set_size_inches(12,10)
	
	set_voltages = pd.unique(df['v_in_set'])
	
	num_voltages = len(set_voltages)
	cm = plt.get_cmap('Set1')
	ax.set_prop_cycle('color', [cm(1.*i/num_voltages) for i in range(num_voltages)])

	for voltage in set_voltages:
		df_mask = df[df['v_in_set'] == voltage]
		ax.plot('i_out', 'eff', data = df_mask, label = voltage)
	
	title = "{} Efficiency".format(test_name)
	
	fig.suptitle(title)
	ax.set_ylabel('Efficiency')
	ax.set_xlabel('Load Current (A)')

	fig.legend(loc='lower right')
	ax.grid(b=True, axis='both')
	
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
		dir_name, file_name = os.path.split(filepath)
		
		split_path = filename.split(" ")
		test_name = split_path[0]
		graph_filename = os.path.join(graph_dir, "{}_Graph".format(test_name))
		
		#get the input voltage for this test
		df = pd.read_csv(filepaths)
		
		calc_eff(df)
		plot_eff(df, test_name, graph_filename)

################ PROGRAM ###################

if __name__ == '__main__':
	create_graphs()
	