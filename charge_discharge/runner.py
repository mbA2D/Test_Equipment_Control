"""Battery charge/discharge execution engine."""

import queue
import time

import equipment as eq
import FileIO
from battery_app.bdf_output import build_bdf_row, step_type_label, temperature_source_map
from battery_app.logging_config import get_logger
from battery_app.simulation import (
    SimulationLinkService,
    assignment_uses_fake_equipment,
    is_simulated_cell_name,
)

from charge_discharge.conditions import evaluate_end_condition as evaluate_step_end_condition
from charge_discharge.cycle_executor import CycleExecutor
from charge_discharge.equipment_control import EquipmentController
from charge_discharge.measurement import CycleMeasurementAccumulator, MeasurementService


logger = get_logger(__name__)


class CyclingControl():
    
    def __init__(self):
        self.eq_dict = None
        self.input_dict = None
        self.battery_link = None
        self.simulation_service = None
        self._simulation_devices = []
        self.cycle_measurements = CycleMeasurementAccumulator()
        self.test_start_perf = None
        self.temperature_sources = {}
        self._readback_checked_roles = set()
        self._last_instrument_health_check = 0.0
        self._instrument_health_check_interval_s = 1.0

    def _configure_instrument_readbacks(self, assignment):
        """Limit model-specific health queries to the audited first-test models."""
        self._readback_checked_roles = set()
        for role in ("psu", "eload"):
            descriptor = assignment.get(role)
            if not isinstance(descriptor, dict):
                continue
            identity = " ".join((
                str(descriptor.get("class_name", "")),
                str(descriptor.get("eq_idn", "")),
            )).upper()
            if role == "eload" and "8601" in identity:
                self._readback_checked_roles.add(role)
            elif role == "psu" and "SPD1168X" in identity:
                self._readback_checked_roles.add(role)

    def _check_instrument_health(self, step_settings=None, *, force=False):
        """Ask each audited instrument owner to verify output and health state."""
        now = time.monotonic()
        if not force and now - self._last_instrument_health_check < self._instrument_health_check_interval_s:
            return

        expected_output = {"psu": False, "eload": False}
        if step_settings is not None:
            drive_style = step_settings.get("drive_style")
            drive_value = float(step_settings.get("drive_value", 0))
            if drive_style == "current_a":
                if drive_value > 0:
                    expected_output["psu"] = True
                elif drive_value < 0:
                    expected_output["eload"] = True
            elif drive_style == "voltage_v" and float(step_settings.get("drive_value_other", 0)) >= 0:
                expected_output["psu"] = True

        for role in self._readback_checked_roles:
            device = (self.eq_dict or {}).get(role)
            if device is None:
                continue
            if role == "eload" and expected_output[role]:
                device.check_status(expected_output=True, expected_mode="CURR")
            else:
                device.check_status(expected_output=expected_output[role])
        self._last_instrument_health_check = now

    def start_measurement_session(self):
        """Start the test-time clock and capture the BDF temperature mapping."""
        self.test_start_perf = time.perf_counter()
        self.temperature_sources = temperature_source_map(self.eq_dict or {})

    def reset_cycle_measurements(self):
        """Reset directional capacity and energy counters for a new cycle."""
        self.cycle_measurements.reset()

    def add_cycle_measurements(self, data):
        """Add current cycle totals to a measurement row before it is logged."""
        data.update(self.cycle_measurements.update(data))
        return data

    def write_bdf_measurement(
            self,
            data,
            *,
            cycle_count,
            step_count,
            step_id,
            step_start_time_perf,
            step_type,
    ):
        """Serialize one internal measurement using the fixed BDF schema."""
        if self.test_start_perf is None:
            raise RuntimeError("Measurement session has not been started")
        bdf_row = build_bdf_row(
            data,
            test_time_s=max(data["Data_Timestamp"] - self.test_start_perf, 0.0),
            cycle_count=cycle_count,
            step_count=step_count,
            step_id=step_id,
            step_time_s=max(data["Data_Timestamp"] - step_start_time_perf, 0.0),
            step_type=step_type_label(step_type),
            temperature_sources=self.temperature_sources,
        )
        FileIO.write_bdf_data(self.csv_filepath, bdf_row)
    
    ################################################## EQUIPMENT SETUP #############################################

    def init_eload(self):
        self.eq_dict['eload'].toggle_output(False)
        self.eq_dict['eload'].set_current(0)
        
    def init_psu(self):
        self.eq_dict['psu'].toggle_output(False)
        self.eq_dict['psu'].set_voltage(0)
        self.eq_dict['psu'].set_current(0)

    def init_dmm_v(self, device = None):
        #test voltage measurement to ensure everything is set up correctly
        #often the first measurement takes longer as it needs to setup range, NPLC
        #This also gets it setup to the correct range.
        #TODO - careful of batteries that will require a range switch during the charge
        #	  - this could lead to a measurement delay. 6S happens to cross the 20V range.
        if device is not None:
            device.measure_voltage()
        else:
            self.eq_dict['dmm_v'].measure_voltage()

    def init_dmm_i(self, device = None):
        #test measurement to ensure everything is set up correctly
        #and the fisrt measurement which often takes longer is out of the way
        if device is not None:
            device.measure_current()
        else:
            self.eq_dict['dmm_i'].measure_current()
        
    def init_dmm_t(self, device = None):
        #test measurement to ensure everything is set up correctly
        #and the fisrt measurement which often takes longer is out of the way
        if device is not None:
            device.measure_temperature()
        else:
            self.eq_dict['dmm_t'].measure_temperature()

    def init_relay_board(self):
        #turn off all channels
        self.eq_dict['relay_board'].connect_eload(False)
        self.eq_dict['relay_board'].connect_psu(False)
        
    def initialize_connected_equipment(self):
        EquipmentController(self.eq_dict).initialize()

    def disable_equipment_single(self, equipment):
        EquipmentController.disable_single(equipment)

    def disable_equipment(self):
        EquipmentController(self.eq_dict).disable_all()

    def _report_worker_failure(self, data_out_queue, worker, error):
        """Publish a GUI-safe failure message while retaining the traceback in logs."""
        if data_out_queue is None:
            return
        message = f"{worker} failed: {type(error).__name__}: {error}"
        try:
            data_out_queue.put_nowait({
                "type": "error",
                "data": {
                    "message": message,
                    "worker": worker,
                    "exception_type": type(error).__name__,
                },
            })
        except Exception:
            # Do not replace the original worker failure with a queue-reporting
            # error. The process-exit monitor remains the final fallback.
            logger.exception("Could not report %s failure to the application", worker)

    def _disable_equipment_after_failure(self):
        """Make a best-effort safe shutdown after a worker exception."""
        if not self.eq_dict:
            return
        try:
            self.disable_equipment()
        except Exception:
            logger.exception("Could not disable equipment after worker failure")

    def connect_proper_equipment(self, eq_req_for_cycle_dict):
        #If a relay board is connected (that can connect or disconnect equipment) then we want to have only the necessary equipment connected on each cycle
        #For now, we will assume that all 'relay boards' can only be connected to PSUs or eLoads - which channels these are connected to happens on setup of the relay board.
        #But only 2 channels and only 1 of each equipment.
        
        #TODO - add a voltage check to see if equipment switched properly.
        
        #Disconnect first (break before make)
        #if not required but it is connected, then break connection
        if not eq_req_for_cycle_dict['psu'] and self.eq_dict['relay_board'].psu_connected():
            self.disable_equipment_single(self.eq_dict['psu'])
            self.eq_dict['relay_board'].connect_psu(False)
        if not eq_req_for_cycle_dict['eload'] and self.eq_dict['relay_board'].eload_connected():
            self.disable_equipment_single(self.eq_dict['eload'])
            self.eq_dict['relay_board'].connect_eload(False)
        
        #Connect second (break before make)
        #if required but is not connected, then make connection
        if eq_req_for_cycle_dict['psu'] and not self.eq_dict['relay_board'].psu_connected(): #if changing states
            #ensure psu output is disabled before connecting
            self.disable_equipment_single(self.eq_dict['psu'])
            self.eq_dict['relay_board'].connect_psu(True)
        if eq_req_for_cycle_dict['eload'] and not self.eq_dict['relay_board'].eload_connected():
            #ensure eload output is disabled before connecting
            self.disable_equipment_single(self.eq_dict['eload'])
            self.eq_dict['relay_board'].connect_eload(True)

        time.sleep(0.1) #Delay to make sure all the relays click.


    ###################################################### TEST CONTROL ###################################################
       
    def start_step(self, step_settings):
        #This function will set all the supplies to the settings given in the step
        
        #CURRENT DRIVEN
        if step_settings["drive_style"] == 'current_a':
            logger.info("Current-driven step setup")
            if step_settings["drive_value"] > 0:
                # Open both outputs before applying a new setpoint.
                self.disable_equipment_single(self.eq_dict['eload'])
                self.disable_equipment_single(self.eq_dict['psu'])
                if self.eq_dict['psu'] != None:
                    time.sleep(0.01)
                    self.eq_dict['psu'].set_current(step_settings["drive_value"])
                    time.sleep(0.01)
                    self.eq_dict['psu'].set_voltage(step_settings["drive_value_other"])
                    time.sleep(0.01)
                    self.eq_dict['psu'].toggle_output(True)
                    time.sleep(0.01)
                else:
                    logger.error("No PSU connected; cannot charge")
                    return False
            elif step_settings["drive_value"] < 0:
                # Open both outputs before applying a new setpoint.
                self.disable_equipment_single(self.eq_dict['psu'])
                self.disable_equipment_single(self.eq_dict['eload'])
                if self.eq_dict['eload'] != None:
                    if 'eload' in self._readback_checked_roles:
                        self.eq_dict['eload'].set_mode_current()
                    time.sleep(0.01)
                    self.eq_dict['eload'].set_current(step_settings["drive_value"])
                    time.sleep(0.01)
                    self.eq_dict['eload'].toggle_output(True)
                    time.sleep(0.01)
                    #we're in constant current mode - can't set a voltage.
                else:
                    logger.error("No electronic load connected; cannot discharge")
                    return False
            elif step_settings["drive_value"] == 0:
                #rest
                self.disable_equipment()
        
        #VOLTAGE DRIVEN
        elif step_settings["drive_style"] == 'voltage_v':
            logger.info("Voltage-driven step setup")
            #positive current
            if step_settings["drive_value_other"] >= 0:
                self.disable_equipment_single(self.eq_dict['eload'])
                self.disable_equipment_single(self.eq_dict['psu'])
                if self.eq_dict['psu'] != None:
                    time.sleep(0.01)
                    self.eq_dict['psu'].set_current(step_settings["drive_value_other"])
                    time.sleep(0.01)
                    self.eq_dict['psu'].set_voltage(step_settings["drive_value"])
                    time.sleep(0.01)
                    self.eq_dict['psu'].toggle_output(True)
                    time.sleep(0.01)
                else:
                    logger.error("No PSU connected; cannot charge")
                    return False
            #TODO - needs CV mode on eloads
            else:
                logger.error("Voltage-driven step for negative current is not implemented")
                #Ensure everything is off since not yet implemented.
                self.disable_equipment()
                return False
        
        #NOT DRIVEN
        elif step_settings["drive_style"] == 'none':
            logger.info("Non-driven (rest) step setup")
            #Ensure all sources and loads are off.
            self.disable_equipment()
        
        #return True for a successful step start.
        #print("start_step returning True")
        return True

    def evaluate_end_condition(self, step_settings, data, data_in_queue):
        """Evaluate one step and record safety side effects."""
        stop_requested = self.end_signal(data_in_queue)
        reason = evaluate_step_end_condition(
            step_settings,
            data,
            stop_requested=stop_requested,
        )
        if reason.value == 'safety_condition':
            logger.warning("Safety limit reached: %s", data)
        return reason.value

    ######################### MEASURING ######################

    def measure_battery(self, data_out_queue = None, step_index = 0, current_time = None):
        measurement = MeasurementService(self.eq_dict).read(
            step_index=step_index,
            current_time=current_time,
        )
        data_dict = {'type': 'measurement', 'data': measurement}
        
        #Send voltage and current to be displayed in the main test window
        if data_out_queue != None:
            #add the new data to the output queue
            data_out_queue.put_nowait(data_dict)
        
        #print("Measurement: {}".format(data_dict['data']))
        return measurement


    ########################## CHARGE, DISCHARGE, REST #############################

    def end_signal(self, data_in_queue):
        end_signal = False
        try:
            signal = data_in_queue.get_nowait()
            if signal == 'stop':
                end_signal = True
        except queue.Empty:
            pass
        return end_signal
        
    def idle_cell(self, data_out_queue = None, data_in_queue = None):
        #Measures voltage (and current if available) when no other process is running to have live voltage updates
        while not self.end_signal(data_in_queue):
            self.measure_battery(data_out_queue = data_out_queue)
            time.sleep(1)

    def step_cell(
            self,
            step_settings,
            data_out_queue=None,
            data_in_queue=None,
            step_index=0,
            cycle_count=1,
            step_count=1,
            step_id=1,
    ):
        
        if self.start_step(step_settings):
            logger.info("Start step successful")
            step_start_time_perf = time.perf_counter()
            self._check_instrument_health(step_settings, force=True)

            # Allow a short output-settling interval before the first driven
            # sample. Instrument readbacks and VISA query latency also elapse
            # before measurement; keep this explicit wait inside step limits.
            output_enabled = (
                step_settings["drive_style"] in {"current_a", "voltage_v"}
                and float(step_settings["drive_value"]) != 0
            )
            first_sample_delay_s = 0.0
            if output_enabled:
                measurement_interval_s = float(step_settings["meas_log_int_s"])
                first_sample_delay_s = 0.5
                safety_timeout_s = float(step_settings["safety_max_time_s"])
                if safety_timeout_s > 0:
                    first_sample_delay_s = min(
                        first_sample_delay_s,
                        max(0.0, safety_timeout_s - measurement_interval_s),
                    )
                if step_settings["end_style"] == "time_s":
                    first_sample_delay_s = min(
                        first_sample_delay_s,
                        max(
                            0.0,
                            float(step_settings["end_value"]) - measurement_interval_s,
                        ),
                    )
            first_sample_deadline = step_start_time_perf + first_sample_delay_s
            while time.perf_counter() < first_sample_deadline:
                self._check_instrument_health(step_settings)
                time.sleep(0.001)

            perf_counter_start = time.perf_counter()
            
            data = dict()
            data.update(
                self.measure_battery(
                    step_index=step_index,
                    current_time=perf_counter_start,
                )
            )
            self.add_cycle_measurements(data)
            data["Data_Timestamp_From_Step_Start"] = (
                data["Data_Timestamp"] - step_start_time_perf
            )
            self.write_bdf_measurement(
                data,
                cycle_count=cycle_count,
                step_count=step_count,
                step_id=step_id,
                step_start_time_perf=step_start_time_perf,
                step_type=step_settings.get("cycle_display"),
            )
            
            #If we are charging to the end of a CC cycle, then we need to not exit immediately.
            condition_data = data
            if (step_settings["drive_style"] == "voltage_v" and
                step_settings["end_style"] == "current_a" and
                step_settings["end_condition"] == "lesser"):

                # Use the configured current only for end-condition evaluation;
                # retain the measured current in the BDF row.
                condition_data = dict(data)
                condition_data["Current"] = step_settings["drive_value_other"]
            
            end_condition = self.evaluate_end_condition(step_settings, condition_data, data_in_queue)
            logger.info("End condition before measurement loop: %s", end_condition)
            
            #Do the measurements and check the end conditions at every logging interval
            while end_condition == 'none':
                perf_counter_end = perf_counter_start + step_settings["meas_log_int_s"]
                perf_counter_start = time.perf_counter()
                
                perf_counter_delay = perf_counter_start
                while perf_counter_delay < perf_counter_end:
                    time.sleep(0.001) #1ms
                    perf_counter_delay = time.perf_counter()
                    self._check_instrument_health(step_settings)
                
                data.update(self.measure_battery(data_out_queue = data_out_queue, step_index = step_index, current_time = perf_counter_delay))
                self.add_cycle_measurements(data)
                data["Data_Timestamp_From_Step_Start"] = (data["Data_Timestamp"] - step_start_time_perf)
                self._check_instrument_health(step_settings)
                end_condition = self.evaluate_end_condition(step_settings, data, data_in_queue)
                self.write_bdf_measurement(
                    data,
                    cycle_count=cycle_count,
                    step_count=step_count,
                    step_id=step_id,
                    step_start_time_perf=step_start_time_perf,
                    step_type=step_settings.get("cycle_display"),
                )
            
            #if the end condition is due to safety settings, then we want to end all future steps as well so return the exit reason
            return end_condition
        
        else:
            logger.error("Step setup failed")
            return 'settings'

    ################################## SETTING CYCLE, CHARGE, DISCHARGE ############################

    def idle_cell_cycle(self, data_out_queue = None, data_in_queue = None):
        if self.eq_dict['dmm_v'] == None or self.eq_dict['dmm_v'] == self.eq_dict['eload'] or self.eq_dict['dmm_v'] == self.eq_dict['psu']:
            if self.eq_dict['eload'] != None:
                self.eq_dict['dmm_v'] = self.eq_dict['eload']
            elif self.eq_dict['psu'] != None:
                self.eq_dict['dmm_v'] = self.eq_dict['psu']
            else:
                logger.error("No voltage measurement equipment connected; exiting")
                return 'settings'
        
        if self.eq_dict['dmm_i'] == None or self.eq_dict['dmm_i'] == self.eq_dict['eload'] or self.eq_dict['dmm_i'] == self.eq_dict['psu']:
            if self.eq_dict['eload'] != None:
                self.eq_dict['dmm_i'] = self.eq_dict['eload']
            elif self.eq_dict['psu'] != None:
                self.eq_dict['dmm_i'] = self.eq_dict['psu']
                
        self.idle_cell(data_out_queue = data_out_queue, data_in_queue = data_in_queue)

    def single_step_cycle(
            self,
            step_settings,
            data_out_queue=None,
            data_in_queue=None,
            ch_num=None,
            step_index=0,
            cycle_count=1,
            step_count=1,
            step_id=1,
    ):

        #if we don't have separate voltage measurement equipment, then choose what to use:
        if self.eq_dict['dmm_v'] == None or self.eq_dict['dmm_v'] == self.eq_dict['eload'] or self.eq_dict['dmm_v'] == self.eq_dict['psu']:
            if self.eq_dict['eload'] != None:
                self.eq_dict['dmm_v'] = self.eq_dict['eload']
            elif self.eq_dict['psu'] != None:
                self.eq_dict['dmm_v'] = self.eq_dict['psu']
            else:
                logger.error("No voltage measurement equipment connected; exiting")
                return 'settings'
        
        logger.info("Voltage measurement equipment chosen")
        
        #if we don't have separate current measurement equipment, then choose what to use:
        if self.eq_dict['dmm_i'] == None or self.eq_dict['dmm_i'] == self.eq_dict['eload'] or self.eq_dict['dmm_i'] == self.eq_dict['psu']:
            resting = False
            left_comparator = 0
            if step_settings["drive_style"] == 'current_a':
                left_comparator = step_settings["drive_value"]
            elif step_settings["drive_style"] == 'voltage_v':
                left_comparator = step_settings["drive_value_other"]
            if step_settings["drive_style"] == ['none'] or left_comparator == 0:
                resting = True
            
            if left_comparator > 0 and self.eq_dict['psu'] != None:
                self.eq_dict['dmm_i'] = self.eq_dict['psu'] #current measurement during charge
            elif left_comparator < 0 and self.eq_dict['eload'] != None:
                self.eq_dict['dmm_i'] = self.eq_dict['eload'] #current measurement during discharge
            elif not resting:
                logger.error("No current measurement equipment connected and step is not resting; exiting")
                return 'settings'
        
        logger.info("Current measurement equipment chosen")
        
        end_reason = 'none'
        end_reason = self.step_cell(
            step_settings,
            data_out_queue=data_out_queue,
            data_in_queue=data_in_queue,
            step_index=step_index,
            cycle_count=cycle_count,
            step_count=step_count,
            step_id=step_id,
        )

        return end_reason
        
    ################################## BATTERY CYCLING SETUP FUNCTION ######################################
    def idle_control(self, res_ids_dict, data_out_queue = None, data_in_queue = None):
        try:
            self.eq_dict = eq.get_equipment_dict(res_ids_dict)
            result = self.idle_cell_cycle(
                data_out_queue=data_out_queue,
                data_in_queue=data_in_queue,
            )
            if result == "settings":
                raise RuntimeError("Idle measurement has no usable voltage measurement equipment")
            self.disable_equipment()
        except Exception as error:
            logger.exception("Idle control failed")
            self._disable_equipment_after_failure()
            self._report_worker_failure(data_out_queue, "Idle worker", error)
            raise
        
    def charge_discharge_control(self, res_ids_dict, data_out_queue = None, data_in_queue = None, input_dict = None, ch_num = None):
        try:
            self._configure_instrument_readbacks(res_ids_dict)
            simulated_cell = is_simulated_cell_name(
                input_dict.get('cell_name') if input_dict else None
            )
            if simulated_cell:
                self._validate_simulated_equipment_assignment(res_ids_dict)
            elif assignment_uses_fake_equipment(res_ids_dict):
                raise ValueError(
                    'Fake Test equipment requires the SIMULATED_LG_MJ1 cell name'
                )
            self.eq_dict = eq.get_equipment_dict(res_ids_dict)
            if simulated_cell:
                self._connect_simulated_battery()
            #print("Got Equipment Dict")
            
            # The GUI/application boundary supplies a validated profile plus
            # run context. The execution engine must not revise profile
            # identity or silently repair imported data.
            self.input_dict = input_dict
            
            #CHECKING CONNECTION OF REQUIRED EQUIPMENT
            if self.input_dict['eq_req_dict']['eload'] and self.eq_dict['eload'] == None:
                raise RuntimeError("E-load required for cycle but none is connected")
        
            if self.input_dict['eq_req_dict']['psu'] and self.eq_dict['psu'] == None:
                raise RuntimeError("Power supply required for cycle type but none is connected")
            
            #Ensure that the proper directory exists for measurement CSV files.
            csv_dir = FileIO.ensure_subdir_exists_dir(self.input_dict['directory'], self.input_dict['cell_name'])
            
            #Now initialize all the equipment that is connected
            self.initialize_connected_equipment()
            self._check_instrument_health(force=True)
            self.start_measurement_session()
            
            CycleExecutor(
                self,
                self.input_dict,
                data_out_queue,
                data_in_queue,
                ch_num,
            ).run(csv_dir)
        except Exception as error:
            logger.exception("Charge/discharge control failed")
            self._disable_equipment_after_failure()
            self._report_worker_failure(data_out_queue, "Charge/discharge worker", error)
            raise
        finally:
            if self.simulation_service is not None:
                self._disconnect_simulated_battery()
                self.simulation_service.close()
                self.simulation_service = None
                self.battery_link = None

    @staticmethod
    def _validate_simulated_equipment_assignment(res_ids_dict):
        """Require simulation to use assigned fake instrument-owner proxies."""

        expected_class_by_role = {
            'psu': 'Fake Test PSU',
            'eload': 'Fake Test Eload',
            'dmm_v': 'Fake Test DMM',
            'dmm_i': 'Fake Test DMM',
            'dmm_t': 'Fake Test DMM',
        }
        for role, descriptor in res_ids_dict.items():
            if descriptor is None:
                continue

            expected_class = expected_class_by_role.get(role)
            class_name = descriptor.get('class_name')
            resource = descriptor.get('res_id')
            if (
                class_name != expected_class
                or not isinstance(resource, dict)
                or resource.get('queue_in') is None
                or resource.get('response_queue') is None
            ):
                raise ValueError(
                    'SIMULATED_LG_MJ1 requires assigned Fake Test PSU, Fake Test '
                    'Eload, and Fake Test DMM instrument-owner proxies'
                )

    def _connect_simulated_battery(self):
        """Attach every fake owner to one process-safe LG MJ1 model."""

        self.simulation_service = SimulationLinkService()
        link = self.simulation_service.start()
        try:
            self._simulation_devices = []
            attached = set()
            for device in self.eq_dict.values():
                if device is None or id(device) in attached:
                    continue
                device.attach_battery_link(link)
                attached.add(id(device))
                self._simulation_devices.append(device)
        except Exception:
            self._disconnect_simulated_battery()
            self.simulation_service.close()
            self.simulation_service = None
            raise
        self.battery_link = link

    def _disconnect_simulated_battery(self):
        """Detach fake owners before the shared model stops."""

        for device in reversed(self._simulation_devices):
            try:
                device.attach_battery_link(None)
            except Exception:
                logger.exception("Could not detach simulated battery from fake owner")
        self._simulation_devices = []
