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
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from config.providers.discord.types import (
    DEFAULT_WEBHOOK_CONFIG,
    WebhookConfig,
)
from shared.types.discord import (
    ApiLimits,
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
    inline: bool = Field(
        default=False,
        description="Display field inline"
    )

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
        default=DEFAULT_WEBHOOK_CONFIG["embed_color"],
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
    timestamp: Optional[datetime] = Field(
        default=None,
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

    def to_dict(self) -> Dict:
        """Convert embed to Discord API format."""
        data = self.model_dump(exclude_none=True)
        if self.timestamp:
            data['timestamp'] = self.timestamp.isoformat()
        return data


class WebhookConfigSchema(BaseModel):
    """Schema for Discord webhook configuration validation."""
    webhook_url: HttpUrl = Field(
        ...,
        description="Discord webhook URL"
    )
    username: str = Field(
        default=DEFAULT_WEBHOOK_CONFIG["username"],
        min_length=1,
        max_length=ApiLimits.USERNAME_LENGTH,
        description="Webhook username"
    )
    avatar_url: Optional[HttpUrl] = Field(
        default=None,
        description="Webhook avatar URL"
    )
    thread_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Thread name for forum posts"
    )

    @field_validator('webhook_url')
    @classmethod
    def validate_webhook_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate Discord webhook URL format."""
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

    def to_webhook_config(self) -> WebhookConfig:
        """Convert to WebhookConfig dictionary."""
        return {
            "url": str(self.webhook_url),
            "username": self.username,
            "avatar_url": str(self.avatar_url) if self.avatar_url else None,
            "thread_name": self.thread_name,
            "embed_color": DEFAULT_WEBHOOK_CONFIG["embed_color"]
        }

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "username": "Mover Bot",
                    "thread_name": "Mover Status Updates"
                }
            ]
        }
    }
