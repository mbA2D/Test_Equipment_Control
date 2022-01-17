#test to read voltage, current, temperature, and charge

import time
import board
import LTC2944

import adafruit_tca9548a

i2c = board.I2C()

print("Scan I2C {}".format([hex(x) for x in i2c.scan()]))

tca = adafruit_tca9548a.TCA9548A(i2c)

print("Scan I2C TCA {}".format([hex(x) for x in tca[2].scan()]))

#gauge = LTC2944.LTC2944(i2c)
gauge = LTC2944.LTC2944(tca[2])
gauge.RSHUNT = 0.002 #Set 2mOhm Shunt Resistance
gauge.adc_mode = LTC2944.LTC2944_ADCMode.AUTO #Continuous conversions.
gauge.prescaler = LTC2944.LTC2944_Prescaler.PRESCALER_1

while True:
    print(
        "Current: %.4f A  Voltage: %.4f V  Temp: %.2f C  Charge: %X"
        % (gauge.get_current_a(), gauge.get_voltage_v(), \
           gauge.get_temp_c(), gauge.charge)
    )
    time.sleep(0.1) #should be enough time to get a new reading every time
