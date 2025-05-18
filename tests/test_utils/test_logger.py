"""Tests for the logger module."""

import logging
import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from mover_status.utils.logger import (
    setup_logger,
    get_logger,
    LogLevel,
    LogFormat,
    LoggerConfig,
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
            f.write("")

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
