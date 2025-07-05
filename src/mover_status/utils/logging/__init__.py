"""Logging utilities and structured logging setup."""

from __future__ import annotations

from .handlers import (
    ColoredFormatter,
    ConsoleHandler,
    FileHandler,
    SyslogHandler,
    configure_handler,
    create_rotating_file_handler,
)
from .log_level_manager import (
    ConfigurationError,
    LogLevel,
    LogLevelManager,
    get_global_level,
    get_log_level_manager,
    get_logger_level,
    reset_all_levels,
    set_global_level,
    set_logger_level,
)
from .structured_formatter import (
    LogFormat,
    StructuredFormatter,
    TimestampFormat,
)
from .context_managers import (
    ContextualLogRecord,
    LogFieldContext,
    LogLevelContext,
    ThreadLocalContext,
    combined_log_context,
    log_field_context,
    log_level_context,
    thread_local_context,
)

__all__ = [
    "ColoredFormatter",
    "ConfigurationError",
    "ConsoleHandler",
    "ContextualLogRecord",
    "FileHandler",
    "LogFieldContext",
    "LogFormat",
    "LogLevel",
    "LogLevelContext",
    "LogLevelManager",
    "StructuredFormatter",
    "SyslogHandler",
    "ThreadLocalContext",
    "TimestampFormat",
    "combined_log_context",
    "configure_handler",
    "create_rotating_file_handler",
    "get_global_level",
    "get_log_level_manager",
    "get_logger_level",
    "log_field_context",
    "log_level_context",
    "reset_all_levels",
    "set_global_level",
    "set_logger_level",
    "thread_local_context",
]
