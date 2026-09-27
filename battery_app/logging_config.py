"""Application-wide logging for the battery test application.

The application starts several Windows multiprocessing workers.  Each process
therefore configures its own handler, all pointing at the same rotating log
file.  Handler setup is idempotent so repeated initialization does not
duplicate messages.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path


APPLICATION_LOG_DIR_ENV = "TEST_EQUIPMENT_LOG_DIR"
DEFAULT_LOG_DIR_NAME = "logs"
APPLICATION_LOG_FILENAME = "application.log"
_HANDLER_MARKER = "test_equipment_application_log"


def get_application_log_directory(log_directory: str | os.PathLike[str] | None = None) -> Path:
    """Return the configured application log directory.

    The environment variable lets the GUI choose a stable location and is
    inherited by Windows child processes.  The current working directory is a
    useful fallback for direct worker/test invocation.
    """
    configured = log_directory or os.environ.get(APPLICATION_LOG_DIR_ENV)
    directory = Path(configured) if configured else Path.cwd() / DEFAULT_LOG_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def configure_application_logging(
    log_directory: str | os.PathLike[str] | None = None,
    level: int = logging.INFO,
) -> Path:
    """Configure the process-wide logger and return the log file path."""
    directory = get_application_log_directory(log_directory)
    os.environ[APPLICATION_LOG_DIR_ENV] = str(directory)
    log_path = directory / APPLICATION_LOG_FILENAME

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    existing_handlers = [
        handler for handler in root_logger.handlers
        if getattr(handler, "_test_equipment_marker", None) == _HANDLER_MARKER
    ]
    matching_handler = next(
        (handler for handler in existing_handlers
         if Path(getattr(handler, "baseFilename", "")).resolve() == log_path.resolve()),
        None,
    )
    if matching_handler is None:
        for handler in existing_handlers:
            root_logger.removeHandler(handler)
            handler.close()
        handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler._test_equipment_marker = _HANDLER_MARKER
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(processName)s[%(process)d] | "
            "%(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root_logger.addHandler(handler)

    return log_path


def get_logger(name: str) -> logging.Logger:
    """Return an application logger without configuring handlers implicitly."""
    return logging.getLogger(name)
