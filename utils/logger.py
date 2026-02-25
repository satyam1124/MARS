"""
logger.py — Logging utility for MARS.

Provides :func:`get_logger` which returns a :class:`logging.Logger` configured
with:
- A rotating file handler writing to ``logs/mars.log``.
- A coloured console handler for human-friendly output.
- Log level read from ``config/settings.yaml`` (``logging.level``).
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

import yaml

# ---------------------------------------------------------------------------
# ANSI colour codes used by the console formatter
# ---------------------------------------------------------------------------
_RESET: Final[str] = "\033[0m"
_BOLD: Final[str] = "\033[1m"

_LEVEL_COLOURS: Final[dict[int, str]] = {
    logging.DEBUG: "\033[36m",      # cyan
    logging.INFO: "\033[32m",       # green
    logging.WARNING: "\033[33m",    # yellow
    logging.ERROR: "\033[31m",      # red
    logging.CRITICAL: "\033[35m",   # magenta
}


class _ColourFormatter(logging.Formatter):
    """Logging formatter that adds ANSI colour codes to the level-name field."""

    _FMT: Final[str] = (
        "%(asctime)s | {colour}{bold}%(levelname)-8s{reset} | "
        "%(name)s | %(message)s"
    )
    _DATE_FMT: Final[str] = "%Y-%m-%d %H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        colour = _LEVEL_COLOURS.get(record.levelno, "")
        fmt = self._FMT.format(colour=colour, bold=_BOLD, reset=_RESET)
        formatter = logging.Formatter(fmt, datefmt=self._DATE_FMT)
        return formatter.format(record)


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

_SETTINGS_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"
_DEFAULT_LEVEL: Final[str] = "INFO"
_DEFAULT_LOG_FILE: Final[str] = "logs/mars.log"
_DEFAULT_MAX_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MB
_DEFAULT_BACKUP_COUNT: Final[int] = 5


def _load_log_settings() -> tuple[str, str, int, int]:
    """Return *(level, file, max_bytes, backup_count)* from settings.yaml.

    Falls back to sensible defaults if the file is absent or malformed.
    """
    try:
        with _SETTINGS_PATH.open() as fh:
            cfg = yaml.safe_load(fh) or {}
        log_cfg: dict = cfg.get("logging", {})
        level = str(log_cfg.get("level", _DEFAULT_LEVEL)).upper()
        log_file = str(log_cfg.get("file", _DEFAULT_LOG_FILE))
        max_bytes = int(log_cfg.get("max_bytes", _DEFAULT_MAX_BYTES))
        backup_count = int(log_cfg.get("backup_count", _DEFAULT_BACKUP_COUNT))
    except Exception:  # noqa: BLE001
        level, log_file, max_bytes, backup_count = (
            _DEFAULT_LEVEL,
            _DEFAULT_LOG_FILE,
            _DEFAULT_MAX_BYTES,
            _DEFAULT_BACKUP_COUNT,
        )
    return level, log_file, max_bytes, backup_count


# ---------------------------------------------------------------------------
# Cache so each logger name is only configured once
# ---------------------------------------------------------------------------
_configured_loggers: set[str] = set()


def get_logger(name: str) -> logging.Logger:
    """Return a configured :class:`logging.Logger` for *name*.

    The logger has two handlers:
    - **RotatingFileHandler** — writes to the path specified in
      ``config/settings.yaml`` (default ``logs/mars.log``).
    - **StreamHandler** — writes coloured output to *stdout*.

    The ``logs/`` directory is created automatically if it does not exist.

    Parameters
    ----------
    name:
        Logger name, typically ``__name__`` of the calling module.

    Returns
    -------
    logging.Logger
        Fully configured logger instance.

    Examples
    --------
    >>> log = get_logger(__name__)
    >>> log.info("MARS initialised.")
    """
    logger = logging.getLogger(name)

    if name in _configured_loggers:
        return logger

    _configured_loggers.add(name)

    level_str, log_file, max_bytes, backup_count = _load_log_settings()
    level: int = getattr(logging, level_str, logging.INFO)
    logger.setLevel(level)

    # Resolve log file path relative to the project root (parent of utils/)
    log_path = Path(log_file)
    if not log_path.is_absolute():
        log_path = Path(__file__).resolve().parents[1] / log_path

    log_path.parent.mkdir(parents=True, exist_ok=True)

    # ----- file handler -----
    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)

    # ----- console handler -----
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(_ColourFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Prevent log records from propagating to the root logger's handlers so
    # messages are not printed twice when a root logger is also configured.
    logger.propagate = False

    return logger
