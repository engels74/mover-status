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
    ContextCapturingFilter,
    ContextualLogRecord,
    LogFieldContext,
    LogLevelContext,
    ThreadLocalContext,
    combined_log_context,
    log_field_context,
    log_level_context,
    thread_local_context,
)
from .correlation_id import (
    CorrelationIdContext,
    CorrelationIdManager,
    clear_correlation_id,
    correlation_id_context,
    generate_correlation_id,
    get_correlation_id,
    get_correlation_id_manager,
    set_correlation_id,
)

__all__ = [
    "ColoredFormatter",
    "ConfigurationError",
    "ConsoleHandler",
    "ContextCapturingFilter",
    "ContextualLogRecord",
    "CorrelationIdContext",
    "CorrelationIdManager",
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
    "clear_correlation_id",
    "combined_log_context",
    "configure_handler",
    "correlation_id_context",
    "create_rotating_file_handler",
    "generate_correlation_id",
    "get_correlation_id",
    "get_correlation_id_manager",
    "get_global_level",
    "get_log_level_manager",
    "get_logger_level",
    "log_field_context",
    "log_level_context",
    "reset_all_levels",
    "set_correlation_id",
    "set_global_level",
    "set_logger_level",
    "thread_local_context",
]
