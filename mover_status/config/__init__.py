"""
Configuration management for the Mover Status Monitor.

This package provides functionality for loading, validating, and saving
configuration data for the application.
"""

from mover_status.config.config_manager import ConfigManager
from mover_status.config.default_config import DEFAULT_CONFIG
from mover_status.config.validation_error import ValidationError

__all__ = ["ConfigManager", "DEFAULT_CONFIG", "ValidationError"]