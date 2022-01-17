#Test Program for the PCA9539 IO Expander

import board
from community_pca9539 import PCA9539
import time


i2c = board.I2C()
expander = PCA9539(i2c)

# Read the configuration of all 16 pins
# 0 = output, 1 = input
in_or_out = expander.configuration_ports
print("Configuration\n{:016b}".format(in_or_out))

# Read the polarity inversion state of all 16 pins
polarity_inversion = expander.polarity_inversions
print("Polarity inversion\n{:016b}".format(polarity_inversion))

# Read the input state of all 16 pins
input_state = expander.input_ports
print("Input state\n{:016b}".format(input_state))

# Read the output state of all 16 pins
# At power up, this defaults to 1111111111111111
output_state = expander.output_ports
print("Output state\n{:016b}".format(output_state))


#configure pin as output
configuration_port_0_pin_2 = False #Output

while True:
    #blink an output and print the state
    
    expander.output_port_0_pin_2 = True
    print("Set 1")
    time.sleep(0.5)
    value = expander.input_port_0_pin_2
    print("Read {}".format(value))
    
    expander.output_port_0_pin_2 = False
    print("Set 0")
    time.sleep(0.5)
    value = expander.input_port_0_pin_2
    print("Read {}".format(value))
    
    print("\n")
    