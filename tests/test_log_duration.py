"""Tests for :func:`ctxlogkit.log_setup.log_duration`."""

import itertools
import logging

import pytest

from ctxlogkit import log_duration, log_setup

LOGGER = logging.getLogger("duration-test")


def _fake_clock(monkeypatch, start=10.0, end=12.5):
    ticks = itertools.chain([start, end], itertools.repeat(end))
    monkeypatch.setattr(log_setup.time, "perf_counter", lambda: next(ticks))


def test_logs_duration_and_returns_result(monkeypatch, caplog):
    """A successful call logs ``took`` and passes the result through."""
    _fake_clock(monkeypatch)

    @log_duration(LOGGER)
    def work(a, b=1):
        return a + b

    with caplog.at_level(logging.INFO, logger=LOGGER.name):
        assert work(1, b=2) == 3

    assert [r.getMessage() for r in caplog.records] == ["work took 2.5000 seconds"]


def test_logs_duration_when_the_function_raises(monkeypatch, caplog):
    """Failures used to be untimed because logging came after the call."""
    _fake_clock(monkeypatch)

    @log_duration(LOGGER)
    def boom():
        raise RuntimeError("bad")

    with caplog.at_level(logging.INFO, logger=LOGGER.name):
        with pytest.raises(RuntimeError, match="bad"):
            boom()

    assert [r.getMessage() for r in caplog.records] == ["boom failed after 2.5000 seconds"]


def test_uses_the_requested_level(caplog):
    """The ``level`` argument selects the record level, case-insensitively."""

    @log_duration(LOGGER, level="DEBUG")
    def work():
        return None

    with caplog.at_level(logging.DEBUG, logger=LOGGER.name):
        work()

    assert [r.levelno for r in caplog.records] == [logging.DEBUG]


def test_unknown_level_fails_when_decorating():
    """A typo must fail immediately, not on the first call of the function."""
    with pytest.raises(ValueError, match="nonsense"):
        log_duration(LOGGER, level="nonsense")


def test_preserves_function_metadata():
    """``functools.wraps`` keeps the name and docstring of the original."""

    @log_duration(LOGGER)
    def documented():
        """Docstring."""

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "Docstring."
