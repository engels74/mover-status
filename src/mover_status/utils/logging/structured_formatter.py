"""Structured logging formatter implementation."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, override


class LogFormat(Enum):
    """Supported log output formats."""
    
    JSON = "json"
    KEYVALUE = "keyvalue"


class TimestampFormat(Enum):
    """Supported timestamp formats."""
    
    ISO = "iso"
    EPOCH = "epoch"
    HUMAN = "human"


class StructuredFormatter(logging.Formatter):
    """Structured logging formatter supporting multiple output formats."""
    
    def __init__(
        self,
        format_type: LogFormat = LogFormat.JSON,
        timestamp_format: TimestampFormat = TimestampFormat.ISO,
        field_order: list[str] | None = None,
        exclude_fields: list[str] | None = None,
    ) -> None:
        """Initialize the structured formatter.
        
        Args:
            format_type: Output format type (JSON or key-value)
            timestamp_format: Timestamp format to use
            field_order: Custom field ordering (for key-value format)
            exclude_fields: Fields to exclude from output
        """
        super().__init__()
        self.format_type: LogFormat = format_type
        self.timestamp_format: TimestampFormat = timestamp_format
        self.field_order: list[str] = field_order or []
        self.exclude_fields: set[str] = set(exclude_fields or [])
        
        # Default field order for consistent output
        self.default_fields: list[str] = [
            "timestamp",
            "level",
            "logger",
            "message",
            "module",
            "function",
            "line",
        ]
    
    @override
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record into structured output.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted log string
        """
        # Build the structured data
        log_data = self._build_log_data(record)
        
        # Format based on output type
        if self.format_type == LogFormat.JSON:
            return self._format_json(log_data)
        elif self.format_type == LogFormat.KEYVALUE:
            return self._format_keyvalue(log_data)
        else:
            raise ValueError(f"Unsupported format type: {self.format_type}")
    
    def _build_log_data(self, record: logging.LogRecord) -> dict[str, Any]:
        """Build structured log data from log record.
        
        Args:
            record: The log record to process
            
        Returns:
            Dictionary containing structured log data
        """
        # Start with basic fields
        log_data: dict[str, Any] = {
            "timestamp": self._format_timestamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": Path(record.pathname).stem,
            "function": record.funcName or "<module>",
            "line": record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "lineno", "funcName", "created",
                "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "getMessage", "exc_info",
                "exc_text", "stack_info", "extra",
            }:
                log_data[key] = self._serialize_value(value)
        
        # Remove excluded fields
        for field in self.exclude_fields:
            log_data.pop(field, None)
        
        return log_data
    
    def _format_timestamp(self, created: float) -> str | float:
        """Format timestamp according to configured format.
        
        Args:
            created: Timestamp from log record
            
        Returns:
            Formatted timestamp
        """
        if self.timestamp_format == TimestampFormat.ISO:
            return datetime.fromtimestamp(created).isoformat()
        elif self.timestamp_format == TimestampFormat.EPOCH:
            return created
        elif self.timestamp_format == TimestampFormat.HUMAN:
            return datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")
        else:
            raise ValueError(f"Unsupported timestamp format: {self.timestamp_format}")
    
    def _format_json(self, log_data: dict[str, Any]) -> str:
        """Format log data as JSON.
        
        Args:
            log_data: Dictionary containing log data
            
        Returns:
            JSON formatted string
        """
        try:
            return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
        except (TypeError, ValueError) as e:
            # Fallback for serialization errors
            sanitized_data = {
                "timestamp": log_data.get("timestamp", "unknown"),
                "level": log_data.get("level", "UNKNOWN"),
                "logger": log_data.get("logger", "unknown"),
                "message": str(log_data.get("message", "Failed to serialize log message")),
                "serialization_error": str(e),
            }
            return json.dumps(sanitized_data, ensure_ascii=False, separators=(',', ':'))
    
    def _format_keyvalue(self, log_data: dict[str, Any]) -> str:
        """Format log data as key-value pairs.
        
        Args:
            log_data: Dictionary containing log data
            
        Returns:
            Key-value formatted string
        """
        # Determine field order
        field_order = self.field_order if self.field_order else self.default_fields
        
        # Build key-value pairs
        pairs = []
        
        # Add ordered fields first
        for field in field_order:
            if field in log_data:
                pairs.append(self._format_keyvalue_pair(field, log_data[field]))
        
        # Add remaining fields
        for key, value in log_data.items():
            if key not in field_order:
                pairs.append(self._format_keyvalue_pair(key, value))
        
        return " ".join(pairs)
    
    def _format_keyvalue_pair(self, key: str, value: Any) -> str:
        """Format a single key-value pair.
        
        Args:
            key: The key name
            value: The value to format
            
        Returns:
            Formatted key-value pair
        """
        # Handle different value types
        if isinstance(value, str):
            # Escape quotes and backslashes
            escaped_value = value.replace('\\', '\\\\').replace('"', '\\"')
            return f'{key}="{escaped_value}"'
        elif isinstance(value, (int, float, bool)):
            return f'{key}={value}'
        elif value is None:
            return f'{key}=null'
        else:
            # Convert to string and escape
            str_value = str(value).replace('\\', '\\\\').replace('"', '\\"')
            return f'{key}="{str_value}"'
    
    def _serialize_value(self, value: Any, _seen: set[int] | None = None) -> Any:
        """Serialize a value for JSON output.
        
        Args:
            value: The value to serialize
            _seen: Set of object IDs to detect circular references
            
        Returns:
            JSON-serializable value
        """
        if _seen is None:
            _seen = set()
        
        # Handle basic types
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        
        # Check for circular references
        value_id = id(value)
        if value_id in _seen:
            return f"<circular-reference-{type(value).__name__}>"
        
        # Add to seen set for container types
        if isinstance(value, (list, tuple, dict)):
            _seen.add(value_id)
        
        try:
            # Handle containers
            if isinstance(value, (list, tuple)):
                result = [self._serialize_value(item, _seen) for item in value]
                _seen.discard(value_id)
                return result
            
            if isinstance(value, dict):
                result = {k: self._serialize_value(v, _seen) for k, v in value.items()}
                _seen.discard(value_id)
                return result
            
            # Handle datetime objects
            if isinstance(value, datetime):
                return value.isoformat()
            
            # Handle Path objects
            if isinstance(value, Path):
                return str(value)
            
            # For everything else, convert to string
            try:
                # Try to convert to string
                return str(value)
            except Exception:
                # Last resort - return type name
                return f"<{type(value).__name__}>"
        finally:
            # Ensure we clean up the seen set
            _seen.discard(value_id)