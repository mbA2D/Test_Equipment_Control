import time
import MCP2221_Multiple.MCP2221_Multiple as MMCP

mcp_dict_list = []

def get_gpio_id(mcp):
	value = 0
	for pin in range(3): #only 3 pins used for addressing
		pin_val = mcp.gpio_get_pin(pin)
		print("Pin {} Value: {}".format(pin, pin_val))
		value += (2**pin)*pin_val
	return value

def print_gpio_ids():
	print_string = ""
	iteration = 0
	for entry in mcp_dict_list:
		print_string += "MCP{}: {}\t".format(iteration, entry["GPIO_ID"])
		iteration += 1
	print(print_string)
	time.sleep(0.5)
    
def find_mcp_by_gpio_id(search_id):
	for entry in mcp_dict_list:
		if(entry["GPIO_ID"] == search_id):
			return entry["MCP"]
	print("GPIO ID {} not found".format(search_id))

def get_devices_dict():
	devices = {}
	devices[gpio_to_name[1]] = []
	gpio_ids = [mcp.gpio_id for mcp in mcps]
	if (0 in gpio_ids):
		devices[gpio_to_name[0]] = find_mcp_by_gpio_id(0)
		devices[gpio_to_name[0]].name = gpio_to_name[0]
	for i in range(1, 5):
		if (i in gpio_ids):
			devices[gpio_to_name[i]].append(find_mcp_by_gpio_id(i))
			devices[gpio_to_name[i]][-1].name_id = i-1
			devices[gpio_to_name[i]][-1].name = gpio_to_name[i]
	return devices

def print_devices(devices):
	print("\nDevices With Names:")
	try:
		print("{}: {}".format(devices[gpio_to_name[0]].name,
								devices[gpio_to_name[0]].gpio_id))
	except KeyError:
		pass
	for device in devices[gpio_to_name[1]]:
		print("{}: {}".format(device.name, device.gpio_id))


gpio_to_name = {0: "Safety Controller",
				1: "FET Board",
				2: "FET Board",
				3: "FET Board",
				4: "FET Board"}

mcps = MMCP.connect_to_all_mcps()
num_mcps = len(mcps)

print("Number of MCP2221s connected: {}\n".format(num_mcps))

for mcp in mcps:
	try:
		mcp_dict = {}
		mcp_dict["MCP"] = mcp
		mcp_dict["Num_GPIOs"] = 4
		mcp_dict["I2C_Bus"] = MMCP.I2C(MMCP.MCP2221_I2C(mcp_dict["MCP"], frequency = 100000))
		mcp_dict["GPIO_ID"] = get_gpio_id(mcp_dict["MCP"])
		print("GPIO ID: {}".format(mcp_dict["GPIO_ID"]))
		
		try:
			mcp_dict["Name"] = gpio_to_name[mcp_dict["GPIO_ID"]]
		except KeyError:
			print("GPIO ID Out of bounds: {}".format(mcp_dict["GPIO_ID"]))
		mcp_dict_list.append(mcp_dict)
		
	except OSError:
		continue

print_gpio_ids()

#devices = get_devices_dict()
#print_devices(devices)

#Then scan all the I2C busses:
print("\nScanning I2C Busses")
for entry in mcp_dict_list:
	print("\nMCP GPIO ID: {}".format(entry["GPIO_ID"]))
	print("I2C Addresses Found:")
	print(entry["I2C_Bus"].scan())
	print("\n")


#after we get the GPIOs, we don't need the MCP devices any more, just I2C addresses

#accessing channel reads like this:
#v = tester.measure_voltage(ch=0)
#i = tester.measure_current(ch=0)

#Do we want to kick the watchdogs all at once or does this introduce too much delay?
#tester.kick_dogs() #this would kick all the watchdogs. Task would run every 0.75s?

#I want to access devices like this:
#devices["Safety_Controller"].i2c_bus
#devices["Fet_Board"][0].i2c_bus
#devices["Fet_Board"][1].i2c_bus
#devices["Fet_Board"][2].i2c_bus
#devices["Fet_Board"][3].i2c_bus

#device name, device id, mcp device, i2c bus
