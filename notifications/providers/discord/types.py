# notifications/providers/discord/types.py

"""
Type definitions specific to Discord webhook notifications.
Contains types used for sending notifications, importing shared types as needed.

Example:
    >>> from notifications.discord.types import NotificationContext
    >>> context = NotificationContext(
    ...     webhook_url="https://discord.com/api/webhooks/123/abc",
    ...     forum_enabled=True
    ... )
"""

from typing import List, Optional, TypedDict

from shared.providers.discord import (
    ApiLimits,
    DiscordColor,
    Embed,
    WebhookPayload,
    get_progress_color,
)


class NotificationContext(TypedDict, total=False):
    """Additional context for Discord notifications."""
    mention_roles: List[str]
    mention_users: List[str]
    mention_everyone: bool
    suppress_embeds: bool
    forum_enabled: bool  # Added to track forum usage in context


class NotificationResponse(TypedDict):
    """Discord webhook response structure."""
    id: str
    type: int
    channel_id: str
    content: Optional[str]
    timestamp: str
    thread_id: Optional[str]  # Added to capture created thread ID if applicable


class RateLimitInfo(TypedDict):
    """Discord API rate limit information."""
    limit: int
    remaining: int
    reset_after: float
    bucket: str


class ForumThreadInfo(TypedDict, total=False):
    """Information about created Discord forum threads."""
    thread_id: str
    thread_name: str
    archived: bool
    archive_timestamp: Optional[str]
    auto_archive_duration: int  # in minutes


# Re-export commonly used items
__all__ = [
    'NotificationContext',
    'NotificationResponse',
    'RateLimitInfo',
    'ForumThreadInfo',
    'ApiLimits',
    'DiscordColor',
    'Embed',
    'WebhookPayload',
    'get_progress_color',
]

# Rate limiting constants specific to notifications
RATE_LIMIT = {
    "max_retries": 3,    # Maximum number of retry attempts
    "retry_delay": 5,    # Delay between retries in seconds
    "rate_limit": 30,    # Maximum requests per rate period
    "rate_period": 60,   # Rate limit period in seconds
}
