"""ctxlogkit: a structured and colourised logging toolkit for Python applications.

The public API lives in :mod:`ctxlogkit.log_setup` and is re-exported here, so
applications can write::

    from ctxlogkit import setup_logging, ContextualLoggerAdapter

    logger = ContextualLoggerAdapter(setup_logging(name=__name__, level="DEBUG"))
    logger.info("Hello, logging!")
"""

from ctxlogkit._version import __version__
from ctxlogkit.log_setup import (
    DEFAULT_REDACT_KEYS,
    ContextualLoggerAdapter,
    RedactionFilter,
    clear_log_context,
    get_log_context,
    log_context,
    log_duration,
    log_exception,
    set_log_context,
    setup_logging,
    setup_syslog_logger,
    shutdown_logging,
    tqdm_logging,
)

__all__ = [
    "DEFAULT_REDACT_KEYS",
    "ContextualLoggerAdapter",
    "RedactionFilter",
    "__version__",
    "clear_log_context",
    "get_log_context",
    "log_context",
    "log_duration",
    "log_exception",
    "set_log_context",
    "setup_logging",
    "setup_syslog_logger",
    "shutdown_logging",
    "tqdm_logging",
]
