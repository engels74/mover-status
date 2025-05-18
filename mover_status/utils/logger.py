"""
Configurable logging utilities for the Mover Status application.

This module provides functions to set up and configure logging for the application,
supporting both console and file logging with customizable formats and log levels.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast, final


class LogLevel(Enum):
    """Enum representing log levels."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogFormat(Enum):
    """Enum representing predefined log formats."""
    SIMPLE = "%(asctime)s - %(message)s"
    DETAILED = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"


@dataclass
@final
class LoggerConfig:
    """Configuration for the logger."""
    console_enabled: bool = True
    file_enabled: bool = False
    file_path: str | None = None
    level: LogLevel | int = LogLevel.INFO
    format: LogFormat | str = LogFormat.SIMPLE
    # Whether to append to existing log file or overwrite it
    file_append: bool = True
    # Maximum size of log file in bytes before rotation (default: 10MB)
    max_file_size: int = 10 * 1024 * 1024
    # Number of backup log files to keep
    backup_count: int = 3


# Cache for loggers to ensure we don't create duplicates
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger by name.

    If a logger with this name already exists, returns the existing instance.
    Otherwise, returns a new logger with the given name.

    Args:
        name: The name of the logger.

    Returns:
        A logger instance.
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    _loggers[name] = logger
    return logger


def setup_logger(name: str, config: LoggerConfig) -> logging.Logger:
    """
    Set up a logger with the given configuration.

    Args:
        name: The name of the logger.
        config: The configuration for the logger.

    Returns:
        A configured logger instance.

    Raises:
        ValueError: If file logging is enabled but no file path is provided.
    """
    logger = get_logger(name)

    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Set the log level
    log_level = config.level.value if isinstance(config.level, LogLevel) else config.level
    logger.setLevel(log_level)

    # Create formatter
    log_format = config.format.value if isinstance(config.format, LogFormat) else config.format
    formatter = logging.Formatter(log_format)

    # Add console handler if enabled
    if config.console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if enabled
    if config.file_enabled:
        if not config.file_path:
            raise ValueError("File logging enabled but no file path provided")

        # Ensure the directory exists
        log_dir = os.path.dirname(config.file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Create file handler
        file_mode = 'a' if config.file_append else 'w'

        if config.max_file_size > 0 and config.backup_count > 0:
            # Use RotatingFileHandler for log rotation
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                config.file_path,
                mode=file_mode,
                maxBytes=config.max_file_size,
                backupCount=config.backup_count
            )
        else:
            # Use standard FileHandler
            file_handler = logging.FileHandler(config.file_path, mode=file_mode)

        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def configure_from_dict(name: str, config_dict: dict[str, Any]) -> logging.Logger:
    """
    Configure a logger from a dictionary.

    This is a convenience function for configuring a logger from a dictionary,
    such as one loaded from a configuration file.

    Args:
        name: The name of the logger.
        config_dict: A dictionary containing logger configuration.
            Expected keys:
            - console_enabled: bool
            - file_enabled: bool
            - file_path: str (optional)
            - level: str (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            - format: str (SIMPLE, DETAILED, or a custom format string)
            - file_append: bool (optional)
            - max_file_size: int (optional)
            - backup_count: int (optional)

    Returns:
        A configured logger instance.

    Raises:
        ValueError: If the configuration is invalid.
    """
    # Convert string log level to LogLevel enum
    level_str = cast(str, config_dict.get('level', 'INFO')).upper()
    try:
        level = LogLevel[level_str]
    except KeyError:
        raise ValueError(f"Invalid log level: {level_str}")

    # Convert string format to LogFormat enum or use as custom format
    format_str = cast(str, config_dict.get('format', 'SIMPLE'))
    try:
        log_format = LogFormat[format_str.upper()]
    except KeyError:
        # If not a predefined format, use as custom format string
        log_format = format_str

    # Create config object
    config = LoggerConfig(
        console_enabled=bool(config_dict.get('console_enabled', True)),
        file_enabled=bool(config_dict.get('file_enabled', False)),
        file_path=cast(str | None, config_dict.get('file_path')),
        level=level,
        format=log_format,
        file_append=bool(config_dict.get('file_append', True)),
        max_file_size=int(config_dict.get('max_file_size', 10 * 1024 * 1024)),
        backup_count=int(config_dict.get('backup_count', 3))
    )

    return setup_logger(name, config)
