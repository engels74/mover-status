"""Configuration management system for the mover status monitor."""

from __future__ import annotations

# Import exceptions to make them available to users
from .exceptions import (
    ConfigError,
    ConfigLoadError,
    ConfigMergeError,
    ConfigValidationError,
    EnvLoadError,
    get_error_context,
    handle_config_error,
    log_config_error,
    suggest_config_fix,
)

__all__ = [
    # Exception classes
    "ConfigError",
    "ConfigLoadError",
    "ConfigMergeError", 
    "ConfigValidationError",
    "EnvLoadError",
    # Utility functions
    "get_error_context",
    "handle_config_error",
    "log_config_error",
    "suggest_config_fix",
    # TODO: Add configuration classes when implemented
    # "ConfigManager",
    # "ConfigLoader",
    # "ConfigModels",
    # "ConfigValidator",
]