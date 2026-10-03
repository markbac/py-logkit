"""Tests that declared dependencies are real, installable distributions.

These tests read the metadata of the installed ``pylogkit`` distribution, so
run them in an environment created with ``pip install -e ".[all,dev]"``.
"""

import importlib.metadata
import re

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def _requirement_names():
    """Return the distribution names of every declared requirement."""
    requires = importlib.metadata.requires("pylogkit") or []
    return {NAME.match(requirement).group(0) for requirement in requires}


def test_core_dependency_is_colorlog():
    """The only mandatory dependency is ``colorlog`` (not the misspelt name)."""
    core = [
        r for r in importlib.metadata.requires("pylogkit") if "extra ==" not in r
    ]

    assert [NAME.match(r).group(0) for r in core] == ["colorlog"]


def test_optional_features_are_extras():
    """JSON output and progress bars are optional extras."""
    extras = set(importlib.metadata.metadata("pylogkit").get_all("Provides-Extra"))

    assert {"json", "progress", "all", "dev"} <= extras


def test_requirements_resolve_to_real_distributions():
    """A misspelt dependency name (for example ``colourlog``) must be caught."""
    for name in _requirement_names():
        importlib.metadata.distribution(name)
