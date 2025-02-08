# config/providers/discord/settings.py

"""
Discord-specific configuration models and settings.

This module provides configuration models for Discord webhook integration,
extending the base provider settings with Discord-specific functionality:

- Webhook configuration (URL, username, avatar)
- Forum channel integration
- Thread management
- Message customization (embeds, colors)

The settings are validated using Pydantic models and include specific
validation for Discord's API requirements and limitations.

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

from pydantic import BaseModel, Field, field_validator, ValidationInfo
from pydantic import ValidationError

from config.providers.base import BaseProviderSettings
from config.providers.discord.schemas import DiscordSchemaError, WebhookConfigSchema
from shared.providers.discord import (
    ASSET_DOMAINS,
    WEBHOOK_DOMAINS,
    ApiLimit,
    DiscordColor,
    validate_url,
)
from config.constants import JsonDict, JsonValue
from typing import cast
import re

# Thread name validation pattern
THREAD_NAME_PATTERN: Final = re.compile(r"^[\w\-\s]{1,100}$")

def validate_thread_name(name: str, field: Optional[str] = None) -> bool:
    """Validate thread name format.
    
    Args:
        name: Thread name to validate
        field: Optional field name for error context
        
    Returns:
        bool: True if thread name is valid
        
    Raises:
        ValueError: If thread name is invalid
    """
    if not name or not name.strip():
        raise ValueError(f"Thread name cannot be empty{f' ({field})' if field else ''}")
    
    if not THREAD_NAME_PATTERN.match(name):
        raise ValueError(
            f"Thread name must be 1-100 characters and contain only letters, numbers, "
            f"hyphens, and spaces{f' ({field})' if field else ''}"
        )
    
    return True

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
        max_length=ApiLimit.CHANNEL_NAME_LENGTH,
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
        if v is None:
            return None
            
        try:
            validate_thread_name(v, "forum.default_thread_name")
        except ValueError as e:
            raise DiscordSettingsError(str(e), setting="forum.default_thread_name") from e
        return v


class WebhookSettings(BaseModel):
    """Discord webhook configuration and validation.

    This model defines the core webhook settings required for Discord integration,
    including URL validation, username customization, and thread support.

    Attributes:
        url: Discord webhook URL (must be from discord.com domain)
        username: Optional custom username for the webhook
        avatar_url: Optional custom avatar URL (must be from allowed domains)
        thread_id: Optional Discord thread ID for message routing
        thread_name: Optional thread name (required if thread_id is set)

    Example:
        >>> webhook = WebhookSettings(
        ...     url="https://discord.com/api/webhooks/123/abc",
        ...     username="Status Bot",
        ...     thread_id="789",
        ...     thread_name="Mover Updates"
        ... )
    """
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
        if v is None:
            return None
            
        try:
            validate_thread_name(v)
        except ValueError as e:
            raise ValueError(str(e))
        return v

    @field_validator("thread_id", "thread_name")
    @classmethod
    def validate_thread_settings(
        cls, v: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        """Validate thread settings."""
        if info.field_name == "thread_id":
            thread_name = info.data.get("thread_name")
            if bool(v) != bool(thread_name):
                raise ValueError("Both thread_id and thread_name must be provided together")
        elif info.field_name == "thread_name":
            thread_id = info.data.get("thread_id")
            if bool(v) != bool(thread_id):
                raise ValueError("Both thread_id and thread_name must be provided together")
        return v


class DiscordSettings(BaseProviderSettings):
    """Discord integration settings with webhook and forum support.

    This model extends BaseProviderSettings with Discord-specific configuration,
    including webhook setup, forum channel integration, and message customization.
    It handles validation of Discord's API requirements and provides conversion
    to provider configuration format.

    Attributes:
        webhook_url: Discord webhook URL for message delivery
        username: Optional custom username for webhook messages
        avatar_url: Optional custom avatar URL for webhook messages
        thread_id: Optional thread ID for message routing
        forum: Optional forum channel configuration
        embed_color: Default color for Discord embeds (0x000000 to 0xFFFFFF)

    Example:
        >>> settings = DiscordSettings(
        ...     enabled=True,
        ...     webhook_url="https://discord.com/api/webhooks/123/abc",
        ...     username="Mover Bot",
        ...     forum=ForumSettings(
        ...         enabled=True,
        ...         auto_thread=True,
        ...         default_thread_name="Status Updates"
        ...     )
        ... )
    """
    webhook_url: Optional[str] = Field(
        default=None,
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

    thread_name: Optional[str] = Field(
        default=None,
        description="Thread name to send messages to"
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

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str], info: Any) -> Optional[str]:
        """Validate webhook URL when Discord is enabled.

        Args:
            v: Webhook URL to validate
            info: Validation context information

        Returns:
            Optional[str]: Validated webhook URL

        Raises:
            ValueError: If webhook URL is missing when enabled
        """
        enabled = info.data.get("enabled", False)

        if enabled and not v:
            raise ValueError("webhook_url is required when Discord is enabled")

        if v and not v.startswith("https://discord.com/api/webhooks/"):
            raise ValueError("webhook_url must be a valid Discord webhook URL")

        return v

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
                # Convert webhook config to Dict[str, JsonValue] for type compatibility
                raw_config = WebhookConfigSchema(
                    webhook_url=str(self.webhook_url),
                    username=self.username,
                    avatar_url=self.avatar_url,
                    thread_name=self.thread_name if self.thread_id else None
                ).to_webhook_config()
                # Convert to compatible type by extracting only JsonValue fields
                webhook_config = {
                    "content": raw_config.get("content"),
                    "username": raw_config.get("username"),
                    "avatar_url": raw_config.get("avatar_url"),
                    "thread_name": raw_config.get("thread_name"),
                    "embeds": [],  # Initialize as empty list
                }

            # Add Discord-specific configuration
            config.update([
                ("webhook_config", webhook_config),
                ("embed_color", int(self.embed_color or DiscordColor.INFO))
            ])

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
