#Quick and dirty python script to read a voltage a bunch of times

import equipment as eq
import time
import easygui as eg

def main():
    dmm = eq.dmms.choose_dmm()[1]
    channel = None
    try:
        channel = eq.choose_channel(dmm.num_channels, dmm.start_channel)
    except AttributeError:
        pass
    
    choices = ['voltage', 'current', 'temperature']
    msg = "What do you want to measure?"
    title = "Measurement Type"
    measurement_type = eg.choicebox(msg = msg, title = title, choices = choices)
    
    msg = "How Many Measurements to perform?"
    title = "Number of Measurements"
    num_measurements = int(eg.enterbox(msg = msg, title = title, default = 10, strip = True))

    msg = "How many seconds to delay between measurements?"
    title = "Between Measurement Delay"
    delay_s_between = float(eg.enterbox(msg = msg, title = title, default = 0.1, strip = True))

    msg = "How many seconds to delay before starting to measure?"
    title = "Pre-Measurement Delay"
    delay_s_before_start = int(eg.enterbox(msg = msg, title = title, default = 5, strip = True))

    time.sleep(delay_s_before_start)

    for i in range(num_measurements):
        if measurement_type == 'voltage':
            if channel is not None:
                voltage = dmm.measure_voltage(channel)
            else:
                voltage = dmm.measure_voltage()
            print(voltage)
        elif measurement_type == 'current':
            if channel is not None:
                current = dmm.measure_current(channel)
            else:
                current = dmm.measure_current()
            print(current)
        elif measurement_type == 'temperature':
            if channel is not None:
                temperature = dmm.measure_temperature(channel)
            else:
                temperature = dmm.measure_temperature()
            print(temperature)
        time.sleep(delay_s_between)

if __name__ == '__main__':
    main()
