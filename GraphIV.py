#Create a graph of a voltage and current log

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import easygui as eg
import os
import sys
import Templates
import PlotTemps
import FileIO
import scipy.signal




######################################## DiffCapAnalyzer Example for Differential Capacity Analysis

import glob
import itertools
import matplotlib 
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import peakutils
import scipy
import sqlite3 as sql

from diffcapanalyzer.databasewrappers import process_data
from diffcapanalyzer.databasewrappers import get_filename_pref
from diffcapanalyzer.databasefuncs import init_master_table
from diffcapanalyzer.databasefuncs import get_file_from_database
from diffcapanalyzer.descriptors import generate_model

def process_one_file(df, save_as_name, database, datatype, windowlength = 9,
                     polyorder = 3, peak_thresh = 0.7, save_to_excel = False):
    if not os.path.exists(database): 
        init_master_table(database)
    cleanset_name = save_as_name + 'CleanSet'
    
    expected_cols = [
        'Voltage',
        'Current',
        'Abs_Capacity_Ah_Up_To']
    assert all(item in list(df.columns) for item in expected_cols)
    df.rename(
        columns={
            'Voltage': 'Voltage(V)',
            'Current': 'Current(A)',
            'Abs_Capacity_Ah_Up_To': 'Cap(Ah)'},
        inplace=True)
    df['Cycle_Index'] = 1
        
    process_data(
        save_as_name,
        database,
        df,
        datatype,
        windowlength,
        polyorder)
    df_clean = get_file_from_database(cleanset_name, database)
    feedback = generate_model(
        df_clean, save_as_name, peak_thresh, database)
    descriptors_df = get_file_from_database(save_as_name + '-descriptors', database)
    if save_to_excel: 
        writer = pd.ExcelWriter(save_as_name + '-descriptors.xlsx')
        descriptors_df.to_excel(writer, 'Sheet1')
        writer.save()
    return descriptors_df

def diffcapanalyzer_plot_ica(df, cell_name, filepath_dqdv_graph, filepath_dqdv_stats):
    database = os.path.join(os.path.split(filepath_dqdv_stats)[0], 'diff_cap_analyzer_db.db')
    base_filename = 'CS2_33_8_30_10'
    datatype = 'MACCOR'

    descriptors_df = process_one_file(df, base_filename, database, datatype, peak_thresh = 0.3)


    # First let's define some variable names
    # If you are interested in plotting something other than 
    # the file that was just processed, simply change the base_filename
    # variable to the file name in the database you wish to plot. 

    raw_filename = base_filename + "Raw"
    model_filename = base_filename + "-ModPoints"
    descriptors_filename = base_filename + "-descriptors"
    clean_filename = base_filename + "CleanSet"

    # First let's plot the raw dQ/dV curve of an example cycle, with the model overlaid.

    raw_df = get_file_from_database(raw_filename, database)
    mod_df = get_file_from_database(model_filename, database)

    fig1 = plt.figure(figsize = (7,8), facecolor = 'w', edgecolor= 'k')
    # create the color map based off of the max value in the cycle index column
    colors = matplotlib.cm.Greys(np.linspace(0.3, 1, int(max(raw_df['Cycle_Index']))))

    cycle_to_plot = 1
    # plot cycle 1, this number can be changed to any cycle

    for name, group in raw_df.groupby(['Cycle_Index']):
        if name == cycle_to_plot:
            plt.plot(group['Voltage(V)'], group['dQ/dV'], c = 'black', linewidth = 2, label = 'Cycle Data') 

    for name, group in mod_df.groupby(['Cycle_Index']): 
        if name == cycle_to_plot:
            plt.plot(group['Voltage(V)'], group['Model'], c = 'red', linewidth = 2, label = 'Model', linestyle = '--')

    plt.legend()
    leg = plt.legend(loc = 'upper left', fontsize = 14)
    plt.ylabel('dQ/dV (Ah/V)', fontsize =20)
    plt.xlabel('Voltage(V)', fontsize = 20)
    plt.title('{} ICA'.format(cell_name), fontsize = 24)
    plt.xticks(fontsize = 20)
    plt.yticks(fontsize = 20)
    plt.tick_params(size = 10, width = 1)

    # plt.xlim(0, 4)
    #plt.ylim(-20,20)

    # Uncomment the following line if you would like to save the plot. 
    plt.savefig(os.path.splitext(filepath_dqdv_graph)[0], bbox_inches='tight', dpi = 600)

######################################## End of DiffCapAnalyzer Example
def plot_ica(df_charge, df_discharge, cell_name, filepath_dqdv_graph, filepath_dqdv_stats):    
    df_discharge['Step_Index'] = 1
    df_ica = df_charge.append(df_discharge, ignore_index=True)
    df_ica['datatype'] = 'MACCOR'
    df_ica['Abs_Capacity_Ah_Up_To'] = df_ica['Capacity_Ah_Up_To'].abs()
    
    #So it looks like a MACCOR df to the DiffCapAnalyzer tools
    df_ica['Md'] = df_ica['Step_Index']
    df_ica['Rec'] = df_ica['Data_Timestamp']
    
    diffcapanalyzer_plot_ica(df_ica, cell_name, filepath_dqdv_graph, filepath_dqdv_stats)

'''
#Function to plot the incremental capacity analysis of a battery's charge or discharge data.
#DiffCapAnalyzer may be helpful here: https://www.theoj.org/joss-papers/joss.02624/10.21105.joss.02624.pdf
#Also, a few other articles as well: https://www.mdpi.com/2313-0105/5/2/37
def plot_ica(data_charge, sub_dirs, cell_name, filedir, filename):
    
    #################### Setting up all the graphs:
    fig = plt.figure()
    
    ax_ica_raw = fig.add_subplot(411)
    ax_cap_raw = ax_ica_raw.twinx()
    
    title = cell_name + ' Incremental Capacity Analysis'
    fig.suptitle(title)
    ax_cap_raw.set_ylabel('Capacity (Ah)', color = 'r')
    
    #Smoothing the voltage curve:
    ax_ica_smoothed_v = fig.add_subplot(412, sharex = ax_ica_raw)
    #Set Y-label to be smoothed ICA - ylabel will be shared by all since its positioned in the middle.
    ax_ica_smoothed_v.set_ylabel('dQ/dV (Ah/V)')
    
    #add another subplot below, and share the X-axis.
    ax_ica_smoothed1 = fig.add_subplot(413, sharex = ax_ica_raw)
    
    
    #another subplot - 2nd pass of Savgol Filter
    ax_ica_smoothed2 = fig.add_subplot(414, sharex = ax_ica_raw)
    
    #Label on the bottom-most subplot since all x is shared.
    ax_ica_smoothed2.set_xlabel('Voltage')
    
    fig.subplots_adjust(hspace=0.5) #add a little extra space vertically
    
    
    ################# First step - smooth the voltage curve
    data_w_cap['SecsFromLastTimestamp'] = data_w_cap['Data_Timestamp'].diff().fillna(0)
    data_w_cap['Capacity_Ah'] = data_w_cap['Current'] * data_w_cap['SecsFromLastTimestamp'] / 3600
    
    data_w_cap['Voltage_Diff'] = data_w_cap['Voltage'].diff()
    data_w_cap = data_w_cap.assign(dQ_dV = data_w_cap['Capacity_Ah'] / data_w_cap['Voltage_Diff'])
    
    #Voltage should not change too quickly - this will only be computed on constant current curves
    data_w_cap['Voltage_smoothed'] = scipy.signal.savgol_filter(data_w_cap['Voltage'].tolist(), 9, 3)
    #need to recalculate the voltage difference
    data_w_cap['Voltage_smoothed_diff'] = data_w_cap['Voltage_smoothed'].diff()
    data_w_cap = data_w_cap.assign(dQ_dV_v_smoothed = data_w_cap['Capacity_Ah'] / data_w_cap['Voltage_smoothed_diff'])
    
    ################# 2nd Step - smooth the resulting data
    #savgol filter with window size 9 and polynomial order 3 as suggested by DiffCapAnalyzer.
    data_w_cap['dQ_dV_smoothed1'] = scipy.signal.savgol_filter(data_w_cap['dQ_dV_v_smoothed'].tolist(), 9, 3)
    
    ################# 3rd Step - 2nd pass of Savgol Filter
    data_w_cap['dQ_dV_smoothed2'] = scipy.signal.savgol_filter(data_w_cap['dQ_dV_smoothed1'].tolist(), 9, 3)
    
    
    ################ Plots
    #Plot raw data
    ax_cap_raw.plot('Voltage', 'Capacity_Ah_Up_To', data = data_w_cap, color = 'r')
    ax_ica_raw.plot('Voltage', 'dQ_dV', data = data_w_cap, color = 'b')
    #Plot 1st step
    ax_ica_smoothed_v.plot('Voltage_smoothed', 'dQ_dV_v_smoothed', data = data_w_cap, color = 'c')
    #Plot 2nd step
    ax_ica_smoothed1.plot('Voltage', 'dQ_dV_smoothed1', data = data_w_cap, color = 'g')
    #Plot 3rd step
    ax_ica_smoothed2.plot('Voltage','dQ_dV_smoothed2', data = data_w_cap, color = 'y')
    
    
    #Save graph
    filename_ica_graph = 'ICA ' + filename
    filepath_ica_graph = os.path.join(filedir, sub_dirs[0], filename_ica_graph)
    plt.savefig(os.path.splitext(filepath_ica_graph)[0])
'''

def plot_iv(log_data, save_filepath = '', show_graph=False):
    #plot time(in seconds) as x
    #voltage and current on independant Y axes

    fig, ax_volt = plt.subplots()
    fig.set_size_inches(12, 10)

    ax_volt.plot('Data_Timestamp', 'Voltage', data = log_data, color='r')
    
    ax_curr = ax_volt.twinx()
    ax_curr.plot('Data_Timestamp', 'Current', data = log_data, color='b')
    
    fig.suptitle('Cell Cycle Graph')
    ax_volt.set_ylabel('Voltage (V)', color = 'r')
    ax_curr.set_ylabel('Current (A)', color = 'b')
    ax_volt.set_xlabel('Seconds From Start of Test (S)')
    
    fig.legend(loc='upper right')
    ax_volt.xaxis.grid(which='both')
    ax_volt.yaxis.grid(which='both')
    
    if(save_filepath != ''):
        plt.savefig(os.path.splitext(save_filepath)[0])
    
    if(show_graph):
        plt.show()
    else:
        plt.close()


#Calculates the capacity of the charge or discharge in wh and ah.
#Also returns a dataframe that contains the temperature log entries corresponding to the
#same timestamps as the log.
def calc_capacity(log_data, stats, sub_dirs, filedir, charge = True, temp_log_dir = None, show_ica_graphs = False):
    #create a mask to get only the discharge data
    if charge:
        prefix = 'charge'
        mask = log_data['Current'] > 0
    else:
        prefix = 'discharge'
        mask = log_data['Current'] < 0

    separate_temps = False
    if temp_log_dir is not None:
        separate_temps = True
    
    dsc_data = log_data.loc[mask]
    
    #print(dsc_data.head())
    #print(dsc_data.tail())
    
    if(dsc_data.size == 0):
        print(f"Data for {prefix} does not exist in log")
        return None
    
    #Calculate time required for cycle
    start_time = dsc_data.loc[dsc_data.index[0], 'Data_Timestamp']
    end_time = dsc_data.loc[dsc_data.index[-1], 'Data_Timestamp']
    end_v = dsc_data.loc[dsc_data.index[-1], 'Voltage']
    total_time = (end_time - start_time)/3600
    
    #add columns to the dataset
    dsc_data['SecsFromLastTimestamp'] = dsc_data['Data_Timestamp'].diff().fillna(0)
    
    dsc_data['Capacity_Ah'] = dsc_data['Current'] * dsc_data['SecsFromLastTimestamp'] / 3600
    dsc_data['Capacity_wh'] = dsc_data['Capacity_Ah'] * dsc_data['Voltage']
    
    dsc_data['Capacity_Ah_Up_To'] = dsc_data['Capacity_Ah'].cumsum() #cumulative sum of the values
    dsc_data['Capacity_wh_Up_To'] = dsc_data['Capacity_wh'].cumsum()
    
    capacity_ah = dsc_data['Capacity_Ah_Up_To'].iloc[-1]
    capacity_wh = dsc_data['Capacity_wh_Up_To'].iloc[-1]
    
    #TODO - better way of detecting charge current - find the CV and CC phases?
    #round current to 2 demicals
    charge_a = round(dsc_data['Current'].median(),2)
    
    print(f'{prefix}:')
    
    stats.stats[f'{prefix}_capacity_ah'] = capacity_ah
    stats.stats[f'{prefix}_capacity_wh'] = capacity_wh
    stats.stats[f'{prefix}_time_h'] = total_time
    stats.stats[f'{prefix}_current_a'] = charge_a
    stats.stats[f'{prefix}_start_time'] = start_time
    stats.stats[f'{prefix}_end_time'] = end_time
    stats.stats[f'{prefix}_end_v'] = end_v
    
    print(f'Ah: {capacity_ah}')
    print(f'wh: {capacity_wh}')
    print(f'Time(h): {total_time}')
    print(f'Current(A): {charge_a}')
    print(f'Start Time: {start_time}')
    print(f'End Time: {end_time}')

    #plot_ica(dsc_data, sub_dirs, filedir)
    
    if separate_temps:
        #now add some temperature data
        temp_data, max_temp = PlotTemps.get_temps(stats.stats, prefix, temp_log_dir)
        stats.stats[f'{prefix}_max_temp_c'] = max_temp
        return temp_data
        
    if True in ['dmm_t' in col_name for col_name in dsc_data]:
        #There are temperatures in the same log as the voltages and currents.
        t_col_list = [col_name for col_name in dsc_data if 'dmm_t' in col_name]
        temp_data = dsc_data[t_col_list]
        max_temp = temp_data[t_col_list].max().max()
        stats.stats[f'{prefix}_max_temp_c'] = max_temp
        t_col_list.append('Data_Timestamp')
        temp_data = dsc_data[t_col_list]
        return temp_data
        
    return None

#adds a CycleStatistic dictionary to a CSV without duplicating results in the csv
def dict_to_csv(dict, filepath):
    if dict['charge_start_time'] == 0:
        #if we only have discharge data
        dict['charge_start_time'] = dict['discharge_start_time']
    dict_dataframe = pd.DataFrame(dict, index = [0])
    
    if(os.path.exists(filepath)):
        FileIO.allow_write(filepath)
        dataframe_csv = pd.read_csv(filepath)
        
        try:
            #drop any entries with the same charge start time as the one we want to add
            matching_index = dataframe_csv.index[dataframe_csv['charge_start_time'] == dict['charge_start_time']].tolist()[0]
            dataframe_csv.drop(matching_index, axis=0, inplace=True)
        except IndexError:
            pass
            
        dict_dataframe = pd.DataFrame(dict, index = [0])
        dict_dataframe = dataframe_csv.append(dict_dataframe)#, ignore_index=True)
        
    dict_dataframe.to_csv(filepath, mode='w', header=True, index=False)
    
    FileIO.set_read_only(filepath)

def add_cycle_numbers(stats_filepath):
    #only want to add on discharge?
    
    #stats_df = pd.read_csv(stats_filepath)
    #stats_df.sort_values(by=['charge_start_time'])
    
    #assume that every entry is a charge and discharge cycle
    #split into each cell name
    #cell_names = stats_df.cell_name.unique()
    
    #add a new row in the dataframe to store the cycle number
    #stats_df = 
    
    #sort by charge_start_time
    #for cell_name in cell_names:
        #add mask to dataframe
        #cell_stats_df = stats_df[stats_df[cell_name]]
        
        #go through each row
        
        
        #number each of the cycles
        
        #if a number already there, then use that number
    pass
        
def dataframe_to_csv(df, filepath):
    #if the file exists, make sure it is write-able.
    if(os.path.exists(filepath)):
        FileIO.allow_write(filepath)
    df.to_csv(filepath, mode='w', header=True, index=False)
    FileIO.set_read_only(filepath)
    

#changes all timestamps in the dataframe to show seconds from
#cycle start instead python's time.time
def timestamp_to_cycle_start(df):
    if df.size > 0:
        start_time = df['Data_Timestamp'].iloc[0]
        df['Data_Timestamp'] = df['Data_Timestamp'] - start_time
    return df



def process_standard_charge_discharge_cycle(filedir, filename, subdirs, df, separate_temps, temp_log_dir, show_ica_graphs, show_discharge_graphs):
    #Modify file names for saving graphs and other files
    filename_graph = 'GraphIV ' + filename
    filename_stats = 'Cycle_Statistics.csv'	
    
    #Create directory names to store graphs etc.
    filepath_graph = os.path.join(filedir, sub_dirs[0], filename_graph)
    filepath_stats = os.path.join(filedir, sub_dirs[1], filename_stats)		
    
    #Calculate stats and export
    cycle_stats = Templates.CycleStats()
    cycle_stats.stats['cell_name'] = cell_name
    
    #Calculate capacity and get temperature datasets
    temps_charge = calc_capacity(df, cycle_stats, subdirs, filedir, charge=True, temp_log_dir = temp_log_dir, show_ica_graphs = show_ica_graphs)
    temps_discharge = calc_capacity(df, cycle_stats, subdirs, filedir, charge=False, temp_log_dir = temp_log_dir, show_ica_graphs = show_ica_graphs)
    dict_to_csv(cycle_stats.stats, filepath_stats)
    
    #Plot temperatures
    if temps_charge is not None:
        temps_charge = timestamp_to_cycle_start(temps_charge)
        filename_temp_charge = 'Temps_Charge ' + filename
        filepath_graph_temps_charge = os.path.join(filedir, sub_dirs[2], filename_temp_charge)
        if separate_temps:
            filepath_logs_temps_charge = os.path.join(filedir, sub_dirs[3], filename_temp_charge)
            dataframe_to_csv(temps_charge, filepath_logs_temps_charge)
        PlotTemps.plot_temps(temps_charge, cycle_stats.stats['cell_name'], separate_temps,\
                save_filepath=filepath_graph_temps_charge, show_graph=False, suffix = 'charge')
    if temps_discharge is not None:
        temps_discharge = timestamp_to_cycle_start(temps_discharge)
        filename_temp_discharge = 'Temps_Discharge ' + filename
        filepath_graph_temps_discharge = os.path.join(filedir, sub_dirs[2], filename_temp_discharge)
        if separate_temps:
            filepath_logs_temps_discharge = os.path.join(filedir, sub_dirs[3], filename_temp_discharge)
            dataframe_to_csv(temps_discharge, filepath_logs_temps_discharge)
        PlotTemps.plot_temps(temps_discharge, cycle_stats.stats['cell_name'], separate_temps,\
                save_filepath=filepath_graph_temps_discharge, show_graph=False, suffix = 'discharge')
    
    #Change timestamp to be seconds from cycle start for the graph instead of epoch
    df = timestamp_to_cycle_start(df)
    
    #Show plot
    plot_iv(df, save_filepath=filepath_graph, show_graph=show_discharge_graphs)


def df_drop_low_and_high_value_by_column(df, column_label):
    min_index = df[column_label].idxmin()
    max_index = df[column_label].idxmax()
    df.drop(index=[min_index, max_index], inplace=True)

def clean_single_step_data_ir_test(df):
    #Clean up the data
    df.reset_index(inplace=True)
    if df['Voltage'].size > 1:
        #If more than 1 measurement, discard the first since the current may still be rising.
        df.drop(index=0, inplace=True)
    
    if df['Voltage'].size >= 10:
        #TODO
        #If we still have at least 10 measurements, we can consider only the 2nd half and extrapolate
        #voltage back to the start of the step to account for capacity loss.
        # - drop the first half of the data (will be less linear)
        # - calculate a line equation for the voltage data (voltage vs time_from_start_of_step)
        # - extrapolate that line back to the start of the step (time t=0)
        # - drop all values except that extrapolated value (since all the values left get averaged later)
        
        # - If this is the 2nd step, we could theoretically extrapolate a line back to the start of the first step.
        # - We might need a bit more data for that though (e.g. cell capacity, SoC?)
        pass
    elif df['Voltage'].size >= 5:
        #If we only have 5 measurements, then drop the highest and lowest values before averaging.
        df_drop_low_and_high_value_by_column(df, 'Voltage')

def process_single_ir_test(df, printout = False):
    #find index of last extry in first step
    #Data_Timestamp_From_Step_Start goes from high back to low - diff is negative.
    df['step_time_diff_single_step'] = df['Data_Timestamp_From_Step_Start'].diff().fillna(0)
    row_index_2nd_step = df['step_time_diff_single_step'].argmin()
    
    
    #split data into 1st step and 2nd step
    df_1 = df.iloc[:row_index_2nd_step]
    df_2 = df.iloc[row_index_2nd_step:]
    
    clean_single_step_data_ir_test(df_1)
    clean_single_step_data_ir_test(df_2)
    
    s1_v = df_1['Voltage'].mean()
    s1_i = df_1['Current'].mean()
    s2_v = df_2['Voltage'].mean()
    s2_i = df_2['Current'].mean()
    
    #r = v/i
    ir = (s2_v - s1_v) / (s2_i - s1_i)
    if printout:
        print("Internal Resistance: {} Ohms, {} mOhms".format(ir, ir*1000))
    
    return ir
    
def process_repeated_ir_test(df, return_type = 'array', printout = False):
    #find index of last entry in first step
    
    #Data_Timestamp_From_Step_Start goes from high back to low - diff is negative.
    df['step_time_diff'] = df['Data_Timestamp_From_Step_Start'].diff().fillna(-1)
    df['internal_resistance_ohms'] = pd.NA
    
    #Need to split up the data into a df for each step.
    #indexes where a new step starts:
    indexes_new_ir_test = df['step_time_diff'].where(df['step_time_diff'] < 0).dropna().iloc[0::2].index.to_numpy()
    indexes_at_current_change = df['step_time_diff'].where(df['step_time_diff'] < 0).dropna().iloc[1::2].index.to_numpy()
    
    for i in range(len(indexes_new_ir_test)-1):
        #get ir
        df_2_steps = df.iloc[indexes_new_ir_test[i]:indexes_new_ir_test[i+1]].copy()
        ir_step = process_single_ir_test(df_2_steps)
        
        #put it in the right spot in the df
        df['internal_resistance_ohms'].iloc[indexes_at_current_change[i]] = ir_step
    
    if printout:
        print(df['internal_resistance_ohms'].dropna().values)
    
    if return_type == 'df':
        return df
    elif return_type == 'array':
        return df['internal_resistance_ohms'].dropna().values
    
def process_repeated_ir_discharge_test(df, filename, filedir, sub_dirs, cell_name):
    #get index and ir value for each IR test
    df = add_soc_by_coulomb_counting(df)
    df = process_repeated_ir_test(df, return_type = 'df')
    
    #remove NaN values in IR
    df.dropna(inplace=True)
    #remove everything except soc and ir values
    df_soc_ir = df[['soc', 'internal_resistance_ohms']]
    
    #Plot IR vs SoC
    fig, ax = plt.subplots()
    fig.set_size_inches(7, 8)
    ax.plot('soc', 'internal_resistance_ohms', data = df_soc_ir, linewidth=2)
    fig.suptitle('{} IR vs SoC'.format(cell_name), fontsize =24)
    ax.set_xlim(1, 0) #high SoC at left, low SoC at right
    ax.set_ylabel('Internal Resistance (Ohms)', fontsize =20)
    ax.set_xlabel('State of Charge', fontsize =20)
    plt.xticks(fontsize = 20)
    plt.yticks(fontsize = 20)
    plt.tick_params(size = 10, width = 1)

    ax.xaxis.grid(which='both')
    ax.yaxis.grid(which='both')
    
    #Modify file names for saving graphs and other files
    filename_SoC_IR = 'SoC-IR ' + filename
    
    #Create directory names to store graphs etc.
    filepath_SoC_IR = os.path.join(filedir, sub_dirs[1], filename_SoC_IR)	
    filepath_SoC_IR_graph = os.path.join(filedir, sub_dirs[0], filename_SoC_IR)
    
    #export csv and png for graph
    df_soc_ir.to_csv(filepath_SoC_IR, index=False)
    plt.savefig(os.path.splitext(filepath_SoC_IR_graph)[0], bbox_inches='tight', dpi = 600)

def process_soc_ocv_test(df_charge, df_discharge, cell_name, sub_dirs, filedir, log_date, log_time):
    df_charge = add_soc_by_coulomb_counting(df_charge, charging=True)
    #need to reverse to have increasing SoC for np.interp
    df_discharge_before_reverse = add_soc_by_coulomb_counting(df_discharge)
    df_discharge = df_discharge_before_reverse.iloc[::-1] #[df_discharge.columns[::-1]]
    
    #Now we have soc and voltage pairs.
    #Need to match up the soc pairs to a common format and then interpolate/extrapolate and average the two
    soc_points = np.linspace(0, 1, int(100/0.05) + 1).tolist()
    list_points = list()
    for soc in soc_points:
        v_charge = np.interp(soc, df_charge['soc'], df_charge['Voltage'])
        v_discharge = np.interp(soc, df_discharge['soc'], df_discharge['Voltage'])
        v_avg = (v_charge + v_discharge) / 2
        list_points.append({"soc": soc, "Voltage": v_avg, "v_charge": v_charge, "v_discharge": v_discharge})
    df_soc_ocv = pd.DataFrame.from_records(list_points)
    
    #Modify file names for saving graphs and other files
    filename_SoC_OCV = 'SoC-OCV ' + cell_name + ' ' + log_date + ' ' + log_time
    filename_dqdv = 'dQdV ' + cell_name + ' ' + log_date + ' ' + log_time
    
    #Create directory names to store graphs etc.
    filepath_SoC_OCV = os.path.join(filedir, sub_dirs[1], filename_SoC_OCV)	
    filepath_SoC_OCV_graph = os.path.join(filedir, sub_dirs[0], filename_SoC_OCV)	
    filepath_dqdv_stats = os.path.join(filedir, sub_dirs[1], filename_dqdv)	
    filepath_dqdv_graph = os.path.join(filedir, sub_dirs[0], filename_dqdv)
    
    plot_ica(df_charge, df_discharge_before_reverse, cell_name, filepath_dqdv_graph, filepath_dqdv_stats)
    
    #Plot OCV vs SoC
    fig, ax = plt.subplots()
    fig.set_size_inches(8, 7)
    ax.plot('soc', 'Voltage', data = df_soc_ocv, linewidth = 2)
    fig.suptitle('{} OCV vs SoC'.format(cell_name), fontsize =24)
    ax.set_xlim(1, 0) #high SoC at left, low SoC at right
    ax.set_ylabel('Open Circuit Voltage (V)', fontsize =20)
    ax.set_xlabel('State of Charge', fontsize =20)
    plt.xticks(fontsize = 20)
    plt.yticks(fontsize = 20)
    plt.tick_params(size = 10, width = 1)
    
    ax.xaxis.grid(which='both')
    ax.yaxis.grid(which='both')
    
    
    
    #Save csv and png
    df_soc_ocv.to_csv(filepath_SoC_OCV, index = False)
    plt.savefig(os.path.splitext(filepath_SoC_OCV_graph)[0], bbox_inches='tight', dpi = 600)  

def process_rest(df, printout = True):
    #Rest start voltage, end voltage, and average voltage.
    #A rest cycle should have only a single step.
    
    first_voltage = df['Voltage'].iloc[0]
    average_voltage = df['Voltage'].mean()
    last_voltage = df['Voltage'].iloc[-1]
    time_s = df['Data_Timestamp_From_Step_Start'].max()
    
    if printout:
        print("Rest Voltages: First: {} V  Average: {} V  Last: {} V  Time: {} s".format(first_voltage, average_voltage, last_voltage, time_s))
    
    return (first_voltage, average_voltage, last_voltage, time_s)

def add_soc_by_coulomb_counting(df, charging=False):
    #We know for a full cycle, we start with a full charge and end with a full discharge
    df['SecsFromLastTimestamp'] = df['Data_Timestamp'].diff().fillna(0)
    df['Capacity_Ah_Step'] = df['Current'] * df['SecsFromLastTimestamp'] / 3600
    total_capacity = df['Capacity_Ah_Step'].sum()
    df['Capacity_Ah_Up_To'] = df['Capacity_Ah_Step'].cumsum()
    if charging:
        df['soc'] = df['Capacity_Ah_Up_To'] / total_capacity
    else:
        df['soc'] = 1 - (df['Capacity_Ah_Up_To'] / total_capacity)
    return df

def parse_filename(filename):
    filename_parts = filename.split()
    if len(filename_parts) == 3:
        cell_name = filename_parts[0]
        log_date = filename_parts[1]
        log_time = filename_parts[2]
        cycle_type = "Standard_Charge-Discharge_Cycle"
        cycle_display = "Step"
    elif len(filename_parts) == 4:
        cell_name = filename_parts[0]
        cycle_type = filename_parts[1]
        log_date = filename_parts[2]
        log_time = filename_parts[3]
        cycle_display = "Step"
    elif len(filename_parts) == 5:
        cell_name = filename_parts[0]
        cycle_type = filename_parts[1]
        cycle_display = filename_parts[2]
        log_date = filename_parts[3]
        log_time = filename_parts[4]
        
    return cell_name, cycle_type, log_date, log_time, cycle_display

if __name__ == '__main__':
    
    message = "Do you want to process all files in a directory or select files yourself?"
    title = "File Location"
    choices = ["Directory", "Files"]
    choice = eg.buttonbox(message, title, choices)
    if choice == None:
        quit()
    elif choice == "Files":
        filepaths = FileIO.get_multiple_filepaths()
    elif choice == "Directory":
        filepaths = list()
        for root, dirs, files in os.walk(FileIO.get_directory()):
            for name in files:
                if os.path.splitext(name)[1] == ".csv":
                    filepaths.append(os.path.join(root, name))
    
    #Are there temperature logs associated?
    temp_log_dir = None
    separate_temps = eg.ynbox(title = "Temperature Logs",
                                msg = "Are there separate temperature logs associated with these discharge logs\n" + 
                                        "created by the A2D Electronics 64CH DAQ?")
    if(separate_temps):
        #get the temps file location
        temp_log_dir = FileIO.get_directory("Choose the directory that contains the temp logs")
    
    #Are these 2 files meant for SoC-OCV tracking?
    soc_ocv = eg.ynbox(title = "SoC-OCV Test",
                       msg = "Are these 2 files for SoC-OCV Testing?\n" + 
                             "Only include the charge and discharge files")
                       
    show_discharge_graphs = False  #eg.ynbox(title = "Discharge Graphs",
                                   #  msg = "Show the discharge plots?")
    show_ica_graphs = False #eg.ynbox(title = "ICA Graphs",
                            #   msg = "Show the ICA plots?")
    
    #ensure that all directories exist
    filedir = os.path.dirname(filepaths[0])
    sub_dirs = ['Graphs', 'Stats', 'Temperature Graphs']
    if separate_temps: sub_dirs.append('Split Temperature Logs')
    for sub_dir in sub_dirs:
        FileIO.ensure_subdir_exists_dir(filedir, sub_dir)
    
    #go through each voltage log and check it
    if soc_ocv:
        if len(filepaths) != 2:
            print("Please Choose 2 Files!")
            sys.exit()
        if "Charge" in filepaths[0] and "Discharge" in filepaths[1]:
            filepath_charge = filepaths[0]
            filepath_discharge = filepaths[1]
        elif "Charge" in filepaths[1] and "Discharge" in filepaths[0]:
            filepath_charge = filepaths[1]
            filepath_discharge = filepaths[0]
        else:
            print("Please select a Charge and a Discharge file!")
            sys.exit()
            
        #Now we have the charge and discharge files.
        df_charge = pd.read_csv(filepath_charge)
        df_discharge = pd.read_csv(filepath_discharge)
        
        
        filedir = os.path.dirname(filepath_charge)
        filename_charge = os.path.split(filepath_charge)[-1] 
        cell_name, cycle_type, log_date, log_time, cycle_display = parse_filename(filename_charge)
        process_soc_ocv_test(df_charge, df_discharge, cell_name, sub_dirs, filedir, log_date, log_time)
        
    
    for filepath in filepaths:
        print(f"Log File: {os.path.split(filepath)[-1]}")
        
        filedir = os.path.dirname(filepath)
        filename = os.path.split(filepath)[-1]  
            
        cell_name, cycle_type, log_date, log_time, cycle_display = parse_filename(filename)

        df = pd.read_csv(filepath)
        
        #THIS ALL HAPPENS FOR A STANDARD CHARGE-DISCHARGE CYCLE
        if  cycle_type == "Standard_Charge-Discharge_Cycle" or \
            cycle_type == "Single_CC_Cycle" or \
            cycle_type == "One_Setting_Continuous_CC_Cycles_With_Rest" or \
            cycle_type == "Two_Setting_Continuous_CC_Cycles_With_Rest" or \
            cycle_type == "CC_Charge_Only" or \
            cycle_type == "CC_Discharge_Only":
            
            process_standard_charge_discharge_cycle(filedir, filename, sub_dirs, df, separate_temps, temp_log_dir, show_ica_graphs, show_discharge_graphs)
        
        elif cycle_display == "Single_IR_Test": #Prints out an IR value
            process_single_ir_test(df, printout = True)
        
        elif cycle_display == "Repeated_IR_Test": #Prints out array with IR values
            process_repeated_ir_test(df, printout = True)
        
        elif cycle_display == "Repeated_IR_Discharge_Test": #Creates a csv with SoC and IR
            process_repeated_ir_discharge_test(df, filename, filedir, sub_dirs, cell_name)
            
        elif cycle_display == "Rest": #Prints out first, last and average voltages of the rest period
            process_rest(df, printout = True)
        