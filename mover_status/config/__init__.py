"""
Configuration management for the Mover Status Monitor.

This package provides functionality for loading, validating, and saving
configuration data for the application.
"""

# Import from reorganized modules
from mover_status.config.manager import ConfigManager
from mover_status.config.models import MoverStatusConfig
from mover_status.config.types import (
    TelegramConfig, DiscordConfig, ProvidersConfig,
    NotificationConfig, MonitoringConfig, MessagesConfig,
    PathsConfig, DebugConfig, ConfigSections
)

# Import existing modules
from mover_status.config.default_config import DEFAULT_CONFIG
from mover_status.config.validation_error import ValidationError
from mover_status.config.loader import ConfigLoader, LoaderError
from mover_status.config.validator import ConfigValidator
from mover_status.config.registry import ConfigRegistry, RegistryError
from mover_status.config.schema import (
    ConfigSchema,
    SchemaField,
    SchemaValidationError,
    FieldType,
)

# Note: Backward compatibility is handled by the config_manager module itself,
# which re-exports all reorganized components. No additional imports needed here.

__all__ = [
    # Reorganized modules
    "ConfigManager",
    "MoverStatusConfig",
    "TelegramConfig",
    "DiscordConfig",
    "ProvidersConfig",
    "NotificationConfig",
    "MonitoringConfig",
    "MessagesConfig",
    "PathsConfig",
    "DebugConfig",
    "ConfigSections",
    # Existing modules
    "DEFAULT_CONFIG",
    "ValidationError",
    "ConfigLoader",
    "LoaderError",
    "ConfigValidator",
    "ConfigRegistry",
    "RegistryError",
    "ConfigSchema",
    "SchemaField",
    "SchemaValidationError",
    "FieldType",
]