"""Tests for configuration through ``LOG_LEVEL``, ``LOG_FORMAT`` and ``LOG_FILE``."""

import io
import json
import logging

import pytest

from ctxlogkit import setup_logging


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch):
    """Start every test without any of the variables set."""
    for name in ("LOG_LEVEL", "LOG_FORMAT", "LOG_FILE"):
        monkeypatch.delenv(name, raising=False)


def test_defaults_without_environment():
    """With nothing set the behaviour is unchanged: INFO, console only."""
    logger = setup_logging("env-default")

    assert logger.handlers[0].level == logging.INFO
    assert len(logger.handlers) == 1


def test_log_level_from_environment(monkeypatch):
    """``LOG_LEVEL`` sets the level when ``level`` is not passed."""
    monkeypatch.setenv("LOG_LEVEL", "debug")

    logger = setup_logging("env-level")

    assert logger.handlers[0].level == logging.DEBUG


def test_explicit_level_overrides_environment(monkeypatch):
    """An explicit argument beats the environment."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    logger = setup_logging("env-level-arg", level="ERROR")

    assert logger.handlers[0].level == logging.ERROR


def test_invalid_log_level_is_rejected(monkeypatch):
    """A bad level name fails loudly instead of being ignored."""
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    with pytest.raises(ValueError, match="LOUD"):
        setup_logging("env-level-bad")


def test_log_file_enables_file_logging(monkeypatch, tmp_path):
    """``LOG_FILE`` turns on the plain-text file at that path."""
    path = tmp_path / "from-env.log"
    monkeypatch.setenv("LOG_FILE", str(path))

    setup_logging("env-file", to_console=False).info("hello")

    assert "hello" in path.read_text(encoding="utf-8")


def test_explicit_file_arguments_override_environment(monkeypatch, tmp_path):
    """``file_path`` and ``to_file=False`` both beat ``LOG_FILE``."""
    env_path = tmp_path / "env.log"
    own_path = tmp_path / "own.log"
    monkeypatch.setenv("LOG_FILE", str(env_path))

    setup_logging("env-file-path", to_console=False, file_path=str(own_path)).info("a")
    setup_logging("env-file-off", to_console=False, to_file=False).info("b")

    assert own_path.exists()
    assert not env_path.exists()


def test_compact_format_from_environment(monkeypatch):
    """``LOG_FORMAT=compact`` selects the compact layout."""
    monkeypatch.setenv("LOG_FORMAT", "compact")
    stream = io.StringIO()

    setup_logging("env-compact", console_stream=stream).info("hi")

    assert stream.getvalue().strip() == "[INFO] hi"


@pytest.mark.json_logger
def test_json_format_from_environment(monkeypatch):
    """``LOG_FORMAT=json`` writes JSON lines to the console."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    stream = io.StringIO()

    setup_logging("env-json", console_stream=stream).info("hi")

    assert json.loads(stream.getvalue())["message"] == "hi"


@pytest.mark.json_logger
def test_auto_format_is_json_when_not_a_terminal(monkeypatch):
    """``auto`` picks JSON for a pipe or file."""
    monkeypatch.setenv("LOG_FORMAT", "auto")
    stream = io.StringIO()

    setup_logging("env-auto-pipe", console_stream=stream).info("hi")

    assert json.loads(stream.getvalue())["message"] == "hi"


def test_auto_format_is_pretty_on_a_terminal(monkeypatch):
    """``auto`` picks the verbose layout for a terminal."""
    monkeypatch.setenv("LOG_FORMAT", "auto")
    monkeypatch.setenv("NO_COLOR", "1")

    class Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    stream = Terminal()

    setup_logging("env-auto-tty", console_stream=stream).info("hi")

    assert "env-auto-tty" in stream.getvalue()
    assert not stream.getvalue().lstrip().startswith("{")


def test_explicit_mode_overrides_log_format(monkeypatch):
    """Passing ``mode`` or ``use_json`` makes ``LOG_FORMAT`` irrelevant, even when invalid."""
    monkeypatch.setenv("LOG_FORMAT", "nonsense")
    stream = io.StringIO()

    setup_logging("env-mode", mode="compact", console_stream=stream).info("hi")

    assert stream.getvalue().strip() == "[INFO] hi"


def test_unknown_log_format_is_rejected(monkeypatch):
    """A typo in ``LOG_FORMAT`` raises a clear error."""
    monkeypatch.setenv("LOG_FORMAT", "yaml")

    with pytest.raises(ValueError, match="LOG_FORMAT"):
        setup_logging("env-format-bad")
