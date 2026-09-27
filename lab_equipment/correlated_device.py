"""Correlated proxy transport for shared instrument-owner processes."""

from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
from typing import Any
from uuid import uuid4


class InstrumentRequestError(RuntimeError):
    """A structured failure returned by an instrument-owner process."""

    def __init__(self, error_type: str, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(f"{error_type}: {message}")


class InstrumentRequestTimeout(TimeoutError):
    """The instrument owner did not answer within the request deadline."""


@dataclass
class _PendingResponse:
    event: threading.Event
    value: Any = None
    error: dict[str, Any] | None = None


class _ResponseRouter:
    """Read one shared response queue and route responses by request ID."""

    def __init__(self, response_queue):
        self.response_queue = response_queue
        self.pending: dict[str, _PendingResponse] = {}
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def request(self, request_id: str) -> _PendingResponse:
        pending = _PendingResponse(threading.Event())
        with self.lock:
            self.pending[request_id] = pending
        return pending

    def cancel(self, request_id: str) -> None:
        with self.lock:
            self.pending.pop(request_id, None)

    def _run(self) -> None:
        while True:
            try:
                response = self.response_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            except (EOFError, OSError, BrokenPipeError):
                # The equipment manager owns this private queue.  Its normal
                # shutdown closes the manager connection after all owners stop.
                return
            if not isinstance(response, dict) or "request_id" not in response:
                continue
            request_id = response["request_id"]
            with self.lock:
                pending = self.pending.get(request_id)
            if pending is None:
                continue
            if response.get("ok", False):
                pending.value = response.get("value")
            else:
                pending.error = response.get("error") or {
                    "type": "RemoteError",
                    "message": "Instrument operation failed",
                }
            pending.event.set()

    def wait(self, request_id: str, timeout: float) -> Any:
        with self.lock:
            pending = self.pending.get(request_id)
        if pending is None or not pending.event.wait(timeout):
            self.cancel(request_id)
            raise InstrumentRequestTimeout(
                f"Timed out waiting for instrument request {request_id}"
            )
        self.cancel(request_id)
        if pending.error is not None:
            raise InstrumentRequestError(
                pending.error.get('type', 'RemoteError'),
                pending.error.get('message', 'Instrument operation failed'),
            )
        return pending.value


_ROUTERS: dict[int, _ResponseRouter] = {}
_ROUTERS_LOCK = threading.Lock()


def _router_for(response_queue) -> _ResponseRouter:
    key = id(response_queue)
    with _ROUTERS_LOCK:
        router = _ROUTERS.get(key)
        if router is None:
            router = _ResponseRouter(response_queue)
            _ROUTERS[key] = router
        return router


class CorrelatedVirtualDevice:
    """Queue proxy using correlated, acknowledged requests.

    ``response_queue`` is a private queue for this client. The owner process
    routes responses to it using ``client_id``. A router still correlates
    responses by request ID so concurrent calls from one channel are safe.
    """

    def __init__(
        self,
        queue_in,
        response_queue,
        eq_ch: int = 0,
        timeout_s: float = 10.0,
        *,
        client_id: str,
    ):
        self._queue_in = queue_in
        self._response_queue = response_queue
        if not isinstance(eq_ch, int) or isinstance(eq_ch, bool) or eq_ch < 0:
            raise ValueError("eq_ch must be a non-negative integer")
        self._eq_ch = eq_ch
        self._timeout_s = timeout_s
        self._client_id = client_id
        self._response_router = _router_for(response_queue)

    def _call(
        self,
        operation: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        request_id = str(uuid4())
        self._response_router.request(request_id)
        try:
            self._queue_in.put_nowait({
                "protocol": 2,
                "request_id": request_id,
                "client_id": self._client_id,
                "operation": operation,
                "args": [] if args is None else args,
                "kwargs": {} if kwargs is None else kwargs,
                "instrument_channel": self._eq_ch,
            })
        except Exception:
            self._response_router.cancel(request_id)
            raise
        # The request is registered before publication. The router keeps the
        # pending object alive until the response arrives.
        return self._response_router.wait(request_id, self._timeout_s)

    def attach_battery_link(self, battery_link) -> Any:
        """Give a fake instrument owner its shared simulated-cell proxy."""

        return self._call("attach_battery_link", [battery_link])

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def call(*args, **kwargs):
            value = self._call(name, list(args), kwargs)
            if name.startswith("measure_"):
                return float(value)
            if name in {"get_calibration", "get_cal_v", "get_cal_i"}:
                return [float(item) for item in value]
            if name in {"psu_connected", "eload_connected", "get_output", "get_led", "get_fan"}:
                return bool(value)
            if name in {"get_num_channels", "get_rs485_addr"}:
                return int(value)
            return value

        return call


class PowerSupplyProxy(CorrelatedVirtualDevice):
    """Named proxy for source-capable equipment."""

    def set_voltage(self, voltage_v):
        return self._call("set_voltage", [voltage_v])

    def set_current(self, current_a):
        return self._call("set_current", [current_a])

    def toggle_output(self, state):
        return self._call("toggle_output", [state])

    def measure_voltage(self):
        return float(self._call("measure_voltage"))

    def measure_current(self):
        return float(self._call("measure_current"))


class ElectronicLoadProxy(CorrelatedVirtualDevice):
    """Named proxy for sink-capable equipment."""

    def set_current(self, current_a):
        return self._call("set_current", [current_a])

    def set_mode_current(self):
        return self._call("set_mode_current")

    def toggle_output(self, state):
        return self._call("toggle_output", [state])

    def measure_voltage(self):
        return float(self._call("measure_voltage"))

    def measure_current(self):
        return float(self._call("measure_current"))


class DmmProxy(CorrelatedVirtualDevice):
    """Named proxy for measurement-only equipment."""

    def measure_voltage(self):
        return float(self._call("measure_voltage"))

    def measure_current(self):
        return float(self._call("measure_current"))

    def measure_temperature(self):
        return float(self._call("measure_temperature"))


class RelayProxy(CorrelatedVirtualDevice):
    """Named proxy for isolation and relay equipment."""

    def connect_psu(self, state):
        return self._call("connect_psu", [state])

    def connect_eload(self, state):
        return self._call("connect_eload", [state])
