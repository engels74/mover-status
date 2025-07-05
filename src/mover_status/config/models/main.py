"""Main configuration model."""

from __future__ import annotations

from pydantic import Field, model_validator

from .base import BaseConfig
from .monitoring import (
    MonitoringConfig,
    ProcessConfig,
    ProgressConfig,
    NotificationConfig,
    LoggingConfig,
)
from .providers import ProviderConfig


class AppConfig(BaseConfig):
    """Complete application configuration."""

    monitoring: MonitoringConfig = Field(
        default_factory=MonitoringConfig,
        description="Monitoring configuration",
    )
    process: ProcessConfig = Field(
        description="Process detection configuration",
    )
    progress: ProgressConfig = Field(
        default_factory=ProgressConfig,
        description="Progress tracking configuration",
    )
    notifications: NotificationConfig = Field(
        default_factory=NotificationConfig,
        description="Notification configuration",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration",
    )
    providers: ProviderConfig = Field(
        default_factory=ProviderConfig,
        description="Provider-specific configurations",
    )

    @model_validator(mode="after")
    def validate_config_consistency(self) -> AppConfig:
        """Validate configuration consistency across components."""
        # Ensure at least one provider is configured if providers are enabled
        if self.notifications.enabled_providers:
            enabled_providers: set[str] = set(self.notifications.enabled_providers)
            configured_providers: set[str] = set()
            
            if self.providers.telegram is not None:
                configured_providers.add("telegram")
            if self.providers.discord is not None:
                configured_providers.add("discord")
            
            missing_providers = enabled_providers - configured_providers
            if missing_providers:
                raise ValueError(
                    f"Enabled providers {missing_providers} are not configured"
                )
        
        # Validate that events in notifications config are consistent
        # with provider event configurations
        if self.providers.telegram is not None:
            telegram_events = set(self.providers.telegram.notifications.events)
            global_events = set(self.notifications.events)
            
            # Warn if there are mismatches (but don't fail)
            if telegram_events != global_events:
                # Could log warning here if logger is available
                pass
        
        return self