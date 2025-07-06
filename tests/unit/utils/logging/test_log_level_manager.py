"""Test cases for log level management system."""

from __future__ import annotations

import logging
import pytest
from unittest.mock import Mock, patch

from mover_status.utils.logging.log_level_manager import (
    LogLevelManager,
    LogLevel,
    ConfigurationError,
    get_log_level_manager,
    set_logger_level,
    get_logger_level,
    set_global_level,
    get_global_level,
    reset_all_levels,
)


class TestLogLevel:
    """Test LogLevel enum functionality."""
    
    def test_log_level_enum_values(self) -> None:
        """Test LogLevel enum has correct values."""
        assert LogLevel.DEBUG.value == logging.DEBUG
        assert LogLevel.INFO.value == logging.INFO
        assert LogLevel.WARNING.value == logging.WARNING
        assert LogLevel.ERROR.value == logging.ERROR
        assert LogLevel.CRITICAL.value == logging.CRITICAL
    
    def test_log_level_from_string(self) -> None:
        """Test LogLevel.from_string method."""
        assert LogLevel.from_string("DEBUG") == LogLevel.DEBUG
        assert LogLevel.from_string("info") == LogLevel.INFO
        assert LogLevel.from_string("Warning") == LogLevel.WARNING
        assert LogLevel.from_string("ERROR") == LogLevel.ERROR
        assert LogLevel.from_string("critical") == LogLevel.CRITICAL
    
    def test_log_level_from_string_invalid(self) -> None:
        """Test LogLevel.from_string with invalid values."""
        with pytest.raises(ValueError, match="Invalid log level: INVALID"):
            _ = LogLevel.from_string("INVALID")
    
    def test_log_level_from_int(self) -> None:
        """Test LogLevel.from_int method."""
        assert LogLevel.from_int(logging.DEBUG) == LogLevel.DEBUG
        assert LogLevel.from_int(logging.INFO) == LogLevel.INFO
        assert LogLevel.from_int(logging.WARNING) == LogLevel.WARNING
        assert LogLevel.from_int(logging.ERROR) == LogLevel.ERROR
        assert LogLevel.from_int(logging.CRITICAL) == LogLevel.CRITICAL
    
    def test_log_level_from_int_invalid(self) -> None:
        """Test LogLevel.from_int with invalid values."""
        with pytest.raises(ValueError, match="Invalid log level: 999"):
            _ = LogLevel.from_int(999)


class TestLogLevelManager:
    """Test LogLevelManager class functionality."""
    
    def test_initialization(self) -> None:
        """Test LogLevelManager initialization."""
        manager = LogLevelManager()
        assert manager.default_level == LogLevel.INFO
        assert len(manager.logger_levels) == 0
    
    def test_initialization_with_custom_default(self) -> None:
        """Test LogLevelManager initialization with custom default level."""
        manager = LogLevelManager(default_level=LogLevel.DEBUG)
        assert manager.default_level == LogLevel.DEBUG
    
    def test_set_logger_level(self) -> None:
        """Test setting logger level."""
        manager = LogLevelManager()
        manager.set_logger_level("test.logger", LogLevel.DEBUG)
        assert manager.logger_levels["test.logger"] == LogLevel.DEBUG
    
    def test_get_logger_level_configured(self) -> None:
        """Test getting configured logger level."""
        manager = LogLevelManager()
        manager.set_logger_level("test.logger", LogLevel.DEBUG)
        assert manager.get_logger_level("test.logger") == LogLevel.DEBUG
    
    def test_get_logger_level_unconfigured(self) -> None:
        """Test getting unconfigured logger level returns default."""
        manager = LogLevelManager()
        assert manager.get_logger_level("test.logger") == LogLevel.INFO
    
    def test_get_logger_level_parent_configured(self) -> None:
        """Test getting logger level with parent configuration."""
        manager = LogLevelManager()
        manager.set_logger_level("test", LogLevel.DEBUG)
        # Child logger should inherit parent level
        assert manager.get_logger_level("test.child") == LogLevel.DEBUG
    
    def test_get_logger_level_most_specific_parent(self) -> None:
        """Test getting logger level with most specific parent."""
        manager = LogLevelManager()
        manager.set_logger_level("test", LogLevel.DEBUG)
        manager.set_logger_level("test.module", LogLevel.WARNING)
        # Should use most specific parent
        assert manager.get_logger_level("test.module.child") == LogLevel.WARNING
    
    def test_set_global_level(self) -> None:
        """Test setting global level."""
        manager = LogLevelManager()
        manager.set_global_level(LogLevel.ERROR)
        assert manager.default_level == LogLevel.ERROR
    
    def test_reset_logger_level(self) -> None:
        """Test resetting logger level."""
        manager = LogLevelManager()
        manager.set_logger_level("test.logger", LogLevel.DEBUG)
        manager.reset_logger_level("test.logger")
        assert "test.logger" not in manager.logger_levels
    
    def test_reset_all_levels(self) -> None:
        """Test resetting all logger levels."""
        manager = LogLevelManager()
        manager.set_logger_level("test.logger1", LogLevel.DEBUG)
        manager.set_logger_level("test.logger2", LogLevel.WARNING)
        manager.reset_all_levels()
        assert len(manager.logger_levels) == 0
    
    def test_apply_to_logger(self) -> None:
        """Test applying level to actual logger."""
        manager = LogLevelManager()
        logger = logging.getLogger("test.apply")
        manager.set_logger_level("test.apply", LogLevel.DEBUG)
        manager.apply_to_logger(logger)
        assert logger.level == logging.DEBUG
    
    def test_apply_to_logger_unconfigured(self) -> None:
        """Test applying level to unconfigured logger uses default."""
        manager = LogLevelManager()
        logger = logging.getLogger("test.unconfigured")
        manager.apply_to_logger(logger)
        assert logger.level == logging.INFO
    
    def test_configure_from_dict(self) -> None:
        """Test configuring from dictionary."""
        manager = LogLevelManager()
        config = {
            "default": "DEBUG",
            "loggers": {
                "test.logger1": "WARNING",
                "test.logger2": "ERROR"
            }
        }
        manager.configure_from_dict(config)
        assert manager.default_level == LogLevel.DEBUG
        assert manager.logger_levels["test.logger1"] == LogLevel.WARNING
        assert manager.logger_levels["test.logger2"] == LogLevel.ERROR
    
    def test_configure_from_dict_no_loggers(self) -> None:
        """Test configuring from dictionary without loggers section."""
        manager = LogLevelManager()
        config: dict[str, str | dict[str, str]] = {"default": "WARNING"}
        manager.configure_from_dict(config)
        assert manager.default_level == LogLevel.WARNING
        assert len(manager.logger_levels) == 0
    
    def test_configure_from_dict_invalid_default(self) -> None:
        """Test configuring from dictionary with invalid default level."""
        manager = LogLevelManager()
        config: dict[str, str | dict[str, str]] = {"default": "INVALID"}
        with pytest.raises(ConfigurationError, match="Invalid default log level"):
            manager.configure_from_dict(config)
    
    def test_configure_from_dict_invalid_logger_level(self) -> None:
        """Test configuring from dictionary with invalid logger level."""
        manager = LogLevelManager()
        config = {
            "default": "INFO",
            "loggers": {"test.logger": "INVALID"}
        }
        with pytest.raises(ConfigurationError, match="Invalid log level for logger"):
            manager.configure_from_dict(config)
    
    def test_get_configuration(self) -> None:
        """Test getting current configuration."""
        manager = LogLevelManager()
        manager.set_global_level(LogLevel.WARNING)
        manager.set_logger_level("test.logger1", LogLevel.DEBUG)
        manager.set_logger_level("test.logger2", LogLevel.ERROR)
        
        config = manager.get_configuration()
        assert config["default"] == "WARNING"
        loggers = config["loggers"]
        assert isinstance(loggers, dict)
        assert loggers["test.logger1"] == "DEBUG"
        assert loggers["test.logger2"] == "ERROR"


class TestGlobalFunctions:
    """Test module-level convenience functions."""
    
    def test_get_log_level_manager_singleton(self) -> None:
        """Test get_log_level_manager returns singleton."""
        manager1 = get_log_level_manager()
        manager2 = get_log_level_manager()
        assert manager1 is manager2
    
    def test_set_logger_level_function(self) -> None:
        """Test set_logger_level convenience function."""
        set_logger_level("test.function", LogLevel.DEBUG)
        manager = get_log_level_manager()
        assert manager.get_logger_level("test.function") == LogLevel.DEBUG
    
    def test_get_logger_level_function(self) -> None:
        """Test get_logger_level convenience function."""
        set_logger_level("test.get", LogLevel.WARNING)
        level = get_logger_level("test.get")
        assert level == LogLevel.WARNING
    
    def test_set_global_level_function(self) -> None:
        """Test set_global_level convenience function."""
        set_global_level(LogLevel.ERROR)
        manager = get_log_level_manager()
        assert manager.default_level == LogLevel.ERROR
    
    def test_get_global_level_function(self) -> None:
        """Test get_global_level convenience function."""
        set_global_level(LogLevel.CRITICAL)
        level = get_global_level()
        assert level == LogLevel.CRITICAL
    
    def test_reset_all_levels_function(self) -> None:
        """Test reset_all_levels convenience function."""
        set_logger_level("test.reset", LogLevel.DEBUG)
        reset_all_levels()
        manager = get_log_level_manager()
        assert len(manager.logger_levels) == 0


class TestIntegration:
    """Test integration with Python logging system."""
    
    def test_runtime_level_changes(self) -> None:
        """Test runtime level changes are applied to loggers."""
        manager = LogLevelManager()
        logger = logging.getLogger("test.runtime")
        
        # Initial setup
        manager.set_logger_level("test.runtime", LogLevel.INFO)
        manager.apply_to_logger(logger)
        assert logger.level == logging.INFO
        
        # Runtime change
        manager.set_logger_level("test.runtime", LogLevel.DEBUG)
        manager.apply_to_logger(logger)
        assert logger.level == logging.DEBUG
    
    def test_handler_level_filtering(self) -> None:
        """Test that handler levels work with logger levels."""
        manager = LogLevelManager()
        logger = logging.getLogger("test.handler")
        handler = logging.StreamHandler()
        
        # Set logger to DEBUG but handler to WARNING
        manager.set_logger_level("test.handler", LogLevel.DEBUG)
        manager.apply_to_logger(logger)
        handler.setLevel(logging.WARNING)
        logger.addHandler(handler)
        
        # Logger should be DEBUG, handler should be WARNING
        assert logger.level == logging.DEBUG
        assert handler.level == logging.WARNING
    
    def test_per_module_configuration(self) -> None:
        """Test per-module logger configuration."""
        manager = LogLevelManager()
        
        # Configure different modules
        manager.set_logger_level("module1", LogLevel.DEBUG)
        manager.set_logger_level("module2", LogLevel.ERROR)
        
        # Create loggers for each module
        logger1 = logging.getLogger("module1.component")
        logger2 = logging.getLogger("module2.component")
        
        # Apply configuration
        manager.apply_to_logger(logger1)
        manager.apply_to_logger(logger2)
        
        # Verify levels
        assert logger1.level == logging.DEBUG
        assert logger2.level == logging.ERROR
    
    @patch('logging.getLogger')
    def test_auto_configuration_on_logger_creation(self, mock_get_logger: Mock) -> None:
        """Test automatic configuration when loggers are created."""
        mock_logger = Mock(spec=['setLevel', 'name'])
        mock_manager = Mock()
        mock_manager.loggerDict = {}
        mock_logger.manager = mock_manager
        mock_get_logger.return_value = mock_logger
        
        manager = LogLevelManager()
        manager.set_logger_level("auto.test", LogLevel.WARNING)
        
        # Simulate logger creation and auto-configuration
        logger = logging.getLogger("auto.test")
        manager.apply_to_logger(logger)
        
        # Verify configuration was applied
        mock_get_logger.assert_any_call("auto.test")
        mock_logger.setLevel.assert_called_with(logging.WARNING)  # pyright: ignore[reportAny]