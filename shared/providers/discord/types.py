# shared/providers/discord/types.py

"""
Shared type definitions for Discord integration.
Contains types used by both configuration and notification components.
Provides constants, TypedDict classes, and utility functions for Discord webhook API.

Example:
    >>> from shared.providers.discord import DiscordColor, Embed
    >>> color = DiscordColor.SUCCESS
    >>> embed = {"title": "Test", "description": "Message", "color": color}
"""

from enum import IntEnum
from typing import Any, Dict, List, Literal, Optional, TypedDict
from urllib.parse import urlparse


class DiscordColor(IntEnum):
    """Discord embed color codes."""
    SUCCESS = 0x2ECC71      # Green
    INFO = 0x3498DB         # Blue
    WARNING = 0xF1C40F      # Yellow
    ERROR = 0xE74C3C        # Red
    PROGRESS = 0x9B59B6     # Purple
    SYSTEM = 0x95A5A6       # Gray
    DEBUG = 0x34495E        # Dark Blue

    # Progress gradient colors (from red to green)
    PROGRESS_0 = 0xFF4136   # Red (0-10%)
    PROGRESS_10 = 0xFF6B6B  # Light Red (11-20%)
    PROGRESS_20 = 0xFF9F40  # Orange (21-30%)
    PROGRESS_30 = 0xFFA07A  # Light Orange (31-40%)
    PROGRESS_40 = 0xFFD700  # Gold (41-50%)
    PROGRESS_50 = 0xF1C40F  # Yellow (51-60%)
    PROGRESS_60 = 0xB8E986  # Light Green (61-70%)
    PROGRESS_70 = 0x90EE90  # Pale Green (71-80%)
    PROGRESS_80 = 0x98FB98  # Mint Green (81-90%)
    PROGRESS_90 = 0x2ECC71  # Green (91-100%)

class ApiLimit(IntEnum):
    """Discord API limits and constraints."""
    # Message Limits
    CONTENT_LENGTH = 2000      # Maximum message content length
    EMBEDS_PER_MESSAGE = 10    # Maximum embeds per message
    TOTAL_LENGTH = 6000        # Maximum combined length across all embeds
    COMPONENTS_PER_ROW = 5     # Maximum buttons/components per row
    ROWS_PER_MESSAGE = 5       # Maximum component rows per message

    # Embed Limits
    TITLE_LENGTH = 256         # Maximum embed title length
    DESCRIPTION_LENGTH = 4096   # Maximum embed description length
    FIELDS_COUNT = 25          # Maximum number of fields
    FIELD_NAME_LENGTH = 256    # Maximum field name length
    FIELD_VALUE_LENGTH = 1024   # Maximum field value length
    FOOTER_LENGTH = 2048       # Maximum footer text length
    AUTHOR_NAME_LENGTH = 256   # Maximum author name length

    # Webhook Limits
    USERNAME_LENGTH = 80       # Maximum webhook username length
    WEBHOOK_NAME_LENGTH = 32   # Maximum webhook name length
    CHANNEL_NAME_LENGTH = 100   # Maximum channel name length
    RATE_LIMIT_PER_SEC = 30    # Maximum webhook requests per second


class EmbedFooter(TypedDict, total=False):
    """Discord embed footer structure."""
    text: str
    icon_url: Optional[str]


class EmbedImage(TypedDict, total=False):
    """Discord embed image structure."""
    url: str
    proxy_url: Optional[str]
    height: Optional[int]
    width: Optional[int]


class EmbedThumbnail(TypedDict, total=False):
    """Discord embed thumbnail structure."""
    url: str
    proxy_url: Optional[str]
    height: Optional[int]
    width: Optional[int]


class EmbedVideo(TypedDict, total=False):
    """Discord embed video structure."""
    url: Optional[str]
    proxy_url: Optional[str]
    height: Optional[int]
    width: Optional[int]


class EmbedProvider(TypedDict, total=False):
    """Discord embed provider structure."""
    name: Optional[str]
    url: Optional[str]


class EmbedAuthor(TypedDict, total=False):
    """Discord embed author structure."""
    name: str
    url: Optional[str]
    icon_url: Optional[str]
    proxy_icon_url: Optional[str]


class EmbedField(TypedDict):
    """Discord embed field structure."""
    name: str
    value: str
    inline: Optional[bool]


class Embed(TypedDict, total=False):
    """Discord embed structure following official API specification."""
    title: Optional[str]
    type: Literal["rich"]  # Only "rich" is supported for webhook embeds
    description: Optional[str]
    url: Optional[str]
    timestamp: Optional[str]  # ISO8601 timestamp
    color: Optional[int]
    footer: Optional[EmbedFooter]
    image: Optional[EmbedImage]
    thumbnail: Optional[EmbedThumbnail]
    video: Optional[EmbedVideo]
    provider: Optional[EmbedProvider]
    author: Optional[EmbedAuthor]
    fields: Optional[List[EmbedField]]


class WebhookPayload(TypedDict, total=False):
    """Discord webhook payload structure."""
    content: Optional[str]
    username: Optional[str]
    avatar_url: Optional[str]
    tts: Optional[bool]
    embeds: List[Embed]  # Changed from Optional[List[Embed]] as it's always required
    allowed_mentions: Optional[dict]
    components: Optional[List[dict]]
    flags: Optional[int]
    thread_name: Optional[str]


class DiscordWebhookError(Exception):
    """Exception raised for Discord webhook errors.

    This exception is raised when a webhook request fails, providing context
    about the error and any rate limiting information.

    Args:
        message (str): Error description
        code (Optional[int]): HTTP status code if applicable
        context (Optional[Dict[str, Any]]): Additional error context
        retry_after (Optional[float]): Seconds to wait before retry if rate limited

    Example:
        >>> raise DiscordWebhookError(
        ...     "Rate limit exceeded",
        ...     code=429,
        ...     context={"bucket": "global"},
        ...     retry_after=5.0
        ... )
    """

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        retry_after: Optional[float] = None
    ):
        super().__init__(message)
        self.code = code
        self.context = context or {}
        self.retry_after = retry_after

    def __str__(self) -> str:
        """Format error message with context."""
        parts = [f"{self.args[0]}"]
        if self.code:
            parts.append(f"(Status: {self.code})")
        if self.context:
            parts.append(f"Context: {self.context}")
        if self.retry_after:
            parts.append(f"Retry after: {self.retry_after}s")
        return " ".join(parts)


# Type aliases for domain sets
WebhookDomains = frozenset[str]
AssetDomains = frozenset[str]

# Allowed domains for webhooks and assets
WEBHOOK_DOMAINS: WebhookDomains = frozenset({
    "discord.com",
    "discordapp.com",
    "discord.gg"
})

ASSET_DOMAINS: AssetDomains = frozenset({
    "cdn.discordapp.com",
    "media.discordapp.net",
    "i.imgur.com"
})


def get_progress_color(percent: float) -> int:
    """Get appropriate color based on progress percentage.

    Args:
        percent: Progress percentage (0-100)

    Returns:
        int: Discord color code

    Raises:
        ValueError: If percentage is out of valid range
    """
    if not 0 <= percent <= 100:
        raise ValueError("Progress percentage must be between 0 and 100")

    # Define color brackets
    brackets = [
        (10, DiscordColor.PROGRESS_0),
        (20, DiscordColor.PROGRESS_10),
        (30, DiscordColor.PROGRESS_20),
        (40, DiscordColor.PROGRESS_30),
        (50, DiscordColor.PROGRESS_40),
        (60, DiscordColor.PROGRESS_50),
        (70, DiscordColor.PROGRESS_60),
        (80, DiscordColor.PROGRESS_70),
        (90, DiscordColor.PROGRESS_80),
        (100, DiscordColor.PROGRESS_90)
    ]

    # Find appropriate color bracket
    for threshold, color in brackets:
        if percent <= threshold:
            return color

    return DiscordColor.PROGRESS_90  # Fallback for 100%


def validate_url(url: str, allowed_domains: WebhookDomains | AssetDomains) -> bool:
    """Validate URL against allowed domains.

    Args:
        url: URL to validate
        allowed_domains: Set of allowed domain names

    Returns:
        bool: True if URL is valid and from allowed domain

    Example:
        >>> allowed = {"discord.com", "cdn.discord.com"}
        >>> validate_url("https://discord.com/api/webhooks/123", allowed)
        True
    """
    try:
        parsed = urlparse(url)
        return bool(
            parsed.scheme in {"http", "https"}
            and any(domain in parsed.netloc for domain in allowed_domains)
        )
    except Exception:
        return False


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to maximum length with suffix.

    Args:
        text: String to truncate
        max_length: Maximum allowed length
        suffix: String to append when truncating

    Returns:
        str: Truncated string

    Example:
        >>> truncate_string("Very long text", 8)
        'Very ...'
    """
    if len(text) <= max_length:
        return text
    return text[:(max_length - len(suffix))] + suffix
