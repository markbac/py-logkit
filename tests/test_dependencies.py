"""Tests that declared dependencies are real, installable distributions."""

import ast
import importlib.metadata
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def _names(requirements):
    """Return the distribution names from an iterable of requirement strings."""
    return {NAME.match(line.strip()).group(0).lower() for line in requirements}


def _requirements_txt():
    lines = (ROOT / "requirements.txt").read_text().splitlines()
    return [line for line in lines if line.strip() and not line.startswith("#")]


def _setup_py_install_requires():
    tree = ast.parse((ROOT / "setup.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "install_requires":
            return ast.literal_eval(node.value)
    raise AssertionError("install_requires not found in setup.py")


def test_requirements_resolve_to_real_distributions():
    """A misspelt dependency name (for example ``colourlog``) must be caught."""
    for name in _names(_requirements_txt()):
        importlib.metadata.distribution(name)


def test_setup_py_matches_requirements_txt():
    """The two dependency lists must not drift apart."""
    assert _names(_setup_py_install_requires()) == _names(_requirements_txt())
