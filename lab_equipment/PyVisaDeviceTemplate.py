#Class to have all device selection have a common area instead of repeated in each device class.

import pyvisa
import easygui as eg
import serial
import time
from .PSU_BK9100 import BK9100 #Since this doesn't have an IDN command, need a special way of dealing with it

class PyVisaDevice:
    selection_window_title = "PyVisa Device Selection"
    
    connection_settings = {
        'pyvisa_backend':           '@py',
        'time_wait_after_open':     0,
        'idn_available':            True
    }
    
    def __init__(self, resource_id = None, resources_list = None):
        rm = pyvisa.ResourceManager(self.connection_settings['pyvisa_backend'])
        
        if(resource_id == None):
        
            if resources == None:
                resources = rm.list_resources()
            else:
                #resources should be all the resources that have the same backend as this.
                resources = [resource['resource'] for resource in resources_list if resource['backend'] == self.connection_settings['pyvisa_backend']]

            ################# IDN VERSION #################
            #Attempt to connect to each Visa Resource and get the IDN response
            if(len(resources) == 0):
                resource_id = 0
                print("No PyVisa Resources Available. Connection attempt will exit with errors")
            idns_dict = {}
            for resource in resources:
                try:
                    instrument = rm.open_resource(resource)
                    time.sleep(self.connection_settings['time_wait_after_open'])
                    
                    #Instrument settings
                    try:
                        instrument.baud_rate = self.connection_settings['baud_rate']
                    except KeyError:
                        pass
                    
                    try:
                        instrument.read_termination = self.connection_settings['read_termination']
                    except KeyError:
                        pass
                        
                    try:
                        instrument.query_delay = self.connection_settings['query_delay']
                    except KeyError:
                        pass
                        
                    try:
                        instrument.write_termination = self.connection_settings['write_termination']
                    except KeyError:
                        pass
                    
                    try:
                        instrument.chunk_size = self.connection_settings['chunk_size']
                    except KeyError:
                        pass
                        
                    try:
                        instrument.timeout = self.connection_settings['timeout']
                    except KeyError:
                        pass
                    
                    #Get IDN and add to dict
                    if self.connection_settings['idn_available']:
                        instrument_idn = instrument.query("*IDN?")
                        idns_dict[resource] = instrument_idn
                    else:
                        if isinstance(self, BK9100):
                            try:
                                instrument.query("GOUT") #try to get something from the instrument
                                instrument.query("") #clear output buffer
                                idns_dict[resource] = resource
                            except (pyvisa.errors.VisaIOError, PermissionError, serial.serialutil.SerialException):
                                pass
                        else:
                            idns_dict[resource] = resource
                    
                    #Close connection
                    instrument.close()
                except (pyvisa.errors.VisaIOError, PermissionError, serial.serialutil.SerialException):
                    pass
                    
            #Now we have all the available resources that we can connect to, with their IDNs.
            resource_id = 0
            idn = None
            if(len(idns_dict.values()) == 0):
                print("No Equipment Available. Connection attempt will exit with errors")
            elif(len(idns_dict.values()) == 1):
                msg = "There is only 1 Visa Equipment available.\nWould you like to use it?\n{}".format(list(idns_dict.values())[0])
                if(eg.ynbox(msg, self.selection_window_title)):
                    idn = list(idns_dict.values())[0]
            else:
                msg = "Select the PyVisaDevice Resource:"
                idn = eg.choicebox(msg, self.selection_window_title, idns_dict.values())
            #Now we know which IDN we want to connect to
            #swap keys and values and then connect
            if idn != None:
                resources_dict = dict((v,k) for k,v in idns_dict.items())
                resource_id = resources_dict[idn]
            else:
                print("No Device Selected. Exiting.")
                return
        
        
        #Now we know the resource ID (no matter what type of device)
        self.inst = rm.open_resource(resource_id)
        time.sleep(self.connection_settings['time_wait_after_open'])
        
        try:
            self.inst.baud_rate = self.connection_settings['baud_rate']
        except KeyError:
            pass
        
        try:
            self.inst.read_termination = self.connection_settings['read_termination']
        except KeyError:
            pass
            
        try:
            self.inst.query_delay = self.connection_settings['query_delay']
        except KeyError:
            pass
            
        try:
            self.inst.write_termination = self.connection_settings['write_termination']
        except KeyError:
            pass
        
        try:
            self.inst.chunk_size = self.connection_settings['chunk_size']
        except KeyError:
            pass
            
        try:
            instrument.timeout = self.connection_settings['timeout']
        except KeyError:
            pass
        
        if self.connection_settings['idn_available']:
            self.inst_idn = self.inst.query("*IDN?")
            print("Connected to {}\n".format(self.inst_idn))
        
        self.initialize() #Specific initialization for each device
    
    def initialize(self):
        pass
    
            
class PowerSupplyDevice(PyVisaDevice):
    selection_window_title = "Power Supply Selection"
    
class EloadDevice(PyVisaDevice):
    selection_window_title = "Eload Selection"
    
class DMMDevice(PyVisaDevice):
    selection_window_title = "DMM Selection"