"""Tests for file rotation."""

from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

from pylogkit import setup_logging


def test_size_rotation_keeps_the_configured_number_of_backups(tmp_path):
    """Files roll over at ``max_bytes`` and ``backup_count`` bounds the history."""
    path = tmp_path / "app.log"
    logger = setup_logging(
        "rot-size",
        to_console=False,
        to_file=True,
        file_path=str(path),
        max_bytes=300,
        backup_count=2,
    )

    for number in range(60):
        logger.info("message number %d", number)
    for handler in logger.handlers:
        handler.close()

    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["app.log", "app.log.1", "app.log.2"]


def test_size_rotation_uses_a_rotating_file_handler(tmp_path):
    """``rotation="size"`` is the default."""
    logger = setup_logging(
        "rot-default", to_console=False, to_file=True, file_path=str(tmp_path / "a.log")
    )

    assert [type(h) for h in logger.handlers] == [RotatingFileHandler]


def test_time_rotation_rotates_at_midnight(tmp_path):
    """``rotation="time"`` selects a handler that rolls over daily."""
    logger = setup_logging(
        "rot-time",
        to_console=False,
        to_file=True,
        file_path=str(tmp_path / "a.log"),
        rotation="time",
        backup_count=5,
    )

    (handler,) = logger.handlers
    assert isinstance(handler, TimedRotatingFileHandler)
    assert handler.when == "MIDNIGHT"
    assert handler.backupCount == 5


def test_parent_directories_are_created(tmp_path):
    """Log files may live in directories that do not exist yet."""
    path = tmp_path / "deep" / "er" / "app.log"

    logger = setup_logging("rot-dirs", to_console=False, to_file=True, file_path=str(path))
    logger.info("hello")
    for handler in logger.handlers:
        handler.flush()

    assert "hello" in path.read_text()
