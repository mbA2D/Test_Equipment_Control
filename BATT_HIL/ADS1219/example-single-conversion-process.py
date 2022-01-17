#modified to use board instead of Pin and I2C.

import board
import ads1219
import adafruit_tca9548a
import time
from multiprocessing import Process, Event

# This example demonstrates how to use the ADS1219 using single-shot conversion mode 
# The ADC1219 will initiate a conversion when adc.read_data() is called 

def read_adc_values(event = None):
	i2c = board.I2C()

	#time.sleep(0.25)

	#print("Scan I2C {}".format([hex(x) for x in i2c.scan()]))

	tca = adafruit_tca9548a.TCA9548A(i2c)

	#print("Scan I2C {}".format([hex(x) for x in tca[0].scan()]))

	adc = ads1219.ADS1219(tca[0], 0x40)
	#adc = ads1219.ADS1219(i2c, 0x40)


	adc.set_channel(ads1219.ADS1219_MUX.AIN2)
	adc.set_conversion_mode(ads1219.ADS1219_CONV_MODE.CM_SINGLE)
	adc.set_gain(ads1219.ADS1219_GAIN.GAIN_1)
	adc.set_data_rate(ads1219.ADS1219_DATA_RATE.DR_20_SPS)  # 20 SPS is the most accurate
	adc.set_vref(ads1219.ADS1219_VREF.VREF_EXTERNAL)


	if event == None:
		while True:
			result = adc.read_data()
			print('result = {}, V = {:.5f}'.format(result, 
					result * 2.5 * (18.7+2)/2 / ads1219.ADS1219.POSITIVE_CODE_RANGE))
			time.sleep(0.06)
	else:
		while True:
			event.wait() #blocks until the event is set by the other process
			event.clear()
			result = adc.read_data()
			print('result = {}, V = {:.5f}'.format(result, 
					result * 2.5 * (18.7+2)/2 / ads1219.ADS1219.POSITIVE_CODE_RANGE))

def event_settings_process(event):
	while True:
		time.sleep(1)
		event.set()
	
if __name__ == '__main__':
	ch_event = Event()
	
	multi_ch_device_process = Process(target = read_adc_values, args = (ch_event,))
	multi_ch_device_process.start()
	
	event_trigger_process = Process(target = event_settings_process, args = (ch_event,))
	event_trigger_process.start()
	