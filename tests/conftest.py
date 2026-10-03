"""Shared pytest fixtures."""

from importlib.util import find_spec

import pytest

from pylogkit import clear_log_context

_HAS_JSON_LOGGER = find_spec("pythonjsonlogger") is not None
_HAS_TQDM = find_spec("tqdm") is not None


def pytest_collection_modifyitems(items):
    """Skip tests that need optional extras which are not installed."""
    unavailable = {
        "json_logger": not _HAS_JSON_LOGGER,
        "extras": not (_HAS_JSON_LOGGER and _HAS_TQDM),
    }
    for item in items:
        for marker, missing in unavailable.items():
            if missing and marker in item.keywords:
                item.add_marker(pytest.mark.skip(reason=f"{marker}: optional packages missing"))


@pytest.fixture(autouse=True)
def _isolated_log_context():
    """Start and finish every test with an empty global log context."""
    clear_log_context()
    yield
    clear_log_context()
