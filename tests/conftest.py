"""Shared pytest fixtures."""

import pytest

from pylogkit import clear_log_context


@pytest.fixture(autouse=True)
def _isolated_log_context():
    """Start and finish every test with an empty global log context."""
    clear_log_context()
    yield
    clear_log_context()
