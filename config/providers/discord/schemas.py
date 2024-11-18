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

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from shared.providers.discord import (
    ApiLimits,
    ForumConfig,
    WebhookConfig,
    validate_image_url,
    validate_thread_name,
    validate_url_domain,
    validate_url_length,
    validate_webhook_path,
)


class DiscordSchemaError(Exception):
    """Base exception for Discord schema validation errors."""
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(message)


class EmbedFieldSchema(BaseModel):
    """Schema for Discord embed field validation."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=ApiLimits.FIELD_NAME_LENGTH,
        description="Field name"
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=ApiLimits.FIELD_VALUE_LENGTH,
        description="Field value"
    )
    inline: bool = Field(
        default=False,
        description="Display field inline"
    )

    @model_validator(mode='after')
    def validate_content(self) -> 'EmbedFieldSchema':
        """Validate field content is not empty after trimming."""
        if not self.name.strip() or not self.value.strip():
            raise DiscordSchemaError(
                "Field name and value cannot be empty or whitespace",
                field="name" if not self.name.strip() else "value"
            )
        return self

    def calculate_length(self) -> int:
        """Calculate total length including newlines."""
        return len(self.name) + len(self.value) + 2  # +2 for name/value separator


class EmbedFooterSchema(BaseModel):
    """Schema for Discord embed footer validation."""
    text: str = Field(
        ...,
        min_length=1,
        max_length=ApiLimits.FOOTER_LENGTH,
        description="Footer text"
    )
    icon_url: Optional[HttpUrl] = Field(
        default=None,
        description="Footer icon URL"
    )

    @field_validator('icon_url')
    @classmethod
    def validate_icon_url(cls, v: Optional[HttpUrl]) -> Optional[HttpUrl]:
        """Validate icon URL is from allowed domains."""
        try:
            return validate_image_url(v, "icon_url")
        except ValueError as e:
            raise DiscordSchemaError(str(e), field="icon_url") from e


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
        max_length=ApiLimits.CHANNEL_NAME_LENGTH,
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
        try:
            return validate_thread_name(v, "default_thread_name")
        except ValueError as e:
            raise DiscordSchemaError(str(e), field="default_thread_name") from e

    def to_dict(self) -> ForumConfig:
        """Convert to ForumConfig dictionary."""
        return self.model_dump(exclude_none=True)


class WebhookConfigSchema(BaseModel):
    """Schema for Discord webhook configuration validation."""
    webhook_url: HttpUrl = Field(
        ...,
        description="Discord webhook URL"
    )
    username: str = Field(
        default="Mover Bot",
        min_length=1,
        max_length=ApiLimits.USERNAME_LENGTH,
        description="Webhook username"
    )
    avatar_url: Optional[HttpUrl] = Field(
        default=None,
        description="Webhook avatar URL"
    )
    forum: Optional[ForumConfigSchema] = Field(
        default=None,
        description="Optional forum channel configuration"
    )

    @field_validator('webhook_url')
    @classmethod
    def validate_webhook_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate Discord webhook URL format."""
        try:
            url_str = str(v)
            validate_url_length(url_str, "webhook_url")
            validate_url_domain(url_str, "webhook_url", ["discord.com"])
            validate_webhook_path(url_str)
            return v
        except ValueError as e:
            raise DiscordSchemaError(str(e), field="webhook_url") from e

    def to_webhook_config(self) -> WebhookConfig:
        """Convert to WebhookConfig dictionary."""
        config: WebhookConfig = {
            "url": str(self.webhook_url),
            "username": self.username,
        }

        if self.avatar_url:
            config["avatar_url"] = str(self.avatar_url)

        if self.forum and self.forum.enabled:
            config["forum"] = self.forum.to_dict()

        return config

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
