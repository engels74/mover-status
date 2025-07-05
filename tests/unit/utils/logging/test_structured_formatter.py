"""Test cases for structured logging formatter."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

from mover_status.utils.logging.structured_formatter import (
    StructuredFormatter,
    LogFormat,
    TimestampFormat,
)


class TestStructuredFormatter:
    """Test cases for StructuredFormatter."""

    def test_json_format_basic_record(self) -> None:
        """Test basic JSON formatting of log record."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        # Create a basic log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message %s",
            args=("arg1",),
            exc_info=None,
        )
        
        # Format the record
        formatted = formatter.format(record)
        
        # Parse as JSON to verify structure
        parsed = json.loads(formatted)
        
        # Verify required fields
        assert parsed["timestamp"]
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message arg1"
        assert parsed["module"] == "path"
        assert parsed["function"] == "<module>"
        assert parsed["line"] == 42

    def test_json_format_with_extra_fields(self) -> None:
        """Test JSON formatting with extra fields."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/test/module.py",
            lineno=100,
            msg="Error occurred",
            args=(),
            exc_info=None,
        )
        
        # Add extra fields
        record.correlation_id = "abc-123"  # type: ignore[attr-defined]
        record.user_id = 456  # type: ignore[attr-defined]
        record.metadata = {"key": "value"}  # type: ignore[attr-defined]
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify extra fields are included
        assert parsed["correlation_id"] == "abc-123"
        assert parsed["user_id"] == 456
        assert parsed["metadata"] == {"key": "value"}

    def test_keyvalue_format_basic_record(self) -> None:
        """Test key-value formatting of log record."""
        formatter = StructuredFormatter(format_type=LogFormat.KEYVALUE)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="/test/warning.py",
            lineno=25,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        # Verify key-value format
        assert 'level="WARNING"' in formatted
        assert 'logger="test.logger"' in formatted
        assert 'message="Warning message"' in formatted
        assert 'module="warning"' in formatted
        assert 'line=25' in formatted

    def test_keyvalue_format_with_extra_fields(self) -> None:
        """Test key-value formatting with extra fields."""
        formatter = StructuredFormatter(format_type=LogFormat.KEYVALUE)
        
        record = logging.LogRecord(
            name="app.service",
            level=logging.DEBUG,
            pathname="/app/service.py",
            lineno=15,
            msg="Debug info",
            args=(),
            exc_info=None,
        )
        
        record.request_id = "req-789"  # type: ignore[attr-defined]
        record.duration = 0.125  # type: ignore[attr-defined]
        
        formatted = formatter.format(record)
        
        assert 'request_id="req-789"' in formatted
        assert 'duration=0.125' in formatted

    def test_timestamp_format_iso(self) -> None:
        """Test ISO timestamp format."""
        formatter = StructuredFormatter(
            format_type=LogFormat.JSON,
            timestamp_format=TimestampFormat.ISO,
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        
        # Set a specific timestamp
        record.created = 1703509845.123456
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify ISO format (should convert from timestamp)
        assert "T" in parsed["timestamp"]  # Should contain ISO format separator
        assert isinstance(parsed["timestamp"], str)

    def test_timestamp_format_epoch(self) -> None:
        """Test epoch timestamp format."""
        formatter = StructuredFormatter(
            format_type=LogFormat.JSON,
            timestamp_format=TimestampFormat.EPOCH,
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        
        # Set a specific timestamp
        test_timestamp = 1703509845.123456
        record.created = test_timestamp
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify epoch format
        assert parsed["timestamp"] == test_timestamp

    def test_custom_field_order(self) -> None:
        """Test custom field ordering."""
        custom_fields = ["message", "level", "logger", "timestamp"]
        formatter = StructuredFormatter(
            format_type=LogFormat.JSON,
            field_order=custom_fields,
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        # For JSON, we can't directly test order, but we can test that
        # the custom fields are present
        parsed = json.loads(formatted)
        for field in custom_fields:
            assert field in parsed

    def test_field_exclusion(self) -> None:
        """Test field exclusion."""
        formatter = StructuredFormatter(
            format_type=LogFormat.JSON,
            exclude_fields=["module", "function", "line"],
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify excluded fields are not present
        assert "module" not in parsed
        assert "function" not in parsed
        assert "line" not in parsed
        
        # Verify required fields are still present
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "logger" in parsed
        assert "message" in parsed

    def test_nested_objects_serialization(self) -> None:
        """Test serialization of nested objects and arrays."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add complex nested data
        record.config = {  # type: ignore[attr-defined]
            "database": {
                "host": "localhost",
                "port": 5432,
                "ssl": True,
            },
            "features": ["auth", "cache", "metrics"],
        }
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify nested structure is preserved
        assert parsed["config"]["database"]["host"] == "localhost"
        assert parsed["config"]["database"]["port"] == 5432
        assert parsed["config"]["database"]["ssl"] is True
        assert parsed["config"]["features"] == ["auth", "cache", "metrics"]

    def test_exception_handling(self) -> None:
        """Test formatting with exception information."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="/test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify exception information is included
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "Test error" in parsed["exception"]

    def test_invalid_json_serialization(self) -> None:
        """Test handling of non-JSON serializable objects."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add non-serializable object
        record.non_serializable = Mock()  # type: ignore[attr-defined]
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Should convert to string representation
        assert "non_serializable" in parsed
        assert isinstance(parsed["non_serializable"], str)
        assert "Mock" in parsed["non_serializable"]

    def test_keyvalue_special_characters(self) -> None:
        """Test key-value formatting with special characters."""
        formatter = StructuredFormatter(format_type=LogFormat.KEYVALUE)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg='Message with "quotes" and \\ backslashes',
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        # Verify special characters are escaped
        assert 'message="Message with \\"quotes\\" and \\\\ backslashes"' in formatted

    def test_large_message_handling(self) -> None:
        """Test handling of large log messages."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        large_message = "x" * 10000
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg=large_message,
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify large message is handled correctly
        assert parsed["message"] == large_message
        assert len(parsed["message"]) == 10000

    def test_unicode_handling(self) -> None:
        """Test Unicode character handling."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        unicode_message = "Test with unicode: 测试 🎉 ñoño"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg=unicode_message,
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify Unicode is preserved
        assert parsed["message"] == unicode_message

    def test_unsupported_format_type(self) -> None:
        """Test error handling for unsupported format types."""
        from unittest.mock import patch
        
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Mock the format_type to be invalid
        with patch.object(formatter, 'format_type', 'invalid'):
            # Should raise ValueError for unsupported format
            try:
                formatter.format(record)
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "Unsupported format type" in str(e)

    def test_unsupported_timestamp_format(self) -> None:
        """Test error handling for unsupported timestamp formats."""
        from unittest.mock import patch
        
        formatter = StructuredFormatter(
            format_type=LogFormat.JSON,
            timestamp_format=TimestampFormat.ISO,
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Mock the timestamp_format to be invalid
        with patch.object(formatter, 'timestamp_format', 'invalid'):
            # Should raise ValueError for unsupported timestamp format
            try:
                formatter.format(record)
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "Unsupported timestamp format" in str(e)

    def test_timestamp_format_human(self) -> None:
        """Test human readable timestamp format."""
        formatter = StructuredFormatter(
            format_type=LogFormat.JSON,
            timestamp_format=TimestampFormat.HUMAN,
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        
        # Set a specific timestamp
        record.created = 1703509845.123456
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify human format
        assert isinstance(parsed["timestamp"], str)
        assert "-" in parsed["timestamp"]  # Should contain date separators
        assert ":" in parsed["timestamp"]  # Should contain time separators

    def test_serialization_fallback(self) -> None:
        """Test JSON serialization fallback for complex errors."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Create a circular reference
        circular_dict: dict[str, Any] = {"key": "value"}
        circular_dict["self"] = circular_dict  # Creates circular reference
        record.bad_field = circular_dict  # type: ignore[attr-defined]
        
        # Should handle the circular reference gracefully
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Should have circular reference marker
        assert "circular-reference" in str(parsed["bad_field"]["self"])
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"

    def test_path_serialization(self) -> None:
        """Test Path object serialization."""
        from pathlib import Path
        
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        record.path_field = Path("/home/user/file.txt")  # type: ignore[attr-defined]
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Path should be converted to string
        assert parsed["path_field"] == "/home/user/file.txt"

    def test_datetime_serialization(self) -> None:
        """Test datetime object serialization."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        test_datetime = datetime(2023, 12, 25, 12, 30, 45)
        record.datetime_field = test_datetime  # type: ignore[attr-defined]
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Datetime should be converted to ISO format
        assert parsed["datetime_field"] == "2023-12-25T12:30:45"

    def test_serialization_last_resort(self) -> None:
        """Test serialization last resort error handling."""
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Create an object that will fail both JSON and str conversion
        class BadObject:
            def __str__(self) -> str:
                raise Exception("Can't convert to string")
        
        record.bad_object = BadObject()  # type: ignore[attr-defined]
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        # Should fall back to type name
        assert parsed["bad_object"] == "<BadObject>"

    def test_json_fallback_error(self) -> None:
        """Test JSON fallback for unparseable data."""
        from unittest.mock import patch
        
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Mock json.dumps to raise an error on the first call but succeed on the second
        with patch("json.dumps") as mock_dumps:
            # First call raises error, second call succeeds with fallback data
            mock_dumps.side_effect = [
                ValueError("Mock JSON error"),
                '{"timestamp":"unknown","level":"INFO","logger":"test","message":"Test message","serialization_error":"Mock JSON error"}'
            ]
            
            formatted = formatter.format(record)
            parsed = json.loads(formatted)
            
            # Should have fallback data
            assert parsed["level"] == "INFO"
            assert parsed["message"] == "Test message"
            assert parsed["serialization_error"] == "Mock JSON error"

    def test_keyvalue_null_handling(self) -> None:
        """Test key-value formatting with None values."""
        formatter = StructuredFormatter(format_type=LogFormat.KEYVALUE)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add a None value
        record.null_field = None  # type: ignore[attr-defined]
        
        formatted = formatter.format(record)
        
        # Verify None is formatted as null
        assert 'null_field=null' in formatted

    def test_keyvalue_complex_object_formatting(self) -> None:
        """Test key-value formatting with complex objects."""
        formatter = StructuredFormatter(format_type=LogFormat.KEYVALUE)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add a complex object that will be converted to string
        class CustomObject:
            def __str__(self) -> str:
                return "custom_value_with_quotes_and\\backslashes"
        
        record.custom_object = CustomObject()  # type: ignore[attr-defined]
        
        formatted = formatter.format(record)
        
        # Verify complex object is properly escaped in key-value format
        assert 'custom_object="custom_value_with_quotes_and\\\\backslashes"' in formatted