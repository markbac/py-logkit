"""Tests for console colour detection and the console stream option."""

import io
import sys

import pytest

from ctxlogkit import setup_logging


class FakeTTY(io.StringIO):
    """A text stream that claims to be an interactive terminal."""

    def isatty(self):
        return True


@pytest.fixture(autouse=True)
def _clean_colour_environment(monkeypatch):
    """Make the tests independent of the colour settings of the host or CI."""
    for name in ("NO_COLOR", "FORCE_COLOR", "TERM"):
        monkeypatch.delenv(name, raising=False)


def _log_to(stream, name):
    logger = setup_logging(name, console_stream=stream)
    logger.info("hello")
    return stream.getvalue()


def test_colour_is_used_on_a_terminal():
    """Interactive terminals keep the coloured output."""
    assert "\x1b[" in _log_to(FakeTTY(), "colour-tty")


def test_colour_is_disabled_when_output_is_not_a_terminal():
    """Piped or redirected output must not contain escape codes."""
    output = _log_to(io.StringIO(), "colour-pipe")

    assert "\x1b" not in output
    assert "hello" in output


def test_no_color_disables_colour_on_a_terminal(monkeypatch):
    """The ``NO_COLOR`` convention is honoured."""
    monkeypatch.setenv("NO_COLOR", "1")

    assert "\x1b" not in _log_to(FakeTTY(), "colour-no-color")


def test_dumb_terminals_get_no_colour(monkeypatch):
    """``TERM=dumb`` terminals cannot render escape codes."""
    monkeypatch.setenv("TERM", "dumb")

    assert "\x1b" not in _log_to(FakeTTY(), "colour-dumb")


def test_force_color_enables_colour_when_piped(monkeypatch):
    """``FORCE_COLOR`` is the documented override for CI systems."""
    monkeypatch.setenv("FORCE_COLOR", "1")

    assert "\x1b[" in _log_to(io.StringIO(), "colour-force")


def test_console_stream_redirects_output(capsys):
    """Records go to the chosen stream and nothing reaches stdout."""
    stream = io.StringIO()

    setup_logging("stream-custom", console_stream=stream).info("to the buffer")

    assert "to the buffer" in stream.getvalue()
    assert capsys.readouterr().out == ""


def test_console_stream_can_be_stderr(capsys):
    """Diagnostics can go to stderr, as is conventional for logs."""
    setup_logging("stream-stderr", console_stream=sys.stderr).info("on stderr")

    captured = capsys.readouterr()
    assert "on stderr" in captured.err
    assert captured.out == ""


def test_default_stream_is_stdout(capsys):
    """Behaviour is unchanged for callers that do not pass a stream."""
    setup_logging("stream-default").info("on stdout")

    assert "on stdout" in capsys.readouterr().out
