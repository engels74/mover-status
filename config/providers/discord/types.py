# config/providers/discord/types.py

"""
Type definitions specific to Discord webhook configuration.
Contains types used for sending notifications, importing shared types as needed.

Example:
    >>> from config.providers.discord.types import WebhookConfig
    >>> config = WebhookConfig(url="https://discord.com/api/webhooks/...", username="Bot")
"""

from typing import Final, Literal, Optional, Set, TypedDict

from config.constants import JsonDict
from shared.providers.discord import (
    ApiLimits,
    DiscordColor,
    Embed,
    WebhookPayload,
)


class ForumConfig(TypedDict, total=False):
    """Configuration for Discord forum channel integration."""
    enabled: bool
    auto_thread: bool
    default_thread_name: Optional[str]
    archive_duration: Optional[int]  # Thread auto-archive duration in minutes


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

# Allowed domains for webhooks and assets
ALLOWED_DOMAINS: Final[Set[str]] = frozenset({
    "discord.com",
    "ptb.discord.com",
    "canary.discord.com"
})

ALLOWED_ASSET_DOMAINS: Final[Set[str]] = frozenset({
    "cdn.discordapp.com",
    "media.discordapp.net",
    "i.imgur.com"
})

# Default webhook configuration
DEFAULT_WEBHOOK_CONFIG: Final[WebhookConfig] = {
    "username": "Mover Bot",
    "embed_color": DiscordColor.INFO
}

# Forum configuration defaults
DEFAULT_FORUM_CONFIG: Final[ForumConfig] = {
    "enabled": False,
    "auto_thread": False,
    "archive_duration": 1440  # 24 hours in minutes
}

# Webhook API constraints
WEBHOOK_CONSTRAINTS: Final[JsonDict] = {
    "max_retries": 3,
    "retry_delay": 5,
    "max_embeds": ApiLimits.EMBEDS_PER_MESSAGE,
    "max_username_length": ApiLimits.USERNAME_LENGTH,
    "webhook_timeout": 30,
    "allowed_domains": ALLOWED_DOMAINS,
    "allowed_asset_domains": ALLOWED_ASSET_DOMAINS,
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
    'ALLOWED_DOMAINS',
    'ALLOWED_ASSET_DOMAINS',

    # Re-exports from shared types
    'ApiLimits',
    'DiscordColor',
    'Embed',
    'WebhookPayload',
]
