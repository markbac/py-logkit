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


def test_py_typed_marker_is_present():
    """PEP 561: the marker tells type checkers that the package ships inline types."""
    assert (ROOT / "pylogkit" / "py.typed").is_file()


def test_package_data_includes_py_typed():
    """The marker must be listed as package data or the wheel omits it."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'pylogkit = ["py.typed"]' in text


def test_public_api_is_annotated():
    """Every public function and method has annotations for all parameters and the return."""
    import inspect

    import pylogkit

    missing = []
    for name in pylogkit.__all__:
        obj = getattr(pylogkit, name)
        members = [obj]
        if inspect.isclass(obj):
            members = [
                m
                for n, m in vars(obj).items()
                if inspect.isfunction(m) and (not n.startswith("_") or n == "__init__")
            ]
        for func in members:
            hints = inspect.signature(func).parameters
            annotated = all(
                p.annotation is not p.empty for n, p in hints.items() if n not in ("self", "cls")
            )
            if not annotated or "return" not in getattr(func, "__annotations__", {}):
                missing.append(f"{name}:{getattr(func, '__qualname__', func)}")

    assert not missing, missing
