#Calibrate a voltage meter with interface like the A2D_4CH_Isolated_ADC
#3 instruments required
#A power supply to generate voltage
#A calibrated DMM for the reference meter
#A Devide-Under-Test to generate calibration data for

#Confirmed working with:
#A2D_4CH_Isolated_ADC

import equipment as eq
import time
import easygui as eg
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def calibrate_voltage_meter():
    #CAL POINT 1
    psu.set_voltage(0)
    psu.set_current(0.1)
    psu.toggle_output(True)
    
    time.sleep(1)
    voltage_1 = measure_average(num_to_average = 10, dut_channel = channel, at_adc = True)
    
    #CAL POINT 2
    psu.set_voltage(4)
    time.sleep(1)
    voltage_2 = measure_average(num_to_average = 10, dut_channel = channel, at_adc = True)
    
    psu.toggle_output(False)
    
    if channel is not None:
        old_calibration = dut.get_calibration(channel)
    else:
        old_calibration = dut.get_calibration()
    
    #CALIBRATE
    if channel is not None:
        dut.calibrate_voltage(voltage_1['dmm'], voltage_1['dut'], voltage_2['dmm'], voltage_2['dut'], channel)
    else:
        dut.calibrate_voltage(voltage_1['dmm'], voltage_1['dut'], voltage_2['dmm'], voltage_2['dut'])
    
    if channel is not None:
        new_calibration = dut.get_calibration(channel)
    else:
        new_calibration = dut.get_calibration()
    
    title = 'Use New Calibration?'
    message = f'Would you like to save the new calibration?\nOld Calibration: {old_calibration}\nNew Calibration: {new_calibration}'
    
    if eg.ynbox(title = title,msg = message):
        if channel is not None:
            dut.save_calibration(channel)
        else:
            dut.save_calibration()
    else:
        dut.reset() #resets calibration values back to original values

def check_voltage_calibration():
    steps = 10
    min_voltage = 0
    max_voltage = 5
    voltages = np.linspace(min_voltage, max_voltage, steps)
    
    psu.set_voltage(min_voltage)
    psu.toggle_output(True)
    
    measurements_list = []
    
    for voltage in voltages:
        print(voltage)
        psu.set_voltage(voltage)
        time.sleep(1)
        measurements = {'psu': voltage}
        measurements.update(measure_average(dut_channel = channel, at_adc = False))
        measurements_list.append(measurements)
    
    psu.toggle_output(False)
    
    df = pd.DataFrame.from_records(measurements_list)
    df['dut-dmm'] = df['dut'] - df['dmm']
    df['dut-dmm_percent'] = df['dut-dmm']/df['psu']*100
    
    fig, ax1 = plt.subplots()
    ax1.set_xlabel('Input Voltage (V)')
    ax1.plot(df['psu'], df['dut-dmm'], color='r')
    ax1.set_ylabel('Error (V)', color='r')
    
    ax2 = ax1.twinx()
    
    ax2.plot(df['psu'], df['dut-dmm_percent'], color='b')
    ax2.set_ylabel('Error (%)', color = 'b')
    
    fig.suptitle('Calibration Check')
    fig.tight_layout()
    plt.show()

def measure_average(num_to_average = 10, dut_channel = None, at_adc = False):
    #get measurements from each source
    measurements = {'dut': [],'dmm': []}
    for i in range(num_to_average):
        if dut_channel is not None:
            if at_adc:
                measurements['dut'].append(dut.measure_voltage_at_adc(channel))
            else:
                measurements['dut'].append(dut.measure_voltage(channel))
        else:
            if at_adc:
                measurements['dut'].append(dut.measure_voltage_at_adc())
            else:
                measurements['dut'].append(dut.measure_voltage())
        measurements['dmm'].append(dmm.measure_voltage())
        time.sleep(0.1)
    
    #remove high and low readings if there are enough
    if num_to_average >= 5:
        measurements['dut'].remove(max(measurements['dut']))
        measurements['dut'].remove(min(measurements['dut']))
        measurements['dmm'].remove(max(measurements['dmm']))
        measurements['dmm'].remove(min(measurements['dmm']))
    
    measurements['dut'] = np.mean(measurements['dut'])
    measurements['dmm'] = np.mean(measurements['dmm']) 
        
    return measurements

if __name__ == '__main__':
    #CONNECT EQUIPMENT
    dmm = eq.dmms.choose_dmm()[1] #6.5 digit DMM to calibrate to
    
    dut = eq.dmms.choose_dmm()[1] #The voltage measurement device to calibrate
    dut.reset() #resets calibration values to whatever is in EEPROM
    channel = None
    try:
        channel = eq.choose_channel(dut.num_channels, dut.start_channel)
    except AttributeError:
        pass
    
    psu = eq.powerSupplies.choose_psu()[1]
    
    cal_choices = ["Calibrate", "Check Calibration"]
    
    cal_type = eg.indexbox(msg = "What would you like to do?",
                    title = "Calibration Options",
                    choices = cal_choices,
                    default_choice = cal_choices[0])
    
    psu.set_voltage(0)
    psu.set_current(0.1)                
    
    if cal_type == 0:
        calibrate_voltage_meter()
    elif cal_type == 1:
        check_voltage_calibration()
