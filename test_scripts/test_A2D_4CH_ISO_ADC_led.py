#run this test from the test_equipment_control directory using the command:
#python -m test_scripts.test_A2D_4CH_ISO_ADC_led
import equipment as eq
import time

num_readings = 100

dmm = eq.dmms.choose_dmm()[1]

start_time = time.time()
time_list = list()
for i in range(num_readings):
    s_time = time.time()
    dig_val = dmm.get_rs485_addr()
    time_list.append(time.time() - s_time)
end_time = time.time()

print(f"total_time: {end_time - start_time}s")
print(f"avg_time_single: {sum(time_list) / len(time_list)}s")
