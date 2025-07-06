"""Log level management system with dynamic configuration support."""

from __future__ import annotations

import logging
from enum import Enum


class LogLevel(Enum):
    """Enumeration of supported log levels."""
    
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL
    
    @classmethod
    def from_string(cls, level_str: str) -> LogLevel:
        """Create LogLevel from string representation.
        
        Args:
            level_str: String representation of log level (case-insensitive)
            
        Returns:
            LogLevel enum value
            
        Raises:
            ValueError: If level_str is not a valid log level
        """
        level_str = level_str.upper()
        try:
            return cls[level_str]
        except KeyError:
            raise ValueError(f"Invalid log level: {level_str}")
    
    @classmethod
    def from_int(cls, level_int: int) -> LogLevel:
        """Create LogLevel from integer value.
        
        Args:
            level_int: Integer log level value
            
        Returns:
            LogLevel enum value
            
        Raises:
            ValueError: If level_int is not a valid log level
        """
        for level in cls:
            if level.value == level_int:
                return level
        raise ValueError(f"Invalid log level: {level_int}")


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass


class LogLevelManager:
    """Manages log levels for loggers with dynamic configuration support."""
    
    def __init__(self, default_level: LogLevel = LogLevel.INFO) -> None:
        """Initialize log level manager.
        
        Args:
            default_level: Default log level for unconfigured loggers
        """
        self.default_level: LogLevel = default_level
        self.logger_levels: dict[str, LogLevel] = {}
    
    def set_logger_level(self, logger_name: str, level: LogLevel) -> None:
        """Set log level for a specific logger.
        
        Args:
            logger_name: Name of the logger
            level: Log level to set
        """
        self.logger_levels[logger_name] = level
        # Actually apply the level to the Python logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(level.value)
        
        # Apply level to child loggers that don't have their own explicit level set
        # This ensures hierarchical level inheritance
        logger_manager = logging.getLogger().manager
        for existing_logger_name in logger_manager.loggerDict:
            # Check if this is a child logger
            if (existing_logger_name.startswith(logger_name + ".") and 
                existing_logger_name not in self.logger_levels):
                child_logger = logging.getLogger(existing_logger_name)
                child_logger.setLevel(level.value)
    
    def get_logger_level(self, logger_name: str) -> LogLevel:
        """Get log level for a specific logger.
        
        Args:
            logger_name: Name of the logger
            
        Returns:
            LogLevel for the logger, or default if not configured
        """
        # Check for exact match first
        if logger_name in self.logger_levels:
            return self.logger_levels[logger_name]
        
        # Check for parent logger configuration
        # Find the most specific parent configuration
        best_match = ""
        best_level = self.default_level
        
        for configured_logger, level in self.logger_levels.items():
            # Check if this is a parent of the target logger
            if logger_name.startswith(configured_logger + "."):
                # Use the most specific parent (longest name)
                if len(configured_logger) > len(best_match):
                    best_match = configured_logger
                    best_level = level
        
        return best_level
    
    def set_global_level(self, level: LogLevel) -> None:
        """Set global default log level.
        
        Args:
            level: Log level to set as default
        """
        self.default_level = level
    
    def reset_logger_level(self, logger_name: str) -> None:
        """Reset logger level to default.
        
        Args:
            logger_name: Name of the logger to reset
        """
        _ = self.logger_levels.pop(logger_name, None)
    
    def reset_all_levels(self) -> None:
        """Reset all logger levels to default."""
        self.logger_levels.clear()
    
    def apply_to_logger(self, logger: logging.Logger) -> None:
        """Apply configured level to a logger instance.
        
        Args:
            logger: Logger instance to configure
        """
        level = self.get_logger_level(logger.name)
        logger.setLevel(level.value)
    
    def configure_from_dict(self, config: dict[str, str | dict[str, str]]) -> None:
        """Configure log levels from dictionary.
        
        Args:
            config: Configuration dictionary with 'default' and 'loggers' keys
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Set default level
        if "default" in config:
            default_value = config["default"]
            if isinstance(default_value, str):
                try:
                    self.default_level = LogLevel.from_string(default_value)
                except ValueError as e:
                    raise ConfigurationError(f"Invalid default log level: {e}")
        
        # Set logger-specific levels
        if "loggers" in config:
            loggers_config = config["loggers"]
            if isinstance(loggers_config, dict):
                for logger_name, level_str in loggers_config.items():
                    try:
                        level = LogLevel.from_string(level_str)
                        self.set_logger_level(logger_name, level)
                    except ValueError as e:
                        raise ConfigurationError(f"Invalid log level for logger '{logger_name}': {e}")
    
    def get_configuration(self) -> dict[str, str | dict[str, str]]:
        """Get current configuration as dictionary.
        
        Returns:
            Dictionary with current configuration
        """
        return {
            "default": self.default_level.name,
            "loggers": {
                name: level.name for name, level in self.logger_levels.items()
            }
        }


# Global instance for convenience
_log_level_manager: LogLevelManager | None = None


def get_log_level_manager() -> LogLevelManager:
    """Get the global log level manager instance.
    
    Returns:
        Global LogLevelManager instance
    """
    global _log_level_manager
    if _log_level_manager is None:
        _log_level_manager = LogLevelManager()
    return _log_level_manager


def set_logger_level(logger_name: str, level: LogLevel) -> None:
    """Set log level for a specific logger.
    
    Args:
        logger_name: Name of the logger
        level: Log level to set
    """
    manager = get_log_level_manager()
    manager.set_logger_level(logger_name, level)


def get_logger_level(logger_name: str) -> LogLevel:
    """Get log level for a specific logger.
    
    Args:
        logger_name: Name of the logger
        
    Returns:
        LogLevel for the logger
    """
    manager = get_log_level_manager()
    return manager.get_logger_level(logger_name)


def set_global_level(level: LogLevel) -> None:
    """Set global default log level.
    
    Args:
        level: Log level to set as default
    """
    manager = get_log_level_manager()
    manager.set_global_level(level)


def get_global_level() -> LogLevel:
    """Get global default log level.
    
    Returns:
        Global default log level
    """
    manager = get_log_level_manager()
    return manager.default_level


def reset_all_levels() -> None:
    """Reset all logger levels to default."""
    manager = get_log_level_manager()
    manager.reset_all_levels()