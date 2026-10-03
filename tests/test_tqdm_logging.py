"""Tests for :func:`pylogkit.log_setup.tqdm_logging`."""

import logging

import pytest

from pylogkit import log_setup
from pylogkit.log_setup import tqdm_logging

LOGGER = logging.getLogger("tqdm-test")


def test_yields_every_item_with_tqdm_branch(monkeypatch):
    """The tqdm branch must hand the items through, not end the generator."""
    monkeypatch.setattr(log_setup, "tqdm", lambda iterable: iter(list(iterable)))
    assert list(tqdm_logging(range(3), LOGGER)) == [0, 1, 2]


def test_yields_every_item_with_real_tqdm():
    """Same check against the real library when it is installed."""
    pytest.importorskip("tqdm")
    assert list(tqdm_logging(range(3), LOGGER)) == [0, 1, 2]


def test_fallback_logs_progress_for_sized_iterable(monkeypatch, caplog):
    """Without tqdm each item produces a ``Progress: n/total`` message."""
    monkeypatch.setattr(log_setup, "tqdm", None)
    with caplog.at_level(logging.INFO, logger=LOGGER.name):
        assert list(tqdm_logging(["a", "b"], LOGGER)) == ["a", "b"]
    assert [r.getMessage() for r in caplog.records] == ["Progress: 1/2", "Progress: 2/2"]


def test_fallback_supports_unsized_iterables(monkeypatch, caplog):
    """Generators have no ``len()``, which previously raised ``TypeError``."""
    monkeypatch.setattr(log_setup, "tqdm", None)
    with caplog.at_level(logging.INFO, logger=LOGGER.name):
        assert list(tqdm_logging((n for n in range(2)), LOGGER)) == [0, 1]
    assert [r.getMessage() for r in caplog.records] == ["Progress: 1", "Progress: 2"]


def test_fallback_honours_level(monkeypatch, caplog):
    """The configured level name selects the logger method used."""
    monkeypatch.setattr(log_setup, "tqdm", None)
    with caplog.at_level(logging.DEBUG, logger=LOGGER.name):
        list(tqdm_logging([1], LOGGER, level="debug"))
    assert [r.levelno for r in caplog.records] == [logging.DEBUG]
