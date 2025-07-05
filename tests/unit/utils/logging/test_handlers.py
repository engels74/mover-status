"""Test module for logging handlers."""

from __future__ import annotations

import logging
import logging.handlers
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from mover_status.utils.logging.handlers import (
    ConsoleHandler,
    FileHandler,
    SyslogHandler,
    configure_handler,
    create_rotating_file_handler,
)
from mover_status.utils.logging.structured_formatter import (
    LogFormat,
    StructuredFormatter,
    TimestampFormat,
)


class TestConsoleHandler:
    """Test suite for ConsoleHandler."""

    def test_console_handler_creation(self) -> None:
        """Test console handler creation with default settings."""
        handler = ConsoleHandler()
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream == sys.stdout
        assert handler.level == logging.INFO

    def test_console_handler_with_stderr(self) -> None:
        """Test console handler creation with stderr output."""
        handler = ConsoleHandler(use_stderr=True)
        assert handler.stream == sys.stderr

    def test_console_handler_with_custom_level(self) -> None:
        """Test console handler with custom log level."""
        handler = ConsoleHandler(level=logging.DEBUG)
        assert handler.level == logging.DEBUG

    def test_console_handler_with_color_support(self) -> None:
        """Test console handler with color support enabled."""
        handler = ConsoleHandler(enable_colors=True)
        # Check that a color formatter is applied
        assert handler.formatter is not None
        assert hasattr(handler.formatter, 'enable_colors')

    def test_console_handler_without_color_support(self) -> None:
        """Test console handler without color support."""
        handler = ConsoleHandler(enable_colors=False)
        # Should have a structured formatter without colors
        assert isinstance(handler.formatter, StructuredFormatter)

    def test_console_handler_with_custom_formatter(self) -> None:
        """Test console handler with custom formatter."""
        custom_formatter = StructuredFormatter(
            format_type=LogFormat.KEYVALUE,
            timestamp_format=TimestampFormat.HUMAN
        )
        handler = ConsoleHandler(formatter=custom_formatter)
        assert handler.formatter is custom_formatter


class TestFileHandler:
    """Test suite for FileHandler."""

    def test_file_handler_creation(self) -> None:
        """Test file handler creation with default settings."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            handler = FileHandler(tmp_path)
            assert isinstance(handler, logging.FileHandler)
            assert handler.baseFilename == str(tmp_path)
            assert handler.level == logging.INFO
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_file_handler_with_custom_level(self) -> None:
        """Test file handler with custom log level."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            handler = FileHandler(tmp_path, level=logging.DEBUG)
            assert handler.level == logging.DEBUG
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_file_handler_with_append_mode(self) -> None:
        """Test file handler with append mode."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            handler = FileHandler(tmp_path, mode='a')
            assert handler.mode == 'a'
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_file_handler_directory_creation(self) -> None:
        """Test file handler creates parent directories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "logs" / "app.log"
            handler = FileHandler(log_path)
            assert log_path.parent.exists()
            assert handler.baseFilename == str(log_path)

    def test_file_handler_with_custom_formatter(self) -> None:
        """Test file handler with custom formatter."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            custom_formatter = StructuredFormatter(format_type=LogFormat.JSON)
            handler = FileHandler(tmp_path, formatter=custom_formatter)
            assert handler.formatter is custom_formatter
        finally:
            tmp_path.unlink(missing_ok=True)


class TestSyslogHandler:
    """Test suite for SyslogHandler."""

    @patch('mover_status.utils.logging.handlers.logging.handlers.SysLogHandler')
    def test_syslog_handler_creation(self, mock_syslog: Mock) -> None:
        """Test syslog handler creation with default settings."""
        _ = SyslogHandler()
        mock_syslog.assert_called_once_with(
            address=('localhost', 514),
            facility=1  # LOG_USER value
        )

    @patch('mover_status.utils.logging.handlers.logging.handlers.SysLogHandler')
    def test_syslog_handler_with_custom_address(self, mock_syslog: Mock) -> None:
        """Test syslog handler with custom address."""
        _ = SyslogHandler(address=('custom.host', 1234))
        mock_syslog.assert_called_once_with(
            address=('custom.host', 1234),
            facility=1  # LOG_USER value
        )

    @patch('mover_status.utils.logging.handlers.logging.handlers.SysLogHandler')
    def test_syslog_handler_with_custom_facility(self, mock_syslog: Mock) -> None:
        """Test syslog handler with custom facility."""
        _ = SyslogHandler(facility=16)  # Use the actual value instead of the constant
        mock_syslog.assert_called_once_with(
            address=('localhost', 514),
            facility=16  # LOG_LOCAL0 value
        )

    @patch('mover_status.utils.logging.handlers.logging.handlers.SysLogHandler')
    def test_syslog_handler_with_unix_socket(self, mock_syslog: Mock) -> None:
        """Test syslog handler with Unix socket."""
        _ = SyslogHandler(address='/dev/log')
        mock_syslog.assert_called_once_with(
            address='/dev/log',
            facility=1  # LOG_USER value
        )


class TestCreateRotatingFileHandler:
    """Test suite for create_rotating_file_handler function."""

    def test_create_rotating_file_handler_by_size(self) -> None:
        """Test creating rotating file handler with size-based rotation."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            handler = create_rotating_file_handler(
                tmp_path,
                max_bytes=1024 * 1024,
                backup_count=5
            )
            assert isinstance(handler, logging.handlers.RotatingFileHandler)
            assert handler.maxBytes == 1024 * 1024
            assert handler.backupCount == 5
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_create_rotating_file_handler_by_time(self) -> None:
        """Test creating rotating file handler with time-based rotation."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            handler = create_rotating_file_handler(
                tmp_path,
                when='midnight',
                interval=1,
                backup_count=7
            )
            assert isinstance(handler, logging.handlers.TimedRotatingFileHandler)
            assert handler.when == 'MIDNIGHT'
            assert handler.interval == 86400  # midnight converts interval to seconds
            assert handler.backupCount == 7
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_create_rotating_file_handler_invalid_parameters(self) -> None:
        """Test creating rotating file handler with invalid parameters."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            with pytest.raises(ValueError, match="Cannot specify both size and time"):
                _ = create_rotating_file_handler(
                    tmp_path,
                    max_bytes=1024,
                    when='midnight'
                )
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_create_rotating_file_handler_no_rotation(self) -> None:
        """Test creating rotating file handler without rotation parameters."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            with pytest.raises(ValueError, match="Must specify either max_bytes for size-based rotation or when for time-based rotation"):
                _ = create_rotating_file_handler(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)


class TestConfigureHandler:
    """Test suite for configure_handler function."""

    def test_configure_handler_with_formatter(self) -> None:
        """Test configuring handler with custom formatter."""
        handler = logging.StreamHandler()
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        
        configured_handler = configure_handler(handler, formatter=formatter)
        assert configured_handler.formatter is formatter

    def test_configure_handler_with_level(self) -> None:
        """Test configuring handler with custom level."""
        handler = logging.StreamHandler()
        
        configured_handler = configure_handler(handler, level=logging.DEBUG)
        assert configured_handler.level == logging.DEBUG

    def test_configure_handler_with_filter(self) -> None:
        """Test configuring handler with custom filter."""
        handler = logging.StreamHandler()
        
        def custom_filter(record: logging.LogRecord) -> bool:
            return record.levelno >= logging.WARNING
        
        configured_handler = configure_handler(handler, filter_func=custom_filter)
        info_record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test', args=(), exc_info=None
        )
        warning_record = logging.LogRecord(
            name='test', level=logging.WARNING, pathname='', lineno=0,
            msg='test', args=(), exc_info=None
        )
        assert configured_handler.filter(info_record) == 0  # Filter returns 0 for rejected records
        assert configured_handler.filter(warning_record) != 0  # Filter returns non-zero for accepted records

    def test_configure_handler_with_all_options(self) -> None:
        """Test configuring handler with all options."""
        handler = logging.StreamHandler()
        formatter = StructuredFormatter(format_type=LogFormat.KEYVALUE)
        
        def custom_filter(_: logging.LogRecord) -> bool:
            return True
        
        configured_handler = configure_handler(
            handler,
            formatter=formatter,
            level=logging.DEBUG,
            filter_func=custom_filter
        )
        
        assert configured_handler.formatter is formatter
        assert configured_handler.level == logging.DEBUG
        test_record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test', args=(), exc_info=None
        )
        assert configured_handler.filter(test_record) != 0  # Filter returns non-zero for accepted records