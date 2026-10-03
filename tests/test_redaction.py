"""Tests for masking secrets with ``redact_keys`` and ``redact_patterns``."""

import json
import logging

import pytest

from pylogkit import (
    DEFAULT_REDACT_KEYS,
    ContextualLoggerAdapter,
    RedactionFilter,
    set_log_context,
    setup_logging,
    shutdown_logging,
)


def _record(msg="hello", args=(), **extra):
    """Build a record with extra attributes the way ``extra=`` does."""
    record = logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)
    record.__dict__.update(extra)
    return record


def test_matching_fields_are_masked_case_insensitively_by_substring():
    """``token`` masks ``Access_Token`` and ``password`` masks ``db_password``."""
    record = _record(Access_Token="abc", db_password="hunter2", user="alice")

    RedactionFilter(["token", "password"]).filter(record)

    assert record.Access_Token == "***"
    assert record.db_password == "***"
    assert record.user == "alice"


def test_standard_record_attributes_are_never_masked():
    """A key such as ``name`` or ``msg`` must not wipe the logger name or the message."""
    record = _record("the message")

    RedactionFilter(["name", "msg", "message"]).filter(record)

    assert record.name == "t"
    assert record.getMessage() == "the message"


def test_nested_values_are_masked_without_touching_the_callers_objects():
    """Dictionaries inside lists inside extras are searched, on a copy."""
    original = {"user": "alice", "auth": {"password": "p"}, "items": [{"token": "t"}]}
    record = _record(payload=original)

    RedactionFilter(["password", "token"]).filter(record)

    assert record.payload == {
        "user": "alice",
        "auth": {"password": "***"},
        "items": [{"token": "***"}],
    }
    assert original["auth"]["password"] == "p"


def test_patterns_mask_message_text_including_arguments():
    """Matches in the formatted message are replaced, strings or compiled."""
    import re

    record = _record("login %s with Bearer abc123", ("alice",))

    RedactionFilter(patterns=[r"Bearer \S+", re.compile("alice")], mask="[hidden]").filter(record)

    assert record.getMessage() == "login [hidden] with [hidden]"


def test_message_is_left_alone_without_a_match():
    """A message without matches keeps its arguments, so nothing is formatted early."""
    record = _record("value %d", (5,))

    RedactionFilter(patterns=["secret"]).filter(record)

    assert record.msg == "value %d"
    assert record.args == (5,)


def test_filter_is_idempotent():
    """A record passes through once per handler, so a second pass changes nothing."""
    record = _record("Bearer abc", token="t")
    log_filter = RedactionFilter(["token"], [r"Bearer \S+"])

    log_filter.filter(record)
    log_filter.filter(record)

    assert record.getMessage() == "***"
    assert record.token == "***"


def test_default_keys_cover_the_usual_suspects():
    """The exported defaults include the names from the issue."""
    assert {"password", "token", "authorization"} <= set(DEFAULT_REDACT_KEYS)


def test_nothing_is_masked_by_default():
    """Redaction is opt-in: without arguments no handler carries the filter."""
    logger = setup_logging("red-off")

    filters = [f for handler in logger.handlers for f in handler.filters]

    assert filters
    assert not any(isinstance(f, RedactionFilter) for f in filters)


def test_context_fields_are_masked_in_every_handler(tmp_path):
    """Global context, adapter fields and ``extra`` all go through the filter."""
    text = tmp_path / "a.log"
    set_log_context(session_id="sess-1", api_key="KEY-1")
    logger = setup_logging(
        "red-ctx",
        to_console=False,
        to_file=True,
        file_path=str(text),
        redact_keys=["api_key", "request_id"],
    )
    log = ContextualLoggerAdapter(logger).with_context(request_id="REQ-9")

    log.info("hello", extra={"api_key": "KEY-2"})

    contents = text.read_text(encoding="utf-8")
    assert "REQ-9" not in contents
    assert "KEY-" not in contents
    assert "[session_id=sess-1]" in contents


@pytest.mark.json_logger
def test_json_output_is_masked(tmp_path):
    """Extras and message text are masked in the JSON file too."""
    path = tmp_path / "red.json.log"
    logger = setup_logging(
        "red-json",
        to_console=False,
        to_json_file=True,
        json_file_path=str(path),
        redact_keys=DEFAULT_REDACT_KEYS,
        redact_patterns=[r"card=\d+"],
    )

    logger.info("paid card=4111", extra={"authorization": "Bearer x", "order": 7})

    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["message"] == "paid ***"
    assert record["authorization"] == "***"
    assert record["order"] == 7


def test_masking_happens_before_records_are_queued(tmp_path):
    """With ``use_queue`` the secret never reaches the listener thread."""
    path = tmp_path / "q.log"
    set_log_context(token="TOKEN-1")
    logger = setup_logging(
        "red-queue",
        to_console=False,
        to_file=True,
        file_path=str(path),
        use_queue=True,
        redact_keys=["token"],
        redact_patterns=["TOKEN-\\d"],
    )

    logger.info("using TOKEN-1")
    shutdown_logging()

    assert "TOKEN-1" not in path.read_text(encoding="utf-8")
