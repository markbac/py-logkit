"""Tests that keep the README accurate."""

import inspect
import re
from pathlib import Path

import pytest

from pylogkit import setup_logging

README = (Path(__file__).resolve().parent.parent / "README.md").read_text()


def _python_blocks():
    return re.findall(r"```python\n(.*?)```", README, re.S)


@pytest.mark.json_logger
def test_quick_start_and_context_examples_run(tmp_path, monkeypatch):
    """The first two Python examples are complete programs and must work."""
    monkeypatch.chdir(tmp_path)
    namespace = {}

    for block in _python_blocks()[:2]:
        exec(compile(block, "README.md", "exec"), namespace)

    assert (tmp_path / "logs" / "app.log").read_text()
    assert (tmp_path / "logs" / "app.json.log").read_text()


def test_every_setup_logging_argument_is_documented():
    """New arguments must be added to the options table in the README."""
    for name in inspect.signature(setup_logging).parameters:
        assert f"| `{name}` |" in README, f"{name} is missing from the README table"
