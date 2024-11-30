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

from __future__ import annotations

from typing import Any, Dict, Final, Optional

from pydantic import BaseModel, Field, field_validator

from config.providers.base import BaseProviderSettings
from config.providers.discord.schemas import DiscordSchemaError, WebhookConfigSchema
from shared.providers.discord import (
    ASSET_DOMAINS,
    WEBHOOK_DOMAINS,
    ApiLimits,
    DiscordColor,
    validate_thread_name,
    validate_url,
)

"""Discord webhook settings and configuration."""

class DiscordSettingsError(Exception):
    """Base exception for Discord settings validation errors."""

    def __init__(self, message: str, setting: Optional[str] = None):
        """Initialize Discord settings error.

        Args:
            message: Error message
            setting: Setting that caused the error
        """
        super().__init__(message)
        self.setting = setting


# Immutable sets of allowed domains
WEBHOOK_DOMAINS: Final = WEBHOOK_DOMAINS
ASSET_DOMAINS: Final = ASSET_DOMAINS


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


class WebhookSettings(BaseModel):
    """Discord webhook configuration settings."""
    url: str = Field(
        ...,
        title="Webhook URL",
        description="Discord webhook URL"
    )
    username: Optional[str] = Field(
        None,
        title="Username",
        description="Override the default username of the webhook"
    )
    avatar_url: Optional[str] = Field(
        None,
        title="Avatar URL",
        description="Override the default avatar of the webhook"
    )
    thread_id: Optional[str] = Field(
        None,
        title="Thread ID",
        description="Thread ID to send messages to"
    )
    thread_name: Optional[str] = Field(
        None,
        title="Thread Name",
        description="Thread name to send messages to"
    )

    @field_validator("url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        """Validate webhook URL domain."""
        if not validate_url(str(v), WEBHOOK_DOMAINS):
            raise ValueError("Invalid webhook URL domain")
        return str(v)

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate avatar URL domain."""
        if v is not None and not validate_url(str(v), ASSET_DOMAINS):
            raise ValueError("Invalid avatar URL domain")
        return str(v) if v else None

    @field_validator("thread_name")
    @classmethod
    def validate_thread_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate thread name format."""
        if v is not None:
            if not v.strip():
                raise ValueError("Thread name cannot be empty")
            if not validate_thread_name(v):
                raise ValueError("Invalid thread name format")
        return v

    @field_validator("thread_id", "thread_name")
    @classmethod
    def validate_thread_settings(cls, v: Optional[str], info: Dict[str, Any]) -> Optional[str]:
        """Validate thread settings."""
        if "thread_id" in info.data and "thread_name" in info.data:
            if bool(info.data["thread_id"]) != bool(info.data["thread_name"]):
                raise ValueError("Both thread_id and thread_name must be provided together")
        return v


class DiscordSettings(BaseProviderSettings):
    """Discord webhook notification settings."""

    webhook_url: str = Field(
        ...,
        pattern=r"^https://discord\.com/api/webhooks/\d+/.+$",
        description="Discord webhook URL"
    )

    username: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=80,
        description="Custom username for webhook messages"
    )

    avatar_url: Optional[str] = Field(
        default=None,
        pattern=r"^https?://.+",
        description="Custom avatar URL for webhook messages"
    )

    thread_id: Optional[str] = Field(
        default=None,
        pattern=r"^\d+$",
        description="Thread ID to send messages to"
    )

    forum: Optional[ForumSettings] = Field(
        default=None,
        description="Optional forum channel settings"
    )

    embed_color: Optional[int] = Field(
        default=DiscordColor.INFO,
        ge=0,
        le=0xFFFFFF,  # 16777215
        description="Default color for Discord embeds (hex color code)"
    )

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
                    "username": "Mover Bot"
                },
                {
                    "enabled": True,
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "username": "Status Bot",
                    "avatar_url": "https://cdn.discordapp.com/avatars/123/abc.png",
                },
                {
                    "enabled": True,
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "forum": {
                        "enabled": True,
                        "auto_thread": True,
                        "default_thread_name": "Status Updates"
                    }
                }
            ]
        }
    }
