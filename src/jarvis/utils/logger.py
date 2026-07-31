"""
Structured Logging Utility for Jarvis.
"""

import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(log_level: str = "INFO", log_dir: str = "data/logs") -> logging.Logger:
    """Configure root logger with console stream and rotating log files."""
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("jarvis")
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate logs
    if root_logger.handlers:
        root_logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler
    log_file = path / "jarvis.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return root_logger
