#Quick and dirty python script to read a voltage a bunch of times

import equipment as eq
import time
import easygui as eg

def main():
    psu = eq.powerSupplies.choose_psu()[1]
    psu.set_current(1)
    psu.set_voltage(3.25)
    print(psu.get_output())
    psu.toggle_output(True)
    print(psu.get_output())
    psu.toggle_output(False)


if __name__ == '__main__':
    main()
