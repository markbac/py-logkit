"""Tests for :func:`pylogkit.log_setup.log_exception`."""

import logging

from pylogkit import log_exception


def test_logs_an_error_with_the_traceback(caplog):
    """The helper records ERROR level and attaches the active exception."""
    logger = logging.getLogger("log-exception-test")

    with caplog.at_level(logging.ERROR, logger=logger.name):
        try:
            1 / 0
        except ZeroDivisionError:
            log_exception(logger, "division failed")

    (record,) = caplog.records
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "division failed"
    assert record.exc_info[0] is ZeroDivisionError
