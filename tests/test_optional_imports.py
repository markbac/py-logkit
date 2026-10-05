"""Tests for behaviour when optional dependencies are missing.

Each case runs in a fresh interpreter, because imports happen at module load
time and cannot be undone safely inside the test process.
"""

import subprocess
import sys

import pytest


def _run(code):
    return subprocess.run(
        [sys.executable, "-W", "ignore", "-c", code],
        capture_output=True,
        text=True,
    )


def test_tqdm_is_optional():
    """Without tqdm the module still imports and ``tqdm`` is ``None``."""
    result = _run(
        "import sys; sys.modules['tqdm'] = None\n"
        "from ctxlogkit import log_setup\n"
        "assert log_setup.tqdm is None"
    )

    assert result.returncode == 0, result.stderr


def test_json_logger_is_optional():
    """Without python-json-logger the module imports with no formatter."""
    result = _run(
        "import sys\n"
        "sys.modules['pythonjsonlogger'] = None\n"
        "from ctxlogkit import log_setup\n"
        "assert log_setup.JsonFormatter is None"
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.json_logger
def test_old_json_logger_import_path_is_used_as_a_fallback():
    """If ``pythonjsonlogger.json`` is unavailable the 2.x module is used.

    Newer releases implement ``pythonjsonlogger.jsonlogger`` as a shim over
    the new module, so the 2.x layout is simulated with a stand-in module.
    """
    result = _run(
        "import sys, types\n"
        "fake = types.ModuleType('pythonjsonlogger.jsonlogger')\n"
        "class JsonFormatter: pass\n"
        "fake.JsonFormatter = JsonFormatter\n"
        "sys.modules['pythonjsonlogger.json'] = None\n"
        "sys.modules['pythonjsonlogger.jsonlogger'] = fake\n"
        "from ctxlogkit import log_setup\n"
        "assert log_setup.JsonFormatter is JsonFormatter"
    )

    assert result.returncode == 0, result.stderr


def test_colorlog_is_required_and_the_error_says_how_to_install_it():
    """The one mandatory dependency fails with an actionable message."""
    result = _run("import sys; sys.modules['colorlog'] = None\nimport ctxlogkit")

    assert result.returncode != 0
    assert "pip install colorlog" in result.stderr


@pytest.mark.parametrize("module", ["ctxlogkit", "ctxlogkit.log_setup"])
def test_modules_import_cleanly(module):
    """Plain imports must not print anything or emit warnings."""
    result = subprocess.run(
        [sys.executable, "-W", "error", "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
