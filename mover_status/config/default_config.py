"""
Core default configuration values for the Mover Status Monitor.

This module defines the core default configuration dictionary that will be used
if no user configuration is provided or as a fallback for missing values.

Provider-specific configuration defaults are defined in their respective modules
and will be aggregated by the ConfigManager.
"""

from typing import TypedDict


# Define type structures for the core configuration (non-provider specific)
class NotificationConfig(TypedDict):
    """Notification settings configuration."""
    notification_increment: int
    enabled_providers: list[str]


class MonitoringConfig(TypedDict):
    """Monitoring settings configuration."""
    mover_executable: str
    cache_directory: str
    poll_interval: int


class MessagesConfig(TypedDict):
    """Message templates configuration."""
    completion: str


class PathsConfig(TypedDict):
    """Path settings configuration."""
    exclude: list[str]


class DebugConfig(TypedDict):
    """Debug settings configuration."""
    dry_run: bool
    enable_debug: bool


# Define a type for the complete configuration structure
class DefaultConfigType(TypedDict):
    """Complete configuration structure with all sections."""
    notification: NotificationConfig
    monitoring: MonitoringConfig
    messages: MessagesConfig
    paths: PathsConfig
    debug: DebugConfig


# Core default configuration dictionary (non-provider specific)
DEFAULT_CONFIG: DefaultConfigType = {
    # Notification settings (shared across providers)
    "notification": {
        # Notification frequency (percentage increments)
        "notification_increment": 25,

        # List of enabled providers
        "enabled_providers": [],
    },

    # Monitoring settings
    "monitoring": {
        # Path to the mover executable
        "mover_executable": "/usr/local/sbin/mover",

        # Path to the cache directory to monitor
        "cache_directory": "/mnt/cache",

        # Polling interval in seconds
        "poll_interval": 1,
    },

    # Message templates (shared/fallback)
    "messages": {
        # Completion message (used for all platforms)
        "completion": "Moving has been completed!",
    },

    # Path settings
    "paths": {
        # List of paths to exclude from monitoring
        "exclude": [],
    },

    # Debug settings
    "debug": {
        # Enable dry run mode (test notifications without monitoring)
        "dry_run": False,

        # Enable debug logging
        "enable_debug": False,
    },
}
