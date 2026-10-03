# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- `setup_logging()` accepts `syslog_address` (a `(host, port)` tuple or a Unix
  socket path such as `/dev/log`) and `syslog_facility`. Syslog lines now
  include the context fields (#12).
- `setup_logging(console_stream=...)` selects the console stream, for example
  `sys.stderr`. The default is still `sys.stdout` (#13).
- A full README: rationale, installation, quick start with real output
  samples, context fields, a reference table of every `setup_logging()`
  argument, colour and JSON behaviour, helpers and development setup. Tests
  run its examples and check that every argument is documented (#15).
- Tests for size and time rotation, directory creation, `log_exception`,
  thread isolation of the context, the `context=` argument, the module demo
  and the behaviour without each optional dependency. Coverage is now 96%, and
  `pytest --cov` fails below 90% (#16).
- GitHub Actions workflow: ruff lint and format checks, mypy, tests on Python
  3.10 to 3.14, tests without the optional extras and with python-json-logger
  2.0.7, and a job that builds the sdist and wheel, runs `twine check` and
  imports the wheel from a clean environment. Ruff (pycodestyle, pyflakes,
  isort, pep8-naming, pyupgrade, bugbear and pydocstyle) and mypy are
  configured in `pyproject.toml` (#17).
- The package is fully type annotated, ships a PEP 561 `py.typed` marker and
  is checked with `mypy --strict` in CI. A CI step checks that the wheel
  contains the marker (#19).
- The version is single-sourced in `pylogkit/_version.py` and exposed as
  `pylogkit.__version__`. A release workflow builds and checks the
  distribution when a `v*` tag is pushed, verifies that the tag matches the
  version, and creates a GitHub release. The process is documented in
  `docs/releasing.md`. Publishing to PyPI is deliberately left out until the
  distribution name is settled (#20).

### Changed

- `setup_logging()` gains a `propagate` argument that defaults to `False`, so
  records are no longer emitted a second time by handlers on ancestor loggers.
  Pass `propagate=True` for the previous behaviour (#5).
- Requesting JSON output (`use_json=True` or `to_json_file=True`) without
  python-json-logger installed now raises `ImportError` with an install hint
  instead of silently doing nothing (#6).
- `log_duration()` validates `level` when the decorator is created and raises
  `ValueError` for unknown level names, instead of failing with
  `AttributeError` on the first call (#9).
- Internal tidy-up with no behaviour change: the coloured console formatter is
  built by one helper, level colours are defined once, format strings and the
  date format are module constants, and the remaining public functions and
  classes have docstrings (#10).
- The host name is looked up once and cached instead of calling
  `socket.gethostname()` for every log record (#11).
- Console colour is now disabled automatically when the stream is not a
  terminal, when `NO_COLOR` is set or when `TERM=dumb`. `FORCE_COLOR` turns it
  back on, which CI systems that render ANSI colours can use. Piped output
  therefore no longer contains escape codes (#13).
- All packaging metadata now lives in `pyproject.toml` (PEP 621), with project
  URLs, a licence expression, classifiers and a readme. The minimum Python
  version is raised from 3.7 to 3.10 (#14).
- python-json-logger and tqdm are now optional extras: `pip install
  "pylogkit[json]"`, `"pylogkit[progress]"` or `"pylogkit[all]"`. Only
  colorlog is installed by default. Use `pip install -e ".[all,dev]"` for
  development (#14).
- The code is formatted with `ruff format` and annotations use `X | None`.
  `log_exception()`, `log_duration()` and `tqdm_logging()` are typed to accept
  a `ContextualLoggerAdapter` as well as a `Logger`. The `ImportError` raised
  when colorlog is missing now chains the original error (#17).

### Deprecated

- `setup_syslog_logger()` is deprecated and now delegates to
  `setup_logging(to_syslog=True, ...)`. It emits a `DeprecationWarning` and
  will be removed in a future release (#12).

### Removed

- The unused `CompactContextFormatter` class and the unused `json` import
  (#10).
- `setup.py` and `requirements.txt`, which duplicated `pyproject.toml` (#14).

### Fixed

- Added the missing `pylogkit/__init__.py`, so installed distributions
  actually contain the package. The public API is re-exported from `pylogkit`
  (#1).
- Corrected the dependency name `colourlog` to `colorlog` in `setup.py`,
  `requirements.txt` and the module docstring. The misspelt name pointed at a
  package that does not provide the module the code imports (#2).
- `tqdm_logging()` no longer yields nothing when tqdm is installed, and the
  fallback no longer raises `TypeError` for iterables without a length (#3).
- `ContextualLoggerAdapter.with_context()` now returns a new adapter instead
  of permanently changing the global thread-local context. `ContextFilter` no
  longer overwrites fields already set on a record (#4).
- `setup_logging()` is now idempotent: it closes the handlers and removes the
  context filter from a previous call instead of stacking them (#5).
- `setup_logging()` options are no longer silently ignored: `overwrite`
  truncates the plain-text and JSON log files, `use_json` writes JSON to the
  console, and `mode="compact"` works whether or not python-json-logger is
  installed (#6).
- Records from child loggers (for example `myapp.db`) are no longer dropped
  with `ValueError: Formatting field not found in record: 'emoji'`.
  `ContextFilter` is now attached to each handler instead of the logger, so
  every record a handler emits gets the context fields and level emoji (#7).
- python-json-logger is now imported from `pythonjsonlogger.json` (3.1 and
  later), falling back to `pythonjsonlogger.jsonlogger` for 2.x. Importing
  `pylogkit` no longer triggers a `DeprecationWarning` with current releases
  (#8).
- `log_duration()` now logs the duration even when the decorated function
  raises (as `... failed after N seconds`) and measures with the monotonic
  `time.perf_counter()` instead of `time.time()` (#9).
- Plain-text log files no longer end every line with a stray ANSI reset
  sequence (`\x1b[0m`) appended by colorlog (#36).
- JSON log records now contain `timestamp` (ISO 8601 with UTC offset),
  `level`, `logger` and `message`, in that order, followed by the context
  fields. Before, they had only the message and the context. The internal
  `emoji` and `context` fields no longer leak into JSON, and the output is
  identical across python-json-logger 2.x and later releases (#42).
