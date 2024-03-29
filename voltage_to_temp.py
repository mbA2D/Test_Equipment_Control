#Convert voltage measurements to resistance and temperature
#Specifically for use with the A2D DAQ testing setup

from math import log

#https://www.thinksrs.com/downloads/programs/Therm%20Calc/NTCCalibrator/NTCcalculator.htm
#Thermistor Constants Steinhart_hart

max_temp = 9999

#NXRT15XV103FA1B
NXRT15XV103FA1B_SH_CONSTANTS = {'SH_A': 1.119349044e-3,
								'SH_B': 2.359019498e-4,
								'SH_C': 0.7926382169e-7}

#http://hyperphysics.phy-astr.gsu.edu/hbase/Tables/rstiv.html
#in ohm * m^2 / m
RESISTIVITY = {'copper': 1.59e-8,
			   'silver': 1.68e-8,
			   'aluminum': 2.65e-8,
			   'nickel': 6.99e-8}
			   
#https://www.powerstream.com/Wire_Size.htm
#AWG: mm^2
AWG_TO_MM2 = {30: 0.057,
			 28: 0.080,
			 26: 0.128,
			 24: 0.205,
			 22: 0.237,
			 20: 0.519,
			 18: 0.823,
			 16: 1.31,
			 14: 2.08,
			 12: 3.31,
			 10: 5.26,
			 8: 8.37,
			 6: 13.3,
			 4: 21.1,
			 2: 33.6,
			 1: 42.4,
			 0: 53.5}
	   

def wire_resistance(length_m = 1.0, awg = 26.0, material = 'copper'):
	#ohms = p * l / A
	return RESISTIVITY[material] * length_m / (AWG_TO_MM2[awg]/1000.0/1000.0)

def resistance_to_temp(resistance, sh_dict = NXRT15XV103FA1B_SH_CONSTANTS):
	#Convert resistance to temperature (C)
	return (1.0/(sh_dict['SH_A'] + sh_dict['SH_B'] * log(resistance) + sh_dict['SH_C'] * (log(resistance)**3.0))) - 273.15

def voltage_to_C(v_meas, r_pullup, v_pullup, sh_constants = NXRT15XV103FA1B_SH_CONSTANTS, wire_length_m = 3.0, wire_awg = 26.0):
	if(v_meas >= v_pullup):
		return max_temp
	
	#calculate bottom resistor in voltage divider
	resistance = (float(v_meas) * float(r_pullup)) / (float(v_pullup) - float(v_meas))
	
	#compensate for the wire length
	resistance = resistance - wire_resistance(length_m = wire_length_m, awg = wire_awg)
	
	#compensate for the switch resistance of the IO expander
	#TODO - measure this
	
	#calculate temperature in Celcius
	temp_C = float(resistance_to_temp(resistance, sh_dict = sh_constants))
	
	return temp_C
	
	