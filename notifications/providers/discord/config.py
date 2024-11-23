# notifications/providers/discord/config.py

"""
Runtime configuration management for Discord webhook notifications.
Handles validation, normalization, and conversion of webhook configuration settings.

Example:
    >>> from notifications.providers.discord import DiscordConfig
    >>> config = DiscordConfig(
    ...     webhook_url="https://discord.com/api/webhooks/123/abc",
    ...     username="Mover Bot",
    ...     embed_color=0x2ECC71
    ... )
    >>> provider_config = config.to_provider_config()
"""

import re
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from notifications.providers.discord.types import (
    RATE_LIMIT,
    DiscordColor,
)
from shared.types.discord import ApiLimits


class DiscordConfig(BaseModel):
    """Discord webhook configuration settings."""
    webhook_url: str = Field(
        ...,  # Required field
        description="Discord webhook URL",
        examples=["https://discord.com/api/webhooks/123/abc"]
    )

    username: str = Field(
        default="Mover Bot",
        max_length=ApiLimits.USERNAME_LENGTH,
        description="Display name for webhook messages"
    )

    avatar_url: Optional[str] = Field(
        default=None,
        description="URL for webhook avatar image"
    )

    embed_color: Optional[int] = Field(
        default=DiscordColor.INFO,
        ge=0,
        le=0xFFFFFF,  # 16777215
        description="Default color for message embeds (hex color code)"
    )

    thread_name: Optional[str] = Field(
        default=None,
        max_length=ApiLimits.CHANNEL_NAME_LENGTH,
        description="Thread name for forum posts"
    )

    rate_limit: int = Field(
        default=RATE_LIMIT["rate_limit"],
        ge=1,
        le=60,
        description="Maximum number of messages per minute"
    )

    rate_period: int = Field(
        default=RATE_LIMIT["rate_period"],
        ge=30,
        le=3600,
        description="Rate limit period in seconds"
    )

    retry_attempts: int = Field(
        default=RATE_LIMIT["max_retries"],
        ge=1,
        le=5,
        description="Number of retry attempts for failed messages"
    )

    retry_delay: int = Field(
        default=RATE_LIMIT["retry_delay"],
        ge=1,
        le=30,
        description="Delay between retry attempts in seconds"
    )

    @field_validator("webhook_url")
    def validate_webhook_url(cls, v: str) -> str:
        """Validate Discord webhook URL format and domain.

        Args:
            v: Webhook URL to validate

        Returns:
            str: Validated webhook URL

        Raises:
            ValueError: If URL is invalid or not from discord.com
        """
        if not v:
            raise ValueError("Webhook URL is required")

        parsed = urlparse(v)
        if not all([parsed.scheme, parsed.netloc, parsed.path]):
            raise ValueError("Invalid webhook URL format")

        if parsed.scheme not in ["http", "https"]:
            raise ValueError("Webhook URL must use HTTP(S) protocol")

        if "discord.com" not in parsed.netloc:
            raise ValueError("Webhook URL must be from discord.com domain")

        # Validate webhook path format
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) != 4 or path_parts[0:2] != ["api", "webhooks"]:
            raise ValueError("Invalid webhook URL path format")

        # Validate webhook ID and token
        webhook_id, token = path_parts[2:4]
        if not webhook_id.isdigit():
            raise ValueError("Invalid webhook ID format")

        if not re.match(r"^[A-Za-z0-9_-]{60,80}$", token):
            raise ValueError("Invalid webhook token format")

        return v

    @field_validator("avatar_url")
    def validate_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate avatar URL if provided.

        Args:
            v: Avatar URL to validate

        Returns:
            Optional[str]: Validated avatar URL or None

        Raises:
            ValueError: If URL format is invalid
        """
        if not v:
            return None

        parsed = urlparse(v)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError("Invalid avatar URL format")

        if parsed.scheme not in ["http", "https"]:
            raise ValueError("Avatar URL must use HTTP(S) protocol")

        # Validate against allowed domains
        allowed_domains = {
            "cdn.discordapp.com",
            "media.discordapp.net",
            "i.imgur.com"
        }

        if not any(domain in parsed.netloc for domain in allowed_domains):
            domains_str = ", ".join(allowed_domains)
            raise ValueError(f"Avatar URL must be from: {domains_str}")

        return v

    def to_provider_config(self) -> dict:
        """Convert configuration to provider-compatible dictionary.

        Returns:
            dict: Configuration dictionary for provider initialization

        Example:
            >>> config = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/abc")
            >>> provider_config = config.to_provider_config()
            >>> assert "webhook_url" in provider_config
        """
        return {
            "webhook_url": self.webhook_url,
            "username": self.username,
            "avatar_url": self.avatar_url,
            "embed_color": self.embed_color or DiscordColor.INFO,
            "thread_name": self.thread_name,
            "rate_limit": {
                "limit": self.rate_limit,
                "period": self.rate_period,
                "retry_attempts": self.retry_attempts,
                "retry_delay": self.retry_delay
            }
        }

    class Config:
        """Pydantic model configuration."""
        frozen = True  # Make the config immutable
        validate_assignment = True
        allow_mutation = False
        extra = "forbid"  # Prevent additional fields
        title = "Discord Webhook Configuration"
        json_schema_extra = {
            "examples": [
                {
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "username": "Mover Bot",
                    "embed_color": DiscordColor.INFO,
                    "rate_limit": 30,
                    "rate_period": 60,
                    "retry_attempts": 3,
                    "retry_delay": 5
                }
            ]
        }
