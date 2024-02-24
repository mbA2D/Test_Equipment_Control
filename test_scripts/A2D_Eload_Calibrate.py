#run this test from the test_equipment_control directory using the command:
#python -m test_scripts.test_A2D_Eload
import equipment as eq
import time

eload = eq.eLoads.choose_eload()[1]

print(eload.get_cal_i())

eload.calibrate_current(0.5037, 0.1245, 5.0618, 1.25)
eload.cal_i_save()

print(eload.get_cal_i())
