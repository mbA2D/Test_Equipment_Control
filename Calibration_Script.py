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

class CalibrationClass:
    def __init__(self):
        self.dmm = None
        self.dut = None
        self.psu = None
        
        self.dmm_idn = "None"
        self.dut_idn = "None"
        self.psu_idn = "None"
        
        self.dut_channel = None

    def connect_psu(self):
        if self.psu is not None:
            self.psu.close()
    
        self.psu = eq.powerSupplies.choose_psu()[1]
        self.psu_idn = self.psu.inst_idn
        
    def connect_dmm(self):
        if self.dmm is not None:
            self.psu.close()
            
        self.dmm = eq.dmms.choose_dmm()[1]
        self.dmm_idn = self.dmm.inst_idn
    
    def connect_dut(self):
        if self.dut in not None:
            self.dut.close()
    
        self.dut = eq.dmms.choose_dmm()[1]
        self.dut.reset()
        self.dut_idn = self.dut.inst_idn
        
        try:
            self.dut_channel = eq.choose_channel(self.dut.num_channels, self.dut.start_channel)
            self.dut_idn += f' CH {self.dut_channel}'
        except AttributeError:
            pass

    def calibrate_voltage_meter(self):
        #CAL POINT 1
        self.psu.set_voltage(0)
        self.psu.set_current(0.1)
        self.psu.toggle_output(True)
        
        time.sleep(1)
        voltage_1 = self.measure_average(num_to_average = 10, at_adc = True)
        
        #CAL POINT 2
        self.psu.set_voltage(4)
        time.sleep(1)
        voltage_2 = self.measure_average(num_to_average = 10, at_adc = True)
        
        self.psu.toggle_output(False)
        
        if self.dut_channel is not None:
            old_calibration = self.dut.get_calibration(self.dut_channel)
        else:
            old_calibration = self.dut.get_calibration()
        
        #CALIBRATE
        if self.dut_channel is not None:
            self.dut.calibrate_voltage(voltage_1['dmm'], voltage_1['dut'], voltage_2['dmm'], voltage_2['dut'], self.dut_channel)
        else:
            self.dut.calibrate_voltage(voltage_1['dmm'], voltage_1['dut'], voltage_2['dmm'], voltage_2['dut'])
        
        if self.dut_channel is not None:
            new_calibration = self.dut.get_calibration(self.dut_channel)
        else:
            new_calibration = self.dut.get_calibration()
        
        title = 'Use New Calibration?'
        message = f'Would you like to save the new calibration?\nOld Calibration: {old_calibration}\nNew Calibration: {new_calibration}'
        
        if eg.ynbox(title = title,msg = message):
            if self.dut_channel is not None:
                self.dut.save_calibration(self.dut_channel)
            else:
                self.dut.save_calibration()
        else:
            self.dut.reset() #resets calibration values back to original values

    def check_voltage_calibration(self):
        steps = 10
        min_voltage = 0
        max_voltage = 5
        voltages = np.linspace(min_voltage, max_voltage, steps)
        
        self.psu.set_voltage(min_voltage)
        self.psu.toggle_output(True)
        
        measurements_list = []
        
        for voltage in voltages:
            print(voltage)
            self.psu.set_voltage(voltage)
            time.sleep(1)
            measurements = {'psu': voltage}
            measurements.update(self.measure_average(at_adc = False))
            measurements_list.append(measurements)
        
        self.psu.toggle_output(False)
        
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

    def measure_average(self, num_to_average = 10, at_adc = False):
        #get measurements from each source
        measurements = {'dut': [],'dmm': []}
        for i in range(num_to_average):
            if self.dut_channel is not None:
                if at_adc:
                    measurements['dut'].append(self.dut.measure_voltage_at_adc(self.dut_channel))
                else:
                    measurements['dut'].append(self.dut.measure_voltage(self.dut_channel))
            else:
                if at_adc:
                    measurements['dut'].append(self.dut.measure_voltage_at_adc())
                else:
                    measurements['dut'].append(self.dut.measure_voltage())
            measurements['dmm'].append(self.dmm.measure_voltage())
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
    cal_class = CalibrationClass()
    cal_class.connect_dmm()
    cal_class.connect_dut()
    cal_class.connect_psu()
    
    cal_choices = ["Calibrate", "Check Calibration"]
    
    cal_type = eg.indexbox(msg = "What would you like to do?",
                    title = "Calibration Options",
                    choices = cal_choices,
                    default_choice = cal_choices[0])
    
    cal_class.psu.set_voltage(0)
    cal_class.psu.set_current(0.1)                
    
    if cal_type == 0:
        cal_class.calibrate_voltage_meter()
    elif cal_type == 1:
        cal_class.check_voltage_calibration()
