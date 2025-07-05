"""Configuration models module with Pydantic models for configuration validation."""

from __future__ import annotations

from .base import (
    BaseConfig,
    RetryConfig,
    RateLimitConfig,
    ConfigurableProvider,
    LogLevel,
    NotificationEvent,
    ProviderName,
)
from .main import AppConfig
from .monitoring import (
    MonitoringConfig,
    ProcessConfig,
    ProgressConfig,
    NotificationConfig,
    LoggingConfig,
)
from .providers import (
    DiscordConfig,
    DiscordEmbedConfig,
    DiscordEmbedColors,
    DiscordMentions,
    DiscordNotificationConfig,
    TelegramConfig,
    TelegramFormatConfig,
    TelegramTemplates,
    TelegramNotificationConfig,
    ProviderConfig,
)

__all__ = [
    # Base models
    "BaseConfig",
    "RetryConfig",
    "RateLimitConfig",
    "ConfigurableProvider",
    "LogLevel",
    "NotificationEvent",
    "ProviderName",
    # Main configuration
    "AppConfig",
    # Monitoring models
    "MonitoringConfig",
    "ProcessConfig",
    "ProgressConfig",
    "NotificationConfig",
    "LoggingConfig",
    # Provider models
    "DiscordConfig",
    "DiscordEmbedConfig",
    "DiscordEmbedColors",
    "DiscordMentions",
    "DiscordNotificationConfig",
    "TelegramConfig",
    "TelegramFormatConfig",
    "TelegramTemplates",
    "TelegramNotificationConfig",
    "ProviderConfig",
]
