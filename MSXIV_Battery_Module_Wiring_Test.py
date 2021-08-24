import Arduino_IO_Module_control
import voltage_to_temp as V2T

#connect to the io module
io = Arduino_IO_Module_control.Arduino_IO()


################ CONNECTIONS ON THE BOARD #################

#cell connections
c1_vpin = 2
c2_vpin = 3
c1_bpin = 4
c2_bpin = 5
c2_div_ratio = 2 #cell 2 has a voltage divider to get the 5V analog range

#thermistor connections - have a 10K pullup
t1_pin = 6
t2_pin = 7
t3_pin = 8
t4_pin = 9
pullup_r = 10000
pullup_v = 5


############# PIN SETUP AND READING ######################

def setup_pins():
	input_pins = [c1_vpin, c2_vpin, c1_bpin, c2_bpin, t1_pin, t2_pin, t3_pin, t4_pin]
	for pin in input_pins:
		io.conf_io(pin, 0) #0 is input

def read_voltages():
	voltages = list()
	voltages.append(io.get_analog_v(c1_vpin))
	voltages.append(io.get_analog_v(c2_vpin)/c2_div_ratio)
	voltages.append(io.get_analog_v(c1_bpin))
	voltages.append(io.get_analog_v(c2_bpin)/c2_div_ratio)
	return voltages
	
def read_temperatures():
	temperatures = list()
	t_pins = [t1_pin, t2_pin, t3_pin, t4_pin]
	
	for pin in t_pins:
		pin_v = io.get_analog_v(pin)
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
	
	write_line(filepath, headers)
	
	return filepath

def write_data(filepath, test_data, printout=False):
	data = list()
	
	#add timestamp
	data.append(time.time())
	data.extend(test_data)
	
	if(printout):
		print(data)
	
	write_line(filepath, test_data)


######################## GATHER DATA #######################

def gather_data():
	data = list()
	
	#get the module number
	module_number = input("Enter the module number:")
	data.append(module_number)
	
	#read the data
	data.extend(read_voltages())
	data.extend(read_temperatures())
	
	

######################### MAIN PROGRAM #######################

dir = get_directory("MSXIV Battery Module Test)
filepath = start_file(dir, "Module_Manufacturing_Test")

response = "Y"

while response == "Y":
	data = gather_data()
	write_data(filepath, data, printout=True)
	response = input("\n\nDo you want to test another module (Y or N)?\n").upper()


