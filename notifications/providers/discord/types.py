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

from typing import List, Optional, TypedDict, Union
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from shared.providers.discord import (
    ApiLimits,
    DiscordColor,
    Embed,
    WebhookPayload,
    get_progress_color,
    DiscordWebhookError,
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


class NotificationState:
    """Track Discord notification provider state."""

    def __init__(self):
        """Initialize notification state."""
        self._lock = asyncio.Lock()
        self.disabled: bool = False
        self.rate_limited: bool = False
        self.rate_limit_until: float = 0
        self.last_error: Optional[DiscordWebhookError] = None
        self.last_error_time: Optional[datetime] = None
        self.last_success: Optional[datetime] = None
        self.last_update: float = 0
        self.consecutive_errors: int = 0
        self.total_errors: int = 0
        self.total_retries: int = 0

    async def update(self, **kwargs) -> None:
        """Thread-safe state update.

        Args:
            **kwargs: State attributes to update
        """
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.last_update = datetime.now().timestamp()

    @property
    def is_healthy(self) -> bool:
        """Check if provider is in a healthy state.

        Returns:
            bool: True if provider is healthy
        """
        return not (self.disabled or self.rate_limited)

    @property
    def can_retry(self) -> bool:
        """Check if provider can retry operations.

        Returns:
            bool: True if retries are allowed
        """
        if self.rate_limited:
            return datetime.now().timestamp() > self.rate_limit_until
        return not self.disabled


@dataclass
class RateLimitState:
    """Thread-safe rate limit tracking."""
    limit: int = 0
    remaining: int = 0
    reset_after: float = 0
    bucket: str = ""
    last_update: float = field(default_factory=lambda: datetime.now().timestamp())
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def update(self, **kwargs) -> None:
        """Thread-safe rate limit update.

        Args:
            **kwargs: Rate limit attributes to update
        """
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.last_update = datetime.now().timestamp()

    async def is_rate_limited(self) -> bool:
        """Thread-safe rate limit check.

        Returns:
            bool: True if currently rate limited
        """
        async with self._lock:
            if self.remaining > 0:
                return False
            if not self.reset_after:
                return False
            elapsed = datetime.now().timestamp() - self.last_update
            return elapsed < self.reset_after


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
    'NotificationState',
    'RateLimitState',
]

# Rate limiting constants specific to notifications
RATE_LIMIT = {
    "max_retries": 3,    # Maximum number of retry attempts
    "retry_delay": 5,    # Delay between retries in seconds
    "rate_limit": 30,    # Maximum requests per rate period
    "rate_period": 60,   # Rate limit period in seconds
}
