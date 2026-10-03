'''
log_setup.py
-------------
Reusable Python logging setup with colourised output and configurable logging to file and/or console.

Dependencies:
- colorlog (install via `pip install colorlog`)
- python-json-logger (optional, install via `pip install python-json-logger`)
- tqdm (optional, install via `pip install tqdm`)

Usage:
from pylogkit import ContextualLoggerAdapter, setup_logging
logger = setup_logging(name=__name__, to_console=True, to_file=True, file_path="app.log", level="DEBUG", mode="verbose")
logger = ContextualLoggerAdapter(logger)
logger.info("Hello, logging!")
logger.with_context(user_id="bob").info("Info with dynamic context")
'''

import logging
import os
import sys
import json
import time
import threading
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler, SysLogHandler
from typing import Optional
from functools import wraps

# 🎨 Colour config
COLOUR_TIMESTAMP = "bold_purple"
COLOUR_CONTEXT_LABEL = "yellow"
COLOUR_MODULE_NAME = "cyan"
COLOUR_FILENAME = "green"
COLOUR_FUNCTION = "purple"
COLOUR_LINENO = "blue"

try:
    import colorlog
except ImportError:
    raise ImportError("Please install 'colorlog' using pip: pip install colorlog")

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

_log_context = threading.local()

def set_log_context(**kwargs):
    _log_context.data = kwargs

def clear_log_context():
    _log_context.data = {}

def get_log_context():
    import socket
    context = getattr(_log_context, 'data', {}).copy()
    context.setdefault("user_id", "-")
    context.setdefault("session_id", "-")
    context.setdefault("request_id", "-")
    context.setdefault("hostname", socket.gethostname())
    context.setdefault("env", os.getenv("APP_ENV", "dev"))
    context.setdefault("pid", os.getpid())
    return context

class CompactContextFormatter(colorlog.ColoredFormatter):
    def format(self, record):
        # Remove any context field that is empty, "-", or None
        for attr in list(vars(record)):
            if isinstance(getattr(record, attr), str) and getattr(record, attr).strip() in {"", "-"}:
                setattr(record, attr, "")

        return super().format(record)

class SmartFieldFormatter(colorlog.ColoredFormatter):
    def format(self, record):
        for key in ["user_id", "session_id", "request_id", "hostname", "env", "pid"]:
            if not hasattr(record, key):
                setattr(record, key, "")

        field_map = {
            "user_id": record.user_id,
            "session_id": record.session_id,
            "request_id": record.request_id,
            "hostname": record.hostname,
            "env": record.env,
            "pid": record.pid
        }

        dynamic_fields = []
        for k, v in field_map.items():
            if v and v != "-":
                dynamic_fields.append(f"[{k}={v}]")

        record.context = " ".join(dynamic_fields)
        return super().format(record)

class ContextFilter(logging.Filter):
    def filter(self, record):
        context = get_log_context()
        for k, v in context.items():
            setattr(record, k, v)
        emoji_map = {
            'DEBUG': '🐛',
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '💥',
            'SYSTEM': '🖥️',
            'SECURITY': '🔐',
            'NETWORK': '🌐',
            'DATABASE': '🗄️',
            'STARTUP': '🚀',
            'SHUTDOWN': '🛑'
        }
        setattr(record, 'emoji', emoji_map.get(record.levelname, ''))
        return True

class ContextualLoggerAdapter(logging.LoggerAdapter):
    def __init__(self, logger):
        super().__init__(logger, {})

    def process(self, msg, kwargs):
        context = get_log_context()
        kwargs.setdefault("extra", {}).update(context)
        return msg, kwargs

    def with_context(self, **context):
        prev_context = get_log_context().copy()
        combined_context = prev_context.copy()
        combined_context.update(context)
        set_log_context(**combined_context)
        return self

def setup_logging(name: Optional[str] = None,
                  overwrite: bool = False,
                  to_console: bool = True,
                  to_file: bool = False,
                  file_path: Optional[str] = "app.log",
                  to_json_file: bool = False,
                  json_file_path: Optional[str] = "app.json.log",
                  to_syslog: bool = False,
                  level: str = "INFO",
                  console_level: Optional[str] = None,
                  file_level: Optional[str] = None,
                  json_level: Optional[str] = None,
                  syslog_level: Optional[str] = None,
                  mode: str = "verbose",
                  use_json: bool = False,
                  rotation: str = "size",
                  max_bytes: int = 5*1024*1024,
                  backup_count: int = 2,
                  context: Optional[dict] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # set to DEBUG globally; control per handler
    logger.handlers.clear()

    logger.addFilter(ContextFilter())
    if context:
        set_log_context(**context)

    log_format_verbose = (
        "%(asctime)s [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d %(funcName)s()] %(context)s - %(message)s"
    )

    log_format_compact = ("[%(levelname)s] %(message)s")

    if jsonlogger:
        json_formatter = jsonlogger.JsonFormatter(json_ensure_ascii=False)
        formatter = SmartFieldFormatter(
            fmt=f"%({COLOUR_TIMESTAMP})s%(asctime)s%(reset)s "
                "[%(log_color)s%(levelname)s %(emoji)s%(reset)s] "
                f"[%({COLOUR_MODULE_NAME})s%(name)s%(reset)s] "
                f"%({COLOUR_FILENAME})s%(filename)s%(reset)s::"
                f"%({COLOUR_FUNCTION})s%(funcName)s%(reset)s():"
                f"%({COLOUR_LINENO})s%(lineno)d%(reset)s "
                f"%({COLOUR_CONTEXT_LABEL})s%(context)s%(reset)s - "
                "%(log_color)s%(message)s%(reset)s",

            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'blue',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'bold_red'
            },
            secondary_log_colors={
                'message': {
                    'DEBUG':    'cyan',
                    'INFO':     'blue',
                    'WARNING':  'yellow',
                    'ERROR':    'red',
                    'CRITICAL': 'bold_red'
                }
            },
            style='%',
            reset=True
        )


    elif mode == "compact":
        formatter = logging.Formatter(log_format_compact, datefmt="%Y-%m-%d %H:%M:%S")
    else:
        formatter = SmartFieldFormatter(
            fmt=f"%({COLOUR_TIMESTAMP})s%(asctime)s%(reset)s "
                "[%(log_color)s%(levelname)s %(emoji)s%(reset)s] "
                f"[%({COLOUR_MODULE_NAME})s%(name)s%(reset)s] "
                f"%({COLOUR_FILENAME})s%(filename)s%(reset)s::"
                f"%({COLOUR_FUNCTION})s%(funcName)s%(reset)s():"
                f"%({COLOUR_LINENO})s%(lineno)d%(reset)s "
                f"%({COLOUR_CONTEXT_LABEL})s%(context)s%(reset)s - "
                "%(log_color)s%(message)s%(reset)s",

            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'blue',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'bold_red'
            },
            secondary_log_colors={
                'message': {
                    'DEBUG':    'cyan',
                    'INFO':     'blue',
                    'WARNING':  'yellow',
                    'ERROR':    'red',
                    'CRITICAL': 'bold_red'
                }
            },
            style='%',
            reset=True
        )

    if to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel((console_level or level).upper())
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if to_file and file_path:
        os.makedirs(os.path.dirname(file_path), exist_ok=True) if os.path.dirname(file_path) else None
        if rotation == "time":
            mode = 'w' if overwrite else 'a'
            file_handler = TimedRotatingFileHandler(file_path, when="midnight", backupCount=backup_count, encoding='utf-8')
        else:
            mode = 'w' if overwrite else 'a'
            file_handler = RotatingFileHandler(file_path, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
        file_handler.setLevel((file_level or level).upper())
        file_formatter = SmartFieldFormatter(log_format_verbose, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    if to_json_file and json_file_path and jsonlogger:
        if os.path.dirname(json_file_path):
            os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
        mode = 'w' if overwrite else 'a'
        json_handler = RotatingFileHandler(json_file_path, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
        json_handler.setLevel((json_level or level).upper())
        json_handler.setFormatter(json_formatter)
        logger.addHandler(json_handler)



    if to_syslog:
        syslog_handler = SysLogHandler(address=("localhost", 514))
        syslog_handler.setLevel((syslog_level or level).upper())
        syslog_formatter = logging.Formatter("%(name)s[%(process)d]: %(levelname)s %(message)s")
        syslog_handler.setFormatter(syslog_formatter)
        logger.addHandler(syslog_handler)

    return logger

def log_exception(logger: logging.Logger, msg: str):
    logger.exception(msg)

def setup_syslog_logger(name: str = "myapp",
                        level: str = "INFO",
                        address: tuple = ("localhost", 514)) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level.upper())
    handler = SysLogHandler(address=address)
    formatter = logging.Formatter("%(name)s[%(process)d]: %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def log_duration(logger: logging.Logger, level: str = "info"):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            getattr(logger, level)(f"{func.__name__} took {duration:.4f} seconds")
            return result
        return wrapper
    return decorator

def tqdm_logging(iterable, logger: logging.Logger, level: str = "info"):
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
    total = len(iterable) if hasattr(iterable, "__len__") else None
    for index, item in enumerate(iterable, 1):
        if total is None:
            log("Progress: %d", index)
        else:
            log("Progress: %d/%d", index, total)
        yield item

# Example usage
if __name__ == "__main__":
    log = setup_logging(
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
        context={"user_id": "test_user"}
    )
    log = ContextualLoggerAdapter(log)

    # Global context set for all following log entries
    set_log_context(user_id="test_user", session_id="abc123", request_id="req-001")

    log.debug("Debugging the log setup.")
    log.info("Info message.")

    # Per-message context override
    log.with_context(user_id="bob", session_id="xyz456").debug("This is Bob's debug")
    log.with_context(user_id="alice", session_id="xyz789").info("This is Alice's info")

    log.warning("Warning issued.")

    try:
        1 / 0
    except ZeroDivisionError:
        log_exception(log, "Division by zero error")

    @log_duration(log)
    def simulate_work():
        time.sleep(1)

    simulate_work()

    for _ in tqdm_logging(range(5), logger=log):
        time.sleep(0.2)

    log.critical("Critical failure.")
