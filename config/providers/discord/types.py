# config/providers/discord/types.py

"""
Type definitions specific to Discord webhook configuration.
Contains types used for sending notifications, importing shared types as needed.

Example:
    >>> from config.providers.discord.types import WebhookConfig
    >>> config = WebhookConfig(url="https://discord.com/api/webhooks/...", username="Bot")
"""

from typing import Optional, TypedDict

from config.constants import JsonDict
from shared.types.discord import (
    ApiLimits,
    DiscordColor,
    Embed,
    WebhookPayload,
)


class WebhookConfig(TypedDict, total=False):
    """Discord webhook configuration structure."""
    url: str
    username: str
    avatar_url: Optional[str]
    embed_color: Optional[int]
    thread_name: Optional[str]
    content: Optional[str]


class WebhookResponse(TypedDict):
    """Discord webhook response structure."""
    id: str
    type: int
    channel_id: str
    content: Optional[str]
    embeds: list[Embed]
    author: Optional[JsonDict]
    timestamp: str


class RateLimitInfo(TypedDict):
    """Discord API rate limit information."""
    limit: int
    remaining: int
    reset_after: float
    bucket: str
    reset_time: str


# Default webhook configuration
DEFAULT_WEBHOOK_CONFIG = {
    "username": "Mover Bot",
    "embed_color": DiscordColor.INFO
}

# Webhook API constraints
WEBHOOK_CONSTRAINTS = {
    "max_retries": 3,
    "retry_delay": 5,
    "max_embeds": ApiLimits.EMBEDS_PER_MESSAGE,
    "max_username_length": ApiLimits.USERNAME_LENGTH,
    "webhook_timeout": 30,
}

__all__ = [
    'WebhookConfig',
    'WebhookResponse',
    'RateLimitInfo',
    'DEFAULT_WEBHOOK_CONFIG',
    'WEBHOOK_CONSTRAINTS',
    'ApiLimits',
    'DiscordColor',
    'Embed',
    'WebhookPayload',
]
