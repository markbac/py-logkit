"""Smoke test for the example in ``python -m ctxlogkit.log_setup``."""

import runpy
import time

import pytest

from ctxlogkit import log_setup

pytestmark = pytest.mark.json_logger


def test_module_demo_runs_and_writes_its_log_files(tmp_path, monkeypatch, capsys):
    """The built-in demo exercises most features end to end."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)

    runpy.run_path(log_setup.__file__, run_name="__main__")

    assert "Division by zero error" in (tmp_path / "logs" / "example.log").read_text()
    assert (tmp_path / "logs" / "example.json").read_text().strip()
    assert "Critical failure." in capsys.readouterr().out
