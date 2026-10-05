"""Tests for the content of JSON log records."""

import json
from datetime import datetime

import pytest

from ctxlogkit import log_setup, set_log_context, setup_logging

pytestmark = pytest.mark.json_logger


def _json_lines(path, logger):
    for handler in logger.handlers:
        handler.flush()
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_records_carry_timestamp_level_logger_and_message(tmp_path):
    """JSON lines were missing everything except the message."""
    path = tmp_path / "app.json.log"
    logger = setup_logging(
        "json-core", to_console=False, to_json_file=True, json_file_path=str(path)
    )

    logger.warning("careful")

    (record,) = _json_lines(path, logger)
    assert record["level"] == "WARNING"
    assert record["logger"] == "json-core"
    assert record["message"] == "careful"
    datetime.strptime(record["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
    assert list(record)[:4] == ["timestamp", "level", "logger", "message"]


def test_context_fields_are_included(tmp_path):
    """The context fields remain part of every JSON record."""
    path = tmp_path / "app.json.log"
    set_log_context(user_id="alice", request_id="req-1")
    logger = setup_logging(
        "json-ctx", to_console=False, to_json_file=True, json_file_path=str(path)
    )

    logger.info("x")

    (record,) = _json_lines(path, logger)
    assert record["user_id"] == "alice"
    assert record["request_id"] == "req-1"
    assert record["session_id"] == "-"


def test_internal_text_fields_are_not_leaked(tmp_path):
    """``emoji`` and ``context`` are for text output, and must not reach JSON.

    The plain-text file handler formats the record first, which used to leave
    its helper ``context`` field on the record shared with the JSON handler.
    """
    json_path = tmp_path / "app.json.log"
    text_path = tmp_path / "app.log"
    logger = setup_logging(
        "json-leak",
        to_console=False,
        to_file=True,
        file_path=str(text_path),
        to_json_file=True,
        json_file_path=str(json_path),
    )

    logger.info("x")

    (record,) = _json_lines(json_path, logger)
    assert "emoji" not in record
    assert "context" not in record


def test_exceptions_are_included(tmp_path):
    """``logger.exception`` produces an ``exc_info`` field with the traceback."""
    path = tmp_path / "app.json.log"
    logger = setup_logging(
        "json-exc", to_console=False, to_json_file=True, json_file_path=str(path)
    )

    try:
        _ = 1 / 0
    except ZeroDivisionError:
        logger.exception("failed")

    (record,) = _json_lines(path, logger)
    assert "ZeroDivisionError" in record["exc_info"]


def test_console_json_has_the_same_fields(capsys):
    """``use_json`` console output uses the same layout as the JSON file."""
    setup_logging("json-console", use_json=True).error("bad")

    record = json.loads(capsys.readouterr().out)
    assert (record["level"], record["logger"], record["message"]) == (
        "ERROR",
        "json-console",
        "bad",
    )


def test_text_formatters_do_not_leave_context_on_the_record():
    """``SmartFieldFormatter`` must clean up the helper field it adds."""
    import logging

    record = logging.LogRecord("t", logging.INFO, __file__, 1, "m", None, None)
    record.emoji = ""

    log_setup._build_console_formatter().format(record)

    assert not hasattr(record, "context")
