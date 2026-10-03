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
