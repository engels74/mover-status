# notifications/discord/config.py

"""
Configuration models for Discord webhook notifications.
Provides Pydantic models for configuration validation and type safety.

Example:
    >>> from notifications.discord.config import DiscordConfig
    >>> config = DiscordConfig(
    ...     webhook_url="https://discord.com/api/webhooks/...",
    ...     username="Mover Bot",
    ...     rate_limit=30
    ... )
"""

from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, validator

from notifications.discord.types import RATE_LIMIT, WEBHOOK_LIMITS


class DiscordConfig(BaseModel):
    """Discord webhook configuration settings."""
    webhook_url: str = Field(
        ...,  # Required field
        description="Discord webhook URL",
        examples=["https://discord.com/api/webhooks/123/abc"]
    )

    username: str = Field(
        default="Mover Bot",
        max_length=WEBHOOK_LIMITS["username"],
        description="Display name for webhook messages"
    )

    avatar_url: Optional[str] = Field(
        default=None,
        description="URL for webhook avatar image"
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

    @validator("webhook_url")
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

        # Basic webhook path validation
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2 or "webhooks" not in path_parts:
            raise ValueError("Invalid webhook URL path format")

        return v

    @validator("avatar_url")
    def validate_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate avatar URL if provided.

        Args:
            v: Avatar URL to validate

        Returns:
            Optional[str]: Validated avatar URL or None

        Raises:
            ValueError: If URL is invalid
        """
        if not v:
            return None

        parsed = urlparse(v)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError("Invalid avatar URL format")

        if parsed.scheme not in ["http", "https"]:
            raise ValueError("Avatar URL must use HTTP(S) protocol")

        return v

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
                    "rate_limit": 30,
                    "rate_period": 60,
                    "retry_attempts": 3,
                    "retry_delay": 5
                }
            ]
        }

    def to_provider_config(self) -> dict:
        """Convert configuration to provider-compatible dictionary.

        Returns:
            dict: Configuration dictionary for provider initialization
        """
        return {
            "webhook_url": self.webhook_url,
            "username": self.username,
            "avatar_url": self.avatar_url,
            "rate_limit": {
                "limit": self.rate_limit,
                "period": self.rate_period,
                "retry_attempts": self.retry_attempts,
                "retry_delay": self.retry_delay
            }
        }
