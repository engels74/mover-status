"""Context managers for logging level and field management."""

from __future__ import annotations

import contextvars
import logging
import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, cast, override

from .log_level_manager import LogLevel


class ThreadLocalContext:
    """Context storage for logging context using contextvars for async support."""
    
    def __init__(self) -> None:
        """Initialize context storage."""
        self._local: threading.local = threading.local()
        self._contextvar: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar('log_fields', default={})  # pyright: ignore[reportExplicitAny]
    
    @property
    def fields(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        """Get context fields for current thread/context."""
        # Always use context variable first (for async support)
        context_fields = self._contextvar.get()
        # Always return a copy to avoid shared state
        return dict(context_fields)
    
    @fields.setter
    def fields(self, value: dict[str, Any]) -> None:  # pyright: ignore[reportExplicitAny]
        """Set context fields for current thread/context."""
        # Use only context variable for async support
        # Always create a copy to avoid shared state
        value_copy = dict(value)
        _ = self._contextvar.set(value_copy)


# Global thread-local context instance
thread_local_context = ThreadLocalContext()


class LogLevelContext:
    """Context manager for temporarily changing log levels."""
    
    def __init__(
        self,
        logger: logging.Logger | str | list[logging.Logger | str],
        level: LogLevel
    ) -> None:
        """Initialize log level context manager.
        
        Args:
            logger: Logger instance(s) or name(s) to modify
            level: Temporary log level to set
        """
        self.level: LogLevel = level
        self.original_levels: dict[logging.Logger, int] = {}
        
        # Normalize logger input to list of Logger instances
        if isinstance(logger, str):
            self.loggers: list[logging.Logger] = [logging.getLogger(logger)]
        elif isinstance(logger, logging.Logger):
            self.loggers = [logger]
        else:
            # Check if it's a list, otherwise it's an invalid type  
            if not isinstance(logger, list):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise TypeError(f"Invalid logger type: {type(logger)}")  # pyright: ignore[reportUnreachable]
            self.loggers = []
            for log in logger:
                if isinstance(log, str):
                    self.loggers.append(logging.getLogger(log))
                elif isinstance(log, logging.Logger):  # pyright: ignore[reportUnnecessaryIsInstance]
                    self.loggers.append(log)
                else:
                    raise TypeError(f"Invalid logger type: {type(log)}")
    
    def __enter__(self) -> LogLevelContext:
        """Enter context and set temporary log levels."""
        # Store original levels
        for logger in self.loggers:
            self.original_levels[logger] = logger.level
            logger.setLevel(self.level.value)
        
        return self
    
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Exit context and restore original log levels."""
        # Restore original levels
        for logger, original_level in self.original_levels.items():
            logger.setLevel(original_level)


class LogFieldContext:
    """Context manager for adding contextual fields to log messages."""
    
    def __init__(self, fields: dict[str, Any]) -> None:  # pyright: ignore[reportExplicitAny]
        """Initialize log field context manager.
        
        Args:
            fields: Dictionary of fields to add to log context
        """
        self.fields: dict[str, Any] = fields  # pyright: ignore[reportExplicitAny]
        self.previous_fields: dict[str, Any] = {}  # pyright: ignore[reportExplicitAny]
    
    def __enter__(self) -> LogFieldContext:
        """Enter context and add fields to context storage."""
        # Store previous values for fields we're about to override
        current_fields = thread_local_context.fields
        for key in self.fields:
            if key in current_fields:
                self.previous_fields[key] = current_fields[key]
        
        # Create new dict with merged fields to avoid shared state
        new_fields = dict(current_fields)
        new_fields.update(self.fields)
        thread_local_context.fields = new_fields
        
        return self
    
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Exit context and restore previous field values."""
        current_fields = thread_local_context.fields
        
        # Create new dict with restored fields to avoid shared state
        new_fields = dict(current_fields)
        for key in self.fields:
            if key in self.previous_fields:
                # Restore previous value
                new_fields[key] = self.previous_fields[key]
            else:
                # Remove the field entirely
                new_fields.pop(key, None)
        
        thread_local_context.fields = new_fields


class ContextualLogRecord:
    """Wrapper for log records that includes contextual fields."""
    
    def __init__(self, record: logging.LogRecord) -> None:
        """Initialize contextual log record.
        
        Args:
            record: Original log record to wrap
        """
        self.record: logging.LogRecord = record
        
        # Copy all attributes from original record
        for attr in dir(record):
            if not attr.startswith('_'):
                value = getattr(record, attr)  # pyright: ignore[reportAny]
                if not callable(value):  # pyright: ignore[reportAny]
                    setattr(self, attr, value)
    
    def get_context_fields(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        """Get context fields from context storage.
        
        Returns:
            Dictionary of context fields
        """
        return dict(thread_local_context.fields)
    
    def __getattr__(self, name: str) -> object:
        """Delegate attribute access to original record."""
        return getattr(self.record, name)  # pyright: ignore[reportAny] # LogRecord attributes are dynamically typed


@contextmanager
def log_level_context(
    logger: logging.Logger | str | list[logging.Logger | str],
    level: LogLevel
) -> Generator[None, None, None]:
    """Context manager for temporarily changing log levels.
    
    Args:
        logger: Logger instance(s) or name(s) to modify
        level: Temporary log level to set
        
    Yields:
        None
    """
    with LogLevelContext(logger, level):
        yield


@contextmanager
def log_field_context(fields: dict[str, Any]) -> Generator[None, None, None]:  # pyright: ignore[reportExplicitAny]
    """Context manager for adding contextual fields to log messages.
    
    Args:
        fields: Dictionary of fields to add to log context
        
    Yields:
        None
    """
    with LogFieldContext(fields):
        yield


@contextmanager
def combined_log_context(
    logger: logging.Logger | str | list[logging.Logger | str],
    level: LogLevel,
    fields: dict[str, Any]  # pyright: ignore[reportExplicitAny]
) -> Generator[None, None, None]:
    """Combined context manager for both level and field changes.
    
    Args:
        logger: Logger instance(s) or name(s) to modify
        level: Temporary log level to set
        fields: Dictionary of fields to add to log context
        
    Yields:
        None
    """
    with LogLevelContext(logger, level):
        with LogFieldContext(fields):
            yield


class ContextCapturingFilter(logging.Filter):
    """Filter that captures context fields at log record creation time."""
    
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Capture context fields and store them in the log record.
        
        Args:
            record: The log record to process
            
        Returns:
            True to allow the record to be processed
        """
        # Capture current context fields at log time
        context_fields = dict(thread_local_context.fields)
        setattr(record, '_context_fields', context_fields)
        return True