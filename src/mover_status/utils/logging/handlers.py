"""Logging handlers with structured formatting support."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Callable, TextIO, override

from .structured_formatter import LogFormat, StructuredFormatter, TimestampFormat


class ColoredFormatter(StructuredFormatter):
    """Structured formatter with color support for console output."""
    
    # ANSI color codes
    COLORS: dict[str, str] = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',      # Reset
    }
    
    def __init__(
        self,
        format_type: LogFormat = LogFormat.KEYVALUE,
        timestamp_format: TimestampFormat = TimestampFormat.HUMAN,
        enable_colors: bool = True,
        field_order: list[str] | None = None,
        exclude_fields: list[str] | None = None,
    ) -> None:
        """Initialize colored formatter.
        
        Args:
            format_type: Output format type
            timestamp_format: Timestamp format
            enable_colors: Whether to enable color output
            field_order: Custom field ordering
            exclude_fields: Fields to exclude from output
        """
        super().__init__(
            format_type=format_type, 
            timestamp_format=timestamp_format, 
            field_order=field_order,
            exclude_fields=exclude_fields
        )
        self.enable_colors: bool = enable_colors
    
    @override
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with optional colors.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted log string with optional colors
        """
        formatted = super().format(record)
        
        if self.enable_colors and record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]
            reset = self.COLORS['RESET']
            return f"{color}{formatted}{reset}"
        
        return formatted


class ConsoleHandler(logging.StreamHandler[TextIO]):
    """Console handler with structured formatting and optional color support."""
    
    def __init__(
        self,
        level: int = logging.INFO,
        use_stderr: bool = False,
        enable_colors: bool = True,
        formatter: logging.Formatter | None = None,
    ) -> None:
        """Initialize console handler.
        
        Args:
            level: Log level threshold
            use_stderr: Whether to use stderr instead of stdout
            enable_colors: Whether to enable color output
            formatter: Custom formatter (overrides color settings)
        """
        stream = sys.stderr if use_stderr else sys.stdout
        super().__init__(stream)
        self.setLevel(level)
        
        if formatter is not None:
            self.setFormatter(formatter)
        elif enable_colors:
            self.setFormatter(ColoredFormatter(enable_colors=True))
        else:
            self.setFormatter(StructuredFormatter(format_type=LogFormat.KEYVALUE))


class FileHandler(logging.FileHandler):
    """File handler with structured formatting and directory creation."""
    
    def __init__(
        self,
        filename: Path | str,
        level: int = logging.INFO,
        mode: str = 'a',
        formatter: logging.Formatter | None = None,
    ) -> None:
        """Initialize file handler.
        
        Args:
            filename: Path to log file
            level: Log level threshold
            mode: File open mode
            formatter: Custom formatter
        """
        filepath = Path(filename)
        
        # Create parent directories if they don't exist
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        super().__init__(str(filepath), mode=mode)
        self.setLevel(level)
        
        if formatter is not None:
            self.setFormatter(formatter)
        else:
            self.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))


class SyslogHandler:
    """Syslog handler with structured formatting."""
    
    def __init__(
        self,
        address: tuple[str, int] | str = ('localhost', 514),
        facility: int = logging.handlers.SysLogHandler.LOG_USER,
        level: int = logging.INFO,
        formatter: logging.Formatter | None = None,
    ) -> None:
        """Initialize syslog handler.
        
        Args:
            address: Syslog server address (host, port) or Unix socket path
            facility: Syslog facility
            level: Log level threshold
            formatter: Custom formatter
        """
        self.handler: logging.handlers.SysLogHandler = logging.handlers.SysLogHandler(address=address, facility=facility)
        self.handler.setLevel(level)
        
        if formatter is not None:
            self.handler.setFormatter(formatter)
        else:
            # Use JSON format for syslog for better parsing
            self.handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
    
    def __getattr__(self, name: str) -> object:
        """Delegate attribute access to the underlying handler."""
        return getattr(self.handler, name)  # pyright: ignore[reportAny] # delegation pattern


def create_rotating_file_handler(
    filename: Path | str,
    level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
    max_bytes: int | None = None,
    backup_count: int = 5,
    when: str | None = None,
    interval: int = 1,
) -> logging.handlers.RotatingFileHandler | logging.handlers.TimedRotatingFileHandler:
    """Create a rotating file handler with size or time-based rotation.
    
    Args:
        filename: Path to log file
        level: Log level threshold
        formatter: Custom formatter
        max_bytes: Maximum file size before rotation (for size-based rotation)
        backup_count: Number of backup files to keep
        when: When to rotate (for time-based rotation): 'S', 'M', 'H', 'D', 'W0'-'W6', 'midnight'
        interval: Rotation interval
        
    Returns:
        Configured rotating file handler
        
    Raises:
        ValueError: If both size and time rotation parameters are specified or neither is specified
    """
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Validate parameters
    if max_bytes is not None and when is not None:
        raise ValueError("Cannot specify both size and time-based rotation parameters")
    
    if max_bytes is None and when is None:
        raise ValueError("Must specify either max_bytes for size-based rotation or when for time-based rotation")
    
    # Create appropriate handler
    if max_bytes is not None:
        # Size-based rotation
        handler = logging.handlers.RotatingFileHandler(
            str(filepath),
            maxBytes=max_bytes,
            backupCount=backup_count
        )
    else:
        # Time-based rotation
        assert when is not None  # Safe due to validation above
        handler = logging.handlers.TimedRotatingFileHandler(
            str(filepath),
            when=when,
            interval=interval,
            backupCount=backup_count
        )
    
    handler.setLevel(level)
    
    if formatter is not None:
        handler.setFormatter(formatter)
    else:
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
    
    return handler


def configure_handler(
    handler: logging.Handler,
    formatter: logging.Formatter | None = None,
    level: int | None = None,
    filter_func: Callable[[logging.LogRecord], bool] | None = None,
) -> logging.Handler:
    """Configure a logging handler with formatter, level, and filter.
    
    Args:
        handler: The handler to configure
        formatter: Custom formatter to apply
        level: Log level threshold
        filter_func: Filter function to apply
        
    Returns:
        The configured handler
    """
    if formatter is not None:
        handler.setFormatter(formatter)
    
    if level is not None:
        handler.setLevel(level)
    
    if filter_func is not None:
        handler.addFilter(filter_func)
    
    return handler