"""Multiprocessing entry points for battery test execution."""

from charge_discharge.runner import CyclingControl
from battery_app.logging_config import configure_application_logging


def run_charge_discharge_control(
    res_ids_dict,
    data_out_queue=None,
    data_in_queue=None,
    input_dict=None,
    ch_num=None,
):
    """Run the charge/discharge controller in a worker process."""
    configure_application_logging()
    CyclingControl().charge_discharge_control(
        res_ids_dict=res_ids_dict,
        data_out_queue=data_out_queue,
        data_in_queue=data_in_queue,
        input_dict=input_dict,
        ch_num=ch_num,
    )


def run_idle_control(res_ids_dict, data_out_queue=None, data_in_queue=None):
    """Run the idle controller in a worker process."""
    configure_application_logging()
    CyclingControl().idle_control(
        res_ids_dict=res_ids_dict,
        data_out_queue=data_out_queue,
        data_in_queue=data_in_queue,
    )
