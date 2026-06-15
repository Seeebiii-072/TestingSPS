"""Structured logging configuration for the email worker."""

import logging
import sys
from typing import Optional


def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Create and configure a structured logger.

    Args:
        name: The logger name, typically __name__.
        level: Override log level. Defaults to INFO.

    Returns:
        A configured Logger instance.
    """
    logger = logging.getLogger(name)

    if level:
        log_level = getattr(logging, level.upper(), logging.INFO)
    else:
        log_level = logging.INFO

    logger.setLevel(log_level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger("email_worker")