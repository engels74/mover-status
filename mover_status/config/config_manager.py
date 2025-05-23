"""
Configuration manager for the Mover Status Monitor.

This module provides backward compatibility imports for the reorganized
configuration system. All classes and types have been moved to separate
modules for better organization and maintainability.

For new code, import from the specific modules:
- mover_status.config.manager for ConfigManager
- mover_status.config.models for MoverStatusConfig
- mover_status.config.types for type definitions

This module maintains backward compatibility for existing imports.
"""

# Import all reorganized components for backward compatibility
from mover_status.config.manager import ConfigManager
from mover_status.config.models import MoverStatusConfig
from mover_status.config.types import (
    TelegramConfig, DiscordConfig, ProvidersConfig,
    NotificationConfig, MonitoringConfig, MessagesConfig,
    PathsConfig, DebugConfig, ConfigSections
)

# Re-export everything for backward compatibility
__all__ = [
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
]