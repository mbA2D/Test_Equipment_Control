#Plotting temperatures for each channel

import pandas as pd
import matplotlib.pyplot as plt
import easygui as eg
import os
import TempChannels

tc = TempChannels.TempChannels()

#returns a dataframe with all entried in the directory that   
#fall within the start and end times in the stats directory
def find_timestamp(stats, prefix, dir, file = None, tolerance = 10):
	
	check_time_low = stats['{}_start_time'.format(prefix)] - tolerance
	check_time_high = stats['{}_end_time'.format(prefix)] + tolerance
	
	#better way - apply upper and lower masks, check size.
	
	if(file is None):
		num_data_files_used = 0
		for file_name in os.listdir(dir):
			data_added = False
			file_path = os.path.join(dir, file_name)
			if os.path.isdir(file_path):
				#ignore other subdirectories
				continue
			if(num_data_files_used == 0):
				valid, df = check_file(file_path, check_time_high, check_time_low)
			else:
				valid, df_file = check_file(file_path, check_time_high, check_time_low)
			
			#add to the dataframe if we have already started one
			if valid:
				data_added = True
				if(num_data_files_used > 0):
					df = df.append(df_file)
				num_data_files_used += 1
			
			if((valid == False) and (num_data_files_used > 0)):
				#break when no new data was added and we already have data
				break
			
	else:
		file_path = os.path.join(dir, file_name)
		df = check_file(file_path, check_time_high, check_time_low)
	
	if df.size == 0:
		print("No File Found")
	
	return df

#check to see if the file has any measurements with valid timestamps in them
def check_file(file_path, check_high, check_low):
	df = pd.read_csv(file_path)
	
	valid_data = False
	
	#apply mask
	df = df[(df['Timestamp'] >= check_low) & (df['Timestamp'] <= check_high)]
	
	if(df.size > 0):
		print('File Name: {}\tDataframe Size: {}'.format(os.path.split(file_path)[-1], df.size))
		valid_data = True
	
	return valid_data, df

#return a dataframe with the temperature log for the discharge log
#uses start and end timestamps to get the data from the temp logs
#channels for each device found with the TempChannels.py cell names
def get_temps(stats, prefix, log_dir):
	
	#get the filtered data from while charging or discharging
	df = find_timestamp(stats, prefix, log_dir)
	
	#get the channels that were used for this test
	channels = tc.channels[stats['cell_name']]
	
	channel_list = list()
	#get each channel number
	for label in channels:
		for channel_num in channels[label]:
			channel_list.append('Channel_C_{}'.format(channel_num))
	
	max_temp = df[channel_list].max().max()
	
	channel_list.append('Timestamp')
	df = df[channel_list]
	
	print("Max Temp: {}".format(max_temp))
	
	#now we should have just the filtered temperatures for this cell
	return df, max_temp

#plot a dataframe that has all the temperatures in it
def plot_temps(df, cell_name, separate_temps, save_filepath = '', show_graph=True, suffix = ''):
	if df.size == 0:
		return
	
	fig, ax_temps = plt.subplots()
	fig.set_size_inches(12,10)
	
	num_colors = len(df.columns.values.tolist())-1
	cm = plt.get_cmap('tab20') #this colormap has 20 different colors in it
	ax_temps.set_prop_cycle('color', [cm(1.*i/num_colors) for i in range(num_colors)])

	
	#plot all of the temps
	for temp_name in df.columns.values.tolist():
		if temp_name == 'Data_Timestamp':
			continue
		if separate_temps:
			channel_num = temp_name.split('_')[-1]		
			#find the correct location
			location = tc.find_location(cell_name, channel_num)
		else:
			location = temp_name.split('t')[-1]
		#plot
		ax_temps.plot('Data_Timestamp', temp_name, data = df, label = location)
	
	title = 'Temperature log'
	if suffix != '':
		title += ' {}'.format(suffix)
	
	fig.suptitle(title)
	ax_temps.set_ylabel('Temperature (Celsius)')
	ax_temps.set_xlabel('Seconds from Start of Test (S)')
		
	fig.legend(loc='upper right')
	ax_temps.grid(b=True, axis='both')
	
	#save the file if specified
	if(save_filepath != ''):
		plt.savefig(os.path.splitext(save_filepath)[0])
	
	if(show_graph):
		plt.show()
	else:
		plt.close()
	