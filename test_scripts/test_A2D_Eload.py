#run this test from the test_equipment_control directory using the command:
#python -m test_scripts.test_A2D_Eload
import equipment as eq
import time

eload = eq.eLoads.choose_eload()[1]

#set output current to a low value and print v,i,t.
eload.toggle_output(True)
eload.set_current(10)

try:
    start_time = time.time()
    while time.time() - start_time < (10*60):
        temp_c = eload.measure_temperature()
        volt_v = eload.measure_voltage_supply()
        curr_a = eload.measure_current()
        ctrl_a = eload.measure_current_control()

        print(f"temp: {temp_c}  volt: {volt_v}  curr: {curr_a}  ctrl: {ctrl_a}")
        time.sleep(1)
    eload.toggle_output(False)
    print("Test Complete")
except KeyboardInterrupt:
    eload.toggle_output(False)
    print("Closing")
    exit()
