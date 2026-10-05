"""Tests that the project is packaged and importable as a real package."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_package_directory_is_a_regular_package():
    """Without ``__init__.py`` build tools discover no package and ship no code."""
    assert (ROOT / "ctxlogkit" / "__init__.py").is_file()


def test_public_api_is_exported():
    """Every name in ``__all__`` is importable from the package root."""
    import ctxlogkit

    assert ctxlogkit.__all__
    for name in ctxlogkit.__all__:
        assert hasattr(ctxlogkit, name), name


def test_py_typed_marker_is_present():
    """PEP 561: the marker tells type checkers that the package ships inline types."""
    assert (ROOT / "ctxlogkit" / "py.typed").is_file()


def test_package_data_includes_py_typed():
    """The marker must be listed as package data or the wheel omits it."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'ctxlogkit = ["py.typed"]' in text


def test_public_api_is_annotated():
    """Every public function and method has annotations for all parameters and the return."""
    import inspect

    import ctxlogkit

    missing = []
    for name in ctxlogkit.__all__:
        obj = getattr(ctxlogkit, name)
        if not callable(obj):
            continue
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


def test_version_is_single_sourced():
    """``pyproject.toml`` reads the version from ``_version.py`` instead of repeating it."""
    import re

    import ctxlogkit
    from ctxlogkit import _version

    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'dynamic = ["version"]' in text
    assert "ctxlogkit._version.__version__" in text
    assert not re.search(r'^version = "', text, re.M)
    assert ctxlogkit.__version__ == _version.__version__
    assert re.fullmatch(r"\d+\.\d+\.\d+", _version.__version__)


def test_release_workflow_checks_tag_against_version():
    """The release workflow exists and refuses a tag that disagrees with the version."""
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert 'tags: ["v*"]' in workflow
    assert "_version.py" in workflow
