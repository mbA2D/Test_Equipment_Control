import board
from adafruit_pca9685 import PCA9685

i2c = board.I2C()

print("Scan I2C {}".format([hex(x) for x in i2c.scan()]))

pca = PCA9685(i2c, address=0x60)
pca.frequency = 250
pca.channels[0].duty_cycle = 0xFFFF
