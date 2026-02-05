"""Logging configuration for Kalib microscopy control system.

Provides structured logging with file rotation, console output,
and context-aware logging for debugging and monitoring.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class KalibLogger:
    """Custom logger configuration for Kalib."""

    _instance: Optional['KalibLogger'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self._loggers = {}
            self._log_dir = None
            self._console_level = logging.INFO
            self._file_level = logging.DEBUG

    def setup(
        self,
        log_dir: str = './logs',
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ) -> None:
        """Setup logging configuration.

        Args:
            log_dir: Directory for log files
            console_level: Logging level for console output
            file_level: Logging level for file output
            max_bytes: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
        """
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._console_level = console_level
        self._file_level = file_level

        # Log format
        detailed_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        simple_format = logging.Formatter(
            '%(levelname)s - %(name)s - %(message)s'
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(simple_format)

        # Main log file (daily rotation)
        today = datetime.now().strftime('%Y%m%d')
        main_log_file = self._log_dir / f'kalib_{today}.log'
        file_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(detailed_format)

        # Error log file
        error_log_file = self._log_dir / 'kalib_error.log'
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_format)

        # Store handlers for later use
        self._console_handler = console_handler
        self._file_handler = file_handler
        self._error_handler = error_handler

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the given name.

        Args:
            name: Logger name (typically __name__ from calling module)

        Returns:
            Configured logger instance
        """
        if name in self._loggers:
            return self._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)  # Capture all levels

        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()

        # Add handlers
        if hasattr(self, '_console_handler'):
            logger.addHandler(self._console_handler)
        if hasattr(self, '_file_handler'):
            logger.addHandler(self._file_handler)
        if hasattr(self, '_error_handler'):
            logger.addHandler(self._error_handler)

        # Prevent propagation to root logger
        logger.propagate = False

        self._loggers[name] = logger
        return logger

    def set_console_level(self, level: int) -> None:
        """Change console logging level.

        Args:
            level: New logging level (e.g., logging.DEBUG, logging.INFO)
        """
        self._console_level = level
        if hasattr(self, '_console_handler'):
            self._console_handler.setLevel(level)

    def set_file_level(self, level: int) -> None:
        """Change file logging level.

        Args:
            level: New logging level
        """
        self._file_level = level
        if hasattr(self, '_file_handler'):
            self._file_handler.setLevel(level)


# Global logger instance
_logger_instance = KalibLogger()


def setup_logging(
    log_dir: str = './logs',
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG
) -> None:
    """Setup global logging configuration.

    Args:
        log_dir: Directory for log files
        console_level: Logging level for console output
        file_level: Logging level for file output
    """
    _logger_instance.setup(log_dir, console_level, file_level)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
        logger.error("An error occurred", exc_info=True)
    """
    return _logger_instance.get_logger(name)


def set_console_level(level: int) -> None:
    """Change console logging level.

    Args:
        level: New logging level (e.g., logging.DEBUG, logging.INFO)
    """
    _logger_instance.set_console_level(level)


def set_file_level(level: int) -> None:
    """Change file logging level.

    Args:
        level: New logging level
    """
    _logger_instance.set_file_level(level)
