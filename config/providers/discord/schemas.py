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

import re
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from shared.types.discord import (
    ApiLimits,
    DiscordColor,
    WebhookPayload,
)


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
    inline: bool = Field(default=False, description="Display field inline")

    @model_validator(mode='after')
    def validate_content(self) -> 'EmbedFieldSchema':
        """Validate field content is not empty after trimming."""
        if not self.name.strip() or not self.value.strip():
            raise ValueError("Field name and value cannot be empty or whitespace")
        return self


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
        if v:
            hostname = urlparse(str(v)).hostname or ""
            allowed_domains = {"cdn.discordapp.com", "i.imgur.com", "media.discordapp.net"}
            if not any(domain in hostname for domain in allowed_domains):
                raise ValueError("Icon URL must be from Discord or Imgur domains")
        return v


class EmbedAuthorSchema(BaseModel):
    """Schema for Discord embed author validation."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=ApiLimits.AUTHOR_NAME_LENGTH,
        description="Author name"
    )
    url: Optional[HttpUrl] = Field(
        default=None,
        description="Author URL"
    )
    icon_url: Optional[HttpUrl] = Field(
        default=None,
        description="Author icon URL"
    )


class EmbedSchema(BaseModel):
    """Schema for Discord embed validation."""
    title: Optional[str] = Field(
        default=None,
        max_length=ApiLimits.TITLE_LENGTH,
        description="Embed title"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=ApiLimits.DESCRIPTION_LENGTH,
        description="Embed description"
    )
    url: Optional[HttpUrl] = Field(
        default=None,
        description="Embed URL"
    )
    color: Optional[int] = Field(
        default=None,
        ge=0,
        le=0xFFFFFF,
        description="Embed color (hex)"
    )
    fields: List[EmbedFieldSchema] = Field(
        default_factory=list,
        max_length=ApiLimits.FIELDS_COUNT,
        description="Embed fields"
    )
    footer: Optional[EmbedFooterSchema] = Field(
        default=None,
        description="Embed footer"
    )
    author: Optional[EmbedAuthorSchema] = Field(
        default=None,
        description="Embed author"
    )
    timestamp: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$",
        description="ISO8601 timestamp"
    )

    @model_validator(mode='after')
    def validate_embed(self) -> 'EmbedSchema':
        """Validate total embed length and content requirements."""
        total_length = 0
        if self.title:
            total_length += len(self.title)
        if self.description:
            total_length += len(self.description)
        if self.footer:
            total_length += len(self.footer.text)
        if self.author:
            total_length += len(self.author.name)
        for field in self.fields:
            total_length += len(field.name) + len(field.value)

        if total_length > ApiLimits.TOTAL_LENGTH:
            raise ValueError(f"Total embed length exceeds {ApiLimits.TOTAL_LENGTH} characters")

        # Ensure at least one of title, description, or fields is present
        if not any([self.title, self.description, self.fields]):
            raise ValueError("Embed must contain at least one of: title, description, or fields")

        return self


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
    rate_limit: int = Field(
        default=30,
        ge=1,
        le=60,
        description="Rate limit per minute"
    )
    rate_period: int = Field(
        default=60,
        ge=30,
        le=3600,
        description="Rate limit period in seconds"
    )
    retry_attempts: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum retry attempts"
    )
    retry_delay: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Delay between retries in seconds"
    )

    @field_validator('webhook_url')
    @classmethod
    def validate_webhook_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate Discord webhook URL format and domain."""
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

        if not re.match(r"^[A-Za-z0-9_-]+$", token):
            raise ValueError("Invalid webhook token format")

        return v

    @field_validator('avatar_url')
    @classmethod
    def validate_avatar_url(cls, v: Optional[HttpUrl]) -> Optional[HttpUrl]:
        """Validate avatar URL format and domain."""
        if v:
            parsed = urlparse(str(v))
            allowed_domains = {"cdn.discordapp.com", "i.imgur.com"}
            if not any(domain in parsed.netloc for domain in allowed_domains):
                raise ValueError("Avatar URL must be from Discord or Imgur domains")
        return v

    class Config:
        """Pydantic model configuration."""
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


def validate_webhook_payload(payload: WebhookPayload) -> bool:
    """Validate webhook payload against Discord limits.

    Args:
        payload: Webhook payload to validate

    Returns:
        bool: True if payload is valid

    Raises:
        ValueError: If payload exceeds Discord limits
    """
    if len(payload.get("embeds", [])) > ApiLimits.EMBEDS_PER_MESSAGE:
        raise ValueError(f"Maximum of {ApiLimits.EMBEDS_PER_MESSAGE} embeds allowed")

    if "content" in payload and len(payload["content"]) > ApiLimits.CONTENT_LENGTH:
        raise ValueError(f"Content exceeds {ApiLimits.CONTENT_LENGTH} characters")

    if "username" in payload and len(payload["username"]) > ApiLimits.USERNAME_LENGTH:
        raise ValueError(f"Username exceeds {ApiLimits.USERNAME_LENGTH} characters")

    total_size = len(str(payload))  # Simple size estimation
    if total_size > 8192:  # Discord's approximate payload size limit
        raise ValueError("Webhook payload too large")

    return True


def get_color_for_status(status: str) -> int:
    """Get appropriate color for status messages.

    Args:
        status: Status identifier

    Returns:
        int: Discord color code
    """
    status_colors = {
        "success": DiscordColor.SUCCESS,
        "warning": DiscordColor.WARNING,
        "error": DiscordColor.ERROR,
        "info": DiscordColor.INFO
    }
    return status_colors.get(status.lower(), DiscordColor.INFO)
