"""Tests that build, cache and log output stays out of version control."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="needs git and a checkout of the repository",
)


@pytest.mark.parametrize(
    "path",
    [
        "ctxlogkit/__pycache__/log_setup.cpython-313.pyc",
        "dist/ctxlogkit-0.1.0-py3-none-any.whl",
        "build/lib/ctxlogkit/__init__.py",
        "ctxlogkit.egg-info/PKG-INFO",
        ".venv/bin/python",
        ".pytest_cache/README.md",
        ".mypy_cache/CACHEDIR.TAG",
        ".ruff_cache/CACHEDIR.TAG",
        ".coverage",
        "app.log",
        "logs/example.json",
    ],
)
def test_generated_files_are_ignored(path):
    """``git check-ignore`` exits with 0 for ignored paths."""
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, check=False)

    assert result.returncode == 0, f"{path} is not ignored"


@pytest.mark.parametrize("path", ["ctxlogkit/log_setup.py", "tests/test_gitignore.py", "README.md"])
def test_source_files_are_not_ignored(path):
    """The patterns must not hide real source files."""
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, check=False)

    assert result.returncode == 1, f"{path} is ignored"
