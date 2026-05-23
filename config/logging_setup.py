"""
config/logging_setup.py — Centralized logging configuration for Numa.

Provides a single entry point to configure logging across all modules.
Call configure_logging() early in main.main() with the desired log level.
"""

import logging
import sys


def configure_logging(level_str: str = "INFO"):
    """
    Configure logging for the entire application.

    Parameters
    ----------
    level_str : str
        Log level as a string: "DEBUG", "INFO", "WARNING", "ERROR"
        Default: "INFO"

    Sets up:
    - Console output with a simple format
    - Log level based on settings
    """
    # Map string to logging level
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }

    level = level_map.get(level_str.upper(), logging.INFO)

    # Configure basic logging — console only for now
    logging.basicConfig(
        level=level,
        format="[%(name)s] %(levelname)s: %(message)s",
        stream=sys.stdout,
    )
