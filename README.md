# Test_Equipment_Control
Controlling Various Lab Test Equipment

TODO List
 - DONE - Flush queues after and before idle control cycle
	- Will cause issues with multiple channels accessing the same queues?
 - GraphIV.py - Single IR Processing - if we have enough data points for each step, apply some statistical processing (drop outliers, try and account for capacity)
 - There are way too many queues and processes in the MainWindow. Consolidate them and make a better messaging system
 - Allow adding another cycle to test configuration GUI - e.g. Rest then Single IR Test
 - Make 'charge_discharge_control' file into a class
 - Double-check commands where possible? e.g. send output on command, then check status of output.
 - View equipment connections and change settings per instrument instead of having to setup everything again - e.g. remote sense.
 - Create a 'remove channel' button
 - DONE - Show fake equipment even when no resources are available
 - Make GUIs better with drop-downs and checkboxes
    - PSU, Eload, DMM selections should all happen on a single page with a dropdown for each equipment type.
	- Step cycles should have dropdowns for all text fields instead of requiring to know what goes there (voltage_v, current_a, etc.)
 - DONE - Common equipment selection template - instead of a for loop and if statements in each device file
 - Add a way to get output state of all equipment so we can remove redundant disable and waits.
 - DONE - Make all instruments 'virtual' - e.g. controlled globally and not by the individual battery test channel processes. This opens the door to scheduled use of equipment, sharing between channels, and using all channels of multi channel devices.
 - Create safety limits for extra measurement devices - e.g. cell monitors on multi-cell battery packs, temperature sensors.
 - Make a way to add temperature control of the ambient temp through heaters - heaters will have external controller, just need to pass setpoint.
 - DONE - cell logs go in a folder with the cell name
 - DONE - Separate safety conditions for each channel from end cycle conditions
 - Create a way to 'simulate a cell', connect multiple pieces of 'fake' equipment to a 'battery equivalent circuit'
 - DONE - Add safety conditions to all types of cycles (just make them all use step at the core)
 - DONE - Add a way to show a 'charge' or 'discharge' or 'ir test' instead of just showing 'step'
 - DONE - Change log file name to show which cycle_display name instead of just date, time, and cell name, overall cycle type
 - DONE - Add WARNING on the GUI if a safety setting was hit
 - Show which safety error was hit on GUI instead of needing to search through the logs?
 - Add a button on the GUI to advance to the next cycle or step
 - Add support for range switching of eloads between different cycles (e.g. use 4A range for a 1A discharge and 40A range for 5A discharge).
 - Allow 1 device to have multiple uses (e.g. a relay board and voltage/current/temperature monitor all in one) - will be easier when all equipment is virtual
 - Add features to relay board to define which inputs could connect to which outputs (e.g. share 2 power supplies and 2 eloads between 4 cells). (Board definition file for different relay boards?)
 - Add support for 'scheduling' different cycles when we have relay boards connected - e.g. share an eload and wait for other cell to be done with it.
 - DONE - Add internal resistance test through the step profiles
 - DONE - Add capability to test SoC vs Internal Resistance
 - Properly synchronize voltage and current measurements (only available on certain equipment). - Low Priority
 - finish adding ICA: smooth data before analysis
 - HPPC test profile creation gui
 - DONE - Add parallel eloads ability to draw more power
 - DONE - Add ability to control and interact with the A2D DAQ
 - DONE - create auto-recognizing equipment profiles
      - DONE - choose instruments based on IDN? response instead of visa resource name.
      - DONE - Save equipment connections to a json file
 - DONE - change charge and discharge to have the psu or eload passed in to the function
 - DONE - add multiple end conditions (time, current, voltage) to each step
 - DONE - charge/discharge profiles from a file
 - DONE - Add ability to choose different voltage measurement equipment (e.g. DMM instead of eload or PSU for voltage).
 - DONE - Add ability to choose different current measurement equipment
 - DONE - use multiple processes to have multiple tests running at the same time
 - DONE - Add support for a current profile - or a number of steps
 - DONE - Add 'safety limits' for voltage, time, current
 - DONE - Ensure Step functions use minimal equipment - e.g. only power supply when charging or only eload when discharging.


## Setup:
### Prerequisites:
 - Tested with Python 3.9.10 (https://www.python.org/downloads/release/python-3910/)
 - Keysight Instrument Control Bundle (https://www.keysight.com/ca/en/lib/software-detail/computer-software/keysight-instrument-control-bundle-download-1184883.html)
 - You might also need to download NI VISA (https://www.ni.com/en-ca/support/downloads/drivers/download.ni-visa.html#460225)
 - To install all the required python packages
    - Open a command line in the Test_Equipment_Control folder and run "pip install -r requirements.txt"
 - You may need to install libusb (backend for pyusb): https://github.com/pyusb/pyusb/issues/120#issuecomment-322058585

We also need to comment out a few lines in the included libraries from adafruit.  
1. Find where the python packages get installed ("Users->UserName->AppData->Local->Programs->Python->Python39->Lib->site-packages" for me, not using a virtual environment) and find the folder adafruit_blinka->microcontroller->mcp2221  
2. Adafruit packages are amazing, but this one tries to create an object and creates an error when it can't find an mcp2221 device.  
3. In the file "mcp2221.py", comment out the last line "#mcp2221 = MCP2221()" that tries to create the object.  
4. In the file "i2c.py", comment out the first line "#from .mcp2221 import mcp2221" that tries to import that object that was created.  

### Testing Connection:
To make sure that your computer can see the devices you connect, run Keysight Connection Expert and see which devices are available.  
You can open the Interactive IO and send the query "\*IDN?" to get the device's identification.  
If Keysight Connection Expert can see it, then the drivers are installed and you should be able to connect from the python script.  
	
## Running Tests:
### Testing Batteries:
Run '__battery_test.py__' from command line.  
1. File->Scan resources
    - This checks all the backends for available equipment. Some equipment previously connected to but not available now may be recognized.
2. File->Connect to equipment
    - Choose the type and model of equipment that you want to connect to. Fake equipment is available for playing around with the software.
3. Assign Equipment to channel
    - Equipment that you have previously connected to will be available to assign to the channel.
    - An 'idle_test' will be started that will measure voltage and current using the connected equipment.
    - Ensure voltage shown matches the battery voltage expected (if one is connected).
4. Configure Test
    - If any of the safety settings are exceeded, then the test will stop.
5. Start Test  
    - The 'idle_test' that was running will be stopped and the configured test will start.
    - The test can be manually stopped at any time with the 'Stop Test' button.

The setups and tests can be exported and imported (.json format) for easy reconfiguration when restarting the software.  

See the results with GraphIV.py. Graphs and stats (capacity_ah, capacity _wh, max temperature, etc.) for each cycle can be generated.  

### Testing DC-DC Converters  
Run '__dc_dc_test.py__' from command line  
- Allows setting up a test with psu on input, eload on output.  
- Sweeps a range of output currents and a range of input voltages.  

An efficiency graph can be generated from the data with DC_DC_Graph.py    

### Testing solar panels by sweeping an e-load in CV mode  
Run '__Eload_cv_sweep.py__' from command line  
See results (solar panel IV curve with MPP marked) with Eload_cv_sweep.py  

### Quick measurements with a DMM
Run '__Measurement_Script.py__' from command line.  
Choose to measure voltage, current, or temperature, the number of measurements to take, and the delay before starting the measurements.  
Measurements will be printed out in the console.  


TODO List Graveyard
 - DONE - Create an 'add channel' button
 - DONE - Repeated IR Discharge Test: Fix charge safety time, add rest after discharge
