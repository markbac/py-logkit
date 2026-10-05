"""Tests that repeated ``setup_logging`` calls replace, not accumulate, state."""

import logging

from ctxlogkit import setup_logging
from ctxlogkit.log_setup import ContextFilter


def _context_filters(obj):
    return [f for f in obj.filters if isinstance(f, ContextFilter)]


def test_repeated_setup_keeps_a_single_context_filter_per_handler():
    """Each call used to add another ``ContextFilter`` to the logger."""
    setup_logging("idem-filter")
    logger = setup_logging("idem-filter")

    assert _context_filters(logger) == []
    assert logger.handlers
    for handler in logger.handlers:
        assert len(_context_filters(handler)) == 1


def test_repeated_setup_emits_one_line_per_record(tmp_path):
    """Two calls must not write each record twice to the same file."""
    path = tmp_path / "app.log"
    setup_logging("idem-lines", to_console=False, to_file=True, file_path=str(path))
    logger = setup_logging("idem-lines", to_console=False, to_file=True, file_path=str(path))

    logger.info("once")
    for handler in logger.handlers:
        handler.flush()

    assert path.read_text().count("once") == 1


def test_previous_handlers_are_closed(tmp_path):
    """Dropped file handlers must release their file descriptors."""
    path = tmp_path / "app.log"
    first = setup_logging("idem-close", to_console=False, to_file=True, file_path=str(path))
    old_handler = first.handlers[0]
    assert old_handler.stream is not None

    setup_logging("idem-close", to_console=False, to_file=True, file_path=str(path))

    assert old_handler.stream is None


def test_propagation_is_off_by_default(caplog):
    """Records must not also reach ancestor handlers unless asked to."""
    logger = setup_logging("idem-propagate", to_console=False)

    with caplog.at_level(logging.INFO):
        logger.info("hidden")

    assert "hidden" not in caplog.text
    assert logger.propagate is False


def test_propagation_can_be_enabled(caplog):
    """``propagate=True`` restores standard logging hierarchy behaviour."""
    logger = setup_logging("idem-propagate-on", to_console=False, propagate=True)

    with caplog.at_level(logging.INFO):
        logger.info("visible")

    assert "visible" in caplog.text
