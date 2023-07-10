#Configuration settings for the A2D DAQ
#This exposes a menu to setup the channels for I/O type

#Input, output, drive high, drive low

import pandas as  pd
import easygui as eg
from os import path

#CSV File Format - needs these column headers
#Channel, Input_Type, Voltage_Scaling, Temp_A, Temp_B, Temp_C

def get_config_dict(default = False):
    if default:
        filename = 'A2D_DAQ_Config_Default.csv'
        filepath = path.join(path.dirname(__file__), filename)
    else:
        #Choose CSV to load from
        filepath = eg.fileopenbox(title = "Choose the CSV to load config for A2D_64CH_DAQ from", filetypes = [['*.csv', 'CSV Files']])

    #Load dict from CSV
    df = pd.read_csv(filepath)
    df = df.astype({'Channel': 'int32'})
    df.set_index('Channel', inplace = True)
    
    return df.to_dict('index')
    