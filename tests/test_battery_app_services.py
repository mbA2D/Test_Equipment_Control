from multiprocessing import Queue

import equipment
from battery_app.messages import MessageRouter
from battery_app.equipment_manager import EquipmentManager
from battery_app.persistence import ConfigurationStore
from lab_equipment.correlated_device import CorrelatedVirtualDevice
import queue
import threading
from battery_app.process_manager import ProcessManager
from battery_app.state import ChannelState, ChannelStatus
import pytest


def test_channel_state_tracks_runtime_only_measurements():
    state = ChannelState(number=2, data_queue=Queue())
    state.latest_measurement = {"Voltage": 3.8, "Current": 1.2}
    state.status = ChannelStatus.RUNNING

    assert state.number == 2
    assert state.latest_measurement["Voltage"] == 3.8
    assert state.status is ChannelStatus.RUNNING


def test_message_router_delivers_measurements():
    messages = queue.Queue()
    messages.put({"type": "measurement", "data": {"Voltage": 4.0}})
    received = []

    count = MessageRouter().drain(1, messages, lambda channel, message: received.append((channel, message)))

    assert count == 1
    assert received == [(1, {"type": "measurement", "data": {"Voltage": 4.0}})]


def test_process_manager_handles_not_started_process():
    ProcessManager().stop(None)


def test_equipment_manager_rejects_duplicate_physical_resource():
    manager = EquipmentManager()
    manager.connected_equipment.append({"res_id": "USB::INSTR0"})
    descriptor = {"res_id": "USB::INSTR0"}

    assert manager.is_duplicate(descriptor)


def test_equipment_manager_uses_next_local_id_when_descriptor_has_none():
    manager = EquipmentManager()
    manager.connected_equipment.extend([{}, {}])

    assert manager.next_local_id({"local_id": None}) == 2


def test_equipment_manager_claims_single_instrument_for_one_channel():
    manager = EquipmentManager()
    try:
        routes = manager._response_manager.dict()
        manager.connected_equipment.append({
            "local_id": 1,
            "instrument_channels": [0],
            "owners": {},
            "response_routes": routes,
        })

        first = manager.response_queue_for(1, "channel-0-psu", 0, 0)
        second = manager.response_queue_for(1, "channel-1-psu", 1, 0)
        same_channel = manager.response_queue_for(1, "channel-0-dmm", 0, 0)

        assert first is not None
        assert second is None
        assert same_channel is not None
    finally:
        manager.close()


def test_configuration_store_round_trips_test_configuration(tmp_path):
    store = ConfigurationStore()
    configuration = {
        "cell_name": "cell_1",
        "settings_cycle_list_step_list": [[{"cycle_type": "step"}]],
    }
    filename = tmp_path / "test.json"

    store.save_test_configuration(configuration, filename)

    assert store.load_test_configuration(filename) == configuration


def test_configuration_store_requires_current_test_profile_envelope(tmp_path):
    store = ConfigurationStore()
    filename = tmp_path / "profile.json"
    store.save_json({"test_configuration": {}}, filename)

    with pytest.raises(ValueError, match="Test profiles require schema version"):
        store.load_test_configuration(filename)

    store.save_json(
        {"schema_version": store.schema_version, "test_configuration": {}, "notes": "nope"},
        filename,
    )

    with pytest.raises(ValueError, match="unsupported fields"):
        store.load_test_configuration(filename)


def test_configuration_store_removes_runtime_queue_handles(tmp_path):
    store = ConfigurationStore()
    filename = tmp_path / "equipment.json"
    equipment = [{
        "equipment_id": "fake-1",
        "local_id": 1,
        "instrument_channels": [0],
        "res_id": "Fake",
        "queue_in": object(),
    }]
    assignments = {0: {"psu": {"res_id": {
        "equipment_id": "fake-1",
        "local_id": 1,
        "eq_ch": 0,
        "queue_in": object(),
    }}}}

    store.save_equipment_assignment(equipment, assignments, filename)
    loaded = store.load_equipment_assignment(filename)

    assert "queue_in" not in loaded["connected_equipment_dict"][1]
    assert "queue_in" not in loaded["res_ids_dict"][0]["psu"]["res_id"]


def test_configuration_store_rejects_pre_canonical_channel_equipment_assignment(tmp_path):
    store = ConfigurationStore()
    filename = tmp_path / "equipment-v1.json"
    store.save_json({
        "schema_version": 2,
        "connected_equipment_dict": {},
        "res_ids_dict": {},
    }, filename)

    with pytest.raises(ValueError, match="require schema version 3"):
        store.load_equipment_assignment(filename)


def test_correlated_device_routes_response_by_request_id():
    requests = queue.Queue()
    responses = queue.Queue()
    device = CorrelatedVirtualDevice(requests, responses, timeout_s=1, client_id="client-one")
    result = []

    worker = threading.Thread(target=lambda: result.append(device.measure_voltage()))
    worker.start()
    request = requests.get(timeout=1)
    assert request["protocol"] == 2
    assert request["operation"] == "measure_voltage"
    responses.put({
        "protocol": 2,
        "request_id": request["request_id"],
        "ok": True,
        "value": 3.7,
        "error": None,
    })
    worker.join(timeout=1)

    assert result == [3.7]


def test_correlated_devices_route_concurrent_responses_without_cross_talk():
    requests = queue.Queue()
    responses = queue.Queue()
    first = CorrelatedVirtualDevice(requests, responses, timeout_s=1, client_id="client-one")
    second = CorrelatedVirtualDevice(requests, responses, timeout_s=1, client_id="client-two")
    results = []

    first_worker = threading.Thread(target=lambda: results.append(("first", first.measure_voltage())))
    second_worker = threading.Thread(target=lambda: results.append(("second", second.measure_voltage())))
    first_worker.start()
    second_worker.start()

    requests_seen = [requests.get(timeout=1), requests.get(timeout=1)]
    responses.put({
        "protocol": 2,
        "request_id": requests_seen[1]["request_id"],
        "ok": True,
        "value": 4.2,
    })
    responses.put({
        "protocol": 2,
        "request_id": requests_seen[0]["request_id"],
        "ok": True,
        "value": 3.7,
    })

    first_worker.join(timeout=1)
    second_worker.join(timeout=1)

    assert sorted(results) == [("first", 3.7), ("second", 4.2)]


def test_correlated_device_preserves_selected_instrument_channel():
    requests = queue.Queue()
    responses = queue.Queue()
    device = CorrelatedVirtualDevice(requests, responses, eq_ch=4, timeout_s=1, client_id="client-one")
    result = []

    worker = threading.Thread(target=lambda: result.append(device.measure_voltage()))
    worker.start()
    request = requests.get(timeout=1)
    assert request["instrument_channel"] == 4
    assert request["args"] == []
    responses.put({"request_id": request["request_id"], "ok": True, "value": 3.9})
    worker.join(timeout=1)

    assert result == [3.9]


def test_correlated_device_forwards_keyword_arguments():
    requests = queue.Queue()
    responses = queue.Queue()
    device = CorrelatedVirtualDevice(requests, responses, timeout_s=1, client_id="client-one")
    result = []

    worker = threading.Thread(
        target=lambda: result.append(device.check_status(expected_output=False))
    )
    worker.start()
    request = requests.get(timeout=1)
    assert request["operation"] == "check_status"
    assert request["args"] == []
    assert request["kwargs"] == {"expected_output": False}
    responses.put({"request_id": request["request_id"], "ok": True, "value": None})
    worker.join(timeout=1)

    assert result == [None]


def test_singleton_proxy_keeps_channel_zero_as_metadata_without_driver_argument():
    requests = queue.Queue()
    responses = queue.Queue()
    device = CorrelatedVirtualDevice(requests, responses, eq_ch=0, timeout_s=1, client_id="client-one")
    result = []

    worker = threading.Thread(target=lambda: result.append(device.measure_voltage()))
    worker.start()
    request = requests.get(timeout=1)
    assert request["instrument_channel"] == 0
    assert request["args"] == []
    responses.put({"request_id": request["request_id"], "ok": True, "value": 3.9})
    worker.join(timeout=1)

    assert result == [3.9]


def test_owner_selects_positive_channel_before_dispatch():
    class Device:
        def __init__(self):
            self.selected_channel = None

        def select_channel(self, channel):
            self.selected_channel = channel

        def measure_voltage(self):
            return self.selected_channel

    device = Device()
    equipment._select_assignment_channel(device, 4)

    assert equipment._dispatch_virtual_device_method(device, "measure_voltage", []) == 4


def test_correlated_device_surfaces_remote_errors():
    requests = queue.Queue()
    responses = queue.Queue()
    device = CorrelatedVirtualDevice(requests, responses, timeout_s=1, client_id="client-one")
    result = []

    worker = threading.Thread(target=lambda: _capture_error(result, device.set_current, 1.0))
    worker.start()
    request = requests.get(timeout=1)
    responses.put({
        "protocol": 2,
        "request_id": request["request_id"],
        "ok": False,
        "value": None,
        "error": {"type": "InstrumentError", "message": "output rejected"},
    })
    worker.join(timeout=1)

    assert "InstrumentError" in result[0]


def test_correlated_device_uses_private_response_queue():
    requests = queue.Queue()
    private_responses = queue.Queue()
    device = CorrelatedVirtualDevice(
        requests,
        response_queue=private_responses,
        client_id="channel-one",
        timeout_s=1,
    )
    result = []

    worker = threading.Thread(target=lambda: result.append(device.measure_voltage()))
    worker.start()
    request = requests.get(timeout=1)
    private_responses.put({
        "request_id": request["request_id"],
        "client_id": "channel-one",
        "ok": True,
        "value": 4.1,
    })
    worker.join(timeout=1)

    assert result == [4.1]


def _capture_error(result, function, *args):
    try:
        function(*args)
    except RuntimeError as error:
        result.append(str(error))
