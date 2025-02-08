# notifications/providers/discord/config.py

"""
Discord webhook configuration management and validation.
Handles configuration parsing and validation using Pydantic models.

Example:
    >>> from notifications.providers.discord import DiscordConfig
    >>> config = DiscordConfig(
    ...     webhook_url="https://discord.com/api/webhooks/123/abc",
    ...     username="Mover Bot"
    ... )
    >>> provider_config = config.to_provider_config()
"""

from typing import Any, Dict, Optional, cast

from pydantic import Field, HttpUrl, field_validator

from config.providers.base import BaseProviderSettings
from config.providers.discord.schemas import WebhookConfigSchema
from notifications.providers.discord.validators import DiscordValidator
from shared.providers.discord.types import ApiLimit as ApiLimits
from shared.providers.discord.types import DiscordColor


class DiscordConfig(BaseProviderSettings):
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
        max_length=ApiLimits.CHANNEL_NAME_LENGTH,
        description="Thread name for forum posts"
    )

    _validator: DiscordValidator = DiscordValidator()

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
        enabled = info.data.get("enabled", False)

        try:
            if v is not None:
                cls._validator.validate_webhook_url(str(v), required=enabled)
            elif enabled:
                raise ValueError("Webhook URL must be provided when Discord is enabled")
            return v
        except Exception as err:
            raise ValueError(str(err)) from err

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
        try:
            if v is not None:
                cls._validator.validate_avatar_url(str(v))
            return v
        except Exception as err:
            raise ValueError(str(err)) from err

    def to_provider_config(self) -> Dict[str, Any]:
        """Convert settings to Discord provider configuration.

        Returns:
            Dict[str, Any]: Discord provider configuration dictionary

        Example:
            >>> config = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/abc")
            >>> provider_config = config.to_provider_config()
            >>> assert "webhook_url" in provider_config
        """
        # Get base configuration
        config = super().to_provider_config()

        # Create webhook config using schema
        webhook_config = None
        if self.webhook_url:
            webhook_config = WebhookConfigSchema(
                webhook_url=str(self.webhook_url),
                username=self.username,
                avatar_url=str(self.avatar_url) if self.avatar_url else None,
                thread_name=self.thread_name
            ).to_webhook_config()

            # Validate complete webhook configuration
            try:
                self._validator.validate_config(cast(Dict[str, Any], webhook_config))
            except Exception as err:
                raise ValueError(f"Invalid webhook configuration: {err}") from err

        # Add Discord-specific configuration
        config.update(cast(Dict[str, Any], {
            "webhook_config": webhook_config,
            "embed_color": self.embed_color or DiscordColor.INFO
        }))

        return config

    class Config:
        """Pydantic model configuration."""
        validate_assignment = True
        extra = "forbid"
        json_schema_extra = {
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
