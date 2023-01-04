#importing and exporting settings to json files
import easygui as eg
from os import path
import json
import pandas as pd

##################### Checking User Input ##############
def check_user_entry(keys, entries, valid_strings):
    if(entries == None):
        return False
    
    entry_dict = dict(zip(keys, entries))
    
    for key in entry_dict:
        if not is_entry_valid(key, entry_dict[key], valid_strings):
            return False
    
    return True

def is_entry_valid(key, value, valid_strings):
    try:
        float(value)
        return True
    except ValueError:
        try:
            if value in valid_strings[key]:
                return True
        except (AttributeError, KeyError):
            return False
        return False
    return False

def convert_to_float(settings):
    #if possible, convert items to floats
    for key in settings:
        try:
            settings[key] = float(settings[key])
        except ValueError:
            pass
    return settings
    
def convert_keys_to_int(settings):
    settings = {int(k):v for k,v in settings.items()}
    return settings

def force_extension(filename, extension):
    #Checking the file type
    file_root, file_extension = path.splitext(filename)
    if(file_extension != extension):
        file_extension = extension
    file_name = file_root + file_extension
    return file_name
    
def get_extension(filename):
    name, ext = path.splitext(filename)
    return ext


####################### Getting Input from User #######################

def update_settings(settings, new_value_list):
    #assuming an ordered response list
    #a bit hacky but it should work
    index = 0
    for key in settings.keys():
        settings.update({key: new_value_list[index]})
        index += 1
    
    return settings

def export_cycle_settings(settings, cycle_name = ""):
    #add extra space to get formatting correct
    if (cycle_name != ""):
        cycle_name += " "
    
    #get the file to export to
    file_name = eg.filesavebox(msg = "Choose a File to export {}settings to".format(cycle_name),
                                title = "Settings", filetypes = ['*.json', 'JSON files'])
    
    if file_name == None:
        return
    
    #force file name extension
    file_name = force_extension(file_name, '.json')
    
    #export the file
    with open(file_name, "w") as write_file:
        json.dump(settings, write_file, indent = 4)

def import_multi_step_from_csv():
    file_name = eg.fileopenbox(msg = "Choose a File to import step settings from",
                                title = "Settings", filetypes = ['*.csv', 'CSV files'])
    
    if file_name == None:
        return None
        
    df = pd.read_csv(file_name)
    settings_list = df.to_dict(orient = 'records')
    return settings_list

def import_cycle_settings(cycle_name = "", queue = None, ch_num = None):
    #add extra space to get formatting correct
    if (cycle_name != ""):
        cycle_name += " "
    
    #get the file to import from
    file_name = eg.fileopenbox(msg = "Choose a File to import {}settings from".format(cycle_name),
                                title = "Settings", filetypes = [['*.json', 'JSON files'],['*.csv', 'CSV files']])
    
    if file_name == None:
        return None
    
    settings = None
    
    #import the file
    if(file_name != None):
        #determine the file type - JSON or CSV
        extension = get_extension(file_name)
        if extension == '.json':
            with open(file_name, "r") as read_file:
                settings = json.load(read_file)
        elif extension == '.csv':
            df = pd.read_csv(file_name)
            settings = df.to_dict(orient = 'records')[0]

    if queue != None:
        settings = {'ch_num': ch_num, 'cdc_input_dict': settings}
        queue.put_nowait(settings)
    else:
        return settings

def get_cycle_settings(settings, valid_strings = None, cycle_name = ""):
    
    if(cycle_name != ""):
        cycle_name += " "
    
    response = eg.buttonbox(msg = "Would you like to import settings for {}cycle or create new settings?".format(cycle_name),
                                    title = "Settings for {}cycle".format(cycle_name), choices = ("New Settings", "Import Settings"))
    if response == None:
        return None
    
    elif response == "New Settings":
        valid_entries = False
        while not valid_entries:
            response_list = eg.multenterbox(msg = "Enter Info for {}cycle".format(cycle_name), title = response,
                                            fields = list(settings.keys()), values = list(settings.values()))
            if response_list == None:
                return None
            valid_entries = check_user_entry(list(settings.keys()), response_list, valid_strings)
        
        #update dict entries with the response - can't use the dict.update since we only have a list here.
        settings = update_settings(settings, response_list)
        
        if (eg.ynbox(msg = "Would you like to save these settings for future use?", title = "Save Settings")):
            export_cycle_settings(settings, cycle_name)
    elif response == "Import Settings":
        settings = import_cycle_settings(cycle_name)
    
    settings = convert_to_float(settings)
    
    return settings
