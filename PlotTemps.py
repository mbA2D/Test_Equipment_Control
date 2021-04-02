#Plotting temperatures for each channel

import pandas as pd
import matplotlib.pyplot as plt
import easygui as eg
import os
import TempChannels

tc = TempChannels.TempChannels()
temp_log_dir = eg.diropenbox(title = "Choose the directory that contains the temp logs")

#parameters
#timestamp - the timestampt to look for
#directory - the directory with the temperature log files to look in
#before - look for a timestamp before or after the given one
#tolerance - the tolerance around the timestamp to accept
#returns the filename and timestamp in the temp log file that is closest
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

#check file
def check_file(file_path, check_high, check_low):
	df = pd.read_csv(file_path)
	
	valid_data = False
	
	#apply mask
	df = df[(df['Timestamp'] >= check_low) & (df['Timestamp'] <= check_high)]
	print('File Name: {}\tDataframe Size: {}'.format(os.path.split(file_path)[-1], df.size))
	
	if(df.size > 0):
		valid_data = True
	
	return valid_data, df

#return a dataframe with the temperature log for the discharge log
#uses start and end timestamps to get the data from the temp logs
#channels for each device found with the TempChannels.py cell names
def get_temps(stats, prefix):
	
	#get the filtered data from while charging or discharging
	df = find_timestamp(stats, prefix, temp_log_dir)
	
	#get the channels that were used for this test
	channels = tc.channels[stats['cell_name']]
	
	channel_list = list()
	#get each channel number
	for label in channels:
		for channel_num in channels[label]:
			channel_list.append('Channel_C_{}'.format(channel_num))
	
	df = df[channel_list]
	max_temp = df.max().max()
	print("Max Temp: {}".format(max_temp))
	
	#now we should have just the filtered temperatures for this cell
	return df, max_temp
