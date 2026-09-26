"""Pipeline logging: stage, project ID, match status and evidence; never secrets or env values."""

from __future__ import annotations

import logging
import sys

FORMAT = "%(asctime)s %(levelname)-7s %(name)s  %(message)s"


def configure_logging(level: str) -> None:
    """Send GridLock logs to stderr, leaving stdout for command output such as JSON reports."""
    root = logging.getLogger("gridlock")
    root.setLevel(level)
    if not any(getattr(handler, "_gridlock", False) for handler in root.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(FORMAT, datefmt="%H:%M:%S"))
        handler._gridlock = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.propagate = False


def get_logger(stage: str) -> logging.Logger:
    return logging.getLogger(f"gridlock.{stage}")
