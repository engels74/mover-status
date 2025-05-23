"""
Type definitions for the Mover Status Monitor configuration system.

This module contains all TypedDict definitions and type aliases used throughout
the configuration system. It provides a centralized location for all configuration
type definitions, making them easier to maintain and reuse.
"""

from typing import TypedDict, NotRequired


# Type variables for generic dictionary operations
# These are imported from the main config_manager module for backward compatibility

# Provider-specific configuration types
class TelegramConfig(TypedDict):
    """Telegram notification provider configuration."""
    enabled: bool
    bot_token: str
    chat_id: str
    message_template: str
    parse_mode: str
    disable_notification: bool


class DiscordConfig(TypedDict):
    """Discord notification provider configuration."""
    enabled: bool
    webhook_url: str
    username: str
    message_template: str
    use_embeds: bool
    embed_title: str
    embed_colors: dict[str, int]


class ProvidersConfig(TypedDict):
    """Container for all notification provider configurations."""
    telegram: TelegramConfig
    discord: DiscordConfig


# Main configuration section types
class NotificationConfig(TypedDict):
    """Notification settings configuration."""
    notification_increment: int
    enabled_providers: list[str]
    providers: ProvidersConfig
    # Fields accessed from other sections for validation
    mover_executable: NotRequired[str]
    cache_directory: NotRequired[str]
    poll_interval: NotRequired[int]
    dry_run: NotRequired[bool]
    enable_debug: NotRequired[bool]


class MonitoringConfig(TypedDict):
    """Monitoring settings configuration."""
    mover_executable: str
    cache_directory: str
    poll_interval: int
    # Fields accessed from other sections for validation
    notification_increment: NotRequired[int]
    enabled_providers: NotRequired[list[str]]
    providers: NotRequired[ProvidersConfig]
    dry_run: NotRequired[bool]
    enable_debug: NotRequired[bool]


class MessagesConfig(TypedDict):
    """Message templates configuration."""
    completion: str
    # Fields accessed from other sections for validation
    notification_increment: NotRequired[int]
    enabled_providers: NotRequired[list[str]]
    providers: NotRequired[ProvidersConfig]
    mover_executable: NotRequired[str]
    cache_directory: NotRequired[str]
    poll_interval: NotRequired[int]
    dry_run: NotRequired[bool]
    enable_debug: NotRequired[bool]


class PathsConfig(TypedDict):
    """Path settings configuration."""
    exclude: list[str]
    # Fields accessed from other sections for validation
    notification_increment: NotRequired[int]
    enabled_providers: NotRequired[list[str]]
    providers: NotRequired[ProvidersConfig]
    mover_executable: NotRequired[str]
    cache_directory: NotRequired[str]
    poll_interval: NotRequired[int]
    dry_run: NotRequired[bool]
    enable_debug: NotRequired[bool]


class DebugConfig(TypedDict):
    """Debug settings configuration."""
    dry_run: bool
    enable_debug: bool
    # Fields accessed from other sections for validation
    notification_increment: NotRequired[int]
    enabled_providers: NotRequired[list[str]]
    providers: NotRequired[ProvidersConfig]
    mover_executable: NotRequired[str]
    cache_directory: NotRequired[str]
    poll_interval: NotRequired[int]


# Complete configuration structure type
class ConfigSections(TypedDict):
    """Complete configuration structure with all sections."""
    notification: NotificationConfig
    monitoring: MonitoringConfig
    messages: MessagesConfig
    paths: PathsConfig
    debug: DebugConfig
