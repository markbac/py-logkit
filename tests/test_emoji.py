"""Tests for the level emoji in the verbose console layout."""

import logging

from ctxlogkit import log_setup, setup_logging

STANDARD_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def test_emoji_map_only_names_registered_levels():
    """Every emoji entry belongs to a level that exists, so none is dead code."""
    registered = {logging.getLevelName(n) for n in (10, 20, 30, 40, 50)}

    assert set(log_setup._LEVEL_EMOJI) == STANDARD_LEVELS == registered


def test_emoji_is_shown_by_default(capsys):
    """The verbose layout puts the emoji right after the level name."""
    setup_logging("emoji-on", level="DEBUG")

    logging.getLogger("emoji-on").error("boom")

    assert "[ERROR ❌]" in capsys.readouterr().out


def test_emoji_can_be_disabled(capsys):
    """Without emoji the level name is not followed by stray spacing."""
    setup_logging("emoji-off", use_emoji=False)

    logging.getLogger("emoji-off").error("boom")

    out = capsys.readouterr().out
    assert "[ERROR]" in out
    assert "❌" not in out


def test_unknown_level_has_no_emoji_and_no_spacing(capsys):
    """A custom level prints cleanly."""
    logging.addLevelName(25, "NOTICE")
    setup_logging("emoji-custom", level="DEBUG")

    logging.getLogger("emoji-custom").log(25, "custom")

    assert "[NOTICE]" in capsys.readouterr().out
