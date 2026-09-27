"""Application-level routing for channel worker messages."""

from collections.abc import Callable
from multiprocessing.queues import Queue
import queue
from typing import Any


class MessageRouter:
    """Drain channel queues and translate messages into state updates.

    The router is deliberately independent of Qt. A GUI timer can call
    :meth:`drain` while headless tests can call it directly.
    """

    def drain(
        self,
        channel: int,
        data_queue: Queue,
        on_message: Callable[[int, dict[str, Any]], None],
    ) -> int:
        count = 0
        while True:
            try:
                message = data_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(message, dict):
                on_message(channel, message)
                count += 1
        return count
