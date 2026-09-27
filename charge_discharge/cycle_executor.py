"""Cycle-loop orchestration for the charge/discharge execution engine."""

import os

import FileIO
from battery_app.bdf_output import (
    build_cycle_metadata,
    read_metadata,
    utc_now,
)
from battery_app.identity import new_session_id, new_test_id
from battery_app.logging_config import get_logger
from battery_app.manifest import (
    load_manifest,
    manifest_timestamped_update,
    save_manifest,
)

from charge_discharge.requirements import equipment_requirements_for_cycle


logger = get_logger(__name__)


class CycleExecutor:
    """Run configured cycles using a :class:`CyclingControl` implementation.

    The control object owns equipment operations and step measurement.  This
    class owns only cycle/step navigation and status messages. Diagnostic
    events go to the application-wide logger; measurements go to CSV files.
    """

    def __init__(self, control, input_dict, data_out_queue, data_in_queue, ch_num):
        self.control = control
        self.input_dict = input_dict
        self.data_out_queue = data_out_queue
        self.data_in_queue = data_in_queue
        self.ch_num = ch_num

    def run(self, csv_dir):
        end_list_of_lists = False
        end_condition = 'none'
        institution_code = self.input_dict.get('institution_code', 'LOCAL')
        cell_name = self.input_dict['cell_name']
        manifest = load_manifest(csv_dir)
        self._recover_stale_cycle(csv_dir, manifest)

        profile_id = self.input_dict['profile_id']
        profile_version = self.input_dict['profile_version']
        previous_test_id = manifest.get('test_id')
        same_profile = (
            manifest.get('profile_id') == profile_id
            and manifest.get('profile_version') == profile_version
        )
        continue_test = bool(previous_test_id) and same_profile and not self.input_dict.get(
            'start_new_test', False
        )
        test_id = previous_test_id if continue_test else new_test_id()
        if previous_test_id and not continue_test and not same_profile:
            continued_from_test_id = previous_test_id
        elif self.input_dict.get('start_new_test', False):
            continued_from_test_id = None
        else:
            continued_from_test_id = manifest.get('continued_from_test_id')
        session_id = new_session_id()
        step_count = FileIO.latest_bdf_step_count(
            csv_dir,
            institution_code,
            cell_name,
        )
        try:
            step_count = max(step_count, int(manifest.get('last_step_count', 0)))
        except (TypeError, ValueError):
            pass

        manifest = manifest_timestamped_update(
            manifest,
            schema_version=1,
            institution_code=institution_code,
            cell_name=cell_name,
            profile_id=profile_id,
            profile_version=profile_version,
            test_id=test_id,
            last_session_id=session_id,
            last_step_count=step_count,
            status='running',
            current_cycle=None,
            continued_from_test_id=continued_from_test_id,
        )
        save_manifest(csv_dir, manifest)

        for cycle_num, settings_cycle_list in enumerate(
            self.input_dict['settings_cycle_list_step_list']
        ):
            self.control.reset_cycle_measurements()
            self.control.csv_filepath = FileIO.start_bdf_file(
                csv_dir,
                institution_code,
                cell_name,
                minimum_sequence=manifest.get('last_cycle_number', 0),
            )
            cycle_count = FileIO.bdf_cycle_number(self.control.csv_filepath)
            manifest = manifest_timestamped_update(
                manifest,
                last_cycle_number=cycle_count,
                last_step_count=step_count,
                current_cycle={
                    'cycle_number': cycle_count,
                    'file': os.path.basename(self.control.csv_filepath),
                    'status': 'running',
                },
            )
            save_manifest(csv_dir, manifest)
            cycle_metadata = build_cycle_metadata(
                data_path=self.control.csv_filepath,
                institution_code=institution_code,
                cell_name=cell_name,
                cycle_count=cycle_count,
                cycle_settings=settings_cycle_list,
                equipment=self.control.eq_dict or {},
                temperature_sources=self.control.temperature_sources,
                start_time_utc=utc_now(),
                profile_id=profile_id,
                profile_version=profile_version,
                test_id=test_id,
                session_id=session_id,
                continued_from_test_id=continued_from_test_id,
            )
            FileIO.write_bdf_metadata(self.control.csv_filepath, cycle_metadata)
            logger.info("CH%s - Cycle %s starting", self.ch_num, cycle_count)
            self.data_out_queue.put_nowait({
                'type': 'event',
                'data': {'message': f'Cycle {cycle_count} started', 'color': '#18794e'},
            })
            logger.info("CH%s - Cycle settings: %s", self.ch_num, settings_cycle_list)

            try:
                if self.control.eq_dict.get('relay_board') is not None:
                    self.control.connect_proper_equipment(
                        equipment_requirements_for_cycle(settings_cycle_list)
                    )

                for step_num, step_settings in enumerate(settings_cycle_list):
                    logger.info("CH%s - Cycle %s step %s starting", self.ch_num, cycle_count, step_num)
                    logger.info("CH%s - Step settings: %s", self.ch_num, step_settings)
                    end_condition = 'none'

                    current_display_status = step_settings['cycle_display']
                    next_display_status = self._next_display_status(cycle_num, step_num, settings_cycle_list)
                    self.data_out_queue.put_nowait(
                        {'type': 'status', 'data': (current_display_status, next_display_status)}
                    )

                    if step_settings['cycle_type'] == 'step':
                        # Step Count is global across the test and advances
                        # only for steps that produce measurement rows.
                        step_count += 1
                        try:
                            end_condition = self.control.single_step_cycle(
                                step_settings,
                                data_out_queue=self.data_out_queue,
                                data_in_queue=self.data_in_queue,
                                ch_num=self.ch_num,
                                step_index=step_num,
                                cycle_count=cycle_count,
                                step_count=step_count,
                                step_id=step_num + 1,
                            )
                        finally:
                            sampling_summary = getattr(
                                self.control,
                                "last_step_sampling_summary",
                                None,
                            )
                            if isinstance(sampling_summary, dict):
                                cycle_metadata["test"]["steps"][step_num]["sampling"] = dict(
                                    sampling_summary
                                )
                                FileIO.write_bdf_metadata(
                                    self.control.csv_filepath,
                                    cycle_metadata,
                                )
                                overrun_count = sampling_summary.get("overrun_count", 0)
                                if overrun_count:
                                    message = (
                                        f"CH{self.ch_num} - Step {step_num + 1}: "
                                        f"{overrun_count} sampling interval(s) missed; "
                                        f"maximum overrun "
                                        f"{sampling_summary.get('max_overrun_s', 0.0):.3f} s"
                                    )
                                    logger.warning(message)
                                    if self.data_out_queue is not None:
                                        try:
                                            self.data_out_queue.put_nowait({
                                                "type": "event",
                                                "data": {
                                                    "message": message,
                                                    "color": "#b54708",
                                                },
                                            })
                                        except Exception:
                                            logger.exception(
                                                "CH%s - Could not report sampling overrun",
                                                self.ch_num,
                                            )

                    logger.info(
                        "CH%s - Cycle %s step %s ending; reason: %s",
                        self.ch_num, cycle_count, step_num, end_condition,
                    )

                    if end_condition == 'settings':
                        raise RuntimeError(
                            "Step setup failed; check the assigned equipment and profile"
                        )
                    if end_condition == 'cycle_end_condition':
                        self.control.disable_equipment()
                        break
                    if end_condition == 'safety_condition':
                        self.data_out_queue.put_nowait(
                            {'type': 'end_condition', 'data': 'safety_condition'}
                        )
                    if end_condition in ('end_request', 'safety_condition'):
                        end_list_of_lists = True
                        break

                if end_list_of_lists:
                    logger.info("CH%s - Ending all cycles", self.ch_num)
                    break

                logger.info("CH%s - Cycle %s ending", self.ch_num, cycle_count)
            except KeyboardInterrupt:
                self._mark_cycle_interrupted(
                    cycle_metadata,
                    manifest,
                    csv_dir,
                    reason='keyboard_interrupt',
                )
                self.control.disable_equipment()
                logger.warning("CH%s - Keyboard interrupt", self.ch_num)
                raise
            except Exception:
                self._mark_cycle_interrupted(
                    cycle_metadata,
                    manifest,
                    csv_dir,
                    reason='execution_error',
                )
                self.control.disable_equipment()
                raise

            cycle_metadata['test']['status'] = (
                'stopped_safety' if end_condition == 'safety_condition'
                else 'completed'
            )
            cycle_metadata['test']['end_time_utc'] = utc_now()
            FileIO.write_bdf_metadata(self.control.csv_filepath, cycle_metadata)
            manifest = manifest_timestamped_update(
                manifest,
                last_cycle_number=cycle_count,
                last_step_count=step_count,
                current_cycle=None,
                status='running',
            )
            save_manifest(csv_dir, manifest)

        self.control.disable_equipment()
        manifest = manifest_timestamped_update(
            manifest,
            last_step_count=step_count,
            current_cycle=None,
            status='completed',
        )
        save_manifest(csv_dir, manifest)
        if end_condition == 'safety_condition':
            self.data_out_queue.put_nowait({
                'type': 'event',
                'data': {'message': 'Safety limit reached; all cycles stopped', 'color': '#b42318'},
            })
            logger.warning("CH%s - Safety limit hit", self.ch_num)
        else:
            self.data_out_queue.put_nowait({
                'type': 'event',
                'data': {'message': 'All cycles completed', 'color': '#18794e'},
            })
            logger.info("CH%s - All cycles completed", self.ch_num)

    def _recover_stale_cycle(self, csv_dir, manifest):
        """Mark a cycle left running by an earlier process as interrupted."""
        current_cycle = manifest.get('current_cycle')
        if not isinstance(current_cycle, dict) or current_cycle.get('status') != 'running':
            return

        filename = current_cycle.get('file')
        if filename:
            filepath = os.path.join(csv_dir, filename)
            try:
                metadata = read_metadata(filepath)
                metadata.setdefault('test', {})['status'] = 'interrupted'
                metadata['test']['interruption_reason'] = 'previous_session_stale'
                metadata['test']['end_time_utc'] = utc_now()
                FileIO.write_bdf_metadata(filepath, metadata)
            except (FileNotFoundError, OSError, ValueError):
                logger.warning("Could not update stale cycle metadata: %s", filepath)

        manifest.update({
            'status': 'interrupted',
            'current_cycle': {
                **current_cycle,
                'status': 'interrupted',
                'interruption_reason': 'previous_session_stale',
            },
        })

    def _mark_cycle_interrupted(self, cycle_metadata, manifest, csv_dir, reason):
        """Persist interrupted status in both metadata and the cell manifest."""
        cycle_metadata['test']['status'] = 'interrupted'
        cycle_metadata['test']['interruption_reason'] = reason
        cycle_metadata['test']['end_time_utc'] = utc_now()
        FileIO.write_bdf_metadata(self.control.csv_filepath, cycle_metadata)
        current_cycle = manifest.get('current_cycle') or {}
        manifest.update({
            'status': 'interrupted',
            'last_step_count': manifest.get('last_step_count', 0),
            'current_cycle': {
                **current_cycle,
                'status': 'interrupted',
                'interruption_reason': reason,
            },
        })
        save_manifest(csv_dir, manifest)

    def _next_display_status(self, cycle_num, step_num, settings_cycle_list):
        try:
            return settings_cycle_list[step_num + 1]['cycle_display']
        except (IndexError, TypeError):
            try:
                return self.input_dict['settings_cycle_list_step_list'][cycle_num + 1][0][
                    'cycle_display'
                ]
            except (IndexError, TypeError):
                return 'Idle'
