"""Bounded lifecycle management for multiprocessing workers."""

from multiprocessing import Process
from multiprocessing.queues import Queue
from typing import Any, Callable, Iterable

from .logging_config import configure_application_logging


def _run_with_application_logging(target: Callable[..., Any], args: tuple[Any, ...]) -> Any:
    """Initialize logging before running a target in a child process."""
    configure_application_logging()
    return target(*args)


class ProcessManager:
    """Start and stop child processes with cooperative shutdown first."""

    def __init__(self, join_timeout_s: float = 2.0):
        self.join_timeout_s = join_timeout_s

    def start(self, target: Callable[..., Any], args: Iterable[Any] = ()) -> Process:
        process = Process(target=_run_with_application_logging, args=(target, tuple(args)))
        process.start()
        return process

    def stop(self, process: Process | None, control_queue: Queue | None = None) -> None:
        if process is None:
            return
        try:
            if process.is_alive() and control_queue is not None:
                control_queue.put_nowait("stop")
            if process.is_alive():
                process.join(self.join_timeout_s)
            if process.is_alive():
                process.terminate()
                process.join(self.join_timeout_s)
        finally:
            try:
                process.close()
            except ValueError:
                # A process that failed before starting cannot be closed.
                pass

    def stop_many(self, workers: Iterable[tuple[Process | None, Queue | None]]) -> None:
        for process, control_queue in workers:
            self.stop(process, control_queue)
