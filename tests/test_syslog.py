"""Tests for the syslog handler, using a local UDP socket as the server."""

import socket
from logging.handlers import SysLogHandler

import pytest

from ctxlogkit import set_log_context, setup_logging, setup_syslog_logger


@pytest.fixture
def udp_server():
    """A UDP socket on an ephemeral localhost port, standing in for syslogd."""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(2)
    yield server
    server.close()


def _receive(server):
    return server.recv(4096).decode()


def test_syslog_address_is_configurable(udp_server):
    """The address was hardcoded to ``localhost:514``."""
    logger = setup_logging(
        "syslog-addr",
        to_console=False,
        to_syslog=True,
        syslog_address=udp_server.getsockname(),
    )

    logger.info("hello")

    message = _receive(udp_server)
    assert "INFO" in message
    assert "hello" in message


def test_syslog_facility_is_configurable(udp_server):
    """The priority prefix encodes ``facility * 8 + severity`` (local0 info = 134)."""
    logger = setup_logging(
        "syslog-facility",
        to_console=False,
        to_syslog=True,
        syslog_address=udp_server.getsockname(),
        syslog_facility=SysLogHandler.LOG_LOCAL0,
    )

    logger.info("hello")

    assert _receive(udp_server).startswith("<134>")


def test_syslog_lines_include_context_fields(udp_server):
    """Syslog output carries the same context fields as the other handlers."""
    set_log_context(user_id="alice")
    logger = setup_logging(
        "syslog-context",
        to_console=False,
        to_syslog=True,
        syslog_address=udp_server.getsockname(),
    )

    logger.info("hello")

    assert "[user_id=alice]" in _receive(udp_server)


def test_setup_syslog_logger_is_deprecated_but_still_works(udp_server):
    """The old helper warns and delegates to ``setup_logging``."""
    with pytest.warns(DeprecationWarning, match="setup_logging"):
        logger = setup_syslog_logger(
            "syslog-legacy", level="DEBUG", address=udp_server.getsockname()
        )

    logger.debug("legacy")

    assert "legacy" in _receive(udp_server)
    assert [type(h) for h in logger.handlers] == [SysLogHandler]
