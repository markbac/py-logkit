"""Tests for :func:`pylogkit.log_setup.get_log_context`."""

import socket

from pylogkit import get_log_context, set_log_context
from pylogkit.log_setup import _hostname


def test_hostname_is_looked_up_once(monkeypatch):
    """``socket.gethostname`` was called for every log record."""
    calls = []

    def fake_gethostname():
        calls.append(1)
        return "test-host"

    _hostname.cache_clear()
    monkeypatch.setattr(socket, "gethostname", fake_gethostname)
    try:
        for _ in range(5):
            assert get_log_context()["hostname"] == "test-host"
        assert len(calls) == 1
    finally:
        _hostname.cache_clear()


def test_defaults_are_filled_in():
    """Unset identity fields default to ``"-"`` and host fields are present."""
    context = get_log_context()

    assert context["user_id"] == context["session_id"] == context["request_id"] == "-"
    assert context["hostname"]
    assert isinstance(context["pid"], int)


def test_app_env_is_read_on_every_call(monkeypatch):
    """``APP_ENV`` is not cached, so changes take effect immediately."""
    monkeypatch.setenv("APP_ENV", "staging")
    assert get_log_context()["env"] == "staging"

    monkeypatch.setenv("APP_ENV", "prod")
    assert get_log_context()["env"] == "prod"


def test_explicit_context_overrides_defaults():
    """Values set with ``set_log_context`` win over the defaults."""
    set_log_context(user_id="alice", hostname="custom")

    context = get_log_context()

    assert context["user_id"] == "alice"
    assert context["hostname"] == "custom"


def test_context_is_isolated_between_threads():
    """A thread must not see, or change, another thread's context."""
    import threading

    set_log_context(user_id="main")
    seen = {}

    def worker():
        seen["before"] = get_log_context()["user_id"]
        set_log_context(user_id="worker")
        seen["after"] = get_log_context()["user_id"]

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert seen == {"before": "-", "after": "worker"}
    assert get_log_context()["user_id"] == "main"


def test_context_argument_of_setup_logging_sets_the_global_context():
    """``setup_logging(context=...)`` seeds the context for later records."""
    from pylogkit import setup_logging

    setup_logging("ctx-arg", to_console=False, context={"user_id": "seeded"})

    assert get_log_context()["user_id"] == "seeded"


def test_log_context_adds_fields_and_restores_them():
    """Fields apply inside the block and the previous context returns afterwards."""
    from pylogkit import log_context

    set_log_context(user_id="alice")

    with log_context(request_id="abc", user_id="bob"):
        inside = get_log_context()

    after = get_log_context()
    assert inside["request_id"] == "abc"
    assert inside["user_id"] == "bob"
    assert after["request_id"] == "-"
    assert after["user_id"] == "alice"


def test_log_context_restores_on_exception():
    """The previous context is restored when the block raises."""
    import pytest

    from pylogkit import log_context

    set_log_context(user_id="alice")

    with pytest.raises(RuntimeError), log_context(user_id="bob"):
        raise RuntimeError("boom")

    assert get_log_context()["user_id"] == "alice"


def test_log_context_nests():
    """Inner blocks add to the outer one and leave it intact on exit."""
    from pylogkit import log_context

    with log_context(request_id="outer"):
        with log_context(user_id="bob"):
            assert get_log_context()["request_id"] == "outer"
            assert get_log_context()["user_id"] == "bob"
        assert get_log_context()["user_id"] == "-"
        assert get_log_context()["request_id"] == "outer"


def test_log_context_reaches_log_records(capsys):
    """Records logged inside the block carry its fields."""
    import logging

    from pylogkit import log_context, setup_logging

    setup_logging("ctx-manager")

    with log_context(request_id="req-7"):
        logging.getLogger("ctx-manager").info("inside")
    logging.getLogger("ctx-manager").info("outside")

    inside, outside = capsys.readouterr().out.strip().splitlines()
    assert "[request_id=req-7]" in inside
    assert "request_id" not in outside


def test_context_is_isolated_between_asyncio_tasks():
    """Concurrent tasks must each keep their own context (``threading.local`` could not)."""
    import asyncio

    from pylogkit import log_context

    async def handle(name: str) -> str:
        with log_context(request_id=name):
            await asyncio.sleep(0.01)
            return str(get_log_context()["request_id"])

    async def main() -> list[str]:
        return await asyncio.gather(*(handle(f"req-{i}") for i in range(5)))

    assert asyncio.run(main()) == [f"req-{i}" for i in range(5)]
    assert get_log_context()["request_id"] == "-"


def test_set_log_context_copies_its_arguments():
    """Later changes to the returned context must not leak into the stored one."""
    set_log_context(user_id="alice")

    get_log_context()["user_id"] = "mallory"

    assert get_log_context()["user_id"] == "alice"
