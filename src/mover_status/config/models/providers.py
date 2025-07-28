"""Notification provider configuration models."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, field_validator, HttpUrl, ConfigDict

from .base import BaseConfig, RetryConfig, RateLimitConfig


class DiscordEmbedColors(BaseConfig):
    """Discord embed color configuration."""

    started: int = Field(
        default=0x00ff00,
        ge=0,
        le=0xffffff,
        description="Color for started notifications (hex color)",
    )
    progress: int = Field(
        default=0x0099ff,
        ge=0,
        le=0xffffff,
        description="Color for progress notifications (hex color)",
    )
    completed: int = Field(
        default=0x00cc00,
        ge=0,
        le=0xffffff,
        description="Color for completed notifications (hex color)",
    )
    failed: int = Field(
        default=0xff0000,
        ge=0,
        le=0xffffff,
        description="Color for failed notifications (hex color)",
    )


class DiscordEmbedConfig(BaseConfig):
    """Discord embed configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable rich embeds",
    )
    colors: DiscordEmbedColors = Field(
        default_factory=DiscordEmbedColors,
        description="Color scheme for different states",
    )
    thumbnail: bool = Field(
        default=True,
        description="Include thumbnail image",
    )
    timestamp: bool = Field(
        default=True,
        description="Include timestamp",
    )


class DiscordMentions(BaseConfig):
    """Discord mention configuration."""

    started: list[str] = Field(
        default_factory=list,
        description="Mentions for started notifications",
    )
    failed: list[str] = Field(
        default_factory=lambda: ["@everyone"],
        description="Mentions for failed notifications",
    )
    completed: list[str] = Field(
        default_factory=list,
        description="Mentions for completed notifications",
    )


class DiscordNotificationConfig(BaseConfig):
    """Discord notification configuration."""

    mentions: DiscordMentions = Field(
        default_factory=DiscordMentions,
        description="Mention configuration for different events",
    )
    rate_limits: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="Rate limiting configuration",
    )


class DiscordConfig(BaseConfig):
    """Discord provider configuration."""

    webhook_url: str = Field(
        description="Discord webhook URL",
    )
    username: str = Field(
        default="Mover Status Bot",
        description="Bot username override",
    )
    avatar_url: HttpUrl | None = Field(
        default=None,
        description="Bot avatar URL",
    )
    embeds: DiscordEmbedConfig = Field(
        default_factory=DiscordEmbedConfig,
        description="Embed configuration",
    )
    notifications: DiscordNotificationConfig = Field(
        default_factory=DiscordNotificationConfig,
        description="Notification configuration",
    )
    retry: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry configuration",
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        """Validate Discord webhook URL format."""
        # Allow placeholder values for initial configuration
        placeholder_values = [
            "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN",
            "${DISCORD_WEBHOOK_URL}",
            "YOUR_DISCORD_WEBHOOK_URL_HERE"
        ]
        if v in placeholder_values:
            return v
            
        pattern = r"^https://discord\.com/api/webhooks/\d+/[A-Za-z0-9_-]+$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid Discord webhook URL format. "
                + "Expected: https://discord.com/api/webhooks/ID/TOKEN"
            )
        return v


class TelegramFormatConfig(BaseConfig):
    """Telegram message format configuration."""

    parse_mode: Literal["HTML", "Markdown", "MarkdownV2"] = Field(
        default="HTML",
        description="Message parse mode",
    )
    disable_web_page_preview: bool = Field(
        default=True,
        description="Disable link previews",
    )
    disable_notification: bool = Field(
        default=False,
        description="Disable notification sound",
    )


class TelegramTemplates(BaseConfig):
    """Telegram message templates."""

    started: str = Field(
        default=(
            "🚀 <b>Mover Started</b>\n\n"
            "📊 Initial data: {initial_size}\n"
            "📁 Source: {source_path}\n"
            "📁 Destination: {destination_path}\n\n"
            "<i>Started at {start_time}</i>"
        ),
        description="Template for started notifications",
    )
    progress: str = Field(
        default=(
            "📈 <b>Mover Progress</b>\n\n"
            "✅ Progress: {progress_percent}%\n"
            "📊 Transferred: {transferred_size} / {total_size}\n"
            "⏱️ Speed: {transfer_rate}\n"
            "🕐 ETC: {etc}\n\n"
            "<i>Updated at {update_time}</i>"
        ),
        description="Template for progress notifications",
    )
    completed: str = Field(
        default=(
            "✅ <b>Mover Completed</b>\n\n"
            "📊 Total transferred: {total_size}\n"
            "⏱️ Duration: {duration}\n"
            "💾 Average speed: {avg_speed}\n\n"
            "<i>Completed at {completion_time}</i>"
        ),
        description="Template for completed notifications",
    )
    failed: str = Field(
        default=(
            "❌ <b>Mover Failed</b>\n\n"
            "🚨 Error: {error_message}\n"
            "📊 Progress at failure: {progress_percent}%\n\n"
            "<i>Failed at {failure_time}</i>"
        ),
        description="Template for failed notifications",
    )


class TelegramNotificationConfig(BaseConfig):
    """Telegram notification configuration."""

    events: list[Literal["started", "progress", "completed", "failed"]] = Field(
        default=["started", "progress", "completed", "failed"],
        description="Events to send notifications for",
    )
    rate_limits: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="Rate limiting configuration",
    )

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        """Validate event names."""
        valid_events = {"started", "progress", "completed", "failed"}
        for event in v:
            if event not in valid_events:
                raise ValueError(f"Invalid event: {event}")
        return v


class TelegramConfig(BaseConfig):
    """Telegram provider configuration."""

    bot_token: str = Field(
        description="Telegram bot token from @BotFather",
    )
    chat_ids: list[int] = Field(
        min_length=1,
        description="Chat IDs to send notifications to",
    )
    format: TelegramFormatConfig = Field(
        default_factory=TelegramFormatConfig,
        description="Message formatting configuration",
    )
    templates: TelegramTemplates = Field(
        default_factory=TelegramTemplates,
        description="Message templates",
    )
    notifications: TelegramNotificationConfig = Field(
        default_factory=TelegramNotificationConfig,
        description="Notification configuration",
    )
    retry: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry configuration",
    )

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """Validate Telegram bot token format."""
        # Allow placeholder values for initial configuration
        placeholder_values = [
            "YOUR_TELEGRAM_BOT_TOKEN_HERE",
            "${TELEGRAM_BOT_TOKEN}",
            "YOUR_BOT_TOKEN_FROM_BOTFATHER"
        ]
        if v in placeholder_values:
            return v
            
        pattern = r"^\d+:[A-Za-z0-9_-]+$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid Telegram bot token format. "
                + "Expected: <bot_id>:<bot_token>"
            )
        return v

    @field_validator("chat_ids")
    @classmethod
    def validate_chat_ids(cls, v: list[int]) -> list[int]:
        """Validate chat IDs."""
        if not v:
            raise ValueError("At least one chat ID must be provided")
        return v


class ProviderConfig(BaseConfig):
    """Provider configuration container with dynamic provider support."""

    # Keep existing providers for backward compatibility
    telegram: TelegramConfig | None = Field(
        default=None,
        description="Telegram provider configuration",
    )
    discord: DiscordConfig | None = Field(
        default=None,
        description="Discord provider configuration",
    )
    
    # Allow extra fields for dynamic providers
    model_config = ConfigDict(extra='allow')

    def get_provider_config(self, provider_name: str) -> dict[str, object] | None:
        """Get configuration for a specific provider dynamically.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Configuration dictionary for the provider, or None if not found
        """
        provider_config = getattr(self, provider_name, None)
        
        if provider_config is not None:
            if hasattr(provider_config, 'model_dump'):
                return provider_config.model_dump()
            elif hasattr(provider_config, 'dict'):
                return provider_config.dict()
            elif isinstance(provider_config, dict):
                return provider_config
            else:
                # Try to convert to dict
                try:
                    return dict(provider_config) if provider_config else None
                except (TypeError, ValueError):
                    return None
        
        return None
    
    def has_provider_config(self, provider_name: str) -> bool:
        """Check if configuration exists for a provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            True if configuration exists, False otherwise
        """
        return hasattr(self, provider_name) and getattr(self, provider_name) is not None
    
    def list_configured_providers(self) -> list[str]:
        """List all providers that have configurations.
        
        Returns:
            List of provider names with configurations
        """
        providers = []
        
        # Check known providers
        if self.telegram is not None:
            providers.append("telegram")
        if self.discord is not None:
            providers.append("discord")
        
        # Check for dynamic providers (extra fields)
        for attr_name in dir(self):
            if (not attr_name.startswith('_') and 
                attr_name not in ['telegram', 'discord', 'model_config', 'model_fields', 'model_computed_fields'] and
                not callable(getattr(self, attr_name))):
                attr_value = getattr(self, attr_name)
                if attr_value is not None:
                    providers.append(attr_name)
        
        return providers

    @field_validator("telegram", "discord")
    @classmethod
    def validate_provider_config(cls, v: BaseConfig | None) -> BaseConfig | None:
        """Validate provider configuration."""
        return v