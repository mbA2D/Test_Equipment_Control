# Test_Equipment_Control
Controlling Various Lab Test Equipment



TODO List
 - finish adding ICA: smooth data before analysis
 - create auto-recognizing equipment profiles
      - DONE - choose instruments based on IDN? response instead of visa resource name.
      - Save equipment connections to a json file
 - DONE - change charge and discharge to have the psu or eload passed in to the function
 - DONE - add multiple end conditions (time, current, voltage) to each step
 - charge/discharge profiles from a file
     - HPPC test profile
 - DONE - Add ability to choose different voltage measurement equipment (e.g. DMM instead of eload or PSU for voltage).
 - DONE - Add ability to choose different current measurement equipment
 - Properly synchronize voltage and current measurements (only available on certain equipment).
 - DONE - use multiple processes to have multiple tests running at the same time
 - DONE - Add support for a current profile - or a number of steps
 - DONE - Add 'safety limits' for voltage, time, current
 - DONE - Ensure Step functions use minimal equipment - e.g. only power supply when charging or only eload when discharging.
