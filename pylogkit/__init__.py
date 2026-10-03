"""pylogkit: a structured and colourised logging toolkit for Python applications.

The public API lives in :mod:`pylogkit.log_setup` and is re-exported here, so
applications can write::

    from pylogkit import setup_logging, ContextualLoggerAdapter

    logger = ContextualLoggerAdapter(setup_logging(name=__name__, level="DEBUG"))
    logger.info("Hello, logging!")
"""

from pylogkit._version import __version__
from pylogkit.log_setup import (
    ContextualLoggerAdapter,
    clear_log_context,
    get_log_context,
    log_context,
    log_duration,
    log_exception,
    set_log_context,
    setup_logging,
    setup_syslog_logger,
    tqdm_logging,
)

__all__ = [
    "__version__",
    "ContextualLoggerAdapter",
    "clear_log_context",
    "get_log_context",
    "log_context",
    "log_duration",
    "log_exception",
    "set_log_context",
    "setup_logging",
    "setup_syslog_logger",
    "tqdm_logging",
]
