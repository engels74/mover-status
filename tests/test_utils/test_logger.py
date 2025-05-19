"""Tests for the logger module."""

import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path
from collections.abc import Generator
from unittest.mock import patch
from typing import cast, TypedDict, Literal

from tests.test_utils.mock_types import CallArgs


class HandlerKwargs(TypedDict, total=False):
    """Type definition for handler keyword arguments."""
    mode: Literal['a', 'w']
    maxBytes: int
    backupCount: int
    # Add any other possible keyword arguments here

import pytest

from mover_status.utils.logger import (
    setup_logger,
    get_logger,
    LogLevel,
    LogFormat,
    LoggerConfig,
    configure_from_dict,
)


@pytest.fixture
def temp_log_file() -> Generator[Path, None, None]:
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as temp_file:
        temp_path = Path(temp_file.name)

    yield temp_path

    # Clean up after test
    if temp_path.exists():
        os.unlink(temp_path)


class TestLogger:
    """Test cases for the logger module."""

    def test_get_logger_returns_same_instance(self) -> None:
        """Test that get_logger returns the same logger instance for the same name."""
        logger1 = get_logger("test_logger")
        logger2 = get_logger("test_logger")

        assert logger1 is logger2
        assert logger1.name == "test_logger"

    def test_get_logger_returns_different_instances_for_different_names(self) -> None:
        """Test that get_logger returns different logger instances for different names."""
        logger1 = get_logger("test_logger1")
        logger2 = get_logger("test_logger2")

        assert logger1 is not logger2
        assert logger1.name == "test_logger1"
        assert logger2.name == "test_logger2"

    def test_setup_logger_with_console_handler(self) -> None:
        """Test setting up a logger with a console handler."""
        logger_name = "test_console_logger"
        config = LoggerConfig(
            console_enabled=True,
            file_enabled=False,
            level=LogLevel.INFO,
            format=LogFormat.SIMPLE,
        )

        with patch("logging.StreamHandler") as mock_handler:
            logger = setup_logger(logger_name, config)

            assert logger.name == logger_name
            assert logger.level == logging.INFO
            mock_handler.assert_called_once()
            assert len(logger.handlers) == 1

    def test_setup_logger_with_file_handler(self, temp_log_file: Path) -> None:
        """Test setting up a logger with a file handler."""
        logger_name = "test_file_logger"
        config = LoggerConfig(
            console_enabled=False,
            file_enabled=True,
            file_path=str(temp_log_file),
            level=LogLevel.DEBUG,
            format=LogFormat.DETAILED,
        )

        logger = setup_logger(logger_name, config)

        assert logger.name == logger_name
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.FileHandler)
        assert logger.handlers[0].baseFilename == str(temp_log_file)

    def test_setup_logger_with_both_handlers(self, temp_log_file: Path) -> None:
        """Test setting up a logger with both console and file handlers."""
        logger_name = "test_both_handlers"
        config = LoggerConfig(
            console_enabled=True,
            file_enabled=True,
            file_path=str(temp_log_file),
            level=LogLevel.WARNING,
            format=LogFormat.DETAILED,
        )

        logger = setup_logger(logger_name, config)

        assert logger.name == logger_name
        assert logger.level == logging.WARNING
        assert len(logger.handlers) == 2

        # Check that we have one of each handler type
        handler_types = [type(h) for h in logger.handlers]
        assert logging.StreamHandler in handler_types
        # Check for either FileHandler or RotatingFileHandler
        assert any(issubclass(t, logging.FileHandler) for t in handler_types)

    def test_logger_respects_log_level(self, temp_log_file: Path) -> None:
        """Test that the logger respects the configured log level."""
        logger_name = "test_log_level"
        config = LoggerConfig(
            console_enabled=False,
            file_enabled=True,
            file_path=str(temp_log_file),
            level=LogLevel.WARNING,
            format=LogFormat.SIMPLE,
        )

        logger = setup_logger(logger_name, config)

        # These should not be logged
        logger.debug("Debug message")
        logger.info("Info message")

        # These should be logged
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        with open(temp_log_file, "r") as f:
            log_content = f.read()

        assert "Debug message" not in log_content
        assert "Info message" not in log_content
        assert "Warning message" in log_content
        assert "Error message" in log_content
        assert "Critical message" in log_content

    def test_logger_formats_messages_correctly(self, temp_log_file: Path) -> None:
        """Test that the logger formats messages according to the configured format."""
        logger_name = "test_formatting"

        # Test simple format
        simple_config = LoggerConfig(
            console_enabled=False,
            file_enabled=True,
            file_path=str(temp_log_file),
            level=LogLevel.INFO,
            format=LogFormat.SIMPLE,
        )

        logger = setup_logger(logger_name, simple_config)
        logger.info("Simple format test")

        with open(temp_log_file, "r") as f:
            simple_content = f.read()

        # Simple format should just have timestamp and message
        assert "Simple format test" in simple_content
        assert " - " in simple_content  # Timestamp separator

        # Clear the file
        with open(temp_log_file, "w") as f:
            _ = f.write("")

        # Test detailed format
        detailed_config = LoggerConfig(
            console_enabled=False,
            file_enabled=True,
            file_path=str(temp_log_file),
            level=LogLevel.INFO,
            format=LogFormat.DETAILED,
        )

        logger = setup_logger(logger_name, detailed_config)
        logger.info("Detailed format test")

        with open(temp_log_file, "r") as f:
            detailed_content = f.read()

        # Detailed format should have level name and logger name
        assert "Detailed format test" in detailed_content
        assert "INFO" in detailed_content
        assert logger_name in detailed_content

    def test_custom_format(self, temp_log_file: Path) -> None:
        """Test using a custom log format."""
        logger_name = "test_custom_format"
        custom_format = "%(asctime)s [CUSTOM] %(message)s"

        config = LoggerConfig(
            console_enabled=False,
            file_enabled=True,
            file_path=str(temp_log_file),
            level=LogLevel.INFO,
            format=custom_format,
        )

        logger = setup_logger(logger_name, config)
        logger.info("Custom format test")

        with open(temp_log_file, "r") as f:
            content = f.read()

        assert "Custom format test" in content
        assert "[CUSTOM]" in content

    def test_log_directory_creation(self) -> None:
        """Test that the logger creates the log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a path to a log file in a non-existent subdirectory
            log_dir = os.path.join(temp_dir, "logs")
            log_file = os.path.join(log_dir, "test.log")

            # Verify the directory doesn't exist yet
            assert not os.path.exists(log_dir)

            # Configure logger with the non-existent directory
            config = LoggerConfig(
                console_enabled=False,
                file_enabled=True,
                file_path=log_file,
                level=LogLevel.INFO,
            )

            # This should create the directory
            logger = setup_logger("test_dir_creation", config)
            logger.info("Test message")

            # Verify the directory was created
            assert os.path.exists(log_dir)
            assert os.path.isfile(log_file)

            # Verify the log message was written
            with open(log_file, "r") as f:
                content = f.read()
                assert "Test message" in content

    def test_rotating_file_handler(self) -> None:
        """Test that the logger uses RotatingFileHandler when configured."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "rotating.log")

            # Configure logger with rotation settings
            config = LoggerConfig(
                console_enabled=False,
                file_enabled=True,
                file_path=log_file,
                level=LogLevel.INFO,
                max_file_size=100,  # Small size to trigger rotation
                backup_count=2,
            )

            # Set up the logger
            logger = setup_logger("test_rotation", config)

            # Verify we're using a RotatingFileHandler
            assert len(logger.handlers) == 1
            assert isinstance(logger.handlers[0], RotatingFileHandler)

            # Verify the rotation settings
            handler = logger.handlers[0]  # We've already verified it's a RotatingFileHandler
            assert isinstance(handler, RotatingFileHandler)
            assert handler.maxBytes == 100
            assert handler.backupCount == 2

            # Write enough data to trigger rotation
            for _ in range(10):
                logger.info("X" * 20)  # Each log entry should be > 20 bytes with timestamp

            # Check that the main log file exists
            assert os.path.exists(log_file)

            # Check that at least one backup file was created
            backup_file = f"{log_file}.1"
            assert os.path.exists(backup_file)

    def test_standard_file_handler(self) -> None:
        """Test that the logger uses standard FileHandler when rotation is disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "standard.log")

            # Configure logger with rotation disabled
            config = LoggerConfig(
                console_enabled=False,
                file_enabled=True,
                file_path=log_file,
                level=LogLevel.INFO,
                max_file_size=0,  # Disable rotation
                backup_count=0,
            )

            # Set up the logger
            logger = setup_logger("test_standard", config)

            # Verify we're using a standard FileHandler
            assert len(logger.handlers) == 1
            assert isinstance(logger.handlers[0], logging.FileHandler)
            assert not isinstance(logger.handlers[0], RotatingFileHandler)

    def test_file_handler_modes(self) -> None:
        """Test that the FileHandler respects the mode parameter."""
        # This test directly verifies that the mode parameter is passed correctly
        # to the FileHandler constructor

        # Mock os.makedirs to prevent directory creation attempts
        with patch('os.makedirs'):
            # Test append mode ('a')
            with patch('logging.FileHandler') as mock_file_handler:
                config = LoggerConfig(
                    console_enabled=False,
                    file_enabled=True,
                    file_path="test_path.log",  # Use a simple path
                    file_append=True,
                    max_file_size=0,  # Disable rotation to use FileHandler
                    backup_count=0,
                )

                _ = setup_logger("test_append_mode", config)

                # Verify FileHandler was called with mode='a'
                mock_file_handler.assert_called_once()
                call_args = cast(CallArgs, mock_file_handler.call_args)
                _, kwargs = call_args
                # Use direct dictionary access instead of casting
                assert kwargs.get('mode') == 'a'

            # Test write/overwrite mode ('w')
            with patch('logging.FileHandler') as mock_file_handler:
                config = LoggerConfig(
                    console_enabled=False,
                    file_enabled=True,
                    file_path="test_path.log",  # Use a simple path
                    file_append=False,
                    max_file_size=0,  # Disable rotation to use FileHandler
                    backup_count=0,
                )

                _ = setup_logger("test_write_mode", config)

                # Verify FileHandler was called with mode='w'
                mock_file_handler.assert_called_once()
                call_args = cast(CallArgs, mock_file_handler.call_args)
                _, kwargs = call_args
                # Use direct dictionary access instead of casting
                assert kwargs.get('mode') == 'w'

    def test_rotating_file_handler_modes(self) -> None:
        """Test that the RotatingFileHandler respects the mode parameter."""
        # This test directly verifies that the mode parameter is passed correctly
        # to the RotatingFileHandler constructor

        # Mock os.makedirs to prevent directory creation attempts
        with patch('os.makedirs'):
            # Test append mode ('a')
            with patch('logging.handlers.RotatingFileHandler') as mock_handler:
                config = LoggerConfig(
                    console_enabled=False,
                    file_enabled=True,
                    file_path="test_path.log",  # Use a simple path
                    file_append=True,
                    max_file_size=1024,  # Enable rotation
                    backup_count=3,
                )

                _ = setup_logger("test_append_mode_rotating", config)

                # Verify RotatingFileHandler was called with mode='a'
                mock_handler.assert_called_once()
                call_args = cast(CallArgs, mock_handler.call_args)
                _, kwargs = call_args
                # Use direct dictionary access instead of casting
                assert kwargs.get('mode') == 'a'

            # Test write/overwrite mode ('w')
            with patch('logging.handlers.RotatingFileHandler') as mock_handler:
                config = LoggerConfig(
                    console_enabled=False,
                    file_enabled=True,
                    file_path="test_path.log",  # Use a simple path
                    file_append=False,
                    max_file_size=1024,  # Enable rotation
                    backup_count=3,
                )

                _ = setup_logger("test_write_mode_rotating", config)

                # Verify RotatingFileHandler was called with mode='w'
                mock_handler.assert_called_once()
                call_args = cast(CallArgs, mock_handler.call_args)
                _, kwargs = call_args
                # Use direct dictionary access instead of casting
                assert kwargs.get('mode') == 'w'

    def test_configure_from_dict(self, temp_log_file: Path) -> None:
        """Test configuring a logger from a dictionary."""
        logger_name = "test_dict_config"

        # Create a configuration dictionary
        config_dict: dict[str, object] = {
            "console_enabled": False,
            "file_enabled": True,
            "file_path": str(temp_log_file),
            "level": "DEBUG",
            "format": "DETAILED",
            "file_append": True,
            "max_file_size": 1024,
            "backup_count": 2
        }

        # Configure the logger from the dictionary
        logger = configure_from_dict(logger_name, config_dict)

        # Verify the logger was configured correctly
        assert logger.name == logger_name
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], RotatingFileHandler)

        # Test logging
        logger.debug("Debug from dict config")

        with open(temp_log_file, "r") as f:
            content = f.read()
            assert "Debug from dict config" in content
            assert logger_name in content  # DETAILED format includes logger name

    def test_configure_from_dict_with_custom_format(self, temp_log_file: Path) -> None:
        """Test configuring a logger with a custom format string from a dictionary."""
        logger_name = "test_dict_custom"

        # Create a configuration dictionary with custom format
        config_dict: dict[str, object] = {
            "console_enabled": False,
            "file_enabled": True,
            "file_path": str(temp_log_file),
            "level": "INFO",
            "format": "%(asctime)s [DICT-CUSTOM] %(message)s",
        }

        # Configure the logger from the dictionary
        logger = configure_from_dict(logger_name, config_dict)

        # Test logging
        logger.info("Custom format from dict")

        with open(temp_log_file, "r") as f:
            content = f.read()
            assert "Custom format from dict" in content
            assert "[DICT-CUSTOM]" in content

    def test_configure_from_dict_invalid_level(self) -> None:
        """Test that configure_from_dict raises an error for invalid log levels."""
        config_dict: dict[str, object] = {
            "level": "INVALID_LEVEL",
        }

        with pytest.raises(ValueError, match="Invalid log level"):
            _ = configure_from_dict("test_invalid", config_dict)

    def test_file_logging_without_path(self) -> None:
        """Test that setup_logger raises an error when file logging is enabled without a path."""
        config = LoggerConfig(
            console_enabled=False,
            file_enabled=True,
            file_path=None,  # No path provided
        )

        with pytest.raises(ValueError, match="File logging enabled but no file path provided"):
            _ = setup_logger("test_no_path", config)
