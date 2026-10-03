"""Tests for non-blocking logging through ``use_queue``."""

import json
import logging
import threading
import time

import pytest

from pylogkit import log_context, log_exception, log_setup, setup_logging, shutdown_logging


@pytest.fixture(autouse=True)
def _stop_listeners():
    """Never leave a listener thread behind."""
    yield
    shutdown_logging()


def test_records_reach_the_file_after_shutdown(tmp_path):
    """Everything logged before ``shutdown_logging`` is written, in order."""
    path = tmp_path / "queued.log"
    logger = setup_logging(
        "q-file", to_console=False, to_file=True, file_path=str(path), use_queue=True
    )

    for i in range(200):
        logger.info("message %d", i)
    shutdown_logging()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert [line.rsplit(" - ", 1)[1] for line in lines] == [f"message {i}" for i in range(200)]


def test_handlers_are_owned_by_the_listener():
    """The logger itself only holds the queue handler."""
    logger = setup_logging("q-owner", use_queue=True)

    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.handlers.QueueHandler)


def test_context_of_the_logging_thread_is_used(tmp_path):
    """The listener thread has no context, so it must be captured when logging."""
    path = tmp_path / "ctx.log"
    logger = setup_logging(
        "q-ctx", to_console=False, to_file=True, file_path=str(path), use_queue=True
    )

    with log_context(request_id="req-q"):
        logger.info("inside")
    shutdown_logging()

    assert "[request_id=req-q]" in path.read_text(encoding="utf-8")


def test_handler_levels_are_respected(tmp_path):
    """A handler with a higher level still filters, as it does without a queue."""
    path = tmp_path / "levels.log"
    logger = setup_logging(
        "q-level",
        to_console=False,
        to_file=True,
        file_path=str(path),
        file_level="ERROR",
        use_queue=True,
    )

    logger.info("quiet")
    logger.error("loud")
    shutdown_logging()

    text = path.read_text(encoding="utf-8")
    assert "loud" in text
    assert "quiet" not in text


@pytest.mark.json_logger
def test_exceptions_keep_their_traceback_field(tmp_path):
    """The traceback stays in ``exc_info`` instead of being folded into the message."""
    path = tmp_path / "exc.json.log"
    logger = setup_logging(
        "q-exc", to_console=False, to_json_file=True, json_file_path=str(path), use_queue=True
    )

    try:
        raise ValueError("bad value")
    except ValueError:
        log_exception(logger, "failed")
    shutdown_logging()

    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["message"] == "failed"
    assert "ValueError: bad value" in record["exc_info"]


def test_slow_handler_does_not_block_the_caller(tmp_path):
    """Logging returns at once while the handler takes its time."""
    release = threading.Event()
    handled = []

    class Slow(logging.Handler):
        def emit(self, record):
            release.wait(5)
            handled.append(record.getMessage())

    logger = setup_logging("q-slow", to_console=False, use_queue=True)
    listener = log_setup._listeners["q-slow"]
    listener.handlers = (Slow(),)

    start = time.perf_counter()
    logger.info("one")
    logger.info("two")
    elapsed = time.perf_counter() - start
    release.set()
    shutdown_logging()

    assert elapsed < 1
    assert handled == ["one", "two"]


def test_reconfiguring_stops_the_previous_listener():
    """Calling ``setup_logging`` again must not leak a listener thread."""
    setup_logging("q-again", to_console=False, use_queue=True)
    first = log_setup._listeners["q-again"]

    setup_logging("q-again", to_console=False, use_queue=True)

    assert log_setup._listeners["q-again"] is not first
    assert first._thread is None


def test_switching_the_queue_off_stops_the_listener():
    """A later call without ``use_queue`` returns to direct handlers."""
    setup_logging("q-off", use_queue=True)

    logger = setup_logging("q-off")

    assert "q-off" not in log_setup._listeners
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_shutdown_is_idempotent_and_closes_files(tmp_path):
    """Calling it twice is harmless and the file handler is closed."""
    path = tmp_path / "close.log"
    setup_logging("q-close", to_console=False, to_file=True, file_path=str(path), use_queue=True)
    handler = log_setup._listeners["q-close"].handlers[0]

    shutdown_logging()
    shutdown_logging()

    assert handler.stream is None
    assert log_setup._listeners == {}
    assert logging.getLogger("q-close").handlers == []


def test_logging_without_a_queue_is_unchanged(capsys):
    """The default stays synchronous."""
    logger = setup_logging("q-default")

    logger.info("direct")

    assert "direct" in capsys.readouterr().out
