"""Structured logging infrastructure with syslog integration and correlation ID tracking.

This module provides comprehensive logging infrastructure for the mover-status application,
including integration with Unraid syslog, correlation ID tracking using ContextVar for
tracing notifications across multiple providers, and structured log formatters.

Requirements:
- 13.1: Log all mover lifecycle events at INFO level
- 13.2: Log all notification delivery attempts with provider name and outcome
- 13.3: Use correlation IDs to track notifications across multiple providers
- 13.4: Integrate with Unraid syslog for operational transparency
- 13.5: Log errors with full context without exposing secrets
- 6.4: NO logging or exposure of secrets in error messages or diagnostic output
- 6.5: Authentication failures logged WITHOUT including secret values
"""

import contextvars
import logging
import logging.handlers
import sys
from collections.abc import Mapping
from typing import Final, override

from mover_status.utils.sanitization import (
    sanitize_args,
    sanitize_value,
)

# Correlation ID context variable for tracking notifications across providers
# Automatically inherited by asyncio tasks and threads in free-threaded Python
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id",
    default=None,
)

# Log format constants
DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s"

SYSLOG_LOG_FORMAT: Final[str] = (
    "mover-status[%(process)d]: %(levelname)s - [%(correlation_id)s] - %(name)s - %(message)s"
)

# Default syslog address for Unraid
DEFAULT_SYSLOG_ADDRESS: Final[str] = "/dev/log"


class CorrelationIDFilter(logging.Filter):
    """Logging filter that adds correlation ID to log records.

    Retrieves the correlation ID from the ContextVar and adds it to each
    log record, enabling tracking of notifications across multiple providers
    and async tasks.

    The correlation ID is automatically inherited by:
    - Asyncio tasks created within the same context
    - Threads spawned in free-threaded Python builds
    - All function calls within the same execution context
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to log record from ContextVar.

        Args:
            record: Log record to enhance with correlation ID

        Returns:
            True to allow the record to be logged
        """
        # Get correlation ID from context variable, default to "N/A" if not set
        correlation_id = correlation_id_var.get()
        record.correlation_id = correlation_id if correlation_id is not None else "N/A"
        return True


class SecretRedactingFilter(logging.Filter):
    """Logging filter that redacts sensitive information from log messages.

    Prevents accidental exposure of secrets (webhook URLs, tokens, API keys)
    in log output by sanitizing:
    - Log message text (URLs, sensitive patterns)
    - Log message arguments (args tuple)
    - Structured logging context (extra dictionary)

    This filter uses comprehensive sanitization utilities to ensure secrets
    never appear in log output regardless of how they are passed to the logger.

    Requirements:
        - 13.5: Log errors with full context without exposing secrets
        - 6.4: NO logging or exposure of secrets in error messages or diagnostic output
        - 6.5: Authentication failures logged WITHOUT including secret values

    Examples:
        >>> logger.info("POST to %s", "https://discord.com/api/webhooks/123/token")
        # Logged as: "POST to https://discord.com/api/webhooks/123/<REDACTED>"

        >>> logger.error("Failed", extra={"url": "https://api.telegram.org/bot123/send"})
        # extra sanitized to: {"url": "https://api.telegram.org/bot<REDACTED>/send"}
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize sensitive information from log record.

        This method sanitizes three key areas of the log record:
        1. Message text: Sanitize the msg attribute directly
        2. Arguments: Sanitize the args tuple used for % formatting
        3. Extra context: Sanitize any extra fields passed to logger

        Args:
            record: Log record to sanitize

        Returns:
            True to allow the record to be logged (always)
        """
        # Sanitize the message text itself
        if isinstance(record.msg, str):
            sanitized_msg = sanitize_value(record.msg)
            if isinstance(sanitized_msg, str):
                record.msg = sanitized_msg

        # Sanitize arguments tuple (used for % formatting in getMessage())
        if record.args:
            # record.args can be a tuple or a Mapping (for % formatting)
            if isinstance(record.args, tuple):
                record.args = sanitize_args(record.args)
            # For Mapping args, sanitization happens through extra field processing below

        # Sanitize extra context dictionary
        # Extra fields are stored as attributes on the LogRecord
        # We need to sanitize any non-standard attributes that were added via extra={}
        if hasattr(record, "__dict__"):
            # Get standard LogRecord attributes to exclude from sanitization
            standard_attrs = {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "correlation_id",  # Our custom field added by CorrelationIDFilter
            }

            # Sanitize any extra fields
            for attr_name in list(record.__dict__.keys()):
                if attr_name not in standard_attrs and not attr_name.startswith("_"):
                    # getattr inherently returns Any for dynamic attributes - use explicit cast
                    attr_value: object = getattr(record, attr_name)  # pyright: ignore[reportAny]
                    sanitized_value = sanitize_value(attr_value, field_name=attr_name)
                    setattr(record, attr_name, sanitized_value)

        return True


def configure_logging(
    *,
    log_level: str = "INFO",
    enable_syslog: bool = True,
    syslog_address: str = DEFAULT_SYSLOG_ADDRESS,
    enable_console: bool = True,
) -> None:
    """Configure application logging with syslog integration and structured output.

    Sets up logging infrastructure with:
    - Correlation ID tracking via ContextVar
    - Syslog integration for Unraid compatibility
    - Console output for development/debugging
    - Secret redaction for security
    - Structured log formatting

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_syslog: Enable syslog handler for Unraid integration
        syslog_address: Syslog socket address (default: /dev/log for Unraid)
        enable_console: Enable console output handler

    Example:
        >>> configure_logging(log_level="INFO", enable_syslog=True)
        >>> logger = logging.getLogger(__name__)
        >>> correlation_id_var.set("abc-123")
        >>> logger.info("Notification sent", extra={"provider": "discord"})
    """
    # Get root logger
    root_logger = logging.getLogger()

    # Set log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create correlation ID filter (shared by all handlers)
    correlation_filter = CorrelationIDFilter()

    # Create secret redacting filter (shared by all handlers)
    secret_filter = SecretRedactingFilter()

    # Configure syslog handler for Unraid integration
    if enable_syslog:
        try:
            # Create syslog handler with Unix domain socket
            syslog_handler = logging.handlers.SysLogHandler(
                address=syslog_address,
                facility=logging.handlers.SysLogHandler.LOG_DAEMON,
            )

            # Set syslog-specific format
            syslog_formatter = logging.Formatter(SYSLOG_LOG_FORMAT)
            syslog_handler.setFormatter(syslog_formatter)

            # Add filters
            syslog_handler.addFilter(correlation_filter)
            syslog_handler.addFilter(secret_filter)

            # Add to root logger
            root_logger.addHandler(syslog_handler)

        except (OSError, FileNotFoundError) as exc:
            # Syslog not available (e.g., development environment)
            # Fall back to console only
            print(
                f"Warning: Could not connect to syslog at {syslog_address}: {exc}",
                file=sys.stderr,
            )

    # Configure console handler for development/debugging
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)

        # Set console-specific format
        console_formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
        console_handler.setFormatter(console_formatter)

        # Add filters
        console_handler.addFilter(correlation_filter)
        console_handler.addFilter(secret_filter)

        # Add to root logger
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified module.

    Convenience function to get a properly configured logger for a module.
    The logger will automatically include correlation IDs and redact secrets.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing notification")
    """
    return logging.getLogger(name)


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context.

    The correlation ID is stored in a ContextVar and automatically inherited by:
    - All asyncio tasks created within this context
    - All threads spawned in free-threaded Python builds
    - All function calls within the same execution context

    This enables tracking of a single notification across multiple providers
    without manual context passing.

    Args:
        correlation_id: Unique identifier for correlation (e.g., UUID)

    Example:
        >>> import uuid
        >>> set_correlation_id(str(uuid.uuid4()))
        >>> logger.info("Starting notification dispatch")
        >>> # All subsequent logs in this context will include the correlation ID
    """
    _ = correlation_id_var.set(correlation_id)


def get_correlation_id() -> str | None:
    """Get the current correlation ID from context.

    Returns:
        Current correlation ID or None if not set

    Example:
        >>> correlation_id = get_correlation_id()
        >>> if correlation_id:
        ...     print(f"Current correlation: {correlation_id}")
    """
    return correlation_id_var.get()


def clear_correlation_id() -> None:
    """Clear the correlation ID from the current context.

    Useful for cleanup after processing a notification event.

    Example:
        >>> set_correlation_id("abc-123")
        >>> # ... process notification ...
        >>> clear_correlation_id()
    """
    _ = correlation_id_var.set(None)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    extra: Mapping[str, object] | None = None,
) -> None:
    """Log a message with additional context fields.

    Convenience function for structured logging with extra context fields.
    Automatically includes correlation ID from ContextVar.

    Args:
        logger: Logger instance to use
        level: Logging level (e.g., logging.INFO)
        message: Log message
        extra: Additional context fields to include in log

    Example:
        >>> logger = get_logger(__name__)
        >>> log_with_context(
        ...     logger,
        ...     logging.INFO,
        ...     "Notification sent successfully",
        ...     extra={
        ...         "provider": "discord",
        ...         "event_type": "progress",
        ...         "percent": 75.5,
        ...         "delivery_time_ms": 234.5,
        ...     }
        ... )
    """
    # Merge extra context with correlation ID
    context = dict(extra) if extra else {}

    # Add correlation ID if available
    correlation_id = get_correlation_id()
    if correlation_id:
        context["correlation_id"] = correlation_id

    # Log with context
    logger.log(level, message, extra=context)
