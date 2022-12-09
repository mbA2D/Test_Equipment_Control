# Test_Equipment_Control
Controlling Various Lab Test Equipment

TODO List
 - DONE - Add internal resistance test through the step profiles
 - DONE - Add capability to test SoC vs Internal Resistance
 - Properly synchronize voltage and current measurements (only available on certain equipment).
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
 - Testing Batteries  
    - battery_test.py  
    - See the results with GraphIV.py   
 - Testing DC-DC Converters  
    - dc_dc_test.py  
    - See results (efficiency graph) with DC_DC_Graph.py  
 - Testing solar panels by sweeping an e-load in CV mode  
    - Eload_cv_sweep.py  
    - See results (solar panel IV curve with MPP marked) with Eload_cv_sweep.py  
