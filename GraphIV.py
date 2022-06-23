#Create a graph of a voltage and current log

import pandas as pd
import matplotlib.pyplot as plt
import easygui as eg
import os
import Templates
import PlotTemps
import FileIO
import scipy.signal

def plot_iv(log_data, save_filepath = '', show_graph=False):
	#plot time(in seconds) as x
	#voltage and current on independant Y axes

	fig, ax_volt = plt.subplots()
	fig.set_size_inches(12, 10)

	ax_volt.plot('Data_Timestamp', 'Voltage', data = log_data, color='r')
	
	ax_curr = ax_volt.twinx()
	ax_curr.plot('Data_Timestamp', 'Current', data = log_data, color='b')
	
	fig.suptitle('Cell Cycle Graph')
	ax_volt.set_ylabel('Voltage (V)', color = 'r')
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

#Function to plot the incremental capacity analysis of a battery's charge or discharge data.
#DiffCapAnalyzer may be helpful here: https://www.theoj.org/joss-papers/joss.02624/10.21105.joss.02624.pdf
#Also, a few other articles as well: https://www.mdpi.com/2313-0105/5/2/37
def plot_ica(data_w_cap):
	
	#################### Setting up all the graphs:
	fig = plt.figure()
	
	ax_ica_raw = fig.add_subplot(411)
	ax_cap_raw = ax_ica_raw.twinx()
	
	title = 'Charge and Incremental Capacity Analysis'
	if(data_w_cap.loc[data_w_cap.index[0], 'Current'] < 0):
		title = 'Discharge'
	fig.suptitle(title)
	ax_cap_raw.set_ylabel('Capacity (Ah)', color = 'r')
	
	#Smoothing the voltage curve:
	ax_ica_smoothed_v = fig.add_subplot(412, sharex = ax_ica_raw)
	#Set Y-label to be smoothed ICA - ylabel will be shared by all since its positioned in the middle.
	ax_ica_smoothed_v.set_ylabel('dQ/dV (Ah/V)')
	
	#add another subplot below, and share the X-axis.
	ax_ica_smoothed1 = fig.add_subplot(413, sharex = ax_ica_raw)
	
	
	#another subplot - 2nd pass of Savgol Filter
	ax_ica_smoothed2 = fig.add_subplot(414, sharex = ax_ica_raw)
	
	#Label on the bottom-most subplot since all x is shared.
	ax_ica_smoothed2.set_xlabel('Voltage')
	
	fig.subplots_adjust(hspace=0.5) #add a little extra space vertically
	
	
	################ Plot capacity and raw dQ/dV - lots of noise
	ax_cap_raw.plot('Voltage', 'Capacity_Ah_Up_To', data = data_w_cap, color = 'r')
	
	ax_ica_raw.plot('Voltage', 'dQ_dV', data = data_w_cap, color = 'b')
	
	
	################# First step - smooth the voltage curve
	#Voltage should not change too quickly - this will only be computed on constant current curves
	data_w_cap['Voltage_smoothed'] = scipy.signal.savgol_filter(data_w_cap['Voltage'].tolist(), 9, 3)
	#need to recalculate the voltage difference
	data_w_cap['Voltage_smoothed_diff'] = data_w_cap['Voltage_smoothed'].diff()
	data_w_cap = data_w_cap.assign(dQ_dV_v_smoothed = data_w_cap['Capacity_Ah'] / data_w_cap['Voltage_smoothed_diff'])
	
	ax_ica_smoothed_v.plot('Voltage_smoothed', 'dQ_dV_v_smoothed', data = data_w_cap, color = 'c')
	
	
	################# 2nd Step - smooth the resulting data
	#savgol filter with window size 9 and polynomial order 3 as suggested by DiffCapAnalyzer.
	data_w_cap['dQ_dV_smoothed1'] = scipy.signal.savgol_filter(data_w_cap['dQ_dV_v_smoothed'].tolist(), 9, 3)
	
	#plot the smoothed data on the 3rd subplot
	ax_ica_smoothed1.plot('Voltage', 'dQ_dV_smoothed1', data = data_w_cap, color = 'g')
	
	################# 3rd Step - 2nd pass of Savgol Filter
	data_w_cap['dQ_dV_smoothed2'] = scipy.signal.savgol_filter(data_w_cap['dQ_dV_smoothed1'].tolist(), 9, 3)
	ax_ica_smoothed2.plot('Voltage','dQ_dV_smoothed2', data = data_w_cap, color = 'y')
	
	plt.show()
	

#Calculates the capacity of the charge or discharge in wh and ah.
#Also returns a dataframe that contains the temperature log entries corresponding to the
#same timestamps as the log.
def calc_capacity(log_data, stats, charge = True, temp_log_dir = None, show_ica_graphs = False):
	#create a mask to get only the discharge data
	if charge:
		prefix = 'charge'
		mask = log_data['Current'] > 0
	else:
		prefix = 'discharge'
		mask = log_data['Current'] < 0

	separate_temps = False
	if temp_log_dir is not None:
		separate_temps = True
	
	log_data.loc[mask]
	dsc_data = log_data
	
	if(dsc_data.size == 0):
		print(f"Data for {prefix} does not exist in log")
		return None
	
	#Calculate time required for cycle
	start_time = dsc_data.loc[dsc_data.index[0], 'Data_Timestamp']
	end_time = dsc_data.loc[dsc_data.index[-1], 'Data_Timestamp']
	end_v = dsc_data.loc[dsc_data.index[-1], 'Voltage']
	total_time = (end_time - start_time)/3600
	
	#add columns to the dataset
	dsc_data['SecsFromLastTimestamp'] = dsc_data['Data_Timestamp'].diff()
	dsc_data.loc[dsc_data.index.tolist()[0], 'SecsFromLastTimestamp'] = 0 #Set first val to 0 instead of NaN.
	
	dsc_data['Capacity_Ah'] = dsc_data['Current'] * dsc_data['SecsFromLastTimestamp'] / 3600
	dsc_data['Capacity_wh'] = dsc_data['Capacity_Ah'] * dsc_data['Voltage']
	
	dsc_data['Capacity_Ah_Up_To'] = dsc_data['Capacity_Ah'].cumsum() #cumulative sum of the values
	dsc_data['Capacity_wh_Up_To'] = dsc_data['Capacity_wh'].cumsum()
	
	dsc_data['Voltage_Diff'] = dsc_data['Voltage'].diff()
	dsc_data = dsc_data.assign(dQ_dV = dsc_data['Capacity_Ah'] / dsc_data['Voltage_Diff'])
	
	capacity_ah = dsc_data['Capacity_Ah_Up_To'].iloc[-1]
	capacity_wh = dsc_data['Capacity_wh_Up_To'].iloc[-1]
	
	#TODO - better way of detecting charge current - find the CV and CC phases?
	#round current to 2 demicals
	charge_a = round(dsc_data['Current'].median(),2)
	
	print(f'{prefix}:')
	
	stats.stats[f'{prefix}_capacity_ah'] = capacity_ah
	stats.stats[f'{prefix}_capacity_wh'] = capacity_wh
	stats.stats[f'{prefix}_time_h'] = total_time
	stats.stats[f'{prefix}_current_a'] = charge_a
	stats.stats[f'{prefix}_start_time'] = start_time
	stats.stats[f'{prefix}_end_time'] = end_time
	stats.stats[f'{prefix}_end_v'] = end_v
	
	print(f'Ah: {capacity_ah}')
	print(f'wh: {capacity_wh}')
	print(f'Time(h): {total_time}')
	print(f'Current(A): {charge_a}')
	print(f'Start Time: {start_time}')
	print(f'End Time: {end_time}')

	if show_ica_graphs: 
		plot_ica(dsc_data)
	
	if separate_temps:
		#now add some temperature data
		temp_data, max_temp = PlotTemps.get_temps(stats.stats, prefix, temp_log_dir)
		stats.stats[f'{prefix}_max_temp_c'] = max_temp
		return temp_data
		
	if True in ['dmm_t' in col_name for col_name in dsc_data]:
		#There are temperatures in the same log as the voltages and currents.
		t_col_list = [col_name for col_name in dsc_data if 'dmm_t' in col_name]
		t_col_list.append('Data_Timestamp')
		temp_data = dsc_data[t_col_list]
		max_temp = temp_data[t_col_list].max().max()
		stats.stats[f'{prefix}_max_temp_c'] = max_temp
		return temp_data
		
	return None

#adds a CycleStatistic dictionary to a CSV without duplicating results in the csv
def dict_to_csv(dict, filepath):
	dict_dataframe = pd.DataFrame(dict, index = [0])

	if(os.path.exists(filepath)):
		write_header = False
		
		FileIO.allow_write(filepath)
		
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
	
	FileIO.set_read_only(filepath)

def add_cycle_numbers(stats_filepath):
	#only want to add on discharge?
	
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
		FileIO.allow_write(filepath)
	df.to_csv(filepath, mode='w', header=True, index=False)
	FileIO.set_read_only(filepath)
	

#changes all timestamps in the dataframe to show seconds from
#cycle start instead python's time.time
def timestamp_to_cycle_start(df):
	if df.size > 0:
		start_time = df['Data_Timestamp'].iloc[0]
		df['Data_Timestamp'] = df['Data_Timestamp'] - start_time
	return df



if __name__ == '__main__':
	filepaths = FileIO.get_multiple_filepaths()
	
	#Are there temperature logs associated?
	temp_log_dir = None
	separate_temps = eg.ynbox(title = "Temperature Logs",
								msg = "Are there separate temperature logs associated with these discharge logs\n" + 
										"created by the A2D Electronics 64CH DAQ?")
	if(separate_temps):
		#get the temps file location
		temp_log_dir = FileIO.get_directory("Choose the directory that contains the temp logs")
	
	show_discharge_graphs = eg.ynbox(title = "Discharge Graphs",
									 msg = "Show the discharge plots?")
	show_ica_graphs = eg.ynbox(title = "ICA Graphs",
							   msg = "Show the ICA plots?")
	
	#ensure that all directories exist
	filedir = os.path.dirname(filepaths[0])
	sub_dirs = ['Graphs', 'Stats', 'Temperature Graphs']
	if separate_temps: sub_dirs.append('Split Temperature Logs')
	for sub_dir in sub_dirs:
		FileIO.ensure_subdir_exists_dir(filedir, sub_dir)
	
	#go through each voltage log and check it
	for filepath in filepaths:
		print(f"Voltage Log File: {os.path.split(filepath)[-1]}")
		filedir = os.path.dirname(filepath)
		filename = os.path.split(filepath)[-1]  
		
		df = pd.read_csv(filepath)
		
		filename_parts = filename.split()

		cell_name = filename_parts[0]
		log_date = filename_parts[1]
		log_time = filename_parts[2]

		#Modify file names for saving graphs and other files
		filename_graph = 'GraphIV ' + filename
		filename_stats = 'Cycle_Statistics.csv'	
		
		#Create directory names to store graphs etc.
		filepath_graph = os.path.join(filedir, sub_dirs[0], filename_graph)
		filepath_stats = os.path.join(filedir, sub_dirs[1], filename_stats)		
		
		#Calculate stats and export
		cycle_stats = Templates.CycleStats()
		cycle_stats.stats['cell_name'] = cell_name
		
		#Calculate capacity and get temperature datasets
		temps_charge = calc_capacity(df, cycle_stats, charge=True, temp_log_dir = temp_log_dir, show_ica_graphs = show_ica_graphs)
		temps_discharge = calc_capacity(df, cycle_stats, charge=False, temp_log_dir = temp_log_dir, show_ica_graphs = show_ica_graphs)
		dict_to_csv(cycle_stats.stats, filepath_stats)
		
		if temps_charge is not None:
			temps_charge = timestamp_to_cycle_start(temps_charge)
			filename_temp_charge = 'Temps_Charge ' + filename
			filepath_graph_temps_charge = os.path.join(filedir, sub_dirs[2], filename_temp_charge)
			if separate_temps:
				filepath_logs_temps_charge = os.path.join(filedir, sub_dirs[3], filename_temp_charge)
				dataframe_to_csv(temps_charge, filepath_logs_temps_charge)
			PlotTemps.plot_temps(temps_charge, cycle_stats.stats['cell_name'], separate_temps,\
					save_filepath=filepath_graph_temps_charge, show_graph=False, suffix = 'charge')
		if temps_discharge is not None:
			temps_discharge = timestamp_to_cycle_start(temps_discharge)
			filename_temp_discharge = 'Temps_Discharge ' + filename
			filepath_graph_temps_discharge = os.path.join(filedir, sub_dirs[2], filename_temp_discharge)
			if separate_temps:
				filepath_logs_temps_discharge = os.path.join(filedir, sub_dirs[3], filename_temp_discharge)
				dataframe_to_csv(temps_discharge, filepath_logs_temps_discharge)
			PlotTemps.plot_temps(temps_discharge, cycle_stats.stats['cell_name'], separate_temps,\
					save_filepath=filepath_graph_temps_discharge, show_graph=False, suffix = 'discharge')
		
		#Change timestamp to be seconds from cycle start instead of epoch
		df = timestamp_to_cycle_start(df)
		
		#Show plot
		plot_iv(df, save_filepath=filepath_graph, show_graph=show_discharge_graphs)
		