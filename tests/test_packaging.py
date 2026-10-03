"""Tests that the project is packaged and importable as a real package."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_package_directory_is_a_regular_package():
    """Without ``__init__.py`` build tools discover no package and ship no code."""
    assert (ROOT / "pylogkit" / "__init__.py").is_file()


def test_public_api_is_exported():
    """Every name in ``__all__`` is importable from the package root."""
    import pylogkit

    assert pylogkit.__all__
    for name in pylogkit.__all__:
        assert hasattr(pylogkit, name), name
