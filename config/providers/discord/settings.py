# config/providers/discord/settings.py

"""
Discord-specific configuration models and settings.
Extends base provider settings with Discord webhook configuration.

Contains:
    - DiscordSettingsError: Base exception for settings validation
    - ForumSettings: Configuration for Discord forum channels
    - DiscordSettings: Main settings class for Discord integration

Example:
    >>> from config.providers.discord.settings import DiscordSettings
    >>> settings = DiscordSettings(
    ...     enabled=True,
    ...     webhook_url="https://discord.com/api/webhooks/123/abc",
    ...     username="Mover Bot"
    ... )
"""

from typing import Any, Dict, Final, Optional, Set

from pydantic import BaseModel, Field, HttpUrl, field_validator

from config.providers.base import BaseProviderSettings
from config.providers.discord.schemas import DiscordSchemaError, WebhookConfigSchema
from shared.providers.discord import (
    WEBHOOK_DOMAINS,
    ApiLimits,
    DiscordColor,
    validate_image_url,
    validate_thread_name,
    validate_url_domain,
    validate_url_length,
    validate_webhook_path,
)


class DiscordSettingsError(Exception):
    """Base exception for Discord settings validation errors."""
    def __init__(self, message: str, setting: Optional[str] = None):
        self.setting = setting
        super().__init__(message)


# Immutable sets of allowed domains
AVATAR_DOMAINS: Final[Set[str]] = frozenset({
    "cdn.discordapp.com",
    "i.imgur.com",
    "media.discordapp.net"
})


class ForumSettings(BaseModel):
    """Configuration settings for Discord forum channels and thread management.

    Handles settings related to forum channel integration, including automatic thread
    creation and management of thread properties like names and archive duration.
    """
    enabled: bool = Field(
        default=False,
        description="Enable forum channel integration"
    )
    auto_thread: bool = Field(
        default=False,
        description="Automatically create threads for messages"
    )
    default_thread_name: Optional[str] = Field(
        default=None,
        max_length=ApiLimits.CHANNEL_NAME_LENGTH,
        description="Default name for auto-created threads"
    )
    archive_duration: int = Field(
        default=1440,  # 24 hours
        ge=60,  # 1 hour minimum
        le=10080,  # 1 week maximum
        description="Thread auto-archive duration in minutes"
    )

    @field_validator("default_thread_name")
    @classmethod
    def validate_thread_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate thread name format if provided.

        Args:
            v: Thread name to validate, or None if not set

        Returns:
            Optional[str]: The validated thread name, unchanged if valid

        Raises:
            DiscordSettingsError: If thread name is invalid
        """
        try:
            return validate_thread_name(v, "forum.default_thread_name")
        except ValueError as e:
            raise DiscordSettingsError(str(e), setting="forum.default_thread_name") from e


class DiscordSettings(BaseProviderSettings):
    """Discord webhook configuration settings."""
    webhook_url: Optional[HttpUrl] = Field(
        default=None,
        description="Discord webhook URL for notifications",
        examples=["https://discord.com/api/webhooks/123/abc"]
    )

    username: str = Field(
        default="Mover Bot",
        min_length=1,
        max_length=ApiLimits.USERNAME_LENGTH,
        description="Display name for webhook messages"
    )

    avatar_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL for webhook avatar image"
    )

    embed_color: Optional[int] = Field(
        default=DiscordColor.INFO,
        ge=0,
        le=0xFFFFFF,  # 16777215
        description="Default color for Discord embeds (hex color code)"
    )

    forum: Optional[ForumSettings] = Field(
        default=None,
        description="Optional forum channel settings"
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[HttpUrl], info: Any) -> Optional[HttpUrl]:
        """Validate Discord webhook URL format and presence.

        Args:
            v: Webhook URL to validate
            info: Validation context information

        Returns:
            Optional[HttpUrl]: Validated webhook URL

        Raises:
            DiscordSettingsError: If URL is invalid or missing when enabled
        """
        enabled = info.data.get("enabled", False)

        if enabled and not v:
            raise DiscordSettingsError(
                "Webhook URL must be provided when Discord is enabled",
                setting="webhook_url"
            )

        if v:
            try:
                url_str = str(v)
                validate_url_length(url_str, "webhook_url")
                validate_url_domain(url_str, "webhook_url", WEBHOOK_DOMAINS)
                validate_webhook_path(url_str)
            except ValueError as e:
                raise DiscordSettingsError(str(e), setting="webhook_url") from e

        return v

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: Optional[HttpUrl]) -> Optional[HttpUrl]:
        """Validate avatar URL format if provided.

        Args:
            v: Avatar URL to validate

        Returns:
            Optional[HttpUrl]: Validated avatar URL

        Raises:
            DiscordSettingsError: If URL format is invalid
        """
        try:
            return validate_image_url(v, "avatar_url")
        except ValueError as e:
            raise DiscordSettingsError(str(e), setting="avatar_url") from e

    def to_provider_config(self) -> Dict[str, Any]:
        """Convert settings to Discord provider configuration.

        Returns:
            Dict[str, Any]: Discord provider configuration dictionary

        Raises:
            DiscordSettingsError: If configuration conversion fails
        """
        try:
            # Get base configuration
            config = super().to_provider_config()

            # Create webhook config using schema
            webhook_config = None
            if self.webhook_url:
                webhook_config = WebhookConfigSchema(
                    webhook_url=str(self.webhook_url),
                    username=self.username,
                    avatar_url=self.avatar_url,
                    forum=self.forum.model_dump() if self.forum else None
                ).to_webhook_config()

            # Add Discord-specific configuration
            config.update({
                "webhook_config": webhook_config,
                "embed_color": self.embed_color or DiscordColor.INFO
            })

            return config

        except DiscordSchemaError as err:
            raise DiscordSettingsError(
                f"Invalid webhook configuration: {err}",
                setting=err.field
            ) from err
        except Exception as err:
            raise DiscordSettingsError(
                f"Failed to create provider configuration: {err}"
            ) from err

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "enabled": True,
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "username": "Mover Bot",
                    "embed_color": DiscordColor.INFO,
                },
                {
                    "enabled": True,
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "username": "Status Bot",
                    "avatar_url": "https://cdn.discordapp.com/avatars/123/abc.png",
                    "forum": {
                        "enabled": True,
                        "auto_thread": True,
                        "default_thread_name": "Status Updates"
                    }
                }
            ]
        }
    }
