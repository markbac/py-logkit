"""Tests that ``setup_logging`` options have the documented effect."""

import json

import pytest

from pylogkit import log_setup, setup_logging


def _flush(logger):
    for handler in logger.handlers:
        handler.flush()


def test_overwrite_truncates_existing_files(tmp_path):
    """``overwrite=True`` starts the plain-text and JSON files afresh."""
    plain = tmp_path / "app.log"
    jsonl = tmp_path / "app.json.log"
    plain.write_text("stale plain\n")
    jsonl.write_text("stale json\n")

    logger = setup_logging(
        "opt-overwrite",
        to_console=False,
        to_file=True,
        file_path=str(plain),
        to_json_file=True,
        json_file_path=str(jsonl),
        overwrite=True,
    )
    logger.info("fresh")
    _flush(logger)

    assert "stale" not in plain.read_text() + jsonl.read_text()
    assert "fresh" in plain.read_text()


def test_append_is_the_default(tmp_path):
    """Without ``overwrite`` existing content is kept."""
    plain = tmp_path / "app.log"
    plain.write_text("kept\n")

    logger = setup_logging(
        "opt-append", to_console=False, to_file=True, file_path=str(plain)
    )
    logger.info("added")
    _flush(logger)

    assert plain.read_text().startswith("kept\n")
    assert "added" in plain.read_text()


def test_use_json_writes_json_to_the_console(capsys):
    """``use_json`` used to be accepted and ignored."""
    logger = setup_logging("opt-json-console", use_json=True)

    logger.info("hello")

    record = json.loads(capsys.readouterr().out.strip())
    assert record["message"] == "hello"


def test_compact_mode_is_honoured_with_json_library_installed(capsys):
    """The JSON library being importable must not override ``mode``."""
    assert log_setup.jsonlogger is not None
    logger = setup_logging("opt-compact", mode="compact")

    logger.info("hello")

    assert capsys.readouterr().out.strip() == "[INFO] hello"


def test_json_file_contains_valid_json_lines(tmp_path):
    """The JSON file handler writes one JSON object per record."""
    path = tmp_path / "app.json.log"
    logger = setup_logging(
        "opt-json-file", to_console=False, to_json_file=True, json_file_path=str(path)
    )

    logger.info("hello")
    _flush(logger)

    assert json.loads(path.read_text().strip())["message"] == "hello"


@pytest.mark.parametrize("option", [{"use_json": True}, {"to_json_file": True}])
def test_json_options_fail_clearly_without_the_library(monkeypatch, option):
    """Requesting JSON output without python-json-logger raises ImportError."""
    monkeypatch.setattr(log_setup, "jsonlogger", None)

    with pytest.raises(ImportError, match="python-json-logger"):
        setup_logging("opt-missing-lib", to_console=False, **option)
