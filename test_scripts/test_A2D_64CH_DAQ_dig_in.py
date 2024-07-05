#run this test from the test_equipment_control directory using the command:
#python -m test_scripts.test_A2D_64CH_DAQ_dig_in
import equipment as eq
import time

dmm = eq.dmms.choose_dmm()[1]

num_readings = 100
num_channels = 64

start_time = time.time()
time_list = list()
for i in range(num_readings):
    s_time = time.time()
    dig_val = dmm.get_dig_in(channel = 10)
    time_list.append(time.time() - s_time)
end_time = time.time()

start_channel_time = time.time()
for i in range(num_channels):
    dig_val = dmm.get_dig_in(channel = i)
end_channel_time = time.time()

print(f"total_time: {end_time - start_time}s")
print(f"avg_time_single: {sum(time_list) / len(time_list)}s")
print(f"read_all_channels: {end_channel_time - start_channel_time}s")
