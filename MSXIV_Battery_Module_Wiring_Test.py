import A2D_DAQ_control as AD_control
import voltage_to_temp as V2T
import tkinter as tk
import os
from datetime import datetime
import pandas as pd
import time


#connect to the io module
daq = AD_control.A2D_DAQ()


################ CONNECTIONS ON THE BOARD #################

#cell connections
c1_vpin = 16
c2_vpin = 17
c1_bpin = 18
c2_bpin = 19
input_pins = [c1_vpin, c2_vpin, c1_bpin, c2_bpin]

c1_div_ratio = 2 #cell 1 has a voltage divider for 3.3V max range
c2_div_ratio = 3 #cell 2 has a voltage divider to get the 3.3V analog range


#thermistor connections
t1_pin = 20
t2_pin = 21
t3_pin = 22
t4_pin = 23
t5_pin = 24
thermistor_pins = [t1_pin, t2_pin, t3_pin, t4_pin, t5_pin]

pullup_r = 3300
pullup_v = 3.3


############# PIN SETUP AND READING ######################

def setup_pins():
	daq.calibrate_pullup_v()
	pullup_v = daq.get_pullup_v()
	
	for pin in input_pins:
		daq.conf_io(pin, 0) #0 is input
	
	for pin in thermistor_pins:
		daq.conf_io(pin, 1) #1 is output
		daq.set_dig(pin, 1) #pull high

def read_voltages():
	voltages = list()
	
	daq.set_read_delay_ms(50)
	
	voltages.append(daq.get_analog_v(c1_vpin)*c1_div_ratio)
	voltages.append(daq.get_analog_v(c2_vpin)*c2_div_ratio-voltages[-1])
	voltages.append(daq.get_analog_v(c1_bpin)*c1_div_ratio)
	voltages.append(daq.get_analog_v(c2_bpin)*c2_div_ratio-voltages[-1])
	
	return voltages
	
def read_temperatures():
	daq.set_read_delay_ms(5)
	
	daq.calibrate_pullup_v()
	pullup_v = daq.get_pullup_v()
	
	temperatures = list()
	t_pins = [t1_pin, t2_pin, t3_pin, t4_pin, t5_pin]
	
	for pin in t_pins:
		pin_v = daq.get_analog_v(pin)
		temperature_c = V2T.voltage_to_C(pin_v, pullup_r, pullup_v)
		temperatures.append(temperature_c)
		
	return temperatures


####################### FILE IO ###########################

def get_directory(name):
	root = tk.Tk()
	root.withdraw()
	dir = tk.filedialog.askdirectory(
		title='Select location to save {} data files'.format(name))
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
	headers.append('Module_Number')
	headers.append('Cell_1_Voltage-V')
	headers.append('Cell_2_Voltage-V')
	headers.append('Cell_1_Balance-V')
	headers.append('Cell_2_Balance-V')
	headers.append('Temperature_1-degC')
	headers.append('Temperature_2-degC')
	headers.append('Temperature_3-degC')
	headers.append('Temperature_4-degC')
	headers.append('Temperature_5-degC')
	
	write_line(filepath, headers)
	
	return filepath

def write_data(filepath, test_data, printout=False):
	data = list()
	
	#add timestamp
	data.append(time.time())
	data.extend(test_data)
	
	if(printout):
		print(data)
	
	write_line(filepath, data)


######################## GATHER DATA #######################

def gather_data():
	data = list()
	
	#get the module number
	module_number = input("Enter the module number:")
	data.append(module_number)
	
	#read the data
	data.extend(read_voltages())
	data.extend(read_temperatures())
	
	return data


######################### MAIN PROGRAM #######################

dir = get_directory("MSXIV Battery Module Wiring Test")
filepath = start_file(dir, "Module_Manufacturing_Test")

response = "Y"

while response == "Y":
	data = gather_data()
	write_data(filepath, data, printout=True)
	response = input("\n\nDo you want to test another module (Y or N)?\n").upper()


