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
        max_length=80,
        description="Display name for webhook messages"
    )

    avatar_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL for webhook avatar image"
    )

    embed_color: Optional[int] = Field(
        default=None,
        ge=0,
        le=16777215,  # 0xFFFFFF
        description="Default color for Discord embeds (hex color code)"
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

        if enabled:
            if not v:
                raise ValueError("Webhook URL must be provided when Discord is enabled")

        if v:
            parsed = urlparse(str(v))
            if "discord.com" not in parsed.netloc:
                raise ValueError("Webhook URL must be from discord.com domain")

            if not parsed.path.startswith("/api/webhooks/"):
                raise ValueError("Invalid webhook URL format")

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

        return v

    def to_provider_config(self) -> Dict:
        """Convert settings to Discord provider configuration.

        Returns:
            Dict: Discord provider configuration dictionary
        """
        config = super().to_provider_config()
        config.update({
            "webhook_url": str(self.webhook_url) if self.webhook_url else None,
            "username": self.username,
            "avatar_url": str(self.avatar_url) if self.avatar_url else None,
            "embed_color": self.embed_color
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
                    "embed_color": 3447003,  # Discord Blurple
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
