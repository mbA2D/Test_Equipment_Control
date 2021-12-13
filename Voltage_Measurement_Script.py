#Quick and dirty python script to read a voltage a bunch of times

import equipment as eq
import time
import easygui as eg

def main():
	dmm = eq.dmms.choose_dmm()[1]

	msg = "How Many Measurements to perform?"
	title = "Number of Measurements"
	num_measurements = int(eg.enterbox(msg = msg, title = title, default = 100, strip = True))

	msg = "How many seconds to delay before starting to measure?"
	title = "Pre-Measurement Delay"
	delay_s_before_start = int(eg.enterbox(msg = msg, title = title, default = 5, strip = True))

	time.sleep(delay_s_before_start)

	for i in range(num_measurements):
		print(dmm.measure_voltage())


if __name__ == '__main__':
	main()