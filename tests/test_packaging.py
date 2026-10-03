"""Tests that the project is packaged and importable as a real package."""

from pathlib import Path

from setuptools import find_packages

ROOT = Path(__file__).resolve().parent.parent


def test_find_packages_discovers_pylogkit():
    """``find_packages`` must see ``pylogkit`` or built wheels ship no code."""
    assert "pylogkit" in find_packages(where=str(ROOT))


def test_public_api_is_exported():
    """Every name in ``__all__`` is importable from the package root."""
    import pylogkit

    assert pylogkit.__all__
    for name in pylogkit.__all__:
        assert hasattr(pylogkit, name), name
