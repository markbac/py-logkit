"""Tests for :func:`ctxlogkit.log_setup.log_exception`."""

import logging

from ctxlogkit import log_exception


def test_logs_an_error_with_the_traceback(caplog):
    """The helper records ERROR level and attaches the active exception."""
    logger = logging.getLogger("log-exception-test")

    with caplog.at_level(logging.ERROR, logger=logger.name):
        try:
            _ = 1 / 0
        except ZeroDivisionError:
            log_exception(logger, "division failed")

    (record,) = caplog.records
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "division failed"
    assert record.exc_info[0] is ZeroDivisionError
