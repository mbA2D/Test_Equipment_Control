#Create a graph of a voltage and current log

import pandas as pd
import matplotlib.pyplot as plt
import easygui as eg
import os
import Templates
import PlotTemps
from stat import S_IREAD, S_IWUSR

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

def calc_capacity(log_data, stats, charge=True, temp_log_dir = ""):
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
		return dsc_data
	
	#Calculate time required for cycle
	start_time = dsc_data.loc[dsc_data.index[0], 'Timestamp']
	end_time = dsc_data.loc[dsc_data.index[-1], 'Timestamp']
	end_v = dsc_data.loc[dsc_data.index[-1], 'Voltage']
	total_time = (end_time - start_time)/3600
	
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
	#round current to 1 decimal point
	charge_a = round(dsc_data['Current'].median(),1)
	
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

	if(temps):
		#now add some temperature data
		temp_data, max_temp = PlotTemps.get_temps(stats.stats, prefix, temp_log_dir)
		stats.stats['{}_max_temp_c'.format(prefix)] = max_temp
		
		return temp_data
	return dsc_data

def set_read_only(filepath):
	#make the file read-only so we don't lose decimal places if the CSV is opened in excel
	os.chmod(filepath, S_IREAD)

def allow_write(filepath):
	#make the file writable 
	#https://stackoverflow.com/questions/28492685/change-file-to-read-only-mode-in-python
	os.chmod(filepath, S_IWUSR|S_IREAD)

#adds a CycleStatistic dictionary to a CSV without duplicating results in the csv
def dict_to_csv(dict, filepath):
	dict_dataframe = pd.DataFrame(dict, index = [0])

	if(os.path.exists(filepath)):
		write_header = False
		
		allow_write(filepath)
		
		dataframe_csv = pd.read_csv(filepath)
		
		dataframe_csv = dataframe_csv.set_index('charge_start_time')
		try:
			dataframe_csv.drop(dict['charge_start_time'], axis=0, inplace=True)
		except KeyError:
			pass
		dataframe_csv.reset_index(inplace=True)
		dataframe_csv.rename(columns={'index': 'charge_start_time'})
		
		dict_dataframe = dataframe_csv.append(dict_dataframe)
		
	dict_dataframe.to_csv(filepath, mode='w', header=True, index=False)
	
	set_read_only(filepath)

def add_cycle_numbers(stats_filepath):
	#stats_df = pd.read_csv(stats_filepath)
	#stats_df.sort_values(by=['charge_start_time'])
	
	#assume that every entry is a charge and discharge cycle
	#split into each cell name
	#cell_names = stats_df.cell_name.unique()
	
	#add a new row in the dataframe to store the cycle number
	#stats_df = 
	
	#sort by charge_start_time
	#for cell_name in cell_names:
		#add mask to dataframe
		#cell_stats_df = stats_df[stats_df[cell_name]]
		
		#go through each row
		
		
		#number each of the cycles
		
		#if a number already there, then use that number
	pass
		
def dataframe_to_csv(df, filepath):
	#if the file exists, make sure it is write-able.
	if(os.path.exists(filepath)):
		allow_write(filepath)
	df.to_csv(filepath, mode='w', header=True, index=False)
	set_read_only(filepath)
	

#changes all timestamps in the dataframe to show seconds from
#cycle start instead python's time.time
def timestamp_to_cycle_start(df):
	if df.size > 0:
		start_time = df['Timestamp'].iloc[0]
		df['Timestamp'] = df['Timestamp'] - start_time
	return df



if __name__ == '__main__':
	filepaths = eg.fileopenbox(title = "Select the Log(s) to Graph", filetypes = [['*.csv', 'CSV Files']], multiple = True)
	
	#Are there temperature logs associated?
	temp_log_dir = ""
	temps = eg.ynbox(title = "Are there temperature logs associated with these discharge logs\ncreated by the A2D Electronics 64CH DAQ?")):
	if(temps):
		#get the temps file location
		temp_log_dir = eg.diropenbox(title = "Choose the directory that contains the temp logs")
	
	#ensure that all directories exist
	filedir = os.path.dirname(filepaths[0])
	sub_dirs = ['Graphs','Stats']
	if(temps):
		sub_dirs.append('Temperature Graphs')
		sub_dirs.append('Split Temperature Logs')
	for sub_dir in sub_dirs:
		if not os.path.exists(os.path.join(filedir, sub_dir)):
			os.makedirs(os.path.join(filedir, sub_dir))
	
	#go through each voltage log and check it
	for filepath in filepaths:
		print("Voltage Log File: {}".format(os.path.split(filepath)[-1]))
		filedir = os.path.dirname(filepath)
		filename = os.path.split(filepath)[-1]  
		
		df = pd.read_csv(filepath)
		
		filename_parts = filename.split()

		cell_name = filename_parts[0]
		log_date = filename_parts[1]
		log_time = filename_parts[2]

		#modify file names for savings graphs and other files
		filename_graph = 'GraphIV ' + filename
		filename_stats = 'Cycle_Statistics.csv'
		if(temps):
			filename_temp_charge = 'Temps_Charge ' + filename
			filename_temp_discharge = 'Temps_Discharge ' + filename
		
		#Create directory names to store graphs etc.
		filepath_graph = os.path.join(filedir, sub_dirs[0], filename_graph)
		filepath_stats = os.path.join(filedir, sub_dirs[1], filename_stats)		
		if(temps):
			filepath_graph_temps_charge = os.path.join(filedir, sub_dirs[2], filename_temp_charge)
			filepath_graph_temps_discharge = os.path.join(filedir, sub_dirs[2], filename_temp_discharge)
			filepath_logs_temps_charge = os.path.join(filedir, sub_dirs[3], filename_temp_charge)
			filepath_logs_temps_discharge = os.path.join(filedir, sub_dirs[3], filename_temp_discharge)
			
		#calculate stats and export
		cycle_stats = Templates.CycleStats()
		cycle_stats.stats['cell_name'] = cell_name
		
		temps_charge = calc_capacity(df, cycle_stats, charge=True, temp_log_dir)
		temps_discharge = calc_capacity(df, cycle_stats, charge=False, temp_log_dir)
		dict_to_csv(cycle_stats.stats, filepath_stats)
		
		#Change timestamp to be seconds from cycle start instead of epoch
		df = timestamp_to_cycle_start(df)
		if(temps):
			temps_charge = timestamp_to_cycle_start(temps_charge)
			temps_discharge = timestamp_to_cycle_start(temps_discharge)
			#export temps for this cell directly to csv
			dataframe_to_csv(temps_charge, filepath_logs_temps_charge)
			dataframe_to_csv(temps_discharge, filepath_logs_temps_discharge)
		
		#Show plot
		plot_iv(df, save_filepath=filepath_graph, show_graph=False)
		if(temps):
			PlotTemps.plot_temps(temps_charge, cycle_stats.stats['cell_name'], \
					save_filepath=filepath_graph_temps_charge, show_graph=False, prefix = 'charge')
			PlotTemps.plot_temps(temps_discharge, cycle_stats.stats['cell_name'], \
					save_filepath=filepath_graph_temps_discharge, show_graph=False, prefix = 'discharge')
