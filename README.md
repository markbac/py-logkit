# pylogkit

[![CI](https://github.com/markbac/py-logkit/actions/workflows/ci.yml/badge.svg)](https://github.com/markbac/py-logkit/actions/workflows/ci.yml)

A small logging toolkit for Python applications. One call to `setup_logging()` gives you
colourised console output, rotating plain-text and JSON-lines files, and syslog, all
carrying the same request context (user, session, request, host, environment and process id).

It builds on the standard `logging` module and [`colorlog`](https://pypi.org/project/colorlog/),
so everything it returns is an ordinary `logging.Logger`.

## Why pylogkit

- **One call, sensible defaults.** Console, file, JSON and syslog handlers with their own
  levels, formats and rotation, configured by keyword arguments.
- **Context on every line.** Set a user, session or request id once and every record carries it,
  in text and in JSON, including records from child loggers such as `myapp.db`.
- **Safe to call again.** Reconfiguring a logger replaces its handlers (and closes the old ones)
  instead of duplicating output.
- **Behaves in pipelines.** Colour switches off for pipes, `NO_COLOR` and dumb terminals, and
  plain-text files never contain escape codes.

## Installation

Requires Python 3.10 or later. The only mandatory dependency is `colorlog`.

> **Warning:** The name `pylogkit` on PyPI belongs to a different, unrelated project, so
> `pip install pylogkit` does **not** install this library. Install it from this repository
> instead (see the naming discussion in [#44](https://github.com/markbac/py-logkit/issues/44)).

```bash
pip install "pylogkit[all] @ git+https://github.com/markbac/py-logkit"
```

or from a clone:

```bash
pip install .              # console and file logging
pip install ".[json]"      # adds JSON output (python-json-logger)
pip install ".[progress]"  # adds tqdm progress bars to tqdm_logging()
pip install ".[all]"       # everything optional
```

## Quick start

```python
from pylogkit import ContextualLoggerAdapter, set_log_context, setup_logging

logger = setup_logging(
    name="shop.checkout",
    level="DEBUG",
    to_file=True,
    file_path="logs/app.log",
    to_json_file=True,
    json_file_path="logs/app.json.log",
)
log = ContextualLoggerAdapter(logger)

set_log_context(user_id="alice", request_id="req-42")
log.info("Order accepted")
log.with_context(user_id="bob").warning("Payment retry")
```

The console shows (colours omitted here):

```text
2026-10-03 11:42:25 [INFO ℹ️] [shop.checkout] checkout.py::<module>():9 [user_id=alice] [request_id=req-42] [hostname=vm] [env=dev] [pid=2705] - Order accepted
2026-10-03 11:42:25 [WARNING ⚠️] [shop.checkout] checkout.py::<module>():10 [user_id=bob] [request_id=req-42] [hostname=vm] [env=dev] [pid=2705] - Payment retry
```

and `logs/app.json.log` receives one JSON object per line:

```json
{"timestamp": "2026-10-03T11:42:25+0100", "level": "INFO", "logger": "shop.checkout", "message": "Order accepted", "user_id": "alice", "request_id": "req-42", "session_id": "-", "hostname": "vm", "env": "dev", "pid": 2705}
{"timestamp": "2026-10-03T11:42:25+0100", "level": "WARNING", "logger": "shop.checkout", "message": "Payment retry", "user_id": "bob", "request_id": "req-42", "session_id": "-", "hostname": "vm", "env": "dev", "pid": 2705}
```

## Context fields

Every record carries these fields. Values that are not set are shown as `-` in JSON and are
left out of the text layouts.

| Field        | Default                              |
| ------------ | ------------------------------------ |
| `user_id`    | `-`                                  |
| `session_id` | `-`                                  |
| `request_id` | `-`                                  |
| `hostname`   | the machine's host name (looked up once) |
| `env`        | the `APP_ENV` environment variable, or `dev` |
| `pid`        | the process id                       |

Context is applied in three layers. Later layers win:

1. The global context of the current thread: `set_log_context(**fields)`,
   `clear_log_context()` and `get_log_context()`.
2. The fields of a `ContextualLoggerAdapter`, added with `log.with_context(**fields)`.
   This returns a new adapter and never changes the global context.
3. `extra={...}` passed to an individual logging call.

```python
set_log_context(user_id="alice")
log.with_context(user_id="bob").info("this line is bob's")
log.info("this line is alice's again")
log.info("this one is carol's", extra={"user_id": "carol"})
```

## Configuring `setup_logging()`

`setup_logging()` returns a standard `logging.Logger`. Every argument is optional.

| Argument | Default | Purpose |
| --- | --- | --- |
| `name` | `None` | Logger name. `None` configures the root logger. |
| `level` | `"INFO"` | Level for every handler unless overridden below. |
| `to_console` | `True` | Log to the console. |
| `console_level` | `None` | Console level, defaulting to `level`. |
| `console_stream` | `None` | Console stream, for example `sys.stderr`. Defaults to `sys.stdout`. |
| `mode` | `"verbose"` | Console layout: `"verbose"` (coloured, with source location and context) or `"compact"` (`[LEVEL] message`). |
| `use_json` | `False` | Write JSON lines to the console instead. Needs the `json` extra. |
| `to_file` | `False` | Log to `file_path`. |
| `file_path` | `"app.log"` | Plain-text log file. Parent directories are created. |
| `file_level` | `None` | File level, defaulting to `level`. |
| `to_json_file` | `False` | Log JSON lines to `json_file_path`. Needs the `json` extra. |
| `json_file_path` | `"app.json.log"` | JSON log file. |
| `json_level` | `None` | JSON file level, defaulting to `level`. |
| `to_syslog` | `False` | Log to syslog. |
| `syslog_address` | `("localhost", 514)` | A `(host, port)` tuple (UDP) or a Unix socket path such as `"/dev/log"`. |
| `syslog_facility` | `SysLogHandler.LOG_USER` | Syslog facility. |
| `syslog_level` | `None` | Syslog level, defaulting to `level`. |
| `rotation` | `"size"` | `"size"` rotates at `max_bytes`, `"time"` rotates the plain-text file at midnight. |
| `max_bytes` | `5 * 1024 * 1024` | Size at which size-based rotation happens. |
| `backup_count` | `2` | Number of rotated files to keep. |
| `overwrite` | `False` | Truncate the plain-text and JSON files at start-up instead of appending. |
| `context` | `None` | Initial global context, as a dictionary. |
| `propagate` | `False` | Let records also reach the handlers of parent loggers. |

Things worth knowing:

- Calling `setup_logging()` again for the same logger replaces its handlers and closes the old
  ones, so it is safe to call from several places.
- `propagate` defaults to `False` because the logger gets its own handlers. Turn it on if the root
  logger also has handlers and you want records there too.
- Asking for JSON output without `python-json-logger` installed raises an `ImportError` with an
  install hint.

### Console colour

Colour is used only when the console stream is a terminal. It is switched off when output is
piped or redirected, when the `NO_COLOR` environment variable is set, or when `TERM=dumb`. Set
`FORCE_COLOR` to keep colour on regardless, which suits CI systems that render ANSI codes.
Log files never contain colour codes.

### JSON records

Each JSON record starts with `timestamp` (ISO 8601 with UTC offset), `level`, `logger` and
`message`, followed by the context fields. Exceptions add an `exc_info` field with the traceback.

## Helpers

```python
from pylogkit import log_duration, log_exception, tqdm_logging

@log_duration(logger, level="debug")
def import_orders():
    ...                    # logs "import_orders took 0.1234 seconds", even if it raises

try:
    risky()
except ValueError:
    log_exception(logger, "risky() failed")      # ERROR with traceback

for order in tqdm_logging(orders, logger):       # progress bar if tqdm is installed,
    process(order)                               # otherwise "Progress: n/total" log lines
```

## Development

```bash
git clone https://github.com/markbac/py-logkit
cd py-logkit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
pytest                   # run the tests
pytest --cov             # with coverage (the build fails below 90%)
ruff check . && ruff format --check .   # lint and formatting
mypy                     # strict type checking (the package ships py.typed)
```

The same checks run in GitHub Actions on every push and pull request, across Python 3.10 to 3.14,
with and without the optional extras, and with python-json-logger 2.x as well as the latest release.

See [CHANGELOG.md](CHANGELOG.md) for what has changed, and the
[issue tracker](https://github.com/markbac/py-logkit/issues) for planned work.

## Licence

MIT. See [LICENSE](LICENSE).
