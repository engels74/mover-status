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
            placeholder_providers: set[str] = set()
            
            # Check telegram configuration
            if self.providers.telegram is not None:
                configured_providers.add("telegram")
                # Check for placeholder values (but not valid test tokens)
                is_placeholder_token = self.providers.telegram.bot_token in [
                    "YOUR_TELEGRAM_BOT_TOKEN_HERE", 
                    "${TELEGRAM_BOT_TOKEN}",
                    "YOUR_BOT_TOKEN_FROM_BOTFATHER"
                ]
                # Only consider chat_ids placeholder if combined with placeholder token
                if is_placeholder_token:
                    placeholder_providers.add("telegram")
            
            # Check discord configuration  
            if self.providers.discord is not None:
                configured_providers.add("discord")
                # Check for placeholder values
                if (self.providers.discord.webhook_url in [
                    "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN",
                    "${DISCORD_WEBHOOK_URL}"
                ]):
                    placeholder_providers.add("discord")
            
            missing_providers = enabled_providers - configured_providers
            if missing_providers:
                # Provide helpful error message with configuration examples
                if "telegram" in missing_providers and "discord" in missing_providers:
                    config_example = """
Add provider configurations to your config file:

providers:
  telegram:
    bot_token: "YOUR_BOT_TOKEN_FROM_BOTFATHER"
    chat_ids: [YOUR_CHAT_ID]
  discord:
    webhook_url: "https://discord.com/api/webhooks/ID/TOKEN"
"""
                elif "telegram" in missing_providers:
                    config_example = """
Add Telegram configuration to your config file:

providers:
  telegram:
    bot_token: "YOUR_BOT_TOKEN_FROM_BOTFATHER"
    chat_ids: [YOUR_CHAT_ID]
"""
                elif "discord" in missing_providers:
                    config_example = """
Add Discord configuration to your config file:

providers:
  discord:
    webhook_url: "https://discord.com/api/webhooks/ID/TOKEN"
"""
                else:
                    config_example = ""
                    
                raise ValueError(
                    f"Enabled providers {missing_providers} are not configured.{config_example}"
                )
            
            # Check for placeholder values in configured providers
            if placeholder_providers:
                placeholder_messages: list[str] = []
                if "telegram" in placeholder_providers:
                    placeholder_messages.append(
                        "Telegram: Replace 'YOUR_TELEGRAM_BOT_TOKEN_HERE' with your actual bot token and update chat_ids"
                    )
                if "discord" in placeholder_providers:
                    placeholder_messages.append(
                        "Discord: Replace the webhook_url with your actual Discord webhook URL"
                    )
                
                raise ValueError(
                    "Provider(s) " + str(placeholder_providers) + " are configured with placeholder values. " +
                    "Please update: " + "; ".join(placeholder_messages)
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