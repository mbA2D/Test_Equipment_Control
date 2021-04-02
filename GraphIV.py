#Create a graph of a voltage and current log

import pandas as pd
import matplotlib.pyplot as plt
import easygui as eg
import os
import Templates
import PlotTemps

def plot_iv(log_data, save_filepath = '', show_graph=False):
	#plot time(in seconds) as x
	#voltage and current on independant Y axes

	fig, ax_volt = plt.subplots()
	fig.set_size_inches(12, 10)

	ax_volt.plot('Timestamp', 'Voltage', data = log_data, color='r')
	
	ax_curr = ax_volt.twinx()
	ax_curr.plot('Timestamp', 'Current', data = log_data, color='b')
	
	fig.suptitle('Cell Cycle Graph')
	ax_volt.set_ylabel('Votlage (V)', color = 'r')
	ax_curr.set_ylabel('Current (A)', color = 'b')
	ax_volt.set_xlabel('Seconds From Start of Test (S)')
	
	fig.legend(loc='upper right')
	ax_volt.xaxis.grid(which='both')
	ax_volt.yaxis.grid(which='both')
	
	if(save_filepath != ''):
		plt.savefig(os.path.splitext(save_filepath)[0])
	
	if(show_graph):
		plt.show()
	else:
		plt.close()

def calc_capacity(log_data, stats, charge=True):
	#create a mask to get only the discharge data
	if (charge):
		prefix = 'charge'
		mask = log_data['Current'] > 0
	else:
		prefix = 'discharge'
		mask = log_data['Current'] < 0

	dsc_data = log_data[mask]
	
	if(dsc_data.size == 0):
		print("Data for {} does not exist in log".format(prefix))
		return
	
	#add 3 columns to the dataset
	dsc_data = dsc_data.assign(SecsFromLastTimestamp=0)
	dsc_data = dsc_data.assign(Capacity_Ah=0)
	dsc_data = dsc_data.assign(Capacity_wh=0)
	
	#requires indexes to be the default numeric ones
	for data_index in dsc_data.index:
		
		try:
			dsc_data.loc[data_index, 'SecsFromLastTimestamp'] = \
			dsc_data.loc[data_index, 'Timestamp'] - dsc_data.loc[data_index-1, 'Timestamp']
		except KeyError:
			continue
		
		dsc_data.loc[data_index, 'Capacity_Ah'] = \
		dsc_data.loc[data_index, 'Current'] * dsc_data.loc[data_index, 'SecsFromLastTimestamp'] / 3600
		
		dsc_data.loc[data_index, 'Capacity_wh'] = \
		dsc_data.loc[data_index, 'Capacity_Ah'] * dsc_data.loc[data_index, 'Voltage']
		
	capacity_ah = dsc_data['Capacity_Ah'].sum()
	capacity_wh = dsc_data['Capacity_wh'].sum()
	charge_a = dsc_data['Current'].median()
	
	#Calculate time required for cycle
	start_time = dsc_data.loc[dsc_data.index[0], 'Timestamp']
	end_time = dsc_data.loc[dsc_data.index[-1], 'Timestamp']
	end_v = dsc_data.loc[dsc_data.index[-1], 'Voltage']
	total_time = (end_time - start_time)/3600
	
	print("{}:".format(prefix))
	
	stats.stats['{}_capacity_ah'.format(prefix)] = capacity_ah
	stats.stats['{}_capacity_wh'.format(prefix)] = capacity_wh
	stats.stats['{}_time_h'.format(prefix)] = total_time
	stats.stats['{}_current_a'.format(prefix)] = charge_a
	stats.stats['{}_start_time'.format(prefix)] = start_time
	stats.stats['{}_end_time'.format(prefix)] = end_time
	stats.stats['{}_end_v'.format(prefix)] = end_v
	
	print('Ah: {}'.format(capacity_ah))
	print('wh: {}'.format(capacity_wh))
	print('Time(h): {}'.format(total_time))
	print('Current(A): {}'.format(charge_a))
	print('Start Time: {}'.format(start_time))
	print('End Time: {}'.format(end_time))
	
	#now add some temperature data
	temp_data, max_temp = PlotTemps.get_temps(stats.stats, prefix)
	stats.stats['{}_max_temp_c'.format(prefix)] = max_temp
	
	

def dict_to_csv(dict, filepath):
	dict_dataframe = pd.DataFrame(dict, index = [0])
	
	write_mode = 'w'
	write_header = True
	if(os.path.exists(filepath)):
		write_mode = 'a'
		write_header = False
	dict_dataframe.to_csv(filepath, mode=write_mode, header=write_header, index=False)

if __name__ == '__main__':
	filepaths = eg.fileopenbox(title = "Select the Log(s) to Graph", filetypes = [['*.csv', 'CSV Files']], multiple = True)
		
	for filepath in filepaths:
		print("Voltage Log File: {}".format(os.path.split(filepath)[-1]))
		filedir = os.path.dirname(filepath)
		filename = os.path.split(filepath)[-1]
		
		df = pd.read_csv(filepath)
		
		filename_parts = filename.split()

		cell_name = filename_parts[0]
		log_date = filename_parts[1]
		log_time = filename_parts[2]

		#add graph to the filename
		filename_graph = 'GraphIV_' + filename
		#filename_stats = 'Stats_' + filename
		filename_stats = 'Cycle_Statistics.csv'
		
		filepath_graph = os.path.join(filedir, 'Graphs', filename_graph)
		filepath_stats = os.path.join(filedir, 'Stats', filename_stats)
		
		#calculate stats and export
		cycle_stats = Templates.CycleStats()
		cycle_stats.stats['cell_name'] = cell_name
		calc_capacity(df, cycle_stats, charge=True)
		calc_capacity(df, cycle_stats, charge=False)
		dict_to_csv(cycle_stats.stats, filepath_stats)
		
		#Change timestamp to be seconds from cycle start instead of epoch
		start_time = df['Timestamp'].iloc[0]
		df['Timestamp'] = df['Timestamp'] - start_time
		
		#Show plot
		plot_iv(df, save_filepath=filepath_graph, show_graph=False)

