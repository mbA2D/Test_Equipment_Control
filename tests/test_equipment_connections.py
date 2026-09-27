import equipment
import pyvisa
import queue
import threading


def test_direct_fallback_accepts_resource_strings_and_reuses_connection(monkeypatch):
    connected = []

    def fake_connect(key, class_name, res_id, setup_dict):
        instrument = object()
        connected.append((key, class_name, res_id, setup_dict))
        return instrument

    monkeypatch.setattr(equipment, "connect_to_eq", fake_connect)
    resource = "GPIB0::1::INSTR"
    result = equipment.get_equipment_dict({
        "psu": {
            "res_id": resource,
            "class_name": "HP6632B",
            "setup_dict": {},
        },
        "dmm_v": {
            "res_id": resource,
            "class_name": "HP6632B",
            "setup_dict": {},
        },
    })

    assert result["psu"] is result["dmm_v"]
    assert len(connected) == 1


def test_equipment_dict_includes_unassigned_optional_roles():
    result = equipment.get_equipment_dict({})

    assert result == {
        "psu": None,
        "eload": None,
        "dmm_v": None,
        "dmm_i": None,
        "dmm_t": None,
        "relay_board": None,
    }


def test_virtual_equipment_still_uses_queue_proxy(monkeypatch):
    proxy = object()
    monkeypatch.setattr(equipment, "connect_to_virtual_eq", lambda res_id: proxy)

    result = equipment.get_equipment_dict({
        "dmm_v": {
            "res_id": {
                "queue_in": object(),
            },
            "class_name": "HP6632B",
            "setup_dict": {},
        },
    })

    assert result["dmm_v"] is proxy


def test_virtual_owner_returns_structured_errors_and_closes_device(monkeypatch):
    requests = queue.Queue()
    responses = queue.Queue()

    class FakeDevice:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    device = FakeDevice()
    monkeypatch.setattr(equipment, "connect_to_eq", lambda *args: device)
    worker = threading.Thread(
        target=equipment.virtual_device_management_process,
        args=("dmm", {"class_name": "Fake", "res_id": "Fake", "setup_dict": {}}, requests, {"client-1": responses}),
    )
    worker.start()

    requests.put({
        "protocol": 2,
        "request_id": "request-1",
        "client_id": "client-1",
        "operation": "unsupported_operation",
        "args": [],
    })
    response = responses.get(timeout=1)
    requests.put("stop")
    worker.join(timeout=1)

    assert response["request_id"] == "request-1"
    assert response["ok"] is False
    assert response["error"]["type"] == "ValueError"
    assert device.closed is True


def test_virtual_owner_routes_protocol_v2_responses_to_private_client_queues(monkeypatch):
    requests = queue.Queue()
    client_one = queue.Queue()
    client_two = queue.Queue()
    routes = {"client-one": client_one, "client-two": client_two}

    class FakeDevice:
        def measure_voltage(self, _channel=None):
            return 3.7

        def close(self):
            pass

    monkeypatch.setattr(equipment, "connect_to_eq", lambda *args: FakeDevice())
    worker = threading.Thread(
        target=equipment.virtual_device_management_process,
        args=("dmm", {"class_name": "Fake", "res_id": "Fake", "setup_dict": {}}, requests, routes),
    )
    worker.start()

    requests.put({
        "protocol": 2,
        "request_id": "request-one",
        "client_id": "client-one",
        "operation": "measure_voltage",
        "args": [],
    })
    requests.put({
        "protocol": 2,
        "request_id": "request-two",
        "client_id": "client-two",
        "operation": "measure_voltage",
        "args": [],
    })

    assert client_one.get(timeout=1)["request_id"] == "request-one"
    assert client_two.get(timeout=1)["request_id"] == "request-two"
    requests.put("stop")
    worker.join(timeout=1)


def test_virtual_owner_dispatches_protocol_v2_keyword_arguments(monkeypatch):
    requests = queue.Queue()
    responses = queue.Queue()

    class FakeDevice:
        def check_status(self, *, expected_output):
            return {"expected_output": expected_output}

        def close(self):
            pass

    monkeypatch.setattr(equipment, "connect_to_eq", lambda *args: FakeDevice())
    worker = threading.Thread(
        target=equipment.virtual_device_management_process,
        args=("psu", {"class_name": "Fake", "res_id": "Fake", "setup_dict": {}}, requests, {"client-1": responses}),
    )
    worker.start()
    requests.put({
        "protocol": 2,
        "request_id": "request-keyword-args",
        "client_id": "client-1",
        "operation": "check_status",
        "args": [],
        "kwargs": {"expected_output": False},
    })

    response = responses.get(timeout=1)
    requests.put("stop")
    worker.join(timeout=1)

    assert response["ok"] is True
    assert response["value"] == {"expected_output": False}


def test_resource_scan_skips_unavailable_optional_ivi_backend(monkeypatch):
    calls = []

    class FakeResourceManager:
        def list_resources(self):
            return ("TCPIP0::192.0.2.10::inst0::INSTR",)

        def close(self):
            pass

    def fake_resource_manager(backend):
        calls.append(backend)
        if backend == "@ivi":
            raise pyvisa.errors.LibraryError("native VISA library is not installed")
        return FakeResourceManager()

    monkeypatch.setattr(equipment.pyvisa, "ResourceManager", fake_resource_manager)

    assert equipment.get_resources_list() == [{
        "resource": "TCPIP0::192.0.2.10::inst0::INSTR",
        "backend": "@py",
    }]
    assert calls == ["@py", "@ivi"]


def test_ivi_device_falls_back_to_pyvisa_py_when_native_backend_is_missing(monkeypatch):
    from lab_equipment import PyVisaDeviceTemplate

    class FakeInstrument:
        def close(self):
            pass

    class FakeResourceManager:
        def open_resource(self, resource_id):
            assert resource_id == "ASRL/dev/ttyUSB0::INSTR"
            return FakeInstrument()

    def fake_resource_manager(backend):
        if backend == "@ivi":
            raise pyvisa.errors.LibraryError("native VISA library is not installed")
        assert backend == "@py"
        return FakeResourceManager()

    monkeypatch.setattr(PyVisaDeviceTemplate.pyvisa, "ResourceManager", fake_resource_manager)

    class OptionalIviDevice(PyVisaDeviceTemplate.PyVisaDevice):
        connection_settings = {
            "pyvisa_backend": "@ivi",
            "time_wait_after_open": 0,
            "idn_available": False,
        }

    device = OptionalIviDevice("ASRL/dev/ttyUSB0::INSTR")

    assert isinstance(device.inst, FakeInstrument)
