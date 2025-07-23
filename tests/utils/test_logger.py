"""Test logging utility for consistent logging across all tests."""
import logging
import sys
from pathlib import Path


class TestLogger:
    """Centralized logging utility for tests."""

    _loggers = {}
    _log_dir = Path("test_logs")
    _log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    _date_format = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def get_logger(cls, name: str, level="INFO") -> logging.Logger:
        """Get or create a logger with the specified name."""
        if name in cls._loggers:
            return cls._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level))

        logger.handlers = []

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            "%(levelname)-8s | %(name)-20s | %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # # File handler
        # cls._log_dir.mkdir(exist_ok=True)
        # log_file = cls._log_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        # file_handler = logging.FileHandler(log_file)
        # file_handler.setLevel(logging.DEBUG)
        # file_formatter = logging.Formatter(cls._log_format, cls._date_format)
        # file_handler.setFormatter(file_formatter)
        # logger.addHandler(file_handler)

        cls._loggers[name] = logger
        return logger


def get_test_logger(name: str = "test", level="INFO") -> logging.Logger:
    """Get a test logger instance."""
    return TestLogger.get_logger(name, level)
