#contains a list of all the equipment that there are libraries for
#organized into which ones have common function calls

import pyvisa

import queue #For handling queue.Empty error

import time
from battery_app.logging_config import get_logger
from battery_app.simulation import SIMULATED_FAKE_CLASSES


logger = get_logger(__name__)


def _dialogs():
    """Load GUI dialogs only for interactive equipment-selection paths."""
    from battery_gui import dialogs

    return dialogs

#Eloads
from lab_equipment import Eload_BK8600
from lab_equipment import Eload_DL3000
from lab_equipment import Eload_KEL10X
from lab_equipment import Eload_IT8500
from lab_equipment import Eload_PARALLEL
from lab_equipment import Eload_A2D_Eload
from lab_equipment import Eload_Fake

#Power Supplies
from lab_equipment import PSU_DP800
from lab_equipment import PSU_SPD1000
from lab_equipment import PSU_MP71025X
from lab_equipment import PSU_BK9100
from lab_equipment import PSU_N8700
from lab_equipment import PSU_KAXXXXP
from lab_equipment import PSU_E3631A
from lab_equipment import PSU_HP6632B
from lab_equipment import PSU_Fake

#SMUs
from lab_equipment import PSU_A2D_POWER_BOARD

#Digital Multimeters
from lab_equipment import DMM_DM3000
from lab_equipment import DMM_SDM3065X
from lab_equipment import A2D_DAQ_control
from lab_equipment import A2D_DAQ_config #to load config file from csv
from lab_equipment import DMM_A2D_SENSE_BOARD
from lab_equipment import DMM_A2D_4CH_Isolated_ADC
from lab_equipment import DMM_Fake

#Other Equipment
from lab_equipment import OTHER_A2D_Relay_Board
from lab_equipment import OTHER_Arduino_IO_Module
from lab_equipment.PyVisaDeviceTemplate import PyVisaDevice

#Virtual Equipment Management
from lab_equipment.correlated_device import (
    CorrelatedVirtualDevice,
    DmmProxy,
    ElectronicLoadProxy,
    PowerSupplyProxy,
    RelayProxy,
)


# Canonical capability registry. A physical instrument is registered once;
# role-specific menus discover it through these capabilities.
EQUIPMENT_CAPABILITIES = {
    'SPD1000': frozenset({'can_source_voltage', 'can_source_current', 'can_measure_voltage', 'can_measure_current'}),
    'DP800': frozenset({'can_source_voltage', 'can_source_current', 'can_measure_voltage', 'can_measure_current'}),
    'KWR10X or MP71025X': frozenset({'can_source_voltage', 'can_source_current', 'can_measure_voltage', 'can_measure_current'}),
    'BK9100': frozenset({'can_source_voltage', 'can_source_current', 'can_measure_voltage', 'can_measure_current'}),
    'N8700': frozenset({'can_source_voltage', 'can_source_current', 'can_measure_voltage', 'can_measure_current'}),
    'KAXXXXP': frozenset({'can_source_voltage', 'can_source_current', 'can_measure_voltage', 'can_measure_current'}),
    'E3631A': frozenset({'can_source_voltage', 'can_source_current', 'can_measure_voltage', 'can_measure_current'}),
    'HP6632B': PSU_HP6632B.HP6632B.capabilities,
    'Fake Test PSU': frozenset({'can_source_voltage', 'can_source_current', 'can_measure_voltage', 'can_measure_current'}),
    'BK8600': frozenset({'can_sink_current', 'can_measure_voltage', 'can_measure_current'}),
    'DL3000': frozenset({'can_sink_current', 'can_measure_voltage', 'can_measure_current'}),
    'KEL10X': frozenset({'can_sink_current', 'can_measure_voltage', 'can_measure_current'}),
    'IT8500': frozenset({'can_sink_current', 'can_measure_voltage', 'can_measure_current'}),
    'A2D_Eload': frozenset({'can_sink_current'}),
    'Parallel Eloads': frozenset({'can_sink_current', 'can_measure_voltage', 'can_measure_current'}),
    'Fake Test Eload': frozenset({'can_sink_current', 'can_measure_voltage', 'can_measure_current'}),
    'DM3000': frozenset({'can_measure_voltage'}),
    'SDM3065X': frozenset({'can_measure_voltage'}),
    'A2D_DAQ_CH': frozenset({'can_measure_temperature'}),
    'A2D_SENSE_BOARD': frozenset({'can_measure_voltage', 'can_measure_current', 'can_measure_temperature'}),
    'A2D_4CH_Isolated_ADC_Channel': frozenset({'can_measure_voltage'}),
    'A2D_POWER_BOARD': frozenset({
        'can_source_voltage', 'can_source_current', 'can_sink_current',
        'can_measure_voltage', 'can_measure_current', 'can_measure_temperature',
    }),
    'Fake Test DMM': frozenset({'can_measure_voltage', 'can_measure_current', 'can_measure_temperature'}),
    'A2D Relay Board': frozenset({'can_isolate_output'}),
    'Arduino IO Module': frozenset(),
}


def get_capable_equipment(*capabilities):
    """Return registered devices that provide every requested capability."""
    return [
        class_name
        for class_name, device_capabilities in EQUIPMENT_CAPABILITIES.items()
        if all(capability in device_capabilities for capability in capabilities)
    ]


def get_capability_choices(capabilities, fallback_choices):
    """Use capability selection when registered; retain legacy fallback otherwise."""
    choices = get_capable_equipment(*capabilities)
    return choices if choices else list(fallback_choices)


def _create_selected_instrument(driver_class, resource_id, resources_list, probe_only):
    """Construct a driver without device initialization during identity probes."""
    if probe_only and issubclass(driver_class, PyVisaDevice):
        return driver_class(
            resource_id=resource_id,
            resources_list=resources_list,
            initialize=False,
        )
    return driver_class(resource_id=resource_id, resources_list=resources_list)


def _finish_instrument_setup(instrument, setup_dict, interactive, probe_only):
    """Keep probe settings for the owner process without applying them here."""
    if probe_only:
        return setup_instrument(instrument, setup_dict, interactive=False, apply=False)
    return setup_instrument(instrument, setup_dict, interactive=interactive)


# Explicit operation registry. Adding an instrument operation requires adding
# it here and exposing it through the appropriate capability proxy.
_VIRTUAL_DEVICE_METHODS = frozenset({
    'measure_voltage', 'measure_voltage_supply', 'measure_voltage_at_adc',
    'measure_voltage_at_adc_supply', 'measure_current',
    'measure_current_control', 'measure_power', 'measure_temperature',
    'set_current', 'set_voltage', 'set_mode_current', 'set_mode_voltage',
    'set_cv_voltage', 'toggle_output', 'remote_sense', 'lock_front_panel',
    'lock_commands', 'select_channel', 'reset', 'reset_calibration',
    'cal_v_reset', 'cal_i_reset', 'save_calibration', 'cal_v_save',
    'cal_i_save', 'get_calibration', 'get_cal_v', 'get_cal_i',
    'calibrate_voltage', 'calibrate_current', 'connect_psu',
    'connect_eload', 'psu_connected', 'eload_connected', 'get_output',
    'get_current', 'get_voltage', 'get_mode', 'get_fault_status', 'check_status',
    'set_led', 'get_led', 'set_fan', 'get_fan', 'get_num_channels',
    'get_rs485_addr', 'set_rs485_addr', 'save_rs485_addr',
    'set_i2c_expander_addr', 'set_i2c_adc_addr', 'set_i2c_dac_addr',
    'attach_battery_link',
})


def _dispatch_virtual_device_method(device, method_name, method_data, method_kwargs=None):
    if method_name not in _VIRTUAL_DEVICE_METHODS:
        raise ValueError(f"Unsupported virtual-device method: {method_name!r}")

    method = getattr(device, method_name, None)
    if not callable(method):
        raise AttributeError(f"Device does not support virtual-device method: {method_name!r}")

    args = [] if method_data is None else method_data
    if not isinstance(args, list):
        args = [args]
    kwargs = {} if method_kwargs is None else method_kwargs
    if not isinstance(kwargs, dict):
        raise TypeError("Virtual-device keyword arguments must be a dictionary")
    return method(*args, **kwargs)


def _select_assignment_channel(device, assignment_channel):
    """Select a positive canonical assignment channel on a multi-channel driver."""
    if assignment_channel == 0:
        return
    if not isinstance(assignment_channel, int) or isinstance(assignment_channel, bool):
        raise ValueError("Instrument assignment channel must be a non-negative integer")
    if assignment_channel < 0:
        raise ValueError("Instrument assignment channel must be a non-negative integer")
    select_channel = getattr(device, 'select_channel', None)
    if not callable(select_channel):
        raise ValueError(
            f"{type(device).__name__} does not support multi-channel assignments"
        )
    select_channel(assignment_channel)

def choose_channel(num_channels = 64, start_val = 0):
    max_number = num_channels + start_val - 1
    return _dialogs().ask_integer(
        "Which channel on this device would you like to use?",
        "Channel Selection",
        start_val,
        start_val,
        max_number,
    )

#used in create_new_equipment in battery_test.py
def virtual_device_management_process(
    eq_type,
    new_eq_res_id_dict,
    queue_in,
    response_routes,
    startup_result_queue=None,
):
    # - connect to the equipment using the equipment type and the res_id_dict
            # - Then loop:
                # - listen for any messages in queue_in
                    # - take action on messages in queue_in
                # - route responses to the requesting channel
    
    device = None
    try:
        try:
            device = connect_to_eq(
                eq_type,
                new_eq_res_id_dict['class_name'],
                new_eq_res_id_dict['res_id'],
                new_eq_res_id_dict['setup_dict'],
                interactive=False,
            )
            if device is None:
                raise ConnectionError("Equipment driver did not return a connected device")
        except Exception as error:
            if startup_result_queue is not None:
                startup_result_queue.put((False, {
                    "error_type": type(error).__name__,
                    "message": str(error),
                }))
                startup_result_queue.close()
                startup_result_queue.join_thread()
                startup_result_queue = None
            raise

        if startup_result_queue is not None:
            startup_result_queue.put((True, {
                "resource_id": new_eq_res_id_dict['res_id'],
                "eq_idn": getattr(device, 'inst_idn', None),
                "rated_limits": (
                    dict(device.rated_limits)
                    if isinstance(getattr(device, 'rated_limits', None), dict)
                    else None
                ),
            }))
            startup_result_queue.close()
            startup_result_queue.join_thread()
            startup_result_queue = None
        logger.info("Virtual device connected: %s", new_eq_res_id_dict['class_name'])
        last_kick_time = time.time()

        while True:
            try:
                queue_in_message = queue_in.get(timeout=0.1)
            except queue.Empty:
                queue_in_message = None

            if queue_in_message == 'stop':
                return
            if queue_in_message is None:
                pass
            elif isinstance(queue_in_message, dict) and queue_in_message.get('protocol') == 2:
                request_id = queue_in_message.get('request_id')
                if not request_id:
                    continue
                try:
                    operation = queue_in_message['operation']
                    args = queue_in_message.get('args', [])
                    kwargs = queue_in_message.get('kwargs', {})
                    if (
                        operation == 'attach_battery_link'
                        and new_eq_res_id_dict['class_name'] not in SIMULATED_FAKE_CLASSES
                    ):
                        raise ValueError(
                            'Only built-in fake instruments may attach a battery link'
                        )
                    if operation != 'select_channel':
                        _select_assignment_channel(
                            device,
                            queue_in_message.get('instrument_channel', 0),
                        )
                    return_data = _dispatch_virtual_device_method(device, operation, args, kwargs)
                    response = {
                        'protocol': 2,
                        'request_id': request_id,
                        'client_id': queue_in_message.get('client_id'),
                        'ok': True,
                        'value': return_data,
                        'error': None,
                    }
                except Exception as error:
                    logger.exception("Virtual device operation failed: %s", operation)
                    response = {
                        'protocol': 2,
                        'request_id': request_id,
                        'client_id': queue_in_message.get('client_id'),
                        'ok': False,
                        'value': None,
                        'error': {
                            'type': type(error).__name__,
                            'message': str(error),
                        },
                    }
                response_queue = response_routes.get(response['client_id'])
                if response_queue is None:
                    logger.warning("Dropping response without route for client %r", response['client_id'])
                    continue
                response_queue.put_nowait(response)

            if time.time() - last_kick_time > 5:
                try:
                    device.kick()
                except AttributeError:
                    pass
                last_kick_time = time.time()
    finally:
        close = getattr(device, 'close', None)
        if callable(close):
            close()

def get_resources_list():
    """Return resources exposed by the VISA backends available on this host.

    PyVISA-py is the portable backend used on Debian and other Linux hosts.
    The native IVI backend remains useful when a vendor VISA library is
    installed, but it is optional and must not prevent the portable backend
    from being scanned.
    """
    resources_list = []
    backends = ['@py', '@ivi']
    for backend in backends:
        resource_manager = None
        try:
            resource_manager = pyvisa.ResourceManager(backend)
            resource_list = resource_manager.list_resources()
        except (OSError, ValueError, pyvisa.errors.Error) as error:
            logger.warning("VISA backend %s is unavailable; skipping it: %s", backend, error)
            continue
        finally:
            if resource_manager is not None:
                resource_manager.close()

        for resource in resource_list:
            resources_list.append({'resource': resource, 'backend': backend})
    return resources_list
    #How do we know which device settings to use to communicate with it? Try all the settings until we get a legible response from IDN that we can use?

def setup_instrument(instrument, setup_dict, interactive=True, apply=True):
    if setup_dict == None:
        setup_dict = {}
    
    #REMOTE SENSE
    if hasattr(instrument, 'has_remote_sense') and instrument.has_remote_sense:
        if 'remote_sense' not in setup_dict.keys():
            setup_dict['remote_sense'] = None
        
        if setup_dict['remote_sense'] is None:
            #ask to use remote sense
            msg = "Do you want to use remote sense on this instrument?"
            title = "Remote Sense"
            use_remote_sense = _dialogs().ask_yes_no(msg, title) if interactive else False
            setup_dict['remote_sense'] = use_remote_sense
            
        if apply:
            time.sleep(0.5) #Allow the instrument to process commands after initialization.
            instrument.remote_sense(setup_dict['remote_sense'])
    
    #A2D Relay Board Special Setup
    if isinstance(instrument, OTHER_A2D_Relay_Board.A2D_Relay_Board):
        #special setup for this instrument
        #Need to determine if channel has an eload or a psu.
        #Cannot have multiple of the same device yet.

        if 'num_channels' not in setup_dict.keys():
            setup_dict['num_channels'] = instrument.get_num_channels()

        if 'equipment_type_connected' not in setup_dict.keys():
            title = "A2D Relay Board Setup - Connected Equipment"
            choices = ['eload', 'psu', 'none']
            equipment_type_connected = list()
            
            for i in range(setup_dict['num_channels']):
                msg = "What is connected to channel {}?".format(i + 1)
                response = _dialogs().ask_choice(msg, title, choices) if interactive else 'none'
                if response == None:
                    return None
                equipment_type_connected.append(response)
            
            setup_dict['equipment_type_connected'] = equipment_type_connected
        
        if 'i2c_expander_addr' not in setup_dict.keys():
            title = "A2D Relay Board Setup - I2C Expander"
            msg = "Enter I2C Expander Address\n Use 7-bit right-justified hexadecimal\n(e.g. '0x77')"
            response = _dialogs().ask_text(msg, title, '0x74') if interactive else '0x74'
            if response == None:
                return None
            setup_dict['i2c_expander_addr'] = int(response, 16)
            
        if apply:
            instrument.equipment_type_connected = setup_dict['equipment_type_connected']
            instrument.set_i2c_expander_addr(setup_dict['i2c_expander_addr'])
    
    #A2D Sense Board Special Setup
    if isinstance(instrument, DMM_A2D_SENSE_BOARD.A2D_SENSE_BOARD):

        if 'i2c_adc_addr' not in setup_dict.keys():
            title = "A2D Sense Board Setup - I2C ADC"
            msg = "Enter ADC I2C Address\n Use 7-bit right-justified hexadecimal\n(e.g. '0x77')"
            response = _dialogs().ask_text(msg, title, '0x74') if interactive else '0x74'
            if response == None:
                return None
            setup_dict['i2c_adc_addr'] = int(response, 16)
            
        if apply:
            instrument.set_i2c_adc_addr(setup_dict['i2c_adc_addr'])
    
    #A2D Power Board Special Setup
    if isinstance(instrument, PSU_A2D_POWER_BOARD.A2D_POWER_BOARD):

        if 'i2c_adc_addr' not in setup_dict.keys():
            title = "A2D Power Board Setup - I2C ADC"
            msg = "Enter ADC I2C Address\n Use 7-bit right-justified hexadecimal\n(e.g. '0x77')"
            response = _dialogs().ask_text(msg, title, '0x32') if interactive else '0x32'
            if response == None:
                return None
            setup_dict['i2c_adc_addr'] = int(response, 16)
            
        if apply:
            instrument.set_i2c_adc_addr(setup_dict['i2c_adc_addr'])
            
        if 'i2c_dac_addr' not in setup_dict.keys():
            title = "A2D Power Board Setup - I2C DAC"
            msg = "Enter DAC I2C Address\n Use 7-bit right-justified hexadecimal\n(e.g. '0x77')"
            response = _dialogs().ask_text(msg, title, '0x4A') if interactive else '0x4A'
            if response == None:
                return None
            setup_dict['i2c_dac_addr'] = int(response, 16)
            
        if apply:
            instrument.set_i2c_dac_addr(setup_dict['i2c_dac_addr'])
    
    #A2D 64 CH DAQ special setup
    if isinstance(instrument, A2D_DAQ_control.A2D_DAQ):
        if 'config_dict' not in setup_dict.keys() and interactive:
            #Get the config dict and save it in the setup_dict
            setup_dict['config_dict'] = A2D_DAQ_config.get_config_dict()
        setup_dict['config_dict'] = {
            int(key): value for key, value in setup_dict.get('config_dict', {}).items()
        }
        if apply:
            instrument.config_dict = setup_dict['config_dict']
            instrument.configure_from_dict()
    
    return setup_dict

def connect_to_eq(key, class_name, res_id, setup_dict = None, interactive=True):
    #Key should be 'eload', 'psu', 'dmm', 'relay_board'
    #'dmm' with any following characters will be considered a dmm
    instrument = None
    
    if class_name == 'E3631A': time.sleep(1) #testing E3631A and delay for passing equipment between threads
    
    #return the actual equipment object instead of the equipment dictionary
    if key == 'eload':
        instrument = eLoads.choose_eload(class_name, res_id, setup_dict, interactive=interactive)[1]
    elif key == 'psu':
        instrument = powerSupplies.choose_psu(class_name, res_id, setup_dict, interactive=interactive)[1]
    elif 'dmm' in key: #for dmm_i and dmm_v and dmm_t keys
        instrument = dmms.choose_dmm(class_name, resource_id = res_id, setup_dict = setup_dict, interactive=interactive)[1]
    elif key == 'relay_board' or key == 'other':
        instrument = otherEquipment.choose_equipment(class_name, res_id, setup_dict, interactive=interactive)[1]
    elif key == 'smu':
        instrument = smus.choose_smu(class_name, res_id, setup_dict, interactive=interactive)[1]
    time.sleep(0.1)
    return instrument

#Used in get_equipment_dict
def connect_to_virtual_eq(virtual_res_id_dict):
    client_id = virtual_res_id_dict.get('client_id')
    eq_type = virtual_res_id_dict.get('eq_type', '')
    proxy_type = CorrelatedVirtualDevice
    if eq_type == 'psu':
        proxy_type = PowerSupplyProxy
    elif eq_type == 'eload':
        proxy_type = ElectronicLoadProxy
    elif 'dmm' in eq_type:
        proxy_type = DmmProxy
    elif eq_type in {'relay_board', 'other'}:
        proxy_type = RelayProxy
    eq_ch = virtual_res_id_dict.get('eq_ch')
    if not isinstance(eq_ch, int) or isinstance(eq_ch, bool) or eq_ch < 0:
        raise ValueError("Virtual equipment requires a non-negative integer eq_ch")
    proxy = proxy_type(
        virtual_res_id_dict['queue_in'],
        virtual_res_id_dict['response_queue'],
        eq_ch,
        client_id=client_id,
    )
    # Preserve owner-verified identity on the channel proxy for BDF provenance.
    proxy.eq_idn = virtual_res_id_dict.get('eq_idn')
    idn_parts = [part.strip() for part in proxy.eq_idn.split(',')] if isinstance(proxy.eq_idn, str) else []
    proxy.manufacturer = idn_parts[0] if len(idn_parts) >= 3 else None
    proxy.model_number = idn_parts[1] if len(idn_parts) >= 3 else None
    proxy.serial_number = idn_parts[2] if len(idn_parts) >= 3 else None
    proxy.firmware_version = idn_parts[3] if len(idn_parts) >= 4 else None
    proxy.equipment_id = virtual_res_id_dict.get('equipment_id')
    proxy.class_name = virtual_res_id_dict.get('class_name')
    proxy.resource_id = virtual_res_id_dict.get('resource_id')
    proxy.instrument_channel = eq_ch
    return proxy

#used in battery_test.py when connecting to a new piece of equipment
#equipment_list comes from the choose_eload, choose_dmm, etc. functions in equipment.py
'''
eq_list has 3 items: 
    class_name - the instrument class e.g. 'DM3000'
    instrument - the instrument object that communicates with the instrument
    setup_dict - gets passed to the setup_equipment function for special setup
'''
def get_res_id_dict_and_disconnect(eq_list):
    class_name = eq_list[0]
    
    #print(eq_list)
    
    eq_type = getattr(eq_list[1], '_selected_equipment_type', None)
    if eq_type is not None:
        pass
    elif class_name in smus.part_numbers.keys():
        eq_type = 'smu'
    if class_name in otherEquipment.part_numbers.keys():
        if class_name == otherEquipment.part_numbers['A2D Relay Board']:
            eq_type = 'relay_board'
        else:
            eq_type = 'other'
    elif class_name in eLoads.part_numbers.keys():
        eq_type = 'eload'
    elif class_name in powerSupplies.part_numbers.keys():
        eq_type = 'psu'
    elif class_name in dmms.part_numbers.keys():
        eq_type = 'dmm'
    
    eq_idn = None
    try:
        eq_idn = eq_list[1].inst_idn
    except AttributeError:
        pass
    
    eq_res_id_dict = {
        'eq_idn':       eq_idn,
        'eq_type':      eq_type,
        'class_name':   class_name,
        'res_id':       None,
        'setup_dict':   {}
    }
    eq_res_id_dict['capabilities'] = list(
        EQUIPMENT_CAPABILITIES.get(
            class_name,
            getattr(eq_list[1], 'capabilities', ()),
        )
    )
    if class_name == 'Parallel Eloads':
        eq_res_id_dict['res_id'] = {}
        eq_res_id_dict['res_id']['class_name_1'] = eq_list[1].class_name_1
        eq_res_id_dict['res_id']['class_name_2'] = eq_list[1].class_name_2
        try:
            eq_res_id_dict['res_id']['res_id_1'] = eq_list[1].eload1.inst.resource_name
        except AttributeError:
            eq_res_id_dict['res_id']['res_id_1'] = None #For fake instruments
        try:
            eq_res_id_dict['res_id']['res_id_2'] = eq_list[1].eload2.inst.resource_name
        except AttributeError:
            eq_res_id_dict['res_id']['res_id_2'] = None #For fake instruments
        #print('Adding setup_dict to res_id_dict')
        eq_res_id_dict['res_id']['remote_sense_1'] = eq_list[1].use_remote_sense_1
        eq_res_id_dict['res_id']['remote_sense_2'] = eq_list[1].use_remote_sense_2
    elif 'Fake' in class_name:
        eq_res_id_dict['res_id'] = 'Fake'
        eq_res_id_dict['setup_dict'] = eq_list[2]
    else:
        try:
            eq_res_id_dict['res_id'] = eq_list[1].inst.resource_name
            eq_res_id_dict['setup_dict'] = eq_list[2]
        except AttributeError:
            logger.error("No resource ID for instrument")

    instrument_channels = get_instrument_channels(
        class_name,
        eq_list[1],
        eq_res_id_dict['setup_dict'],
    )
    if instrument_channels is not None:
        eq_res_id_dict['instrument_channels'] = instrument_channels
        
    #disconnect from equipment
    try:
        if class_name == 'Parallel Eloads':
            eq_list[1].eload1.inst.close()
            eq_list[1].eload2.inst.close()
        else:
            eq_list[1].inst.close()
    except AttributeError:
        pass #temporary fix for 'virtual and fake instruments' - TODO - figure out a way to do this more properly
    
    return eq_res_id_dict


def get_instrument_channels(class_name, instrument, setup_dict=None):
    """Return canonical assignment channels: singleton ``0`` or multi-channel ``1..N``."""
    setup_dict = setup_dict or {}
    explicit_channels = setup_dict.get('instrument_channels')
    if explicit_channels is not None:
        try:
            count = len([int(channel) for channel in explicit_channels])
        except (TypeError, ValueError):
            count = 0
        return list(range(1, count + 1)) if count else [0]

    known_channels = {
        'DP800': 3,
        'E3631A': 3,
        'A2D_Eload': 32,
        'A2D_DAQ_CH': 64,
        'A2D_4CH_Isolated_ADC_Channel': 4,
    }
    count = known_channels.get(class_name)
    if count is None:
        count = setup_dict.get('num_channels')
    if count is None:
        count = getattr(instrument, 'num_channels', None)
    if count is None:
        count = getattr(instrument, 'max_channels', None)
    if count is None:
        get_num_channels = getattr(instrument, 'get_num_channels', None)
        if callable(get_num_channels):
            try:
                count = get_num_channels()
            except Exception:
                count = None
    try:
        count = int(count)
    except (TypeError, ValueError):
        return [0]
    if count <= 0:
        return [0]
    return list(range(1, count + 1))


#Connect to the equipment and return the handle for the virtual equipment
def get_equipment_dict(res_ids_dict):
    # Execution code uses these canonical roles for optional equipment
    # fallbacks (for example, using the PSU as dmm_v/dmm_i). Keep them present
    # even when a profile assigns only a PSU or E-load.
    eq_dict = {
        role: None
        for role in ("psu", "eload", "dmm_v", "dmm_i", "dmm_t", "relay_board")
    }
    direct_instruments = {}
    direct_resource_classes = {}
    for key in res_ids_dict:
        if res_ids_dict[key] != None and res_ids_dict[key]['res_id'] != None:
            res_id = res_ids_dict[key]['res_id']
            has_virtual_queue = isinstance(res_id, dict) and res_id.get('queue_in') != None
            if has_virtual_queue:
                #This is a virtual equipment that is communicated with through queues.
                virtual_res_id = dict(res_id)
                virtual_res_id['eq_type'] = key
                eq_dict[key] = connect_to_virtual_eq(virtual_res_id)
            else:
                class_name = res_ids_dict[key]['class_name']
                # Standalone scripts use this direct-connection fallback. Reuse
                # the concrete object when the same VISA resource is assigned
                # to multiple roles in one dictionary.
                if isinstance(res_id, str) and res_id != 'Fake':
                    previous_class = direct_resource_classes.get(res_id)
                    if previous_class is not None and previous_class != class_name:
                        raise ValueError(
                            "VISA resource {} was assigned to multiple device classes".format(res_id)
                        )
                    direct_resource_classes[res_id] = class_name
                    if res_id not in direct_instruments:
                        direct_instruments[res_id] = connect_to_eq(
                            key, class_name, res_id, res_ids_dict[key]['setup_dict']
                        )
                    eq_dict[key] = direct_instruments[res_id]
                else:
                    eq_dict[key] = connect_to_eq(
                        key, class_name, res_id, res_ids_dict[key]['setup_dict']
                    )
        else:
            eq_dict[key] = None
    return eq_dict    
    

class otherEquipment:
    part_numbers = {
        'A2D Relay Board': 		'OTHER_A2D_Relay_Board',
        'Arduino IO Module':	'OTHER_Arduino_IO_Module'
    }
        
    @classmethod
    def choose_equipment(self, class_name = None, resource_id = None, setup_dict = None, resources_list = None, interactive=True, probe_only=False):
        if class_name == None:
            msg = "What type of equipment?"
            title = "Equipment Series Selection"
            class_name = _dialogs().ask_choice(msg, title, list(otherEquipment.part_numbers.keys()))

        if class_name == None:
            print("Failed to select the equipment.")
            return			
        
        if class_name == 'A2D Relay Board':
            instrument = _create_selected_instrument(OTHER_A2D_Relay_Board.A2D_Relay_Board, resource_id, resources_list, probe_only)
        elif class_name == 'Arduino IO Module':
            instrument = _create_selected_instrument(OTHER_Arduino_IO_Module.Arduino_IO, resource_id, resources_list, probe_only)
            
        setup_dict = _finish_instrument_setup(instrument, setup_dict, interactive, probe_only)
        if setup_dict == None:
            logger.error("Equipment setup failed")
            return
        return class_name, instrument, setup_dict


class eLoads:
    part_numbers = {
        'BK8600': 			'Eload_BK8600',
        'DL3000': 			'Eload_DL3000',
        'KEL10X': 			'Eload_KEL10X',
        'IT8500': 			'Eload_IT8500',
        'A2D_Eload':        'Eload_A2D_Eload',
        'Parallel Eloads':	'Eload_PARALLEL',
        'Fake Test Eload': 	'Eload_Fake'
    }
        
    @classmethod
    def choose_eload(self, class_name = None, resource_id = None, setup_dict = None, resources_list = None, interactive=True, probe_only=False):
        if class_name == None:
            msg = "In which series is the E-Load?"
            title = "E-Load Series Selection"
            choices = get_capability_choices(
                ('can_sink_current',),
                list(eLoads.part_numbers.keys()) + list(smus.part_numbers.keys()),
            )
            class_name = _dialogs().ask_choice(msg, title, choices)

        if class_name == None:
            print("Failed to select the equipment.")
            return			
        
        if class_name == 'Parallel Eloads' and probe_only:
            raise ValueError("Parallel Eloads do not support non-mutating identity probes")
        if class_name == 'BK8600':
            eload = _create_selected_instrument(Eload_BK8600.BK8600, resource_id, resources_list, probe_only)
        elif class_name == 'DL3000':
            eload = _create_selected_instrument(Eload_DL3000.DL3000, resource_id, resources_list, probe_only)
        elif class_name == 'KEL10X':
            eload = _create_selected_instrument(Eload_KEL10X.KEL10X, resource_id, resources_list, probe_only)
        elif class_name == 'IT8500':
            eload = _create_selected_instrument(Eload_IT8500.IT8500, resource_id, resources_list, probe_only)
        elif class_name == 'A2D_POWER_BOARD':
            eload = _create_selected_instrument(PSU_A2D_POWER_BOARD.A2D_POWER_BOARD, resource_id, resources_list, probe_only)
        elif class_name == 'A2D_Eload':
            eload = _create_selected_instrument(Eload_A2D_Eload.A2D_Eload, resource_id, resources_list, probe_only)
        elif class_name == 'Parallel Eloads':
            eload = Eload_PARALLEL.PARALLEL(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'Fake Test Eload':
            eload = Eload_Fake.Fake_Eload(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'HP6632B':
            eload = PSU_HP6632B.HP6632B(resource_id = resource_id, resources_list = resources_list)
            
        setup_dict = _finish_instrument_setup(eload, setup_dict, interactive, probe_only)
        if setup_dict == None:
            print("Equipment Setup Failed")
            return
        eload._selected_equipment_type = 'eload'
        return class_name, eload, setup_dict


class powerSupplies:
    part_numbers = {
        'SPD1000': 				'PSU_SPD1000',
        'DP800': 				'PSU_DP800',
        'KWR10X or MP71025X': 	'PSU_MP71025X',
        'BK9100': 				'PSU_BK9100',
        'N8700': 				'PSU_N8700',
        'KAXXXXP': 				'PSU_KAXXXXP',
        'E3631A':				'PSU_E3631A',
        'HP6632B':              'PSU_HP6632B',
        'A2D_POWER_BOARD':      'PSU_A2D_POWER_BOARD',
        'Fake Test PSU':        'PSU_Fake'
    }
    
    @classmethod
    def choose_psu(self, class_name = None, resource_id = None, setup_dict = None, resources_list = None, interactive=True, probe_only=False):
        if class_name == None:
            msg = "In which series is the PSU?"
            title = "PSU Series Selection"
            class_name = _dialogs().ask_choice(
                msg,
                title,
                get_capability_choices(
                    ('can_source_voltage',),
                    list(powerSupplies.part_numbers.keys()) + list(smus.part_numbers.keys()),
                ),
            )

        if class_name == None:
            print("Failed to select the equipment.")
            return
        
        if class_name == 'SPD1000':
            psu = _create_selected_instrument(PSU_SPD1000.SPD1000, resource_id, resources_list, probe_only)
        elif class_name == 'DP800':
            psu = _create_selected_instrument(PSU_DP800.DP800, resource_id, resources_list, probe_only)
        elif class_name == 'KWR10X or MP71025X':
            psu = _create_selected_instrument(PSU_MP71025X.MP71025X, resource_id, resources_list, probe_only)
        elif class_name == 'BK9100':
            psu = _create_selected_instrument(PSU_BK9100.BK9100, resource_id, resources_list, probe_only)
        elif class_name == 'N8700':
            psu = _create_selected_instrument(PSU_N8700.N8700, resource_id, resources_list, probe_only)
        elif class_name == 'KAXXXXP':
            psu = _create_selected_instrument(PSU_KAXXXXP.KAXXXXP, resource_id, resources_list, probe_only)
        elif class_name == 'E3631A':
            psu = _create_selected_instrument(PSU_E3631A.E3631A, resource_id, resources_list, probe_only)
        elif class_name == 'HP6632B':
            psu = _create_selected_instrument(PSU_HP6632B.HP6632B, resource_id, resources_list, probe_only)
        elif class_name == 'A2D_POWER_BOARD':
            psu = _create_selected_instrument(PSU_A2D_POWER_BOARD.A2D_POWER_BOARD, resource_id, resources_list, probe_only)
        elif class_name == 'Fake Test PSU':
            psu = PSU_Fake.Fake_PSU(resource_id = resource_id, resources_list = resources_list)
            
        setup_dict = _finish_instrument_setup(psu, setup_dict, interactive, probe_only)
        if setup_dict == None:
            print("Equipment Setup Failed")
            return
        psu._selected_equipment_type = 'psu'
        return class_name, psu, setup_dict


class smus:
    part_numbers = {}
    
    @classmethod
    def choose_smu(self, class_name = None, resource_id = None, setup_dict = None, resources_list = None, interactive=True):
        if class_name == None:
            msg = "In which series is the PSU?"
            title = "PSU Series Selection"
            class_name = _dialogs().ask_choice(msg, title, list(smus.part_numbers.keys()))

        if class_name == None:
            print("Failed to select the equipment.")
            return
        
        if class_name == 'A2D_POWER_BOARD':
            smu = PSU_A2D_POWER_BOARD.A2D_POWER_BOARD(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'HP6632B':
            smu = PSU_HP6632B.HP6632B(resource_id = resource_id, resources_list = resources_list)
            
        setup_dict = setup_instrument(smu, setup_dict, interactive=interactive)
        if setup_dict == None:
            print("Equipment Setup Failed")
            return
        smu._selected_equipment_type = 'smu'
        return class_name, smu, setup_dict
        

class dmms:
    part_numbers = {
        'DM3000': 					        'DMM_DM3000',
        'SDM3065X': 				        'DMM_SDM3065X',
        'A2D_DAQ_CH':				        'A2D_DAQ',
        'A2D_SENSE_BOARD':                  'A2D_SENSE_BOARD',
        'A2D_4CH_Isolated_ADC_Channel':     'A2D_4CH_Isolated_ADC',
        'Fake Test DMM': 			        'DMM_Fake'
    }
    
    @classmethod
    def choose_dmm(self, class_name = None, resource_id = None, multi_ch_event_and_queue_dict = None, setup_dict = None, resources_list = None, interactive=True, probe_only=False):
        if class_name == None:
            msg = "In which series is the DMM?"
            title = "DMM Series Selection"
            choices = get_capability_choices(
                ('can_measure_voltage',),
                list(dmms.part_numbers.keys()) + list(smus.part_numbers.keys()),
            )
            class_name = _dialogs().ask_choice(msg, title, choices)

        if class_name == None:
            print("Failed to select the equipment.")
            return			
        
        if class_name == 'DM3000':
            dmm = _create_selected_instrument(DMM_DM3000.DM3000, resource_id, resources_list, probe_only)
        elif class_name == 'SDM3065X':
            dmm = _create_selected_instrument(DMM_SDM3065X.SDM3065X, resource_id, resources_list, probe_only)
        elif class_name == 'Fake Test DMM':
            dmm = DMM_Fake.Fake_DMM(resource_id = resource_id, resources_list = resources_list)
        elif class_name == 'A2D_SENSE_BOARD':
            dmm = _create_selected_instrument(DMM_A2D_SENSE_BOARD.A2D_SENSE_BOARD, resource_id, resources_list, probe_only)
        elif class_name == 'A2D_POWER_BOARD':
            dmm = _create_selected_instrument(PSU_A2D_POWER_BOARD.A2D_POWER_BOARD, resource_id, resources_list, probe_only)
        elif class_name == 'A2D_DAQ_CH':
            dmm = _create_selected_instrument(A2D_DAQ_control.A2D_DAQ, resource_id, resources_list, probe_only)
        elif class_name == 'A2D_4CH_Isolated_ADC_Channel':
            dmm = _create_selected_instrument(DMM_A2D_4CH_Isolated_ADC.A2D_4CH_Isolated_ADC, resource_id, resources_list, probe_only)
        elif class_name == 'HP6632B':
            dmm = _create_selected_instrument(PSU_HP6632B.HP6632B, resource_id, resources_list, probe_only)
        setup_dict = _finish_instrument_setup(dmm, setup_dict, interactive, probe_only)
        if setup_dict == None:
            print("Equipment Setup Failed")
            return
        dmm._selected_equipment_type = 'dmm'
        return class_name, dmm, setup_dict
