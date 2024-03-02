target_offset = -0.1
target_gain = 3.4

dut_val_2 = 0.3
dmm_val_2 = target_offset + dut_val_2 / target_gain
dut_val_1 = 0.2
dmm_val_1 = (dut_val_1 - dut_val_2) / target_gain + dmm_val_2

_v_scaling = (dut_val_2 - dut_val_1) / (dmm_val_2 - dmm_val_1) #rise in actual / run in measured
_v_offset = dmm_val_2 - (1/_v_scaling) * dut_val_2

print(_v_offset)
print(_v_scaling)
