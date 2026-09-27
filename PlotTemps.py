"""Plot temperature channels embedded in a battery-test log."""

import matplotlib.pyplot as plt
import os


def plot_temps(df, save_filepath='', show_graph=True, suffix=''):
    if df.size == 0:
        return

    time_column = 'Test Time / s'
    temperature_columns = [
        column for column in df.columns
        if column.startswith('Surface Temperature ') and column.endswith(' / degC')
    ]
    if time_column not in df.columns:
        raise ValueError(f'Temperature data is missing required column: {time_column}')
    if not temperature_columns:
        return

    fig, ax_temps = plt.subplots()
    fig.set_size_inches(12, 10)

    num_colors = len(temperature_columns)
    cm = plt.get_cmap('tab20')
    ax_temps.set_prop_cycle(
        'color', [cm(1.0 * i / num_colors) for i in range(num_colors)])

    for temp_name in temperature_columns:
        location = temp_name.removeprefix('Surface Temperature ').removesuffix(' / degC')
        ax_temps.plot(time_column, temp_name, data=df, label=location)

    title = 'Temperature log'
    if suffix != '':
        title += ' {}'.format(suffix)

    fig.suptitle(title)
    ax_temps.set_ylabel('Temperature (Celsius)')
    ax_temps.set_xlabel('Seconds from Start of Test (S)')
    fig.legend(loc='upper right')
    ax_temps.grid(b=True, axis='both')

    if save_filepath != '':
        plt.savefig(os.path.splitext(save_filepath)[0])

    if show_graph:
        plt.show()
    else:
        plt.close()
