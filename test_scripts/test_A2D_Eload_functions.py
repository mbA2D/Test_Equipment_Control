#run this test from the test_equipment_control directory using the command:
#python -m test_scripts.test_A2D_Eload_functions

import equipment as eq
import time

eload = eq.eLoads.choose_eload()[1]

def test_toggle_output():
    eload.toggle_output(False)
    #check to make sure it turned off
    if eload.get_output() != False:
        print("test_toggle_output: eload output did not turn off 1")
        return False
    
    eload.toggle_output(True)
    #check to make sure it turned on
    if eload.get_output() != True:
        print("test_toggle_output: eload output did not turn on")
        return False
    
    eload.toggle_output(False)
    #check to make sure it turned off
    if eload.get_output() != False:
        print("test_toggle_output: eload output did not turn off 2")
        return False
    
    print("test_toggle_output: PASS")
    return True

def test_watchdog():
    #turn output on 
    eload.toggle_output(True)

    #check to make sure it turned on
    if eload.get_output() != True:
        print("test_watchdog: eload output did not turn on")
        return False

    #wait longer than the watchdog period
    time.sleep(11)

    #check to see if the output turned off
    if eload.get_output() != False:
        print("test_watchdog: eload output did not turn off due to watchdog")
        return False
    
    eload.toggle_output(False)

    print("test_watchdog: PASS")
    return True

def test_set_led():
    eload.set_led(False)
    
    if eload.get_led() != False:
        print("test_set_led: LED did not turn off 1")
        return False

    eload.set_led(True)

    if eload.get_led() != True:
        print("test_set_led: LED did not turn on")
        return False
    
    eload.set_led(False)

    if eload.get_led() != False:
        print("test_set_led: LED did not turn off 2")
        return False
    
    print("test_set_led: PASS")
    return True

def test_set_rs485_addr():
    existing_rs485_addr = eload.get_rs485_addr()
    eload.set_rs485_addr(existing_rs485_addr + 2)

    if eload.get_rs485_addr() != (existing_rs485_addr + 2):
        print("test_set_rs485_addr: failed to set rs485 address")
        return False
    
    eload.reset()

    if eload.get_rs485_addr() != existing_rs485_addr:
        print("test_set_rs485_addr: failed to set rs485_addr back to original")
        return False

    print("test_set_rs485_addr: PASS")
    return True

def test_save_rs485_addr():
    #get address, change it, save it, reset, check it, set it back
    existing_rs485_addr = eload.get_rs485_addr()

    eload.set_rs485_addr(existing_rs485_addr + 1)
    eload.save_rs485_addr()

    eload.reset()

    if eload.get_rs485_addr() != (existing_rs485_addr + 1):
        print("test_save_rs485_addr: failed to keep address after reset")
        return False
    
    eload.set_rs485_addr(existing_rs485_addr)
    eload.save_rs485_addr()

    eload.reset()

    if eload.get_rs485_addr() != (existing_rs485_addr):
        print("test_save_rs485_addr: failed to change rs485 address back to original")
        return False
    
    print("test_save_rs485_addr: PASS")
    return True

def test_set_current():
    current_setpoint_tolerance = 0.005 #5mA
    target_current = 4.0

    i_cal = eload.get_cal_i()
    i_offset = i_cal[0]
    i_gain = i_cal [1]

    #test positive values
    eload.set_current(target_current)

    #measure_current (returns negative)
    if abs(eload.measure_current() + target_current) > current_setpoint_tolerance:
        print(f"test_set_current: positive set - measure_current too far out of spec: {abs(eload.measure_current() + target_current)}")
        return False

    #test negative values
    eload.set_current(-target_current)

    #measure_current (returns negative)
    if abs(eload.measure_current() + target_current) > current_setpoint_tolerance:
        print("test_set_current: negative set - measure_current too far out of spec")
        return False

    #measure_current_control (retunrs negative) - make sure it matches with calibration
    control_voltage = eload.measure_current_control()
    eload_current = (control_voltage - i_offset) * i_gain
    if abs(eload_current + target_current) > current_setpoint_tolerance:
        print(f"test_set_current: measure_current_control did not produce correct result: {abs(eload_current + target_current)}")
        return False

    print("test_set_current: PASS")
    return True

def test_reset():
    #get default values (calibration, R485)
    eload.reset()
    default_rs485 = eload.get_rs485_addr()
    default_cal_v = eload.get_cal_v()
    default_cal_i = eload.get_cal_i()
    
    #change a bunch of things - RS485, calibration, output, current
    eload.calibrate_voltage(0.1, 1.0, 0.5, 10.0)
    eload.calibrate_current(0.25, 1.1, 2.5, 10.5)
    eload.set_rs485_addr(3)
    eload.toggle_output(True)
    eload.set_current(3.0)

    #do a reset
    eload.reset()

    #make sure they are back to EEPROM values
    if eload.get_output() != False:
        print("test_reset: error turning output OFF")
        return False
    if abs(eload.measure_current()) > 0.005:
        print("test_reset: error resetting current target to 0")
        return False
    if eload.get_rs485_addr() != default_rs485:
        print("test_reset: error resetting rs485_addr")
        return False
    if eload.get_cal_v() != default_cal_v:
        print("test_reset: error resetting voltage calibration")
        return False
    if eload.get_cal_i() != default_cal_i:
        print("test_reset: error resetting current calibration")
        return False
        
    print("test_reset: PASS")
    return True

def test_fan_control():
    #turn eload on and wait for temp to get up to 42
    eload.toggle_output(True)
    eload.set_current(8.0)

    print("test_fan_control: waiting for temp to rise to 42")
    eload_temp = eload.measure_temperature()
    while(eload_temp < 42):
        time.sleep(5)
        eload_temp = eload.measure_temperature()
        print(f"test_fan_control: eload_temp {eload_temp}")

    #make sure fan turned on
    if eload.get_fan() != True:
        print("test_fan_control: failed to turn fan on")
        eload.toggle_output(False)
        return False
    
    #turn output off so it stops heating
    eload.toggle_output(False)

    #wait for temp under 38
    print("test_fan_control: waiting for temp to fall to 38")
    eload_temp = eload.measure_temperature()
    while(eload_temp > 38):
        time.sleep(5)
        eload_temp = eload.measure_temperature()
        print(f"test_fan_control: eload_temp {eload_temp}")

    #make sure fan turned off
    if eload.get_fan() != True:
        print("test_fan_control: failed to turn fan off")
        return False
    
    print("test_fan_control: PASS")
    return True

def test_calibration():
    default_i_cal = eload.get_cal_i()
    default_v_cal = eload.get_cal_v()

    cal_val_tol = 0.001

    target_offset = -0.1
    target_gain = 12.75

    dut_val_2 = 0.3
    dmm_val_2 = target_offset + dut_val_2 / target_gain
    dut_val_1 = 0.2
    dmm_val_1 = (dut_val_1 - dut_val_2) / target_gain + dmm_val_2

    #voltage
    eload.calibrate_voltage(-dut_val_1, dmm_val_1, -dut_val_2, dmm_val_2)

    v_cal = eload.get_cal_v()
    if (abs(v_cal[0] - target_offset) > cal_val_tol):
        print(f"test_calibration: voltage offset calibration not correct: {v_cal[0]}")
        eload.reset()
        return False
    
    if (abs(v_cal[1] - target_gain) > cal_val_tol):
        print(f"test_calibration: voltage gain calibration not correct: {v_cal[1]}")
        eload.reset()
        return False

    #current
    eload.calibrate_current(dut_val_1, dmm_val_1, dut_val_2, dmm_val_2)

    i_cal = eload.get_cal_i()
    if (abs(i_cal[0] - target_offset) > cal_val_tol):
        print("test_calibration: current offset calibration not correct")
        eload.reset()
        return False
    
    if (abs(i_cal[1] - target_gain) > cal_val_tol):
        print("test_calibration: current gain calibration not correct")
        eload.reset()
        return False

    eload.reset()
    print("test_calibration: PASS")
    return True

def test_set_current_over_max():
    target_current = 12.0
    eload.set_current(target_current)
    if abs(eload.measure_current()) > 10.1:
        print("test_set_current_over_max: failed to cut off target current at max")
        return False
    
    print("test_set_current_over_max: PASS")
    return True

try:
    #assert test_set_led() == True
    #assert test_set_rs485_addr() == True
    #assert test_save_rs485_addr() == True
    #assert test_set_current() == True
    #assert test_reset() == True
    #assert test_toggle_output() == True
    #assert test_set_current() == True
    #assert test_watchdog() == True
    assert test_calibration() == True
    assert test_set_current_over_max() == True
    assert test_fan_control() == True
    
except (KeyboardInterrupt, AssertionError):
    eload.toggle_output(False)
    print("Test Failed Closing")
    exit()
