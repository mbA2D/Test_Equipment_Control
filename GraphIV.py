"""Post-process battery test logs and generate diagnostic plots."""

import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import sys

import FileIO
import PlotTemps
import Templates
from battery_gui import dialogs

from battery_app.bdf_output import read_metadata, validate_bdf_dataframe


TEST_TIME = 'Test Time / s'
VOLTAGE = 'Voltage / V'
CURRENT = 'Current / A'
UNIX_TIME = 'Unix Time / s'
CYCLE_COUNT = 'Cycle Count / 1'
STEP_COUNT = 'Step Count / 1'
STEP_ID = 'Step ID'
STEP_TIME = 'Step Time / s'

CHARGING_CAPACITY = 'Cycle Charging Capacity / Ah'
DISCHARGING_CAPACITY = 'Cycle Discharging Capacity / Ah'
CHARGING_ENERGY = 'Cycle Charging Energy / Wh'
DISCHARGING_ENERGY = 'Cycle Discharging Energy / Wh'


def _require_columns(dataframe, required_columns, context):
    """Raise ``ValueError`` when a processing input lacks required columns."""
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        missing = ', '.join(missing_columns)
        raise ValueError(f'{context} is missing required column(s): {missing}')


def load_bdf_metadata(filepath):
    """Load the paired JSON-LD metadata, returning an empty mapping if absent."""
    try:
        return read_metadata(filepath)
    except FileNotFoundError:
        return {}


def load_bdf_file(filepath):
    """Read a BDF CSV without renaming or mutating its source columns."""
    dataframe = pd.read_csv(filepath)
    _require_columns(dataframe, [TEST_TIME, VOLTAGE, CURRENT], 'BDF data')

    project_report = validate_bdf_dataframe(dataframe, require_fixed_headers=False)
    if not project_report['ok']:
        raise ValueError(f'Project BDF validation failed for {filepath}: {project_report}')

    try:
        import bdf
        report = bdf.validate(dataframe, report=False, raise_on_error=False)
        if not report.get('ok', False):
            raise ValueError(f'BDF validation failed for {filepath}: {report}')
    except ImportError:
        # The project-level required-column check remains useful without the
        # optional batterydf dependency.
        pass
    return dataframe, load_bdf_metadata(filepath)


def metadata_test_type(metadata):
    """Return the test/step type recorded in the BDF metadata sidecar."""
    test_metadata = metadata.get('test', {})
    if test_metadata.get('type'):
        return test_metadata['type']
    steps = test_metadata.get('steps', [])
    if steps:
        return steps[0].get('display_name') or steps[0].get('step_type')
    return None


def metadata_cell_name(metadata):
    """Return the cell name recorded in metadata, if available."""
    return metadata.get('cell', {}).get('name')


# TODO: Re-implement incremental-capacity analysis without DiffCapAnalyzer.


def plot_iv(log_data, save_filepath = '', show_graph=False):
    """Plot voltage and current against elapsed test time."""
    _require_columns(
        log_data,
        [TEST_TIME, VOLTAGE, CURRENT],
        'IV plot data')

    fig, ax_volt = plt.subplots()
    fig.set_size_inches(12, 10)

    ax_volt.plot(TEST_TIME, VOLTAGE, data=log_data, color='r')
    
    ax_curr = ax_volt.twinx()
    ax_curr.plot(TEST_TIME, CURRENT, data=log_data, color='b')
    
    fig.suptitle('Cell Cycle Graph')
    ax_volt.set_ylabel(VOLTAGE, color='r')
    ax_curr.set_ylabel(CURRENT, color='b')
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


def calc_capacity(log_data, stats, charge = True):
    """Read directional BDF capacity and energy for one phase."""
    _require_columns(
        log_data,
        [TEST_TIME, VOLTAGE, CURRENT],
        'Capacity calculation data')

    if charge:
        prefix = 'charge'
        mask = log_data[CURRENT] > 0
        capacity_column = CHARGING_CAPACITY
        energy_column = CHARGING_ENERGY
    else:
        prefix = 'discharge'
        mask = log_data[CURRENT] < 0
        capacity_column = DISCHARGING_CAPACITY
        energy_column = DISCHARGING_ENERGY

    dsc_data = log_data.loc[mask].copy()
    if dsc_data.empty:
        print(f"Data for {prefix} does not exist in log")
        return None

    start_time = dsc_data[TEST_TIME].iloc[0]
    end_time = dsc_data[TEST_TIME].iloc[-1]
    end_v = dsc_data[VOLTAGE].iloc[-1]
    total_time = (end_time - start_time) / 3600

    if capacity_column in dsc_data.columns and energy_column in dsc_data.columns:
        capacity_values = pd.to_numeric(dsc_data[capacity_column], errors='coerce').dropna()
        energy_values = pd.to_numeric(dsc_data[energy_column], errors='coerce').dropna()
        capacity_ah = capacity_values.iloc[-1] if not capacity_values.empty else 0.0
        capacity_wh = energy_values.iloc[-1] if not energy_values.empty else 0.0
    else:
        # Keep GraphIV usable with older BDF-like files that lack derived fields.
        elapsed_s = dsc_data[TEST_TIME].diff().fillna(0).clip(lower=0)
        direction_current = dsc_data[CURRENT].abs()
        capacity_ah = (direction_current * elapsed_s / 3600).sum()
        capacity_wh = (direction_current * dsc_data[VOLTAGE] * elapsed_s / 3600).sum()

    representative_current = round(dsc_data[CURRENT].median(), 2)

    print(f'{prefix}:')
    stats.stats[f'{prefix}_capacity_ah'] = capacity_ah
    stats.stats[f'{prefix}_capacity_wh'] = capacity_wh
    stats.stats[f'{prefix}_time_h'] = total_time
    stats.stats[f'{prefix}_current_a'] = representative_current
    stats.stats[f'{prefix}_start_time'] = start_time
    stats.stats[f'{prefix}_end_time'] = end_time
    stats.stats[f'{prefix}_end_v'] = end_v

    temperature_columns = [
        column for column in dsc_data.columns
        if column.startswith('Surface Temperature ') and column.endswith(' / degC')
    ]
    if temperature_columns:
        max_temp = dsc_data[temperature_columns].max().max()
        stats.stats[f'{prefix}_max_temp_c'] = max_temp
        temp_data = dsc_data[[TEST_TIME] + temperature_columns].copy()
        return temp_data

    return None

def dict_to_csv(dict, filepath):
    """Upsert cycle statistics by charge start time."""
    if dict['charge_start_time'] == 0:
        # Use the discharge start when no charge phase was recorded.
        dict['charge_start_time'] = dict['discharge_start_time']
    dict_dataframe = pd.DataFrame(dict, index = [0])
    
    if(os.path.exists(filepath)):
        FileIO.allow_write(filepath)
        dataframe_csv = pd.read_csv(filepath)
        
        try:
            # Replace an existing result for the same cycle.
            matching_index = dataframe_csv.index[dataframe_csv['charge_start_time'] == dict['charge_start_time']].tolist()[0]
            dataframe_csv.drop(matching_index, axis=0, inplace=True)
        except IndexError:
            pass
            
        dict_dataframe = pd.DataFrame(dict, index = [0])
        dict_dataframe = pd.concat([dataframe_csv, dict_dataframe], ignore_index=True)
        
    dict_dataframe.to_csv(filepath, mode='w', header=True, index=False)
    
    FileIO.set_read_only(filepath)

def timestamp_to_cycle_start(df):
    """Return a copy whose BDF test time starts at zero."""
    if not df.empty:
        df = df.copy()
        start_time = df[TEST_TIME].iloc[0]
        df[TEST_TIME] = df[TEST_TIME] - start_time
    return df



def process_standard_charge_discharge_cycle(
        filedir,
        filename,
        sub_dirs,
        cell_name,
        df,
        show_discharge_graphs):
    """Process a standard cycle, including statistics and embedded temperatures."""
    # Build output paths for the cycle plot and statistics.
    filename_graph = 'GraphIV ' + filename
    filename_stats = 'Cycle_Statistics.csv'	
    
    filepath_graph = os.path.join(filedir, sub_dirs[0], filename_graph)
    filepath_stats = os.path.join(filedir, sub_dirs[1], filename_stats)		
    
    # Calculate capacity statistics and persist them.
    cycle_stats = Templates.CycleStats()
    cycle_stats.stats['cell_name'] = cell_name
    
    temps_charge = calc_capacity(df, cycle_stats, charge=True)
    temps_discharge = calc_capacity(df, cycle_stats, charge=False)
    dict_to_csv(cycle_stats.stats, filepath_stats)
    
    # Plot embedded temperature channels when available.
    if temps_charge is not None:
        temps_charge = timestamp_to_cycle_start(temps_charge)
        filename_temp_charge = 'Temps_Charge ' + filename
        filepath_graph_temps_charge = os.path.join(filedir, sub_dirs[2], filename_temp_charge)
        PlotTemps.plot_temps(temps_charge,\
                save_filepath=filepath_graph_temps_charge, show_graph=False, suffix = 'charge')
    if temps_discharge is not None:
        temps_discharge = timestamp_to_cycle_start(temps_discharge)
        filename_temp_discharge = 'Temps_Discharge ' + filename
        filepath_graph_temps_discharge = os.path.join(filedir, sub_dirs[2], filename_temp_discharge)
        PlotTemps.plot_temps(temps_discharge,\
                save_filepath=filepath_graph_temps_discharge, show_graph=False, suffix = 'discharge')
    
    # Plot the IV curve using elapsed time.
    df = timestamp_to_cycle_start(df)
    
    plot_iv(df, save_filepath=filepath_graph, show_graph=show_discharge_graphs)


def df_drop_low_and_high_value_by_column(df, column_label):
    min_index = df[column_label].idxmin()
    max_index = df[column_label].idxmax()
    df.drop(index=[min_index, max_index], inplace=True)

def clean_single_step_data_ir_test(df):
    """Remove startup and outlier samples before averaging an IR step."""
    df.reset_index(inplace=True)
    if df[VOLTAGE].size > 1:
        # Discard the first sample while current may still be settling.
        df.drop(index=0, inplace=True)
    
    if df[VOLTAGE].size >= 10:
        # TODO: extrapolate the settled voltage to the start of the step.
        pass
    elif df[VOLTAGE].size >= 5:
        # Trim one high and one low sample before averaging short steps.
        df_drop_low_and_high_value_by_column(df, VOLTAGE)

def process_single_ir_test(df, printout = False):
    """Calculate resistance from a two-step current transition."""
    _require_columns(
        df,
        [STEP_TIME, VOLTAGE, CURRENT],
        'Single IR test data')

    # A negative timestamp difference marks the transition to the next step.
    df['step_time_diff_single_step'] = df[STEP_TIME].diff().fillna(0)
    row_index_2nd_step = df['step_time_diff_single_step'].argmin()
    
    
    # Separate the two current levels and clean each segment.
    df_1 = df.iloc[:row_index_2nd_step]
    df_2 = df.iloc[row_index_2nd_step:]
    
    clean_single_step_data_ir_test(df_1)
    clean_single_step_data_ir_test(df_2)
    
    s1_v = df_1[VOLTAGE].mean()
    s1_i = df_1[CURRENT].mean()
    s2_v = df_2[VOLTAGE].mean()
    s2_i = df_2[CURRENT].mean()
    
    ir = (s2_v - s1_v) / (s2_i - s1_i)
    if printout:
        print("Internal Resistance: {} Ohms, {} mOhms".format(ir, ir*1000))
    
    return ir
    
def process_repeated_ir_test(df, return_type = 'array', printout = False):
    """Calculate resistance for each transition in a repeated IR test."""
    _require_columns(
        df,
        [STEP_TIME, VOLTAGE, CURRENT],
        'Repeated IR test data')

    # Negative timestamp differences identify step boundaries.
    df['step_time_diff'] = df[STEP_TIME].diff().fillna(-1)
    df['internal_resistance_ohms'] = pd.NA
    
    # Pair the boundaries into individual two-step IR tests.
    indexes_new_ir_test = df['step_time_diff'].where(df['step_time_diff'] < 0).dropna().iloc[0::2].index.to_numpy()
    indexes_at_current_change = df['step_time_diff'].where(df['step_time_diff'] < 0).dropna().iloc[1::2].index.to_numpy()
    
    for i in range(len(indexes_new_ir_test)-1):
        df_2_steps = df.iloc[indexes_new_ir_test[i]:indexes_new_ir_test[i+1]].copy()
        ir_step = process_single_ir_test(df_2_steps)
        
        # Store the result at the current-transition row.
        df.loc[indexes_at_current_change[i], 'internal_resistance_ohms'] = ir_step
    
    if printout:
        print(df['internal_resistance_ohms'].dropna().values)
    
    if return_type == 'df':
        return df
    elif return_type == 'array':
        return df['internal_resistance_ohms'].dropna().values
    
def process_repeated_ir_discharge_test(df, filename, filedir, sub_dirs, cell_name):
    """Generate an IR-versus-SoC report for a repeated discharge test."""
    df = add_soc_by_coulomb_counting(df)
    df = process_repeated_ir_test(df, return_type = 'df')
    
    # Keep only rows containing a calculated resistance.
    df.dropna(inplace=True)
    # Export only the two report columns.
    df_soc_ir = df[['soc', 'internal_resistance_ohms']]
    
    # Plot resistance against state of charge.
    fig, ax = plt.subplots()
    fig.set_size_inches(7, 8)
    ax.plot('soc', 'internal_resistance_ohms', data = df_soc_ir, linewidth=2)
    fig.suptitle('{} IR vs SoC'.format(cell_name), fontsize =24)
    ax.set_xlim(1, 0)  # Display high SoC on the left.
    ax.set_ylabel('Internal Resistance (Ohms)', fontsize =20)
    ax.set_xlabel('State of Charge', fontsize =20)
    plt.xticks(fontsize = 20)
    plt.yticks(fontsize = 20)
    plt.tick_params(size = 10, width = 1)

    ax.xaxis.grid(which='both')
    ax.yaxis.grid(which='both')
    
    # Build output paths for the report and plot.
    filename_SoC_IR = 'SoC-IR ' + filename
    
    filepath_SoC_IR = os.path.join(filedir, sub_dirs[1], filename_SoC_IR)	
    filepath_SoC_IR_graph = os.path.join(filedir, sub_dirs[0], filename_SoC_IR)
    
    #export csv and png for graph
    df_soc_ir.to_csv(filepath_SoC_IR, index=False)
    plt.savefig(os.path.splitext(filepath_SoC_IR_graph)[0], bbox_inches='tight', dpi = 600)

def process_soc_ocv_test(df_charge, df_discharge, cell_name, sub_dirs, filedir, log_date, log_time):
    """Create an averaged SoC-OCV curve from charge and discharge logs."""
    df_charge = add_soc_by_coulomb_counting(df_charge, charging=True)
    # Reverse discharge data so interpolation receives increasing SoC values.
    df_discharge_before_reverse = add_soc_by_coulomb_counting(df_discharge)
    df_discharge = df_discharge_before_reverse.iloc[::-1]
    
    # Interpolate both curves onto a common SoC grid, then average them.
    soc_points = np.linspace(0, 1, int(100/0.05) + 1).tolist()
    list_points = list()
    for soc in soc_points:
        v_charge = np.interp(soc, df_charge['soc'], df_charge[VOLTAGE])
        v_discharge = np.interp(soc, df_discharge['soc'], df_discharge[VOLTAGE])
        v_avg = (v_charge + v_discharge) / 2
        list_points.append({"soc": soc, VOLTAGE: v_avg, "v_charge": v_charge, "v_discharge": v_discharge})
    df_soc_ocv = pd.DataFrame.from_records(list_points)
    
    # Build the output path for the SoC-OCV result.
    filename_SoC_OCV = 'SoC-OCV ' + cell_name + ' ' + log_date + ' ' + log_time
    
    filepath_SoC_OCV = os.path.join(filedir, sub_dirs[1], filename_SoC_OCV)	
    filepath_SoC_OCV_graph = os.path.join(filedir, sub_dirs[0], filename_SoC_OCV)	
    
    # Plot the averaged OCV curve.
    fig, ax = plt.subplots()
    fig.set_size_inches(8, 7)
    ax.plot('soc', VOLTAGE, data=df_soc_ocv, linewidth=2)
    fig.suptitle('{} OCV vs SoC'.format(cell_name), fontsize =24)
    ax.set_xlim(1, 0)  # Display high SoC on the left.
    ax.set_ylabel('Open Circuit Voltage (V)', fontsize =20)
    ax.set_xlabel('State of Charge', fontsize =20)
    plt.xticks(fontsize = 20)
    plt.yticks(fontsize = 20)
    plt.tick_params(size = 10, width = 1)
    
    ax.xaxis.grid(which='both')
    ax.yaxis.grid(which='both')
    
    
    
    # Save the data and plot.
    df_soc_ocv.to_csv(filepath_SoC_OCV, index = False)
    plt.savefig(os.path.splitext(filepath_SoC_OCV_graph)[0], bbox_inches='tight', dpi = 600)  

def process_rest(df, printout = True):
    _require_columns(
        df,
        [STEP_TIME, VOLTAGE],
        'Rest data')

    # A rest period should contain one step.
    
    first_voltage = df[VOLTAGE].iloc[0]
    average_voltage = df[VOLTAGE].mean()
    last_voltage = df[VOLTAGE].iloc[-1]
    time_s = df[STEP_TIME].max()
    
    if printout:
        print("Rest Voltages: First: {} V  Average: {} V  Last: {} V  Time: {} s".format(first_voltage, average_voltage, last_voltage, time_s))
    
    return (first_voltage, average_voltage, last_voltage, time_s)

def add_soc_by_coulomb_counting(df, charging=False):
    """Add cumulative capacity and state-of-charge fields to a test log."""
    _require_columns(
        df,
        [TEST_TIME, CURRENT],
        'SoC calculation data')

    df = df.copy()
    elapsed_s = df[TEST_TIME].diff().fillna(0).clip(lower=0)
    capacity_ah_step = df[CURRENT].abs() * elapsed_s / 3600
    total_capacity = capacity_ah_step.sum()
    cumulative_capacity = capacity_ah_step.cumsum()
    if total_capacity == 0:
        df['soc'] = 0.0
        return df
    if charging:
        df['soc'] = cumulative_capacity / total_capacity
    else:
        df['soc'] = 1 - (cumulative_capacity / total_capacity)
    return df

def parse_filename(filename):
    """Parse legacy and BDF-style measurement filenames.

    BDF filenames use ``Institution__Cell__YYYYMMDD_XXX.bdf.csv``.  The
    sequence is the persistent cycle number; cycle-local step identifiers
    come from the BDF data columns, while the
    metadata sidecar supplies the test type and cell details when available.
    """
    if filename.endswith('.bdf.csv'):
        bdf_parts = filename[:-len('.bdf.csv')].split('__')
        if len(bdf_parts) == 3:
            _institution, cell_name, date_sequence = bdf_parts
            date_parts = date_sequence.split('_', 1)
            if (
                _institution
                and cell_name
                and len(date_parts) == 2
                and len(date_parts[0]) == 8
                and date_parts[0].isdigit()
                and date_parts[1].isdigit()
            ):
                return (
                    cell_name,
                    "Standard_Charge-Discharge_Cycle",
                    date_parts[0],
                    date_parts[1],
                    "Step",
                )

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
    else:
        raise ValueError(
            'Unexpected log filename format. Expected 3, 4, or 5 space-separated parts: '
            f'{filename}')

    return cell_name, cycle_type, log_date, log_time, cycle_display

if __name__ == '__main__':
    
    message = "Do you want to process all files in a directory or select files yourself?"
    title = "File Location"
    choices = ["Directory", "Files"]
    choice = dialogs.ask_buttons(message, title, choices)
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
    
    # Ask whether the selected files form a SoC-OCV pair.
    soc_ocv = dialogs.ask_yes_no(
        "Are these 2 files for SoC-OCV Testing?\nOnly include the charge and discharge files",
        "SoC-OCV Test",
    )
                       
    show_discharge_graphs = False
    
    # Ensure output directories exist before processing files.
    filedir = os.path.dirname(filepaths[0])
    sub_dirs = ['Graphs', 'Stats', 'Temperature Graphs']
    for sub_dir in sub_dirs:
        FileIO.ensure_subdir_exists_dir(filedir, sub_dir)
    
    # Process each selected voltage log.
    if soc_ocv:
        if len(filepaths) != 2:
            print("Please Choose 2 Files!")
            sys.exit()
        first_type = metadata_test_type(load_bdf_metadata(filepaths[0])) or filepaths[0]
        second_type = metadata_test_type(load_bdf_metadata(filepaths[1])) or filepaths[1]
        if "charge" in first_type.lower() and "discharge" in second_type.lower():
            filepath_charge = filepaths[0]
            filepath_discharge = filepaths[1]
        elif "charge" in second_type.lower() and "discharge" in first_type.lower():
            filepath_charge = filepaths[1]
            filepath_discharge = filepaths[0]
        else:
            print("Please select a Charge and a Discharge file!")
            sys.exit()
            
        # Load BDF data and use metadata to identify the paired phases.
        df_charge, metadata_charge = load_bdf_file(filepath_charge)
        df_discharge, _metadata_discharge = load_bdf_file(filepath_discharge)
        
        
        filedir = os.path.dirname(filepath_charge)
        filename_charge = os.path.split(filepath_charge)[-1] 
        cell_name, cycle_type, log_date, log_time, cycle_display = parse_filename(filename_charge)
        cell_name = metadata_cell_name(metadata_charge) or cell_name
        process_soc_ocv_test(df_charge, df_discharge, cell_name, sub_dirs, filedir, log_date, log_time)
        
    
    for filepath in filepaths:
        print(f"Log File: {os.path.split(filepath)[-1]}")
        
        filedir = os.path.dirname(filepath)
        filename = os.path.split(filepath)[-1]  
            
        cell_name, cycle_type, log_date, log_time, cycle_display = parse_filename(filename)
        df, metadata = load_bdf_file(filepath)
        cell_name = metadata_cell_name(metadata) or cell_name
        metadata_type = metadata_test_type(metadata)
        if metadata_type:
            cycle_display = metadata_type
            cycle_type = metadata_type
        
        # Process standard charge/discharge cycle variants together.
        if cycle_display not in {
            "Single_IR_Test",
            "Repeated_IR_Test",
            "Repeated_IR_Discharge_Test",
            "Rest",
        }:
            
            process_standard_charge_discharge_cycle(
                filedir,
                filename,
                sub_dirs,
                cell_name,
                df,
                show_discharge_graphs)
        
        elif cycle_display == "Single_IR_Test":  # Print one IR value.
            process_single_ir_test(df, printout = True)
        
        elif cycle_display == "Repeated_IR_Test":  # Print all IR values.
            process_repeated_ir_test(df, printout = True)
        
        elif cycle_display == "Repeated_IR_Discharge_Test":  # Save SoC/IR results.
            process_repeated_ir_discharge_test(df, filename, filedir, sub_dirs, cell_name)
            
        elif cycle_display == "Rest":  # Print rest-period voltage statistics.
            process_rest(df, printout = True)

