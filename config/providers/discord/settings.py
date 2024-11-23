# config/providers/discord/settings.py

"""
Discord-specific configuration models and settings.
Extends base provider settings with Discord webhook configuration.

Example:
    >>> from config.providers.discord.settings import DiscordSettings
    >>> settings = DiscordSettings(
    ...     enabled=True,
    ...     webhook_url="https://discord.com/api/webhooks/123/abc",
    ...     username="Mover Bot"
    ... )
"""

from typing import Any, Dict, Optional
from urllib.parse import urlparse

from pydantic import Field, HttpUrl, field_validator

from config.providers.base import BaseProviderSettings
from config.providers.discord.schemas import WebhookConfigSchema
from shared.types.discord import ApiLimits, DiscordColor


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

    thread_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Thread name for forum posts"
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
            ValueError: If URL is invalid or missing when enabled
        """
        # Get the enabled status from the validation context
        enabled = info.data.get("enabled", False)

        if enabled and not v:
            raise ValueError("Webhook URL must be provided when Discord is enabled")

        if v:
            parsed = urlparse(str(v))
            if "discord.com" not in parsed.netloc:
                raise ValueError("Webhook URL must be from discord.com domain")

            if not parsed.path.startswith("/api/webhooks/"):
                raise ValueError("Invalid webhook URL format")

            # Validate webhook ID and token format
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) != 4 or path_parts[0:2] != ["api", "webhooks"]:
                raise ValueError("Invalid webhook URL path format")

            webhook_id, token = path_parts[2:4]
            if not webhook_id.isdigit():
                raise ValueError("Invalid webhook ID format")

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
            ValueError: If URL format is invalid
        """
        if v:
            parsed = urlparse(str(v))
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("Avatar URL must use HTTP(S) protocol")

            # Validate against allowed domains
            allowed_domains = {"cdn.discordapp.com", "i.imgur.com", "media.discordapp.net"}
            if not any(domain in parsed.netloc for domain in allowed_domains):
                raise ValueError("Avatar URL must be from Discord or Imgur domains")

        return v

    def to_provider_config(self) -> Dict:
        """Convert settings to Discord provider configuration.

        Returns:
            Dict: Discord provider configuration dictionary
        """
        # Get base configuration
        config = super().to_provider_config()

        # Create webhook config using schema
        webhook_config = None
        if self.webhook_url:
            webhook_config = WebhookConfigSchema(
                webhook_url=str(self.webhook_url),
                username=self.username,
                avatar_url=self.avatar_url,
                thread_name=self.thread_name
            ).to_webhook_config()

        # Add Discord-specific configuration
        config.update({
            "webhook_config": webhook_config,
            "embed_color": self.embed_color or DiscordColor.INFO
        })

        return config

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
                    "rate_limit": {
                        "rate_limit": 30,
                        "rate_period": 60,
                        "retry_attempts": 3,
                        "retry_delay": 5
                    }
                }
            ]
        }
    }
