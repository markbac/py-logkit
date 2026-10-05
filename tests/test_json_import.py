"""Tests for how the optional python-json-logger dependency is imported."""

import subprocess
import sys

import pytest

from ctxlogkit import log_setup


def test_import_emits_no_deprecation_warning():
    """The deprecated ``pythonjsonlogger.jsonlogger`` path must not be used."""
    result = subprocess.run(
        [sys.executable, "-W", "error::DeprecationWarning", "-c", "import ctxlogkit"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.json_logger
def test_json_formatter_is_resolved():
    """python-json-logger is a declared dependency, so the class must resolve."""
    assert log_setup.JsonFormatter is not None


@pytest.mark.json_logger
def test_build_json_formatter_returns_a_logging_formatter():
    """The helper returns an instance usable as a handler formatter."""
    formatter = log_setup._build_json_formatter()

    assert hasattr(formatter, "format")


def test_missing_library_is_reported(monkeypatch):
    """Without the library the helper raises with an install hint."""
    monkeypatch.setattr(log_setup, "JsonFormatter", None)

    with pytest.raises(ImportError, match="pip install python-json-logger"):
        log_setup._build_json_formatter()
