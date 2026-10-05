"""Tests for :class:`ctxlogkit.log_setup.ContextualLoggerAdapter`."""

from ctxlogkit import (
    ContextualLoggerAdapter,
    get_log_context,
    set_log_context,
    setup_logging,
)


def _adapter(name):
    return ContextualLoggerAdapter(setup_logging(name=name, level="DEBUG"))


def test_with_context_does_not_mutate_global_context():
    """The reported bug: ``with_context`` replaced the global context."""
    log = _adapter("adapter-global")
    set_log_context(user_id="orig")

    log.with_context(user_id="bob")

    assert get_log_context()["user_id"] == "orig"


def test_with_context_applies_only_to_the_returned_adapter(capsys):
    """Later lines logged without ``with_context`` must not carry the override."""
    log = _adapter("adapter-scope")
    set_log_context(user_id="orig")

    log.with_context(user_id="bob").info("first")
    log.info("second")

    first, second = capsys.readouterr().out.splitlines()
    assert "[user_id=bob]" in first
    assert "[user_id=orig]" in second


def test_with_context_chains_and_later_values_win(capsys):
    """Chained calls accumulate fields and the last value for a key wins."""
    log = _adapter("adapter-chain")

    log.with_context(user_id="a", request_id="r1").with_context(user_id="b").info("x")

    out = capsys.readouterr().out
    assert "[user_id=b]" in out
    assert "[request_id=r1]" in out


def test_explicit_extra_beats_adapter_and_global_context(capsys):
    """``extra=`` passed to the call has the highest precedence."""
    log = _adapter("adapter-extra")
    set_log_context(user_id="global")

    log.with_context(user_id="adapter").info("x", extra={"user_id": "call"})

    assert "[user_id=call]" in capsys.readouterr().out


def test_global_context_is_used_without_with_context(capsys):
    """Without overrides the adapter reports the global context."""
    log = _adapter("adapter-plain")
    set_log_context(session_id="s-1")

    log.info("x")

    assert "[session_id=s-1]" in capsys.readouterr().out
