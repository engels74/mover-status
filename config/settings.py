# config/settings.py

"""
Configuration management using Pydantic.
Handles environment variables, YAML files, and provides type-safe access to settings.
Designed to work seamlessly with Docker environment variables and configuration files.

Example:
    >>> settings = Settings()  # Load from environment
    >>> settings = Settings.from_yaml("config.yml")  # Load from YAML
    >>> settings.discord.webhook_url  # Access nested settings
"""

from pathlib import Path
from typing import List, Set, Union

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from config.constants import (
    LogLevel,
    MessagePriority,
    Monitoring,
    NotificationProvider,
    Paths,
    Templates,
)
from config.providers.discord.settings import DiscordSettings
from config.providers.telegram.settings import TelegramSettings


class FileSystemSettings(BaseModel):
    """File system related settings."""
    cache_path: Path = Field(
        default=Paths.DEFAULT_CACHE,
        description="Path to the cache directory to monitor"
    )
    excluded_paths: Set[Path] = Field(
        default_factory=set,
        description="Set of paths to exclude from monitoring"
    )

    @field_validator("cache_path")
    @classmethod
    def validate_cache_path(cls, v: Path) -> Path:
        """Validate cache path exists and is accessible."""
        path = Path(v).resolve()
        if not path.exists():
            raise ValueError(f"Cache path does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Cache path is not a directory: {path}")
        return path

    @field_validator("excluded_paths")
    @classmethod
    def validate_excluded_paths(cls, v: Set[Path]) -> Set[Path]:
        """Validate excluded paths are within cache path."""
        resolved = {Path(p).resolve() for p in v}
        for path in resolved:
            if not path.exists():
                raise ValueError(f"Excluded path does not exist: {path}")
            if not path.is_dir():
                raise ValueError(f"Excluded path is not a directory: {path}")
        return resolved


class LoggingSettings(BaseModel):
    """Logging related settings."""
    log_dir: Path = Field(
        default=Paths.DEFAULT_LOGS,
        description="Directory for log files"
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    debug_mode: bool = Field(
        default=False,
        description="Enable debug mode for additional logging"
    )

    @field_validator("log_dir")
    @classmethod
    def validate_log_dir(cls, v: Path) -> Path:
        """Ensure log directory exists or can be created."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path


class MonitoringSettings(BaseModel):
    """Monitoring behavior settings."""
    polling_interval: float = Field(
        default=Monitoring.MONITORING_INTERVAL,
        ge=0.1,
        le=60.0,
        description="Interval in seconds between monitoring checks"
    )
    notification_increment: int = Field(
        default=Monitoring.DEFAULT_INCREMENT,
        ge=Monitoring.MIN_INCREMENT,
        le=Monitoring.MAX_INCREMENT,
        description="Percentage increment for notifications"
    )
    message_template: str = Field(
        default=Templates.DEFAULT_MESSAGE,
        min_length=1,
        description="Template for notification messages"
    )
    message_priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Default priority for notifications"
    )


class Settings(BaseSettings):
    """
    Main application settings.
    Combines all setting categories and provider configurations.
    """
    # Core settings groups
    filesystem: FileSystemSettings = Field(default_factory=FileSystemSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)

    # Provider settings
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)

    # Application behavior
    dry_run: bool = Field(
        default=False,
        description="Run without sending notifications"
    )
    check_version: bool = Field(
        default=True,
        description="Enable version checking"
    )

    @property
    def active_providers(self) -> List[NotificationProvider]:
        """Get list of enabled notification providers."""
        providers = []
        if self.discord.enabled:
            providers.append(NotificationProvider.DISCORD)
        if self.telegram.enabled:
            providers.append(NotificationProvider.TELEGRAM)
        return providers

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Settings":
        """Load settings from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Settings: Settings instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
            ValueError: If config values are invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        try:
            with open(path) as f:
                config_data = yaml.safe_load(f)
            return cls.model_validate(config_data)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}") from e

    def save_yaml(self, path: Union[str, Path]) -> None:
        """Save current settings to YAML file.

        Args:
            path: Path to save configuration file

        Raises:
            OSError: If file cannot be written
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, excluding None values
        config_data = self.model_dump(exclude_none=True)

        with open(path, 'w') as f:
            yaml.safe_dump(config_data, f, default_flow_style=False)

    class Config:
        """Pydantic configuration."""
        env_prefix = "MOVER_"
        env_nested_delimiter = "__"
        case_sensitive = False
        validate_assignment = True
        extra = "forbid"

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "filesystem": {
                    "cache_path": "/mnt/cache",
                    "excluded_paths": ["/mnt/cache/system"]
                },
                "logging": {
                    "log_level": "INFO",
                    "debug_mode": False
                },
                "monitoring": {
                    "polling_interval": 1.0,
                    "notification_increment": 25
                },
                "discord": {
                    "enabled": True,
                    "webhook_url": "https://discord.com/api/webhooks/..."
                },
                "telegram": {
                    "enabled": False
                }
            }]
        }
    }
