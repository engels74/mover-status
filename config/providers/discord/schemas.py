# config/providers/discord/schemas.py

"""
Validation schemas for Discord webhook configuration.
Provides Pydantic models for configuration validation and type safety.

Example:
    >>> from config.providers.discord.schemas import WebhookConfigSchema
    >>> config = WebhookConfigSchema(
    ...     webhook_url="https://discord.com/api/webhooks/123/abc",
    ...     username="Mover Bot"
    ... )
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from shared.providers.discord import (
    ASSET_DOMAINS,
    WEBHOOK_DOMAINS,
    ApiLimit,
    validate_url,
)
from shared.providers.discord.types import WebhookPayload as WebhookConfig


class DiscordSchemaError(Exception):
    """Base exception for Discord schema validation errors."""

    def __init__(self, message: str, field: Optional[str] = None):
        """Initialize Discord schema error.

        Args:
            message: Error message
            field: Field that caused the error
        """
        super().__init__(message)
        self.field = field


class EmbedFieldSchema(BaseModel):
    """Schema for Discord embed field validation."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=ApiLimit.FIELD_NAME_LENGTH,
        description="Field name"
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=ApiLimit.FIELD_VALUE_LENGTH,
        description="Field value"
    )
    inline: bool = Field(
        default=False,
        description="Display field inline"
    )

    @field_validator("name", "value")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate field content is not empty after trimming."""
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v

    def calculate_length(self) -> int:
        """Calculate total length including newlines."""
        return len(self.name) + len(self.value) + 2  # +2 for name/value separator


class EmbedFooterSchema(BaseModel):
    """Schema for Discord embed footer validation."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=ApiLimit.FOOTER_LENGTH,
        description="Footer text"
    )
    icon_url: Optional[str] = Field(
        default=None,
        description="Footer icon URL"
    )

    @field_validator("icon_url")
    @classmethod
    def validate_icon_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate icon URL is from allowed domains."""
        if v is not None and not validate_url(v, ASSET_DOMAINS):
            raise ValueError("Invalid icon URL domain")
        return v


class ForumConfigSchema(BaseModel):
    """Schema for Discord forum configuration validation."""
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
        ge=60,         # 1 hour minimum
        le=10080,      # 1 week maximum
        description="Thread auto-archive duration in minutes"
    )

    @field_validator("default_thread_name")
    @classmethod
    def validate_thread_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate thread name format."""
        if v is not None and not v.strip():
            raise ValueError("Thread name cannot be empty or whitespace")
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.dict(exclude_none=True)


class WebhookConfigSchema(BaseModel):
    """Discord webhook configuration schema."""

    webhook_url: str = Field(
        ...,
        min_length=1,
        description="Discord webhook URL"
    )
    username: Optional[str] = Field(
        None,
        min_length=1,
        max_length=ApiLimit.USERNAME_LENGTH,
        description="Override the default username of the webhook"
    )
    avatar_url: Optional[str] = Field(
        None,
        description="Override the default avatar of the webhook"
    )
    thread_name: Optional[str] = Field(
        None,
        description="Name of thread to send messages to"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "username": "Mover Bot",
                },
                {
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "username": "Status Bot",
                    "forum": {
                        "enabled": True,
                        "auto_thread": True,
                        "default_thread_name": "Status Updates"
                    }
                }
            ]
        }
    }

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        """Validate webhook URL."""
        if not validate_url(v, WEBHOOK_DOMAINS):
            raise ValueError("Invalid webhook URL domain")
        return v

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate avatar URL."""
        if v is not None and not validate_url(v, ASSET_DOMAINS):
            raise ValueError("Invalid avatar URL domain")
        return v

    def to_webhook_config(self) -> WebhookConfig:
        """Convert schema to webhook configuration.

        Returns:
            WebhookConfig: Webhook configuration dictionary
        """
        config: WebhookConfig = {
            "content": None,  # Initialize with required fields
            "embeds": []
        }

        if self.username:
            config["username"] = self.username
        if self.avatar_url:
            config["avatar_url"] = self.avatar_url
        if self.thread_name:
            config["thread_name"] = self.thread_name

        return config
