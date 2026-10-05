"""Reusable logging setup with colourised, structured and rotating outputs.

:func:`setup_logging` configures console, file, JSON-lines and syslog output
for a logger. Context fields (user, session, request, host, environment and
process id) are attached to every record, globally through
:func:`set_log_context` and :func:`log_context`, or per logger through
:class:`ContextualLoggerAdapter`.

Dependencies:

- ``colorlog`` (required)
- ``python-json-logger`` (optional, needed for JSON output)
- ``tqdm`` (optional, used by :func:`tqdm_logging`)

Example::

    from ctxlogkit import ContextualLoggerAdapter, setup_logging

    logger = setup_logging(name=__name__, to_file=True, file_path="app.log", level="DEBUG")
    logger = ContextualLoggerAdapter(logger)
    logger.info("Hello, logging!")
    logger.with_context(user_id="bob").info("Info with dynamic context")
"""

from __future__ import annotations

import atexit
import copy
import logging
import os
import queue
import re
import socket
import sys
import time
import warnings
from collections.abc import Callable, Iterable, Iterator, Sized
from contextlib import contextmanager
from contextvars import ContextVar
from functools import cache, wraps
from logging.handlers import (
    QueueHandler,
    QueueListener,
    RotatingFileHandler,
    SysLogHandler,
    TimedRotatingFileHandler,
)
from typing import IO, TYPE_CHECKING, Any, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping
    from typing import TypeAlias

    # The helpers work with a plain logger and with a ContextualLoggerAdapter.
    LoggerLike: TypeAlias = "logging.Logger | logging.LoggerAdapter[logging.Logger]"

    _AdapterBase: TypeAlias = "logging.LoggerAdapter[logging.Logger]"
else:
    # ``LoggerAdapter`` is only subscriptable at runtime from Python 3.11.
    _AdapterBase = logging.LoggerAdapter

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")

# 🎨 Colour config
COLOUR_TIMESTAMP = "bold_purple"
COLOUR_CONTEXT_LABEL = "yellow"
COLOUR_MODULE_NAME = "cyan"
COLOUR_FILENAME = "green"
COLOUR_FUNCTION = "purple"
COLOUR_LINENO = "blue"

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
FILE_FORMAT = (
    "%(asctime)s [%(levelname)s] [%(name)s] "
    "[%(filename)s:%(lineno)d %(funcName)s()] %(context)s - %(message)s"
)
COMPACT_FORMAT = "[%(levelname)s] %(message)s"
JSON_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
JSON_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
_JSON_FIELD_NAMES = {"asctime": "timestamp", "levelname": "level", "name": "logger"}
_JSON_LEADING_FIELDS = ("timestamp", "level", "logger", "message")
# Presentation details of the text formats, and ``taskName`` (new in
# Python 3.12), which python-json-logger 2.x does not know to skip.
_JSON_INTERNAL_FIELDS = ("emoji", "context", "taskName")
SYSLOG_FORMAT = "%(name)s[%(process)d]: %(levelname)s %(context)s - %(message)s"

# One colour per level, used for the level name and for the message text.
_LEVEL_EMOJI = {
    "DEBUG": "🐛",
    "INFO": "ℹ️",
    "WARNING": "⚠️",
    "ERROR": "❌",
    "CRITICAL": "💥",
}

_LEVEL_COLOURS = {
    "DEBUG": "cyan",
    "INFO": "blue",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}

try:
    import colorlog
except ImportError as err:
    raise ImportError("Please install 'colorlog' using pip: pip install colorlog") from err

try:  # python-json-logger 3.1 and later
    from pythonjsonlogger.json import JsonFormatter
except ImportError:
    try:  # python-json-logger 2.x, where the class lives in ``jsonlogger``
        from pythonjsonlogger.jsonlogger import (  # type: ignore[attr-defined,unused-ignore]
            JsonFormatter,
        )
    except ImportError:
        JsonFormatter = None  # type: ignore[assignment,misc,unused-ignore]

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

_log_context: ContextVar[dict[str, Any] | None] = ContextVar("ctxlogkit_log_context", default=None)


def set_log_context(**kwargs: Any) -> None:
    """Replace the global log context of the current thread or task with ``kwargs``.

    The context is stored in a :class:`contextvars.ContextVar`, so each thread
    and each :mod:`asyncio` task sees its own value. A new thread starts with
    an empty context, and a task starts with a copy of its parent's.
    """
    _log_context.set(dict(kwargs))


def clear_log_context() -> None:
    """Remove all fields from the global log context of the current thread or task."""
    _log_context.set({})


@contextmanager
def log_context(**kwargs: Any) -> Iterator[None]:
    """Add ``kwargs`` to the log context for the duration of a ``with`` block.

    Fields are merged over the active context. On exit, including when the
    block raises, the previous context is restored exactly, so blocks nest and
    concurrent :mod:`asyncio` tasks do not affect each other::

        with log_context(request_id="abc"):
            logger.info("handled")  # carries request_id="abc"

    Args:
        **kwargs: Fields to add to, or override in, the active context.
    """
    token = _log_context.set({**(_log_context.get() or {}), **kwargs})
    try:
        yield
    finally:
        _log_context.reset(token)


@cache
def _hostname() -> str:
    """Return the host name, looked up once.

    ``socket.gethostname()`` can be slow on some systems and the value does
    not change while the process runs, so it must not be queried per record.
    """
    return socket.gethostname()


def get_log_context() -> dict[str, Any]:
    """Return a copy of the active context, with defaults filled in.

    Defaults are ``"-"`` for ``user_id``, ``session_id`` and ``request_id``,
    plus the cached host name, the ``APP_ENV`` environment variable (``"dev"``
    if unset) and the process id. ``APP_ENV`` and the process id are read on
    every call because they are cheap and may change (for example after a
    ``fork``).
    """
    context = dict(_log_context.get() or {})
    context.setdefault("user_id", "-")
    context.setdefault("session_id", "-")
    context.setdefault("request_id", "-")
    context.setdefault("hostname", _hostname())
    context.setdefault("env", os.getenv("APP_ENV", "dev"))
    context.setdefault("pid", os.getpid())
    return context


class SmartFieldFormatter(colorlog.ColoredFormatter):  # type: ignore[misc,unused-ignore]
    """Colour formatter that builds a compact ``%(context)s`` field.

    Only context values that are set (neither empty nor ``"-"``) are shown, as
    ``[key=value]``, so records without context do not carry placeholder text.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format ``record`` after adding the ``%(context)s`` field to it."""
        for key in ["user_id", "session_id", "request_id", "hostname", "env", "pid"]:
            if not hasattr(record, key):
                setattr(record, key, "")

        field_map = {
            key: getattr(record, key)
            for key in ("user_id", "session_id", "request_id", "hostname", "env", "pid")
        }

        dynamic_fields = []
        for k, v in field_map.items():
            if v and v != "-":
                dynamic_fields.append(f"[{k}={v}]")

        record.context = " ".join(dynamic_fields)
        try:
            return str(super().format(record))
        finally:
            # The record is shared with the other handlers. Leaving the text
            # layout's helper field behind would leak it into JSON output.
            delattr(record, "context")


def _build_console_formatter(stream: IO[str] | None = None) -> SmartFieldFormatter:
    """Return the coloured, verbose formatter used for console output.

    Colour is switched off automatically when ``stream`` is not a terminal,
    when the ``NO_COLOR`` environment variable is set, or when ``TERM`` is
    ``dumb``. Setting ``FORCE_COLOR`` turns it back on, for example for CI
    systems that render ANSI colours although their output is piped.

    Args:
        stream: The stream the formatted text is written to, used to detect
            whether it is a terminal. ``None`` skips that check.
    """
    return SmartFieldFormatter(
        fmt=f"%({COLOUR_TIMESTAMP})s%(asctime)s%(reset)s "
        "[%(log_color)s%(levelname)s%(emoji)s%(reset)s] "
        f"[%({COLOUR_MODULE_NAME})s%(name)s%(reset)s] "
        f"%({COLOUR_FILENAME})s%(filename)s%(reset)s::"
        f"%({COLOUR_FUNCTION})s%(funcName)s%(reset)s():"
        f"%({COLOUR_LINENO})s%(lineno)d%(reset)s "
        f"%({COLOUR_CONTEXT_LABEL})s%(context)s%(reset)s - "
        "%(log_color)s%(message)s%(reset)s",
        datefmt=DATE_FORMAT,
        log_colors=_LEVEL_COLOURS,
        secondary_log_colors={"message": _LEVEL_COLOURS},
        style="%",
        reset=True,
        stream=stream,
        no_color=os.environ.get("TERM") == "dumb",
    )


class ContextFilter(logging.Filter):
    """Copy the active log context and a level emoji onto every record.

    Values already present on the record (for example those supplied through
    ``extra=`` or by :class:`ContextualLoggerAdapter`) take precedence over
    the global context.

    Args:
        use_emoji: Set ``record.emoji`` to the level's emoji (preceded by a
            space, so that it lines up after the level name). When false the
            field is empty.
    """

    def __init__(self, use_emoji: bool = True) -> None:
        """Create the filter, optionally without level emoji."""
        super().__init__()
        self._use_emoji = use_emoji

    def filter(self, record: logging.LogRecord) -> bool:
        """Add the context fields and emoji to ``record`` and accept it."""
        context = get_log_context()
        for k, v in context.items():
            if not hasattr(record, k):
                setattr(record, k, v)
        record.emoji = (
            f" {_LEVEL_EMOJI[record.levelname]}"
            if self._use_emoji and record.levelname in _LEVEL_EMOJI
            else ""
        )
        return True


DEFAULT_REDACT_KEYS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
)
"""Field names worth masking in most applications, for ``redact_keys=``."""

_STANDARD_RECORD_ATTRIBUTES = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class RedactionFilter(logging.Filter):
    """Mask secrets in a record's extra fields and, optionally, in its message.

    Fields are the attributes added through ``extra=``, a
    :class:`ContextualLoggerAdapter` or the global context. A field is masked
    when its name contains any of ``keys``, compared case-insensitively, so
    ``"token"`` also masks ``access_token``. Dictionaries, lists and tuples
    inside a field are searched too, on a copy, so the caller's objects are
    never modified. Masking is idempotent, which makes it safe for a record to
    pass through the filter once per handler.

    Message text is only touched when ``patterns`` are given. Tracebacks are
    not searched.

    Args:
        keys: Field names to mask, for example :data:`DEFAULT_REDACT_KEYS`.
        patterns: Regular expressions, as strings or compiled patterns, whose
            matches are replaced by ``mask`` in the message.
        mask: Replacement text.
    """

    def __init__(
        self,
        keys: Iterable[str] = (),
        patterns: Iterable[str | re.Pattern[str]] = (),
        mask: str = "***",
    ) -> None:
        """Create the filter."""
        super().__init__()
        self._keys = tuple(key.lower() for key in keys)
        self._patterns = tuple(re.compile(p) if isinstance(p, str) else p for p in patterns)
        self._mask = mask

    def _is_secret(self, name: object) -> bool:
        """Return whether a field called ``name`` must be masked."""
        lowered = str(name).lower()
        return any(key in lowered for key in self._keys)

    def _clean(self, value: Any) -> Any:
        """Return ``value`` with secret entries of nested containers masked."""
        if isinstance(value, dict):
            return {
                k: self._mask if self._is_secret(k) else self._clean(v) for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return type(value)(self._clean(v) for v in value)
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask ``record`` in place and accept it."""
        if self._patterns:
            message = record.getMessage()
            redacted = message
            for pattern in self._patterns:
                redacted = pattern.sub(self._mask, redacted)
            if redacted != message:
                record.msg = redacted
                record.args = None
        for name, value in list(record.__dict__.items()):
            if name in _STANDARD_RECORD_ATTRIBUTES:
                continue
            record.__dict__[name] = self._mask if self._is_secret(name) else self._clean(value)
        return True


class ContextualLoggerAdapter(_AdapterBase):
    """Logger adapter that attaches context fields to every record.

    Fields come from three layers, lowest precedence first: the global
    context (:func:`set_log_context`), the adapter's own fields (added with
    :meth:`with_context`) and any ``extra=`` passed to the logging call.

    Args:
        logger: The logger to wrap.
        extra: Optional fields private to this adapter.
    """

    def __init__(self, logger: logging.Logger, extra: Mapping[str, Any] | None = None) -> None:
        """Wrap ``logger``, optionally with fields private to this adapter."""
        super().__init__(logger, dict(extra or {}))

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        """Merge the context layers into ``kwargs["extra"]``."""
        extra = get_log_context()
        extra.update(self.extra or {})
        extra.update(kwargs.get("extra") or {})
        kwargs["extra"] = extra
        return msg, kwargs

    def with_context(self, **context: Any) -> ContextualLoggerAdapter:
        """Return a new adapter with extra fields, leaving this one untouched.

        The global context is not modified, so the fields apply only to
        records logged through the returned adapter::

            log.with_context(user_id="bob").info("only this line is bob's")
            log.info("this line is not")

        Args:
            **context: Fields to add to, or override on, this adapter's fields.

        Returns:
            A new :class:`ContextualLoggerAdapter` on the same logger.
        """
        return ContextualLoggerAdapter(self.logger, {**(self.extra or {}), **context})


class _QueueHandler(QueueHandler):
    """Queue handler that hands records over without losing information.

    :class:`logging.handlers.QueueHandler` formats the record and drops
    ``exc_info``, which would move tracebacks into the message and out of the
    JSON ``exc_info`` field. This subclass only resolves the message
    arguments, so the listener's handlers format the record as usual.
    """

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        """Return a copy of ``record`` with ``msg`` and ``args`` already merged."""
        record = copy.copy(record)
        record.msg = record.getMessage()
        record.args = None
        return record


# Listeners that own the real handlers of loggers configured with ``use_queue``.
_listeners: dict[str, QueueListener] = {}
_atexit_registered = False


def _stop_listener(logger: logging.Logger) -> None:
    """Stop the listener of ``logger``, if any, after it has handled queued records."""
    listener = _listeners.pop(logger.name, None)
    if listener is not None:
        listener.stop()
        for handler in listener.handlers:
            handler.close()


def _reset_logger(logger: logging.Logger) -> None:
    """Remove and close the handlers ``logger`` has.

    Closing matters for file handlers: dropping them without closing leaks
    open file descriptors every time logging is reconfigured. A queue
    listener is stopped, and so flushed, after the logger stops feeding it.
    """
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    _stop_listener(logger)


def shutdown_logging() -> None:
    """Flush and stop the background logging of every ``use_queue`` logger.

    Records still waiting in a queue are written, then the listener threads
    stop and their handlers are closed. The affected loggers are left without
    handlers. It is safe to call more than once, and it runs automatically
    when the interpreter exits, so call it explicitly only when you need the
    output to be complete at a particular point, for example before
    ``os._exit()`` or before reading a log file.
    """
    for name in list(_listeners):
        _reset_logger(logging.getLogger(name))


if JsonFormatter is not None:

    class _PylogkitJsonFormatter(JsonFormatter):  # type: ignore[misc,unused-ignore]
        """JSON formatter with a stable field set and order.

        python-json-logger 2.x and later versions differ in the order of the
        fields and in which ones they skip, so both are normalised here.
        """

        def process_log_record(self, log_record: dict[str, Any]) -> dict[str, Any]:
            for key in _JSON_INTERNAL_FIELDS:
                log_record.pop(key, None)
            ordered = {k: log_record[k] for k in _JSON_LEADING_FIELDS if k in log_record}
            ordered.update(log_record)
            processed: dict[str, Any] = super().process_log_record(ordered)
            return processed


def _build_json_formatter() -> logging.Formatter:
    """Return the JSON formatter for JSON file and console output.

    Each record has ``timestamp`` (ISO 8601 with UTC offset), ``level``,
    ``logger`` and ``message``, followed by the context fields and, for
    exceptions, ``exc_info``.

    Raises:
        ImportError: If ``python-json-logger`` is not installed.
    """
    if JsonFormatter is None:
        raise ImportError("JSON output needs 'python-json-logger': pip install python-json-logger")
    return _PylogkitJsonFormatter(
        JSON_FORMAT,
        datefmt=JSON_DATE_FORMAT,
        rename_fields=_JSON_FIELD_NAMES,
        json_ensure_ascii=False,
    )


def _prepare_log_file(path: str, overwrite: bool) -> None:
    """Create the parent directory of ``path`` and optionally truncate the file."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if overwrite:
        open(path, "w", encoding="utf-8").close()


_LOG_FORMATS = ("pretty", "compact", "json", "auto")


def _resolve_environment(
    to_file: bool | None,
    file_path: str | None,
    level: str | None,
    mode: str | None,
    use_json: bool | None,
    console_stream: IO[str],
) -> tuple[bool, str | None, str, str, bool]:
    """Fill the arguments that were not given from the environment.

    An argument that was passed explicitly (anything but ``None``) always wins
    over ``LOG_LEVEL``, ``LOG_FORMAT`` and ``LOG_FILE``. ``LOG_FORMAT`` is
    ignored as soon as ``mode`` or ``use_json`` is given.

    Returns:
        ``(to_file, file_path, level, mode, use_json)`` with no ``None`` left,
        except ``file_path``, which stays ``None`` only if it was never set.

    Raises:
        ValueError: If ``LOG_FORMAT`` is not one of ``pretty``, ``compact``,
            ``json`` or ``auto``.
    """
    env_file = os.environ.get("LOG_FILE") or None
    if to_file is None:
        to_file = env_file is not None
    if file_path is None:
        file_path = env_file or "app.log"
    if level is None:
        level = os.environ.get("LOG_LEVEL") or "INFO"

    if mode is None and use_json is None:
        log_format = (os.environ.get("LOG_FORMAT") or "pretty").strip().lower()
        if log_format not in _LOG_FORMATS:
            raise ValueError(
                f"LOG_FORMAT must be one of {', '.join(_LOG_FORMATS)}, got {log_format!r}"
            )
        if log_format == "auto":
            log_format = "pretty" if _is_tty(console_stream) else "json"
        mode = "compact" if log_format == "compact" else "verbose"
        use_json = log_format == "json"
    return to_file, file_path, level, mode or "verbose", bool(use_json)


def _is_tty(stream: IO[str]) -> bool:
    """Return whether ``stream`` is an interactive terminal."""
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def setup_logging(
    name: str | None = None,
    overwrite: bool = False,
    to_console: bool = True,
    to_file: bool | None = None,
    file_path: str | None = None,
    to_json_file: bool = False,
    json_file_path: str | None = "app.json.log",
    to_syslog: bool = False,
    level: str | None = None,
    console_level: str | None = None,
    file_level: str | None = None,
    json_level: str | None = None,
    syslog_level: str | None = None,
    mode: str | None = None,
    use_json: bool | None = None,
    rotation: str = "size",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 2,
    context: dict[str, Any] | None = None,
    propagate: bool = False,
    syslog_address: tuple[str, int] | str = ("localhost", 514),
    syslog_facility: int = SysLogHandler.LOG_USER,
    console_stream: IO[str] | None = None,
    use_emoji: bool = True,
    use_queue: bool = False,
    redact_keys: Iterable[str] | None = None,
    redact_patterns: Iterable[str | re.Pattern[str]] | None = None,
) -> logging.Logger:
    """Configure and return a logger with console, file, JSON and syslog output.

    The function is idempotent: calling it again for the same logger replaces
    the handlers installed by the previous call (closing the old handlers)
    instead of adding to them.

    The :class:`ContextFilter` is attached to each handler rather than to the
    logger. Logger-level filters are skipped for records that propagate up
    from child loggers (``logging.getLogger("name.child")``), whereas handler
    filters see every record the handler emits.

    Arguments left as ``None`` fall back to the environment variables
    ``LOG_LEVEL``, ``LOG_FORMAT`` and ``LOG_FILE`` (see ``level``, ``mode``,
    ``use_json``, ``to_file`` and ``file_path``). An explicit argument always
    overrides the environment.

    Args:
        name: Logger name. ``None`` configures the root logger.
        overwrite: Truncate the plain-text and JSON log files when logging is
            set up instead of appending to them.
        to_console: Log to the console (see ``console_stream``).
        to_file: Log to ``file_path``. Defaults to true when the ``LOG_FILE``
            environment variable is set, otherwise false.
        file_path: Path of the plain-text log file. Defaults to ``LOG_FILE``,
            then to ``"app.log"``.
        to_json_file: Log JSON lines to ``json_file_path``.
        json_file_path: Path of the JSON log file.
        to_syslog: Log to syslog (see ``syslog_address``).
        level: Default level name for every handler. Defaults to ``LOG_LEVEL``,
            then to ``"INFO"``.
        console_level: Console level, defaulting to ``level``.
        file_level: File level, defaulting to ``level``.
        json_level: JSON file level, defaulting to ``level``.
        syslog_level: Syslog level, defaulting to ``level``.
        mode: ``"verbose"`` (coloured, with source location and context) or
            ``"compact"`` (``[LEVEL] message``) console layout. Ignored when
            ``use_json`` is true.
        use_json: Write JSON lines to the console instead of the text layout.
            When neither ``mode`` nor ``use_json`` is given, ``LOG_FORMAT``
            chooses the layout: ``pretty`` (the default), ``compact``,
            ``json``, or ``auto`` for pretty output on a terminal and JSON
            otherwise.
        rotation: ``"size"`` or ``"time"`` file rotation.
        max_bytes: Rotation size for size-based rotation.
        backup_count: Number of rotated files to keep.
        context: Initial global log context (see :func:`set_log_context`).
        propagate: Whether records also reach the handlers of parent loggers.
            Defaults to ``False`` because this function installs its own
            handlers, and propagating would duplicate every record when an
            ancestor (often the root logger) has handlers too.
        syslog_address: Syslog server as a ``(host, port)`` tuple (UDP) or the
            path of a Unix domain socket such as ``"/dev/log"``.
        syslog_facility: Syslog facility, for example
            ``logging.handlers.SysLogHandler.LOG_LOCAL0``.
        console_stream: Stream for console output, for example ``sys.stderr``.
            Defaults to ``sys.stdout`` as it is when this function is called.
            Console colour is disabled when the stream is not a terminal, when
            ``NO_COLOR`` is set or ``TERM`` is ``dumb``, unless ``FORCE_COLOR``
            is set.
        use_emoji: Show a level emoji after the level name in the verbose
            console layout. Set it to false for terminals and log viewers
            that render emoji badly.
        use_queue: Hand records to a background thread through a queue, so
            that slow handlers (files, syslog) do not block the code that logs.
            The queue is unbounded. Records are written when the thread gets
            to them, so call :func:`shutdown_logging` to wait for the queue to
            drain. That happens automatically at interpreter exit.
        redact_keys: Field names to mask in every handler's output, for
            example :data:`DEFAULT_REDACT_KEYS`. See :class:`RedactionFilter`.
        redact_patterns: Regular expressions whose matches are masked in the
            message text.

    Returns:
        The configured :class:`logging.Logger`.

    Raises:
        ImportError: If JSON output is requested but ``python-json-logger`` is
            not installed.
        ValueError: If ``LOG_FORMAT`` holds an unknown value.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # set to DEBUG globally; control per handler
    _reset_logger(logger)
    logger.propagate = propagate

    if context:
        set_log_context(**context)

    stream = console_stream if console_stream is not None else sys.stdout
    to_file, file_path, level, mode, use_json = _resolve_environment(
        to_file, file_path, level, mode, use_json, stream
    )
    if use_json:
        formatter = _build_json_formatter()
    elif mode == "compact":
        formatter = logging.Formatter(COMPACT_FORMAT, datefmt=DATE_FORMAT)
    else:
        formatter = _build_console_formatter(stream)

    handlers: list[logging.Handler] = []

    if to_console:
        console_handler = logging.StreamHandler(stream)
        console_handler.setLevel((console_level or level).upper())
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    if to_file and file_path:
        _prepare_log_file(file_path, overwrite)
        file_handler: RotatingFileHandler | TimedRotatingFileHandler
        if rotation == "time":
            file_handler = TimedRotatingFileHandler(
                file_path, when="midnight", backupCount=backup_count, encoding="utf-8"
            )
        else:
            file_handler = RotatingFileHandler(
                file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
        file_handler.setLevel((file_level or level).upper())
        file_formatter = SmartFieldFormatter(FILE_FORMAT, datefmt=DATE_FORMAT, no_color=True)
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    if to_json_file and json_file_path:
        json_formatter = _build_json_formatter()
        _prepare_log_file(json_file_path, overwrite)
        json_handler = RotatingFileHandler(
            json_file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        json_handler.setLevel((json_level or level).upper())
        json_handler.setFormatter(json_formatter)
        handlers.append(json_handler)

    if to_syslog:
        syslog_handler = SysLogHandler(address=syslog_address, facility=syslog_facility)
        syslog_handler.setLevel((syslog_level or level).upper())
        syslog_formatter = SmartFieldFormatter(SYSLOG_FORMAT, no_color=True)
        syslog_handler.setFormatter(syslog_formatter)
        handlers.append(syslog_handler)

    filters: list[logging.Filter] = [ContextFilter(use_emoji=use_emoji)]
    if redact_keys or redact_patterns:
        filters.append(RedactionFilter(redact_keys or (), redact_patterns or ()))
    if use_queue:
        _start_queue(logger, handlers, filters)
    else:
        for handler in handlers:
            for log_filter in filters:
                handler.addFilter(log_filter)
            logger.addHandler(handler)

    return logger


def _start_queue(
    logger: logging.Logger, handlers: list[logging.Handler], filters: list[logging.Filter]
) -> None:
    """Route ``logger`` through a queue drained by a listener thread owning ``handlers``.

    The filters run on the queue handler, that is in the thread that logs.
    The listener thread has no access to that thread's context, and secrets
    are masked before a record is queued.
    """
    global _atexit_registered
    log_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
    queue_handler = _QueueHandler(log_queue)
    for log_filter in filters:
        queue_handler.addFilter(log_filter)
    listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    listener.start()
    _listeners[logger.name] = listener
    logger.addHandler(queue_handler)
    if not _atexit_registered:
        atexit.register(shutdown_logging)
        _atexit_registered = True


def log_exception(logger: LoggerLike, msg: str) -> None:
    """Log ``msg`` at ERROR level with the current exception's traceback.

    Call it from inside an ``except`` block. It is a thin wrapper around
    :meth:`logging.Logger.exception`.
    """
    logger.exception(msg)


def setup_syslog_logger(
    name: str = "myapp", level: str = "INFO", address: tuple[str, int] = ("localhost", 514)
) -> logging.Logger:
    """Return a logger that only writes to syslog at ``address``.

    .. deprecated::
        Use ``setup_logging(name, to_console=False, to_syslog=True,
        syslog_address=address)`` instead. This function is a thin wrapper
        around it and will be removed in a future release.

    Args:
        name: Logger name.
        level: Level name for the logger.
        address: ``(host, port)`` of the syslog server.
    """
    warnings.warn(
        "setup_syslog_logger() is deprecated, use "
        "setup_logging(to_console=False, to_syslog=True, syslog_address=...)",
        DeprecationWarning,
        stacklevel=2,
    )
    return setup_logging(
        name=name, to_console=False, to_syslog=True, level=level, syslog_address=address
    )


def log_duration(
    logger: LoggerLike, level: str = "info"
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Return a decorator that logs how long the decorated function takes.

    The duration is measured with :func:`time.perf_counter`, a monotonic clock,
    and is logged even when the function raises (the exception is re-raised
    unchanged).

    Args:
        logger: Logger, or adapter, used for the message.
        level: Level name for the message, for example ``"debug"``. It is
            checked when the decorator is created, not on the first call.

    Returns:
        A decorator for functions.

    Raises:
        ValueError: If ``level`` is not a known logging level name.
    """
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"Unknown logging level: {level!r}")

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            outcome = "took"
            try:
                return func(*args, **kwargs)
            except BaseException:
                outcome = "failed after"
                raise
            finally:
                duration = time.perf_counter() - start
                logger.log(numeric_level, "%s %s %.4f seconds", func.__name__, outcome, duration)

        return wrapper

    return decorator


def tqdm_logging(iterable: Iterable[T], logger: LoggerLike, level: str = "info") -> Iterator[T]:
    """Yield the items of ``iterable`` while reporting progress.

    When tqdm is installed a progress bar is shown. Otherwise one
    ``Progress: n/total`` message is logged per item (``Progress: n`` if the
    iterable has no length, for example a generator).

    Args:
        iterable: Any iterable to loop over.
        logger: Logger used for the fallback progress messages.
        level: Name of the logger method used for those messages.

    Yields:
        The items of ``iterable``, unchanged and in order.
    """
    if tqdm:
        yield from tqdm(iterable)
        return

    log = getattr(logger, level)
    total = len(iterable) if isinstance(iterable, Sized) else None
    for index, item in enumerate(iterable, 1):
        if total is None:
            log("Progress: %d", index)
        else:
            log("Progress: %d/%d", index, total)
        yield item


# Example usage
if __name__ == "__main__":
    base_logger = setup_logging(
        name=__name__,
        to_console=True,
        to_file=True,
        file_path="logs/example.log",
        to_json_file=True,
        json_file_path="logs/example.json",
        overwrite=True,
        level="DEBUG",
        mode="verbose",
        rotation="time",
        context={"user_id": "test_user"},
    )
    log = ContextualLoggerAdapter(base_logger)

    # Global context set for all following log entries
    set_log_context(user_id="test_user", session_id="abc123", request_id="req-001")

    log.debug("Debugging the log setup.")
    log.info("Info message.")

    # Per-message context override
    log.with_context(user_id="bob", session_id="xyz456").debug("This is Bob's debug")
    log.with_context(user_id="alice", session_id="xyz789").info("This is Alice's info")

    log.warning("Warning issued.")

    try:
        _ = 1 / 0
    except ZeroDivisionError:
        log_exception(log, "Division by zero error")

    @log_duration(log)
    def simulate_work() -> None:
        """Sleep for a second, so there is a duration to log."""
        time.sleep(1)

    simulate_work()

    for _ in tqdm_logging(range(5), logger=log):
        time.sleep(0.2)

    log.critical("Critical failure.")
