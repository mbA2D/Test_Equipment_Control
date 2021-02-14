#adds temperature to python logs that do not have it from early testing
#this is fairly inefficient but it does work.

import pandas as pd
import voltage_to_temp as V2T
import easygui as eg
import os

pull_up_v = 3.3
pull_up_r = 3300.0

filepath = eg.fileopenbox(title = "Select the log to add temperature to", filetypes = [['*.csv', 'CSV Files']])
filedir = os.path.dirname(filepath)
filename = os.path.split(filepath)[-1]

#add temp to the filename
filename = 'temp_' + filename
new_filepath = os.path.join(filedir, filename)

df = pd.read_csv(filepath)

for ch in range(64):
	df['Channel_C_{}'.format(ch)] = 9999
	df['Channel_C_{}'.format(ch)] = df['Channel_C_{}'.format(ch)].astype('float64')
	new_col = df['Channel_C_{}'.format(ch)]
	col = df['Channel_{}'.format(ch)]
	#print(col.head())
	for meas in range(len(df.index)):
		new_col[meas] = V2T.voltage_to_C(col[meas]/1000.0, pull_up_r, pull_up_v)
	df['Channel_C_{}'.format(ch)] = new_col
	print('Done Ch {}\n'.format(ch))

df.to_csv(new_filepath, index=False)
