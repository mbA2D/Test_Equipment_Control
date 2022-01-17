#Driver for the LTC2944 Coulomb Counter
#Written By: Micah Black
#Date: Oct 1, 2021
#For use with Adafruit's CircuitPython Libraries


from micropython import const
import adafruit_bus_device.i2c_device as i2cdevice

from adafruit_register.i2c_struct import ROUnaryStruct, UnaryStruct
from adafruit_register.i2c_bits import ROBits, RWBits
from adafruit_register.i2c_bit import ROBit, RWBit


# I2C Address and Register Locations
_I2C_ADDRESS = const(0x64)

_REG_STATUS = const(0x00)
_REG_CONTROL = const(0x01)
_REG_ACCUMULATED_CHARGE_MSB = const(0x02)
#_REG_ACCUMULATED_CHARGE_LSB = const(0x03)
_REG_CHARGE_THRESHOLD_HIGH_MSB = const(0x04)
#_REG_CHARGE_THRESHOLD_HIGH_LSB = const(0x05)
_REG_CHARGE_THRESHOLD_LOW_MSB = const(0x06)
#_REG_CHARGE_THRESHOLD_LOW_LSB = const(0x07)
_REG_VOLTAGE_MSB = const(0x08)
#_REG_VOLTAGE_LSB = const(0x09)
_REG_VOLTAGE_THRESHOLD_HIGH_MSB = const(0x0A)
#_REG_VOLTAGE_THRESHOLD_HIGH_LSB = const(0x0B)
_REG_VOLTAGE_THRESHOLD_LOW_MSB = const(0x0C)
#_REG_VOLTAGE_THRESHOLD_LOW_LSB = const(0x0D)
_REG_CURRENT_MSB = const(0x0E)
#_REG_CURRENT_LSB = const(0x0F)
_REG_CURRENT_THRESHOLD_HIGH_MSB = const(0x10)
#_REG_CURRENT_THRESHOLD_HIGH_LSB = const(0x11)
_REG_CURRENT_THRESHOLD_LOW_MSB = const(0x12)
#_REG_CURRENT_THRESHOLD_LOW_LSB = const(0x13)
_REG_TEMPERATURE_MSB = const(0x14)
#_REG_TEMPERATURE_LSB = const(0x15)
_REG_TEMPERATURE_THRESHOLD_HIGH = const(0x16)
_REG_TEMPERATURE_THRESHOLD_LOW = const(0x17)


class LTC2944_ADCMode:
    AUTO = const(0x03) #Continuous conversions of voltage, current, and temp
    SCAN = const(0x02) #Conversions every 10s
    MANUAL = const(0x01) #Single conversion then sleep
    SLEEP = const(0x00) #Sleep

class LTC2944_Prescaler:
    PRESCALER_1 = const(0x00)
    PRESCALER_4 = const(0x01)
    PRESCALER_16 = const(0x02)
    PRESCALER_64 = const(0x03)
    PRESCALER_256 = const(0x04)
    PRESCALER_1024 = const(0x05)
    PRESCALER_4096 = const(0x06)
    PRESCALER_4096_2 = const(0x07)
    
    def get_prescaler(prescaler_enum):
        conv_dict = {
            0: 1,
            1: 4,
            2: 16,
            3: 64,
            4: 256,
            5: 1024,
            6: 4096,
            7: 4096
        }
        return conv_dict[prescaler_enum]
        
class LTC2944_ALCCConf:
    ALERT = const(0x02) #Pin is a logic output for alert functionality
    CC = const(0x01) #Pin is Logic input, accepts active low charge complete signal
    DISABLED = const(0x00) #pin disabled
    #0x03 is not allowed

            

class LTC2944:
    """Driver for the LTC2944 power and current sensor.
    :param ~busio.I2C i2c_bus: The I2C bus the LTC2944 is connected to.
    """
    
    def __init__(self, i2c_bus):
        self.i2c_device = i2cdevice.I2CDevice(i2c_bus, _I2C_ADDRESS)
        
    
    RSHUNT = 0.1 #Set the value of the shunt resistor in Ohms.
    
    #Status Register A
    current_alert = ROBit(_REG_STATUS, 6)
    accum_charge_over_under_flow = ROBit(_REG_STATUS, 5)
    temp_alert = ROBit(_REG_STATUS, 4)
    charge_high_alert = ROBit(_REG_STATUS, 3)
    charge_low_alert = ROBit(_REG_STATUS, 2)
    voltage_alert = ROBit(_REG_STATUS, 1)
    uvlo_alert = ROBit(_REG_STATUS, 0)
    
    #Control Register B
    adc_mode = RWBits(2, _REG_CONTROL, 6)
    prescaler = RWBits(3, _REG_CONTROL, 3)
    alcc_config = RWBits(2, _REG_CONTROL, 1)
    shutdown = RWBit(_REG_CONTROL, 0)
    
    #Accumulated Charge
    charge = UnaryStruct(_REG_ACCUMULATED_CHARGE_MSB, ">H") #Unsigned Short
    charge_thresh_high = UnaryStruct(_REG_CHARGE_THRESHOLD_HIGH_MSB, ">H")
    charge_thresh_low = UnaryStruct(_REG_CHARGE_THRESHOLD_LOW_MSB, ">H")
    
    #Voltage
    _raw_voltage = ROUnaryStruct(_REG_VOLTAGE_MSB, ">H") #Unsigned Short
    volt_thresh_high = UnaryStruct(_REG_VOLTAGE_THRESHOLD_HIGH_MSB, ">H")
    volt_thresh_low = UnaryStruct(_REG_VOLTAGE_THRESHOLD_LOW_MSB, ">H")
    
    #Current
    _raw_current = ROUnaryStruct(_REG_CURRENT_MSB, ">H") #Unsigned Short
    current_thresh_high = UnaryStruct(_REG_CURRENT_THRESHOLD_HIGH_MSB, ">H")
    current_thresh_low = UnaryStruct(_REG_CURRENT_THRESHOLD_LOW_MSB, ">H")
    
    #Temperature
    _raw_temp = ROUnaryStruct(_REG_TEMPERATURE_MSB, ">H") #Unsigned Short
    temp_thresh_high = UnaryStruct(_REG_TEMPERATURE_THRESHOLD_HIGH, ">B") #unsigned Char
    temp_thresh_low = UnaryStruct(_REG_TEMPERATURE_THRESHOLD_LOW, ">B") #unsigned Char
    
    
    #Measurements
    
    def get_current_a(self):
        return self.convert_raw_current(self._raw_current)
        
    def get_voltage_v(self):
        return self.convert_raw_voltage(self._raw_voltage)
        
    def get_temp_c(self):
        return self.convert_raw_temp(self._raw_temp)
    
    
    #Thresholds
    
    def set_current_thresh_high(self, current_a):
        current_thresh_high = self.convert_current(current_a)
        
    def set_current_thresh_low(self, current_a):
        current_thresh_low = self.convert_current(current_a)
    
    def set_voltage_thresh_high(self, voltage_v):
        volt_thresh_high = self.convert_voltage(voltage_v)
    
    def set_voltage_thresh_low(self, voltage_v):
        volt_thresh_low = self.convert_voltage(voltage_v)
    
    def set_temp_thresh_high(self, temp_c):
        temp_thresh_high = self.convert_temp(temp_c)
    
    def set_temp_thresh_low(self, temp_c):
        temp_thresh_low = self.convert_temp(temp_c)
        
    
    #Measurement Conversions to get values
    
    def convert_raw_voltage(self, raw_voltage):
        return 70.8 * raw_voltage / 0xFFFF
    
    def convert_raw_current(self, raw_current):
        return 0.064 / self.RSHUNT * ((raw_current - 0x7FFF)/0x7FFF)
        
    def convert_raw_temp(self, raw_temp):
        return (510*raw_temp/0xFFFF) -273.15
    
    
    #Setting Conversions to set registers
    
    def convert_voltage(self, voltage):
        return voltage/70.8*0xFFFF
        
    def convert_current(self, current):
        return current * self.RSHUNT/0.064*32767 + 32767
        
    def convert_temp(self, temp):
        return ((temp + 273.15)/510*0xFFFF) & 0b11111111 #convert to 8 bits only since regs are 8-bit
    
    
    #Setting Charge Register
    def set_charge(self, set_charge):
        #check analog section power
        analog_off = self.shutdown
        
        if not analog_off:
            #disable analog section
            self.shutdown = True
            
        #set charge
        if 0 <= set_charge <= 0xFFFF:
            self.charge = set_charge
        else:
            print("Charge set is out of bounds")
        
        if not analog_off:
            #re-enable analog section to same state as before call to this function
            self.shutdown = False
        