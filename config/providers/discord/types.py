# config/providers/discord/types.py

"""
Discord webhook types and constants.
Contains types used for sending notifications, importing shared types as needed.

Example:
    >>> from config.providers.discord.types import WebhookConfig
    >>> config = WebhookConfig(url="https://discord.com/api/webhooks/...", username="Bot")
"""

from typing import Final, Literal, Optional, TypedDict

from config.constants import JsonDict
from shared.providers.discord import (
    ASSET_DOMAINS,
    WEBHOOK_DOMAINS,
    ApiLimits,
    AssetDomains,
    DiscordColor,
    DomainSet,
    Embed,
    WebhookDomains,
    WebhookPayload,
)


class ForumConfig(TypedDict, total=False):
    """Configuration for Discord forum channel integration."""
    enabled: bool
    channel_id: str
    thread_title: str


class WebhookConfig(TypedDict, total=False):
    """Discord webhook configuration structure."""
    url: str
    username: str
    avatar_url: Optional[str]
    embed_color: Optional[int]
    forum: Optional[ForumConfig]  # Optional forum settings


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


# HTTP Methods and Content Types
HttpMethod = Literal["GET", "POST", "PATCH", "DELETE"]
ContentType = Literal["application/json"]

# Webhook API constraints
WEBHOOK_CONSTRAINTS: Final[JsonDict] = {
    "max_retries": 3,
    "retry_delay": 5,
    "max_embeds": ApiLimits.EMBEDS_PER_MESSAGE,
    "max_username_length": ApiLimits.USERNAME_LENGTH,
    "webhook_timeout": 30,
    "allowed_domains": WEBHOOK_DOMAINS,
    "allowed_asset_domains": ASSET_DOMAINS,
}

# Default webhook configuration
DEFAULT_WEBHOOK_CONFIG: Final[WebhookConfig] = {
    "username": "Mover Bot",
    "embed_color": DiscordColor.INFO
}

# Forum configuration defaults
DEFAULT_FORUM_CONFIG: Final[ForumConfig] = {
    "enabled": False,
    "channel_id": "",
    "thread_title": ""
}


class WebhookError(TypedDict, total=False):
    """Discord webhook error response structure."""
    code: int
    message: str
    errors: Optional[JsonDict]


class WebhookValidation(TypedDict, total=False):
    """Discord webhook validation result structure."""
    valid: bool
    errors: list[str]
    details: Optional[JsonDict]


__all__ = [
    # Type definitions
    'ForumConfig',
    'WebhookConfig',
    'WebhookResponse',
    'RateLimitInfo',
    'WebhookError',
    'WebhookValidation',
    'HttpMethod',
    'ContentType',

    # Constants
    'DEFAULT_WEBHOOK_CONFIG',
    'DEFAULT_FORUM_CONFIG',
    'WEBHOOK_CONSTRAINTS',

    # Re-exports from shared types
    'ApiLimits',
    'DiscordColor',
    'Embed',
    'WebhookPayload',
    'DomainSet',
    'WebhookDomains',
    'AssetDomains',
]
