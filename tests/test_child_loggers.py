"""Tests that records from child loggers get context fields and emoji."""

import json
import logging

import pytest

from pylogkit import set_log_context, setup_logging


def test_child_logger_records_are_formatted(capsys):
    """A record from ``app.db`` used to fail with ``ValueError`` on ``emoji``."""
    setup_logging("child-app")

    logging.getLogger("child-app.db").info("from child")

    captured = capsys.readouterr()
    assert "from child" in captured.out
    assert "ValueError" not in captured.err
    assert "Formatting field not found" not in captured.err


def test_child_logger_records_carry_global_context(capsys):
    """Context fields reach records that propagate from child loggers."""
    set_log_context(user_id="alice")
    setup_logging("child-ctx")

    logging.getLogger("child-ctx.worker").info("work")

    assert "[user_id=alice]" in capsys.readouterr().out


@pytest.mark.json_logger
def test_child_logger_records_reach_the_json_file(tmp_path):
    """The JSON handler also sees the context fields for child records."""
    path = tmp_path / "app.json.log"
    set_log_context(request_id="req-9")
    logger = setup_logging(
        "child-json", to_console=False, to_json_file=True, json_file_path=str(path)
    )

    logging.getLogger("child-json.sub").info("hello")
    for handler in logger.handlers:
        handler.flush()

    record = json.loads(path.read_text().strip())
    assert record["request_id"] == "req-9"
    assert record["logger"] == "child-json.sub"
