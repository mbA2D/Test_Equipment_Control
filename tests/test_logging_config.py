import logging

from battery_app.logging_config import configure_application_logging


def test_application_logging_writes_process_context_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_EQUIPMENT_LOG_DIR", raising=False)
    log_path = configure_application_logging(tmp_path)
    logger = logging.getLogger("tests.application_logging")
    logger.info("logging smoke test")

    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path == tmp_path / "application.log"
    content = log_path.read_text(encoding="utf-8")
    assert "INFO" in content
    assert "tests.application_logging" in content
    assert "logging smoke test" in content
    assert "MainProcess" in content

    handler_count = len(logging.getLogger().handlers)
    configure_application_logging(tmp_path)
    assert len(logging.getLogger().handlers) == handler_count
