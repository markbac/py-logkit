"""Tests for the console, file and context formatters."""

import logging

from pylogkit import set_log_context, setup_logging
from pylogkit.log_setup import (
    FILE_FORMAT,
    SmartFieldFormatter,
    _build_console_formatter,
)


def _record(**fields):
    record = logging.LogRecord("t", logging.INFO, __file__, 7, "hello", None, None)
    record.emoji = ""
    for key, value in fields.items():
        setattr(record, key, value)
    return record


def test_context_field_omits_placeholders():
    """Unset values (``""`` and ``"-"``) must not appear in ``%(context)s``."""
    formatter = SmartFieldFormatter("%(context)s|%(message)s", reset=False)

    line = formatter.format(_record(user_id="bob", session_id="-", request_id=""))

    assert line == "[user_id=bob]|hello"


def test_console_formatter_shows_level_location_context_and_message():
    """The verbose console layout carries the documented fields."""
    formatter = _build_console_formatter()

    line = formatter.format(_record(user_id="bob"))

    for expected in ("INFO", "t", "[user_id=bob]", "hello", "test_formatters.py"):
        assert expected in line


def test_file_log_contains_context_and_message(tmp_path):
    """The plain-text file layout includes the context field and the message."""
    path = tmp_path / "app.log"
    set_log_context(user_id="bob")
    logger = setup_logging(
        "fmt-file", to_console=False, to_file=True, file_path=str(path)
    )

    logger.info("hello")
    for handler in logger.handlers:
        handler.flush()

    text = path.read_text()
    assert "[user_id=bob]" in text
    assert "hello" in text


def test_file_format_constant_includes_source_location():
    """The file layout records where each message was logged."""
    assert "%(filename)s:%(lineno)d" in FILE_FORMAT


def test_file_log_has_no_ansi_escape_codes(tmp_path):
    """colorlog appends a reset code unless colour is disabled for files."""
    path = tmp_path / "app.log"
    logger = setup_logging(
        "fmt-no-ansi", to_console=False, to_file=True, file_path=str(path)
    )

    logger.info("hello")
    logger.error("boom")
    for handler in logger.handlers:
        handler.flush()

    assert "\x1b" not in path.read_text()
