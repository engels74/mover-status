# config/settings.py

"""
Configuration management using Pydantic.
Handles environment variables and provides type-safe access to settings.
Designed to work seamlessly with Docker environment variables.
"""

from pathlib import Path
from typing import List

from pydantic import BaseSettings, Field

from config.constants import (
    DEFAULT_CACHE_PATH,
    DEFAULT_LOG_DIR,
    DEFAULT_NOTIFICATION_INCREMENT,
    LogLevel,
    NotificationProvider,
)
from config.providers.discord.settings import DiscordSettings
from config.providers.telegram.settings import TelegramSettings


class Settings(BaseSettings):
    """
    Main application settings.
    All settings can be configured via environment variables with the MOVER_ prefix.
    Example: MOVER_CACHE_PATH=/path/to/cache
    """
    # Monitoring settings
    cache_path: Path = Field(
        default=DEFAULT_CACHE_PATH,
        description="Path to the cache directory to monitor",
        env="CACHE_PATH"
    )
    excluded_paths: List[Path] = Field(
        default_factory=list,
        description="Comma-separated list of paths to exclude from monitoring",
        env="EXCLUDED_PATHS"
    )
    notification_increment: int = Field(
        default=DEFAULT_NOTIFICATION_INCREMENT,
        description="Percentage increment for notifications",
        env="NOTIFICATION_INCREMENT"
    )

    # Logging settings
    log_dir: Path = Field(
        default=DEFAULT_LOG_DIR,
        description="Directory for log files",
        env="LOG_DIR"
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level",
        env="LOG_LEVEL"
    )
    debug_mode: bool = Field(
        default=False,
        description="Enable debug mode for additional logging",
        env="DEBUG_MODE"
    )

    # Provider settings
    discord: DiscordSettings = Field(
        default_factory=DiscordSettings,
        description="Discord notification settings"
    )
    telegram: TelegramSettings = Field(
        default_factory=TelegramSettings,
        description="Telegram notification settings"
    )

    # Advanced settings
    polling_interval: float = Field(
        default=1.0,
        description="Interval in seconds between monitoring checks",
        env="POLLING_INTERVAL"
    )
    dry_run: bool = Field(
        default=False,
        description="Run in dry-run mode without sending notifications",
        env="DRY_RUN"
    )
    check_version: bool = Field(
        default=True,
        description="Enable version checking",
        env="CHECK_VERSION"
    )

    @property
    def active_providers(self) -> List[NotificationProvider]:
        """Get list of active notification providers."""
        providers = []
        if self.discord.enabled:
            providers.append(NotificationProvider.DISCORD)
        if self.telegram.enabled:
            providers.append(NotificationProvider.TELEGRAM)
        return providers

    class Config:
        """Pydantic configuration."""
        env_prefix = "MOVER_"
        case_sensitive = False
        allow_mutation = False
        validate_assignment = True

        # Enable environment variable loading for nested models
        env_nested_delimiter = "__"

        # Allow environment variables to override file configs
        env_file = ".env"
        env_file_encoding = "utf-8"
