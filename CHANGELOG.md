# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Fixed

- Added the missing `pylogkit/__init__.py`, so installed distributions actually
  contain the package. The public API is re-exported from `pylogkit` (#1).
- Corrected the dependency name `colourlog` to `colorlog` in `setup.py`,
  `requirements.txt` and the module docstring. The misspelt name pointed at
  a package that does not provide the module the code imports (#2).
- `tqdm_logging()` no longer yields nothing when tqdm is installed, and the
  fallback no longer raises `TypeError` for iterables without a length (#3).
- `ContextualLoggerAdapter.with_context()` now returns a new adapter instead of
  permanently changing the global thread-local context. `ContextFilter` no
  longer overwrites fields already set on a record (#4).
