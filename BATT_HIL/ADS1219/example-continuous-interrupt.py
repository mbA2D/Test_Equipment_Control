from machine import Pin
from machine import I2C
from ads1219 import ADS1219
import utime

#
# Example for Espressif ESP32 microcontroller
#
# This example demonstrates how to use the ADS1219 in continuous conversion mode 
# The DRDY output pin of the ADS1219 is wired to a GPIO input pin on the ESP32.  
# DRDY indicates when each ADC conversion has completed
#
# The falling edge of the DRDY pin indicates that a new conversion result is ready for retrieval.
# An ESP32 GPIO pin can be configured to trigger an interrupt on each falling 
# edge of DRDY.  When DRDY falls an interrupt service routine (ISR) is called.
# The ISR uses I2C to read the conversion result from the ADC.
#
# This is an efficient way to use the ADC.  The processor does
# not need to repeatedly poll the ADC to detect that a conversion has completed
#
# In this example, isr_callback() runs every time DRDY indicates that a conversion is done.
# The read_data_irq() method reads the ADC using I2C to retrieve the conversion result
# read_data_irq() is similar to read_data() but is optimized
# for operation in an interrupt service routine
#
# here is the REPL output that is generated when this example is run.
# output shows the 24-bit conversion result and the result converted to mV 
#
#    enabling DRDY interrupt
#    result = 6640930, mV = 1621.32
#    result = 6656388, mV = 1625.09
#    < ... 18 more results...>
#    irq_count = 20
#

def isr_callback(arg):
    global irq_count
    result = adc.read_data_irq()
    print('result = {}, mV = {:.2f}'.format(result, 
            result * ADS1219.VREF_INTERNAL_MV / ADS1219.POSITIVE_CODE_RANGE))  
    irq_count += 1

i2c = I2C(scl=Pin(26), sda=Pin(27))
adc = ADS1219(i2c)
adc.set_channel(ADS1219.CHANNEL_AIN0)
adc.set_conversion_mode(ADS1219.CM_CONTINUOUS)
adc.set_gain(ADS1219.GAIN_1X)
adc.set_data_rate(ADS1219.DR_20_SPS)  # 20 SPS is the most accurate
adc.set_vref(ADS1219.VREF_INTERNAL)
drdy_pin = Pin(34, mode=Pin.IN)
adc.start_sync() # starts continuous sampling
irq_count = 0

# enable interrupts
print("enabling DRDY interrupt")
irq = drdy_pin.irq(trigger=Pin.IRQ_FALLING, handler=isr_callback)

# from this point onwards the ADS1219 will pull the DRDY pin
# low whenever an ADC conversion has completed.  The ESP32
# will detect this falling edge on the GPIO pin (pin 34 in this 
# example) which will cause the isr_callback() routine to run. 

# The ESP32 will continue to process interrupts and call
# isr_callback() during the following one second of sleep time.
# The ADS1219 is configured for 20 conversions every second, so
# the ISR will be called 20x during this second of sleep time.  
utime.sleep(1)
# disable interrupt by specifying handler=None
irq = drdy_pin.irq(handler=None)
print('irq_count =', irq_count)