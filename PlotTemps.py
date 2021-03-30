#Plotting temperatures for each channel

import pandas as pd
import matplotlib.pyplot as plt
import easygui as eg
import os
import TempChannels

tc = TempChannels.TempChannels()

#parameters
#timestamp - the timestampt to look for
#directory - the directory with the temperature log files to look in
#before - look for a timestamp before or after the given one
#tolerance - the tolerance around the timestamp to accept
#returns the filename and timestamp in the temp log file that is closest
def find_timestamp(timestamp, dir, file = None, before = True, tolerance = 5):
	
	check_time_low = timestamp - before*tolerance
	check_time_high = timestamp + (!before)*tolerance
	
	#better way - apply upper and lower masks, check size.
	
	if(file is None):
		for file_name in os.listdir(dir):
			file_path = os.path.join(dir, file_name)
			if os.path.isdir(file_path):
				#ignore other subdirectories
				continue
			df = check_file(file_path)
			#exit for loop once a file with the correct timestamps is found
			if df.size() != 0:
				break
	else:
		df = check_file(file)
	
	return file, df

#check file
def check_file(file_path, check_high, check_low):
	df = pd.read_csv(file_path)
	
	#apply mask
	df = df[df['Timestamp'] >= check_low & df['Timestamp'] <= check_high]
	print('Dataframe Size: {}'.format(df.size()	))
	
	return df

#return a dictionary with the temperature log for the discharge log
#timestamp_start - the timestamp at the start of the discharge
#timestamp_end - the timestamp at the end of the discahrge
#cell_name - the name of the cell - e.g. "EMS_SC_EPOXY", must match an entry in TempChannels.py
def get_temps(timestamp_start, timestamp_end, cell_name):
	
	temp_log_dir = eg.opendirbox(title = "Choose the directory that contains the temp logs")
	
	#get the file and the filtered data from while charging or discharging
	file, df = find_timestamp(timestamp_start, temp_log_dir, before = True)
	
	#get the channels that were used for this test
	channels = tc.channels[cell_name]
	
	channel_list = list()
	
	#get each channel number
	for label in channels:
		for channel_num in channels[label]:
			channel_list.append('Channel_{}_C'.format(channel_num))
	
	df = df[[channel_list]]
	
	#now we should have just the filtered temperatures for this cell
	return df
